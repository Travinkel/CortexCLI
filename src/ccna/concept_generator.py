"""
CCNA Concept Hierarchy Generator.

Uses AI (Gemini) to analyze CCNA module content and generate a semantic
concept hierarchy: ConceptArea → ConceptCluster → Concept.

This enables:
- Mastery tracking (dec_score, proc_score, app_score)
- Prerequisite relationships
- Knowledge graph construction
- Adaptive learning paths
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from loguru import logger

from config import get_settings
from src.ccna.content_parser import CCNAContentParser, ModuleContent, Section
from src.db.database import session_scope
from src.db.models.canonical import CleanConceptArea, CleanConceptCluster, CleanConcept


@dataclass
class GeneratedConcept:
    """A concept suggested by AI."""

    name: str
    definition: str
    section_ids: list[str]  # Which sections this concept covers
    knowledge_types: list[str]  # declarative, procedural, application
    domain: str = "networking"


@dataclass
class GeneratedCluster:
    """A concept cluster suggested by AI."""

    name: str
    description: str
    exam_weight: float  # 0-1, relative importance
    concepts: list[GeneratedConcept] = field(default_factory=list)


@dataclass
class HierarchyResult:
    """Result of hierarchy generation for a module."""

    module_id: str
    cluster: GeneratedCluster
    section_to_concept_map: dict[str, str]  # section_id → concept_name
    success: bool
    error: str | None = None


class ConceptGenerator:
    """Generate concept hierarchy from CCNA modules using AI."""

    HIERARCHY_PROMPT = """
You are an expert curriculum designer analyzing CCNA (Cisco Certified Network Associate) content.

Analyze this module and create a semantic concept hierarchy. Group related sections into meaningful concepts that represent learnable knowledge units.

## Module Information
Title: {module_title}
Module ID: {module_id}

## Sections
{sections_list}

## Requirements

1. **Cluster**: Create ONE ConceptCluster for this module
   - Name should be specific and descriptive (e.g., "Ethernet Switching Fundamentals", not "Module 7")
   - Description should explain what the learner will understand after mastering this cluster

2. **Concepts**: Group sections into 3-8 concepts
   - Each concept should be learnable in one focused session (30-60 minutes)
   - Combine closely related sections into single concepts
   - Each section must map to exactly one concept
   - Concept names should be specific (e.g., "ARP Cache Management", not "ARP Basics")

3. **Knowledge Types**: For each concept, identify which types of knowledge it primarily teaches:
   - "declarative" - Facts, definitions, terminology
   - "procedural" - Steps, processes, CLI commands
   - "application" - Troubleshooting, design decisions, real-world scenarios

4. **Exam Weight**: Estimate relative importance (0.0-1.0) based on:
   - CCNA exam objectives coverage
   - Foundational vs advanced content
   - Practical relevance

## Output Format (JSON)
```json
{{
    "cluster_name": "Descriptive cluster name",
    "cluster_description": "What mastery of this cluster means",
    "exam_weight": 0.15,
    "concepts": [
        {{
            "name": "Specific concept name",
            "definition": "Clear, concise definition of what this concept covers",
            "section_ids": ["{module_id}-S1-1", "{module_id}-S1-2"],
            "knowledge_types": ["declarative", "procedural"]
        }}
    ]
}}
```

Return ONLY valid JSON, no markdown formatting or explanation.
"""

    def __init__(self):
        """Initialize concept generator."""
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.ai_model  # e.g., "gemini-2.0-flash"
        self._client = None
        self.parser = CCNAContentParser()

    @property
    def client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Gemini API key not configured")

            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(model_name=self.model_name)
        return self._client

    async def _call_gemini(self, prompt: str) -> str | None:
        """Call Gemini API with the given prompt."""
        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,  # Lower for consistency
                    "top_p": 0.8,
                    "max_output_tokens": 4096,
                },
            )

            if response.text:
                return response.text

            logger.warning("Empty response from Gemini")
            return None

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    async def generate_hierarchy_for_module(
        self,
        module: ModuleContent,
    ) -> HierarchyResult:
        """
        Use Gemini to suggest concept structure for a module.

        Args:
            module: Parsed module content

        Returns:
            HierarchyResult with cluster and concepts
        """
        try:
            # Build sections list for prompt
            sections_list = self._format_sections(module.sections)

            prompt = self.HIERARCHY_PROMPT.format(
                module_title=module.title or f"Module {module.module_number}",
                module_id=module.module_id,
                sections_list=sections_list,
            )

            # Call Gemini
            response = await self._call_gemini(prompt)
            if not response:
                raise ValueError("Empty response from Gemini")

            # Parse response
            cluster = self._parse_response(response, module.module_id)

            # Build section → concept mapping
            section_to_concept = {}
            for concept in cluster.concepts:
                for section_id in concept.section_ids:
                    section_to_concept[section_id] = concept.name

            logger.info(
                f"Generated hierarchy for {module.module_id}: "
                f"cluster='{cluster.name}', concepts={len(cluster.concepts)}"
            )

            return HierarchyResult(
                module_id=module.module_id,
                cluster=cluster,
                section_to_concept_map=section_to_concept,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to generate hierarchy for {module.module_id}: {e}")
            return HierarchyResult(
                module_id=module.module_id,
                cluster=GeneratedCluster(name="", description="", exam_weight=0.0),
                section_to_concept_map={},
                success=False,
                error=str(e),
            )

    def _format_sections(self, sections: list[Section], indent: int = 0) -> str:
        """Format sections as a readable list for the prompt."""
        lines = []
        prefix = "  " * indent

        for section in sections:
            lines.append(f"{prefix}- {section.id}: {section.title}")
            if section.subsections:
                lines.append(self._format_sections(section.subsections, indent + 1))

        return "\n".join(lines)

    def _parse_response(self, response: str, module_id: str) -> GeneratedCluster:
        """Parse Gemini response into GeneratedCluster."""
        # Clean response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\n?", "", response)
            response = re.sub(r"\n?```$", "", response)

        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            raise ValueError(f"Invalid JSON from AI: {e}")

        # Build concepts
        concepts = []
        for c in data.get("concepts", []):
            concepts.append(
                GeneratedConcept(
                    name=c.get("name", "Unknown"),
                    definition=c.get("definition", ""),
                    section_ids=c.get("section_ids", []),
                    knowledge_types=c.get("knowledge_types", ["declarative"]),
                )
            )

        return GeneratedCluster(
            name=data.get("cluster_name", f"Module {module_id}"),
            description=data.get("cluster_description", ""),
            exam_weight=float(data.get("exam_weight", 0.1)),
            concepts=concepts,
        )

    async def generate_all_hierarchies(
        self,
    ) -> list[HierarchyResult]:
        """Generate concept hierarchies for all CCNA modules."""
        modules = self.parser.parse_all_modules()
        results = []

        for module in modules:
            result = await self.generate_hierarchy_for_module(module)
            results.append(result)

        successful = sum(1 for r in results if r.success)
        logger.info(f"Generated hierarchies: {successful}/{len(results)} successful")

        return results

    def save_hierarchy_to_db(
        self,
        result: HierarchyResult,
        concept_area_id: UUID,
    ) -> tuple[str, list[str]]:
        """
        Save generated hierarchy to database.

        Args:
            result: HierarchyResult from generation
            concept_area_id: Parent ConceptArea UUID

        Returns:
            Tuple of (cluster name, list of concept names) - strings to avoid detached session
        """
        with session_scope() as session:
            # Create CleanConceptCluster
            cluster = CleanConceptCluster(
                concept_area_id=concept_area_id,
                name=result.cluster.name,
                description=result.cluster.description,
                exam_weight=result.cluster.exam_weight,
                display_order=int(result.module_id.replace("NET-M", "")),
            )
            session.add(cluster)
            session.flush()  # Get cluster ID

            # Create CleanConcepts
            concept_names = []
            for i, gen_concept in enumerate(result.cluster.concepts):
                concept = CleanConcept(
                    cluster_id=cluster.id,
                    name=gen_concept.name,
                    definition=gen_concept.definition,
                    domain="networking",
                    status="to_learn",
                    # Initialize mastery scores to 0
                    dec_score=0.0,
                    proc_score=0.0,
                    app_score=0.0,
                )
                session.add(concept)
                concept_names.append(gen_concept.name)

            session.commit()

            cluster_name = result.cluster.name
            logger.info(
                f"Saved to DB: cluster '{cluster_name}' with {len(concept_names)} concepts"
            )

            # Return strings, not ORM objects
            return cluster_name, concept_names

    def create_ccna_concept_area(self) -> UUID:
        """Create the top-level CCNA ConceptArea if it doesn't exist.

        Returns:
            UUID of the ConceptArea (not the object, to avoid detached session issues)
        """
        with session_scope() as session:
            # Check if already exists
            existing = (
                session.query(CleanConceptArea)
                .filter(CleanConceptArea.name.ilike("%CCNA%"))
                .first()
            )

            if existing:
                logger.info(f"Found existing CCNA ConceptArea: {existing.id}")
                # Return UUID, not the object
                return existing.id

            # Create new
            area = CleanConceptArea(
                name="CCNA: Introduction to Networks",
                description=(
                    "Cisco Certified Network Associate - Introduction to Networks (ITN) "
                    "course content covering networking fundamentals, protocols, and configuration."
                ),
                domain="networking",
                display_order=1,
            )
            session.add(area)
            session.commit()

            logger.info(f"Created CCNA ConceptArea: {area.id}")
            # Return UUID, not the object
            return area.id

    def get_section_concept_mapping(
        self,
        module_id: str,
    ) -> dict[str, UUID]:
        """
        Get mapping from section_id to concept_id for a module.

        This is used during atom generation to link atoms to concepts.

        Args:
            module_id: Module ID (e.g., "NET-M7")

        Returns:
            Dict mapping section_id → concept_id (UUID)
        """
        with session_scope() as session:
            # Find the cluster for this module
            cluster = (
                session.query(CleanConceptCluster)
                .filter(CleanConceptCluster.name.ilike(f"%{module_id}%"))
                .first()
            )

            if not cluster:
                logger.warning(f"No cluster found for {module_id}")
                return {}

            # Get all concepts in this cluster
            concepts = (
                session.query(CleanConcept)
                .filter(CleanConcept.cluster_id == cluster.id)
                .all()
            )

            # For now, map all sections to first concept
            # TODO: Store section_ids in concept metadata for precise mapping
            mapping = {}
            if concepts:
                default_concept_id = concepts[0].id
                # This would need section metadata stored during generation
                # For now, return empty and handle in generation pipeline

            return mapping


async def generate_ccna_hierarchy() -> dict[str, Any]:
    """
    Main function to generate complete CCNA concept hierarchy.

    Returns:
        Summary dict with stats and any errors
    """
    generator = ConceptGenerator()

    # 1. Create or get ConceptArea (returns UUID, not object)
    concept_area_id = generator.create_ccna_concept_area()

    # 2. Generate hierarchies for all modules
    results = await generator.generate_all_hierarchies()

    # 3. Save to database
    saved_clusters = []
    saved_concepts = []
    errors = []

    for result in results:
        if result.success:
            try:
                cluster_name, concept_names = generator.save_hierarchy_to_db(
                    result, concept_area_id
                )
                saved_clusters.append(cluster_name)
                saved_concepts.extend(concept_names)
            except Exception as e:
                errors.append(f"{result.module_id}: {e}")
        else:
            errors.append(f"{result.module_id}: {result.error}")

    summary = {
        "concept_area_id": str(concept_area_id),
        "clusters_created": len(saved_clusters),
        "concepts_created": len(saved_concepts),
        "errors": errors,
        "clusters": saved_clusters,
    }

    logger.info(
        f"Hierarchy generation complete: "
        f"{len(saved_clusters)} clusters, {len(saved_concepts)} concepts"
    )

    return summary
