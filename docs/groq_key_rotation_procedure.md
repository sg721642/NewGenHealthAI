# Groq API Key Rotation Procedure & Runbook

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Status:** `BLOCKED — OWNER ACTION REQUIRED`\
**Security Classification:** Highly Confidential SOP\

---

> [!WARNING]
> **CRITICAL SECURITY REQUIREMENT: ZERO CREDENTIAL EXPOSURE**\
> 1. Never reveal, print, grep, echo, or log raw API keys, bearer tokens, or secrets in terminal sessions, audit transcripts, screenshots, or commit histories.\
> 2. Antigravity and automated agents are strictly prohibited from generating, inspecting, or recovering credentials from memory or transcripts.\
> 3. Key creation and revocation require manual owner authentication via the GroqCloud web console.

---

## 1. Security Pre-Flight Verification

Before performing key rotation, verify repository security hygiene:

```bash
# 1. Confirm .env is ignored by git
git check-ignore -v .env
# Output must show: .gitignore: .env

# 2. Confirm no API keys or .env files staged in git index
git status --short | grep -E '\.env|secret|key'
# Output must be empty

# 3. Verify absence of committed secrets in recent git commit history
git log -n 20 --name-only | grep -E '\.env'
# Output must be empty
```

---

## 2. Step-by-Step Owner Key Rotation Runbook

### Step 1: Provision New Key in GroqCloud Console
1. Navigate to the official GroqCloud console: [https://console.groq.com/keys](https://console.groq.com/keys)
2. Authenticate using owner credentials.
3. Click **Create API Key**.
4. Set name: `newgenhealthai-prod-v3`
5. Copy the newly generated key `gsk_...` directly to a local password manager.
6. **Mandatory ₹0 Policy Verification:** Verify that the account tier is set to **Developer / Free Tier** with zero attached credit cards or pay-as-you-go billing schedules.

### Step 2: Update Local Development Environment
Open the local uncommitted `.env` file in an editor and update the key:

```bash
# Inside .env in repository root
GROQ_API_KEY="gsk_NEW_GENERATED_KEY_HERE"
```

Verify application loads the new key without logging its contents:
```bash
PYTHONPATH=backend python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')
k = os.getenv('GROQ_API_KEY', '')
print('Loaded successfully:', len(k) > 10 and k.startswith('gsk_'))
"
```

### Step 3: Update Cloud Production Secrets (Hugging Face Spaces)
If deploying to Hugging Face Spaces:
1. Open the Hugging Face Space repository: `https://huggingface.co/spaces/sg721642/NewGenHealthAI/settings`
2. Scroll to **Variables and secrets**.
3. Under **Repository secrets**, locate `GROQ_API_KEY`.
4. Click **Edit** and paste the new key value.
5. Save changes. Hugging Face will trigger an automatic clean container restart.

### Step 4: Revoke Deprecated Key
1. Return to [https://console.groq.com/keys](https://console.groq.com/keys).
2. Locate the previous API key (`newgenhealthai-legacy` or older key).
3. Click **Delete / Revoke**.
4. Confirm deletion. Any in-flight requests on the old token will immediately be rejected with HTTP 401.

### Step 5: Verification & Audit Logging
1. Run endpoint health verification:
   ```bash
   curl -s http://localhost:8000/api/v1/health | grep '"status":"ok"'
   ```
2. Log the rotation event (recording date, timestamp, and operator username, **never** the key itself) in institutional change records.
