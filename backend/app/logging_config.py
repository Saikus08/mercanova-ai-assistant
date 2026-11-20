"""Log output of the application.

Python drops INFO records unless something configures a handler, and uvicorn only configures its
own loggers. Without this, the per-step logs of the agent (tool, arguments, duration, tokens,
outcome) never reach the container output.
"""

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
HANDLER_NAME = "mercanova-app"


def configure_logging(level: str) -> None:
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        raise ValueError(f"Unknown log level: {level}")
    app_logger = logging.getLogger("app")
    app_logger.setLevel(numeric)
    if not any(handler.get_name() == HANDLER_NAME for handler in app_logger.handlers):
        handler = logging.StreamHandler()
        handler.set_name(HANDLER_NAME)
        handler.setFormatter(logging.Formatter(_FORMAT))
        app_logger.addHandler(handler)
