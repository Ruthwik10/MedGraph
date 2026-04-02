from neo4j import GraphDatabase
from difflib import SequenceMatcher
import os

# ── Connection ────────────────────────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "medgraph123")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_session():
    return driver.session()


# ── Seed Graph ────────────────────────────────────────────────────────────────

def seed_graph(bundles: list[dict]):
    """Load all parsed FHIR bundles into Neo4j."""
    with get_session() as session:
        # Clear existing data
        session.run("MATCH (n) DETACH DELETE n")
        print("Cleared existing graph.")

        for bundle in bundles:
            inst_id = bundle["institution_id"]
            inst_name = bundle["institution"]

            # Institution node
            session.run("""
                MERGE (o:Institution {id: $id})
                SET o.name = $name
            """, id=inst_id, name=inst_name)

            # Patient nodes
            for p in bundle["patients"]:
                session.run("""
                    MERGE (pt:Patient {id: $id})
                    SET pt.family = $family,
                        pt.given = $given,
                        pt.dob = $dob,
                        pt.gender = $gender,
                        pt.zip = $zip,
                        pt.city = $city,
                        pt.phone = $phone,
                        pt.institution_id = $inst_id
                """, **p, inst_id=inst_id)

            # Encounter nodes + relationships
            for e in bundle["encounters"]:
                session.run("""
                    MERGE (en:Encounter {id: $id})
                    SET en.start = $start,
                        en.end = $end,
                        en.type = $type,
                        en.reason = $reason,
                        en.provider_name = $provider_name,
                        en.provider_id = $provider_id,
                        en.institution_id = $inst_id
                    WITH en
                    MATCH (pt:Patient {id: $patient_id})
                    MERGE (pt)-[:HAD_ENCOUNTER]->(en)
                    WITH en
                    MATCH (o:Institution {id: $inst_id})
                    MERGE (en)-[:AT_INSTITUTION]->(o)
                """, **e, inst_id=inst_id)

            # Condition nodes + relationships
            for c in bundle["conditions"]:
                session.run("""
                    MERGE (cd:Condition {id: $id})
                    SET cd.code = $code,
                        cd.system = $system,
                        cd.display = $display,
                        cd.onset = $onset,
                        cd.status = $status
                    WITH cd
                    MATCH (pt:Patient {id: $patient_id})
                    MERGE (pt)-[:HAS_CONDITION]->(cd)
                """, **c)

            # Medication nodes + relationships
            for m in bundle["medications"]:
                session.run("""
                    MERGE (med:Medication {id: $id})
                    SET med.rxnorm_code = $rxnorm_code,
                        med.name = $name,
                        med.status = $status,
                        med.authored_on = $authored_on,
                        med.requester = $requester,
                        med.note = $note,
                        med.institution_id = $inst_id
                    WITH med
                    MATCH (pt:Patient {id: $patient_id})
                    MERGE (pt)-[:PRESCRIBED]->(med)
                """, **m, inst_id=inst_id)

            # Allergy nodes + relationships
            for a in bundle["allergies"]:
                session.run("""
                    MERGE (al:Allergy {id: $id})
                    SET al.substance_code = $substance_code,
                        al.substance = $substance,
                        al.reaction = $reaction,
                        al.severity = $severity,
                        al.recorded_date = $recorded_date
                    WITH al
                    MATCH (pt:Patient {id: $patient_id})
                    MERGE (pt)-[:HAS_ALLERGY]->(al)
                """, **a)

            # Observation nodes + relationships
            for ob in bundle["observations"]:
                session.run("""
                    MERGE (obs:Observation {id: $id})
                    SET obs.loinc_code = $loinc_code,
                        obs.display = $display,
                        obs.value = $value,
                        obs.unit = $unit,
                        obs.date = $date
                    WITH obs
                    MATCH (pt:Patient {id: $patient_id})
                    MERGE (pt)-[:HAS_OBSERVATION]->(obs)
                """, **ob)

        print("Graph seeded.")
        _resolve_identities()


# ── Identity Resolution ───────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _resolve_identities():
    """
    Probabilistic Master Patient Index:
    Link patients across institutions via SAME_AS edge
    if DOB matches exactly + name similarity > 0.7 + phone matches or zip proximity.
    """
    with get_session() as session:
        patients = session.run("MATCH (p:Patient) RETURN p").data()
        patients = [r["p"] for r in patients]

        linked = set()
        for i, p1 in enumerate(patients):
            for j, p2 in enumerate(patients):
                if i >= j:
                    continue
                if p1["institution_id"] == p2["institution_id"]:
                    continue

                pair_key = tuple(sorted([p1["id"], p2["id"]]))
                if pair_key in linked:
                    continue

                score = 0.0

                # DOB exact match — high weight
                if p1.get("dob") == p2.get("dob"):
                    score += 0.4

                # Name similarity — medium weight
                name1 = f"{p1.get('family', '')} {p1.get('given', '')}"
                name2 = f"{p2.get('family', '')} {p2.get('given', '')}"
                name_sim = _similarity(name1, name2)
                score += name_sim * 0.3

                # Phone match — high weight
                if p1.get("phone") and p1.get("phone") == p2.get("phone"):
                    score += 0.3

                # ZIP proximity (same city area)
                elif p1.get("zip", "")[:3] == p2.get("zip", "")[:3]:
                    score += 0.1

                if score >= 0.75:
                    session.run("""
                        MATCH (p1:Patient {id: $id1})
                        MATCH (p2:Patient {id: $id2})
                        MERGE (p1)-[:SAME_AS {confidence: $score}]->(p2)
                        MERGE (p2)-[:SAME_AS {confidence: $score}]->(p1)
                    """, id1=p1["id"], id2=p2["id"], score=round(score, 2))
                    linked.add(pair_key)
                    print(f"Identity resolved: {p1['id']} ↔ {p2['id']} (confidence: {round(score, 2)})")


# ── Clinical Queries ──────────────────────────────────────────────────────────

def get_all_patients():
    """Return all patients with their institution."""
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient)
            OPTIONAL MATCH (p)-[:SAME_AS]-(linked:Patient)
            RETURN p.id AS id,
                   p.given + ' ' + p.family AS name,
                   p.dob AS dob,
                   p.institution_id AS institution,
                   collect(DISTINCT linked.id) AS linked_ids
        """)
        return [dict(r) for r in result]


def get_unified_medications(patient_id: str) -> list[dict]:
    """
    Get all medications for a patient across ALL institutions
    by traversing SAME_AS edges.
    """
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient {id: $pid})
            OPTIONAL MATCH (p)-[:SAME_AS*0..1]-(linked:Patient)
            WITH collect(DISTINCT p) + collect(DISTINCT linked) AS all_patients
            UNWIND all_patients AS pt
            MATCH (pt)-[:PRESCRIBED]->(med:Medication)
            RETURN DISTINCT med.name AS medication,
                   med.rxnorm_code AS rxnorm,
                   med.status AS status,
                   med.authored_on AS prescribed_on,
                   med.requester AS prescriber,
                   med.institution_id AS institution,
                   med.note AS note
            ORDER BY med.authored_on DESC
        """, pid=patient_id)
        return [dict(r) for r in result]


def get_allergy_conflicts(patient_id: str) -> list[dict]:
    """
    Detect medications prescribed that conflict with documented allergies —
    across all institutions via SAME_AS traversal.
    """
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient {id: $pid})
            OPTIONAL MATCH (p)-[:SAME_AS*0..1]-(linked:Patient)
            WITH collect(DISTINCT p) + collect(DISTINCT linked) AS all_patients
            UNWIND all_patients AS pt
            MATCH (pt)-[:HAS_ALLERGY]->(al:Allergy)
            MATCH (pt2)-[:PRESCRIBED]->(med:Medication)
            WHERE pt2 IN all_patients
            AND (
                toLower(med.name) CONTAINS toLower(al.substance)
                OR toLower(al.substance) CONTAINS 'penicillin'
                AND toLower(med.name) CONTAINS 'amoxicillin'
            )
            RETURN al.substance AS allergen,
                   al.reaction AS reaction,
                   al.severity AS severity,
                   al.recorded_date AS allergy_recorded,
                   med.name AS conflicting_medication,
                   med.authored_on AS prescribed_on,
                   med.institution_id AS prescribed_at,
                   med.requester AS prescriber
        """, pid=patient_id)
        return [dict(r) for r in result]


def get_encounter_timeline(patient_id: str) -> list[dict]:
    """Get full encounter history across all institutions."""
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient {id: $pid})
            OPTIONAL MATCH (p)-[:SAME_AS*0..1]-(linked:Patient)
            WITH collect(DISTINCT p) + collect(DISTINCT linked) AS all_patients
            UNWIND all_patients AS pt
            MATCH (pt)-[:HAD_ENCOUNTER]->(en:Encounter)-[:AT_INSTITUTION]->(org:Institution)
            RETURN en.start AS date,
                   en.type AS type,
                   en.reason AS reason,
                   en.provider_name AS provider,
                   org.name AS institution
            ORDER BY en.start DESC
        """, pid=patient_id)
        return [dict(r) for r in result]


def get_observations(patient_id: str) -> list[dict]:
    """Get all lab results and vitals across institutions."""
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient {id: $pid})
            OPTIONAL MATCH (p)-[:SAME_AS*0..1]-(linked:Patient)
            WITH collect(DISTINCT p) + collect(DISTINCT linked) AS all_patients
            UNWIND all_patients AS pt
            MATCH (pt)-[:HAS_OBSERVATION]->(obs:Observation)
            RETURN obs.display AS test,
                   obs.value AS value,
                   obs.unit AS unit,
                   obs.date AS date,
                   pt.institution_id AS institution
            ORDER BY obs.date DESC
        """, pid=patient_id)
        return [dict(r) for r in result]


def get_patient_summary(patient_id: str) -> dict:
    """Full patient summary across all institutions."""
    return {
        "medications": get_unified_medications(patient_id),
        "conflicts": get_allergy_conflicts(patient_id),
        "encounters": get_encounter_timeline(patient_id),
        "observations": get_observations(patient_id),
    }


def get_graph_visualization(patient_id: str) -> dict:
    """Return nodes and edges for frontend graph visualization."""
    with get_session() as session:
        result = session.run("""
            MATCH (p:Patient {id: $pid})
            OPTIONAL MATCH (p)-[:SAME_AS*0..1]-(linked:Patient)
            WITH collect(DISTINCT p) + collect(DISTINCT linked) AS all_patients
            UNWIND all_patients AS pt
            OPTIONAL MATCH (pt)-[r1:HAD_ENCOUNTER]->(en:Encounter)-[:AT_INSTITUTION]->(org:Institution)
            OPTIONAL MATCH (pt)-[r2:PRESCRIBED]->(med:Medication)
            OPTIONAL MATCH (pt)-[r3:HAS_ALLERGY]->(al:Allergy)
            OPTIONAL MATCH (pt)-[r4:HAS_CONDITION]->(cd:Condition)
            OPTIONAL MATCH (pt)-[:SAME_AS]-(other:Patient)
            RETURN pt, en, org, med, al, cd, other
        """, pid=patient_id)

        nodes = {}
        edges = []

        for record in result:
            for key in ["pt", "en", "org", "med", "al", "cd", "other"]:
                node = record.get(key)
                if node and hasattr(node, 'id'):
                    nid = str(node.id)
                    if nid not in nodes:
                        labels = list(node.labels)
                        props = dict(node)
                        nodes[nid] = {
                            "id": nid,
                            "label": labels[0] if labels else "Node",
                            "properties": props,
                            "display": _node_display(labels[0] if labels else "", props)
                        }

        return {"nodes": list(nodes.values()), "edges": edges}


def _node_display(label: str, props: dict) -> str:
    if label == "Patient":
        return f"{props.get('given', '')} {props.get('family', '')}"
    if label == "Medication":
        return props.get("name", "Medication")
    if label == "Condition":
        return props.get("display", "Condition")
    if label == "Encounter":
        return props.get("reason", "Encounter")
    if label == "Institution":
        return props.get("name", "Institution")
    if label == "Allergy":
        return f"⚠️ {props.get('substance', 'Allergy')}"
    if label == "Observation":
        return f"{props.get('display', '')}: {props.get('value', '')} {props.get('unit', '')}"
    return label
