"""Quick test script for the image analysis API."""
import requests
import json
import os

test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_images")
url = "http://127.0.0.1:8000/api/v1/analyze-image"

for fname in ["skin_test.jpg", "xray_test.jpg", "retina_test.jpg"]:
    fpath = os.path.join(test_dir, fname)
    if not os.path.exists(fpath):
        print(f"SKIP: {fname} not found")
        continue

    print(f"\n{'='*50}")
    print(f"Testing: {fname}")
    print(f"{'='*50}")

    with open(fpath, "rb") as f:
        resp = requests.post(url, files={"file": (fname, f, "image/jpeg")}, timeout=120)

    data = resp.json()
    print(f"  Status code : {resp.status_code}")
    print(f"  Type        : {data.get('type', 'N/A')}")
    print(f"  Domain hint : {data.get('domain_hint', 'N/A')}")
    print(f"  Domain conf : {data.get('domain_confidence', 'N/A')}")
    print(f"  Domain scores: {json.dumps(data.get('domain_scores', {}), indent=4)}")
    print(f"  Disease     : {data.get('disease', 'N/A')}")
    print(f"  Category    : {data.get('category', 'N/A')}")
    print(f"  Confidence  : {data.get('confidence', 'N/A')}")

    preds = data.get("predictions", [])
    if preds:
        print(f"  Top predictions:")
        for p in preds:
            print(f"    - {p['disease']}: {p['confidence']}")

    if "description" in data:
        print(f"  BLIP Description: {data['description']}")

    print()
