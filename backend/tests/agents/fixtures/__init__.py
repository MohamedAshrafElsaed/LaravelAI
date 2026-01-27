"""
Test fixtures for multi-agent testing.

Provides test scenarios, mock responses, and sample code
for comprehensive agent pipeline testing.
"""

from .scenarios import (
    SUBSCRIPTION_SCENARIO,
    SIMPLE_CRUD_SCENARIO,
    BUG_FIX_SCENARIO,
    REFACTOR_SCENARIO,
    get_scenario,
)

__all__ = [
    "SUBSCRIPTION_SCENARIO",
    "SIMPLE_CRUD_SCENARIO",
    "BUG_FIX_SCENARIO",
    "REFACTOR_SCENARIO",
    "get_scenario",
]
