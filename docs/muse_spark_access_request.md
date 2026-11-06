# GroqCloud Access Request: Muse Spark Open

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Status:** `ACCESS NOT VERIFIED — PREVIEW APPROVAL / NO-COST ACCESS NOT ESTABLISHED`\
**Model Identifier:** `meta-models/muse-spark-open`\
**Provider Platform:** GroqCloud Model Garden / Developer Preview\

---

> [!IMPORTANT]
> **GOVERNANCE & POLICY STATUS**\
> Under NewGenHealthAI's non-negotiable **₹0 budget constraint**, no paid API calls, cloud credits, billable quotas, or credit card attachments may be initiated.\
> As of this release audit, `meta-models/muse-spark-open` remains **unverified** for zero-cost operation. Inference with this model is strictly skipped in production until explicit developer preview approval or no-cost tier terms are confirmed in writing by GroqCloud.

---

## 1. Application Details & Project Profile

- **Project Name:** NewGenHealthAI
- **Repository:** `https://github.com/sg721642/NewGenHealthAI`
- **License:** Open Source (Educational & Investigational Research)
- **Primary Architecture:** Hybrid multimodal healthcare decision support system (FastAPI backend + Vite/React frontend + Groq LPU acceleration + Local Torch CPU fallback).
- **Target Workload:** Real-time visual understanding and clinical triage classification of open-source medical imaging datasets (ISIC Archive CC0, Wikimedia Commons CC-BY-SA).

---

## 2. Formal Access Request Draft

**To:** GroqCloud Developer Relations & Preview Access Team (`support@groq.com` / Groq Console Portal)\
**Subject:** [Developer Preview Request] No-Cost Academic Access for Open-Source Clinical Research (`meta-models/muse-spark-open`)\

```text
Dear Groq Developer Relations Team,

I am writing on behalf of the NewGenHealthAI open-source project (https://github.com/sg721642/NewGenHealthAI).
We are currently evaluating high-throughput, low-latency multimodal architectures on the Groq LPU inference engine
to improve automated diagnostic intake, image understanding, and medical triage.

We have integrated Groq SDK client pipelines supporting 'qwen/qwen3.8-27b' and would like to formally request preview access
and quota confirmation for the secondary multimodal model:

    Model: meta-models/muse-spark-open
    Organization: NewGenHealthAI Open Research
    Use Case: Educational and clinical triage demonstration on open dermatological (ISIC) and biomedical imagery.

CRITICAL POLICY REQUIREMENT:
Our project operates under a strict ₹0 ($0.00 USD) research budget. We do not maintain a commercial billing account or
credit card on file, and our policy strictly prohibits incurring any pay-as-you-go or usage-based charges.

We kindly request confirmation on the following:
1. Is 'meta-models/muse-spark-open' available under a free Developer Preview tier or free quota tier for open-source research?
2. If preview approval or whitelisting is required for our GroqCloud Organization ID, can our account be enrolled under the
   academic / open-source grant program?
3. Can a hard billing cap of $0.00 USD be enforced on the API key to ensure zero unexpected billing liability?

Thank you for your support of open-source AI and developer innovation on the Groq LPU engine.

Sincerely,
NewGenHealthAI Project Maintainers
GitHub: https://github.com/sg721642/NewGenHealthAI
```

---

## 3. Deployment Gating & Verification Criteria

Prior to enabling `meta-models/muse-spark-open` in `vision_service.py` or running unmocked inference in CI/CD pipelines, the project owner must verify:
1. [ ] GroqCloud dashboard confirms `meta-models/muse-spark-open` status as **Active** for the provisioned API key.
2. [ ] Billing threshold is explicitly set to **$0.00 hard limit** in the GroqCloud console.
3. [ ] A smoke test probe using `curl` returns HTTP 200 with zero charges registered against the account balance.
4. [ ] Until items 1–3 are complete, the system will maintain:
   ```json
   "status": "ACCESS NOT VERIFIED — PREVIEW APPROVAL / NO-COST ACCESS NOT ESTABLISHED"
   ```
