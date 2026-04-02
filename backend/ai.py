import httpx
import json
from graph import get_patient_summary, get_allergy_conflicts, get_unified_medications

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

HEADERS = {
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
}

# ── Natural Language Query Handler ────────────────────────────────────────────

NL_SYSTEM_PROMPT = """You are MedGraph AI — a clinical intelligence assistant built on top of a Neo4j patient graph.

You have access to a patient's unified medical record pulled from multiple healthcare institutions. 
The data includes: medications, allergies, encounters, observations (labs/vitals), and conditions — all connected across institutions via graph traversal.

When a clinician asks a question:
1. Identify what data is needed
2. Answer directly and clinically
3. Flag any safety concerns prominently with ⚠️
4. Always cite which institution the data came from
5. Be concise — clinicians are busy

Format your response in plain clinical language. No jargon overload. No unnecessary hedging."""


async def answer_clinical_question(patient_id: str, question: str) -> str:
    """
    Takes a natural language question from a clinician,
    pulls relevant graph data, and returns an AI-generated clinical answer.
    """
    # Pull all relevant data from graph
    summary = get_patient_summary(patient_id)

    context = f"""
PATIENT GRAPH DATA (pulled from Neo4j across all institutions):

MEDICATIONS ({len(summary['medications'])} found):
{json.dumps(summary['medications'], indent=2)}

ALLERGY CONFLICTS DETECTED ({len(summary['conflicts'])} found):
{json.dumps(summary['conflicts'], indent=2)}

ENCOUNTER TIMELINE ({len(summary['encounters'])} encounters):
{json.dumps(summary['encounters'], indent=2)}

OBSERVATIONS / VITALS ({len(summary['observations'])} found):
{json.dumps(summary['observations'], indent=2)}

CLINICIAN QUESTION: {question}
"""

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": NL_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": context}]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        data = response.json()
        return data["content"][0]["text"]


# ── Conflict Explainer ────────────────────────────────────────────────────────

CONFLICT_SYSTEM_PROMPT = """You are a clinical safety AI. Your job is to explain medication-allergy conflicts clearly and urgently.

For each conflict:
- State what the conflict is in plain language
- Explain WHY it's dangerous (mechanism if relevant)
- Say where the allergy was documented vs where the medication was prescribed
- Recommend immediate action

Be direct. This is a patient safety issue."""


async def explain_conflicts(patient_id: str) -> str:
    """Generate plain-language explanation of all detected conflicts."""
    conflicts = get_allergy_conflicts(patient_id)

    if not conflicts:
        return "No allergy-medication conflicts detected across all institutions."

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": CONFLICT_SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"Explain these detected conflicts:\n{json.dumps(conflicts, indent=2)}"
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        data = response.json()
        return data["content"][0]["text"]


# ── Anomaly Explainer ─────────────────────────────────────────────────────────

ANOMALY_SYSTEM_PROMPT = """You are MedGraph's clinical anomaly AI. You analyze detected anomalies in a patient's health record and explain what's going wrong in plain clinical language.

You will receive a structured anomaly report containing:
- A risk score and level
- Individual anomalies (vital anomalies, trend anomalies, medication conflicts, monitoring gaps)

Your job:
1. Open with the overall clinical picture in 1-2 sentences
2. Walk through each critical anomaly first, then warnings
3. For each — explain what it means clinically and why it matters
4. Close with a clear recommended action list

Be direct, clinical, urgent where needed. Flag ⚠️ for critical items."""


async def explain_anomalies(patient_id: str, report: dict) -> str:
    """Generate plain-language clinical explanation of all detected anomalies."""
    if not report.get("anomalies"):
        return "No anomalies detected in this patient's record. Vitals and medications appear within normal parameters."

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": ANOMALY_SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"Explain these anomalies for patient {patient_id}:\n{json.dumps(report, indent=2)}"
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        data = response.json()
        return data["content"][0]["text"]


CARE_GAP_SYSTEM_PROMPT = """You are a clinical quality AI. Analyze a patient's encounter and observation history and identify care gaps.

Look for:
- Missing follow-ups after hospitalizations
- Abnormal vitals not addressed in subsequent encounters
- Overdue screenings based on conditions
- Medications prescribed without documented follow-up

Be specific. Reference dates and institutions. Flag urgency level."""


async def detect_care_gaps(patient_id: str) -> str:
    """Analyze patient history and surface care gaps."""
    summary = get_patient_summary(patient_id)

    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": CARE_GAP_SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": f"Analyze this patient's history for care gaps:\n{json.dumps(summary, indent=2)}"
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        data = response.json()
        return data["content"][0]["text"]
