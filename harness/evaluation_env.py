"""Credential-minimal local child environments, not host or network isolation."""

import importlib.util
from pathlib import Path


_metrics_path = Path(__file__).resolve().parents[1] / "skeleton" / "tools" / "metrics_core.py"
_metrics_spec = importlib.util.spec_from_file_location("_mve_evaluation_metrics", _metrics_path)
if _metrics_spec is None or _metrics_spec.loader is None:
    raise ImportError("Cannot load the kit's evaluation environment")
_metrics_module = importlib.util.module_from_spec(_metrics_spec)
_metrics_spec.loader.exec_module(_metrics_module)

evaluation_environment = _metrics_module.evaluation_environment
