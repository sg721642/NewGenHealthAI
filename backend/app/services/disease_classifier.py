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
import threading
from typing import Dict, Optional, Tuple

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

        # ── SECONDARY VALIDATION ──
        # If the top domain confidence is low (<0.30), check if any medical
        # domain is close.  This prevents a borderline medical image from
        # being routed to "non_medical".
        if best_domain == "non_medical" and best_conf < 0.45:
            # Sum up all medical domain probabilities
            medical_sum = sum(
                float(probs[i]) for i in range(4)  # skin + xray + retina + general
            )
            if medical_sum > 0.55:
                # Re-pick the best medical domain
                medical_probs = {CLIP_DOMAIN_MAP[i]: float(probs[i]) for i in range(4)}
                best_medical = max(medical_probs, key=medical_probs.get)
                logger.info(
                    f"CLIP secondary validation: overriding non_medical -> {best_medical} "
                    f"(medical_sum={medical_sum:.3f})"
                )
                return best_medical, medical_probs[best_medical], scores

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
            for model_name in ["tf_efficientnet_b4_ns", "efficientnet_b4", "tf_efficientnet_b4"]:
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
        """Load class labels and model weights, auto-detecting architecture."""
        if not os.path.exists(self.model_path):
            logger.warning(f"[{self.model_name}] Model weights artifact missing")
            return False
        if not os.path.exists(self.class_path):
            logger.warning(f"[{self.model_name}] Class label definition missing")
            return False

        try:
            self.classes = _parse_class_file(self.class_path)
            num_classes = len(self.classes)
            if num_classes == 0:
                logger.error(f"[{self.model_name}] Class file empty or invalid")
                return False
            logger.info(f"[{self.model_name}] Loaded {num_classes} classes")

            # Safe loading attempting weights_only=True without PyTorch version spoofing
            checkpoint = None
            try:
                checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=True)
            except Exception:
                # If weights_only fails on legacy pickled state dictionaries, attempt load without version spoofing
                try:
                    checkpoint = torch.load(self.model_path, map_location=self.device)
                except Exception as inner_e:
                    logger.error(f"[{self.model_name}] Checkpoint loading failed: %s", type(inner_e).__name__)
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

class DiseaseClassifier:
    """Orchestrates multi-model disease classification with CLIP domain routing and lazy loading."""

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.models: Dict[str, MedicalModel] = {}
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

    def get_specialist_model(self, domain: str) -> Optional[MedicalModel]:
        """
        Lazy-load a specialist model on demand with double-checked locking stampede protection.
        Explicitly tracks lifecycle states: unloaded -> loading -> ready | failed | unavailable.
        """
        # If model is already loaded or pre-injected (e.g. in test fixtures), return immediately
        if domain in self.models and self.models[domain] is not None:
            self.model_status[domain] = "ready"
            return self.models[domain]

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
                    f"The model identified the anatomical region as {part}. "
                    "The classifier vocabulary does not provide evidence of fracture or pneumonia for this image, "
                    "and anatomical classification alone cannot determine the presence or absence of an abnormality."
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

    def classify(self, image: Image.Image, routed_category: str = None) -> dict:
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

        # ── 1. CLIP domain detection ──────────────────────────
        domain, domain_conf, domain_scores = detect_visual_domain(image)
        logger.info(f"CLIP domain detection: {domain} (conf={domain_conf:.3f})")

        # Non-medical image detection
        if domain == "non_medical" and domain_conf >= 0.40:
            logger.info("Image classified as non-medical — skipping disease models")
            return {
                "status": "unsupported_image",
                "message": "The uploaded image does not appear to be a supported medical image.",
                "category": "non_medical",
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": "non_medical",
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4),
                "predictions": [],
            }

        # Ambiguous or failed CLIP domain
        if domain in ("unknown", "ambiguous"):
            logger.warning("Modality could not be reliably determined from visual features: %s", domain)
            return {
                "status": "inconclusive",
                "message": "Image modality could not be reliably determined from visual features.",
                "category": domain,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4),
                "predictions": [],
            }

        # ── 2. Determine target modality with routed_category validation ──
        target_category = domain
        if routed_category:
            routed_clean = routed_category.lower().strip()
            if routed_clean in ("skin", "xray", "retina", "general"):
                if domain == "non_medical" and domain_conf >= 0.45:
                    return {
                        "status": "unsupported_image",
                        "message": "Uploaded image is non-medical; user-requested modality override rejected.",
                        "category": "non_medical",
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "calibrated_conf": None,
                        "calibrated_confidence": None,
                        "domain_hint": "non_medical",
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4),
                        "predictions": [],
                    }
                # Guard against conflicting distinct modalities (e.g. xray vs retina)
                if domain != "general" and routed_clean != domain and domain_conf >= 0.60:
                    logger.warning(
                        "Modality conflict: image detected as %s (conf=%.3f) but requested as %s",
                        domain, domain_conf, routed_clean
                    )
                    return {
                        "status": "inconclusive",
                        "message": (
                            f"Modality conflict: detected visual domain is '{domain}' but requested "
                            f"modality was '{routed_clean}'. Cross-modality inference prevented."
                        ),
                        "category": domain,
                        "disease": None,
                        "score": 0.0,
                        "confidence": 0.0,
                        "calibrated_conf": None,
                        "calibrated_confidence": None,
                        "domain_hint": domain,
                        "domain_scores": domain_scores,
                        "domain_confidence": round(domain_conf, 4),
                        "predictions": [],
                    }
                target_category = routed_clean

        # ── 3. HARD MODALITY LOCK: Check model availability with lazy loading ──
        model = self.get_specialist_model(target_category)
        if not model or target_category not in self.models:
            logger.warning(
                "HARD MODALITY LOCK: Domain '%s' detected, but specialist model NOT LOADED or failed (status=%s). "
                "Refusing unsafe fallback to general or other models.",
                target_category,
                self.model_status.get(target_category, "unavailable"),
            )
            return {
                "status": "model_unavailable",
                "message": f"Specialist AI model for '{target_category}' is not loaded on this server.",
                "category": target_category,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4),
                "predictions": [],
            }

        # ── 4. Execute ONLY the matching specialist model ──
        try:
            preds, raw_conf = model.predict(image)
        except Exception as e:
            logger.error("Inference error in '%s' specialist model: %s", target_category, type(e).__name__)

            return {
                "status": "inconclusive",
                "message": f"An error occurred during {target_category} model inference.",
                "category": target_category,
                "disease": None,
                "score": 0.0,
                "confidence": 0.0,
                "calibrated_conf": None,
                "calibrated_confidence": None,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4),
                "predictions": [],
                "error": "Inference failure",
            }

        # ── 5. Safe, uncalibrated prediction interpretation ──
        interp = self._interpret_predictions(target_category, preds, raw_conf)
        interp["category"] = target_category
        interp["domain_hint"] = domain
        interp["domain_scores"] = domain_scores
        interp["domain_confidence"] = round(domain_conf, 4)
        interp["confidence"] = interp.get("score", 0.0)  # Deprecated alias for raw score
        interp["calibrated_conf"] = None  # Deprecated
        interp["calibrated_confidence"] = None  # Deprecated
        interp["score_interpretation"] = "Unvalidated model score; not a calibrated clinical probability."
        return interp


# Module-level singleton
disease_classifier = DiseaseClassifier()
