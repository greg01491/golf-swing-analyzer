"""Rule-based swing tips from flagged metrics (FR18, Phase 6).

Each metric has "too low" / "too high" tip text. Severity is the metric's
deviation from its reference range, normalized by the range width, so a
shoulder turn 20% below range outranks a tempo 5% above -- and the top N
most severe deviations become the session's tips. Deliberately simple and
transparent; a smarter model can replace this layer later without touching
metrics or UI (plan.md Phase 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from golf_sim.analysis.metrics import MetricResult, MetricsReport

# (too_low_tip, too_high_tip) per metric name
_TIP_RULES: dict[str, tuple[str, str]] = {
    "shoulder_turn_deg": (
        "Your shoulder turn is on the short side. Try turning your lead shoulder "
        "back until it's over your trail leg at the top -- a fuller turn stores "
        "more power without swinging harder.",
        "Your shoulder turn is longer than it needs to be, which can make timing "
        "inconsistent. Feel like you stop turning once your back faces the target.",
    ),
    "hip_turn_deg": (
        "Your hips are barely turning back. Let your trail hip rotate behind you "
        "in the backswing -- restricting it too much costs depth and strains the back.",
        "Your hips are over-rotating in the backswing, which bleeds coil. Feel "
        "like your lower body resists while your upper body turns.",
    ),
    "x_factor_deg": (
        "Your shoulders and hips are turning together, losing coil. Try keeping "
        "your hips quieter early in the backswing so your torso stretches against them.",
        "The separation between shoulders and hips is very large -- powerful, but "
        "hard on the back and tough to time. A slightly earlier hip turn can smooth it out.",
    ),
    "spine_tilt_deg": (
        "You're standing quite tall at address. Bow forward a touch more from the "
        "hips (not the waist) so your arms can hang naturally under your shoulders.",
        "You're bent over more than typical at address, which restricts rotation. "
        "Stand a touch taller and keep your weight balanced over mid-foot.",
    ),
    "tempo_ratio": (
        "Your backswing is quick relative to your downswing. Give yourself a beat "
        "more time going back -- think 'three counts back, one count down'.",
        "Your backswing is slow relative to a punchy downswing, which often means "
        "a rushed transition. Blend the change of direction more gradually.",
    ),
    "hip_sway_top_pct": (
        "",  # low sway is fine; no tip
        "You're sliding sideways in the backswing rather than turning. Feel like "
        "you rotate around your trail hip instead of swaying onto it.",
    ),
    "hip_sway_impact_pct": (
        "",
        "There's a lot of lateral slide through impact. A stable lead side gives "
        "the club something to release against -- feel like you post up on your lead leg.",
    ),
}


@dataclass
class Tip:
    metric: str
    direction: str  # "low" | "high"
    severity: float  # deviation normalized by range width; larger = worse
    text: str


def _severity(metric: MetricResult) -> tuple[str, float] | None:
    if metric.in_range is not False:
        return None
    assert metric.range_min is not None and metric.range_max is not None
    width = metric.range_max - metric.range_min
    if width <= 0:
        width = abs(metric.range_max) or 1.0
    if metric.value < metric.range_min:
        return "low", (metric.range_min - metric.value) / width
    return "high", (metric.value - metric.range_max) / width


def generate_tips(report: MetricsReport, max_tips: int = 3) -> list[Tip]:
    candidates: list[Tip] = []
    for metric in report.metrics:
        flagged = _severity(metric)
        if flagged is None:
            continue
        direction, severity = flagged
        rules = _TIP_RULES.get(metric.name)
        if rules is None:
            continue
        text = rules[0] if direction == "low" else rules[1]
        if not text:
            continue
        candidates.append(
            Tip(metric=metric.name, direction=direction, severity=severity, text=text)
        )

    candidates.sort(key=lambda tip: tip.severity, reverse=True)
    return candidates[:max_tips]


def tips_to_dicts(tips: list[Tip]) -> list[dict]:
    return [
        {
            "metric": tip.metric,
            "direction": tip.direction,
            "severity": round(tip.severity, 3),
            "text": tip.text,
        }
        for tip in tips
    ]
