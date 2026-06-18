"""Load and save JSON, YAML, TSV, CSV, and plain-text files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency checked at load time
    yaml = None


class DotDict(dict):
    """Dict with attribute access for nested config objects."""

    def __getattr__(self, attr: str) -> Any:
        val = self.get(attr)
        if isinstance(val, dict):
            return DotDict(val)
        if isinstance(val, list):
            return [DotDict(x) if isinstance(x, dict) else x for x in val]
        return val

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class FileLoader:
    """Dispatch file loading and saving by extension."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self._handler = self._get_handler(self.file_path)(self.file_path)

    def load(self, **kwargs: Any) -> Any:
        return self._handler.load(**kwargs)

    def save(self, content: Any, **kwargs: Any) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._handler.save(content, **kwargs)

    @classmethod
    def load_config(cls, config_path: str | Path) -> "Config":
        """Load a YAML or JSON configuration file."""
        return Config(config_path)

    @classmethod
    def load_table(cls, file_path: str | Path, **kwargs: Any) -> pd.DataFrame:
        """Load a tabular file as a DataFrame."""
        path = Path(file_path)
        return cls._get_table_handler(path)(path).load(**kwargs)

    @classmethod
    def save_table(
        cls, file_path: str | Path, content: pd.DataFrame, **kwargs: Any
    ) -> None:
        """Save a DataFrame to a tabular file."""
        path = Path(file_path)
        handler = cls._get_table_handler(path)(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler.save(content, **kwargs)

    @classmethod
    def _get_table_handler(cls, file_path: Path):
        ext = file_path.suffix.lower()
        if ext == ".csv":
            return CsvFile
        if ext in {".tsv", ".txt"}:
            return TsvFile
        raise ValueError(
            f"Unsupported tabular file type: {ext}. "
            "Use .tsv, .csv, or tab-delimited .txt files."
        )

    @classmethod
    def _get_handler(cls, file_path: Path):
        ext = file_path.suffix.lower()
        handlers = {
            ".json": JsonFile,
            ".yaml": YamlFile,
            ".yml": YamlFile,
            ".csv": CsvFile,
            ".tsv": TsvFile,
            ".txt": TxtFile,
        }
        handler = handlers.get(ext)
        if handler is None:
            raise ValueError(f"Unsupported file type: {ext}")
        return handler


class Config:
    """Configuration wrapper with path resolution helpers."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path).resolve()
        self.config_dir = self.config_path.parent
        raw = FileLoader(self.config_path).load()
        self.config = DotDict(raw) if isinstance(raw, dict) else raw

    @property
    def base_dir(self) -> Path:
        location = self.config.get("base_dir", self.config.get("location", "."))
        base = Path(location)
        if not base.is_absolute():
            base = (self.config_dir / base).resolve()
        return base

    def resolve(self, relative_path: str | Path) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()


class BaseFile:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def load(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def save(self, content: Any, **kwargs: Any) -> None:
        raise NotImplementedError


class JsonFile(BaseFile):
    def load(self, **kwargs: Any) -> DotDict:
        with open(self.file_path, encoding="utf-8") as file:
            return DotDict(json.load(file))

    def save(self, content: dict, **kwargs: Any) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(content, file, indent=2)
            file.write("\n")


class YamlFile(BaseFile):
    def load(self, **kwargs: Any) -> DotDict:
        if yaml is None:
            raise ImportError(
                "PyYAML is required for YAML config files. Install with: pip install pyyaml"
            )
        with open(self.file_path, encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return DotDict(data)

    def save(self, content: dict, **kwargs: Any) -> None:
        if yaml is None:
            raise ImportError(
                "PyYAML is required for YAML config files. Install with: pip install pyyaml"
            )
        with open(self.file_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(content, file, sort_keys=False)


class TsvFile(BaseFile):
    def load(self, **kwargs: Any) -> pd.DataFrame:
        kwargs.setdefault("sep", "\t")
        kwargs.setdefault("dtype", str)
        kwargs.setdefault("keep_default_na", False)
        if not self.file_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.file_path, **kwargs)

    def save(self, content: pd.DataFrame, **kwargs: Any) -> None:
        kwargs.setdefault("sep", "\t")
        kwargs.setdefault("index", False)
        content.to_csv(self.file_path, **kwargs)


class CsvFile(BaseFile):
    def load(self, **kwargs: Any) -> pd.DataFrame:
        kwargs.setdefault("sep", ",")
        kwargs.setdefault("dtype", str)
        kwargs.setdefault("keep_default_na", False)
        if not self.file_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.file_path, **kwargs)

    def save(self, content: pd.DataFrame, **kwargs: Any) -> None:
        kwargs.setdefault("sep", ",")
        kwargs.setdefault("index", False)
        content.to_csv(self.file_path, **kwargs)


class TxtFile(BaseFile):
    def load(self, **kwargs: Any) -> str:
        with open(self.file_path, encoding="utf-8") as file:
            return file.read()

    def save(self, content: str, **kwargs: Any) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            file.write(content)
