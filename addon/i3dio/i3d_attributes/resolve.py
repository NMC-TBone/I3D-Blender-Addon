from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .. import utility
from .schema import I3DSchema, PropertyDefinition

ErrorHandler = Callable[[str, Exception], None]


@dataclass(frozen=True, slots=True)
class ResolvedAttribute:
    """An I3D attribute ready to be written or added to the export IR."""

    source: str
    target: str
    name: str
    value: object


def _resolve_value(values: object, owner: object, schema: I3DSchema, source: str) -> object:
    value = getattr(values, source)

    if (tracking := schema[source].tracking) is None or not getattr(values, f"{source}_tracking"):
        return value

    value = getattr(owner, tracking.member_path)
    if tracking.mapping is not None:
        value = tracking.mapping[value]

    return value


def _dependencies_met(
    values: object,
    owner: object,
    schema: I3DSchema,
    definition: PropertyDefinition,
) -> bool:
    for source, expected in definition.dependencies:
        if _resolve_value(values, owner, schema, source) != expected:
            return False
    return True


def resolve_attributes(
    values: object,
    schema: I3DSchema | None = None,
    *,
    owner: object | None = None,
    on_error: ErrorHandler | None = None,
) -> Iterator[ResolvedAttribute]:
    if schema is None:
        schema = getattr(type(values), "i3d_schema")
    if owner is None:
        owner = getattr(values, "id_data", values)

    for source, definition in schema.items():
        export = definition.export
        if export is None:
            continue

        if not _dependencies_met(values, owner, schema, definition):
            continue

        value = _resolve_value(values, owner, schema, source)
        if utility.isclose_value(value, export.i3d_default):
            continue

        try:
            if export.converter is not None:
                value = export.converter(value)
        except (TypeError, ValueError) as error:
            if on_error is None:
                raise

            on_error(source, error)
            continue

        yield ResolvedAttribute(source=source, target=export.target, name=export.i3d_name, value=value)
