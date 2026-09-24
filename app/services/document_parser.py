import os
import csv
import io
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import UploadFile, HTTPException

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"
}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def get_upload_dir() -> Path:
    base_dir = Path(__file__).resolve().parents[2]
    upload_dir = base_dir / "data" / "business_documents"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def sanitize_filename(filename: str) -> str:
    # Extract only the base filename to prevent path traversal
    base = os.path.basename(filename).replace("\\", "/").split("/")[-1]
    # Remove any relative directory traversal dots
    cleaned = re.sub(r"\.\.+", "_", base)
    # Keep alphanumeric, dot, underscore, hyphen
    cleaned = re.sub(r"[^\w\.\- ]", "_", cleaned)
    return cleaned.strip() or "unnamed_document.txt"


def extract_text_from_txt(file_bytes: bytes) -> str:
    for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    stream = io.BytesIO(file_bytes)
    reader = PdfReader(stream)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages_text.append(f"--- Page {idx + 1} ---\n" + text.strip())
    return "\n\n".join(pages_text)


def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx
    stream = io.BytesIO(file_bytes)
    doc = docx.Document(stream)
    lines = []
    for p in doc.paragraphs:
        if p.text.strip():
            lines.append(p.text.strip())
    
    # Also extract tables
    for table in doc.tables:
        lines.append("\n[Table]")
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                lines.append(" | ".join(row_cells))
        lines.append("[End Table]\n")

    return "\n".join(lines)


def extract_text_from_csv(file_bytes: bytes) -> str:
    text_content = extract_text_from_txt(file_bytes)
    reader = csv.reader(io.StringIO(text_content))
    lines = []
    for row in reader:
        filtered = [col.strip() for col in row if col.strip()]
        if filtered:
            lines.append(" | ".join(filtered))
    return "\n".join(lines)


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    import openpyxl
    stream = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(stream, data_only=True)
    lines = []
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        lines.append(f"\n--- Sheet: {sheet_name} ---")
        for row in sheet.iter_rows(values_only=True):
            row_vals = [str(val).strip() for val in row if val is not None and str(val).strip()]
            if row_vals:
                lines.append(" | ".join(row_vals))
    return "\n".join(lines)


def extract_text_from_image(file_bytes: bytes, filename: str) -> str:
    # Basic image metadata / OCR placeholder
    try:
        from PIL import Image
        stream = io.BytesIO(file_bytes)
        img = Image.open(stream)
        w, h = img.size
        format_name = img.format
        return f"[Image File: {filename}, Dimensions: {w}x{h}, Format: {format_name}. Uploaded business promotional/menu image.]"
    except Exception:
        return f"[Image File: {filename}]"


def parse_and_save_uploaded_file(
    file_bytes: bytes,
    original_filename: str,
    owner_id: int,
    business_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Validates, securely stores, and extracts readable text from an uploaded document.
    Enforces format, file size, empty file checks, and captures extraction failures gracefully.
    """
    clean_name = sanitize_filename(original_filename)
    suffix = Path(clean_name).suffix.lower()

    if not suffix or suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Supported formats: PDF, DOCX, TXT, CSV, XLSX."
        )

    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"File '{clean_name}' is empty (0 bytes). Uploaded document must contain readable content."
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of 15MB (File size: {file_size / (1024*1024):.1f}MB)"
        )

    upload_dir = get_upload_dir()
    # Secure storage naming associated with business/tenant and owner
    import time
    timestamp = int(time.time() * 1000)
    biz_prefix = f"biz_{business_id}_" if business_id else ""
    saved_filename = f"{biz_prefix}owner_{owner_id}_{timestamp}_{clean_name}"
    saved_path = upload_dir / saved_filename

    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Extract text based on file type
    extracted_text = ""
    error_msg = None
    status = "processed"

    try:
        if suffix == ".pdf":
            extracted_text = extract_text_from_pdf(file_bytes)
        elif suffix in [".docx", ".doc"]:
            extracted_text = extract_text_from_docx(file_bytes)
        elif suffix == ".txt":
            extracted_text = extract_text_from_txt(file_bytes)
        elif suffix == ".csv":
            extracted_text = extract_text_from_csv(file_bytes)
        elif suffix in [".xlsx", ".xls"]:
            extracted_text = extract_text_from_xlsx(file_bytes)
        elif suffix in [".png", ".jpg", ".jpeg"]:
            extracted_text = extract_text_from_image(file_bytes, clean_name)
        else:
            extracted_text = extract_text_from_txt(file_bytes)
    except Exception as e:
        status = "failed"
        error_msg = f"Failed to extract readable content: {str(e)}"
        extracted_text = ""

    return {
        "original_filename": clean_name,
        "file_type": suffix.lstrip("."),
        "file_path": str(saved_path),
        "file_size": file_size,
        "extracted_text": (extracted_text or "").strip(),
        "processing_status": status,
        "error_message": error_msg
    }
