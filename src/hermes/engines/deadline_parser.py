from __future__ import annotations

from datetime import datetime
import re
from typing import Any


def _parse_ical_datetime(raw_dt: str) -> str:
    """Convert iCalendar timestamp (e.g. 20261120T165900Z) to readable format."""
    cleaned = raw_dt.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1].strip()

    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return cleaned


def _unfold_ical_lines(ics_content: str) -> list[str]:
    """Unfold RFC 5545 multi-line fields where continuation lines start with space/tab."""
    raw_lines = ics_content.replace("\r\n", "\n").splitlines()
    unfolded: list[str] = []
    for line in raw_lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line.strip())
    return unfolded


def parse_ics_deadlines(ics_content: str) -> list[dict[str, Any]]:
    """
    Extract upcoming course deadlines from raw Moodle .ics content.

    Returns a list of dicts with keys:
    - summary: Event title / assignment name
    - course: Course code or category (from CATEGORIES or SUMMARY)
    - deadline: Formatted due date/time string ("YYYY-MM-DD HH:MM")
    - description: Cleaned description text
    """
    if not isinstance(ics_content, str) or "BEGIN:VEVENT" not in ics_content:
        return []

    lines = _unfold_ical_lines(ics_content)
    events: list[dict[str, Any]] = []
    in_event = False
    current: dict[str, str] = {}

    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
        elif line == "END:VEVENT" and in_event:
            in_event = False
            summary = current.get("SUMMARY", "Bài tập Moodle").replace("\\,", ",")
            categories = current.get("CATEGORIES", "").replace("\\,", ",")
            dt_end = current.get("DTEND") or current.get("DTSTART") or ""
            desc = (
                current.get("DESCRIPTION", "")
                .replace("\\n", " ")
                .replace("\\,", ",")
                .strip()
            )

            course_name = categories if categories else "Chưa xác định"
            if course_name == "Chưa xác định":
                match = re.search(r"\[([A-Za-z0-9_\-\s]+)\]", summary)
                if match:
                    course_name = match.group(1).strip()

            events.append(
                {
                    "summary": summary,
                    "course": course_name,
                    "deadline": (
                        _parse_ical_datetime(dt_end) if dt_end else "Chưa xác định"
                    ),
                    "description": desc,
                }
            )
        elif in_event and ":" in line:
            key_part, _, val_part = line.partition(":")
            base_key = key_part.split(";")[0].strip().upper()
            current[base_key] = val_part.strip()

    return sorted(events, key=lambda x: x["deadline"])
