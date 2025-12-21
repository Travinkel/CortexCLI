Feature: CCNA interaction types behave as expected
  Background:
    Given the atom deck is loaded

  Scenario: MCQ exposes options and correct answer
    Given an MCQ atom exists
    Then it has 4 options and one correct_index
    And the correct answer text is non-empty

  Scenario: Numeric atom has a correct value and optional tolerance
    Given a numeric atom exists
    Then it has a correct_value
    And the rendered back includes the value and units when present

  Scenario: Ordering atom defines options and a correct order
    Given an ordering atom exists
    Then it exposes options and a non-empty correct_order
    And the back shows the ordered sequence text

  Scenario: Labeling atom defines targets and label bank
    Given a labeling atom exists
    Then it has targets with ids and labels
    And it may include a diagram_ref

  Scenario: Hotspot atom defines correct regions or ids
    Given a hotspot atom exists
    Then it provides hotspots and optional discrete choices

  Scenario: Case scenario atom defines multi-step decisions
    Given a case_scenario atom exists
    Then it includes steps with prompts and options
    And a summary is provided
