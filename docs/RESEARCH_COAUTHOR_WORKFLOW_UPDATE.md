# Research Co-Author Workflow Update

## Purpose

This document explains the implementation work completed to move ScholarFlow closer to its intended product goal:

- a research co-author assistant
- capable of supporting literature review workflows
- capable of supporting original research workflows
- capable of helping plan, draft, and refine research papers using both external papers and the user's own research artifacts

This update focused on closing the biggest gap we identified:

- the app was stronger at literature assistance than at end-to-end original paper production
- the experimental/original-research path was only partially wired
- workflow identity was not preserved cleanly
- planning and drafting were split across overlapping frontend and backend paths

## What Was Wrong Before

Before this change set, the application had several mismatches between product goal and implementation:

- Project workflow identity was blurred.
  Literature review, experimental paper, and manuscript flows did not persist cleanly as distinct project kinds.

- Experimental project setup did not persist uploaded assets.
  The dashboard let users upload files during project creation, but those uploads were converted into placeholder frontend objects and never actually stored.

- Original research assets were not first-class in the active UI flow.
  The backend had a dedicated `ResearchAsset` model, but the main app mostly behaved as if all assets were generic lab uploads.

- Planning and drafting were split between local UI state and backend logic.
  Outlines were stored in `localStorage` in the studio sidebar, while the backend had draft persistence and planner/writer logic that was only partially used.

- Section drafting did not consistently receive section context and research asset context.
  That limited the app's ability to behave like a genuine co-author for methodology, results, and discussion writing.

## What Changed

### 1. Project Kind Is Now Preserved Explicitly

The system now preserves the actual project kind instead of collapsing everything into the older backend `mode` field.

Implemented changes:

- Added and persisted `project_kind` for projects.
- Derived a more appropriate `current_phase` from project kind.
- Fixed project creation so literature review, experimental, and manuscript projects are stored as distinct workflows.
- Fixed generated projects to use a real phase instead of the broken `PLANNING` enum reference.

Primary files:

- `backend/app/models/database.py`
- `backend/app/models/schemas.py`
- `backend/app/api/projects.py`
- `lib/api-client.ts`
- `App.tsx`

Why this matters:

- Reopening a project now better reflects the workflow the user originally selected.
- Experimental work no longer looks like a generic manuscript project after reload.

### 2. Research Assets Are Now First-Class

Original research inputs now have a real ingestion path instead of being treated as temporary placeholders.

Implemented changes:

- Added a dedicated backend service for research asset upload and ingestion.
- Added research asset upload and list endpoints.
- Extended the frontend API client to upload and fetch research assets.
- Merged lab assets and research assets into project hydration.
- Added `kind`, `researchAssetType`, `description`, `methodologyNote`, `sectionHint`, and `aiDescription` handling in the frontend asset model.

Primary files:

- `backend/app/services/research_asset_service.py`
- `backend/app/api/research.py`
- `backend/app/models/schemas.py`
- `lib/api-client.ts`
- `types.ts`

Why this matters:

- A user's own experiment data, figures, and code can now be treated as real drafting context.
- The app is better aligned with original paper writing, not just paper search and summarization.

### 3. Experimental Project Creation Now Uploads Real Inputs

The dashboard onboarding flow for experimental papers is now connected to the real backend upload path.

Implemented changes:

- Replaced placeholder dashboard asset objects with real pending uploads containing the actual `File`.
- Updated project creation so initial experimental assets are uploaded immediately after the project is created.
- Routed experimental assets to the research asset endpoint instead of the lab asset endpoint.

Primary files:

- `components/Dashboard.tsx`
- `App.tsx`

Why this matters:

- "Upload & Draft" now actually uploads and persists user materials during project setup.
- Experimental projects begin with usable original-research context instead of empty placeholders.

### 4. Studio Outline State Now Uses Backend Draft Persistence

The studio planning flow no longer depends on sidebar-only `localStorage` as the main source of truth.

Implemented changes:

- Sidebar now loads saved outline state from backend draft persistence.
- Generated outlines are normalized and stored as structured sections.
- Outline reset clears persisted draft outline through the backend.
- Outline generation now uses normalized sections returned from the backend.

Primary files:

- `backend/app/api/research.py`
- `components/SidebarRight.tsx`
- `lib/api-client.ts`

Why this matters:

- Plans survive reloads more reliably.
- The backend is now the canonical source of truth for outline state.
- Planning is less fragmented and easier to extend.

### 5. Drafting Is More Unified and Section-Aware

The drafting path now sends better context into the backend writer flow.

Implemented changes:

- Chat payloads now support `research_asset_ids`.
- Section drafting now sends both `research_asset_ids` and `current_section`.
- Rewrite actions also send section context and research asset context.
- The `/chat/draft-section` backend path already uses the shared writer and reviewer nodes, and the frontend now supplies the needed context more consistently.
- References sections are handled more safely in the studio flow instead of being treated like a normal prose section.

Primary files:

- `backend/app/api/chat.py`
- `backend/app/models/schemas.py`
- `components/SidebarRight.tsx`
- `lib/api-client.ts`
- `hooks/useStreaming.ts`

Why this matters:

- The writer can better distinguish between writing an introduction and writing results or methods.
- Original research assets can now influence drafting in the places they belong.
- The app behaves more like a co-author and less like a generic text generator.

### 6. Project Opening and Asset Hydration Are More Reliable

The app no longer depends entirely on the cached project list when opening a project.

Implemented changes:

- Opening a project now falls back to direct hydration from the backend even if the project is not in the current cached list.
- Project hydration now fetches both lab assets and research assets.
- Agent-triggered workflows split lab assets and research assets instead of sending one undifferentiated asset list.

Primary files:

- `App.tsx`
- `lib/api-client.ts`

Why this matters:

- Newly created projects open more reliably.
- Project context is more complete once a project is loaded.

### 7. Supporting Stability Fixes Were Included

Several enabling fixes were included because they directly affected this workflow slice.

Implemented changes:

- Fixed chat session creation contract so JSON `{ title }` works correctly.
- Fixed relevance score usage so downstream logic reads `relevance_score` correctly.
- Added schema drift protection for important SQLite columns.
- Hardened backend config parsing for `debug`.
- Narrowed TypeScript scope so local scratch files and `venv` do not break verification.
- Fixed agent store typings so the current app code type-checks cleanly.

Primary files:

- `backend/app/api/projects.py`
- `backend/app/agents/specialists.py`
- `backend/app/models/database.py`
- `backend/app/core/config.py`
- `stores/agentStore.ts`
- `tsconfig.json`

## User Experience Impact

### A. Creating an Experimental Paper

Before:

- The user could enter methodology/findings and upload files.
- The UI looked like those files were attached.
- The project was created, but those files were not actually persisted as original-research inputs.

After:

- Uploaded setup files are preserved as real research assets.
- The project opens with those assets available for later drafting and analysis.
- The app better understands that the user is creating an experimental/original research paper, not just a generic manuscript.

### B. Reopening a Project

Before:

- Project type could be misinterpreted after persistence.
- Studio outline state depended on sidebar local storage behavior.
- Asset hydration was incomplete.

After:

- Project kind is restored more accurately.
- The outline reloads from backend draft persistence.
- Research assets and lab assets both come back into project state.

### C. Drafting a Section

Before:

- Drafting was section-triggered from the UI, but the context sent to the backend was incomplete.
- The writer path did not consistently receive the user's research assets or the current section name.

After:

- Drafting passes selected papers, selected lab assets, selected research assets, and the active section name.
- The writing pipeline is better positioned to produce methods/results/discussion text grounded in the user's own work.

### D. Chatting With the Co-Author

Before:

- Co-author chat mostly reasoned over paper context and generic assets.

After:

- Co-author chat can carry research asset context separately from lab asset context.
- Rewrite actions also benefit from the same distinction.

### E. Resetting and Regenerating Plans

Before:

- Studio outline state was partially a frontend-local concern.

After:

- The saved plan can be cleared through backend draft persistence.
- Generated outlines and persisted outlines now live closer to one canonical model.

## Verification Completed

Completed verification:

- `tsc --noEmit` passed after the wiring changes.
- Backend smoke test passed for the modules touched in this workflow update.
  The smoke output confirmed:
  - config import worked
  - schema import worked
  - `ProjectKind.EXPERIMENTAL` resolved correctly
  - project kind maps to `ProjectPhase.ANALYSIS`

## Known Remaining Gaps

This update closes the biggest implementation mismatch, but it does not mean the product is now fully complete in every direction.

Important remaining gaps:

- The planner still receives a generic asset list for outline generation rather than a deeply structured research-asset reasoning context.
- Search coverage is still narrower than a full multi-source research assistant should be.
- Full backend app startup in this sandbox is still affected by restricted network access when embedding models try to download.
- A full production runtime pass in the browser is still worth doing after this implementation slice.

## Short Product Summary

After this update, ScholarFlow is materially closer to a real research co-author workflow.

It is now better at:

- preserving the user's intended project type
- treating original research materials as real first-class inputs
- reloading planning state from backend persistence
- passing the right context into section drafting
- using one more coherent planning and drafting path

In practical terms, the app now behaves less like:

- a literature review assistant with a separate writing surface

and more like:

- a research workspace that can support both literature-grounded writing and original paper production

