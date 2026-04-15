# OpenClaw GUI Front-End Design Spec
Version: 0.1  
Date: April 15, 2026

## 1. Purpose

This document defines a concrete design specification for a desktop GUI front-end that manages and controls an OpenClaw agent through the OpenClaw gateway rather than through direct command-line use.

The GUI is intended to improve project switching, session continuity, personality management, and overall usability while preserving the experience of interacting with an OpenClaw agent in an agent-session style workflow.

This spec is written to be handed directly to Codex as the implementation brief for the first production-ready version.

---

## 2. Product Summary

The application is a desktop GUI that connects to the OpenClaw gateway and gives the user a structured control surface for:

- selecting a current code project
- opening or restoring a session tied to that project
- suspending and resuming project-scoped sessions
- restarting or resetting sessions
- viewing the current session dialog in the center of the GUI
- managing reusable agent personalities made up of `SOUL.md`, `AGENTS.md`, and `IDENTITY.md`
- tracking project/session metadata over time

The app should not replace OpenClaw itself. It should operate as a session manager and GUI control layer around the existing OpenClaw ecosystem.

---

## 3. Core Design Principles

1. **Gateway-first integration**  
   The GUI communicates with OpenClaw through the OpenClaw gateway rather than by driving a terminal subprocess.

2. **Project-scoped session management**  
   Sessions are associated with projects, and switching projects switches the active session context.

3. **Personality as a reusable configuration bundle**  
   Personalities are global reusable bundles made up of `SOUL.md`, `AGENTS.md`, and `IDENTITY.md`.

4. **Transcript-first user experience**  
   The center panel should feel like the OpenClaw session conversation, while the surrounding GUI adds structured management tools.

5. **Soft suspend/restore for v1**  
   The first implementation should save and restore session context through metadata and transcript persistence, without depending on native gateway-side session parking unless that is already supported cleanly.

6. **Extensible local architecture**  
   The app should be designed so session control, persistence, and GUI rendering are modular and can evolve without major rewrites.

---

## 4. Recommended Tech Stack

### Primary recommendation
- **Language:** Python 3.11+
- **GUI framework:** PySide6
- **Persistence:** SQLite + filesystem
- **HTTP client:** `httpx`
- **Data models:** `pydantic` or Python dataclasses
- **Markdown editing/viewing:** Qt text widgets with plain markdown editing support
- **Background tasks / async bridge:** Qt signals/slots + worker threads or `qasync` if needed

### Why this stack
- Fits an existing Python-heavy environment
- Good support for split layouts, toolbars, dialogs, status bars, and model/view patterns
- Easy to package for desktop use
- Easy to integrate with existing OpenClaw/gateway workflows
- Good fit for Codex-generated implementation work

---

## 5. High-Level Architecture

The application should be divided into five major layers:

### 5.1 Presentation Layer
PySide6 GUI components:
- Main window
- Top control panel
- Session dialog panel
- Bottom status bar
- Project manager dialogs
- Personality manager dialogs
- Session history dialogs

### 5.2 Application Layer
Coordinates user actions and business logic:
- project switching
- session creation/restoration
- suspend/restart actions
- personality changes
- gateway communication requests

### 5.3 Session Controller Layer
A local controller module responsible for:
- creating logical sessions
- associating sessions with projects
- loading/saving session metadata
- managing the active session in the GUI
- reconstructing previous context when restoring a session

### 5.4 Gateway Integration Layer
Wraps all HTTP/API calls to the OpenClaw gateway:
- health checks
- agent/session start calls
- message send calls
- transcript retrieval if available
- status polling
- error normalization

### 5.5 Persistence Layer
Stores:
- projects
- personalities
- sessions
- transcript logs
- summaries
- app settings

---

## 6. Main Window Layout

The UI should be composed of three panels:

### 6.1 Top Panel
A narrow control strip across the top containing:
- Current Project dropdown
- Current Personality dropdown
- Session Action buttons
- Gateway status indicator
- Agent/session state indicator

#### Recommended controls
- **Project dropdown**
- **Personality dropdown**
- **New Session** button
- **Suspend** button
- **Restore** button
- **Restart** button
- **Projects...** button
- **Personalities...** button
- **Open Folder** button
- **Gateway Connected/Disconnected** indicator
- **Current Session State** badge

### 6.2 Middle Panel
The main session dialog area showing the current conversation.

This panel should contain:
- transcript/history view
- current session banner/header
- message input box
- send button
- optional conversation tools like search/export in later versions

The transcript should be rendered as a structured chat-like log or log-style conversation view that clearly distinguishes:
- user messages
- assistant messages
- system/status events

### 6.3 Bottom Panel
A narrow status bar showing current runtime/session stats.

Recommended fields:
- Current project name
- Current personality name
- Session ID
- Session status
- Project root path
- Last activity time
- Message count
- Gateway endpoint
- Optional agent/model info if available

---

## 7. Functional Requirements

## 7.1 Project Management

The application must support CRUD operations for project references.

### Project fields
- `name`
- `description`
- `root_path`
- optional `default_personality_id`
- timestamps

### Project requirements
- User can add a project reference
- User can edit project metadata
- User can delete a project reference
- Deleting a project reference should not delete actual project files
- User can pick the active project from the top dropdown
- Switching projects should suspend or save the current active session and load the target project’s latest active/restorable session

### Validation
- `root_path` must exist
- `name` must be non-empty
- duplicate project names should be discouraged or prevented

---

## 7.2 Personality Management

A personality is a reusable bundle of:
- `SOUL.md`
- `AGENTS.md`
- `IDENTITY.md`

### Personality fields
- `name`
- `description`
- `folder_path` or managed internal storage path
- `SOUL.md` content
- `AGENTS.md` content
- `IDENTITY.md` content
- timestamps

### Personality requirements
- User can create a personality
- User can edit a personality
- User can delete a personality
- User can select the active personality globally
- User can change personality at any time
- Session metadata must record which personality was active for that session
- If personality changes during a session, log this as a session event

### Storage recommendation
Store each personality in its own folder:

```text
personalities/
  default/
    SOUL.md
    AGENTS.md
    IDENTITY.md
    personality.json
```

---

## 7.3 Session Management

A session is logically associated with:
- one project
- one active personality snapshot
- one transcript/history
- one session state record

### Required session actions
- Start new session
- Suspend session
- Restore session
- Restart session
- View session history

### Session behavior
- Each project can have multiple historical sessions
- Each project has at most one currently active/restorable session in v1
- Switching away from a project should save the current session state
- Switching back should restore the latest compatible session for that project
- Restarting a session creates a fresh session while preserving old history

### Definitions for v1
#### Suspend
“Soft suspend” means:
- save transcript
- save metadata
- save project association
- save active personality reference
- optionally save a user-written or auto-generated summary
- mark session as suspended

#### Restore
Restore means:
- load transcript into the GUI
- re-establish the session context in the application
- if gateway-native restore exists, use it
- otherwise create a fresh logical session and seed it with saved context/summary as needed

#### Restart
Restart means:
- archive the current session
- begin a new session for the same project
- preserve project reference
- optionally preserve active personality
- clear active conversation state from the current live pane

---

## 7.4 Session Dialog / Conversation View

The center panel should mimic the feel of an OpenClaw session without looking like a raw terminal dump.

### Required capabilities
- Show historical messages for the active session
- Show new user messages immediately
- Show assistant responses as they arrive
- Show system/status events
- Auto-scroll to newest content
- Preserve timestamps
- Support long transcript history

### Message/event types
- `user`
- `assistant`
- `system`
- `status`
- `error`
- `personality_change`

### v1 rendering recommendation
Use a styled scrollable transcript widget with:
- role-based visual formatting
- timestamps
- separators or message cards
- optional monospace font option

The initial implementation does not need a full terminal emulator.

---

## 7.5 Gateway Connectivity

The application must connect to the existing OpenClaw gateway.

### Required gateway capabilities
Codex should design the integration behind an adapter interface because the exact gateway API may vary.

Minimum expected needs:
- gateway base URL configuration
- authentication token configuration if required
- health check or connection test
- start or identify an agent/session
- send a user message
- receive agent response
- fetch or reconstruct session state if supported
- error reporting

### Recommended approach
Create a dedicated `GatewayClient` abstraction:

- `ping()`
- `get_status()`
- `start_session(project_context, personality_context)`
- `send_message(session_handle, text)`
- `restore_session(session_handle or saved_state)`
- `end_session(session_handle)`
- `list_capabilities()`

If the gateway API differs from this shape, preserve this internal abstraction and adapt the implementation behind it.

---

## 7.6 Status and Metrics

The bottom status bar should show compact session information.

### Minimum fields
- active project
- active personality
- current session ID
- session state
- gateway connectivity state
- last activity time

### Nice-to-have fields if available
- agent name
- model/backend
- token count
- message count
- elapsed session duration

---

## 8. Data Model

## 8.1 Project

```python
class Project:
    id: str
    name: str
    description: str
    root_path: str
    default_personality_id: str | None
    created_at: datetime
    updated_at: datetime
```

## 8.2 Personality

```python
class Personality:
    id: str
    name: str
    description: str
    storage_path: str
    created_at: datetime
    updated_at: datetime
```

## 8.3 Session

```python
class SessionRecord:
    id: str
    project_id: str
    personality_id: str
    status: str   # active, suspended, archived, failed
    gateway_session_ref: str | None
    started_at: datetime
    last_activity_at: datetime
    summary_path: str | None
    transcript_path: str
    metadata_json: str | None
```

## 8.4 Session Event / Message

```python
class SessionEvent:
    id: str
    session_id: str
    timestamp: datetime
    event_type: str   # user, assistant, system, status, error, personality_change
    content: str
    metadata_json: str | None
```

---

## 9. Persistence Design

Use a hybrid persistence model:

### SQLite stores
- projects
- personalities metadata
- sessions metadata
- session indexes
- app settings
- optional message/event index

### Filesystem stores
- transcript files
- summary files
- personality markdown files
- exported session logs
- backups

### Recommended app data layout

```text
openclaw_gui/
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

---

## 10. Session Lifecycle Rules

### 10.1 Starting a new session
1. User selects project
2. User selects personality
3. App creates a local session record
4. App starts a gateway-backed session
5. App records any gateway session reference
6. Session becomes active in the GUI

### 10.2 Sending a message
1. User enters text in input box
2. Message is appended locally as a `user` event
3. App sends message through `GatewayClient`
4. App receives response
5. Response is appended as an `assistant` event
6. `last_activity_at` is updated

### 10.3 Switching projects
1. Save current session state
2. If active session exists, mark current one suspended
3. Load target project
4. Restore its latest restorable session or offer new session creation
5. Update top controls and status bar

### 10.4 Suspending a session
1. Flush transcript to disk
2. Persist metadata
3. Optionally capture/edit summary
4. Mark session as suspended
5. Disconnect or close gateway-side active handle if required

### 10.5 Restoring a session
1. Load session metadata and transcript
2. Rehydrate transcript in the center pane
3. Reconnect to gateway if supported
4. Otherwise start a new logical session and inject summary/context if needed
5. Mark as active

### 10.6 Restarting a session
1. Mark current session archived
2. Preserve old transcript/history
3. Create a new session under the same project
4. Use current personality unless user chooses otherwise
5. Clear live conversation pane
6. Mark new session active

---

## 11. UI Components

## 11.1 MainWindow
Contains:
- toolbar/top panel
- session panel
- status bar
- menu actions

## 11.2 ProjectSelector
Top dropdown for choosing active project

## 11.3 PersonalitySelector
Top dropdown for choosing active personality

## 11.4 SessionView
Middle panel widget containing:
- transcript area
- input box
- send button
- session banner/header

## 11.5 StatusBar
Bottom info strip

## 11.6 ProjectManagerDialog
CRUD interface for projects

Recommended fields:
- Name
- Description
- Root folder picker
- Optional default personality

## 11.7 PersonalityManagerDialog
CRUD interface for personalities

Recommended interface:
- personality list on left
- editor tabs on right:
  - SOUL.md
  - AGENTS.md
  - IDENTITY.md
  - metadata/preview

## 11.8 SessionHistoryDialog
Per-project session browser showing:
- session date
- status
- personality used
- last activity
- summary preview

---

## 12. Configuration

The app should support an application settings file for:
- gateway URL
- gateway auth token
- default data storage path
- UI theme preferences
- default personality
- transcript export preferences
- optional autosave interval

Example:

```json
{
  "gateway_url": "http://localhost:3000",
  "gateway_token": "",
  "data_root": "~/.openclaw_gui",
  "default_personality_id": "default",
  "autosave_seconds": 15
}
```

Sensitive values such as tokens should ideally be stored more securely than plain JSON if practical. For v1, a config file is acceptable if documented clearly.

---

## 13. Error Handling Requirements

The app must handle:
- gateway unavailable
- auth failures
- invalid project paths
- failed session start
- failed message send
- failed restore
- corrupt metadata/transcript files

### UX requirements for errors
- show user-facing message dialogs for major failures
- log technical details to a local app log
- do not lose the current transcript if the gateway fails
- keep local state recoverable whenever possible

---

## 14. Non-Functional Requirements

### Responsiveness
- GUI must remain responsive while waiting for gateway responses
- network calls must not block the UI thread

### Reliability
- autosave transcript and metadata regularly
- recover cleanly after app restart
- load prior projects/personality definitions on startup

### Maintainability
- separate gateway integration code from UI code
- separate persistence code from controller code
- keep model definitions centralized

### Portability
- target Linux first
- avoid platform-specific assumptions where possible
- leave packaging path open for Windows later

---

## 15. Suggested Package Structure

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
      gateway_models.py
      gateway_adapter.py
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
        status_bar.py
      dialogs/
        project_manager_dialog.py
        personality_manager_dialog.py
        session_history_dialog.py
        settings_dialog.py
  tests/
    test_projects.py
    test_personalities.py
    test_sessions.py
    test_gateway_client.py
```

---

## 16. Recommended MVP Scope

Codex should implement the following as the first milestone:

### MVP features
- Main window with 3-panel layout
- Project CRUD
- Personality CRUD
- Gateway settings dialog
- Connect/disconnect indicator
- Start session for selected project/personality
- Send messages and show responses
- Persist transcript locally
- Soft suspend session
- Restore previous session by project
- Restart session
- Status bar with basic metadata

### Explicitly defer from MVP unless easy
- multi-live-session parking
- advanced transcript search
- export/import packages
- token accounting dashboards
- personality version history
- rich markdown preview
- plugin system

---

## 17. Version 2 Enhancements

After MVP, likely next features should be:

- searchable transcript
- per-session summary editor
- project notes / scratchpad
- session branching/forking
- import/export personality bundles
- better transcript styling
- session filters and archive browser
- per-project preferred personality
- theme support
- agent capability display from gateway

---

## 18. Open Questions for Implementation

Codex should identify and resolve these during implementation:

1. What exact OpenClaw gateway endpoints are available?
2. Does the gateway natively support session persistence/restoration?
3. What authentication method is required?
4. Can the gateway return structured message events, or only raw responses?
5. How should prior context be re-injected if native restore is unavailable?
6. Does personality injection happen through files, prompt payload fields, or session bootstrap context?
7. Is there an existing OpenClaw concept of session/workspace/project that should map directly to the GUI’s model?

Codex should build the internal adapter layer so these answers do not force major UI rewrites.

---

## 19. Implementation Guidance for Codex

### Coding priorities
1. Build persistence and data models first
2. Build gateway adapter second
3. Build session controller third
4. Build GUI on top of those layers
5. Keep UI and gateway code cleanly separated

### Design constraints
- Do not hard-code gateway endpoints throughout the app
- Do not store only in-memory session state
- Do not let UI widgets own business logic directly
- Do not block the main Qt thread with network calls

### UX constraints
- Project switching must feel immediate
- Old sessions must remain browsable even after restart
- The active project and active personality must always be visible
- Session status must be easy to understand at a glance

---

## 20. Acceptance Criteria

The MVP is complete when all of the following are true:

1. The user can create, edit, and delete project references
2. The user can create, edit, and delete personalities composed of `SOUL.md`, `AGENTS.md`, and `IDENTITY.md`
3. The user can configure the OpenClaw gateway URL/token
4. The app can connect to the gateway and display connection state
5. The user can start a session for a selected project
6. The user can send messages and see responses in the center session pane
7. The app persists session transcript and metadata locally
8. Switching projects preserves/restores the appropriate session state
9. The user can suspend and later restore a session
10. The user can restart a project session without deleting historical session logs
11. The GUI always shows current project, personality, and session status
12. Restarting the GUI app does not lose previously saved projects, personalities, or session history

---

## 21. Suggested Future Polishing Ideas

Not required for MVP, but highly aligned with the product vision:

- session summary cards on restore
- “continue” vs “start fresh” choice when reopening a project
- personality badges or icons
- branch session / fork session action
- quick open recent projects
- transcript export to markdown or JSON
- integrated project notes panel
- gateway diagnostics panel

---

## 22. Final Recommendation

This application should be implemented as a **PySide6 desktop app with a modular gateway adapter, a local session controller, SQLite metadata storage, and filesystem-backed transcript/personality files**.

The first version should focus on:
- reliable project switching
- session persistence
- gateway-backed conversation flow
- reusable personality management

The product should behave like a **control cockpit for OpenClaw**, not a replacement for OpenClaw itself.
