"""vb_spectra must import nested FCC helpers at module scope.

A logging-only refactor dropped these names; Gaussian then succeeded and
vb_spectra crashed with NameError on fcc_state / FileStack.
"""

from inspect import getsource, signature

from molecular_qm_fcctools.nodes import vibrational_spectra as vs


def test_vb_spectra_defines_nested_node_helpers():
    for name in (
        "ArrayList",
        "FileListIO",
        "FileStack",
        "IntData",
        "fcc_dipole",
        "fcc_make_plot",
        "fcc_state",
    ):
        assert hasattr(vs, name), name
    assert "formchk_checkpoint" in getsource(vs._formatted_checkpoint)
    params = list(signature(vs._formatted_checkpoint).parameters.keys())
    assert params == ["qm_result", "kwargs"]


def test_fcc_helpers_reject_binary_chk():
    from molecular_qm_fcctools.nodes import fcc

    assert "formatted checkpoint (.fchk)" in getsource(fcc.fcc_state)
    assert "formatted checkpoint (.fchk)" in getsource(fcc.fcc_dipole)
    assert "last_stdout" in getsource(fcc.fcc_state)
    assert "last_stdout" in getsource(fcc.fcc_dipole)
