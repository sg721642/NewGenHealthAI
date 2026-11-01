from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io

from app.core.dependencies import get_current_user
from app.core.logging_config import logger
from app.models.message import User

router = APIRouter()

try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    torch = None
    device = "cpu"


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
    from app.tools.vector_store import get_retriever
    from app.tools.llm_client import get_llm

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
    from app.services.disease_classifier import disease_classifier

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
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Classify uploaded medical image with strict modality locking, safe negative-class handling,
    and uncalibrated model scores. Never fabricates clinical certainty or cross-modality diagnoses.
    """
    try:
        contents = await file.read()
        if not contents:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "invalid_image",
                    "success": False,
                    "error": "Empty file provided.",
                },
            )

        try:
            image = Image.open(io.BytesIO(contents)).convert("RGB")
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "invalid_image",
                    "success": False,
                    "error": "The uploaded file could not be decoded as a valid image.",
                },
            )

        from app.services.disease_classifier import disease_classifier

        # ── 1. Disease classification with hard modality lock ──
        prediction = disease_classifier.classify(image)
        status = prediction.get("status", "inconclusive")

        # ── 2. Handle 'model_unavailable' (HTTP 503) ──
        if status == "model_unavailable":
            return JSONResponse(
                status_code=503,
                content={
                    "status": "model_unavailable",
                    "success": False,
                    "category": prediction.get("category"),
                    "message": prediction.get(
                        "message",
                        "The required AI specialist model is not currently loaded on this server."
                    ),
                    "domain_hint": prediction.get("domain_hint"),
                },
            )

        # ── 3. Handle 'unsupported_image' (HTTP 422) ──
        if status == "unsupported_image":
            logger.info(
                "Non-medical or unsupported image detected (domain=%s, conf=%.3f) — generating descriptive caption",
                prediction.get("domain_hint"),
                prediction.get("domain_confidence", 0.0),
            )
            caption = None
            try:
                blip_proc, blip_mdl = _get_blip()
                inputs = blip_proc(images=image, return_tensors="pt").to(device)
                output = blip_mdl.generate(**inputs, max_new_tokens=50)
                caption = blip_proc.decode(output[0], skip_special_tokens=True)
            except Exception as blip_err:
                logger.warning("BLIP captioning unavailable: %s", blip_err)

            return JSONResponse(
                status_code=422,
                content={
                    "status": "unsupported_image",
                    "success": False,
                    "type": "general_image",
                    "category": "non_medical",
                    "description": caption or "The uploaded image does not appear to be a supported medical image.",
                    "domain_hint": prediction.get("domain_hint", "non_medical"),
                    "domain_confidence": prediction.get("domain_confidence", 0.0),
                },
            )

        # ── 4. Handle 'inconclusive' (HTTP 200) ──
        if status == "inconclusive":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "inconclusive",
                    "success": False,
                    "message": prediction.get(
                        "message",
                        "Image analysis was inconclusive or visual features could not be reliably classified."
                    ),
                    "category": prediction.get("category"),
                    "domain_hint": prediction.get("domain_hint"),
                    "domain_confidence": prediction.get("domain_confidence", 0.0),
                },
            )

        # ── 5. Handle 'analysis_complete' (HTTP 200) ──
        disease = prediction.get("disease")
        category = prediction.get("category", "general")
        finding_type = prediction.get("finding_type", "condition_detected")
        is_negative = prediction.get("is_negative_finding", False)
        score = prediction.get("score", 0.0)

        # Retrieve medical literature only for verified disease conditions, not normal or anatomy findings
        medical_details = None
        if finding_type == "condition_detected" and not is_negative and disease:
            medical_info = get_medical_info(disease, category)
            medical_details = medical_info.get("raw")
        elif is_negative:
            medical_details = (
                "The model identified features matching normal reference imagery. "
                "No pathological symptoms or treatments are applicable to a normal reference finding."
            )
        elif finding_type == "anatomy_identified":
            medical_details = (
                "The model identified the anatomical location. "
                "No disease pathology or fracture was classified for this image."
            )

        response_body = {
            "status": "analysis_complete",
            "success": True,
            "type": "medical_diagnosis",  # Backwards compatibility
            "category": category,
            "disease": disease,
            "finding_type": finding_type,
            "is_negative_finding": is_negative,
            "anatomical_region": prediction.get("anatomical_region"),
            "score": round(score, 4),
            "confidence": round(score, 4),  # Deprecated alias for raw uncalibrated score
            "calibrated_confidence": None,  # False calibration removed
            "score_interpretation": prediction.get(
                "score_interpretation",
                "Unvalidated prototype model score; not a calibrated clinical probability."
            ),
            "predictions": prediction.get("predictions", []),
            "medical_details": medical_details,
            "clinical_note": prediction.get("clinical_note"),
            "domain_hint": prediction.get("domain_hint"),
            "domain_confidence": prediction.get("domain_confidence", 0.0),
        }

        return JSONResponse(status_code=200, content=response_body)

    except Exception as e:
        logger.error("Image analysis unexpected error: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={
                "status": "inconclusive",
                "success": False,
                "error": "An internal error occurred while processing the image.",
            },
        )
