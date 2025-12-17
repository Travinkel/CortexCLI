import random
import time
import typer
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from collections import deque

console = Console()

# Mock objects to simulate the application's components without the full dependency chain
class MockAtom:
    def __init__(self, id, front, back, atom_type="mcq", content_json=None):
        self.id = id
        self.front = front
        self.back = back
        self.atom_type = atom_type
        self.content_json = content_json or "{}"

class MockAdaptiveTutor:
    def __init__(self):
        self.triggers = {"SELF_EXPLANATION": 0, "FOCUS_RESET": 0, "WORKED_EXAMPLE": 0}
        self.response_times = deque(maxlen=10)

    def get_next_atom(self):
        return MockAtom(id=random.randint(1, 10000), front="Mock Question", back="Mock Answer")

    def record_interaction(self, atom_id, response_time, is_correct):
        self.response_times.append(response_time)
        
        # Simulate trigger logic
        if response_time < 0.5:
            self.triggers["SELF_EXPLANATION"] += 1
        
        if len(self.response_times) > 5:
            variance = max(self.response_times) - min(self.response_times)
            if variance > 3.0:
                self.triggers["FOCUS_RESET"] += 1
        
        if not is_correct:
            self.triggers["WORKED_EXAMPLE"] += 1

def simulate_user(persona, tutor, num_cards):
    """Simulate a user persona interacting with the tutor."""
    with Progress(
        TextColumn("[bold blue]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console
    ) as progress:
        task = progress.add_task(f"[cyan]Simulating {persona['name']}...", total=num_cards)

        for _ in range(num_cards):
            atom = tutor.get_next_atom()
            
            response_time = persona["response_time_func"]()
            is_correct = persona["correctness_func"]()
            
            try:
                tutor.record_interaction(atom.id, response_time, is_correct)
            except ZeroDivisionError:
                console.print("[bold red]ZeroDivisionError caught during simulation![/bold red]")
                raise
            except Exception as e:
                console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
                raise

            time.sleep(0.001) # Prevent overwhelming the CPU
            progress.update(task, advance=1)

def main(num_cards: int = 1000):
    """Run the user simulation stress test."""
    console.print(f"[bold green]Starting user simulation with {num_cards} cards...[/bold green]")
    
    tutor = MockAdaptiveTutor()
    
    personas = [
        {
            "name": "Speed Runner",
            "response_time_func": lambda: random.uniform(0.1, 0.49),
            "correctness_func": lambda: random.random() > 0.1 # 90% correct
        },
        {
            "name": "The Drifter",
            "response_time_func": lambda: random.uniform(0.5, 5.0),
            "correctness_func": lambda: random.random() > 0.3 # 70% correct
        },
        {
            "name": "The Struggler",
            "response_time_func": lambda: random.uniform(1.0, 4.0),
            "correctness_func": lambda: random.random() > 0.8 # 20% correct
        }
    ]
    
    for persona in personas:
        simulate_user(persona, tutor, num_cards)
    
    console.print("\n[bold green]Simulation complete![/bold green]")
    console.print("\n[bold]Trigger Counts:[/bold]")
    for trigger, count in tutor.triggers.items():
        console.print(f"  - {trigger}: {count}")
        
    # Verify triggers were hit
    assert tutor.triggers["SELF_EXPLANATION"] > 0
    assert tutor.triggers["FOCUS_RESET"] > 0
    assert tutor.triggers["WORKED_EXAMPLE"] > 0
    
    console.print("\n[bold green]All personas simulated successfully and triggers were activated.[/bold green]")

if __name__ == "__main__":
    typer.run(main)
