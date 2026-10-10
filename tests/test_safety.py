from __future__ import annotations

from models import MissionContent
from safety import check_mission


def make_content(**overrides) -> MissionContent:
    payload = {
        "title": "Quiet Park Observation",
        "introduction": (
            "A calm observation mission that keeps you in one safe public place "
            "for a short while."
        ),
        "steps": [
            "Find a safe spot on the grass or a bench away from the path.",
            "Watch how the trees move for two full minutes without talking.",
            "Write down one thing that surprised you before standing up.",
        ],
        "observation_goal": "Notice one detail about tree movement you had never seen before.",
        "completion_condition": "You noted one surprising detail and stood up slowly.",
        "safety_notes": [
            "Stay clear of roads and keep traffic in mind near park boundaries.",
        ],
    }
    payload.update(overrides)
    return MissionContent(**payload)


def test_safe_mission_passes():
    report = check_mission(make_content())
    assert report.ok
    assert report.violations == ()


def with_unsafe_step(step: str) -> MissionContent:
    return make_content(
        steps=[
            step,
            "Watch how the trees move for two full minutes without talking.",
            "Write down one thing that surprised you before standing up.",
        ]
    )


def test_trespass_rejected():
    mission = with_unsafe_step("Ignore the no-entry sign and trespass past the fence.")
    report = check_mission(mission)
    assert not report.ok
    assert any("restricted" in v.lower() or "trespass" in v.lower() for v in report.violations)


def test_wildlife_approach_rejected():
    mission = with_unsafe_step("Approach the fox carefully and feed it by hand today.")
    report = check_mission(mission)
    assert not report.ok


def test_unknown_plant_tasting_rejected():
    mission = with_unsafe_step("Taste any wild berry you find to learn its flavour.")
    report = check_mission(mission)
    assert not report.ok
    assert any("tasting" in v.lower() or "unknown" in v.lower() for v in report.violations)


def test_unsafe_road_behavior_rejected():
    mission = with_unsafe_step("Walk into the middle of the road to watch the sunset there.")
    report = check_mission(mission)
    assert not report.ok


def test_isolated_location_rejected():
    mission = with_unsafe_step("Explore the abandoned building on the edge of the park.")
    report = check_mission(mission)
    assert not report.ok


def test_medical_claim_rejected():
    mission = make_content(
        introduction="This walk is proven to treat your anxiety within one session of walking."
    )
    report = check_mission(mission)
    assert not report.ok
    assert any("medical" in v.lower() or "mental" in v.lower() for v in report.violations)


def test_links_rejected():
    mission = make_content(introduction="Read more at https://example.com before you start walking.")
    report = check_mission(mission)
    assert not report.ok
    assert any("link" in v.lower() for v in report.violations)


def test_missing_traffic_note_rejected():
    mission = make_content(safety_notes=["Wear comfortable shoes for the whole walk today."])
    report = check_mission(mission)
    assert not report.ok
    assert any("traffic" in v.lower() for v in report.violations)


def test_negated_safety_instructions_pass():
    mission = make_content(
        steps=[
            "Stay on the pavement and never cross outside a marked crossing.",
            "Do not approach wildlife; watch birds from a respectful distance.",
            "Do not taste unknown plants or berries on this walk.",
        ]
    )
    report = check_mission(mission)
    assert report.ok, report.violations


def test_html_rejected_by_model_validation():
    try:
        make_content(title="Bad <script>alert(1)</script> title")
    except ValueError as exc:
        assert "HTML" in str(exc)
    else:
        raise AssertionError("expected validation error for script tag in title")


def test_multiple_violations_reported():
    mission = make_content(
        introduction="Cross the freeway quickly and then treat your depression with this view."
    )
    report = check_mission(mission)
    assert not report.ok
    assert len(report.violations) >= 2
