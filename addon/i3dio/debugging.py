"""Debug module which primarily contains the loggers used in the code and any helpful functions for debugging"""

import logging
from contextlib import contextmanager

# A top level logger with the module name
addon_name = __package__
addon_logger = logging.getLogger(addon_name)
addon_logger.setLevel(logging.DEBUG)
addon_logger.handlers = []  # Reset upon reload, since reloading the addon does not reload the logging module

# Top-level handler for outputting to blender console
addon_console_handler = logging.StreamHandler()
addon_console_formatter = logging.Formatter("%(name)s:%(funcName)s:%(levelname)s: %(message)s")
addon_console_handler.setFormatter(addon_console_formatter)
addon_console_handler_default_level = logging.WARNING
addon_console_handler.setLevel(addon_console_handler_default_level)
addon_logger.addHandler(addon_console_handler)
addon_logger.propagate = False  # Prevent double logging if root logger is used

# Formatting for writing to a log file
addon_export_log_formatter = logging.Formatter("%(name)s:%(funcName)s:%(levelname)s: %(message)s")

# Write a little message to indicate that initialization is done
addon_logger.info(f"Initialized logging for {addon_name} addon")

export_log_file_ending = "_export_log.txt"


class ObjectNameAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # allow overriding per-call: logger.info("...", extra={"object_name": "X"})
        extra = kwargs.get("extra", {})
        object_name = extra.pop("object_name", None) or self.extra.get("object_name", "?")
        kwargs["extra"] = extra
        return f"[{object_name}] {msg}", kwargs


class PrefixAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        prefix = self.extra.get("prefix", "")
        return (f"{prefix}{msg}" if prefix else msg), kwargs


def get_logger(name: str) -> logging.Logger:
    # keeps everything under the addon root for consistent filtering
    return addon_logger.getChild(name)


@contextmanager
def export_log_file(filepath: str):
    handler = logging.FileHandler(filepath, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(addon_export_log_formatter)
    addon_logger.addHandler(handler)
    try:
        yield handler
    finally:
        addon_logger.removeHandler(handler)
        handler.close()
