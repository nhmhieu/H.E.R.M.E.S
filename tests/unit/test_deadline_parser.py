"""
Unit tests for Moodle .ics Deadline Parser & Notification Helpers (Role R4 / R6 / R8).
"""

from datetime import datetime

from hermes.engines.deadline_parser import (
    compute_deadline_status,
    export_deadlines_to_ics,
    parse_flexible_deadline,
    parse_ics_deadlines,
)


def test_parse_ics_deadlines_extracts_events():
    sample_ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:[CSC10014] Nộp báo cáo Đồ án H.E.R.M.E.S\r\n"
        "CATEGORIES:CSC10014_2026\r\n"
        "DTEND:20261115T165900Z\r\n"
        "DESCRIPTION:Nộp file báo cáo PDF và link GitHub.\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    events = parse_ics_deadlines(sample_ics)
    assert len(events) == 1
    assert events[0]["course"] == "CSC10014_2026"
    assert events[0]["deadline"] == "2026-11-15 16:59"
    assert "H.E.R.M.E.S" in events[0]["summary"]


def test_parse_ics_empty_or_invalid_returns_empty():
    assert parse_ics_deadlines("") == []
    assert parse_ics_deadlines("NOT AN ICS FILE") == []


def test_parse_flexible_deadline_formats():
    dt1 = parse_flexible_deadline("23:59 ngày 20/11/2026")
    assert dt1 == datetime(2026, 11, 20, 23, 59)

    dt2 = parse_flexible_deadline("2026-11-18 16:30")
    assert dt2 == datetime(2026, 11, 18, 16, 30)

    dt3 = parse_flexible_deadline("15/10", reference_year=2026)
    assert dt3 == datetime(2026, 10, 15, 23, 59)


def test_compute_deadline_status_urgency_and_countdown():
    ref_now = datetime(2026, 11, 18, 10, 0)
    urgent_res = compute_deadline_status("23:59 ngày 19/11/2026", now=ref_now)
    assert urgent_res["urgency"] == "urgent"
    assert "Còn 1 ngày" in urgent_res["countdown_label"]

    overdue_res = compute_deadline_status("2026-11-16 12:00", now=ref_now)
    assert overdue_res["urgency"] == "overdue"


def test_export_deadlines_to_ics_includes_valarm_reminders():
    items = [
        {
            "course": "Mạng máy tính",
            "summary": "Đồ án Socket",
            "deadline": "2026-11-20 23:59",
            "description": "Nộp qua Moodle",
        }
    ]
    ics_out = export_deadlines_to_ics(items)
    assert "BEGIN:VCALENDAR" in ics_out
    assert "BEGIN:VEVENT" in ics_out
    assert "BEGIN:VALARM" in ics_out
    assert "TRIGGER:-PT24H" in ics_out
    assert "TRIGGER:-PT2H" in ics_out
