import hashlib
import json
import logging
import math
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from transcription.terminology import find_concepts, fold
from .clinical_protocol import CHRISTUS_SINERGIA_LEVELS, _normalize_text
from .negation import strip_negated

logger = logging.getLogger(__name__)

# Stopwords funcionales en espanol que contaminaban la interseccion lexica del RAG.
_RAG_STOPWORDS = frozenset({
    "a", "al", "algo", "algun", "alguna", "algunas", "algunos", "ante", "antes", "asi", "aun",
    "bajo", "cabe", "cada", "casi", "como", "con", "contra", "cual", "cuando", "de", "del",
    "desde", "donde", "dos", "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estaba", "estado", "estan", "estar", "estas",
    "este", "esto", "estos", "estoy", "fue", "ha", "hace", "hacia", "han", "hasta", "hay", "he",
    "hoy", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi", "mis", "mucho", "mucha",
    "muy", "nada", "ni", "no", "nos", "o", "otra", "otras", "otro", "otros", "para", "pero",
    "poco", "por", "porque", "pues", "que", "quien", "se", "sea", "segun", "ser", "si", "sido",
    "sin", "sobre", "solo", "son", "su", "sus", "tal", "tambien", "tan", "tanto", "te", "tengo",
    "tiene", "tienen", "todo", "toda", "todos", "todas", "tras", "tu", "tus", "un", "una",
    "unas", "uno", "unos", "usted", "va", "van", "varios", "veces", "viene", "vengo", "y", "ya", "yo",
    "paciente", "cuadro", "signos", "sintomas", "criterio", "criterios", "nivel", "atencion",
    "compromiso", "evolucion", "periodo", "sospecha", "presencia", "evidente", "requiere",
})

_WORD_RE = re.compile(r"[a-z0-9]{2,}")
_VECTOR_TABLE = "triage_clinical_rag_vectors"
_HASH_EMBED_DIM = 256

# Base de Conocimiento Ontologico y Criterios Institucionales Enriquecidos
CLINICAL_KNOWLEDGE_BASE = [
    # =========================================================================
    # --- NIVEL 1: REANIMACION (ATENCION INMEDIATA - RIESGO VITAL CRITICO) ---
    # =========================================================================
    {
        "id": "c1_vital_arrest",
        "level": 1,
        "name": "Reanimación",
        "category": "neurologico_vital",
        "criterion": "Ausencia de signos vitales, paro cardiorrespiratorio presenciado o inminente, o estado de coma profundo (Glasgow <= 8).",
        "keywords": [
            "paro cardiaco", "paro cardiorrespiratorio", "sin signos vitales", "inconsciente", "inconciencia",
            "coma profundo", "muerte aparente", "sin pulso", "glasgow menor de 8", "no despierta",
            "no reacciona", "no responde", "frio y morado",
        ]
    },
    {
        "id": "c1_resp_failure_extreme",
        "level": 1,
        "name": "Reanimación",
        "category": "respiratorio",
        "criterion": "Insuficiencia respiratoria extrema, asfixia aguda, respiración agónica/gasping o paro respiratorio.",
        "keywords": [
            "asfixia", "cianosis severa", "no respira", "paro respiratorio", "ahogo severo",
            "gasping", "apnea", "respiracion agonica", "boqueando", "labios morados",
        ]
    },
    {
        "id": "c1_airway_obstruction",
        "level": 1,
        "name": "Reanimación",
        "category": "respiratorio",
        "criterion": "Obstrucción completa o inminente de la vía aérea superior por cuerpo extraño, laringoespasmo o angioedema severo.",
        "keywords": [
            "cuerpo extrano via aerea", "atragantamiento", "angioedema laringeo",
            "estridor inspiratorio severo", "obstruccion via aerea", "lengua hinchada no deja respirar",
        ]
    },
    {
        "id": "c1_exsanguination",
        "level": 1,
        "name": "Reanimación",
        "category": "hemodinamico_trauma",
        "criterion": "Hemorragia masiva exanguinante activa, herida arterial pulsátil, amputación traumática mayor o pérdida de órgano/miembro.",
        "keywords": [
            "hemorragia masiva", "desangrando", "amputacion", "perdida de miembro", "perdida de organo",
            "sangrado arterial", "choque hemorragico", "sangre a chorros", "sangre a borbotones",
        ]
    },
    {
        "id": "c1_shock_severe",
        "level": 1,
        "name": "Reanimación",
        "category": "hemodinamico",
        "criterion": "Choque profundo (séptico, hipovolémico, anafiláctico o cardiogénico) con colapso circulatorio y presión arterial sistólica < 70 mmHg.",
        "keywords": [
            "choque septico", "colapso circulatorio", "choque anafilactico", "presion indetectable",
            "hipotension extrema", "pulso filiforme", "manos heladas", "sudoroso y palido",
        ]
    },
    {
        "id": "c1_status_epilepticus",
        "level": 1,
        "name": "Reanimación",
        "category": "neurologico",
        "criterion": "Estatus epiléptico convulsivo activo prolongado (> 5 minutos) o crisis repetitivas continuas sin recuperación de conciencia.",
        "keywords": [
            "estatus epileptico", "convulsion continua", "crisis convulsiva sin despertar",
            "convulsion mayor a 5 minutos", "sigue convulsionando",
        ]
    },
    {
        "id": "c1_imminent_birth",
        "level": 1,
        "name": "Reanimación",
        "category": "obstetrico",
        "criterion": "Trabajo de parto en período expulsivo inminente con periné abombado o coronamiento fetal.",
        "keywords": [
            "parto expulsivo", "coronando", "bebe naciendo", "expulsivo", "cabeza visible",
            "cabeza del bebe", "se le ve la cabeza", "esta pujando", "ganas de pujar", "saliendo el bebe",
        ]
    },
    {
        "id": "c1_major_burn_trauma",
        "level": 1,
        "name": "Reanimación",
        "category": "trauma",
        "criterion": "Politraumatismo severo múltiple, herida penetrante de tórax/abdomen, gran quemado (> 20% SCT) o quemadura por inhalación de vía aérea.",
        "keywords": [
            "politraumatismo", "gran quemado", "quemadura todo el cuerpo", "quemadura via aerea",
            "trauma toracico penetrante", "herida por arma de fuego", "apunalado en el pecho",
        ]
    },
    {
        "id": "c1_hypothermia_extreme",
        "level": 1,
        "name": "Reanimación",
        "category": "ambiental",
        "criterion": "Hipotermia extrema (< 32°C) o golpe de calor extremo con alteración del estado de conciencia y colapso vital.",
        "keywords": [
            "hipotermia severa", "temperatura menor de 32", "golpe de calor severo", "colapso termico",
        ]
    },
    {
        "id": "c1_sexual_abuse_acute",
        "level": 1,
        "name": "Reanimación",
        "category": "legal_urgencia",
        "criterion": "Víctima de violencia o abuso sexual con evento ocurrido en un período menor a 72 horas (Código Blanco / profilaxis PEP inmediata).",
        "keywords": [
            "abuso sexual menor a 72 horas", "violencia sexual reciente", "codigo blanco",
            "agresion sexual menor de 72 horas", "abuso sexual anoche", "abuso sexual hoy",
        ]
    },

    # =========================================================================
    # --- NIVEL 2: EMERGENCIA (ATENCION < 30 MIN - ALTO RIESGO DE DETERIORO) ---
    # =========================================================================
    {
        "id": "c2_chest_pain_sca",
        "level": 2,
        "name": "Emergencia",
        "category": "cardiovascular",
        "criterion": "Dolor torácico opresivo con signos de alarma, sospecha de Síndrome Coronario Agudo, infarto de miocardio o angina inestable.",
        "keywords": [
            "dolor de pecho", "dolor en el pecho", "dolor toracico", "opresion en el pecho", "aprieta el pecho",
            "infarto", "angina", "irradiado al brazo", "irradiado a la mandibula", "diaforesis", "dolor precordial",
        ]
    },
    {
        "id": "c2_stroke_acv",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Sospecha de Accidente Cerebrovascular (ACV/Ictus) agudo: asimetría facial, pérdida de fuerza en hemicuerpo, afasia o disartria aguda en ventana terapéutica.",
        "keywords": [
            "acv", "accidente cerebrovascular", "derrame cerebral", "ictus", "asimetria facial",
            "boca torcida", "torcio la boca", "hemiparesia", "perdida de fuerza en brazo", "disartria",
            "afasia", "habla enredado", "no puede mover el lado", "no siente la pierna", "no entiende lo que le decimos",
        ]
    },
    {
        "id": "c2_thunderclap_headache",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Cefalea súbita de máxima intensidad ('en estallido' o en trueno), sospecha de hemorragia subaracnoidea o signos meníngeos agudos.",
        "keywords": [
            "cefalea en trueno", "cefalea en estallido", "la peor cefalea de la vida",
            "dolor de cabeza subito insoportable", "rigidez de nuca", "peor dolor de cabeza",
        ]
    },
    {
        "id": "c2_hypertensive_crisis",
        "level": 2,
        "name": "Emergencia",
        "category": "cardiovascular",
        "criterion": "Crisis hipertensiva con cifras sistólicas >= 180 mmHg o diastólicas >= 110 mmHg con o sin compromiso de órgano diana.",
        "keywords": [
            "crisis hipertensiva", "presion muy alta", "tension 180", "tension 200",
            "emergencia hipertensiva", "encefalopatia hipertensiva", "presion en 190",
        ]
    },
    {
        "id": "c2_seizures",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Estado convulsivo reciente o crisis epilépticas repetitivas con período postictal prolongado o alteración neurológica persistente.",
        "keywords": [
            "convulsion", "convulsionando", "estado convulsivo", "crisis epileptica",
            "ataque de epilepsia", "postictal prolongado",
        ]
    },
    {
        "id": "c2_resp_moderate",
        "level": 2,
        "name": "Emergencia",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria moderada-severa, desaturación SpO2 < 90%, taquipnea marcada (FR > 28 rpm) o uso de músculos accesorios/tirajes.",
        "keywords": [
            "dificultad respiratoria moderada", "saturacion menor a 90", "tirajes", "disnea moderada",
            "fatiga respiratoria", "tirajes intercostales", "aleteo nasal", "se le hunden las costillas",
        ]
    },
    {
        "id": "c2_diabetes_decompensation",
        "level": 2,
        "name": "Emergencia",
        "category": "metabolico",
        "criterion": "Diabetes descompensada aguda, cetoacidosis diabética, estado hiperosmolar (glucemia > 350 mg/dL) o hipoglucemia severa (< 50 mg/dL) con neuroglucopenia.",
        "keywords": [
            "diabetes descompensada", "cetoacidosis", "coma diabetico", "azucar por las nubes",
            "azucar alta", "hiperglucemia", "azucar 400", "azucar 500", "glucometria", "hipoglucemia severa",
            "glucemia menor de 50", "respiracion de kussmaul", "mucha sed", "polidipsia",
        ]
    },
    {
        "id": "c2_acute_abdomen",
        "level": 2,
        "name": "Emergencia",
        "category": "digestivo",
        "criterion": "Abdomen agudo quirúrgico sospechado, signos de irritación peritoneal, defensa muscular involuntaria o dolor abdominal intolerable con hipotensión.",
        "keywords": [
            "abdomen agudo", "irritacion peritoneal", "vientre en tabla", "peritonitis",
            "defensa muscular", "apendicitis complicada", "abdomen perforado",
            "barriga durisima", "estomago duro", "no se deja tocar", "no puedo caminar derecho del dolor",
        ]
    },
    {
        "id": "c2_gastro_bleeding_high",
        "level": 2,
        "name": "Emergencia",
        "category": "digestivo",
        "criterion": "Hemorragia digestiva alta activa manifestada por hematemesis o melenas abundantes con taquicardia o hipotensión ortostática.",
        "keywords": [
            "hematemesis", "vomito con sangre", "vomitando sangre", "melenas", "hemorragia digestiva alta",
            "sangrado digestivo activo", "cuncho de cafe", "borra de cafe", "popo negra", "heces negras",
        ]
    },
    {
        "id": "c2_open_fracture_burn",
        "level": 2,
        "name": "Emergencia",
        "category": "trauma",
        "criterion": "Fractura expuesta con hueso visible, luxofractura con compromiso de pulsos distales, síndrome compartimental o quemadura de III grado profunda.",
        "keywords": [
            "fractura expuesta", "hueso afuera", "hueso visible", "quemadura de tercer grado",
            "quemadura grado 3", "sindrome compartimental", "falta de pulso distal",
        ]
    },
    {
        "id": "c2_toxic_ingestion",
        "level": 2,
        "name": "Emergencia",
        "category": "toxicologico",
        "criterion": "Ingestión de sustancias tóxicas, cáusticos, plaguicidas, sobredosis medicamentosa o envenenamiento por mordedura de serpiente/escorpión.",
        "keywords": [
            "intoxicacion", "veneno", "envenenamiento", "ingestion toxico", "sobredosis",
            "plaguicida", "mordedura de serpiente", "acido ingerido", "caustico", "tomo pastillas",
        ]
    },
    {
        "id": "c2_pregnancy_bleeding_preeclampsia",
        "level": 2,
        "name": "Emergencia",
        "category": "obstetrico",
        "criterion": "Sangrado vaginal agudo en paciente embarazada, sospecha de desprendimiento de placenta, embarazo ectópico o preeclampsia severa con cefalea y fosfenos.",
        "keywords": [
            "sangrado embarazada", "embarazada sangrando", "sangrado vaginal", "metrorragia",
            "perdida de sangre en embarazo", "preeclampsia severa", "embarazo ectopico",
            "dolor de cabeza en embarazo", "lucecitas embarazo",
        ]
    },
    {
        "id": "c2_active_labor",
        "level": 2,
        "name": "Emergencia",
        "category": "obstetrico",
        "criterion": "Trabajo de parto activo con contracciones uterinas regulares intensas, salida de líquido amniótico (ruptura de membranas) o disminución de movimientos fetales.",
        "keywords": [
            "trabajo de parto", "contracciones seguidas", "rompio fuente", "liquido amniotico",
            "bebe no se mueve", "disminucion movimientos fetales",
        ]
    },
    {
        "id": "c2_sexual_abuse_subacute",
        "level": 2,
        "name": "Emergencia",
        "category": "legal_urgencia",
        "criterion": "Víctima de abuso o violencia sexual con evento ocurrido en un período mayor a 72 horas (atención integral prioritaria médica, legal y psicosocial).",
        "keywords": [
            "abuso sexual mayor a 72 horas", "abuso sexual", "violencia sexual", "agresion sexual",
            "violacion", "abuso sexual hace una semana", "abuso sexual hace dias",
        ]
    },
    {
        "id": "c2_sepsis_qsofa",
        "level": 2,
        "name": "Emergencia",
        "category": "infeccioso",
        "criterion": "Sospecha de sepsis con criterios qSOFA >= 2: alteración del sensorio, FR >= 22 rpm y PAS <= 100 mmHg con foco infeccioso evidente.",
        "keywords": [
            "sepsis", "choque septico inminente", "infeccion con presion baja", "qsofa",
            "confuso y con fiebre", "desorientado con fiebre", "hablando incoherencias",
        ]
    },
    {
        "id": "c2_ocular_chemical_trauma",
        "level": 2,
        "name": "Emergencia",
        "category": "oftalmologico",
        "criterion": "Quemadura química ocular por ácidos o álcalis, trauma ocular penetrante con pérdida de líquido intraocular o pérdida súbita total de visión.",
        "keywords": [
            "quemadura quimica en ojo", "quimico en el ojo", "trauma ocular penetrante",
            "ojo perforado", "ceguera subita", "no ve nada de un ojo",
        ]
    },
    {
        "id": "c2_testicular_torsion",
        "level": 2,
        "name": "Emergencia",
        "category": "urologico",
        "criterion": "Dolor escrotal agudo intenso de inicio súbito (< 6 horas), sospecha de torsión testicular o priapismo isquémico agudo.",
        "keywords": ["torsion testicular", "dolor testicular subito", "testiculo hinchado", "priapismo"]
    },
    {
        "id": "c2_psychiatric_agitation_suicide",
        "level": 2,
        "name": "Emergencia",
        "category": "salud_mental",
        "criterion": "Agitación psicomotora severa con riesgo inminente de auto/heteroagresión o intento suicida reciente activo con ideación estructurada.",
        "keywords": [
            "agitacion psicomotora", "intento de suicidio", "intento suicida", "quitarse la vida",
            "ideacion suicida estructurada", "agresion incontrolable", "psicosis aguda",
        ]
    },
    {
        "id": "c2_febrile_infant_young",
        "level": 2,
        "name": "Emergencia",
        "category": "pediatrico",
        "criterion": "Lactante menor de 3 meses (< 90 días) con fiebre (> 38.0°C), rechazo alimentario, letargia o irritabilidad inconsolable.",
        "keywords": [
            "bebe menor de 3 meses con fiebre", "lactante febril", "recien nacido con fiebre",
            "bebe de un mes con fiebre", "bebe que no recibe pecho",
        ]
    },

    # =========================================================================
    # --- NIVEL 3: URGENCIA (ATENCION < 120 MIN - ESTABLE CON RECURSOS) ---
    # =========================================================================
    {
        "id": "c3_renal_colic",
        "level": 3,
        "name": "Urgencia",
        "category": "urologico",
        "criterion": "Cólico renoureteral o litiasis renal con dolor lumbar intenso tipo cólico unilateral, irradiado a fosa ilíaca o genitales, que requiere analgesia parenteral.",
        "keywords": ["colico renal", "calculo renal", "piedra en el rinon", "dolor lumbar tipo colico", "colico nefritico"]
    },
    {
        "id": "c3_vertigo_incapacitating",
        "level": 3,
        "name": "Urgencia",
        "category": "neurologico",
        "criterion": "Vértigo severo incapacitante con náuseas y vómito que impide la bipedestación o marcha pero con signos vitales estables.",
        "keywords": ["vertigo severo", "mareo incapacitante", "no se puede parar", "todo le da vueltas", "vertigo con vomito"]
    },
    {
        "id": "c3_mild_resp",
        "level": 3,
        "name": "Urgencia",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria leve, sibilancias aisladas o tos asmática sin desaturación severa (SpO2 92% a 94%) que requiere terapia inhalada.",
        "keywords": ["dificultad respiratoria leve", "silbido pecho", "silbidos en el pecho", "sibilancia", "disnea leve", "asma leve", "saturacion 92", "saturacion 93"]
    },
    {
        "id": "c3_gastro_dehydration",
        "level": 3,
        "name": "Urgencia",
        "category": "digestivo",
        "criterion": "Vómito y diarrea con signos clínicos de deshidratación moderada o intolerancia a la vía oral que requiere rehidratación endovenosa.",
        "keywords": ["vomito y diarrea", "deshidratacion", "no tolera suero", "no tolero ni el agua", "intolerancia via oral", "boca muy seca", "diarrea abundante", "deshidratacion moderada"]
    },
    {
        "id": "c3_dialysis_complication",
        "level": 3,
        "name": "Urgencia",
        "category": "renal",
        "criterion": "Síntomas asociados a tratamiento de diálisis renal o complicación local de fístula arteriovenosa / catéter peritoneal sin choque.",
        "keywords": ["dialisis", "hemodialisis", "fistula arteriovenosa", "cateter peritoneal", "insuficiencia renal en dialisis"]
    },
    {
        "id": "c3_moderate_trauma",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Trauma moderado de extremidades con dolor limitante, sospecha de fractura cerrada, luxación articular o esguince severo (grado II/III).",
        "keywords": ["trauma moderado", "golpe fuerte", "esguince severo", "luxacion", "fractura cerrada", "deformidad articular", "no puede apoyar el pie"]
    },
    {
        "id": "c3_allergic_reaction",
        "level": 3,
        "name": "Urgencia",
        "category": "inmunoalergico",
        "criterion": "Reacción alérgica con urticaria/brote generalizado y prurito intenso, sin compromiso de vía aérea ni edema de glotis.",
        "keywords": ["reaccion alergica", "alergia con brote", "urticaria", "ronchas en todo el cuerpo", "ronchas en el cuerpo", "picazon generalizada", "habones generalizados"]
    },
    {
        "id": "c3_burn_grade_2",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Quemadura de II grado localizada con flictenas o ampollas en área menor al 10% corporal en zonas no especiales.",
        "keywords": ["quemadura de segundo grado", "quemadura grado 2", "ampollas por quemadura", "flictenas", "quemadura con agua caliente"]
    },
    {
        "id": "c3_urinary_retention",
        "level": 3,
        "name": "Urgencia",
        "category": "urologico",
        "criterion": "Retención urinaria aguda con globo vesical palpable y dolor hipogástrico intenso que requiere cateterismo vesical de urgencia.",
        "keywords": ["retencion urinaria aguda", "globo vesical", "no puede orinar nada", "vejiga llena y dolorosa"]
    },
    {
        "id": "c3_cellulitis_abscess",
        "level": 3,
        "name": "Urgencia",
        "category": "infeccioso",
        "criterion": "Infección de tejidos blandos moderada, celulitis extensa en progresión rápida o absceso subcutáneo fluctuante doloroso que requiere drenaje.",
        "keywords": ["celulitis", "absceso doloroso", "nacido hinchado con pus", "infeccion en piel que avanza", "flemon"]
    },
    {
        "id": "c3_epistaxis_persistent",
        "level": 3,
        "name": "Urgencia",
        "category": "orl",
        "criterion": "Sangrado nasal (epistaxis) persistente que no cede tras 20-30 minutos de compresión digital directa.",
        "keywords": ["epistaxis persistente", "sangrado nasal que no para", "hemorragia nasal continua"]
    },
    {
        "id": "c3_persistent_fever",
        "level": 3,
        "name": "Urgencia",
        "category": "infeccioso",
        "criterion": "Fiebre persistente de más de 48-72 horas de evolución con compromiso del estado general, o sospecha de dengue en zona endémica sin signos de alarma.",
        "keywords": ["fiebre de varios dias", "fiebre persistente de 3 dias", "sospecha de dengue", "fiebre con dolor retroocular y mialgias"]
    },
    {
        "id": "c3_deep_laceration",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Herida por corte profunda que compromete fascia o músculo y requiere sutura quirúrgica por planos o hemostasia local.",
        "keywords": ["herida profunda", "corte profundo", "herida para suturar", "laceracion muscular"]
    },
    {
        "id": "c3_panic_attack",
        "level": 3,
        "name": "Urgencia",
        "category": "salud_mental",
        "criterion": "Ataque de pánico o crisis de angustia aguda severa con hiperventilación y parestesias, tras descartar patología cardiovascular orgánica.",
        "keywords": ["ataque de panico", "crisis de angustia severa", "hiperventilacion con adormecimiento de manos", "crisis de ansiedad aguda"]
    },
    {
        "id": "c3_medicolegal_assessment",
        "level": 3,
        "name": "Urgencia",
        "category": "legal_urgencia",
        "criterion": "Valoración médico-legal en urgencias por lesiones personales o violencia intrafamiliar con estabilidad fisiológica conservada.",
        "keywords": ["valoracion medico legal", "medicina legal", "violencia intrafamiliar", "dictamen lesiones"]
    },

    # =========================================================================
    # --- NIVEL 4: CONSULTA PRIORITARIA (ATENCION SUBAGUDA / 24 HORAS) ---
    # =========================================================================
    {
        "id": "c4_upper_respiratory",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "respiratorio_infeccioso",
        "criterion": "Cuadro respiratorio alto: tos, congestión nasal, odinofagia, faringitis o amigdalitis sin dificultad respiratoria ni desaturación.",
        "keywords": ["tos y congestion", "gripe", "gripa", "resfriado", "dolor de garganta", "amigdalitis", "faringitis", "rinorrea", "moqueo", "catarro", "congestion"]
    },
    {
        "id": "c4_gastro_mild",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "digestivo",
        "criterion": "Vómito o diarrea autolimitada sin deshidratación y con adecuada tolerancia comprobada a líquidos orales.",
        "keywords": ["vomito sin deshidratacion", "diarrea sin deshidratacion", "gastroenteritis leve", "soltura leve", "diarrea tolerando suero"]
    },
    {
        "id": "c4_dysuria_urinary",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "urologico",
        "criterion": "Ardor al orinar (disuria), polaquiuria o síntomas de infección urinaria baja sin fiebre alta, náuseas ni dolor lumbar.",
        "keywords": ["ardor al orinar", "chistata", "infeccion urinaria", "disuria", "polaquiuria", "dolor para orinar", "cistitis simple"]
    },
    {
        "id": "c4_subacute_pain",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "dolor_general",
        "criterion": "Dolor leve a moderado de más de 24 horas de evolución, trauma superficial menor, raspaduras o herida sin hemorragia activa.",
        "keywords": ["dolor de varios dias", "dolor mas de 24 horas", "trauma leve", "raspada", "golpe leve", "escoriacion", "morado"]
    },
    {
        "id": "c4_acute_lumbalgia",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "osteomuscular",
        "criterion": "Lumbalgia o dolor de espalda agudo mecánico de esfuerzo, sin irradiación radicular, sin pérdida de fuerza ni incontinencia de esfínteres.",
        "keywords": ["dolor de cintura", "lumbalgia aguda", "dolor de espalda de ayer", "tiron en la espalda", "lumbago de esfuerzo"]
    },
    {
        "id": "c4_ear_infection_mild",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "orl",
        "criterion": "Otitis media o externa leve-moderada, dolor de oído (otalgia) sin parálisis facial ni fiebre alta.",
        "keywords": ["dolor de oido", "otalgia", "otitis", "oido tapado y adolorido"]
    },
    {
        "id": "c4_conjunctivitis",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "oftalmologico",
        "criterion": "Conjuntivitis aguda infecciosa o alérgica con secreción o enrojecimiento ocular, sin dolor severo ni disminución de la agudeza visual.",
        "keywords": ["conjuntivitis", "ojo rojo con laganas", "infeccion en el ojo simple", "picazon en ojos"]
    },
    {
        "id": "c4_mild_sprain",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "trauma",
        "criterion": "Esguince leve de tobillo o muñeca (grado I) con inflamación moderada, apoyo conservado y dolor tolerable.",
        "keywords": ["torcedura de tobillo leve", "esguince leve", "dolor de tobillo apoyando bien"]
    },
    {
        "id": "c4_anxiety_mild",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "salud_mental",
        "criterion": "Episodio de ansiedad o angustia leve a moderada sin ideación suicida ni agitación psicomotora.",
        "keywords": ["ansiedad", "nerviosismo", "depresion leve", "angustia", "estres"]
    },
    {
        "id": "c4_dental_pain",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "odontologico",
        "criterion": "Dolor dental agudo (odontalgia) o caries dolorosa sin inflamación facial extensa ni dificultad para deglutir.",
        "keywords": ["dolor de muela", "odontalgia", "caries con dolor", "dolor de diente"]
    },

    # =========================================================================
    # --- NIVEL 5: CONSULTA EXTERNA (DIRECCIONAMIENTO A EPS / TRAMITES) ---
    # =========================================================================
    {
        "id": "c5_chronic_headache",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Dolor de cabeza crónico de meses o años de evolución con características habituales y sin signos de alarma.",
        "keywords": ["dolor de cabeza cronico", "migrana de anos", "cefalea cronica habitual", "dolor de cabeza de siempre", "migrana de toda la vida"]
    },
    {
        "id": "c5_chronic_digestive",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Síntomas digestivos crónicos: estreñimiento habitual de larga data, dispepsia crónica, inapetencia o dolor abdominal no agudo.",
        "keywords": ["estrenimiento cronico", "inapetencia", "dolor abdominal cronico", "gastritis de meses", "reflujo de anos", "pesadez estomacal cronica"]
    },
    {
        "id": "c5_administrative_routine",
        "level": 5,
        "name": "Consulta Externa",
        "category": "administrativo",
        "criterion": "Trámites administrativos: formulación y renovación de medicamentos de control, incapacidades vencidas o lectura de exámenes de rutina.",
        "keywords": ["formulacion de medicamentos", "receta medica", "renovacion formula", "lectura de examenes", "resultados de laboratorio", "pedir medicamentos", "renovar orden", "certificado medico"]
    },
    {
        "id": "c5_dermatology_subacute",
        "level": 5,
        "name": "Consulta Externa",
        "category": "dermatologia",
        "criterion": "Lesiones de piel crónicas o subagudas: dermatitis de contacto, eccema antiguo, acné o micosis cutánea sin sobreinfección sistémica.",
        "keywords": ["dermatitis", "alergia en la piel cronica", "hongos en las unas", "eccema", "granos antiguos", "acne", "manchas en la piel", "lunar antiguo"]
    },
    {
        "id": "c5_chronic_joint_pain",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico_osteomuscular",
        "criterion": "Dolor osteoarticular crónico mecánico de meses de evolución (artrosis, dolor de rodilla antiguo) sin trauma agudo ni flogosis.",
        "keywords": ["dolor de rodilla de anos", "artrosis", "dolor articular cronico", "dolor de espalda antiguo", "reumatismo"]
    },
    {
        "id": "c5_suture_removal",
        "level": 5,
        "name": "Consulta Externa",
        "category": "enfermeria_procedimientos",
        "criterion": "Retiro de puntos de sutura de herida cicatrizada o curación de herida limpia programada sin complicaciones.",
        "keywords": ["retirar puntos", "quitar puntos de sutura", "curacion programada", "revision de herida limpia"]
    },
    {
        "id": "c5_allergic_rhinitis_chronic",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Rinitis alérgica crónica habitual de años sin cuadro infeccioso agudo ni fiebre.",
        "keywords": ["rinitis alergica cronica", "estornudos de siempre", "rinitis de anos"]
    }
]


def _stem_es(token: str) -> str:
    """Raiz morfologica ligera en espanol clinico para unificar flexiones ('pujando'/'pujar', 'durisima'/'duro')."""
    if len(token) <= 4:
        return token
    for suffix in ("isima", "isimo", "ando", "iendo", "aciones", "acion", "mente", "amiento", "imiento"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[:-len(suffix)]
    for suffix in ("adas", "ados", "idas", "idos", "ada", "ado", "ida", "ido", "ares", "ores", "es", "as", "os", "ar", "er", "ir", "a", "o", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[:-len(suffix)]
    return token


def _tokenize_content(norm_text: str) -> List[str]:
    """Tokens clinicos sin stopwords, acompañados de su raiz morfologica."""
    out: List[str] = []
    for tok in _WORD_RE.findall(norm_text):
        if tok in _RAG_STOPWORDS:
            continue
        out.append(tok)
        stem = _stem_es(tok)
        if stem != tok and stem not in _RAG_STOPWORDS:
            out.append(stem)
    return out


def compute_hashed_embedding(text: str, dim: int = _HASH_EMBED_DIM) -> List[float]:
    """
    Embedding denso determinista L2-normalizado mediante feature hashing con signo sobre
    n-gramas de caracteres (3-5) y raices clinicas sin stopwords. Permite indexar y consultar
    pgvector sin costo de red ni VRAM, y sirve de respaldo cuando no hay servidor de embeddings.
    """
    norm = _normalize_text(text or "")
    tokens = [tok for tok in _WORD_RE.findall(norm) if tok not in _RAG_STOPWORDS]
    vec = [0.0] * dim
    for tok in tokens:
        stem = _stem_es(tok)
        features = [(f"w:{tok}", 2.0), (f"s:{stem}", 1.5)]
        padded = f"<{tok}>"
        for n in (3, 4, 5):
            for i in range(max(0, len(padded) - n + 1)):
                features.append((f"c:{padded[i:i + n]}", 0.6))
        for feat, weight in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign * weight
    norm_val = math.sqrt(sum(v * v for v in vec))
    if norm_val > 0:
        vec = [round(v / norm_val, 6) for v in vec]
    return vec


def embed_texts(texts: List[str], provider: str = "hashed_ngram", model: Optional[str] = None) -> Tuple[List[List[float]], str]:
    """Calcula vectores con 'hashed_ngram', 'ollama' (/api/embed) o 'gemini'."""
    if provider == "ollama":
        base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://ollama:11434/v1").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        embed_model = model or os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
        req = urllib.request.Request(
            f"{base_url}/api/embed",
            data=json.dumps({"model": embed_model, "input": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["embeddings"], f"ollama:{embed_model}"

    if provider == "gemini":
        from google import genai
        from .ai_analyzer import _resolve_gemini_api_key
        api_key = _resolve_gemini_api_key()
        if not api_key:
            raise RuntimeError("No hay GEMINI_API_KEY configurada para embeddings.")
        embed_model = model or os.getenv("RAG_GEMINI_EMBED_MODEL", "gemini-embedding-001")
        client = genai.Client(api_key=api_key)
        res = client.models.embed_content(model=embed_model, contents=texts)
        return [list(e.values) for e in res.embeddings], f"gemini:{embed_model}"

    return [compute_hashed_embedding(t) for t in texts], f"hashed_ngram:{_HASH_EMBED_DIM}"


class ClinicalKnowledgeRAG:
    """
    Motor RAG hibrido (BM25 sin stopwords + expansion terminologica + vectores pgvector opcionales)
    para triaje medico hospitalario bajo el protocolo Christus Sinergia Salud.
    """
    _bm25_cache: Optional[Dict[str, Any]] = None
    _pgvector_ready: Optional[Tuple[str, int]] = None  # (provider_label, dim) cacheado en proceso

    @classmethod
    def _criterion_document(cls, item: Dict[str, Any]) -> str:
        return f"{item['criterion']} {' '.join(item['keywords'])}"

    @classmethod
    def _ensure_bm25_index(cls) -> Dict[str, Any]:
        if cls._bm25_cache is not None and cls._bm25_cache.get("size") == len(CLINICAL_KNOWLEDGE_BASE):
            return cls._bm25_cache
        docs_tf: List[Dict[str, int]] = []
        doc_lens: List[int] = []
        df: Dict[str, int] = {}
        for item in CLINICAL_KNOWLEDGE_BASE:
            tokens = _tokenize_content(_normalize_text(cls._criterion_document(item)))
            tf: Dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            for tok in tf:
                df[tok] = df.get(tok, 0) + 1
            docs_tf.append(tf)
            doc_lens.append(max(1, len(tokens)))
        n_docs = max(1, len(CLINICAL_KNOWLEDGE_BASE))
        idf = {
            tok: math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))
            for tok, freq in df.items()
        }
        avgdl = sum(doc_lens) / n_docs
        cls._bm25_cache = {
            "size": len(CLINICAL_KNOWLEDGE_BASE),
            "docs_tf": docs_tf,
            "doc_lens": doc_lens,
            "idf": idf,
            "avgdl": avgdl,
        }
        return cls._bm25_cache

    @classmethod
    def _expand_query_synonyms(cls, query_norm: str) -> str:
        """Anade el termino clinico de cada coloquialismo o sigla del catalogo terminologico."""
        terms = [fold(match.concept.term) for match in find_concepts(query_norm)]
        return " ".join([query_norm, *terms])

    @classmethod
    def _compute_relevance(cls, query_norm: str, criterion: Dict[str, Any], idx: Optional[int] = None) -> float:
        """Puntaje hibrido: coincidencia de frases clave + Okapi BM25 sin stopwords."""
        score = 0.0

        for kw in criterion["keywords"]:
            kw_norm = _normalize_text(kw)
            if " " in kw_norm:
                if kw_norm in query_norm:
                    score += 3.8
            elif re.search(rf"\b{re.escape(kw_norm)}\b", query_norm):
                score += 2.0

        bm25 = cls._ensure_bm25_index()
        if idx is None:
            idx = next((i for i, c in enumerate(CLINICAL_KNOWLEDGE_BASE) if c["id"] == criterion["id"]), None)
        if idx is not None:
            tf = bm25["docs_tf"][idx]
            dl = bm25["doc_lens"][idx]
            avgdl = bm25["avgdl"]
            k1, b = 1.5, 0.75
            for tok in set(_tokenize_content(query_norm)):
                freq = tf.get(tok, 0)
                if freq:
                    idf = bm25["idf"].get(tok, 0.0)
                    denom = freq + k1 * (1.0 - b + b * (dl / avgdl))
                    score += idf * ((freq * (k1 + 1.0)) / denom)
        else:
            # Criterio ad-hoc pasado en pruebas unitarias fuera de CLINICAL_KNOWLEDGE_BASE.
            crit_tokens = set(_tokenize_content(_normalize_text(criterion["criterion"])))
            query_tokens = set(_tokenize_content(query_norm))
            score += len(crit_tokens & query_tokens) * 0.85

        return score

    @classmethod
    def index_pgvector(cls, provider: str = "hashed_ngram", model: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea la extension pgvector y la tabla vectorial en PostgreSQL e indexa todos los criterios
        de CLINICAL_KNOWLEDGE_BASE. En otros motores lanza RuntimeError explicito.
        """
        from django.db import connection
        if connection.vendor != "postgresql":
            raise RuntimeError(f"pgvector requiere PostgreSQL (motor actual: {connection.vendor}).")

        texts = [cls._criterion_document(item) for item in CLINICAL_KNOWLEDGE_BASE]
        vectors, provider_label = embed_texts(texts, provider=provider, model=model)
        dim = len(vectors[0]) if vectors else _HASH_EMBED_DIM

        with connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"DROP TABLE IF EXISTS {_VECTOR_TABLE};")
            cur.execute(
                f"""
                CREATE TABLE {_VECTOR_TABLE} (
                    criterion_id VARCHAR(80) PRIMARY KEY,
                    level SMALLINT NOT NULL,
                    provider VARCHAR(80) NOT NULL,
                    dim INTEGER NOT NULL,
                    embedding vector({dim}) NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            for item, vec in zip(CLINICAL_KNOWLEDGE_BASE, vectors):
                vec_lit = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
                cur.execute(
                    f"""
                    INSERT INTO {_VECTOR_TABLE} (criterion_id, level, provider, dim, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector);
                    """,
                    [item["id"], item["level"], provider_label, dim, vec_lit],
                )
        cls._pgvector_ready = (provider_label, dim)
        return {"indexed": len(vectors), "provider": provider_label, "dim": dim, "table": _VECTOR_TABLE}

    @classmethod
    def pgvector_search(cls, query_text: str, top_k: int = 8) -> Dict[str, float]:
        """
        Consulta de similitud coseno en PostgreSQL pgvector (`1 - (embedding <=> query::vector)`).
        Si la base de datos no es PostgreSQL, no hay tabla indexada o las pruebas bloquean DB,
        retorna `{}` sin interrumpir la inferencia.
        """
        db_engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
        if "postgresql" not in db_engine or os.getenv("RAG_DISABLE_PGVECTOR") == "1":
            return {}
        try:
            from django.db import connection
            with connection.cursor() as cur:
                if cls._pgvector_ready is None:
                    cur.execute("SELECT to_regclass(%s);", [_VECTOR_TABLE])
                    exists = cur.fetchone()[0]
                    if not exists:
                        cls._pgvector_ready = ("", 0)
                        return {}
                    cur.execute(f"SELECT provider, dim FROM {_VECTOR_TABLE} LIMIT 1;")
                    row = cur.fetchone()
                    if not row:
                        cls._pgvector_ready = ("", 0)
                        return {}
                    cls._pgvector_ready = (row[0], int(row[1]))

                provider_label, dim = cls._pgvector_ready
                if not provider_label or dim <= 0:
                    return {}
                prov, _, mod = provider_label.partition(":")
                q_vecs, _ = embed_texts([query_text], provider=prov, model=mod if prov != "hashed_ngram" else None)
                if not q_vecs or len(q_vecs[0]) != dim:
                    return {}
                vec_lit = "[" + ",".join(f"{v:.6f}" for v in q_vecs[0]) + "]"
                cur.execute(
                    f"""
                    SELECT criterion_id, 1 - (embedding <=> %s::vector) AS similarity
                    FROM {_VECTOR_TABLE}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    [vec_lit, vec_lit, top_k],
                )
                return {cid: float(sim) for cid, sim in cur.fetchall() if sim is not None and float(sim) > 0.22}
        except Exception as err:
            logger.debug(f"Busqueda pgvector omitida: {err}")
            return {}

    @classmethod
    def retrieve(cls, transcript: str, top_k: int = 4, red_flags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recupera los top-K criterios institucionales mas pertinentes para el cuadro clinico.
        Combina Okapi BM25 sin stopwords, expansion ontologica y similitud vectorial pgvector.
        """
        # Los hallazgos negados no deben recuperar criterios: "niega dolor toracico" no es un SCA.
        base_norm = strip_negated(_normalize_text(transcript))
        if not base_norm.strip():
            fallback_ids = ["c1_resp_failure_extreme", "c2_chest_pain_sca", "c4_upper_respiratory", "c5_administrative_routine"]
            id_map = {item["id"]: item for item in CLINICAL_KNOWLEDGE_BASE}
            return [id_map[fid] for fid in fallback_ids if fid in id_map][:top_k]

        query_norm = cls._expand_query_synonyms(base_norm)
        vec_scores = cls.pgvector_search(query_norm, top_k=max(top_k * 2, 8))
        scored_criteria = []

        for idx, item in enumerate(CLINICAL_KNOWLEDGE_BASE):
            lexical = cls._compute_relevance(query_norm, item, idx=idx)
            vec_sim = vec_scores.get(item["id"], 0.0)
            rel = lexical + (vec_sim * 2.5 if vec_sim > 0.22 else 0.0)
            if red_flags and item["level"] in [1, 2] and rel > 0:
                rel += 2.5
            if rel > 0:
                scored_criteria.append((rel, item))

        # Si hay banderas rojas pero ningun criterio 1-2 tuvo solape lexico directo, garantizar diferencial critico.
        if red_flags and not any(item["level"] in (1, 2) for _, item in scored_criteria[:top_k]):
            for item in CLINICAL_KNOWLEDGE_BASE:
                if item["level"] in (1, 2):
                    scored_criteria.append((0.5, item))
                    break

        scored_criteria.sort(key=lambda x: x[0], reverse=True)
        retrieved = [item for _, item in scored_criteria[:top_k]]

        if not retrieved:
            fallback_ids = ["c1_resp_failure_extreme", "c2_chest_pain_sca", "c4_upper_respiratory", "c5_administrative_routine"]
            id_map = {item["id"]: item for item in CLINICAL_KNOWLEDGE_BASE}
            retrieved = [id_map[fid] for fid in fallback_ids if fid in id_map][:top_k]

        return retrieved

    @classmethod
    def describe(cls, criterion_ids: List[str]) -> List[Dict[str, Any]]:
        """Nivel, nombre y texto de cada criterio recuperado, para mostrar al clinico en que se apoyo el triaje."""
        by_id = {item["id"]: item for item in CLINICAL_KNOWLEDGE_BASE}
        return [
            {"id": cid, "level": by_id[cid]["level"], "name": by_id[cid]["name"], "criterion": by_id[cid]["criterion"]}
            for cid in criterion_ids or [] if cid in by_id
        ]

    @classmethod
    def format_context_for_prompt(cls, retrieved_criteria: List[Dict[str, Any]]) -> str:
        """
        Formatea los criterios recuperados en un bloque de contexto altamente comprimido y denso.
        Reduce de ~700 tokens a ~120-180 tokens.
        """
        lines = ["CRITERIOS INSTITUCIONALES RELEVANTES (CHRISTUS SINERGIA SALUD):"]
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
