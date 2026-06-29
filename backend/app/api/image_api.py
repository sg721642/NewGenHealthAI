from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image
import io
import torch

from app.services.disease_classifier import disease_classifier
from app.tools.vector_store import get_retriever
from app.tools.llm_client import get_llm
from app.core.logging_config import logger

router = APIRouter()

device = "cuda" if torch.cuda.is_available() else "cpu"

# Initialize multi-model classifier at startup
disease_classifier.initialize_models()

# -------------------------------------------------------
# BLIP model — lazy-loaded, only used for non-medical images
# -------------------------------------------------------
_blip_processor = None
_blip_model = None


def _get_blip():
    """Lazy-load BLIP model only when needed (saves memory on startup)."""
    global _blip_processor, _blip_model
    if _blip_processor is None:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        logger.info("Lazy-loading BLIP model (non-medical image captioning)...")
        _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model.to(device)
        logger.info(f"BLIP loaded on: {device}")
    return _blip_processor, _blip_model


# ───────────────────────────────────────────────────────
#  Helper: RAG + LLM medical details
# ───────────────────────────────────────────────────────

def get_medical_info(disease_name: str, category: str) -> dict:
    """Retrieve symptoms, causes, and treatment using RAG + LLM."""
    retriever = get_retriever()
    llm = get_llm()

    if not llm:
        return {"raw": "Medical AI service is temporarily unavailable."}

    rag_context = ""
    if retriever:
        query = f"{disease_name} symptoms causes treatment"
        docs = retriever.invoke(query)
        if docs:
            rag_context = "\n\n".join([d.page_content for d in docs[:5]])

    category_label = {
        "skin": "Skin Disease",
        "xray": "X-ray / Fracture",
        "retina": "Retinal / Eye Disease",
        "general": "General Medical Condition",
    }.get(category, "Medical Condition")

    prompt = (
        "You are a compassionate and knowledgeable medical AI assistant.\n\n"
        f"A patient has uploaded a medical image. Our AI classifier has detected "
        f"**{disease_name}** (Category: {category_label}).\n\n"
    )

    if rag_context:
        prompt += (
            "Here is relevant information from our medical literature database:\n"
            f"---\n{rag_context}\n---\n\n"
        )

    prompt += (
        "Based on your medical knowledge and the literature above, provide a detailed "
        "response with the following sections:\n\n"
        "## Symptoms\nList the common symptoms of this condition.\n\n"
        "## Causes\nList the known causes and risk factors.\n\n"
        "## Treatment\nDescribe the recommended treatments and management options.\n\n"
        "## When to See a Doctor\nAdvise when professional consultation is necessary.\n\n"
        "Be clear, professional, and caring. Use bullet points where appropriate."
    )

    try:
        response = llm.invoke(prompt)
        text = response.content.strip() if hasattr(response, "content") else str(response)
        return {"raw": text}
    except Exception as e:
        logger.error(f"Error fetching medical info for {disease_name}: {str(e)}")
        return {"raw": "Could not retrieve detailed medical information at this time."}


# ───────────────────────────────────────────────────────
#  Diagnostics endpoint
# ───────────────────────────────────────────────────────

@router.get("/api/v1/diagnostics")
async def get_diagnostics():
    """Check which models are currently loaded in memory."""
    loaded = list(disease_classifier.models.keys())
    all_configs = disease_classifier.model_configs

    status = {}
    for kw in ["skin", "xray", "retina", "general"]:
        if kw in loaded:
            status[kw] = "LOADED"
        elif kw in all_configs:
            status[kw] = "ERROR (Check logs)"
        else:
            status[kw] = "NOT FOUND"

    return {
        "status": "ready" if len(loaded) > 0 else "degraded",
        "loaded_count": len(loaded),
        "models": status,
        "device": str(disease_classifier.device),
        "base_dir": disease_classifier.base_dir,
    }


# ───────────────────────────────────────────────────────
#  Main image analysis endpoint
# ───────────────────────────────────────────────────────

@router.post("/api/v1/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        # ── 1. Disease classification (CLIP routes to the right model) ──
        prediction = disease_classifier.classify(image)

        confidence = prediction.get("confidence", 0.0)
        calibrated_conf = prediction.get("calibrated_conf", 0.0)
        disease = prediction.get("disease")
        category = prediction.get("category", "non_medical")
        domain_hint = prediction.get("domain_hint", "unknown")

        response = {
            "success": True,
            "calibrated_confidence": round(calibrated_conf, 4),
            "domain_hint": domain_hint,
            "domain_scores": prediction.get("domain_scores", {}),
            "domain_confidence": prediction.get("domain_confidence", 0.0),
        }

        # ── 2. Medical image detected → return diagnosis ──
        # CLIP detected a medical domain AND a specialist model returned a disease
        if category != "non_medical" and disease:
            logger.info(
                f"DIAGNOSIS: {category} -> {disease} "
                f"(raw={confidence:.4f}, domain={domain_hint})"
            )
            response["type"] = "medical_diagnosis"
            response["category"] = category
            response["disease"] = disease
            response["confidence"] = round(confidence, 4)
            response["predictions"] = prediction.get("predictions", [])
            response["all_model_results"] = prediction.get("all_results", {})

            # Fetch detailed medical info via RAG + LLM
            medical_info = get_medical_info(disease, category)
            response["medical_details"] = medical_info["raw"]

        else:
            # ── 3. Non-medical image → BLIP caption ──
            logger.info(
                f"Non-medical image detected (domain={domain_hint}, "
                f"conf={prediction.get('domain_confidence', 0):.3f}) "
                f"— using BLIP caption"
            )
            try:
                blip_proc, blip_mdl = _get_blip()
                inputs = blip_proc(images=image, return_tensors="pt").to(device)
                output = blip_mdl.generate(**inputs, max_new_tokens=50)
                caption = blip_proc.decode(output[0], skip_special_tokens=True)
            except Exception as blip_err:
                logger.warning(f"BLIP fallback failed: {blip_err}")
                caption = "Could not generate image description."

            response["type"] = "general_image"
            response["description"] = caption
            response["confidence"] = round(confidence, 4) if confidence else 0.0

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )
