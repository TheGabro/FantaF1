import sys

import django


def apply_python314_django42_context_copy_patch() -> None:
    """
    Django 4.2 uses copy(super()) in BaseContext.__copy__.
    On Python 3.14 this can return an immutable super object and raise
    AttributeError while rendering templates (e.g. Django admin changelist).
    """
    if sys.version_info < (3, 14):
        return
    if django.VERSION[:2] != (4, 2):
        return

    from django.template.context import BaseContext

    # Keep patch idempotent across autoreloads.
    if getattr(BaseContext, "_py314_copy_patch_applied", False):
        return

    def _safe_basecontext_copy(self):
        duplicate = self.__class__.__new__(self.__class__)

        if hasattr(self, "__dict__"):
            duplicate.__dict__ = self.__dict__.copy()

        for slot in getattr(self.__class__, "__slots__", ()):
            if hasattr(self, slot):
                setattr(duplicate, slot, getattr(self, slot))

        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _safe_basecontext_copy
    BaseContext._py314_copy_patch_applied = True