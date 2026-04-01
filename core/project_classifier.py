
from __future__ import annotations

"""
project_classifier.py (TRUE MAX MERGED CIVIL-GRADE VERSION)

Purpose
-------
System-level request classification and routing layer for the AI civil / CAD
product.

This file preserves the strong original rule-based classification foundation and
expands it into a fuller routing / orchestration decision layer that can:
- classify request mode, discipline, subtasks, and outputs
- estimate request complexity
- extract optimization intent / review intent / image intent
- decide which product pipeline should run
- decide which engines / systems should be activated
- signal whether multi-pass iteration is required
- produce orchestrator-ready routing decisions
- support one-click full design workflows

Architecture role
-----------------
- planner.py = execution brain
- planner_intelligence.py = option/ranking/evolution layer
- planner_orchestrator.py = workflow shell / design-loop controller
- project_classifier.py = front-door intent + routing intelligence layer
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re


# =============================================================================
# ENUMS
# =============================================================================

class RequestMode(str, Enum):
    GENERATE = "generate"
    REVIEW = "review"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    OPTIMIZE = "optimize"
    EXPLAIN = "explain"
    UNKNOWN = "unknown"


class Discipline(str, Enum):
    SITE_CIVIL = "site_civil"
    UTILITY = "utility"
    STRUCTURE = "structure"
    BRIDGE = "bridge"
    BUILDING = "building"
    IMAGE = "image"
    MULTI = "multi"
    UNKNOWN = "unknown"


class Subtask(str, Enum):
    PIPING = "piping"
    PLUMBING = "plumbing"
    DRAINAGE = "drainage"
    STORM = "storm"
    SANITARY = "sanitary"
    WATER = "water"
    GRADING = "grading"
    SUBDIVISION = "subdivision"
    CORRIDOR = "corridor"
    ROADWAY = "roadway"
    PARKING = "parking"
    STRUCTURAL_LAYOUT = "structural_layout"
    BRIDGE_LAYOUT = "bridge_layout"
    BUILDING_LAYOUT = "building_layout"
    PLAN_REVIEW = "plan_review"
    IMAGE_ANALYSIS = "image_analysis"
    SKETCH_TO_PLAN = "sketch_to_plan"
    DXF_EXPORT = "dxf_export"
    QUANTITIES = "quantities"
    EXPLAIN_DESIGN = "explain_design"
    FIX_PLAN = "fix_plan"
    OPTIMIZE_LAYOUT = "optimize_layout"
    UNKNOWN = "unknown"


class PipelineType(str, Enum):
    FULL_DESIGN_LOOP = "full_design_loop"
    SINGLE_PLAN = "single_plan"
    MULTI_OPTION = "multi_option"
    REVIEW_PIPELINE = "review_pipeline"
    ANALYSIS_PIPELINE = "analysis_pipeline"
    IMAGE_TO_PLAN_PIPELINE = "image_to_plan_pipeline"
    SKETCH_TO_PLAN_PIPELINE = "sketch_to_plan_pipeline"
    TRANSFORM_PIPELINE = "transform_pipeline"
    EXPLAIN_PIPELINE = "explain_pipeline"
    UNKNOWN = "unknown"


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    HEAVY = "heavy"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ClassificationResult:
    mode: RequestMode
    discipline: Discipline
    subtasks: List[Subtask] = field(default_factory=list)
    confidence: float = 0.0
    matched_keywords: Dict[str, List[str]] = field(default_factory=dict)
    requested_outputs: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def has_subtask(self, subtask: Subtask) -> bool:
        return subtask in self.subtasks


@dataclass
class RoutingDecision:
    mode: RequestMode
    discipline: Discipline
    pipeline: PipelineType
    engines: List[str] = field(default_factory=list)
    workflow: str = "single_pass"
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    requires_iterations: bool = False
    use_intelligence_layer: bool = False
    use_full_design_mode: bool = False
    prefer_multi_option: bool = False
    needs_image_analysis: bool = False
    needs_sketch_parser: bool = False
    plan_type_hint: Optional[str] = None
    optimize_goal: Optional[str] = None
    requested_outputs: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    matched_keywords: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CLASSIFIER
# =============================================================================

class ProjectClassifier:
    """
    Product-level rule-based classifier and routing engine.

    Preserved strengths:
    - detects generation / review / analysis / transform
    - detects discipline and subtasks
    - detects output intent
    - includes confidence estimation and fallback inference

    Added capabilities:
    - routing decision output
    - complexity scoring
    - pipeline selection
    - engine activation hints
    - iteration / optimization control hints
    - one-click full-design detection
    - goal extraction
    """

    MODE_KEYWORDS: Dict[RequestMode, Tuple[str, ...]] = {
        RequestMode.GENERATE: (
            "design", "create", "generate", "make", "produce", "lay out", "layout",
            "build", "draft", "draw", "model",
        ),
        RequestMode.REVIEW: (
            "review", "check", "inspect", "validate", "audit", "find issues",
            "find errors", "flag", "verify", "critique",
        ),
        RequestMode.ANALYZE: (
            "analyze", "read", "interpret", "understand", "identify", "extract",
            "detect", "recognize",
        ),
        RequestMode.TRANSFORM: (
            "convert", "turn", "transform", "clean up", "redraw", "refine",
            "improve", "rewrite", "update",
        ),
        RequestMode.OPTIMIZE: (
            "optimize", "improve performance", "best", "better", "maximize",
            "minimize", "reduce", "increase efficiency",
        ),
        RequestMode.EXPLAIN: (
            "explain", "why", "reason", "walk me through", "describe the design",
            "how does this work",
        ),
    }

    DISCIPLINE_KEYWORDS: Dict[Discipline, Tuple[str, ...]] = {
        Discipline.UTILITY: (
            "pipe", "piping", "plumbing", "sanitary", "storm", "drainage",
            "drain", "water main", "domestic water", "hot water", "vent",
            "utility", "utilities", "sewer", "grease interceptor",
        ),
        Discipline.SITE_CIVIL: (
            "site", "grading", "contour", "road", "roadway", "parking",
            "subdivision", "parcel", "lot", "detention", "pond", "pad",
            "earthwork", "alignment", "corridor", "cul-de-sac", "curb",
            "sidewalk", "stormwater", "mixed use development", "site plan",
        ),
        Discipline.STRUCTURE: (
            "beam", "column", "framing", "frame", "grid", "structural",
            "foundation", "footing", "slab", "brace", "girder",
        ),
        Discipline.BRIDGE: (
            "bridge", "abutment", "pier", "span", "deck", "superstructure",
            "substructure", "girder bridge", "bridge layout",
        ),
        Discipline.BUILDING: (
            "building", "floor plan", "room", "rooms", "core", "hallway",
            "stairs", "elevator", "facade", "footprint", "architectural",
            "multi-story", "multistory",
        ),
        Discipline.IMAGE: (
            "image", "photo", "screenshot", "scan", "drawing image",
            "sketch", "hand sketch", "marked up", "picture", "plan image",
        ),
    }

    SUBTASK_KEYWORDS: Dict[Subtask, Tuple[str, ...]] = {
        Subtask.PIPING: ("pipe", "piping"),
        Subtask.PLUMBING: ("plumbing", "fixture", "fixtures"),
        Subtask.DRAINAGE: ("drainage", "drain"),
        Subtask.STORM: ("storm", "roof drain", "stormwater"),
        Subtask.SANITARY: ("sanitary", "sewer", "waste", "grease waste"),
        Subtask.WATER: ("domestic water", "cold water", "hot water", "hwr", "dcw", "dhw"),
        Subtask.GRADING: ("grading", "grade", "cut and fill", "earthwork", "proposed contours"),
        Subtask.SUBDIVISION: ("subdivision", "lots", "parcel split", "parcel", "cul-de-sac"),
        Subtask.CORRIDOR: ("corridor", "alignment", "profile", "cross section", "assembly"),
        Subtask.ROADWAY: ("road", "roadway", "intersection", "lane", "curb return"),
        Subtask.PARKING: ("parking", "stalls", "aisle", "parking lot"),
        Subtask.STRUCTURAL_LAYOUT: ("beam", "column", "grid", "framing", "structural layout"),
        Subtask.BRIDGE_LAYOUT: ("bridge", "span", "pier", "abutment", "deck"),
        Subtask.BUILDING_LAYOUT: ("floor plan", "building layout", "rooms", "core"),
        Subtask.PLAN_REVIEW: ("review", "check", "validate", "find issues", "flag"),
        Subtask.IMAGE_ANALYSIS: ("image", "photo", "detect", "extract", "recognize"),
        Subtask.SKETCH_TO_PLAN: ("sketch", "hand sketch", "napkin sketch", "rough layout"),
        Subtask.DXF_EXPORT: ("dxf", "autocad", "civil 3d", "export"),
        Subtask.QUANTITIES: ("quantity", "quantities", "materials", "takeoff", "cut fill", "earthwork summary"),
        Subtask.EXPLAIN_DESIGN: ("explain", "why", "reason", "design choices"),
        Subtask.FIX_PLAN: ("fix", "repair", "resolve conflicts", "auto-fix"),
        Subtask.OPTIMIZE_LAYOUT: ("optimize", "maximize", "minimize", "best layout"),
    }

    OUTPUT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
        "dxf": ("dxf", "dwg-like", "autocad", "civil 3d"),
        "annotations": ("label", "annotate", "annotations", "notes", "callouts"),
        "schedules": ("schedule", "schedules"),
        "report": ("report", "summary", "calculation report"),
        "review_issues": ("issues", "warnings", "errors", "review notes"),
        "riser": ("riser", "riser diagram"),
        "profile": ("profile", "profiles"),
        "sections": ("section", "sections", "cross section", "cross sections"),
        "quantities": ("quantity", "quantities", "takeoff", "materials"),
    }

    GOAL_PATTERNS: Dict[str, Tuple[str, ...]] = {
        "maximize_parking": ("maximize parking", "more parking", "increase parking", "parking efficiency"),
        "reduce_grading": ("reduce grading", "less grading", "minimize grading", "lower earthwork"),
        "improve_drainage": ("better drainage", "improve drainage", "cleaner drainage", "drain better"),
        "reduce_pipe_length": ("shorter pipe", "reduce pipe length", "pipe efficiency"),
        "balance_earthwork": ("balance cut and fill", "balanced earthwork", "earthwork balance"),
        "balanced": ("balanced", "overall balance", "best overall"),
    }

    FULL_DESIGN_TRIGGERS: Tuple[str, ...] = (
        "one click design",
        "design a site",
        "complete site plan",
        "fully engineered",
        "full design",
        "complete civil site plan",
        "end to end",
        "everything automatically",
        "solve the whole site",
    )

    def classify(self, prompt: str) -> ClassificationResult:
        text = self._normalize(prompt)

        mode, mode_matches = self._detect_mode(text)
        discipline, discipline_matches = self._detect_discipline(text)
        subtasks, subtask_matches = self._detect_subtasks(text)
        outputs = self._detect_outputs(text)
        confidence = self._estimate_confidence(
            mode_matches=mode_matches,
            discipline_matches=discipline_matches,
            subtask_matches=subtask_matches,
            outputs=outputs,
        )

        assumptions: List[str] = []
        notes: List[str] = []

        if discipline == Discipline.UNKNOWN and subtasks:
            inferred = self._infer_discipline_from_subtasks(subtasks)
            if inferred != Discipline.UNKNOWN:
                discipline = inferred
                assumptions.append("Discipline inferred from subtask keywords.")

        if mode == RequestMode.UNKNOWN:
            mode = self._infer_mode_from_context(text, subtasks)
            if mode != RequestMode.UNKNOWN:
                assumptions.append("Mode inferred from request phrasing.")

        if discipline == Discipline.IMAGE and mode == RequestMode.GENERATE and any(
            st in subtasks for st in (Subtask.SKETCH_TO_PLAN, Subtask.IMAGE_ANALYSIS)
        ):
            notes.append("Image/sketch input likely needs parsing before design generation.")

        if discipline == Discipline.UNKNOWN:
            notes.append("Could not confidently determine discipline.")
        if not subtasks:
            notes.append("No strong subtask keywords detected.")

        matched_keywords = {
            "mode": mode_matches,
            "discipline": discipline_matches,
            "subtasks": subtask_matches,
        }

        return ClassificationResult(
            mode=mode,
            discipline=discipline,
            subtasks=subtasks,
            confidence=confidence,
            matched_keywords=matched_keywords,
            requested_outputs=outputs,
            assumptions=assumptions,
            notes=notes,
        )

    def classify_and_route(self, prompt: str) -> RoutingDecision:
        base = self.classify(prompt)
        text = self._normalize(prompt)

        complexity = self._estimate_complexity(text, base)
        optimize_goal = self._extract_goal(text)
        pipeline = self._select_pipeline(text, base, complexity)
        engines = self._select_engines(base, complexity)
        workflow = self._select_workflow(base, complexity, pipeline)
        requires_iterations = self._requires_iterations(text, base, complexity, pipeline)
        use_intelligence = pipeline in {
            PipelineType.MULTI_OPTION,
            PipelineType.FULL_DESIGN_LOOP,
            PipelineType.TRANSFORM_PIPELINE,
        } or complexity in {ComplexityLevel.COMPLEX, ComplexityLevel.HEAVY}
        use_full_design_mode = pipeline == PipelineType.FULL_DESIGN_LOOP
        prefer_multi_option = pipeline in {PipelineType.MULTI_OPTION, PipelineType.FULL_DESIGN_LOOP}

        assumptions = list(base.assumptions)
        notes = list(base.notes)

        if optimize_goal:
            notes.append(f"Optimization goal detected: {optimize_goal}.")
        if use_full_design_mode:
            notes.append("Full-design loop recommended due to complexity / scope.")
        if base.discipline == Discipline.MULTI:
            notes.append("Multi-discipline routing enabled.")

        return RoutingDecision(
            mode=base.mode,
            discipline=base.discipline,
            pipeline=pipeline,
            engines=engines,
            workflow=workflow,
            complexity=complexity,
            requires_iterations=requires_iterations,
            use_intelligence_layer=use_intelligence,
            use_full_design_mode=use_full_design_mode,
            prefer_multi_option=prefer_multi_option,
            needs_image_analysis=(base.discipline == Discipline.IMAGE and base.has_subtask(Subtask.IMAGE_ANALYSIS)),
            needs_sketch_parser=(base.discipline == Discipline.IMAGE and base.has_subtask(Subtask.SKETCH_TO_PLAN)),
            plan_type_hint=self._plan_type_hint(base),
            optimize_goal=optimize_goal,
            requested_outputs=list(base.requested_outputs),
            assumptions=assumptions,
            notes=notes,
            matched_keywords=deepcopy_dict(base.matched_keywords),
            metadata={
                "confidence": base.confidence,
                "subtasks": [s.value for s in base.subtasks],
                "full_design_triggered": self._contains_phrase(text, self.FULL_DESIGN_TRIGGERS),
            },
        )

    # ---------------------------------------------------------------------
    # Detection helpers
    # ---------------------------------------------------------------------

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[_\-\/]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _detect_mode(self, text: str) -> Tuple[RequestMode, List[str]]:
        scores: Dict[RequestMode, int] = {}
        matches_by_mode: Dict[RequestMode, List[str]] = {}

        for mode, keywords in self.MODE_KEYWORDS.items():
            matches = self._find_keyword_matches(text, keywords)
            if matches:
                scores[mode] = len(matches)
                matches_by_mode[mode] = matches

        if not scores:
            return RequestMode.UNKNOWN, []

        best_mode = max(scores, key=scores.get)
        return best_mode, matches_by_mode.get(best_mode, [])

    def _detect_discipline(self, text: str) -> Tuple[Discipline, List[str]]:
        scores: Dict[Discipline, int] = {}
        matches_by_disc: Dict[Discipline, List[str]] = {}

        for discipline, keywords in self.DISCIPLINE_KEYWORDS.items():
            matches = self._find_keyword_matches(text, keywords)
            if matches:
                scores[discipline] = len(matches)
                matches_by_disc[discipline] = matches

        if not scores:
            return Discipline.UNKNOWN, []

        top_disciplines = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if len(top_disciplines) >= 2 and top_disciplines[0][1] == top_disciplines[1][1]:
            top_two = {top_disciplines[0][0], top_disciplines[1][0]}
            if len(top_two) > 1:
                merged_matches = matches_by_disc[top_disciplines[0][0]] + matches_by_disc[top_disciplines[1][0]]
                return Discipline.MULTI, sorted(set(merged_matches))

        best = top_disciplines[0][0]
        return best, matches_by_disc.get(best, [])

    def _detect_subtasks(self, text: str) -> Tuple[List[Subtask], List[str]]:
        found: List[Subtask] = []
        matched_terms: List[str] = []

        for subtask, keywords in self.SUBTASK_KEYWORDS.items():
            matches = self._find_keyword_matches(text, keywords)
            if matches:
                found.append(subtask)
                matched_terms.extend(matches)

        return found, sorted(set(matched_terms))

    def _detect_outputs(self, text: str) -> List[str]:
        outputs: List[str] = []
        for name, keywords in self.OUTPUT_KEYWORDS.items():
            if self._find_keyword_matches(text, keywords):
                outputs.append(name)
        return outputs

    def _estimate_confidence(
        self,
        mode_matches: Sequence[str],
        discipline_matches: Sequence[str],
        subtask_matches: Sequence[str],
        outputs: Sequence[str],
    ) -> float:
        score = 0.0
        if mode_matches:
            score += 0.25
        if discipline_matches:
            score += 0.30
        if subtask_matches:
            score += min(0.30, 0.05 * len(subtask_matches))
        if outputs:
            score += min(0.15, 0.05 * len(outputs))
        return min(1.0, round(score, 2))

    def _infer_discipline_from_subtasks(self, subtasks: Sequence[Subtask]) -> Discipline:
        utility_subtasks = {
            Subtask.PIPING, Subtask.PLUMBING, Subtask.DRAINAGE,
            Subtask.STORM, Subtask.SANITARY, Subtask.WATER,
        }
        civil_subtasks = {
            Subtask.GRADING, Subtask.SUBDIVISION, Subtask.CORRIDOR,
            Subtask.ROADWAY, Subtask.PARKING,
        }
        structure_subtasks = {Subtask.STRUCTURAL_LAYOUT}
        bridge_subtasks = {Subtask.BRIDGE_LAYOUT}
        building_subtasks = {Subtask.BUILDING_LAYOUT}
        image_subtasks = {Subtask.IMAGE_ANALYSIS, Subtask.SKETCH_TO_PLAN}

        sset = set(subtasks)
        flags = 0
        result = Discipline.UNKNOWN
        if sset & utility_subtasks:
            flags += 1
            result = Discipline.UTILITY
        if sset & civil_subtasks:
            flags += 1
            result = Discipline.SITE_CIVIL if flags == 1 else Discipline.MULTI
        if sset & structure_subtasks:
            flags += 1
            result = Discipline.STRUCTURE if flags == 1 else Discipline.MULTI
        if sset & bridge_subtasks:
            flags += 1
            result = Discipline.BRIDGE if flags == 1 else Discipline.MULTI
        if sset & building_subtasks:
            flags += 1
            result = Discipline.BUILDING if flags == 1 else Discipline.MULTI
        if sset & image_subtasks:
            flags += 1
            result = Discipline.IMAGE if flags == 1 else Discipline.MULTI
        return result

    def _infer_mode_from_context(self, text: str, subtasks: Sequence[Subtask]) -> RequestMode:
        if any(token in text for token in ("fix", "improve", "clean up", "redraw", "convert")):
            return RequestMode.TRANSFORM
        if any(token in text for token in ("review", "check", "validate", "find issues")):
            return RequestMode.REVIEW
        if any(token in text for token in ("analyze", "read", "interpret", "extract", "detect")):
            return RequestMode.ANALYZE
        if any(token in text for token in ("optimize", "maximize", "minimize", "best layout")):
            return RequestMode.OPTIMIZE
        if any(token in text for token in ("explain", "why", "reason")):
            return RequestMode.EXPLAIN
        if subtasks:
            return RequestMode.GENERATE
        return RequestMode.UNKNOWN

    def _find_keyword_matches(self, text: str, keywords: Sequence[str]) -> List[str]:
        matches: List[str] = []
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                matches.append(kw)
        return matches

    def _contains_phrase(self, text: str, phrases: Sequence[str]) -> bool:
        return any(phrase in text for phrase in phrases)

    # ---------------------------------------------------------------------
    # Routing helpers
    # ---------------------------------------------------------------------

    def _estimate_complexity(self, text: str, base: ClassificationResult) -> ComplexityLevel:
        complexity_score = 0

        if base.discipline == Discipline.MULTI:
            complexity_score += 3
        elif base.discipline != Discipline.UNKNOWN:
            complexity_score += 1

        complexity_score += min(4, len(base.subtasks))
        complexity_score += min(2, len(base.requested_outputs))

        heavy_markers = (
            "complete", "fully engineered", "end to end", "entire", "coordinated",
            "25 acre", "mixed use", "detention basin", "full grading plan",
            "storm drainage system", "utility systems", "earthwork summary",
            "multiple options", "optimize layout", "resolve all conflicts",
        )
        for marker in heavy_markers:
            if marker in text:
                complexity_score += 1

        if self._contains_phrase(text, self.FULL_DESIGN_TRIGGERS):
            complexity_score += 3

        if complexity_score <= 2:
            return ComplexityLevel.SIMPLE
        if complexity_score <= 5:
            return ComplexityLevel.MODERATE
        if complexity_score <= 8:
            return ComplexityLevel.COMPLEX
        return ComplexityLevel.HEAVY

    def _extract_goal(self, text: str) -> Optional[str]:
        for goal, phrases in self.GOAL_PATTERNS.items():
            if self._contains_phrase(text, phrases):
                return goal
        return None

    def _select_pipeline(
        self,
        text: str,
        base: ClassificationResult,
        complexity: ComplexityLevel,
    ) -> PipelineType:
        if base.discipline == Discipline.IMAGE:
            if base.has_subtask(Subtask.SKETCH_TO_PLAN):
                return PipelineType.SKETCH_TO_PLAN_PIPELINE
            return PipelineType.IMAGE_TO_PLAN_PIPELINE

        if base.mode == RequestMode.REVIEW or base.has_subtask(Subtask.PLAN_REVIEW):
            return PipelineType.REVIEW_PIPELINE

        if base.mode == RequestMode.ANALYZE:
            return PipelineType.ANALYSIS_PIPELINE

        if base.mode == RequestMode.EXPLAIN or base.has_subtask(Subtask.EXPLAIN_DESIGN):
            return PipelineType.EXPLAIN_PIPELINE

        if base.mode == RequestMode.TRANSFORM or base.has_subtask(Subtask.FIX_PLAN):
            return PipelineType.TRANSFORM_PIPELINE

        if self._contains_phrase(text, self.FULL_DESIGN_TRIGGERS):
            return PipelineType.FULL_DESIGN_LOOP

        if base.mode in {RequestMode.OPTIMIZE, RequestMode.GENERATE}:
            if complexity in {ComplexityLevel.COMPLEX, ComplexityLevel.HEAVY}:
                return PipelineType.FULL_DESIGN_LOOP
            if base.discipline in {Discipline.MULTI, Discipline.SITE_CIVIL, Discipline.UTILITY}:
                return PipelineType.MULTI_OPTION
            return PipelineType.SINGLE_PLAN

        return PipelineType.UNKNOWN

    def _select_engines(self, base: ClassificationResult, complexity: ComplexityLevel) -> List[str]:
        engines: List[str] = []

        subtasks = set(base.subtasks)

        # discipline defaults
        if base.discipline in {Discipline.SITE_CIVIL, Discipline.MULTI}:
            engines.extend(["layout", "grading", "drainage", "earthwork"])
        if base.discipline in {Discipline.UTILITY, Discipline.MULTI}:
            engines.extend(["pipe", "utility"])
        if base.discipline == Discipline.STRUCTURE:
            engines.extend(["structure"])
        if base.discipline == Discipline.BRIDGE:
            engines.extend(["bridge"])
        if base.discipline == Discipline.BUILDING:
            engines.extend(["building"])
        if base.discipline == Discipline.IMAGE:
            engines.extend(["image_analysis"])

        # subtask-specific enrichments
        if Subtask.STORM in subtasks or Subtask.DRAINAGE in subtasks:
            engines.extend(["drainage", "storm_network", "pipe"])
        if Subtask.SANITARY in subtasks:
            engines.extend(["sanitary", "pipe", "utility"])
        if Subtask.WATER in subtasks:
            engines.extend(["utility", "pipe"])
        if Subtask.GRADING in subtasks:
            engines.extend(["grading", "earthwork"])
        if Subtask.SUBDIVISION in subtasks:
            engines.extend(["subdivision", "grading", "drainage", "utility"])
        if Subtask.CORRIDOR in subtasks or Subtask.ROADWAY in subtasks:
            engines.extend(["corridor", "roadway", "grading", "drainage"])
        if Subtask.PARKING in subtasks:
            engines.extend(["layout", "grading"])
        if Subtask.STRUCTURAL_LAYOUT in subtasks:
            engines.extend(["structure"])
        if Subtask.BRIDGE_LAYOUT in subtasks:
            engines.extend(["bridge"])
        if Subtask.BUILDING_LAYOUT in subtasks:
            engines.extend(["building"])
        if Subtask.IMAGE_ANALYSIS in subtasks:
            engines.extend(["image_analysis"])
        if Subtask.SKETCH_TO_PLAN in subtasks:
            engines.extend(["sketch_to_plan"])
        if Subtask.QUANTITIES in subtasks:
            engines.extend(["quantity"])
        if Subtask.EXPLAIN_DESIGN in subtasks:
            engines.extend(["explain"])
        if Subtask.FIX_PLAN in subtasks:
            engines.extend(["autofix", "conflict", "compliance"])
        if Subtask.OPTIMIZE_LAYOUT in subtasks:
            engines.extend(["optimization", "planner_intelligence"])

        if complexity in {ComplexityLevel.COMPLEX, ComplexityLevel.HEAVY}:
            engines.extend(["planner", "planner_intelligence", "conflict", "compliance"])

        return dedupe_keep_order_str(engines)

    def _select_workflow(
        self,
        base: ClassificationResult,
        complexity: ComplexityLevel,
        pipeline: PipelineType,
    ) -> str:
        if pipeline == PipelineType.FULL_DESIGN_LOOP:
            return "global_design_loop"
        if pipeline == PipelineType.MULTI_OPTION:
            return "multi_option"
        if pipeline in {PipelineType.REVIEW_PIPELINE, PipelineType.ANALYSIS_PIPELINE, PipelineType.EXPLAIN_PIPELINE}:
            return "analysis"
        if pipeline in {PipelineType.IMAGE_TO_PLAN_PIPELINE, PipelineType.SKETCH_TO_PLAN_PIPELINE}:
            return "parse_then_design"
        if pipeline == PipelineType.TRANSFORM_PIPELINE:
            return "fix_transform"
        return "single_pass"

    def _requires_iterations(
        self,
        text: str,
        base: ClassificationResult,
        complexity: ComplexityLevel,
        pipeline: PipelineType,
    ) -> bool:
        if pipeline == PipelineType.FULL_DESIGN_LOOP:
            return True
        if base.mode == RequestMode.OPTIMIZE:
            return True
        if base.has_subtask(Subtask.FIX_PLAN) or base.has_subtask(Subtask.OPTIMIZE_LAYOUT):
            return True
        if complexity in {ComplexityLevel.COMPLEX, ComplexityLevel.HEAVY}:
            return True
        if any(word in text for word in ("iterate", "repeat", "until it works", "resolve all conflicts")):
            return True
        return False

    def _plan_type_hint(self, base: ClassificationResult) -> Optional[str]:
        subtasks = set(base.subtasks)
        if base.discipline == Discipline.BRIDGE or Subtask.BRIDGE_LAYOUT in subtasks:
            return "bridge"
        if base.discipline == Discipline.BUILDING or Subtask.BUILDING_LAYOUT in subtasks:
            return "building"
        if Subtask.SUBDIVISION in subtasks:
            return "subdivision"
        if Subtask.DRAINAGE in subtasks or Subtask.STORM in subtasks:
            return "drainage"
        if Subtask.ROADWAY in subtasks or Subtask.CORRIDOR in subtasks:
            return "road"
        if base.discipline in {Discipline.SITE_CIVIL, Discipline.MULTI}:
            return "site_plan"
        return None


# =============================================================================
# PUBLIC API
# =============================================================================

def classify_request(prompt: str) -> ClassificationResult:
    return ProjectClassifier().classify(prompt)


def classify_and_route_request(prompt: str) -> RoutingDecision:
    return ProjectClassifier().classify_and_route(prompt)


# =============================================================================
# MISC HELPERS
# =============================================================================

def dedupe_keep_order_str(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def deepcopy_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: list(v) if isinstance(v, list) else v for k, v in d.items()}
