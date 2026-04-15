# AGENTS.md
Project: OpenClaw GUI Front-End  
Date: April 15, 2026  
Primary Target: Linux desktop  
Language: Python 3.11+  
GUI Toolkit: PySide6

## 1. Mission

Build a desktop GUI front-end for OpenClaw that connects through the OpenClaw gateway and gives the user a much better control surface than the command line alone.

The GUI must let the user:

- manage multiple code projects
- maintain multiple reusable agent personalities
- start, suspend, restore, and restart project-scoped sessions
- view the current session dialog in a center conversation panel
- switch between projects while preserving each project’s session history
- see live connection/session status in a compact status bar

This application is a control cockpit for OpenClaw, not a replacement for OpenClaw.

---

## 2. Product Vision

The app should feel like a blend of:

- a lightweight IDE control panel
- a session manager
- an agent personality switchboard
- a conversation window for the currently active OpenClaw session

The user should be able to hop between projects without losing context, swap personalities when desired, and avoid doing routine OpenClaw management from the terminal.

The design spec for this project exists in `openclaw_gui_design_spec.md`. Treat that file as the source of truth for architecture and behavior. This `AGENTS.md` is the implementation brief and execution guide.

---

## 3. Core Rules

### Rule 1: Gateway-first
Do not build this around terminal subprocess control as the primary path. The primary integration target is the OpenClaw gateway.

### Rule 2: Project-scoped sessions
Sessions belong to projects. Project switching is a central feature and must be designed cleanly from the start.

### Rule 3: Personality bundles are first-class
Each personality is made from:
- `SOUL.md`
- `AGENTS.md`
- `IDENTITY.md`

These are editable and reusable.

### Rule 4: Persistence matters
Do not rely on only in-memory state. Projects, personalities, sessions, and transcripts must survive app restarts.

### Rule 5: UI must stay responsive
Network I/O and gateway calls must not block the main Qt thread.

### Rule 6: Keep layers separate
Do not entangle UI widgets with persistence and gateway logic. Use a modular architecture.

---

## 4. Deliverable

Produce a working PySide6 application with:

- a 3-panel main window
- project management
- personality management
- gateway configuration
- gateway-backed session messaging
- local persistence of session history
- project-based suspend/restore/restart flow

The code should be organized, testable, and easy to iterate on.

---

## 5. MVP Scope

Build the following first. Do not overreach before these are stable.

### Required MVP features
- Main window with:
  - top control bar
  - middle session dialog pane
  - bottom status bar
- Project CRUD
- Personality CRUD
- Gateway settings storage
- Gateway connect/test status
- Start a session for a selected project/personality
- Send a message to the gateway-backed session
- Display responses in the conversation pane
- Persist transcript and session metadata locally
- Soft suspend current session
- Restore previous project session
- Restart session while preserving history
- Reopen app and retain projects, personalities, and past sessions

### Explicitly defer unless implementation is trivial
- multi-live-session parking
- transcript search
- fancy markdown preview
- token dashboards
- personality version history
- plugin framework
- cross-platform installer polish

---

## 6. Technical Stack

Use:

- Python 3.11+
- PySide6
- SQLite
- filesystem-backed storage for transcripts and personality files
- `httpx` for gateway calls
- dataclasses or pydantic models
- pytest for tests

You may add light helper libraries if they clearly improve code quality, but do not bloat the stack.

---

## 7. Directory / Package Shape

Target package structure:

```text
openclaw_gui/
  __init__.py
  main.py
  app/
    controllers/
      app_controller.py
      session_controller.py
      project_controller.py
      personality_controller.py
    gateway/
      gateway_client.py
      gateway_adapter.py
      gateway_models.py
    persistence/
      db.py
      repositories.py
      file_store.py
    models/
      project.py
      personality.py
      session.py
      event.py
      settings.py
    services/
      restore_service.py
      summary_service.py
      export_service.py
    ui/
      main_window.py
      widgets/
        top_bar.py
        session_view.py
        status_strip.py
      dialogs/
        project_manager_dialog.py
        personality_manager_dialog.py
        session_history_dialog.py
        settings_dialog.py
  tests/
```

You may adjust names slightly if needed, but preserve the architectural separation.

---

## 8. Data Model Requirements

Implement persistent models for:

### Project
Fields:
- id
- name
- description
- root_path
- default_personality_id nullable
- created_at
- updated_at

### Personality
Fields:
- id
- name
- description
- storage_path
- created_at
- updated_at

### SessionRecord
Fields:
- id
- project_id
- personality_id
- status
- gateway_session_ref nullable
- started_at
- last_activity_at
- transcript_path
- summary_path nullable
- metadata_json nullable

### SessionEvent
Fields:
- id
- session_id
- timestamp
- event_type
- content
- metadata_json nullable

Statuses should include at least:
- active
- suspended
- archived
- failed

Event types should include at least:
- user
- assistant
- system
- status
- error
- personality_change

---

## 9. Persistence Requirements

Use hybrid persistence:

### SQLite for
- project records
- personality metadata
- session metadata
- settings
- event index if useful

### Filesystem for
- personality files
- transcript files
- summary files
- exported logs

Recommended app data layout:

```text
<data_root>/
  app.db
  settings.json
  personalities/
    <personality-id>/
      SOUL.md
      AGENTS.md
      IDENTITY.md
      personality.json
  projects/
    <project-id>/
      sessions/
        <session-id>/
          transcript.md
          transcript.jsonl
          summary.md
          metadata.json
```

On startup, load persisted state cleanly.

---

## 10. UI Requirements

## Main Window Layout

### Top control bar
Must include:
- Project dropdown
- Personality dropdown
- New Session button
- Suspend button
- Restore button
- Restart button
- Projects button
- Personalities button
- Settings button
- Open Folder button
- Gateway status indicator
- Session state indicator

### Middle session panel
Must include:
- transcript/history view
- current session header/banner
- message input
- send button

Should visually distinguish:
- user messages
- assistant messages
- system/status messages

### Bottom status strip
Must show:
- current project
- current personality
- session id
- session state
- gateway state
- last activity time

Optional if easy:
- model/backend
- message count
- project root path

---

## 11. Gateway Integration Requirements

You must build a gateway abstraction layer instead of hard-coding endpoint logic directly into the UI.

Create an internal adapter/client with roughly this shape:

```python
class GatewayClient:
    def ping(self) -> bool: ...
    def get_status(self): ...
    def start_session(self, project_context, personality_context): ...
    def send_message(self, session_handle, text): ...
    def restore_session(self, saved_state): ...
    def end_session(self, session_handle): ...
    def list_capabilities(self): ...
```

The exact gateway API may differ. Discover it and adapt behind this interface.

### Important
- Centralize all gateway calls
- Normalize errors into app-friendly exceptions/results
- Keep the rest of the app insulated from API quirks

---

## 12. Session Lifecycle Requirements

Implement these flows carefully.

### Start Session
1. User selects project
2. User selects personality
3. Local session record is created
4. Gateway session is started
5. Session becomes active in UI
6. Transcript begins logging

### Send Message
1. User enters text
2. User message is appended locally
3. Message is sent through gateway
4. Response arrives
5. Assistant response is appended locally
6. Session metadata updates

### Suspend Session
1. Flush transcript to disk
2. Persist metadata
3. Optionally persist summary placeholder
4. Mark session suspended
5. Close or detach gateway-side state as needed

### Restore Session
1. Load transcript and session metadata
2. Display old transcript in UI
3. Reconnect to gateway-side session if supported
4. Otherwise create a new logical session and continue from saved context

### Restart Session
1. Archive current session
2. Preserve transcript/history
3. Create new active session for same project
4. Keep current personality unless changed
5. Clear live conversation pane for the new session

### Switch Project
1. Save and suspend current session if needed
2. Load the target project
3. Restore the latest restorable session if available
4. Otherwise present a fresh session state
5. Update all visible controls/status

---

## 13. Personality Requirements

Support full CRUD for personalities.

Each personality must have editable content for:
- `SOUL.md`
- `AGENTS.md`
- `IDENTITY.md`

Recommended UI:
- list of personalities on the left
- editor tabs on the right for the three markdown files plus metadata

When personality changes during an active session:
- update the active personality selection
- record an event of type `personality_change`

Do not lose older session-to-personality history.

---

## 14. Project Requirements

Support full CRUD for project references.

Important constraints:
- deleting a project from the GUI must not delete the actual project folder
- validate project path existence
- prevent empty project names
- ideally prevent duplicate project names

Include:
- name
- description
- root path
- optional default personality

---

## 15. Settings Requirements

Implement settings storage for at least:
- gateway URL
- gateway auth token
- app data root
- default personality
- autosave interval

If secure storage for secrets is easy and clean, use it. Otherwise document token storage plainly and keep it centralized.

---

## 16. Error Handling

The app must handle and surface errors for:
- gateway unavailable
- bad authentication
- invalid project path
- failed session start
- failed message send
- failed restore
- corrupt local session data

Rules:
- do not crash the entire UI for normal operational failures
- preserve transcript if sending fails
- show readable error dialogs for user-visible failures
- log technical details to a local log file

---

## 17. Code Quality Expectations

- Use type hints throughout
- Keep controllers thin but meaningful
- Keep models explicit
- Use repositories/services where that improves clarity
- Avoid giant god-classes
- Avoid mixing Qt widget code with gateway networking code
- Keep imports tidy
- Prefer small, testable methods

---

## 18. Testing Expectations

Write tests for the following:

### Persistence
- create/read/update/delete project records
- create/read/update/delete personality metadata
- create/load session records
- transcript file writing

### Session logic
- start session lifecycle
- suspend/restore behavior
- restart behavior
- project switching behavior

### Gateway layer
- ping/status happy path
- error normalization
- mocked send_message flow

### UI smoke tests if practical
- main window instantiation
- project switching updates visible state

Mock gateway interactions in tests. Do not depend on a live gateway for core test coverage.

---

## 19. Implementation Plan

Build in this order:

### Milestone 1: Foundation
- scaffold package structure
- implement models
- implement SQLite layer
- implement file storage layer
- implement settings loading/saving

### Milestone 2: Gateway adapter
- inspect/confirm OpenClaw gateway API
- build `GatewayClient`
- add health check and message sending support
- add mocked tests

### Milestone 3: Session controller
- implement session lifecycle rules
- implement project switching logic
- implement persistence hooks
- implement transcript append/save behavior

### Milestone 4: Core UI
- main window
- top bar
- session view
- status strip
- settings dialog

### Milestone 5: Management dialogs
- project manager dialog
- personality manager dialog
- session history dialog

### Milestone 6: Polish
- error handling pass
- autosave
- startup restore
- UX cleanup
- final tests

Do not start with polished visual cosmetics. Make the system solid first.

---

## 20. Definition of Done

The MVP is done when:

1. user can manage project references
2. user can manage personalities with `SOUL.md`, `AGENTS.md`, and `IDENTITY.md`
3. user can configure gateway connection settings
4. app can verify gateway connectivity
5. user can start a session for a project/personality
6. user can exchange messages with the agent through the GUI
7. transcript and session metadata persist locally
8. switching projects preserves/restores appropriate sessions
9. user can suspend and restore sessions
10. user can restart sessions without destroying old history
11. app restart preserves projects, personalities, and session history
12. UI remains responsive while gateway calls are in progress

---

## 21. Open Questions to Resolve Early

Investigate these before hardening the gateway layer:

1. What exact OpenClaw gateway endpoints are available?
2. How does the gateway identify sessions?
3. Is there native session restoration?
4. How are personalities injected?
5. Does the gateway provide structured message objects or raw response text?
6. What authentication mode is required?
7. Is there an existing concept of project/workspace/session that maps naturally to this app?

Record findings in code comments or a short dev note.

---

## 22. Guardrails

Do not:
- hard-code gateway URLs all over the codebase
- keep only in-memory session history
- block the main thread with network calls
- tightly couple widgets to database code
- tightly couple widgets to gateway code
- delete user project directories from project removal actions
- assume native gateway restore exists without checking

Do:
- persist aggressively but safely
- keep old sessions browsable
- keep project and personality always visible
- design for future enhancement without overengineering v1

---

## 23. Nice Future Enhancements

After MVP, likely best next features are:
- transcript search
- session summary cards
- continue vs start-fresh restore prompt
- project notes panel
- session branching/forking
- import/export personality bundles
- theme support
- richer gateway diagnostics

These are not MVP blockers.

---

## 24. Final Instruction

Implement the MVP cleanly, modularly, and with strong session persistence.  
Bias toward reliability and architecture over visual flourish.  
The GUI should make OpenClaw feel easier to steer, not more complicated.
