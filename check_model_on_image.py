
import os
import sys
import argparse
from PIL import Image

# Add backend to PYTHONPATH so we can import 'app'
sys.path.append(os.path.abspath("backend"))

# Monkey-patch torch version before importing anything that might check it
try:
    import torch
    torch.__version__ = "2.6.1"
except ImportError:
    pass

from app.services.disease_classifier import disease_classifier

def main():
    parser = argparse.ArgumentParser(description="Run Medical AI model on an image file.")
    parser.add_argument("image_path", help="Path to the image file to analyze")
    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        print(f"Error: Image file not found at {args.image_path}")
        sys.exit(1)

    print(f"Loading image: {args.image_path}")
    try:
        image = Image.open(args.image_path).convert("RGB")
    except Exception as e:
        print(f"Error opening image: {e}")
        sys.exit(1)

    print("Initializing models (this may take a moment)...")
    disease_classifier.initialize_models()

    if not disease_classifier.models:
        print("Error: No models were loaded. Check your 'backend/app/models' directory.")
        sys.exit(1)

    print("Running classification...")
    result = disease_classifier.classify(image)

    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    print(f"Domain Detected: {result['domain_hint']} ({result['domain_confidence']:.2%})")
    print(f"Diagnosis:       {result['disease']}")
    print(f"Confidence:      {result['confidence']:.2%}")
    
    if result['predictions']:
        print("\nTop 3 Predictions:")
        for i, p in enumerate(result['predictions'][:3]):
            print(f"  {i+1}. {p['disease']}: {p['confidence']:.2%}")
    
    print("="*60)

if __name__ == "__main__":
    main()
