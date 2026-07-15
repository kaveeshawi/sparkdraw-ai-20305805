class HealthService:
    """
    Rule-based health score engine (C3).
    V1: transparent, explainable rules.
    V2: replace with ML classifier trained on real labeled outcomes.
    """

    def compute(self, project_id: int, metrics: dict | None = None) -> dict:
        # metrics injected by Laravel via internal HTTP call
        # placeholder until Laravel integration is wired
        if metrics is None:
            return {"score": None, "flag": "none", "reasons": [], "project_id": project_id}

        score = 100
        reasons = []

        if metrics.get("revision_rate_high"):
            score -= 15
            reasons.append("Revision rate doubled this week")

        if metrics.get("hours_burn_ratio", 0) > 0.85 and metrics.get("completion_pct", 100) < 50:
            score -= 20
            reasons.append(f"Hours at {int(metrics['hours_burn_ratio']*100)}% with {int(metrics['completion_pct'])}% of work remaining")

        if metrics.get("approval_lag_days", 0) > 2:
            score -= 10
            reasons.append(f"Client approval lag averaging {metrics['approval_lag_days']:.1f} days")

        if metrics.get("milestone_missed"):
            score -= 15
            reasons.append("Milestone deadline missed")

        if metrics.get("message_velocity_drop"):
            score -= 10
            reasons.append("Client message frequency dropped significantly")

        if metrics.get("sentiment_declining"):
            score -= 10
            reasons.append("Client sentiment trending negative over last 3 messages")

        score = max(0, score)

        if score >= 70:
            flag = "green"
        elif score >= 40:
            flag = "amber"
        else:
            flag = "red"

        return {"score": score, "flag": flag, "reasons": reasons, "project_id": project_id}
