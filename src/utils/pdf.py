"""
PDF to Image Conversion Utility.

Uses PyMuPDF (fitz) to convert PDF pages to PIL Images.
"""

import fitz  # type: ignore[import-untyped]  # PyMuPDF
from PIL import Image
from pathlib import Path


def pdf_to_images(
    pdf_path: str | Path, 
    dpi: int = 144,
    save_dir: str | Path | None = None
) -> list[Image.Image]:
    """
    Convert a PDF file to a list of PIL Images.

    Args:
        pdf_path: Path to the input PDF file
        dpi: Resolution for rendering (144 recommended for OCR)
        save_dir: Optional directory to save images (e.g., "img")

    Returns:
        List of PIL Image objects, one per page
        
    Example:
        # Get all pages
        images = pdf_to_images("doc.pdf")
        
        # Get single page (first page)
        first_page = pdf_to_images("doc.pdf")[0]
    """
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path_obj}")

    # Create save directory if specified
    save_dir_path: Path | None = None
    pdf_name: str = ""
    if save_dir:
        save_dir_path = Path(save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)
        pdf_name = pdf_path_obj.stem

    images = []
    zoom = dpi / 72.0  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(pdf_path_obj)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)

            if save_dir_path:
                img_path = save_dir_path / f"{pdf_name}_page_{page_num + 1}.png"
                img.save(img_path, format="PNG")
                print(f"Saved: {img_path}")
    finally:
        doc.close()

    return images
