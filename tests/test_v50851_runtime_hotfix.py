from __future__ import annotations

import ast
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "app.py"


def _top_level_function_lines() -> dict[str, int]:
    tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
    return {
        node.name: node.lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_auth_error_helper_exists_before_source_text() -> None:
    functions = _top_level_function_lines()
    assert "v13_is_auth_error" in functions
    assert "v13_source_text" in functions
    assert functions["v13_is_auth_error"] < functions["v13_source_text"]


def test_auth_error_helper_has_expected_markers() -> None:
    source = APP.read_text(encoding="utf-8")
    start = source.index("def v13_is_auth_error")
    end = source.index("def v13_source_text", start)
    helper = source[start:end]
    namespace: dict[str, object] = {}
    exec(helper, namespace)
    fn = namespace["v13_is_auth_error"]
    assert fn("401 Unauthorized") is True
    assert fn("Access token expired") is True
    assert fn("DhanHQ Live OC") is False
