from __future__ import annotations

from typing import List

import fitz

from app.core.logging import logger
from app.services.pdf.classifier import ClassifierService
from app.services.pdf.extractor import ExtractorService
from app.services.pdf.models import ParsedDocumentNode, ParsedElement
from app.services.pdf.ocr import OCRService
from app.services.pdf.tree_builder import TreeBuilderService


class PDFParserService:
    """Orchestrator for the PDF parsing pipeline."""

    def __init__(self) -> None:
        self.ocr_service = OCRService()
        self.extractor_service = ExtractorService(self.ocr_service)
        self.classifier_service = ClassifierService()
        self.tree_builder_service = TreeBuilderService()

    def parse_pdf(self, file_path: str) -> ParsedDocumentNode:
        """Parses a PDF file into a hierarchical document tree structure."""
        logger.info("Opening PDF file for parsing", path=file_path)

        doc = fitz.open(file_path)
        all_elements: List[ParsedElement] = []

        try:
            for page_idx in range(len(doc)):
                page_number = page_idx + 1
                page = doc[page_idx]

                # Extract page content blocks (text blocks and parsed tables)
                raw_page_elements = (
                    self.extractor_service.extract_page_elements(
                        page, page_number
                    )
                )

                for pos, element in enumerate(raw_page_elements):
                    if isinstance(element, dict):
                        # It is a raw text block dictionary, classify and potentially split it
                        classified_elements = (
                            self.classifier_service.classify_and_split_block(
                                element, page_number, pos
                            )
                        )
                        all_elements.extend(classified_elements)
                    else:
                        # Already parsed table element
                        element.position = pos
                        all_elements.append(element)

            # Build structural tree from classified elements
            tree_root = self.tree_builder_service.build_tree(all_elements)
            logger.info(
                "PDF parsing completed successfully",
                total_elements=len(all_elements),
            )
            return tree_root

        finally:
            doc.close()
            logger.info("Closed PDF document reference")
