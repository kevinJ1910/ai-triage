"""
Revision humana de las etiquetas del corpus (nivel de referencia, criterio y entidades) con una planilla.

export_rows genera la planilla de un split: transcript, nivel y criterio actuales y un resumen legible de las
entidades, mas columnas vacias para el revisor. Nunca incluye predicciones de ningun motor: la revision de test
debe hacerse sin ver resultados del sistema.

apply_review lleva la planilla al corpus:
- nivel_revisado distinto del actual: cambia reference_level y guarda el nivel original en nivel_particion, para
  que la particion dev/test (por hash dentro de cada lote y nivel) no mueva ningun caso.
- criterio_revisado: sustituye el criterio (obligatorio si cambia el nivel).
- entidades_ok = si: el caso pasa a estado 'revisado'. Con 'no' sigue en 'borrador' y se lista para corregir las
  entidades a mano en el JSON (spans exactos, ver README y GUIA_LIMITES.md).
Solo se aplican las filas con revisado_por. Funciones puras: los comandos leen y escriben los archivos.
"""
import csv
import io
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .entity_corpus import ENTITY_TYPES

COLUMNS = ('id', 'lote', 'tipo', 'transcript', 'nivel_actual', 'nombre_nivel', 'criterio_actual', 'entidades',
           'nivel_revisado', 'criterio_revisado', 'entidades_ok', 'comentario', 'revisado_por')
LEVEL_NAMES = {1: 'Reanimación', 2: 'Emergencia', 3: 'Urgencia', 4: 'Consulta Prioritaria', 5: 'Consulta Externa'}
ENTITY_LABELS = {'symptoms': 'Síntomas', 'diagnoses': 'Diagnósticos', 'medications': 'Medicamentos',
                 'allergies': 'Alergias', 'vitals': 'Signos vitales', 'history': 'Antecedentes'}
_YES = {'si', 'sí', 's', 'yes', 'y', 'x', 'ok'}
_NO = {'no', 'n'}


def entities_summary(entities: Dict[str, List[Dict[str, Any]]]) -> str:
    """'Síntomas: «no respira» → apnea; «dolor» → dolor (NEGADO) | Antecedentes: ...'"""
    parts = []
    for etype in ENTITY_TYPES:
        items = entities.get(etype) or []
        if not items:
            continue
        rendered = []
        for item in items:
            text = f"«{item['text']}» → {item['normalized']}"
            if item.get('cie10'):
                text += f" [{item['cie10']}]"
            if item.get('negated'):
                text += ' (NEGADO)'
            rendered.append(text)
        parts.append(f"{ENTITY_LABELS[etype]}: {'; '.join(rendered)}")
    return ' | '.join(parts) or '(sin entidades)'


def export_rows(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        'id': c['id'], 'lote': c.get('lote', 1), 'tipo': c['tipo'], 'transcript': c['transcript'],
        'nivel_actual': c['reference_level'], 'nombre_nivel': LEVEL_NAMES[c['reference_level']],
        'criterio_actual': c['criterio'], 'entidades': entities_summary(c['entities']),
        'nivel_revisado': '', 'criterio_revisado': '', 'entidades_ok': '', 'comentario': '', 'revisado_por': '',
    } for c in cases]


def to_csv(rows: List[Dict[str, Any]]) -> str:
    """CSV con ';' (Excel en español lo abre en columnas) y BOM para que muestre bien las tildes."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return '﻿' + buffer.getvalue()


def read_csv(text: str) -> List[Dict[str, str]]:
    """Lee la planilla con ';' o ',' (Excel y Google Sheets exportan uno u otro)."""
    text = text.lstrip('﻿')
    first_line = text.split('\n', 1)[0]
    delimiter = ';' if first_line.count(';') >= first_line.count(',') else ','
    return [{k.strip(): (v or '').strip() for k, v in row.items() if k}
            for row in csv.DictReader(io.StringIO(text), delimiter=delimiter)]


def _flag(value: str) -> Optional[bool]:
    value = value.strip().lower()
    if value in _YES:
        return True
    if value in _NO:
        return False
    return None


def apply_review(cases: List[Dict[str, Any]], rows: List[Dict[str, str]], today: Optional[str] = None
                 ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Devuelve (corpus actualizado, informe). Lanza ValueError con todos los errores si la planilla es invalida."""
    today = today or date.today().isoformat()
    by_id = {c['id']: dict(c) for c in cases}
    errors, level_changes, criterio_changes, reviewed, entity_fixes, skipped = [], [], [], [], [], []
    for number, row in enumerate(rows, start=2):
        cid = row.get('id', '')
        case = by_id.get(cid)
        if case is None:
            errors.append(f"fila {number}: id {cid!r} no esta en el corpus")
            continue
        if row.get('transcript') and row['transcript'] != case['transcript']:
            errors.append(f"fila {number} ({cid}): el transcript no coincide con el corpus (planilla desactualizada)")
            continue
        reviewer = row.get('revisado_por', '')
        if not reviewer:
            skipped.append(cid)
            continue
        new_level = row.get('nivel_revisado', '')
        new_criterio = row.get('criterio_revisado', '')
        if new_level:
            if new_level not in {'1', '2', '3', '4', '5'}:
                errors.append(f"fila {number} ({cid}): nivel_revisado debe ser 1-5, no {new_level!r}")
                continue
            if int(new_level) != case['reference_level']:
                if not new_criterio:
                    errors.append(f"fila {number} ({cid}): si cambia el nivel hay que escribir criterio_revisado")
                    continue
                level_changes.append((cid, case['reference_level'], int(new_level)))
                case.setdefault('nivel_particion', case['reference_level'])
                case['reference_level'] = int(new_level)
        if new_criterio and new_criterio != case['criterio']:
            criterio_changes.append(cid)
            case['criterio'] = new_criterio
        flag = _flag(row.get('entidades_ok', ''))
        if flag is None:
            errors.append(f"fila {number} ({cid}): entidades_ok debe ser si o no")
            continue
        case['revisado_por'] = reviewer
        case['revisado_el'] = today
        if row.get('comentario'):
            case['comentario_revision'] = row['comentario']
        if flag:
            case['estado'] = 'revisado'
            reviewed.append(cid)
        else:
            case['estado'] = 'borrador'
            entity_fixes.append((cid, row.get('comentario', '')))
        by_id[cid] = case
    if errors:
        raise ValueError('\n'.join(errors))
    updated = [by_id[c['id']] for c in cases]
    return updated, {'reviewed': reviewed, 'level_changes': level_changes, 'criterio_changes': criterio_changes,
                     'entity_fixes': entity_fixes, 'skipped': skipped}
