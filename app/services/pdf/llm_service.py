from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.sql.llm_failure import LLMFailureLog
from app.models.sql.node import Node
from app.models.sql.qa_test_case import GeneratedTestCase
from app.models.sql.selection import Selection
from app.schemas.selection import QATestCaseList


class LLMIntegrationService:
    """Service to handle LLM queries for text selections, generating validated QA test cases."""

    def reconstruct_text(self, selection: Selection) -> str:
        """Concatenates the text content of all nodes mapped to a selection, respecting positions and offsets."""
        mappings_sorted = sorted(
            selection.node_mappings, key=lambda m: m.node.position
        )
        parts: List[str] = []

        for mapping in mappings_sorted:
            content = mapping.node.content
            start = mapping.anchor_offset
            end = mapping.focus_offset

            if start is not None and end is not None:
                # Sort offsets to avoid inversion errors
                s, e = min(start, end), max(start, end)
                parts.append(content[s:e])
            else:
                parts.append(content)

        return "\n".join(parts)

    async def _call_gemini_api(self, prompt: str) -> str:
        """Executes an async HTTP request to Google's Gemini API."""
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured in application settings."
            )

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={api_key}"
        )

        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=payload, headers=headers, timeout=20.0
            )

            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Gemini API returned status code {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )

            data = response.json()
            try:
                # Extract generated text from Gemini response payload structure
                generated_text = data["candidates"][0]["content"]["parts"][0][
                    "text"
                ]
                return generated_text.strip()
            except (KeyError, IndexError) as e:
                raise ValueError(
                    f"Failed to parse text candidates from Gemini response structure: {e}. "
                    f"Raw payload: {data}"
                )

    async def generate_qa_test_cases(
        self, selection: Selection, db: AsyncSession
    ) -> QATestCaseList:
        """Generates 3-5 QA test cases from selection text, retrying once on formatting failure, and logging errors."""
        reconstructed_text = self.reconstruct_text(selection)

        prompt = (
            "You are an expert QA Engineer. Your task is to generate 3 to 5 realistic "
            "Question-and-Answer (QA) test cases based on the provided text.\n"
            "The test cases must be designed to verify a user's understanding of the text "
            "or to serve as automated QA check questions.\n\n"
            f"Input Text:\n{reconstructed_text}\n\n"
            "Output format:\n"
            "Return a JSON object with a single key 'test_cases' containing a list of objects. "
            "Each object must have:\n"
            "- 'question': The QA question (str).\n"
            "- 'answer': The detailed, accurate answer derived from the text (str).\n\n"
            "JSON Schema to follow:\n"
            "{\n"
            '  "test_cases": [\n'
            "    {\n"
            '      "question": "string",\n'
            '      "answer": "string"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        raw_response = ""
        last_error = ""

        # Attempt up to 2 times (Initial try + 1 validation retry)
        for attempt in range(1, 3):
            try:
                logger.info(
                    f"LLM QA Generation: Attempt {attempt}",
                    selection_id=selection.id,
                )
                raw_response = await self._call_gemini_api(prompt)

                # Validate response against Pydantic schema
                validated = QATestCaseList.model_validate_json(raw_response)
                logger.info(
                    "LLM QA Generation: Successful validation",
                    selection_id=selection.id,
                )
                return validated

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"LLM QA Generation failed on attempt {attempt}: {last_error}",
                    selection_id=selection.id,
                    raw_response=raw_response,
                )

                if attempt == 1:
                    # Emphasize strict format compliance on the retry attempt
                    prompt += (
                        "\n\nCRITICAL: Your previous response failed Pydantic schema validation. "
                        "Make sure your output matches the JSON schema EXACTLY."
                    )
                    continue

        # If we reach here, both attempts failed. Persistently log the failure to database.
        logger.error(
            "LLM QA Generation: Both attempts failed. Logging failure.",
            selection_id=selection.id,
        )
        failure_log = LLMFailureLog(
            id=uuid.uuid4(),
            selection_id=selection.id,
            error_message=f"Validation failed after 2 attempts. Last error: {last_error}",
            raw_response=raw_response if raw_response else None,
        )
        db.add(failure_log)
        await db.commit()

        raise ValueError(
            f"Failed to generate valid QA test cases after 2 attempts. Last error: {last_error}"
        )

    async def check_qa_traceability(
        self,
        selection_id: uuid.UUID,
        target_version_id: uuid.UUID,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Determines the traceability status of QA test cases against a new target version.

        Evaluates logical identity mappings and content hash consistency.
        """
        # Fetch test cases associated with this selection
        tc_stmt = select(GeneratedTestCase).where(
            GeneratedTestCase.selection_id == selection_id
        )
        tc_res = await db.execute(tc_stmt)
        test_cases = tc_res.scalars().all()

        # Fetch all nodes in the target version
        v2_stmt = select(Node).where(Node.version_id == target_version_id)
        v2_res = await db.execute(v2_stmt)
        v2_nodes = v2_res.scalars().all()
        logical_to_v2_node = {node.logical_id: node for node in v2_nodes}

        results = []
        for tc in test_cases:
            # Query logical IDs of original referenced nodes
            v1_uuids = [uuid.UUID(nid) for nid in tc.referenced_node_ids]
            v1_stmt = select(Node.id, Node.logical_id).where(
                Node.id.in_(v1_uuids)
            )
            v1_res = await db.execute(v1_stmt)
            node_id_to_logical = {
                str(row.id): row.logical_id for row in v1_res.all()
            }

            status = "Fresh"
            reason = "All source nodes exist and content hashes match exactly."

            for nid_str in tc.referenced_node_ids:
                lid = node_id_to_logical.get(nid_str)

                # 1. Stale: Logical node does not exist in target version
                if not lid or lid not in logical_to_v2_node:
                    status = "Stale"
                    reason = f"Source node with logical ID {lid or 'unknown'} was deleted in target version."
                    break

                # 2. Possibly Stale: Node exists but content hash changed
                v2_node = logical_to_v2_node[lid]
                original_hash = tc.referenced_content_hashes.get(nid_str)
                if v2_node.content_hash != original_hash:
                    status = "Possibly stale"
                    reason = f"Content of source node (logical ID {lid}) was modified in target version."

            results.append(
                {
                    "test_case_id": tc.id,
                    "question": tc.question,
                    "status": status,
                    "reason": reason,
                }
            )

        return results
