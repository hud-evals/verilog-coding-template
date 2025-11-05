import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Dict, List, Literal, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class Grade:
    """The grade to return within the mcp.grade_problem tool."""

    subscores: dict[str, float]
    weights: dict[str, float]
    metadata: dict[str, Any] | None

    @property
    def score(self):
        assert self.subscores.keys() == self.weights.keys()
        assert np.isclose(sum(self.weights.values()), 1)
        assert min(self.subscores.values()) >= 0
        assert max(self.subscores.values()) <= 1

        score = sum([self.subscores[key] * self.weights[key] for key in self.subscores.keys()])

        return np.clip(score, 0.0, 1.0)


# the different levels of review
ReviewLevel = Literal[
    "no-review",
    "creator-reviewed",
    "hud-approved",
    "customer-approved",
]


@dataclass
class HintSpec:
    hint_type: Literal["legit", "leaky"]
    # the text of the hint (provided to the model)
    text: str
    # the reason why the hint is legitimate (for human reviewers)
    why_legitmate: str | None = None


# New registry machinery
@dataclass
class ProblemSpec:
    # required fields (no defaults)
    id: str
    description: str
    base: str
    test: str
    golden: str
    test_files: list[str]
    # optional fields (with defaults)
    hints: list[HintSpec] = field(default_factory=list)
    difficulty: str = "easy"
    task_type: str = "coding"
    review_level: ReviewLevel = "no-review"
    config: dict[str, Any] | None = None
    startup_command: str = "hud_eval"
    demo: bool = False
    too_hard: bool = False



# global list of all registered problems
PROBLEM_REGISTRY: list[ProblemSpec] = []
