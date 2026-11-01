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


import os

DEFAULT_CRISIS_LOCALE: str = os.getenv("DEFAULT_CRISIS_LOCALE", "IN").strip().upper()


def generate_urgent_advisory(
    category: str,
    title: str,
    locale: Optional[str] = None,
) -> str:
    """
    Construct deterministic emergency response message.

    Emergency numbers listed below are static reference information for common
    regions. This tool does NOT infer a user's country from their symptoms or
    message content. If your emergency number is not listed, call your local
    emergency services number immediately.
    """
    active_locale = (locale or DEFAULT_CRISIS_LOCALE).upper()

    if category == "crisis":
        india_block = (
            "- **India:**\n"
            "  - **Immediate Danger / Emergency:** Call **112** (All-in-one National Emergency Service)\n"
            "  - **Tele-MANAS:** Call **14416** or **1800-891-4416** (24/7 Toll-free National Mental Health Helpline, Ministry of Health & Family Welfare, Government of India)\n"
            "  - **Vandrevala Foundation:** Call or WhatsApp **+91 9999 666 555** (24/7 Free Confidential Support)\n"
            "  - **KIRAN Helpline:** Call **1800-599-0019** (24/7 Mental Health Rehabilitation Helpline, Govt of India)\n"
            "  - **TISS iCALL:** Call **9152987821** or **022-25521111** (Mon–Sat, 10:00 AM – 8:00 PM IST)"
        )
        us_block = "- **US and Canada:** Call or text **988** (Suicide & Crisis Lifeline) or call **911**."
        uk_block = "- **UK:** Call **111** (NHS mental health services) or **999** (immediate emergency)."
        eu_block = "- **EU / International:** Call **112** (pan-European emergency) or your local emergency number."
        text_lines = "- **Crisis Text Line:** Text **HOME** to **741741** (US and Canada) or **85258** (UK)."

        if active_locale == "IN":
            blocks = [india_block, text_lines, eu_block, us_block]
        elif active_locale in ("US", "CA"):
            blocks = [us_block, text_lines, india_block]
        elif active_locale == "UK":
            blocks = [uk_block, text_lines, india_block]
        else:
            blocks = [india_block, us_block, uk_block, eu_block, text_lines]

        regional_content = "\n".join(blocks)

        return (
            "## 🚨 Immediate Emergency & Crisis Assistance Required\n\n"
            "**If you or someone you know is in immediate danger or experiencing thoughts of self-harm, "
            "please reach out for immediate professional support:**\n\n"
            f"{regional_content}\n\n"
            "**If your country or region is not listed above, dial your local emergency telephone number or visit the nearest emergency facility immediately.**\n\n"
            "Please speak with someone now. Professional support is confidential and free.\n\n"
            "> **Safety Notice:** Automated tools cannot provide crisis intervention or emergency medical care. "
            "Emergency service numbers listed are static reference information and may not be exhaustive."
        )

    # General medical emergency advisory
    if active_locale == "IN":
        emergency_contacts = (
            "- **India National Emergency:** Call **112** (All-in-one Emergency Response: Medical, Police, Fire)\n"
            "- **Medical Ambulance Service:** Call **108** (Emergency Critical Care Ambulance where available)\n"
            "- **National Ambulance Transport:** Call **102** (Free transport for maternal and infant care)\n"
            "- **Other Regions / International:** Call **911** (US/Canada), **999** (UK), **112** (EU), or your local emergency number."
        )
    else:
        emergency_contacts = (
            "- **India: 112** (National Emergency) / **108** (Ambulance)\n"
            "- **US and Canada: 911**\n"
            "- **UK: 999**\n"
            "- **EU: 112**\n"
            "- **Other regions:** Dial your local emergency medical service immediately."
        )

    return (
        f"## 🚨 Emergency Medical Alert: {title}\n\n"
        "**Based on the symptoms you reported, you may be experiencing a medical emergency that requires "
        "immediate, in-person evaluation. Do not wait — contact emergency services now.**\n\n"
        "### Call Emergency Services Immediately\n"
        "Contact the emergency services number for your location:\n"
        f"{emergency_contacts}\n\n"
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


