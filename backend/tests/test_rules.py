"""
Basic unit tests for the rule engine.
Run with: pytest backend/tests/ -v
"""
import ast
import pytest

from analysis.rules.security import HardcodedSecretRule, SQLInjectionRule, EvalExecRule, SubprocessShellRule
from analysis.rules.code_smell import EmptyExceptRule, LongMethodRule, TooManyArgsRule


def _parse(code: str):
    return ast.parse(code)


# ── Security Rules ────────────────────────────────────────────────────────────

class TestSEC001_HardcodedSecret:
    rule = HardcodedSecretRule()

    def test_detects_api_key_assignment(self):
        code = 'api_key = "sk-abc123xyz"'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1
        assert findings[0].rule_id == "SEC001"

    def test_ignores_env_variable(self):
        code = 'api_key = os.environ["API_KEY"]'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0

    def test_detects_password_assignment(self):
        code = 'password = "mysecretpassword"'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1


class TestSEC002_EvalExec:
    rule = EvalExecRule()

    def test_detects_eval(self):
        code = 'result = eval(user_input)'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1
        assert findings[0].rule_id == "SEC002"

    def test_detects_exec(self):
        code = 'exec(user_code)'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1

    def test_no_false_positive_on_safe_call(self):
        code = 'result = len(items)'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0


class TestSEC003_SQLInjection:
    rule = SQLInjectionRule()

    def test_detects_fstring_sql(self):
        code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) >= 1
        assert any(f.rule_id == "SEC003" for f in findings)

    def test_detects_concat_sql(self):
        code = 'query = "SELECT * FROM users WHERE name = " + username'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) >= 1


class TestSEC004_SubprocessShell:
    rule = SubprocessShellRule()

    def test_detects_shell_true(self):
        code = 'subprocess.run("ls -la", shell=True)'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1
        assert findings[0].rule_id == "SEC004"

    def test_no_flag_without_shell_true(self):
        code = 'subprocess.run(["ls", "-la"])'
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0


# ── Code Smell Rules ──────────────────────────────────────────────────────────

class TestCS003_EmptyExcept:
    rule = EmptyExceptRule()

    def test_detects_bare_except(self):
        code = dedent("""
try:
    risky()
except:
    pass
""")
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) >= 1
        assert any(f.rule_id == "CS003" for f in findings)

    def test_no_flag_on_specific_except(self):
        code = dedent("""
try:
    risky()
except ValueError as e:
    print(e)
""")
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0


class TestCS001_LongMethod:
    rule = LongMethodRule()

    def test_detects_long_function(self):
        # Generate a function with 60 lines
        lines = ["def long_function():"]
        for i in range(60):
            lines.append(f"    x_{i} = {i}")
        code = "\n".join(lines)
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1
        assert findings[0].rule_id == "CS001"

    def test_no_flag_on_short_function(self):
        code = "def short():\n    return 42"
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0


class TestCS002_TooManyArgs:
    rule = TooManyArgsRule()

    def test_detects_too_many_args(self):
        code = "def fn(a, b, c, d, e, f, g): pass"
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 1
        assert findings[0].rule_id == "CS002"

    def test_ignores_self_in_method(self):
        code = "def fn(self, a, b, c): pass"
        findings = self.rule.check(_parse(code), "test.py", code)
        assert len(findings) == 0


# helper
from textwrap import dedent
