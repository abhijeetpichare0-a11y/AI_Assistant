from pathlib import Path
import pickle

import faiss
import numpy as np


class VectorStore:

    def __init__(self, storage_path: str):

        self.storage_path = Path(storage_path)

        self.storage_path.mkdir(
            parents=True,
            exist_ok=True
        )

        self.index = None
        self.documents = []

    def build(self, embeddings, documents):

        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        if len(embeddings) == 0:
            raise ValueError(
                "No embeddings available to build vector index."
            )

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dimension)

        self.index.add(embeddings)

        self.documents = documents

        print(
            f"FAISS index created with {len(documents)} documents."
        )

    def save(self):

        if self.index is None:
            raise ValueError(
                "Vector index has not been created."
            )

        index_path = self.storage_path / "index.faiss"

        documents_path = self.storage_path / "documents.pkl"

        faiss.write_index(
            self.index,
            str(index_path)
        )

        with open(
            documents_path,
            "wb"
        ) as file:

            pickle.dump(
                self.documents,
                file
            )

        print(
            f"Vector index saved to: {self.storage_path}"
        )

    def load(self):

        index_path = self.storage_path / "index.faiss"

        documents_path = self.storage_path / "documents.pkl"

        if not index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {index_path}"
            )

        if not documents_path.exists():
            raise FileNotFoundError(
                f"Document metadata not found: {documents_path}"
            )

        self.index = faiss.read_index(
            str(index_path)
        )

        with open(
            documents_path,
            "rb"
        ) as file:

            self.documents = pickle.load(file)

        print(
            f"Vector index loaded with {len(self.documents)} documents."
        )

    def search(
        self,
        query_embedding,
        top_k=3
    ):

        if self.index is None:
            raise ValueError(
                "Vector index has not been loaded."
            )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(
                1,
                -1
            )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0]
        ):

            if index < 0:
                continue

            if index >= len(self.documents):
                continue

            result = {
                "score": float(score),
                "source": self.documents[index]["source"],
                "text": self.documents[index]["text"],
            }

            results.append(result)

        return results