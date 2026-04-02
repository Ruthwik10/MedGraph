# MedGraph — Graph-Powered Patient Interoperability

> Cross-institution patient intelligence using Neo4j + RocketRide AI

---

## Stack
- **Neo4j** — graph database (patient journey modeling)
- **FastAPI** — Python backend
- **Claude API** — AI clinical reasoning layer
- **HTML/CSS/JS** — frontend dashboard

---

## Setup (Do This First)

### 1. Neo4j
Option A — Neo4j Desktop (recommended for demo):
- Download: https://neo4j.com/download/
- Create a new project → New Database
- Set password to: `medgraph123`
- Start the database

Option B — Neo4j Aura (cloud free tier):
- https://neo4j.com/cloud/platform/aura-graph-database/
- Create free instance → update .env with your URI + password

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `/backend`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=medgraph123
```

Start the API:
```bash
uvicorn main:app --reload --port 8000
```

### 3. Seed the Database

Once the API is running, call the seed endpoint once:
```bash
curl -X POST http://localhost:8000/seed
```

This loads the two synthetic FHIR bundles into Neo4j and runs identity resolution.

### 4. Frontend

Just open the file directly in your browser:
```
frontend/index.html
```

---

## Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/patients` | All patients across institutions |
| GET | `/patients/{id}/summary` | Full unified summary |
| GET | `/patients/{id}/medications` | Medications across all institutions |
| GET | `/patients/{id}/conflicts` | Allergy-medication conflicts |
| GET | `/patients/{id}/timeline` | Encounter history |
| GET | `/patients/{id}/observations` | Vitals and labs |
| POST | `/ai/ask` | Natural language clinical question |
| GET | `/ai/conflicts/{id}` | AI conflict explanation |
| GET | `/ai/care-gaps/{id}` | AI care gap analysis |
| POST | `/seed` | Load FHIR data into Neo4j |

---

## The Demo Flow (8 minutes)

1. Open the app — show the patient list with linked records badge
2. Select Maria Rivera — point out "2 institutions linked" via SAME_AS edge
3. Overview tab — show the ⚠️ allergy conflict (Amoxicillin + Penicillin allergy)
4. Medications tab — show unified list from 2 institutions
5. Timeline tab — show cross-institution encounter history
6. Ask AI tab — type: *"Are there any safety concerns I should know about before prescribing?"*
7. Watch AI traverse the graph and surface the conflict with explanation

**That's the story:** Same patient. Two hospitals. One prescribed a drug she's allergic to — because they didn't know. MedGraph caught it.

---

## Project Structure

```
medgraph/
├── backend/
│   ├── main.py          # FastAPI app + all endpoints
│   ├── graph.py         # Neo4j queries + identity resolution
│   ├── fhir_parser.py   # FHIR bundle parser
│   ├── ai.py            # AI clinical reasoning
│   └── requirements.txt
├── frontend/
│   └── index.html       # Full dashboard UI
└── data/
    ├── patient_a.json   # Northwestern Memorial (Hospital A)
    └── patient_b.json   # Rush University Medical Center (Hospital B)
```

---

## The Core Demo Story

**Maria Rivera** has COPD and hypertension. She's seen at:
- **Northwestern Memorial** — 2 encounters, prescribed Albuterol + Lisinopril, documented Penicillin allergy
- **Rush University** — Emergency admission, prescribed Amoxicillin (a penicillin-class antibiotic) ⚠️

Rush didn't know about the Penicillin allergy documented at Northwestern.

MedGraph resolves them as the same patient via SAME_AS edge, traverses both records, detects the conflict, and surfaces it in plain language.

**That's the gap. That's the graph. That's MedGraph.**
