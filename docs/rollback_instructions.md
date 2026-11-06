# Emergency Rollback Instructions

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Target Infrastructure:** Hugging Face Spaces / Docker CPU Basic\

---

> [!CAUTION]
> **EMERGENCY RESPONSE PROTOCOL**\
> In the event of a critical failure (production crash loop, memory exhaustion OOM, database locking, or frontend asset 404), follow the immediate rollback procedures detailed below. Do not attempt unvalidated live code edits on the production server.

---

## 1. Fast Rollback via Git (Hugging Face Spaces)

If a newly deployed commit causes container failure on Hugging Face Spaces:

### Step 1: Identify Known Good Commit
Check the git commit log for the prior stable release tag:

```bash
git log --oneline -n 5
# Example:
# a1b2c3d (HEAD -> fix/healthai-audit-premium-ui) Release v3.0.0-rc1
# 9f8e7d6 (tag: v2.9.4-stable) Previous verified release
```

### Step 2: Force Rollback Commit on Hugging Face Remote
```bash
# Force rollback to known stable commit (replace 9f8e7d6 with stable SHA)
git push --force origin 9f8e7d6:main
```
Hugging Face Spaces will automatically terminate the failing container and rebuild from the known stable commit.

---

## 2. Database Recovery Runbook (`susham_health.db`)

If a database corruption or lock deadlock occurs during a release event:

### Step 1: Terminate Active Backend Workers
```bash
# Stop running uvicorn/gunicorn server
pkill -f "uvicorn.*app.main:app"
```

### Step 2: Restore from Pre-Deployment Backup
```bash
# Locate most recent backup
ls -lt susham_health.db.backup_* | head -n 1

# Restore the snapshot
cp susham_health.db.backup_YYYYMMDD_HHMMSS susham_health.db
```

### Step 3: Verify Integrity & Foreign Keys
```bash
PYTHONPATH=backend /private/tmp/nghai_venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('susham_health.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check;')
res = cursor.fetchone()
assert res[0] == 'ok', f'Integrity check failed: {res}'
cursor.execute('PRAGMA foreign_key_check;')
fk_res = cursor.fetchall()
assert len(fk_res) == 0, f'Foreign key violations: {fk_res}'
print('Database integrity verified: 100% OK')
conn.close()
"
```

---

## 3. Frontend Static Fallback

If frontend client assets fail to resolve or serve HTTP 404:

```bash
# Rebuild production static bundle locally
npm --prefix frontend run build

# Verify presence of compiled static index and assets
ls -la backend/app/static/index.html
ls -la backend/app/static/assets/
```

Restart backend server to ensure FastAPI mounts the fresh static directory:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

---

## 4. Post-Rollback Escalation & Incident Log

1. Notify development team of rollback execution.
2. Export Hugging Face container logs: `https://huggingface.co/spaces/sg721642/NewGenHealthAI/logs`
3. Open a post-mortem issue in GitHub issues tracking the root cause.
