from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingModel:

    def __init__(self):
        print(f"Loading embedding model: {MODEL_NAME}")

        self.model = SentenceTransformer(MODEL_NAME)

        print("Embedding model loaded successfully.")

    def encode(self, texts):
        """
        Convert text into numerical vectors.
        """

        return self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )