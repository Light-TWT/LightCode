# Phase 3 Windows Desktop Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package LightCode as a Windows Electron application with a bundled FastAPI sidecar, safe native workspace registration, a warm-paper chat homepage, and manually installed versioned releases.

**Architecture:** Electron is only the native shell and trust broker. Vue remains a sandboxed renderer; FastAPI remains the authority for file access, model calls, registration validation, ChangeSets, approval, and writes. Mutable desktop data is outside the install directory, while immutable application resources are replaced by an installer upgrade.

**Tech Stack:** Electron, TypeScript, Vue 3, Vite, FastAPI, SQLite, PyInstaller, electron-builder, NSIS, Windows Credential Manager.

---

## Preconditions and Safety Gates

- [ ] Obtain explicit permission before adding Electron/PyInstaller/credential dependencies or changing package manifests.
- [ ] Obtain explicit permission before adding a SQLite workspace-registration migration or copying legacy static registrations into desktop storage.
- [ ] Do not begin any dynamic workspace deletion feature; it is out of scope.
- [ ] Do not alter `.env`, API keys, CI/CD configuration, or global system configuration.
- [ ] Preserve all existing Phase 1/2 tests and security behavior.

## File Map

| File | Change | Purpose |
| --- | --- | --- |
| `AGENTS.md` | Modify | Update Phase 3 scope and desktop security rules before code work. |
| `docs/architecture/lightcode-local-first-agent-design.md` | Modify | Record desktop delivery status and approved boundaries. |
| `docs/workspace-registration.md` | Modify | Define Electron-native registration and renderer path prohibition. |
| `electron/package.json` | Create | Electron, builder, test, and development scripts. |
| `electron/src/main.ts` | Create | Window lifecycle, sidecar lifecycle, native picker, restricted IPC. |
| `electron/src/preload.ts` | Create | Narrow typed context bridge. |
| `electron/src/sidecar.ts` | Create | Spawn, health probe, graceful shutdown, redacted errors. |
| `electron/src/ipc.ts` | Create | IPC channel constants and runtime validation. |
| `electron/electron-builder.yml` | Create | Windows NSIS packaging and extra resources. |
| `electron/tests/*.test.ts` | Create | Main/preload/sidecar unit tests. |
| `frontend/src/views/WorkspaceHomeView.vue` | Rewrite | Warm-paper homepage and first-message transition. |
| `frontend/src/components/WorkspacePicker.vue` | Create | Anchored recent-workspace popover. |
| `frontend/src/services/desktop.service.ts` | Create | Typed preload bridge adapter; no Electron global access. |
| `frontend/src/stores/workspace.store.ts` | Modify | Homepage selection and first-message session creation. |
| `frontend/src/types/agent.ts` | Modify | Safe desktop registration DTO only. |
| `frontend/src/contracts/*.ts` | Modify | Reject paths and unknown desktop DTO fields. |
| `backend/app/config/desktop.py` | Create | Explicit desktop data root/startup token/port configuration. |
| `backend/app/workspaces/registry.py` | Modify | Read static entries plus persisted desktop registrations. |
| `backend/app/services/workspace_registration.py` | Create | Canonical validation and private registration persistence. |
| `backend/app/api/routes.py` | Modify | Token-authenticated desktop registration endpoint. |
| `backend/app/db/database.py` | Modify | Idempotent desktop workspace registration schema migration. |
| `backend/app/services/credential_store.py` | Modify | Windows Credential Manager implementation under existing protocol. |
| `backend/app/main.py` | Modify | Desktop data-root wiring and loopback sidecar startup behavior. |
| `backend/pyinstaller.spec` | Create | Reproducible sidecar collection configuration. |
| `scripts/build-sidecar.ps1` | Create | Local reproducible PyInstaller build wrapper. |
| `scripts/test-desktop-install.ps1` | Create | Clean install/relaunch/upgrade verification harness. |
| `backend/tests/test_desktop_*.py` | Create | Registration, token, data root, and credential tests. |

## Task 1: Freeze Desktop Contract and Prove Existing Baseline

- [ ] Read `AGENTS.md`, Phase 1 safety contract, workspace registration specification, desktop design document, `main.py`, `registry.py`, and `credential_store.py`.
- [ ] Run backend baseline: `cd backend; python -m pytest -q`.
- [ ] Run frontend baseline: `cd frontend; npm run test; npm run typecheck; npm run build -- --emptyOutDir false`.
- [ ] Update `AGENTS.md`, architecture, and workspace registration docs to state: Electron has no direct workspace write authority; the renderer never receives a path; sidecar is loopback-only; user data is outside install resources; desktop registration supports browse/chat/single-file proposed edits only.
- [ ] Commit documentation-only boundary update: `git commit -m "docs: define phase 3 desktop boundaries"`.

## Task 2: Establish Desktop Data Root and Sidecar Configuration

- [ ] Write failing backend tests proving desktop mode rejects a relative data root, resolves database/skills/registration locations under one supplied absolute root, and does not expose that root in error messages.
- [ ] Add `backend/app/config/desktop.py` with immutable config loaded only from `LIGHTCODE_DESKTOP_DATA_DIR`, `LIGHTCODE_SIDECAR_TOKEN`, and `LIGHTCODE_SIDECAR_PORT`.
- [ ] Change `main.py` so desktop mode uses the supplied mutable root for database, skills, and registration state; preserve repository defaults outside desktop mode.
- [ ] Bind Uvicorn to `127.0.0.1` and the Electron-selected port in desktop mode.
- [ ] Run focused desktop config tests, then backend full suite.
- [ ] Commit: `git commit -m "feat: configure desktop sidecar data root"`.

## Task 3: Add Persisted Desktop Workspace Registration

**Safety gate:** obtain explicit approval for the SQLite migration before this task.

- [ ] Write failing tests for valid desktop registration, duplicate canonical root rejection, reparse-point rejection, disabled/unknown workspace rejection, token rejection, API/SSE/log path-leak checks, restart persistence, and legacy static registration compatibility.
- [ ] Add an idempotent `desktop_workspaces` table through the established inline migration mechanism. Store server-private canonical root and safe metadata separately; index canonical root uniquely.
- [ ] Implement `workspace_registration.py`: derive a safe display name from the folder name, create a stable server id, use `WorkspaceGuard`/filesystem canonical validation, persist only after validation, and return `RegisteredWorkspaceResponse` without path fields.
- [ ] Extend `WorkspaceRegistry` with static plus persisted source loading. Remove the dynamic-registration requirement for `targetFile`; retain existing static task behavior and let model proposals select a read-verified file later.
- [ ] Add one desktop-only route protected by the per-launch token. It accepts no browser-provided root path; Electron main sends the selected path through its own trusted channel to the sidecar. Reject all unexpected body fields.
- [ ] Run focused tests and backend full suite.
- [ ] Commit: `git commit -m "feat: register desktop workspaces safely"`.

## Task 4: Persist Provider Keys in Windows Credential Manager

- [ ] Write failing protocol-level tests for set/get/get-all/remove/clear, no-secret `repr`, unavailable-store fail-closed behavior, and API profile responses without key/base URL leaks.
- [ ] Add a Windows Credential Manager adapter behind `ProviderCredentialStore`; do not alter `ChatService` or `ModelOrchestrator` callers.
- [ ] In desktop mode, select the Credential Manager adapter in `main.py`; development mode retains `InMemoryProviderCredentialStore`.
- [ ] Verify provider profiles survive sidecar restart while database and log scans contain no secret.
- [ ] Run credential tests and backend full suite.
- [ ] Commit: `git commit -m "feat: store desktop provider credentials securely"`.

## Task 5: Build the Electron Security Boundary

- [ ] Add Electron-local dependencies only after manifest-change approval; lock them in `electron/package-lock.json`.
- [ ] Write failing main-process tests for BrowserWindow webPreferences, allowed IPC channels, picker cancellation, startup token non-exposure, sidecar failure behavior, and shutdown timeout behavior.
- [ ] Implement `main.ts`: create one BrowserWindow with `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, and no remote module; load Vite only in development and packaged Vue assets in production.
- [ ] Implement `preload.ts` with a single `lightcode.workspace.selectFolder()` function and a typed safe-result DTO. Do not expose `ipcRenderer`, Node globals, path strings, shell, filesystem, environment, or process methods.
- [ ] Implement `sidecar.ts`: choose a free loopback port, generate an in-memory token, spawn the bundled executable, poll health with a deadline, redacted failure output, and graceful shutdown followed by bounded force termination.
- [ ] Implement picker IPC: main invokes Windows `showOpenDialog`; cancellation returns `{ cancelled: true }`; success forwards only internally to sidecar registration and returns a safe workspace DTO to preload.
- [ ] Run Electron unit tests.
- [ ] Commit: `git commit -m "feat: add secure Electron shell"`.

## Task 6: Build the Warm-Paper Homepage and Workspace Picker

- [ ] Write failing Vue tests for no automatic redirect, disabled submit with no workspace, picker keyboard/focus behavior, cancellation, selected workspace persistence in local UI state, safe recent-item rendering, and first-message navigation.
- [ ] Add `desktop.service.ts`, which uses `window.lightcode` only after a guarded availability check and has no API for raw paths.
- [ ] Create `WorkspacePicker.vue` as an anchored popover: recent safe workspace rows, `选择工作文件夹`, loading/error states, Esc/outside click close, focus return, and no raw location text.
- [ ] Rewrite `WorkspaceHomeView.vue` using approved warm-paper styling. Center `LightCode`, a chat composer, workspace footer control, and compact suggested task chips; do not use the reference image's black palette, TRAE name, or copied controls.
- [ ] On selected workspace and first non-empty submit: create chat session, submit message, and navigate only after session id exists. Keep user on homepage after registration.
- [ ] Preserve existing `/workspace/:workspaceId` chat page and settings/skills routes.
- [ ] Run focused Vue tests, full frontend tests, typecheck, and build.
- [ ] Commit: `git commit -m "feat: add desktop workspace homepage"`.

## Task 7: Build the Python Sidecar

- [ ] Add PyInstaller only after dependency-change approval, pinned in the backend development build tooling.
- [ ] Write a sidecar smoke test that runs the collected executable with a temporary desktop root and verifies `/health`, loopback-only binding, and clean process exit.
- [ ] Create `backend/pyinstaller.spec` to collect FastAPI, Uvicorn, application modules, required package data, and no development test assets.
- [ ] Create `scripts/build-sidecar.ps1` that clears only generated build output, invokes the project virtual environment's PyInstaller, and writes a versioned artifact under ignored `electron/resources/sidecar/`.
- [ ] Verify the bundled executable can start without relying on repository working directory or a system Python installation.
- [ ] Commit: `git commit -m "build: bundle FastAPI desktop sidecar"`.

## Task 8: Produce the Windows Installer

- [ ] Configure `electron-builder.yml`: application id, product name, version metadata, NSIS target, architecture, Vue dist, bundled sidecar extra resource, and no user-data placement under install resources.
- [ ] Add package scripts for development, Electron tests, sidecar build, and Windows installer build.
- [ ] Create a clean-user-data installer test script: install v1, launch, register workspace, create chat session, close, relaunch, assert registration/session persistence, install v2, relaunch, and repeat assertions.
- [ ] Build an unsigned internal NSIS installer and verify product version, uninstaller, fresh install, restart, manual upgrade, and uninstall behavior. Uninstall must not silently delete user data without explicit product policy and confirmation.
- [ ] Run backend/frontend/Electron/sidecar/installer verification suite.
- [ ] Commit build metadata only after artifacts are excluded from git: `git commit -m "build: package Windows desktop installer"`.

## Task 9: Release Documentation and Final Evidence

- [ ] Update root README and backend/frontend/electron documentation with development mode, first install, manual upgrade, data location category, known unsigned warning, and recovery steps.
- [ ] Add a release checklist covering installer hashes, clean-machine install, restart, upgrade, data backup, secret scan, and signing gate before public publication.
- [ ] Verify no application/source log, event, DTO, screenshot fixture, or installer config contains a real API key, full provider URL, or absolute workspace path.
- [ ] Run final commands:

```powershell
cd backend; python -m pytest -q
cd ../frontend; npm run test; npm run typecheck; npm run build -- --emptyOutDir false
cd ../electron; npm run test; npm run build:win
```

- [ ] Record exact passing test counts, artifact version, clean-install evidence, restart evidence, and upgrade evidence in the release checklist.

## Rollout Sequence

1. Complete Tasks 1-2 without schema changes.
2. Stop for explicit migration approval before Task 3.
3. Complete Tasks 3-6 in a development-only Electron build.
4. Complete Tasks 7-8 only after all source-level tests pass.
5. Test installer manually on a clean Windows account, then perform one controlled manual upgrade.
6. Keep the package internal and unsigned. Create a separate signing/auto-update plan before public release.
