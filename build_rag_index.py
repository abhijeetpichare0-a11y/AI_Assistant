from pathlib import Path

from app.rag.document_loader import load_documents
from app.rag.embeddings import EmbeddingModel
from app.rag.vector_store import VectorStore


BASE_DIR = Path(__file__).resolve().parent

KNOWLEDGE_BASE_PATH = (
    BASE_DIR / "app" / "knowledge_base"
)

VECTOR_DB_PATH = (
    BASE_DIR / "data" / "vector_db"
)


def main():

    print("=" * 60)
    print("RAG INDEX BUILDING")
    print("=" * 60)

    # ----------------------------------------
    # Load documents
    # ----------------------------------------

    print("\nLoading knowledge-base documents...")

    documents = load_documents(
        str(KNOWLEDGE_BASE_PATH)
    )

    if not documents:
        print(
            "ERROR: No documents found in knowledge base."
        )
        return

    print(
        f"Loaded {len(documents)} documents."
    )

    for document in documents:

        print(
            f"  - {document['source']}"
        )

    # ----------------------------------------
    # Create embeddings
    # ----------------------------------------

    print("\nCreating embeddings...")

    embedding_model = EmbeddingModel()

    texts = [
        document["text"]
        for document in documents
    ]

    embeddings = embedding_model.encode(
        texts
    )

    print(
        f"Generated embeddings with shape: {embeddings.shape}"
    )

    # ----------------------------------------
    # Build FAISS index
    # ----------------------------------------

    print("\nBuilding FAISS vector index...")

    vector_store = VectorStore(
        str(VECTOR_DB_PATH)
    )

    vector_store.build(
        embeddings,
        documents
    )

    # ----------------------------------------
    # Save index
    # ----------------------------------------

    print("\nSaving vector database...")

    vector_store.save()

    print("\n" + "=" * 60)
    print("RAG INDEX BUILD COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()