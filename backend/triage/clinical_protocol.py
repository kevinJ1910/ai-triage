import re
import unicodedata
from typing import Dict, Any, List, Optional

from .negation import find_affirmed

# Protocolo Institucional de Triaje: Christus Sinergia Salud / Resolucion 5596 Minsalud Colombia

CHRISTUS_SINERGIA_LEVELS = {
    1: {
        "name": "Reanimación",
        "color": "Rojo",
        "attention_time": "Inmediata",
        "definition": (
            "La condición clínica del paciente representa un riesgo vital y necesita "
            "maniobras de reanimación por su compromiso ventilatorio, respiratorio, "
            "hemodinámico o neurológico, pérdida de miembro u órgano u otras condiciones "
            "que por norma exijan atención inmediata."
        ),
        "criteria": [
            "Ausencia de signos vitales",
            "Inconciencia",
            "Dificultad respiratoria severa",
            "Hipotermia severa",
            "Traumatismos severos múltiples",
            "Quemaduras en todo el cuerpo",
            "Pérdida de miembro u órgano",
            "Hemorragia masiva",
            "Trabajo de parto expulsivo",
            "Abuso sexual menor a 72 horas"
        ]
    },
    2: {
        "name": "Emergencia",
        "color": "Naranja",
        "attention_time": "Dentro de los siguientes 30 minutos",
        "definition": (
            "La condición clínica del paciente puede evolucionar hacia un rápido deterioro "
            "o a su muerte, o incrementar el riesgo para la pérdida de un miembro u órgano."
        ),
        "criteria": [
            "Alteración aguda de signos vitales",
            "Estado convulsivo",
            "Dificultad respiratoria moderada",
            "Crisis hipertensiva",
            "Diabetes descompensada",
            "Dolor torácico con signos de alarma",
            "Trauma severo",
            "Quemadura de III grado",
            "Riesgo de pérdida de miembro u órgano",
            "Fractura expuesta",
            "Sangrado vaginal en embarazadas",
            "Trabajo de parto",
            "Abuso sexual mayor a 72 horas",
            "Agitación psicomotora",
            "Ingestión de sustancias tóxicas o envenenamiento"
        ]
    },
    3: {
        "name": "Urgencia",
        "color": "Amarillo",
        "attention_time": "Hasta 120 minutos",
        "definition": (
            "La condición clínica del paciente requiere de medidas diagnósticas y terapéuticas "
            "en urgencias. Son aquellos pacientes que necesitan un examen complementario o un "
            "tratamiento rápido, dado que se encuentran estables desde el punto de vista fisiológico "
            "aunque su situación puede empeorar si no se actúa."
        ),
        "criteria": [
            "Vértigo severo",
            "Dificultad respiratoria leve",
            "Vómito y diarrea con deshidratación severa",
            "Síntomas asociados a diálisis",
            "Trauma moderado",
            "Quemadura de II o III grado",
            "Reacción alérgica con brote generalizado",
            "Valoración médico legal"
        ]
    },
    4: {
        "name": "Consulta Prioritaria",
        "color": "Verde",
        "attention_time": "Direccionamiento a su EPS",
        "definition": (
            "El paciente presenta condiciones médicas que no comprometen su estado general, "
            "ni representan un riesgo evidente para la vida o pérdida de miembro u órgano. "
            "No obstante, existen riesgos de complicación o secuelas de la enfermedad o lesión "
            "si no recibe la atención correspondiente."
        ),
        "criteria": [
            "Tos y congestión",
            "Faringitis o amigdalitis",
            "Vómito y diarrea sin deshidratación",
            "Dolor leve a moderado de más de 24 horas",
            "Trauma leve",
            "Signos de infección local",
            "Ardor al orinar",
            "Enfermedad venérea aguda",
            "Ansiedad y depresión"
        ]
    },
    5: {
        "name": "Consulta Externa",
        "color": "Azul",
        "attention_time": "Direccionamiento a su EPS",
        "definition": (
            "El paciente presenta una condición clínica relacionada con problemas agudos o crónicos "
            "sin evidencia de deterioro que comprometa el estado general de paciente y no representa "
            "un riesgo evidente para la vida o la funcionalidad de miembro u órgano."
        ),
        "criteria": [
            "Síntomas agudos que no comprometan el estado general",
            "Dolor de cabeza crónico",
            "Tos crónica",
            "Inapetencia",
            "Diarrea crónica",
            "Estreñimiento",
            "Dolor abdominal crónico",
            "Dolor postraumático leve",
            "Dermatitis",
            "Estrés emocional",
            "Enfermedades crónicas",
            "Formulación de medicamentos",
            "Lectura de exámenes"
        ]
    }
}


def _normalize_text(text: str) -> str:
    """Elimina tildes y pasa a minusculas para concordancia fonetica/lexica."""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def evaluate_christus_sinergia_triage(transcript: str, symptoms: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Motor determinista de clasificacion de triaje basado estrictamente en el protocolo
    institucional Christus Sinergia Salud.
    Sirve como mecanismo de garantia asistencial si el LLM falla, no responde (503) o se excede el timeout.
    Un patron solo dispara su nivel si alguna coincidencia no esta negada ("niega dolor toracico").
    """
    combined = transcript + " " + " ".join(symptoms or [])
    norm = _normalize_text(combined)

    # 1. Reglas de Triage 1 (Reanimacion - Inmediata)
    triage1_patterns = [
        # "paro" y "coma" sueltos casaban con frases cotidianas ("cuando me paro", "que coma").
        (r"\b(paro (?:cardiaco|cardiorrespiratorio|respiratorio)|(?:un|en) paro|sin signos vitales|no respira|inconsciente|inconciencia|desmayado sin responder|(?:en|estado de) coma|comatoso)\b", "Inconciencia o ausencia de signos vitales"),
        (r"\b(asfixia|cianosis severa|paro respiratorio|dificultad respiratoria severa|no puede respirar nada)\b", "Dificultad respiratoria severa con riesgo vital"),
        (r"\b(hemorragia masiva|desangrando|sangrado exanguinante|amputacion|perdida de miembro|perdida de organo)\b", "Hemorragia masiva o pérdida de miembro u órgano"),
        (r"\b(parto expulsivo|coronando|bebe saliendo|naciendo ya)\b", "Trabajo de parto expulsivo"),
        (r"\b(quemadura en todo el cuerpo|gran quemado|hipotermia severa)\b", "Quemaduras corporales extensas o hipotermia severa"),
        (r"\b(politraumatismo severo|atropellado alta velocidad|caida de gran altura)\b", "Traumatismos severos múltiples")
    ]
    for pattern, reason in triage1_patterns:
        if find_affirmed(pattern, norm):
            return {
                "level": 1,
                "name": "Reanimación",
                "attention_time": "Inmediata",
                "justification": f"Protocolo Christus Sinergia Salud - Triage 1: {reason}. Requiere reanimación inmediata.",
                "confidence": 0.98,
                "protocol": "Christus Sinergia Salud"
            }

    # 2. Reglas de Triage 2 (Emergencia - < 30 min)
    triage2_patterns = [
        (r"\b(dolor (de|en el) pecho|opresion toracica|dolor toracico|infarto|angina|irradiado al brazo|irradiado a la mandibula)\b", "Dolor torácico con signos de alarma (sospecha SCA)"),
        (r"\b(convulsion(?:es)?|convulsionando|estado convulsivo|crisis epilepticas?|estatus)\b", "Estado convulsivo"),
        (r"\b(crisis hipertensiva|presion muy alta|presion 180|presion 200|emergencia hipertensiva)\b", "Crisis hipertensiva"),
        (r"\b(diabetes descompensada|cetoacidosis|glucosa ?> ?\d+|azucar 400|azucar 500|coma diabetico)\b", "Diabetes descompensada"),
        (r"\b(dificultad respiratoria moderada|ahogo moderado|tirajes intercostales|saturacion menor|sat < 90)\b", "Dificultad respiratoria moderada"),
        (r"\b(fractura expuesta|hueso afuera|hueso visible)\b", "Fractura expuesta"),
        (r"\b(sangrado vaginal.*embaraz\w*|embarazada.*sangr\w*|metrorragia)\b", "Sangrado vaginal en paciente embarazada"),
        (r"\b(intoxicacion|envenenamiento|tomo veneno|ingestion de toxicos|sobredosis)\b", "Ingestión de sustancias tóxicas o envenenamiento"),
        (r"\b(agitacion psicomotora|brote psicotico|intento de suicidio|agresivo incontrolable)\b", "Agitación psicomotora aguda"),
        (r"\b(quemadura de tercer grado|quemadura profunda|quemadura de 3er grado)\b", "Quemadura de III grado")
    ]
    for pattern, reason in triage2_patterns:
        if find_affirmed(pattern, norm):
            return {
                "level": 2,
                "name": "Emergencia",
                "attention_time": "Dentro de los siguientes 30 minutos",
                "justification": f"Protocolo Christus Sinergia Salud - Triage 2: {reason}. Condición con riesgo de rápido deterioro vital o funcional.",
                "confidence": 0.94,
                "protocol": "Christus Sinergia Salud"
            }

    # 3. Reglas de Triage 3 (Urgencia - < 120 min)
    triage3_patterns = [
        (r"\b(vertigo severo|mareo incapacitante|no se puede parar)\b", "Vértigo severo incapacitante"),
        (r"\b(dificultad respiratoria leve|disnea leve|silbidos? en el pecho|sibilancias?)\b", "Dificultad respiratoria leve"),
        (r"\b(vomito y diarrea(?! sin deshidrat)|(?<!sin )deshidratacion|no tolera via oral|vomitando todo|diarrea abundante)\b", "Vómito y diarrea con signos de deshidratación"),
        (r"\b(dialisis|fistula arteriovenosa|insuficiencia renal aguda)\b", "Síntomas asociados a tratamiento de diálisis"),
        (r"\b(reaccion alergica|alergia con brote|urticaria generalizada|ronchas en todo el cuerpo)\b", "Reacción alérgica con brote generalizado"),
        (r"\b(quemadura de segundo grado|quemadura 2do grado|ampollas por quemadura)\b", "Quemadura de II o III grado localizada"),
        (r"\b(trauma moderado|golpe fuerte|esguince severo|luxacion|deformidad sin herida expuesta)\b", "Trauma moderado con dolor agudo")
    ]
    for pattern, reason in triage3_patterns:
        if find_affirmed(pattern, norm):
            return {
                "level": 3,
                "name": "Urgencia",
                "attention_time": "Hasta 120 minutos",
                "justification": f"Protocolo Christus Sinergia Salud - Triage 3: {reason}. Paciente estable fisiológicamente pero requiere exámenes diagnósticos o terapia de urgencia.",
                "confidence": 0.89,
                "protocol": "Christus Sinergia Salud"
            }

    # 4. Reglas de Triage 4 (Consulta Prioritaria - Direccionamiento EPS)
    triage4_patterns = [
        (r"\b(tos y congestion|gripe|gripa|resfriado comun|congestiona|rinorrea|moqueo)\b", "Tos y congestión respiratoria alta"),
        (r"\b(faringitis|amigdalitis|dolor de garganta|placas en la garganta|odinofagia)\b", "Faringitis o amigdalitis aguda"),
        (r"\b(vomito.*sin deshidrat\w*|diarrea.*sin deshidrat\w*|gastroenteritis leve)\b", "Vómito o diarrea sin deshidratación"),
        (r"\b(ardor al orinar|chistata|infeccion urinaria leve|disuria)\b", "Ardor al orinar o sospecha de infección local"),
        (r"\b(dolor de cabeza leve|dolor leve.*24 horas|dolor moderado.*dias)\b", "Dolor leve a moderado de más de 24 horas de evolución"),
        (r"\b(trauma leve|golpe leve|raspada|herida superficial)\b", "Trauma menor superficial"),
        (r"\b(ansiedad|depresion|crisis de angustia leve)\b", "Ansiedad o depresión sin ideación autolítica")
    ]
    for pattern, reason in triage4_patterns:
        if find_affirmed(pattern, norm):
            return {
                "level": 4,
                "name": "Consulta Prioritaria",
                "attention_time": "Direccionamiento a su EPS",
                "justification": f"Protocolo Christus Sinergia Salud - Triage 4: {reason}. Cuadro médico que no compromete el estado general; direccionable a consulta prioritaria de EPS.",
                "confidence": 0.88,
                "protocol": "Christus Sinergia Salud"
            }

    # 5. Reglas de Triage 5 (Consulta Externa - Direccionamiento EPS)
    triage5_patterns = [
        (r"\b(dolor de cabeza cronico|migrana de anos|cefalea cronica)\b", "Dolor de cabeza crónico"),
        (r"\b(tos cronica|tos de meses|tos de semanas)\b", "Tos crónica"),
        (r"\b(estrenimiento|inapetencia|dolor abdominal cronico|gastritis cronica)\b", "Síntomas digestivos crónicos o inapetencia"),
        (r"\b(dermatitis|alergia en la piel de tiempo|granos cronicos)\b", "Dermatitis o afección cutánea crónica"),
        (r"\b(lectura de examenes|mirar examenes|resultados de laboratorio)\b", "Lectura de exámenes de laboratorio"),
        (r"\b(formulacion de medicamentos|receta|renovacion de formula)\b", "Formulación de medicamentos o control rutinario")
    ]
    for pattern, reason in triage5_patterns:
        if find_affirmed(pattern, norm):
            return {
                "level": 5,
                "name": "Consulta Externa",
                "attention_time": "Direccionamiento a su EPS",
                "justification": f"Protocolo Christus Sinergia Salud - Triage 5: {reason}. Problema agudo o crónico sin evidencia de deterioro vital; corresponde a Consulta Externa ambulatoria.",
                "confidence": 0.87,
                "protocol": "Christus Sinergia Salud"
            }

    # Fallback por defecto si no encaja en patrones criticos: Nivel 4 o 5 segun presencia de dolor
    if find_affirmed(r"\b(dolor|duele|fiebre)\b", norm):
        return {
            "level": 4,
            "name": "Consulta Prioritaria",
            "attention_time": "Direccionamiento a su EPS",
            "justification": "Protocolo Christus Sinergia Salud - Triage 4: Síntomas generales estables sin signos de alarma vital identificados. Requiere consulta prioritaria.",
            "confidence": 0.80,
            "protocol": "Christus Sinergia Salud"
        }

    return {
        "level": 5,
        "name": "Consulta Externa",
        "attention_time": "Direccionamiento a su EPS",
        "justification": "Protocolo Christus Sinergia Salud - Triage 5: Motivo de consulta sin compromiso de estado general. Corresponde a atención ambulatoria en red EPS.",
        "confidence": 0.78,
        "protocol": "Christus Sinergia Salud"
    }
