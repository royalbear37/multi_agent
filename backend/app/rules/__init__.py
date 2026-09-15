"""Versioned, deterministic demo rules.

The rules in this package are deliberately fictional.  They exercise software
boundaries and must not be presented as clinical guidance.
"""

from .engine import RuleEngine, load_demo_rules

__all__ = ["RuleEngine", "load_demo_rules"]
