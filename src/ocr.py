"""Optical character recognition for image CVs and scanned PDFs.

Some uploads have no text layer at all: a photo of a printed CV, a screenshot,
or a PDF that is really just scanned pages. :mod:`file_extract` handles files
that *do* contain extractable text; this module is the fallback that reads text
off pixels.

Two backends, tried in this order (a "layered" strategy):

1. **Tesseract** (``pytesseract`` + the ``tesseract`` system binary) — local,
   free, offline, and private. Used whenever it is installed.
2. **Vision LLM** — the image is sent as a base64 data URL through the shared
   :mod:`llm_client` (``Task.OCR``). Needs the configured OCR model to support
   image input. Used only when Tesseract is unavailable.

If neither backend can run, :class:`OCRUnavailableError` is raised with an
actionable message rather than returning garbage. All heavy/optional pieces are
imported lazily so importing this module never fails.
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

try:  # importable both as a bare module (main.py) and as the src package
    import llm_client
except ImportError:  # pragma: no cover
    from . import llm_client  # type: ignore


class OCRError(Exception):
    """Raised when OCR is attempted but fails to read usable text."""


class OCRUnavailableError(OCRError):
    """Raised when no OCR backend (Tesseract or a vision LLM) is usable."""


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default


# Tunables (overridable via environment).
def _ocr_languages() -> str:
    """Tesseract language string, e.g. ``"eng"`` or ``"eng+fra"``.

    Each language needs its data pack installed (``tesseract-ocr-fra`` etc.).
    """
    return (os.environ.get("OCR_LANGUAGES") or "eng").strip() or "eng"


def _pdf_dpi() -> int:
    return _int_env("OCR_PDF_DPI", 200)


def _max_pages() -> int:
    return max(1, _int_env("OCR_MAX_PAGES", 10))


def _vision_max_side() -> int:
    """Longest image edge sent to the vision LLM (keeps token cost sane)."""
    return max(512, _int_env("OCR_VISION_MAX_SIDE", 2200))


# ---------------------------------------------------------------------------
# Backend availability
# ---------------------------------------------------------------------------


def tesseract_available() -> bool:
    """True when both the Python binding and the system binary are present."""
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# PDF -> page images
# ---------------------------------------------------------------------------


def pdf_to_images(data: bytes, dpi: Optional[int] = None) -> List[bytes]:
    """Rasterize a PDF to a list of PNG byte strings (one per page).

    Prefers ``pdf2image`` when installed; otherwise shells out to poppler's
    ``pdftoppm`` directly (commonly present even when the Python wrapper is
    not). Returns ``[]`` if neither path is available.
    """
    dpi = dpi or _pdf_dpi()
    limit = _max_pages()

    # Preferred path: pdf2image (a thin wrapper over the same poppler binary).
    try:
        from pdf2image import convert_from_bytes  # type: ignore

        images = convert_from_bytes(data, dpi=dpi, last_page=limit, fmt="png")
        out: List[bytes] = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - fall through to the poppler CLI
        pass

    # Fallback path: call poppler's pdftoppm if it is on PATH.
    if shutil.which("pdftoppm") is None:
        return []
    return _pdftoppm_to_pngs(data, dpi=dpi, limit=limit)


def _pdftoppm_to_pngs(data: bytes, *, dpi: int, limit: int) -> List[bytes]:
    """Rasterize via the ``pdftoppm`` CLI into a temp dir, then read the PNGs."""
    with tempfile.TemporaryDirectory(prefix="autocv_ocr_") as tmp:
        src = os.path.join(tmp, "in.pdf")
        with open(src, "wb") as fh:
            fh.write(data)
        prefix = os.path.join(tmp, "page")
        try:
            subprocess.run(
                [
                    "pdftoppm", "-png", "-r", str(dpi),
                    "-l", str(limit), src, prefix,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
        except (subprocess.SubprocessError, OSError):
            return []
        pages = sorted(
            f for f in os.listdir(tmp)
            if f.startswith("page") and f.endswith(".png")
        )
        out: List[bytes] = []
        for name in pages[:limit]:
            with open(os.path.join(tmp, name), "rb") as fh:
                out.append(fh.read())
        return out


# ---------------------------------------------------------------------------
# Backend: Tesseract
# ---------------------------------------------------------------------------


def _ocr_image_tesseract(png_bytes: bytes) -> str:
    import pytesseract  # local import: only reached when available
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        return pytesseract.image_to_string(img, lang=_ocr_languages()) or ""


# ---------------------------------------------------------------------------
# Backend: Vision LLM
# ---------------------------------------------------------------------------

_VISION_SYSTEM_PROMPT = (
    "You are an OCR engine for CV / résumé documents. Transcribe ALL text you "
    "see, preserving the reading order and line breaks. Keep section headings, "
    "names, dates, bullet points and contact details. Do not summarise, "
    "translate, correct, or add anything that is not in the image. Output only "
    "the transcribed text — no commentary, no markdown fences."
)


def _to_data_url(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _downscale_png(png_bytes: bytes) -> bytes:
    """Cap the longest edge so vision payloads stay small. Best-effort."""
    try:
        from PIL import Image
    except ImportError:
        return png_bytes
    try:
        with Image.open(io.BytesIO(png_bytes)) as img:
            img = img.convert("RGB")
            longest = max(img.size)
            cap = _vision_max_side()
            if longest > cap:
                scale = cap / float(longest)
                new_size = (max(1, int(img.width * scale)),
                            max(1, int(img.height * scale)))
                img = img.resize(new_size)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:  # noqa: BLE001 - send the original on any failure
        return png_bytes


def _ocr_images_vision(png_pages: List[bytes]) -> str:
    data_urls = [_to_data_url(_downscale_png(p)) for p in png_pages]
    instruction = (
        "Transcribe the text from "
        + ("this CV image." if len(data_urls) == 1
           else f"these {len(data_urls)} CV pages, in order.")
    )
    raw = llm_client.vision(
        instruction,
        data_urls,
        system_prompt=_VISION_SYSTEM_PROMPT,
        task=llm_client.Task.OCR,
        log_prefix="ocr",
    )
    return (raw or "").strip()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def ocr_png_pages(png_pages: List[bytes]) -> str:
    """OCR a list of PNG page images using the best available backend.

    Tesseract is used per-page when installed; otherwise a single vision-LLM
    call transcribes all pages. Raises :class:`OCRUnavailableError` when no
    backend can run, or :class:`OCRError` when a backend ran but produced no
    text.
    """
    if not png_pages:
        raise OCRError("No image data to read.")

    if tesseract_available():
        parts = [_ocr_image_tesseract(p).strip() for p in png_pages]
        text = "\n\n".join(p for p in parts if p).strip()
        if text:
            return text
        # Tesseract ran but found nothing — let the vision backend try if set.

    text = _ocr_images_vision(png_pages)
    if text:
        return text

    if not tesseract_available():
        raise OCRUnavailableError(
            "This file has no text layer and OCR is not configured. Install "
            "Tesseract (e.g. `sudo apt install tesseract-ocr` + "
            "`pip install pytesseract`) for offline OCR, or set a vision-"
            "capable OCR model (OPENROUTER_MODEL_OCR / LOCAL_MODEL_OCR)."
        )
    raise OCRError("OCR ran but could not read any text from the file.")


def ocr_image_bytes(data: bytes) -> str:
    """OCR a single uploaded image file (PNG/JPG/WebP/…)."""
    return ocr_png_pages([_normalize_to_png(data)])


def ocr_pdf_bytes(data: bytes) -> str:
    """Rasterize a (scanned) PDF and OCR every page."""
    pages = pdf_to_images(data)
    if not pages:
        raise OCRUnavailableError(
            "Could not rasterize the PDF for OCR. Install poppler "
            "(`pdftoppm`) or the `pdf2image` package."
        )
    return ocr_png_pages(pages)


def _normalize_to_png(data: bytes) -> bytes:
    """Re-encode an arbitrary image upload to PNG via Pillow.

    Returns the original bytes if Pillow is missing (Tesseract/vision can often
    still read common formats), so this stays best-effort.
    """
    try:
        from PIL import Image
    except ImportError:
        return data
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        raise OCRError("Could not read the image file.") from exc
