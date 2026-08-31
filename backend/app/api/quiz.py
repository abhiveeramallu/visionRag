"""
Quiz/flashcards API re-export from summary router.
"""
from app.api.summary import router  # noqa: F401 - re-use same router

__all__ = ['router']
