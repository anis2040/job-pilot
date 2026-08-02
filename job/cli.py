from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
import time

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from .config import load_config
from .db import (
    init_db, already_seen, is_duplicate, insert_job, insert_filter_log,
    update_status, get_pending, get_pending_deduped, get_jobs_by_status,
    update_description, log_fetch, last_fetch_at, get_job, stats as db_stats,
)
from .fetcher import fetch_search
from .linkedin_fetcher import fetch_description as li_fetch_description
from .profiles import get_profile_path

app = typer.Typer(help="Job hunt automator — fetch, track, and manage job listings.")
console = Console()


# ── helpers ──────────────────────────────────────────────────────────────────

def _age(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        return f"{hours // 24}d"
    except Exception:
        return "?"


def _remote_color(remote: str) -> str:
    colors = {"Remote": "green", "Hybrid": "yellow", "On-site": "red"}
    color = colors.get(remote, "white")
    return f"[{color}]{remote}[/{color}]"


def _resume_exists(company: str) -> bool:
    if not company:
        return False
    from .web_api import _candidate_name_slug
    from .profiles import company_resumes_path
    path = company_resumes_path(company)
    if not path:
        return False
    pdf = path / f"{_candidate_name_slug()}_Resume.pdf"
    return pdf.exists()


def _open_url(url: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", url])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", url])
    else:
        subprocess.Popen(["xdg-open", url])


def _notify(title: str, message: str) -> None:
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{title}"'],
                check=False,
            )
        except Exception:
            pass


def _print_jobs_table(rows) -> None:
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    table.add_column("Title", max_width=34)
    table.add_column("Company", max_width=20)
    table.add_column("Remote", no_wrap=True)
    table.add_column("Location", max_width=18)
    table.add_column("Exp.", max_width=12)
    table.add_column("Posted", no_wrap=True)
    table.add_column("Age", no_wrap=True)
    table.add_column("CV", no_wrap=True)
    table.add_column("Link", no_wrap=True)

    for row in rows:
        title = row["title"] or "(no title)"
        company = row["company"] or ""
        url = row["url"] or ""
        title_cell = f"[link={url}]{title}[/link]" if url else title
        open_cell = f"[link={url}]Open ↗[/link]" if url else ""
        resume_cell = "[green]✓[/green]" if _resume_exists(company) else "[dim]—[/dim]"
        posted = _age(row["posted_at"]) if row["posted_at"] else "[dim]—[/dim]"
        table.add_row(
            title_cell,
            company,
            _remote_color(row["remote"] or "Unknown"),
            row["location"] or "",
            row["experience"] or "",
            posted,
            _age(row["first_seen_at"]),
            resume_cell,
            open_cell,
        )

    console.print(table)


# ── commands ──────────────────────────────────────────────────────────────────

@app.command()
def fetch() -> None:
    """Fetch new job listings from all configured searches."""
    init_db()
    config = load_config()
    total_new = 0

    # Staleness warning
    last = last_fetch_at()
    if last:
        dt = datetime.fromisoformat(last)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if hours_ago > 24:
            console.print(f"[yellow]⚠ Last fetch was {int(hours_ago)}h ago.[/yellow]")

    for search in config.searches:
        console.print(f"[bold]Fetching[/bold] {search.name}…")
        jobs = fetch_search(search)
        new_count = 0

        for job in jobs:
            if already_seen(job.job_id):
                continue
            from .web_api import _should_include_job
            include, kw = _should_include_job(job, config)
            if not include:
                if kw:
                    insert_filter_log(job.job_id, job.title, kw)
                continue
            if is_duplicate(job.title, job.company):
                continue

            insert_job(
                job_id=job.job_id,
                url=job.url,
                title=job.title,
                company=job.company,
                location=job.location,
                remote=job.remote,
                experience=job.experience,
                description=job.description,
                posted_at=job.posted_at,
                search_name=search.name,
            )
            new_count += 1

        log_fetch(search.source, new_count)
        console.print(f"  → {new_count} new listing(s)")
        total_new += new_count

    console.print(f"\n[bold green]{total_new} total new job(s) saved.[/bold green]\n")

    if total_new > 0:
        _notify("job-scraper", f"{total_new} new job listing(s) found!")

    pending = get_pending_deduped()
    if pending:
        _print_jobs_table(pending)


@app.command(name="list")
def list_jobs(
    status: str = typer.Option("pending", "--status", "-s", help="Status to show: pending | applied | skipped"),
) -> None:
    """Show job listings by status (default: pending)."""
    init_db()
    rows = get_jobs_by_status(status)
    if not rows:
        console.print(f"[dim]No {status} listings.[/dim]")
        return
    console.print(f"[bold]{len(rows)} {status} listing(s):[/bold]\n")
    _print_jobs_table(rows)


@app.command()
def unique() -> None:
    """Show pending listings deduplicated by company + title."""
    init_db()
    rows = get_pending_deduped()
    if not rows:
        console.print("[dim]No pending listings.[/dim]")
        return
    all_count = len(get_pending())
    console.print(f"[bold]{len(rows)} unique listing(s)[/bold] [dim](from {all_count} total)[/dim]\n")
    _print_jobs_table(rows)


@app.command()
def done(job_id: str) -> None:
    """Mark a listing as applied."""
    init_db()
    if update_status(job_id, "applied"):
        console.print(f"[green]Marked {job_id} as applied.[/green]")
    else:
        console.print(f"[red]Job ID {job_id} not found.[/red]")


@app.command()
def skip(job_id: str) -> None:
    """Skip a listing."""
    init_db()
    if update_status(job_id, "skipped"):
        console.print(f"[yellow]Skipped {job_id}.[/yellow]")
    else:
        console.print(f"[red]Job ID {job_id} not found.[/red]")


@app.command(name="open")
def open_job(job_id: str) -> None:
    """Open a job listing URL in the browser."""
    init_db()
    row = get_job(job_id)
    if not row:
        console.print(f"[red]Job ID {job_id} not found.[/red]")
        return
    if not row["url"]:
        console.print(f"[red]No URL for {job_id}.[/red]")
        return
    _open_url(row["url"])
    console.print(f"[green]Opened {row['url']}[/green]")


@app.command()
def stats() -> None:
    """Show counts per status and last fetch times."""
    init_db()
    counts = db_stats()
    if not counts:
        console.print("[dim]No listings in database yet.[/dim]")
        return

    table = Table(box=box.SIMPLE, show_edge=False)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    for status, count in sorted(counts.items()):
        table.add_row(status, str(count))
    console.print(table)

    # Last fetch per source
    config = load_config()
    sources = {s.source for s in config.searches}
    console.print()
    fetch_table = Table(box=box.SIMPLE, show_edge=False, header_style="bold cyan")
    fetch_table.add_column("Source")
    fetch_table.add_column("Last fetched")
    fetch_table.add_column("Status")
    for source in sorted(sources):
        last = last_fetch_at(source)
        if last:
            dt = datetime.fromisoformat(last)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            age_str = _age(last)
            warning = " [yellow]⚠ stale[/yellow]" if hours_ago > 24 else " [green]✓[/green]"
            fetch_table.add_row(source, age_str, warning)
        else:
            fetch_table.add_row(source, "[dim]never[/dim]", "[dim]—[/dim]")
    console.print(fetch_table)


@app.command()
def resume(
    limit: int = typer.Option(5, "--limit", "-n", help="Max number of resumes to generate"),
) -> None:
    """Fetch descriptions for pending jobs and generate a tailored resume for each."""
    init_db()

    all_pending = get_pending_deduped()
    candidates = [dict(r) for r in all_pending[:limit]]

    if not candidates:
        console.print("[yellow]No pending jobs found. Run fetch first.[/yellow]")
        return

    console.print(f"[bold]Fetching descriptions for {len(candidates)} job(s)…[/bold]")
    for i, row in enumerate(candidates, 1):
        if row["description"] and len(row["description"]) > 100:
            continue
        if not row["job_id"].startswith("li_"):
            continue
        console.print(f"  [{i}/{len(candidates)}] {row['company']} — {row['title']}")
        desc = li_fetch_description(row["url"])
        if desc:
            update_description(row["job_id"], desc)
            candidates[i - 1]["description"] = desc
        time.sleep(1.5)

    console.print(f"\n[bold]Generating resumes for {len(candidates)} job(s)…[/bold]\n")
    from .web_api import _skill_path
    skill_dir = _skill_path()

    for i, row in enumerate(candidates, 1):
        company = row["company"] or "Unknown"
        title = row["title"] or "Job"
        console.print(f"[bold cyan][{i}/{len(candidates)}][/bold cyan] {company} — {title}")

        prompt = (
            f"Apply to this job for me. Here is the job description:\n\n"
            f"Company: {company}\n"
            f"Title: {title}\n"
            f"Location: {row['location'] or ''}\n"
            f"URL: {row['url'] or ''}\n\n"
            f"{row['description']}"
        )

        skill_instructions = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        latex_template = skill_dir / "references" / "latex_template.md"
        if latex_template.exists():
            skill_instructions += f"\n\n## latex_template.md (embedded)\n\n{latex_template.read_text(encoding='utf-8')}"
        profile_path = get_profile_path()
        if profile_path and profile_path.exists():
            skill_instructions += f"\n\n## profile.md (embedded)\n\n{profile_path.read_text(encoding='utf-8')}"

        claude_exe = shutil.which("claude") or "claude"
        result = subprocess.run(
            [claude_exe, "-p", prompt,
             "--append-system-prompt", skill_instructions,
             "--allowedTools", "Bash,Edit,Write,Read"],
            capture_output=False,
            text=True,
            cwd=str(skill_dir),
        )

        if result.returncode != 0:
            console.print(f"  [red]Failed for {company}[/red]")
        else:
            console.print(f"  [green]Done — resume saved to resumes/{company}/[/green]")

        if row["url"]:
            _open_url(row["url"])

        if i < len(candidates):
            time.sleep(2)


if __name__ == "__main__":
    app()
