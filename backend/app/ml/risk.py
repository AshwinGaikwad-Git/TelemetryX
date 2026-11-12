"""Risk mapping and actionable maintenance recommendations for predicted RUL."""

from dataclasses import dataclass
from typing import Any


@dataclass
class MaintenanceRecommendationResult:
    recommendation_type: str
    priority: str  # healthy, planning, attention, urgent
    rationale: str
    status: str = "active"

    def to_dict(self) -> dict[str, str]:
        return {
            "recommendation_type": self.recommendation_type,
            "priority": self.priority,
            "rationale": self.rationale,
            "status": self.status,
        }


def map_rul_to_risk(predicted_rul: float) -> str:
    """Deterministically maps predicted RUL in cycles to a risk band.

    Bands per Technical Specification:
      - > 30 cycles: 'healthy'
      - 15 <= RUL <= 30 cycles: 'planning'
      - 5 <= RUL < 15 cycles: 'attention'
      - < 5 cycles: 'urgent'
    """
    if predicted_rul > 30.0:
        return "healthy"
    elif predicted_rul >= 15.0:
        return "planning"
    elif predicted_rul >= 5.0:
        return "attention"
    else:
        return "urgent"


def generate_recommendation(
    predicted_rul: float,
    lower_bound: float,
    upper_bound: float,
    top_contributors: list[dict[str, Any]] | None = None,
) -> MaintenanceRecommendationResult:
    """Generates non-automated, human-readable maintenance recommendations."""
    risk = map_rul_to_risk(predicted_rul)

    # Extract degradation sensor cues
    degraded_sensors = []
    if top_contributors:
        for c in top_contributors:
            if c.get("direction") == "decreases_rul":
                desc = c.get("description", "").split(" - ")[0]
                if desc and desc not in degraded_sensors:
                    degraded_sensors.append(desc)

    sensor_context = (
        f" Driven by sensor trends: {', '.join(degraded_sensors[:2])}." if degraded_sensors else ""
    )
    interval_str = (
        f"Estimated RUL: {predicted_rul:.1f} cycles "
        f"(Nominal 90% prediction interval: {lower_bound:.1f} – {upper_bound:.1f} cycles)."
    )
    disclaimer = " [Simulated C-MAPSS benchmark analysis; not operational aviation authorization.]"

    if risk == "urgent":
        rec_type = "immediate_maintenance_escalation"
        rationale = (
            f"URGENT: Unit has fewer than 5 operating cycles remaining. "
            f"{interval_str}{sensor_context} "
            f"Escalate for prompt engineering inspection and maintenance staging.{disclaimer}"
        )
    elif risk == "attention":
        rec_type = "priority_engineering_review"
        rationale = (
            f"ATTENTION: Unit is in high-degradation regime (5–15 cycles). "
            f"{interval_str}{sensor_context} "
            f"Prioritize engineering review and prepare maintenance work-order.{disclaimer}"
        )
    elif risk == "planning":
        rec_type = "scheduled_inspection"
        rationale = (
            f"PLANNING: Unit approaching maintenance window (15–30 cycles). "
            f"{interval_str}{sensor_context} "
            f"Schedule preventative borescope/compressor inspection within the "
            f"projected cycle range.{disclaimer}"
        )
    else:
        rec_type = "routine_monitoring"
        rationale = (
            f"HEALTHY: Unit telemetry exhibits nominal wear rates (>30 cycles remaining). "
            f"{interval_str} Continue routine operational monitoring.{disclaimer}"
        )

    return MaintenanceRecommendationResult(
        recommendation_type=rec_type,
        priority=risk,
        rationale=rationale,
    )
