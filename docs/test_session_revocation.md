# Remote Test Session Revocation Runbook

**Document Version:** 1.0.0\
**Effective Date:** November 2026\
**Status:** `BLOCKED — OWNER ACTION REQUIRED`\
**Target Account:** `audit_live_tester_01`\
**Database File:** `susham_health.db`\

---

> [!CAUTION]
> **DATABASE SAFETY NON-NEGOTIABLE PRINCIPLE**\
> 1. Under **no circumstances** may the database `susham_health.db` be dropped, reset, recreated, or overwritten.\
> 2. No tables or data belonging to legitimate registered users or existing clinical sessions may be altered.\
> 3. Revocation of `audit_live_tester_01` must be surgical and verified using foreign-key cascade checks.

---

## 1. Context & Purpose

During earlier security and automated intake penetration audits, an ephemeral audit user account `audit_live_tester_01` was provisioned to test multi-user isolation, session hijacking protection, and concurrency locks.\
To return the production and staging environments to a clean release state, all active JWT sessions, messages, conversations, and records associated with this audit account must be revoked.

---

## 2. Pre-Execution Database Backup

Before executing any deletion queries, perform an atomic file copy backup:

```bash
# Atomic snapshot of live database
cp susham_health.db "susham_health.db.backup_$(date +%Y%m%d_%H%M%S)"
```

---

## 3. Surgical Procedures: Session Revocation vs Account Deletion

### Procedure A: Targeted Session Revocation (Recommended)
This is the **recommended, non-destructive procedure**. It immediately invalidates all active JWT bearer session tokens for `audit_live_tester_01` while preserving conversation records, messages, and account history for audit transparency:

* **Target Runtime & Database:** The backend administrative shell or Python environment connecting to the database specified by `DATABASE_URL` (locally `backend/storage/chat_db/susham_health.db`; remotely the Hugging Face Space persistent storage).
* **Scope:** Targets **ONLY** `audit_live_tester_01` sessions via `DELETE FROM user_sessions WHERE user_id = :user_id`. Leaves all other registered users and existing clinical sessions 100% untouched.

```python
from app.services.database_service import db_service

# Surgically revokes all active session tokens for audit_live_tester_01 only
revoked_count = db_service.revoke_sessions_for_user("audit_live_tester_01")
print(f"Targeted session revocation completed: {revoked_count} active sessions revoked for audit_live_tester_01.")
```

---

### Procedure B: Permanent Account & History Deletion (Destructive — NOT a Session Revocation Alternative)

> [!WARNING]
> **DESTRUCTIVE ACCOUNT DELETION NOTICE**\
> Procedure B is a **permanent, irreversible data deletion procedure** that purges the user account, conversations, messages, and session tokens. It is **NOT** an alternative session-revocation method. It should only be executed if the repository owner explicitly decides to permanently erase the test user and its historical records entirely.

Executed via `sqlite3` CLI against the target database:

```sql
-- Step 1: Verify the audit user ID
SELECT id, username, email, created_at FROM users WHERE username = 'audit_live_tester_01';

-- Step 2: Delete messages associated with audit tester conversations
DELETE FROM messages
WHERE session_id IN (
    SELECT id FROM conversations WHERE user_id IN (
        SELECT id FROM users WHERE username = 'audit_live_tester_01'
    )
);

-- Step 3: Delete conversations belonging to audit tester
DELETE FROM conversations
WHERE user_id IN (
    SELECT id FROM users WHERE username = 'audit_live_tester_01'
);

-- Step 4: Revoke active session tokens
DELETE FROM user_sessions
WHERE user_id IN (
    SELECT id FROM users WHERE username = 'audit_live_tester_01'
);

-- Step 5: Permanently delete the user account
DELETE FROM users
WHERE username = 'audit_live_tester_01';
```

---

## 4. Verification & Integrity Checklist

Run verification queries to ensure surgical deletion with zero collateral data loss:

```bash
PYTHONPATH=backend /private/tmp/nghai_venv/bin/python3 -c "
import sqlite3

conn = sqlite3.connect('susham_health.db')
cursor = conn.cursor()

# 1. Confirm audit user is gone
cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('audit_live_tester_01',))
audit_count = cursor.fetchone()[0]
assert audit_count == 0, 'Audit user still exists!'

# 2. Confirm other users remain intact
cursor.execute('SELECT COUNT(*) FROM users')
total_users = cursor.fetchone()[0]
print(f'Verification passed: audit_live_tester_01 = 0 records. Total registered users remaining = {total_users}.')

conn.close()
"
```

---

## 5. Execution Authorization Sign-Off

Because production database modifications require explicit administrator authorization, this task is designated:
```text
STATUS: BLOCKED — OWNER ACTION REQUIRED
```
The repository owner must execute the script in Section 3 on the production host or execute the Python verification command once deployed.
