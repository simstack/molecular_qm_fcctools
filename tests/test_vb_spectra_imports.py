"""vb_spectra must import nested FCC helpers at module scope.

A logging-only refactor dropped these names; Gaussian then succeeded and
vb_spectra crashed with NameError on fcc_state / FileStack.
"""

from inspect import getsource
import importlib

from molecular_qm_models import Atom, Molecule, QMInput
from molecular_qm_models.basis_set import BasisSet, BasisSetEnum
from molecular_qm_models.density_functional import Functional, FunctionalEnum

from molecular_qm_fcctools.nodes import run_vb_spectra as rvs
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


def test_vb_spectra_p2_uses_molecule_formula_for_iterative_refinement_name():
    src = getsource(vs.vb_spectra)
    assert "qm_input.name" not in src
    assert "name" not in QMInput.model_fields
    assert "qm_input.molecule.formula" in src


def test_iterative_refinement_persists_converged_as_boolean_data():
    """Raw bools and nested SimstackResult are dropped; a lone chart then unwraps."""
    src = getsource(vs.iterative_refinement)
    assert "node_runner.converged = True" not in src
    assert "node_runner.converged = False" not in src
    assert 'BooleanData(field_name="converged"' in src
    assert "node_runner.int_td_spectrum" in src
    caller = getsource(vs.vb_spectra)
    assert "iterative_refinement_result.result.int_td_spectrum" not in caller
    assert "isinstance(iterative_refinement_result, SimstackResult)" in caller
    assert "iterative_refinement_result.converged.value" in caller


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


def test_fcc_classes_data_uses_importable_function_mapping():
    src = getsource(rvs.init_artifacts)
    assert "get_module_path" not in src
    assert 'f"{__name__}.fcc_classes_data"' in src
    assert 'f"{__name__}.vb_spectra_plots"' in src
    assert r".*\.vb_spectra\.(iterative_refinement|fc_classes)$" in src


def test_legacy_examples_path_imports_fcc_classes_data():
    module = importlib.import_module(
        "examples.science.electronic_structure.spectra.run_vb_spectra"
    )
    assert module.fcc_classes_data is rvs.fcc_classes_data
    assert module.vb_spectra_plots is rvs.vb_spectra_plots
