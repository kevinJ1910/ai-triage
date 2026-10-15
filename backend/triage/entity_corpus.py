"""
Corpus de evaluacion de entidades clinicas (benchmark/corpus_entidades.json).

Cada caso extiende el formato de casos_sinteticos.json (id, transcript, reference_level, tipo,
criterio), asi que evaluate_benchmark tambien lo acepta, y anade las entidades anotadas y la
particion dev/test. Las reglas de anotacion estan en benchmark/README.md.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

CORPUS_PATH = Path(__file__).resolve().parent / 'benchmark' / 'corpus_entidades.json'

# Mismas claves que EntitiesSchema del analizador, mas diagnoses y allergies (objetivo 5).
ENTITY_TYPES = ('symptoms', 'diagnoses', 'medications', 'allergies', 'vitals', 'history')
TIPOS = ('tipico', 'coloquial', 'negacion', 'signos_vitales')
SPLITS = ('dev', 'test')
ANNOTATION_STATES = ('borrador', 'revisado')

# Fraccion de cada nivel que va a test. La particion se deriva del id (no se elige a mano):
# asi no depende de que casos resultan faciles o dificiles para algun motor.
TEST_FRACTION = 0.4


def assign_splits(case_ids_by_level: Dict[int, List[str]]) -> Dict[str, str]:
    """Particion estratificada por nivel: ordena los ids por su SHA-256 y envia a test el primer 40 %."""
    splits = {}
    for ids in case_ids_by_level.values():
        ordered = sorted(ids, key=lambda cid: hashlib.sha256(cid.encode('utf-8')).hexdigest())
        n_test = round(len(ordered) * TEST_FRACTION)
        for position, cid in enumerate(ordered):
            splits[cid] = 'test' if position < n_test else 'dev'
    return splits


def double_annotation_sample(cases: List[Dict[str, Any]], per_level: int = 6) -> List[str]:
    """Ids que un segundo anotador etiqueta a ciegas para medir el acuerdo entre anotadores."""
    by_level = defaultdict(list)
    for case in cases:
        by_level[case['reference_level']].append(case['id'])
    sample = []
    for level in sorted(by_level):
        ordered = sorted(by_level[level], key=lambda cid: hashlib.sha256(f'doble:{cid}'.encode('utf-8')).hexdigest())
        sample.extend(ordered[:per_level])
    return sample


def blank_annotation_template(cases: List[Dict[str, Any]], ids: List[str]) -> List[Dict[str, Any]]:
    """Casos sin entidades ni nivel, para que el segundo anotador no vea la primera anotacion."""
    by_id = {c['id']: c for c in cases}
    return [
        {'id': cid, 'transcript': by_id[cid]['transcript'], 'entities': {etype: [] for etype in ENTITY_TYPES}}
        for cid in ids
    ]


def validate_entity_corpus(cases: List[Dict[str, Any]]) -> List[str]:
    """Devuelve la lista de errores del corpus; vacia si es valido."""
    errors = []
    seen = set()
    by_level = defaultdict(list)

    for index, case in enumerate(cases, start=1):
        cid = case.get('id') or f'#{index}'
        if cid in seen:
            errors.append(f'{cid}: id duplicado')
        seen.add(cid)

        transcript = case.get('transcript') or ''
        if not transcript.strip():
            errors.append(f'{cid}: transcript vacio')
        level = case.get('reference_level')
        if level not in range(1, 6):
            errors.append(f'{cid}: reference_level debe estar entre 1 y 5')
        else:
            by_level[level].append(cid)
        if case.get('tipo') not in TIPOS:
            errors.append(f'{cid}: tipo invalido {case.get("tipo")!r}')
        if not (case.get('criterio') or '').strip():
            errors.append(f'{cid}: falta criterio')
        if case.get('split') not in SPLITS:
            errors.append(f'{cid}: split invalido {case.get("split")!r}')
        if case.get('estado') not in ANNOTATION_STATES:
            errors.append(f'{cid}: estado invalido {case.get("estado")!r}')

        entities = case.get('entities')
        if not isinstance(entities, dict) or set(entities) != set(ENTITY_TYPES):
            errors.append(f'{cid}: entities debe tener exactamente las claves {ENTITY_TYPES}')
            continue
        for etype, items in entities.items():
            for item in items:
                text = item.get('text') or ''
                # El span debe aparecer tal cual: permite calcular offsets para el NER (BIO).
                if not text or text not in transcript:
                    errors.append(f'{cid}: {etype} {text!r} no aparece en el transcript')
                if not (item.get('normalized') or '').strip():
                    errors.append(f'{cid}: {etype} {text!r} sin forma normalizada')
                if not isinstance(item.get('negated'), bool):
                    errors.append(f'{cid}: {etype} {text!r} sin negated booleano')
                if 'cie10' not in item:
                    errors.append(f'{cid}: {etype} {text!r} sin campo cie10')

    expected = assign_splits(by_level)
    for case in cases:
        cid = case.get('id')
        if cid in expected and case.get('split') != expected[cid]:
            errors.append(f'{cid}: split {case.get("split")!r} no coincide con la regla ({expected[cid]!r})')
    return errors


def load_entity_corpus(path: Optional[Path] = None, split: Optional[str] = None) -> List[Dict[str, Any]]:
    """Carga y valida el corpus; con split devuelve solo los casos de esa particion."""
    path = Path(path or CORPUS_PATH)
    cases = json.loads(path.read_text(encoding='utf-8'))
    errors = validate_entity_corpus(cases)
    if errors:
        raise ValueError('Corpus de entidades invalido:\n' + '\n'.join(errors))
    if split is not None:
        if split not in SPLITS:
            raise ValueError(f'split debe ser uno de {SPLITS}')
        cases = [c for c in cases if c['split'] == split]
    return cases
