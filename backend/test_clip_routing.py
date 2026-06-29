"""
Test script: Verify CLIP-based domain routing works correctly.
Tests with local test images and verifies no cross-contamination.
"""
import io
import os
import sys
import json
import requests
from PIL import Image

API_URL = "http://127.0.0.1:8000/api/v1/analyze-image"

# Local test images (mapped to expected domains)
LOCAL_IMAGES = {
    "skin": {
        "path": "test_images/skin_test.jpg",
        "expected_domain": "skin",
        "description": "Skin disease photograph",
        "should_NOT_contain": ["fracture", "pneumonia"],  # cross-contamination check
    },
    "xray": {
        "path": "test_images/xray_test.jpg",
        "expected_domain": "xray",
        "description": "X-ray radiograph",
        "should_NOT_contain": ["acne", "eczema", "psoriasis", "melanoma", "retinopathy"],
    },
    "retina": {
        "path": "test_images/retina_test.jpg",
        "expected_domain": "retina",
        "description": "Retinal fundus photograph",
        "should_NOT_contain": ["fracture", "pneumonia", "acne", "eczema"],
    },
}


def test_image(name, config):
    """Load a local image file and send it to the API."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  Description: {config['description']}")
    print(f"  Expected domain: {config['expected_domain']}")
    print(f"{'='*60}")

    fpath = config["path"]
    if not os.path.exists(fpath):
        print(f"  SKIP: File not found: {fpath}")
        return None

    try:
        with open(fpath, "rb") as f:
            img_data = f.read()

        img = Image.open(io.BytesIO(img_data))
        print(f"  Image size: {img.size}, mode: {img.mode}, file: {len(img_data):,} bytes")

        # Send to API
        files = {"file": (f"{name}.jpg", img_data, "image/jpeg")}
        api_resp = requests.post(API_URL, files=files, timeout=120)
        api_resp.raise_for_status()
        result = api_resp.json()

        # Extract key fields
        domain_hint = result.get("domain_hint", "???")
        domain_conf = result.get("domain_confidence", 0)
        response_type = result.get("type", "???")
        disease = result.get("disease", result.get("description", "N/A"))
        category = result.get("category", "N/A")
        confidence = result.get("confidence", 0)
        domain_scores = result.get("domain_scores", {})

        # Check routing correctness
        routing_correct = domain_hint == config["expected_domain"]
        
        # Check for cross-contamination
        cross_contaminated = False
        if disease and config.get("should_NOT_contain"):
            for bad_word in config["should_NOT_contain"]:
                if bad_word.lower() in str(disease).lower():
                    cross_contaminated = True
                    break

        status = "PASS" if (routing_correct and not cross_contaminated) else "FAIL"

        print(f"\n  RESULT: [{status}]")
        print(f"  Domain detected:  {domain_hint} (conf={domain_conf})")
        print(f"  Response type:    {response_type}")
        print(f"  Category:         {category}")
        print(f"  Disease/Desc:     {disease}")
        print(f"  Confidence:       {confidence}")
        print(f"  Domain scores:    {json.dumps(domain_scores, indent=2)}")

        preds = result.get("predictions", [])
        if preds:
            print(f"  Top predictions:")
            for p in preds:
                print(f"    - {p['disease']}: {p['confidence']}")

        if not routing_correct:
            print(f"  ROUTING FAIL: Expected '{config['expected_domain']}' but got '{domain_hint}'")
        if cross_contaminated:
            print(f"  CROSS-CONTAMINATION: '{disease}' is wrong for domain '{config['expected_domain']}'")

        return routing_correct and not cross_contaminated

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("CLIP Domain Routing Verification")
    print("=" * 60)

    # Check API is running
    try:
        r = requests.get("http://127.0.0.1:8000/api/v1/diagnostics", timeout=5)
        diag = r.json()
        print(f"Server status: {diag.get('status')}")
        print(f"Models loaded: {diag.get('models')}")
        print(f"Device: {diag.get('device')}")
    except Exception as e:
        print(f"ERROR: Server not running at {API_URL}!")
        print(f"Start with: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
        sys.exit(1)

    results = {}
    for name, config in LOCAL_IMAGES.items():
        result = test_image(name, config)
        if result is not None:
            results[name] = result

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    if not results:
        print("  No tests ran! Make sure test_images/ has real medical images.")
        return
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, passed_test in results.items():
        status = "PASS" if passed_test else "FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\n  Total: {passed}/{total} passed")
    
    if passed == total:
        print("\n  All routing tests passed! No cross-contamination detected.")
    else:
        print("\n  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
