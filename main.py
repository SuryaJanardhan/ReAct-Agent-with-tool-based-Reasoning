import sys
import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Confirm
from rich.markdown import Markdown

from agent.core import run_agent, AgentEventHandler

# Load variables
load_dotenv()

console = Console()

class CLIAgentEventHandler(AgentEventHandler):
    """Custom event handler that prints formatted traces to the console using rich."""
    
    def on_plan_created(self, plan: str):
        console.print()
        console.print(Panel(
            Markdown(plan),
            title="[bold cyan]📋 Agent Execution Plan[/bold cyan]",
            border_style="cyan",
            expand=False
        ))
        console.print()

    def on_step_start(self, step: int, max_steps: int):
        if step > 0:
            console.print(f"\n[bold yellow]═══ Step {step}/{max_steps} ═══[/bold yellow]")
        else:
            console.print("[bold yellow]═══ Preparing Agent ═══[/bold yellow]")

    def on_thought(self, step: int, thought: str):
        console.print(Panel(
            thought,
            title=f"[bold blue]🤔 Thought (Step {step})[/bold blue]",
            border_style="blue",
            width=100
        ))

    def on_action(self, step: int, tool_name: str, tool_input: dict):
        table = Table(title="Action Details", border_style="magenta", show_header=True)
        table.add_column("Property", style="bold magenta")
        table.add_column("Value")
        
        table.add_row("Tool Name", tool_name)
        table.add_row("Arguments", str(tool_input))
        
        console.print(Panel(
            table,
            title=f"[bold magenta]⚙️ Executing Action (Step {step})[/bold magenta]",
            border_style="magenta",
            expand=False
        ))

    def on_hitl_request(self, tool_name: str, tool_input: dict) -> bool:
        console.print(Panel(
            f"[bold warning]Security Check:[/bold warning] The agent wants to execute a side-effect tool:\n"
            f"[bold]Tool:[/bold] {tool_name}\n"
            f"[bold]Arguments:[/bold] {tool_input}",
            title="[bold red]⚠️ Human-In-The-Loop Approval[/bold red]",
            border_style="red",
            width=80
        ))
        # Wait for user confirmation in standard input
        proceed = Confirm.ask("Do you want to allow this action?", default=False)
        return proceed

    def on_observation(self, step: int, observation: str):
        # Limit length of long observation outputs in console to keep it clean
        display_obs = observation
        if len(observation) > 1000:
            display_obs = observation[:1000] + "\n\n... (output truncated for readability) ..."
            
        console.print(Panel(
            display_obs,
            title=f"[bold green]👁️ Observation (Step {step})[/bold green]",
            border_style="green",
            width=100
        ))

    def on_complete(self, final_answer: str):
        console.print()
        console.print(Panel(
            final_answer,
            title="[bold green]🏁 Final Answer[/bold green]",
            border_style="bold green",
            box=Panel.box.DOUBLE,
            width=100
        ))
        console.print()

    def on_timeout(self, max_steps: int):
        console.print()
        console.print(Panel(
            f"Failed to complete the task within the maximum limit of {max_steps} steps.",
            title="[bold red]❌ Execution Timeout[/bold red]",
            border_style="bold red",
            width=80
        ))

    def on_error(self, error_msg: str):
        console.print(f"[bold red]Error encountered: {error_msg}[/bold red]", err=True)


def main():
    parser = argparse.ArgumentParser(description="Run the ReAct AI Agent from CLI.")
    parser.add_argument("task", type=str, nargs="?", help="The task for the AI agent to solve.")
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum execution steps.")
    parser.add_argument("--no-plan", action="store_true", help="Disable the preliminary planning phase.")
    
    args = parser.parse_args()
    
    task = args.task
    if not task:
        # Prompt user if task not provided in CLI args
        console.print("[bold cyan]Welcome to the ReAct AI Agent CLI![/bold cyan]")
        task = console.input("[bold]Enter your task prompt: [/bold]").strip()
        if not task:
            console.print("[red]Task prompt cannot be empty. Exiting.[/red]")
            sys.exit(1)
            
    # Run the agent
    event_handler = CLIAgentEventHandler()
    run_agent(
        task=task,
        max_steps=args.max_steps,
        enable_planning=not args.no_plan,
        event_handler=event_handler
    )


if __name__ == "__main__":
    main()
