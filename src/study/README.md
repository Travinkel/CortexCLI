# src/study/ - Legacy Study Services

**Status: DEPRECATED - Migration in Progress**

This module contains legacy study services that are being superseded by the new
`src/cortex/` modular architecture.

## Migration Path

| Legacy (src/study/)      | New (src/cortex/)           | Status       |
|--------------------------|------------------------------|--------------|
| `study_service.py`       | `cortex/session.py`          | In Progress  |
| `quiz_engine.py`         | `cortex/atoms/*.py`          | Migrated     |
| `mastery_calculator.py`  | `adaptive/mastery_calculator.py` | Migrated |

## Files in This Module

### `study_service.py` (1,832 lines) - DEPRECATED

Large monolithic service that handles:
- Quiz generation and serving
- Mastery tracking
- CCNA section management
- Session state

**Migration**: Functionality is being decomposed into:
- `src/cortex/session.py` - Interactive study sessions
- `src/cortex/atoms/` - Modular atom type handlers (7 types)
- `src/adaptive/learning_engine.py` - Adaptive sequencing
- `src/db/models/adaptive.py` - Mastery state models

### `quiz_engine.py` - DEPRECATED

Legacy quiz handling replaced by:
- `src/cortex/atoms/mcq.py` - Multiple choice
- `src/cortex/atoms/true_false.py` - True/False
- `src/cortex/atoms/parsons.py` - Parsons problems
- `src/cortex/atoms/matching.py` - Matching
- `src/cortex/atoms/numeric.py` - Numeric answers

### Other Files

- `interleaver.py` - Topic interleaving (still in use)
- `mastery_calculator.py` - Migrated to src/adaptive/
- `pomodoro_engine.py` - Break scheduling (still in use)
- `retention_engine.py` - Retention tracking (still in use)

## When to Use Legacy vs New

**Use src/cortex/ (new) when:**
- Building new study session features
- Adding new atom types
- Implementing NCDE cognitive diagnosis
- Creating interactive CLI experiences

**Use src/study/ (legacy) only when:**
- Maintaining backward compatibility
- Fixing bugs in existing functionality
- The new equivalent doesn't exist yet

## Deprecation Timeline

1. **Current**: Both systems coexist, new features use cortex/
2. **Phase 2**: study_service.py functions progressively replaced
3. **Phase 3**: Legacy imports deprecated with warnings
4. **Phase 4**: Legacy code removed

## Questions?

See `src/cortex/README.md` for the new architecture documentation.
