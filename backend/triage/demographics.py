"""
Sexo y grupo de edad de los casos del corpus, para el analisis descriptivo de sesgo (seccion 7.5 del anteproyecto).

El corpus no trae estos campos: se derivan del transcript con reglas y se guardan aparte, en
benchmark/demografia.json, para no tocar corpus_entidades.json (su particion y su validacion no cambian).
Cada entrada lleva fuente 'regex' hasta que alguien la revisa a mano y la cambia a 'revisado'.
Muchos relatos en primera persona no dicen el sexo ni la edad: se quedan como 'desconocido'.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .clinical_protocol import _normalize_text

DEMOGRAPHICS_PATH = Path(__file__).resolve().parent / 'benchmark' / 'demografia.json'

SEXES = ('femenino', 'masculino', 'desconocido')
AGE_GROUPS = ('pediatrico', 'adulto', 'mayor', 'desconocido')

_FEMALE = re.compile(
    r"\b(senora|mujer|nina|bebe nina|muchacha|joven embarazada|embarazada|gestante|esposa|mama|madre|hija|abuela|"
    r"senorita|paciente femenina|la paciente|una paciente|ella|la nina|la bebe|parto|semanas de embarazo)\b"
)
_MALE = re.compile(
    r"\b(senor|hombre|nino|muchacho|esposo|papa|padre|hijo|abuelo|el paciente|un paciente|paciente masculino|"
    r"el nino|el bebe|el joven|un joven|un senor|el senor)\b"
)
_AGE_YEARS = re.compile(r"\b(\d{1,3})\s*(?:anos|ano)\b")
_AGE_MONTHS = re.compile(r"\b(\d{1,2})\s*(?:meses|mes|dias de nacido|semanas de nacido)\b")
_PEDIATRIC = re.compile(r"\b(bebe|nino|nina|recien nacido|lactante|menor de edad|colegio|hijo de|hija de)\b")
_ELDERLY = re.compile(r"\b(abuelo|abuela|anciano|anciana|adulto mayor|tercera edad)\b")


def derive(transcript: str) -> Dict[str, Optional[Any]]:
    """Sexo, edad (si se dice) y grupo de edad derivados del texto. Ante pistas contradictorias: desconocido."""
    text = _normalize_text(transcript)
    female, male = bool(_FEMALE.search(text)), bool(_MALE.search(text))
    sex = 'femenino' if female and not male else 'masculino' if male and not female else 'desconocido'

    age = None
    years = _AGE_YEARS.search(text)
    if years:
        age = int(years.group(1))
    elif _AGE_MONTHS.search(text):
        age = 0
    if age is not None:
        group = 'pediatrico' if age < 18 else 'mayor' if age >= 65 else 'adulto'
    elif _PEDIATRIC.search(text):
        group = 'pediatrico'
    elif _ELDERLY.search(text):
        group = 'mayor'
    else:
        group = 'desconocido'
    return {'sexo': sex, 'edad': age, 'grupo_edad': group}


def derive_all(cases: List[Dict[str, Any]], previous: Optional[Dict[str, Dict[str, Any]]] = None
               ) -> Dict[str, Dict[str, Any]]:
    """Deriva todos los casos; las entradas ya revisadas a mano se conservan tal cual."""
    previous = previous or {}
    out = {}
    for case in cases:
        old = previous.get(case['id'])
        if old and old.get('fuente') == 'revisado':
            out[case['id']] = old
        else:
            out[case['id']] = {**derive(case['transcript']), 'fuente': 'regex'}
    return out


def load_demographics(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    path = Path(path or DEMOGRAPHICS_PATH)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else {}
