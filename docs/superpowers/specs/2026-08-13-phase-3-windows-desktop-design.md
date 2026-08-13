# Phase 3 Windows Desktop Design

## 1. Goal

Deliver LightCode as a Windows desktop application that runs on a machine without Node.js, Python, or pip. The desktop application must retain the current security model: FastAPI remains the only process permitted to access a registered workspace, call a model Provider, create ChangeSets, accept approval, and write a file.

The first release is an internal-test Windows installer. It is manually downloaded and installed, has no automatic update service, and is not code-signed. It must clearly be treated as unsuitable for public distribution until signing is added.

## 2. Decisions

| Area | Decision |
| --- | --- |
| Target | Windows only |
| Desktop shell | Electron with `electron-builder` and an NSIS installer |
| Python delivery | PyInstaller sidecar executable bundled in the application resources |
| First install | Start with a new desktop data directory; do not import development data |
| Upgrade | A later installer replaces program resources and preserves user data |
| Update delivery | Manual download and install only |
| Signing | Deferred; required before public distribution |
| Workspace selection | Native Windows folder picker, then backend-controlled registration |
| Selected workspace | Browse, chat, and single-file proposed edits with existing approval protocol |
| Provider key | Windows Credential Manager, never SQLite, logs, renderer persistence, or IPC responses |

## 3. What Electron and Packaging Mean

Electron supplies a desktop process around the existing web frontend. It owns native facilities which a web browser must not own: creating a window, opening a Windows directory picker, locating the application data folder, and starting/stopping the local backend.

Packaging is a release build operation, not a fork of the project. A package contains one immutable version of the Electron shell, Vue build output, Python sidecar executable, and their runtime dependencies. Source development remains unchanged:

```text
edit source -> test source -> build installer vX.Y.Z -> install/upgrade -> test installed app
```

New features are developed in this repository and released by building a later installer. They are not blocked by an earlier package. The strict rule is to separate program resources from user data:

```text
Application resources (replaced on upgrade)
  Electron main/preload code, Vue dist, sidecar executable

Windows user data (preserved on upgrade)
  SQLite database, workspace registration metadata, managed Skill packages, logs

Windows Credential Manager (preserved independently)
  Provider API keys
```

An installer must never store the database or skills under its own installation directory. It must not migrate or import the repository development database during first install.

## 4. Runtime Architecture

```text
Electron main process
  -> creates BrowserWindow with contextIsolation, sandbox, and nodeIntegration disabled
  -> starts bundled FastAPI executable on 127.0.0.1 with a random available port
  -> passes desktop data root, startup token, and loopback port through process environment
  -> opens the Windows directory picker
  -> exposes a minimal, typed preload IPC API
  -> stops the sidecar with bounded graceful shutdown then termination

Electron preload bridge
  -> exposes workspace.selectFolder() only
  -> validates request/response shape; never exposes Node, fs, shell, child_process, or raw ipcRenderer

Vue renderer
  -> homepage chat input and workspace popover
  -> invokes workspace.selectFolder()
  -> calls FastAPI REST/SSE only through the configured loopback API base

FastAPI sidecar
  -> validates startup token for desktop-only registration requests
  -> resolves and validates selected directories and persists server-private registrations
  -> owns WorkspaceGuard, Provider network traffic, SQLite, ChangeSets, approval, and writes
```

The sidecar listens only on `127.0.0.1`, not `0.0.0.0`. Electron generates a random per-launch token and does not put it in the renderer, URL, logs, SQLite, or SSE. The token may be passed from the main process to the sidecar and sent only by the trusted preload bridge using a narrowly scoped registration request. Registration responses remain path-free public DTOs.

## 5. Homepage and Workspace Selection

The existing `WorkspaceHomeView` currently loads registered workspaces and immediately redirects to the first one. Phase 3 replaces that behavior with a real home screen that borrows only the reference image's information structure, not its dark color scheme, TRAE naming, controls, or assets.

Visual rules:

- Preserve LightCode's approved warm-paper background, ink text, hand-drawn typography, fine borders, and compact utility controls.
- Center a `LightCode` heading and a focused chat composer.
- Place the current workspace picker in the composer footer at the lower left.
- Keep the recent-workspace picker as an anchored popover, not a centered modal.
- Use the existing product's icon approach and avoid copying TRAE controls or labels.

Flow:

1. First launch shows the chat composer and a disabled submit action because no workspace is selected.
2. The user opens the workspace picker and chooses `选择工作文件夹`.
3. The renderer asks the preload API; the Electron main process opens `dialog.showOpenDialog({ properties: ['openDirectory'] })`.
4. Cancellation changes nothing.
5. The selected absolute path travels only through trusted main-to-sidecar IPC. The renderer receives only a safe `RegisteredWorkspace` DTO.
6. The sidecar validates and stores the registration. On success, the popover remains open and shows the workspace in `最近`; it becomes the selected workspace.
7. The user remains on the homepage. Sending the first message creates a session for that workspace, submits the message, then navigates to `/workspace/:workspaceId/session/:sessionId`.

The workspace menu displays display name, enabled state, and policy version. It must not display absolute paths, drive letters, user names, paths from the source directory, or a raw picker result.

## 6. Dynamic Workspace Registration

The static `workspaces.json` model requires `targetFile`, which is incompatible with choosing an arbitrary source directory. The desktop registration model must not guess or solicit a target file at folder-selection time.

For desktop-created workspaces, store only server-private registration information: stable id, display name, canonical root, enabled state, supported policy, policy version, source marker, and timestamps. The existing model workflow later determines an editable existing UTF-8 file through `search_files` and `read_file`; the server independently generates a single-file ChangeSet and retains approval/hash/atomic-write checks.

This requires an SQLite schema migration or equivalent persistent registration store. It is a user-defined red-line operation and requires explicit confirmation immediately before implementation. The migration must include a safe upgrade path for legacy `workspaces.json` entries, a uniqueness policy for canonical roots, and no root-path fields in public API, logs, events, or error messages.

The initial policy permits only local canonical directories that are not symlinks, junctions, or other reparse points. All existing `WorkspaceGuard` checks remain authoritative after registration. Deleting or unregistering a workspace is deliberately out of the initial desktop scope.

## 7. Credential Persistence

`ProviderCredentialStore` already isolates callers from its implementation. Add a Windows Credential Manager implementation under that protocol and select it only in desktop-sidecar mode. It stores the API key in the OS secret store; profile metadata stays in the existing safe runtime storage only if it cannot reveal the complete provider URL or key. The GET/list API continues to return only the current safe summaries.

If Credential Manager is unavailable or fails, saving credentials fails closed with a fixed safe error. No fallback to SQLite, file storage, Electron settings, or renderer storage is permitted.

## 8. Build and Installer Pipeline

Development has three independently runnable processes: Vite, FastAPI, and Electron. Production builds are ordered as follows:

1. Run frontend tests/typecheck/build.
2. Run backend tests.
3. Build the Python sidecar with a reproducible PyInstaller specification.
4. Verify the sidecar starts on loopback with a temporary data root and passes its health check.
5. Build the Electron main/preload bundle and package Vue `dist` plus the sidecar executable with `electron-builder`.
6. Produce an NSIS installer named with application version and architecture.
7. Install into a clean Windows test user profile and verify first launch, folder selection, chat, candidate ChangeSet approval, quit/relaunch, and upgrade preservation.

The production sidecar must find application resources from the executable bundle but derive mutable locations only from explicit desktop environment variables. Development mode retains the current repository-relative defaults to avoid changing local developer workflow.

## 9. Release and Upgrade Teaching Notes

An NSIS installer is a Windows executable that copies the application into a standard install location, registers an uninstaller, and can replace an older application version. It does not by itself update users. Manual update means publishing a new installer, asking testers to close LightCode, and having them run it over the prior version.

Before every upgrade test, back up the desktop user-data directory. The upgrade acceptance test must prove:

1. installer v1 creates user data outside the install directory;
2. user registers a workspace and creates a chat session;
3. installer v2 replaces application resources;
4. registered workspace and chat metadata still load;
5. API keys are still present only through Credential Manager and are never displayed;
6. a failed sidecar launch produces a clear local recovery screen, not a blank window.

Code signing is deferred only for internal testing. Public release requires a Windows signing certificate, protected signing credentials, signed installer verification, SmartScreen testing, a privacy review, and documented support/rollback policy. Automatic updates are a later separate work package because they require an authenticated update source and signed artifact verification.

## 10. Non-goals

- macOS and Linux packages;
- auto-update, update download server, or background installers;
- public release without code signing;
- importing the repository's existing development database;
- arbitrary renderer access to files, shell, environment variables, process spawning, or Electron APIs;
- external command execution, package management, Git write operations, multi-file edits, deletion, rename, move, binary edits, or automatic approval;
- dynamic workspace removal and network workspaces.

## 11. Acceptance Criteria

1. A clean Windows machine without Python or Node can install and launch LightCode.
2. The homepage uses LightCode warm-paper design, shows a centered `LightCode` composer, and has a lower-left workspace picker.
3. The native folder picker is the only folder-selection mechanism; cancellation has no persistent effect.
4. A valid selected directory appears as a safe recent-workspace entry and enables direct homepage chat.
5. Absolute paths do not occur in renderer state, public API DTOs, SSE, logs, screenshots, or user-visible errors.
6. Selected workspaces can browse, chat, and produce only version-bound, user-approved single-file changes.
7. The sidecar is loopback-only and rejects unauthenticated registration requests.
8. Restart preserves desktop SQLite, workspace registrations, and Skill packages; Provider keys stay in Windows Credential Manager.
9. Manual upgrade preserves desktop user data while replacing executable resources.
10. Backend tests, frontend tests/typecheck/build, desktop unit tests, sidecar smoke test, clean-install E2E, restart E2E, and upgrade E2E pass.
