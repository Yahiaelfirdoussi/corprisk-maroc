"""Policy retrieval (RAG) over the bank's internal policy documents.

Policies are split into sections ("## ..." headings) and indexed with TF-IDF,
which runs fully offline. To scale up, swap TfidfVectorizer for an embedding
model hosted inside the bank and a vector database (pgvector, Chroma, FAISS).
"""
import re
from dataclasses import dataclass
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import POLICY_DIR


@dataclass
class PolicyChunk:
    doc_id: str
    doc_title: str
    section: str
    text: str

    @property
    def ref(self) -> str:
        return f"{self.doc_id} §{self.section}"


def _load_chunks() -> list[PolicyChunk]:
    chunks = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title_m = re.search(r"^# (.+)$", raw, re.M)
        title = title_m.group(1).strip() if title_m else path.stem
        doc_id = title.split("—")[0].strip()
        for part in re.split(r"^## ", raw, flags=re.M)[1:]:
            heading, _, body = part.partition("\n")
            chunks.append(PolicyChunk(doc_id, title, heading.strip(), " ".join(body.split())))
    return chunks


class PolicyIndex:
    def __init__(self):
        self.chunks = _load_chunks()
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([f"{c.section} {c.text}" for c in self.chunks])

    def search(self, query: str, doc_id: str | None = None, k: int = 1) -> list[tuple[PolicyChunk, float]]:
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        out = [(self.chunks[i], float(scores[i])) for i in ranked if doc_id is None or self.chunks[i].doc_id == doc_id]
        return out[:k]


@lru_cache
def get_index() -> PolicyIndex:
    return PolicyIndex()
