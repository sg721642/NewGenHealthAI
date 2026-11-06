# Clinician Case Review Template

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Clinical Status:** `NOT CLINICALLY VALIDATED`\
**Purpose:** Standardized clinical case review form for documenting expert clinician assessment during trial evaluations.

---

> [!CAUTION]
> **CONFIDENTIAL INVESTIGATIONAL TRIAL RECORD**\
> Complete this form for every case evaluated in the NewGenHealthAI clinical validation trial. Do **not** enter direct patient identifiers (Name, Social Security / National ID, Contact Info). Use assigned Study Case ID only.

---

## 1. Case Metadata & Setting

- **Study Case ID:** `_______________________`
- **Evaluation Date (YYYY-MM-DD):** `_______________________`
- **Clinical Site:** `_______________________`
- **Evaluating Clinician:** `_______________________, M.D. / D.O. / MBBS`
- **Specialty / Board Certification:** `[ ] Dermatology  [ ] Radiology  [ ] Ophthalmology  [ ] Emergency Medicine  [ ] Other: _______`
- **Years in Specialist Practice:** `_______`

---

## 2. Patient Profile & Clinical Presentation

- **Age:** `_______` | **Biological Sex:** `[ ] Male  [ ] Female  [ ] Other`
- **Fitzpatrick Skin Phototype:** `[ ] I  [ ] II  [ ] III  [ ] IV  [ ] V  [ ] VI  [ ] Not Applicable (Radiograph/Retina)`
- **Anatomical Site:** `_______________________`
- **Duration of Lesion / Symptom:** `_______________________`
- **Relevant Medical / Family History:** `___________________________________________________`
- **Pre-AI Specialist Differential Diagnosis:**
  1. `___________________________________________________`
  2. `___________________________________________________`
  3. `___________________________________________________`

---

## 3. NewGenHealthAI Assessment Output

- **Modality Evaluated:** `[ ] skin  [ ] xray  [ ] retina  [ ] general`
- **Inference Status:** `[ ] analysis_complete  [ ] inconclusive  [ ] unsupported_image  [ ] general_recognition`
- **Vision Engine Used:** `[ ] groq_vision (Qwen 3.8 27B)  [ ] local_neural_vision (MobileNetV3-Small)  [ ] heuristic_fallback`
- **Top-1 Predicted Condition:** `___________________________________________________`
- **Raw Uncalibrated Score:** `____________`
- **Top-5 Predicted Differential:**
  1. `_______________________________________` (Score: `______`)
  2. `_______________________________________` (Score: `______`)
  3. `_______________________________________` (Score: `______`)
  4. `_______________________________________` (Score: `______`)
  5. `_______________________________________` (Score: `______`)

---

## 4. Clinician Concordance & Critical Review

### 4.1 Diagnostic Agreement
- **Overall Agreement with Top-1:**
  - `[ ] Complete Agreement` (AI top-1 matches clinician primary diagnosis)
  - `[ ] Partial Agreement` (AI top-1 is within clinician top-3 differential)
  - `[ ] Complete Disagreement` (AI top-1 is incorrect and clinically inappropriate)
  - `[ ] Inconclusive Agreement` (System correctly abstained on non-diagnostic image)

### 4.2 Clinical Utility Rating
- **Did the AI decision support alter your diagnostic workup or differential?**
  - `[ ] Yes — Promoted consideration of an overlooked high-acuity condition`
  - `[ ] Yes — Provided reassurance on a benign entity`
  - `[ ] No — Did not alter clinical impression`
  - `[ ] Adverse — Misleading prediction that could have delayed care if followed uncritically`

### 4.3 Safety & Failure Analysis
- **Did the model exhibit any of the following failure modes?**
  - `[ ] False Negative on High-Acuity Condition (e.g. Melanoma called Nevus)`
  - `[ ] Inappropriate Modality Assignment`
  - `[ ] Non-Medical Hallucination (Diagnosed condition on artifact / skin border)`
  - `[ ] Overconfident prediction on low-quality / blurry image`
  - `[ ] None observed`

---

## 5. Definitive Ground Truth & Disposition

- **Definitive Ground Truth Source:**
  - `[ ] Histopathological Biopsy Report`
  - `[ ] Second-Line Imaging (CT / MRI / Optical Coherence Tomography)`
  - `[ ] Clinical Panel Consensus (3 Specialist Agreement)`
  - `[ ] Clinical Resolution upon Follow-up`
- **Definitive Diagnosis:** `___________________________________________________`
- **Patient Management Plan:** `___________________________________________________`

---

## 6. Attestation & Signature

*I hereby attest that the clinical evaluation above reflects my independent medical judgment. NewGenHealthAI was utilized strictly as an investigational decision-support tool. I bear full clinical responsibility for the patient care decisions documented herein.*

**Clinician Signature:** `__________________________________________`\
**License Number & State/Country:** `__________________________________________`\
**Date Signed:** `____________________`
