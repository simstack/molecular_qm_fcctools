"""fcc_tools nodes: gen_fcc_state / gen_fcc_dipfile / reconvolute_* / convolute_RR."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from molecular_qm_fcctools.lib.file_utils import (
    collect_outputs,
    command_string,
    default_eldip_output,
    default_state_output,
    materialize_file_stack,
)
from molecular_qm_fcctools.models.fcc_tools_input import (
    ConvoluteRRInput,
    ConvoluteRRType,
    GenFccDipfileInput,
    GenFccStateInput,
    ReconvoluteTDInput,
    ReconvoluteTIInput,
)
from simstack.core.node import node
from simstack.core.simstack_result import SimstackResult
from simstack.models.files import FileStack

logger = logging.getLogger(__name__)


def _cleanup(path: Path | None) -> None:
    if path is not None and path.exists() and path.is_file():
        path.unlink()


@node
async def gen_fcc_state(
    file_stack: FileStack,
    options: Optional[GenFccStateInput] = None,
    **kwargs,
) -> SimstackResult:
    """
    Run ``gen_fcc_state`` to build an FCclasses state file from a QM output.

    Returns:
        SimstackResult with ``file_stack`` pointing at the generated ``.fcc`` state file.
    """
    node_runner = kwargs["node_runner"]
    options = options or GenFccStateInput()
    cleanup: Path | None = None

    try:
        input_path, cleanup = materialize_file_stack(file_stack)
        node_runner.info(f"Running gen_fcc_state on {input_path.name}")

        args = options.cli_args(str(input_path.name))
        ok = node_runner.subprocess("gen_fcc_state", command_string(args))
        if not ok:
            return node_runner.fail("gen_fcc_state failed")

        out_name = default_state_output(input_path, options.output_file)
        if not Path(out_name).exists():
            return node_runner.fail(f"State file {out_name} not found")

        stacks = collect_outputs(node_runner, [out_name])
        node_runner.file_stack = stacks[0]
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in gen_fcc_state: {e}")
    finally:
        _cleanup(cleanup)


@node
async def gen_fcc_dipfile(
    file_stack: FileStack,
    options: Optional[GenFccDipfileInput] = None,
    **kwargs,
) -> SimstackResult:
    """
    Run ``gen_fcc_dipfile`` to build ELDIP (and optionally MAGDIP/NAC) files.

    Returns:
        SimstackResult with ``file_stack`` for the primary eldip file and
        ``files`` for any additional MagDip/NAC outputs.
    """
    node_runner = kwargs["node_runner"]
    options = options or GenFccDipfileInput()
    cleanup: Path | None = None

    try:
        input_path, cleanup = materialize_file_stack(file_stack)
        node_runner.info(f"Running gen_fcc_dipfile on {input_path.name}")

        args = options.cli_args(str(input_path.name))
        ok = node_runner.subprocess("gen_fcc_dipfile", command_string(args))
        if not ok:
            return node_runner.fail("gen_fcc_dipfile failed")

        eldip_name = default_eldip_output(input_path, options.eldip_file)
        extras: list[str] = []
        if options.magdip_file:
            extras.append(options.magdip_file)
        else:
            maybe_mag = f"{input_path.stem}.magdip"
            if Path(maybe_mag).exists():
                extras.append(maybe_mag)
        if options.nac_file:
            extras.append(options.nac_file)
        elif options.write_nac:
            maybe_nac = f"{input_path.stem}.nac"
            if Path(maybe_nac).exists():
                extras.append(maybe_nac)

        primary = collect_outputs(node_runner, [eldip_name])
        node_runner.file_stack = primary[0]
        if extras:
            node_runner.files = collect_outputs(node_runner, extras, required=False)
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in gen_fcc_dipfile: {e}")
    finally:
        _cleanup(cleanup)


@node
async def reconvolute_td(
    corr_file: FileStack,
    options: Optional[ReconvoluteTDInput] = None,
    fcc_out: Optional[FileStack] = None,
    **kwargs,
) -> SimstackResult:
    """
    Run ``reconvolute_TD`` to regenerate a TD spectrum with a new broadening.

    ``corr_file`` should be the TD correlation function (typically ``corr.dat``).
    Optionally pass ``fcc_out`` so the tool can recover the energy shift.
    """
    node_runner = kwargs["node_runner"]
    options = options or ReconvoluteTDInput()
    cleanups: list[Path | None] = []

    try:
        corr_path, cleanup = materialize_file_stack(
            corr_file, preferred_name=options.corr_file or "corr.dat"
        )
        cleanups.append(cleanup)
        options.corr_file = corr_path.name

        if fcc_out is not None:
            fcc_path, cleanup = materialize_file_stack(
                fcc_out, preferred_name=options.fcc_out or "fcc.out"
            )
            cleanups.append(cleanup)
            options.fcc_out = fcc_path.name

        node_runner.info(
            f"Running reconvolute_TD hwhm={options.hwhm} brd={options.broadening}"
        )
        ok = node_runner.subprocess(
            "reconvolute_TD", command_string(options.cli_args())
        )
        if not ok:
            return node_runner.fail("reconvolute_TD failed")

        # Upstream writes spectrum data files; collect common TD names if present.
        candidates = [
            "spec_Int_TD.dat",
            "spec_LS_TD.dat",
            "Int_TD.dat",
            "LS_TD.dat",
        ]
        found = [name for name in candidates if Path(name).exists()]
        if not found:
            return node_runner.fail("reconvolute_TD produced no recognized spectrum files")

        stacks = collect_outputs(node_runner, found)
        node_runner.file_stack = stacks[0]
        node_runner.files = stacks
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in reconvolute_td: {e}")
    finally:
        for path in cleanups:
            _cleanup(path)


@node
async def reconvolute_ti(
    spectrum_file: FileStack,
    options: Optional[ReconvoluteTIInput] = None,
    **kwargs,
) -> SimstackResult:
    """
    Run ``reconvolute_TI`` to regenerate a TI spectrum with a new broadening.

    ``spectrum_file`` is typically ``Bin_Spectrum.dat`` from an FCclasses3 TI run.
    """
    node_runner = kwargs["node_runner"]
    options = options or ReconvoluteTIInput()
    cleanup: Path | None = None

    try:
        spec_path, cleanup = materialize_file_stack(
            spectrum_file, preferred_name=options.spectrum_file or "Bin_Spectrum.dat"
        )
        options.spectrum_file = spec_path.name

        node_runner.info(
            f"Running reconvolute_TI hwhm={options.hwhm} brd={options.broadening}"
        )
        ok = node_runner.subprocess(
            "reconvolute_TI", command_string(options.cli_args())
        )
        if not ok:
            return node_runner.fail("reconvolute_TI failed")

        candidates = [
            "spec_Int_TI.dat",
            "spec_LS_TI.dat",
            "Int_TI.dat",
            "LS_TI.dat",
            "Bin_Spectrum.dat",
        ]
        found = [name for name in candidates if Path(name).exists()]
        # Always include the input if nothing else appeared (tool may overwrite in place).
        if not found:
            found = [spec_path.name]

        stacks = collect_outputs(node_runner, found)
        node_runner.file_stack = stacks[0]
        node_runner.files = stacks
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in reconvolute_ti: {e}")
    finally:
        _cleanup(cleanup)


@node
async def convolute_rr(
    spectrum_file: FileStack,
    options: Optional[ConvoluteRRInput] = None,
    **kwargs,
) -> SimstackResult:
    """
    Run ``convolute_RR`` to broaden a resonance-Raman stick / 2D spectrum.

    For ``1D`` the default input is ``RR_Spectrum_VertE.dat``;
    for ``2D`` it is ``RR_Spectrum_2D.dat``.
    """
    node_runner = kwargs["node_runner"]
    options = options or ConvoluteRRInput()
    cleanup: Path | None = None

    try:
        default_name = (
            "RR_Spectrum_2D.dat"
            if options.spectrum_type == ConvoluteRRType.TWO_D
            else "RR_Spectrum_VertE.dat"
        )
        spec_path, cleanup = materialize_file_stack(
            spectrum_file, preferred_name=options.spectrum_file or default_name
        )
        options.spectrum_file = spec_path.name

        node_runner.info(
            f"Running convolute_RR type={options.spectrum_type.value} "
            f"hwhm={options.hwhm}"
        )
        ok = node_runner.subprocess(
            "convolute_RR", command_string(options.cli_args())
        )
        if not ok:
            return node_runner.fail("convolute_RR failed")

        candidates = [
            "RR_Spectrum.dat",
            "RR_convoluted.dat",
            spec_path.name,
        ]
        found = [name for name in candidates if Path(name).exists()]
        if not found:
            return node_runner.fail("convolute_RR produced no recognized output files")

        stacks = collect_outputs(node_runner, found)
        node_runner.file_stack = stacks[0]
        node_runner.files = stacks
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error in convolute_rr: {e}")
    finally:
        _cleanup(cleanup)
