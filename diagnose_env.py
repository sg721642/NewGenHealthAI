
import os
import sys
import torch
from PIL import Image

# Add backend to path
sys.path.append(os.path.abspath("backend"))

def check_package(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False

def main():
    print("="*60)
    print("MEDICAL AI ENVIRONMENT DIAGNOSTIC")
    print("="*60)
    
    print(f"Python Version: {sys.version}")
    print(f"Working Dir: {os.getcwd()}")
    
    print("\n--- Package Checks ---")
    packages = ["torch", "torchvision", "timm", "transformers", "PIL", "numpy", "fastapi"]
    missing = []
    for p in packages:
        status = "INSTALLED" if check_package(p) else "MISSING"
        print(f"[{status:9}] {p}")
        if status == "MISSING":
            missing.append(p)

    print("\n--- Hardware Check ---")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cpu":
        print("Note: Running on CPU will be slower but works for diagnosis.")

    print("\n--- Model File Discovery ---")
    model_dir = os.path.join(os.getcwd(), "backend", "app", "models")
    if not os.path.exists(model_dir):
        print(f"[ERROR] Models directory not found at {model_dir}")
    else:
        files = os.listdir(model_dir)
        for kw in ["skin", "xray", "retina", "general"]:
            exists = any(kw in f.lower() and f.endswith(".pth") for f in files)
            status = "FOUND" if exists else "MISSING"
            print(f"[{status:9}] {kw} model")

    print("\n--- Classifier Initialization ---")
    try:
        from app.services.disease_classifier import DiseaseClassifier
        classifier = DiseaseClassifier()
        classifier.initialize_models()
        loaded = list(classifier.models.keys())
        print(f"Successfully loaded models: {loaded}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize classifier: {e}")

    print("\n" + "="*60)
    if missing:
        print("RECOMMENDATION: Install missing packages using:")
        print(f"pip install {' '.join(missing)}")
    elif len(loaded) < 4:
        print("RECOMMENDATION: Some models are missing. Check backend/app/models/ folder.")
    else:
        print("STATUS: Environment is READY! You can now run the app.")
    print("="*60)

if __name__ == "__main__":
    main()
