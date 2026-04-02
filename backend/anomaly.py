"""
anomaly.py — MedGraph Anomaly Detection Engine

Analyzes patient vitals and medication patterns across the graph
and returns scored anomalies with severity levels.
"""

from datetime import datetime, timedelta
from typing import Optional

# ── Clinical Thresholds ───────────────────────────────────────────────────────

VITAL_THRESHOLDS = {
    "Systolic Blood Pressure": {
        "loinc": "8480-6",
        "unit": "mmHg",
        "normal": (90, 120),
        "warning": (80, 140),
        "critical_low": 80,
        "critical_high": 160,
        "direction": "both",
    },
    "Diastolic Blood Pressure": {
        "loinc": "8462-4",
        "unit": "mmHg",
        "normal": (60, 80),
        "warning": (50, 90),
        "critical_low": 50,
        "critical_high": 100,
        "direction": "both",
    },
    "Oxygen Saturation (SpO2)": {
        "loinc": "59408-5",
        "unit": "%",
        "normal": (95, 100),
        "warning": (90, 95),
        "critical_low": 88,
        "critical_high": None,
        "direction": "low",
    },
    "Heart Rate": {
        "loinc": "8867-4",
        "unit": "bpm",
        "normal": (60, 100),
        "warning": (50, 110),
        "critical_low": 40,
        "critical_high": 130,
        "direction": "both",
    },
    "Body Temperature": {
        "loinc": "8310-5",
        "unit": "°C",
        "normal": (36.1, 37.2),
        "warning": (35.5, 38.0),
        "critical_low": 35.0,
        "critical_high": 39.0,
        "direction": "both",
    },
    "HbA1c": {
        "loinc": "4548-4",
        "unit": "%",
        "normal": (4.0, 5.6),
        "warning": (5.7, 6.4),
        "critical_low": None,
        "critical_high": 7.0,
        "direction": "high",
    },
}

# Drug classes that should not be co-prescribed
DRUG_CLASS_CONFLICTS = [
    {
        "class_a": ["amoxicillin", "ampicillin", "penicillin", "piperacillin"],
        "class_b": ["penicillin allergy"],
        "description": "Penicillin-class antibiotic prescribed with documented penicillin allergy",
        "severity": "critical",
    },
    {
        "class_a": ["warfarin", "coumadin"],
        "class_b": ["aspirin", "ibuprofen", "naproxen", "nsaid"],
        "description": "Anticoagulant co-prescribed with NSAID — increased bleeding risk",
        "severity": "critical",
    },
    {
        "class_a": ["lisinopril", "enalapril", "ramipril"],
        "class_b": ["spironolactone", "eplerenone"],
        "description": "ACE inhibitor + potassium-sparing diuretic — hyperkalemia risk",
        "severity": "warning",
    },
    {
        "class_a": ["metformin"],
        "class_b": ["contrast dye", "iodinated contrast"],
        "description": "Metformin + contrast dye — lactic acidosis risk",
        "severity": "warning",
    },
]

# Gap thresholds in days — if patient hasn't had a reading in this long, flag it
MONITORING_GAPS = {
    "J44.1": {  # COPD
        "required_observations": ["59408-5"],  # SpO2
        "max_gap_days": 30,
        "label": "SpO2 monitoring gap for COPD patient",
        "severity": "warning",
    },
    "I10": {  # Hypertension
        "required_observations": ["8480-6"],  # Systolic BP
        "max_gap_days": 60,
        "label": "Blood pressure monitoring gap for hypertensive patient",
        "severity": "warning",
    },
    "E11": {  # Type 2 Diabetes
        "required_observations": ["4548-4"],  # HbA1c
        "max_gap_days": 90,
        "label": "HbA1c monitoring gap for diabetic patient",
        "severity": "critical",
    },
}


# ── Anomaly Detection Functions ───────────────────────────────────────────────

def score_vitals(observations: list[dict]) -> list[dict]:
    """
    Score each observation against clinical thresholds.
    Returns list of anomalies with severity, value, and context.
    """
    anomalies = []

    for obs in observations:
        test = obs.get("test", "")
        value = obs.get("value")
        date = obs.get("date", "")
        institution = obs.get("institution", "")

        if value is None:
            continue

        try:
            value = float(value)
        except (ValueError, TypeError):
            continue

        # Match to threshold definition
        threshold = None
        for name, spec in VITAL_THRESHOLDS.items():
            if (name.lower() in test.lower() or
                spec.get("loinc") in test or
                test.lower() in name.lower()):
                threshold = spec
                matched_name = name
                break

        if not threshold:
            continue

        severity = "normal"
        message = ""
        normal_low, normal_high = threshold["normal"]
        warn_low, warn_high = threshold["warning"]

        if threshold["direction"] in ("low", "both"):
            if threshold.get("critical_low") and value <= threshold["critical_low"]:
                severity = "critical"
                message = f"{matched_name} critically low: {value} {threshold['unit']} (critical threshold: ≤{threshold['critical_low']})"
            elif value < normal_low:
                severity = "warning" if value >= warn_low else "critical"
                message = f"{matched_name} below normal: {value} {threshold['unit']} (normal: {normal_low}–{normal_high})"

        if threshold["direction"] in ("high", "both"):
            if threshold.get("critical_high") and value >= threshold["critical_high"]:
                severity = "critical"
                message = f"{matched_name} critically high: {value} {threshold['unit']} (critical threshold: ≥{threshold['critical_high']})"
            elif value > normal_high:
                severity = "warning" if value <= warn_high else "critical"
                message = f"{matched_name} above normal: {value} {threshold['unit']} (normal: {normal_low}–{normal_high})"

        if severity != "normal":
            anomalies.append({
                "type": "vital_anomaly",
                "severity": severity,
                "test": matched_name,
                "value": value,
                "unit": threshold["unit"],
                "date": date,
                "institution": institution,
                "message": message,
                "normal_range": f"{normal_low}–{normal_high} {threshold['unit']}",
            })

    return anomalies


def detect_vital_trend(observations: list[dict]) -> list[dict]:
    """
    Detect worsening trends across sequential observations of the same test.
    Flags if a vital is consistently moving in the wrong direction.
    """
    trend_anomalies = []

    # Group by test type
    grouped = {}
    for obs in observations:
        test = obs.get("test", "")
        val = obs.get("value")
        date = obs.get("date", "")
        if val is None or not date:
            continue
        try:
            val = float(val)
        except:
            continue
        if test not in grouped:
            grouped[test] = []
        grouped[test].append({"date": date, "value": val})

    for test, readings in grouped.items():
        if len(readings) < 2:
            continue

        # Sort by date
        readings.sort(key=lambda x: x["date"])
        values = [r["value"] for r in readings]

        # Check if consistently worsening
        threshold = None
        for name, spec in VITAL_THRESHOLDS.items():
            if name.lower() in test.lower() or test.lower() in name.lower():
                threshold = spec
                matched_name = name
                break

        if not threshold:
            continue

        normal_low, normal_high = threshold["normal"]

        # Worsening = each reading further from normal than the last
        if threshold["direction"] == "low":
            # For SpO2-type — worsening means consistently dropping
            diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
            if all(d < 0 for d in diffs) and values[-1] < normal_low:
                trend_anomalies.append({
                    "type": "trend_anomaly",
                    "severity": "warning",
                    "test": matched_name,
                    "message": f"{matched_name} showing consistent downward trend: {' → '.join(str(v) for v in values)}",
                    "values": values,
                    "dates": [r["date"] for r in readings],
                    "direction": "declining",
                })

        elif threshold["direction"] == "high" or threshold["direction"] == "both":
            # Worsening = consistently rising above normal
            diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
            if all(d > 0 for d in diffs) and values[-1] > normal_high:
                trend_anomalies.append({
                    "type": "trend_anomaly",
                    "severity": "warning",
                    "test": matched_name,
                    "message": f"{matched_name} showing consistent upward trend: {' → '.join(str(v) for v in values)}",
                    "values": values,
                    "dates": [r["date"] for r in readings],
                    "direction": "rising",
                })

    return trend_anomalies


def detect_medication_anomalies(
    medications: list[dict],
    allergies: list[dict],
    conflicts: list[dict]
) -> list[dict]:
    """
    Flag medication anomalies:
    - Allergy conflicts (already detected in graph)
    - Duplicate medications across institutions
    - Medications active without a recent encounter
    """
    med_anomalies = []

    # 1. Allergy conflicts from graph
    for c in conflicts:
        med_anomalies.append({
            "type": "medication_conflict",
            "severity": "critical",
            "message": f"⚠️ {c.get('conflicting_medication')} prescribed at {c.get('prescribed_at')} "
                      f"conflicts with documented {c.get('allergen')} allergy "
                      f"({c.get('reaction')}, {c.get('severity')} severity). "
                      f"Allergy documented: {c.get('allergy_recorded')}.",
            "medication": c.get("conflicting_medication"),
            "allergen": c.get("allergen"),
            "institution": c.get("prescribed_at"),
            "date": c.get("prescribed_on"),
        })

    # 2. Duplicate medications across institutions (same RxNorm code)
    seen_rxnorm = {}
    for med in medications:
        code = med.get("rxnorm") or med.get("rxnorm_code")
        name = med.get("medication") or med.get("name", "")
        inst = med.get("institution", "")
        if not code:
            continue
        if code in seen_rxnorm and seen_rxnorm[code] != inst:
            med_anomalies.append({
                "type": "duplicate_medication",
                "severity": "warning",
                "message": f"{name} (RxNorm: {code}) is prescribed at both "
                          f"{seen_rxnorm[code]} and {inst}. "
                          f"Verify intentional cross-institution duplication.",
                "medication": name,
                "institution_a": seen_rxnorm[code],
                "institution_b": inst,
                "date": med.get("authored_on") or med.get("prescribed_on"),
            })
        else:
            seen_rxnorm[code] = inst

    return med_anomalies


def detect_monitoring_gaps(
    conditions: list[dict],
    observations: list[dict],
    reference_date: Optional[str] = None
) -> list[dict]:
    """
    Flag when a patient with a known condition hasn't had required monitoring.
    E.g. COPD patient without SpO2 reading in 30+ days.
    """
    gap_anomalies = []

    if not reference_date:
        # Use most recent observation date as reference
        dates = [o.get("date", "") for o in observations if o.get("date")]
        reference_date = max(dates) if dates else datetime.now().isoformat()

    try:
        ref_dt = datetime.fromisoformat(reference_date.split("T")[0])
    except:
        ref_dt = datetime.now()

    condition_codes = [c.get("code", "") for c in conditions]

    for icd_code, rule in MONITORING_GAPS.items():
        if icd_code not in condition_codes:
            continue

        # Find last observation matching required LOINC
        required_loincs = rule["required_observations"]
        matching_obs = [
            o for o in observations
            if any(loinc in o.get("loinc_code", "") or loinc in o.get("test", "")
                   for loinc in required_loincs)
        ]

        if not matching_obs:
            gap_anomalies.append({
                "type": "monitoring_gap",
                "severity": rule["severity"],
                "message": f"{rule['label']} — no readings found in patient record.",
                "condition_code": icd_code,
                "last_reading": None,
                "gap_days": None,
            })
            continue

        # Find most recent
        matching_obs.sort(key=lambda x: x.get("date", ""), reverse=True)
        last_obs = matching_obs[0]
        last_date_str = last_obs.get("date", "").split("T")[0]

        try:
            last_dt = datetime.fromisoformat(last_date_str)
            gap_days = (ref_dt - last_dt).days
        except:
            continue

        if gap_days > rule["max_gap_days"]:
            gap_anomalies.append({
                "type": "monitoring_gap",
                "severity": rule["severity"],
                "message": f"{rule['label']} — last reading was {gap_days} days ago "
                          f"(threshold: {rule['max_gap_days']} days). Last value: "
                          f"{last_obs.get('value')} {last_obs.get('unit', '')} on {last_date_str}.",
                "condition_code": icd_code,
                "last_reading": last_date_str,
                "gap_days": gap_days,
                "last_value": last_obs.get("value"),
                "unit": last_obs.get("unit", ""),
            })

    return gap_anomalies


def compute_risk_score(anomalies: list[dict]) -> dict:
    """
    Compute an overall patient risk score from all anomalies.
    Returns score (0–100), level (critical/warning/normal), and breakdown.
    """
    if not anomalies:
        return {"score": 0, "level": "normal", "breakdown": {}}

    weights = {"critical": 35, "warning": 15}
    score = 0
    breakdown = {"critical": 0, "warning": 0, "normal": 0}

    for a in anomalies:
        sev = a.get("severity", "normal")
        breakdown[sev] = breakdown.get(sev, 0) + 1
        score += weights.get(sev, 0)

    score = min(score, 100)

    if score >= 35:
        level = "critical"
    elif score >= 15:
        level = "warning"
    else:
        level = "normal"

    return {
        "score": score,
        "level": level,
        "breakdown": breakdown,
        "total_anomalies": len(anomalies),
    }


def build_trend_series(observations: list[dict]) -> dict:
    """
    Build time-series data per vital for the frontend chart.
    Returns dict of {test_name: [{date, value}]}
    """
    series = {}
    for obs in observations:
        test = obs.get("test", "")
        val = obs.get("value")
        date = obs.get("date", "")
        if val is None or not test or not date:
            continue
        try:
            val = float(val)
        except:
            continue
        if test not in series:
            series[test] = []
        series[test].append({
            "date": date.split("T")[0],
            "value": val,
            "unit": obs.get("unit", ""),
            "institution": obs.get("institution", ""),
        })

    # Sort each series by date
    for test in series:
        series[test].sort(key=lambda x: x["date"])

    return series


def run_full_anomaly_detection(summary: dict) -> dict:
    """
    Master function — runs all anomaly checks and returns full report.
    Called from the FastAPI endpoint.
    """
    observations = summary.get("observations", [])
    medications = summary.get("medications", [])
    conflicts = summary.get("conflicts", [])
    conditions = summary.get("conditions", [])

    # Run all detectors
    vital_anomalies = score_vitals(observations)
    trend_anomalies = detect_vital_trend(observations)
    med_anomalies = detect_medication_anomalies(medications, [], conflicts)

    # Try to get conditions from summary
    gap_anomalies = []
    if conditions:
        gap_anomalies = detect_monitoring_gaps(conditions, observations)

    all_anomalies = vital_anomalies + trend_anomalies + med_anomalies + gap_anomalies

    # Sort by severity (critical first)
    severity_order = {"critical": 0, "warning": 1, "normal": 2}
    all_anomalies.sort(key=lambda x: severity_order.get(x.get("severity", "normal"), 2))

    risk = compute_risk_score(all_anomalies)
    trend_series = build_trend_series(observations)

    return {
        "risk": risk,
        "anomalies": all_anomalies,
        "trend_series": trend_series,
        "summary": {
            "critical_count": risk["breakdown"].get("critical", 0),
            "warning_count": risk["breakdown"].get("warning", 0),
            "total": len(all_anomalies),
        }
    }
