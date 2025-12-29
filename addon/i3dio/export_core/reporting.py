from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import ExportUserError
from .messages import ExportMessage, Severity

if TYPE_CHECKING:
    from .ctx import ExportContext


@dataclass(slots=True)
class Reporter:
    ctx: ExportContext
    log: logging.Logger
    operator: Any | None = None  # Blender operator, optional, will make reports appear in UI directly

    def _default_object_name(self) -> str | None:
        extra = getattr(self.log, "extra", None)  # works for LoggerAdapter
        if isinstance(extra, dict):
            return extra.get("object_name")
        return None

    @staticmethod
    def _msg_text(msg: str, args: tuple[object, ...]) -> str:
        # Keep current style: only %-format when args are present
        return (msg % args) if args else msg

    def info(self, msg: str, *args) -> None:
        self.log.info(msg, *args, stacklevel=2)

    def debug(self, msg: str, *args) -> None:
        self.log.debug(msg, *args, stacklevel=2)

    def warning(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        report: bool = False,
    ) -> None:
        self.log.warning(msg, *args, stacklevel=2)
        text = self._msg_text(msg, args)
        obj = object_name or self._default_object_name()
        self.ctx.messages.warning(text, object_name=obj, code=code)
        if report and self.operator:
            self.operator.report({"WARNING"}, text)

    def error(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        report: bool = False,
    ) -> None:
        self.log.error(msg, *args, stacklevel=2)
        text = self._msg_text(msg, args)
        obj = object_name or self._default_object_name()
        self.ctx.messages.error(text, object_name=obj, code=code)
        if report and self.operator:
            self.operator.report({"ERROR"}, text)

    def exception(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        severity: Severity = Severity.WARNING,
    ) -> None:
        self.log.exception(msg, *args, stacklevel=2)
        text = self._msg_text(msg, args)
        obj = object_name or self._default_object_name()
        if severity is Severity.ERROR:
            self.ctx.messages.error(text, object_name=obj, code=code)
        else:
            self.ctx.messages.warning(text, object_name=obj, code=code)

    def fail(
        self,
        msg: str,
        *args,
        object_name: str | None = None,
        code: str | None = None,
        report: bool = True,
    ) -> None:
        # one call: log + messages + optional operator.report + raise
        self.error(msg, *args, object_name=object_name, code=code, report=report)
        raise ExportUserError(self._msg_text(msg, args))


def report_messages_to_operator(ctx: ExportContext, *, limit: int = 10, code_summary_limit: int = 5) -> None:
    operator = getattr(ctx, "operator", None)
    if operator is None or limit <= 0:
        return

    items = ctx.messages.items
    if not items:
        return

    errors: list[ExportMessage] = [m for m in items if m.severity is Severity.ERROR]
    warnings: list[ExportMessage] = [m for m in items if m.severity is Severity.WARNING]

    def fmt(m: ExportMessage) -> str:
        return f"[{m.object_name}] {m.text}" if m.object_name else m.text

    shown = 0
    shown_ids: set[int] = set()

    for m in errors:
        if shown >= limit:
            break
        operator.report({"ERROR"}, fmt(m))
        shown_ids.add(id(m))
        shown += 1

    for m in warnings:
        if shown >= limit:
            break
        operator.report({"WARNING"}, fmt(m))
        shown_ids.add(id(m))
        shown += 1

    remaining = [m for m in (errors + warnings) if id(m) not in shown_ids]
    if not remaining:
        return

    # Group remaining ONLY by code (ignore messages without code for grouping)
    coded = [m for m in remaining if m.code]
    # uncoded_count = len(remaining) - len(coded)

    counts = Counter(m.code for m in coded)  # type: ignore[arg-type]
    # Show biggest repeating codes first
    for code, n in counts.most_common(code_summary_limit):
        operator.report({"WARNING"}, f"...and {n} more: {code} (see export log)")

        # Mark these as accounted for in our final hidden count
        # (we'll subtract them from hidden below)
    accounted = sum(n for _, n in counts.most_common(code_summary_limit))

    hidden = len(remaining) - accounted
    if hidden > 0:
        operator.report({"WARNING"}, f"...and {hidden} more messages (see export log).")
