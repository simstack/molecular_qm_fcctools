import copy
import glob
import os
import traceback
from typing import Tuple

import numpy as np

from molecular_qm_models.basis_set import BasisSetModel
from molecular_qm_models.density_functional import FunctionalModel
from simstack.core.simstack_result import SimstackResult
from molecular_qm_gaussian import gaussian
from molecular_qm_models import Molecule, QMResult
from molecular_qm_models.qm_input import QMInput
from simstack.core.context import context
from simstack.core.definitions import TaskStatus
from simstack.core.node import node

from molecular_qm_fcctools.nodes.fcc import fcc_dipole, fcc_make_plot, fcc_state
from molecular_qm_fcctools.nodes.fc_classes import FC_ClassesInput, fc_classes

from simstack.models import ArrayList, IntData, StringData, FloatData

import logging
from simstack.models.files import FileStack
from simstack.models.file_list import FileListIO
from simstack.models.charts_artifact import create_simple_line_chart

logger = logging.getLogger("vb_spectra")

def fix_bounds(
    spc_min: float,
    spc_max: float,
    spectrum_data: np.ndarray,
    *,
    node_runner,
    loop: int,
    task_id=None,
    intensity_floor: float = -0.1,
) -> Tuple[float, float, bool]:
    """
    Adjust spectral bounds based on the current spectrum window.

    Rules (as requested):
      - If there are intensities < intensity_floor, determine whether they occur above or below reference_energy:
          * above reference_energy -> reduce spc_max by delta_energy
          * below reference_energy -> increase spc_min by delta_energy
      - Also check if intensities for low energies are large and positive:
          * if yes -> reduce spc_min by delta_energy
      - Log via node_runner.info(...)
      - Create a line chart and store it on node_runner as node_runner.chart_{loop}

    Returns:
        (new_spc_min, new_spc_max, changed)
    """
    if spectrum_data is None or len(spectrum_data) == 0:
        node_runner.info("fix_bounds: spectrum_data empty; no bound changes")
        return spc_min, spc_max, False


    energies = np.asarray(spectrum_data[:, 0], dtype=float)
    intensities = np.asarray(spectrum_data[:, 1], dtype=float)

    delta_energy = (spc_max - spc_min) / 10
    low_energy_positive_threshold = max(max(intensities), 10)
    node_runner.info(f"low_energy_positive_threshold: {low_energy_positive_threshold} delta_energy: {delta_energy}")

    # Save a chart artifact for this loop
    chart_data = [{"energy": float(e), "intensity": float(i)} for e, i in zip(energies, intensities)]
    chart = create_simple_line_chart(
        chart_data,
        x_key="energy",
        y_key="intensity",
        title=f"Spectrum window (loop {loop})",
        parent_id=None,
    )
    setattr(node_runner, f"chart_{loop}", chart)

    changed = False
    new_min = float(spc_min)
    new_max = float(spc_max)
    reference_energy = (max(energies) + min(energies)) / 2

    low_mask = intensities < intensity_floor
    if np.any(low_mask):
        low_energies = energies[low_mask]
        has_low_below_ref = bool(np.any(low_energies < reference_energy))
        has_low_above_ref = bool(np.any(low_energies > reference_energy))

        if has_low_above_ref:
            new_max = max(reference_energy, new_max - delta_energy)
            changed = True
            node_runner.info(
                f"fix_bounds(loop={loop}): found intensities < {intensity_floor} above reference_energy "
                f"({reference_energy:.6g} eV) -> spcmax {spc_max:.6g} -> {new_max:.6g}"
            )
        if has_low_below_ref:
            new_min = new_min + delta_energy
            changed = True
            node_runner.info(
                f"fix_bounds(loop={loop}): found intensities < {intensity_floor} below reference_energy "
                f"({reference_energy:.6g} eV) -> spcmin {spc_min:.6g} -> {new_min:.6g}"
            )

    # "low energies are large and positive" -> interpret as: near the low-energy end of the window.
    # Use first 20% of the energy span as the "low-energy" region.
    if len(energies) >= 2:
        e_lo = float(np.min(energies))
        e_hi = float(np.max(energies))
        e_cut = e_lo + 0.2 * (e_hi - e_lo)
        low_energy_region = energies <= e_cut
        if np.any(low_energy_region):
            max_low = float(np.max(intensities[low_energy_region]))
            if max_low > low_energy_positive_threshold:
                new_min = max(0.0, new_min - delta_energy)
                changed = True
                node_runner.info(
                    f"fix_bounds(loop={loop}): low-energy intensities are large/positive "
                    f"(max_low={max_low:.6g} > {low_energy_positive_threshold}) -> "
                    f"spcmin {spc_min:.6g} -> {new_min:.6g}"
                )

    # Basic sanity to avoid an invalid window
    if new_min < 0.0:
        new_min = 0.0
    if new_max <= new_min:
        # Nudge max to remain above min (avoids infinite loops due to collapse)
        new_max = new_min + max(delta_energy, 1e-6)
        changed = True
        node_runner.info(
            f"fix_bounds(loop={loop}): window collapsed; nudging spcmax to {new_max:.6g}"
        )

    # "write noderunner.infor to the logs" (typo assumed) -> ensure info lines are written,
    # and also add a compact summary line to the debug log-string collector.
    node_runner.log(
        f"fix_bounds(loop={loop}) summary: spcmin={new_min:.6g}, spcmax={new_max:.6g}, changed={changed}"
    )

    return new_min, new_max, changed

@node
def iterative_refinement(fc_classes_input: FC_ClassesInput, name: StringData,
                         reference_energy_model: FloatData,  **kwargs):
    node_runner = kwargs.get('node_runner', None)
    task_id = kwargs.get("task_id", None)
    fc_classes_copy = FC_ClassesInput(**fc_classes_input.model_dump(exclude={"id"}))
    fc_classes_copy.field_name = name.value
    reference_energy = reference_energy_model.value

    # Convert reference_energy (eV) to nm: λ = 1239.84 / E
    reference_nm = 1239.84 / reference_energy

    # Calculate spc_max: subtract 50nm from wavelength, convert back to eV
    spc_max_nm = max(reference_nm - 50.0, 150.0)
    fc_classes_copy.spcmax = 1239.84 / spc_max_nm

    # Calculate spc_min: add 400nm to wavelength, convert back to eV
    spc_min_nm = reference_nm + 400.0
    fc_classes_copy.spcmin = max(1239.84 / spc_min_nm, 0.0)
    node_runner.info(f"reference_nm: {reference_nm}")

    loop = 0
    delta_energy = 0.1  # eV; tweak if you want more/less aggressive window changes

    while loop < 10:
        loop += 1
        node_runner.info(
            f"loop {loop} reference_nm: {reference_nm} "
            f"spcmin: {fc_classes_copy.spcmin} spcmax: {fc_classes_copy.spcmax}"
        )


        fc_classes_result = fc_classes(fc_classes_copy, **kwargs)
        if not isinstance(fc_classes_result, SimstackResult) or fc_classes_result.status != TaskStatus.COMPLETED:
            return node_runner.fail(
                f"unexpected result in fc_classes {fc_classes_result} [{type(fc_classes_result)}]"
            )

        spectrum_data = fc_classes_result.int_td_spectrum.get_array()
        intensities = spectrum_data[:, 1]
        min_intensity = float(np.min(intensities))
        max_intensity = float(np.max(intensities))
        node_runner.info(f"try: {loop} min_intensity: {min_intensity} max_intensity: {max_intensity}")

        new_min, new_max, changed = fix_bounds(
            float(fc_classes_copy.spcmin),
            float(fc_classes_copy.spcmax),
            spectrum_data,
            node_runner=node_runner,
            loop=loop,
            task_id=task_id,
        )
        fc_classes_copy.spcmin = new_min
        fc_classes_copy.spcmax = new_max

        # If no change was needed, we accept the window.
        if not changed:
            node_runner.result = fc_classes_result
            node_runner.converged = True
            node_runner.info(f"accepted window at loop {loop}: spcmin={new_min} spcmax={new_max}")
            return node_runner.succeed()

    node_runner.converged = False
    return node_runner.succeed()


def _as_qm_result(gaussian_result):
    if isinstance(gaussian_result, SimstackResult):
        gaussian_result = gaussian_result.result
    if not isinstance(gaussian_result, QMResult):
        raise TypeError(f"gaussian returned {type(gaussian_result)}, expected QMResult")
    return gaussian_result


def _gaussian_fchk(qm_result, task_id):
    fchk_file = qm_result.files.find(r"gaussian\.fchk$")
    if fchk_file is None:
        raise ValueError(
            f"task_id: {task_id} gaussian result has no gaussian.fchk"
        )
    return fchk_file


@node
async def vb_spectra(qm_input: QMInput, excited_state_functional_input: FunctionalModel,
                     excited_state_basis_input: BasisSetModel,
                     protocol_name: StringData,
                     spc_low: FloatData, spc_high: FloatData,
                     fc_classes_input: FC_ClassesInput, **kwargs) -> SimstackResult:
    """

    vb_spectra performs
    1) an initial calculation of the first 20 excited states of the molecule
    2) checks roughly how many states are needed to match the experimental spectrum
    3) compute excited state spectra for all relevant focus states

    Args:
        qm_input (QMInput): the input parameters for the ground state calculation.
        excited_state_functional_input (QMInput): the input parameters for the ground state calculation.
        excited_state_basis_input (BasisSetModel): the basis set for the excited state calculation.
        protocol_name (StringData): the name of the protocol to use for the calculation.
        spc_low (FloatData): the lower threshold for the spectrum
        spc_high (FloatData): the upper threshold for the spectrum
        fc_classes_input (FC_ClassesInput): the input parameters for the force field calculation.

    Returns:
        SimstackResult: the result of the calculation.

    SimstackResult:
        all_spectra (ArrayList): a list of spectra for each state.

    Called Nodes: gaussian, fcc_state, fcc_dipole, fc_classes
    """
    node_runner = kwargs.get('node_runner', None)
    task_id = kwargs.get("task_id", None)
    try:
        if not qm_input.molecule.formula:
            qm_input.molecule.make_formula()
        if not qm_input.molecule.formula:
            raise ValueError("molecule.formula is missing and could not be computed")
        node_runner.custom_name = protocol_name.value + "." + qm_input.molecule.formula
        excited_state_functional = excited_state_functional_input.functional
        excited_state_basis = excited_state_basis_input.basis_set

        node_runner.log(f"starting vb_spectra for {qm_input.molecule.formula}")
        node_runner.log(f"excited_state_functional: {excited_state_functional} excited_state_basis: {excited_state_basis}")
        node_runner.custom_name = qm_input.molecule.formula

        node_runner.log(f"starting ground state optimization")
        node_runner.info(f"starting gs optimization")
        input_data = qm_input.model_dump()
        del input_data['id']
        ground_state_input = QMInput(**input_data)
        ground_state_input.states = 0
        gaussian_kwargs = copy.deepcopy(kwargs)
        gaussian_kwargs["custom_name"] = "ground_state." + qm_input.molecule.formula
        optimization_result = _as_qm_result(await gaussian(ground_state_input, **gaussian_kwargs))
        if optimization_result.final_structure is None:
            raise ValueError("gaussian ground-state result has no final_structure")

        optimized_geometry = Molecule.from_molecule(optimization_result.final_structure)
        fchk_file = _gaussian_fchk(optimization_result, task_id)
        ground_state_fcc_file = fcc_state(fchk_file, IntData(value=0), **kwargs)

        node_runner.info(f"ground_state_fcc_file: {str(ground_state_fcc_file)}")

        # QMInput zeros `states` whenever excited_states is False (including on
        # later field assignment). Build the TD input in one constructor call.
        excited_state_data = dict(input_data)
        excited_state_data["molecule"] = optimized_geometry
        excited_state_data["basis_set"] = excited_state_basis
        excited_state_data["functional"] = excited_state_functional
        excited_state_data["excited_states"] = True
        excited_state_data["frequencies"] = False
        excited_state_data["states"] = 20
        excited_state_data["focus_state"] = 1
        excited_state_input = QMInput(**excited_state_data)

        node_runner.log(f"starting excited state calculation for {excited_state_input.states} states")
        gaussian_kwargs["custom_name"] = "excited_state_scan." + qm_input.molecule.formula
        excited_state_gaussian_result = _as_qm_result(
            await gaussian(excited_state_input, **gaussian_kwargs)
        )

        node_runner.excited_state_gaussian_result = excited_state_gaussian_result
        excited_states_table = excited_state_gaussian_result.excited_states
        excited_states_energy = []
        states_to_calculate = 0
        max_exp = fc_classes_input.spcmax
        node_runner.log(f"Bound on excited states: {max_exp}")
        for index, row in enumerate(excited_states_table.row):
            node_runner.log(f"      excited state {index}: {row['energy_ev']} eV {row['energy_nm']} nm")
            excited_states_energy.append(row['energy_ev'])
            if row['energy_ev'] < max_exp:
                states_to_calculate = index + 1

        node_runner.log(f"states_to_calculate: {states_to_calculate} with threshold {max_exp} eV")
        spectra_arrays = ArrayList()
        max_target_states = min(states_to_calculate + 1, 6)
        for focus_state in range(1, max_target_states):
            node_runner.log(f"starting excited state calculation for focus state {focus_state}")

            excited_state_data["states"] = focus_state + 2
            excited_state_data["focus_state"] = focus_state
            excited_state_input = QMInput(**excited_state_data)

            state_number = IntData(value=focus_state)
            gaussian_kwargs["custom_name"] = "excited_state_scan." + qm_input.molecule.formula + f".state_{focus_state}"
            excited_state_gaussian_result = _as_qm_result(
                await gaussian(excited_state_input, **gaussian_kwargs)
            )
            fchk_file = _gaussian_fchk(excited_state_gaussian_result, task_id)
            excited_state_fcc_file = fcc_state(fchk_file, state_number, **kwargs)
            excited_state_dipole_file = fcc_dipole(fchk_file, state_number, **kwargs)

            input_list = FileListIO()
            input_list.file_list.append(ground_state_fcc_file)
            input_list.file_list.append(excited_state_fcc_file)
            input_list.file_list.append(excited_state_dipole_file)

            if protocol_name.value == "P1":
                fc_classes_copy = FC_ClassesInput(**fc_classes_input.model_dump(exclude={"id"}))
                fc_classes_copy.spcmin = max(excited_states_energy[focus_state - 1] - spc_low.value, 0.0)
                fc_classes_copy.spcmax = excited_states_energy[focus_state - 1] + spc_high.value
                node_runner.info(f"spcmin: {fc_classes_copy.spcmin} spcmax: {fc_classes_copy.spcmax}")
                fc_classes_copy.file_list_io = input_list
                fc_classes_copy.state_number = focus_state

                fc_classes_result = fc_classes(fc_classes_copy, **kwargs)
                if not isinstance(fc_classes_result, SimstackResult) or fc_classes_result.status != TaskStatus.COMPLETED:
                    return node_runner.fail(f"unexpected result in fc_classes {fc_classes_result} [{type(fc_classes_result)}]")
                spectra_arrays.append(fc_classes_result.int_td_spectrum)

            elif protocol_name.value == "P2":
                fc_classes_input.file_list_io = input_list
                fc_classes_input.state_number = focus_state
                reference_energy_model = FloatData(value=excited_states_energy[focus_state - 1])
                iterative_refinement_result = iterative_refinement(fc_classes_input=fc_classes_input,
                                                                   name=StringData(field_name="molecule_name",value=qm_input.name),
                                                                   reference_energy_model=reference_energy_model, **kwargs)
                if iterative_refinement_result.converged:
                    spectra_arrays.append(iterative_refinement_result.result.int_td_spectrum)
                else:
                    node_runner.log(f"iterative_refinement failed for focus state {focus_state}")

        node_runner.log(f"finished processing {max_target_states} excited states")
        node_runner.log(f"making plots")
        spectra_plot_result = fcc_make_plot(spectra_arrays, **kwargs)

        if not isinstance(spectra_plot_result, SimstackResult):
            raise RuntimeError("task_id: {task:id} result in fcc_make_plot {spectra_plot_result} [{type(spectra_plot_result)}]")
        node_runner.all_spectra = spectra_plot_result.all_spectra
        return node_runner.succeed()

    except Exception as e:
        tb_str = traceback.format_exc()
        node_runner.error_message = f"vb_spectra error: {str(e)} {tb_str}"
        raise e
    finally:
        files_dict = {}
        # Add any .out and .err files that match the job pattern
        for out_file in glob.glob("*.log"):
            files_dict[f"{out_file}"] = out_file
        for out_file in glob.glob("*.out"):
            files_dict[f"{out_file}"] = out_file
        for err_file in glob.glob("*.err"):
            files_dict[f"{err_file}"] = err_file

        for key, file_path in files_dict.items():
            if os.path.exists(file_path):
                file_stack = FileStack.from_local_file(file_path, in_memory=False, is_hashable=True, secure_source=True)
                await context.db.save(file_stack)  # Save the file stack to the database
                node_runner.info_files.append(file_stack)