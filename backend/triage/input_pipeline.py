import re
from typing import Dict, Any, List, Tuple, Optional

from .clinical_protocol import _normalize_text
from .negation import find_affirmed

# Expresiones regulares para muletillas, redundancias y ruido conversacional en consultas de voz
FILLER_PATTERNS = [
    r"\b(eh+|eh+m+|este+|mmm+|ah+|oh+|uh+)\b",
    r"\b(o sea|digamos que|por decirlo asi|bueno|como le digo|como le explicaba|mire doctor|mire doctora|buenas tardes|buenos dias|buenas noches|hola doctor|hola doctora)\b",
    r"\b(pues nada|la verdad es que|como le venia diciendo|segun parece|por asi decirlo|si me entiende|usted sabe|como quien dice|la cosa es que|le cuento que|imaginese que)\b",
    r"\b(yo estaba en la casa y|entonces vine a ver si|a ver que me dice|a ver si me manda|desde hace rato|hace unos dias por ahi)\b",
    r"\s{2,}",
]

# Signos vitales: patrones para extraccion y normalizacion compacta
VITAL_PATTERNS = {
    "blood_pressure": [
        (r"\b(?:tension|presion|pa|ta)\s*(?:arterial)?\s*(?:de|en|esta en|salio en|dio|marco)?\s*([0-9]{2,3})\s*(?:sobre|\/|\s)\s*([0-9]{2,3})\b", "PA: {0}/{1} mmHg"),
        (r"\b([0-9]{2,3})\s*\/\s*([0-9]{2,3})\s*(?:de tension|de presion|mmhg)?\b", "PA: {0}/{1} mmHg"),
    ],
    "heart_rate": [
        (r"\b(?:frecuencia cardiaca|fc|pulso)\s*(?:de|en|esta en|salio en|dio|marco)?\s*([0-9]{2,3})\s*(?:lpm|latidos|por minuto)?\b", "FC: {0} lpm"),
        (r"\b([0-9]{2,3})\s*(?:latidos por minuto|lpm)\b", "FC: {0} lpm"),
    ],
    "oxygen_saturation": [
        (r"\b(?:saturacion|saturando|sat|spo2)\s*(?:al|en|de|esta en|salio en|dio|marco)?\s*([0-9]{2,3})\s*(?:%|por ciento)?\b", "SpO2: {0}%"),
        (r"\b([0-9]{2,3})\s*%\s*(?:de saturacion|sat)?\b", "SpO2: {0}%"),
    ],
    "temperature": [
        (r"\b(?:(?:temperatura|temp|fiebre)\s*(?:de|en|esta en|salio en|dio|marco)?|t\s*(?:de)?)\s*([0-9]{2}(?:[\.,][0-9])?)\s*(?:grados|c|°c)?\b", "T: {0}°C"),
        (r"\b([0-9]{2}(?:[\.,][0-9])?)\s*(?:grados|°c)\b", "T: {0}°C"),
        (r"\b([0-9]{2})\s*y\s*medio\s*(?:de fiebre|de temperatura|grados)?\b", "T: {0}.5°C"),
    ],
    "respiratory_rate": [
        (r"\b(?:frecuencia respiratoria|fr|respiraciones)\s*(?:de|en|esta en|salio en|dio|marco)?\s*([0-9]{1,2})\s*(?:rpm|respiraciones|por minuto)?\b", "FR: {0} rpm"),
        (r"\b([0-9]{1,2})\s*(?:respiraciones por minuto|rpm|respiraciones)\b", "FR: {0} rpm"),
    ],
    "glucose": [
        (r"\b(?:glucometria|azucar|glucemia|glicemia|glucosa|dextrostix)\s*(?:de|en|salio en|esta en|dio|marco|mayor a|>)?\s*([0-9]{2,3})\s*(?:mg\/dl)?\b", "GLU: {0} mg/dL"),
    ],
    "pain_scale": [
        (r"\b(?:dolor|eva)\s*(?:de|en)?\s*([0-9]{1,2})\s*(?:\/|\s*sobre\s*)\s*10\b", "EVA: {0}/10"),
    ],
    "glasgow": [
        (r"\b(?:glasgow|gcs)\s*(?:de|en)?\s*([0-9]{1,2})\s*(?:\/|\s*sobre\s*)\s*15\b", "GCS: {0}/15"),
    ]
}

# Banderas rojas clinicas criticas
RED_FLAGS = [
    (r"\b(paro|sin signos vitales|no respira|inconsciente|inconciencia|desmayado|sin responder)\b", "Riesgo Vital Inmediato"),
    (r"\b(dolor (?:en el|de) pecho|dolor toracico|opresion precordial|irradia.*brazo|irradia.*mandibula)\b", "Sospecha Síndrome Coronario Agudo"),
    (r"\b(asimetria facial|boca torcida|medio cuerpo dormido|hemiparesia|afasia|no puede hablar bien|disartria)\b", "Sospecha ACV / Déficit Neurológico Agudo"),
    (r"\b(convulsion|convulsionando|estatus convulsivo|crisis epileptica)\b", "Convulsión en Curso"),
    (r"\b(dificultad respiratoria severa|asfixia|ahogo severo|cianosis|tirajes severos)\b", "Insuficiencia Respiratoria Aguda"),
    (r"\b(hemorragia masiva|desangrando|sangrado profuso|amputacion|sangrado arterial)\b", "Hemorragia Exanguinante"),
    (r"\b(parto expulsivo|coronando|bebe naciendo|cabeza asomando)\b", "Parto Inminente"),
    (r"\b(abdomen en tabla|defensa involuntaria|irritacion peritoneal|peritonitis)\b", "Abdomen Agudo Peritoneal"),
    (r"\b(quemadura quimica ojo|acido en el ojo|ojo perforado)\b", "Emergencia Oftalmológica Aguda"),
    (r"\b(sangrado.*embaraz\w*|embarazada.*sangr\w*|metrorragia)\b", "Hemorragia Obstétrica")
]


class ClinicalTranscriptCompressor:
    """
    Optimizador y compresor determinista de transcripciones clinicas.
    Elimina ruido conversacional, extrae y compacta constantes vitales, detecta alertas
    criticas y maximiza la densidad informativa del prompt para reducir consumo de tokens.
    """

    @classmethod
    def clean_filler_words(cls, text: str) -> str:
        """Remueve muletillas y vacilaciones de voz sin alterar la semantica clinica."""
        cleaned = text
        for pat in FILLER_PATTERNS:
            cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
        # Limpieza de repeticiones continuas de palabras identicas (hallucinacion comun de Whisper)
        cleaned = re.sub(r'\b(\w+)(?:\s+\1\b){2,}', r'\1', cleaned, flags=re.IGNORECASE)
        return " ".join(cleaned.split()).strip()

    @classmethod
    def extract_vitals(cls, text: str) -> Tuple[List[str], Dict[str, Any]]:
        """
        Extrae constantes vitales y las formatea en notacion clinica compacta estandar.
        Retorna la lista de strings compactos y el diccionario estructurado.
        """
        compact_vitals = []
        parsed_vitals: Dict[str, Any] = {}
        # Sin tildes: los patrones estan escritos sin ellas ('tension', 'saturacion').
        norm_text = _normalize_text(text)

        # Presion arterial
        for pat, fmt in VITAL_PATTERNS["blood_pressure"]:
            match = re.search(pat, norm_text)
            if match:
                sys, dia = match.group(1), match.group(2)
                compact_vitals.append(fmt.format(sys, dia))
                parsed_vitals["bp_sys"] = int(sys)
                parsed_vitals["bp_dia"] = int(dia)
                break

        # Frecuencia cardiaca
        for pat, fmt in VITAL_PATTERNS["heart_rate"]:
            match = re.search(pat, norm_text)
            if match:
                hr = match.group(1)
                compact_vitals.append(fmt.format(hr))
                parsed_vitals["heart_rate"] = int(hr)
                break

        # Saturacion SpO2
        for pat, fmt in VITAL_PATTERNS["oxygen_saturation"]:
            match = re.search(pat, norm_text)
            if match:
                sat = match.group(1)
                compact_vitals.append(fmt.format(sat))
                parsed_vitals["spo2"] = int(sat)
                break

        # Temperatura
        for pat, fmt in VITAL_PATTERNS["temperature"]:
            match = re.search(pat, norm_text)
            if match:
                temp = match.group(1).replace(',', '.')
                compact_vitals.append(fmt.format(temp))
                try:
                    parsed_vitals["temperature"] = float(temp)
                except ValueError:
                    pass
                break

        # Frecuencia respiratoria
        for pat, fmt in VITAL_PATTERNS["respiratory_rate"]:
            match = re.search(pat, norm_text)
            if match:
                rr = match.group(1)
                compact_vitals.append(fmt.format(rr))
                parsed_vitals["respiratory_rate"] = int(rr)
                break

        # Glucometria
        for pat, fmt in VITAL_PATTERNS["glucose"]:
            match = re.search(pat, norm_text)
            if match:
                glu = match.group(1)
                compact_vitals.append(fmt.format(glu))
                parsed_vitals["glucose"] = int(glu)
                break

        # Escala del dolor EVA
        for pat, fmt in VITAL_PATTERNS["pain_scale"]:
            match = re.search(pat, norm_text)
            if match:
                eva = match.group(1)
                compact_vitals.append(fmt.format(eva))
                parsed_vitals["eva"] = int(eva)
                break

        # Glasgow
        for pat, fmt in VITAL_PATTERNS["glasgow"]:
            match = re.search(pat, norm_text)
            if match:
                gcs = match.group(1)
                compact_vitals.append(fmt.format(gcs))
                parsed_vitals["gcs"] = int(gcs)
                break

        return compact_vitals, parsed_vitals

    @classmethod
    def detect_red_flags(cls, text: str) -> List[str]:
        """Identifica signos de alarma clinica de maxima criticidad."""
        norm = _normalize_text(text)
        detected = []
        for pat, label in RED_FLAGS:
            # "no ha perdido el conocimiento" no es bandera roja; "no respira" si lo es.
            if find_affirmed(pat, norm, flags=re.IGNORECASE):
                if label not in detected:
                    detected.append(label)
        return detected

    @classmethod
    def process(cls, transcript: str) -> Dict[str, Any]:
        """
        Ejecuta el pipeline de compresion y enriquecimiento clinico sobre la transcripcion.
        Calcula la tasa de reduccion de caracteres y prepara la estructura densa.
        """
        original_len = len(transcript)
        cleaned = cls.clean_filler_words(transcript)
        compact_vitals, structured_vitals = cls.extract_vitals(transcript)
        red_flags = cls.detect_red_flags(transcript)

        cleaned_len = len(cleaned)
        reduction = 0.0
        if original_len > 0 and cleaned_len < original_len:
            reduction = round(((original_len - cleaned_len) / original_len) * 100, 1)

        return {
            "original_transcript": transcript,
            "cleaned_transcript": cleaned,
            "compact_vitals": compact_vitals,
            "structured_vitals": structured_vitals,
            "red_flags": red_flags,
            "reduction_percentage": reduction
        }
