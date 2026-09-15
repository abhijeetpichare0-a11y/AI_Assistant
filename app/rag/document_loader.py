from pathlib import Path
from typing import List, Dict


SUPPORTED_EXTENSIONS = {".txt", ".pdf"}


def load_documents(knowledge_base_path: str) -> List[Dict[str, str]]:
    """
    Load documents from the knowledge base directory.

    Supports:
    - TXT files
    - PDF files

    Returns:
        List of dictionaries containing:
        - source
        - text
    """

    from pypdf import PdfReader

    knowledge_base = Path(knowledge_base_path)

    if not knowledge_base.exists():
        raise FileNotFoundError(
            f"Knowledge base directory not found: {knowledge_base}"
        )

    documents = []

    for file_path in knowledge_base.rglob("*"):

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:

            # -----------------------------
            # TXT FILE
            # -----------------------------
            if file_path.suffix.lower() == ".txt":

                text = file_path.read_text(
                    encoding="utf-8"
                )

            # -----------------------------
            # PDF FILE
            # -----------------------------
            elif file_path.suffix.lower() == ".pdf":

                reader = PdfReader(str(file_path))

                pages = []

                for page in reader.pages:
                    page_text = page.extract_text()

                    if page_text:
                        pages.append(page_text)

                text = "\n".join(pages)

            else:
                continue

            text = text.strip()

            if not text:
                continue

            documents.append(
                {
                    "source": file_path.name,
                    "text": text,
                }
            )

        except Exception as e:

            print(
                f"Warning: Could not load {file_path.name}: {e}"
            )

    return documents