"""
NewGenHealthAI — api/image_api.py
Medical image classification endpoint with secure upload validation,
bounded inference capacity, lazy specialist model execution, and sanitized diagnostics.
"""

import asyncio
import io
import os
from typing import Dict, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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
                "The model identified the anatomical location. "
                "No disease pathology or fracture was classified for this image. "
                "Pathology, fracture presence, or internal skeletal abnormalities cannot be reliably determined by this prototype model. "
                "Anatomical classification does NOT establish that no fracture or abnormality exists. "
                "Formal clinical radiographic evaluation by a qualified physician or radiologist is required."
            )
        }
    if not disease_name or disease_name.lower().strip() in ("none", "unknown", "inconclusive"):
        return {"raw": "No specific educational literature is available for this finding."}

    try:
        from app.tools.vector_store import get_retriever
        retriever = get_retriever()
    except Exception:
        retriever = None

    try:
        from app.tools.llm_client import get_llm
        llm = get_llm()
    except Exception:
        llm = None

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
        if hasattr(response, "content"):
            raw_c = response.content
            text = str(raw_c.strip()) if hasattr(raw_c, "strip") else str(raw_c)
        else:
            text = str(response).strip()
        text = str(text)
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
    request: Request,
    file: UploadFile = File(...),
    modality: Optional[str] = Form(None),
    modality_confirmed: Optional[str] = Form(None),
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

    session_id = request.headers.get("X-Session-ID") if request else None
    if session_id and current_user:
        try:
            from app.services.database_service import db_service
            conv = db_service.get_conversation(session_id, current_user.id)
            if not conv and hasattr(db_service, "get_or_create_conversation"):
                db_service.get_or_create_conversation(session_id, current_user.id, title="Medical Image Consultation")
            elif conv and (not conv.title or conv.title.startswith("Consultation") or conv.title == "New Consultation"):
                conv.title = "Medical Image Consultation"
            db_service.save_message(session_id, "user", "Uploaded medical image for clinical analysis", user_id=current_user.id)
        except Exception as e:
            logger.warning("Could not persist image consultation start: %s", type(e).__name__)

    def _persist_assistant_msg(content: str):
        if session_id and current_user:
            try:
                from app.services.database_service import db_service
                db_service.save_message(session_id, "assistant", content, source="Vision Service", user_id=current_user.id)
            except Exception:
                pass

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
            clean_modality = None
            if modality and isinstance(modality, str):
                m_clean = modality.strip().lower()
                if m_clean in ("skin", "xray", "retina", "general"):
                    clean_modality = m_clean

            is_confirmed = False
            if modality_confirmed is not None:
                if isinstance(modality_confirmed, bool):
                    is_confirmed = modality_confirmed
                elif isinstance(modality_confirmed, str):
                    is_confirmed = modality_confirmed.strip().lower() in ("true", "1", "yes")

            prediction = await asyncio.to_thread(
                disease_classifier.classify,
                image,
                routed_category=clean_modality,
                modality_confirmed=is_confirmed,
            )
            status = prediction.get("status", "inconclusive")

            # ── 4. Handle 'general_recognition' (HTTP 200) ──
            if status == "general_recognition":
                detected_subj = prediction.get("detected_subject", "Visible Subject")
                detected_cat = prediction.get("detected_category", prediction.get("category", "non_medical"))
                raw_is_person = prediction.get("is_person")
                p_status = prediction.get(
                    "person_detection",
                    prediction.get(
                        "person_detection_status",
                        "unsupported" if raw_is_person is not True else "detected_portrait"
                    )
                )
                is_person = True if raw_is_person is True else None if p_status == "unsupported" or raw_is_person is None else False
                reason_not_applicable = prediction.get(
                    "reason_not_applicable",
                    "Everyday non-medical images are not applicable for medical diagnostic analysis."
                )
                safety_disclaimer = prediction.get("safety_disclaimer")
                desc = (
                    prediction.get("description")
                    or f"Visual recognition complete: {detected_subj}."
                )
                top1_class = prediction.get("top1_class") or prediction.get("top1_name")
                top1_prob = prediction.get("top1_prob")
                raw_score = prediction.get("raw_score") if prediction.get("raw_score") is not None else top1_prob
                predictions_list = prediction.get("predictions", [])

                persisted_text = (
                    f"## Universal Image Recognition\n\n"
                    f"**Detected Subject:** {detected_subj}\n\n"
                    f"**Visual Description:** {desc}\n\n"
                    f"> **Medical Analysis:** Not applicable.\n"
                    f"> *{reason_not_applicable}*\n"
                )
                if safety_disclaimer:
                    persisted_text += f"\n*Safety Policy: {safety_disclaimer}*\n"
                _persist_assistant_msg(persisted_text)

                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "general_recognition",
                        "success": True,
                        "type": "general_image",
                        "category": detected_cat,
                        "detected_category": detected_cat,
                        "detected_subject": detected_subj,
                        "description": desc,
                        "top1_class": top1_class,
                        "top1_name": top1_class,
                        "top1_prob": round(top1_prob, 4) if top1_prob is not None else None,
                        "raw_score": round(raw_score, 4) if raw_score is not None else None,
                        "score": round(raw_score, 4) if raw_score is not None else 0.0,
                        "predictions": predictions_list,
                        "is_person": is_person,
                        "person_detection": p_status,
                        "person_detection_status": p_status,
                        "person_detection_note": prediction.get(
                            "person_detection_note",
                            "Person presence could not be reliably determined. Closed-set object classifier does not support general person detection; does not confirm absence of human."
                        ),
                        "medical_applicable": False,
                        "reason_not_applicable": reason_not_applicable,
                        "safety_disclaimer": safety_disclaimer,
                        "vision_engine": prediction.get("vision_engine", "local_neural_vision"),
                        "vision_model": prediction.get("vision_model"),
                        "domain_hint": prediction.get("domain_hint", "non_medical"),
                        "domain_confidence": prediction.get("domain_confidence", 0.95),
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    },
                )

            # ── 4b. Handle 'modality_selection_required' (HTTP 200) ──
            if status == "modality_selection_required":
                msg_text = prediction.get(
                    "message",
                    "Automatic clinical routing is disabled to ensure patient safety. "
                    "If this is a medical image, please explicitly select the modality (Skin, X-ray, Retina) to proceed.",
                )
                detected_subj = prediction.get("detected_subject", "Unrecognized Visual Subject")
                persisted_text = (
                    f"## Medical Modality Selection Required\n\n"
                    f"**Detected Subject:** {detected_subj}\n\n"
                    f"{msg_text}\n\n"
                    f"> **Safety Notice:** *Autonomous routing using visual heuristics is disabled. "
                    f"Specialist models are only invoked upon explicit modality selection.*"
                )
                _persist_assistant_msg(persisted_text)

                top1_class = prediction.get("top1_class") or prediction.get("top1_name")
                top1_prob = prediction.get("top1_prob")
                raw_score = prediction.get("raw_score") if prediction.get("raw_score") is not None else top1_prob

                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "modality_selection_required",
                        "success": False,
                        "type": "medical_selection_required",
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                        "message": msg_text,
                        "category": prediction.get("category", "ambiguous"),
                        "detected_category": prediction.get("detected_category", "ambiguous"),
                        "detected_subject": detected_subj,
                        "description": prediction.get("description"),
                        "top1_class": top1_class,
                        "top1_name": top1_class,
                        "top1_prob": round(top1_prob, 4) if top1_prob is not None else None,
                        "raw_score": round(raw_score, 4) if raw_score is not None else None,
                        "predictions": prediction.get("predictions", []),
                        "medical_applicable": False,
                        "modality_source": "auto_intake_abstention",
                        "vision_engine": prediction.get("vision_engine", "local_neural_vision"),
                        "domain_hint": prediction.get("domain_hint", "ambiguous"),
                        "domain_confidence": prediction.get("domain_confidence", 0.0),
                    },
                )

            # ── 4c. Handle 'clinical_analysis_disabled' (HTTP 200) ──
            if status == "clinical_analysis_disabled":
                msg_text = prediction.get(
                    "message",
                    "Clinical specialist analysis is disabled in this release pending formal clinical validation "
                    "and regulatory review. General image recognition remains available."
                )
                persisted_text = (
                    f"## Clinical Specialist Analysis Unavailable\n\n"
                    f"{msg_text}\n\n"
                    f"> **Governance Notice:** *This system is NOT clinically validated. "
                    f"Diagnostic specialist models are disabled by default in production.*"
                )
                _persist_assistant_msg(persisted_text)
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "clinical_analysis_disabled",
                        "success": False,
                        "type": "clinical_disabled",
                        "message": msg_text,
                        "category": prediction.get("category"),
                        "clinical_governance_status": "NOT_CLINICALLY_VALIDATED",
                        "medical_applicable": False,
                        "safety_notice": "Unvalidated diagnostic specialist models are disabled by default in production.",
                    },
                )

            # ── 4d. Handle 'modality_confirmation_required' (HTTP 200) ──
            if status == "modality_confirmation_required":
                msg_text = prediction.get(
                    "message",
                    "Explicit confirmation required: Please confirm that the uploaded image matches the selected modality for research evaluation."
                )
                disclaimer = prediction.get(
                    "research_disclaimer",
                    "RESEARCH ONLY — NOT FOR CLINICAL USE: This prototype model has not undergone clinical validation."
                )
                detected_subj = prediction.get("detected_subject", "Medical Specimen")
                persisted_text = (
                    f"## Research Modality Confirmation Required\n\n"
                    f"**Selected Modality:** {prediction.get('category', clean_modality)}\n\n"
                    f"{msg_text}\n\n"
                    f"> **Research Disclaimer:** *{disclaimer}*"
                )
                _persist_assistant_msg(persisted_text)

                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "modality_confirmation_required",
                        "success": False,
                        "type": "confirmation_required",
                        "message": msg_text,
                        "category": prediction.get("category", clean_modality),
                        "requires_confirmation": True,
                        "research_disclaimer": disclaimer,
                        "detected_subject": detected_subj,
                        "description": prediction.get("description"),
                        "medical_applicable": False,
                        "is_person": None,
                        "person_detection": "unsupported",
                        "person_detection_status": "unsupported",
                        "modality_source": "user_selected_unconfirmed",
                    },
                )

            # ── 5. Handle 'recognition_unavailable' (HTTP 200) ──
            if status == "recognition_unavailable":
                msg_text = prediction.get(
                    "message",
                    "Visual recognition service is currently unavailable. Specialist medical models (Skin, X-ray, Retina) can still be selected manually."
                )
                _persist_assistant_msg(f"## Visual Recognition Unavailable\n\n{msg_text}")
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "recognition_unavailable",
                        "success": False,
                        "message": msg_text,
                        "category": "unknown",
                        "detected_subject": "Visual Recognition Unavailable",
                        "description": "Visual recognition service is currently unavailable offline.",
                        "medical_applicable": False,
                        "vision_engine": prediction.get("vision_engine", "heuristic_fallback"),
                    },
                )

            # ── 6. Handle 'model_unavailable' (HTTP 503) ──
            if status == "model_unavailable":
                msg_text = prediction.get(
                    "message",
                    "The required AI specialist model is not currently loaded on this server.",
                )
                _persist_assistant_msg(f"Specialist Model Unavailable: {msg_text}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "model_unavailable",
                        "success": False,
                        "category": prediction.get("category"),
                        "message": msg_text,
                        "domain_hint": prediction.get("domain_hint"),
                    },
                )

            # ── 7. Handle 'unsupported_image' (HTTP 422) ──
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

                detected_subj = prediction.get("detected_subject", "Visible Subject")
                detected_cat = prediction.get("detected_category", "non_medical")
                raw_is_person = prediction.get("is_person")
                p_status = prediction.get(
                    "person_detection",
                    prediction.get("person_detection_status", "unsupported")
                )
                is_person = True if raw_is_person is True else None if p_status == "unsupported" or raw_is_person is None else False
                reason_not_applicable = prediction.get(
                    "reason_not_applicable",
                    "Medical analysis is not applicable to this image."
                )

                unsupported_desc = (
                    caption
                    or prediction.get("description")
                    or prediction.get("message")
                    or "The uploaded image does not appear to be a supported medical image."
                )

                persisted_text = (
                    f"## Image Understanding\n\n"
                    f"**Detected Subject:** {detected_subj}\n\n"
                    f"**Visual Description:** {unsupported_desc}\n\n"
                    f"> **Medical Analysis:** Not applicable.\n"
                    f"> *{reason_not_applicable}*"
                )
                _persist_assistant_msg(persisted_text)

                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "unsupported_image",
                        "success": False,
                        "type": "general_image",
                        "category": "non_medical",
                        "detected_category": detected_cat,
                        "detected_subject": detected_subj,
                        "description": unsupported_desc,
                        "is_person": is_person,
                        "person_detection": p_status,
                        "person_detection_status": p_status,
                        "medical_applicable": False,
                        "reason_not_applicable": reason_not_applicable,
                        "safety_disclaimer": prediction.get("safety_disclaimer"),
                        "override_rejected": prediction.get("override_rejected", False),
                        "override_rejection_reason": prediction.get("override_rejection_reason"),
                        "vision_engine": prediction.get("vision_engine", "vision_service"),
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
                        "detected_subject": prediction.get("detected_subject"),
                        "description": prediction.get("description"),
                        "medical_applicable": False,
                        "domain_hint": prediction.get("domain_hint"),
                        "domain_confidence": prediction.get("domain_confidence", 0.0),
                        "vision_engine": prediction.get("vision_engine", "vision_service"),
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
                    "No disease pathology or fracture was classified for this image. "
                    "Pathology, fracture presence, or internal skeletal abnormalities cannot be reliably determined by this prototype model. "
                    "Anatomical classification does NOT establish that no fracture or abnormality exists. "
                    "Formal clinical radiographic evaluation by a qualified physician or radiologist is required."
                )
            if medical_details is not None and not isinstance(medical_details, str):
                medical_details = str(medical_details)

            response_body = {
                "status": "analysis_complete",
                "success": True,
                "type": "medical_diagnosis",  # Backwards compatibility
                "category": category,
                "disease": disease,
                "finding_type": finding_type,
                "is_negative_finding": is_negative,
                "anatomical_region": prediction.get("anatomical_region"),
                "detected_subject": prediction.get("detected_subject"),
                "description": prediction.get("description"),
                "vision_engine": prediction.get("vision_engine", "vision_service"),
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "modality_confirmed": prediction.get("modality_confirmed", True),
                "research_disclaimer": prediction.get("research_disclaimer"),
                "medical_applicable": True,
                "score": round(score, 4),
                "confidence": round(score, 4),  # Deprecated alias
                "calibrated_confidence": None,
                "score_interpretation": prediction.get(
                    "score_interpretation",
                    "Unvalidated prototype model score; not a calibrated clinical probability. Do NOT use for medical diagnosis or treatment.",
                ),
                "clinical_warning": (
                    "CRITICAL MEDICAL DISCLAIMER: This is an unvalidated research prototype finding. "
                    "Do NOT use this result for self-diagnosis, clinical decisions, or treatment planning. "
                    "Please consult a qualified dermatologist for an in-person evaluation. "
                    "Any further investigation or biopsy should be determined by the treating clinician."
                ),
                "predictions": prediction.get("predictions", []),
                "medical_details": medical_details,
                "clinical_note": prediction.get("clinical_note"),
                "domain_hint": prediction.get("domain_hint"),
                "domain_confidence": prediction.get("domain_confidence", 0.0),
            }

            return JSONResponse(status_code=200, content=response_body)

        except Exception as e:
            logger.error("Image analysis unexpected failure: %s: %s", type(e).__name__, str(e), exc_info=True)
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
