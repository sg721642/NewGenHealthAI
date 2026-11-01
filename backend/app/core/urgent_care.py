"""
NewGenHealthAI — core/urgent_care.py
Deterministic Urgent-Risk Screening Module.

Provides pure offline, zero-dependency screening for acute medical red flags
(e.g., suspected acute coronary syndrome, stroke, severe respiratory distress,
anaphylaxis, severe uncontrolled hemorrhage, and acute crisis).

Crucial Safety Principle:
When acute emergency symptoms are detected, the system immediately returns
emergency escalation instructions (e.g. 911 / 999 / 112 / nearest ED)
WITHOUT asking follow-up triage questions or attempting speculative diagnosis.
"""

import re
from typing import Any, Dict, List, Optional

# ── Red Flag Heuristic Rule Definitions ────────────────────────────────────────

URGENT_CATEGORIES = {
    "cardiac": {
        "title": "Possible Acute Coronary Event / Cardiac Emergency",
        "patterns": [
            r"\bcrushing\s+(?:chest\s+)?(?:pain|pressure|tightness|heaviness)\b",
            r"\bchest\s+(?:pain|pressure|tightness|heaviness)\b.*\b(?:radiat|spread|arm|jaw|neck|back)\b",
            r"\b(?:radiat|spread|arm|jaw|neck|back)\b.*\bchest\s+(?:pain|pressure|tightness|heaviness)\b",
            r"\bchest\s+(?:pain|pressure)\b.*\b(?:shortness\s+of\s+breath|sweat|diaphoresis|dizziness|nausea)\b",
            r"\b(?:heart\s+attack|myocardial\s+infarction)\b",
        ],
    },
    "stroke": {
        "title": "Possible Stroke / Acute Neurological Emergency",
        "patterns": [
            r"\b(?:face\s+droop|facial\s+droop|drooping\s+face|drooping\s+on\s+one\s+side)\b",
            r"\b(?:arm|leg|side\s+of\s+(?:my\s+)?body)\s+(?:weakness|numbness|paraly[sz]ed)\b",
            r"\b(?:slurred\s+speech|cannot\s+speak|difficulty\s+speaking|speech\s+is\s+slurred|trouble\s+speaking)\b",
            r"\b(?:sudden\s+loss\s+of\s+vision|sudden\s+blindness)\b",
            r"\b(?:thunderclap\s+headache|worst\s+headache\s+of\s+(?:my\s+)?life)\b",
            r"\b(?:stroke|transient\s+ischemic\s+attack|tia)\b",
        ],
    },
    "respiratory": {
        "title": "Severe Respiratory Distress",
        "patterns": [
            r"\b(?:cannot\s+breathe|unable\s+to\s+breathe|can'?t\s+catch\s+my\s+breath|gasping\s+for\s+(?:air|breath))\b",
            r"\bsevere\s+(?:shortness\s+of\s+breath|breathing\s+difficulty|dyspnea)\b",
            r"\b(?:turning\s+blue|blue\s+lips|cyanosis)\b",
            r"\b(?:stridor|choking\s+and\s+cannot\s+breathe)\b",
        ],
    },
    "anaphylaxis": {
        "title": "Possible Anaphylaxis / Severe Allergic Reaction",
        "patterns": [
            r"\bthroat\s+(?:is\s+)?(?:closing|swelling|tightening)\b",
            r"\b(?:closing\s+up|swelling\s+shut|swollen\s+shut)\b",
            r"\btongue\s+(?:is\s+)?swelling\b",
            r"\b(?:anaphylaxis|anaphylactic)\b",
            r"\ballergic\s+reaction\b.*\b(?:cannot\s+breathe|trouble\s+breathing|throat\s+swelling|closing)\b",
            r"\b(?:bee\s+sting|insect\s+sting|peanut|food\s+allergy)\b.*\b(?:throat|breathe|swelling|closing)\b",
            r"\b(?:throat|breathe|swelling|closing)\b.*\b(?:bee\s+sting|insect\s+sting|peanut|food\s+allergy)\b",
        ],
    },
    "hemorrhage": {
        "title": "Severe / Uncontrolled Hemorrhage",
        "patterns": [
            r"\b(?:spurting\s+blood|bleeding\s+won'?t\s+stop|uncontrolled\s+bleeding)\b",
            r"\b(?:coughing\s+up\s+blood|vomiting\s+blood|hematemesis)\b",
            r"\bsevere\s+blood\s+loss\b",
        ],
    },
    "crisis": {
        "title": "Immediate Safety / Crisis Alert",
        "patterns": [
            r"\b(?:want\s+to\s+kill\s+myself|commit\s+suicide|end\s+my\s+life|suicidal\s+thoughts|suicide\s+attempt)\b",
            r"\b(?:overdosed\s+on|swallowed\s+a\s+bottle\s+of)\b",
        ],
    },
}

COMPILED_PATTERNS = {
    cat: [re.compile(p, re.IGNORECASE) for p in data["patterns"]]
    for cat, data in URGENT_CATEGORIES.items()
}


def check_urgent_risk(text: str) -> Optional[Dict[str, Any]]:
    """
    Evaluate user text for acute red-flag emergency symptoms.

    Returns:
        Dict with risk metadata if urgent risk is detected, else None.
    """
    if not text or not text.strip():
        return None

    cleaned_text = text.strip()

    for category, patterns in COMPILED_PATTERNS.items():
        matched_patterns = []
        for pat in patterns:
            if pat.search(cleaned_text):
                matched_patterns.append(pat.pattern)

        if matched_patterns:
            cat_info = URGENT_CATEGORIES[category]
            advisory = generate_urgent_advisory(category, cat_info["title"])
            return {
                "is_urgent": True,
                "category": category,
                "title": cat_info["title"],
                "matched_patterns": matched_patterns,
                "advisory": advisory,
            }

    return None


def generate_urgent_advisory(category: str, title: str) -> str:
    """Construct deterministic emergency response message."""
    if category == "crisis":
        return (
            "## 🚨 Immediate Emergency & Crisis Assistance Required\n\n"
            "**If you or someone you know is in immediate danger or experiencing thoughts of self-harm, "
            "please reach out for immediate professional support:**\n\n"
            "- **In the US and Canada:** Call or text **988** to reach the Suicide & Crisis Lifeline, or call **911**.\n"
            "- **In the UK:** Call **111** (NHS mental health services) or **999** for immediate emergency.\n"
            "- **In the EU / International:** Call **112** or your local emergency telephone number.\n"
            "- **Crisis Text Line:** Text **HOME** to **741741** (US and Canada) or **85258** (UK).\n\n"
            "Please speak with someone immediately. Support is confidential, free, and available 24/7.\n\n"
            "> **Safety Notice:** Automated tools cannot provide crisis intervention or emergency medical care."
        )

    return (
        f"## 🚨 Emergency Medical Alert: {title}\n\n"
        "**Based on the symptoms you reported, you may be experiencing a medical emergency that requires "
        "immediate, in-person evaluation.**\n\n"
        "### Recommended Immediate Actions:\n"
        "1. **Call emergency services immediately:**\n"
        "   - **911** (United States & Canada)\n"
        "   - **999** (United Kingdom)\n"
        "   - **112** (European Union & International)\n"
        "   - Or your local emergency contact number.\n"
        "2. **Go to the nearest hospital Emergency Department (ED)** if transport can be safely and rapidly arranged.\n"
        "3. **Do not attempt to drive yourself** if experiencing severe chest pain, shortness of breath, dizziness, or weakness; call for an ambulance.\n"
        "4. If someone is with you, alert them to your symptoms immediately.\n\n"
        "**Do not wait for symptom follow-ups or online AI consultations during an acute medical emergency.**\n\n"
        "> **Important Clinical Limitation:** Automated heuristic screening is not a clinical assessment, cannot replace "
        "a physical examination or diagnostic testing, and does not guarantee detection of all medical emergencies. "
        "If you feel severely unwell, deteriorate, or are uncertain, seek emergency medical care immediately."
    )
