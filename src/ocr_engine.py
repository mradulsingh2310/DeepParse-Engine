"""
DeepSeek OCR Engine Module

Uses Ollama to run DeepSeek OCR locally for text extraction from images.
"""

import tempfile
from pathlib import Path

import ollama
from PIL import Image


def extract_text(
    images: list[Image.Image] | Image.Image,
    use_grounding: bool = False,
    model: str = "deepseek-ocr"
) -> str:
    """
    Extract text from image(s) using DeepSeek OCR via Ollama.

    Args:
        images: Single PIL Image or list of PIL Images
        use_grounding: Use grounding mode (preserves layout as markdown)
        model: Ollama model name

    Returns:
        Extracted text (concatenated with page breaks if multiple images)
    """
    # Normalize to list
    if isinstance(images, Image.Image):
        images = [images]

    prompt = "<|grounding|>Convert the document to markdown." if use_grounding else "Free OCR."

    results = []
    for i, img in enumerate(images):
        text = _process_single_image(img, prompt, model)
        results.append(f"[PAGE {i + 1}]\n{text}")

    return "\n\n".join(results)


def _process_single_image(image: Image.Image, prompt: str, model: str) -> str:
    """Process a single image through OCR."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name, format="PNG")
        tmp_path = tmp.name

    try:
        response = ollama.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [tmp_path]
            }]
        )
        return response["message"]["content"]
    finally:
        Path(tmp_path).unlink(missing_ok=True)
