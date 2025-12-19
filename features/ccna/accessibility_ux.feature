Feature: CCNA study flow is keyboard accessible and screen-reader friendly
  Background:
    Given the study UI is open on a CCNA atom

  Scenario: Keyboard navigation works across interaction types
    When the user presses Tab and Arrow keys
    Then focus moves predictably across interactive elements
    And pressing Enter submits the current response
    And pressing 1..4 selects MCQ options when available

  Scenario: Screen reader announces content and feedback
    Given the user navigates to the question
    Then the screen reader announces the question text and atom type
    And after submission it announces correctness and shows explanation text

  Scenario: Color contrast and non-color cues
    When correctness is shown
    Then success and error are conveyed with icons/text in addition to color
    And contrast ratios meet WCAG AA for text and UI components
