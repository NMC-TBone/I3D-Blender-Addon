from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import ExportUserError
from .messages import Severity

if TYPE_CHECKING:
    from .ctx import ExportContext


@dataclass(slots=True)
class Reporter:
    ctx: ExportContext
    log: logging.Logger
    operator: Any | None = None  # Blender operator, optional

    def info(self, msg: str, *args) -> None:
        self.log.info(msg, *args, stacklevel=2)

    def debug(self, msg: str, *args) -> None:
        self.log.debug(msg, *args, stacklevel=2)

    def warn(self, msg: str, *args, object_name: str | None = None, report: bool = False) -> None:
        self.log.warning(msg, *args, stacklevel=2)
        self.ctx.messages.warn(msg % args if args else msg, object_name=object_name)
        if report and self.operator:
            self.operator.report({"WARNING"}, msg % args if args else msg)

    def error(self, msg: str, *args, object_name: str | None = None, report: bool = False) -> None:
        self.log.error(msg, *args, stacklevel=2)
        self.ctx.messages.error(msg % args if args else msg, object_name=object_name)
        if report and self.operator:
            self.operator.report({"ERROR"}, msg % args if args else msg)

    def fail(self, msg: str, *args, object_name: str | None = None) -> None:
        # one call: log + messages + operator.report + raise
        self.error(msg, *args, object_name=object_name, report=True)
        raise ExportUserError(msg % args if args else msg)

    def exception(self, msg: str, *args, object_name: str | None = None, severity: Severity = Severity.WARNING) -> None:
        # traceback in logs, clean message for users
        self.log.exception(msg, *args, stacklevel=2)
        text = msg % args if args else msg
        if severity is Severity.ERROR:
            self.ctx.messages.error(text, object_name=object_name)
        else:
            self.ctx.messages.warn(text, object_name=object_name)


def report_messages_to_operator(operator, ctx, *, limit: int = 10) -> None:
    """Report collected messages to Blender UI (operator.report)."""
    if operator is None:
        return

    shown = 0
    for m in ctx.messages.items:
        text = f"[{m.object_name}] {m.text}" if m.object_name else m.text
        if m.severity is Severity.ERROR:
            operator.report({"ERROR"}, text)
            shown += 1
        elif m.severity is Severity.WARNING:
            operator.report({"WARNING"}, text)
            shown += 1
        elif m.severity is Severity.INFO:
            operator.report({"INFO"}, text)
            shown += 1

        if shown >= limit:
            remaining = len(ctx.messages.items) - shown
            if remaining > 0:
                operator.report({"WARNING"}, f"...and {remaining} more messages (see export log).")
            break
