import re
import math
import unicodedata
from typing import Dict, Any, List, Optional
from .clinical_protocol import CHRISTUS_SINERGIA_LEVELS, _normalize_text
from .negation import strip_negated
from transcription.terminology import find_concepts, fold

# Base de Conocimiento Ontologico y Criterios Institucionales Enriquecidos (80+ Criterios)
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
        "keywords": ["paro", "sin signos vitales", "inconsciente", "inconciencia", "coma", "muerte aparente", "sin pulso", "glasgow menor de 8"]
    },
    {
        "id": "c1_resp_failure_extreme",
        "level": 1,
        "name": "Reanimación",
        "category": "respiratorio",
        "criterion": "Insuficiencia respiratoria extrema, asfixia aguda, respiración agónica/gasping o paro respiratorio.",
        "keywords": ["asfixia", "cianosis severa", "no respira", "paro respiratorio", "ahogo severo", "gasping", "apnea", "respiracion agonica"]
    },
    {
        "id": "c1_airway_obstruction",
        "level": 1,
        "name": "Reanimación",
        "category": "respiratorio",
        "criterion": "Obstrucción completa o inminente de la vía aérea superior por cuerpo extraño, laringoespasmo o angioedema severo.",
        "keywords": ["cuerpo extrano via aerea", "atragantamiento", "angioedema laríngeo", "estridor inspiratorio severo", "obstruccion via aerea"]
    },
    {
        "id": "c1_exsanguination",
        "level": 1,
        "name": "Reanimación",
        "category": "hemodinamico_trauma",
        "criterion": "Hemorragia masiva exanguinante activa, herida arterial pulsátil, amputación traumática mayor o pérdida de órgano/miembro.",
        "keywords": ["hemorragia masiva", "desangrando", "amputacion", "perdida de miembro", "perdida de organo", "sangrado arterial", "choque hemorragico"]
    },
    {
        "id": "c1_shock_severe",
        "level": 1,
        "name": "Reanimación",
        "category": "hemodinamico",
        "criterion": "Choque profundo (séptico, hipovolémico, anafiláctico o cardiogénico) con colapso circulatorio y presión arterial sistólica < 70 mmHg.",
        "keywords": ["choque septico", "colapso circulatorio", "choque anafilactico", "presion indetectable", "hipotension extrema", "pulso filiforme"]
    },
    {
        "id": "c1_status_epilepticus",
        "level": 1,
        "name": "Reanimación",
        "category": "neurologico",
        "criterion": "Estatus epiléptico convulsivo activo prolongado (> 5 minutos) o crisis repetitivas continuas sin recuperación de conciencia.",
        "keywords": ["estatus epileptico", "convulsion continua", "crisis convulsiva sin despertar", "convulsion mayor a 5 minutos"]
    },
    {
        "id": "c1_imminent_birth",
        "level": 1,
        "name": "Reanimación",
        "category": "obstetrico",
        "criterion": "Trabajo de parto en período expulsivo inminente con periné abombado o coronamiento fetal.",
        "keywords": ["parto expulsivo", "coronando", "bebe naciendo", "expulsivo", "cabeza visible"]
    },
    {
        "id": "c1_major_burn_trauma",
        "level": 1,
        "name": "Reanimación",
        "category": "trauma",
        "criterion": "Politraumatismo severo múltiple, herida penetrante de tórax/abdomen, gran quemado (> 20% SCT) o quemadura por inhalación de vía aérea.",
        "keywords": ["politraumatismo", "gran quemado", "quemadura todo el cuerpo", "quemadura via aerea", "trauma toracico penetrante", "herida por arma de fuego"]
    },
    {
        "id": "c1_hypothermia_extreme",
        "level": 1,
        "name": "Reanimación",
        "category": "ambiental",
        "criterion": "Hipotermia extrema (< 32°C) o golpe de calor extremo con alteración del estado de conciencia y colapso vital.",
        "keywords": ["hipotermia severa", "temperatura menor de 32", "golpe de calor severo", "colapso termico"]
    },
    {
        "id": "c1_sexual_abuse_acute",
        "level": 1,
        "name": "Reanimación",
        "category": "legal_urgencia",
        "criterion": "Víctima de violencia o abuso sexual con evento ocurrido en un período menor a 72 horas (Código Blanco / profilaxis PEP inmediata).",
        "keywords": ["abuso sexual menor a 72 horas", "violencia sexual reciente", "codigo blanco", "agresion sexual menor de 72 horas"]
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
        "keywords": ["dolor de pecho", "dolor toracico", "opresion en el pecho", "infarto", "angina", "irradiado al brazo", "irradiado a la mandibula", "diaforesis", "dolor precordial"]
    },
    {
        "id": "c2_stroke_acv",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Sospecha de Accidente Cerebrovascular (ACV/Ictus) agudo: asimetría facial, pérdida de fuerza en hemicuerpo, afasia o disartria aguda en ventana terapéutica.",
        "keywords": ["acv", "accidente cerebrovascular", "derrame cerebral", "ictus", "asimetria facial", "boca torcida", "hemiparesia", "perdida de fuerza en brazo", "disartria", "afasia"]
    },
    {
        "id": "c2_thunderclap_headache",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Cefalea súbita de máxima intensidad ('en estallido' o en trueno), sospecha de hemorragia subaracnoidea o signos meníngeos agudos.",
        "keywords": ["cefalea en trueno", "cefalea en estallido", "la peor cefalea de la vida", "dolor de cabeza subito insoportable", "rigidez de nuca"]
    },
    {
        "id": "c2_hypertensive_crisis",
        "level": 2,
        "name": "Emergencia",
        "category": "cardiovascular",
        "criterion": "Crisis hipertensiva con cifras sistólicas >= 180 mmHg o diastólicas >= 110 mmHg con o sin compromiso de órgano diana.",
        "keywords": ["crisis hipertensiva", "presion muy alta", "tension 180", "tension 200", "emergencia hipertensiva", "encefalopatia hipertensiva"]
    },
    {
        "id": "c2_seizures",
        "level": 2,
        "name": "Emergencia",
        "category": "neurologico",
        "criterion": "Estado convulsivo reciente o crisis epilépticas repetitivas con período postictal prolongado o alteración neurológica persistente.",
        "keywords": ["convulsion", "convulsionando", "estado convulsivo", "crisis epileptica", "ataque de epilepsia", "postictal prolongado"]
    },
    {
        "id": "c2_resp_moderate",
        "level": 2,
        "name": "Emergencia",
        "category": "respiratorio",
        "criterion": "Dificultad respiratoria moderada-severa, desaturación SpO2 < 90%, taquipnea marcada (FR > 28 rpm) o uso de músculos accesorios/tirajes.",
        "keywords": ["dificultad respiratoria moderada", "saturacion menor a 90", "tirajes", "disnea moderada", "fatiga respiratoria", "tirajes intercostales", "aleteo nasal"]
    },
    {
        "id": "c2_diabetes_decompensation",
        "level": 2,
        "name": "Emergencia",
        "category": "metabolico",
        "criterion": "Diabetes descompensada aguda, cetoacidosis diabética, estado hiperosmolar (glucemia > 350 mg/dL) o hipoglucemia severa (< 50 mg/dL) con neuroglucopenia.",
        "keywords": ["diabetes descompensada", "diabetes", "diabetico", "diabetica", "cetoacidosis", "coma diabetico", "azucar por las nubes", "azucar alta", "hiperglucemia", "azucar 400", "azucar 500", "hipoglucemia severa", "glucemia menor de 50", "respiracion de kussmaul"]
    },
    {
        "id": "c2_acute_abdomen",
        "level": 2,
        "name": "Emergencia",
        "category": "digestivo",
        "criterion": "Abdomen agudo quirúrgico sospechado, signos de irritación peritoneal, defensa muscular involuntaria o dolor abdominal intolerable con hipotensión.",
        "keywords": ["abdomen agudo", "irritacion peritoneal", "vientre en tabla", "peritonitis", "defensa muscular", "apendicitis complicada", "abdomen perforado"]
    },
    {
        "id": "c2_gastro_bleeding_high",
        "level": 2,
        "name": "Emergencia",
        "category": "digestivo",
        "criterion": "Hemorragia digestiva alta activa manifestada por hematemesis o melenas abundantes con taquicardia o hipotensión ortostática.",
        "keywords": ["hematemesis", "vomito con sangre", "melenas abundantes", "hemorragia digestiva alta", "sangrado digestivo activo"]
    },
    {
        "id": "c2_open_fracture_burn",
        "level": 2,
        "name": "Emergencia",
        "category": "trauma",
        "criterion": "Fractura expuesta con hueso visible, luxofractura con compromiso de pulsos distales, síndrome compartimental o quemadura de III grado profunda.",
        "keywords": ["fractura expuesta", "hueso afuera", "hueso visible", "quemadura de tercer grado", "quemadura grado 3", "sindrome compartimental", "falta de pulso distal"]
    },
    {
        "id": "c2_toxic_ingestion",
        "level": 2,
        "name": "Emergencia",
        "category": "toxicologico",
        "criterion": "Ingestión de sustancias tóxicas, cáusticos, plaguicidas, sobredosis medicamentosa o envenenamiento por mordedura de serpiente/escorpión.",
        "keywords": ["intoxicacion", "veneno", "envenenamiento", "ingestion toxico", "sobredosis", "plaguicida", "mordedura de serpiente", "acido ingerido", "caustico"]
    },
    {
        "id": "c2_pregnancy_bleeding_preeclampsia",
        "level": 2,
        "name": "Emergencia",
        "category": "obstetrico",
        "criterion": "Sangrado vaginal agudo en paciente embarazada, sospecha de desprendimiento de placenta, embarazo ectópico o preeclampsia severa con cefalea y fosfenos.",
        "keywords": ["sangrado embarazada", "embarazada sangrando", "metrorragia", "perdida de sangre en embarazo", "preeclampsia severa", "embarazo ectopico", "dolor de cabeza en embarazo"]
    },
    {
        "id": "c2_sepsis_qsofa",
        "level": 2,
        "name": "Emergencia",
        "category": "infeccioso",
        "criterion": "Sospecha de sepsis con criterios qSOFA >= 2: alteración del sensorio, FR >= 22 rpm y PAS <= 100 mmHg con foco infeccioso evidente.",
        "keywords": ["sepsis", "choque septico inminente", "infeccion con presion baja", "qsofa", "bacteremia con taquipnea e hipotension"]
    },
    {
        "id": "c2_ocular_chemical_trauma",
        "level": 2,
        "name": "Emergencia",
        "category": "oftalmologico",
        "criterion": "Quemadura química ocular por ácidos o álcalis, trauma ocular penetrante con pérdida de líquido intraocular o pérdida súbita total de visión.",
        "keywords": ["quemadura quimica en ojo", "quimico en el ojo", "trauma ocular penetrante", "ojo perforado", "ceguera subita"]
    },
    {
        "id": "c2_testicular_torsion",
        "level": 2,
        "name": "Emergencia",
        "category": "urologico",
        "criterion": "Dolor escrotal agudo intenso de inicio súbito (< 6 horas), sospecha de torsión testicular o priapismo isquémico agudo.",
        "keywords": ["torsion testicular", "dolor testicular subito", "testiculo hinchado y adolorido", "priapismo"]
    },
    {
        "id": "c2_psychiatric_agitation_suicide",
        "level": 2,
        "name": "Emergencia",
        "category": "salud_mental",
        "criterion": "Agitación psicomotora severa con riesgo inminente de auto/heteroagresión o intento suicida reciente activo con ideación estructurada.",
        "keywords": ["agitacion psicomotora", "intento de suicidio", "intento suicida", "ideacion suicida estructurada", "agresion incontrolable", "psicosis aguda"]
    },
    {
        "id": "c2_febrile_infant_young",
        "level": 2,
        "name": "Emergencia",
        "category": "pediatrico",
        "criterion": "Lactante menor de 3 meses (< 90 días) con fiebre (> 38.0°C), rechazo alimentario, letargia o irritabilidad inconsolable.",
        "keywords": ["bebe menor de 3 meses con fiebre", "lactante febril", "recien nacido con fiebre", "bebe que no despierta y con fiebre"]
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
        "keywords": ["dificultad respiratoria leve", "silbido pecho", "sibilancia", "disnea leve", "asma leve", "saturacion 92", "saturacion 93"]
    },
    {
        "id": "c3_gastro_dehydration",
        "level": 3,
        "name": "Urgencia",
        "category": "digestivo",
        "criterion": "Vómito y diarrea con signos clínicos de deshidratación moderada o intolerancia a la vía oral que requiere rehidratación endovenosa.",
        "keywords": ["vomito y diarrea", "deshidratacion", "no tolera suero", "intolerancia via oral", "diarrea abundante", "deshidratacion moderada"]
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
        "keywords": ["reaccion alergica", "alergia con brote", "urticaria", "ronchas en el cuerpo", "picazon generalizada", "habones generalizados"]
    },
    {
        "id": "c3_burn_grade_2",
        "level": 3,
        "name": "Urgencia",
        "category": "trauma",
        "criterion": "Quemadura de II grado localizada con flictenas o ampollas en área menor al 10% corporal en zonas no especiales.",
        "keywords": ["quemadura de segundo grado", "quemadura grado 2", "ampollas por quemadura", "flictenas"]
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

    # =========================================================================
    # --- NIVEL 4: CONSULTA PRIORITARIA (ATENCION SUBAGUDA / 24 HORAS) ---
    # =========================================================================
    {
        "id": "c4_upper_respiratory",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "respiratorio_infeccioso",
        "criterion": "Cuadro respiratorio alto: tos, congestión nasal, odinofagia, faringitis o amigdalitis sin dificultad respiratoria ni desaturación.",
        "keywords": ["tos y congestion", "gripe", "resfriado", "dolor de garganta", "amigdalitis", "faringitis", "rinorrea", "catarro", "congestion"]
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
        "keywords": ["ardor al orinar", "chistata", "infeccion urinaria", "disuria", "dolor para orinar", "cistitis simple"]
    },
    {
        "id": "c4_subacute_pain",
        "level": 4,
        "name": "Consulta Prioritaria",
        "category": "dolor_general",
        "criterion": "Dolor leve a moderado de más de 24 horas de evolución, trauma superficial menor, raspaduras o herida sin hemorragia activa.",
        "keywords": ["dolor de varios dias", "dolor mas de 24 horas", "trauma leve", "raspada", "golpe leve", "escoriacion"]
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
        "keywords": ["conjuntivitis", "ojo rojo con lagañas", "infeccion en el ojo simple", "picazon en ojos"]
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
    # --- NIVEL 5: CONSULTA EXTERNA (DIRECCIONAMIENTO A EPS / TRÁMITES) ---
    # =========================================================================
    {
        "id": "c5_chronic_headache",
        "level": 5,
        "name": "Consulta Externa",
        "category": "cronico",
        "criterion": "Dolor de cabeza crónico de meses o años de evolución con características habituales y sin signos de alarma.",
        "keywords": ["dolor de cabeza cronico", "migrana de anos", "cefalea cronica habitual", "dolor de cabeza de siempre", "migraña de toda la vida"]
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
        "keywords": ["formulacion de medicamentos", "receta medica", "renovacion formula", "lectura de examenes", "resultados de laboratorio", "pedir medicamentos", "renovar orden"]
    },
    {
        "id": "c5_dermatology_subacute",
        "level": 5,
        "name": "Consulta Externa",
        "category": "dermatologia",
        "criterion": "Lesiones de piel crónicas o subagudas: dermatitis de contacto, eccema antiguo, acné o micosis cutánea sin sobreinfección sistémica.",
        "keywords": ["dermatitis", "alergia en la piel cronica", "hongos en las unas", "eccema", "granos antiguos", "acne", "manchas en la piel"]
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


class ClinicalKnowledgeRAG:
    """
    Motor RAG semantico y ontologico para triaje medico hospitalario.
    Recupera los criterios institucionales Christus Sinergia mas pertinentes
    para el cuadro clinico del paciente con maxima densidad informativa y minimo consumo de tokens.
    """

    @classmethod
    def _expand_query_synonyms(cls, query_norm: str) -> str:
        """Anade el termino clinico de cada coloquialismo o sigla del catalogo terminologico."""
        terms = [fold(match.concept.term) for match in find_concepts(query_norm)]
        return " ".join([query_norm, *terms])

    @classmethod
    def _compute_relevance(cls, query_norm: str, criterion: Dict[str, Any]) -> float:
        """Calcula el puntaje de relevancia hibrida lexico-semantica."""
        score = 0.0

        # Coincidencia con palabras clave y expresiones multipalabra
        for kw in criterion["keywords"]:
            kw_norm = _normalize_text(kw)
            if kw_norm in query_norm:
                # Mayor peso a coincidencias multipalabra
                score += 3.5 if " " in kw_norm else 1.8

        # Coincidencia lexica sobre el criterio descriptivo
        crit_tokens = set(_normalize_text(criterion["criterion"]).split())
        query_tokens = set(query_norm.split())
        overlap = crit_tokens.intersection(query_tokens)
        score += len(overlap) * 0.45

        return score

    @classmethod
    def retrieve(cls, transcript: str, top_k: int = 4, red_flags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recupera los top-K criterios institucionales mas pertinentes para el cuadro clinico.
        Garantiza inclusion de criterios diferenciales relevantes (ej. Triage 1 y 2 si hay red flags).
        """
        # Los hallazgos negados no deben recuperar criterios: "niega dolor toracico" no es un SCA.
        base_norm = strip_negated(_normalize_text(transcript))
        query_norm = cls._expand_query_synonyms(base_norm)
        scored_criteria = []

        for item in CLINICAL_KNOWLEDGE_BASE:
            rel = cls._compute_relevance(query_norm, item)
            # Boost por banderas rojas clinicas
            if red_flags and item["level"] in [1, 2]:
                rel += 2.5
            if rel > 0:
                scored_criteria.append((rel, item))

        scored_criteria.sort(key=lambda x: x[0], reverse=True)
        retrieved = [item for _, item in scored_criteria[:top_k]]

        # Si no hubo coincidencias especificas, proveer un marco contextual sintetico
        if not retrieved:
            fallback_ids = ["c1_resp_failure_extreme", "c2_chest_pain_sca", "c4_upper_respiratory", "c5_administrative_routine"]
            id_map = {item["id"]: item for item in CLINICAL_KNOWLEDGE_BASE}
            retrieved = [id_map[fid] for fid in fallback_ids if fid in id_map]

        return retrieved

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
