"""vb_spectra must import nested FCC helpers at module scope.

A logging-only refactor dropped these names; Gaussian then succeeded and
vb_spectra crashed with NameError on fcc_state / FileStack.
"""

from inspect import getsource

from molecular_qm_models import Atom, Molecule, QMInput
from molecular_qm_models.basis_set import BasisSet, BasisSetEnum
from molecular_qm_models.density_functional import Functional, FunctionalEnum

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
    assert "formchk_checkpoint" not in getsource(vs)
    assert "gaussian.fchk" in getsource(vs._gaussian_fchk)


def test_fcc_helpers_reject_binary_chk():
    from molecular_qm_fcctools.nodes import fcc

    assert "formatted checkpoint (.fchk)" in getsource(fcc.fcc_state)
    assert "formatted checkpoint (.fchk)" in getsource(fcc.fcc_dipole)
    assert "last_stdout" in getsource(fcc.fcc_state)
    assert "last_stdout" in getsource(fcc.fcc_dipole)
    assert 'kwargs["node_runner"]' in getsource(fcc.fcc_make_plot)
    assert 'kwargs["node_runner"]' in getsource(fcc.fcc_dipole)
    assert "NodeRunner(" not in getsource(fcc.fcc_make_plot)
    assert "NodeRunner(" not in getsource(fcc.fcc_dipole)


def test_vb_spectra_enables_excited_states_toggle_before_td_scan():
    src = getsource(vs.vb_spectra)
    assert 'excited_state_data["excited_states"] = True' in src
    assert 'excited_state_data["states"] = 20' in src
    assert "excited_state_input.states = 20" not in src


def test_qm_input_keeps_td_states_when_excited_states_flag_is_set():
    molecule = Molecule(atoms=[Atom(element="C", x=0.0, y=0.0, z=0.0)])
    ground = QMInput(
        molecule=molecule,
        basis_set=BasisSet(basis_set=BasisSetEnum.Def2_SVP),
        functional=Functional(functional=FunctionalEnum.CAM_B3LYP),
        frequencies=True,
    )
    data = ground.model_dump(exclude={"id"})
    data["excited_states"] = True
    data["frequencies"] = False
    data["states"] = 20
    data["focus_state"] = 1
    excited = QMInput(**data)
    assert excited.states == 20
    assert excited.excited_states is True
