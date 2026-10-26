"""
Indexa la base de conocimiento institucional del RAG clinico en PostgreSQL (pgvector)
y permite verificar consultas de similitud coseno e hibridas (BM25 + pgvector).

    python manage.py index_clinical_rag
    python manage.py index_clinical_rag --provider ollama --model nomic-embed-text
    python manage.py index_clinical_rag --query "Embarazada de 39 semanas, se le ve la cabeza del bebe y esta pujando"
"""
from django.core.management.base import BaseCommand, CommandError

from triage.clinical_rag import ClinicalKnowledgeRAG


class Command(BaseCommand):
    help = "Indexa los criterios clinicos de Christus Sinergia en PostgreSQL pgvector."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            choices=("hashed_ngram", "ollama", "gemini"),
            default="hashed_ngram",
            help="Proveedor de embeddings para poblar pgvector.",
        )
        parser.add_argument("--model", default=None, help="Modelo de embeddings opcional para ollama o gemini.")
        parser.add_argument("--query", default=None, help="Consulta opcional de verificacion tras indexar.")
        parser.add_argument("--top-k", type=int, default=4)

    def handle(self, *args, **options):
        try:
            stats = ClinicalKnowledgeRAG.index_pgvector(provider=options["provider"], model=options["model"])
        except Exception as err:
            raise CommandError(str(err)) from err

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexados {stats['indexed']} criterios en {stats['table']} "
                f"(proveedor={stats['provider']}, dim={stats['dim']})."
            )
        )
        if options.get("query"):
            vec_hits = ClinicalKnowledgeRAG.pgvector_search(options["query"], top_k=options["top_k"])
            hybrid = ClinicalKnowledgeRAG.retrieve(options["query"], top_k=options["top_k"])
            self.stdout.write(f"Consulta: {options['query']}")
            for item in hybrid:
                v_sim = vec_hits.get(item["id"], 0.0)
                self.stdout.write(
                    f"  [{item['level']}] {item['id']} (pgvector_cos={v_sim:.3f}): {item['criterion']}"
                )
