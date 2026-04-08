# Feature: monad-template, Property 4: Process型はsearch結果が存在する場合にwrite()を呼ぶ
"""
Property 4 tests: For any non-empty search results list (1+ items), the Process-type
Monad loop calls think() and write().

Validates: Requirements 3.3
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure the monad-template package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# process_monad.py calls TelosClient.from_env() and reads SEED_QUERY at module level.
# Set dummy values before importing so the module loads without error.
os.environ.setdefault("TELOS_CORE_URL", "http://localhost:9999")
os.environ.setdefault("SEED_QUERY", "test seed query")

import process_monad


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_search_result = st.fixed_dictionaries({
    "id": st.text(min_size=1, max_size=20),
    "content": st.text(min_size=1, max_size=200),
    "score": st.floats(min_value=0.0, max_value=1.0),
})
_nonempty_results = st.lists(_search_result, min_size=1, max_size=10)


# ---------------------------------------------------------------------------
# Helper: StopLoop exception to break the infinite while loop
# ---------------------------------------------------------------------------

class _StopLoop(BaseException):
    """Raised by the mocked time.sleep to break the infinite loop after one iteration."""


# ===========================================================================
# Property 4 – think() is called when search returns non-empty results
# ===========================================================================

@settings(max_examples=100)
@given(results=_nonempty_results)
def test_think_is_called_when_search_returns_results(results: list[dict]):
    """For any non-empty search results list, the Process-type loop calls think()."""
    with patch.object(process_monad.telos, "search", return_value=results), \
         patch.object(process_monad, "think", return_value="synthesized output") as mock_think, \
         patch.object(process_monad.telos, "write", return_value="node-id"), \
         patch("time.sleep", side_effect=_StopLoop()):
        with pytest.raises(_StopLoop):
            process_monad.run()

    mock_think.assert_called_once()


# ===========================================================================
# Property 4 – write() is called when search returns non-empty results
# ===========================================================================

@settings(max_examples=100)
@given(results=_nonempty_results)
def test_write_is_called_when_search_returns_results(results: list[dict]):
    """For any non-empty search results list, the Process-type loop calls write()."""
    think_output = "synthesized output"

    with patch.object(process_monad.telos, "search", return_value=results), \
         patch.object(process_monad, "think", return_value=think_output), \
         patch.object(process_monad.telos, "write", return_value="node-id") as mock_write, \
         patch("time.sleep", side_effect=_StopLoop()):
        with pytest.raises(_StopLoop):
            process_monad.run()

    mock_write.assert_called_once()


# ===========================================================================
# Property 4 – write() receives the output of think()
# ===========================================================================

@settings(max_examples=100)
@given(results=_nonempty_results)
def test_write_receives_think_output(results: list[dict]):
    """write() is called with the string returned by think() as its first argument."""
    think_output = "synthesized output from think"

    with patch.object(process_monad.telos, "search", return_value=results), \
         patch.object(process_monad, "think", return_value=think_output), \
         patch.object(process_monad.telos, "write", return_value="node-id") as mock_write, \
         patch("time.sleep", side_effect=_StopLoop()):
        with pytest.raises(_StopLoop):
            process_monad.run()

    call_args = mock_write.call_args
    assert call_args[0][0] == think_output


# ===========================================================================
# Unit tests – edge cases
# ===========================================================================

class TestProcessMonadLoopBehavior:
    """Unit tests for specific loop behaviors."""

    def test_write_not_called_when_search_returns_empty(self):
        """When search returns 0 results, think() and write() are NOT called."""
        with patch.object(process_monad.telos, "search", return_value=[]), \
             patch.object(process_monad, "think") as mock_think, \
             patch.object(process_monad.telos, "write") as mock_write, \
             patch("time.sleep", side_effect=_StopLoop()):
            with pytest.raises(_StopLoop):
                process_monad.run()

        mock_think.assert_not_called()
        mock_write.assert_not_called()

    def test_think_called_with_prompt_containing_seed_query(self):
        """think() is called with a prompt that references the SEED_QUERY."""
        results = [{"id": "abc", "content": "some content", "score": 0.9}]

        with patch.object(process_monad.telos, "search", return_value=results), \
             patch.object(process_monad, "think", return_value="output") as mock_think, \
             patch.object(process_monad.telos, "write", return_value="node-id"), \
             patch("time.sleep", side_effect=_StopLoop()):
            with pytest.raises(_StopLoop):
                process_monad.run()

        prompt_arg = mock_think.call_args[0][0]
        assert process_monad.SEED_QUERY in prompt_arg

    def test_write_called_with_parent_ids_from_high_score_results(self):
        """write() is called with parent_ids from results with score > 0.75."""
        results = [
            {"id": "high1", "content": "content", "score": 0.9},
            {"id": "low1",  "content": "content", "score": 0.5},
            {"id": "high2", "content": "content", "score": 0.8},
        ]

        with patch.object(process_monad.telos, "search", return_value=results), \
             patch.object(process_monad, "think", return_value="output"), \
             patch.object(process_monad.telos, "write", return_value="node-id") as mock_write, \
             patch("time.sleep", side_effect=_StopLoop()):
            with pytest.raises(_StopLoop):
                process_monad.run()

        _, kwargs = mock_write.call_args
        parent_ids = mock_write.call_args[0][1] if len(mock_write.call_args[0]) > 1 else kwargs.get("parent_ids", [])
        assert "high1" in parent_ids
        assert "high2" in parent_ids
        assert "low1" not in parent_ids
