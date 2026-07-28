import os
import re
from collections.abc import Iterable
from pathlib import Path

_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_agent_environment(
    env_file: str | Path | None = None,
    *,
    override: bool = False,
) -> Path | None:
    path = Path(env_file) if env_file else default_agent_env_file()
    try:
        exists = path.exists()
    except OSError:
        return None

    if not exists:
        return None

    values = parse_environment_lines(path.read_text(encoding="utf-8").splitlines())
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return path


def default_agent_env_file() -> Path:
    explicit_path = os.getenv("AGENT_ENV_FILE")
    if explicit_path and explicit_path.strip():
        return Path(explicit_path.strip())

    if os.name == "nt":
        program_data = os.getenv("ProgramData", r"C:\ProgramData")
        return Path(program_data) / "TheAllSeeingEye" / "agent.env"

    return Path("/etc/the-all-seeing-eye/agent.env")


def parse_environment_lines(lines: Iterable[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        key, separator, raw_value = line.partition("=")
        if separator == "":
            raise ValueError(f"Linea {line_number} no contiene asignacion KEY=VALUE")

        key = key.strip()
        if not _ENV_NAME_PATTERN.fullmatch(key):
            raise ValueError(f"Linea {line_number} contiene una variable invalida: {key}")

        values[key] = _normalize_value(raw_value.strip())
    return values


def _normalize_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
