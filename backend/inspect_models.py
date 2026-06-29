"""
Quick script to inspect the architecture of each .pth file by examining state dict keys.
"""
import torch
import os
import sys

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "models")

models_to_check = {
    "skin": "skin_disease_model.pth",
    "xray": "xray_fracture_model.pth",
    "retina": "retina_model.pth",
    "general": "general_disease_model.pth",
}

for name, filename in models_to_check.items():
    path = os.path.join(MODEL_DIR, filename)
    if not os.path.exists(path):
        print(f"\n[{name}] FILE NOT FOUND: {path}")
        continue

    print(f"\n{'='*60}")
    print(f"[{name}] {filename}")
    print(f"{'='*60}")
    
    sd = torch.load(path, map_location="cpu")
    
    # Check if it's a raw state_dict or wrapped in a dict
    if isinstance(sd, dict) and "state_dict" in sd:
        print(f"  Wrapped in dict with keys: {list(sd.keys())}")
        sd = sd["state_dict"]
    elif isinstance(sd, dict) and "model_state_dict" in sd:
        print(f"  Wrapped in dict with keys: {list(sd.keys())}")
        sd = sd["model_state_dict"]
    
    keys = list(sd.keys())
    print(f"  Total keys: {len(keys)}")
    print(f"  First 10 keys: {keys[:10]}")
    print(f"  Last 5 keys: {keys[-5:]}")
    
    # Check for common architecture signatures
    key_str = " ".join(keys[:20])
    if "features" in key_str and "classifier" in " ".join(keys[-5:]):
        print(f"  -> Likely EfficientNet or similar (features + classifier)")
    elif "layer1" in key_str:
        print(f"  -> Likely ResNet (layer1/2/3/4)")
    elif "conv1" in key_str and "bn1" in key_str:
        print(f"  -> Likely ResNet variant")
    elif "encoder" in key_str:
        print(f"  -> Likely Vision Transformer or encoder-based")
    
    # Show the final classifier layer shape
    for k in reversed(keys):
        if "weight" in k and ("classifier" in k or "fc" in k or "head" in k):
            shape = sd[k].shape
            print(f"  -> Final layer: {k} shape={shape} (num_classes={shape[0]})")
            break
