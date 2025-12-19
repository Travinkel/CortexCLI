"""
Targeted Atom Generation for Struggling Areas.

Generates specific atom types for weak modules identified from practice exam.
Focuses on: Numeric (calculation), Parsons (CLI), Matching (discrimination).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from config import get_settings
from src.content.generation.prompts import get_prompt, get_system_prompt

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

OUTPUT_DIR = Path("outputs/generated_atoms")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_module_content(module_num: int) -> str:
    """Load CCNA module content from text file."""
    ccna_dir = Path("docs/source-materials/CCNA")
    module_file = ccna_dir / f"CCNA Module {module_num}.txt"
    if module_file.exists():
        return module_file.read_text(encoding="utf-8")
    return ""


async def generate_atoms(atom_type: str, section_id: str, content: str, count: int = 5) -> list[dict]:
    """Generate atoms using Gemini API."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction=get_system_prompt()
    )

    prompt = get_prompt(atom_type, section_id, content[:15000])  # Limit content

    try:
        response = await model.generate_content_async(prompt)
        text = response.text

        # Extract JSON from response
        import re
        match = re.search(r"```json\s*([\s\S]*?)```", text)
        if match:
            json_str = match.group(1).strip()
        else:
            match_list = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
            if match_list:
                json_str = match_list.group(0)
            else:
                json_str = text

        atoms = json.loads(json_str)
        if isinstance(atoms, dict) and "atoms" in atoms:
            atoms = atoms["atoms"]
        return atoms[:count] if isinstance(atoms, list) else []

    except Exception as e:
        print(f"  Error generating {atom_type} for {section_id}: {e}")
        return []


async def main():
    print("=" * 60)
    print("TARGETED ATOM GENERATION FOR STRUGGLING AREAS")
    print("=" * 60)

    all_atoms = []

    # =========================================================================
    # MODULE 5: Binary/Hex Calculations (NUMERIC)
    # =========================================================================
    print("\n[1/4] Module 5 - Number Systems (Numeric Atoms)")
    content_5 = load_module_content(5)
    if content_5:
        print("  Generating binary/decimal conversion atoms...")
        atoms = await generate_atoms("numeric", "5.1", content_5[:8000], count=10)
        for a in atoms:
            a["module"] = 5
            a["atom_type"] = "numeric"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} numeric atoms")
        time.sleep(3)  # Rate limit

    # =========================================================================
    # MODULE 11: Subnetting Calculations (NUMERIC)
    # =========================================================================
    print("\n[2/4] Module 11 - IPv4 Subnetting (Numeric Atoms)")
    content_11 = load_module_content(11)
    if content_11:
        print("  Generating subnetting calculation atoms...")
        atoms = await generate_atoms("numeric", "11.4", content_11[:8000], count=15)
        for a in atoms:
            a["module"] = 11
            a["atom_type"] = "numeric"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} numeric atoms")
        time.sleep(3)

    # =========================================================================
    # MODULE 2: CLI Commands (PARSONS)
    # =========================================================================
    print("\n[3/4] Module 2 - IOS Commands (Parsons Problems)")
    content_2 = load_module_content(2)
    if content_2:
        print("  Generating CLI sequence ordering problems...")
        atoms = await generate_atoms("parsons", "2.3", content_2[:8000], count=10)
        for a in atoms:
            a["module"] = 2
            a["atom_type"] = "parsons"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} parsons atoms")
        time.sleep(3)

    # =========================================================================
    # MODULE 3: OSI/Encapsulation (MATCHING)
    # =========================================================================
    print("\n[4/4] Module 3 - OSI Model (Matching Atoms)")
    content_3 = load_module_content(3)
    if content_3:
        print("  Generating OSI layer discrimination atoms...")
        atoms = await generate_atoms("matching", "3.2", content_3[:8000], count=10)
        for a in atoms:
            a["module"] = 3
            a["atom_type"] = "matching"
        all_atoms.extend(atoms)
        print(f"  Generated {len(atoms)} matching atoms")

    # =========================================================================
    # SAVE RESULTS
    # =========================================================================
    output_file = OUTPUT_DIR / "targeted_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"COMPLETE: Generated {len(all_atoms)} atoms")
    print(f"Saved to: {output_file}")
    print("=" * 60)

    # Summary by type
    by_type = {}
    for a in all_atoms:
        t = a.get("atom_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\nBreakdown:")
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    asyncio.run(main())
