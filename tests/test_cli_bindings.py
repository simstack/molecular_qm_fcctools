"""Smoke checks for fcc_tools / FCclasses3 CLI argument builders."""

from molecular_qm_fcctools.models.fcc_tools_input import (
    ConvoluteRRInput,
    ConvoluteRRType,
    GenFccDipfileInput,
    GenFccStateInput,
    ReconvoluteTDInput,
)
from molecular_qm_fcctools.models.fcclasses_input import FCClassesInput


def test_gen_fcc_state_cli_args():
    opts = GenFccStateInput(output_file="out.fcc", write_modes=True)
    args = opts.cli_args("mol.fchk")
    assert args[:3] == ["gen_fcc_state", "-i", "mol.fchk"]
    assert "-o" in args and "out.fcc" in args
    assert "-write-modes" in args


def test_gen_fcc_dipfile_cli_args():
    opts = GenFccDipfileInput(initial_state=0, final_state=1, eldip_file="x.eldip")
    args = opts.cli_args("mol.fchk")
    assert args[0] == "gen_fcc_dipfile"
    assert args[args.index("-Si") + 1] == "0"
    assert args[args.index("-Sf") + 1] == "1"
    assert args[args.index("-oe") + 1] == "x.eldip"


def test_reconvolute_td_cli_args():
    opts = ReconvoluteTDInput(hwhm=0.1, fcc_out="fcc.out")
    args = opts.cli_args()
    assert args[0] == "reconvolute_TD"
    assert args[args.index("-hwhm") + 1] == "0.1"


def test_convolute_rr_cli_args():
    opts = ConvoluteRRInput(spectrum_type=ConvoluteRRType.TWO_D, incident_freq=25000.0)
    args = opts.cli_args()
    assert args[args.index("-type") + 1] == "2D"
    assert args[args.index("-wI") + 1] == "25000.0"


def test_fcclasses_input_file_contains_keys():
    text = FCClassesInput().input_file()
    assert "PROPERTY" in text
    assert "MODEL" in text
    assert "METHOD" in text
