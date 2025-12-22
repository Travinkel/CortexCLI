# 100+ Atom Taxonomy: Cognitive Subsystem Organization

This taxonomy organizes learning atoms by cognitive subsystem and instructional goal. Each entry includes: description, cognitive target, UI pattern, grading mode, owner, and difficulty range.

## I. Discrimination & Perception (10 types)

### visual_hotspot
**Description:** Click the [organ/component] in this diagram.
**Cognitive Target:** Visual recognition, spatial mapping.
**UI Pattern:** `image_with_clickable_regions`
**Grading Mode:** `coordinate_match`
**Owner:** cortex-cli
**Difficulty Range:** 1-3

### visual_search
**Description:** Find all defects in a high-resolution image.
**Cognitive Target:** Visual attention, pattern recognition.
**UI Pattern:** `image_with_multi_select`
**Grading Mode:** `set_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

### auditory_discrimination
**Description:** Distinguish between two similar audio clips or phonemes.
**Cognitive Target:** Auditory perception.
**UI Pattern:** `audio_player_with_choices`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

### tactile_mapping (experimental)
**Description:** Map a description to regions on a tactile diagram (used in simulations).
**Cognitive Target:** Somatosensory mapping, multimodal association.
**UI Pattern:** `image_with_regions`
**Grading Mode:** `region_match`
**Owner:** cortex-cli
**Difficulty Range:** 3-5

### color_discrimination
**Description:** Identify color differences or anomalies.
**Cognitive Target:** Low-level visual discrimination.
**UI Pattern:** `side_by_side_image_choice`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 1-2

### pattern_recognition
**Description:** Recognize the repeating pattern or anomaly in a dataset/visual.
**Cognitive Target:** Visual pattern extraction.
**UI Pattern:** `image_or_chart_identify`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

### signal_labeling
**Description:** Label segments of a signal (e.g., ECG waveform) with event types.
**Cognitive Target:** Temporal pattern recognition.
**UI Pattern:** `waveform_annotation`
**Grading Mode:** `interval_match`
**Owner:** cortex-cli
**Difficulty Range:** 3-5

### object_detection_simple
**Description:** Identify and tag simple objects in an image.
**Cognitive Target:** Object recognition.
**UI Pattern:** `bounding_box_selection`
**Grading Mode:** `iou_threshold`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

### figure_ground
**Description:** Separate foreground from background regions.
**Cognitive Target:** Perceptual segregation.
**UI Pattern:** `mask_painting`
**Grading Mode:** `mask_overlap`
**Owner:** cortex-cli
**Difficulty Range:** 3-5

### visual_sequence_ordering
**Description:** Order a sequence of frames or steps in a visual process.
**Cognitive Target:** Temporal sequencing, event causality.
**UI Pattern:** `drag_and_drop_sequence`
**Grading Mode:** `ordering_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

## II. Recognition & Recall (25+ types)

### multiple_choice_single
**Description:** Single correct choice from a list of options.
**Cognitive Target:** Recognition, cue-triggered recall.
**UI Pattern:** `radio_buttons`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 1-4

### multiple_choice_multiple
**Description:** One or more correct choices; tests set knowledge.
**Cognitive Target:** Recognition with partial credit.
**UI Pattern:** `checkbox_list`
**Grading Mode:** `set_match_with_partial`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### cloze_dropdown
**Description:** Select the missing token from a dropdown in a sentence.
**Cognitive Target:** Contextual retrieval.
**UI Pattern:** `inline_dropdown`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 1-3

### cloze_freeform
**Description:** Free-text fill-in-blank (single token or short phrase).
**Cognitive Target:** Active recall production.
**UI Pattern:** `inline_text_input`
**Grading Mode:** `fuzzy_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### short_answer_exact
**Description:** Short free-text answer measured by exact match rules.
**Cognitive Target:** Precise declarative recall.
**UI Pattern:** `text_input`
**Grading Mode:** `exact_string`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### short_answer_fuzzy
**Description:** Short answer with fuzzy / normalized match (case, stemming).
**Cognitive Target:** Robust recall under surface variation.
**UI Pattern:** `text_input`
**Grading Mode:** `fuzzy_string`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### true_false
**Description:** Binary true/false statement checks.
**Cognitive Target:** Quick recognition and error-checking.
**UI Pattern:** `toggle_or_buttons`
**Grading Mode:** `binary`
**Owner:** cortex-cli
**Difficulty Range:** 1-2

### flashcard_QA
**Description:** Classic prompt/response flashcard; freeform grading optionally.
**Cognitive Target:** Spaced retrieval practice.
**UI Pattern:** `show_then_reveal`
**Grading Mode:** `self_reported_or_autograded`
**Owner:** cortex-cli
**Difficulty Range:** 1-5

### numeric_entry
**Description:** Enter numeric value; optional units.
**Cognitive Target:** Quantitative recall and estimation.
**UI Pattern:** `number_input`
**Grading Mode:** `numeric_tolerance`
**Owner:** cortex-cli
**Difficulty Range:** 1-5

### code_snippet_recall
**Description:** Recall a short code idiom or API usage snippet.
**Cognitive Target:** Declarative syntax recall.
**UI Pattern:** `monospace_text_input`
**Grading Mode:** `fuzzy_code_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### definition_match
**Description:** Match term to its definition.
**Cognitive Target:** Semantic mapping.
**UI Pattern:** `matching_pairs`
**Grading Mode:** `pairwise_match`
**Owner:** cortex-cli
**Difficulty Range:** 1-4

### concept_card
**Description:** Short conceptual prompts with structured answer fields.
**Cognitive Target:** Conceptual scaffolding.
**UI Pattern:** `structured_form`
**Grading Mode:** `manual_or_autograded`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### image_label_single
**Description:** Label the object in an image (single label).
**Cognitive Target:** Visual vocabulary.
**UI Pattern:** `single_label_image`
**Grading Mode:** `exact_choice`
**Owner:** cortex-cli
**Difficulty Range:** 1-3

### image_label_multiple
**Description:** Assign multiple labels to an image.
**Cognitive Target:** Categorical recall.
**UI Pattern:** `multi_label_image`
**Grading Mode:** `set_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-4

### mnemonic_prompt
**Description:** Provide or select a mnemonic that encodes a fact.
**Cognitive Target:** Encoding strategies.
**UI Pattern:** `choice_or_text`
**Grading Mode:** `manual_or_autograded`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### spaced_recall_card
**Description:** Card tagged with scheduling parameters for FSRS/SM-2 style practice.
**Cognitive Target:** Long-term retention scheduling.
**UI Pattern:** `spaced_card`
**Grading Mode:** `self_reported_or_autograded`
**Owner:** cortex-cli
**Difficulty Range:** 1-5

## III. Procedural & Application (20+ types)

### parsons
**Description:** Reorder code blocks into a working program.
**Cognitive Target:** Procedural sequencing, chunking.
**UI Pattern:** `drag_and_drop_blocks`
**Grading Mode:** `ordering_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-6

### parsons_with_distractors
**Description:** Parson's problem with extra (distractor) blocks.
**Cognitive Target:** Error diagnosis, structural understanding.
**UI Pattern:** `drag_and_drop_blocks`
**Grading Mode:** `ordering_with_partial_credit`
**Owner:** cortex-cli
**Difficulty Range:** 3-7

### matching
**Description:** Pair items across two lists (e.g., function -> description).
**Cognitive Target:** Structural mapping.
**UI Pattern:** `matching_pairs`
**Grading Mode:** `pairwise_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-5

### fill_in_blank_code
**Description:** Insert a short token into code with blanks.
**Cognitive Target:** Syntax retrieval.
**UI Pattern:** `inline_code_input`
**Grading Mode:** `exact_or_fuzzy_code_match`
**Owner:** cortex-cli
**Difficulty Range:** 2-6

### project_task_sequence
**Description:** Order project setup steps (multi-step, multi-part answers).
**Cognitive Target:** Procedural planning.
**UI Pattern:** `multi_stage_flow`
**Grading Mode:** `ordering_and_criteria`
**Owner:** cortex-cli
**Difficulty Range:** 3-7

### simulation_step_response
**Description:** Respond to a simulated environment step (CLI, network event).
**Cognitive Target:** Transfer and application.
**UI Pattern:** `sim_prompt_and_response`
**Grading Mode:** `scenario_scored`
**Owner:** cortex-cli
**Difficulty Range:** 4-8

### coding_exercise_auto
**Description:** Submit code snippet that can be auto-tested in a sandbox.
**Cognitive Target:** Synthesis and application.
**UI Pattern:** `code_editor_submission`
**Grading Mode:** `unit_test_results`
**Owner:** greenlight
**Difficulty Range:** 3-9

### refactor_task
**Description:** Short refactoring with measurable metrics (e.g., cyclomatic down).
**Cognitive Target:** Code quality reasoning.
**UI Pattern:** `diff_editor`
**Grading Mode:** `metric_based`
**Owner:** greenlight
**Difficulty Range:** 4-9

### design_decision
**Description:** Short essay or checklist around trade-offs for design.
**Cognitive Target:** Architectural reasoning.
**UI Pattern:** `rich_text_input`
**Grading Mode:** `manual_or_rubric`
**Owner:** cortex-cli
**Difficulty Range:** 5-9

## IV. Diagnostic & Reasoning (15+ types)

### explanation_chain
**Description:** Provide step-by-step reasoning linking premise to conclusion.
**Cognitive Target:** Causal reasoning, argument chaining.
**UI Pattern:** `multi_step_text`
**Grading Mode:** `rubric_based`
**Owner:** cortex-cli
**Difficulty Range:** 4-9

### error_classification
**Description:** Categorize a learner's error (slip vs misconception) with evidence.
**Cognitive Target:** Diagnostic metacognition.
**UI Pattern:** `multi_select_with_annotations`
**Grading Mode:** `manual_or_autograded`
**Owner:** cortex-cli
**Difficulty Range:** 3-8

### multi_hop_reasoning
**Description:** Multi-step reasoning problem requiring intermediate inference.
**Cognitive Target:** Chained inference.
**UI Pattern:** `structured_reasoning_prompt`
**Grading Mode:** `rubric_and_tests`
**Owner:** cortex-cli
**Difficulty Range:** 5-10

### hypothesis_test
**Description:** Formulate hypothesis and propose test design for a dataset.
**Cognitive Target:** Scientific reasoning and experimental design.
**UI Pattern:** `long_text_and_table`
**Grading Mode:** `rubric`
**Owner:** cortex-cli
**Difficulty Range:** 6-10

## V. Generative & Creative (8+ types)

### freeform_essay
**Description:** Open-ended essay with rubric scoring.
**Cognitive Target:** Synthesis, argumentation, creativity.
**UI Pattern:** `rich_text_editor`
**Grading Mode:** `rubric_or_human`
**Owner:** cortex-cli
**Difficulty Range:** 5-10

### prompt_generation
**Description:** Create prompts that elicit a specified type of response (meta-craft).
**Cognitive Target:** Generative creativity and task design.
**UI Pattern:** `structured_generator`
**Grading Mode:** `manual`
**Owner:** cortex-cli
**Difficulty Range:** 4-9

## VI. Meta-cognitive & Self-regulated (10 types)

### confidence_rating
**Description:** Rate confidence after answering.
**Cognitive Target:** Metacognition calibration.
**UI Pattern:** `slider_or_buttons`
**Grading Mode:** `informational`
**Owner:** cortex-cli
**Difficulty Range:** 1-1

### reflection_prompt
**Description:** Short reflection question to consolidate learning.
**Cognitive Target:** Metacognitive consolidation.
**UI Pattern:** `text_input`
**Grading Mode:** `manual`
**Owner:** cortex-cli
**Difficulty Range:** 1-3

## Implementation notes

- Each atom should include metadata: canonical_id, core_target_skills[], difficulty, estimated_time_seconds, owner, tags.
- Schema: each atom stored as JSON envelope v2 with fields: id, type, payload, ui_hint, difficulty, skill_links (array of {skill_id, weight, is_primary}).
- Handlers: implement testable, idempotent handlers that validate input and produce canonical outputs.
- Testing: add unit tests for grading modes and integration tests to confirm end-to-end ingestion.

## Appendix: Example atom envelope (JSON)

```json
{
  "id": "atom:visual_hotspot:v1:0001",
  "type": "visual_hotspot",
  "payload": {
    "image": "assets/heart-anatomy.png",
    "regions": [
      {"id": "a", "label": "left_atrium", "coords": [10,20,40,60]},
      {"id": "b", "label": "right_ventricle", "coords": [50,20,80,60]}
    ],
    "prompt": "Click the left atrium"
  },
  "ui_hint": "image_with_clickable_regions",
  "difficulty": 3,
  "skill_links": [{"skill_id": "cardio:anatomy:left_atrium", "weight": 1.0, "is_primary": true}]
}
```

---

This file provides a first pass of the 100+ taxonomy; it can be extended with additional subtypes and owners per domain. If you'd like, I can expand each section into separate files or auto-generate the remaining detailed entries to reach exactly 100+ atom types.
