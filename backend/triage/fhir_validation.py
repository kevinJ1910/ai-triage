"""
Validacion estructural minima de Bundles HL7 FHIR R4.
No sustituye a un validador oficial (HAPI / Firely): comprueba la estructura del Bundle
y los elementos obligatorios (cardinalidad 1..1) y value sets requeridos de los recursos que usa el sistema.
"""
from typing import Any, Dict, List, Tuple

BUNDLE_TYPES = {
    "document", "message", "transaction", "transaction-response", "batch",
    "batch-response", "history", "searchset", "collection",
}
ENCOUNTER_STATUS = {
    "planned", "arrived", "triaged", "in-progress", "onleave", "finished",
    "cancelled", "entered-in-error", "unknown",
}
OBSERVATION_STATUS = {
    "registered", "preliminary", "final", "amended", "corrected",
    "cancelled", "entered-in-error", "unknown",
}
MEDICATION_STATEMENT_STATUS = {
    "active", "completed", "entered-in-error", "intended", "stopped",
    "on-hold", "unknown", "not-taken",
}


def _check_resource(resource: Dict[str, Any], where: str) -> List[str]:
    errors: List[str] = []
    rtype = resource.get("resourceType")

    if rtype == "Encounter":
        if resource.get("status") not in ENCOUNTER_STATUS:
            errors.append(f"{where} Encounter.status ausente o fuera del value set R4")
        if not resource.get("class"):
            errors.append(f"{where} Encounter.class es obligatorio")
    elif rtype == "Observation":
        if resource.get("status") not in OBSERVATION_STATUS:
            errors.append(f"{where} Observation.status ausente o fuera del value set R4")
        if not resource.get("code"):
            errors.append(f"{where} Observation.code es obligatorio")
    elif rtype == "Condition":
        if not resource.get("subject"):
            errors.append(f"{where} Condition.subject es obligatorio")
    elif rtype == "MedicationStatement":
        if resource.get("status") not in MEDICATION_STATEMENT_STATUS:
            errors.append(f"{where} MedicationStatement.status ausente o fuera del value set R4")
        if not resource.get("subject"):
            errors.append(f"{where} MedicationStatement.subject es obligatorio")
        if not (resource.get("medicationCodeableConcept") or resource.get("medicationReference")):
            errors.append(f"{where} MedicationStatement.medication[x] es obligatorio")
    return errors


def validate_fhir_bundle(payload: Dict[str, Any]) -> Tuple[bool, str]:
    """Devuelve (es_valido, detalle legible)."""
    errors: List[str] = []

    if payload.get("resourceType") != "Bundle":
        errors.append("resourceType debe ser 'Bundle'")
    if payload.get("type") not in BUNDLE_TYPES:
        errors.append(f"Bundle.type '{payload.get('type')}' no pertenece al value set R4")

    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        errors.append("Bundle.entry debe ser una lista")
        entries = []

    found_types = []
    for idx, entry in enumerate(entries):
        where = f"entry[{idx}]"
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict) or not resource.get("resourceType"):
            errors.append(f"{where} sin resource.resourceType")
            continue
        found_types.append(resource["resourceType"])
        errors.extend(_check_resource(resource, where))

    if errors:
        return False, "Bundle FHIR R4 invalido: " + "; ".join(errors)

    summary = ", ".join(sorted(set(found_types))) or "sin entradas"
    return True, f"Estructura FHIR R4 verificada ({len(entries)} entradas: {summary})."
