# NewGenHealthAI — Audit Findings (A01–A17)

Commit audited: `1605ec87683e735857ad3c0353fa0ce8feceffbe`
Last updated: Phase 1C.1 (Authentication Hardening and Database Migration Risks Remediation)

| ID | Priority | File(s) | Finding Summary | Status | Fix Phase |
|---|---|---|---|---|---|
| A01 | P0 | `dependencies.py`, `session.py`, `chat.py`, `database_service.py`, `voice.py` | Missing/invalid auth returned None. Anonymous list/read/delete paths allowed arbitrary data access. Fixed via `get_current_user` (401 on missing/invalid), query-param tokens eliminated completely, and strict owner-enforced database queries. | 🟢 Fixed | Phase 1A / Phase 1B |
| A02 | P0 | `message.py`, `chat_service.py`, `session.py`, `chat.py`, `migrations.py` | `conversation_states` keyed by client-supplied session ID without ownership check. Fixed with `Conversation` entity, server-generated session IDs, memory keyed by `f"{user_id}:{session_id}"`, strict rejection of arbitrary/unknown client IDs, and safe quarantine migration. | 🟢 Fixed | Phase 1A / Phase 1B / Phase 1C.1 |
| A03 | P0 | `disease_classifier.py` | `GARBAGE_CLASSES` includes legitimate normal/negative labels. Normal=0.96/pneumonia=0.04 input returns pneumonia. `_get_xray_diagnosis` converts wrist=0.95 into an abnormality. | 🔴 Open | Phase 3 |
| A04 | P0 | `disease_classifier.py` | Claims hard modality lock but falls back to general then all models. CLIP failure returns general. No models → non-medical. Min score 0.02; calibrated_conf copies raw score with no calibration. | 🔴 Open | Phase 3 |
| A05 | P1 | `langgraph_workflow.py` | `_route_after_llm` routes failure to retriever; `_route_after_rag` routes back to llm_agent. Attempt flags do not terminate the cycle. `_route_after_llm_fallback` is unused. | 🔴 Open | Phase 4 |
| A06 | P1 | `models/message.py`, `auth.py`, `database_service.py`, `main.py`, `migrations.py` | Argon2id hashing with unique per-password random salts. Safe PBKDF2 migration rehash via optimistic concurrency. 256-bit entropy tokens stored as SHA-256 hashes (`token_hash`) with expiration (`expires_at`) and immediate revocation. Starlette key persistent via `SESSION_SECRET_KEY`. Phase 1C.1: SEC-01 trusted proxy validation (`TRUSTED_PROXIES`), SEC-02 bounded in-memory rate limiting with per-account lockouts, MIG-01 atomic staging migration with pre-cutover validation and rollback, and MIG-02 fail-closed quarantine for missing users table. | 🟢 Fixed | Phase 1C / Phase 1C.1 |

| A07 | P1 | `main.py` | Wildcard CORS with credentials (`allow_origins=["*"]`, `allow_credentials=True`). Fixed in Phase 1C: restricted to explicit `ALLOWED_ORIGINS` whitelist. Image and voice routes protected with authentication (Phase 1A). | 🟢 Fixed | Phase 1A / Phase 1C |
| A08 | P1 | `voice.py`, `App.jsx` | TTS text sent as GET query parameter (URL-logged). STT logs transcript excerpts. Raw exception strings returned to clients. Fixed in Phase 1B/1C: TTS converted to POST with JSON body and Bearer token; frontend revokes Blob URLs; STT transcript logging removed (character count only); error responses sanitized. | 🟢 Fixed | Phase 1B / Phase 1C |
| A09 | P1 | `disease_classifier.py`, `conftest.py` | Models initialize at import time. Classifier constructor can download weights. Test conftest imports app before mock fixture runs. | 🟡 Partial | Phase 1A (Lazy ML imports, offline tests working) |
| A10 | P1 | `App.jsx` | Callbacks capture stale `authHeaders`. Login state trusted from localStorage without server validation. New-chat session ID discarded. Fixed in Phase 1A/1B/1C: session ID captured, authHeaders in dependencies, mount-time token validation against `/api/v1/auth/me`, logout state wipe. | 🟢 Fixed | Phase 1A / Phase 1B / Phase 1C |
| A11 | P1 | `session.py`, `chat_service.py` | `/clear` resets memory only; old messages remain in SQLite. Delete history does not clear memory. Memory does not hydrate from saved messages after restart. | 🟡 Partial | Phase 1A (Clear now clears both DB and memory; Delete removes both; restart hydration in Phase 2) |
| A12 | P1 | `frontend/public/index.html`, Dockerfile | `public/index.html` duplicates Vite entry with stale title/script. Standalone Dockerfile expects `/app/dist` but Vite defaults to backend static path. | 🔴 Open | Phase 5 |
| A13 | P1 | `requirements.txt`, `pyproject.toml`, README | Root and backend requirements disagree. pyproject includes TensorFlow not evidenced as necessary. README advertises scripts absent in source. | 🔴 Open | Phase 6 |
| A14 | P1 | `run.py` | Patches `torch.__version__` at runtime. Ignores install failures. Uses shell-based npm. Machine-specific paths. | 🔴 Open | Phase 5 |
| A15 | P2 | `eslint.config.js`, `setupTests.js`, `tailwind.config.js`, `vite.config.js`, `App.test.jsx`, `App.jsx` | ESLint lacked test/Node globals. `global` undefined in test setup. CommonJS `require` in ESM tailwind. `process` undefined in vite.config. Phase 1B resolved all React Hook ESLint warnings (0 errors, 0 warnings). | 🟢 Fixed | Phase 0 / Phase 1B |
| A16 | P2 | `package.json`, `logging_config.py`, `voice.py`, `App.jsx`, `test_logging.py` | Legacy names: `dr-susham-health-ai` (packages), `susham_health`/`dr_susham` (loggers), `Dr. Susham Biswas` (UI). Static password salt removed from source in Phase 1C and isolated to migration env `LEGACY_PBKDF2_SALT`. Default DB path `susham_health.db` preserved for compatibility. | 🟡 Partial | Phase 0 / Phase 1C |
| A17 | P1 | `App.jsx`, system prompts | Prompts impersonate physician. Force diagnosis after fixed rounds. UI claims clinical accuracy. | 🔴 Open | Phase 6 |

## A16 Preservation Notes

The following legacy identifiers were intentionally preserved for database compatibility:
- `backend/app/core/config.py`: Default DB path `susham_health.db` — rename with database file migration
- Note: Static password salt was completely removed from source code in Phase 1C and moved to external migration-only configuration (`LEGACY_PBKDF2_SALT`)

## Legend

- 🔴 Open — Not yet remediated
- 🟡 Partial — Partially addressed; remaining work documented
- 🟢 Fixed — Remediation committed and verified
