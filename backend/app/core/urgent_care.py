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
    """
    Construct deterministic emergency response message.

    Emergency numbers listed below are static reference information for common
    regions. This tool does NOT infer a user's country from their symptoms or
    message content. If your emergency number is not listed, call your local
    emergency services number immediately.
    """
    if category == "crisis":
        return (
            "## 🚨 Immediate Emergency & Crisis Assistance Required\n\n"
            "**If you or someone you know is in immediate danger or experiencing thoughts of self-harm, "
            "please reach out for immediate professional support:**\n\n"
            "- **India:** Call **iCall: 9152987821** or **Vandrevala Foundation: 1860-2662-345** (24/7). "
            "For immediate physical danger call **112**.\n"
            "- **US and Canada:** Call or text **988** (Suicide & Crisis Lifeline) or call **911**.\n"
            "- **UK:** Call **111** (NHS mental health) or **999** (immediate emergency).\n"
            "- **EU / most countries:** Call **112** (pan-European emergency) or your local emergency number.\n"
            "- **Crisis Text Line (US/CA):** Text **HOME** to **741741**. "
            "**Crisis Text Line (UK):** Text **85258**.\n\n"
            "**If you are outside the regions listed above, call your local emergency telephone number immediately.**\n\n"
            "Please speak with someone now. Support is confidential, free, and available 24/7.\n\n"
            "> **Safety Notice:** Automated tools cannot provide crisis intervention or emergency medical care. "
            "Emergency service numbers listed are static reference information and may not be exhaustive."
        )

    return (
        f"## 🚨 Emergency Medical Alert: {title}\n\n"
        "**Based on the symptoms you reported, you may be experiencing a medical emergency that requires "
        "immediate, in-person evaluation. Do not wait — contact emergency services now.**\n\n"
        "### Call Emergency Services Immediately\n"
        "Contact the emergency number for your location:\n"
        "- **India: 112** (all-in-one national emergency)\n"
        "- **US and Canada: 911**\n"
        "- **UK: 999**\n"
        "- **EU and many other countries: 112**\n"
        "- **If your country is not listed:** Dial your local emergency services number immediately.\n\n"
        "### Additional Recommended Actions\n"
        "1. **Go to the nearest hospital Emergency Department (ED)** if safe and rapid transport can be arranged.\n"
        "2. **Do not attempt to drive yourself** if experiencing severe chest pain, shortness of breath, "
        "dizziness, or muscle weakness — call for an ambulance.\n"
        "3. **Alert anyone nearby** to your symptoms immediately.\n"
        "4. **Do not wait for online consultations or AI follow-up questions** during an acute medical emergency.\n\n"
        "> **Important Clinical Limitation:** This automated heuristic screening is NOT a clinical assessment, "
        "cannot replace a physical examination or diagnostic testing, and does not detect all medical emergencies. "
        "If you feel severely unwell, are deteriorating, or are uncertain whether this is an emergency, "
        "seek emergency care immediately — do not wait for further assessment."
    )

