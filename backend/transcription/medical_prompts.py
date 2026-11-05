# Vocabulario clinico calibrado al presupuesto real de tokens BPE del decodificador de Whisper (max_length = 448).
# En faster-whisper, `hotwords` + `initial_prompt` + `sot_sequence` comparten la misma ventana de 448 posiciones
# con el texto generado; mantener su suma <= 185 tokens deja >= 263 tokens libres para cada segmento de 30 s.

CLINICAL_INITIAL_PROMPT = (
    "Entrevista de triaje en urgencias médicas en español: motivo de consulta, tiempo de evolución, "
    "signos vitales, tensión arterial, saturación, glucometría, escala de Glasgow, alergias y medicamentos."
)

_BASE_CLINICAL_HOTWORDS = (
    "losartán", "metformina", "omeprazol", "enalapril", "acetaminofén", "ácido valproico",
    "amoxicilina", "penicilina", "salbutamol", "levotiroxina", "warfarina", "furosemida",
    "insulina", "glucometría", "saturación", "Glasgow", "disnea", "amígdalas",
    "gastritis", "arritmia", "epilepsia", "hipotermia", "preeclampsia", "sepsis",
)


def build_clinical_hotwords(max_terms: int = 24, max_chars: int = 280) -> str:
    """
    Construye la lista compacta de hotwords clinicos respetando el presupuesto de ventana de Whisper
    (~65 tokens BPE) para evitar desbordar las 448 posiciones del decodificador junto a `initial_prompt`.
    """
    seen = set()
    ordered = []
    for word in _BASE_CLINICAL_HOTWORDS:
        key = word.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(word)
    try:
        from .terminology import _read
        for item in _read("correcciones_asr.json").get("correcciones", []):
            target = (item.get("correccion") or "").strip()
            key = target.lower()
            if target and key not in seen and 4 <= len(target) <= 18:
                seen.add(key)
                ordered.append(target)
    except Exception:
        pass

    selected = []
    total_chars = 0
    for term in ordered[:max_terms]:
        added = len(term) + (2 if selected else 0)
        if total_chars + added > max_chars:
            break
        selected.append(term)
        total_chars += added
    return ", ".join(selected)


CLINICAL_HOTWORDS = build_clinical_hotwords()
