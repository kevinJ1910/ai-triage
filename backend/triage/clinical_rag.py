import re
import math
import unicodedata
from typing import Dict, Any, List, Optional
from .clinical_protocol import CHRISTUS_SINERGIA_LEVELS, _normalize_text

# Base de Conocimiento Ontologico y Criterios Institucionales Desglosados
CLINICAL_KNOWLEDGE_BASE = [
    # --- NIVEL 1: REANIMACION ---
    {
        "id": "c1_vital_arrest",
        "level": 1,
        "name": "Reanimación",
        "category": "neurologico_vital",
        "criterion": "Ausencia de signos vitales, paro cardiorrespiratorio o estado de coma profundo.",
        "keywords": ["paro", "sin signos vitales", "inconsciente", "inconciencia", "coma", "muerte aparente"]
    },
    {
        "id": "c1_resp_failure",
        "level": 1,
        "name": "Reanimación",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria severa, asfixia aguda o paro respiratorio inminente.",
        "keywords": ["asfixia", "cianosis severa", "no respira", "paro respiratorio", "ahogo severo"]
    },
    {
        "id": "c1_exsanguination",
        "level": 1,
        "name": "Reanimación",
        "category": "hemodinamico_trauma",
        "criterion": "Hemorragia masiva exanguinante, amputación traumática o pérdida de órgano/miembro.",
        "keywords": ["hemorragia masiva", "desangrando", "amputacion", "perdida de miembro", "perdida de organo"]
    },
    {
        "id": "c1_imminent_birth",
        "level": 1,
        "name": "Reanimación",
        "category": "obstetrico",
        "criterion": "Trabajo de parto en periodo expulsivo inminente.",
        "keywords": ["parto expulsivo", "coronando", "bebe naciendo", "expulsivo"]
    },
    {
        "id": "c1_major_burn_trauma",
        "level": 1,
        "name": "Reanimación",
        "category": "trauma",
        "criterion": "Politraumatismo severo múltiple, quemaduras corporales masivas o hipotermia severa.",
        "keywords": ["politraumatismo", "gran quemado", "quemadura todo el cuerpo", "hipotermia severa"]
    },

    # --- NIVEL 2: EMERGENCIA ---
    {
        "id": "c2_chest_pain_sca",
        "level": 2,
        "name": "Emergencia",
        "category": "cardiovascular",
        "criterion": "Dolor torácico opresivo con signos de alarma, sospecha de Síndrome Coronario Agudo o infarto.",
        "keywords": ["dolor de pecho", "dolor toracico", "opresion en el pecho", "infarto", "angina", "irradiado al brazo", "irradiado a la mandibula"]
    },
    {
        "id": "c2_hypertensive_crisis",
        "level": 2,
        "name": "Emergencia",
        "category": "cardiovascular",
        "criterion": "Crisis hipertensiva con cifras sistólicas >= 180 mmHg o diastólicas >= 110 mmHg con o sin compromiso de órgano diana.",
        "keywords": ["crisis hipertensiva", "presion muy alta", "tension 180", "tension 200", "emergencia hipertensiva"]
    },
    {
        "id": "c2_seizures",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Estado convulsivo activo o crisis epilépticas repetitivas.",
        "keywords": ["convulsion", "convulsionando", "estado convulsivo", "crisis epileptica", "ataque de epilepsia"]
    },
    {
        "id": "c2_resp_moderate",
        "level": 2,
        "name": "Emergencia",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria moderada, desaturación SpO2 < 90% o tirajes intercostales.",
        "keywords": ["dificultad respiratoria moderada", "saturacion menor a 90", "tirajes", "disnea moderada", "fatiga respiratoria"]
    },
    {
        "id": "c2_diabetes_decompensation",
        "level": 2,
        "name": "Emergencia",
        "category": "metabolico",
        "criterion": "Diabetes descompensada aguda, cetoacidosis o hiperglucemia severa con alteración del sensorio.",
        "keywords": ["diabetes descompensada", "cetoacidosis", "coma diabetico", "azucar 400", "azucar 500"]
    },
    {
        "id": "c2_open_fracture_burn",
        "level": 2,
        "name": "Emergencia",
        "category": "trauma",
        "criterion": "Fractura expuesta con hueso visible o quemadura de III grado profunda.",
        "keywords": ["fractura expuesta", "hueso afuera", "hueso visible", "quemadura de tercer grado", "quemadura grado 3"]
    },
    {
        "id": "c2_toxic_ingestion",
        "level": 2,
        "name": "Emergencia",
        "category": "toxicologico",
        "criterion": "Ingestión de sustancias tóxicas, cáusticos, plaguicidas o sobredosis medicamentosa.",
        "keywords": ["intoxicacion", "veneno", "envenenamiento", "ingestion toxico", "sobredosis", "plaguicida"]
    },
    {
        "id": "c2_pregnancy_bleeding",
        "level": 2,
        "name": "Emergencia",
        "category": "obstetrico",
        "criterion": "Sangrado vaginal agudo en paciente embarazada o amenaza de aborto.",
        "keywords": ["sangrado embarazada", "embarazada sangrando", "metrorragia", "perdida de sangre en embarazo"]
    },

    # --- NIVEL 3: URGENCIA ---
    {
        "id": "c3_vertigo_incapacitating",
        "level": 3,
        "name": "Urgencia",
        "category": "neurologico",
        "criterion": "Vértigo severo incapacitante con náuseas que impide la bipedestación pero con signos vitales estables.",
        "keywords": ["vertigo severo", "mareo incapacitante", "no se puede parar", "todo le da vueltas"]
    },
    {
        "id": "c3_mild_resp",
        "level": 3,
        "name": "Urgencia",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria leve, sibilancias aisladas o tos asmática sin desaturación severa (SpO2 >= 92%).",
        "keywords": ["dificultad respiratoria leve", "silbido pecho", "sibilancia", "disnea leve", "asma leve"]
    },
    {
        "id": "c3_gastro_dehydration",
        "level": 3,
        "name": "Urgencia",
        "category": "digestivo",
        "criterion": "Vómito y diarrea con signos clínicos de deshidratación moderada o intolerancia a la vía oral.",
        "keywords": ["vomito y diarrea", "deshidratacion", "no tolera suero", "intolerancia via oral", "diarrea abundante"]
    },
    {
        "id": "c3_moderate_trauma",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Trauma moderado, sospecha de fractura cerrada, luxación articular o dolor agudo limitante.",
        "keywords": ["trauma moderado", "golpe fuerte", "esguince severo", "luxacion", "fractura cerrada", "deformidad"]
    },
    {
        "id": "c3_allergic_reaction",
        "level": 3,
        "name": "Urgencia",
        "category": "inmunoalergico",
        "criterion": "Reacción alérgica con urticaria/brote generalizado sin compromiso de vía aérea ni edema de glotis.",
        "keywords": ["reaccion alergica", "alergia con brote", "urticaria", "ronchas en el cuerpo", "picazon generalizada"]
    },
    {
        "id": "c3_burn_grade_2",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Quemadura de II grado localizada con flictenas o ampollas en área menor al 10% corporal.",
        "keywords": ["quemadura de segundo grado", "quemadura grado 2", "ampollas por quemadura"]
    },

    # --- NIVEL 4: CONSULTA PRIORITARIA ---
    {
        "id": "c4_upper_respiratory",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "respiratorio_infeccioso",
        "criterion": "Cuadro respiratorio alto: tos, congestión nasal, odinofagia, faringitis o amigdalitis sin dificultad respiratoria.",
        "keywords": ["tos y congestion", "gripe", "resfriado", "dolor de garganta", "amigdalitis", "faringitis", "rinorrea"]
    },
    {
        "id": "c4_gastro_mild",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "digestivo",
        "criterion": "Vómito o diarrea autolimitada sin deshidratación y con adecuada tolerancia a líquidos orales.",
        "keywords": ["vomito sin deshidratacion", "diarrea sin deshidratacion", "gastroenteritis leve", "soltura leve"]
    },
    {
        "id": "c4_dysuria_urinary",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "urologico",
        "criterion": "Ardor al orinar (disuria), polaquiuria o síntomas de infección urinaria baja sin fiebre alta ni compromiso renal.",
        "keywords": ["ardor al orinar", "chistata", "infeccion urinaria", "disuria", "dolor para orinar"]
    },
    {
        "id": "c4_subacute_pain",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "dolor_general",
        "criterion": "Dolor leve a moderado de más de 24 horas de evolución, trauma superficial menor o herida sin hemorragia activa.",
        "keywords": ["dolor de varios dias", "dolor mas de 24 horas", "trauma leve", "raspada", "golpe leve"]
    },
    {
        "id": "c4_anxiety_mild",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "salud_mental",
        "criterion": "Episodio de ansiedad o angustia leve a moderada sin ideación suicida ni agitación psicomotora.",
        "keywords": ["ansiedad", "nerviosismo", "depresion leve", "angustia"]
    },

    # --- NIVEL 5: CONSULTA EXTERNA ---
    {
        "id": "c5_chronic_headache",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Dolor de cabeza crónico de meses o años de evolución con características habituales y sin signos de alarma.",
        "keywords": ["dolor de cabeza cronico", "migrana de anos", "cefalea cronica habitual", "dolor de cabeza de siempre"]
    },
    {
        "id": "c5_chronic_digestive",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Síntomas digestivos crónicos: estreñimiento habitual, dispepsia crónica, inapetencia o dolor abdominal no agudo.",
        "keywords": ["estrenimiento cronico", "inapetencia", "dolor abdominal cronico", "gastritis de meses"]
    },
    {
        "id": "c5_administrative_routine",
        "level": 5,
        "name": "Consulta Externa",
        "category": "administrativo",
        "criterion": "Trámites administrativos: formulación y renovación de medicamentos de control, incapacidades o lectura de exámenes.",
        "keywords": ["formulacion de medicamentos", "receta medica", "renovacion formula", "lectura de examenes", "resultados de laboratorio"]
    },
    {
        "id": "c5_dermatology_subacute",
        "level": 5,
        "name": "Consulta Externa",
        "category": "dermatologia",
        "criterion": "Lesiones de piel crónicas o subagudas: dermatitis, eccema, acné o micosis cutánea sin signos de sobreinfección sistémica.",
        "keywords": ["dermatitis", "alergia en la piel cronica", "hongos", "eccema", "granos antiguos"]
    }
]


class ClinicalKnowledgeRAG:
    """
    Motor RAG semantico y ontologico para triaje medico hospitalario.
    Permite recuperar los criterios institucionales Christus Sinergia especificos
    mas relevantes para la consulta del paciente, evitando inyectar monolitos de texto estatico.
    """

    @classmethod
    def _compute_relevance(cls, query_norm: str, criterion: Dict[str, Any]) -> float:
        """Calcula el puntaje de relevancia hibrida lexico-semantica."""
        score = 0.0
        # Coincidencia con palabras clave
        for kw in criterion["keywords"]:
            kw_norm = _normalize_text(kw)
            if kw_norm in query_norm:
                # Mas peso a coincidencias multipalabra
                score += 3.0 if " " in kw_norm else 1.5

        # Coincidencia con el texto descriptivo del criterio
        crit_tokens = set(_normalize_text(criterion["criterion"]).split())
        query_tokens = set(query_norm.split())
        overlap = crit_tokens.intersection(query_tokens)
        score += len(overlap) * 0.4

        return score

    @classmethod
    def retrieve(cls, transcript: str, top_k: int = 4, red_flags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recupera los top-K criterios institucionales mas pertinentes para el cuadro clinico.
        Garantiza inclusion de criterios diferenciales relevantes (ej. Triage 1 y 2 si hay red flags).
        """
        query_norm = _normalize_text(transcript)
        scored_criteria = []

        for item in CLINICAL_KNOWLEDGE_BASE:
            rel = cls._compute_relevance(query_norm, item)
            # Boost por red flags detectadas
            if red_flags and item["level"] in [1, 2]:
                rel += 2.0
            if rel > 0:
                scored_criteria.append((rel, item))

        scored_criteria.sort(key=lambda x: x[0], reverse=True)
        retrieved = [item for _, item in scored_criteria[:top_k]]

        # Si no hubo coincidencias especificas, proveer un marco contextual sintetico
        if not retrieved:
            retrieved = [
                CLINICAL_KNOWLEDGE_BASE[1],   # Resp failure (T1)
                CLINICAL_KNOWLEDGE_BASE[5],   # Chest pain SCA (T2)
                CLINICAL_KNOWLEDGE_BASE[14],  # Upper resp (T4)
                CLINICAL_KNOWLEDGE_BASE[18],  # Administrative/routine (T5)
            ]

        return retrieved

    @classmethod
    def format_context_for_prompt(cls, retrieved_criteria: List[Dict[str, Any]]) -> str:
        """
        Formatea los criterios recuperados en un bloque de contexto altamente comprimido y denso.
        Reduce de ~700 tokens a ~150-200 tokens.
        """
        lines = ["CRITERIOS INSTITUCIONALES RELEVANTES (CHRISTUS SINERGIA SALUD):"]
        # Agrupar por nivel para claridad cognitiva del modelo
        by_level: Dict[int, List[Dict[str, Any]]] = {}
        for c in retrieved_criteria:
            by_level.setdefault(c["level"], []).append(c)

        for lvl in sorted(by_level.keys()):
            lvl_meta = CHRISTUS_SINERGIA_LEVELS.get(lvl, {})
            name = lvl_meta.get("name", f"Nivel {lvl}")
            time_limit = lvl_meta.get("attention_time", "No especificado")
            crit_texts = [f"• {item['criterion']}" for item in by_level[lvl]]
            lines.append(f"[{lvl} - {name.upper()}] (Tiempo: {time_limit}):")
            lines.extend(crit_texts)

        return "\n".join(lines)
