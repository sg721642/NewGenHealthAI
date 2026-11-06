"""
NewGenHealthAI — services/image_ai_service.py
Optional image captioning service.
Lazy-loads BLIP only when ENABLE_BLIP_CAPTIONING=true and model artifacts are provisioned.
Never triggers uncontrolled downloads at import time or during offline testing.
"""

from typing import Optional
from PIL import Image

from app.core.config import ENABLE_BLIP_CAPTIONING
from app.core.logging_config import logger

_blip_processor = None
_blip_model = None
_blip_loaded = False


def _get_lazy_blip():
    """Lazy-load BLIP only if explicitly enabled."""
    global _blip_processor, _blip_model, _blip_loaded
    if not ENABLE_BLIP_CAPTIONING:
        return None, None

    if not _blip_loaded:
        try:
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading BLIP captioning model (explicitly enabled)...")
            _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)
            _blip_loaded = True
            logger.info("BLIP captioning model loaded on %s", device)
        except Exception as e:
            logger.warning("BLIP captioning unavailable: %s", type(e).__name__)
            _blip_loaded = False
            return None, None

    return _blip_processor, _blip_model


def describe_medical_image(image_path: str) -> str:
    """Describe an image using BLIP if enabled, otherwise return safe fallback description."""
    processor, model = _get_lazy_blip()
    if not processor or not model:
        return "Image description is currently unavailable (captioning model not enabled)."

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        with Image.open(image_path) as img:
            image = img.convert("RGB")
            inputs = processor(image, return_tensors="pt").to(device)
            output = model.generate(**inputs, max_new_tokens=50)
            return processor.decode(output[0], skip_special_tokens=True)
    except Exception as e:
        logger.warning("Image captioning failed (%s)", type(e).__name__)
        return "Image description unavailable."
