# Release Manifest: NewGenHealthAI v3.0.0-rc1

**Release Tag Candidate:** `v3.0.0-rc1`\
**Git Branch:** `fix/healthai-audit-premium-ui`\
**Repository:** `https://github.com/sg721642/NewGenHealthAI`\
**Target Infrastructure:** Hugging Face Spaces (CPU Basic: 2 vCPU, 16 GB RAM)\
**Release Readiness Status:** `BLOCKED — INTEGRITY REMEDIATION COMPLETED; AWAITING QUALIFIED HUMAN REVIEW, CLINICAL VALIDATION & OWNER AUTHORIZATION`\

---

## 1. Release Verification Matrix (15 Mandatory Checks)

| # | Check Item | Requirement | Verification Method | Status |
|---|---|---|---|:---:|
| **1** | **Git Branch Integrity** | Clean branch `fix/healthai-audit-premium-ui` | `git status` | **PASSED** |
| **2** | **Zero-Cost Budget Policy** | ₹0 incurred; zero paid API calls or cloud billing | Unmocked billed API skips in `vision_service.py` | **PASSED** |
| **3** | **Hardware Constraints** | Sub-500ms CPU inference on local Apple M5 host | PyTorch benchmark on CPU | **PASSED** |
| **4** | **Database Protection** | `susham_health.db` never overwritten, connected, or altered | `PRAGMA database_list;` + SHA-256 baseline invariance (`e86d5e99...`) | **PASSED** |
| **5** | **Zero Secret Exposure** | No API keys committed or displayed in logs | Git index and log inspection | **PASSED** |
| **6** | **Everyday Recognition** | Neural local vision model for non-medical images | MobileNetV3-Small (1000 classes, 50ms) | **PASSED** |
| **7** | **Genuine Everyday Dataset** | 8 Wikimedia Commons photographs (CC-BY-SA-4.0) | Dog & Apple resolved via Wikimedia API; originals preserved via verified TLS; independent SHA-256 hashes pinned | **PASSED** |
| **8** | **Genuine Clinical Dataset** | 4 ISIC Archive dermoscopy images (CC0-1.0) | Originals preserved via verified TLS; independent SHA-256 hashes pinned; explicit modality gate | **PASSED** |
| **9** | **Specialist Models Benchmark** | Benchmark 4 models on CPU without crash | Local CPU forward pass latency audit (`FORWARD PASS VERIFIED`); production gate disabled by default | **PASSED** |
| **10** | **Clinical Governance Docs** | 5 formal governance protocols authored | `docs/` clinical documents created; status `NOT CLINICALLY VALIDATED` | **PASSED** |
| **11** | **Security Runbooks** | Key rotation, session revocation, access request | `docs/` runbooks drafted; targeted revocation unit tests passing (`OWNER ACTION REQUIRED`) | **PASSED** |
| **12** | **Backend Test Suite** | 100% test pass rate in isolated Python 3.13.9 venv | Pytest (459/459 passed, 0 application warnings, 1 third-party Starlette/AnyIO deprecation warning in `/tmp/nghai_final_clean_venv`) | **PASSED** |
| **13** | **Frontend Component Suite** | 100% unit and integration test pass rate | Vitest (36/36 passed, previously verified) | **PASSED** |
| **14** | **Frontend Browser E2E Suite** | 100% browser UI rendering & mobile layout | Playwright Chromium (5/5 passed, previously verified) | **PASSED** |
| **15** | **Frontend Production Build** | Static bundle built cleanly to `backend/app/static/` | Vite build (564ms, 0 errors, previously verified) | **PASSED** |

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

### 6.0 Review Methodology & Evidence Distinction
Note: `git diff --stat` only summarizes changes within tracked files and does not include untracked file contents. Repository verification used distinct methods appropriate to each asset type:
1. **Tracked-File Diff Review:** Full line-by-line inspection of changes across all 30 modified tracked files and 1 deleted tracked file via git diffs.
2. **Individually Inspected Untracked Source Files & Scripts:** Complete manual inspection of untracked application source (`backend/app/services/vision_service.py`), scripts (`backend/scripts/*.py`, `frontend/scripts/*.cjs`), and untracked test suites (`backend/tests/test_*.py`).
3. **Binary Asset & Cryptographic Checksum Verification:** Direct cryptographic SHA-256 checksum calculation and size verification for binary weights (`mobilenet_v3_small-047dcff4.pth`) and test image fixtures (`backend/tests/fixtures/`), as binary files cannot be evaluated via text diffs.
4. **Documentation Review:** Comprehensive textual review of all 11 untracked and 2 modified documentation files in `docs/`.
5. **Test Accounting Distinction:** The 459/459 backend test result represents the latest previously executed clean-environment verification in `/tmp/nghai_final_clean_venv` (459 passed, 0 application warnings, 1 third-party Starlette warning). Tests were not rerun during this code review pass. Frontend Vitest unit tests (36 passed) and Playwright browser E2E tests (5 passed) remain separately identified as earlier executions.

Independently verified from `git status --porcelain=v1` on branch `fix/healthai-audit-premium-ui`:
- **Total Porcelain Lines:** Exactly **54**
- **Staged Changes (Index):** Exactly **0**
- **Renamed Entries:** Exactly **0**
- **Modified Tracked Files (` M`):** Exactly **30** unique files
- **Deleted Tracked Files (` D`):** Exactly **1** unique file
- **Untracked Entries (`??`):** Exactly **23** unique entries
- **Double-Counted Entries:** Exactly **0** (Reconciliation note: `docs/release_manifest.md` is strictly untracked; an earlier draft inadvertently listed it under both modified tracked and untracked entries, creating an apparent 31-item list against a count of 30. Removing this duplicate restores exact 30-item parity).

### 6.1 Modified Tracked Files (30)
- **Configuration & Environment (3):**
  1. `.dockerignore`
  2. `.env.example`
  3. `.gitignore`
- **Backend Application Source & Services (12):**
  4. `backend/app/agents/executor.py`
  5. `backend/app/agents/retriever.py`
  6. `backend/app/api/image_api.py`
  7. `backend/app/api/v1/endpoints/session.py`
  8. `backend/app/core/config.py`
  9. `backend/app/db/migrations.py`
  10. `backend/app/db/session.py`
  11. `backend/app/main.py`
  12. `backend/app/services/database_service.py`
  13. `backend/app/services/disease_classifier.py`
  14. `backend/app/tools/llm_client.py`
  15. `backend/app/tools/vector_store.py`
- **Build & Test Configurations (2):**
  16. `backend/pyproject.toml`
  17. `pytest.ini`
- **Backend Test Files (9 — 8 test modules and 1 conftest configuration file):**
  18. `backend/tests/conftest.py` (pytest setup/fixtures)
  19. `backend/tests/test_agents.py`
  20. `backend/tests/test_model_fairness_and_safety.py`
  21. `backend/tests/test_phase1d_concurrency.py`
  22. `backend/tests/test_phase2a_image_classifier.py`
  23. `backend/tests/test_phase3a_image_security.py`
  24. `backend/tests/test_phase3b_voice_security.py`
  25. `backend/tests/test_phase4_hardening.py`
  26. `backend/tests/test_tools.py`
- **Tracked Documentation (2):**
  27. `docs/DEPLOYMENT_RUNBOOK.md`
  28. `docs/IMPLEMENTATION_STATUS.md`
- **Frontend Source & Component Tests (2 — 1 source + 1 test suite):**
  29. `frontend/src/App.jsx`
  30. `frontend/src/App.test.jsx`

*(Sub-count check: 3 + 12 + 2 + 9 + 2 + 2 = Exactly 30 modified tracked files).*

### 6.2 Deleted Tracked Files (1)
1. `backend/pytest.ini` (Consolidated into repository root `pytest.ini`)

### 6.3 Untracked Entries (23)
- **Backend Model Weights, Service & Evaluation Scripts (4):**
  1. `backend/app/models/mobilenet_v3_small-047dcff4.pth` (verified via SHA-256)
  2. `backend/app/services/vision_service.py` (inspected line-by-line)
  3. `backend/scripts/evaluate_image_understanding.py` (inspected line-by-line)
  4. `backend/scripts/redownload_with_verified_tls.py` (inspected line-by-line)
- **Test Fixtures Directory (1):**
  5. `backend/tests/fixtures/` (verified via manifests and cryptographic SHA-256 hashes)
- **Untracked Backend Test Suites (6):**
  6. `backend/tests/test_clinical_gate.py` (inspected line-by-line)
  7. `backend/tests/test_endpoint_regression_safety.py` (inspected line-by-line)
  8. `backend/tests/test_offline_mode_subprocess.py` (inspected line-by-line)
  9. `backend/tests/test_session_history_security.py` (inspected line-by-line)
  10. `backend/tests/test_targeted_session_revocation.py` (inspected line-by-line)
  11. `backend/tests/test_vision_understanding.py` (inspected line-by-line)
- **Untracked Documentation Files (11):**
  - *Clinical Governance Protocols (5):*
    12. `docs/clinical_evaluation_checklist.md` (inspected line-by-line)
    13. `docs/clinical_risk_assessment.md` (inspected line-by-line)
    14. `docs/clinical_validation_protocol.md` (inspected line-by-line)
    15. `docs/clinician_review_template.md` (inspected line-by-line)
    16. `docs/intended_use_and_limitations.md` (inspected line-by-line)
  - *Security, Operational & Release Runbooks / Manifests (6):*
    17. `docs/groq_key_rotation_procedure.md` (inspected line-by-line)
    18. `docs/image_understanding_audit.md` (inspected line-by-line)
    19. `docs/muse_spark_access_request.md` (inspected line-by-line)
    20. `docs/release_manifest.md` (inspected line-by-line)
    21. `docs/rollback_instructions.md` (inspected line-by-line)
    22. `docs/test_session_revocation.md` (inspected line-by-line)
- **Untracked Frontend E2E Verification Script (1):**
  23. `frontend/scripts/browser_e2e_verification.cjs` (inspected line-by-line)

*(Sub-count check: 4 + 1 + 6 + 11 + 1 = Exactly 23 untracked entries).*
