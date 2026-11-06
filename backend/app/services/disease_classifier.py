"""
NewGenHealthAI — services/disease_classifier.py

Multi-model disease classifier with CLIP-based domain detection,
lazy specialist loading, and hard modality locking.

Pipeline:
1. Use CLIP zero-shot to determine image domain (skin / xray / retina / general / non_medical)
2. Run ONLY the matching specialist model (hard lock — no cross-contamination)
3. Filter garbage / dataset-artifact predictions
4. Return the top disease prediction from the specialist model
5. Non-medical images are flagged for optional captioning in the API layer

Detected architectures (from inspect_models.py):
  skin    -> timm EfficientNet (conv_stem + blocks), 216 classes
  xray    -> DenseNet121 (features.denseblock), 10 classes
  retina  -> EfficientNet-B0 (custom classifier), 47 classes
  general -> ResNet18 (layer1-4, fc), 69 classes
"""

import os
import hashlib
import threading
from typing import Dict, Optional, Tuple

TRUSTED_CHECKPOINT_HASHES = {
    "skin_disease_model.pth": "0bc3877c6ece5c9b72b59f174403874d73cd3204dc4ed2f38edd9b2be5ed61fe",
    "xray_fracture_model.pth": "ed146630d81fa37dc44f45f72cb80cc8b7f7aa3628bcee92c555bd4061580937",
    "retina_model.pth": "b5510938daea44433589fabe98ba7c5069ceb8a18dea0ebab68c861258e28862",
    "general_disease_model.pth": "adcdb81092710787de6dbf382b8e6432e5f279237667b67ef88b0a81a191f7cc",
}

import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image

from app.core.logging_config import logger

# ═══════════════════════════════════════════════════════════════
# PREDICTION QUALITY FILTERS
# ═══════════════════════════════════════════════════════════════

# Dataset artifact classes — non-medical strings, filesystem paths, split names.
# NEVER return these as a condition or diagnosis.
DATASET_ARTIFACT_CLASSES = {
    "all", "train", "test", "val", "valid", "done", "preview", "cropped",
    "jpegimages", "test cases", "other", "others", "others augmented",
    "c-nmc test final phase data", "c-nmc test prelim phase data",
    "im dyskeratotic", "im koilocytotic", "im metaplastic",
    "im parabasal", "im superficial-intermediate",
    "none", "monkeypox augmented",
}

# Backward compatibility alias
GARBAGE_CLASSES = DATASET_ARTIFACT_CLASSES

# Legitimate negative, normal, uninfected, and benign reference findings.
# These MUST NEVER be suppressed or treated as garbage dataset artifacts.
VALID_NEGATIVE_CLASSES = {
    "normal", "normal cases", "notumor", "notinfected", "uninfected",
    "non-covid", "bengin cases", "benign",
    "healthy eye (no observable ocular disease)",
}

# X-ray body parts — anatomical locations, not diseases
XRAY_BODY_PARTS = {
    "elbow", "finger", "forearm", "hand", "humerus", "shoulder", "wrist",
}

# X-ray actual medical conditions
XRAY_CONDITIONS = {"fracture", "pneumonia"}

# Retina "healthy" label
RETINA_HEALTHY = {"healthy eye (no observable ocular disease)"}

# Better display names for messy general-model classes
GENERAL_DISPLAY = {
    "monkey pox": "Monkeypox", "monkeypox": "Monkeypox",
    "covid": "COVID-19 (Lung Imaging)",
    "glioma": "Glioma (Brain Tumor)",
    "meningioma": "Meningioma (Brain Tumor)",
    "pituitary": "Pituitary Tumor",
    "diabetic wounds": "Diabetic Wound",
    "pressure wounds": "Pressure Wound / Ulcer",
    "surgical wounds": "Surgical Wound",
    "venous wounds": "Venous Wound",
    "abrasions": "Skin Abrasion", "burns": "Burn Injury",
    "bruises": "Bruise / Contusion", "cut": "Cut / Laceration",
    "laseration": "Laceration",
    "gingivitis": "Gingivitis", "calculus": "Dental Calculus",
    "hypodontia": "Hypodontia", "cyst": "Cyst",
    "tooth discoloration original dataset": "Tooth Discoloration",
    "ulcer original dataset": "Oral Ulcer",
    "stone": "Kidney / Bladder Stone", "stroke": "Stroke",
    "angina disease": "Angina",
    "coronary artery disease": "Coronary Artery Disease",
    "hypotension disease": "Hypotension",
    "cardio disease": "Cardiovascular Disease",
    "basophil": "Basophil (Blood Cell)",
    "eosinophil": "Eosinophil (Blood Cell)",
    "erythroblast": "Erythroblast (Blood Cell)",
    "lymphocyte": "Lymphocyte (Blood Cell)",
    "monocyte": "Monocyte (Blood Cell)",
    "neutrophil": "Neutrophil (Blood Cell)",
    "platelet": "Platelet (Blood Cell)",
    "hem": "Hematological Sample", "ig": "Immunoglobulin Sample",
    "infected": "Infected Tissue", "parasitized": "Parasitized Cell",
    "benign": "Benign Growth", "malignant": "Malignant Growth",
    "malignant cases": "Malignant Growth", "tumor": "Tumor",
}


# ═══════════════════════════════════════════════════════════════
# CLIP-BASED DOMAIN DETECTION  (replaces pixel heuristics)
# ═══════════════════════════════════════════════════════════════

_clip_model = None
_clip_processor = None

# Carefully engineered text prompts for zero-shot classification.
# Each prompt is designed to capture the visual characteristics of that domain.
CLIP_DOMAIN_PROMPTS = [
    # 0 → skin: photos of skin with lesions, rashes, discolorations
    "a clinical photograph of human skin showing a skin disease, rash, lesion, mole, or dermatological condition",
    # 1 → xray: radiographic bone/chest images
    "a medical X-ray radiograph image showing bones, joints, fractures, or chest scan in grayscale",
    # 2 → retina: circular fundus photographs of the retina
    "a retinal fundus photograph of the inside of a human eye showing the optic disc and blood vessels",
    # 3 → general: microscopy, CT scans, wound photos, other medical
    "a medical image such as a microscope slide, MRI scan, CT scan, wound photo, or laboratory test image",
    # 4 → non_medical: everyday photos, landscapes, objects, selfies
    "a non-medical photograph such as a landscape, animal, food, object, selfie, or everyday scene",
]

CLIP_DOMAIN_MAP = {
    0: "skin",
    1: "xray",
    2: "retina",
    3: "general",
    4: "non_medical",
}


def _get_clip():
    """Lazy-load CLIP model without implicit network downloads when offline."""
    global _clip_model, _clip_processor
    if _clip_model is None:
        try:
            from transformers import CLIPProcessor, CLIPModel
            from app.core.config import ALLOW_MODEL_DOWNLOADS

            kwargs = {}
            if not ALLOW_MODEL_DOWNLOADS:
                kwargs["local_files_only"] = True

            logger.info("Loading CLIP model for domain detection...")
            _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", **kwargs)
            _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", **kwargs)
            _clip_model.eval()
            logger.info("CLIP model loaded successfully.")
        except Exception as e:
            logger.warning("CLIP model unavailable (%s)", type(e).__name__)
            return None, None
    return _clip_model, _clip_processor


def detect_domain_from_visual_features(img: Image.Image) -> tuple:
    """
    DEPRECATED & NEUTRALIZED — Visual heuristics are prohibited from clinical modality routing.

    Autonomous clinical modality routing or medical image acceptance/rejection using visual heuristics
    (such as skin chrominance, YCbCr, green/blue ratios, chroma saturation, corner aperture brightness,
    or edge density) is completely disabled in accordance with clinical safety governance.

    Explicit user modality selection is the mandatory requirement for medical analysis.

    Returns: (domain_name: str, confidence: float, all_scores: dict)
    domain_name is unconditionally 'ambiguous' (conf=0.0).
    """
    return "ambiguous", 0.0, {"ambiguous": 0.0}


def detect_visual_domain(image: Image.Image) -> tuple:
    """
    Use CLIP zero-shot classification to determine image domain.
    Returns: (domain_name: str, confidence: float, all_scores: dict)
    """
    try:
        model, processor = _get_clip()
        if model is None or processor is None:
            return "unknown", 0.0, {"error": "CLIP model unavailable"}

        inputs = processor(
            text=CLIP_DOMAIN_PROMPTS,
            images=image,
            return_tensors="pt",
            padding=True,
        )

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits_per_image[0]  # shape: [num_prompts]
            probs = logits.softmax(dim=0)

        # Build scores dict for logging
        scores = {}
        for idx, domain_name in CLIP_DOMAIN_MAP.items():
            scores[domain_name] = round(float(probs[idx]), 4)

        best_idx = probs.argmax().item()
        best_domain = CLIP_DOMAIN_MAP[best_idx]
        best_conf = float(probs[best_idx])

        logger.info(
            f"CLIP domain detection: {best_domain} ({best_conf:.3f}) | "
            f"scores={scores}"
        )

        if best_conf < 0.30:
            logger.info("CLIP domain detection confidence below threshold (%.3f); marking ambiguous", best_conf)
            return "ambiguous", best_conf, scores

        return best_domain, best_conf, scores

    except Exception as e:
        logger.error("CLIP domain detection error: %s", type(e).__name__)
        # Never silently fall back to general on CLIP failure; return unknown
        return "unknown", 0.0, {"error": type(e).__name__}



# ═══════════════════════════════════════════════════════════════
# MODEL HELPERS  (unchanged from original)
# ═══════════════════════════════════════════════════════════════

def _parse_class_file(class_path):
    """Parse a class file (tab-separated or plain, one name per line)."""
    classes = []
    with open(class_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "\t" in line:
                parts = line.split("\t", 1)
                name = parts[1].strip() if len(parts) > 1 else parts[0].strip()
            else:
                name = line
            classes.append(name.replace("_", " "))
    return classes


def _unwrap_state_dict(checkpoint):
    """Extract the raw state_dict from a checkpoint that may be wrapped."""
    metadata = {}
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            metadata = {k: v for k, v in checkpoint.items() if k != "model_state_dict"}
            return checkpoint["model_state_dict"], metadata
        elif "state_dict" in checkpoint:
            metadata = {k: v for k, v in checkpoint.items() if k != "state_dict"}
            return checkpoint["state_dict"], metadata
    return checkpoint, metadata


def _detect_architecture(state_dict_keys):
    """Detect model architecture from state dict key patterns."""
    keys_str = " ".join(list(state_dict_keys)[:30])
    keys_end_str = " ".join(list(state_dict_keys)[-20:])

    if "conv_stem" in keys_str and "blocks" in keys_str:
        return "timm_efficientnet"
    elif "features.denseblock1" in keys_str:
        return "densenet121"
    elif "features.0.0.weight" in keys_str and "features.1.0.block" in keys_str:
        if "classifier.5.weight" in keys_end_str:
            return "retina_efficientnet_b0"
        return "mobilenet_v2"
    elif "layer1" in keys_str and "conv1.weight" in keys_str:
        return "resnet18"
    elif "features.0.weight" in keys_str:
        return "efficientnet_b4"
    return "unknown"


def _build_model(arch, num_classes, state_dict):
    """Build a model of the given architecture and load the state dict."""

    if arch == "timm_efficientnet":
        try:
            import timm
            for model_name in ["tf_efficientnet_b4.ns_jft_in1k", "tf_efficientnet_b4_ns", "efficientnet_b4", "tf_efficientnet_b4"]:
                try:
                    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
                    model.load_state_dict(state_dict)
                    return model, 380
                except Exception:
                    continue
        except ImportError:
            logger.warning("timm not installed; attempting to load with weights remapping")
        
        try:
            model = models.efficientnet_b4(weights=None)
            model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
            
            # Attempt weights remapping (timm -> torchvision)
            remapped_sd = {}
            for k, v in state_dict.items():
                new_k = k
                if k.startswith("conv_stem."):
                    new_k = k.replace("conv_stem.", "features.0.0.")
                elif k.startswith("bn1."):
                    new_k = k.replace("bn1.", "features.0.1.")
                elif k.startswith("blocks."):
                    # Basic block mapping: blocks.x.y -> features.x+1.y
                    parts = k.split(".")
                    if len(parts) >= 3 and parts[1].isdigit():
                        block_idx = int(parts[1])
                        new_k = f"features.{block_idx+1}." + ".".join(parts[2:])
                elif k.startswith("conv_head."):
                    new_k = k.replace("conv_head.", "features.8.0.")
                elif k.startswith("bn2."):
                    new_k = k.replace("bn2.", "features.8.1.")
                elif k.startswith("classifier."):
                    new_k = k.replace("classifier.", "classifier.1.")
                
                remapped_sd[new_k] = v
            
            try:
                model.load_state_dict(remapped_sd)
                logger.info("Successfully remapped timm weights to torchvision EfficientNet")
            except Exception as e:
                logger.warning(f"Weights remapping failed: {e}. Trying strict load...")
                model.load_state_dict(state_dict)
                
            return model, 380
        except Exception as e:
            logger.error(f"Failed to build EfficientNet-B4: {e}")
        return None, None

    elif arch == "densenet121":
        model = models.densenet121(weights=None)
        model.classifier = nn.Linear(model.classifier.in_features, num_classes)
        model.load_state_dict(state_dict)
        return model, 224

    elif arch == "retina_efficientnet_b0":
        model = models.efficientnet_b0(weights=None)
        model.classifier = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(1280, 512),
            nn.ReLU(),
            nn.BatchNorm1d(512),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )
        model.load_state_dict(state_dict)
        return model, 224

    elif arch == "mobilenet_v2":
        classifier_keys = [k for k in state_dict.keys() if k.startswith("classifier.")]
        max_idx = 0
        for k in classifier_keys:
            parts = k.split(".")
            if len(parts) >= 2 and parts[1].isdigit():
                max_idx = max(max_idx, int(parts[1]))

        model = models.mobilenet_v2(weights=None)
        if max_idx >= 5:
            in_features = model.classifier[1].in_features
            model.classifier = nn.Sequential(
                nn.Dropout(0.2),
                nn.Linear(in_features, 512),
                nn.ReLU(),
                nn.BatchNorm1d(512),
                nn.Dropout(0.3),
                nn.Linear(512, num_classes),
            )
        else:
            model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
        model.load_state_dict(state_dict)
        return model, 224

    elif arch == "resnet18":
        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        model.load_state_dict(state_dict)
        return model, 224

    elif arch == "resnet50":
        model = models.resnet50(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        model.load_state_dict(state_dict)
        return model, 224

    elif arch == "efficientnet_b4":
        model = models.efficientnet_b4(weights=None)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
        model.load_state_dict(state_dict)
        return model, 380

    return None, None


# ═══════════════════════════════════════════════════════════════
# MEDICAL MODEL WRAPPER  (unchanged)
# ═══════════════════════════════════════════════════════════════

class MedicalModel:
    """Wrapper for a specific medical diagnosis model."""

    def __init__(self, model_name, model_path, class_path, device="cpu"):
        self.model_name = model_name
        self.model_path = model_path
        self.class_path = class_path
        self.device = device
        self.classes = []
        self.model = None
        self.arch = None
        self.input_size = 224
        self._transform = None

    @property
    def transform(self):
        if self._transform is None:
            self._transform = transforms.Compose([
                transforms.Resize((self.input_size, self.input_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ])
        return self._transform

    def load(self):
        """Load class labels and model weights, verifying SHA-256 integrity and safe weights-only loading."""
        if not os.path.exists(self.model_path):
            logger.warning(f"[{self.model_name}] Model weights artifact missing")
            return False
        if not os.path.exists(self.class_path):
            logger.warning(f"[{self.model_name}] Class label definition missing")
            return False

        # Security Pre-flight: verify checkpoint SHA-256 hash against pinned trusted hashes
        base_name = os.path.basename(self.model_path)
        expected_sha = TRUSTED_CHECKPOINT_HASHES.get(base_name)
        if expected_sha:
            hasher = hashlib.sha256()
            try:
                with open(self.model_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                actual_sha = hasher.hexdigest().lower()
                if actual_sha != expected_sha.lower():
                    logger.error(
                        f"[{self.model_name}] Checkpoint hash mismatch! Expected {expected_sha}, got {actual_sha}. Loading aborted for security."
                    )
                    return False
                logger.info(f"[{self.model_name}] Cryptographic integrity verified: {expected_sha[:16]}...")
            except Exception as e:
                logger.error(f"[{self.model_name}] Failed to verify file integrity hash: {type(e).__name__}")
                return False

        try:
            self.classes = _parse_class_file(self.class_path)
            num_classes = len(self.classes)
            if num_classes == 0:
                logger.error(f"[{self.model_name}] Class file empty or invalid")
                return False
            logger.info(f"[{self.model_name}] Loaded {num_classes} classes")

            # Safe loading with strict weights_only=True (never executes arbitrary pickle payloads)
            try:
                checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
            except Exception as e:
                logger.error(f"[{self.model_name}] Safe weights_only loading failed: %s", type(e).__name__)
                return False

            if checkpoint is None:
                logger.error(f"[{self.model_name}] Checkpoint could not be deserialized")
                return False

            state_dict, metadata = _unwrap_state_dict(checkpoint)
            if not isinstance(state_dict, dict) or not state_dict:
                logger.error(f"[{self.model_name}] Malformed checkpoint: state_dict is not a dictionary")
                return False

            if "image_size" in metadata:
                img_size = metadata["image_size"]
                if isinstance(img_size, (list, tuple)):
                    self.input_size = img_size[0]
                else:
                    self.input_size = int(img_size)
                logger.info(f"[{self.model_name}] Image size from metadata: {self.input_size}")

            arch = _detect_architecture(state_dict.keys())
            self.arch = arch
            logger.info(f"[{self.model_name}] Detected architecture: {arch}")

            if arch == "unknown":
                logger.error(f"[{self.model_name}] Could not detect architecture")
                return False

            model, default_size = _build_model(arch, num_classes, state_dict)
            if model is None:
                logger.error(f"[{self.model_name}] Failed to build model for arch={arch}")
                return False

            if "image_size" not in metadata and default_size:
                self.input_size = default_size

            self._transform = None
            self.model = model
            self.model.to(self.device)
            self.model.eval()
            logger.info(
                f"[{self.model_name}] Loaded successfully: {arch}, "
                f"{num_classes} classes, input {self.input_size}x{self.input_size}"
            )
            return True
        except Exception as e:
            logger.error(f"[{self.model_name}] Error loading model: %s", type(e).__name__)
            return False


    def predict(self, image: Image.Image):
        """Return top-5 predictions and the top confidence."""
        if self.model is None:
            return [], 0.0

        img_tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.model(img_tensor)
            probs = F.softmax(output, dim=1)
            k = min(5, len(self.classes))
            values, indices = torch.topk(probs, k)

            predictions = []
            for i in range(k):
                predictions.append({
                    "disease": self.classes[indices[0][i].item()],
                    "confidence": round(float(values[0][i]), 4),
                })

            top_confidence = float(values[0][0])
            return predictions, top_confidence


# ═══════════════════════════════════════════════════════════════
# DISEASE CLASSIFIER  (rewritten with CLIP + hard modality lock)
# ═══════════════════════════════════════════════════════════════

class _ModelDict(dict):
    """Custom dictionary that tracks explicit user or test modifications."""
    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = owner

    def pop(self, *args, **kwargs):
        if self._owner is not None:
            self._owner._explicitly_configured_models = True
        return super().pop(*args, **kwargs)

    def clear(self):
        if self._owner is not None:
            self._owner._explicitly_configured_models = True
        super().clear()

    def __delitem__(self, key):
        if self._owner is not None:
            self._owner._explicitly_configured_models = True
        super().__delitem__(key)


class DiseaseClassifier:
    """Orchestrates multi-model disease classification with CLIP domain routing and lazy loading."""

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._explicitly_configured_models = False
        self._models: Dict[str, MedicalModel] = _ModelDict(self)
        self.base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
        )
        self.model_status: Dict[str, str] = {
            "skin": "unloaded",
            "xray": "unloaded",
            "retina": "unloaded",
            "general": "unloaded",
        }
        self._model_load_locks: Dict[str, threading.Lock] = {
            "skin": threading.Lock(),
            "xray": threading.Lock(),
            "retina": threading.Lock(),
            "general": threading.Lock(),
        }

        from app.core.config import ALLOW_MODEL_DOWNLOADS
        if ALLOW_MODEL_DOWNLOADS:
            self._download_models_if_missing()
        else:
            logger.info("Automatic model artifact downloads disabled (ALLOW_MODEL_DOWNLOADS=false).")

        self.model_configs = self._discover_models()
        for domain in ["skin", "xray", "retina", "general"]:
            if domain in self.model_configs:
                self.model_status[domain] = "unloaded"
            else:
                self.model_status[domain] = "unavailable"

    def _download_models_if_missing(self):
        """Download the .pth models from a Hugging Face model repository if configured and permitted."""
        from app.core.config import ALLOW_MODEL_DOWNLOADS
        if not ALLOW_MODEL_DOWNLOADS:
            logger.info("Automatic model artifact downloads disabled (ALLOW_MODEL_DOWNLOADS=false).")
            return False

        repo_id = os.environ.get("HF_MODEL_REPO")
        hf_token = os.environ.get("HF_TOKEN")


        expected_files = {
            "skin": "skin_disease_model.pth",
            "xray": "xray_fracture_model.pth",
            "retina": "retina_model.pth",
            "general": "general_disease_model.pth",
        }

        os.makedirs(self.base_dir, exist_ok=True)

        missing_any = False
        try:
            files = os.listdir(self.base_dir)
            for kw, _ in expected_files.items():
                has_pth = any(kw in f.lower() and f.endswith(".pth") for f in files)
                if not has_pth:
                    missing_any = True
                    break
        except Exception:
            missing_any = True

        if not missing_any:
            logger.info("All medical model files verified present locally.")
            return

        if not repo_id:
            logger.warning(
                "HF_MODEL_REPO environment variable is not configured. "
                "Hugging Face model download skipped. Specialist models will be marked unavailable."
            )
            return

        logger.info("Downloading missing model artifacts from Hugging Face Repo: %s...", repo_id)

        try:
            from huggingface_hub import hf_hub_download
            import shutil

            for kw, filename in expected_files.items():
                dest_path = os.path.join(self.base_dir, filename)
                try:
                    current_files = os.listdir(self.base_dir)
                except Exception:
                    current_files = []
                has_pth = any(kw in f.lower() and f.endswith(".pth") for f in current_files)
                if not has_pth:
                    logger.info(f"[{kw}] Downloading {filename} from HF {repo_id}...")
                    try:
                        downloaded_path = hf_hub_download(
                            repo_id=repo_id,
                            filename=filename,
                            repo_type="model",
                            token=hf_token,
                        )
                        shutil.copy(downloaded_path, dest_path)
                        logger.info(f"[{kw}] Successfully downloaded and copied model.")
                    except Exception as e:
                        logger.warning(f"[{kw}] Model download failed: %s", type(e).__name__)
                        break
        except Exception as e:
            logger.warning("HuggingFace model downloader failed: %s", type(e).__name__)

    def _discover_models(self) -> Dict[str, Dict[str, str]]:
        """Automatically find model and class files in the models directory."""
        configs = {}
        keywords = ["skin", "xray", "retina", "general"]

        if not os.path.exists(self.base_dir):
            return configs

        try:
            files = os.listdir(self.base_dir)
            for kw in keywords:
                pth_file = next((f for f in files if kw in f.lower() and f.endswith(".pth")), None)
                txt_file = next((f for f in files if kw in f.lower() and f.endswith(".txt")), None)
                if kw == "skin" and not txt_file:
                    txt_file = next((f for f in files if f.lower() == "classes.txt"), None)
                if pth_file and txt_file:
                    configs[kw] = {
                        "pth": os.path.join(self.base_dir, pth_file),
                        "txt": os.path.join(self.base_dir, txt_file),
                    }
                    logger.info("Discovered %s model configuration: %s with %s", kw, pth_file, txt_file)
        except Exception as e:
            logger.error("Error during model discovery: %s", type(e).__name__)

        return configs

    @property
    def models(self) -> Dict[str, MedicalModel]:
        return self._models

    @models.setter
    def models(self, value):
        self._models = _ModelDict(self, value or {})
        self._explicitly_configured_models = True

    def get_specialist_model(self, domain: str) -> Optional[MedicalModel]:
        """
        Lazy-load a specialist model on demand with double-checked locking stampede protection.
        Explicitly tracks lifecycle states: unloaded -> loading -> ready | failed | unavailable.
        """
        # If model is already loaded or pre-injected (e.g. in test fixtures), return immediately
        if domain in self._models and self._models[domain] is not None:
            self.model_status[domain] = "ready"
            return self._models[domain]

        # If models were explicitly configured or emptied by caller/tests, do not auto-load from disk
        if self._explicitly_configured_models:
            self.model_status[domain] = "unavailable"
            return None

        if domain not in self.model_configs:
            self.model_status[domain] = "unavailable"
            return None

        if self.model_status.get(domain) in ("unavailable", "failed"):
            return None


        lock = self._model_load_locks.get(domain)
        if not lock:
            lock = threading.Lock()
            self._model_load_locks[domain] = lock

        with lock:
            if self.model_status.get(domain) == "ready" and domain in self.models:
                return self.models[domain]
            if self.model_status.get(domain) in ("unavailable", "failed"):
                return None

            self.model_status[domain] = "loading"
            logger.info("Lazy-loading specialist model for domain '%s'...", domain)
            paths = self.model_configs[domain]
            model = MedicalModel(domain, paths["pth"], paths["txt"], self.device)
            if model.load():
                self.models[domain] = model
                self.model_status[domain] = "ready"
                logger.info("Specialist model '%s' is now READY", domain)
                return model
            else:
                self.model_status[domain] = "failed"
                logger.warning("Specialist model '%s' FAILED to load", domain)
                return None

    def initialize_models(self):
        """Pre-load all discovered specialist models."""
        logger.info("Initializing multi-model disease classifier...")
        for name in list(self.model_configs.keys()):
            self.get_specialist_model(name)
        ready_models = [k for k, v in self.model_status.items() if v == "ready"]
        logger.info(
            "Disease classifier initialization complete — %d model(s) ready: %s",
            len(ready_models), ready_models
        )

        from app.core.config import ALLOW_MODEL_DOWNLOADS
        if ALLOW_MODEL_DOWNLOADS:
            try:
                _get_clip()
            except Exception as e:
                logger.warning("CLIP pre-warm failed: %s", type(e).__name__)


    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _first_clean_prediction(predictions):
        """
        Return the first valid non-artifact prediction, or None.
        Preserves valid negative/normal classes without suppressing them.
        """
        for p in predictions:
            name = p["disease"].lower().strip()
            if name not in DATASET_ARTIFACT_CLASSES:
                return p["disease"], p["confidence"]
        return None, 0.0

    @staticmethod
    def _format_disease(category, raw_name):
        """Format a disease, condition, or reference finding name for display."""
        if not raw_name:
            return ""
        key = raw_name.lower().strip()
        # Handle legitimate negative / normal reference classes
        if key in {"normal", "normal cases"}:
            return "Normal Reference Finding"
        if key == "notumor":
            return "No Tumor Detected (Reference Normal)"
        if key in {"notinfected", "uninfected"}:
            return "Uninfected / Negative Finding"
        if key == "non-covid":
            return "Non-COVID Finding"
        if key in {"bengin cases", "benign"}:
            return "Benign Finding"
        if key == "healthy eye (no observable ocular disease)":
            return "Healthy Eye (No Observable Ocular Disease)"
        if category == "general" and key in GENERAL_DISPLAY:
            return GENERAL_DISPLAY[key]
        if category == "retina":
            return raw_name
        if category == "xray" and key in XRAY_CONDITIONS:
            return raw_name.title()
        return raw_name.replace("_", " ").title()

    def _interpret_xray_predictions(self, predictions, raw_conf):
        """
        Interpret predictions from the X-ray specialist model.
        Guarantees:
        - Anatomical classes (wrist, elbow, etc.) are treated as anatomy, NOT disease.
        - Never manufactures an abnormality or fracture from a body-part prediction.
        - Never promotes a low-ranked fracture or pneumonia when top prediction is anatomy.
        - If top prediction is an artifact, returns inconclusive.
        """
        if not predictions:
            return {
                "status": "inconclusive",
                "reason": "empty_predictions",
                "message": "Model returned no predictions.",
                "disease": None,
                "score": 0.0,
                "predictions": [],
            }

        top_p = predictions[0]
        top_name = top_p["disease"].lower().strip()
        top_score = float(top_p["confidence"])

        # Check if top prediction is an invalid artifact
        if top_name in DATASET_ARTIFACT_CLASSES:
            return {
                "status": "inconclusive",
                "reason": "top_prediction_is_artifact",
                "message": "Highest-ranked prediction is an unvalidated dataset artifact. Automatic disease promotion suppressed.",
                "artifact_class": top_p["disease"],
                "disease": None,
                "score": 0.0,
                "predictions": [],
            }

        # Case 1: Top prediction is an anatomical location (e.g. wrist = 0.95)
        if top_name in XRAY_BODY_PARTS:
            part = top_p["disease"].title()
            formatted_preds = [
                {
                    "disease": self._format_disease("xray", p["disease"]),
                    "score": round(float(p["confidence"]), 4),
                    "confidence": round(float(p["confidence"]), 4),
                }
                for p in predictions
                if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
            ][:5]

            return {
                "status": "analysis_complete",
                "finding_type": "anatomy_identified",
                "is_negative_finding": False,
                "disease": f"Anatomy Identified: {part} (No pathology classified)",
                "anatomical_region": part,
                "score": round(top_score, 4),
                "clinical_note": (
                    f"The model identified visual features consistent with the {part} anatomical region. "
                    "This prototype model classifies anatomical regions and selected conditions, but cannot reliably "
                    "assess, confirm, or rule out fractures, fissures, soft-tissue injuries, or other skeletal abnormalities, "
                    "and cannot determine the presence or absence of an abnormality. "
                    "Anatomical identification must NOT be interpreted as proof that no abnormality exists. "
                    "A qualified radiologist or physician must evaluate the radiograph in person."
                ),
                "predictions": formatted_preds,
            }

        # Case 2: Top prediction is a valid negative finding
        if top_name in VALID_NEGATIVE_CLASSES:
            display = self._format_disease("xray", top_p["disease"])
            formatted_preds = [
                {
                    "disease": self._format_disease("xray", p["disease"]),
                    "score": round(float(p["confidence"]), 4),
                    "confidence": round(float(p["confidence"]), 4),
                }
                for p in predictions
                if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
            ][:5]
            return {
                "status": "analysis_complete",
                "finding_type": "normal_or_negative",
                "is_negative_finding": True,
                "disease": display,
                "raw_prediction": top_p["disease"],
                "score": round(top_score, 4),
                "clinical_note": (
                    f"Model identified features matching '{display}'. "
                    "This is an uncalibrated algorithmic output and does not establish medical health or rule out clinical conditions."
                ),
                "predictions": formatted_preds,
            }

        # Case 3: Top prediction is an actual medical condition (fracture or pneumonia)
        if top_name in XRAY_CONDITIONS:
            cond = top_name.title()
            # If an anatomy class appears as a secondary finding, we can note it
            secondary_anatomy = next(
                (p["disease"].title() for p in predictions[1:] if p["disease"].lower().strip() in XRAY_BODY_PARTS),
                None
            )
            display = f"{secondary_anatomy} {cond}" if secondary_anatomy else cond

            formatted_preds = [
                {
                    "disease": self._format_disease("xray", p["disease"]),
                    "score": round(float(p["confidence"]), 4),
                    "confidence": round(float(p["confidence"]), 4),
                }
                for p in predictions
                if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
            ][:5]

            return {
                "status": "analysis_complete",
                "finding_type": "condition_detected",
                "is_negative_finding": False,
                "disease": display,
                "anatomical_region": secondary_anatomy,
                "score": round(top_score, 4),
                "predictions": formatted_preds,
            }

        # Case 4: Any other non-artifact class
        display = self._format_disease("xray", top_p["disease"])
        formatted_preds = [
            {
                "disease": self._format_disease("xray", p["disease"]),
                "score": round(float(p["confidence"]), 4),
                "confidence": round(float(p["confidence"]), 4),
            }
            for p in predictions
            if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
        ][:5]

        return {
            "status": "analysis_complete",
            "finding_type": "condition_detected",
            "is_negative_finding": False,
            "disease": display,
            "score": round(top_score, 4),
            "predictions": formatted_preds,
        }

    def _get_xray_diagnosis(self, predictions):
        """Backward-compatible helper wrapping _interpret_xray_predictions."""
        res = self._interpret_xray_predictions(predictions, predictions[0]["confidence"] if predictions else 0.0)
        return res.get("disease"), res.get("score", 0.0)

    def _interpret_predictions(self, category: str, predictions: list, raw_conf: float):
        """
        Safely interpret predictions from specialist models.
        Enforces:
        - Highest-ranked valid negative class preserved (never promoted past).
        - Highest-ranked artifact class triggers inconclusive status (never promoted past).
        - Clean formatting of differential predictions.
        """
        if category == "xray":
            return self._interpret_xray_predictions(predictions, raw_conf)

        if not predictions:
            return {
                "status": "inconclusive",
                "reason": "empty_predictions",
                "message": "Model returned no predictions.",
                "disease": None,
                "score": 0.0,
                "predictions": [],
            }

        top_p = predictions[0]
        top_name = top_p["disease"].lower().strip()
        top_score = float(top_p["confidence"])

        # Check if top prediction is an invalid artifact
        if top_name in DATASET_ARTIFACT_CLASSES:
            return {
                "status": "inconclusive",
                "reason": "top_prediction_is_artifact",
                "message": (
                    "The highest-ranked model prediction is an unvalidated dataset artifact. "
                    "Automatic promotion of lower-ranked conditions is suppressed."
                ),
                "artifact_class": top_p["disease"],
                "disease": None,
                "score": 0.0,
                "predictions": [],
            }

        # Check if top prediction is a legitimate normal or negative finding
        if top_name in VALID_NEGATIVE_CLASSES:
            display = self._format_disease(category, top_p["disease"])
            formatted_preds = [
                {
                    "disease": self._format_disease(category, p["disease"]),
                    "score": round(float(p["confidence"]), 4),
                    "confidence": round(float(p["confidence"]), 4),
                }
                for p in predictions
                if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
            ][:5]

            return {
                "status": "analysis_complete",
                "finding_type": "normal_or_negative",
                "is_negative_finding": True,
                "disease": display,
                "raw_prediction": top_p["disease"],
                "score": round(top_score, 4),
                "clinical_note": (
                    f"Model identified features matching '{display}'. "
                    "This is an uncalibrated algorithmic output and does not establish medical health or rule out clinical conditions."
                ),
                "predictions": formatted_preds,
            }

        # Safeguard: do not force a clinical disease prediction on diffuse/low-confidence model scores
        # (e.g. non-medical animal fur or non-dermatological surfaces with skin-like chroma)
        if category == "skin" and top_score < 0.12:
            return {
                "status": "inconclusive",
                "reason": "low_confidence_diffuse_distribution",
                "message": (
                    "Image analysis was inconclusive. Visual features do not match documented dermatological conditions with sufficient specificity. "
                    "Please ensure the image is a clear, well-lit medical photograph of the affected skin area, or consult a physician in person."
                ),
                "disease": None,
                "score": round(top_score, 4),
                "predictions": [],
            }

        # Top prediction is a condition / pathology
        display = self._format_disease(category, top_p["disease"])
        formatted_preds = [
            {
                "disease": self._format_disease(category, p["disease"]),
                "score": round(float(p["confidence"]), 4),
                "confidence": round(float(p["confidence"]), 4),
            }
            for p in predictions
            if p["disease"].lower().strip() not in DATASET_ARTIFACT_CLASSES
        ][:5]

        return {
            "status": "analysis_complete",
            "finding_type": "condition_detected",
            "is_negative_finding": False,
            "disease": display,
            "raw_prediction": top_p["disease"],
            "score": round(top_score, 4),
            "predictions": formatted_preds,
        }

    # ── main entry point ──────────────────────────────────────

    def classify(
        self,
        image: Image.Image,
        routed_category: str = None,
        modality_confirmed: bool = False,
    ) -> dict:
        """
        CLIP-routed classification with strict, hard modality locking.

        Guarantees:
        1. Only the matching specialist model executes (no cross-modality contamination).
        2. Missing specialist models return 'model_unavailable' (never fall back to general or all).
        3. Non-medical images return 'unsupported_image' without running medical disease models.
        4. Ambiguous or failed CLIP results return 'inconclusive'.
        5. Valid normal/negative classes are preserved as top findings without disease promotion.
        6. Top artifact predictions return 'inconclusive' without disease promotion.
        7. Model scores are explicitly uncalibrated (false confidence claims removed).
        """
        if image is None:
            return {
                "status": "invalid_image",
                "message": "No valid image provided for classification.",
                "category": None,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "predictions": [],
                "domain_hint": "unknown",
                "domain_scores": {},
                "domain_confidence": 0.0,
            }

        # ── 1. Multimodal Vision Understanding & Domain Detection ──
        from app.services.vision_service import vision_service

        understanding = vision_service.understand_image(image)
        logger.info(
            "Vision understanding: category=%s, subject=%s, is_medical=%s, engine=%s",
            understanding.get("category"),
            understanding.get("detected_subject"),
            understanding.get("is_medical"),
            understanding.get("engine"),
        )

        domain, domain_conf, domain_scores = detect_visual_domain(image)
        logger.info(f"CLIP domain detection: {domain} (conf={domain_conf:.3f})")

        # Reconcile CLIP domain with Vision understanding:
        # If Groq Vision AI identified the modality, use its multimodal inference
        if domain in ("unknown", "ambiguous"):
            if understanding.get("engine") in ("groq_vision", "local_neural_vision"):
                if understanding.get("is_medical", False) and understanding.get("modality"):
                    domain = understanding["modality"]
                    domain_conf = 0.90 if understanding.get("confidence") == "high" else 0.70
                    domain_scores = {domain: domain_conf}
                elif understanding.get("category") == "ambiguous":
                    domain = "ambiguous"
                    domain_conf = 0.20
                    domain_scores = {"ambiguous": 0.20}
                else:
                    domain = "non_medical"
                    domain_conf = 0.95
                    domain_scores = {"non_medical": 0.95}
            elif not understanding.get("is_medical", True) and understanding.get("category") not in ("ambiguous", "medical_xray", "medical_skin", "medical_retina"):
                domain = "non_medical"
                domain_conf = 0.85
                domain_scores = {"non_medical": 0.85}

        # If CLIP or fallback flagged non_medical, ensure understanding reflects non-medical
        if domain == "non_medical":
            understanding["is_medical"] = False
            understanding["medical_applicable"] = False

        # ── 2. Handle Corrupted / Invalid Image ──
        if understanding.get("category") == "invalid_image" or understanding.get("status") == "invalid_image":
            return {
                "status": "invalid_image",
                "message": understanding.get("reason_not_applicable") or "No valid image provided for classification.",
                "category": None,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "predictions": [],
                "vision_engine": understanding.get("engine", "heuristic_fallback"),
            }

        # ── 3. Routing & Override Safeguards ──
        VALID_SPECIALIST_MODALITIES = {"skin", "xray", "retina", "general"}
        if routed_category and routed_category.lower().strip() in VALID_SPECIALIST_MODALITIES:
            routed_clean = routed_category.lower().strip()
            modality_source = "user_selected"
            target_category = routed_clean

            # Override Safeguard 1: If genuine Groq Vision or Local Neural Vision AI is active
            if understanding.get("engine") in ("groq_vision", "local_neural_vision"):
                should_reject = False
                if understanding.get("engine") == "groq_vision":
                    should_reject = not understanding.get("is_medical", False)
                elif understanding.get("engine") == "local_neural_vision":
                    should_reject = (
                        understanding.get("category") == "person"
                        or understanding.get("detected_subject") == "Portrait of Person"
                        or (
                            understanding.get("category") in ("animal", "vehicle", "plant", "food")
                            and understanding.get("confidence") == "high"
                        )
                    )

                if should_reject:
                    mismatch_explanation = (
                        f"User-selected modality '{routed_category}' does not match the uploaded image content "
                        f"({understanding.get('detected_subject', 'non-medical subject')}). "
                    )
                    base_reason = understanding.get("reason_not_applicable") or (
                        "The uploaded image does not appear to be a supported medical image."
                    )
                    full_message = f"{mismatch_explanation}{base_reason}".strip()
                    logger.info("Override rejected on non-medical image: %s", understanding.get("detected_subject"))

                    p_status = understanding.get("person_detection", understanding.get("person_detection_status", "unsupported"))
                    return {
                        "status": "unsupported_image",
                        "message": full_message,
                        "type": "general_image",
                        "category": "non_medical",
                        "detected_category": understanding.get("category", "non_medical"),
                        "detected_subject": understanding.get("detected_subject", "Visible Subject"),
                        "description": understanding.get("description", full_message),
                        "is_person": None,
                        "person_detection": p_status,
                        "person_detection_status": p_status,
                        "medical_applicable": False,
                        "reason_not_applicable": understanding.get("reason_not_applicable"),
                        "safety_disclaimer": understanding.get("safety_disclaimer"),
                        "modality_source": "user_selected",
                        "override_rejected": True,
                        "override_rejection_reason": f"Selected modality '{routed_category}' is incompatible with detected content ({understanding.get('detected_subject')}).",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "calibrated_conf": None,
                        "calibrated_confidence": None,
                        "predictions": [],
                        "domain_hint": "non_medical",
                        "domain_scores": domain_scores if domain_scores else {"non_medical": 0.95},
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.95,
                        "vision_engine": understanding.get("engine", "groq_vision"),
                        "vision_model": understanding.get("vision_model"),
                    }
                elif understanding.get("modality") and understanding.get("modality").lower().strip() != routed_clean:
                    return {
                        "status": "inconclusive",
                        "message": (
                            f"User-selected modality '{routed_category}' does not match detected medical modality '{understanding.get('modality')}'. "
                            f"Please select '{understanding.get('modality')}' or allow automatic routing."
                        ),
                        "category": "modality_mismatch",
                        "detected_subject": understanding.get("detected_subject"),
                        "override_rejected": True,
                        "modality_source": "user_selected",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "vision_engine": understanding.get("engine", "groq_vision"),
                        "vision_model": understanding.get("vision_model"),
                    }

        else:
            # Automatic Intake (No Modality Override)
            modality_source = "auto_detected"

            # Case A: Multimodal Groq Vision is Active
            if understanding.get("engine") == "groq_vision":
                if not understanding.get("is_medical", False):
                    if understanding.get("category") == "ambiguous":
                        return {
                            "status": "inconclusive",
                            "message": understanding.get("reason_not_applicable") or "Image is too blurry or ambiguous.",
                            "type": "general_image",
                            "category": "ambiguous",
                            "detected_subject": understanding.get("detected_subject", "Ambiguous Image"),
                            "description": understanding.get("description"),
                            "medical_applicable": False,
                            "modality_source": "auto_detected",
                            "disease": None,
                            "score": 0.0,
                            "predictions": [],
                            "vision_engine": "groq_vision",
                        }

                    # Successful Universal General Recognition
                    return {
                        "status": "general_recognition",
                        "success": True,
                        "message": understanding.get("description", "Non-medical visual recognition complete."),
                        "type": "general_image",
                        "category": understanding.get("category", "non_medical"),
                        "detected_category": understanding.get("category", "non_medical"),
                        "detected_subject": understanding.get("detected_subject", "Visible Subject"),
                        "description": understanding.get("description"),
                        "is_person": understanding.get("is_person", False),
                        "medical_applicable": False,
                        "reason_not_applicable": understanding.get("reason_not_applicable"),
                        "safety_disclaimer": understanding.get("safety_disclaimer"),
                        "modality_source": "auto_detected",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "calibrated_conf": None,
                        "calibrated_confidence": None,
                        "predictions": [],
                        "domain_hint": "non_medical",
                        "domain_scores": domain_scores if domain_scores else {"non_medical": 0.95},
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.95,
                        "vision_engine": "groq_vision",
                        "vision_model": understanding.get("vision_model"),
                    }
                else:
                    # In automatic intake without explicit user selection, even if Groq vision detects medical modality,
                    # automatic clinical routing is disabled to protect patient safety.
                    return {
                        "status": "modality_selection_required",
                        "success": False,
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                        "message": (
                            "Automatic clinical routing is disabled to ensure patient safety. "
                            f"Identified potential {understanding.get('modality', 'clinical')} image ({understanding.get('detected_subject')}). "
                            "Please explicitly select the medical modality (Skin, X-ray, Retina) to proceed."
                        ),
                        "type": "medical_selection_required",
                        "category": understanding.get("modality", "ambiguous").lower().strip(),
                        "detected_category": "ambiguous",
                        "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
                        "description": understanding.get("description"),
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
                        "modality_source": "auto_intake_abstention",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "domain_hint": understanding.get("modality", "general"),
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "groq_vision",
                    }

            # Case B: Local Neural Vision (MobileNetV3) is Active
            elif understanding.get("engine") == "local_neural_vision":
                if understanding.get("is_person") is True or (understanding.get("status") == "general_recognition" and understanding.get("category") in ("person", "animal", "vehicle", "plant", "food", "object", "landscape")):
                    p_status = understanding.get("person_detection", understanding.get("person_detection_status", "unsupported" if understanding.get("is_person") is not True else "detected_portrait"))
                    is_person_val = True if understanding.get("is_person") is True else None if p_status == "unsupported" or understanding.get("is_person") is None else False
                    return {
                        "status": "general_recognition",
                        "success": True,
                        "message": understanding.get("description", "Non-medical visual recognition complete."),
                        "type": "general_image",
                        "category": understanding.get("category", "non_medical"),
                        "detected_category": understanding.get("category", "non_medical"),
                        "detected_subject": understanding.get("detected_subject", "Visible Subject"),
                        "description": understanding.get("description"),
                        "is_person": is_person_val,
                        "person_detection": p_status,
                        "person_detection_status": p_status,
                        "person_detection_note": understanding.get(
                            "person_detection_note",
                            "Person presence could not be reliably determined. Closed-set object classifier does not support general person detection."
                        ),
                        "medical_applicable": False,
                        "reason_not_applicable": understanding.get("reason_not_applicable"),
                        "safety_disclaimer": understanding.get("safety_disclaimer"),
                        "modality_source": "auto_detected",
                        "disease": None,
                        "score": understanding.get("top1_prob", 0.0),
                        "confidence": 0.0,
                        "calibrated_conf": None,
                        "calibrated_confidence": None,
                        "top1_class": understanding.get("top1_name"),
                        "top1_name": understanding.get("top1_name"),
                        "top1_prob": understanding.get("top1_prob"),
                        "raw_score": understanding.get("top1_prob"),
                        "top1_idx": understanding.get("top1_idx"),
                        "predictions": understanding.get("top5", []),
                        "domain_hint": "non_medical",
                        "domain_scores": domain_scores if domain_scores else {"non_medical": 0.95},
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.95,
                        "vision_engine": "local_neural_vision",
                        "vision_model": understanding.get("vision_model"),
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    }
                elif domain == "non_medical":
                    return {
                        "status": "unsupported_image",
                        "message": "The uploaded image does not appear to be a supported medical image.",
                        "type": "general_image",
                        "category": "non_medical",
                        "detected_category": "non_medical",
                        "detected_subject": understanding.get("detected_subject", "Non-Medical Image"),
                        "description": understanding.get("description", "Image does not match supported medical modalities."),
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Non-medical imagery is outside medical intake scope.",
                        "modality_source": "auto_detected",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "local_neural_vision",
                        "top1_class": understanding.get("top1_name"),
                        "top1_prob": understanding.get("top1_prob"),
                        "raw_score": understanding.get("top1_prob"),
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    }
                elif understanding.get("status") == "ambiguous" or (domain in ("unknown", "ambiguous") and understanding.get("status") != "modality_selection_required"):
                    return {
                        "status": "inconclusive",
                        "message": "Image modality could not be reliably determined from visual features. Please select a specific modality or upload a clearer clinical image.",
                        "category": "ambiguous",
                        "detected_category": "ambiguous",
                        "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
                        "description": understanding.get("description", "Image modality could not be determined without explicit user selection."),
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Image modality could not be reliably determined from visual features.",
                        "modality_source": "auto_intake_abstention",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": understanding.get("top5", []),
                        "top1_class": understanding.get("top1_name"),
                        "top1_prob": understanding.get("top1_prob"),
                        "raw_score": understanding.get("top1_prob"),
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "local_neural_vision",
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    }
                else:
                    # Unrecognized / Ambiguous under Local Neural Vision without explicit modality selection
                    # SAFETY RULE: Never route to specialist models on colour/contrast or unvalidated visual heuristics without explicit selection.
                    return {
                        "status": "modality_selection_required",
                        "success": False,
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                        "message": (
                            "Automatic clinical routing is disabled to prevent unvalidated heuristic diagnosis. "
                            "If this is a clinical image, please select the specific modality (Skin, X-ray, Retina) to proceed."
                        ),
                        "type": "medical_selection_required",
                        "category": "ambiguous",
                        "detected_category": "ambiguous",
                        "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
                        "description": understanding.get("description", "Image modality could not be determined without explicit user selection."),
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
                        "modality_source": "auto_intake_abstention",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": understanding.get("top5", []),
                        "top1_class": understanding.get("top1_name"),
                        "top1_prob": understanding.get("top1_prob"),
                        "raw_score": understanding.get("top1_prob"),
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "local_neural_vision",
                    }

            # Case C: Offline Heuristic / CLIP Fallback
            else:
                if domain == "non_medical":
                    return {
                        "status": "unsupported_image",
                        "message": "The uploaded image does not appear to be a supported medical image.",
                        "type": "general_image",
                        "category": "non_medical",
                        "detected_category": "non_medical",
                        "detected_subject": "Non-Medical Subject",
                        "description": "Image features identified as non-medical content.",
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Non-medical imagery is outside medical intake scope.",
                        "modality_source": "auto_detected",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "domain_hint": "non_medical",
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "heuristic_fallback",
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    }
                elif domain in ("unknown", "ambiguous"):
                    return {
                        "status": "inconclusive",
                        "message": "Image modality could not be reliably determined from visual features. Please select a specific modality or upload a clearer clinical image.",
                        "category": "ambiguous",
                        "detected_category": "ambiguous",
                        "detected_subject": "Unrecognized Visual Subject",
                        "description": "Image domain could not be reliably determined from visual features.",
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Image modality could not be reliably determined from visual features.",
                        "modality_source": "auto_intake_abstention",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "heuristic_fallback",
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                    }
                else:
                    # Ambiguous or potential medical domain without explicit user modality selection
                    # SAFETY RULE: Never route to specialist models on colour/contrast or unvalidated visual heuristics without explicit selection.
                    logger.info("Automatic medical intake abstention: explicit user modality selection required.")
                    return {
                        "status": "modality_selection_required",
                        "success": False,
                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                        "message": (
                            "Automatic clinical routing is disabled to prevent unvalidated heuristic diagnosis. "
                            "If this is a clinical image, please select the specific modality (Skin, X-ray, Retina) to proceed."
                        ),
                        "type": "medical_selection_required",
                        "category": domain if domain != "unknown" else "ambiguous",
                        "detected_category": "ambiguous",
                        "detected_subject": "Unrecognized Visual Subject",
                        "description": "Image domain could not be reliably determined without explicit modality selection.",
                        "is_person": False,
                        "medical_applicable": False,
                        "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
                        "modality_source": "auto_intake_abstention",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "predictions": [],
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                        "vision_engine": "heuristic_fallback",
                    }

        # ── 4. General Disease Model Scope Audit & Safety Guard ──
        # The general disease model (DenseNet-121, 69 classes) is trained specifically on brain MRI,
        # hematology microscopy, oral lesions, wounds/burns, and lung CT. Do not allow it to act
        # as an arbitrary catch-all for unrelated medical imagery (e.g. ear endoscopy, ultrasound).
        if target_category == "general" and understanding.get("engine") == "groq_vision":
            subj_text = (
                str(understanding.get("detected_subject", "")) + " " +
                str(understanding.get("description", ""))
            ).lower()
            supported_keywords = [
                "mri", "brain", "neuro", "blood", "microscop", "smear", "cell",
                "wound", "burn", "ulcer", "lacerat", "cut", "dental", "tooth",
                "teeth", "gingiv", "oral", "covid", "ct scan", "slide", "tissue"
            ]
            if not any(kw in subj_text for kw in supported_keywords):
                logger.warning(
                    "General model requested for unsupported medical subject: %s",
                    understanding.get("detected_subject")
                )
                return {
                    "status": "inconclusive",
                    "message": (
                        f"The uploaded medical image ({understanding.get('detected_subject', 'medical image')}) is outside the scope of our supported specialist models "
                        "(Skin Dermatology, Bone/Chest X-ray, Retinal Fundus, Brain MRI, Blood Smear Microscopy, Wounds/Burns). "
                        "Please consult a qualified medical specialist for clinical evaluation."
                    ),
                    "category": "unsupported_medical",
                    "detected_subject": understanding.get("detected_subject"),
                    "description": understanding.get("description"),
                    "modality_source": modality_source,
                    "disease": None,
                    "score": 0.0,
                    "confidence": 0.0,
                    "calibrated_conf": None,
                    "calibrated_confidence": None,
                    "domain_hint": "general",
                    "domain_scores": domain_scores,
                    "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                    "predictions": [],
                    "vision_engine": understanding.get("engine", "vision_service"),
                }

        # ── 5. SAFETY INVARIANT GATE: Refuse specialist dispatch without explicit user modality selection ──
        if (
            modality_source != "user_selected"
            or not routed_category
            or not target_category
            or target_category not in VALID_SPECIALIST_MODALITIES
        ):
            logger.warning("SAFETY INVARIANT ENFORCED: Refusing specialist dispatch without valid explicit user modality selection.")
            p_status = understanding.get("person_detection", understanding.get("person_detection_status", "unsupported"))
            raw_is_person = understanding.get("is_person")
            is_person_val = True if raw_is_person is True else None if p_status == "unsupported" or raw_is_person is None else False
            return {
                "status": "modality_selection_required",
                "success": False,
                "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
                "message": (
                    "Automatic clinical routing is disabled to ensure patient safety. "
                    "A valid explicit modality selection (Skin, X-ray, Retina, General) is required to invoke specialist models."
                ),
                "type": "medical_selection_required",
                "category": target_category or "ambiguous",
                "detected_category": "ambiguous",
                "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
                "description": understanding.get("description", "Image modality could not be determined without explicit user selection."),
                "is_person": is_person_val,
                "person_detection": p_status,
                "person_detection_status": p_status,
                "person_detection_note": understanding.get("person_detection_note", "Person presence could not be reliably determined."),
                "medical_applicable": False,
                "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
                "modality_source": "auto_intake_abstention",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "predictions": [],
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                "vision_engine": understanding.get("engine", "local_neural_vision"),
            }

        # ── 5b. CLINICAL GOVERNANCE GATE: Check whether specialist models are enabled ──
        from app.core.config import is_clinical_specialist_enabled
        if not is_clinical_specialist_enabled():
            logger.info("Clinical specialist inference gate: unvalidated diagnostic models disabled in this environment.")
            return {
                "status": "clinical_analysis_disabled",
                "success": False,
                "type": "clinical_disabled",
                "message": (
                    "Clinical specialist analysis is disabled in this release pending formal clinical validation "
                    "and regulatory review. General image recognition remains available."
                ),
                "category": target_category,
                "modality_source": modality_source,
                "clinical_governance_status": "NOT_CLINICALLY_VALIDATED",
                "medical_applicable": False,
                "safety_notice": "Unvalidated diagnostic specialist models are disabled by default in production.",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "predictions": [],
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                "vision_engine": understanding.get("engine", "local_neural_vision"),
            }

        # ── 5c. RESEARCH MODE CONFIRMATION GATE: Require explicit confirmation in non-production research mode ──
        if not modality_confirmed:
            logger.info("Research mode gate: explicit user modality confirmation required.")
            p_status = understanding.get("person_detection", understanding.get("person_detection_status", "unsupported"))
            raw_is_person = understanding.get("is_person")
            is_person_val = True if raw_is_person is True else None if p_status == "unsupported" or raw_is_person is None else False
            return {
                "status": "modality_confirmation_required",
                "success": False,
                "type": "confirmation_required",
                "message": (
                    f"Explicit modality confirmation required for research evaluation of '{target_category}'. "
                    "Please confirm that the uploaded image matches this medical modality and acknowledge "
                    "that this is an unvalidated prototype model intended solely for research evaluation."
                ),
                "category": target_category,
                "modality_source": "user_selected_unconfirmed",
                "requires_confirmation": True,
                "research_disclaimer": (
                    "RESEARCH ONLY — NOT FOR CLINICAL USE: This prototype model has not undergone clinical trials, "
                    "regulatory clearance, or formal medical device validation. Results must never be used for diagnosis, "
                    "prognosis, or treatment decisions."
                ),
                "detected_category": understanding.get("category", "ambiguous"),
                "detected_subject": understanding.get("detected_subject", "Medical Specimen"),
                "description": understanding.get("description", "Awaiting explicit modality confirmation."),
                "is_person": is_person_val,
                "person_detection": p_status,
                "person_detection_status": p_status,
                "medical_applicable": False,
                "reason_not_applicable": "Explicit modality confirmation required for research evaluation.",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "predictions": [],
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                "vision_engine": understanding.get("engine", "local_neural_vision"),
            }

        # ── 5d. PORTRAIT MEDICAL PROHIBITION: Ordinary portraits must never receive medical diagnosis ──
        if understanding.get("category") == "person" or understanding.get("detected_subject") == "Portrait of Person":
            logger.warning("SAFETY INVARIANT ENFORCED: Refusing medical diagnosis on portrait photograph.")
            return {
                "status": "unsupported_image",
                "success": False,
                "type": "general_image",
                "category": "non_medical",
                "detected_category": "person",
                "detected_subject": "Portrait of Person",
                "description": "A photograph depicting a human portrait. Personal identity and clinical disease inference are strictly prohibited.",
                "message": "Personal identity and clinical disease inference are strictly prohibited on ordinary portraits. Photographs of people cannot be used for clinical medical diagnosis.",
                "is_person": None,
                "person_detection": "unsupported",
                "person_detection_status": "unsupported",
                "medical_applicable": False,
                "reason_not_applicable": "This is an ordinary photograph of a person. Ordinary photographs cannot be used for clinical medical diagnosis.",
                "safety_disclaimer": "Real-person facial recognition and medical disease inference are strictly prohibited on ordinary portraits.",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "predictions": [],
                "domain_hint": "non_medical",
                "domain_scores": {"non_medical": 1.0},
                "domain_confidence": 1.0,
                "vision_engine": understanding.get("engine", "local_neural_vision"),
            }

        # ── 6. HARD MODALITY LOCK: Check model availability with lazy loading ──
        model = self.get_specialist_model(target_category)
        if not model or target_category not in self.models:
            cat_display = {
                "skin": "Skin / Dermatology",
                "xray": "X-ray / Radiograph",
                "retina": "Retinal Fundus",
                "general": "General Medical",
            }.get(target_category, target_category.title())
            logger.warning(
                "HARD MODALITY LOCK: Domain '%s' detected, but specialist model NOT LOADED or failed (status=%s). "
                "Refusing unsafe fallback to general or other models.",
                target_category,
                self.model_status.get(target_category, "unavailable"),
            )
            return {
                "status": "model_unavailable",
                "message": (
                    f"Specialist AI model for '{target_category}' is not loaded on this server. "
                    f"The {cat_display} category was recognized, but the specialist deep learning analysis "
                    "model is currently unavailable on this server. No disease classification was performed."
                ),
                "category": target_category,
                "modality_source": modality_source,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                "predictions": [],
                "symptom_interview_suggested": True,
                "follow_up_prompt": f"Would you like to describe your symptoms or clinical history related to this {cat_display} condition in the chat for educational intake guidance?",
            }

        # ── 6. Execute ONLY the matching specialist model ──
        try:
            preds, raw_conf = model.predict(image)
        except Exception as e:
            logger.error("Inference error in '%s' specialist model: %s", target_category, type(e).__name__)

            return {
                "status": "inconclusive",
                "message": f"An error occurred during {target_category} model inference.",
                "category": target_category,
                "modality_source": modality_source,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
                "predictions": [],
                "error": "Inference failure",
            }

        # ── 7. Safe, uncalibrated prediction interpretation ──
        interp = self._interpret_predictions(target_category, preds, raw_conf)
        interp["category"] = target_category
        interp["modality_source"] = modality_source
        interp["detected_subject"] = understanding.get("detected_subject")
        interp["description"] = understanding.get("description")
        interp["is_person"] = None
        interp["person_detection"] = "unsupported"
        interp["person_detection_status"] = "unsupported"
        interp["modality_confirmed"] = True
        interp["research_disclaimer"] = (
            "RESEARCH PROTOTYPE ONLY — NOT FOR DIAGNOSTIC OR CLINICAL USE. "
            "This analysis was performed in non-production research mode with explicit user modality confirmation."
        )
        interp["medical_applicable"] = True
        interp["domain_hint"] = domain
        interp["domain_scores"] = domain_scores
        interp["domain_confidence"] = round(domain_conf, 4) if domain_conf else 0.0
        interp["confidence"] = interp.get("score", 0.0)  # Deprecated alias for raw score
        interp["calibrated_conf"] = None  # Deprecated
        interp["calibrated_confidence"] = None  # Deprecated
        interp["score_interpretation"] = "Unvalidated model score; not a calibrated clinical probability."
        return interp


# Module-level singleton
disease_classifier = DiseaseClassifier()
