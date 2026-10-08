from hermes.engines.scheduler import generate_study_plan


def test_generate_study_plan_empty():
    assert generate_study_plan([], 4.0, 7) == []


def test_generate_study_plan_invalid_time():
    assert generate_study_plan([{"name": "Math"}], -1.0, 7) == []
    assert generate_study_plan([{"name": "Math"}], 4.0, 0) == []


def test_generate_study_plan_normal():
    subjects = [
        {"name": "Math", "credits": 4, "priority": 2},
        {"name": "Physics", "credits": 2, "priority": 1},
    ]
    # Total hours: 4 * 3 = 12
    # Math allocation: 12 * (4/6) = 8.0
    # Physics allocation: 12 * (2/6) = 4.0
    plan = generate_study_plan(subjects, 4.0, 3)

    assert len(plan) == 2
    assert plan[0]["subject"] == "Math"
    assert plan[0]["allocated_hours"] == 8.0
    assert plan[0]["daily_hours"] == round(8.0 / 3, 2)

    assert plan[1]["subject"] == "Physics"
    assert plan[1]["allocated_hours"] == 4.0
    assert plan[1]["daily_hours"] == round(4.0 / 3, 2)
