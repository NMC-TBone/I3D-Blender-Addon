from __future__ import annotations  # Enables python 4.0 annotation typehints fx. class self-referencing

import logging
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import bpy
from addon_utils import module_bl_info
from bpy_extras.io_utils import axis_conversion

from . import debugging, xml_i3d
from .export_core.ctx import ExportContext
from .export_core.errors import ExportUserError
from .export_core.pipeline import run_export
from .export_core.reporting import report_messages_to_operator
from .utility import get_fs_data_path

logger = logging.getLogger(__name__)
logger.debug(f"Loading: {__name__}")

BINARIZER_TIMEOUT_IN_SECONDS = 30


def export_blend_to_i3d(operator, context: bpy.types.Context, filepath: str, axis_forward, axis_up, settings) -> dict:
    export_data: dict = {}
    debugging.addon_console_handler.setLevel(logging.INFO)
    if operator.verbose_output:
        debugging.addon_console_handler.setLevel(logging.DEBUG)
    else:
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)

    log_ctx = nullcontext()
    if operator.log_to_file:
        filename = filepath[: -len(xml_i3d.FILE_EXT)] + debugging.export_log_file_ending
        log_ctx = debugging.export_log_file(filename)

    time_start = time.time()

    # Wrap everything in a try/catch to handle addon breaking exceptions and also get them in the log file
    ctx = None
    try:
        with log_ctx:
            addon_version = module_bl_info(sys.modules[__package__])["version"]
            logger.info(f"Blender version is: {bpy.app.version_string}")
            logger.info(f"I3D Exporter version is: {addon_version}")
            logger.info(f"Exporting to {filepath}")

            depsgraph = context.evaluated_depsgraph_get()
            ctx = ExportContext.create(
                is_dev=addon_version == (0, 0, 0),
                operator=operator,
                filepath=filepath,
                depsgraph=depsgraph,
                scene=context.scene,
                conversion_matrix=axis_conversion(to_forward=axis_forward, to_up=axis_up).to_4x4(),
                settings=settings,
            )

            # Log export settings
            logger.info("Exporter settings:")
            for setting, value in ctx.settings.items():
                logger.info(f"  {setting}: {value}")

            run_export(ctx, context=context)

            if operator.binarize_i3d:
                _binarize_i3d(filepath, operator, logger)

            report_messages_to_operator(ctx, limit=10)

    # Global try/catch exception handler. So that any unspecified exception will still end up in the log file
    except ExportUserError as e:
        logger.warning("Export aborted: %s", e)
        if ctx is not None:
            report_messages_to_operator(ctx, limit=10)
        export_data["success"] = False
    except Exception as e:
        logger.exception("Export crashed due to an unexpected error: %s", e)
        if ctx is not None:
            report_messages_to_operator(ctx, limit=10)
        export_data["success"] = False
        if ctx is not None and ctx.is_dev:
            raise  # In dev mode, re-raise the exception for debugging
    else:
        export_data["success"] = True
    finally:
        export_data["time"] = time.time() - time_start
        logger.info(f"Export took {export_data['time']:.3f} seconds")
        debugging.addon_console_handler.setLevel(debugging.addon_console_handler_default_level)

    return export_data


def _binarize_i3d(filepath: str, operator, logger: logging.Logger):
    """Tries to binarize the exported I3D file"""
    if not (converter_path := bpy.context.preferences.addons[__package__].preferences.i3d_converter_path):
        logger.error("No i3dConverter path set in preferences. Skipping binarization.")
        return
    converter_exe_path = Path(converter_path)
    if not converter_exe_path.exists():
        logger.error(f"i3dConverter.exe path does not exist: {converter_exe_path!r}. Skipping binarization.")
        return
    if not converter_exe_path.is_file():
        logger.error(f"i3dConverter.exe path is not a file: {converter_exe_path!r}. Skipping binarization.")
        return
    if not (game_path := get_fs_data_path(as_path=True).parent):
        logger.error("No game data path set in preferences. Skipping binarization.")
        return

    logger.info(f"Starting binarization of {filepath!r}")
    try:
        conversion_result = subprocess.run(
            args=[str(converter_exe_path), "-in", str(filepath), "-out", str(filepath), "-gamePath", f"{game_path}/"],
            timeout=BINARIZER_TIMEOUT_IN_SECONDS,
            check=False,  # inspect stdout even on non-zero exit code
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        raw = conversion_result.stdout or ""
        lines = [ln.rstrip("\r\n") for ln in raw.splitlines() if ln.strip()]

        # Some lines could be repeated multiple times, collapse them
        collapsed: list[str] = []
        last = None
        for ln in lines:
            if ln != last:
                collapsed.append(ln)
            last = ln

        _unimportant = ("render system", "driver: null", "nullconsoledevice initialized", "i3d contains non-binary")

        def _emit(line: str) -> None:
            msg = line.rstrip()
            low = msg.lower().strip()
            if any(s in low for s in _unimportant):
                return
            if low.startswith("error:"):
                logger.error(f"  {msg}", stacklevel=2)
            elif low.startswith("warning:"):
                logger.warning(msg, stacklevel=2)
            else:
                logger.info(f"   {msg}", stacklevel=2)

        for line in collapsed:
            _emit(line)

        if conversion_result.returncode != 0:  # Non-zero exit
            operator.report({"ERROR"}, "Binarization failed. See log for details.")
            return
        logger.info(f'Finished binarization of "{filepath}"')
        operator.report({"INFO"}, "Binarization completed successfully.")

    except FileNotFoundError:
        logger.error(f"Invalid path to i3dConverter.exe: {converter_exe_path!r}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"i3dConverter.exe timed out after {BINARIZER_TIMEOUT_IN_SECONDS} seconds. Output: {e.output!r}")
        operator.report({"ERROR"}, "Binarization timed out. See log for details.")
    except Exception:
        logger.exception("Unexpected error while running i3dConverter.exe")
        operator.report({"ERROR"}, "Binarization crashed. See log for details.")
