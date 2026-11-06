# Intended Use and Operational Limitations

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Clinical Status:** `NOT CLINICALLY VALIDATED`\
**Regulatory Target:** Investigational Device / Clinical Research Decision Support\

---

> [!WARNING]
> **INVESTIGATIONAL USE ONLY — NOT FOR PRIMARY CLINICAL DIAGNOSIS**\
> NewGenHealthAI is an investigational software platform intended exclusively for educational demonstrations, technical benchmarking, and medical informatics research. It has **not** been cleared or certified by any health authority for clinical diagnostic, prognostic, or treatment decisions.

---

## 1. Intended Use Statement

### 1.1 Purpose
NewGenHealthAI is designed as an **investigational decision-support prototype** to assist clinical researchers in exploring:
1. Multimodal intake of patient clinical history and symptom descriptions via natural language dialogue.
2. Automated classification of dermatological lesions, musculoskeletal radiographs, and retinal fundus photography using pre-trained convolutional neural networks.
3. Policy-based and heuristic filtering to discourage non-medical imagery (e.g. recognized everyday objects and pets), while explicitly documenting that automated general person detection is unsupported.

### 1.2 Target User Profile
- **Authorized Users:** Licensed physicians, clinical fellows, medical researchers, and health informatics professionals operating in controlled research environments.
- **Unauthorized Users:** Unsupervised patients, lay individuals, and emergency first-responders seeking definitive clinical guidance without specialist physician oversight.

---

## 2. Contraindications & Prohibited Use Cases

NewGenHealthAI is **strictly contraindicated** for the following scenarios:

| Category | Prohibited Use Case | Rationale |
|---|---|---|
| **Emergency Triage** | Acute trauma, active myocardial infarction, acute stroke, respiratory distress | Latency, lack of physiological monitoring, and unvalidated error boundaries pose unacceptable risk of life-threatening delay. |
| **Direct-to-Consumer** | Layperson self-diagnosis at home via mobile browser | Unsupervised users cannot accurately interpret uncalibrated probability vectors or clinical differential nuances. |
| **Surgical Planning** | Determining surgical margins for melanoma excision | Model resolutions and spatial registrations are insufficient for millimeter-level operative planning. |
| **Pediatric Intake** | Neonatal, infant, and pediatric patient triage ($<18$ years) | Training datasets (ISIC, MURA, Messidor) are derived predominantly from adult cohorts; pediatric presentation differs significantly. |
| **Pharmacotherapy** | Prescription generation, antibiotic selection, dosage calculation | Platform does not possess pharmacogenomic, drug-interaction, or organ-clearance safety checks. |
| **Ordinary Portraits** | Facial selfies, headshots, biometric identification | **PROHIBITED BY INTENDED-USE POLICY.** Automated general person detection is explicitly unsupported (`is_person: null`, `person_detection: 'unsupported'`). Biometric recognition is strictly prohibited. Portraits must never receive medical diagnoses, but the system does NOT claim universal automated portrait identification without dedicated models. Research intake relies on explicit user self-attestation. |

---

## 3. Technical & Operational Limitations

### 3.1 Uncalibrated Model Confidence
- **Uncalibrated Probability Vectors:** Raw Softmax outputs from convolutional models represent relative logit distances, **not** true Bayesian posterior probabilities of disease.
- **Confidence Disclosure:** A confidence score of `0.85` does **not** indicate an $85\%$ empirical probability of malignancy. Clinicians must treat scores as relative rankings only.

### 3.2 Visual Input Constraints
- **Minimum Resolution:** Images below $224 \times 224$ pixels exhibit severe feature degradation and will yield unreliable embeddings.
- **Lighting & Vignetting:** Clinical skin lesions photographed under harsh flash, low ambient light ($< 100\text{ lux}$), or through non-standard optical adapters can trigger false aperture detection.
- **Projection Limitations:** Musculoskeletal X-ray classification evaluates single-plane static projections. True skeletal displacement frequently requires orthogonal bi-plane or CT correlation.

### 3.3 Hardware Constraints & Offline Fallback
- **Hugging Face CPU Basic (2 vCPU, 16 GB RAM):** Processing times range from $35\text{ ms}$ (X-ray) to $\sim 450\text{ ms}$ (Skin). Extreme server load may queue requests.
- **Network Dependency:** When external multimodal APIs are unavailable or unconfigured, the system automatically falls back to local neural feature extraction and deterministic heuristics.

### 3.4 Person Detection & Portrait Safety Architecture
- **General Automated Person Detection is Unsupported:** The local vision model (MobileNetV3-Small) is a closed-set ImageNet-1K object classifier, not a dedicated face or person detector. Closed-set classes (e.g., `suit`, `groom`, `scuba diver`) reflect object labels, not face detection.
- **Explicit Invariant (`is_person: null`):** Wherever a reliable person detector is unavailable, the system honestly sets `is_person: null` and `person_detection: 'unsupported'`. It does not infer `is_person: false` merely because clothing or objects are predicted.
- **Biometric Recognition Prohibited:** The platform contains zero facial recognition, identity verification, or biometric surveillance capabilities.
- **Portrait Medical Diagnosis Policy:** Portraits are prohibited from receiving medical diagnoses under intended-use policy. Everyday recognition classifies recognizable objects (e.g., clothing), and clinical gates fail-closed without explicit user self-attestation. However, universal automated portrait identification is not claimed without dedicated biometric/face-detection models.
- **Research Modality Confirmation:** In research environments, intake relies on explicit user self-attestation (`modality_confirmed=true`) rather than automated visual person-proofing.

---

## 4. Clinician Responsibilities & Duty of Care

1. **Independent Verification:** The operating clinician retains $100\%$ legal and professional responsibility for all diagnostic conclusions, patient communications, and treatment plans.
2. **Clinical Correlation:** Model outputs must always be correlated with physical palpation, dermatoscopic dermoscopy, full clinical history, family history, and laboratory diagnostics.
3. **Audit Trail Review:** Any discrepancy between automated image routing and clinical suspicion must be manually overridden and documented in accordance with institutional policy.
