"""vb_spectra must import nested FCC helpers at module scope.

A logging-only refactor dropped these names; Gaussian then succeeded and
vb_spectra crashed with NameError on fcc_state / FileStack.
"""

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
