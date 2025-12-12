"""
PDF to Image Conversion Module

Uses PyMuPDF (fitz) to convert PDF pages to PIL Images.
"""

import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path


def pdf_to_images(pdf_path: str, dpi: int = 144) -> list[Image.Image]:
    """
    Convert a PDF file to a list of PIL Images.

    Args:
        pdf_path: Path to the input PDF file
        dpi: Resolution for rendering (144 recommended for OCR)

    Returns:
        List of PIL Image objects, one per page
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images = []
    zoom = dpi / 72.0  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(pdf_path)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    finally:
        doc.close()

    return images


def pdf_to_image(pdf_path: str, page_num: int = 0, dpi: int = 144) -> Image.Image:
    """
    Convert a single page from a PDF to a PIL Image.

    Args:
        pdf_path: Path to the input PDF file
        page_num: Page number to convert (0-indexed)
        dpi: Resolution for rendering

    Returns:
        PIL Image object
    """
    images = pdf_to_images(pdf_path, dpi)
    if page_num >= len(images):
        raise IndexError(f"Page {page_num} not found. PDF has {len(images)} pages.")
    return images[page_num]
