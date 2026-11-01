"""
NewGenHealthAI — api/image_api.py
Medical image classification endpoint with secure upload validation,
bounded inference capacity, lazy specialist model execution, and sanitized diagnostics.
"""

import asyncio
import io
import os
from typing import Dict, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from app.core.config import (
    ENABLE_BLIP_CAPTIONING,
    INFERENCE_QUEUE_TIMEOUT_SECONDS,
    MAX_CONCURRENT_INFERENCE,
)
from app.core.dependencies import get_current_user
from app.core.logging_config import logger
from app.models.message import User
from app.tools.image_preprocess import (
    ImageValidationError,
    safe_decode_and_sanitize_image,
    validate_and_read_image_upload,
)

router = APIRouter()

try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    torch = None
    device = "cpu"


# ─────────────────────────────────────────────────────────────
#  Inference Concurrency & Capacity Protection
# ─────────────────────────────────────────────────────────────

class InferenceCapacityManager:
    """
    Process-local bounded concurrency manager for heavy model operations.
    Enforces:
    1. Global inference execution capacity via asyncio.Semaphore
    2. Per-user active request limit to prevent resource exhaustion / abuse
    3. Bounded queue wait timeout (returns HTTP 503 rather than accumulating indefinitely)
    4. Guaranteed permit release on timeout, cancellation, or error
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_INFERENCE,
        queue_timeout: float = INFERENCE_QUEUE_TIMEOUT_SECONDS,
    ):
        self.semaphore = asyncio.Semaphore(max(1, max_concurrent))
        self.queue_timeout = queue_timeout
        self._active_users: Dict[int, int] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: int):
        """Acquire a concurrency permit for the user within bounded timeout."""
        # 1. Enforce per-user limit (max 1 active inference per user)
        async with self._lock:
            current_active = self._active_users.get(user_id, 0)
            if current_active >= 1:
                logger.warning("User %d exceeded concurrent inference limit (active=%d)", user_id, current_active)
                raise HTTPException(
                    status_code=429,
                    detail="You already have an image analysis request in progress. Please wait for it to complete.",
                )
            self._active_users[user_id] = current_active + 1

        # 2. Acquire global capacity semaphore within timeout
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.queue_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            # Revert user counter on failure to acquire capacity permit
            async with self._lock:
                self._active_users[user_id] = max(0, self._active_users.get(user_id, 1) - 1)
                if self._active_users[user_id] <= 0:
                    self._active_users.pop(user_id, None)
            if isinstance(exc, asyncio.TimeoutError):
                logger.warning("Inference capacity timeout: all %d slots occupied", MAX_CONCURRENT_INFERENCE)
                raise HTTPException(
                    status_code=503,
                    detail="The image analysis service is currently operating at maximum capacity. Please try again shortly.",
                )
            raise

        return _InferencePermit(self, user_id)


class _InferencePermit:
    """Context manager guaranteeing permit release and user counter decrement."""

    def __init__(self, manager: InferenceCapacityManager, user_id: int):
        self.manager = manager
        self.user_id = user_id
        self._released = False

    async def release(self):
        if not self._released:
            self._released = True
            self.manager.semaphore.release()
            async with self.manager._lock:
                if self.user_id in self.manager._active_users:
                    self.manager._active_users[self.user_id] = max(
                        0, self.manager._active_users[self.user_id] - 1
                    )
                    if self.manager._active_users[self.user_id] <= 0:
                        self.manager._active_users.pop(self.user_id, None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


# Module-level capacity manager singleton
inference_capacity_manager = InferenceCapacityManager()


# ─────────────────────────────────────────────────────────────
#  BLIP Model (Strictly Optional, Disabled by Default)
# ─────────────────────────────────────────────────────────────

_blip_processor = None
_blip_model = None


def _get_blip():
    """
    Lazy-load BLIP only if ENABLE_BLIP_CAPTIONING=true.
    Never attempts unrequested multi-GB downloads by default.
    """
    global _blip_processor, _blip_model
    if not ENABLE_BLIP_CAPTIONING:
        return None, None

    if _blip_processor is None:
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            logger.info("Loading BLIP model for non-medical image captioning...")
            _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            _blip_model.to(device)
            logger.info("BLIP loaded successfully on %s", device)
        except Exception as e:
            logger.warning("BLIP model initialization failed: %s", type(e).__name__)
            return None, None
    return _blip_processor, _blip_model


# ─────────────────────────────────────────────────────────────
#  Educational Medical Information Retrieval
# ─────────────────────────────────────────────────────────────

def get_medical_info(
    disease_name: str,
    category: str,
    finding_type: str = "condition_detected",
    is_negative: bool = False,
) -> dict:
    """
    Generate balanced, non-diagnostic educational information for a detected condition.
    Never states confirmed diagnoses, physician impersonation, or prescription drug dosages.
    """
    if is_negative or finding_type == "normal_or_negative":
        return {
            "raw": (
                "The model identified features matching normal reference imagery. "
                "No pathological symptoms or treatments apply to a normal reference finding."
            )
        }
    if finding_type == "anatomy_identified":
        return {
            "raw": (
                "The model identified an anatomical location. "
                "No disease pathology or fracture was classified for this image."
            )
        }
    if not disease_name or disease_name.lower().strip() in ("none", "unknown", "inconclusive"):
        return {"raw": "No specific educational literature is available for this finding."}

    from app.tools.vector_store import get_retriever
    from app.tools.llm_client import get_llm

    retriever = get_retriever()
    llm = get_llm()

    if not llm:
        return {"raw": "Educational medical information service is temporarily unavailable."}

    rag_context = ""
    if retriever:
        try:
            query = f"{disease_name} symptoms causes management"
            docs = retriever.invoke(query)
            if docs:
                rag_context = "\n\n".join([d.page_content for d in docs[:3]])
        except Exception as e:
            logger.warning("RAG retrieval failed for medical details: %s", type(e).__name__)

    category_label = {
        "skin": "Dermatological Condition",
        "xray": "Radiographic Finding",
        "retina": "Retinal / Ocular Finding",
        "general": "General Medical Finding",
    }.get(category, "Medical Observation")

    prompt = (
        "You are NewGenHealthAI, an automated medical education and informational assistant. "
        "You are NOT a doctor and have NOT performed a physical examination.\n\n"
        f"An automated image analysis prototype detected visual patterns suggestive of **{disease_name}** "
        f"(Category: {category_label}). This is a prototype finding and does NOT constitute a clinical diagnosis.\n\n"
    )

    if rag_context:
        prompt += (
            "Verified medical literature reference:\n"
            f"---\n{rag_context}\n---\n\n"
        )

    prompt += (
        "Provide objective, evidence-based educational discussion points with the following sections:\n"
        "## Educational Overview\nBrief description of this visual condition.\n\n"
        "## Common Symptoms\nTypical symptoms documented in medical literature.\n\n"
        "## Known Causes & Risk Factors\nDocumented risk factors.\n\n"
        "## Discussion Points for Your Doctor\nQuestions to ask a qualified healthcare professional.\n\n"
        "Strict rules:\n"
        "- Do not state that the patient has this disease.\n"
        "- Do not prescribe drugs, recommend specific dosages, or suggest self-treatment.\n"
        "- Include a clear medical disclaimer that this information is educational only."
    )

    try:
        response = llm.invoke(prompt)
        text = response.content.strip() if hasattr(response, "content") else str(response).strip()
        return {"raw": text}
    except Exception as e:
        logger.error("Error generating educational info for %s: %s", disease_name, type(e).__name__)
        return {"raw": "Could not retrieve detailed educational information at this time."}


# ─────────────────────────────────────────────────────────────
#  Sanitized Operational Diagnostics Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/diagnostics")
async def get_diagnostics():
    """
    Operational readiness check for vision service models.
    Does NOT leak internal filesystem paths, directory structures, or deployment secrets.
    """
    try:
        from app.services.disease_classifier import disease_classifier
        loaded_models = [k for k, v in disease_classifier.model_status.items() if v == "ready"]
        status_map = {
            kw: disease_classifier.model_status.get(kw, "unavailable")
            for kw in ["skin", "xray", "retina", "general"]
        }
        device_str = str(disease_classifier.device)
    except Exception as e:
        logger.warning("Diagnostics check: vision models unavailable (%s)", type(e).__name__)
        loaded_models = []
        status_map = {kw: "unavailable" for kw in ["skin", "xray", "retina", "general"]}
        device_str = "cpu"

    return {
        "status": "ready" if len(loaded_models) > 0 else "degraded",
        "service": "NewGenHealthAI Vision Service",
        "loaded_models_count": len(loaded_models),
        "models": status_map,
        "device": device_str,
    }


# ─────────────────────────────────────────────────────────────
#  Main Secure Image Analysis Endpoint
# ─────────────────────────────────────────────────────────────

@router.post("/api/v1/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Classify uploaded medical image with strict modality locking, safe negative-class handling,
    uncalibrated model scores, bounded upload reading, and inference concurrency protection.
    """
    # ── 1. Acquire Bounded Inference Capacity Permit ──
    try:
        permit = await inference_capacity_manager.acquire(current_user.id)
    except HTTPException as he:
        status_val = "model_unavailable" if he.status_code == 503 else "rate_limited"
        return JSONResponse(
            status_code=he.status_code,
            content={
                "status": status_val,
                "success": False,
                "message": he.detail,
            },
        )

    image = None
    async with permit:
        # ── 2. Secure Upload Validation & Bounded Reading ──
        try:
            contents = await validate_and_read_image_upload(file)
            image = safe_decode_and_sanitize_image(contents)
        except ImageValidationError as ive:
            return JSONResponse(
                status_code=ive.status_code,
                content={
                    "status": ive.status,
                    "success": False,
                    "error": ive.message,
                },
            )
        except Exception as e:
            logger.warning("Image decoding failed unexpectedly: %s", type(e).__name__)
            return JSONResponse(
                status_code=400,
                content={
                    "status": "invalid_image",
                    "success": False,
                    "error": "The uploaded file could not be decoded as a valid image.",
                },
            )

        try:
            from app.services.disease_classifier import disease_classifier

            # ── 3. Execute Disease Classification in Worker Thread ──
            prediction = await asyncio.to_thread(disease_classifier.classify, image)
            status = prediction.get("status", "inconclusive")

            # ── 4. Handle 'model_unavailable' (HTTP 503) ──
            if status == "model_unavailable":
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "model_unavailable",
                        "success": False,
                        "category": prediction.get("category"),
                        "message": prediction.get(
                            "message",
                            "The required AI specialist model is not currently loaded on this server.",
                        ),
                        "domain_hint": prediction.get("domain_hint"),
                    },
                )

            # ── 5. Handle 'unsupported_image' (HTTP 422) ──
            if status == "unsupported_image":
                logger.info(
                    "Non-medical image detected (domain=%s, conf=%.3f)",
                    prediction.get("domain_hint"),
                    prediction.get("domain_confidence", 0.0),
                )
                caption = None
                try:
                    blip_proc, blip_mdl = _get_blip()
                    if blip_proc is not None and blip_mdl is not None:
                        inputs = blip_proc(images=image, return_tensors="pt").to(device)
                        output = blip_mdl.generate(**inputs, max_new_tokens=50)
                        caption = blip_proc.decode(output[0], skip_special_tokens=True)
                except Exception as blip_err:
                    logger.warning("BLIP captioning unavailable: %s", type(blip_err).__name__)

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

            # ── 6. Handle 'inconclusive' (HTTP 200) ──
            if status == "inconclusive":
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "inconclusive",
                        "success": False,
                        "message": prediction.get(
                            "message",
                            "Image analysis was inconclusive or visual features could not be reliably classified.",
                        ),
                        "category": prediction.get("category"),
                        "domain_hint": prediction.get("domain_hint"),
                        "domain_confidence": prediction.get("domain_confidence", 0.0),
                    },
                )

            # ── 7. Handle 'analysis_complete' (HTTP 200) ──
            disease = prediction.get("disease")
            category = prediction.get("category", "general")
            finding_type = prediction.get("finding_type", "condition_detected")
            is_negative = prediction.get("is_negative_finding", False)
            score = prediction.get("score", 0.0)

            medical_details = None
            if finding_type == "condition_detected" and not is_negative and disease:
                medical_info = get_medical_info(disease, category, finding_type=finding_type, is_negative=is_negative)
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
                "confidence": round(score, 4),  # Deprecated alias
                "calibrated_confidence": None,
                "score_interpretation": prediction.get(
                    "score_interpretation",
                    "Unvalidated prototype model score; not a calibrated clinical probability.",
                ),
                "predictions": prediction.get("predictions", []),
                "medical_details": medical_details,
                "clinical_note": prediction.get("clinical_note"),
                "domain_hint": prediction.get("domain_hint"),
                "domain_confidence": prediction.get("domain_confidence", 0.0),
            }

            return JSONResponse(status_code=200, content=response_body)

        except Exception as e:
            logger.error("Image analysis unexpected failure: %s", type(e).__name__)
            return JSONResponse(
                status_code=500,
                content={
                    "status": "inconclusive",
                    "success": False,
                    "error": "An internal error occurred while processing the image.",
                },
            )
        finally:
            if image is not None:
                try:
                    image.close()
                except Exception:
                    pass
