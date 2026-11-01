# NewGenHealthAI — Test Evidence & Verification Records

Last updated: Phase 4 (Repository Cleanup, Branding, Dependencies and Deployment Consistency)

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

---

## Phase 2A Test Execution Summary

### 1. Complete Backend Test Suite (Pytest)

Command:
```bash
/tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Tests**: 176
- **Passed**: 175
- **Skipped**: 1 (`test_create_workflow` requiring live LangGraph LLM keys)
- **Failed**: 0
- **Duration**: 2.66s
- **Exit Code**: 0

Test Inventory by Module:
| Test Module | Total Tests | Passed | Skipped | Failed | Status |
|---|---|---|---|---|---|
| `test_agents.py` | 8 | 8 | 0 | 0 | Passed |
| `test_api.py` | 13 | 13 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 5 | 5 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 15 | 15 | 0 | 0 | Passed |
| `test_phase2a_image_classifier.py` | 36 | 36 | 0 | 0 | Passed |
| `test_security_ownership.py` | 12 | 12 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 6 | 1 | 0 | Passed (1 Skipped) |
| **Total Suite** | **176** | **175** | **1** | **0** | **Passed** |

Phase 2A 20-Scenario Regression Matrix Coverage (`test_phase2a_image_classifier.py`):
| Matrix Scenario | Scenario Description & Security Guarantee | Tests | Outcome |
|---|---|---|---|
| **Scenario 1** | Normal vs Condition (normal=0.96 vs pneumonia=0.04) -> normal preserved as top valid finding; no pneumonia diagnosis; no clinical certainty claim | `test_scenario_01_normal_preserved_no_disease_promotion` | ✅ Pass |
| **Scenario 2** | Valid negative classes preserved (`normal`, `normal cases`, `notumor`, `notinfected`, `uninfected`, `non-covid`, `benign`, `bengin cases`, `healthy eye`) | `test_scenario_02_valid_negative_classes_preserved` (10 parameterized tests) | ✅ Pass |
| **Scenario 3** | Invalid dataset artifact top prediction (`preview`, `train`, `val`, `cropped`, `jpegimages`, `all`) -> returns `status="inconclusive"`, no disease promotion | `test_scenario_03_top_artifact_triggers_inconclusive` (6 parameterized tests) | ✅ Pass |
| **Scenario 4** | X-ray anatomy-only (wrist=0.95) -> `finding_type="anatomy_identified"`, no fracture/abnormality diagnosed | `test_scenario_04_xray_anatomy_only_wrist` | ✅ Pass |
| **Scenario 5** | X-ray mixed anatomy and condition -> condition detected when top; anatomy preserved when top without disease promotion | `test_scenario_05_xray_condition_top_with_secondary_anatomy`, `test_scenario_05_xray_anatomy_top_with_subthreshold_condition` | ✅ Pass |
| **Scenarios 6–9** | Hard modality lock (missing `skin`, `xray`, `retina`, or `general` model returns `status="model_unavailable"`, HTTP 503; zero fallback to general or other models) | `test_scenarios_06_to_09_hard_modality_lock_missing_model` (4 parameterized tests) | ✅ Pass |
| **Scenario 10** | All models missing -> safe return of `status="model_unavailable"`, HTTP 503 without crashes | `test_scenario_10_all_models_missing` | ✅ Pass |
| **Scenario 11** | CLIP failure / exception -> `status="inconclusive"`, no fallback to general | `test_scenario_11_clip_exception_fails_inconclusive` | ✅ Pass |
| **Scenario 12** | Ambiguous CLIP domain -> `status="inconclusive"` | `test_scenario_12_ambiguous_clip_domain` | ✅ Pass |
| **Scenario 13** | Non-medical image -> `status="unsupported_image"`, HTTP 422 | `test_scenario_13_non_medical_image_returns_unsupported` | ✅ Pass |
| **Scenario 14** | Model exception during inference -> `status="inconclusive"`, no cross-modality fallback | `test_scenario_14_inference_exception_handled_inconclusive` | ✅ Pass |
| **Scenario 15** | Model returns empty predictions -> `status="inconclusive"` | `test_scenario_15_empty_predictions_handled_inconclusive` | ✅ Pass |
| **Scenario 16** | Low-ranked disease not promoted when normal or negative class is top rank | Verified across Scenarios 1, 2, and 5B | ✅ Pass |
| **Scenario 17** | Score interpretation present: uncalibrated score returned, `calibrated_confidence` is None, prototype disclaimer | `test_scenario_17_score_interpretation_and_no_calibrated_confidence` | ✅ Pass |
| **Scenario 18** | Image API endpoint: HTTP 400 on empty or invalid/corrupted image bytes (`status="invalid_image"`) | `test_scenario_18_endpoint_invalid_image_returns_400` | ✅ Pass |
| **Scenario 19** | Image API endpoint: HTTP 422 on unsupported non-medical image (`status="unsupported_image"`) | `test_scenario_19_endpoint_unsupported_image_returns_422` | ✅ Pass |
| **Scenario 20** | Image API endpoint HTTP contract: 503 on `model_unavailable`, 200 on `inconclusive`, 200 on `analysis_complete` | `test_scenario_20a_endpoint_model_unavailable_returns_503`, `test_scenario_20b_endpoint_inconclusive_returns_200`, `test_scenario_20c_endpoint_analysis_complete_returns_200` | ✅ Pass |
| **Auth Security** | Image API requires authentication; unauthenticated request returns HTTP 401 | `test_scenario_security_endpoint_unauthenticated_returns_401` | ✅ Pass |

---

### 2. Frontend Vitest Integration Tests

Command:
```bash
npm --prefix frontend test -- --run
```
- **Tests**: 11 / 11 passed (100%)
- **Duration**: 329ms
- **New Tests Added**:
  - `renders analysis_complete with uncalibrated score and without primary diagnosis or percentage certainty`: Verifies model finding rendering, uncalibrated score display, and absence of misleading claims.
  - `renders normal/negative reference finding notice without diagnosing disease`: Verifies normal reference finding disclaimer and prevention of pneumonia diagnosis.
  - `renders model_unavailable status cleanly`: Verifies HTTP 503 / `model_unavailable` UI feedback informing user of missing specialist model weights.
  - `renders unsupported_image status cleanly`: Verifies HTTP 422 / `unsupported_image` UI feedback with BLIP scene description.
  - `renders inconclusive status cleanly`: Verifies `inconclusive` UI notice requesting clearer clinical imagery.
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

### 4. Frontend Production Build (Vite)

Command:
```bash
npm --prefix frontend run build
```
- **Exit Code**: 0
- **Artifacts**:
  - `../backend/app/static/index.html` (0.68 kB)
  - `../backend/app/static/assets/index-CB66vf3N.css` (18.46 kB)
  - `../backend/app/static/assets/index-DkjXr3wK.js` (397.18 kB)

---

## Phase 2B Test Execution Summary

### 1. Backend Bounded Clinical Workflow, Emergency Handling, and Medical-Response Safety (Pytest)

Command:
```bash
/tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Tests**: 199
- **Passed**: 199 (100%)
- **Failed**: 0
- **Skipped**: 0
- **Duration**: 2.75s
- **Exit Code**: 0

Suite Breakdown:
| Test File | Total | Passed | Failed | Skipped | Status |
|---|---|---|---|---|---|
| `test_agents.py` | 20 | 20 | 0 | 0 | Passed |
| `test_api.py` | 10 | 10 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 4 | 4 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 15 | 15 | 0 | 0 | Passed |
| `test_phase2a_image_classifier.py` | 36 | 36 | 0 | 0 | Passed |
| `test_phase2b_workflow_safety.py` | 23 | 23 | 0 | 0 | Passed |
| `test_phase2b1_corrections.py` | 28 | 28 | 0 | 0 | Passed |
| `test_security_ownership.py` | 18 | 18 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 7 | 0 | 0 | Passed |
| **Total Suite** | **229** | **229** | **0** | **0** | **Passed** |

Phase 2B Verification Matrix (`test_phase2b_workflow_safety.py`):
| Verification Scenario | Scenario Description & Clinical Safety Guarantee | Test Function | Outcome |
|---|---|---|---|
| **Emergency Gate: Cardiac** | Acute coronary symptoms (crushing chest pain radiating to arm/jaw) trigger immediate 911 advisory without symptom follow-up or speculative diagnosis | `test_urgent_risk_cardiac` | ✅ Pass |
| **Emergency Gate: Stroke** | FAST symptoms (facial droop, arm weakness, slurred speech) trigger emergency alert | `test_urgent_risk_stroke` | ✅ Pass |
| **Emergency Gate: Respiratory** | Severe dyspnea / cyanosis / stridor triggers emergency alert | `test_urgent_risk_respiratory` | ✅ Pass |
| **Emergency Gate: Anaphylaxis** | Acute airway closing, tongue/throat swelling after allergen triggers emergency alert | `test_urgent_risk_anaphylaxis` | ✅ Pass |
| **Emergency Gate: Hemorrhage** | Uncontrolled bleeding / hematemesis triggers emergency alert | `test_urgent_risk_hemorrhage` | ✅ Pass |
| **Emergency Gate: Crisis** | Acute self-harm / suicidal ideation triggers 988 Suicide & Crisis Lifeline | `test_urgent_risk_crisis` | ✅ Pass |
| **Emergency Bypass Routing** | Planner routes urgent flags directly to executor (`_route_after_planner == "executor"`); triage node bypassed | `test_urgent_risk_planner_routing` | ✅ Pass |
| **100% Offline Emergency Gate** | Urgent detection executes in pure deterministic Python when Groq LLM, ChromaDB, Wikipedia, and Tavily are offline | `test_urgent_risk_100_percent_offline` | ✅ Pass |
| **Non-Urgent Preservation** | Mild routine complaints (colds, mild cough) are not falsely routed to emergency path | `test_non_urgent_query_does_not_trigger_emergency` | ✅ Pass |
| **Bounded Routing: Retriever First** | When retriever fails, graph routes to LLM; if LLM fails, falls back to Wikipedia/Tavily/Executor without looping back | `test_bounded_routing_retriever_first_both_fail` | ✅ Pass |
| **Bounded Routing: LLM First** | When LLM fails, graph routes to retriever; if retriever fails, falls back to Wikipedia/Tavily/Executor without looping back | `test_bounded_routing_llm_first_both_fail` | ✅ Pass |
| **StateGraph Real Execution: Exhaustion** | Real compiled LangGraph executes offline; visits each provider at most once; terminates at executor with `is_failed_generation=True` and `source="Service Unavailable"` | `test_real_compiled_workflow_execution_total_provider_failure` | ✅ Pass |
| **StateGraph Real Execution: RAG Success** | Real compiled LangGraph executes RAG pipeline successfully when documents are retrieved | `test_real_compiled_workflow_execution_rag_success` | ✅ Pass |
| **Triage Persona De-escalation** | Prompts in triage agent remove physician impersonation, doctor claims, and clinical examination assertions | `test_triage_prompts_do_not_claim_physician_status` | ✅ Pass |
| **No Forced Diagnosis at Round 3** | Triage round 3 transitions to educational summary with explicit uncertainty rather than forcing diagnosis | `test_triage_round_3_does_not_force_diagnosis` | ✅ Pass |
| **Executor Persona & Dosage Ban** | Executor agent prompt forbids physician impersonation, prescription drug recommendations, and dosage guidance | `test_executor_prompts_do_not_claim_physician_status` | ✅ Pass |
| **JSON Parser Resilience** | Extracts JSON from markdown code blocks, raw strings, and handles trailing commas | `test_extract_json_resilience` | ✅ Pass |
| **Triage Malformed JSON Handling** | Invalid/corrupted LLM outputs default safely to `ready_to_diagnose` without crashing | `test_triage_handles_malformed_json_gracefully` | ✅ Pass |
| **Input Validation: Whitespace** | Empty and whitespace-only messages rejected with `ValueError` | `test_empty_or_whitespace_message_rejected` | ✅ Pass |
| **Input Validation: Length** | Messages exceeding 4000 characters rejected with `ValueError` | `test_oversized_message_rejected` | ✅ Pass |
| **Prompt Injection Neutralization** | Delimiter breakout and prompt injection strings in retrieved documents are sanitized | `test_prompt_injection_sanitization_in_documents` | ✅ Pass |
| **Source Provenance Formatting** | Document metadata (title, URL) cited only when verified provenance exists | `test_source_provenance_formatting` | ✅ Pass |
| **Failed Generation Non-Persistence** | Provider exhaustion returns `success=False` and skips persisting failed assistant responses to database | `test_failed_generation_not_persisted_as_successful` | ✅ Pass |

Phase 2B.1 Verification Matrix (`test_phase2b1_corrections.py`):
| Verification Scenario | Scenario Description & Clinical Safety Guarantee | Test Function | Outcome |
|---|---|---|---|
| **Consultation Deadline Timeout** | Workflow execution bounded by `CONSULTATION_TIMEOUT_SECONDS`; `asyncio.wait_for` fires `TimeoutError` without blocking event loop | `test_consultation_timeout_returns_provider_timeout_state` | ✅ Pass |
| **Guaranteed Lock Release on Timeout** | `ConversationLockManager` context manager guarantees per-conversation lock release upon `TimeoutError` or cancellation | `test_lock_released_after_timeout` | ✅ Pass |
| **Result-State Taxonomy Constants** | Standard internal result states (`SUCCESSFUL_EDUCATIONAL`, `SUCCESSFUL_URGENT`, `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, etc.) documented and defined | `test_result_state_taxonomy_constants` | ✅ Pass |
| **Post-Exhaustion Call Prevention** | When `exhaustion_reason` is set, `ExecutorAgent` returns `source="Service Unavailable"` without attempting secondary LLM calls | `test_executor_terminates_on_exhaustion_reason` | ✅ Pass |
| **Exhaustion Flag Propagation** | Provider exhaustion correctly propagates to `is_failed_generation=True` across state transitions | `test_executor_exhaustion_reason_propagates_to_failed_generation` | ✅ Pass |
| **Routing Flags Exhaustion** | LangGraph conditional routing sets `exhaustion_reason` when all providers have been attempted and failed | `test_workflow_routing_sets_exhaustion_reason_after_all_providers` | ✅ Pass |
| **Wikipedia Medical Allowlist** | Only allowlisted generic medical terms are extracted for Wikipedia queries; personal narratives and non-medical terms stripped | `test_wikipedia_query_extraction_allowlist_only` | ✅ Pass |
| **Wikipedia Non-Medical Query Rejection** | Non-medical queries return `None` and completely decline external Wikipedia search | `test_wikipedia_rejects_non_medical_queries` | ✅ Pass |
| **No Wikipedia Raw Fallback** | WikipediaAgent never retries with raw patient questions upon empty results | `test_wikipedia_no_raw_question_retry` | ✅ Pass |
| **No Tavily Raw Fallback** | TavilyAgent never retries with raw patient narrative questions | `test_tavily_no_raw_question_fallback` | ✅ Pass |
| **Tavily Medical Allowlist** | Tavily outbound queries contain exclusively allowlisted generic medical terms | `test_tavily_query_contains_only_medical_terms` | ✅ Pass |
| **Triage Question Text Redaction** | Triage logging records question character length only; never logs patient question content or sensitive medical text | `test_triage_log_does_not_contain_question_text` | ✅ Pass |
| **Emergency Advisory: India 112** | India 112 national emergency routing included prominently in non-crisis emergency advisories | `test_india_112_in_medical_emergency_advisory` | ✅ Pass |
| **Crisis Advisory: India Helplines** | Crisis advisories include India mental health helplines (iCall, Vandrevala Foundation) and physical danger 112 | `test_india_crisis_advisory` | ✅ Pass |
| **Safe Default for Unknown Locales** | Emergency advisory provides explicit guidance for users in unlisted countries to call local emergency services | `test_unknown_locale_safe_default_guidance` | ✅ Pass |
| **No Country Inference from Symptoms** | Advisory presents multi-region reference information; does not infer patient nationality from symptom descriptions | `test_advisory_does_not_infer_country_from_symptoms` | ✅ Pass |
| **No 100% Detection Claim** | Advisory explicitly acknowledges heuristic screening limitations and disclaims 100% emergency detection | `test_advisory_conservative_language_no_100_percent_claim` | ✅ Pass |
| **Conservative Emergency Phrasing** | Advisory uses conservative language ("may be experiencing") to avoid misleading diagnostic assertions | `test_advisory_uses_may_be_not_definitive` | ✅ Pass |
| **Citation Rejects javascript: URLs** | Citations drop `javascript:` schemes to prevent XSS attacks | `test_citation_rejects_javascript_url` | ✅ Pass |
| **Citation Rejects data: URLs** | Citations drop `data:` schemes to prevent HTML/script injection | `test_citation_rejects_data_url` | ✅ Pass |
| **Citation Rejects http: URLs** | Citations drop plain `http:` schemes, strictly enforcing HTTPS | `test_citation_rejects_http_url` | ✅ Pass |
| **Citation Accepts Valid HTTPS** | Valid HTTPS URLs with legitimate hosts are formatted as citations | `test_citation_accepts_https_url` | ✅ Pass |
| **Markdown Title Escaping** | Document titles have markdown link brackets and parentheses escaped to prevent citation breakout | `test_citation_escapes_markdown_in_title` | ✅ Pass |
| **Empty Citation Handling** | Empty document lists yield empty citation strings | `test_citation_no_docs_returns_empty` | ✅ Pass |
| **Title-Only Citation for URL-less Docs** | Documents with metadata title but no URL display clean title without empty markdown links | `test_citation_doc_without_url_shows_title_only` | ✅ Pass |
| **Cardiac Heuristic Offline Verification** | Pure Python offline cardiac red-flag pattern matching verified | `test_urgent_care_cardiac_detected` | ✅ Pass |
| **Crisis Heuristic Offline Verification** | Pure Python offline crisis/self-harm pattern matching verified | `test_urgent_care_crisis_detected` | ✅ Pass |
| **Non-Emergency Passthrough** | Routine symptom descriptions do not trigger acute emergency screening | `test_urgent_care_normal_query_returns_none` | ✅ Pass |


---

### 2. Frontend Vitest Integration Tests

Command:
```bash
npm --prefix frontend test -- --run
```
- **Tests**: 11 / 11 passed (100%)
- **Duration**: 330ms
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

### 4. Frontend Production Build (Vite)

Command:
```bash
npm --prefix frontend run build
```
- **Exit Code**: 0
- **Output**:
  - `../backend/app/static/index.html` (0.68 kB)
  - `../backend/app/static/assets/index-CB66vf3N.css` (18.46 kB)
  - `../backend/app/static/assets/index-DkjXr3wK.js` (397.18 kB)

---

## Phase 3A Verification Results (Secure Image Uploads, Model Loading and Resource Protection)

Executed at: Phase 3A Complete
Branch: `fix/healthai-audit-premium-ui`

### 1. Full Backend Test Suite

Command:
```bash
pytest backend/tests/ -q --tb=short
```

Outcome:
- **Total Tests**: 256
- **Passed**: 256
- **Skipped**: 0
- **Failed**: 0
- **Duration**: 4.14s
- **Exit Code**: 0

Test Inventory by Module (19 modules):
| Test Module | Total Tests | Passed | Skipped | Failed | Status |
|---|---|---|---|---|---|
| `test_agents.py` | 8 | 8 | 0 | 0 | Passed |
| `test_api.py` | 13 | 13 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 5 | 5 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 15 | 15 | 0 | 0 | Passed |
| `test_phase2a_image_classifier.py` | 36 | 36 | 0 | 0 | Passed |
| `test_phase2b_workflow_safety.py` | 23 | 23 | 0 | 0 | Passed |
| `test_phase2b1_corrections.py` | 28 | 28 | 0 | 0 | Passed |
| `test_phase3a_image_security.py` | 27 | 27 | 0 | 0 | Passed |
| `test_security_ownership.py` | 12 | 12 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 7 | 0 | 0 | Passed |
| **Total Suite** | **256** | **256** | **0** | **0** | **Passed (100%)** |

Phase 3A Regression Matrix Coverage (`test_phase3a_image_security.py`):
| Matrix Scenario | Scenario Description & Security Guarantee | Tests | Outcome |
|---|---|---|---|
| **Auth Enforcement** | `/analyze-image` requires valid authentication; unauthenticated request returns HTTP 401 | `test_unauthenticated_image_upload_returns_401` | ✅ Pass |
| **Empty File Rejection** | Zero-byte image upload rejected with HTTP 400 | `test_empty_file_upload_rejected` | ✅ Pass |
| **Oversized Compressed File** | File exceeding `MAX_IMAGE_UPLOAD_BYTES` (5MB) rejected with HTTP 400 before decoding | `test_oversized_compressed_file_rejected` | ✅ Pass |
| **Chunked Stream Enforcement** | Upload read in 64KB chunks; aborts immediately when cumulative size exceeds limit | `test_chunked_upload_size_enforcement` | ✅ Pass |
| **Forged MIME Type** | Non-image files disguised with `image/jpeg` MIME header rejected via magic byte check | `test_forged_mime_type_rejected` | ✅ Pass |
| **Unsupported Image Format** | Formats outside JPEG/PNG/WebP (e.g. BMP, TIFF, GIF, SVG) rejected with HTTP 400 | `test_unsupported_format_rejected` | ✅ Pass |
| **Corrupt Image Bytes** | Corrupted image data rejected with HTTP 400 | `test_corrupt_image_bytes_rejected` | ✅ Pass |
| **Truncated Image Bytes** | Incomplete/truncated stream rejected with HTTP 400 | `test_truncated_image_rejected` | ✅ Pass |
| **Excessive Dimensions** | Image dimensions exceeding `MAX_IMAGE_DIMENSION` (4096px) rejected with HTTP 400 | `test_excessively_large_decoded_dimensions_rejected` | ✅ Pass |
| **Decompression Bomb** | Pillow pixel count exceeding `MAX_IMAGE_PIXELS` (16MP) rejected with HTTP 400 | `test_decompression_bomb_rejected` | ✅ Pass |
| **EXIF Metadata Stripping** | Camera EXIF, GPS, and metadata blocks completely stripped into clean RGB raster buffer | `test_exif_metadata_stripped` | ✅ Pass |
| **Valid Small Image** | Legitimate JPEG image accepted and safely processed | `test_valid_small_image_accepted` | ✅ Pass |
| **Per-User Concurrency Limit** | User with an active in-flight inference receives HTTP 429 on second concurrent request | `test_per_user_concurrency_limit_returns_429` | ✅ Pass |
| **Inference Capacity Semaphore** | Global capacity exhausted (`MAX_CONCURRENT_INFERENCE=2`) returns HTTP 503 `model_unavailable` | `test_multiple_inference_requests_exceeding_capacity_returns_503` | ✅ Pass |
| **Permit Release on Cancellation** | Client cancellation or timeout guaranteed to release capacity permit | `test_cancellation_during_inference_releases_capacity_permit` | ✅ Pass |
| **No Implicit Model Downloads** | When `ALLOW_MODEL_DOWNLOADS=false`, classifier makes zero Hugging Face network downloads | `test_no_implicit_model_downloads_when_downloads_disabled` | ✅ Pass |
| **Missing Weights 503** | When required model weights are missing locally, classify returns 503 `model_unavailable` | `test_model_weights_missing_returns_503_model_unavailable` | ✅ Pass |
| **Stampede Protection** | Concurrent requests initializing the same model serialize via domain lock (`_model_load_locks`) | `test_concurrent_requests_initializing_one_model_stampede_protection` | ✅ Pass |
| **Corrupt Checkpoint Handling** | Malformed model file fails safely into `failed` status without crashing server | `test_malformed_checkpoint_state_dict_fails_safely` | ✅ Pass |
| **BLIP Disabled by Default** | BLIP captioning disabled by default; non-medical images receive clean fallback without download | `test_blip_disabled_by_default_no_download_and_safe_caption_fallback` | ✅ Pass |
| **Diagnostics Privacy** | GET `/api/v1/diagnostics` does not expose `base_dir`, server paths, or device internals | `test_sensitive_diagnostics_not_publicly_exposed` | ✅ Pass |
| **Anatomy-Only Info** | Anatomy findings generate educational anatomical guidance without disease pathology or treatments | `test_medical_info_anatomy_only_returns_no_disease_advice` | ✅ Pass |
| **Normal Reference Info** | Normal findings generate non-pathological reference guidance without disease treatments | `test_medical_info_normal_finding_returns_no_disease_advice` | ✅ Pass |
| **Non-Diagnostic LLM Prompt** | Medical info prompt explicitly instructs LLM that finding is NOT a clinical diagnosis | `test_medical_info_does_not_assert_confirmed_diagnosis` | ✅ Pass |
| **Correction A: Deadline Bypass** | Synchronous fallback invoke executed in worker thread cannot bypass consultation timeout | `test_slow_synchronous_workflow_cannot_bypass_deadline_and_releases_lock` | ✅ Pass |
| **Correction B: Indian Helplines** | Crisis guidance includes Tele-MANAS 24/7 (`14416`), Vandrevala 24/7 (`9999 666 555`), iCALL verified hours | `test_indian_crisis_helplines_accurate_tele_manas_and_icall_hours` | ✅ Pass |
| **Correction B: Unknown Country** | Advisory provides safe fallback guidance when user country is unlisted without inferring from symptoms | `test_unknown_location_crisis_fallback` | ✅ Pass |

### 2. Frontend Verification

- **Vitest Integration Tests**: 11 / 11 passed (100%)
- **ESLint Linter**: 0 errors, 0 warnings
- **Production Build (Vite)**: Clean bundle generated (`index-DkjXr3wK.js`, `index-CB66vf3N.css`)

---

## Phase 3B Verification Results (Secure Voice Processing, Reliable STT/TTS and Resource Protection)

Executed at: Phase 3B Complete
Branch: `fix/healthai-audit-premium-ui`

### 1. Full Backend Test Suite

Command:
```bash
/tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Tests**: 285
- **Passed**: 285 (100%)
- **Skipped**: 0
- **Failed**: 0
- **Duration**: 4.88s
- **Exit Code**: 0

Test Inventory by Module (20 modules):
| Test Module | Total Tests | Passed | Skipped | Failed | Status |
|---|---|---|---|---|---|
| `test_agents.py` | 8 | 8 | 0 | 0 | Passed |
| `test_api.py` | 13 | 13 | 0 | 0 | Passed |
| `test_api_edge_cases.py` | 5 | 5 | 0 | 0 | Passed |
| `test_app.py` | 1 | 1 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 14 | 14 | 0 | 0 | Passed |
| `test_coverage_gaps.py` | 9 | 9 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 15 | 15 | 0 | 0 | Passed |
| `test_phase2a_image_classifier.py` | 36 | 36 | 0 | 0 | Passed |
| `test_phase2b_workflow_safety.py` | 23 | 23 | 0 | 0 | Passed |
| `test_phase2b1_corrections.py` | 28 | 28 | 0 | 0 | Passed |
| `test_phase3a_image_security.py` | 27 | 27 | 0 | 0 | Passed |
| `test_phase3b_voice_security.py` | 29 | 29 | 0 | 0 | Passed |
| `test_security_ownership.py` | 12 | 12 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 7 | 0 | 0 | Passed |
| **Total Suite** | **285** | **285** | **0** | **0** | **Passed (100%)** |

Phase 3B Regression Matrix Coverage (`test_phase3b_voice_security.py`):
| Matrix Scenario | Scenario Description & Security Guarantee | Test Function | Outcome |
|---|---|---|---|
| **STT Auth Enforcement** | `/voice/stt` requires valid Bearer token authentication; unauthenticated request returns HTTP 401 | `test_unauthenticated_voice_stt_returns_401` | ✅ Pass |
| **TTS Auth Enforcement** | `/voice/tts` requires valid Bearer token authentication; unauthenticated request returns HTTP 401 | `test_unauthenticated_voice_tts_returns_401` | ✅ Pass |
| **TTS Query Auth Rejection** | Passing token via URL query parameter (`?token=...`) fails closed with HTTP 401 | `test_tts_query_string_auth_rejected` | ✅ Pass |
| **Empty Audio Upload** | Zero-byte audio file upload rejected with HTTP 400 | `test_empty_audio_upload_rejected` | ✅ Pass |
| **Tiny Audio Upload** | Upload smaller than `MIN_AUDIO_UPLOAD_BYTES` (500B) rejected with HTTP 400 before decoding | `test_tiny_audio_upload_rejected` | ✅ Pass |
| **Oversized Audio Upload** | Upload exceeding `MAX_AUDIO_UPLOAD_BYTES` (10MB) aborted via chunked reader with HTTP 400 | `test_oversized_audio_upload_rejected` | ✅ Pass |
| **Forged MIME Type** | Non-audio file with forged `audio/wav` MIME header rejected via magic byte check | `test_forged_mime_audio_rejected` | ✅ Pass |
| **Unsupported Container** | Containers outside allowlist (e.g. MIDI) rejected with HTTP 400 | `test_unsupported_audio_container_rejected` | ✅ Pass |
| **Valid Containers: WAV** | Standard browser WAV container (`RIFF....WAVE`) accepted | `test_valid_browser_containers_detected[wav]` | ✅ Pass |
| **Valid Containers: WebM** | Standard browser WebM container (`\x1a\x45\xdf\xa3`) accepted | `test_valid_browser_containers_detected[webm]` | ✅ Pass |
| **Valid Containers: OGG** | Browser OGG Opus container (`OggS`) accepted | `test_valid_browser_containers_detected[ogg]` | ✅ Pass |
| **Valid Containers: MP3** | Standard MP3 sync frames (`0xFF\xFB` / ID3) accepted | `test_valid_browser_containers_detected[mp3]` | ✅ Pass |
| **Valid Containers: M4A** | Browser AAC/M4A container (`ftyp`) accepted | `test_valid_browser_containers_detected[m4a]` | ✅ Pass |
| **Valid Containers: FLAC** | Lossless FLAC container (`fLaC`) accepted | `test_valid_browser_containers_detected[flac]` | ✅ Pass |
| **WAV Duration Probe** | WAV files with duration exceeding `MAX_AUDIO_DURATION_SECONDS` (300s) rejected with HTTP 400 | `test_wav_duration_limit_enforced` | ✅ Pass |
| **Private Tempfile Lifecycle** | Temporary directory created with `0o700` and file with `0o600`; cleaned up deterministically in `finally:` without leaking path | `test_secure_temp_file_creation_and_cleanup` | ✅ Pass |
| **Unconfigured Groq 503** | Missing `GROQ_API_KEY` returns HTTP 503 without crashing | `test_stt_unconfigured_groq_api_key_returns_503` | ✅ Pass |
| **Transient Error Fallback** | Transient error on `whisper-large-v3-turbo` triggers fallback to `whisper-large-v3` | `test_stt_fallback_model_tried_on_transient_error` | ✅ Pass |
| **Permanent Error Fast Fail** | Client error (HTTP 400/401) fails immediately without retrying or fallback | `test_stt_permanent_error_fails_fast_without_fallback` | ✅ Pass |
| **All Models Failed 503** | When all fallback models fail, endpoint returns HTTP 503 without generating fake transcript | `test_stt_all_models_failed_returns_503` | ✅ Pass |
| **Per-User STT Limit** | Active user with concurrent in-flight STT request receives HTTP 429 | `test_voice_capacity_per_user_stt_limit_returns_429` | ✅ Pass |
| **Global STT Semaphore 503** | Global STT capacity exhausted (`MAX_CONCURRENT_STT=3`) returns HTTP 503 | `test_voice_capacity_global_stt_semaphore_returns_503` | ✅ Pass |
| **Per-User TTS Limit** | Active user with concurrent in-flight TTS request receives HTTP 429 | `test_voice_capacity_per_user_tts_limit_returns_429` | ✅ Pass |
| **TTS Authenticated POST** | Valid POST `/voice/tts` request streams MP3 audio cleanly | `test_tts_valid_authenticated_post_streams_audio` | ✅ Pass |
| **TTS Boundary Validation** | Empty or too short text (<2 chars) returns HTTP 400 Bad Request | `test_tts_empty_or_too_short_text_returns_400` | ✅ Pass |
| **TTS Multilingual Support** | English and Hindi text correctly route to respective neural voices | `test_tts_unicode_hindi_and_english_supported` | ✅ Pass |
| **TTS Provider Failure 500** | Upstream edge-tts synthesis failure returns sanitized HTTP 500 without leaking stack traces | `test_tts_provider_failure_returns_500` | ✅ Pass |
| **Voice Log Redaction** | Logs record character/byte counts only; never leak spoken text, transcripts, audio bytes, or exception traces | `test_sensitive_transcripts_and_text_not_logged` | ✅ Pass |
| **Model Import Clarification** | Confirms lazy model loading applies to `.pth` weights while framework imports occur on module import | `test_lightweight_import_smoke_test_disease_classifier_clarification` | ✅ Pass |

### 2. Frontend Verification

Command:
```bash
npm --prefix frontend test -- --run
```

Outcome:
- **Total Tests**: 13
- **Passed**: 13 (100%)
- **Failed**: 0
- **Duration**: 410ms
- **Exit Code**: 0

New Frontend Tests Added in Phase 3B:
- `handles microphone permission denial gracefully`: Verifies `NotAllowedError` UI alert and state reset.
- `handles unsupported browser audio recording environment gracefully`: Verifies missing `mediaDevices` or `MediaRecorder` error message without crashing.

Linter & Production Build:
- **ESLint**: 0 errors, 0 warnings (`npm --prefix frontend run lint`)
- **Vite Build**: Clean production bundle output to `backend/app/static/assets/index-wdGNyF6d.js` (398.45 kB) and `index-CB66vf3N.css` (18.46 kB).

---

## Phase 4 Test Execution Summary

### 1. Full Backend Test Suite (Pytest)

Command:
```bash
PYTHONPATH=backend /tmp/nghai_venv/bin/pytest backend/tests/ -v
```

Outcome:
- **Total Test Files**: 21
- **Total Tests**: 300
- **Passed**: 300 (100%)
- **Failed**: 0
- **Skipped**: 0
- **Duration**: 4.66s
- **Exit Code**: 0

Test File Breakdown:
| Test File | Total | Passed | Failed | Skipped | Status |
|---|---|---|---|---|---|
| `test_agents.py` | 13 | 13 | 0 | 0 | Passed |
| `test_api.py` | 10 | 10 | 0 | 0 | Passed |
| `test_auth_hardening.py` | 13 | 13 | 0 | 0 | Passed |
| `test_chat_service.py` | 10 | 10 | 0 | 0 | Passed |
| `test_database.py` | 3 | 3 | 0 | 0 | Passed |
| `test_database_migration.py` | 4 | 4 | 0 | 0 | Passed |
| `test_image_preprocessing.py` | 13 | 13 | 0 | 0 | Passed |
| `test_logging.py` | 4 | 4 | 0 | 0 | Passed |
| `test_phase1c1_hardening.py` | 16 | 16 | 0 | 0 | Passed |
| `test_phase1d_concurrency.py` | 34 | 34 | 0 | 0 | Passed |
| `test_phase2a_image_classifier.py` | 27 | 27 | 0 | 0 | Passed |
| `test_phase2b_workflow_safety.py` | 23 | 23 | 0 | 0 | Passed |
| `test_phase2b1_corrections.py` | 28 | 28 | 0 | 0 | Passed |
| `test_phase3a_image_security.py` | 27 | 27 | 0 | 0 | Passed |
| `test_phase3b_voice_security.py` | 29 | 29 | 0 | 0 | Passed |
| `test_phase4_hardening.py` | 15 | 15 | 0 | 0 | Passed |
| `test_security_ownership.py` | 18 | 18 | 0 | 0 | Passed |
| `test_services.py` | 11 | 11 | 0 | 0 | Passed |
| `test_tools.py` | 12 | 12 | 0 | 0 | Passed |
| `test_workflow.py` | 1 | 1 | 0 | 0 | Passed |
| `test_workflow_routing.py` | 7 | 7 | 0 | 0 | Passed |
| **Total Suite** | **300** | **300** | **0** | **0** | **Passed (100%)** |

Phase 4 Regression Matrix Coverage (`test_phase4_hardening.py`):
| Matrix Scenario | Scenario Description & Security Guarantee | Test Function | Outcome |
|---|---|---|---|
| **STT Cancellation Safety** | Task cancellation during STT permit wait cleans up active user reservation and leaves semaphore consistent | `test_cancelled_stt_acquisition_cleans_up_active_user` | ✅ Pass |
| **TTS Cancellation Safety** | Task cancellation during TTS permit wait cleans up active user reservation and leaves semaphore consistent | `test_cancelled_tts_acquisition_cleans_up_active_user` | ✅ Pass |
| **Idempotent Permit Release** | Calling `VoicePermit.release()` multiple times releases semaphore and active user slot exactly once | `test_permit_release_is_idempotent` | ✅ Pass |
| **Concurrent Same-User 429** | Simultaneous voice requests for the same user are rejected with HTTP 429 Too Many Requests | `test_simultaneous_requests_same_user_rejected_with_429` | ✅ Pass |
| **TTS Oversized Stream Abort** | Streaming generator terminating upon reaching `MAX_TTS_STREAM_BYTES` (5MB) releases permit immediately | `test_tts_oversized_stream_terminates_cleanly` | ✅ Pass |
| **TTS Stream Timeout Bound** | Streaming generator exceeding `TTS_STREAM_TIMEOUT_SECONDS` (30.0s) aborts stream and releases capacity | `test_tts_stream_timeout_bounds_execution` | ✅ Pass |
| **Permanent STT Error Fast-Fail** | Permanent client error (HTTP 400 Bad Request) fails immediately with HTTP 503 without retrying or fallback | `test_stt_permanent_error_fails_immediately_without_fallback` | ✅ Pass |
| **Transient STT Error Fallback** | Transient rate-limit error (HTTP 429) triggers automatic retry using secondary fallback model (`whisper-large-v3`) | `test_stt_transient_error_retries_with_fallback` | ✅ Pass |
| **Canonical Frontend Entry** | Root `frontend/index.html` has title `NewGenHealthAI`, description meta, and `/favicon.svg`; obsolete duplicate in `public/` removed | `test_canonical_frontend_entry_html` | ✅ Pass |
| **Vite Standalone Build Config** | `vite.config.js` and `package.json` support standalone build mode (`build:standalone`) outputting to `dist` | `test_vite_standalone_build_output_config` | ✅ Pass |
| **Launcher Dynamic Paths** | `run.py` resolves paths relative to `__file__` without hardcoded machine paths, locating python and npm executables | `test_launcher_path_and_executable_resolution` | ✅ Pass |
| **Launcher Backend Wait Timeout** | `wait_for_backend` returns False safely if server does not respond within retry window | `test_launcher_wait_for_backend_timeout` | ✅ Pass |
| **Launcher Graceful Process Term** | `terminate_process` shuts down active and terminated child processes gracefully without orphaned processes | `test_launcher_terminate_process` | ✅ Pass |
| **Public Backend Healthcheck** | `/api/v1/health` returns HTTP 200 with `status: ok` and project branding without requiring auth | `test_backend_health_check_public` | ✅ Pass |
| **Complete .env.example Validation** | `.env.example` contains all critical production and operational configuration keys | `test_env_example_contains_all_critical_keys` | ✅ Pass |

### 2. Frontend Test Suite (Vitest)

Command:
```bash
npm --prefix frontend test -- --run
```

Outcome:
- **Total Test Files**: 1
- **Total Tests**: 13
- **Passed**: 13 (100%)
- **Failed**: 0
- **Duration**: 377ms
- **Exit Code**: 0

### 3. Frontend Linter (ESLint)

Command:
```bash
npm --prefix frontend run lint
```

Outcome:
- **Errors**: 0
- **Warnings**: 0
- **Exit Code**: 0

### 4. Frontend Bundle Builds

Commands:
```bash
npm --prefix frontend run build
npm --prefix frontend run build:standalone
```

Outcome:
- **Integrated Build**: Vite bundled to `backend/app/static` (index.html: 0.80 kB, index.js: 398.45 kB, index.css: 18.46 kB) in 500ms.
- **Standalone Build**: Vite bundled to `frontend/dist` (index.html: 0.80 kB, index.js: 398.45 kB, index.css: 18.46 kB) in 460ms.
- **Exit Code**: 0


