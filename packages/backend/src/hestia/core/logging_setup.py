"""One log format for the whole process. Idempotent."""

import logging

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(h, "_hestia", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler._hestia = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level.upper())
