from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_NAME = ".cv-builder.json"
CONFIG_SCHEMA = 1


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    employer: str
    role: str
    schema: int = CONFIG_SCHEMA

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AppConfig":
        employer = value.get("employer")
        role = value.get("role")
        schema = value.get("schema", CONFIG_SCHEMA)
        if not isinstance(employer, str) or not employer.strip():
            raise ConfigError("employer must be a non-empty string")
        if not isinstance(role, str) or not role.strip():
            raise ConfigError("role must be a non-empty string")
        if schema != CONFIG_SCHEMA:
            raise ConfigError(f"unsupported config schema: {schema!r}")
        return cls(employer=" ".join(employer.split()), role=" ".join(role.split()), schema=CONFIG_SCHEMA)


def slugify(value: str) -> str:
    value = value.translate(str.maketrans({"Ł": "L", "ł": "l"}))
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-")
    return slug or "CV"


def application_name(employer: str, role: str) -> str:
    return f"{slugify(employer)}-{slugify(role)}"


def load_config(app: Path) -> AppConfig:
    path = app / CONFIG_NAME
    if not path.is_file() or path.is_symlink():
        raise ConfigError(f"missing or unsafe {CONFIG_NAME}: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config root must be an object")
    return AppConfig.from_dict(raw)


def write_config(app: Path, config: AppConfig) -> Path:
    validated = AppConfig.from_dict(asdict(config))
    path = app / CONFIG_NAME
    if path.exists() or path.is_symlink():
        raise ConfigError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(asdict(validated), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
