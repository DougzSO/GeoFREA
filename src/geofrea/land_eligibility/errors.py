"""Errors of F3, apart from `pipeline` so that the window readers (`windows.py`) can raise them without importing it."""

from __future__ import annotations


class LandEligibilityError(RuntimeError):
    """An input of F3 is missing or an invariant of the result fails (A-09, V-03)."""


class MissingRequiredLayerError(LandEligibilityError):
    """A protected-area, lake or river layer of a configured country is absent; a zero share is never assumed (M-F2b-05)."""
