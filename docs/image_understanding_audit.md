# Image Understanding Audit & Integrity Verification Report

**Audit Date:** 2026-11-04\
**Audit Branch:** `fix/healthai-audit-premium-ui`\
**Execution Environment:** LOCAL MAC CPU (Apple M5, arm64, Darwin 27.0.0)\
**Overall Status:** `BLOCKED — INTEGRITY REMEDIATION COMPLETED; AWAITING QUALIFIED HUMAN REVIEW, CLINICAL VALIDATION & OWNER AUTHORIZATION`\

---

## 1. Executive Summary & Preserved Non-Negotiable Statuses

This audit report documents the comprehensive evidence-and-integrity verification pass on the image understanding subsystem of NewGenHealthAI. All claims have been verified against actual files on disk, live API endpoints, cryptographic hashes, deterministic database isolation via `PRAGMA database_list;`, and unmocked local CPU execution.

### Preserved Non-Negotiable Statuses
- **Qwen Multimodal Vision (`qwen/qwen3.8-27b`):** `UNVERIFIED` (Reason: Zero paid external inference calls executed under ₹0 budget policy; no-cost tier unverified).
- **Muse Spark Preview (`meta-models/muse-spark-open`):** `UNVERIFIED` (Reason: Zero paid external API calls executed; preview approval / no-cost tier unverified).
- **Groq Credential Rotation:** `OWNER ACTION REQUIRED` (Procedure documented in `docs/groq_key_rotation_procedure.md`).
- **Remote Test-Session Revocation:** `OWNER ACTION REQUIRED` (Runbook documented in `docs/test_session_revocation.md`).
- **Clinical Validation:** `NOT CLINICALLY VALIDATED` (Specialist models are prototypes; forward-pass latency checks and 4-sample smoke-tests do NOT constitute clinical validation).
- **Qualified Human Provenance Review:** `PENDING_HUMAN_REVIEW` (All unreviewed rights, consent, and publicity checks set to PENDING).
- **Deployment Status:** `BLOCKED` (Standing by for explicit owner authorization directive: `DEPLOY NOW`).

---

## 2. Source Code Changes & Diff Excerpts

### 2.1 Changed Files Summary
| File Path | Component | Rationale & Changes |
|---|---|---|
| `backend/app/api/image_api.py` | API Layer | Validated incoming `modality` strictly against `VALID_SPECIALIST_MODALITIES`; set `is_person: None` when `person_detection_status` is `unsupported`; updated `clinical_warning` to non-mandating clinician language ("Please consult a qualified dermatologist for an in-person evaluation. Any further investigation or biopsy should be determined by the treating clinician."). |
| `backend/app/services/disease_classifier.py` | Service Layer | Strictly enforces specialist-dispatch security invariant: `VALID_SPECIALIST_MODALITIES = {"skin", "xray", "retina", "general"}`; invalid or model-generated modalities can never establish `user_selected`; Step 5 hard safety invariant gate refuses specialist dispatch without valid user selection; set `is_person: None` when person detection is unsupported. |
| `backend/app/services/vision_service.py` | Vision Service | Corrected person-recognition semantics: when object features (e.g. `suit`) are recognized, `is_person` is set to `None` with `person_detection_status: "unsupported"`, explicitly noting that closed-set ImageNet-1K does not support general face or person detection and does not confirm absence of human. Zero biometric or demographic inference. |
| `frontend/src/App.jsx` | Frontend UI | Rendered actual MobileNetV3 top-1 class and raw uncalibrated score on `general_recognition` card; rendered `Person detection: Unsupported / Unknown`; updated critical medical disclaimer box to state that further investigation or biopsy should be determined by treating clinician (no automatic biopsy mandate). |
| `frontend/src/App.test.jsx` | Frontend Tests | Expanded to 36/36 passing component/integration tests covering auth, sessions, mobile, ordinary recognition, unsupported person notices, and non-mandating biopsy disclaimer cards. |
| `frontend/scripts/browser_e2e_verification.cjs` | E2E Testing | Preserved Playwright Chromium browser E2E test script in repository, testing 5 live scenarios with exact console error recording, real local CPU inference, and project visual evidence. |
| `backend/app/core/config.py` | Core Configuration | Added deterministic guard: if `ENVIRONMENT == "testing"`, any accidental connection pointing to production `susham_health.db` is automatically redirected to an isolated temporary SQLite database. |
| `backend/tests/conftest.py` | Test Harness | Forced isolated temporary SQLite database on every test session before importing application modules, preventing accidental production DB binding. |
| `backend/tests/test_endpoint_regression_safety.py` | Test Suite | 26-test suite with specialist invocation spies, subprocess database isolation verification, all 7 everyday photographic fixtures, all 4 ISIC clinical fixtures (auto-intake vs explicit modality), and negative security invariant tests (invalid modalities, numeric, SQL injection, empty string, model-generated modalities). |

### 2.2 Key Diff Excerpt: Complete Elimination of Automatic Clinical Routing
```diff
--- a/backend/app/services/disease_classifier.py
+++ b/backend/app/services/disease_classifier.py
@@ -1425,7 +1425,23 @@ class DiseaseClassifier:
-                    target_category = understanding.get("modality", "general").lower().strip()
+                    # In automatic intake without explicit user selection, even if Groq vision detects medical modality,
+                    # automatic clinical routing is disabled to protect patient safety.
+                    return {
+                        "status": "modality_selection_required",
+                        "success": False,
+                        "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
+                        "message": (
+                            "Automatic clinical routing is disabled to ensure patient safety. "
+                            f"Identified potential {understanding.get('modality', 'clinical')} image ({understanding.get('detected_subject')}). "
+                            "Please explicitly select the medical modality (Skin, X-ray, Retina) to proceed."
+                        ),
+                        "type": "medical_selection_required",
+                        "category": understanding.get("modality", "ambiguous").lower().strip(),
+                        "detected_category": "ambiguous",
+                        "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
+                        "description": understanding.get("description"),
+                        "is_person": False,
+                        "medical_applicable": False,
+                        "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
+                        "modality_source": "auto_intake_abstention",
+                        "disease": None,
+                        "score": 0.0,
+                        "confidence": 0.0,
+                        "predictions": [],
+                        "domain_hint": understanding.get("modality", "general"),
+                        "domain_scores": domain_scores,
+                        "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
+                        "vision_engine": "groq_vision",
+                    }
@@ -1465,2 +1465,0 @@ class DiseaseClassifier:
-                elif domain in ("skin", "xray", "retina", "general") and domain_conf >= 0.30:
-                    target_category = domain
@@ -1553,2 +1553,0 @@ class DiseaseClassifier:
-                if domain in ("skin", "xray", "retina", "general") and domain_conf >= 0.30:
-                    target_category = domain
@@ -1673,3 +1673,33 @@ class DiseaseClassifier:
+        # ── 5. SAFETY INVARIANT GATE: Refuse specialist dispatch without explicit user modality selection ──
+        if modality_source != "user_selected" or not routed_category or not target_category:
+            logger.warning("SAFETY INVARIANT ENFORCED: Refusing specialist dispatch without explicit user modality selection.")
+            return {
+                "status": "modality_selection_required",
+                "success": False,
+                "routing_decision": "NO AUTOMATIC MEDICAL ROUTE",
+                "message": (
+                    "Automatic clinical routing is disabled to ensure patient safety. "
+                    "Explicit modality selection is required to invoke specialist models."
+                ),
+                "type": "medical_selection_required",
+                "category": target_category or "ambiguous",
+                "detected_category": "ambiguous",
+                "detected_subject": understanding.get("detected_subject", "Unrecognized Visual Subject"),
+                "description": understanding.get("description", "Image modality could not be determined without explicit user selection."),
+                "is_person": False,
+                "medical_applicable": False,
+                "reason_not_applicable": "Automatic medical routing is disabled; explicit user modality selection required.",
+                "modality_source": "auto_intake_abstention",
+                "disease": None,
+                "score": 0.0,
+                "confidence": 0.0,
+                "predictions": [],
+                "domain_hint": domain,
+                "domain_scores": domain_scores,
+                "domain_confidence": round(domain_conf, 4) if domain_conf else 0.0,
+                "vision_engine": understanding.get("engine", "local_neural_vision"),
+            }
+
         # ── 6. HARD MODALITY LOCK: Check model availability with lazy loading ──
```

---

## 3. Image SHA-256 Ambiguity Resolution & Hash Audit

### 2.1 Explicit Definition of Hash Fields
- **`original_sha256`**: The SHA-256 hash computed over the untouched bytes downloaded directly from the official source repository via verified TLS into the `originals/` directory.
- **`derived_sha256`**: The SHA-256 hash computed over the transformed, downscaled, or re-encoded image file stored in the `derived-images/` directory.
- **`legacy_fixture_sha256` / `sha256`**: The SHA-256 hash of the active test fixture file evaluated in `backend/tests/fixtures/`. Its value is recomputed directly from the file on disk. A derived image hash is never used as evidence of the original image hash.

### 2.2 Comprehensive Per-Image Verification Table

| Item ID & Filename | Source URL & Original Accession / File Title | Untouched Original Path, Size & SHA-256 | Transformed Derived Path, Size & SHA-256 | Active Fixture Path, Size & SHA-256 | Transformations Applied | Original Preservation Status |
|---|---|---|---|---|---|:---:|
| `everyday_001_portrait` (`portrait.jpg`) | `https://commons.wikimedia.org/wiki/File:Pamela_Anderson_2024_Headshot_by_Norman_Wong.jpg`<br>Title: `File:Pamela Anderson 2024 Headshot by Norman Wong.jpg` | `originals/portrait.jpg`<br>9,301,495 bytes<br>`31280aa14592e60ac92c19ba5bc018bc519c5ba0b0c52949b8b9d2dea4b1616d` | `derived-images/portrait.jpg`<br>114,018 bytes<br>`2247ae8b128883fe9734c3fa0a7f718b82936ae9d7b49fb30358e99df4fa346f` | `portrait.jpg`<br>173,442 bytes<br>`253e97504cd0da9c8864544b9efc2701f34144b43ea1aa0ae966bd442ead60a6` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_002_dog` (`dog.jpg`) | `https://commons.wikimedia.org/wiki/File:Mixed-breed_dog_Labradoodle_Miniature_poodle_puppy_6_weeks_outdoors_grass_yawn_open_mouth_(hund_blandingsrase_puddel-valp_p%C3%A5_gress_gjesper_med_%C3%A5pen_munn)_Tj%C3%B8me_Norway_2022-06_DSC06973.jpg`<br>Title: `File:Mixed-breed dog Labradoodle Miniature poodle puppy...` | `originals/dog.jpg`<br>3,621,302 bytes<br>`62d302f5d6747ec3010ec78c39c58ab62d8819d0c4f984aad0047a02dbed500f` | `derived-images/dog.jpg`<br>216,656 bytes<br>`16541a9e7a56138319aab0a19faf75ffe58c3a54ed659ee87f3f74213acbb5e2` | `dog.jpg`<br>295,858 bytes<br>`eec7b28ce4123c41339bd6002b3a8e42c2d039fa6b006f2690b7125b834d1a2b` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_003_sunflower` (`sunflower.jpg`) | `https://commons.wikimedia.org/wiki/File:D%C3%BClmen%2C_Weddern%2C_Sonnenblumen_--_2026_--_2005.jpg`<br>Title: `File:Dülmen, Weddern, Sonnenblumen -- 2026 -- 2005.jpg` | `originals/sunflower.jpg`<br>15,209,889 bytes<br>`b39132597f3f1c77da4eab685bd6f76f2f882080ed3d54dbe8e2d7e3046d7b84` | `derived-images/sunflower.jpg`<br>215,181 bytes<br>`cf0af1650f83a59556fd720580cce253899ddc8a5b513478935922b6da61e661` | `sunflower.jpg`<br>297,532 bytes<br>`1cab9bf8b79ab33998cbf139aca01ad662b2a6e690e6fe69ac8151df83468a22` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_004_apple` (`apple.jpg`) | `https://commons.wikimedia.org/wiki/File:Malus_domestica_%27Stark%27s_Earliest%27._Locatie_De_Kruidhof_02.JPG`<br>Title: `File:Malus domestica 'Stark's Earliest'. Locatie De Kruidhof 02.JPG` | `originals/apple.jpg`<br>3,559,244 bytes<br>`2a7bfb8ffd1d5179e7cd19b963990d2a4d87c252cc1c92fa53685d2831b51347` | `derived-images/apple.jpg`<br>241,003 bytes<br>`6313d5491b733739b29806535aaa624517a6943a85b327f787ff1d4908b744c8` | `apple.jpg`<br>330,815 bytes<br>`0bf5f1816b9ff23f33a51ebe71f14d7910ada34273d28ba8059a6f0dd43b85f9` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_005_car` (`car.jpg`) | `https://commons.wikimedia.org/wiki/File:2018_Tesla_Model_3.jpg`<br>Title: `File:2018 Tesla Model 3.jpg` | `originals/car.jpg`<br>1,652,694 bytes<br>`6b279f8e8d5dc927dfd6b616bfba5071c079b598baef803078a752dd1f13ce34` | `derived-images/car.jpg`<br>139,914 bytes<br>`23775daf70e15fa08d19a088c6141fa4c084963aaf37e3192085230d8e76f08d` | `car.jpg`<br>192,579 bytes<br>`9296700c13459acd8ec72bcbcdc471ad1ff7d7c649c26d7c3b0762516dab66c5` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_006_laptop` (`laptop.jpg`) | `https://commons.wikimedia.org/wiki/File:Lenovo_G500s_laptop-2905.jpg`<br>Title: `File:Lenovo G500s laptop-2905.jpg` | `originals/laptop.jpg`<br>3,788,483 bytes<br>`6385c16d9e2660d61d63c74f5697997d7168c8b910f8f1c66f30910555965206` | `derived-images/laptop.jpg`<br>107,442 bytes<br>`a4e0f67d1993c8e1dc637f3722ca6065a91357c7bcd42fa9ef1f69c05d5aa6b0` | `laptop.jpg`<br>143,559 bytes<br>`c6d8b63d04348f695fac80c1125fabe070cb94ba6c9e1304c0bda9e90fa310d9` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `everyday_007_house` (`house.jpg`) | `https://commons.wikimedia.org/wiki/File:County_town_residential_building_of_1902.jpg`<br>Title: `File:County town residential building of 1902.jpg` | `originals/house.jpg`<br>2,128,697 bytes<br>`5304e814aa69c1bfb583f8944a073efa4db01bb04d0ddef75ea57c0b76b6cdfc` | `derived-images/house.jpg`<br>187,346 bytes<br>`c657fdffb36d0df8152c4cb2f622ba2da8208368508b3cc30d7e84007df1ead2` | `house.jpg`<br>252,463 bytes<br>`6fe6eedc076a9fbcd2e786e5ea7c12d664000baaf6af572202db26d459af7317` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `diagram_001_flowchart` (`flowchart.png`) | `https://commons.wikimedia.org/wiki/File:Flowchart_Program.png`<br>Title: `File:Flowchart Program.png` | `diagrams/originals/flowchart.png`<br>59,011 bytes<br>`91166379f71c98414eeb8a7e8028b807a8db2bdc59f3488038c2fba8728ada39` | `diagrams/flowchart.png`<br>122,328 bytes<br>`d0c70a811bcb35bcceb174b83b51dfadde729f4a09f01a258c887e301e2c5781` | `diagrams/flowchart.png`<br>122,328 bytes<br>`d0c70a811bcb35bcceb174b83b51dfadde729f4a09f01a258c887e301e2c5781` | `convert_RGBA_to_RGB`, `jpeg_quality_85` | **VERIFIED** |
| `clinical_001_isic_0000000` (`ISIC_0000000.jpg`) | `https://isic-archive.s3.amazonaws.com/images/ISIC_0000000.jpg`<br>Accession: `ISIC_0000000` | `originals/ISIC_0000000.jpg`<br>54,143 bytes<br>`fc5880144d267ae257a8e2bf25315ea5291c958a452de98c920c71904c71326e` | `derived-images/ISIC_0000000.jpg`<br>64,755 bytes<br>`644e58a26e309f36df1a0c39bf3088abd88b42c6eb0d778481f4832d40bfc270` | `ISIC_0000000.jpg`<br>54,143 bytes<br>`fc5880144d267ae257a8e2bf25315ea5291c958a452de98c920c71904c71326e` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `clinical_002_isic_0000001` (`ISIC_0000001.jpg`) | `https://isic-archive.s3.amazonaws.com/images/ISIC_0000001.jpg`<br>Accession: `ISIC_0000001` | `originals/ISIC_0000001.jpg`<br>42,794 bytes<br>`875fa906a2fc4a96ca331a4c27a28bd94da12b936315dd1ad1f1c1cb5966621d` | `derived-images/ISIC_0000001.jpg`<br>48,467 bytes<br>`71de4c6575a629ee3372078eec1e5b2c17e1641af83dd22d180d23c8ef3bf6b0` | `ISIC_0000001.jpg`<br>42,794 bytes<br>`875fa906a2fc4a96ca331a4c27a28bd94da12b936315dd1ad1f1c1cb5966621d` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `clinical_003_isic_0000002` (`ISIC_0000002.jpg`) | `https://isic-archive.s3.amazonaws.com/images/ISIC_0000002.jpg`<br>Accession: `ISIC_0000002` | `originals/ISIC_0000002.jpg`<br>62,351 bytes<br>`3ec774807849fcb5fa1a0f03bc8cdc639041d5735b2edfe167f8a75e3b6c30a8` | `derived-images/ISIC_0000002.jpg`<br>75,036 bytes<br>`75d62b28e9afa43f96e6ffa2ef8ae71de87c4595f4db77cfbba8ba30dff87aea` | `ISIC_0000002.jpg`<br>62,351 bytes<br>`3ec774807849fcb5fa1a0f03bc8cdc639041d5735b2edfe167f8a75e3b6c30a8` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |
| `clinical_004_isic_0000004` (`ISIC_0000004.jpg`) | `https://isic-archive.s3.amazonaws.com/images/ISIC_0000004.jpg`<br>Accession: `ISIC_0000004` | `originals/ISIC_0000004.jpg`<br>53,851 bytes<br>`0536889aef8dc35813d27d25bb00ffe903972417c73b0e8ed66dd7fea7c85751` | `derived-images/ISIC_0000004.jpg`<br>62,013 bytes<br>`a47193651a2da149edc887475e945f5afd8a87481ab2431cfc0a33a2ae520842` | `ISIC_0000004.jpg`<br>53,851 bytes<br>`0536889aef8dc35813d27d25bb00ffe903972417c73b0e8ed66dd7fea7c85751` | `resize_max_1024px_lanczos`, `jpeg_quality_85` | **VERIFIED** |

---

## 3. Official ISIC Records Matching & Verification

Each clinical image was directly queried from the official detail endpoint: `https://api.isic-archive.com/api/v2/images/{isic_id}/`.

| Accession ID | Official License | Official Attribution | Official Image Type | Official Dimensions | Official Clinical Diagnosis | Official Pathology Confirmation | Local Fixture Byte Match |
|---|:---:|:---:|:---:|:---:|---|---|:---:|
| `ISIC_0000000` | **CC-0** | Anonymous | `dermoscopic` | $1022 \times 767$ | Benign; Nevus, Dysplastic | None (clinical) | **MATCHED (54,143 B)** |
| `ISIC_0000001` | **CC-0** | Anonymous | `dermoscopic` | $1022 \times 767$ | Benign; Nevus, Dysplastic | None (clinical) | **MATCHED (42,794 B)** |
| `ISIC_0000002` | **CC-0** | Anonymous | `dermoscopic` | $1022 \times 767$ | Malignant; Melanoma, NOS | Histopathology (`concomitant_biopsy: True`) | **MATCHED (62,351 B)** |
| `ISIC_0000004` | **CC-0** | Anonymous | `dermoscopic` | $1022 \times 767$ | Malignant; Melanoma, NOS | Histopathology (`concomitant_biopsy: True`) | **MATCHED (53,851 B)** |

*Governance finding: Per-image licenses are individually verified as CC-0. Zero database-level license inference was performed. Human consent and patient publicity review remain strictly `PENDING_HUMAN_REVIEW`.*

---

## 4. Benchmark Terminology & Actual Outputs (Unmocked Local Inference)

### 4.1 Measurement Environment & Execution Context
- **Operating System:** macOS Darwin 27.0.0 (Apple Silicon arm64)
- **CPU Model:** Apple M5 (local developer machine)
- **Python Version:** 3.13.9
- **PyTorch Version:** 2.14.0
- **Model Execution Device:** `cpu`
- **Integrity Notice:** *These benchmarks reflect LOCAL MAC CPU execution, NOT Hugging Face CPU Basic container deployment. Measurements cannot be substituted for cloud production benchmarks.*

### 4.2 Part 1A: EXPLORATORY PILOT — 7 PHOTOGRAPHS
- **Dataset Nature:** One selected photographic example per broad category (7 images total). This is NOT a statistically representative dataset and does NOT establish universal image recognition performance.
- **Summary Agreement:** **6/7 coarse-category agreements on this selected seven-image pilot**.
- **Score Semantics:** All reported scores are raw, uncalibrated softmax scores from MobileNetV3-Small (ImageNet-1K).

| Image ID | Filename | Ground Truth | Top-1 Predicted Class | Top-1 Raw Softmax Score (Uncalibrated) | Top-5 Classes & Raw Scores | Latency (Local Mac CPU) | Agreement |
|---|---|---|---|:---:|---|:---:|:---:|
| `everyday_001_portrait` | `portrait.jpg` | Person | `suit` (Everyday Object) | 0.4459 | `suit` (0.4459), `academic gown` (0.0537), `trench coat` (0.0461), `bow tie` (0.0454), `wig` (0.0447) | 150.3 ms | ❌ False* |
| `everyday_002_dog` | `dog.jpg` | Animal | `curly-coated retriever` (Animal) | 0.8212 | `curly-coated retriever` (0.8212), `Irish water spaniel` (0.0494), `standard poodle` (0.0381), `otterhound` (0.0163), `American Staffordshire terrier` (0.0102) | 84.1 ms | ✅ True |
| `everyday_003_sunflower` | `sunflower.jpg` | Plant | `daisy` (Plant) | 0.9705 | `daisy` (0.9705), `pot` (0.0152), `vase` (0.0031), `bee` (0.0019), `cardoon` (0.0015) | 89.9 ms | ✅ True |
| `everyday_004_apple` | `apple.jpg` | Food | `pomegranate` (Food) | 0.4662 | `pomegranate` (0.4662), `bell pepper` (0.2458), `strawberry` (0.1077), `apple` (0.0894), `orange` (0.0211) | 88.3 ms | ✅ True |
| `everyday_005_car` | `car.jpg` | Vehicle | `convertible` (Vehicle) | 0.7666 | `convertible` (0.7666), `sports car` (0.1432), `car wheel` (0.0289), `grille` (0.0145), `limousine` (0.0104) | 83.5 ms | ✅ True |
| `everyday_006_laptop` | `laptop.jpg` | Object | `notebook` (Object) | 0.6864 | `notebook` (0.6864), `laptop` (0.2371), `monitor` (0.0212), `screen` (0.0151), `keyboard` (0.0098) | 84.8 ms | ✅ True |
| `everyday_007_house` | `house.jpg` | Object | `boathouse` (Everyday Architecture) | 0.5173 | `boathouse` (0.5173), `church` (0.1245), `monastery` (0.0834), `bell cote` (0.0412), `barn` (0.0315) | 78.7 ms | ✅ True |

*\*Portrait Result Analysis: Ground truth is person; prediction is `suit`; category match is false. Person recognition is NOT reliably supported by the current MobileNetV3/ImageNet-1K mapping. General person detection cannot be claimed from the 3 narrow ImageNet human classes (`groom`, `ballplayer`, `scuba diver`). The application does NOT perform face recognition, identity guessing, demographic inference, or biometric processing.*

### 4.3 Part 1B: Diagram Evaluation Group (Separate from Photographic Benchmark)
- **Image:** `diagrams/flowchart.png`
- **Ground Truth:** Flowchart Diagram / Document
- **Predicted Top-1 Class:** `web site` (ImageNet idx 916)
- **Top-1 Raw Softmax Score:** 0.9598
- **Status:** `general_recognition` (`category: object`, subject: `Everyday Object (Web Site)`)
- **Latency:** 71.2 ms (Local Mac CPU)
- **Integrity Finding:** **Diagram understanding is NOT demonstrated by this evaluation.** Classifying a flowchart as a "web site" does NOT constitute successful diagram recognition. It is strictly excluded from photographic accuracy.

### 4.4 Part 2: ISIC Clinical Dermatoscopic Images

| Accession ID | Ground Truth Diagnosis | Benign / Malignant | Automatic Intake (No Modality Selected) | Explicit-Skin Modality (User Selected 'Skin') | Top Raw Softmax Score (Uncalibrated) | Latency (Local Mac CPU) |
|---|---|---|---|---|:---:|:---:|
| `ISIC_0000000` | Nevus, Dysplastic | Benign | **NO AUTOMATIC MEDICAL ROUTE**<br>Underlying: `modality_selection_required` (`category=ambiguous`) | `Melanoma` | 0.714 | 618.3 ms |
| `ISIC_0000001` | Nevus, Dysplastic | Benign | **NO AUTOMATIC MEDICAL ROUTE**<br>Underlying: `modality_selection_required` (`category=ambiguous`) | `Melanocytic Nevi` | 0.597 | 615.4 ms |
| `ISIC_0000002` | Melanoma | Malignant | **NO AUTOMATIC MEDICAL ROUTE**<br>Underlying: `modality_selection_required` (`category=ambiguous`) | `Melanoma` | 0.820 | 619.5 ms |
| `ISIC_0000004` | Melanoma | Malignant | **NO AUTOMATIC MEDICAL ROUTE**<br>Underlying: `general_recognition` (`category=object`, top1='loupe') | `Melanoma` | 0.516 | 624.2 ms |

- **Integrity Finding:** Under automatic intake, the system safely triggers **NO AUTOMATIC MEDICAL ROUTE** on all 4 clinical images, abstaining from medical specialist routing.
- **Explicit Modality Finding:** When the user explicitly selects `Skin`, the specialist model executes with negative guardrails.
- **Clinical Evaluation Finding:** Clinical accuracy **CANNOT** be derived from 4 images. Scores are uncalibrated research outputs, not diagnostic probabilities. Status is `NOT CLINICALLY VALIDATED`.

---

## 5. Live Endpoint Verification Passes (Unmocked Local CPU)

### 5.1 Seven Everyday Photographic Fixtures — `/api/v1/analyze-image` (No Modality Selected)
All 7 everyday photographic fixtures were evaluated against the live FastAPI endpoint without explicit modality selection.

| Fixture Filename | Endpoint HTTP | Resulting Status | Detected Category | Top-1 Class | Raw Softmax Score | Frontend Display | Specialist Model Invoked? | Routing Decision |
|---|:---:|---|---|---|:---:|---|:---:|:---:|
| `portrait.jpg` | 200 | `general_recognition` | `object` | `suit` | 0.4459 | Classification: suit (Raw score: 0.4459) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `dog.jpg` | 200 | `general_recognition` | `animal` | `curly-coated retriever` | 0.8212 | Classification: curly-coated retriever (Raw score: 0.8212) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `sunflower.jpg` | 200 | `general_recognition` | `plant` | `daisy` | 0.9705 | Classification: daisy (Raw score: 0.9705) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `apple.jpg` | 200 | `general_recognition` | `food` | `pomegranate` | 0.4662 | Classification: pomegranate (Raw score: 0.4662) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `car.jpg` | 200 | `general_recognition` | `vehicle` | `convertible` | 0.7666 | Classification: convertible (Raw score: 0.7666) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `laptop.jpg` | 200 | `general_recognition` | `object` | `notebook` | 0.6864 | Classification: notebook (Raw score: 0.6864) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |
| `house.jpg` | 200 | `general_recognition` | `object` | `boathouse` | 0.5173 | Classification: boathouse (Raw score: 0.5173) | ❌ None | `NO AUTOMATIC MEDICAL ROUTE` |

*Verification Finding: Zero everyday photographic fixtures were misrouted to specialist models. All 7 received MobileNetV3 closed-set classifications with honest categories, uncalibrated scores, and `medical_applicable: false`.*

### 5.2 Four ISIC Clinical Fixtures — Auto-Intake vs Explicit Modality Selection
The 4 ISIC clinical images were evaluated under both automatic intake (no modality provided) and explicit user selection (`modality="skin"`).

| Accession ID | Ground Truth | Auto-Intake Status | Auto-Intake Routing Decision | Auto-Intake Specialist Invoked? | Explicit `modality="skin"` Status | Explicit Top Prediction & Raw Score | Explicit Latency (Local Mac CPU) |
|---|---|---|---|:---:|---|---|:---:|
| `ISIC_0000000` | Nevus, Dysplastic (benign) | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | ❌ None | `analysis_complete` | Melanoma (0.714) | 618.3 ms |
| `ISIC_0000001` | Nevus, Dysplastic (benign) | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | ❌ None | `analysis_complete` | Melanocytic Nevi (0.597) | 615.4 ms |
| `ISIC_0000002` | Melanoma (malignant) | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | ❌ None | `analysis_complete` | Melanoma (0.820) | 619.5 ms |
| `ISIC_0000004` | Melanoma (malignant) | `general_recognition` (loupe) | `NO AUTOMATIC MEDICAL ROUTE` | ❌ None | `analysis_complete` | Melanoma (0.516) | 624.2 ms |

*Verification Finding: Under automatic intake, autonomous medical diagnosis is completely disabled (`routing_decision: "NO AUTOMATIC MEDICAL ROUTE"`, `disease: None`). Specialist skin model is only invoked upon explicit modality selection.*

### 5.3 Actual Specialist Model Invocation Spies Table (15 Test Cases)
To rigorously enforce the dispatch boundary invariant (`specialist_model_invocation = permitted only when explicit user modality selection is valid`), an unmocked call spy was instrumented at the dispatch boundary across `disease_classifier.get_specialist_model` and `MedicalModel.predict`.

| # | Test Scenario & Fixture | User Modality Selection | Resulting Status | Routing Decision | `get_specialist_model` Calls | Skin `predict` Calls | X-ray `predict` Calls | Retina `predict` Calls | General `predict` Calls | Total Specialist Invocations | Boundary Invariant |
|---|---|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Everyday: `portrait.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 2 | Everyday: `dog.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 3 | Everyday: `sunflower.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 4 | Everyday: `apple.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 5 | Everyday: `car.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 6 | Everyday: `laptop.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 7 | Everyday: `house.jpg` | *None* | `general_recognition` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 8 | Clinical Auto: `ISIC_0000000.jpg` | *None* | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 9 | Clinical Auto: `ISIC_0000001.jpg` | *None* | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 10 | Clinical Auto: `ISIC_0000002.jpg` | *None* | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 11 | Clinical Auto: `ISIC_0000004.jpg` | *None* | `general_recognition` (loupe) | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 12 | Clinical Explicit: `ISIC_0000000.jpg` | `"skin"` | `analysis_complete` | Dispatched to Skin | 1 (`["skin"]`) | 1 | 0 | 0 | 0 | **1** | ✅ ENFORCED |
| 13 | Clinical Explicit: `ISIC_0000001.jpg` | `"skin"` | `analysis_complete` | Dispatched to Skin | 1 (`["skin"]`) | 1 | 0 | 0 | 0 | **1** | ✅ ENFORCED |
| 14 | Clinical Explicit: `ISIC_0000002.jpg` | `"skin"` | `analysis_complete` | Dispatched to Skin | 1 (`["skin"]`) | 1 | 0 | 0 | 0 | **1** | ✅ ENFORCED |
| 15 | Clinical Explicit: `ISIC_0000004.jpg` | `"skin"` | `analysis_complete` | Dispatched to Skin | 1 (`["skin"]`) | 1 | 0 | 0 | 0 | **1** | ✅ ENFORCED |
| 16 | Negative: `ISIC_0000000.jpg` | `"invalid_foo"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 17 | Negative: `ISIC_0000000.jpg` | `"auto"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 18 | Negative: `ISIC_0000000.jpg` | `"car"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 19 | Negative: `ISIC_0000000.jpg` | `"fraud"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 20 | Negative: `ISIC_0000000.jpg` | `"model_suggested"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 21 | Negative: `ISIC_0000000.jpg` | `"12345"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 22 | Negative: `ISIC_0000000.jpg` | `"skin; DROP TABLE"` | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 23 | Negative: `ISIC_0000002.jpg` (Skin Hues) | *None* (Auto) | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |
| 24 | Negative: `ISIC_0000001.jpg` | `"   "` (Whitespace) | `modality_selection_required` | `NO AUTOMATIC MEDICAL ROUTE` | 0 | 0 | 0 | 0 | 0 | **0** | ✅ ENFORCED |

*Invariant Finding: Across all 20 non-explicit or invalid test requests, specialist model invocation is strictly 0 (zero forward passes, zero model loads). Specialist models are invoked strictly when and only when explicit user modality selection is validated.*

---

## 6. Specialist Medical Models Evaluation & Forward Pass (Local Mac CPU)

To avoid conflating forward pass benchmarks with clinical image understanding, each model is evaluated across separate explicit dimensions:

| Modality | Architecture | Classes | Input Shape & Type | Input Provenance | Local Checkpoint SHA-256 Verified? | Model Loaded? | Forward Pass Verified? | Forward Pass Latency (Local Mac CPU) | Evaluation Dataset Availability | Diagnostic Performance Evaluated? | Overall Status |
|---|---|:---:|:---:|---|:---:|:---:|:---:|:---:|---|:---:|---|
| **Skin Dermatology** | `timm_efficientnet` (`tf_efficientnet_b4_ns`) | 216 | `[1, 3, 380, 380]` `torch.float32` | Genuine clinical pilot (4 ISIC CC-0 images) & synthetic tensor | **YES** | **YES** | **YES** | 762.7 ms/frame | **AVAILABLE** (Open CC-0 ISIC Archive clinical pilot) | **SMOKE-TEST ONLY** (4 samples cannot establish statistical accuracy) | `FORWARD PASS VERIFIED — EXPLORATORY PILOT ONLY — NOT CLINICALLY VALIDATED` |
| **Bone / Chest X-ray** | `densenet121` | 10 | `[1, 3, 224, 224]` `torch.float32` | Synthetic random tensor (`torch.randn`) — zero clinical images ingested | **YES** | **YES** | **YES** | 65.9 ms/frame | **EVALUATION DATASET ACCESS BLOCKED** (MURA / MIMIC-CXR DUA required) | **NO** (No clinical evaluation dataset ingested) | `FORWARD PASS VERIFIED — EVALUATION DATASET ACCESS BLOCKED — NOT CLINICALLY VALIDATED` |
| **Retinal Fundus** | `retina_efficientnet_b0` | 47 | `[1, 3, 224, 224]` `torch.float32` | Synthetic random tensor (`torch.randn`) — zero clinical images ingested | **YES** | **YES** | **YES** | 234.0 ms/frame | **EVALUATION DATASET ACCESS BLOCKED** (Messidor / EyePACS DUA required) | **NO** (No clinical evaluation dataset ingested) | `FORWARD PASS VERIFIED — EVALUATION DATASET ACCESS BLOCKED — NOT CLINICALLY VALIDATED` |
| **General Pathology** | `resnet18` | 69 | `[1, 3, 224, 224]` `torch.float32` | Synthetic random tensor (`torch.randn`) — zero clinical images ingested | **YES** | **YES** | **YES** | 18.6 ms/frame | **EVALUATION DATASET ACCESS BLOCKED** (BraTS / TCIA DUA required) | **NO** (No clinical evaluation dataset ingested) | `FORWARD PASS VERIFIED — EVALUATION DATASET ACCESS BLOCKED — NOT CLINICALLY VALIDATED` |

*Integrity Rule: A CPU forward-pass latency benchmark proves only that the weights load and execute on Apple M5 hardware without crashing. It does NOT establish clinical diagnostic accuracy, safety, or clinical efficacy.*

---

## 7. Deterministic Database Path Reconciliation & Isolation Evidence

### 7.1 Production Database Path Reconciliation
A filesystem and configuration audit was conducted across the codebase to resolve candidate database paths:
- **Configured Production Database Path:** `backend/storage/chat_db/susham_health.db`.
- **Engine Query Introspection (`PRAGMA database_list;`):**
  ```sql
  PRAGMA database_list;
  ```
  Returns: `[(0, 'main', '<repo_root>/backend/storage/chat_db/susham_health.db')]`.
- **Filesystem Audit (`backend/susham_health.db`):**
  - `backend/susham_health.db` **DOES NOT EXIST**.
  - No symlinks exist pointing between `backend/susham_health.db` and `backend/storage/chat_db/susham_health.db`.
  - The live application configuration strictly uses `backend/storage/chat_db/susham_health.db`.
- **Test Subprocess Database Usage:**
  - In automated test execution, the test harness sets `CHAT_DB_PATH` to an isolated temporary SQLite database (e.g. `/tmp/nghai_isolated_test_db_*.db`).
  - Production `susham_health.db` is never resolved or opened by test runs.

### 7.2 Subprocess Isolation & Environment Cleanup Verification
To verify that database isolation is not merely an in-process mock or fixture artifact, an external subprocess test was implemented (`tests/test_endpoint_regression_safety.py::test_subprocess_database_isolation_conflict`).

- **Subprocess Execution:** A separate Python child process is spawned with `PYTHONPATH=backend` and a deliberately conflicting `CHAT_DB_PATH` environment variable pointing to a temporary file (`deliberate_conflicting_*.db`).
- **Pragma Introspection:** The child process imports `backend.app.models.user` and executes `PRAGMA database_list;` directly against the resolved SQLAlchemy engine.
- **Canonical Path Resolution:** On macOS, `/var` paths resolve to the canonical symlink target `/private/var`. The test asserts `os.path.realpath(resolved_db) == os.path.realpath(conflicting_temp_db)` and `assert not resolved_db.endswith("susham_health.db")`.
- **Environment Cleanup:** When the test completes, `os.environ.pop("CHAT_DB_PATH", None)` is strictly executed if the variable was originally absent, preventing contamination of subsequent test suites.

### 7.3 Controlled Production Database Immutability Verification
The production database at `backend/storage/chat_db/susham_health.db` was measured before and after all test suites, benchmark scripts, subprocess executions, and endpoint passes:

| Metric | Pre-Verification Baseline | Post-Verification Measurement | Status |
|---|---|---|:---:|
| **File Path** | `backend/storage/chat_db/susham_health.db` | `backend/storage/chat_db/susham_health.db` | Identical |
| **SHA-256 Checksum** | `e86d5e99d6f2ca59bd140ff7b044173e3e0b730b95becddabd7e3f3cad539614` | `e86d5e99d6f2ca59bd140ff7b044173e3e0b730b95becddabd7e3f3cad539614` | **100% UNTOUCHED (MATCH)** |
| **File Size** | `749,568 bytes` | `749,568 bytes` | **100% UNTOUCHED (MATCH)** |
| **Modification Time (ns)** | `1793812675928127756` | `1793812675928127756` | **100% UNTOUCHED (MATCH)** |
| **WAL File (`-wal`) Exists** | `False` | `False` | **PASSED (ZERO LEAK)** |
| **SHM File (`-shm`) Exists** | `False` | `False` | **PASSED (ZERO LEAK)** |

---

## 8. Software Verification Test Evidence

### 8.1 Reconciled Independent Test Counts
- **Total Test Cases Executed:** **500** (459 backend + 36 frontend + 5 browser E2E).
- **Test Cases Passed:** **500** (100% pass rate).
- **Test Cases Failed:** **0**.
- **Test Cases Skipped:** **0**.
- **Individual Assertion Count:** Not measured (pytest, Vitest, and Playwright do not report individual assertion counts; prior "482 assertions" claim was an unsupported arithmetic summation of 454 tests + 26 double-counted endpoint tests + 2 build/format commands, and has been permanently corrected).
- **Builds & Formatting Checks:** Clean frontend production build (Vite v7.3.1 in 545ms) and `git diff --check` (0 issues).

### 8.2 Backend Pytest Execution
- **Command:** `PYTHONPATH=backend /tmp/nghai_venv/bin/pytest backend/tests -W default -rW`
- **Exit Code:** `0` (Success)
- **Summary:** **459 passed, 0 warnings in 13.69s** (100% pass rate).
- **Warnings Reconciliation:**
  - **0x `DeprecationWarning`**: **Completely resolved.** Explicit ISO datetime and date adapters registered with `sqlite3` in `backend/app/db/session.py` matching standard library specifications and eliminating all 33 legacy Python 3.12+ datetime deprecation warnings.
  - **0x `UserWarning`**: **Completely resolved.** Updated skin specialist model initialization in `disease_classifier.py` to use timm's canonical identifier `tf_efficientnet_b4.ns_jft_in1k` first with legacy fallback, verified bit-for-bit identical forward pass outputs (`diff = 0.0`), eliminating the alias deprecation warning.
  - **0x `ResourceWarning`**: **Completely resolved.** All unclosed SQLite database connection warnings eliminated via deterministic `try ... finally: verify_conn.close()` in `migrations.py` and connection pool disposal (`engine.dispose()`) in test fixtures.
  - **0x Pre-session Startup Warnings**: **Completely resolved.** Set `asyncio_default_fixture_loop_scope = function` in `backend/pytest.ini`, eliminating the pytest-asyncio plugin startup warning.
  - **Total Warnings Across Entire Test Suite:** **0 warnings.**
- **Production Clinical Feature Gate Suite:** `tests/test_clinical_gate.py` passed **12/12** (unconditionally disabled in production; adversarial multi-variable bypass attempts fail closed; explicit modality returns `clinical_analysis_disabled` with zero model loads; everyday general recognition preserved; research mode opt-in supported in recognized non-prod environments).
- **Targeted Test-Session Revocation Suite:** `tests/test_targeted_session_revocation.py` passed **2/2** (narrow revocation of audit user sessions while leaving legitimate users and conversations completely active).
- **Subprocess OFFLINE_MODE Suite:** `tests/test_offline_mode_subprocess.py` passed **18/18** (authoritative `is_offline_mode` blocking in isolated processes).
- **Session History Security Suite:** `tests/test_session_history_security.py` passed **6/6** (zero DB writes on repeated empty requests, 404 on unowned session IDs).
- **Focused Endpoint Regression Suite:** `tests/test_endpoint_regression_safety.py` passed **26/26** (includes unmocked specialist invocation spies across all 24 scenarios and child subprocess isolation verification).
- **Phase 2A Image Classifier Suite:** `tests/test_phase2a_image_classifier.py` passed **36/36**.
- **Phase 3A Image Security Suite:** `tests/test_phase3a_image_security.py` passed **27/27**.
- **Model Fairness & Safety Suite:** `tests/test_model_fairness_and_safety.py` passed **31/31**.
- **Vision Understanding Suite:** `tests/test_vision_understanding.py` passed **29/29**.
- **Agent Architecture Suite:** `tests/test_agents.py` passed **26/26**.
- **Tools Suite:** `tests/test_tools.py` passed **14/14**.
- **Phase 4 Hardening Suite:** `tests/test_phase4_hardening.py` passed **20/20**.

### 8.3 Frontend Component & Integration Test Suite (Vitest)
- **Command:** `npm test -- --run`
- **Exit Code:** `0` (Success)
- **Summary:** **36 passed across 2 test files** in 1.85s (100% pass rate).
- **Coverage:** React component rendering, auth workflows, session handling, mobile layouts, ordinary recognition cards, educational amber notices, person detection unsupported notices, and non-mandating biopsy disclaimer cards.

### 8.4 Playwright Headless Chromium Browser E2E Test Suite
The browser E2E test script is preserved directly inside the project at `frontend/scripts/browser_e2e_verification.cjs`.
- **Runner:** Playwright v1.50+ with Chromium headless engine.
- **Execution Command:** `node frontend/scripts/browser_e2e_verification.cjs`
- **Result:** **5/5 scenarios passed cleanly (100% pass rate, 0 mocked endpoints, 0 console errors)**.
- **Scenarios, Environments, Pipeline & Evidence Details:**

| # | Scenario | Page URL | Server Environment | Upload Interface | Inference Pipeline | Browser Console Errors | Project Screenshot Artifact |
|---|---|---|---|---|---|:---:|---|
| **1** | Everyday Sunflower Recognition | `http://127.0.0.1:8899` | Live FastAPI (Uvicorn 127.0.0.1:8899) | Actual file input upload | Real local neural inference (MobileNetV3-Small on local CPU; daisy: 0.9705) | **0** | `backend/tests/fixtures/browser_evidence/30_browser_sunflower_general_card.png` |
| **2** | Portrait Unsupported-Person Notice | `http://127.0.0.1:8899` | Live FastAPI (Uvicorn 127.0.0.1:8899) | Actual file input upload | Real local neural inference (MobileNetV3-Small on local CPU; suit: 0.4459; `is_person: null`; notice displayed: `Person detection: Unsupported / Unknown`) | **0** | `backend/tests/fixtures/browser_evidence/31_browser_portrait_unsupported_card.png` |
| **3** | Clinical Automatic-Intake Modality Selection | `http://127.0.0.1:8899` | Live FastAPI (Uvicorn 127.0.0.1:8899) | Actual file input upload | Real local safety gate (`NO AUTOMATIC MEDICAL ROUTE`; specialist calls: 0) | **0** | `backend/tests/fixtures/browser_evidence/32_browser_isic_modality_required_card.png` |
| **4** | Explicit-Skin Research-Model Output & Warning | `http://127.0.0.1:8899` | Live FastAPI (Uvicorn 127.0.0.1:8899) | Actual file input upload with explicit `selectOption("skin")` | Real local neural inference (timm EfficientNet-B4 skin specialist model; score: 0.7140; non-mandating disclaimer displayed: "Any further investigation or biopsy should be determined by the treating clinician") | **0** | `backend/tests/fixtures/browser_evidence/33_browser_isic_explicit_skin_medical_card.png` |
| **5** | Responsive 390×844 Mobile Viewport | `http://127.0.0.1:8899` | Live FastAPI (Uvicorn 127.0.0.1:8899) | Real mobile browser viewport (390×844) | Real local rendering of restored conversation session with critical disclaimers visible | **0** | `backend/tests/fixtures/browser_evidence/34_browser_mobile_390x844_explicit_skin.png` |

### 8.5 Frontend Production Build
- **Command:** `npm run build`
- **Exit Code:** `0` (Success)
- **Summary:** Vite v7.3.1 built production client in 946ms into `backend/app/static/` (0 errors).

### 8.6 Git Whitespace & Syntax Formatting
- **Command:** `git diff --check`
- **Exit Code:** `0` (Clean, zero whitespace or syntax errors).

### 8.7 Production Package Inventory & Smoke Test Audit
- **Temporary Package Directory:** `/tmp/newgenhealthai_prod_pkg`
- **Total Files in Package:** 72 files
- **Total Package Size:** 11,207,857 bytes (~10.69 MB)
- **Files Larger Than 5 MB Audit:**
  - **Path:** `backend/app/models/mobilenet_v3_small-047dcff4.pth`
  - **Size:** 10,306,551 bytes (9.83 MB)
  - **SHA-256:** `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`
  - **Purpose:** PyTorch official ImageNet-1K pretrained neural weights for MobileNetV3-Small.
  - **Runtime Necessity:** Essential for production local CPU general object classification and non-medical intake triage. Operates 100% offline with zero cloud API costs, preventing ordinary non-medical images (pets, flowers, vehicles, documents) from being inappropriately routed to clinical analysis.
- **Diagnostic Specialist Checkpoints Excluded from Production Package:**
  - `skin_disease_model.pth`: 72,504,350 bytes (69.15 MB)
  - `general_disease_model.pth`: 44,929,227 bytes (42.85 MB)
  - `xray_fracture_model.pth`: 28,466,113 bytes (27.15 MB)
  - `retina_model.pth`: 19,066,270 bytes (18.18 MB)
  - *Total Excluded Specialist Weights:* 164,965,960 bytes (~157.32 MB).
  - *Rationale:* Clinical specialist feature is unconditionally disabled in the current production release pending formal clinical validation. Eliminating these checkpoints prevents distribution of unvalidated diagnostic models and reduces deployment package footprint from ~168 MB to ~10.7 MB.
- **Package Smoke Test Results:**
  - `GET /`: Status 200, valid HTML returned.
  - `GET /favicon.ico`: Status 200, static asset served.
  - `POST /api/v1/analyze-image` (everyday object pipeline integrity test): Status 200 (`general_recognition`, `medical_applicable: false`, `routing_decision: NO AUTOMATIC MEDICAL ROUTE`, `vision_model: mobilenet_v3_small`).
  - `POST /api/v1/analyze-image` (clinical specialist with `modality="skin"`): Status 200 (`status: clinical_analysis_disabled`, `clinical_governance_status: NOT_CLINICALLY_VALIDATED`, zero specialist model loads).

---

## 9. Final Capability Matrix

| Capability / Subsystem | Verification Status | Operational Notes & Limitations |
|---|:---:|---|
| **Everyday Photographic Pilot (7 images)** | `VERIFIED (PILOT)` | Closed-set ImageNet-1K classification via MobileNetV3. Dog & Apple resolved via Wikimedia API; originals preserved via verified TLS; hashes pinned. |
| **Person / Portrait Recognition & Publicity Rights** | `UNVERIFIED / PENDING REVIEW` | Portrait predicted as 'suit'; person recognition marked unsupported (`is_person: null`). Personality/publicity rights separated: `PENDING_QUALIFIED_HUMAN_REVIEW`. |
| **MobileNetV3 Checkpoint Provenance** | `VERIFIED` | Official torchvision ImageNet-1K pretrained weights (`047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`), BSD-3-Clause, 1000 classes. |
| **Clinical Specialist Production Feature Gate** | `VERIFIED (UNCONDITIONALLY DISABLED)` | Unconditionally disabled in production; returns `clinical_analysis_disabled` with zero model loads; research mode opt-in supported in non-prod. |
| **Clinical Skin Specialist Forward Pass** | `PARTIALLY VERIFIED` | Forward pass runs locally (~762ms Local Mac CPU). Smoke-test on 4 ISIC CC-0 images. NOT clinically validated. Non-mandating disclaimer. |
| **Clinical X-ray / Retina / General Models** | `PARTIALLY VERIFIED` | Forward passes run locally (18ms - 234ms Local Mac CPU). Blocked by clinical DUAs. NOT clinically validated. |
| **Automated Medical Modality Routing** | `DISABLED (SAFE)` | Automatic clinical routing eliminated. Abstains with `NO AUTOMATIC MEDICAL ROUTE`; specialist invocation = 0. |
| **Explicit Modality Selection Safeguards** | `VERIFIED` | Explicit selection passes with negative guardrails against animals, full-color X-rays, landscapes, and invalid modalities. |
| **Verified TLS Dataset Downloader** | `VERIFIED` | Strict TLS context enforced (cert + hostname verification). All 12 files preserved in `originals/` (4 ISIC + 7 Wikimedia photos + 1 diagram). Zero pending. |
| **Deterministic Database Protection** | `VERIFIED` | Reconciled path `backend/storage/chat_db/susham_health.db`. Verified in-process and via child subprocess. Production DB untouched byte-for-byte (`e86d5e99...`). |
| **Backend & Frontend Software Suites** | `VERIFIED` | 459/459 backend tests passed, 36/36 frontend tests passed, 5/5 Playwright browser tests passed (500 total passed), production build clean. |
| **Clinical Validation Framework** | `NOT CLINICALLY VALIDATED` | Governance protocols authored; clinical multi-reader MRMC trials not yet conducted. |
| **Qualified Human Provenance Review** | `PENDING_HUMAN_REVIEW` | All unreviewed rights, consent, and publicity checks set to PENDING. |
| **Qwen Multimodal Vision** | `UNVERIFIED` | Zero paid external inference calls executed under ₹0 policy. |
| **Muse Spark Preview** | `UNVERIFIED` | Zero external API calls executed; preview access unverified. |
| **Groq Credential Rotation** | `OWNER ACTION REQUIRED` | Procedure documented; awaiting project owner execution. |
| **Remote Test-Session Revocation** | `OWNER ACTION REQUIRED` | Targeted revocation implemented and tested locally; live Space execution requires owner action. |
| **Production Release Deployment** | `BLOCKED` | Awaiting explicit owner authorization directive: `DEPLOY NOW`. |
