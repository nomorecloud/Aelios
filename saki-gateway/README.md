# Aelios Saki Gateway (Sanitized OSS Build)

This is a sanitized open-source version of the Python gateway used to power multi-channel chat, memory, reminders, web/image tools, and channel integrations.

## Included
- Python gateway runtime
- Feishu / QQBot channel integrations
- Memory store, runtime store, reminder scheduler
- Search / fetch / image-analysis tool plumbing

## Excluded from this OSS build
- Personal memories, conversation logs, profiles
- API keys, app tokens, webhook secrets
- Private PM2 / deployment specifics

## Quick start
1. Create a virtualenv
2. Install from `pyproject.toml`
3. Copy `data/config.example.json` to `data/config.json`
4. Fill your own provider and channel credentials
5. Run `python -m saki_gateway`

## Notes
This repository is intentionally sanitized for open-source release.

## Memory prompt flow
The runtime reply path now uses a cache-stable prompt order:
1. base persona/system prompt
2. fixed important memories (`importance = 1`)
3. today log
4. recent session context
5. latest user message
6. late-bound supplemental memory from the action runtime

The action runtime no longer relies on `search_memory` during normal replies. Instead, the gateway precomputes a candidate pool from non-fixed long-term memories plus today/yesterday logs, and the action runtime selects only concise missing details worth appending at the end.


## Short-term memory files (Phase 4 slice 1)
`data/core_profile.md` now renders in structured sections:
- `About Her`
- `Relationship Core`
- `My Profile`

`data/active_memory.md` now renders in structured sections:
- `Current Status`
- `Purpose Context`
- `On the Horizon`
- `Others`

Both files keep a backward-compatible timestamp header and add a format marker (`core_profile.v2` / `active_memory.v2`). Rendering is bounded by per-section item limits and per-item character limits to keep prompt token usage stable.


## Nightly digest scheduler (Phase 4 slice 2)
- Scheduler now uses local timezone-aware evaluation and triggers nightly digest once per local date at **04:05**.
- Timezone is configurable via `scheduler.local_timezone` (or env `SAKI_LOCAL_TIMEZONE`). If invalid/missing, gateway falls back to server local timezone.
- Digest run state is persisted to `memory.digest_run_state_path` (default `./data/digest_run_state.json`) with fields:
  - `id`, `run_state`, `status`, `started_at`, `completed_at`, `error_message`
- Idempotency behavior:
  - If a date already completed with `success`, scheduler records skip and does not rerun that date.
  - If a run fails (for example Trilium unavailable), status becomes `failed` and a later tick can retry safely.
- Digest inputs include recent 24h messages, tool execution events, active memory snapshot, and optional recent durable memories.
- Digest output refreshes `active_memory.md` and upserts one Trilium note under `AI Companion Workspace / Daily Digest / YYYY-MM-DD daily digest` (best-effort, graceful failure).

TODOs:
- core profile proposal queue (`pending_core_updates`) is intentionally out-of-scope for slice 2.
- durable-memory archival strategy remains intentionally minimal in this slice.


## Core profile protection + proposal workflow (Phase 4 slice 3)
- `core_profile.md` is protected: automatic jobs must not silently overwrite core sections.
- `active_memory.md` may still refresh automatically.
- Candidate core changes are stored in SQLite table `pending_core_updates` with fields:
  - `id`, `target_section`, `proposed_content`, `reason`, `source_context`, `fingerprint`, `proposal_type`, `confidence`, `status`, `created_at`, `updated_at`, `reviewed_at`
- `proposal_type` is constrained in practice to: `identity | preference | goal | relationship | routine | other`
- `confidence` is constrained in practice to: `low | medium | high`
- `target_section` is validated to the real core sections only:
  - `About Her`, `Relationship Core`, `My Profile`
- Fingerprint purpose:
  - deduplicate semantically same open proposals based on normalized section + normalized content
  - normalization collapses whitespace and strips trivial markdown-only prefixes
- Dedup behavior:
  - if same fingerprint already exists in `open` status, no new row is inserted; existing row `updated_at` is touched and context can be merged
  - approved/rejected history is preserved
- Review lifecycle (backend):
  - `open` -> `approved` performs section-aware semantic merge (dedupe + conservative conflict handling) and sets `reviewed_at`
  - `open` -> `rejected` keeps `core_profile` unchanged and sets `reviewed_at`
- Merge behavior for approval:
  - integrates meaningfully new entries once into the target section
  - suppresses strongly overlapping duplicates
  - handles likely conflicts conservatively (logs conflict, does not overwrite existing safer fact)

Known limitations:
- UI review panel is not included in this slice (backend operations only).
- Semantic merge is intentionally conservative; richer contradiction resolution and ontology-aware merging remain TODO.


## Review/admin visibility surface (Phase 4 slice 5)
A minimal backend review surface is available via authenticated dashboard API routes (no chat UI changes):

- `GET /api/review/proposals?status=open&limit=50`
  - Defaults to `status=open`
  - Supports `status=open|approved|rejected|all`
  - Returns reviewer-facing proposal fields: `id`, `target_section`, `proposed_content`, `proposal_type`, `confidence`, `reason`, `source_context`, `status`, `created_at`, `updated_at`, `reviewed_at`
- `POST /api/review/proposals/{proposal_id}/approve`
  - Runs existing approval workflow + semantic merge
  - Returns clear `ok` flag and updated proposal status payload
- `POST /api/review/proposals/{proposal_id}/reject`
  - Runs existing rejection workflow
  - Returns clear `ok` flag and updated proposal status payload
- `GET /api/review/digest-state?history_limit=10`
  - Returns latest persisted digest run state (`id`/run date, status, started/completed timestamps, error)
  - Also returns whether current local date already completed successfully
  - Includes recent `digest_run` history entries from event log when available
- `GET /api/review/memory`
  - Read-only inspection for current `core_profile.md` and `active_memory.md`
  - Exposes both raw content and section-extracted view for:
    - core: `About Her`, `Relationship Core`, `My Profile`
    - active: `Current Status`, `Purpose Context`, `On the Horizon`, `Others`

Known limitations:
- Surface is intentionally backend/debug-first and not a polished operator UI.
- Digest history is event-derived (best effort) and may be limited by event retention.
- TODO: add richer review pagination/filtering and explicit reviewer identity metadata.

## Human-like message segmentation
Feishu and QQBot outbound text now prefer newline-based segmentation. Each non-empty line is sent as an individual message segment, with a short configurable delay between segments, and long lines still fall back to chunking by `send_chunk_chars`.

## Privacy / sanitization
This OSS build excludes personal memories, private profiles, live API keys/tokens, and conversation logs. Use `data/config.example.json` as the template for local configuration; create your own untracked `data/config.json` when deploying.

## Trilium integration (Phase 1)
The gateway now includes a Trilium client module for deployment integration groundwork.

Environment variables:
- `TRILIUM_ENABLED`
- `TRILIUM_URL`
- `TRILIUM_ETAPI_TOKEN` (recommended)
- `TRILIUM_TOKEN` (backward-compatible fallback)
- `TRILIUM_TIMEOUT_SECONDS` (optional, default `10`)

Current client surface (`saki_gateway.trilium.TriliumClient`):
- `health_check()`
- `search_notes(query, limit=5, parent_note_id=None)`
- `get_note(note_id)`
- `get_note_content(note_id)`
- `list_children(parent_note_id)`

Behavior:
- Uses bounded request timeout.
- Returns safe fallbacks (`[]`, `None`, or `""`) when Trilium is down or unreachable.
- Avoids credential leakage by never exposing `TRILIUM_TOKEN` in public config payloads.


Phase 2 gateway tools are now available when Trilium is enabled and configured:
- `search_trilium`
- `get_trilium_note`

Routing rule in system prompt: for diary notes / study notes / book notes / "my notes", the model is instructed to call `search_trilium` first and then `get_trilium_note`.


## Manual E2E test case (Trilium read-only flow)
1. Set env vars and start gateway:
   - `TRILIUM_ENABLED=true`
   - `TRILIUM_URL=http://<your-trilium-host>`
   - `TRILIUM_ETAPI_TOKEN=<your-etapi-token>`
2. In chat, send: `帮我找一下我的学习笔记里关于线性代数的内容`
3. Confirm tool behavior in logs / tool events:
   - first `search_trilium` runs and injects only compact candidates (titles + ids)
   - then `get_trilium_note` runs for one selected note and injects truncated/compact content
4. Validate result distinction:
   - if Trilium is down/unreachable: assistant should indicate **Trilium unavailable**
   - if Trilium is healthy but query returns empty: assistant should indicate **no notes found**
5. Send an ordinary chat message like `今天心情有点低落` and confirm Trilium tools are not triggered unless notes are explicitly requested.


## Learning session foundation (Phase 4 next slice)
This slice adds a backend-first learning-session flow focused on sustainable study continuity (not harsh productivity scoring).

### Runtime SQLite schema
`runtime_store` now persists:

- `learning_sessions`
  - `id`, `title`, `goal`, `subject`, `mode`, `status`, `runtime_state`
  - `planned_minutes`, `pomodoro_count`, `elapsed_minutes`, `remaining_minutes`, `break_count`
  - `short_break_minutes`, `long_break_minutes`, `pause_started_at`
  - `started_at`, `ended_at`, `actual_minutes`, `summary`, `blockers`, `next_step`, `created_at`, `updated_at`
- `wellbeing_checkins`
  - `id`, `session_id`, `stage`, `energy_level`, `focus_level`, `mood_level`, `body_state_level`, `stress_level`, `note`, `created_at`
- `learning_session_events`
  - inspectable lifecycle/runtime events emitted by the backend
- `learning_session_responses`
  - queued proactive companion messages linked to learning events
  - includes `response_context` for inspectable layered defaults, recovery-state selection, safety settings, next-step sizing, and recent signal snapshots
- `learning_response_styles`
  - lightweight runtime response-style overrides (`default` or per-session scope)

Mode lifecycle:
- `focus | recovery | review`

Status lifecycle:
- `active -> completed`
- `active -> abandoned`

Runtime state lifecycle (minimal backend slice):
- `focus -> paused -> focus`
- `focus -> focus_completed -> break -> focus`
- terminal transitions force `completed` or `abandoned`

Guardrails:
- At most one `active` learning session at a time.
- State transitions require active status.
- `actual_minutes` is computed from `started_at`/`ended_at` when not provided.
- Very small `planned_minutes` values are allowed and `mode=recovery` is first-class.
- Invalid runtime transitions (for example resume without pause) are rejected.
- Study-mode responses stay short, non-sexual, and avoid degrading/punitive language.

### Minimal backend/admin endpoints
Authenticated dashboard API routes:

- `GET /api/learning-sessions/active`
- `GET /api/learning-sessions?status=&limit=20`
- `GET /api/learning-sessions/{session_id}`
- `GET /api/learning-sessions/{session_id}/checkins?limit=20`
- `POST /api/learning-sessions/start`
  - supports optional `start_checkin`
- `POST /api/learning-sessions/{session_id}/update`
- `POST /api/learning-sessions/{session_id}/runtime`
  - `action` supports `pause`, `resume`, `focus_completed`, `break_started`, `break_completed`, `paused_too_long`
- `POST /api/learning-sessions/{session_id}/complete`
  - supports optional `end_checkin`
- `POST /api/learning-sessions/{session_id}/abandon`
  - supports optional `end_checkin`
- `POST /api/learning-sessions/{session_id}/checkins`
- `GET /api/learning-sessions/{session_id}/events?limit=20`
- `GET /api/learning-sessions/{session_id}/responses?limit=20`
- `GET /api/learning-sessions/style?session_id=`
- `POST /api/learning-sessions/style?session_id=`
- `GET /api/learning-sessions/framework?session_id=`
- `GET /api/learning-sessions/progress?window_days=7&session_limit=50`
- `GET /api/learning-sessions/progress?windows=7,14,30&session_limit=50`

### Progress summaries and trend inspection (B4)
B4 adds a backend-first, SQLite-derived summary layer for recent study behavior. It is intentionally small, inspectable, and rule-based rather than a heavy analytics system.

Current summary windows:
- `last 7 days`
- `last 14 days`
- `last 30 days`
- optional recent payload limiting via `session_limit`

Computed metric groups:
- session counts: started / completed / abandoned
- total focus minutes, review minutes, recovery minutes
- completion rate and average completed-session length
- pause/resume friction counts plus a small explicit friction score
- low-energy start counts and recovery-needed signal counts
- repeated blocker text extraction from `blockers` fields

Focus-vs-recovery balance:
- derived from session mode + session minutes
- prefers `actual_minutes`, then `elapsed_minutes`, then `planned_minutes`
- returns totals, ratios, and approximation notes so the output stays inspectable

Minimal friction/blocker pattern rules:
- frequent long pauses
- repeated abandoned sessions
- repeated low-energy starts
- recovery-needed signal spikes
- many short incomplete focus attempts
- strain after multiple pomodoros when recent events support it

Each pattern includes:
- short human-readable label
- explicit reason
- `rule_trace` with the triggering heuristic and matched sessions

Summary text outputs:
- `weekly_summary`
- `recent_pattern_summary`
- `momentum_check`
- `blocker_focus_balance_note`

Inspection payload shape:
- `window`: effective label/date range/session limit
- `metrics`: raw trend metrics
- `focus_balance`: totals + ratios + approximation notes
- `friction_patterns`: fired rules with traces
- `summary_text`: short generated backend summaries
- `memory_digest_hook`: optional future-facing integration hook without automatic long-term memory writes
- `inspection`: source metadata (`computed_on_read`, source counts, session ids)

Known limitations for B4:
- summaries are computed on read, not stored as a historical fact table
- timing is session-level, not second-by-second timer analytics
- pause friction only uses explicit runtime events, not background app inactivity
- blocker extraction is simple text splitting, not semantic clustering
- B4 exposes a safe hook for future digest/memory use, but does not auto-write long-term memory from trend summaries
- richer UI surfacing belongs in a future B5 minimal study UI slice

### Minimal study UI (B5)
B5 adds a small web/admin study surface in `saki-phone/web` without redesigning the main chat product. It stays backend-driven and reuses the existing B1/B2/B3/B4 APIs.

The study page now supports:
- viewing the current active session, mode, runtime state, elapsed/remaining minutes, and recent check-ins
- starting a session with title / goal / mode / planned minutes
- pause / resume / complete / abandon controls against the existing lifecycle endpoints
- lightweight wellbeing check-in submission (`start | end` with optional energy / stress / focus / body / note fields)
- viewing recent learning-session events and recent generated companion responses
- viewing B4 progress summaries and friction notes with simple `7d / 14d / 30d` window switches

Implementation notes:
- the UI is intentionally readable and inspectable, not a polished timer app
- invalid control transitions still defer to backend validation and are surfaced as readable request errors
- progress cards reuse `/api/learning-sessions/progress` instead of calculating trend data in the frontend
- recovery/support context stays tied to the existing B3 response/debug payloads

Still intentionally missing after B5:
- animated timer UX
- rich charts / analytics dashboard
- deep session editing flows
- major chat UI redesign
- automatic long-term memory writes from UI activity

### Check-in behavior
- `stage` supports `start | end`.
- Structured levels are lightweight (1-5) and optional.
- Short free-text `note` is supported.

### Event model and response generation flow
Supported event types in this slice:

- `session_started`
- `focus_completed`
- `break_started`
- `break_completed`
- `session_paused`
- `session_paused_too_long`
- `session_resumed`
- `session_completed`
- `session_abandoned`
- `low_energy_start`
- `recovery_completion`

Flow:
1. learning-session lifecycle or runtime control emits a lightweight event row
2. the event is mirrored into the existing gateway event log for debugging
3. the backend builds a short companion response from layered backend inputs:
   - event type
   - session mode
   - recent wellbeing/check-in context if available
   - recent event history to avoid repeating the same line every time
   - recent response history so recovery adaptation can stay inspectable and avoid pressure loops
   - effective response-style config
4. an explicit recovery interpretation pass derives a lightweight support state (`stable | low_energy | overwhelmed | anxious_or_stressed | recovery_needed`)
   - rules stay inspectable in `response_context.recovery_state.rule_trace`
   - current signals include wellbeing levels/notes, session mode, pause friction, abandonment, incomplete cycles, and lightweight summary hints
5. a minimal next-step sizing pass maps the recovery state to one of:
   - `continue_current_block`
   - `do_one_tiny_next_action`
   - `switch_to_lighter_review_task`
   - `take_short_break`
   - `stop_and_recover`
6. the response is stored in `learning_session_responses` with `delivery_status=queued` and an inspectable `response_context` snapshot
   - includes selected response-variant metadata, derived recovery state, safety flags, style effects, next-step category, and adapted behavior for debugging/admin inspection

This is intentionally backend-first so future chat insertion, banners, or notifications can reuse the same queue.

### Layered persona-ready response architecture
The response generator stays deliberately simple and inspectable. Each proactive message is planned from separable layers instead of one giant injected prompt:

- `base_persona_slot`: safe neutral companion default in this slice
- `context_overlay_slot`: study/recovery/review-ready insertion point
- `event_response_style_slot`: short real-time response behavior
- `safety_boundary_slot`: explicit study-safe boundary rules

Current implementation uses neutral defaults only and leaves an explicit TODO hook for future custom persona injection.

Additional notes:
- The responder rotates through small per-event variant pools when the same event repeats in recent history, which keeps real-time nudges short without becoming mechanically repetitive.
- Style remains inspectable as structured config (`style` + `style_effects`) rather than a hidden prompt blob.

### Recovery-aware interpretation and adaptation (B3)
The B3 layer sits on top of the existing B2 event-response path without changing the main chat flow. It remains backend-first, rule-based, and SQLite-backed.

Interpretation inputs currently include:

- latest wellbeing check-in levels and note text
- session mode (`focus | recovery | review`)
- recent pause / resume / paused-too-long events
- repeated incomplete focus cycles
- recent abandonment signals
- recent queued response history
- lightweight recovery hints already present in session `summary`, `blockers`, or `next_step`

Interpretation behavior:

- explicit scoring/rule composition is used instead of opaque orchestration
- admin/debug inspection can see the chosen state, contributing reasons, and `rule_trace`
- the current state is ephemeral runtime interpretation only; it is not written into long-term memory or `core_profile`

Adaptation behavior by state:

- `stable`: normal B2 behavior continues
- `low_energy`: reduces pressure and favors a simple re-entry action
- `overwhelmed`: stabilizes first and shrinks the task immediately
- `anxious_or_stressed`: prefers grounding language and smaller immediate actions
- `recovery_needed`: stops pushing output and prefers rest/recovery before more study effort

### Next-step sizing
B3 adds a deliberately small structured layer to keep proactive study replies practical without turning the system into a planner.

Possible categories:

- `continue_current_block`
- `do_one_tiny_next_action`
- `switch_to_lighter_review_task`
- `take_short_break`
- `stop_and_recover`

The selected category is stored in `response_context.next_step` together with the main reason. This is primarily for short real-time study support and admin inspection, not for building long task plans.

### Style vs recovery override rules
- Response style config still affects phrasing, warmth, and firmness in normal conditions.
- Recovery interpretation can soften `dominance_style=high` and `correction_style=firm` when the user appears fragile.
- Fragile states force gentler redirects, smaller steps, anti-guilt wording, and stronger recovery-first safety behavior.
- The recovery layer does not permit intimate, RP, punitive, or degrading language.

### Response-style config
Safe default style:

- `dominance_style=medium`
- `care_style=steady`
- `praise_style=warm`
- `correction_style=gentle`

Supported dimensions:

- `dominance_style`: `low | medium | high`
- `care_style`: `soft | steady | strict_care`
- `praise_style`: `restrained | warm | possessive_lite`
- `correction_style`: `gentle | firm`

Notes:
- Style is runtime/config behavior, not long-term identity memory.
- Study mode does **not** automatically use sexual, intimate, or RP language.
- `care_style` shifts how much reassurance/protective structure is used.
- `dominance_style` and `correction_style` only affect brief redirect firmness inside study-safe boundaries.
- `praise_style` changes acknowledgement intensity while staying non-intimate.
- When wellbeing suggests exhaustion, anxiety, or physical strain, responses shift toward stabilization and smaller next steps.

### Minimal memory/digest-adjacent integration
- On completion, a concise long-term memory item is upserted with category `learning_session`.
- This allows the existing active-memory renderer to surface recent session outcomes with minimal change.
- No automatic `core_profile` mutation is performed.

Known limitations / TODO:
- Recovery interpretation is intentionally heuristic and local to recent session signals; it is not a diagnostic or therapy system.
- No trend/summaries view yet for recovery patterns across multiple sessions; that is a better fit for a future B4 slice.
- No dedicated frontend surfacing yet for recovery state, next-step category, or adapted behavior; that is a better fit for a future B5 support UI slice.
- No polished timer/dashboard UI in this slice.
- Responses are queued for inspection/future delivery, not yet inserted directly into the main chat timeline.
- No advanced wellbeing analytics or scoring.
- No per-mode override persistence yet; current style overlay is `default` or per-session only.
- Recent-event de-duplication is intentionally lightweight and template-driven, not full dialogue planning.
- TODO: optional custom persona text should populate the existing layer slots instead of replacing the safety/event framework.
- TODO: optional Trilium completion note output can be added later if needed.
- TODO: hook the queued responses into a future web notification/chat insertion surface.
