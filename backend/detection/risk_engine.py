from __future__ import annotations

from backend.database.models import UnifiedEvent


SEVERITY_FLOOR = {
    "safe": 0,
    "info": 10,
    "warning": 50,
    "critical": 80,
}


class RiskEngine:
    def score(self, event: UnifiedEvent) -> UnifiedEvent:
        score = int(event.risk_score)
        severity = event.severity.lower()
        score = max(score, SEVERITY_FLOOR.get(severity, 0))

        tags = {str(tag).lower() for tag in event.details.get("tags", []) if tag}
        if "multi_device" in tags or "multi_agent_confirmed" in tags:
            score += 15
        if event.source == "ids" and event.event_type in {"SYN_FLOOD", "PORT_SCAN", "ML_ANOMALY"}:
            score += 10
        if event.source == "edr" and event.event_type in {"PROCESS", "NETWORK", "FILE"}:
            score += int(event.details.get("behavior_score") or 0) // 5

        score = max(0, min(100, score))
        severity = "critical" if score >= 80 else "warning" if score >= 50 else "safe"
        return event.model_copy(update={"risk_score": score, "severity": severity})
