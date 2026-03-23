import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEmbeddings:
    def test_get_model(self):
        """Test that model can be loaded."""
        from src.embeddings import get_model

        model = get_model()
        assert model is not None

    def test_embed_returns_list(self):
        """Test that embed returns a list of floats."""
        from src.embeddings import embed

        result = embed("test text")
        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

    def test_embed_consistent(self):
        """Test that same text produces same embedding."""
        from src.embeddings import embed

        text = "consistent test"
        result1 = embed(text)
        result2 = embed(text)

        assert result1 == result2

    def test_embed_different_texts_different_vectors(self):
        """Test that different texts produce different embeddings."""
        from src.embeddings import embed

        result1 = embed("hello world")
        result2 = embed("goodbye moon")

        assert result1 != result2

    def test_embed_batch(self):
        """Test batch embedding."""
        from src.embeddings import embed_batch

        texts = ["text one", "text two", "text three"]
        results = embed_batch(texts)

        assert len(results) == 3
        for r in results:
            assert len(r) == 384

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        from src.embeddings import cosine_similarity

        vec = [0.5, 0.5, 0.5, 0.5]
        sim = cosine_similarity(vec, vec)

        assert abs(sim - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        from src.embeddings import cosine_similarity

        vec1 = [1.0, 0.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0, 0.0]
        sim = cosine_similarity(vec1, vec2)

        assert abs(sim) < 0.0001

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity of opposite vectors."""
        from src.embeddings import cosine_similarity

        vec1 = [1.0, 1.0, 1.0, 1.0]
        vec2 = [-1.0, -1.0, -1.0, -1.0]
        sim = cosine_similarity(vec1, vec2)

        assert abs(sim + 1.0) < 0.0001

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        from src.embeddings import cosine_similarity

        vec1 = [1.0, 1.0, 1.0, 1.0]
        vec2 = [0.0, 0.0, 0.0, 0.0]
        sim = cosine_similarity(vec1, vec2)

        assert sim == 0.0

    def test_warmup(self):
        """Test that warmup loads the model."""
        from src import embeddings

        embeddings._model = None
        embeddings.warmup()

        assert embeddings._model is not None
