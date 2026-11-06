# Clinical Risk Assessment (Informational Risk Framework — Not Formally Certified)

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Clinical Status:** `NOT CLINICALLY VALIDATED`\
**Standard Reference:** ISO 14971:2019 Informative Principles (Informational risk framework only; not audited, cleared, or certified by a Notified Body or regulatory authority).\

---

> [!IMPORTANT]
> **RISK GOVERNANCE STATUS: UNVALIDATED RESIDUAL CLINICAL RISK**\
> Because NewGenHealthAI has not completed formal prospective multi-reader clinical trials or formal conformity assessment, all residual clinical risks documented herein remain active and unvalidated. The controls listed represent software engineering safeguards and diagnostic bounds, but do not replace certified clinical device manufacturing processes or formal regulatory conformity.

---

## 1. Risk Evaluation Criteria

### 1.1 Severity Categories
- **Catastrophic (S4):** Death or permanent severe disability (e.g. missed acute lethal pathology).
- **Critical (S3):** Serious injury or delayed medical intervention requiring hospital care.
- **Moderate (S2):** Minor reversible injury, psychological anxiety, or unnecessary non-invasive diagnostic follow-up.
- **Negligible (S1):** Inconvenience, slight delay, or no clinical consequence.

### 1.2 Probability Levels
- **Frequent (P5):** Occurs in $> 10\%$ of executions.
- **Probable (P4):** Occurs in $1\% - 10\%$ of executions.
- **Occasional (P3):** Occurs in $0.1\% - 1\%$ of executions.
- **Remote (P2):** Occurs in $0.01\% - 0.1\%$ of executions.
- **Improbable (P1):** Occurs in $< 0.01\%$ of executions.

---

## 2. Failure Modes and Effects Analysis (FMEA)

| Hazard ID | Failure Mode | Initial Risk (Sev / Prob) | Clinical Impact | Software Engineering & Clinical Safeguard | Residual Risk |
|---|---|---|---|---|---|
| **HAZ-001** | False Negative Melanoma (Model predicts Benign Nevus for Malignant Melanoma) | **S4 / P3 (High)** | Delayed excision; tumor progression to systemic metastasis. | 1. Raw logit score disclosure without artificial threshold promotion.<br>2. Prominent clinical disclaimer recommending urgent in-person biopsy for all suspicious lesions.<br>3. Differential includes full top-5 disease distribution.<br>4. Fail-closed production gate unconditionally blocks unvalidated specialist inference. | **S4 / P1 (Broadly Acceptable under Research Protocol; Prohibited in Production)** |
| **HAZ-002** | False Negative Radiographic Fracture (Model identifies anatomy but misses non-displaced hairline fracture) | **S3 / P3 (High)** | Inappropriate weight-bearing; progressive displacement; malunion. | 1. Anatomical localization explicitly decoupled from pathology clearance.<br>2. Clear statement: *"Anatomy identification must not be interpreted as proof that no abnormality exists."*<br>3. Fail-closed production gate unconditionally blocks unvalidated specialist inference. | **S3 / P1 (Broadly Acceptable under Research Protocol; Prohibited in Production)** |
| **HAZ-003** | Hallucination on Non-Medical Imagery (Model diagnoses melanoma on pet fur or everyday object) | **S2 / P4 (Moderate)** | Clinical confusion; loss of system trust; inappropriate clinic referral. | 1. Neural classification via MobileNetV3-Small identifies animals, plants, vehicles, and objects.<br>2. Override Safeguard 1 rejects non-medical images under neural vision.<br>3. Unvalidated visual color and chrominance heuristics eliminated; explicit user modality selection required. | **S2 / P1 (Broadly Acceptable)** |
| **HAZ-004** | Privacy / Biometric Violation on Human Portraits | **S2 / P4 (Moderate)** | Breach of patient privacy; unauthorized facial diagnostic assertion. | 1. Automated Portrait Guardrail detects human ImageNet classes and clothing categories.<br>2. Person presence honestly reported as Unsupported/Unknown for clothing-only categories.<br>3. Strictly blocks diagnostic disease inference on ordinary portraits. | **S1 / P1 (Negligible)** |
| **HAZ-005** | Overconfidence in Ambiguous / Blurry Images | **S3 / P4 (High)** | Inaccurate diagnosis based on noise, artifacts, or sensor blur. | 1. Spatial gradient sharpness pre-flight analysis.<br>2. Honest abstention returning status `inconclusive` rather than forced predictions. | **S3 / P1 (Broadly Acceptable)** |
| **HAZ-006** | Out-of-Scope Medical Modality Misrouting (e.g. Endoscopy image routed to general pathology) | **S3 / P3 (High)** | Irrelevant pathology diagnosis applied to unsupported anatomical site. | 1. Hard modality routing with strict cross-modality rejection.<br>2. Scope verification guard restricting General model to verified clinical domains. | **S3 / P1 (Broadly Acceptable)** |

---

## 3. Post-Market Clinical Monitoring (PMCF) Plan

Once clinical trials commence, the following proactive monitoring mechanisms will activate:
1. **Discrepancy Reporting Pipeline:** Immediate flagging whenever clinician override alters the model's top-1 diagnostic prediction.
2. **Subgroup Disparity Auditing:** Automated quarterly stratification audits across sex, age, and Fitzpatrick phototypes.
3. **Model Drift Monitoring:** Daily tracking of entropy distributions on incoming image tensors to detect imaging sensor changes or demographic distribution shifts.
