"""Environment loading helpers for truth.x backend startup.

Loads backend/.env early and emits safe runtime validation logs without
printing secret values.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from backend.utils.logger import logger


def _env_paths() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent
    return [backend_dir / ".env", project_root / ".env"]


@lru_cache(maxsize=1)
def ensure_backend_environment_loaded() -> str:
    """Load backend environment files once and return the loaded path label."""
    loaded_paths: list[str] = []
    for env_path in _env_paths():
        if env_path.exists():
            load_dotenv(env_path, override=True)
            loaded_paths.append(str(env_path))
    if loaded_paths:
        # ─── Automatic Feature Enabling ──────────────────────────────────────
        if os.environ.get("MISTRAL_API_KEY"):
            if "MISTRAL_REASONING_ENABLED" not in os.environ:
                os.environ["MISTRAL_REASONING_ENABLED"] = "true"
                logger.info("Mistral reasoning enabled automatically (MISTRAL_API_KEY found)")
        
        if "TEXT_DETECTOR_BACKEND" not in os.environ:
            os.environ["TEXT_DETECTOR_BACKEND"] = "local"
            
        return ", ".join(loaded_paths)
    return ""


def log_runtime_env_status(context: str = "startup") -> None:
    """Log safe booleans indicating whether required runtime keys are present."""
    ensure_backend_environment_loaded()
    status = {
        "TAVILY_API_KEY": bool(os.environ.get("TAVILY_API_KEY")),
        "MISTRAL_API_KEY": bool(os.environ.get("MISTRAL_API_KEY")),
        "HUGGINGFACEHUB_API_TOKEN": bool(os.environ.get("HUGGINGFACEHUB_API_TOKEN")),
    }
    logger.info(
        "Runtime environment validation (%s): TAVILY_API_KEY loaded=%s MISTRAL_API_KEY loaded=%s HUGGINGFACEHUB_API_TOKEN loaded=%s",
        context,
        status["TAVILY_API_KEY"],
        status["MISTRAL_API_KEY"],
        status["HUGGINGFACEHUB_API_TOKEN"],
    )
