"""
Security rules: SEC001–SEC005.
"""
import ast
import re
from typing import List

from analysis.rules.base import Finding, Rule, registry

# ── Patterns ─────────────────────────────────────────────────────────────────
_SECRET_PATTERNS = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|password|passwd|token|auth[_-]?token"
    r"|access[_-]?key|private[_-]?key|client[_-]?secret|sk-[a-z0-9]{20,})"
)
_HARDCODED_VALUE = re.compile(r'^["\'][\w\-\.@!#$%^&*()+=]{6,}["\']$')


class HardcodedSecretRule(Rule):
    """SEC001 — Detects hardcoded secrets / API keys in assignments."""

    rule_id = "SEC001"
    rule_name = "Hardcoded Secret"
    category = "security"
    severity = "critical"
    confidence = 1.0

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    name = ""
                    if isinstance(target, ast.Name):
                        name = target.id
                    elif isinstance(target, ast.Attribute):
                        name = target.attr
                    if _SECRET_PATTERNS.search(name):
                        # Check if the value looks like a hardcoded string
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            findings.append(self._make_finding(
                                file_path=file_path,
                                line_number=node.lineno,
                                code_snippet=snippet,
                                message=f"Potential hardcoded secret in variable '{name}'. "
                                        f"Never commit credentials to source control.",
                                suggestion="Use environment variables or a secrets manager (e.g. os.environ['KEY']).",
                            ))
        return findings


class EvalExecRule(Rule):
    """SEC002 — Detects dangerous eval() / exec() calls."""

    rule_id = "SEC002"
    rule_name = "Dangerous eval/exec"
    category = "security"
    severity = "high"
    confidence = 1.0

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in ("eval", "exec", "compile"):
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(self._make_finding(
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=snippet,
                        message=f"Use of `{name}()` is dangerous — it executes arbitrary code.",
                        suggestion="Avoid eval/exec. If you need dynamic behavior, use ast.literal_eval() "
                                   "for safe parsing of literals.",
                    ))
        return findings


class SQLInjectionRule(Rule):
    """SEC003 — Detects SQL queries built via f-strings or string concatenation."""

    rule_id = "SEC003"
    rule_name = "SQL Injection Risk"
    category = "security"
    severity = "critical"
    confidence = 0.97

    _SQL_KEYWORDS = re.compile(r"(?i)\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b")

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            # f-string containing SQL keywords
            if isinstance(node, ast.JoinedStr):
                # reconstruct approximate source line
                if hasattr(node, "lineno"):
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    if self._SQL_KEYWORDS.search(snippet):
                        findings.append(self._make_finding(
                            file_path=file_path,
                            line_number=node.lineno,
                            code_snippet=snippet,
                            message="SQL query built with f-string — potential SQL injection vulnerability.",
                            suggestion="Use parameterised queries: cursor.execute(sql, (param,)) "
                                       "or an ORM like SQLAlchemy.",
                        ))
            # string concat: "SELECT ... " + variable
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                if hasattr(node, "lineno"):
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    if self._SQL_KEYWORDS.search(snippet):
                        findings.append(self._make_finding(
                            file_path=file_path,
                            line_number=node.lineno,
                            code_snippet=snippet,
                            message="SQL query built via string concatenation — potential SQL injection.",
                            suggestion="Use parameterised queries instead of string concatenation.",
                        ))
        return findings


class SubprocessShellRule(Rule):
    """SEC004 — Detects subprocess calls with shell=True."""

    rule_id = "SEC004"
    rule_name = "Subprocess shell=True"
    category = "security"
    severity = "high"
    confidence = 1.0

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_str = ""
                if isinstance(node.func, ast.Attribute):
                    func_str = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_str = node.func.id
                if func_str in ("call", "run", "Popen", "check_output", "check_call"):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            findings.append(self._make_finding(
                                file_path=file_path,
                                line_number=node.lineno,
                                code_snippet=snippet,
                                message="subprocess called with shell=True — risk of shell injection.",
                                suggestion="Pass a list of arguments instead: subprocess.run(['cmd', 'arg']) "
                                           "and remove shell=True.",
                            ))
        return findings


class OpenRedirectRule(Rule):
    """SEC005 — Detects potential open redirects (redirect to user-controlled URL)."""

    rule_id = "SEC005"
    rule_name = "Open Redirect Risk"
    category = "security"
    severity = "medium"
    confidence = 0.80

    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings = []
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                if func_name in ("redirect", "RedirectResponse"):
                    # If the first argument is NOT a string literal, it may be user-controlled
                    if node.args:
                        arg = node.args[0]
                        if not isinstance(arg, ast.Constant):
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            findings.append(self._make_finding(
                                file_path=file_path,
                                line_number=node.lineno,
                                code_snippet=snippet,
                                message="Redirect target may be user-controlled — potential open redirect.",
                                suggestion="Validate the URL against a whitelist of allowed domains before redirecting.",
                                confidence=0.80,
                            ))
        return findings


# ── Register all security rules ──────────────────────────────────────────────
registry.register(HardcodedSecretRule())
registry.register(EvalExecRule())
registry.register(SQLInjectionRule())
registry.register(SubprocessShellRule())
registry.register(OpenRedirectRule())
