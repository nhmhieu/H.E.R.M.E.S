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


def parse_flexible_deadline(
    deadline_str: str, reference_year: int | None = None
) -> datetime | None:
    """
    Parse flexible Vietnamese or ISO deadline strings into a datetime object.
    Examples supported:
    - '2026-11-20 16:59'
    - '23:59 ngày 20/11/2026'
    - '20/11/2026 23:59'
    - '23h59 ngày 20.11.2026'
    - '20/10' (uses reference_year or current year)
    """
    if not isinstance(deadline_str, str) or not deadline_str.strip():
        return None

    text = deadline_str.strip()
    ref_year = reference_year or datetime.now().year

    # 1. Exact ISO format YYYY-MM-DD HH:MM or YYYY-MM-DD
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59)
            return dt
        except ValueError:
            pass

    # Extract optional time HH:MM or HHhMM
    hour, minute = 23, 59
    time_match = re.search(r"\b([01]?\d|2[0-3])\s*[:hH]\s*([0-5]\d)\b", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))

    # Extract date DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    full_date_match = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])[\/\.\-](0?[1-9]|1[0-2])[\/\.\-](20\d{2})\b",
        text,
    )
    if full_date_match:
        day = int(full_date_match.group(1))
        month = int(full_date_match.group(2))
        year = int(full_date_match.group(3))
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    # Extract short date DD/MM or DD-MM
    short_date_match = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[0-2])\b", text
    )
    if short_date_match:
        day = int(short_date_match.group(1))
        month = int(short_date_match.group(2))
        try:
            return datetime(ref_year, month, day, hour, minute)
        except ValueError:
            return None

    return None


def compute_deadline_status(
    deadline_str: str, now: datetime | None = None
) -> dict[str, Any]:
    """
    Calculate countdown and urgency status for a deadline so the UI and chatbot
    can proactively alert students before due dates.
    """
    ref_now = now or datetime.now()
    dt = parse_flexible_deadline(deadline_str, reference_year=ref_now.year)
    if dt is None:
        return {
            "urgency": "unknown",
            "countdown_label": "Chưa rõ ngày giờ",
            "hours_remaining": None,
            "days_remaining": None,
            "normalized_dt": deadline_str,
        }

    delta_seconds = (dt - ref_now).total_seconds()
    hours_rem = round(delta_seconds / 3600.0, 1)
    days_rem = int(delta_seconds // 86400)
    rem_hours_in_day = int((abs(delta_seconds) % 86400) // 3600)

    if delta_seconds < 0:
        overdue_days = int(abs(delta_seconds) // 86400)
        if overdue_days == 0:
            label = f"Quá hạn {rem_hours_in_day} giờ"
        else:
            label = f"Đã quá hạn {overdue_days} ngày"
        urgency = "overdue"
    elif hours_rem <= 24:
        label = f"Gấp: Còn {max(1, int(hours_rem))} giờ"
        urgency = "urgent"
    elif days_rem <= 3:
        label = f"Sắp tới hạn: Còn {days_rem} ngày {rem_hours_in_day} giờ"
        urgency = "urgent"
    elif days_rem <= 7:
        label = f"Còn {days_rem} ngày"
        urgency = "upcoming"
    else:
        label = f"Còn {days_rem} ngày"
        urgency = "normal"

    return {
        "urgency": urgency,
        "countdown_label": label,
        "hours_remaining": hours_rem,
        "days_remaining": max(0, days_rem),
        "normalized_dt": dt.strftime("%Y-%m-%d %H:%M"),
    }


def export_deadlines_to_ics(deadlines: list[dict[str, Any]]) -> str:
    """
    Generate an RFC 5545 iCalendar (.ics) file with automatic VALARM reminders
    (24 hours and 2 hours before each deadline) so students can sync tasks to
    Google Calendar, Apple Calendar, or Outlook.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//H.E.R.M.E.S HCMUS//Academic Deadline Tracker//VN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for idx, item in enumerate(deadlines, start=1):
        course = str(item.get("course", "Môn học HCMUS")).strip()
        summary = str(item.get("summary", "Bài tập")).strip()
        raw_dl = str(item.get("deadline", "")).strip()
        desc = str(item.get("description", "")).strip()

        dt = parse_flexible_deadline(raw_dl)
        if dt is None:
            continue

        dt_str = dt.strftime("%Y%m%dT%H%M00")
        title = f"[{course}] {summary}" if course not in summary else summary
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:hermes-deadline-{idx}-{dt.strftime('%Y%m%d%H%M')}@hcmus.edu.vn",
                f"DTSTART:{dt_str}",
                f"DTEND:{dt_str}",
                f"SUMMARY:{title}",
                f"CATEGORIES:{course}",
                f"DESCRIPTION:{desc or 'Nhắc hạn nộp bài từ H.E.R.M.E.S'}",
                "BEGIN:VALARM",
                "TRIGGER:-PT24H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Nhắc hạn trước 24 giờ: {title}",
                "END:VALARM",
                "BEGIN:VALARM",
                "TRIGGER:-PT2H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Khẩn cấp (còn 2 giờ): {title}",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
