from golf_sim.analysis.metrics import MetricResult, MetricsReport
from golf_sim.analysis.phases import SwingPhases
from golf_sim.analysis.tips import generate_tips

NEWLY_RANGED_METRICS = (
    "backswing_time_s",
    "downswing_time_s",
    "hand_speed_impact_ms",
    "swing_plane_deg",
)


def _metric(name, value, lo=None, hi=None):
    in_range = None if lo is None else bool(lo <= value <= hi)
    return MetricResult(
        name=name, value=value, unit="deg", in_range=in_range, range_min=lo, range_max=hi
    )


def _report(metrics):
    return MetricsReport(
        phases=SwingPhases(address_frame=0, top_frame=10, impact_frame=15), metrics=metrics
    )


def test_no_tips_when_all_in_range():
    report = _report([_metric("shoulder_turn_deg", 90, 80, 100)])
    assert generate_tips(report) == []


def test_low_metric_gets_low_tip():
    report = _report([_metric("shoulder_turn_deg", 60, 80, 100)])
    tips = generate_tips(report)
    assert len(tips) == 1
    assert tips[0].metric == "shoulder_turn_deg"
    assert tips[0].direction == "low"
    assert "shoulder turn" in tips[0].text.lower()


def test_high_metric_gets_high_tip():
    report = _report([_metric("tempo_ratio", 4.5, 2.8, 3.2)])
    tips = generate_tips(report)
    assert tips[0].direction == "high"


def test_tips_ranked_by_severity_and_capped_at_max():
    report = _report(
        [
            _metric("shoulder_turn_deg", 75, 80, 100),  # 5/20 = 0.25 below
            _metric("hip_turn_deg", 10, 40, 55),  # 30/15 = 2.0 below
            _metric("tempo_ratio", 3.4, 2.8, 3.2),  # 0.2/0.4 = 0.5 above
            _metric("spine_tilt_deg", 50, 25, 40),  # 10/15 = 0.67 above
        ]
    )
    tips = generate_tips(report, max_tips=3)

    assert len(tips) == 3
    assert [t.metric for t in tips] == ["hip_turn_deg", "spine_tilt_deg", "tempo_ratio"]
    assert tips[0].severity > tips[1].severity > tips[2].severity


def test_unflagged_and_unknown_metrics_produce_no_tips():
    report = _report(
        [
            _metric("hip_sway_top_pct", 10),  # no range configured -> in_range None
            _metric("some_future_metric", 999, 0, 1),  # flagged but no rule
        ]
    )
    assert generate_tips(report) == []


def test_low_sway_has_no_tip_text():
    # sway below range is fine, not a fault -- rule text is empty for "low"
    report = _report([_metric("hip_sway_top_pct", -5, 0, 30)])
    assert generate_tips(report) == []


def test_newly_ranged_metrics_have_advice_in_both_directions():
    for name in NEWLY_RANGED_METRICS:
        low_tip = generate_tips(_report([_metric(name, -1, 0, 1)]))
        high_tip = generate_tips(_report([_metric(name, 2, 0, 1)]))

        assert len(low_tip) == 1, name
        assert low_tip[0].direction == "low"
        assert low_tip[0].text
        assert len(high_tip) == 1, name
        assert high_tip[0].direction == "high"
        assert high_tip[0].text


def test_proxy_advice_uses_qualified_wording():
    hand_speed = generate_tips(_report([_metric("hand_speed_impact_ms", 20, 4, 14)]))[0]
    swing_plane = generate_tips(_report([_metric("swing_plane_deg", 80, 42, 68)]))[0]

    assert "not inherently a fault" in hand_speed.text
    assert "body-pose hand-path estimate" in swing_plane.text


def test_new_timing_metrics_join_severity_ranking_and_top_three_cap():
    report = _report(
        [
            _metric("backswing_time_s", 0.4, 0.7, 0.9),  # 1.5 widths low
            _metric("downswing_time_s", 0.35, 0.2, 0.3),  # 0.5 widths high
            _metric("tempo_ratio", 3.3, 2.8, 3.2),  # 0.25 widths high
            _metric("shoulder_turn_deg", 70, 80, 100),  # 0.5 widths low
        ]
    )

    tips = generate_tips(report, max_tips=3)

    assert len(tips) == 3
    assert [tip.metric for tip in tips] == [
        "backswing_time_s",
        "downswing_time_s",
        "shoulder_turn_deg",
    ]
