from typing import Dict, Any, List

class SecurityAgent:
    """
    Specialist Agent for Anomaly Detection, Security Audit, and Suspicious Pattern Monitoring.
    """
    def __init__(self):
        self.suspicious_keywords = ["delete", "drop table", "grant admin", "override price", "discount 100"]

    def detect_anomalies(self, text: str, user_id: int) -> Dict[str, Any]:
        lower_text = text.lower()
        threats_found = [kw for kw in self.suspicious_keywords if kw in lower_text]

        is_suspicious = len(threats_found) > 0
        return {
            "is_suspicious": is_suspicious,
            "threats": threats_found,
            "risk_score": 0.9 if is_suspicious else 0.0,
            "action": "block" if is_suspicious else "allow"
        }
