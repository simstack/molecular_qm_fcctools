"""FCclasses3 spectrum calculation node."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from molecular_qm_fcctools.lib.file_utils import collect_outputs, command_string
from molecular_qm_fcctools.models.fcclasses_input import FCClassesInput, FCClassesMethod
from simstack.core.node import node
from simstack.core.simstack_result import SimstackResult
from simstack.models.array_storage import ArrayStorage
from simstack.models.files import FileStack

logger = logging.getLogger(__name__)


@node
async def fcclasses3(fc_classes_input: FCClassesInput, **kwargs) -> SimstackResult:
    """
    Run ``fcclasses3`` for a vibronic spectrum calculation.

    Expects ``fc_classes_input.file_list_io`` with exactly three files:
    state1, state2, and ELDIP.

    Returns:
        SimstackResult with TD/TI spectrum ArrayStorage attributes when present,
        plus collected output FileStacks on ``files``.
    """
    node_runner = kwargs["node_runner"]
    local_paths: list[Path] = []

    try:
        node_runner.custom_name = f"state{fc_classes_input.state_number}"
        file_list_io = fc_classes_input.file_list_io
        if file_list_io is None or not file_list_io.file_list:
            return node_runner.fail("file_list_io with three files is required")

        file_list = file_list_io.file_list
        if len(file_list) != 3:
            return node_runner.fail("input file list must have exactly 3 files")

        local_dir = Path(".")
        state1_path = Path(file_list[0].get(local_dir))
        state2_path = Path(file_list[1].get(local_dir))
        eldip_path = Path(file_list[2].get(local_dir))
        local_paths = [state1_path, state2_path, eldip_path]

        with open("fcc.inp", "w", encoding="utf-8") as handle:
            handle.write(fc_classes_input.input_file())
            handle.write(f"STATE1_FILE = {state1_path.name}\n")
            handle.write(f"STATE2_FILE = {state2_path.name}\n")
            handle.write(f"ELDIP_FILE = {eldip_path.name}\n")

        node_runner.info_files.append(
            FileStack.from_local_file(
                "fcc.inp", in_memory=True, is_hashable=True, secure_source=True
            )
        )

        ok = node_runner.subprocess(
            "fcclasses3", command_string(["fcclasses3", "fcc.inp"])
        )
        if not Path("fcc.out").exists():
            return node_runner.fail("fcc.out not found")

        collect_outputs(node_runner, ["fcc.out"])
        if not ok:
            return node_runner.fail("fcclasses3 failed")

        method = fc_classes_input.method
        spectrum_keys = (
            ["Int_TD", "LS_TD"]
            if method == FCClassesMethod.TD
            else ["Int_TI", "LS_TI"]
        )
        collected_files: list[FileStack] = []
        for name in spectrum_keys:
            dat_name = f"spec_{name}.dat"
            if not Path(dat_name).exists():
                return node_runner.fail(f"{dat_name} not found")

            spectrum_data = np.loadtxt(dat_name)
            storage = ArrayStorage(name=f"spec_{name}_{fc_classes_input.state_number}")
            storage.set_array(spectrum_data)
            setattr(node_runner, f"{name.lower()}_spectrum", storage)

            renamed = f"spec_{name}_{fc_classes_input.state_number}.dat"
            if not node_runner.subprocess(
                f"copy_{name}", command_string(["cp", dat_name, renamed])
            ):
                return node_runner.fail(f"could not copy to {renamed}")
            collected_files.extend(collect_outputs(node_runner, [renamed]))

        node_runner.files = collected_files
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in fcclasses3: {e}")
    finally:
        for path in local_paths:
            if path.exists() and path.is_file() and path.parent.resolve() == Path.cwd():
                # Only remove copies that landed in cwd with distinct names if needed;
                # leave caller-owned paths alone when they already lived in cwd.
                pass
