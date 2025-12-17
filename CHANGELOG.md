# Changelog

All notable changes to Cortex are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

#### 3D Visual Engine

- **Volumetric ASCII art**: New `src/delivery/cortex_visuals.py` provides 3D panel rendering with depth shading using gradient characters (`░▒▓█`).
- **Animated brain**: `src/delivery/animated_brain.py` implements pulsing cyberbrain boot sequence with neural activation effects using asciimatics.
- **Adaptive frame selection**: Three frame sets (full 3D, compact 3D, simple) selected based on terminal dimensions.
- **3D UI components**: `create_3d_panel()`, `create_holographic_header()`, `create_depth_meter()`, `create_isometric_cube()`, `render_3d_menu()`.
- **Color theme**: Pink cyberbrain aesthetic with configurable `CORTEX_THEME` dictionary.

#### Socratic Tutoring System (Migration 021)

- **Interactive dialogue**: `src/cortex/socratic.py` implements LLM-powered Socratic tutoring when learners say "I don't know".
- **Progressive scaffolding**: Five levels from pure Socratic questions (level 0) to full answer reveal (level 4).
- **Dialogue persistence**: `socratic_dialogues` and `dialogue_turns` tables record all tutoring sessions.
- **Resolution tracking**: Tracks outcomes (self_solved, guided_solved, gave_up, revealed) for analytics.
- **Gap detection**: Identifies prerequisite knowledge gaps during dialogue for targeted remediation.
- **Cognitive signals**: Detects confusion, progress, stuck states, and breakthrough moments.

#### Dynamic Struggle Tracking (Migration 018-020)

- **Real-time updates**: `update_struggle_from_ncde()` updates struggle weights after each NCDE diagnosis.
- **Audit trail**: `struggle_weight_history` table records all weight changes with timestamps.
- **Trend analysis**: 7-day trend tracking (improving/declining/stable) per module.

### Fixed

#### Database Schema (Migration 017)

- **Missing FK constraint**: Added `learning_path_sessions.target_cluster_id` foreign key reference to `concept_clusters(id)`.
- **View table references**: Updated `v_learner_progress`, `v_suitability_mismatches`, and `v_session_analytics` to use correct canonical table names (`concepts`, `learning_atoms`, `concept_clusters`).

#### Struggle Map

- **Missing modules**: Added M1 (Networking Today, low severity) and M6 (Data Link Layer, medium severity) to `struggle_weights` table.
- **Complete coverage**: All 17 CCNA modules (M1-M17) now appear in the struggle heatmap.
- **Sort order**: Struggle details table now sorted by module number (M1-M17) for consistent display.

#### Mastery Calculation

- **Score range bug**: Fixed bug in `src/study/study_service.py:1484` where `mastery_score` was incorrectly multiplied by 100.
  - **Before**: Values like `67.50` (percentage)
  - **After**: Values like `0.675` (0.0-1.0 range)
- **Data cleanup**: Corrupted mastery values reset to `0.0` to allow recalculation.
- **Documentation**: Clarified that `mastery_score` uses 0.0-1.0 range throughout.

#### UX Improvements

- **Parsons problems**: Removed misleading default prompt that appeared before user interaction.
- **Question panel**: Reduced height for better vertical space utilization.

### Changed

#### Mastery Formula Documentation

- Clarified the two-tier mastery calculation system:
  - **Concept-level**: `combined_mastery = (review_mastery x 0.625) + (quiz_mastery x 0.375)`
  - **Section-level (CCNA)**: `mastery_score = AVG(LEAST(anki_stability / 30.0, 1.0))`
- Documented alignment with right-learning project research for the 62.5%/37.5% weighting.

---

## Schema Version History

| Migration | Description |
|-----------|-------------|
| 021 | Socratic dialogue tables |
| 020 | Struggle weight history |
| 019 | Transfer testing |
| 018 | Dynamic struggle weights / Remediation notes |
| 017 | Fix FK constraints and view table references |
| 016 | Quarantine table for invalid atoms |
| 015 | Struggle weights table |
| 014 | Neuromorphic Cortex schema |
| 013 | Rename tables to canonical names |

---

## Technical Notes

### Mastery Score Range Convention

All mastery scores use the **0.0-1.0 range**:

| Value | Interpretation |
|-------|----------------|
| 0.0 | No mastery / new learner |
| 0.40 | Foundation level |
| 0.65 | Integration level |
| 0.85 | Mastery level |
| 1.0 | Perfect mastery |

Do not multiply by 100 when storing. Display code may convert to percentage for UI.

### Table Name Conventions

Post-migration 013, use canonical names:

| Legacy Name | Canonical Name |
|-------------|----------------|
| `clean_atoms` | `learning_atoms` |
| `clean_concepts` | `concepts` |
| `clean_concept_clusters` | `concept_clusters` |

Views and new code should use canonical names exclusively.
