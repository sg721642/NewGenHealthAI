"""
NewGenHealthAI — services/vision_service.py
Intelligent image-understanding service with Groq Multimodal Vision integration,
deterministic local visual feature fallback, and strict medical safety policies.

Pipeline:
1. Decode and normalize image to safe RGB representation.
2. If Groq Vision is configured and available, query active vision model (qwen/qwen3.8-27b)
   with fallback models (e.g. meta-models/muse-spark-open).
3. Enforce strict safety policies:
   - Photographs of people: recognized as person portrait; disease prediction prohibited; no facial ID.
   - Animals (dogs, cats, etc.): recognized as animal; medical analysis prohibited.
   - Plants, everyday objects, food, vehicles, landscapes: general recognition only.
   - Clinical images (skin lesions, X-rays, retina scans): routed to validated specialist models.
4. If Vision API is rate-limited, timed out, or unconfigured, gracefully fall back to
   deterministic local visual feature detection without fabricating artificial detections.
"""

import base64
import io
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from app.core.config import (
    GROQ_API_KEY,
    GROQ_VISION_MODEL,
    GROQ_VISION_FALLBACK_MODELS,
    VISION_REQUEST_TIMEOUT_SECONDS,
)
from app.core.logging_config import logger

# ─────────────────────────────────────────────────────────────
# Prompts for Structured Multimodal Vision Understanding
# ─────────────────────────────────────────────────────────────

VISION_SYSTEM_INSTRUCTION = """You are an automated visual understanding engine for NewGenHealthAI, an educational health intake assistant.
Analyze the uploaded image factually and return ONLY a valid JSON object matching the requested schema.

Schema requirements:
{
  "is_medical": boolean,
  "category": string, // Exactly one of: "animal", "person", "plant", "food", "vehicle", "object", "landscape", "document", "medical_skin", "medical_xray", "medical_retina", "medical_general", "ambiguous"
  "detected_subject": string, // Specific name of visible subject, e.g. "Golden Retriever Dog", "Portrait of Person", "Ficus Houseplant", "Automobile", "Skin Rash / Dermatitis", "Hand X-ray Radiograph", "Retina Fundus Scan", "Coffee Cup"
  "description": string, // 1-2 objective, factual sentences describing visual content without clinical speculation.
  "modality": string or null, // "skin" for dermatological skin/lesions, "xray" for radiographs, "retina" for fundus eye scans, "general" for wounds/brain MRI/microscopy, or null if non-medical.
  "confidence": "high" | "medium" | "low",
  "is_person": boolean, // true if the image depicts a human face, portrait, selfie, or person.
  "medical_applicable": boolean, // true ONLY if the image is genuine clinical diagnostic imagery.
  "reason_not_applicable": string or null // Explicit explanation if medical analysis is not applicable, or null if applicable.
}

CRITICAL SAFETY & MEDICAL POLICIES:
1. Ordinary Photographs of People: If the image depicts an ordinary person, portrait, selfie, or group:
   - Set is_person=true, is_medical=false, medical_applicable=false, category="person".
   - NEVER attempt to identify the individual's real-world identity or name.
   - NEVER infer medical conditions, illnesses, or dermatological diseases from an ordinary portrait of a person.
   - reason_not_applicable must state: "This is an ordinary photograph of a person. Ordinary photographs cannot be used for clinical medical diagnosis."
2. Animals (dogs, cats, horses, birds, wildlife):
   - Set category="animal", is_medical=false, medical_applicable=false.
   - reason_not_applicable must state: "This image depicts an animal. Veterinary images are outside the scope of human medical intake."
3. Plants, Food, Household Objects, Vehicles, Architecture, Landscapes:
   - Set is_medical=false, medical_applicable=false.
   - reason_not_applicable must state: "Everyday non-medical objects and scenes are not applicable for medical diagnostic analysis."
4. Genuine Clinical Medical Imagery:
   - Dermatological rash, mole, lesion, skin wound -> is_medical=true, category="medical_skin", modality="skin", medical_applicable=true.
   - Radiograph / X-ray -> is_medical=true, category="medical_xray", modality="xray", medical_applicable=true.
   - Retinal fundus eye scan -> is_medical=true, category="medical_retina", modality="retina", medical_applicable=true.
   - Histopathology, surgical wound, brain MRI -> is_medical=true, category="medical_general", modality="general", medical_applicable=true.
5. Blurry, Corrupted, or Ambiguous Images:
   - Set category="ambiguous", is_medical=false, medical_applicable=false, confidence="low".
   - reason_not_applicable must explain that the image is too blurry or unclear for reliable inspection.
"""


def image_to_base64_jpeg(image: Image.Image, max_dim: int = 1024, quality: int = 85) -> str:
    """Convert PIL image to base64-encoded JPEG under bounded dimensions."""
    rgb = image.convert("RGB") if image.mode != "RGB" else image
    w, h = rgb.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        rgb = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ─────────────────────────────────────────────────────────────
# Deterministic Local Visual Feature Fallback
# ─────────────────────────────────────────────────────────────

def analyze_visual_features_deterministic(img: Image.Image) -> Dict[str, Any]:
    """
    Deterministic offline visual feature analyzer (<15ms, zero external API requirement).
    Classifies images strictly as either:
    1. Unusable input (corrupted, extreme blur, low contrast, or solid color).
    2. Usable input with unknown subject (recognition requires vision API).
    Does NOT fabricate confident labels like 'Vegetation', 'Landscape', 'Person', 'Dog', or 'Car'.
    """
    try:
        rgb = img.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float32)
        h, w, _ = arr.shape

        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # 1. Luminance & Contrast analysis
        y_plane = 0.299 * r + 0.587 * g + 0.114 * b
        mean_lum = float(np.mean(y_plane))
        std_lum = float(np.std(y_plane))
        gy, gx = np.gradient(y_plane)
        edge_energy = float(np.mean(np.sqrt(gx**2 + gy**2)))

        # 2. Check for truly unusable input: solid black/white or extreme blur
        is_solid_black_or_white = (std_lum < 1.0) and (mean_lum < 5.0 or mean_lum > 250.0)
        is_extreme_blur = (edge_energy < 0.2 and std_lum < 5.0)

        if is_solid_black_or_white:
            return {
                "status": "ambiguous",
                "is_medical": False,
                "category": "ambiguous",
                "detected_subject": "Solid Blank Image (Black/White)",
                "description": "The uploaded image is completely blank or uniform black/white with no visible features.",
                "modality": None,
                "confidence": "low",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "The uploaded image is solid black or white with no visible features. Please upload a clear photograph.",
                "engine": "heuristic_fallback",
            }

        if is_extreme_blur:
            return {
                "status": "ambiguous",
                "is_medical": False,
                "category": "ambiguous",
                "detected_subject": "Extreme Blur / Low-Contrast Image",
                "description": "The image has near-zero edge sharpness and contrast, making reliable identification impossible.",
                "modality": None,
                "confidence": "low",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "The uploaded image is too blurry, dark, or low in contrast for visual interpretation. Please upload a clear, focused photograph.",
                "engine": "heuristic_fallback",
            }

        # 4. Usable image, but external vision API is unavailable.
        # Honesty guarantee: Local heuristics cannot reliably recognize objects or diagnose conditions.
        return {
            "status": "recognition_unavailable",
            "is_medical": False,
            "category": "unknown",
            "detected_subject": "Visual Recognition Unavailable",
            "description": "Visual recognition is currently unavailable offline. Specialist medical models (Skin, X-ray, Retina) can still be selected manually.",
            "modality": None,
            "confidence": "low",
            "is_person": None,
            "person_detection": "unsupported",
            "person_detection_status": "unsupported",
            "medical_applicable": False,
            "reason_not_applicable": "Visual recognition service is currently unavailable. Specialist medical models (Skin, X-ray, Retina) can still be selected manually.",
            "engine": "heuristic_fallback",
        }

    except Exception as e:
        logger.warning("Deterministic visual feature analysis error: %s", type(e).__name__)
        return {
            "status": "invalid_image",
            "is_medical": False,
            "category": "invalid_image",
            "detected_subject": "Corrupt / Unreadable Image",
            "description": "Could not decode or extract visual features from the image.",
            "modality": None,
            "confidence": "low",
            "is_person": None,
            "person_detection": "unsupported",
            "person_detection_status": "unsupported",
            "medical_applicable": False,
            "reason_not_applicable": "The uploaded image file is corrupt or unreadable.",
            "engine": "heuristic_fallback",
        }

# ─────────────────────────────────────────────────────────────
# Local Neural Vision Model (MobileNetV3-Small on CPU Basic)
# ─────────────────────────────────────────────────────────────

_local_vision_model = None
_local_vision_transform = None
_local_vision_categories = None


def _get_local_vision_model():
    """Lazy-load MobileNetV3-Small neural vision weights pinned to local filesystem."""
    global _local_vision_model, _local_vision_transform, _local_vision_categories
    if _local_vision_model is None:
        try:
            import torch
            import torchvision.models as models
            import torchvision.transforms as transforms

            models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
            weights_path = os.path.join(models_dir, "mobilenet_v3_small-047dcff4.pth")
            if not os.path.exists(weights_path):
                logger.warning("Local neural vision checkpoint missing: %s", weights_path)
                return None, None, None

            model = models.mobilenet_v3_small(weights=None)
            state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state_dict)
            model.eval()

            transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ])
            categories = models.MobileNet_V3_Small_Weights.DEFAULT.meta.get("categories", [])

            _local_vision_model = model
            _local_vision_transform = transform
            _local_vision_categories = categories
            logger.info("Local MobileNetV3-Small neural vision loaded successfully (%d classes).", len(categories))
        except Exception as e:
            logger.warning("Could not initialize local neural vision model: %s", type(e).__name__)
            return None, None, None
    return _local_vision_model, _local_vision_transform, _local_vision_categories


def map_imagenet_to_category_and_subject(idx: int, name: str) -> Tuple[str, str]:
    """Map ImageNet 1k class index and name to high-level domain category and display subject.

    SCOPE LIMITATION: MobileNetV3-Small is a CLOSED-SET ImageNet-1K classifier trained on
    exactly 1,000 object categories. It does NOT perform universal recognition. It cannot
    identify objects outside its 1,000 training classes and cannot perform clinical medical
    diagnosis, facial identification, or dermatological assessment.

    Animal boundary: ImageNet-1K classes 0-397 are animals (mammals, birds, reptiles, fish,
    insects, and similar fauna). This boundary is verified against the official torchvision
    MobileNet_V3_Small_Weights.DEFAULT class list: idx 397 = 'puffer' (last fish), idx 398 =
    'abacus' (first non-animal object). The boundary idx < 398 is correct and verified.

    Person inference: ONLY classes where a human being is explicitly and necessarily depicted
    are mapped to 'person'. Clothing/garment-only classes (bikini, suit, brassiere, gown,
    kimono, etc.) are NOT mapped to 'person'; a garment photograph does not necessarily
    contain a person. 'face powder' (idx=551) is a cosmetic product, not a face.
    Classes explicitly depicting humans: groom (982), ballplayer (981), scuba diver (983).
    """
    name_clean = name.replace("_", " ").lower()

    # Classes 0-397: Animals (verified against ImageNet-1K standard ordering).
    # idx 397 = 'puffer' (last animal); idx 398 = 'abacus' (first non-animal object).
    if idx < 398:
        return "animal", f"Animal ({name.title()})"

    # Person classes: ONLY classes that necessarily and explicitly depict a human being.
    # Clothing-only classes (suit, bikini, brassiere, gown, kimono, etc.) are excluded because
    # those ImageNet classes depict the garment itself, not necessarily a person wearing it.
    _person_classes = {
        "groom",        # idx=982: wedding groom — human explicitly depicted
        "ballplayer",   # idx=981: baseball player — human explicitly depicted
        "scuba diver",  # idx=983: scuba diver — human explicitly depicted
    }
    if name_clean in _person_classes:
        return "person", f"Person ({name.title()})"

    building_kws = [
        "boathouse", "greenhouse", "mobile home", "barn", "church", "palace",
        "monastery", "cinema", "library", "restaurant", "prison"
    ]
    for kw in building_kws:
        if kw in name_clean:
            return "object", f"Everyday Architecture ({name.title()})"

    vehicle_kws = [
        "car", "truck", "van", "jeep", "cab", "bus", "racer", "ambulance",
        "boat", "ship", "canoe", "yacht", "aircraft", "airliner", "plane",
        "bicycle", "motorcycle", "moped", "scooter", "train", "streetcar",
        "locomotive", "cart", "tractor", "trailer", "forklift", "tank",
        "submarine", "unicycle", "wheelbarrow", "rickshaw", "space shuttle",
        "convertible", "sports car", "limousine", "minivan"
    ]
    for kw in vehicle_kws:
        if kw in name_clean:
            return "vehicle", f"Vehicle ({name.title()})"

    food_kws = [
        "food", "fruit", "vegetable", "dish", "apple", "banana", "orange",
        "lemon", "berry", "squash", "pepper", "cabbage", "broccoli",
        "cauliflower", "pizza", "burger", "sandwich", "bread", "loaf",
        "bagel", "pretzel", "soup", "stew", "sauce", "cake", "pie",
        "ice cream", "custard", "wine", "espresso", "coffee", "beer",
        "tea", "chocolate", "pasta", "carbonara", "guacamole", "consomme",
        "hot pot", "trifle", "hotdog", "burrito", "meat loaf", "potpie", "eggnog"
    ]
    for kw in food_kws:
        if kw in name_clean:
            return "food", f"Food ({name.title()})"

    plant_kws = [
        "flower", "plant", "tree", "daisy", "sunflower", "rose", "orchid",
        "tulip", "lily", "cardoon", "rapeseed", "lady's slipper", "corn",
        "acorn", "fungus", "mushroom", "agaric", "gyromitra", "stinkhorn",
        "earthstar", "bolete", "buckeye", "hay"
    ]
    for kw in plant_kws:
        if kw in name_clean:
            return "plant", f"Plant ({name.title()})"

    landscape_kws = [
        "alp", "cliff", "coral reef", "geyser", "lakeside", "promontory",
        "sandbar", "seashore", "valley", "volcano"
    ]
    for kw in landscape_kws:
        if kw in name_clean:
            return "landscape", f"Landscape ({name.title()})"

    if 924 <= idx <= 969:
        return "food", f"Food ({name.title()})"
    if 984 <= idx <= 997:
        return "plant", f"Plant ({name.title()})"
    if 970 <= idx <= 980:
        return "landscape", f"Landscape ({name.title()})"

    return "object", f"Everyday Object ({name.title()})"



def classify_with_local_neural_vision(img: Image.Image) -> Optional[Dict[str, Any]]:
    """
    Classify everyday photographs locally using MobileNetV3-Small neural network on CPU Basic.
    - Zero network dependency, zero cost, ~50ms latency.
    - Enforces safety boundaries: persons and animals are strictly non-medical.
    - Abstains honestly on blank, low-contrast, or ambiguous visual inputs.
    """
    model, transform, categories = _get_local_vision_model()
    if model is None or transform is None or not categories:
        return None

    try:
        import torch

        rgb = img.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float32)
        h, w, _ = arr.shape

        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # 1. Quality & usable input pre-flight
        y_plane = 0.299 * r + 0.587 * g + 0.114 * b
        mean_lum = float(np.mean(y_plane))
        std_lum = float(np.std(y_plane))
        gy, gx = np.gradient(y_plane)
        edge_energy = float(np.mean(np.sqrt(gx**2 + gy**2)))

        is_solid = (std_lum < 1.0) and (mean_lum < 5.0 or mean_lum > 250.0)
        is_blur = (edge_energy < 0.2 and std_lum < 5.0)

        if is_solid:
            return {
                "status": "ambiguous",
                "is_medical": False,
                "category": "ambiguous",
                "detected_subject": "Solid Blank Image (Black/White)",
                "description": "The uploaded image is completely blank or uniform black/white with no visible features.",
                "modality": None,
                "confidence": "low",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "The uploaded image is solid black or white with no visible features. Please upload a clear photograph.",
                "engine": "local_neural_vision",
                "vision_model": "mobilenet_v3_small",
            }

        if is_blur:
            return {
                "status": "ambiguous",
                "is_medical": False,
                "category": "ambiguous",
                "detected_subject": "Extreme Blur / Low-Contrast Image",
                "description": "The image has near-zero edge sharpness and contrast, making reliable identification impossible.",
                "modality": None,
                "confidence": "low",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "The uploaded image is too blurry, dark, or low in contrast for visual interpretation. Please upload a clear, focused photograph.",
                "engine": "local_neural_vision",
                "vision_model": "mobilenet_v3_small",
            }

        # 2. Local Neural Inference First
        tensor = transform(rgb).unsqueeze(0)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)
            top_probs, top_indices = torch.topk(probs, 5)

        top_prob = float(top_probs[0][0].item())
        top_idx = int(top_indices[0][0].item())
        top_name = categories[top_idx] if top_idx < len(categories) else "unknown"
        category, detected_subject = map_imagenet_to_category_and_subject(top_idx, top_name)

        top5 = [
            (int(top_indices[0][k].item()), categories[int(top_indices[0][k].item())])
            for k in range(min(5, len(categories)))
        ]
        top5_probs = [float(top_probs[0][k].item()) for k in range(min(5, len(top5)))]
        top5_names = [t[1] for t in top5]
        top5_indices = [t[0] for t in top5]

        # 3. Portrait Detection Guardrail (Strictly Non-Medical).
        # ImageNet classes such as groom, ballplayer, and scuba diver are closed-set ImageNet-1K labels,
        # NOT a dedicated person or face detector. General person detection remains explicitly unsupported.
        # Medical disease inference is strictly prohibited on portraits.
        is_portrait = (category == "person")
        if is_portrait:
            return {
                "status": "general_recognition",
                "is_medical": False,
                "category": "person",
                "detected_subject": "Portrait of Person",
                "description": "A photograph depicting a human portrait. Personal identity and clinical disease inference are strictly prohibited.",
                "modality": None,
                "confidence": "high" if top_prob >= 0.35 else "medium",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "person_detection_note": (
                    f"Closed-set ImageNet-1K classification predicted human-associated class '{top_name.replace('_', ' ')}', "
                    "but dedicated face or person detection is unsupported. General person detection remains explicitly unsupported. "
                    "Biometric identification and clinical disease inference are strictly prohibited on ordinary portraits."
                ),
                "medical_applicable": False,
                "reason_not_applicable": "This is an ordinary photograph of a person. Ordinary photographs cannot be used for clinical medical diagnosis.",
                "safety_disclaimer": "Real-person facial recognition and medical disease inference are strictly prohibited on ordinary portraits.",
                "engine": "local_neural_vision",
                "vision_model": "mobilenet_v3_small",
                "top1_idx": top_idx,
                "top1_name": top_name,
                "top1_prob": round(top_prob, 4),
                "top5": [{"idx": top5_indices[k], "name": top5_names[k], "prob": round(top5_probs[k], 4)} for k in range(len(top5))],
            }

        # 5. Confident Everyday Non-Medical Object / Animal / Vehicle / Plant / Food Recognition.
        # Neural network predictions >= 0.20 confidence take precedence over ambiguous colour hues.
        # Person detection remains unsupported across all everyday objects/clothing (suit, tie, etc.).
        is_confident_everyday = (
            (category in ("animal", "vehicle", "plant", "food") and top_prob >= 0.20)
            or (category in ("object", "landscape") and top_prob >= 0.20)
        )

        if is_confident_everyday:
            if category == "animal":
                safety_disclaimer = "Veterinary images are outside the scope of human medical intake. No veterinary disease prediction is performed."
                reason_not_applicable = "This image depicts an animal. Veterinary images are outside the scope of human medical intake."
            else:
                safety_disclaimer = "Everyday non-medical objects and scenes are not applicable for clinical diagnostic models."
                reason_not_applicable = f"This image depicts a {category}. Everyday non-medical images are not applicable for medical diagnostic analysis."

            desc = f"Visual recognition identified a non-medical {category} ({top_name.replace('_', ' ')})."
            return {
                "status": "general_recognition",
                "is_medical": False,
                "category": category,
                "detected_subject": detected_subject,
                "description": desc,
                "modality": None,
                "confidence": "high" if top_prob >= 0.35 else "medium",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "person_detection_note": (
                    f"Person presence could not be reliably determined. Closed-set ImageNet-1K classification evaluates object/clothing features ('{top_name.replace('_', ' ')}') "
                    "and does not support general face or person detection; this does not confirm absence of a person. Biometric or demographic inference is strictly prohibited."
                ),
                "medical_applicable": False,
                "reason_not_applicable": reason_not_applicable,
                "safety_disclaimer": safety_disclaimer,
                "engine": "local_neural_vision",
                "vision_model": "mobilenet_v3_small",
                "top1_idx": top_idx,
                "top1_name": top_name,
                "top1_prob": round(top_prob, 4),
                "top5": [{"idx": top5_indices[k], "name": top5_names[k], "prob": round(top5_probs[k], 4)} for k in range(len(top5))],
            }

        # 6. No Confident Category Identified — Modality Selection Required.
        # Without a validated CLIP-based or supervised modality classifier, the system abstains
        # and requires explicit modality selection from the user.
        if top_prob < 0.12:
            abstain_desc = "No dominant object recognized with sufficient confidence (top-1 probability < 0.12)."
        else:
            abstain_desc = f"Neural network top-1 class '{top_name}' (p={top_prob:.3f}) does not map to a confident everyday category."

        return {
            "status": "modality_selection_required",
            "is_medical": False,
            "category": "ambiguous",
            "detected_subject": "Unrecognized Visual Subject",
            "description": (
                f"{abstain_desc} "
                "MobileNetV3-Small is a closed-set ImageNet-1K classifier and cannot reliably determine "
                "if this image is a clinical dermoscopy, radiograph, retina scan, or non-medical photograph."
            ),
            "modality": None,
            "confidence": "low",
            "is_person": None,
            "person_detection": "unsupported",
            "person_detection_status": "unsupported",
            "person_detection_note": "Person presence could not be reliably determined. Dedicated person detection is unsupported.",
            "medical_applicable": False,
            "reason_not_applicable": (
                "Image modality could not be automatically determined. "
                "Please select the appropriate medical modality (Skin, X-ray, Retina) or confirm "
                "this is a non-medical image. Automated colour heuristics are not used as medical routing."
            ),
            "routing_note": (
                "ADVISORY: Colour, YCbCr skin-ratio, brightness, and geometry heuristics "
                "are NOT used as decisive medical routing mechanisms. A validated medical "
                "modality classifier is required for automatic routing. Explicit modality "
                "selection is the only supported path for clinical analysis."
            ),
            "engine": "local_neural_vision",
            "vision_model": "mobilenet_v3_small",
            "top1_idx": top_idx,
            "top1_name": top_name,
            "top1_prob": round(top_prob, 4),
            "top5": [{"idx": top5_indices[k], "name": top5_names[k], "prob": round(top5_probs[k], 4)} for k in range(len(top5))],
        }

    except Exception as e:
        logger.warning("Local neural vision classification failed: %s", type(e).__name__)
        return None


# ─────────────────────────────────────────────────────────────
# Vision Service Class
# ─────────────────────────────────────────────────────────────

class VisionService:
    """
    Intelligent image-understanding service.
    Directs image understanding requests to Groq multimodal vision API (Qwen 3.8 27B)
    with seamless fallback to deterministic local feature analysis.
    """

    def __init__(self):
        self._groq_client = None
        self._last_api_status: Dict[str, Any] = {
            "timestamp": 0.0,
            "available": None,
            "last_error": None,
        }

    def _get_client(self):
        """Return cached Groq client instance if GROQ_API_KEY is configured."""
        if not GROQ_API_KEY or not GROQ_API_KEY.strip():
            return None
        if self._groq_client is None:
            try:
                from groq import Groq
                self._groq_client = Groq(
                    api_key=GROQ_API_KEY.strip(),
                    timeout=VISION_REQUEST_TIMEOUT_SECONDS,
                )
            except Exception as e:
                logger.warning("Could not initialize Groq vision client: %s", type(e).__name__)
                return None
        return self._groq_client

    def call_groq_vision(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        Call Groq Multimodal Vision API to obtain structured understanding.
        Tries GROQ_VISION_MODEL and configured fallbacks.
        Catches rate limits, timeouts, model deprecations, and network issues gracefully.
        """
        client = self._get_client()
        if not client:
            return None

        base64_data = image_to_base64_jpeg(image)
        candidate_models = [GROQ_VISION_MODEL] + [
            m for m in GROQ_VISION_FALLBACK_MODELS if m != GROQ_VISION_MODEL
        ]

        messages = [
            {
                "role": "system",
                "content": VISION_SYSTEM_INSTRUCTION,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Carefully examine this image. Identify what is visible (subject, category, whether medical or non-medical). "
                            "Follow all medical safety policies strictly. Return ONLY the requested JSON object."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_data}"
                        },
                    },
                ],
            },
        ]

        for model_name in candidate_models:
            try:
                logger.info("Querying Groq Vision model: %s...", model_name)
                start_t = time.time()
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=600,
                )
                elapsed = time.time() - start_t
                logger.info("Groq Vision response received from %s in %.2fs", model_name, elapsed)

                raw_content = response.choices[0].message.content.strip()
                data = json.loads(raw_content)

                # Normalize and validate parsed JSON
                is_medical = bool(data.get("is_medical", False))
                category = str(data.get("category", "object")).lower().strip()
                detected_subject = str(data.get("detected_subject", "Visible Subject")).strip()
                description = str(data.get("description", "")).strip()
                modality = data.get("modality")
                if modality:
                    modality = str(modality).lower().strip()
                    if modality not in ("skin", "xray", "retina", "general"):
                        modality = None
                confidence = str(data.get("confidence", "high")).lower().strip()
                is_person = bool(data.get("is_person", False))
                medical_applicable = bool(data.get("medical_applicable", False))
                reason_not_applicable = data.get("reason_not_applicable")

                safety_disclaimer = None

                # Medical safety guardrail: ordinary person photo is NEVER medical
                if is_person or category == "person":
                    is_person = True
                    is_medical = False
                    medical_applicable = False
                    modality = None
                    category = "person"
                    if not reason_not_applicable:
                        reason_not_applicable = "This is an ordinary photograph of a person. Ordinary photographs cannot be used for clinical medical diagnosis."
                    safety_disclaimer = "Real-person facial recognition and medical disease inference are strictly prohibited on ordinary portraits."

                # Animals:
                elif category == "animal":
                    is_medical = False
                    medical_applicable = False
                    modality = None
                    if not reason_not_applicable:
                        reason_not_applicable = "This image depicts an animal. Veterinary images are outside the scope of human medical intake."
                    safety_disclaimer = "Veterinary images are outside the scope of human medical intake. No veterinary disease prediction is performed."

                # Non-medical categories are NEVER medical
                elif category in ("plant", "food", "vehicle", "object", "landscape", "document"):
                    is_medical = False
                    medical_applicable = False
                    modality = None
                    if not reason_not_applicable:
                        reason_not_applicable = f"This image depicts a {category}. Everyday non-medical images are not applicable for medical diagnostic analysis."
                    safety_disclaimer = "Everyday non-medical objects and scenes are not applicable for clinical diagnostic models."

                elif category == "ambiguous":
                    is_medical = False
                    medical_applicable = False
                    modality = None
                    if not reason_not_applicable:
                        reason_not_applicable = "The uploaded image is too blurry, dark, or ambiguous for reliable visual interpretation."

                # Genuine medical imaging modality check
                if is_medical:
                    if not modality:
                        if "skin" in category:
                            modality = "skin"
                        elif "xray" in category:
                            modality = "xray"
                        elif "retina" in category:
                            modality = "retina"
                        else:
                            modality = "general"
                    medical_applicable = True
                    reason_not_applicable = None
                    status = "medical_identified"
                elif category == "ambiguous":
                    status = "ambiguous"
                else:
                    status = "general_recognition"

                self._last_api_status["available"] = True
                self._last_api_status["timestamp"] = time.time()
                self._last_api_status["last_error"] = None

                return {
                    "status": status,
                    "is_medical": is_medical,
                    "category": category,
                    "detected_subject": detected_subject,
                    "description": description,
                    "modality": modality,
                    "confidence": confidence,
                    "is_person": is_person,
                    "medical_applicable": medical_applicable,
                    "reason_not_applicable": reason_not_applicable,
                    "safety_disclaimer": safety_disclaimer,
                    "engine": "groq_vision",
                    "vision_model": model_name,
                }

            except Exception as e:
                err_msg = str(e)
                err_type = type(e).__name__
                logger.warning(
                    "Groq Vision call failed for model '%s': %s (%s)",
                    model_name,
                    err_type,
                    err_msg[:120],
                )
                self._last_api_status["available"] = False
                self._last_api_status["timestamp"] = time.time()
                self._last_api_status["last_error"] = err_type

                # On AuthenticationError, key is invalid for all models on this provider
                low_err = (err_type + " " + err_msg).lower()
                if "authentication" in low_err or "invalid_api_key" in low_err or "invalid api key" in low_err or "401" in low_err:
                    logger.info("Groq authentication failed; skipping remaining remote models to deterministic fallback.")
                    break

                # For other errors (e.g. 404 not found, 429 rate limit, 500/503 server error), try next candidate model
                continue

        return None

    def understand_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Understand any uploaded image.
        1. Calls Groq Vision API if configured.
        2. Falls back cleanly to deterministic local feature analysis if API is offline or unavailable.
        3. Never fabricates artificial detections.
        """
        if image is None:
            return {
                "is_medical": False,
                "category": "invalid_image",
                "detected_subject": "Invalid Image",
                "description": "No valid image data provided.",
                "modality": None,
                "confidence": "low",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "Invalid or missing image file.",
                "engine": "none",
            }

        # 1. Attempt Groq Multimodal Vision (if configured and online)
        groq_result = self.call_groq_vision(image)
        if groq_result is not None:
            return groq_result

        # 2. Attempt Local Neural Vision (MobileNetV3-Small on CPU Basic)
        local_result = classify_with_local_neural_vision(image)
        if local_result is not None:
            return local_result

        # 3. Fall back cleanly to deterministic local visual feature detection
        logger.info("Using deterministic visual feature analyzer fallback for image understanding.")
        fallback_result = analyze_visual_features_deterministic(image)
        return fallback_result


# Module singleton
vision_service = VisionService()
