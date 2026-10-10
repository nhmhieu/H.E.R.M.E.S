import click
from rich.console import Console
from rich.table import Table

from hermes.engines.academic_calc import calculate_gpa, check_academic_warning
from hermes.engines.scheduler import generate_study_plan
from hermes.security.guardrails import sanitize_input

console = Console()


@click.group()
def cli():
    """H.E.R.M.E.S CLI - HCMUS Educational Resource & Mentoring Expert System."""
    pass


@cli.command()
def info():
    """Print system version and status."""
    console.print("[bold blue]H.E.R.M.E.S[/bold blue] v0.1.0")
    console.print("System Status: [green]Online[/green]")


@cli.command()
@click.option(
    "--grades",
    "-g",
    multiple=True,
    type=(float, int),
    help="Grade and credits, e.g. -g 8.5 4 -g 7.0 3",
)
@click.option(
    "--semester",
    type=int,
    default=1,
    help="Current semester for warning check",
)
def gpa(grades, semester):
    """Calculate GPA and check academic standing."""
    if not grades:
        console.print("[yellow]No grades provided. Use -g <grade> <credits>[/yellow]")
        return

    grades_dict_list = [
        {"grade": grade, "credits": credits} for grade, credits in grades
    ]
    gpa_result = calculate_gpa(grades_dict_list)
    console.print(
        f"Calculated GPA (Scale 10): [bold green]{gpa_result['gpa_scale_10']}[/bold green]"
    )
    console.print(
        f"Calculated GPA (Scale 4): [bold green]{gpa_result['gpa_scale_4']}[/bold green]"
    )

    if semester > 0:
        warning_info = check_academic_warning(gpa_result["gpa_scale_4"], semester)
        status_color = "red" if warning_info["is_warning"] else "green"
        console.print(
            f"Academic Status: [bold {status_color}]{warning_info['status']}[/bold {status_color}]"
        )


@cli.command()
@click.option(
    "--subject",
    "-s",
    multiple=True,
    type=(str, int, int),
    help="Subject name, credits, priority (higher is more important)",
)
@click.option(
    "--hours", "-h", type=float, required=True, help="Available daily study hours"
)
@click.option("--days", "-d", type=int, required=True, help="Days left until exams")
def plan(subject, hours, days):
    """Generate a study schedule."""
    if not subject:
        console.print(
            "[yellow]No subjects provided. Use -s <name> <credits> <priority>[/yellow]"
        )
        return

    subjects_list = [
        {"name": name, "credits": credits, "priority": priority}
        for name, credits, priority in subject
    ]

    schedule = generate_study_plan(subjects_list, hours, days)

    if not schedule:
        console.print("[red]Failed to generate schedule. Check inputs.[/red]")
        return

    table = Table(title=f"Study Plan for Next {days} Days ({hours} hrs/day)")
    table.add_column("Subject", style="cyan")
    table.add_column("Total Hours Allocated", justify="right", style="magenta")
    table.add_column("Daily Hours", justify="right", style="green")

    for item in schedule:
        table.add_row(
            item["subject"], str(item["allocated_hours"]), str(item["daily_hours"])
        )

    console.print(table)


@cli.command()
@click.argument("query")
def ask(query):
    """Ask H.E.R.M.E.S a question (routes via guardrails)."""
    is_safe, msg = sanitize_input(query)
    if not is_safe:
        console.print(f"[bold red]Security Block:[/bold red] {msg}")
        return

    console.print(f"[green]Processing safe query:[/green] {query}")
    console.print(
        "[italic yellow](Routing to LLM/RAG engines not fully implemented yet.)[/italic yellow]"
    )


if __name__ == "__main__":
    cli()
