# Feature: monad-template, Property 1: YAML設定値が環境変数より優先される
"""
Property 1 tests: YAML config values always take priority over environment variables.

For any config key (monad_id, interval_sec, llm_model, seed_query), when a value
exists in config.yaml AND the same env var is also set, load_config() always returns
the config.yaml value.

Validates: Requirements 1.2, 3.5
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure the monad-template package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# monad.py calls TelosClient.from_env() at module level, which requires TELOS_CORE_URL.
# Set a dummy value before importing so the module loads without error.
os.environ.setdefault("TELOS_CORE_URL", "http://localhost:9999")

import monad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe printable strings that won't break YAML or env var parsing
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_/"),
    min_size=1,
    max_size=64,
)

_positive_int = st.integers(min_value=1, max_value=86400)


# ===========================================================================
# Property 1 – monad_id: YAML wins over MONAD_ID env var
# ===========================================================================

@settings(max_examples=100)
@given(yaml_value=_safe_text, env_value=_safe_text)
def test_monad_id_yaml_wins_over_env(yaml_value: str, env_value: str):
    """When monad_id is in config.yaml and MONAD_ID env var is also set,
    load_config() returns the YAML value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {"monad_id": yaml_value})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with patch.dict(os.environ, {"MONAD_ID": env_value}):
                cfg = monad.load_config()

    assert cfg.get("monad_id") == yaml_value


# ===========================================================================
# Property 1 – interval_sec: YAML wins over INTERVAL_SEC env var
# ===========================================================================

@settings(max_examples=100)
@given(yaml_value=_positive_int, env_value=_positive_int)
def test_interval_sec_yaml_wins_over_env(yaml_value: int, env_value: int):
    """When interval_sec is in config.yaml and INTERVAL_SEC env var is also set,
    load_config() returns the YAML value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {"interval_sec": yaml_value})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with patch.dict(os.environ, {"INTERVAL_SEC": str(env_value)}):
                cfg = monad.load_config()

    assert cfg.get("interval_sec") == yaml_value


# ===========================================================================
# Property 1 – llm_model: YAML wins over LLM_MODEL env var
# ===========================================================================

@settings(max_examples=100)
@given(yaml_value=_safe_text, env_value=_safe_text)
def test_llm_model_yaml_wins_over_env(yaml_value: str, env_value: str):
    """When llm_model is in config.yaml and LLM_MODEL env var is also set,
    load_config() returns the YAML value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {"llm_model": yaml_value})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with patch.dict(os.environ, {"LLM_MODEL": env_value}):
                cfg = monad.load_config()

    assert cfg.get("llm_model") == yaml_value


# ===========================================================================
# Property 1 – seed_query: YAML wins over SEED_QUERY env var
# ===========================================================================

@settings(max_examples=100)
@given(yaml_value=_safe_text, env_value=_safe_text)
def test_seed_query_yaml_wins_over_env(yaml_value: str, env_value: str):
    """When seed_query is in config.yaml and SEED_QUERY env var is also set,
    load_config() returns the YAML value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {"seed_query": yaml_value})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with patch.dict(os.environ, {"SEED_QUERY": env_value}):
                cfg = monad.load_config()

    assert cfg.get("seed_query") == yaml_value


# ===========================================================================
# Property 1 – all keys simultaneously: YAML wins for every key at once
# ===========================================================================

@settings(max_examples=100)
@given(
    yaml_monad_id=_safe_text,
    yaml_interval=_positive_int,
    yaml_llm_model=_safe_text,
    yaml_seed_query=_safe_text,
    env_monad_id=_safe_text,
    env_interval=_positive_int,
    env_llm_model=_safe_text,
    env_seed_query=_safe_text,
)
def test_all_keys_yaml_wins_over_env(
    yaml_monad_id: str,
    yaml_interval: int,
    yaml_llm_model: str,
    yaml_seed_query: str,
    env_monad_id: str,
    env_interval: int,
    env_llm_model: str,
    env_seed_query: str,
):
    """When all four keys are present in config.yaml and all corresponding env vars
    are also set, load_config() returns the YAML values for every key."""
    yaml_data = {
        "monad_id": yaml_monad_id,
        "interval_sec": yaml_interval,
        "llm_model": yaml_llm_model,
        "seed_query": yaml_seed_query,
    }
    env_data = {
        "MONAD_ID": env_monad_id,
        "INTERVAL_SEC": str(env_interval),
        "LLM_MODEL": env_llm_model,
        "SEED_QUERY": env_seed_query,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, yaml_data)

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with patch.dict(os.environ, env_data):
                cfg = monad.load_config()

    assert cfg.get("monad_id") == yaml_monad_id
    assert cfg.get("interval_sec") == yaml_interval
    assert cfg.get("llm_model") == yaml_llm_model
    assert cfg.get("seed_query") == yaml_seed_query


# Feature: monad-template, Property 2: 不正なYAMLフィールドは起動エラーを引き起こす
"""
Property 2 tests: Any unknown YAML field causes load_config() to raise SystemExit.

For any string s NOT in the allowed field set (monad_id, interval_sec, llm_model,
seed_query), a config.yaml containing s as a key causes load_config() to raise
SystemExit.

Validates: Requirements 1.4
"""

_ALLOWED_FIELDS = {"monad_id", "interval_sec", "llm_model", "seed_query"}

# Strategy: generate strings that are not in the allowed field set
_unknown_field = st.text(min_size=1, max_size=64).filter(
    lambda s: s not in _ALLOWED_FIELDS
)


# ===========================================================================
# Property 2 – unknown field alone causes SystemExit
# ===========================================================================

@settings(max_examples=100)
@given(unknown_key=_unknown_field)
def test_unknown_field_causes_system_exit(unknown_key: str):
    """When config.yaml contains a key not in the allowed set, load_config()
    raises SystemExit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {unknown_key: "some_value"})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with pytest.raises(SystemExit):
                monad.load_config()


# ===========================================================================
# Property 2 – unknown field mixed with valid fields still causes SystemExit
# ===========================================================================

@settings(max_examples=100)
@given(unknown_key=_unknown_field)
def test_unknown_field_with_valid_fields_causes_system_exit(unknown_key: str):
    """When config.yaml contains a mix of valid and unknown keys, load_config()
    still raises SystemExit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        _write_yaml(config_path, {
            "monad_id": "test-monad",
            unknown_key: "some_value",
        })

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with pytest.raises(SystemExit):
                monad.load_config()


# ===========================================================================
# Unit tests – config loader (Requirements 1.2, 1.3)
# ===========================================================================

class TestLoadConfigNoFile:
    """When config.yaml does NOT exist."""

    def test_returns_empty_dict_when_no_config_file(self, tmp_path):
        """load_config() returns {} when config.yaml does not exist."""
        missing_path = tmp_path / "config.yaml"
        # Ensure the file really doesn't exist
        assert not missing_path.exists()

        with patch.object(monad, "_CONFIG_PATH", missing_path):
            result = monad.load_config()

        assert result == {}

    def test_env_vars_used_when_no_config_file(self, tmp_path, monkeypatch):
        """When config.yaml is absent, env vars supply the config values."""
        missing_path = tmp_path / "config.yaml"

        monkeypatch.setenv("MONAD_ID", "env-monad-id")
        monkeypatch.setenv("INTERVAL_SEC", "42")
        monkeypatch.setenv("LLM_MODEL", "openai/gpt-4-turbo")

        with patch.object(monad, "_CONFIG_PATH", missing_path):
            cfg = monad.load_config()

        # load_config() returns {} when no file; callers resolve env vars themselves
        assert cfg == {}

        # Verify env vars are accessible (the resolution pattern used in monad.py)
        assert os.environ.get("MONAD_ID") == "env-monad-id"
        assert int(os.environ.get("INTERVAL_SEC", 180)) == 42
        assert os.environ.get("LLM_MODEL") == "openai/gpt-4-turbo"


class TestLoadConfigWithFile:
    """When config.yaml exists with valid values."""

    def test_returns_values_from_yaml(self, tmp_path):
        """load_config() returns the values defined in config.yaml."""
        config_path = tmp_path / "config.yaml"
        _write_yaml(config_path, {
            "monad_id": "my-monad",
            "interval_sec": 60,
            "llm_model": "openai/gpt-4o",
            "seed_query": "quantum entanglement",
        })

        with patch.object(monad, "_CONFIG_PATH", config_path):
            cfg = monad.load_config()

        assert cfg["monad_id"] == "my-monad"
        assert cfg["interval_sec"] == 60
        assert cfg["llm_model"] == "openai/gpt-4o"
        assert cfg["seed_query"] == "quantum entanglement"

    def test_partial_yaml_returns_only_present_keys(self, tmp_path):
        """load_config() returns only the keys present in config.yaml."""
        config_path = tmp_path / "config.yaml"
        _write_yaml(config_path, {"monad_id": "partial-monad"})

        with patch.object(monad, "_CONFIG_PATH", config_path):
            cfg = monad.load_config()

        assert cfg == {"monad_id": "partial-monad"}

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        """An empty config.yaml (null document) returns {}."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("", encoding="utf-8")

        with patch.object(monad, "_CONFIG_PATH", config_path):
            cfg = monad.load_config()

        assert cfg == {}


class TestLoadConfigYAMLSyntaxError:
    """YAML syntax errors cause SystemExit."""

    def test_syntax_error_causes_system_exit(self, tmp_path):
        """A config.yaml with invalid YAML syntax causes load_config() to raise SystemExit."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("monad_id: [unclosed bracket\n", encoding="utf-8")

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with pytest.raises(SystemExit):
                monad.load_config()

    def test_tab_indentation_error_causes_system_exit(self, tmp_path):
        """YAML with tab characters (invalid indentation) causes SystemExit."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("monad_id:\n\t- bad_indent\n", encoding="utf-8")

        with patch.object(monad, "_CONFIG_PATH", config_path):
            with pytest.raises(SystemExit):
                monad.load_config()
