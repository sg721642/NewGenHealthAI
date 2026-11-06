# Clinical Evaluation Checklist

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Clinical Status:** `NOT CLINICALLY VALIDATED`\
**Purpose:** Standard operating procedure (SOP) checklist for clinical investigators conducting evaluations of NewGenHealthAI.

---

> [!NOTE]
> **INVESTIGATIONAL PROTOCOL COMPLIANCE**\
> Every clinical evaluation session using NewGenHealthAI must be conducted by a licensed physician and documented using this checklist. All items must be completed before saving or exporting case notes.

---

## Pre-Inference Verification

- [ ] **1. Patient Informed Consent**
  - [ ] Patient has signed the institutional IRB-approved Investigational Device Consent Form.
  - [ ] Patient understands that NewGenHealthAI outputs are experimental and that a licensed physician is making all diagnostic decisions.
- [ ] **2. Demographics & Context Verification**
  - [ ] Patient age confirmed $\ge 18$ years (adult cohort only).
  - [ ] Fitzpatrick skin phototype documented (Type I through VI).
  - [ ] Anatomical site of lesion / radiograph documented.
- [ ] **3. Photographic Quality Pre-Flight**
  - [ ] Image resolution $\ge 224 \times 224$ pixels.
  - [ ] Field of view centered on primary pathology.
  - [ ] Adequate ambient lighting ($\ge 100\text{ lux}$); no specular flash glare obliterating lesion borders.
  - [ ] Lens in sharp focus (zero motion blur or sensor noise).
  - [ ] Zero human facial features or non-medical background artifacts present.

---

## Inference Execution & Review

- [ ] **4. Modality Routing Confirmation**
  - [ ] Automated modality detection correctly matched clinical intention (`skin`, `xray`, `retina`, `general`).
  - [ ] If user override was used, override justification was logged in the case record.
  - [ ] Safeguards confirmed zero non-medical rejection flags (`unsupported_image`).
- [ ] **5. Differential Analysis Review**
  - [ ] Top-1 predicted condition reviewed against clinical differential.
  - [ ] Full Top-5 differential distribution inspected for high-acuity life-threatening alternatives (e.g. Melanoma, Acute Displacement, Neovascular Retinopathy).
  - [ ] Raw confidence score recorded as a relative ranking (not interpreted as empirical Bayesian posterior probability).
- [ ] **6. Anatomical vs. Pathology Distinction (Radiographs Only)**
  - [ ] Confirmed that anatomical recognition (e.g. wrist/hand) is not interpreted as clearance of pathology.
  - [ ] Dedicated radiological inspection performed for non-displaced fractures, cortical disruptions, and joint effusions.

---

## Post-Inference Clinical Decision & Documentation

- [ ] **7. Multi-Modal Clinical Correlation**
  - [ ] Output correlated with patient history, duration of symptoms, and palpation/dermoscopic examination.
  - [ ] Physical dermatoscope inspection completed (ABCD rule: Asymmetry, Border, Color, Diameter).
- [ ] **8. Independent Clinician Verdict**
  - [ ] Clinician has recorded independent diagnosis prior to viewing AI recommendation, or has documented concurrence / non-concurrence.
  - [ ] Actionable clinical plan documented (Biopsy, Follow-up in 3 months, Immediate Surgical Referral, Conservative Management).
- [ ] **9. Final Case Sign-off**
  - [ ] Licensed physician signature and medical license number appended.
  - [ ] Record securely archived in encrypted compliance audit store.
