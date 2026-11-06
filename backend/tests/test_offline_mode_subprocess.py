"""
NewGenHealthAI — tests/test_offline_mode_subprocess.py
Isolated process tests for authoritative OFFLINE_MODE configuration and safe LLM invocation.
Strictly zero external inference calls.
"""

import os
import subprocess
import sys
import pytest


def run_in_subprocess(env_overrides, code_snippet):
    """Run Python snippet in an isolated subprocess with explicit environment overrides."""
    env = os.environ.copy()
    # Remove existing OFFLINE_MODE unless explicitly passed
    if "OFFLINE_MODE" not in env_overrides and "OFFLINE_MODE" in env:
        del env["OFFLINE_MODE"]
    env.update(env_overrides)
    # Ensure backend root is on PYTHONPATH
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env["PYTHONPATH"] = backend_dir

    result = subprocess.run(
        [sys.executable, "-c", code_snippet],
        env=env,
        capture_output=True,
        text=True,
        cwd=backend_dir,
    )
    return result


def test_offline_mode_true_blocks_all_llm_invocations():
    """
    When OFFLINE_MODE=true:
    - get_llm returns None
    - invoke_llm_with_fallback returns None
    - _invoke_llm_safe returns None AND injected LLM object's .invoke() is never called
    """
    code = """
import sys
from unittest.mock import MagicMock
from app.core.config import is_offline_mode, OFFLINE_MODE
from app.tools.llm_client import get_llm, invoke_llm_with_fallback
from app.agents.executor import _invoke_llm_safe

assert is_offline_mode() is True, "is_offline_mode should be True"
assert OFFLINE_MODE is True, "OFFLINE_MODE constant should be True"

# 1. get_llm must be blocked
llm = get_llm("openai/gpt-oss-120b")
assert llm is None, f"get_llm should return None, got {llm}"

# 2. invoke_llm_with_fallback must be blocked
fallback_result = invoke_llm_with_fallback("test prompt")
assert fallback_result is None, f"fallback should return None, got {fallback_result}"

# 3. injected LLM's .invoke() must be blocked
mock_llm = MagicMock()
safe_result = _invoke_llm_safe(mock_llm, "test prompt")
assert safe_result is None, f"_invoke_llm_safe should return None, got {safe_result}"
assert mock_llm.invoke.call_count == 0, f"mock_llm.invoke called {mock_llm.invoke.call_count} times, should be 0"

print("SUCCESS")
"""
    res = run_in_subprocess({"OFFLINE_MODE": "true"}, code)
    assert res.returncode == 0, f"Process failed with stderr: {res.stderr}\nstdout: {res.stdout}"
    assert "SUCCESS" in res.stdout


def test_offline_mode_false_allows_normal_configured_llm():
    """
    When OFFLINE_MODE=false:
    - Normal configured LLM operation is available (tested using mocks only)
    - Injected LLM's .invoke() is called
    - On model 404/deprecation, invoke_llm_with_fallback is attempted
    """
    code = """
import sys
from unittest.mock import MagicMock, patch
from app.core.config import is_offline_mode, OFFLINE_MODE
from app.agents.executor import _invoke_llm_safe

assert is_offline_mode() is False, "is_offline_mode should be False"
assert OFFLINE_MODE is False, "OFFLINE_MODE constant should be False"

# 1. Injected LLM is invoked
mock_llm = MagicMock()
mock_llm.invoke.return_value = MagicMock(content="Mocked response")
res = _invoke_llm_safe(mock_llm, "test prompt")
assert res is not None, "Expected non-None response"
assert res.content == "Mocked response"
assert mock_llm.invoke.call_count == 1, "mock_llm.invoke should have been called once"

# 2. Fallback on 404/deprecation
mock_failing_llm = MagicMock()
mock_failing_llm.invoke.side_effect = Exception("404 Model decommissioned")
mock_fallback_resp = MagicMock(content="Fallback response")
with patch("app.agents.executor.invoke_llm_with_fallback", return_value=mock_fallback_resp) as mock_fb:
    res2 = _invoke_llm_safe(mock_failing_llm, "test prompt")
    assert res2.content == "Fallback response"
    assert mock_fb.call_count == 1

print("SUCCESS")
"""
    res = run_in_subprocess({"OFFLINE_MODE": "false"}, code)
    assert res.returncode == 0, f"Process failed with stderr: {res.stderr}\nstdout: {res.stdout}"
    assert "SUCCESS" in res.stdout


def test_offline_mode_missing_defaults_to_false():
    """
    When OFFLINE_MODE is missing from environment:
    - Normal default configuration remains unchanged (defaults to false)
    """
    code = """
import os
from app.core.config import is_offline_mode, OFFLINE_MODE

assert "OFFLINE_MODE" not in os.environ, "OFFLINE_MODE should not be in os.environ"
assert is_offline_mode() is False, "is_offline_mode should default to False"
assert OFFLINE_MODE is False, "OFFLINE_MODE should default to False"

print("SUCCESS")
"""
    res = run_in_subprocess({}, code)
    assert res.returncode == 0, f"Process failed with stderr: {res.stderr}\nstdout: {res.stdout}"
    assert "SUCCESS" in res.stdout


@pytest.mark.parametrize(
    "env_val,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        (" 1 ", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("false", False),
        ("FALSE", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("NO", False),
        ("", False),
        ("invalid_value", False),
    ],
)
def test_offline_mode_string_parsing_isolated(env_val, expected):
    """
    Verify strings 'true', 'false', '1', '0', 'yes', 'no' parse correctly in isolated process.
    """
    code = f"""
from app.core.config import is_offline_mode
val = is_offline_mode()
assert val is {expected}, f"Expected {expected} for value '{env_val}', got {{val}}"
print("SUCCESS")
"""
    res = run_in_subprocess({"OFFLINE_MODE": env_val}, code)
    assert res.returncode == 0, f"Process failed with stderr: {res.stderr}\nstdout: {res.stdout}"
    assert "SUCCESS" in res.stdout
