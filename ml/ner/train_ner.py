"""
Entrenamiento y evaluacion del NER (token classification) sobre documentos de ner_data.py.
Lo usa el notebook finetune_roberta_ner.ipynb; tambien se puede ejecutar como prueba de humo en CPU:

    python ml/ner/train_ner.py --smoke

La prueba de humo usa el tokenizador real del modelo base y un RoBERTa diminuto con pesos aleatorios:
comprueba la alineacion de offsets, el entrenamiento y la decodificacion, no la calidad.
"""
import argparse
import inspect
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_data import (  # noqa: E402
    ID2LABEL, IGNORE_INDEX, LABEL2ID, LABELS, Document, Span, bio_labels, corpus_to_documents, span_prf,
    spans_from_bio,
)

BASE_MODEL = 'PlanTL-GOB-ES/roberta-base-biomedical-clinical-es'
BASE_MODEL_MIRROR = 'BSC-LT/roberta-base-biomedical-clinical-es'
MAX_LENGTH = 512
STRIDE = 128


def load_tokenizer(name: str = BASE_MODEL):
    from transformers import AutoTokenizer
    try:
        return AutoTokenizer.from_pretrained(name, use_fast=True)
    except OSError:
        return AutoTokenizer.from_pretrained(BASE_MODEL_MIRROR, use_fast=True)


def tokenize_documents(docs: Sequence[Document], tokenizer, max_length: int = MAX_LENGTH,
                       stride: int = STRIDE) -> List[dict]:
    """Ventanas solapadas de max_length tokens por documento, con etiquetas BIO por token."""
    features = []
    for doc in docs:
        encoded = tokenizer(doc.text, truncation=True, max_length=max_length, stride=stride,
                            return_overflowing_tokens=True, return_offsets_mapping=True)
        for window, offsets in enumerate(encoded['offset_mapping']):
            features.append({
                'input_ids': encoded['input_ids'][window],
                'attention_mask': encoded['attention_mask'][window],
                'labels': bio_labels(offsets, doc.spans),
                'doc_id': doc.doc_id,
                'window': window,
            })
    return features


def to_dataset(features: List[dict]):
    from datasets import Dataset
    return Dataset.from_list([{k: f[k] for k in ('input_ids', 'attention_mask', 'labels')} for f in features])


def token_entity_metrics(eval_prediction) -> Dict[str, float]:
    """
    P/R/F1 por entidad sobre las etiquetas de cada ventana (como seqeval en modo por defecto), solo para
    elegir el mejor checkpoint. La evaluacion que se reporta es por span de caracteres (evaluate).
    Sin dependencia de seqeval: en Colab su instalacion puede fallar en silencio.
    """
    logits, labels = eval_prediction
    predictions = np.argmax(logits, axis=-1)
    gold, predicted = {}, {}
    for row, (pred_row, label_row) in enumerate(zip(predictions, labels)):
        keep = [k for k, value in enumerate(label_row) if value != IGNORE_INDEX]
        positions = [(k, k + 1) for k in keep]
        gold[row] = spans_from_bio(positions, [int(label_row[k]) for k in keep])
        predicted[row] = spans_from_bio(positions, [int(pred_row[k]) for k in keep])
    micro = span_prf(gold, predicted)['micro']
    return {key: micro[key] or 0.0 for key in ('precision', 'recall', 'f1')}


# Nombre anterior, por compatibilidad con notebooks ya abiertos.
seqeval_metrics = token_entity_metrics


def new_model(name_or_path: str = BASE_MODEL, config=None):
    from transformers import AutoModelForTokenClassification
    if config is not None:
        return AutoModelForTokenClassification.from_config(config)
    try:
        return AutoModelForTokenClassification.from_pretrained(
            name_or_path, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID)
    except OSError:
        if name_or_path != BASE_MODEL:
            raise
        return AutoModelForTokenClassification.from_pretrained(
            BASE_MODEL_MIRROR, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID)


def train(model, tokenizer, train_docs: Sequence[Document], eval_docs: Optional[Sequence[Document]],
          output_dir: str, epochs: float = 3, learning_rate: float = 5e-5, batch_size: int = 16,
          seed: int = 42, max_length: int = MAX_LENGTH, stride: int = STRIDE, **extra):
    """Ajusta el modelo y devuelve el Trainer. Con eval_docs se guarda el mejor checkpoint por F1 por entidad."""
    import torch
    from transformers import DataCollatorForTokenClassification, Trainer, TrainingArguments, set_seed

    set_seed(seed)
    train_ds = to_dataset(tokenize_documents(train_docs, tokenizer, max_length, stride))
    eval_ds = to_dataset(tokenize_documents(eval_docs, tokenizer, max_length, stride)) if eval_docs else None
    # Calentamiento del 10 % de los pasos, en pasos enteros: transformers 5 elimino warmup_ratio.
    total_steps = math.ceil(len(train_ds) / batch_size) * math.ceil(epochs)
    options = dict(
        output_dir=output_dir,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        weight_decay=0.01,
        warmup_steps=max(1, int(0.1 * total_steps)),
        lr_scheduler_type='linear',
        eval_strategy='epoch' if eval_ds is not None else 'no',
        save_strategy='epoch' if eval_ds is not None else 'no',
        load_best_model_at_end=eval_ds is not None,
        metric_for_best_model='f1',
        save_total_limit=1,
        logging_steps=25,
        fp16=torch.cuda.is_available(),
        seed=seed,
        report_to='none',
        **extra,
    )
    accepted = inspect.signature(TrainingArguments.__init__).parameters
    if 'eval_strategy' not in accepted and 'evaluation_strategy' in accepted:  # transformers < 4.41
        options['evaluation_strategy'] = options.pop('eval_strategy')
    args = TrainingArguments(**{k: v for k, v in options.items() if k in accepted})
    trainer = Trainer(
        model=model, args=args, train_dataset=train_ds, eval_dataset=eval_ds,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=token_entity_metrics if eval_ds is not None else None,
    )
    trainer.train()
    return trainer


def predict_spans(model, tokenizer, docs: Sequence[Document], max_length: int = MAX_LENGTH,
                  stride: int = STRIDE, batch_size: int = 16) -> Dict[str, List[Span]]:
    """
    Spans predichos por documento. En los solapes entre ventanas se queda la prediccion del token mas
    alejado del borde de su ventana, donde el modelo tiene mas contexto.
    """
    import torch
    device = next(model.parameters()).device
    model.eval()
    result = {}
    for doc in docs:
        encoded = tokenizer(doc.text, truncation=True, max_length=max_length, stride=stride,
                            return_overflowing_tokens=True, return_offsets_mapping=True, padding=True,
                            return_tensors='pt')
        offsets_batch = encoded.pop('offset_mapping').tolist()
        encoded.pop('overflow_to_sample_mapping', None)
        with torch.no_grad():
            logits = torch.cat([
                model(**{k: v[i:i + batch_size].to(device) for k, v in encoded.items()}).logits.cpu()
                for i in range(0, encoded['input_ids'].shape[0], batch_size)
            ])
        best: Dict[tuple, tuple] = {}
        for window, offsets in enumerate(offsets_batch):
            predictions = logits[window].argmax(-1).tolist()
            real = [i for i, (s, e) in enumerate(offsets) if s != e]
            for rank, i in enumerate(real):
                margin = min(rank, len(real) - 1 - rank)
                key = tuple(offsets[i])
                if key not in best or margin > best[key][0]:
                    best[key] = (margin, predictions[i])
        ordered = sorted(best.items())
        result[doc.doc_id] = spans_from_bio([k for k, _ in ordered], [v[1] for _, v in ordered])
    return result


def evaluate(model, tokenizer, docs: Sequence[Document], **kwargs) -> Dict[str, Dict]:
    predicted = predict_spans(model, tokenizer, docs, **kwargs)
    return span_prf({d.doc_id: d.spans for d in docs}, predicted)


def _save_bpe_files(target: Path) -> None:
    """
    vocab.json y merges.txt del modelo base junto al modelo. transformers 5 solo guarda tokenizer.json, que
    tokenizers 0.19 (el del backend) no sabe leer; con estos dos ficheros el backend reconstruye el mismo
    tokenizador. El ajuste fino no cambia el vocabulario.
    """
    import shutil
    from huggingface_hub import hf_hub_download
    for name in ('vocab.json', 'merges.txt'):
        if (target / name).exists():
            continue
        for repo in (BASE_MODEL, BASE_MODEL_MIRROR):
            try:
                shutil.copy(hf_hub_download(repo, name), target / name)
                break
            except Exception:
                continue


def save_artifacts(trainer, tokenizer, output_dir: str, metrics: dict, training_config: dict) -> Path:
    """Modelo, tokenizador, etiquetas y metricas listos para backend/triage/ner_model.py (paso 3.2)."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(target))
    tokenizer.save_pretrained(str(target))
    _save_bpe_files(target)
    (target / 'ner_labels.json').write_text(json.dumps(LABELS, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'training_config.json').write_text(json.dumps(training_config, ensure_ascii=False, indent=2),
                                                 encoding='utf-8')
    return target


def smoke_test(corpus_path: Path, output_dir: Path) -> dict:
    from transformers import AutoConfig
    tokenizer = load_tokenizer()
    docs = corpus_to_documents(corpus_path, split='dev')[:12]
    # La alineacion debe reconstruir exactamente los spans anotados a partir de las etiquetas BIO.
    for doc in docs:
        for feature in tokenize_documents([doc], tokenizer):
            encoded = tokenizer(doc.text, return_offsets_mapping=True, truncation=True, max_length=MAX_LENGTH)
            rebuilt = spans_from_bio(encoded['offset_mapping'], feature['labels'])
            assert [(s.start, s.end, s.label) for s in rebuilt] == \
                   [(s.start, s.end, s.label) for s in doc.spans], doc.doc_id
    config = AutoConfig.from_pretrained(BASE_MODEL, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID,
                                        hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
                                        intermediate_size=64)
    model = new_model(config=config)
    trainer = train(model, tokenizer, docs[:8], docs[8:], str(output_dir / 'checkpoints'), epochs=1,
                    batch_size=4, max_length=128, stride=32)
    metrics = evaluate(trainer.model, tokenizer, docs[8:], max_length=128, stride=32)
    # Documento largo: varias ventanas solapadas, como en los casos clinicos de SPACCC.
    long_doc = Document('largo', ' '.join(d.text for d in docs), [])
    assert len(tokenize_documents([long_doc], tokenizer, max_length=128, stride=32)) > 1
    long_spans = predict_spans(trainer.model, tokenizer, [long_doc], max_length=128, stride=32)['largo']
    assert all(0 <= s.start < s.end <= len(long_doc.text) for s in long_spans)
    save_artifacts(trainer, tokenizer, str(output_dir / 'modelo'), {'smoke': metrics}, {'smoke': True})
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--smoke', action='store_true', help='Prueba de humo en CPU con un modelo diminuto.')
    parser.add_argument('--corpus', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'backend/triage/benchmark/corpus_entidades.json')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'output' / 'smoke')
    options = parser.parse_args()
    if not options.smoke:
        parser.error('El entrenamiento completo se ejecuta desde el notebook (finetune_roberta_ner.ipynb).')
    print(json.dumps(smoke_test(options.corpus, options.output), indent=2))
