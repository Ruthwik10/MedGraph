# MedGraph — Graph-Powered Patient Interoperability

> Built at HackWithChicago 3.0 — Top 5 Finalist

Every year, 1.3 million Americans end up in the emergency room 
because of preventable medication errors. Not because doctors 
are careless. Because a patient's records are scattered across 
different hospitals that don't talk to each other.

MedGraph connects a patient's complete medical history across 
every hospital they've visited into one intelligent graph — 
and flags what's going wrong before it causes harm.

---

## The Problem

FHIR standardized the format of health data. But it didn't fix 
the relationships. You can have 10 fully FHIR-compliant systems 
and still have zero visibility into what happened to that patient 
at the hospital across the street.

- **1.3 million** preventable ER visits from medication errors annually
- **$8 billion** wasted on duplicate testing every year
- **70%** of hospitals report cross-institutional care coordination 
  as a major unsolved challenge

Format was never the problem. **Relationships were.**

---

## What We Built

A graph-powered interoperability layer that connects patient 
records across institutions into one traversable graph — with 
a natural language AI interface on top so any clinician can 
just ask:

> *"What medications is this patient on across all systems?"*

MedGraph traverses the connected patient graph, surfaces the 
answer, and flags conflicts in plain language. At the point 
of care. Before harm happens.

---

## How It Works

### 1. Graph-Native Patient Identity Resolution
The same patient exists across hospitals as different records 
with different MRNs. MedGraph resolves them using probabilistic 
matching — date of birth, name similarity, phone, ZIP — and 
writes a `SAME_AS` edge connecting the records across institutions.

### 2. Cross-Institution Graph Traversal
Every clinical question is a relationship question. Neo4j 
traverses Patient → Medication → Allergy → Institution nodes 
in milliseconds — surfacing what no single hospital system 
could see alone.

### 3. AI Clinical Intelligence (RocketRide AI)
Three AI-powered features built on top of the graph:
- **Natural language → Cypher** — clinicians ask in plain English
- **Conflict explanation** — why it's dangerous, where it came from, 
  what to do
- **Anomaly detection** — vitals trending wrong, monitoring gaps, 
  duplicate medications, allergy conflicts — surfaced automatically 
  with a risk score

---

## The Demo Story

**Maria Rivera** has COPD and hypertension. She's been seen at:

- **Northwestern Memorial** — prescribed Albuterol + Lisinopril, 
  documented Penicillin allergy
- **Rush University** — emergency admission, prescribed Amoxicillin 
  ⚠️ (a penicillin-class antibiotic)

Rush didn't know about the Penicillin allergy at Northwestern.

MedGraph resolves them as the same patient via `SAME_AS` edge, 
traverses both records, detects the conflict, and surfaces it 
in plain language before the prescription is finalized.

**That's the gap. That's the graph. That's MedGraph.**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Graph Database | Neo4j |
| AI Reasoning | RocketRide AI / Claude API |
| Backend | Python + FastAPI |
| Data Standard | FHIR (Synthetic — HIPAA safe) |
| Frontend | HTML / CSS / JS |

---

## Setup

### 1. Neo4j
- Download [Neo4j Desktop](https://neo4j.com/download/)
- Create a new database, set password to `medgraph123`
- Start the database

### 2. Backend
```bash
cd backend
pip install -r requirements.txt
```

Create `/backend/.env`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=medgraph123
```

Start the API:
```bash
uvicorn main:app --reload --port 8000
```

### 3. Seed the Graph
```bash
curl -X POST http://localhost:8000/seed
```

### 4. Frontend
Open `frontend/index.html` directly in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/patients` | All patients across institutions |
| GET | `/patients/{id}/summary` | Full unified summary |
| GET | `/patients/{id}/medications` | Medications across all institutions |
| GET | `/patients/{id}/conflicts` | Allergy-medication conflicts |
| GET | `/patients/{id}/timeline` | Encounter history |
| GET | `/patients/{id}/observations` | Vitals and labs |
| GET | `/patients/{id}/anomalies` | Anomaly detection report |
| POST | `/ai/ask` | Natural language clinical question |
| GET | `/ai/anomalies/{id}` | AI anomaly explanation |
| GET | `/ai/care-gaps/{id}` | AI care gap analysis |
| POST | `/seed` | Load FHIR data into Neo4j |

---

## Project Structure
```
medgraph/
├── backend/
│   ├── main.py          # FastAPI app + all endpoints
│   ├── graph.py         # Neo4j queries + identity resolution
│   ├── fhir_parser.py   # FHIR bundle parser
│   ├── ai.py            # AI clinical reasoning
│   ├── anomaly.py       # Anomaly detection engine
│   └── requirements.txt
├── frontend/
│   └── index.html       # Full dashboard UI
└── data/
    ├── patient_a.json   # Northwestern Memorial
    └── patient_b.json   # Rush University Medical Center
```

---

## Team

| Name | Role | Background |
|---|---|---|
| Abdul Azeez | Clinical Lead & Graph Architect | MS Health Information Technology , DePaul University |
| Ruthwik | AI & Backend Engineer | MS Artificial Intelligence, Illinois Tech |
| Devang | Business & Product Strategy | MS Bussines Analytics , Depaul University |

---
