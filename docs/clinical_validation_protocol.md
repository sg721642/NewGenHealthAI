# Clinical Validation Protocol

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Clinical Status:** `NOT CLINICALLY VALIDATED`\
**Regulatory Class Target:** Software as a Medical Device (SaMD) — FDA Class II / EU MDR 2017/745 Class IIa\

---

> [!CAUTION]
> **CRITICAL CLINICAL NOTICE: NOT CLINICALLY VALIDATED**\
> NewGenHealthAI has **not** received clearance, approval, CE-mark, or certification from the United States Food and Drug Administration (FDA), European Medicines Agency / Notified Bodies (EU MDR), Central Drugs Standard Control Organisation (CDSCO), or any other national or international regulatory authority.\
> The software, neural architectures, clinical decision support pipelines, and diagnostic classification models implemented within NewGenHealthAI are strictly investigational. They **must not** be used as a standalone diagnostic tool, primary triage device, or definitive basis for medical therapy or intervention in clinical practice.

---

## 1. Study Objectives & Hypotheses

### 1.1 Primary Objective
To prospectively evaluate the diagnostic concordance, sensitivity, and specificity of NewGenHealthAI's specialist convolutional and vision-transformer models against board-certified specialist clinical consensus (ground truth) across four diagnostic modalities:
1. **Dermatological Lesions (`skin`):** 216 cutaneous conditions (EfficientNet-B4).
2. **Musculoskeletal Radiographs (`xray`):** Fracture and anatomical localization (DenseNet-121).
3. **Retinal Fundus Photography (`retina`):** Diabetic retinopathy, macular pathology, glaucoma (EfficientNet-B0).
4. **General Multimodal Pathology (`general`):** Brain MRI, hematology blood smears, oral lesions, cutaneous burns (ResNet-18).

### 1.2 Primary Hypotheses
- **$H_{0}$ (Null):** NewGenHealthAI assistive suggestions do not increase diagnostic accuracy or decrease time-to-triage compared to unassisted clinician review.
- **$H_{1}$ (Alternative):** Clinician review augmented by NewGenHealthAI triage flags demonstrates non-inferior sensitivity ($\ge 90\%$) and non-inferior specificity ($\ge 85\%$) for high-acuity pathologies relative to solo clinician assessment, without increasing diagnostic error.

---

## 2. Study Design & Methodology

### 2.1 Multi-Reader Multi-Case (MRMC) Protocol
- **Design:** Retrospective enriched multi-reader, multi-case (MRMC) paired-crossover clinical trial across three tertiary academic medical centers.
- **Waiver & IRB:** Full Institutional Review Board (IRB) / Independent Ethics Committee (IEC) clearance required prior to patient enrollment or archived specimen ingestion.
- **Reader Cohort:**
  - 6 Board-Certified Dermatologists (FAAD / equivalent).
  - 6 Board-Certified Radiologists (ABR / FRCR / equivalent).
  - 6 Board-Certified Ophthalmologists / Retina Specialists.
  - 6 Emergency Physicians / General Internists.
- **Washout Period:** Minimum 28 days between unassisted reading and AI-assisted reading sessions to eliminate recall bias.

### 2.2 Case Selection & Cohort Stratification
A statistically powered sample size of $N = 2,400$ validated cases ($600$ per modality):
- **Dermatology:** Minimum 100 cases per Fitzpatrick phototype tier (I–II, III–IV, V–VI) verified with histopathological biopsy report as definitive ground truth.
- **Radiography:** Balanced distribution across peripheral skeleton (wrist, hand, ankle, foot) and axial skeleton, with orthogonal two-view projections verified by subsequent CT or follow-up clinical recovery.
- **Ophthalmology:** ETDRS-graded 7-field or 45-degree color fundus photography with OCT confirmation for macular edema.
- **General / Neuro / Heme:** High-field 1.5T/3T MRI sequences with neuroradiology consensus; peripheral blood smears with automated counter plus manual differential microscopy.

---

## 3. Statistical Analysis & Endpoints

### 3.1 Primary Endpoints
- **Area Under the Receiver Operating Characteristic Curve (AUROC):** Multi-class macro-averaged AUROC and binary high-acuity pathology AUROC (target $\ge 0.92$).
- **Top-1 and Top-3 Categorical Accuracy:** Concordance between model top-ranked differential and histopathologic/radiographic ground truth.
- **Clinical Sensitivity / Recall:** High-acuity target conditions (e.g. Malignant Melanoma, Acute Skeletal Displacement, Proliferative Diabetic Retinopathy) must achieve $\ge 95\%$ sensitivity.

### 3.2 Secondary Endpoints
- **Inter-Reader Agreement (Cohen's / Fleiss' Kappa):** Measure concordance between human specialists alone versus human specialists with AI decision support.
- **Time-to-Triage:** Measured latency in seconds from case presentation to completed differential diagnosis documentation.
- **Abstention Utility:** Proportion of ambiguous or non-diagnostic images correctly flagged as `inconclusive` or `unsupported_image` without clinical misdirection.

---

## 4. Algorithmic Fairness & Bias Governance

### 4.1 Demographic & Phototype Stratification
To align with FDA recommendations and best-practice guidance on algorithmic bias in clinical AI:
- Sensitivity and specificity must be independently tabulated across:
  - Sex / Gender (Male, Female, Intersex).
  - Age cohorts ($<18$, $18-65$, $>65$).
  - Fitzpatrick phototypes I, II, III, IV, V, VI.
- **Disparity Threshold:** Any relative disparity $> 5\%$ in sensitivity between Fitzpatrick I–II and Fitzpatrick V–VI shall trigger an immediate algorithmic hold and retraining requirement.

### 4.2 Acquisition Device Robustness
Testing must span diverse camera sensors, optical dermatoscope attachments, radiographic detector brands (GE, Siemens, Philips), and optical fundus cameras (Topcon, Zeiss) to prevent domain overfitting.

---

## 5. Human-in-the-Loop Safeguards & Stopping Rules

1. **Mandatory Human Sign-off:** No model output shall be communicated to a patient or placed into an Electronic Health Record (EHR) without documented, licensed clinician verification.
2. **Adverse Event Stopping Rule:** If at any point during prospective evaluation the AI system causes a false negative recommendation on a critical condition (e.g., missed melanoma or acute fracture) that leads to simulated or actual clinical harm in $> 0.5\%$ of cases, the validation trial shall immediately halt for root cause analysis (RCA).
3. **Current Operating Status:** The system currently operates under research status with **zero** clinical certification.
