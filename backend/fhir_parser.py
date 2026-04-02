import json
from pathlib import Path


def parse_bundle(filepath: str) -> dict:
    """Parse a FHIR bundle JSON file into structured components."""
    with open(filepath) as f:
        bundle = json.load(f)

    result = {
        "institution": bundle.get("institution"),
        "institution_id": bundle.get("institution_id"),
        "patients": [],
        "encounters": [],
        "conditions": [],
        "medications": [],
        "allergies": [],
        "observations": [],
    }

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")

        if rtype == "Patient":
            name = resource.get("name", [{}])[0]
            result["patients"].append({
                "id": resource["id"],
                "family": name.get("family", ""),
                "given": " ".join(name.get("given", [])),
                "dob": resource.get("birthDate", ""),
                "gender": resource.get("gender", ""),
                "zip": resource.get("address", [{}])[0].get("postalCode", ""),
                "city": resource.get("address", [{}])[0].get("city", ""),
                "phone": resource.get("telecom", [{}])[0].get("value", ""),
            })

        elif rtype == "Encounter":
            subject_id = resource.get("subject", {}).get("reference", "").replace("Patient/", "")
            provider = resource.get("participant", [{}])[0].get("individual", {})
            result["encounters"].append({
                "id": resource["id"],
                "patient_id": subject_id,
                "start": resource.get("period", {}).get("start", ""),
                "end": resource.get("period", {}).get("end", ""),
                "type": resource.get("type", ""),
                "reason": resource.get("reasonCode", ""),
                "provider_name": provider.get("display", ""),
                "provider_id": provider.get("id", ""),
            })

        elif rtype == "Condition":
            subject_id = resource.get("subject", {}).get("reference", "").replace("Patient/", "")
            coding = resource.get("code", {}).get("coding", [{}])[0]
            result["conditions"].append({
                "id": resource["id"],
                "patient_id": subject_id,
                "code": coding.get("code", ""),
                "system": coding.get("system", ""),
                "display": coding.get("display", ""),
                "onset": resource.get("onsetDateTime", ""),
                "status": resource.get("clinicalStatus", ""),
            })

        elif rtype == "MedicationRequest":
            subject_id = resource.get("subject", {}).get("reference", "").replace("Patient/", "")
            coding = resource.get("medicationCodeableConcept", {}).get("coding", [{}])[0]
            result["medications"].append({
                "id": resource["id"],
                "patient_id": subject_id,
                "rxnorm_code": coding.get("code", ""),
                "name": coding.get("display", ""),
                "status": resource.get("status", ""),
                "authored_on": resource.get("authoredOn", ""),
                "requester": resource.get("requester", {}).get("display", ""),
                "note": resource.get("note", ""),
            })

        elif rtype == "AllergyIntolerance":
            patient_id = resource.get("patient", {}).get("reference", "").replace("Patient/", "")
            coding = resource.get("code", {}).get("coding", [{}])[0]
            reaction = resource.get("reaction", [{}])[0]
            result["allergies"].append({
                "id": resource["id"],
                "patient_id": patient_id,
                "substance_code": coding.get("code", ""),
                "substance": coding.get("display", ""),
                "reaction": reaction.get("description", ""),
                "severity": reaction.get("severity", ""),
                "recorded_date": resource.get("recordedDate", ""),
            })

        elif rtype == "Observation":
            subject_id = resource.get("subject", {}).get("reference", "").replace("Patient/", "")
            coding = resource.get("code", {}).get("coding", [{}])[0]
            value = resource.get("valueQuantity", {})
            result["observations"].append({
                "id": resource["id"],
                "patient_id": subject_id,
                "loinc_code": coding.get("code", ""),
                "display": coding.get("display", ""),
                "value": value.get("value", ""),
                "unit": value.get("unit", ""),
                "date": resource.get("effectiveDateTime", ""),
            })

    return result


def load_all_bundles(data_dir: str = "data") -> list[dict]:
    """Load and parse all FHIR bundles from a directory."""
    bundles = []
    for path in Path(data_dir).glob("*.json"):
        parsed = parse_bundle(str(path))
        bundles.append(parsed)
        print(f"Parsed: {path.name} — Institution: {parsed['institution']}")
    return bundles


if __name__ == "__main__":
    bundles = load_all_bundles()
    for b in bundles:
        print(f"\n{b['institution']}:")
        print(f"  Patients: {len(b['patients'])}")
        print(f"  Encounters: {len(b['encounters'])}")
        print(f"  Medications: {len(b['medications'])}")
        print(f"  Allergies: {len(b['allergies'])}")
        print(f"  Observations: {len(b['observations'])}")
