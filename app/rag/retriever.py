from app.rag.embeddings import EmbeddingModel
from app.rag.vector_store import VectorStore


class Retriever:

    def __init__(self, vector_db_path: str):

        self.embedding_model = EmbeddingModel()

        self.vector_store = VectorStore(
            vector_db_path
        )

        self.vector_store.load()

    def retrieve(
        self,
        query: str,
        top_k: int = 3
    ):

        query_embedding = self.embedding_model.encode(
            [query]
        )

        results = self.vector_store.search(
            query_embedding,
            top_k=top_k
        )

        return results