import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import get_settings

console = Console()
settings = get_settings()

# Database setup
DATABASE_URL = settings.db_url
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

REPORT_FILE = Path("qa_report.md")

def _get_session():
    """Get a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def _check_null_content(session, progress, task_id):
    """Check for atoms with empty front or back content."""
    progress.update(task_id, description="[bold cyan]Checking for Null Content...[/bold cyan]")
    
    query = text("SELECT id, atom_type, front, back FROM learning_atoms WHERE front IS NULL OR back IS NULL OR front = '' OR back = ''")
    results = session.execute(query).fetchall()
    
    issues = []
    for row in results:
        issues.append({
            "id": row.id,
            "type": row.atom_type,
            "description": f"Atom has empty front or back content. Front: '{row.front or ''}', Back: '{row.back or ''}'"
        })
    return issues

def _check_orphaned_diagrams(session, progress, task_id):
    """Check for atoms with media_type='mermaid' but empty/null media_code."""
    progress.update(task_id, description="[bold cyan]Checking for Orphaned Diagrams...[/bold cyan]")
    
    query = text("SELECT id, atom_type, media_type, media_code FROM learning_atoms WHERE media_type = 'mermaid' AND (media_code IS NULL OR media_code = '')")
    results = session.execute(query).fetchall()
    
    issues = []
    for row in results:
        issues.append({
            "id": row.id,
            "type": row.atom_type,
            "description": f"Atom has media_type 'mermaid' but empty media_code."
        })
    return issues

def _check_bad_json(session, progress, task_id):
    """Check for atoms where content_json is corrupted or missing required keys."""
    progress.update(task_id, description="[bold cyan]Checking for Bad JSON...[/bold cyan]")
    
    query = text("SELECT id, atom_type, content_json FROM learning_atoms WHERE content_json IS NOT NULL")
    results = session.execute(query).fetchall()
    
    issues = []
    for row in results:
        atom_id = row.id
        atom_type = row.atom_type
        content_json_str = row.content_json
        
        if not content_json_str:
            continue

        try:
            content_data = json.loads(content_json_str)
        except json.JSONDecodeError:
            issues.append({
                "id": atom_id,
                "type": atom_type,
                "description": "content_json is not valid JSON."
            })
            continue

        # Specific checks based on atom_type
        if atom_type == "mcq":
            if "options" not in content_data or not isinstance(content_data["options"], list) or not content_data["options"]:
                issues.append({
                    "id": atom_id,
                    "type": atom_type,
                    "description": "MCQ atom missing 'options' key or 'options' is empty/not a list in content_json."
                })
            if "correct_index" not in content_data or not isinstance(content_data["correct_index"], int):
                issues.append({
                    "id": atom_id,
                    "type": atom_type,
                    "description": "MCQ atom missing 'correct_index' key or 'correct_index' is not an integer in content_json."
                })
        # Add more atom_type specific checks here as needed
        
    return issues

def _check_duplicate_detection(session, progress, task_id, threshold=0.95):
    """Flag atoms with identical front content (fuzzy match > threshold)."""
    progress.update(task_id, description="[bold cyan]Checking for Duplicate Content...[/bold cyan]")
    
    query = text("SELECT id, front FROM learning_atoms WHERE front IS NOT NULL AND front != '' ORDER BY id")
    results = session.execute(query).fetchall()
    
    issues = []
    checked_pairs = set()
    
    # Store fronts in a list for indexed access
    atom_fronts = [(row.id, row.front) for row in results]
    
    for i in range(len(atom_fronts)):
        id1, front1 = atom_fronts[i]
        for j in range(i + 1, len(atom_fronts)):
            id2, front2 = atom_fronts[j]
            
            # Ensure we don't check the same pair twice
            if (id1, id2) in checked_pairs or (id2, id1) in checked_pairs:
                continue
            
            # Simple normalization for comparison
            normalized_front1 = re.sub(r'\s+', '', front1).lower()
            normalized_front2 = re.sub(r'\s+', '', front2).lower()

            if not normalized_front1 or not normalized_front2:
                continue

            matcher = SequenceMatcher(None, normalized_front1, normalized_front2)
            if matcher.ratio() >= threshold:
                issues.append({
                    "id": f"{id1} & {id2}",
                    "type": "duplicate",
                    "description": f"Duplicate front content detected (Similarity: {matcher.ratio():.2f}).\n"
                                   f"  Atom {id1} Front: '{front1[:50]}...'\n"
                                   f"  Atom {id2} Front: '{front2[:50]}...'"
                })
                checked_pairs.add((id1, id2))
    return issues

def generate_report(all_issues):
    """Generate a markdown report of all identified issues."""
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# QA Report: Learning Atom Data Integrity\n\n")
        f.write(f"Generated on: {Path(__file__).name}\n\n")
        
        if not all_issues:
            f.write("## ✅ No issues found. Database is clean!\n")
            console.print(Markdown("## ✅ No issues found. Database is clean!"))
            return

        f.write("## ⚠️ Issues Found\n\n")
        console.print(Markdown("## ⚠️ Issues Found"))

        for check_name, issues in all_issues.items():
            if issues:
                f.write(f"### {check_name.replace('_', ' ').title()}\n\n")
                console.print(Markdown(f"### {check_name.replace('_', ' ').title()}"))
                
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Atom ID", style="cyan", no_wrap=True)
                table.add_column("Type", style="green")
                table.add_column("Description", style="white")
                
                for issue in issues:
                    f.write(f"- **Atom ID**: {issue['id']}, **Type**: {issue['type']}\n")
                    f.write(f"  **Description**: {issue['description']}\n\n")
                    table.add_row(str(issue['id']), issue['type'], issue['description'])
                console.print(table)
                f.write("---\n\n")
    
    console.print(f"\n[bold green]Report generated:[/bold green] {REPORT_FILE.absolute()}")

def main():
    console.print("[bold blue]Starting Data Integrity Audit...[/bold blue]")
    
    all_issues = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]"),
        console=console,
        transient=True,
    ) as progress:
        
        session_generator = _get_session()
        session = next(session_generator) # Get the session from the generator

        task1 = progress.add_task("Null Content Check", total=1)
        all_issues["null_content_check"] = _check_null_content(session, progress, task1)
        progress.update(task1, completed=1)

        task2 = progress.add_task("Orphaned Diagrams Check", total=1)
        all_issues["orphaned_diagrams_check"] = _check_orphaned_diagrams(session, progress, task2)
        progress.update(task2, completed=1)

        task3 = progress.add_task("Bad JSON Check", total=1)
        all_issues["bad_json_check"] = _check_bad_json(session, progress, task3)
        progress.update(task3, completed=1)

        task4 = progress.add_task("Duplicate Detection Check", total=1)
        all_issues["duplicate_detection_check"] = _check_duplicate_detection(session, progress, task4)
        progress.update(task4, completed=1)
        
        # Close the session
        try:
            session_generator.throw(StopIteration)
        except StopIteration:
            pass
            
    generate_report(all_issues)
    
    total_issues_count = sum(len(issues) for issues in all_issues.values())
    if total_issues_count > 0:
        console.print(f"\n[bold red]Audit finished with {total_issues_count} issues.[/bold red]")
        sys.exit(1)
    else:
        console.print("\n[bold green]Audit finished. No issues found![/bold green]")
        sys.exit(0)

if __name__ == "__main__":
    main()
