# Vocabulary based on SNOMED CT and ICD-10 for Spanish clinical triage context.
# This serves as an initial prompt and hotwords list for Whisper to guide recognition towards clinical terms.

CLINICAL_INITIAL_PROMPT = (
    "Transcripción médica en español clínico para triaje hospitalario y consulta de urgencias. "
    "Sintomatología y signos: disnea, dolor torácico, opresión precordial, síncope, cefalea, "
    "epigastralgia, melena, hematemesis, hematuria, disuria, polaquiuria, odinofagia, disfagia, "
    "pirosis, náuseas, emesis, artralgia, mialgia, parestesias, vértigo, cianosis, ictericia, prurito, "
    "exantema, sibilancias, estertores, crepitantes, Glasgow, saturación de oxígeno, presión arterial, "
    "frecuencia cardíaca, frecuencia respiratoria, temperatura axilar, fiebre, escalofríos, diaforesis, "
    "palpitaciones, edema en miembros inferiores, claudicación intermitente, alteración del estado de conciencia, "
    "focalización neurológica, hemiparesia, disartria, afasia, rigidez de nuca.\n"
    "Medicamentos e inmunizaciones: metformina, losartán, omeprazol, enalapril, atorvastatina, "
    "paracetamol, ibuprofeno, amoxicilina, ácido acetilsalicílico, aspirina, clonazepam, diazepam, "
    "fluoxetina, sertralina, levotiroxina, warfarina, clopidogrel, salbutamol, budesonida, prednisona, "
    "dexametasona, tramadol, morfina, ciprofloxacino, cefalexina, azitromicina, insulina glargina, "
    "insulina rápida, furosemida, espironolactona, carvedilol, amlodipino, gabapentina, paroxetina.\n"
    "Patologías, antecedentes y diagnósticos: diabetes mellitus tipo 2, hipertensión arterial primaria, "
    "EPOC (Enfermedad Pulmonar Obstructiva Crónica), insuficiencia cardíaca congestiva, fibrilación auricular, "
    "infarto agudo de miocardio, accidente cerebrovascular, asma bronquial, neumonía adquirida en la comunidad, "
    "tromboembolismo pulmonar, apendicitis aguda, pancreatitis aguda, colecistitis, insuficiencia renal crónica, "
    "cirrosis hepática, hipertiroidismo, hipotiroidismo, anemia, leucemia, linfoma, dislipidemia, osteoartritis, "
    "artritis reumatoide, hipoglicemia, cetoacidosis diabética, sepsis."
)

# Hotwords clinicos de alta especificidad fonetica que Faster-Whisper inyecta en cada ventana de decodificacion
# sin ser desplazados por el historial conversacional previo de 400 caracteres.
_BASE_CLINICAL_HOTWORDS = (
    "losartán", "metformina", "omeprazol", "enalapril", "atorvastatina", "acetaminofén",
    "ibuprofeno", "amoxicilina", "salbutamol", "levotiroxina", "warfarina", "clopidogrel",
    "furosemida", "insulina", "amlodipino", "carvedilol", "tramadol", "ciprofloxacino",
    "glucometría", "saturación", "Glasgow", "disnea", "taquicardia", "hipotensión",
    "hematemesis", "melena", "hemiparesia", "disartria", "afasia", "polaquiuria",
    "odinofagia", "disuria", "cianosis", "sibilancias", "cetoacidosis", "preeclampsia",
    "epigastralgia", "parestesias", "síncope", "convulsión", "anafilaxia", "sepsis",
)


def build_clinical_hotwords(max_terms: int = 80) -> str:
    """Construye la cadena de hotwords combinando terminos base y blancos canonicos de correcciones_asr.json."""
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
            if target and key not in seen and len(target) >= 4:
                seen.add(key)
                ordered.append(target)
    except Exception:
        pass
    return ", ".join(ordered[:max_terms])


CLINICAL_HOTWORDS = build_clinical_hotwords()
