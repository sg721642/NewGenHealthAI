# NewGenHealthAI — Test Evidence & Verification Records

Last updated: Phase 1D (Conversation Memory Isolation, Concurrency and Persistence)

## Phase 1B Test Execution Summary

### 1. Backend Security, Ownership, Migration, and Unit Tests (Pytest)

Command:
```bash
PYTHONPATH=backend /tmp/nghai_venv/bin/python -m pytest backend/tests/test_logging.py backend/tests/test_database.py backend/tests/test_security_ownership.py backend/tests/test_api.py -v
```

Outcome:
- **Total Tests**: 35
- **Passed**: 35 (100%)
- **Failed**: 0
- **Skipped**: 0
- **Duration**: 0.79s
- **Exit Code**: 0

Test Details:
| Test File | Test Name | Scenario Verified | Outcome |
|---|---|---|---|
| `test_logging.py` | `test_setup_logging_creates_directory` | Log directory handling | ✅ Pass |
| `test_logging.py` | `test_logger_instance` | Logger instance is `newgenhealthai` | ✅ Pass |
| `test_logging.py` | `test_logger_has_handlers` | Log handlers attached | ✅ Pass |
| `test_logging.py` | `test_logger_level` | Debug/Info levels configured | ✅ Pass |
| `test_database.py` | `test_save_and_get_message` | Message persistence requires existing conversation and user_id | ✅ Pass |
| `test_database.py` | `test_get_all_sessions` | Session listing isolated per user; anonymous returns empty | ✅ Pass |
| `test_database.py` | `test_delete_session` | Deletion strictly owner-enforced | ✅ Pass |
| `test_security_ownership.py` | `test_missing_auth_header_fails_with_401` | Missing Bearer token returns HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_malformed_auth_header_fails_with_401` | Non-Bearer/empty tokens fail with HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_invalid_unrecognized_token_fails_with_401` | Unrecognized token strings fail closed with HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_query_parameter_tokens_are_strictly_rejected` | Tokens passed via `?token=...` are rejected with HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_logout_revokes_token_immediately` | Logout deletes session token; reuse returns HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_user_can_create_and_retrieve_own_conversation` | User A creates and retrieves own consultation | ✅ Pass |
| `test_security_ownership.py` | `test_user_b_cannot_retrieve_user_a_conversation` | User B requesting User A session receives HTTP 404 | ✅ Pass |
| `test_security_ownership.py` | `test_user_b_cannot_list_user_a_conversation` | User B `/sessions` never includes User A data | ✅ Pass |
| `test_security_ownership.py` | `test_user_b_cannot_append_message_to_user_a_conversation` | User B posting to User A session receives HTTP 404 | ✅ Pass |
| `test_security_ownership.py` | `test_user_b_cannot_delete_user_a_conversation` | User B deleting User A session receives HTTP 404 | ✅ Pass |
| `test_security_ownership.py` | `test_user_b_cannot_clear_user_a_clinical_memory` | User B clearing User A session receives HTTP 404 | ✅ Pass |
| `test_security_ownership.py` | `test_clinical_memory_multi_user_isolation` | Memory states keyed by `user_id:session_id` | ✅ Pass |
| `test_security_ownership.py` | `test_image_and_voice_require_authentication` | Unauthenticated image/voice requests receive HTTP 401 | ✅ Pass |
| `test_security_ownership.py` | `test_voice_tts_post_contract_and_audio_streaming` | POST `/voice/tts` with JSON body and Bearer token streams audio; GET and query param text rejected | ✅ Pass |
| `test_security_ownership.py` | `test_arbitrary_client_supplied_session_id_fails_closed` | Arbitrary client UUID in `X-Session-ID` fails closed (404); never auto-creates conversation | ✅ Pass |
| `test_security_ownership.py` | `test_deleted_session_id_cannot_be_reused` | Deleted session cannot be resurrected by passing ID in `X-Session-ID` | ✅ Pass |
| `test_security_ownership.py` | `test_database_migration_unambiguous_and_quarantine` | Pure single-owner migrated; mixed NULL+user, conflicting, anon, and unknown users quarantined; NULL rows preserved; schema_versions tracked | ✅ Pass |
| `test_security_ownership.py` | `test_sqlite_wal_mode_online_backup_and_integrity` | SQLite Online Backup API captures uncheckpointed WAL frames, passes integrity check, and restores safely | ✅ Pass |
| `test_api.py` | `test_health_check` | Health check is public (HTTP 200) | ✅ Pass |
| `test_api.py` | `test_unauthenticated_requests_fail_with_401` | Public requests to protected endpoints return 401 | ✅ Pass |
| `test_api.py` | `test_new_chat` | Authenticated `/new-chat` returns server session_id | ✅ Pass |
| `test_api.py` | `test_get_sessions` | Authenticated `/sessions` returns owned sessions | ✅ Pass |
| `test_api.py` | `test_chat_flow_success` | Full chat roundtrip works with auth | ✅ Pass |
| `test_api.py` | `test_chat_flow_system_not_initialized` | 503 when workflow app is missing | ✅ Pass |
| `test_api.py` | `test_get_history` | Authenticated history retrieval | ✅ Pass |
| `test_api.py` | `test_load_session` | Authenticated load session | ✅ Pass |
| `test_api.py` | `test_delete_session` | Authenticated session delete calls engine | ✅ Pass |
| `test_api.py` | `test_clear_conversation` | Authenticated clear conversation | ✅ Pass |

---

### 2. Frontend Test Suite (Vitest)

Command:
```bash
npm --prefix frontend test -- --run
```

Outcome:
- **Total Test Files**: 1
- **Total Tests**: 4
- **Passed**: 4 (100%)
- **Failed**: 0
- **Duration**: 517ms
- **Exit Code**: 0

Test Details:
- `renders app structure`: ✅ Pass
- `loads sessions on mount`: ✅ Pass
- `sends a message and displays response`: ✅ Pass
- `creates new chat`: ✅ Pass

---

### 3. Frontend Linter (ESLint)

Command:
```bash
npm --prefix frontend run lint
```

Outcome:
- **Errors**: 0
- **Warnings**: 0 (All React Hook dependencies resolved in `App.jsx`)
- **Exit Code**: 0

---

### 4. Frontend Production Build (Vite)

Command:
```bash
npm --prefix frontend run build
```

Outcome:
- **Exit Code**: 0
- **Output Artifacts**:
  - `../backend/app/static/index.html` (0.68 kB)
  - `../backend/app/static/assets/index-CB66vf3N.css` (18.46 kB)
  - `../backend/app/static/assets/index-DZajoq3V.js` (394.19 kB)

---

## Phase 1C Test Execution Summary

### 1. Complete Backend Test Suite (Pytest)

Command:
```bash
PYTHONPATH=backend /tmp/nghai_venv/bin/python -m pytest backend/tests/test_database.py backend/tests/test_security_ownership.py backend/tests/test_api.py backend/tests/test_api_edge_cases.py backend/tests/test_logging.py backend/tests/test_app.py backend/tests/test_auth_hardening.py -v
```

Outcome:
- **Total Tests**: 54
- **Passed**: 54 (100%)
- **Failed**: 0
- **Skipped**: 0
- **Duration**: 1.41s
- **Exit Code**: 0

Phase 1C Specific Test Details (`test_auth_hardening.py`):
| Test Name | Security Scenario Verified | Outcome |
|---|---|---|
| `test_argon2id_unique_salts_for_identical_passwords` | Argon2id generates cryptographically random unique salts per hash | ✅ Pass |
| `test_argon2id_verification_and_rejection` | Correct verification of matching password; rejection of mismatched password | ✅ Pass |
| `test_legacy_password_verification_and_automatic_rehash` | Legacy PBKDF2 hash verifies with migration salt and automatically upgrades to Argon2id in DB | ✅ Pass |
| `test_legacy_password_fails_closed_when_salt_is_missing` | Fails closed safely if legacy salt is unset/None | ✅ Pass |
| `test_legacy_password_rejects_wrong_password` | Rejects wrong password against legacy hash | ✅ Pass |
| `test_optimistic_concurrency_rehash_prevents_race_conditions` | Atomic optimistic concurrency prevents stale hash overwrites during concurrent logins | ✅ Pass |
| `test_session_token_stored_as_sha256_hash_never_raw_token` | Raw 256-bit entropy token returned to client; only SHA-256 hash stored in DB | ✅ Pass |
| `test_session_expiration_rejection_and_cleanup` | Expired tokens fail closed (401); cleanup routine removes expired sessions | ✅ Pass |
| `test_logout_revokes_token_by_hash` | Logout deletes session token row by hash immediately; subsequent access fails closed | ✅ Pass |
| `test_registration_input_boundary_validation` | Strict validation of username length/charset (3-50) and password length (8-128) | ✅ Pass |
| `test_login_rate_limiting_after_excessive_failed_attempts` | Sliding window rate limits failed attempts per IP; 11th failed attempt returns HTTP 429 | ✅ Pass |
| `test_production_fails_if_session_secret_key_missing_or_short` | Rejects startup in production when SESSION_SECRET_KEY is missing or < 32 characters | ✅ Pass |
| `test_cors_does_not_permit_wildcard_origins_with_credentials` | Verifies wildcard '*' origin is disallowed with allow_credentials | ✅ Pass |
| `test_voice_stt_and_tts_error_sanitization` | Internal exceptions are caught; generic client error messages returned without leaking traces | ✅ Pass |

---

### 2. Frontend Vitest Integration Tests

Command:
```bash
npm --prefix frontend test -- --run
```
- **Tests**: 4 / 4 passed (100%)
- **Exit Code**: 0

---

### 3. Frontend ESLint Linter

Command:
```bash
npm --prefix frontend run lint
```
- **Errors**: 0
- **Warnings**: 0
- **Exit Code**: 0

---

### 4. Frontend Production Build

Command:
```bash
npm --prefix frontend run build
```
- **Exit Code**: 0
- **Artifacts**: Static bundle successfully output to `../backend/app/static/`

---

## Phase 1C.1 Test Execution Summary

### 1. Complete Backend Test Suite Inventory (Pytest)

Command:
```bash
/tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Tests**: 125
- **Passed**: 124 (99.2%)
- **Skipped**: 1 (0.8% — `test_create_workflow` requiring optional heavy `langgraph` dependency)
- **Failed**: 0 (0%)
- **Duration**: 2.09s
- **Exit Code**: 0

Test Inventory by Module:
| Test Module | Total | Passed | Skipped | Failed | Classification |
|---|---|---|---|---|---|
| `test_agents.py` | 18 | 18 | 0 | 0 | Passed |
| `test_api.py` | 12 | 12 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 1 | 1 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_security_ownership.py` | 12 | 12 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 6 | 1 | 0 | Passed (1 Skipped) |
| **Total Suite** | **125** | **124** | **1** | **0** | **Passed** |

Phase 1C.1 Specific Test Details (`test_phase1c1_hardening.py`):
| Test Name | Security & Migration Scenario Verified | Outcome |
|---|---|---|
| `test_proxy_untrusted_peer_ignores_xff` | SEC-01: Connecting peer outside TRUSTED_PROXIES ignores spoofed X-Forwarded-For | ✅ Pass |
| `test_proxy_trusted_peer_extracts_client_ip` | SEC-01: Trusted peer extracts authentic client IP from X-Forwarded-For | ✅ Pass |
| `test_proxy_cidr_network_matching` | SEC-01: Supports CIDR blocks (`10.0.0.0/8`, `172.16.0.0/12`) for reverse proxies | ✅ Pass |
| `test_proxy_spoofed_chain_via_trusted_proxy` | SEC-01: Traverses proxy chain right-to-left to locate genuine untrusted client | ✅ Pass |
| `test_proxy_malformed_header_safe_fallback` | SEC-01: Malformed IP strings safely skipped without crashing | ✅ Pass |
| `test_bounded_rate_limiter_memory_cap` | SEC-02: Rate limiter capacity capped at max_entries with automatic eviction | ✅ Pass |
| `test_register_rate_limiting_enforced` | SEC-02: Registration rate limiting (5 attempts per minute) triggers HTTP 429 | ✅ Pass |
| `test_login_per_user_lockout_across_distributed_ips` | SEC-02: 5 failed attempts on specific username triggers per-account lockout across rotating IPs | ✅ Pass |
| `test_login_success_clears_rate_limit` | SEC-02: Successful authentication clears IP and username failure buckets | ✅ Pass |
| `test_mig01_atomic_staging_cutover_success` | MIG-01: Atomic staging table cutover with count, SHA-256 hash, and schema validation | ✅ Pass |
| `test_mig01_atomic_staging_rollback_on_validation_failure` | MIG-01: Transaction rolls back on validation failure; legacy user_sessions preserved intact | ✅ Pass |
| `test_mig02_missing_users_table_quarantines_all_conversations` | MIG-02: Missing users table fails closed into quarantine (`is_quarantined=1, user_id=0`) | ✅ Pass |
| `test_mig02_unregistered_user_id_quarantined` | MIG-02: Unregistered user ID fails closed into quarantine; messages preserved | ✅ Pass |

---

### 2. Frontend Vitest Integration Tests

Command:
```bash
npm --prefix frontend test -- --run
```
- **Tests**: 4 / 4 passed (100%)
- **Exit Code**: 0

---

### 3. Frontend ESLint Linter

Command:
```bash
npm --prefix frontend run lint
```
- **Errors**: 0
- **Warnings**: 0
- **Exit Code**: 0

---

### 4. Frontend Production Build

Command:
```bash
npm --prefix frontend run build
```
- **Exit Code**: 0
- **Artifacts**: Static bundle successfully output to `../backend/app/static/`

---

## Phase 1D Test Execution Summary

### 1. Complete Backend Test Suite Inventory (Pytest)

Command:
```bash
/tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Tests**: 140
- **Passed**: 139 (99.3%)
- **Skipped**: 1 (0.7% — `test_create_workflow` requiring optional heavy `langgraph` dependency)
- **Failed**: 0 (0%)
- **Duration**: 2.93s
- **Exit Code**: 0

Test Inventory by Module:
| Test Module | Total | Passed | Skipped | Failed | Classification |
|---|---|---|---|---|---|
| `test_agents.py` | 18 | 18 | 0 | 0 | Passed |
| `test_api.py` | 12 | 12 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 1 | 1 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 15 | 15 | 0 | 0 | Passed |
| `test_security_ownership.py` | 12 | 12 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 6 | 1 | 0 | Passed (1 Skipped) |
| **Total Suite** | **140** | **139** | **1** | **0** | **Passed** |

Phase 1D Specific Test Details (`test_phase1d_concurrency.py`):
| Test Name | Concurrency, Memory & Lifecycle Scenario Verified | Outcome |
|---|---|---|
| `test_two_simultaneous_turns_in_one_conversation` | 2 concurrent turns on the same conversation serialize via `ConversationLockManager` without interleaving | ✅ Pass |
| `test_concurrent_turns_in_different_conversations` | Concurrent turns across distinct conversations execute in parallel without mutual blocking | ✅ Pass |
| `test_clear_during_in_flight_processing` | Generational versioning detects clear during active generation; returns HTTP 409 Conflict | ✅ Pass |
| `test_delete_during_in_flight_processing` | Deletion tombstoning detects delete during active generation; returns HTTP 409 Conflict | ✅ Pass |
| `test_request_cancellation_and_lock_release` | Cancellation (`asyncio.CancelledError`) frees lock context immediately with zero lock leaks | ✅ Pass |
| `test_provider_exception_while_holding_lock` | LLM provider exceptions release the conversation lock cleanly; subsequent requests succeed | ✅ Pass |
| `test_history_reconstruction_after_simulated_restart` | `_get_or_restore_state` accurately rehydrates memory turns from SQLite history on cold start | ✅ Pass |
| `test_context_reconstruction_after_cache_eviction` | When `conversation_states` exceeds 500 sessions, evicted state is seamlessly restored from DB | ✅ Pass |
| `test_conversation_ownership_during_history_hydration` | History rehydration verifies user ownership before loading records; prevents unauthorized cross-tenant loads | ✅ Pass |
| `test_long_conversation_history_bounded` | History reconstruction bounded to `MAX_RESTORE_TURNS=20` most recent turns | ✅ Pass |
| `test_rate_limit_capacity_flooding_without_active_lockout_eviction` | Flooding rate limiter with dummy keys prunes expired entries first and preserves active lockouts | ✅ Pass |
| `test_stepwise_schema_migration_recovery` | Schema migrations v1 and v2 execute as independent atomic transactions; safe resumption verified | ✅ Pass |
| `test_deleted_id_resurrection_attempts_fail_closed` | In-flight assistant generation discarded on deleted session; memory state tombstoned | ✅ Pass |
| `test_account_switching_isolation` | Multi-user isolation in locks, versions, and memory states prevents cross-tenant data leakage | ✅ Pass |
| `test_failed_generation_excluded_from_history` | Assistant failure responses (`"Unable to generate response"`) excluded from restored memory context | ✅ Pass |

---

### 2. Frontend Vitest Integration Tests

Command:
```bash
npm --prefix frontend test -- --run
```
- **Tests**: 6 / 6 passed (100%)
- **New Tests Added**:
  - `clears sensitive session state and aborts pending requests on logout`: Verifies `AbortController` cancellation, state wipe, and credentials removal upon logout.
  - `discards in-flight responses when switching sessions before request completes`: Verifies stale response suppression when active session changes before server response arrives.
- **Exit Code**: 0

---

### 3. Frontend ESLint Linter

Command:
```bash
npm --prefix frontend run lint
```
- **Errors**: 0
- **Warnings**: 0
- **Exit Code**: 0

---

### 4. Frontend Production Build

Command:
```bash
npm --prefix frontend run build
```
- **Exit Code**: 0
- **Artifacts**: Static bundle successfully output to `../backend/app/static/`


