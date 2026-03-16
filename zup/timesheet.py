"""
Export a monthly time-sheet for the authenticated ClickUp user.

Fetches all time entries for a given year/month, accumulates them per day
and per task, and prints the result as JSON to stdout.

Usage:
    python -m zup.timesheet [--year YEAR] [--month MONTH]

Both options default to the current year and month. The ClickUp API token
is read from the Zup configuration file (set via the Zup settings dialog).
"""

import calendar
import datetime
import json
import logging
import sys

import click

from zup.clickup_client import ClickUpClient
from zup.config_store import ConfigStore

LOG = logging.getLogger(__name__)

_MS_TO_HOURS = 1 / (1000 * 3600)


def _month_range_ms(year: int, month: int) -> tuple[int, int]:
    """Return (start_ms, end_ms) covering the full month in local time."""
    start = datetime.datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime.datetime(year, month, last_day, 23, 59, 59, 999999)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _ms_to_local_date(ms: int) -> str:
    """Convert a millisecond UTC timestamp to a local YYYY-MM-DD string."""
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def fetch_timesheet(client: ClickUpClient, year: int, month: int) -> dict:
    """
    Fetch and accumulate time entries for the given month.

    Returns a dict with shape:
        {
          "year": int,
          "month": int,
          "user": str,
          "days": [
            {
              "date": "YYYY-MM-DD",
              "tasks": [{"id": str, "name": str, "hours": float}],
              "total_hours": float
            }
          ],
          "total_hours": float
        }
    """
    sdk_client = client._get_client()
    team_id = client._get_team_id()
    if not team_id:
        raise RuntimeError("No workspace found for this token.")

    user = sdk_client.TOKEN_USER
    user_name: str = user["username"]
    user_id: str = str(user["id"])

    start_ms, end_ms = _month_range_ms(year, month)
    LOG.debug(
        "Fetching time entries for user %s (%s), %04d-%02d",
        user_name,
        user_id,
        year,
        month,
    )

    response = sdk_client.make_request(
        method="GET",
        route=f"team/{team_id}/time_entries",
        params={
            "start_date": str(start_ms),
            "end_date": str(end_ms),
            "assignee": user_id,
        },
    )
    response_data: dict = response or {}  # type: ignore[assignment]
    entries = response_data.get("data", [])
    LOG.debug("Received %d raw time entr(ies)", len(entries))

    # Accumulate: {date: {task_id: {"name": str, "ms": int}}}
    # Preserve insertion order within each day for stable output.
    days: dict[str, dict[str, dict]] = {}

    for entry in entries:
        duration_ms = int(entry.get("duration", 0))
        if duration_ms <= 0:
            # Negative means a timer is still running; zero is useless.
            LOG.debug("Skipping entry with duration %d ms", duration_ms)
            continue

        start_ms_entry = int(entry.get("start", 0))
        date = _ms_to_local_date(start_ms_entry)

        task = entry.get("task") or {}
        task_id: str = task.get("id", "unknown")
        task_name: str = task.get("name", "(no task name)")

        LOG.debug(
            "  %s  +%dms  task=%s (%s)",
            date,
            duration_ms,
            task_name,
            task_id,
        )

        if date not in days:
            days[date] = {}
        if task_id not in days[date]:
            days[date][task_id] = {"name": task_name, "ms": 0}
        days[date][task_id]["ms"] += duration_ms

    # Build output structure.
    total_ms = 0
    days_out = []
    for date in sorted(days):
        day_ms = 0
        tasks_out = []
        for task_id, data in days[date].items():
            task_ms = data["ms"]
            day_ms += task_ms
            tasks_out.append(
                {
                    "id": task_id,
                    "name": data["name"],
                    "hours": round(task_ms * _MS_TO_HOURS, 2),
                }
            )
        total_ms += day_ms
        days_out.append(
            {
                "date": date,
                "tasks": tasks_out,
                "total_hours": round(day_ms * _MS_TO_HOURS, 2),
            }
        )

    return {
        "year": year,
        "month": month,
        "user": user_name,
        "days": days_out,
        "total_hours": round(total_ms * _MS_TO_HOURS, 2),
    }


@click.command()
@click.option(
    "--year",
    default=lambda: datetime.date.today().year,
    show_default="current year",
    type=click.IntRange(2000, 2100),
    help="Year to export.",
)
@click.option(
    "--month",
    default=lambda: datetime.date.today().month,
    show_default="current month",
    type=click.IntRange(1, 12),
    help="Month to export (1–12).",
)
def main(year: int, month: int) -> None:
    """Print a monthly time-sheet as JSON to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
    )
    LOG.setLevel(logging.DEBUG)

    token = ConfigStore().get("clickup_token")
    if not token:
        raise click.ClickException(
            "No ClickUp API token configured. Set it via the Zup settings dialog."
        )

    client = ClickUpClient(user_token=token)
    try:
        sheet = fetch_timesheet(client, year, month)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    json.dump(sheet, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
