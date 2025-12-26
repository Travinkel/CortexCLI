Feature: CCNA Study Flow Accessibility
  Scenario: Keyboard and screen-reader accessibility
    Given the study UI is open on a CCNA atom
    When the user navigates through the UI using the keyboard
    Then all interactive elements are focusable and usable
