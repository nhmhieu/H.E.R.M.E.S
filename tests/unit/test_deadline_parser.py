"""
Unit tests for Moodle .ics Deadline Parser (Role R4 / R8 - Member 6).
"""

from hermes.engines.deadline_parser import parse_ics_deadlines


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

