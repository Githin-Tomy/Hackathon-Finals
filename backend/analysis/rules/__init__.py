# rules/__init__.py — import all rule modules so they self-register
from analysis.rules import security  # noqa: F401
from analysis.rules import code_smell  # noqa: F401
