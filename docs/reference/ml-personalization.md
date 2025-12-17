# ML Personalization for Adaptive Learning

## Overview

This document describes how to use collected signals to build a personalized learning model that optimizes content presentation for each learner's unique cognitive profile.

## Available Signal Sources

### 1. Response Signals (`atom_responses`)
| Signal | Description | ML Use |
|--------|-------------|--------|
| `response_time_ms` | Time to answer | Optimal difficulty calibration |
| `is_correct` | Answer correctness | Learning curve modeling |
| `streak_before/after` | Consecutive correct | Momentum tracking |
| `session_id` | Session grouping | Session fatigue analysis |
| `pomodoro_number` | Position in session | Attention span modeling |

### 2. Atom Performance (`learning_atoms`)
| Signal | Description | ML Use |
|--------|-------------|--------|
| `anki_stability` | FSRS memory stability | Retention prediction |
| `anki_ease_factor` | Difficulty rating | Optimal challenge calibration |
| `anki_lapses` | Forgetting count | Weak point identification |
| `nls_correct_count` | Total correct | Atom effectiveness |
| `nls_incorrect_count` | Total incorrect | Atom difficulty rating |
| `dont_know_count` | Skip count | Prerequisite gaps |
| `quality_score` | Content quality | Atom filtering |

### 3. Mastery State (`learner_mastery_state`)
| Signal | Description | ML Use |
|--------|-------------|--------|
| `combined_mastery` | Overall concept mastery | Learning progress |
| `dec_score` | Declarative knowledge | Content type selection |
| `proc_score` | Procedural knowledge | Practice type selection |
| `app_score` | Application knowledge | Transfer learning |
| `review_count` | Study intensity | Effort tracking |

### 4. Session Analytics (`ccna_study_sessions`)
| Signal | Description | ML Use |
|--------|-------------|--------|
| Session length | Duration patterns | Optimal session length |
| Start time | Time-of-day | Circadian optimization |
| Atoms completed | Throughput | Pacing optimization |

## ML Model Architecture

### Feature Engineering

```python
class LearnerFeatures:
    """Features extracted for each learner."""

    # Response patterns
    avg_response_time: float        # Baseline speed
    response_time_variance: float   # Consistency
    accuracy_by_atom_type: dict     # {mcq: 0.8, tf: 0.6, ...}
    accuracy_over_session: list     # Fatigue curve

    # Learning velocity
    stability_growth_rate: float    # How fast memory strengthens
    optimal_difficulty: float       # Ease factor sweet spot
    forgetting_rate: float          # Memory decay parameter

    # Preferences (inferred)
    best_atom_types: list           # Ranked by effectiveness
    optimal_session_length: int     # Before fatigue drops accuracy
    optimal_review_interval: float  # Personalized spacing

    # Cognitive profile
    encoding_strength: float        # Initial learning quality
    retrieval_reliability: float    # Recall consistency
    discrimination_ability: float   # Similar item differentiation
```

### Model 1: Atom Sequencing Optimizer

**Objective**: Maximize learning efficiency by selecting optimal next atom.

**Input Features**:
- Current learner state (mastery, fatigue, time in session)
- Candidate atom features (type, difficulty, recency, concept relation)
- Historical performance on similar atoms

**Output**: Probability of successful recall for each candidate atom

**Algorithm**: Gradient boosting or neural ranking model

```python
def predict_recall_probability(
    learner: LearnerFeatures,
    atom: AtomFeatures,
    context: SessionContext
) -> float:
    """Predict probability of correct recall."""
    features = [
        learner.accuracy_by_atom_type.get(atom.type, 0.5),
        atom.stability / 30.0,  # Normalized stability
        atom.ease_factor,
        context.atoms_completed / context.target_atoms,  # Session progress
        context.accuracy_this_session,
        learner.response_time_variance,  # Cognitive load indicator
    ]
    return model.predict(features)
```

### Model 2: Content Presentation Optimizer

**Objective**: Choose best presentation format for each concept.

**Input Features**:
- Concept characteristics (complexity, abstractness, prerequisite depth)
- Learner cognitive profile
- Historical effectiveness by format for this learner

**Output**: Ranked list of presentation formats (MCQ, T/F, Cloze, Flashcard, etc.)

```python
def rank_atom_types(
    learner: LearnerFeatures,
    concept: ConceptFeatures
) -> list[str]:
    """Rank atom types by expected effectiveness."""
    effectiveness = {}
    for atom_type in ['mcq', 'true_false', 'cloze', 'flashcard']:
        # Combine learner preference with concept suitability
        learner_score = learner.accuracy_by_atom_type.get(atom_type, 0.5)
        concept_score = concept.suitability_by_type.get(atom_type, 0.5)
        effectiveness[atom_type] = learner_score * 0.6 + concept_score * 0.4
    return sorted(effectiveness.keys(), key=lambda x: -effectiveness[x])
```

### Model 3: Optimal Difficulty Calibrator

**Objective**: Keep learner in optimal challenge zone (not too easy, not too hard).

**Target**: 85% accuracy (Zone of Proximal Development)

```python
def calculate_optimal_difficulty(learner: LearnerFeatures) -> float:
    """Calculate ideal difficulty level for current session."""
    # Use response time as cognitive load proxy
    if learner.avg_response_time < 3000:  # < 3 seconds
        # Learner is finding it easy, increase difficulty
        return min(1.0, learner.current_difficulty + 0.1)
    elif learner.avg_response_time > 15000:  # > 15 seconds
        # Struggling, decrease difficulty
        return max(0.3, learner.current_difficulty - 0.1)
    else:
        # Optimal zone
        return learner.current_difficulty
```

## Data Collection Requirements

### New Signals to Collect

1. **Confidence Rating** (after each answer)
   ```python
   # Add to atom_responses
   confidence_level: int  # 1-5 scale (optional self-report)
   ```

2. **Hint Usage**
   ```python
   # Track hint requests
   hint_requested: bool
   hint_count: int
   ```

3. **Time of Day**
   ```python
   # Already have responded_at, extract hour for circadian analysis
   hour_of_day = response.responded_at.hour
   ```

4. **Session Context**
   ```python
   # Add to session tracking
   session_fatigue_index: float  # Computed from accuracy decay
   cognitive_load_estimate: float  # From response time trends
   ```

### Signal Aggregation Queries

```sql
-- Learner profile generation
WITH learner_stats AS (
    SELECT
        user_id,
        -- Response patterns
        AVG(response_time_ms) as avg_response_time,
        STDDEV(response_time_ms) as response_time_variance,
        AVG(CASE WHEN is_correct THEN 1 ELSE 0 END) as overall_accuracy,

        -- Breakdown by atom type
        AVG(CASE WHEN la.atom_type = 'mcq' AND ar.is_correct THEN 1 ELSE 0 END) as mcq_accuracy,
        AVG(CASE WHEN la.atom_type = 'true_false' AND ar.is_correct THEN 1 ELSE 0 END) as tf_accuracy,

        -- Session patterns
        COUNT(DISTINCT session_id) as total_sessions,
        AVG(session_atoms) as avg_atoms_per_session
    FROM atom_responses ar
    JOIN learning_atoms la ON ar.atom_id = la.id
    GROUP BY user_id
)
SELECT * FROM learner_stats;
```

## Implementation Phases

### Phase 1: Signal Collection (Current)
- [x] Response logging
- [x] FSRS integration
- [x] NCDE diagnosis
- [ ] Confidence ratings
- [ ] Hint tracking

### Phase 2: Feature Engineering
- [ ] Learner profile generation
- [ ] Atom effectiveness metrics
- [ ] Session fatigue curves
- [ ] Time-of-day patterns

### Phase 3: Model Training
- [ ] Collect baseline data (1000+ responses)
- [ ] Train recall prediction model
- [ ] Train presentation optimizer
- [ ] A/B test against random baseline

### Phase 4: Online Learning
- [ ] Deploy models to production
- [ ] Continuous model updates
- [ ] Personalization loop closure

## Quick Wins (No ML Required)

Before full ML, implement rule-based personalization:

1. **Atom Type Preference**: Track accuracy by type, prefer high-accuracy types
2. **Difficulty Ladder**: Start easy, increase after 3 consecutive correct
3. **Fatigue Detection**: If accuracy drops 20% from session start, suggest break
4. **Time-of-Day**: Track best performance hours, suggest optimal study times

```python
def get_personalized_atoms(learner_id: str, count: int) -> list[Atom]:
    """Rule-based personalization without ML."""
    stats = get_learner_stats(learner_id)

    # Prefer atom types with higher accuracy
    preferred_types = sorted(
        stats.accuracy_by_type.items(),
        key=lambda x: -x[1]
    )[:3]

    # Get atoms matching preferences
    atoms = (
        session.query(Atom)
        .filter(Atom.type.in_([t for t, _ in preferred_types]))
        .filter(Atom.ease_factor.between(
            stats.optimal_difficulty - 0.5,
            stats.optimal_difficulty + 0.5
        ))
        .order_by(Atom.anki_due_date)
        .limit(count)
    )
    return atoms
```

## Metrics for Success

| Metric | Baseline | Target |
|--------|----------|--------|
| Session accuracy | 70% | 85% |
| Session completion rate | 60% | 80% |
| 7-day retention | 40% | 60% |
| Time to mastery | 30 days | 20 days |
| Learner satisfaction | 3.5/5 | 4.5/5 |
