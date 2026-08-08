"""
Rule Engine base: Rule ABC, Finding dataclass, RuleRegistry.
"""
from __future__ import annotations
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    category: str            # security | code_smell | performance | architecture
    severity: str            # critical | high | medium | low
    confidence: float        # 0.0 – 1.0
    file_path: str
    line_number: int
    code_snippet: str
    message: str
    suggestion: str = ""
    source: str = "rule"

    def severity_weight(self) -> float:
        return SEVERITY_WEIGHTS.get(self.severity, 0.25)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Finding):
            return False
        return (
            self.rule_id == other.rule_id
            and self.file_path == other.file_path
            and self.line_number == other.line_number
        )

    def __hash__(self) -> int:
        return hash((self.rule_id, self.file_path, self.line_number))


class Rule(ABC):
    """Abstract base class for all rules."""

    rule_id: str = ""
    rule_name: str = ""
    category: str = ""
    severity: str = "medium"
    confidence: float = 1.0

    @abstractmethod
    def check(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        """Run the rule against a parsed AST and return findings."""
        ...

    def _make_finding(
        self,
        file_path: str,
        line_number: int,
        code_snippet: str,
        message: str,
        suggestion: str = "",
        confidence: Optional[float] = None,
    ) -> Finding:
        return Finding(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            category=self.category,
            severity=self.severity,
            confidence=confidence if confidence is not None else self.confidence,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
            message=message,
            suggestion=suggestion,
        )


class RuleRegistry:
    """Holds all registered Rule instances."""

    def __init__(self):
        self._rules: List[Rule] = []

    def register(self, rule: Rule):
        self._rules.append(rule)

    def all_rules(self) -> List[Rule]:
        return list(self._rules)

    def run_all(self, tree: ast.AST, file_path: str, source: str) -> List[Finding]:
        findings: List[Finding] = []
        for rule in self._rules:
            try:
                findings.extend(rule.check(tree, file_path, source))
            except Exception as exc:
                # Don't let one broken rule kill the whole run
                import logging
                logging.getLogger(__name__).warning(
                    "Rule %s raised %s on %s", rule.rule_id, exc, file_path
                )
        return findings


# ── Global registry singleton ────────────────────────────────────────────────
registry = RuleRegistry()
