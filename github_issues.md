# GitHub Issues

## Refactoring

### [Refactor] Decouple Anki Field Mappings from Client Logic
**File:** `src/anki/anki_client.py`
**Description:** The `AnkiClient` currently hardcodes field names (e.g., "Card ID", "Front", "Back", "concept_id") and assumes a specific note type structure (likely "LearningOS-v2"). This makes the client brittle and unusable for users with different Anki note templates.
**Action:**
- Extract field mappings into `config.py` or a separate mapping configuration.
- Update `_map_note_to_card` and `upsert_card` to use these configurable mappings instead of hardcoded strings.

### [Refactor] Remove Lazy Imports in API Routers
**File:** `src/api/routers/*.py`
**Description:** Multiple routers (`sync_router.py`, `quiz_router.py`, etc.) import dependencies (like `NotionClient`, `SyncService`, `QuizQuestionAnalyzer`, `sqlalchemy` models) inside function bodies. While this avoids circular dependencies at module level, it hides import errors until runtime and complicates testing.
**Action:**
- Move imports to the top level where possible.
- If circular dependencies exist, resolve them using dependency injection or by restructuring the modules (e.g., moving models to a shared module).

### [Refactor] Centralize Grade Logic
**File:** `src/api/routers/quiz_router.py`
**Description:** The `list_questions` endpoint contains hardcoded logic for grade values (`{"A": 5, "B": 4, ...}`). This logic is duplicated or implicitly assumed in other parts of the system (like `MasteryCalculator`).
**Action:**
- Move this logic to a shared constant or Enum in `src/core/mastery.py` or `src/quiz/constants.py`.
- Use the shared definition in the router.

### [Refactor] Generalize Content Chunker
**File:** `src/processing/chunker.py`
**Description:** The `CCNAChunker` is highly coupled to specific CCNA content formats (regex patterns for Module 1, 4, 10, etc.). It should be renamed or refactored to allow for pluggable parsing strategies if other content types are to be supported.
**Action:**
- Rename `CCNAChunker` to `CCNAContentParser` or similar.
- Extract regex patterns to a configuration file or strategy pattern to allow easier updates for new content formats.

### [Refactor] Unify Configuration Management
**File:** `src/core/modes.py` vs `config.py`
**Description:** The CLI uses `CortexCliConfig` (loading from `config.toml`) while the API uses `Settings` (loading from `.env`). This dual configuration system is confusing and prone to inconsistencies.
**Action:**
- Merge configuration into a single source of truth.
- Prefer `.env` for secrets and environment-specific settings, and `config.toml` for user preferences, but access them through a unified interface.

## Security & Stability

### [Security] Safeguard Bulk Deck Deletion
**File:** `src/anki/anki_client.py`
**Description:** The `delete_deck_cards` method deletes *all* cards in a specified deck without any internal safeguards or "force" flags. An accidental call could lead to significant data loss.
**Action:**
- Add a `force=False` parameter to the method.
- Require `force=True` to proceed with deletion.
- Log a high-severity warning before execution.

### [Stability] Improve Exception Handling Granularity
**File:** `src/api/routers/sync_router.py`, `src/anki/anki_client.py`
**Description:** Several areas use broad `except Exception as e` clauses. This can mask specific errors (like `KeyboardInterrupt` or system exits) and makes debugging difficult.
**Action:**
- Replace broad exceptions with specific ones (e.g., `requests.RequestException`, `HTTPException`, `SQLAlchemyError`) where the failure mode is known.
- Keep broad exceptions only at the top-level entry points (like API route handlers) as a last resort, but ensure full stack traces are logged.

## Features

### [Feature] Expose Anki Sync via API
**File:** `src/api/routers/sync_router.py`
**Description:** The `sync_router.py` docstring notes that Anki push/pull operations are currently CLI-only. For a complete headless operation or UI integration, these should be exposed via the API.
**Action:**
- Implement `POST /api/sync/anki/push` and `POST /api/sync/anki/pull` endpoints.
- Reuse the logic from the CLI commands, likely by refactoring the core logic into a shared service if not already done.

### [Feature] Configurable Anki Note Type for Cloze
**File:** `src/anki/anki_client.py`
**Description:** The `upsert_card` method has logic to detect cloze deletions but warns if the note type doesn't seem to support it.
**Action:**
- Allow configuring a specific "Cloze Note Type" in settings, separate from the standard "Basic Note Type".
- Automatically switch to the cloze note type when `{{c` patterns are detected in the front text.

### [Feature] Implement CLI Import and Config Commands
**File:** `src/cli/cortex_cli.py`
**Description:** The `import` and `config --set` commands are currently stubs with no implementation.
**Action:**
- Implement `import_data` logic to read the export file and upload via `PlatformClient`.
- Implement `config` setting logic to update the local configuration (e.g., `.env` file).

### [Feature] Implement Mode Strategies
**File:** `src/core/modes.py`
**Description:** `ApiModeStrategy` and `OfflineModeStrategy` contain stub methods (e.g., `get_due_atoms` returns empty list).
**Action:**
- Implement the actual logic for fetching atoms and recording reviews in both API and Offline modes.
- Delegate to `PlatformClient` for API mode and a local database service for Offline mode.

## Bugs

### [Bug] Unused Diversity Weights in Question Selection
**File:** `src/quiz/quiz_pool_manager.py`
**Description:** The `select_diverse_questions` method accepts a `diversity_weights` argument but completely ignores it, implementing a simple round-robin selection strategy instead.
**Action:**
- Implement the weighted selection logic using the provided weights.
- Or remove the argument if the round-robin strategy is intended.

### [Bug] Inconsistent Seeding Logic
**File:** `src/quiz/quiz_pool_manager.py`
**Description:** Seeding logic is split between `_create_seed` and manual `random.seed` calls. `select_questions` skips seeding if `seed` is None, but `select_questions_for_quiz` constructs a string seed, leading to potential inconsistencies in reproducibility.
**Action:**
- Centralize all RNG operations to a helper method.
- Ensure consistent seed handling across all selection methods.

### [Bug] Hardcoded API URL in Reachability Check
**File:** `src/core/modes.py`
**Description:** `_check_api_reachable` hardcodes `api.rightlearning.io` instead of using the configured `base_url`.
**Action:**
- Update the check to parse and use `self.config.api.base_url`.
