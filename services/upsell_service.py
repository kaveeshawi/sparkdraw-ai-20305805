import os
import pickle

# V1: rule-based fallback until Scikit-learn model is trained on real data.
# V2: load trained model from models/upsell_model.pkl

UPSELL_RULES = {
    "web_design":    ["SEO Package", "Monthly Maintenance"],
    "branding":      ["Social Media Kit", "Brand Guidelines PDF"],
    "social_media":  ["Content Strategy Session", "Paid Ads Management"],
    "development":   ["Performance Audit", "API Integration"],
    "default":       ["Quarterly Review Package"],
}

class UpsellService:
    def __init__(self):
        model_path = os.path.join(os.path.dirname(__file__), "../models/upsell_model.pkl")
        self.model = None
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)

    def predict(self, data: dict) -> dict:
        if self.model:
            return self._ml_predict(data)
        return self._rule_predict(data)

    def _rule_predict(self, data: dict) -> dict:
        project_type = data.get("project_type", "default").lower()
        suggestions = UPSELL_RULES.get(project_type, UPSELL_RULES["default"])
        return {
            "recommended_service": suggestions[0],
            "alternatives": suggestions[1:],
            "confidence": 0.65,
            "method": "rule-based",
        }

    def _ml_predict(self, data: dict) -> dict:
        # Placeholder — implement feature encoding when model is ready
        return self._rule_predict(data)
