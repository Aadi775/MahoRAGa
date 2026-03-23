import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class _FakeSentenceTransformer:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def encode(self, text, convert_to_numpy=True):
        if isinstance(text, str):
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            return rng.random(384, dtype=np.float32)
        vectors = []
        for item in text:
            rng = np.random.default_rng(abs(hash(item)) % (2**32))
            vectors.append(rng.random(384, dtype=np.float32))
        return np.stack(vectors)


@pytest.fixture
def patched_embeddings(monkeypatch):
    from src import embeddings

    embeddings._model = None
    monkeypatch.setattr(embeddings, "SentenceTransformer", _FakeSentenceTransformer)
    yield embeddings
    embeddings._model = None


class TestEmbeddings:
    def test_get_model(self, patched_embeddings):
        model = patched_embeddings.get_model()
        assert model is not None

    def test_embed_returns_list(self, patched_embeddings):
        result = patched_embeddings.embed("test text")
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

    def test_embed_consistent(self, patched_embeddings):
        text = "consistent test"
        result1 = patched_embeddings.embed(text)
        result2 = patched_embeddings.embed(text)
        assert result1 == result2

    def test_embed_different_texts_different_vectors(self, patched_embeddings):
        result1 = patched_embeddings.embed("hello world")
        result2 = patched_embeddings.embed("goodbye moon")
        assert result1 != result2

    def test_embed_batch(self, patched_embeddings):
        texts = ["text one", "text two", "text three"]
        results = patched_embeddings.embed_batch(texts)
        assert len(results) == 3
        for r in results:
            assert len(r) == 384

    def test_cosine_similarity_identical(self, patched_embeddings):
        vec = [0.5, 0.5, 0.5, 0.5]
        sim = patched_embeddings.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self, patched_embeddings):
        vec1 = [1.0, 0.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0, 0.0]
        sim = patched_embeddings.cosine_similarity(vec1, vec2)
        assert abs(sim) < 0.0001

    def test_cosine_similarity_opposite(self, patched_embeddings):
        vec1 = [1.0, 1.0, 1.0, 1.0]
        vec2 = [-1.0, -1.0, -1.0, -1.0]
        sim = patched_embeddings.cosine_similarity(vec1, vec2)
        assert abs(sim + 1.0) < 0.0001

    def test_cosine_similarity_zero_vector(self, patched_embeddings):
        vec1 = [1.0, 1.0, 1.0, 1.0]
        vec2 = [0.0, 0.0, 0.0, 0.0]
        sim = patched_embeddings.cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_warmup(self, patched_embeddings):
        patched_embeddings._model = None
        patched_embeddings.warmup()
        assert patched_embeddings._model is not None
