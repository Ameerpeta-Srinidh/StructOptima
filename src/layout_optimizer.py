"""
Layout Optimizer — Pareto-Optimal Column Placement Generator

Generates candidate column layouts by perturbing the auto-framed baseline,
scores them using LayoutScorer, and returns the Pareto-optimal subset.
"""

import math
import itertools
from typing import List, Tuple, Optional
from dataclasses import dataclass
from .layout_scorer import LayoutScorer, ColumnCandidate, LayoutScore
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for the layout optimizer."""
    perturbation_m: float = 0.5       # ±0.5m shift per column
    perturbation_step_m: float = 0.25  # Step size for perturbation grid
    max_candidates: int = 50           # Max candidate layouts to evaluate
    min_structural_score: float = 40.0 # Reject layouts below this threshold
    top_n: int = 3                     # Number of top layouts to return


class LayoutOptimizer:
    """
    Generates Pareto-optimal column layouts by perturbing the baseline
    and scoring on structural + aesthetic axes.

    Args:
        scorer: LayoutScorer instance with wall geometry loaded
        baseline_columns: The auto-framed column positions
        config: Optimization parameters
    """

    def __init__(
        self,
        scorer: LayoutScorer,
        baseline_columns: List[ColumnCandidate],
        config: Optional[OptimizationConfig] = None,
    ):
        self.scorer = scorer
        self.baseline = baseline_columns
        self.config = config or OptimizationConfig()

    def optimize(self) -> List[LayoutScore]:
        """
        Run the optimization pipeline.
        Returns top-N Pareto-optimal layouts sorted by composite score.
        """
        logger.info("Starting layout optimization with %d baseline columns", len(self.baseline))

        # Step 1: Score the baseline
        baseline_score = self.scorer.score_layout(self.baseline, layout_id="Baseline")
        logger.info(
            "Baseline: structural=%.1f, aesthetic=%.1f, composite=%.1f",
            baseline_score.structural_score, baseline_score.aesthetic_score, baseline_score.composite_score,
        )

        # Step 2: Generate candidates
        candidates = self._generate_candidates()
        logger.info("Generated %d candidate layouts", len(candidates))

        # Step 3: Score all candidates
        scored: List[LayoutScore] = [baseline_score]
        for i, candidate in enumerate(candidates):
            layout_score = self.scorer.score_layout(candidate, layout_id=f"L{i+1}")

            # Filter out structurally unacceptable layouts
            if layout_score.structural_score >= self.config.min_structural_score:
                scored.append(layout_score)

        logger.info("%d candidates passed structural threshold (>%.0f)", len(scored), self.config.min_structural_score)

        # Step 4: Compute Pareto frontier
        pareto = self._pareto_frontier(scored)
        logger.info("Pareto frontier contains %d non-dominated layouts", len(pareto))

        # Step 5: Return top-N by composite score
        pareto.sort(key=lambda s: s.composite_score, reverse=True)
        top = pareto[: self.config.top_n]

        for layout in top:
            logger.info(
                "  %s: structural=%.1f, aesthetic=%.1f, composite=%.1f",
                layout.layout_id, layout.structural_score, layout.aesthetic_score, layout.composite_score,
            )

        return top

    # ------------------------------------------------------------------ #
    #  CANDIDATE GENERATION                                               #
    # ------------------------------------------------------------------ #

    def _generate_candidates(self) -> List[List[ColumnCandidate]]:
        """
        Generate candidate layouts by perturbing non-corner columns.
        Strategy: for each non-corner column, try shifting it along X and Y
        by discrete steps within the perturbation range.
        """
        # Identify movable columns (not corners — moving corners breaks stability)
        movable_indices = [i for i, c in enumerate(self.baseline) if not c.is_corner]

        if not movable_indices:
            logger.info("No movable columns — all are corners. Returning baseline only.")
            return []

        step = self.config.perturbation_step_m
        pert = self.config.perturbation_m
        offsets = []
        v = -pert
        while v <= pert + 1e-9:
            offsets.append(round(v, 3))
            v += step

        candidates = []

        # Strategy 1: Perturb one column at a time (single-column sweep)
        for idx in movable_indices:
            for dx in offsets:
                for dy in offsets:
                    if dx == 0 and dy == 0:
                        continue

                    new_layout = []
                    for i, col in enumerate(self.baseline):
                        if i == idx:
                            new_layout.append(ColumnCandidate(
                                id=col.id,
                                x=col.x + dx,
                                y=col.y + dy,
                                width_mm=col.width_mm,
                                depth_mm=col.depth_mm,
                                is_corner=col.is_corner,
                                is_edge=col.is_edge,
                            ))
                        else:
                            new_layout.append(col)

                    candidates.append(new_layout)

                    if len(candidates) >= self.config.max_candidates:
                        return candidates

        # Strategy 2: Shift ALL movable columns uniformly (grid shift)
        for dx in offsets:
            for dy in offsets:
                if dx == 0 and dy == 0:
                    continue

                new_layout = []
                for i, col in enumerate(self.baseline):
                    if i in movable_indices:
                        new_layout.append(ColumnCandidate(
                            id=col.id,
                            x=col.x + dx,
                            y=col.y + dy,
                            width_mm=col.width_mm,
                            depth_mm=col.depth_mm,
                            is_corner=col.is_corner,
                            is_edge=col.is_edge,
                        ))
                    else:
                        new_layout.append(col)

                candidates.append(new_layout)

                if len(candidates) >= self.config.max_candidates:
                    return candidates

        return candidates

    # ------------------------------------------------------------------ #
    #  PARETO FRONTIER                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pareto_frontier(scores: List[LayoutScore]) -> List[LayoutScore]:
        """
        Compute the Pareto frontier: layouts not dominated on both axes.
        A layout X dominates Y if X.structural >= Y.structural AND
        X.aesthetic >= Y.aesthetic AND at least one is strictly greater.
        """
        if not scores:
            return []

        pareto = []
        for candidate in scores:
            dominated = False
            for other in scores:
                if other.layout_id == candidate.layout_id:
                    continue
                if (
                    other.structural_score >= candidate.structural_score
                    and other.aesthetic_score >= candidate.aesthetic_score
                    and (
                        other.structural_score > candidate.structural_score
                        or other.aesthetic_score > candidate.aesthetic_score
                    )
                ):
                    dominated = True
                    break

            if not dominated:
                pareto.append(candidate)

        return pareto
