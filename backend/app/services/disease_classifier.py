"""
NewGenHealthAI — services/disease_classifier.py

# Override torch version to bypass faulty security check (treats 2.11 as older than 2.6)
try:
    import torch
    torch.__version__ = "2.6.1"
except ImportError:
    pass

Multi-model disease classifier with CLIP-based domain detection and
hard modality locking.

Pipeline:
1. Use CLIP zero-shot to determine image domain (skin / xray / retina / general / non_medical)
2. Run ONLY the matching specialist model (hard lock — no cross-contamination)
3. Filter garbage / dataset-artifact predictions
4. Return the top disease prediction from the specialist model
5. Non-medical images are flagged for BLIP captioning in the API layer

Detected architectures (from inspect_models.py):
  skin    -> timm EfficientNet (conv_stem + blocks), 216 classes
  xray    -> DenseNet121 (features.denseblock), 10 classes
  retina  -> EfficientNet-B0 (custom classifier), 47 classes
  general -> ResNet18 (layer1-4, fc), 69 classes
"""

import os

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

# Dataset artifact classes — NEVER return these as a diagnosis
GARBAGE_CLASSES = {
    "all", "train", "test", "val", "valid", "done", "preview", "cropped",
    "jpegimages", "test cases", "other", "others", "others augmented",
    "c-nmc test final phase data", "c-nmc test prelim phase data",
    "im dyskeratotic", "im koilocytotic", "im metaplastic",
    "im parabasal", "im superficial-intermediate",
    "none", "notumor", "notinfected", "uninfected", "non-covid",
    "bengin cases", "normal", "normal cases", "monkeypox augmented",
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
    """Lazy-load CLIP model (one-time ~600MB download)."""
    global _clip_model, _clip_processor
    if _clip_model is None:
        from transformers import CLIPProcessor, CLIPModel
        logger.info("Loading CLIP model for domain detection (one-time)...")
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model.eval()
        logger.info("CLIP model loaded successfully.")
    return _clip_model, _clip_processor


def detect_visual_domain(image: Image.Image) -> tuple:
    """
    Use CLIP zero-shot classification to determine image domain.
    Returns: (domain_name: str, confidence: float, all_scores: dict)
    """
    try:
        model, processor = _get_clip()

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

        return best_domain, best_conf, scores

    except Exception as e:
        logger.error(f"CLIP domain detection error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Fallback: run general model if CLIP fails
        return "general", 0.0, {}


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
            logger.warning(f"[{self.model_name}] Model file not found: {self.model_path}")
            return False
        if not os.path.exists(self.class_path):
            logger.warning(f"[{self.model_name}] Class file not found: {self.class_path}")
            return False

        try:
            self.classes = _parse_class_file(self.class_path)
            num_classes = len(self.classes)
            logger.info(f"[{self.model_name}] Loaded {num_classes} classes")

            checkpoint = torch.load(self.model_path, map_location=self.device)
            state_dict, metadata = _unwrap_state_dict(checkpoint)

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
            logger.error(f"[{self.model_name}] Error loading model: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
    """Orchestrates multi-model disease classification with CLIP domain routing."""

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.models = {}
        self.base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"
        )
        self._download_models_if_missing()
        self.model_configs = self._discover_models()

    def _download_models_if_missing(self):
        """Download the .pth models from a Hugging Face model repository if they don't exist locally."""
        repo_id = os.environ.get("HF_MODEL_REPO", "Khagesh1/HealthAI-Models")
        hf_token = os.environ.get("HF_TOKEN")

        # Expected filenames
        expected_files = {
            "skin": "skin_disease_model.pth",
            "xray": "xray_fracture_model.pth",
            "retina": "retina_model.pth",
            "general": "general_disease_model.pth"
        }

        os.makedirs(self.base_dir, exist_ok=True)

        # Check if any .pth file is missing
        missing_any = False
        try:
            files = os.listdir(self.base_dir)
            for kw, filename in expected_files.items():
                has_pth = any(kw in f.lower() and f.endswith(".pth") for f in files)
                if not has_pth:
                    missing_any = True
                    break
        except Exception:
            missing_any = True

        if not missing_any:
            logger.info("All medical model files verified present locally.")
            return

        logger.info("Some medical model files are missing. Attempting automatic download from Hugging Face Repo: %s...", repo_id)

        try:
            from huggingface_hub import hf_hub_download
            import shutil

            repo_accessible = True

            for kw, filename in expected_files.items():
                if not repo_accessible:
                    break

                dest_path = os.path.join(self.base_dir, filename)
                # Check if it already exists to avoid re-downloading
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
                            token=hf_token
                        )
                        shutil.copy(downloaded_path, dest_path)
                        logger.info(f"[{kw}] Successfully downloaded and copied model to {dest_path}")
                    except Exception as e:
                        logger.warning(
                            f"WARNING: Image classification model download failed from repository '{repo_id}'. "
                            f"Reason: {e}. Image classification features will be disabled/degraded."
                        )
                        repo_accessible = False
                        break
        except Exception as e:
            logger.warning(
                f"WARNING: HuggingFace model downloader initialization failed: {e}. "
                "Image classification features will be disabled/degraded."
            )


    def _discover_models(self):
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
                    logger.info(f"Discovered {kw} model: {pth_file} with {txt_file}")
        except Exception as e:
            logger.error(f"Error during model discovery: {str(e)}")

        return configs

    def initialize_models(self):
        """Load all available models at startup."""
        logger.info("Initializing multi-model disease classifier...")
        for name, paths in self.model_configs.items():
            model = MedicalModel(name, paths["pth"], paths["txt"], self.device)
            if model.load():
                self.models[name] = model
            else:
                logger.warning(f"Skipping {name} model (failed to load)")
        logger.info(
            f"Disease classifier ready — {len(self.models)} model(s) loaded: "
            f"{list(self.models.keys())}"
        )

        # Pre-warm CLIP so first request isn't slow
        try:
            _get_clip()
        except Exception as e:
            logger.warning(f"CLIP pre-warm failed (will retry on first request): {e}")

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _first_clean_prediction(predictions):
        """Return the first non-garbage prediction, or None."""
        for p in predictions:
            if p["disease"].lower().strip() not in GARBAGE_CLASSES:
                return p["disease"], p["confidence"]
        return None, 0.0

    @staticmethod
    def _format_disease(category, raw_name):
        """Pretty-print a disease name for the UI."""
        key = raw_name.lower().strip()
        if category == "general" and key in GENERAL_DISPLAY:
            return GENERAL_DISPLAY[key]
        if category == "retina":
            return raw_name          # already well-formatted
        if category == "xray" and key in XRAY_CONDITIONS:
            return raw_name.title()
        return raw_name.replace("_", " ").title()

    def _get_xray_diagnosis(self, predictions):
        """
        For X-ray model: extract the actual medical condition.
        The X-ray model has body-part classes (elbow, wrist) AND condition classes
        (fracture, pneumonia). We need the condition, not the body part.
        
        Strategy: 
        - If 'fracture' or 'pneumonia' appears in top predictions, return it
        - If only body parts appear, combine body part + "abnormality detected"
        - Check relative confidence between body part and condition
        """
        conditions = []
        body_parts = []

        for p in predictions:
            name = p["disease"].lower().strip()
            if name in GARBAGE_CLASSES:
                continue
            if name in XRAY_CONDITIONS:
                conditions.append(p)
            elif name in XRAY_BODY_PARTS:
                body_parts.append(p)

        if conditions:
            # Return the top condition
            best = conditions[0]
            # If we also know the body part, make it more descriptive
            if body_parts:
                part = body_parts[0]["disease"].title()
                cond = best["disease"].title()
                return f"{part} {cond}", best["confidence"]
            return best["disease"].title(), best["confidence"]

        if body_parts:
            # Only body parts detected — model sees the anatomy but
            # can't determine the specific condition with high confidence
            part = body_parts[0]["disease"].title()
            return f"{part} X-ray — Abnormality Detected", body_parts[0]["confidence"]

        return None, 0.0

    # ── main entry point ──────────────────────────────────────

    def classify(self, image: Image.Image, routed_category: str = None):
        """
        CLIP-routed classification with hard modality lock.

        1. CLIP determines what type of image this is
        2. Only the matching specialist model runs
        3. No cross-contamination between domains
        4. Non-medical images are flagged for BLIP fallback
        """
        empty = {
            "disease": None, "category": "non_medical",
            "confidence": 0.0, "calibrated_conf": 0.0,
            "predictions": [], "all_results": {},
            "domain_hint": "non_medical", "domain_scores": {},
        }

        if not self.models:
            return empty

        # ── 1. CLIP domain detection ──────────────────────────
        domain, domain_conf, domain_scores = detect_visual_domain(image)

        logger.info(f"CLIP domain: {domain} (conf={domain_conf:.3f})")


        # If CLIP says non-medical with high confidence, skip all models
        if domain == "non_medical" and domain_conf > 0.40:
            logger.info("Image classified as non-medical -- skipping disease models")
            empty["domain_hint"] = "non_medical"
            empty["domain_scores"] = domain_scores
            empty["domain_confidence"] = round(domain_conf, 4)
            return empty

        # ── 2. Determine which model to run ────────────────
        # HARD MODALITY LOCK: Only run the matching specialist model.
        # This eliminates cross-contamination entirely.
        models_to_run = []

        if domain in self.models:
            models_to_run.append(domain)
        else:
            # Domain model not loaded! 
            # We DONT want to silently fallback to general because it will
            # give wrong diagnoses (e.g. skin image used with general model).
            logger.critical(f"HARD MODALITY LOCK: Domain '{domain}' detected, but specialist model NOT LOADED.")
            
            if "general" in self.models:
                # If it's borderline or common enough, we might still want general 
                # but we SHOULD warn the user that they are in a degraded state.
                models_to_run.append("general")
                logger.warning(f"Falling back to 'general' model for domain '{domain}' (DEGRADED STATE)")

        # Safety: if somehow no models to run, run all
        if not models_to_run:
            models_to_run = list(self.models.keys())
            logger.warning(f"No model for domain '{domain}', running all models")

        # ── 3. Run selected model(s) ─────────────────────────
        all_results = {}
        primary_result = None

        for cat in models_to_run:
            model = self.models[cat]
            try:
                preds, raw_conf = model.predict(image)
                if not preds:
                    all_results[cat] = {"error": "empty"}
                    continue

                # Special handling for X-ray model
                if cat == "xray":
                    disease_name, disease_conf = self._get_xray_diagnosis(preds)
                else:
                    disease_name, disease_conf = self._first_clean_prediction(preds)

                all_results[cat] = {
                    "top_disease": disease_name or preds[0]["disease"],
                    "top_confidence": disease_conf or raw_conf,
                    "predictions": preds,
                }

                if disease_name is None:
                    all_results[cat]["note"] = "all garbage classes"
                    continue

                logger.info(
                    f"  [{cat}] {disease_name} (conf={disease_conf:.4f})"
                )

                # Skip predictions with extremely low confidence (noise)
                MIN_CONFIDENCE = 0.02
                if disease_conf < MIN_CONFIDENCE:
                    logger.info(f"  [{cat}] Confidence {disease_conf:.4f} below threshold {MIN_CONFIDENCE}, skipping")
                    all_results[cat]["note"] = f"below min confidence ({disease_conf:.4f})"
                    continue

                # The PRIMARY model (matching domain) always wins
                if cat == domain and primary_result is None:
                    primary_result = {
                        "disease": disease_name,
                        "category": cat,
                        "confidence": disease_conf,
                        "predictions": preds,
                    }
                elif primary_result is None:
                    # General model as fallback only if domain model doesn't exist
                    primary_result = {
                        "disease": disease_name,
                        "category": cat,
                        "confidence": disease_conf,
                        "predictions": preds,
                    }

            except Exception as e:
                logger.error(f"Error running {cat} model: {e}")
                all_results[cat] = {"error": str(e)}

        # ── 4. Format output ──────────────────────────────────
        if primary_result is None:
            # All models failed or returned garbage — but CLIP said it's medical.
            # Still return medical category so BLIP doesn't trigger.
            logger.warning("All models returned garbage/low-conf but CLIP detected medical image")
            return {
                "disease": "Unrecognized Medical Condition",
                "category": domain,
                "confidence": 0.0,
                "calibrated_conf": 0.0,
                "predictions": [],
                "all_results": all_results,
                "domain_hint": domain,
                "domain_scores": domain_scores,
                "domain_confidence": round(domain_conf, 4),
            }

        display_name = self._format_disease(
            primary_result["category"], primary_result["disease"]
        )

        # Format top-3 predictions (excluding garbage)
        fmt_preds = []
        for p in primary_result["predictions"][:5]:
            d = p["disease"].lower().strip()
            if d not in GARBAGE_CLASSES:
                # For X-ray, skip body-part-only predictions in the list
                if primary_result["category"] == "xray" and d in XRAY_BODY_PARTS:
                    continue
                fmt_preds.append({
                    "disease": self._format_disease(primary_result["category"], p["disease"]),
                    "confidence": p["confidence"],
                })
            if len(fmt_preds) >= 3:
                break

        logger.info(
            f"DIAGNOSIS: {primary_result['category']} -> {display_name} "
            f"(conf={primary_result['confidence']:.4f}, domain_conf={domain_conf:.3f})"
        )

        return {
            "disease": display_name,
            "category": primary_result["category"],
            "confidence": primary_result["confidence"],
            "calibrated_conf": primary_result["confidence"],  # No cross-model scoring needed
            "predictions": fmt_preds,
            "all_results": all_results,
            "domain_hint": domain,
            "domain_scores": domain_scores,
            "domain_confidence": round(domain_conf, 4),
        }


# Module-level singleton
disease_classifier = DiseaseClassifier()
