"""Vendor / hub page-builder mixins for :class:`python.gui.qt_app.FlashPilotWindow`.

Split out mechanically from ``qt_app``: each mixin owns one page's builder
methods so the window class stays a thin shell. Bodies are unchanged.

``devices`` is re-exported here so the ``from . import devices`` local import
inside the moved Samsung builders keeps resolving against the package.
"""
from .. import devices  # noqa: F401
from ._shared import FlowRenderMixin
from .fus import FusPageMixin
from .general import GeneralPageMixin
from .mtk import MtkPageMixin
from .qc import QcPageMixin
from .quick import QuickPageMixin
from .samsung import SamsungPageMixin
from .settings import SettingsPageMixin
from .spd import SpdPageMixin

__all__ = [
    "FlowRenderMixin",
    "FusPageMixin",
    "GeneralPageMixin",
    "MtkPageMixin",
    "QcPageMixin",
    "QuickPageMixin",
    "SamsungPageMixin",
    "SettingsPageMixin",
    "SpdPageMixin",
]
