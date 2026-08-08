"""
Code smell / maintainability rules: CS001–CS005.
"""
import ast
from typing import List

from analysis.rules.base import Finding, Rule, registry


class LongMethodRule(Rule):
    """CS001 — Flags functions/methods that exceed a line-length threshold."""

    rule_id = "CS001"
    rule_name = "Long Method"
    category = "code_smell"
    severity = "medium"
    confidence = 0.90
    MAX_LINES = 50

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or node.lineno) - node.lineno
                if length > self.MAX_LINES:
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(self._make_finding(
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet,
                        message=f"Function '{node.name}' is {length} lines long (limit: {self.MAX_LINES}). "
                                f"Long methods are hard to test and reason about.",
                        suggestion="Break this function into smaller, single-responsibility helpers.",
                    ))
        return findings


class TooManyArgsRule(Rule):
    """CS002 — Flags functions with too many parameters."""

    rule_id = "CS002"
    rule_name = "Too Many Arguments"
    category = "code_smell"
    severity = "low"
    confidence = 0.95
    MAX_ARGS = 6

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Exclude 'self' / 'cls'
                args = [a for a in node.args.args if a.arg not in ("self", "cls")]
                if len(args) > self.MAX_ARGS:
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(self._make_finding(
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet,
                        message=f"Function '{node.name}' has {len(args)} arguments (limit: {self.MAX_ARGS}). "
                                f"This often signals that the function does too much.",
                        suggestion="Group related parameters into a dataclass or config object.",
                    ))
        return findings


class EmptyExceptRule(Rule):
    """CS003 — Detects bare/empty except clauses that swallow all errors."""

    rule_id = "CS003"
    rule_name = "Empty Except Block"
    category = "code_smell"
    severity = "high"
    confidence = 1.0

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Bare except (no type specified) or body contains only `pass`
                is_bare = node.type is None
                body_is_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                if is_bare or body_is_pass:
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(self._make_finding(
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet,
                        message="Empty or bare except clause swallows all errors silently.",
                        suggestion="Catch specific exception types and log or re-raise them: "
                                   "`except ValueError as e: logger.error(e)`.",
                    ))
        return findings


class UnusedImportRule(Rule):
    """CS004 — Detects imported names that are never referenced in the module."""

    rule_id = "CS004"
    rule_name = "Unused Import"
    category = "code_smell"
    severity = "low"
    confidence = 0.85

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()

        # Collect all imported names
        imports: dict[str, int] = {}  # name -> line number
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    key = alias.asname or alias.name.split(".")[0]
                    imports[key] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    key = alias.asname or alias.name
                    imports[key] = node.lineno

        # Collect all Name references that aren't imports
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        for name, lineno in imports.items():
            if name not in used and name != "__future__":
                snippet = source_lines[lineno - 1].strip() if lineno <= len(source_lines) else ""
                findings.append(self._make_finding(
                    file_path=file_path,
                    line_number=lineno,
                    code_snippet=snippet,
                    message=f"Import '{name}' appears to be unused.",
                    suggestion=f"Remove the unused import of '{name}'.",
                ))
        return findings


class BareRaiseRule(Rule):
    """CS005 — Detects re-raising exceptions without context (raise from)."""

    rule_id = "CS005"
    rule_name = "Bare Raise Without Context"
    category = "code_smell"
    severity = "low"
    confidence = 0.80

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                # raise SomeError() without `from` clause and not bare `raise`
                if node.exc is not None and node.cause is None:
                    if isinstance(node.exc, (ast.Call, ast.Name)):
                        snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                        findings.append(self._make_finding(
                            file_path=file_path,
                            line_number=node.lineno,
                            code_snippet=snippet,
                            message="Exception raised without chaining original cause — loses traceback context.",
                            suggestion="Use `raise NewError(...) from original_exc` to preserve the cause chain.",
                        ))
        return findings


# ── Register all code smell rules ────────────────────────────────────────────
registry.register(LongMethodRule())
registry.register(TooManyArgsRule())
registry.register(EmptyExceptRule())
registry.register(UnusedImportRule())
registry.register(BareRaiseRule())
