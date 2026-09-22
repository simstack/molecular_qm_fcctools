"""vb_spectra must import nested FCC helpers at module scope.

A logging-only refactor dropped these names; Gaussian then succeeded and
vb_spectra crashed with NameError on fcc_state / FileStack.
"""

from inspect import getsource
import importlib

import pytest

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
    assert "in_memory=False" not in getsource(fcc.fcc_state)
    assert "in_memory=True" in getsource(fcc.fcc_state)


def test_fc_classes_stages_relative_input_files_and_keeps_sources():
    from molecular_qm_fcctools.nodes import fc_classes as fc_classes_mod

    src = getsource(fc_classes_mod)
    assert "STATE1_FILE = {state1_path}" not in src
    assert "STATE1_FILE" in src
    assert "state1.fcc" in src
    assert "shutil.copy2" in src
    assert "file.unlink()" not in src
    assert "last_stderr" in src


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


def test_spectrum_x_to_nm_converts_ev_and_leaves_nm():
    from types import SimpleNamespace

    import numpy as np
    from simstack.core.artifacts import ArtifactArguments
    from simstack.models import ArtifactModel
    from simstack.models.array_storage import ArrayStorage

    from molecular_qm_fcctools.nodes.spectra_analysis import spectrum_x_to_nm

    energies_ev = np.array([3.1, 3.0, 2.9])
    expected_nm = 1239.84 / energies_ev
    np.testing.assert_allclose(spectrum_x_to_nm(energies_ev), expected_nm)
    np.testing.assert_allclose(spectrum_x_to_nm(expected_nm), expected_nm)

    spectrum = ArrayStorage(name="int_td")
    spectrum.set_array(np.column_stack([energies_ev, np.array([0.1, 1.0, 0.2])]))
    fcc_argument = ArtifactArguments(result=SimpleNamespace(int_td_spectrum=spectrum))
    fcc_argument.fc_classes_input = SimpleNamespace(state_number=1)
    _, state_artifact = rvs.fcc_classes_data(fcc_argument)
    np.testing.assert_allclose(
        [point["frequency"] for point in state_artifact.data["plot_data"]],
        expected_nm,
    )

    all_spectra = ArrayStorage(name="all_spectra")
    all_spectra.set_array(np.array([energies_ev, np.array([0.1, 1.0, 0.2])]))
    child = ArtifactModel(name="state_1", path="none")
    child.data["plot_data"] = [
        {"frequency": float(energy), "intensity": intensity}
        for energy, intensity in zip(energies_ev, [0.1, 1.0, 0.2])
    ]
    plot_argument = ArtifactArguments(result=SimpleNamespace(all_spectra=all_spectra))
    plot_argument.child_artifacts = [child]
    _, full_spectrum = rvs.vb_spectra_plots(plot_argument)
    np.testing.assert_allclose(
        [point["frequency"] for point in full_spectrum.data["plot_data"]],
        expected_nm,
    )
    np.testing.assert_allclose(
        [point["frequency"] for point in child.data["plot_data"]],
        expected_nm,
    )

    already_nm_child = ArtifactModel(name="state_2", path="none")
    already_nm_child.data["plot_data"] = [
        {"frequency": float(wavelength), "intensity": 0.5}
        for wavelength in expected_nm
    ]
    nm_argument = ArtifactArguments(result=SimpleNamespace(all_spectra=all_spectra))
    nm_argument.child_artifacts = [already_nm_child]
    rvs.vb_spectra_plots(nm_argument)
    np.testing.assert_allclose(
        [point["frequency"] for point in already_nm_child.data["plot_data"]],
        expected_nm,
    )

    with pytest.raises(ValueError, match="not unambiguously eV or nm"):
        spectrum_x_to_nm(np.array([10.0, 80.0]))
    with pytest.raises(ValueError, match="positive and finite"):
        spectrum_x_to_nm(np.array([0.0, 3.0]))
