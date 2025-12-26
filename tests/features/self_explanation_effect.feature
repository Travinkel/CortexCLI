Feature: Self-Explanation Effect
  As a Cognitive Engineer
  I want the CLI to prompt the user to generate self-explanations during problem-solving
  So that they can integrate new information with their existing mental models and identify knowledge gaps.

  Scenario: Prompting the user for a self-explanation
    Given the user is engaged in a problem-solving task
    When the system determines that a self-explanation is needed
    Then the user is prompted to "Explain this to yourself."
    And the user's explanation of "This makes sense now" is recorded
