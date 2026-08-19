"""Provider-neutral evaluation records and reproducibility helpers.

This package intentionally contains no benchmark fixtures, research results,
provider calls, or complete evaluation pipelines.
"""

from .schemas import EvaluationMode, RunManifest, RunRecord

__all__ = ["EvaluationMode", "RunManifest", "RunRecord"]
