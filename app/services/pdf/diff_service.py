from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict

from app.models.sql.node import Node


class DiffResult(BaseModel):
    """Contains the classified nodes resulting from a version comparison."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    unchanged: List[Tuple[Node, Node]]  # Pairs of (v1_node, v2_node)
    modified: List[Tuple[Node, Node]]  # Pairs of (v1_node, v2_node)
    added: List[Node]  # Nodes present in v2 but not in v1
    removed: List[Node]  # Nodes present in v1 but not in v2


class DiffService:
    """Compares document version nodes, mapping logical identities across updates."""

    @staticmethod
    def clean_heading_title(content: str, node_type: str) -> str:
        """Strips numerical prefixes from heading titles to ensure path stability during renumbering."""
        content_clean = content.strip()
        if node_type == "title":
            return content_clean

        if node_type == "heading":
            # Matches standard numbered heading prefixes like "3.2.1 Title" or "4. Title"
            match = re.match(
                r"^\s*(?:\d+(?:\.\d+)*)\.?\s+(.+)$", content_clean, re.DOTALL
            )
            if match:
                return match.group(1).strip()

        return content_clean

    def compute_node_paths(self, nodes: List[Node]) -> Dict[str, Node]:
        """Reconstructs the hierarchy from a list of nodes and computes stable path keys for each node.

        Path format:
          - Headings: /Title/H1/H2
          - Non-Headings: /Title/H1/H2/[node_type]_[sibling_index]
        """
        # 1. Map nodes by ID for fast lookup
        node_map = {n.id: n for n in nodes}

        # 2. Build parent-to-children relationship mappings
        parent_to_children = defaultdict(list)
        roots: List[Node] = []

        for n in nodes:
            if n.parent_id is None:
                roots.append(n)
            else:
                parent_to_children[n.parent_id].append(n)

        # Sort children by position to ensure deterministic path indexes
        for pid in parent_to_children:
            parent_to_children[pid].sort(key=lambda x: x.position)
        roots.sort(key=lambda x: x.position)

        path_map: Dict[str, Node] = {}

        # 3. Recursive path builder function
        def traverse(
            node: Node, parent_path: str, sibling_counters: Dict[str, int]
        ) -> None:
            clean_title = self.clean_heading_title(node.content, node.node_type)

            if node.node_type in ["title", "heading"]:
                current_path = (
                    f"{parent_path}/{clean_title}"
                    if parent_path
                    else f"/{clean_title}"
                )
            else:
                cnt_key = node.node_type
                idx = sibling_counters[cnt_key]
                sibling_counters[cnt_key] += 1
                current_path = (
                    f"{parent_path}/{node.node_type}_{idx}"
                    if parent_path
                    else f"/{node.node_type}_{idx}"
                )

            path_map[current_path] = node

            # Traverse child elements
            child_counters = defaultdict(int)
            for child in parent_to_children[node.id]:
                traverse(child, current_path, child_counters)

        # 4. Traverse from root nodes
        root_counters = defaultdict(int)
        for r in roots:
            traverse(r, "", root_counters)

        return path_map

    def compare_versions(
        self, v1_nodes: List[Node], v2_nodes: List[Node]
    ) -> DiffResult:
        """Diffs two document versions, matching logical nodes and classifying their changes."""
        path_map_v1 = self.compute_node_paths(v1_nodes)
        path_map_v2 = self.compute_node_paths(v2_nodes)

        unchanged: List[Tuple[Node, Node]] = []
        modified: List[Tuple[Node, Node]] = []
        added: List[Node] = []
        removed: List[Node] = []

        # Compare paths present in Version 2 against Version 1
        for path_v2, node_v2 in path_map_v2.items():
            if path_v2 in path_map_v1:
                node_v1 = path_map_v1[path_v2]
                # Same logical path. Verify content change via hash comparison.
                if node_v1.content_hash == node_v2.content_hash:
                    unchanged.append((node_v1, node_v2))
                else:
                    modified.append((node_v1, node_v2))
            else:
                # Path is new in Version 2
                added.append(node_v2)

        # Find paths present in Version 1 but missing in Version 2
        for path_v1, node_v1 in path_map_v1.items():
            if path_v1 not in path_map_v2:
                removed.append(node_v1)

        return DiffResult(
            unchanged=unchanged, modified=modified, added=added, removed=removed
        )


# --- STRATEGY EXPLANATION & FAILURE CASES ---
"""
### Why This Strategy Was Chosen:
1. **Stability against Renumbering**: Striping numeric prefixes (e.g. "3.4 Auto Shutoff" -> "Auto Shutoff") is crucial. 
   If a new subsection is added, subsequent sections will shift in numbering (e.g., 3.4 becomes 3.5). By ignoring 
   prefixes, their logical path remains stable (e.g. `/Device Operation/Auto Shutoff`), and we correctly match the 
   nodes instead of falsely treating them as deleted/added.
2. **Context-Aware Mapping**: Matching nodes by their heading path ensures that paragraphs with similar content 
   (e.g., standard warning disclaimers) are not matched incorrectly. A disclaimer under "Battery" is kept separate 
   from a disclaimer under "Cuff Inflation" because their prefix paths differ.
3. **Deterministic Sibling Indexing**: Non-heading children (e.g., the 2nd paragraph under a section) are indexed 
   sequentially (e.g. `paragraph_1`). This preserves order and tracks shifts accurately within a specific container.
4. **Fast Change Detection**: Content hashing (SHA-256) provides O(1) comparison of text changes without executing 
   heavy string-distance calculations during diff runs.

### Failure Cases & Ambiguities:
1. **Heading Renaming**: If a heading's title is edited (e.g. "Auto Shutoff" is renamed to "Automatic Shutoff"), the 
   reconstructor sees `/Device Operation/Auto Shutoff` as removed, and `/Device Operation/Automatic Shutoff` as added. 
   All child paragraphs/tables under it will also get new path keys and be classified as added/removed, losing their 
   logical identity mapping.
2. **Structural Sibling Reordering**: If two paragraphs under a section are swapped (Paragraph A and Paragraph B swap positions), 
   the path index shifts. `paragraph_0` (originally A, now B) is marked as modified, and `paragraph_1` (originally B, now A) 
   is also marked as modified, rather than tracking that they were simply reordered.
3. **Duplicate Unnumbered Headings**: If a section has two sibling sub-headings with identical unnumbered titles (e.g., 
   two subheadings named "Overview" under the same parent), their paths clash. The path map dictionary will overwrite one 
   with the other, causing matching anomalies.
"""
