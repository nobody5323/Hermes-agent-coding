"""Command and mount safety checks for sandbox execution."""

from __future__ import annotations

import re
from pathlib import Path


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bdel\s+/s\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bmkfs\b",
    r"\bchmod\s+-R\s+777\s+/",
    r"\b\.ssh\b",
    r"\b\.aws\b",
    r"\b\.env\b",
]


def is_dangerous_command(command: str) -> bool:
    lowered = command.lower()
    return any(re.search(pattern, lowered) for pattern in DANGEROUS_PATTERNS)


def validate_mount_path(path: str | Path) -> bool:
    target = Path(path).resolve()
    sensitive_names = {".ssh", ".aws", ".config"}
    return all(part not in sensitive_names for part in target.parts)


def build_docker_limits() -> dict[str, object]:
    return {
        "network": "none",
        "cpus": "1",
        "memory": "512m",
        "read_only": False,
    }
