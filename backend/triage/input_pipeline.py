import re
import unicodedata
from typing import Dict, Any, List, Tuple, Optional

# Expresiones regulares para muletillas y ruido conversacional en consultas de voz
FILLER_PATTERNS = [
    r"\b(eh+|eh+m+|este+|mmm+|ah+|oh+|uh+)\b",
    r"\b(o sea|digamos que|por decirlo asi|bueno|como le digo|como le explicaba|mire doctor|mire doctora|buenas tardes|buenos dias)\b",
    r"\b(pues nada|la verdad es que|como le venia diciendo|segun parece|por asi decirlo)\b",
    r"\s{2,}",
]

# Signos vitales: patrones para extraccion y normalizacion compacta
VITAL_PATTERNS = {
    "blood_pressure": [
        (r"\b(?:tension|presion|pa|ta)\s*(?:arterial)?\s*(?:de)?\s*([0-9]{2,3})\s*(?:sobre|\/|\s)\s*([0-9]{2,3})\b", "PA: {0}/{1} mmHg"),
        (r"\b([0-9]{2,3})\s*\/\s*([0-9]{2,3})\s*(?:de tension|de presion|mmhg)?\b", "PA: {0}/{1} mmHg"),
    ],
    "heart_rate": [
        (r"\b(?:frecuencia cardiaca|fc|pulso)\s*(?:de)?\s*([0-9]{2,3})\s*(?:lpm|latidos|por minuto)?\b", "FC: {0} lpm"),
        (r"\b([0-9]{2,3})\s*(?:latidos por minuto|lpm)\b", "FC: {0} lpm"),
    ],
    "oxygen_saturation": [
        (r"\b(?:saturacion|saturando|sat|spo2)\s*(?:al|en|de)?\s*([0-9]{2,3})\s*(?:%|por ciento)?\b", "SpO2: {0}%"),
        (r"\b([0-9]{2,3})\s*%\s*(?:de saturacion|sat)?\b", "SpO2: {0}%"),
    ],
    "temperature": [
        (r"\b(?:temperatura|temp|t|fiebre)\s*(?:de)?\s*([0-9]{2}(?:[\.,][0-9])?)\s*(?:grados|c|°c)?\b", "T: {0}°C"),
        (r"\b([0-9]{2}(?:[\.,][0-9])?)\s*(?:grados|°c)\b", "T: {0}°C"),
        (r"\b([0-9]{2})\s*y\s*medio\s*(?:de fiebre|de temperatura|grados)?\b", "T: {0}.5°C"),
    ],
    "respiratory_rate": [
        (r"\b(?:frecuencia respiratoria|fr|respiraciones)\s*(?:de)?\s*([0-9]{1,2})\s*(?:rpm|respiraciones|por minuto)?\b", "FR: {0} rpm"),
        (r"\b([0-9]{1,2})\s*(?:respiraciones por minuto|rpm|respiraciones)\b", "FR: {0} rpm"),
    ]
}

# Banderas rojas clinicas criticas
RED_FLAGS = [
    (r"\b(paro|sin signos vitales|no respira|inconsciente|inconciencia|desmayado)\b", "Riesgo Vital Inmediato"),
    (r"\b(dolor (?:en el|de) pecho|dolor toracico|opresion precordial|irradia.*brazo)\b", "Sospecha Síndrome Coronario Agudo"),
    (r"\b(convulsion|convulsionando|estatus convulsivo)\b", "Convulsión en Curso"),
    (r"\b(dificultad respiratoria severa|asfixia|ahogo severo|cianosis)\b", "Insuficiencia Respiratoria Aguda"),
    (r"\b(hemorragia masiva|desangrando|sangrado profuso|amputacion)\b", "Hemorragia Exanguinante"),
    (r"\b(parto expulsivo|coronando|bebe naciendo)\b", "Parto Inminente")
]


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


class ClinicalTranscriptCompressor:
    """
    Optimizador y compresor determinista de transcripciones clinicas.
    Elimina ruido conversacional, extrae y compacta signos vitales, detecta alertas
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
        norm_text = text.lower()

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

        return compact_vitals, parsed_vitals

    @classmethod
    def detect_red_flags(cls, text: str) -> List[str]:
        """Identifica banderas rojas de emergencia medica inmediata."""
        norm_text = _strip_accents(text)
        detected = []
        for pat, alert in RED_FLAGS:
            if re.search(pat, norm_text):
                detected.append(alert)
        return list(dict.fromkeys(detected))

    @classmethod
    def process(cls, transcript: str) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de pre-procesamiento clinico y compresion de entrada.
        """
        raw_text = transcript.strip()
        cleaned_text = cls.clean_filler_words(raw_text)
        compact_vitals, structured_vitals = cls.extract_vitals(raw_text)
        red_flags = cls.detect_red_flags(raw_text)

        # Calculo de tasa de compresion
        orig_chars = len(raw_text)
        clean_chars = len(cleaned_text)
        char_reduction_pct = round(max(0.0, (orig_chars - clean_chars) / max(1, orig_chars)) * 100, 1)

        return {
            "original_transcript": raw_text,
            "cleaned_transcript": cleaned_text,
            "compact_vitals": compact_vitals,
            "structured_vitals": structured_vitals,
            "red_flags": red_flags,
            "reduction_percentage": char_reduction_pct,
            "is_emergency": len(red_flags) > 0 or structured_vitals.get("spo2", 100) < 90 or structured_vitals.get("bp_sys", 120) >= 180
        }
