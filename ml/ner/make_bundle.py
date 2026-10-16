"""
Empaqueta lo que necesita el notebook (el repositorio es privado y Colab/Kaggle no lo pueden clonar sin token):

    python ml/ner/make_bundle.py        # -> ml/ner/output/ner_bundle.zip

Contiene ner_data.py, train_ner.py y el corpus propio. Subirlo en la celda 2 del notebook.
"""
import hashlib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FILES = {
    'ner_data.py': HERE / 'ner_data.py',
    'train_ner.py': HERE / 'train_ner.py',
    'corpus_entidades.json': ROOT / 'backend' / 'triage' / 'benchmark' / 'corpus_entidades.json',
}


def main() -> Path:
    target = HERE / 'output' / 'ner_bundle.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, path in FILES.items():
            bundle.write(path, name)
    corpus_sha = hashlib.sha256(FILES['corpus_entidades.json'].read_bytes()).hexdigest()[:12]
    print(f'{target} (corpus sha256 {corpus_sha})')
    return target


if __name__ == '__main__':
    main()
