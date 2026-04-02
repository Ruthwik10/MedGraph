from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys
import os

sys.path.append(os.path.dirname(__file__))

from graph import (
    get_all_patients,
    get_unified_medications,
    get_allergy_conflicts,
    get_encounter_timeline,
    get_observations,
    get_patient_summary,
    get_graph_visualization,
)
from ai import answer_clinical_question, explain_conflicts, detect_care_gaps, explain_anomalies
from anomaly import run_full_anomaly_detection

app = FastAPI(title="MedGraph API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ────────────────────────────────────────────────────────────

class QuestionRequest(BaseModel):
    patient_id: str
    question: str


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "MedGraph running", "version": "1.0.0"}


# ── Patient Endpoints ─────────────────────────────────────────────────────────

@app.get("/patients")
def list_patients():
    """List all patients across all institutions."""
    try:
        return {"patients": get_all_patients()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/summary")
def patient_summary(patient_id: str):
    """Full patient summary across all institutions."""
    try:
        return get_patient_summary(patient_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/medications")
def patient_medications(patient_id: str):
    """All medications across institutions via graph traversal."""
    try:
        return {"medications": get_unified_medications(patient_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/conflicts")
def patient_conflicts(patient_id: str):
    """Allergy-medication conflicts detected across institutions."""
    try:
        return {"conflicts": get_allergy_conflicts(patient_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/timeline")
def patient_timeline(patient_id: str):
    """Encounter timeline across all institutions."""
    try:
        return {"encounters": get_encounter_timeline(patient_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/observations")
def patient_observations(patient_id: str):
    """Labs and vitals across all institutions."""
    try:
        return {"observations": get_observations(patient_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients/{patient_id}/graph")
def patient_graph(patient_id: str):
    """Graph nodes and edges for visualization."""
    try:
        return get_graph_visualization(patient_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI Endpoints ──────────────────────────────────────────────────────────────

@app.post("/ai/ask")
async def ask_question(req: QuestionRequest):
    """
    Natural language clinical question answering.
    AI pulls graph data and generates a clinical answer.
    """
    try:
        answer = await answer_clinical_question(req.patient_id, req.question)
        return {"answer": answer, "patient_id": req.patient_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/conflicts/{patient_id}")
async def ai_conflict_explanation(patient_id: str):
    """AI-generated plain-language explanation of all detected conflicts."""
    try:
        explanation = await explain_conflicts(patient_id)
        return {"explanation": explanation, "patient_id": patient_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/care-gaps/{patient_id}")
async def ai_care_gaps(patient_id: str):
    """AI-generated care gap analysis."""
    try:
        gaps = await detect_care_gaps(patient_id)
        return {"care_gaps": gaps, "patient_id": patient_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Anomaly Detection Endpoints ──────────────────────────────────────────────

@app.get("/patients/{patient_id}/anomalies")
def patient_anomalies(patient_id: str):
    """
    Run full anomaly detection on patient vitals + medications.
    Returns risk score, scored anomalies, and trend series for charts.
    """
    try:
        summary = get_patient_summary(patient_id)
        report = run_full_anomaly_detection(summary)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/anomalies/{patient_id}")
async def ai_anomaly_explanation(patient_id: str):
    """AI plain-language explanation of all detected anomalies."""
    try:
        summary = get_patient_summary(patient_id)
        report = run_full_anomaly_detection(summary)
        explanation = await explain_anomalies(patient_id, report)
        return {"explanation": explanation, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Seed Endpoint (for demo setup) ────────────────────────────────────────────

@app.post("/seed")
def seed_database():
    """Load synthetic FHIR data into Neo4j. Run once on startup."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from fhir_parser import load_all_bundles
        from graph import seed_graph
        bundles = load_all_bundles(data_dir=os.path.join(os.path.dirname(__file__), "../data"))
        seed_graph(bundles)
        return {"status": "Database seeded successfully", "bundles_loaded": len(bundles)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
