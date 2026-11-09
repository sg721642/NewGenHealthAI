# Release Manifest: NewGenHealthAI Academic Release Candidate

**Release Tag Candidate:** `v3.1.0-academic`\
**Git Branch:** `ci/add-backend-frontend-test-jobs` (PR #4)\
**Repository:** `https://github.com/sg721642/NewGenHealthAI`\
**Project Context:** College Academic Capstone & Educational Healthcare AI Demonstration\
**Project Lead & Maintainer:** Satyam Gupta\
**Target Infrastructure:** Hugging Face Spaces (CPU Basic: 2 vCPU, 16 GB RAM; Ephemeral Container Storage)\
**Release Readiness Status:** `READY FOR ACADEMIC CAPSTONE DEMONSTRATION & SUBMISSION (REPRODUCIBLE CI VERIFIED; FAIL-CLOSED CLINICAL GOVERNANCE ENFORCED)`\

---

## 1. Release Verification Matrix (16 Mandatory Checks)

| # | Check Item | Requirement | Verification Method | Status |
|---|---|---|---|:---:|
| **1** | **Git Branch & Working Tree Status** | Branch `ci/add-backend-frontend-test-jobs` (PR #4 HEAD: `00a4e7a`); working tree currently has 3 modified documentation files pending commit | `git status -sb` | **VERIFIED (3 docs modified, 0 untracked)** |
| **2** | **Zero-Cost Budget Policy** | ₹0 incurred; zero paid API calls or cloud billing | Unmocked billed API skips in `vision_service.py` | **PASSED** |
| **3** | **Hardware Constraints** | Sub-500ms CPU inference on local host | PyTorch benchmark on CPU | **PASSED** |
| **4** | **Database Protection** | `susham_health.db` never overwritten, connected, or altered | `PRAGMA database_list;` + SHA-256 baseline invariance | **PASSED** |
| **5** | **Zero Secret Exposure** | No API keys committed or displayed in logs | Git index and log inspection | **PASSED** |
| **6** | **Everyday Recognition** | Neural local vision model for non-medical images | MobileNetV3-Small (1000 classes, 50ms) | **PASSED** |
| **7** | **Genuine Everyday Dataset** | 8 Wikimedia Commons photographs (CC-BY-SA-4.0) | Resolved via Wikimedia API; originals preserved; SHA-256 pinned | **PASSED** |
| **8** | **Genuine Clinical Dataset** | 4 ISIC Archive dermoscopy images (CC0-1.0) | Originals preserved; SHA-256 pinned; explicit modality gate | **PASSED** |
| **9** | **Specialist Models Benchmark** | Benchmark 4 models on CPU without crash | Local CPU forward pass latency audit (`FORWARD PASS VERIFIED`); production gate disabled by default | **PASSED** |
| **10** | **Clinical Governance Docs** | 5 formal governance protocols authored | `docs/` clinical documents created; status `NOT CLINICALLY VALIDATED` | **PASSED** |
| **11** | **Security Runbooks** | Key rotation, session revocation, access request | `docs/` runbooks drafted; targeted revocation unit tests passing | **PASSED** |
| **12** | **Backend Test Suite** | 100% test pass rate in isolated Python venv | Pytest (**480/480 passed**, 0 failed, 1 warning) across 23 modules | **PASSED** |
| **13** | **Frontend Component Suite** | 100% unit and integration test pass rate | Vitest (**36/36 passed**, 0 failed) in 1.3s | **PASSED** |
| **14** | **Frontend Browser E2E Suite** | 100% browser UI rendering & mobile layout | Playwright Chromium (5 viewports, 0 console errors) | **PASSED** |
| **15** | **Frontend Production Build** | Static bundle built cleanly to `backend/app/static/` & `dist/` | Vite build (591ms, 0 errors) | **PASSED** |
| **16** | **Triple-Job GitHub Actions CI** | Automated Pytest, Vitest & Docker smoke test | GitHub Actions Run [#42657594147](https://github.com/sg721642/NewGenHealthAI/actions/runs/42657594147) | **PASSED** |

---

## 2. Pinned Model Checkpoints & Cryptographic Checksums

| Modality | Architecture | Input Size | Classes | Local Weights File | Checkpoint SHA-256 | Forward Pass Status | Evaluation Dataset Status |
|---|---|:---:|:---:|---|---|:---:|---|
| **Everyday Vision** | MobileNetV3-Small | $224 \times 224$ | 1000 | `mobilenet_v3_small-047dcff4.pth` | `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f` | **VERIFIED** | Genuine Everyday Pilot (7 images; official PyTorch ImageNet-1K) |
| **Skin Dermatology** | tf_efficientnet_b4_ns | $380 \times 380$ | 216 | `skin_disease_model.pth` | `b5c1fdc1a4db...` | **VERIFIED (765.7ms)** | AVAILABLE (4 ISIC CC-0 images; Smoke-test only; gated in prod) |
| **Bone / Chest X-ray** | DenseNet-121 | $224 \times 224$ | 10 | `xray_fracture_model.pth` | `bf78bb25d7c9...` | **VERIFIED (67.8ms)** | BLOCKED (MURA / MIMIC-CXR DUA required; gated in prod) |
| **Retinal Fundus** | EfficientNet-B0 | $224 \times 224$ | 47 | `retina_model.pth` | `999efb89a8c1...` | **VERIFIED (228.1ms)** | BLOCKED (Messidor / EyePACS DUA required; gated in prod) |
| **General Pathology** | ResNet-18 | $224 \times 224$ | 69 | `general_disease_model.pth` | `adcdb8109271...` | **VERIFIED (20.7ms)** | BLOCKED (BraTS / TCIA DUA required; gated in prod) |

---

## 3. Dataset Integrity & Artifact Terminology Manifests

### 3.0 Architectural Dataset Taxonomy (12 Unique Sources → 36 File Artifacts)
The 36 cryptographic hash-verified files in the repository represent copies/variants across 12 unique image sources:
- **Unique Source Images (12):** 8 everyday/diagram source images (7 photographs + 1 flowchart) + 4 ISIC clinical dermoscopy images.
- **Original Files (12):** Untouched original bytes downloaded directly via verified TLS from authoritative repositories and preserved in `originals/` subdirectories.
- **Derived Files (12):** Transformed, resized, or format-normalized files stored in `derived-images/` subdirectories.
- **Active Fixture Files (12):** Deployed fixture files located in fixture directory roots evaluated by automated test suites.
- **Taxonomic Rule:** The 36 file artifacts must NEVER be described as "36 unique photographs" or "36 clinical images". They represent exactly 12 unique image sources across 3 lifecycle states.

### 3.1 Genuine Everyday Photographic Dataset (Wikimedia Commons)
- **Location:** `backend/tests/fixtures/genuine_everyday_images/`
- **Unique Sources:** 8 unique source images (7 photographs + 1 diagram).
- **Photographic Benchmark (7 images):** Portrait (`portrait.jpg`), Dog (`dog.jpg`), Sunflower (`sunflower.jpg`), Apple (`apple.jpg`), Car (`car.jpg`), Laptop (`laptop.jpg`), House (`house.jpg`).
- **Separate Diagram Evaluation (1 image):** Flowchart diagram (`diagrams/flowchart.png`), evaluated separately and excluded from photographic benchmark accuracy.
- **Source Repositories:** Wikimedia Commons (all contributor names, Commons file URLs, dates, and page titles verified via official API).
- **Licence Terms:** CC-BY-SA-4.0 verified via Wikimedia Commons API. ShareAlike conditions recorded.
- **Consent & Rights Metadata:**
  * Portrait Publicity Rights: `PENDING_QUALIFIED_HUMAN_REVIEW` (Wikimedia "Personality rights warning" tagged; personality rights not cleared).
  * Subject Consent: `NOT_INDEPENDENTLY_VERIFIED`
  * Everyday Objects Rights: `NOT_APPLICABLE` (no recognizable persons in dog, sunflower, apple, car, laptop, house, diagram).
  * Legal Rule: A CC-BY-SA-4.0 copyright license does NOT constitute personality or publicity clearance.
- **File Artifacts (24 files):** 8 original files in `originals/`, 8 derived files in `derived-images/`, 8 active fixture files in root.
- **Recognition Scope:** MobileNetV3-Small closed-set ImageNet-1K classifier (1,000 classes). Exploratory pilot only — NOT universal recognition.

### 3.2 Genuine Clinical Dermatoscopic Dataset (ISIC Archive CC-0 Verified)
- **Location:** `backend/tests/fixtures/genuine_clinical_images/`
- **Unique Sources:** 4 unique clinical dermoscopic image accessions (`ISIC_0000000`, `ISIC_0000001`, `ISIC_0000002`, `ISIC_0000004`).
- **Source Repository:** International Skin Imaging Collaboration (ISIC) Archive API (detail endpoint per-image verified).
- **Licence Terms:** CC-0 (CC0 1.0 Universal) per ISIC Archive API detail records.
- **Independent Clinical Consent & Ethics Metadata:**
  * Patient Consent Status: `NOT_INDEPENDENTLY_VERIFIED`
  * Privacy & De-identification Status: `NOT_INDEPENDENTLY_VERIFIED`
  * Research Ethics Status: `PENDING_QUALIFIED_HUMAN_REVIEW`
  * Institutional Review Board (IRB) Determination: `NOT_INDEPENDENTLY_VERIFIED`
  * Governance Approval Status: `PENDING_QUALIFIED_HUMAN_REVIEW`
  * Clinical Validation Status: `NOT_CLINICALLY_VALIDATED`
  * Strict Legal Principle: A CC0 copyright licence waives copyright but does NOT constitute patient consent, HIPAA de-identification verification, or institutional ethics approval.
- **File Artifacts (12 files):** 4 original files in `originals/`, 4 derived files in `derived-images/`, 4 active fixture files in root.
- **Clinical Validation Status:** NOT CLINICALLY VALIDATED. Production clinical feature gate disabled by default (`ENABLE_CLINICAL_SPECIALIST_MODELS=false`, `CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=false`); returns `clinical_analysis_disabled` with zero model loads. Explicit modality selection required; automated color heuristics are NOT used for decisive medical routing.

### 3.3 Git-Tracked Synthetic Fixtures for CI Reproducibility
- **Location:** `backend/tests/fixtures/synthetic_images/`
- **Tracked Artifacts:**
  - `medical_skin_lesion.jpg`: Synthetic dermatological image fixture.
  - `portrait_human.jpg`: Synthetic human portrait image fixture.
- **Purpose:** Enables standard CI tests to execute reproducibly on fresh GitHub Actions runners without depending on locally ignored genuine clinical or portrait images.
- **Clinical Boundary Invariant:** Synthetic medical-looking images are strictly used for input validation, MIME verification, and safety-gate testing. They must **NEVER** be treated as clinically representative data or used to claim clinical model accuracy, sensitivity, or validation.

---

---

## 4. Release Packaging Allowlist Specifications

To guarantee separation between production runtime deployment and development/testing benchmarking artifacts, two distinct package specifications are established:

### 4.1 Package A: Production Runtime Package Allowlist
The minimal artifact set permitted inside the production container (Hugging Face Spaces):
- **Backend Application Source Code:**
  - `backend/app/main.py`
  - `backend/app/core/*.py` (including `config.py`, `dependencies.py`)
  - `backend/app/api/**/*.py` (FastAPI route controllers)
  - `backend/app/services/**/*.py` (including `vision_service.py`, `disease_classifier.py`, `database_service.py`)
  - `backend/app/models/**/*.py` (Pydantic schemas and SQLAlchemy ORM models)
  - `backend/app/agents/**/*.py` (LangGraph workflows and nodes)
  - `backend/app/tools/**/*.py` (LLM clients and vector store wrappers)
  - `backend/requirements.txt`
- **Frontend Production Bundle:**
  - `backend/app/static/index.html`
  - `backend/app/static/assets/*.js`
  - `backend/app/static/assets/*.css`
  - `backend/app/static/favicon.ico`
- **Required Model Checkpoints & Metadata:**
  - Neural everyday vision: `backend/app/models/mobilenet_v3_small-047dcff4.pth` (10,306,551 bytes / 9.83 MB; PyTorch official ImageNet-1K pretrained weights; SHA-256: `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`). This is the sole model checkpoint included in the production package (~10.7 MB total package size).
- **Specialist Diagnostic Checkpoints Excluded from Production Runtime:**
  - `backend/app/models/skin_disease_model.pth` (69.15 MB / 72,504,350 bytes)
  - `backend/app/models/general_disease_model.pth` (42.85 MB / 44,929,227 bytes)
  - `backend/app/models/xray_fracture_model.pth` (27.15 MB / 28,466,113 bytes)
  - `backend/app/models/retina_model.pth` (18.18 MB / 19,066,270 bytes)
  - *Total excluded specialist weights: 157.32 MB (164,965,960 bytes).* Since production clinical specialist inference is unconditionally disabled in the current release pending formal clinical validation, these checkpoints are excluded from production distributions to eliminate unneeded weight and prevent unauthorized execution.
- **Hugging Face Spaces Ephemeral Persistence Reality:**
  - On standard CPU-Basic Docker containers, the local SQLite database (`susham_health.db`) is ephemeral.
  - Database state resets whenever the container restarts or rebuilds unless an external persistent volume is attached to `backend/storage/`.
- **Safe Configuration Templates:**
  - `.env.example` (Safe configuration template with zero real secrets; documents `ENABLE_CLINICAL_SPECIALIST_MODELS`, `CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL`, and `OFFLINE_MODE`)
- **Required Runtime Documentation:**
  - `README.md`
  - `docs/intended_use_and_limitations.md`
  - `docs/clinical_risk_assessment.md`
  - `docs/rollback_instructions.md`
  - `package_inventory.tsv` (SHA-256 and byte-size cryptographic inventory generated at `/tmp/newgenhealthai_prod_pkg/package_inventory.tsv`)

- **Local Reference Retrieval (RAG / Vector Store) Status in Package A:**
  - `backend/data/medical_book.pdf` and pre-built vector store databases (`backend/storage/vector_store/`) are **EXCLUDED** from Package A.
  - Runtime behavior: The application detects the absence honestly at startup and logs: `PDF not found ... medical_book.pdf and no pre-built vector store — vector store skipped`.
  - The retriever gracefully returns empty document lists without raising exceptions or making unverified claims.
  - The frontend UI does not falsely advertise or promise PDF/RAG reference retrieval.
  - No unapproved or copyrighted medical documents are downloaded, and ₹0 external inference expenditure is preserved.
- **Production Package Isolation Invariant:**
  - `backend/tests/fixtures/` is **STRICTLY EXCLUDED** from the production runtime package.
  - All unreviewed benchmark images (portrait photographs, clinical ISIC dermoscopy images, originals, derived images) remain excluded from production containers.

### 4.2 Package B: Development, Testing & Verification Package Allowlist
Artifacts preserved for local testing, CI validation, benchmark replication, and audit reproducibility:
- **Test Suites:**
  - Backend pytest suites: `backend/tests/test_*.py`, `backend/tests/conftest.py`
  - Frontend component tests: `frontend/src/**/*.test.jsx`
  - Playwright browser E2E test runner: `frontend/scripts/browser_e2e_verification.cjs`
- **Benchmark Images & Datasets:**
  - Genuine Everyday Dataset: `backend/tests/fixtures/genuine_everyday_images/` (active fixtures, `diagrams/`, `originals/`, `derived-images/`)
  - Genuine Clinical Dataset: `backend/tests/fixtures/genuine_clinical_images/` (active fixtures, `originals/`, `derived-images/`)
- **Evaluation & Reproducibility Tooling:**
  - `backend/scripts/evaluate_image_understanding.py`
  - `backend/scripts/redownload_with_verified_tls.py`
  - `backend/logs/evaluation_results.json`
- **Visual Evidence & Proof Artifacts:**
  - Browser E2E screenshots: `backend/tests/fixtures/browser_evidence/*.png`
- **Provenance Manifests & Legal Reviews:**
  - `backend/tests/fixtures/genuine_everyday_images/manifest.json`
  - `backend/tests/fixtures/genuine_everyday_images/provenance_review.json` (status: `PENDING_QUALIFIED_HUMAN_REVIEW`)
  - `backend/tests/fixtures/genuine_clinical_images/manifest.json`
  - `backend/tests/fixtures/genuine_clinical_images/provenance_review.json` (status: `PENDING_QUALIFIED_HUMAN_REVIEW`)
- **Frontend Development Source:**
  - `frontend/src/**/*`, `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`
- **Clinical Governance Protocols & Runbooks:**
  - `docs/clinical_validation_protocol.md`, `docs/clinician_review_template.md`, `docs/clinical_evaluation_checklist.md`
  - `docs/groq_key_rotation_procedure.md`, `docs/test_session_revocation.md`, `docs/image_understanding_audit.md`

### 4.3 Explicit Release Package Exclusions (All Packages)
- **Secrets & Credentials:**
  - All `.env` and `.env.*` files (strictly ignored by `.gitignore`)
  - Live API keys (Groq, Tavily, Qwen, Hugging Face tokens)
- **Databases & Private User Data:**
  - Production SQLite databases: `backend/storage/chat_db/susham_health.db`, `*.db`, `*.db-wal`, `*.db-shm`
  - Temporary test databases: `/tmp/*.db`
  - User accounts, session records, and consultation history
- **Caches, Build Artifacts & Virtual Environments:**
  - Python bytecode: `**/__pycache__/**`, `*.pyc`, `*.pyo`
  - Pytest & test caches: `.pytest_cache/`, `.coverage`, `htmlcov/`
  - Node modules & local build caches: `frontend/node_modules/`
  - Virtual environments: `.venv/`, `/tmp/nghai_venv/`
- **Developer Artifacts & Logs:**
  - Application logs: `backend/logs/*.log`, `*.log`
  - IDE conversation logs, transcripts, and scratch artifacts (`.gemini/`, `scratch/`)

---

## 5. Verified Security Invariants & Outstanding Owner/Human Blockers

### 5.1 Verified Security Invariants (Automated & Enforced)
- **Unconditional Production Specialist Gate Enforcement:** In `ENVIRONMENT=production`, diagnostic specialist model execution is unconditionally disabled fail-closed. No environment variables (`ENABLE_CLINICAL_SPECIALIST_MODELS=true`, `CLINICAL_GOVERNANCE_PRODUCTION_APPROVAL=true`), approval-shaped payloads, or request parameters can bypass this gate.
- **Physical Package Boundary:** All 4 specialist checkpoints (157.32 MB) are completely excluded from Package A (`/tmp/newgenhealthai_prod_pkg`).
- **General Recognition Independence:** Everyday visual recognition via MobileNetV3-Small operates independently on ImageNet-1K visual classes and makes zero medical diagnosis claims.
- **Production RAG & Vector Store Posture:** Local reference retrieval (RAG) is honestly documented as unavailable in Package A; the system skips vector store initialization gracefully while retaining full multi-turn conversational AI capabilities.
- **Non-Production Research-Mode Posture:** In non-production environments (`ENVIRONMENT!=production`), specialist model execution is accessible strictly as non-production research-mode access with clinical validation pending. The application does not enforce verified clinician-only authorization or technical user-supervision controls.

### 5.2 Outstanding Owner/Human Blockers (Required Prior to Release)
Production release remains strictly blocked until the following six human/owner actions are completed:

1. **Groq API Key Revocation & Replacement:** The previously exposed Groq API key (`gsk_...`) remains compromised and must be permanently revoked in the Groq console and replaced with a newly generated secret in Hugging Face Space settings. Configuring a replacement secret does NOT revoke the exposed key.
   - *Security Disclosure on Previous Exploratory Scanner:* An earlier exploratory credential scanner command used `print(... matched_str ...)`, which had the ability to print complete raw pattern matches. The actual output of that earlier execution is not available as independently verified evidence. Its actual output exposure cannot currently be determined: we do not claim that a live credential was definitely printed, nor do we claim that no credential could have been exposed. In strict accordance with audit guidelines, that exploratory command was not rerun, and IDE transcripts, task logs, or chat histories were not inspected to reconstruct its output. Revocation and replacement of the compromised Groq API key by the owner remains an absolute requirement prior to any deployment.
2. **Targeted Remote Test-Session Revocation:** Remote production session token revocation for test user `audit_live_tester_01` remains an explicit owner action requiring production credentials (`docs/test_session_revocation.md`).
3. **Portrait Photograph Provenance & Publicity Rights:** The test asset `portrait.jpg` is an authentic photograph sourced from Wikimedia Commons (licensed under CC-BY-SA-4.0), not a synthetic image. While copyright is licensed under CC-BY-SA-4.0, separate personality and publicity likeness rights were not cleared and require qualified human review, or the image must be removed from material intended for public distribution (`docs/image_understanding_audit.md`).
4. **ISIC Patient Consent & Ethics Verification:** Patient privacy, de-identification, consent, and applicable research ethics requirements for the four ISIC dermoscopic images (`ISIC_0000000`, `ISIC_0000001`, `ISIC_0000002`, and `ISIC_0000004`) must be verified by a qualified privacy/legal reviewer to determine which jurisdictional requirements actually apply (do not assume HIPAA applies automatically).
5. **Clinical Validation & Regulatory Requirements:** Specialist models (`skin_disease_model.pth`, `xray_fracture_model.pth`, `retina_model.pth`, `general_disease_model.pth`) remain NOT clinically validated. Specific clinical validation and applicable regulatory requirements (e.g., medical device classification, clearance, or exemptions) depend on intended use, user group, and target jurisdiction, and require assessment by qualified clinical, legal, and regulatory personnel rather than assuming a universal clinical trial mandate.
6. **Owner Deployment Authorization:** Deployment to Hugging Face Spaces (`git push origin fix/healthai-audit-premium-ui:main`) remains strictly halted awaiting the explicit authorization command from the repository owner:
   ```text
   DEPLOY NOW
   ```

Zero commits, pushes, merges, tags, or deployments will be executed without this explicit authorization.

---

## 6. Exact Working-Tree Git Status Accounting (`git status --porcelain=v1`)

### 6.0 Pre-Commit Working-Tree Audit Snapshot
This audit snapshot was recorded on 9 November 2026. This is a historical pre-commit snapshot, not a claim about the working tree after committing:
- **Branch:** `ci/add-backend-frontend-test-jobs`
- **Base PR #4 HEAD:** `00a4e7acdabfbded5e7b103273e06a435501c861`
- **Total Porcelain Lines at Audit:** Exactly **3**
- **Staged Changes (Index):** Exactly **0**
- **Modified Tracked Files (` M`):** Exactly **3** documentation files:
  1. `README.md`
  2. `docs/IMPLEMENTATION_STATUS.md`
  3. `docs/release_manifest.md`
- **Deleted Tracked Files (` D`):** Exactly **0**
- **Untracked Entries (`??`):** Exactly **0**

*(At the time of this audit, all application source code, test suites, CI workflows, and configurations were committed in Git HEAD `00a4e7a`; only the 3 designated documentation files were modified).*

### 6.1 Historical Audit Baseline Accounting (Reference)
During the initial recovery audit of branch `fix/healthai-audit-premium-ui` prior to PR #4 commit integration, 54 porcelain entries (30 modified tracked files, 1 deleted file, and 23 untracked entries) were inventoried and verified. All application files from that audit have since been reconciled, tested, and committed into the current PR #4 branch.
