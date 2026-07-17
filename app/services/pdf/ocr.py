import io
from typing import Any, Optional

from app.core.logging import logger


class OCRService:
    """Service to handle OCR on scanned pages with no extractable text."""

    def __init__(self) -> None:
        self.tesseract_available: Optional[bool] = None

    def _check_tesseract(self) -> bool:
        if self.tesseract_available is not None:
            return self.tesseract_available

        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self.tesseract_available = True
        except Exception:
            self.tesseract_available = False
            logger.warning(
                "Tesseract OCR is not installed or configured on the system path. "
                "Any scanned PDF pages will fail to process. Please install Tesseract."
            )
        return self.tesseract_available

    def perform_ocr(self, page_pixmap: Any) -> str:
        """Executes Tesseract OCR on a page's visual image."""
        if not self._check_tesseract():
            return ""

        try:
            import pytesseract
            from PIL import Image

            # Convert PyMuPDF Pixmap to PIL Image
            png_bytes = page_pixmap.tobytes("png")
            img = Image.open(io.BytesIO(png_bytes))

            # Extract text
            text = pytesseract.image_to_string(img)
            logger.info("OCR text extraction completed", length=len(text))
            return text
        except Exception as e:
            logger.error("OCR extraction failed", error=str(e))
            return ""
