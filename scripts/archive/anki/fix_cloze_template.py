#!/usr/bin/env python3
"""
Fix the LearningOS-v2 Cloze template to use the correct cloze field.

The template was incorrectly using {{cloze:concept_id}} but the cloze
deletions ({{c1::...}}) are in the 'front' field.

This script updates the template to use {{cloze:front}}.
"""

import json

import requests


def anki_invoke(action, params=None):
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    response = requests.post("http://127.0.0.1:8765", json=payload, timeout=30)
    result = response.json()
    if result.get("error"):
        raise Exception(result["error"])
    return result.get("result")


# New templates using cloze:front
NEW_FRONT = """<div class="card">
  <main class="front">
    <div class="prompt">{{cloze:front}}</div>

    {{#back}}
    <details class="hint">
      <summary>Hint</summary>
      <div class="hint-body">{{back}}</div>
    </details>
    {{/back}}
  </main>
  <footer class="footer">
    {{#source}}<span class="pill">{{source}}</span>{{/source}}
  </footer>
</div>"""

NEW_BACK = """{{cloze:front}}
<hr class="divider" />

<div class="card back">
  {{#tags}}
  <span class="pill module">{{tags}}</span>
  {{/tags}}

  {{#source}}
  <span class="pill batch">{{source}}</span>
  {{/source}}

  {{#back}}
  <div class="explanation">
    <strong>Answer:</strong> {{back}}
  </div>
  {{/back}}
</div>"""


def main():
    print("Fixing LearningOS-v2 Cloze template...")

    # Get current templates
    templates = anki_invoke("modelTemplates", {"modelName": "LearningOS-v2 Cloze"})
    current_front = templates.get("Cloze", {}).get("Front", "")

    if "cloze:concept_id" in current_front:
        print("  Found bug: template uses cloze:concept_id instead of cloze:front")

        # Update the template
        anki_invoke(
            "updateModelTemplates",
            {
                "model": {
                    "name": "LearningOS-v2 Cloze",
                    "templates": {"Cloze": {"Front": NEW_FRONT, "Back": NEW_BACK}},
                }
            },
        )
        print("  Fixed! Now using cloze:front")
    elif "cloze:front" in current_front:
        print("  Template already uses cloze:front - no fix needed")
    else:
        print(f"  Unknown template format: {current_front[:100]}")

    # Verify
    templates = anki_invoke("modelTemplates", {"modelName": "LearningOS-v2 Cloze"})
    if "cloze:front" in templates.get("Cloze", {}).get("Front", ""):
        print("\nVerified: Template is now correct!")

        # Test adding a note
        print("\nTesting note creation...")
        note = {
            "deckName": "CCNA::ITN::Module 1::Test",
            "modelName": "LearningOS-v2 Cloze",
            "fields": {
                "concept_id": "test-fix-123",
                "front": "Test after fix: {{c1::42}} is the answer",
                "back": "42",
                "tags": "test",
                "source": "test",
                "metadata_json": json.dumps({"test": True}),
            },
            "tags": ["test"],
        }

        try:
            result = anki_invoke("addNote", {"note": note})
            print(f"  Success! Added note ID: {result}")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()
