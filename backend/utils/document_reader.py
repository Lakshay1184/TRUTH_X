"""truth.x — Document reader (PDF, DOCX, TXT)."""

from __future__ import annotations

import os
from typing import Optional

from backend.utils.logger import logger

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def read_document(file_path: str) -> str:
    """Read a document and return its text content.

    Supported formats: .pdf, .docx, .txt
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    logger.info("Reading document '%s' (format: %s)", file_path, ext)

    if ext == ".txt":
        return _read_txt(file_path)
    elif ext == ".pdf":
        return _read_pdf(file_path)
    elif ext == ".docx":
        return _read_docx(file_path)
    return ""


def detect_format(filename: str) -> Optional[str]:
    """Return the file extension if supported, else None."""
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in SUPPORTED_EXTENSIONS else None


def _read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    logger.info("TXT: extracted %d characters", len(text))
    return text


def _read_pdf(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise RuntimeError("PyPDF2 is required for PDF support. Install with: pip install PyPDF2")

    reader = PdfReader(path)
    pages = [page.extract_text() for page in reader.pages if page.extract_text()]
    text = "\n".join(pages)
    logger.info("PDF: extracted %d characters from %d pages", len(text), len(reader.pages))
    return text


def _read_docx(path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("python-docx is required for DOCX support. Install with: pip install python-docx")

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    logger.info("DOCX: extracted %d characters from %d paragraphs", len(text), len(paragraphs))
    return text
