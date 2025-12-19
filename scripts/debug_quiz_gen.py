#!/usr/bin/env python
"""Debug quiz generation."""

import sys
import json
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel(settings.ai_model)

# Read module 5 content
source_path = Path("docs/source-materials/CCNA/CCNA Module 5.txt")
content = source_path.read_text(encoding="utf-8")[:15000]

MCQ_PROMPT = """Generate 5 high-quality MCQ questions from this CCNA content.

RULES:
1. ONE fact per question
2. 4 options: 1 correct + 3 plausible distractors
3. Distractors must be plausible (same category/type as correct answer)
4. NO "All of the above" or "None of the above"
5. Question should be scenario-based when possible

OUTPUT FORMAT (JSON array):
[
  {
    "question": "A technician needs to verify connectivity. Which command tests Layer 3?",
    "options": ["ping 192.168.1.1", "show mac address-table", "show vlan brief", "show interfaces"],
    "correct": 0,
    "explanation": "Ping tests Layer 3 (IP) connectivity between devices."
  }
]

CONTENT:
{content}

Generate exactly 5 MCQ questions."""

try:
    response = model.generate_content(MCQ_PROMPT.format(content=content))
    text = response.text
    print("=== RAW RESPONSE (first 500 chars) ===")
    print(repr(text[:500]))

    # Parse
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    print("\n=== AFTER EXTRACTION ===")
    print(repr(text[:500]))

    mcqs = json.loads(text)
    print("\n=== PARSED MCQs ===")
    for i, mcq in enumerate(mcqs):
        print(f"{i}: keys={list(mcq.keys())}")
        print(f"   question={mcq.get('question', 'MISSING')[:50]}...")

except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
