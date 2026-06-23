"""Configure a logger using a dictionary"""

import json
import logging.config
from datetime import datetime

# Setting
LOG_LEVEL_DEFAULT = "INFO"
PACKAGE = __name__.split(".")[0]  # "WebSearcher" -- tells our own logs from foreign ones


class JsonlFormatter(logging.Formatter):
    """Serialize each log record as one JSON object per line (JSON Lines).

    Emits the crawl-log schema downstream tooling consumes directly, so native
    logs no longer need an after-the-fact text parser. ``event`` is the structured
    event type (``"search"``, ``"parse"``, ...) read from the logging ``extra=``
    mechanism, ``None`` for ad-hoc log lines; ``message`` is the human text and is
    ``None`` when empty (a structured event puts its data in fields, not the
    message). Search fields (``response_code``/``qry``/``loc``) are likewise read
    from ``extra=`` and are ``None`` off the search path; ``output`` carries the
    formatted traceback on error lines. ``source`` is the originating logger name,
    but only for foreign logs (urllib3/requests/asyncio bubbling up to the root
    handler) -- ``None`` for WebSearcher's own lines, so third-party WARNING noise
    stays trackable without repeating a constant name on every record.

    Null fields are omitted from the emitted object: ``timestamp``/``pid``/``level``
    are always present, and each line carries only the other keys that apply to it
    (a parse/save/foreign line has no ``qry``/``loc``/``response_code``).
    """

    def format(self, record: logging.LogRecord) -> str:
        name = record.name
        is_own = name == PACKAGE or name.startswith(f"{PACKAGE}.")
        payload = {
            "timestamp": datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "pid": record.process,
            "level": record.levelname,
            "event": getattr(record, "event", None),
            "message": record.getMessage() or None,
            "response_code": getattr(record, "response_code", None),
            "qry": getattr(record, "qry", None),
            "loc": getattr(record, "loc", None),
            "output": self.formatException(record.exc_info) if record.exc_info else None,
            "source": None if is_own else name,
        }
        return json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human/console formatter that falls back to the structured ``event`` name
    when a record has no message (a structured event keeps its data in fields and
    logs an empty message, so the console would otherwise show a blank line).

    Non-mutating: it formats a *copy* of the record, so the shared record stays
    intact for a JSONL sink attached to the same logger.
    """

    def formatMessage(self, record: logging.LogRecord) -> str:
        if not record.message and getattr(record, "event", None):
            record = logging.makeLogRecord({**record.__dict__, "message": record.event})
        return super().formatMessage(record)


# Formatters: change what gets logged
minimal = "%(message)s"
medium = "%(asctime)s.%(msecs)01d | %(levelname)s | %(name)s | %(message)s"
detailed = "%(asctime)s.%(msecs)01d | %(process)d | %(levelname)s | %(name)s | %(message)s"
formatters = {
    "minimal": {"()": TextFormatter, "format": minimal},
    "medium": {"()": TextFormatter, "format": medium, "datefmt": "%Y-%m-%d %H:%M:%S"},
    "detailed": {"()": TextFormatter, "format": detailed, "datefmt": "%Y-%m-%d %H:%M:%S"},
    "jsonl": {"()": JsonlFormatter},
}


class Logger:
    """
    A configurable logger for console and file outputs.

    Attributes:
        log_config (dict): Configuration dictionary for the logger.

    Methods:
        start(name: Optional[str]): Initializes and retrieves the logger instance.
    """

    def __init__(
        self,
        console: bool = True,
        console_format: str = "medium",
        console_level: str = LOG_LEVEL_DEFAULT,
        file_name: str = "",
        file_mode: str = "w",
        file_format: str = "detailed",
        file_level: str = LOG_LEVEL_DEFAULT,
    ) -> None:
        """
        Initializes the Logger configuration.

        Args:
            console (bool): Flag to enable or disable console logging.
            console_format (str): Format of the console logging. One of 'minimal', 'medium', 'detailed', or 'jsonl'.
            console_level (str): Logging level for the console. Default is 'INFO'.
            file_name (str): Name of the file to log messages. If empty, file logging is disabled.
            file_mode (str): File mode for file logging. Default is 'w' (write).
            file_format (str): Format of the file logging. One of 'minimal', 'medium', 'detailed', or 'jsonl'.
            file_level (str): Logging level for the file. Default is 'INFO'.
        """

        # Handlers: change file and console logging details
        handlers = {}
        if console:
            assert console_format in formatters.keys(), (
                f"Console format must be one of {list(formatters.keys())}"
            )
            handlers["console_handle"] = {
                "class": "logging.StreamHandler",
                "level": console_level,
                "formatter": console_format,
            }

        if file_name:
            assert type(file_name) is str, "File name must be a string"
            assert file_format in formatters.keys(), (
                f"File format must be one of {list(formatters.keys())}"
            )
            handlers["file_handle"] = {
                "class": "logging.FileHandler",
                "level": file_level,
                "formatter": file_format,
                "filename": file_name,
                "mode": file_mode,
            }

        # Loggers: change logging options for root and other packages
        loggers = {
            # Root logger
            "": {
                "handlers": list(handlers.keys()),
                "level": "DEBUG",
                "propagate": True,
            },
            # External loggers
            "requests": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "asyncio": {"level": "INFO"},
            "chardet.charsetprober": {"level": "INFO"},
            "parso": {"level": "INFO"},  # Fix for ipython autocomplete bug
        }

        self.log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": handlers,
            "loggers": loggers,
        }

    def start(self, name: str | None = __name__) -> logging.Logger:
        logging.config.dictConfig(self.log_config)
        return logging.getLogger(name)
