"""Check available Anki note types and their fields."""
import requests
import json

def anki_invoke(action, params=None):
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params
    response = requests.post("http://127.0.0.1:8765", json=payload, timeout=30)
    result = response.json()
    if result.get("error"):
        raise Exception(result["error"])
    return result.get("result")

# List all note types
print("=== AVAILABLE NOTE TYPES ===")
model_names = anki_invoke("modelNames")
for name in sorted(model_names):
    print(f"  {name}")

# Check fields for specific types
print("\n=== FIELDS FOR EACH MODEL ===")
for name in ['Basic', 'Cloze', 'LearningOS-v2', 'LearningOS-v2 Cloze']:
    if name in model_names:
        fields = anki_invoke("modelFieldNames", {"modelName": name})
        print(f"\n{name}:")
        for f in fields:
            print(f"  - {f}")
    else:
        print(f"\n{name}: NOT FOUND")
