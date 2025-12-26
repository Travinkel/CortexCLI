Feature: 144-Type Atom Generation via 1M Context Window

  Scenario: Derive a complete and diverse taxonomy of learning atoms
    Given the AI Studio "gemini-1.5-pro" model is active
    And the current textbook chapter is loaded into the 1M context buffer
    When the 144-type atom generation is triggered
    Then a complete and diverse taxonomy of learning atoms is derived
