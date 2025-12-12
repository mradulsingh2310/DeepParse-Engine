"""
DeepSeek OCR Engine Module

Uses Ollama to run DeepSeek OCR locally for text extraction from images.
"""

import tempfile
from pathlib import Path

import httpx
import ollama
from PIL import Image

from .usage_logger import log, log_ollama_usage


class OCRError(Exception):
    """Base exception for OCR-related errors."""


class OCRConnectionError(OCRError):
    """Raised when unable to connect to Ollama."""


class OCRModelError(OCRError):
    """Raised when the OCR model is not available or fails."""


class OCRProcessingError(OCRError):
    """Raised when image processing fails."""


class OCRTimeoutError(OCRError):
    """Raised when OCR processing times out."""


# Default timeout in seconds per page (2 minutes)
DEFAULT_TIMEOUT = 300


def extract_text(
    images: list[Image.Image] | Image.Image,
    use_grounding: bool = False,
    model: str = "deepseek-ocr",
    timeout: float = DEFAULT_TIMEOUT
) -> str:
    """
    Extract text from image(s) using DeepSeek OCR via Ollama.

    Args:
        images: Single PIL Image or list of PIL Images
        use_grounding: Use grounding mode (preserves layout as markdown)
        model: Ollama model name
        timeout: Timeout in seconds per page (default 120s / 2 minutes)

    Returns:
        Extracted text (concatenated with page breaks if multiple images)

    Raises:
        OCRConnectionError: If unable to connect to Ollama
        OCRModelError: If the model is not available or fails
        OCRProcessingError: If image processing fails
        OCRTimeoutError: If OCR processing times out
    """
    log(f"Extracting text from images using {model} (timeout: {timeout}s per page)")

    try:
        # Normalize to list
        if isinstance(images, Image.Image):
            images = [images]

        if not images:
            raise OCRProcessingError("No images provided for OCR processing")

        prompt = "<|grounding|>Convert the document to markdown." if use_grounding else "Free OCR."

        results = []
        failed_pages = []
        total_pages = len(images)
        for i, img in enumerate(images):
            page_num = i + 1
            log(f"Processing page {page_num}/{total_pages}...")
            try:
                text = _process_single_image(img, prompt, model, page_num=page_num, timeout=timeout)
                log(f"Completed page {page_num}/{total_pages}")
                results.append(f"[PAGE {page_num}]\n{text}")
            except OCRTimeoutError:
                # If grounding was enabled and timed out, retry without grounding
                if use_grounding:
                    log(f"Timeout with grounding on page {page_num}, retrying without grounding...")
                    fallback_prompt = "Free OCR."
                    try:
                        text = _process_single_image(img, fallback_prompt, model, page_num=page_num, timeout=timeout)
                        log(f"Completed page {page_num}/{total_pages} (without grounding)")
                        results.append(f"[PAGE {page_num}]\n{text}")
                    except Exception as retry_e:
                        log(f"Failed page {page_num} after retry, skipping: {retry_e}")
                        failed_pages.append(page_num)
                        results.append(f"[PAGE {page_num}]\n[OCR FAILED: {retry_e}]")
                else:
                    # Already without grounding, skip this page
                    log(f"Timeout on page {page_num} without grounding, skipping")
                    failed_pages.append(page_num)
                    results.append(f"[PAGE {page_num}]\n[OCR FAILED: Timeout]")
            except Exception as e:
                log(f"Error processing page {page_num}, skipping: {e}")
                failed_pages.append(page_num)
                results.append(f"[PAGE {page_num}]\n[OCR FAILED: {e}]")

        if failed_pages:
            log(f"OCR completed with {len(failed_pages)} failed page(s): {failed_pages}")

        return "\n\n".join(results)

    except OCRError:
        # Re-raise our custom errors as-is
        raise
    except Exception as e:
        log(f"Unexpected error during OCR extraction: {e}")
        raise OCRError(f"Unexpected error during OCR extraction: {e}") from e


def _process_single_image(
    image: Image.Image, 
    prompt: str, 
    model: str, 
    page_num: int = 1,
    timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Process a single image through OCR."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name, format="PNG")
            tmp_path = tmp.name
    except Exception as e:
        log(f"Failed to save image to temp file: {e}")
        raise OCRProcessingError(f"Failed to save image to temporary file: {e}") from e

    try:
        # Create client with timeout
        client = ollama.Client(timeout=timeout)
        response = client.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [tmp_path]
            }]
        )
        
        # Log token usage from Ollama response
        # Ollama returns prompt_eval_count (input) and eval_count (output)
        input_tokens = response.get("prompt_eval_count", 0)
        output_tokens = response.get("eval_count", 0)
        total_tokens = input_tokens + output_tokens
        
        log_ollama_usage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            operation=f"ocr_page_{page_num}"
        )
        
        return response["message"]["content"]
    except ollama.ResponseError as e:
        log(f"Ollama model error: {e}")
        raise OCRModelError(f"OCR model '{model}' error: {e}") from e
    except (httpx.TimeoutException, TimeoutError) as e:
        log(f"OCR timed out after {timeout}s on page {page_num}")
        raise OCRTimeoutError(
            f"OCR processing timed out after {timeout}s on page {page_num}. "
            "Try increasing the timeout or check if Ollama is responding."
        ) from e
    except (httpx.ConnectError, ConnectionError) as e:
        log(f"Failed to connect to Ollama: {e}")
        raise OCRConnectionError(
            f"Failed to connect to Ollama. Is Ollama running? Error: {e}"
        ) from e
    except Exception as e:
        error_msg = str(e).lower()
        if "timeout" in error_msg or "timed out" in error_msg:
            log(f"OCR timed out on page {page_num}: {e}")
            raise OCRTimeoutError(
                f"OCR processing timed out on page {page_num}: {e}"
            ) from e
        if "connection" in error_msg or "connect" in error_msg or "refused" in error_msg:
            log(f"Failed to connect to Ollama: {e}")
            raise OCRConnectionError(
                f"Failed to connect to Ollama. Is Ollama running? Error: {e}"
            ) from e
        log(f"OCR processing error: {e}")
        raise OCRProcessingError(f"OCR processing failed: {e}") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)
