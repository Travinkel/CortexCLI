#!/usr/bin/env python
"""Generate MCQ, True/False, and Numeric atoms for CCNA modules."""

import sys
import json
import uuid
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from sqlalchemy import text
from src.db.database import engine
from config import get_settings
from rich.console import Console
from rich.progress import Progress

console = Console()

# Struggle modules to prioritize
STRUGGLE_MODULES = [5, 8, 9, 11, 2, 3, 7, 10, 4, 12, 13]


def extract_json_array(text: str) -> list:
    """Extract JSON array from LLM response text."""
    # Try markdown code block first
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Try parsing the extracted text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array with regex
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from: {text[:200]}...")

MCQ_PROMPT = """Generate 10 high-quality MCQ questions from this CCNA content.

RULES:
1. ONE fact per question
2. 4 options: 1 correct + 3 plausible distractors
3. Distractors must be plausible (same category/type as correct answer)
4. NO "All of the above" or "None of the above"
5. Question should be scenario-based when possible

OUTPUT FORMAT (JSON array):
[
  {{
    "question": "A technician needs to verify connectivity. Which command tests Layer 3?",
    "options": ["ping 192.168.1.1", "show mac address-table", "show vlan brief", "show interfaces"],
    "correct": 0,
    "explanation": "Ping tests Layer 3 (IP) connectivity between devices."
  }}
]

CONTENT:
{content}

Generate exactly 10 MCQ questions."""

TF_PROMPT = """Generate 10 True/False questions from this CCNA content.

RULES:
1. ONE fact per question
2. Statement must be clearly true or clearly false
3. Include explanation for why it's true or false
4. Avoid negatives that make the statement confusing

OUTPUT FORMAT (JSON array):
[
  {{
    "statement": "A switch forwards broadcast frames out all ports except the receiving port.",
    "answer": true,
    "explanation": "Switches flood broadcast frames to all ports in the same VLAN except the source port."
  }}
]

CONTENT:
{content}

Generate exactly 10 True/False questions."""

NUMERIC_PROMPT = """Generate 8 Numeric calculation questions from this CCNA content.

RULES:
1. Questions requiring specific numeric answers
2. Include subnet calculations, port numbers, address calculations
3. Provide the exact answer and acceptable tolerance
4. Include step-by-step explanation

OUTPUT FORMAT (JSON array):
[
  {{
    "question": "How many usable host addresses are available in a /26 subnet?",
    "answer": 62,
    "tolerance": 0,
    "explanation": "A /26 subnet has 6 host bits. 2^6 = 64 addresses. Subtract 2 for network and broadcast: 64 - 2 = 62 usable hosts."
  }}
]

CONTENT:
{content}

Generate exactly 8 Numeric questions."""


def generate_atoms(module_num: int) -> list[dict]:
    """Generate MCQ, TF, Numeric atoms for a module."""

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.ai_model)

    # Read source content
    source_path = Path(f"docs/source-materials/CCNA/CCNA Module {module_num}.txt")
    if not source_path.exists():
        console.print(f"[red]Module {module_num} source not found[/red]")
        return []

    content = source_path.read_text(encoding='utf-8')
    # Truncate to avoid token limits
    if len(content) > 15000:
        content = content[:15000]

    atoms = []

    # Generate MCQs
    try:
        response = model.generate_content(MCQ_PROMPT.format(content=content))
        mcqs = extract_json_array(response.text)
        for i, mcq in enumerate(mcqs):
            atoms.append({
                'id': str(uuid.uuid4()),
                'card_id': f'NET-M{module_num}-MCQ-{i+100:03d}',
                'atom_type': 'mcq',
                'front': mcq['question'],
                'back': json.dumps({
                    'options': mcq['options'],
                    'correct': mcq['correct'],
                    'explanation': mcq.get('explanation', '')
                }),
                'module': module_num,
            })
        console.print(f"  [green]MCQ: {len(mcqs)} generated[/green]")
    except Exception as e:
        console.print(f"  [red]MCQ error: {e}[/red]")

    # Generate True/False
    try:
        response = model.generate_content(TF_PROMPT.format(content=content))
        tfs = extract_json_array(response.text)
        for i, tf in enumerate(tfs):
            atoms.append({
                'id': str(uuid.uuid4()),
                'card_id': f'NET-M{module_num}-TF-{i+100:03d}',
                'atom_type': 'true_false',
                'front': tf['statement'],
                'back': json.dumps({
                    'answer': tf['answer'],
                    'explanation': tf.get('explanation', '')
                }),
                'module': module_num,
            })
        console.print(f"  [green]T/F: {len(tfs)} generated[/green]")
    except Exception as e:
        console.print(f"  [red]T/F error: {e}[/red]")

    # Generate Numeric
    try:
        response = model.generate_content(NUMERIC_PROMPT.format(content=content))
        nums = extract_json_array(response.text)
        for i, num in enumerate(nums):
            atoms.append({
                'id': str(uuid.uuid4()),
                'card_id': f'NET-M{module_num}-NUM-{i+100:03d}',
                'atom_type': 'numeric',
                'front': num['question'],
                'back': json.dumps({
                    'answer': num['answer'],
                    'tolerance': num.get('tolerance', 0),
                    'explanation': num.get('explanation', '')
                }),
                'module': module_num,
            })
        console.print(f"  [green]Numeric: {len(nums)} generated[/green]")
    except Exception as e:
        console.print(f"  [red]Numeric error: {e}[/red]")

    return atoms


def save_atoms(atoms: list[dict]):
    """Save generated atoms to database."""

    with engine.connect() as conn:
        for atom in atoms:
            try:
                conn.execute(
                    text('''
                        INSERT INTO learning_atoms (id, card_id, atom_type, front, back, is_quiz_question, quiz_question_type, quiz_question_metadata)
                        VALUES (:id, :card_id, :atom_type, :front, :back, :is_quiz, :quiz_type, :quiz_metadata)
                        ON CONFLICT (id) DO NOTHING
                    '''),
                    {
                        'id': atom['id'],
                        'card_id': atom['card_id'],
                        'atom_type': atom['atom_type'],
                        'front': atom['front'],
                        'back': atom['back'],
                        'is_quiz': True,
                        'quiz_type': atom['atom_type'],
                        'quiz_metadata': atom['back'],  # Store JSON in quiz_question_metadata
                    }
                )
            except Exception as e:
                console.print(f"[red]DB error for {atom['card_id']}: {e}[/red]")
        conn.commit()


def main():
    console.print("\n[bold cyan]Generating Quiz Atoms (MCQ, T/F, Numeric)[/bold cyan]")
    console.print("=" * 50)
    console.print(f"Target modules: {STRUGGLE_MODULES}")

    total_atoms = []

    with Progress() as progress:
        task = progress.add_task("Generating...", total=len(STRUGGLE_MODULES))

        for module_num in STRUGGLE_MODULES:
            console.print(f"\n[bold]Module {module_num}[/bold]")
            atoms = generate_atoms(module_num)
            total_atoms.extend(atoms)
            progress.advance(task)

    console.print(f"\n[bold]Total atoms generated: {len(total_atoms)}[/bold]")

    # Save to DB
    console.print("Saving to database...")
    save_atoms(total_atoms)

    console.print(f"[green]Done! {len(total_atoms)} quiz atoms saved.[/green]")

    # Summary
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT atom_type, COUNT(*) as cnt
            FROM learning_atoms
            WHERE atom_type IN ('mcq', 'true_false', 'numeric')
            GROUP BY atom_type
        ''')).fetchall()

    console.print("\n[bold]Quiz Atom Summary:[/bold]")
    for row in result:
        console.print(f"  {row.atom_type}: {row.cnt}")


if __name__ == "__main__":
    main()
