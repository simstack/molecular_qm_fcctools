from datetime import datetime
from pathlib import Path
import asyncio
import sys
import types
from typing import Any

from matplotlib.pyplot import xlabel
from numpy import ndarray
from odmantic import ObjectId

from molecular_qm_models import Molecule
from molecular_qm_util import compute_iupac_name, smiles_to_molecule
from simstack.core.artifacts import register_artifact_mapping, ArtifactArguments
from simstack.core.context import context

from molecular_qm_fcctools import make_multi_line_chart
from molecular_qm_fcctools.nodes.fc_classes import FC_ClassesInput
from molecular_qm_fcctools.nodes.spectra_analysis import process_experimental_spectrum, spectrum_x_to_nm
from molecular_qm_fcctools.nodes.vibrational_spectra import vb_spectra
from molecular_qm_models.basis_set import BasisSet, BasisSetEnum, BasisSetModel
from molecular_qm_models.density_functional import FunctionalEnum, Functional, FunctionalModel
from molecular_qm_models.dispersion_correction import DispersionCorrection, DispersionCorrectionEnum
from molecular_qm_models.qm_input import QMInput

from simstack.core.node import node
from simstack.core.node_runner import NodeRunner
from simstack.core.simstack_result import SimstackResult
from simstack.models import ArtifactMapping, ArtifactModel, FloatData, Parameters, StringData, DataSetTupleSelection, \
    DataSetTuple, DataSetTupleSelectionField, DataSet, DataSetSelection
from simstack.models.array_storage import ArrayStorage
from simstack.models.charts_artifact import ChartArtifactModel, create_multi_series_line_chart
from scipy.interpolate import interp1d

import logging
import numpy as np
from scipy.stats import norm
from scipy.integrate import trapezoid

logger = logging.getLogger(__name__)

def fcc_classes_data(argument: ArtifactArguments):
    """
    Processes and generates artifact data for an FCCLASSES task based on input arguments.

    This function extracts frequency and intensity data from the given artifact arguments,
    computes the 95% frequency range from the provided spectrum, and organizes the result
    into an artifact model. The output includes plot data, frequency range boundaries, and
    logging information.

    
    Parameters:
    argument (ArtifactArguments): The input arguments containing spectrum data and task details.

    Returns:
    ArtifactModel: An artifact model containing the processed spectrum analysis,
    frequency range data, and associated metadata.
    """
    task_id = argument.task_id
    if hasattr(argument, "result") and hasattr(argument.result, "int_td_spectrum"):
        data = argument.result.int_td_spectrum.get_array()
    else:
        logger.error(f"fcc_classes_data: No spectrum data found task_id: {task_id}")
        return None

    wavelengths = spectrum_x_to_nm(data.T[0])
    intensities = data.T[1]
    state_number = argument.fc_classes_input.state_number if argument.fc_classes_input.state_number else 0
    artifact = spectrum_plot_artifact(f"state_{state_number}", wavelengths, intensities)
    
    logger.info(f"Artifact FCCLASSES: task_id: {argument.task_id} state_number: {state_number}")
    logger.info(
        f"Artifact FCCLASSES: task_id: {argument.task_id} 95% wavelength range: "
        f"{artifact.data['xmin']:.3f} to {artifact.data['xmax']:.3f} nm"
    )
    return artifact


def vb_spectra_plots(argument: ArtifactArguments):
    """
    Function to create a plot artifact from the spectra data.
    :param argument: ArtifactArguments containing the spectra data.
    :return: ArtifactModel with the plot data.
    """
    try:
        data_array = argument.result.all_spectra.get_array()
        wavelengths = spectrum_x_to_nm(data_array[0])
        intensities = data_array[1]
        artifact = spectrum_plot_artifact("full_spectrum", wavelengths, intensities)

        artifacts = []
        seen_names = set()
        for child_artifact in argument.child_artifacts:
            logger.info(f"Artifact: task_id: {argument.task_id} Child artifact: {child_artifact.name}")
            plot_data = child_artifact.data.get("plot_data")
            if not plot_data:
                continue
            if child_artifact.name in seen_names:
                continue
            seen_names.add(child_artifact.name)

            child_x = np.array([point["frequency"] for point in plot_data])
            logger.info(f"Artifact: task_id: {argument.task_id} Child artifact range: {child_x[0]} {child_x[-1]}")
            child_intensities = np.array([point["intensity"] for point in plot_data])
            child_wavelengths = spectrum_x_to_nm(child_x)
            artifacts.append(
                spectrum_plot_artifact(child_artifact.name, child_wavelengths, child_intensities)
            )

        artifacts.append(artifact)
        chart_artifact = make_multi_line_chart(artifacts,
                                               chart_title="All spectra",
                                               x_axis_title="Wavelength (nm)",
                                               y_axis_title="Intensity (arb. units)",
                                               x_key="frequency",
                                               y_key="intensity",
                                               task_id=argument.task_id)

        artifacts.append(chart_artifact)
        return artifacts
    except Exception as e:
        logger.exception(f"Error creating plot artifact: task_id: {argument.task_id} {str(e)}")
        return None

def exp_vs_computed_spectra(argument: ArtifactArguments) -> ChartArtifactModel | None:
    try:
        # Get experimental data
        exp_data_array = argument.experimental_spectrum.get_array()
        exp_wavelengths = exp_data_array[0]
        exp_intensities = exp_data_array[1]

        # Get theoretical data and convert from eV to nm
        theory_spectrum = argument.child_artifacts[0].data['plot_data']
        theory_wavelengths = np.array([spectrum['frequency'] for spectrum in theory_spectrum])
        theory_intensities = np.array([spectrum['intensity'] for spectrum in theory_spectrum])
        
        # Sort both spectra by wavelength
        exp_sorted_idx = np.argsort(exp_wavelengths)
        exp_wavelengths = exp_wavelengths[exp_sorted_idx]
        exp_intensities = exp_intensities[exp_sorted_idx]
        
        theory_sorted_idx = np.argsort(theory_wavelengths)
        theory_wavelengths = theory_wavelengths[theory_sorted_idx]
        theory_intensities = theory_intensities[theory_sorted_idx]
        
        # Calculate integrals in wavelength space
        exp_integral = trapezoid(exp_intensities, exp_wavelengths)
        theory_integral = trapezoid(theory_intensities, theory_wavelengths)
        
        # Normalize both spectra to integral = 1.0
        exp_normalized = exp_intensities / exp_integral
        theory_normalized = theory_intensities / theory_integral
        
        # Compute 95% frequency range for experimental data
        exp_freq_range = compute_frequency_range_95_percent(exp_wavelengths, exp_normalized)
        
        # Compute 95% frequency range for theoretical data
        theory_freq_range = compute_frequency_range_95_percent(theory_wavelengths, theory_normalized)
        
        # Create normalized experimental data
        exp_data_normalized = []
        for wavelength, intensity in zip(exp_wavelengths, exp_normalized):
            exp_data_normalized.append({"frequency": wavelength, "intensity": intensity})
        
        exp_artifact = ArtifactModel(name="experimental spectrum (normalized)", path="none")
        exp_artifact.data['plot_data'] = exp_normalized
        exp_artifact.data['xmin'] = exp_freq_range['xmin']
        exp_artifact.data['xmax'] = exp_freq_range['xmax']
        
        
        # Create normalized theoretical data
        theory_data_normalized = []
        for wavelength, intensity in zip(theory_wavelengths, theory_normalized):
            theory_data_normalized.append({"frequency": wavelength, "intensity": intensity})
        
        # theory_artifact = ArtifactModel(name="computed spectrum (normalized)", path="none")
        # theory_artifact.data['plot_data'] = theory_normalized
        # theory_artifact.data['xmin'] = theory_freq_range['xmin']
        # theory_artifact.data['xmax'] = theory_freq_range['xmax']
        #
        # Log information
        logger.info(f"EXP VS THEORY task_id: {argument.task_id} Experimental 95% range: {exp_freq_range['xmin']:.3f} to {exp_freq_range['xmax']:.3f}")
        logger.info(f"EXP VS THEORY task_id: {argument.task_id} Theoretical 95% range: {theory_freq_range['xmin']:.3f} to {theory_freq_range['xmax']:.3f}")

        combined_data = [
            {
                "frequency": wavelength,
                "experimental_spectrum": exp_intensity,
                "computed_spectrum": theory_intensity,
            }
            for wavelength, exp_intensity, theory_intensity in zip(
                exp_wavelengths, exp_normalized, theory_normalized
            )
        ]

        chart = create_multi_series_line_chart(
            data=combined_data,
            x_key="frequency",
            y_keys=["experimental_spectrum", "computed_spectrum"],
            title="Experimental vs Computed Spectrum",
            parent_id=argument.task_id,
        )
        return chart

    except Exception as e:
        logger.exception(f"Error creating compute_spectra_plot task_id: {argument.task_id} {str(e)}")
        return None


def make_summary_table(argument: ArtifactArguments):
    pass


class SampleInput:
    def __init__(self, molecule: Molecule, solvent: StringData):
        self.dispersion_correction = DispersionCorrection(value=DispersionCorrectionEnum.D3)
        self.functional = Functional(functional=FunctionalEnum.CAM_B3LYP, dispersion_correction=self.dispersion_correction)
        self.basis_set = BasisSet(basis_set=BasisSetEnum.B631G)

        self.qm_input = QMInput(
            molecule=molecule,
            charge=0,
            states = 10,
            multiplicity=1,
            functional=self.functional,
            basis_set=self.basis_set,
            solvent=solvent.value,
            optimization=True,
            gradients=False
        )

        self.protocol_name = StringData(field_name="protocol", value="spc_by_state_fixed_states")
        self.spc_low = FloatData(field_name="spc_low", value=0.5)
        self.spc_high = FloatData(field_name="spc_high", value=1.5)
        self.excited_state_functional = FunctionalModel(functional=Functional(functional=FunctionalEnum.CAM_B3LYP),
                                                   dispersion_correction=self.dispersion_correction)
        self.excited_state_basis = BasisSetModel(basis_set=BasisSet(basis_set=BasisSetEnum.B631G))


@node(parameters=Parameters(recompute_artifacts=True))
async def compute_uv_vis_template(molecule:Molecule, experimental_spectrum: ArrayStorage, solvent: StringData, **kwargs) -> SimstackResult:
    """
    Template for computing UV-Vis spectrum for a single molecule.

    Returns:
        SimstackResult: The result of the UV-Vis spectrum computation.
            result (molecular_qm_models.QMResult): The computation result.
    """
    node_runner = NodeRunner("compute_spectra",logger,**kwargs)

    si =  SampleInput(molecule, solvent)
    result = await compute_uv_vis_spectrum(si.qm_input, experimental_spectrum,
                                           si.excited_state_functional,
                                           si.excited_state_basis,
                                           si.protocol_name,
                                           si.spc_low, si.spc_high, **kwargs)

    node_runner.result = result
    return node_runner.succeed()


async def compute_spectra_job() -> SimstackResult:
    dataset_id = ObjectId("697a4dcb2cc829b79de6a174")
    dataset = await context.db.find_one(DataSet, DataSet.id == dataset_id)

    dataset_selection = DataSetSelection(field_name="hand-selected",
                                         dataset_id=dataset_id,
                                         dataset_selection_fields = [DataSetTupleSelectionField(section_name="spectra", indices=[0])])
    await context.db.save(dataset_selection)


    water = Molecule.from_sites(
        ["O", "H", "H"],
        [[0.0, 0.0, 0.0], [0.758, 0.586, 0.0], [-0.758, 0.586, 0.0]],
    )
    solvent = StringData(field_name="solvent", value="water")
    si = SampleInput(water, solvent)
    result = await compute_spectra(dataset_selection, si.qm_input,
                                           si.excited_state_functional,
                                           si.excited_state_basis,
                                           si.protocol_name,
                                           si.spc_low, si.spc_high)
    return result

@node
async def clean_spectra_dataset(dataset:DataSet, **kwargs) -> SimstackResult:
    """
    Reset the started and success flags in a spectra dataset.

    Returns:
        SimstackResult: The cleaned dataset.
            result (simstack.models.datasettuple.DataSetTuple): The cleaned dataset.
    """
    node_runner = NodeRunner("clean_dataset",logger,**kwargs)

    spectra_section = dataset["spectra"]
    metadata = dataset.metadata

    metadata.data.update({
        "description": "UV spectra of molecules",
        "source": "PhotoChemCad",
        "created_at": datetime.now(),
        "protocol_name": "NA",
        "basis_set": "NA",
        "functional": "NA",
        "excited_state_basis": "NA",
        "excited_state_functional": "NA",
        "low_spc_threshold": 0.0,
        "high_spc_threshold": 0.0,
    })

    for row in spectra_section:
        row_label, started_flag, success_flag, molecule_name, solvent, molecule, experimental_spectrum = row
        started_flag.real_value = False
        await context.db.save(started_flag)
        success_flag.real_value = False
        await context.db.save(success_flag)


    node_runner.result = dataset
    return node_runner.succeed()

@node(parameters=Parameters(resource="local", queue="default", recompute_artifacts=True))
async def compute_spectra(dataset_selection: DataSetSelection, qm_input: QMInput,
                          excited_state_functional: FunctionalModel, excited_state_basis: BasisSetModel,
                          protocol_name: StringData, spc_low: FloatData, spc_high: FloatData,
                          **kwargs) -> SimstackResult:
    """
    Asynchronously computes the spectra for a given dataset selection by calculating UV-Vis spectra
    for molecules using quantum mechanical calculations. Processes individual molecules, checks
    completeness, and updates the status in the dataset.

    Parameters:
        dataset_selection (DataSetSelection): The dataset selection containing the molecules and
            configurations to process.
        qm_input (QMInput): The quantum mechanical input parameters, including molecule charge,
            states, functional, basis set, and optimization settings.
        excited_state_functional (FunctionalModel): The excited state functional model used for the
            quantum mechanical calculations.
        excited_state_basis (BasisSetModel): The excited state basis set model used for the quantum
            mechanical calculations.
        protocol_name (StringData): The name of the protocol to be used during computation.
        spc_low (FloatData): The lower bound of the spectral range.
        spc_high (FloatData): The upper bound of the spectral range.
        **kwargs: Additional parameters to pass to the node runner.

    Returns:
        SimstackResult: The result of the computation, including the status and any generated results.
            dataset (simstack.models.datasettuple.DataSetTuple): the modified dataset containing the updated status for each molecule.
    """
    node_runner = NodeRunner("compute_spectra", logger, **kwargs)
    try:
        tasks = []
        dataset = await dataset_selection.get_dataset()
        metadata = dataset.metadata
        ex_functional = excited_state_functional.functional.functional
        ex_dispersion = excited_state_functional.functional.dispersion_correction.value

        if metadata.get("protocol_name", "NA") == "NA":
            metadata.data["protocol_name"] = protocol_name.value
            metadata.data["functional"] = str(qm_input.functional.functional)
            metadata.data["dispersion_correction"] = str(qm_input.functional.dispersion_correction.value)
            metadata.data["basis_set"] = str(qm_input.basis_set.basis_set)
            metadata.data["excited_state_functional"] = ex_functional
            metadata.data["ex_state_dispersion_correction"] = ex_dispersion
            metadata.data["low_spc_threshold"] = spc_low.value
            metadata.data["high_spc_threshold"] = spc_high.value
            node_runner.info(f"created new metadata: {metadata.data}")
        else:
            assert metadata.data["protocol_name"] == protocol_name.value, f"Protocol mismatch"
            assert metadata.data["functional"] == str(
                qm_input.functional.functional), f"Functional mismatch"
            assert metadata.data["basis_set"] == str(
                qm_input.basis_set.basis_set), f"Basis set mismatch"
            assert metadata.data["dispersion_correction"] == str(
                qm_input.functional.dispersion_correction.value), f"Dispersion correction mismatch"
            assert metadata.data[
                       "excited_state_functional"] == ex_functional, f"Ex-state functional mismatch"
            assert metadata.data[
                       "ex_state_dispersion_correction"] == ex_dispersion, f"Ex-state dispersion correction mismatch"

        result_section = dataset["results"]
        async for selected_item in dataset_selection.__aiter__(section_name="spectra"):
            row_label, started_flag, success_flag, molecule_name, solvent, molecule, experimental_spectrum = selected_item
            if not molecule.formula:
                molecule.make_formula()
                if not molecule.formula:
                    raise ValueError(
                        f"molecule.formula is missing and could not be computed for {molecule_name.real_value}"
                    )
                await context.db.save(molecule)
            node_runner.info(f"processing: {molecule_name.real_value} molecule.formula is {molecule.formula}")
            # Skip if already completed successfully
            if success_flag.real_value:
                node_runner.info(f"Found already completed: {molecule_name.real_value}")
                #continue

            # Mark as started
            started_flag.real_value = True
            await context.db.save(started_flag)
            success_flag.real_value = False
            await context.db.save(success_flag)

            # Create task for computing spectrum
            # kwargs['parameters'] = Parameters(resource="justus",queue="slurm-queue", recompute_artifacts=True)
            task = compute_uv_vis_spectrum(
                qm_input=QMInput(
                    molecule=molecule,
                    charge=qm_input.charge,
                    states=qm_input.states,
                    excited_states=qm_input.excited_states,
                    multiplicity=qm_input.multiplicity,
                    functional=qm_input.functional,
                    basis_set=qm_input.basis_set,
                    solvent=solvent.real_value,
                    optimization=qm_input.optimization,
                    gradients=qm_input.gradients
                ),
                experimental_spectrum=experimental_spectrum,
                excited_state_functional=excited_state_functional,
                excited_state_basis=excited_state_basis,
                protocol_name=protocol_name,
                spc_low=spc_low,
                spc_high=spc_high,
                **kwargs
            )
            tasks.append((task, success_flag, qm_input, row_label))

        # Wait for all tasks to complete
        node_runner.result = dataset
        if tasks:

            results = await asyncio.gather(*[task for task, _, _, _ in tasks], return_exceptions=True)
            one_job_failed = any(isinstance(result, Exception) for result in results)
            # Process results and update success flags
            for index, (result, success_flag, qm_input, row_label) in enumerate(
                    zip(results, [t[1] for t in tasks], [t[2] for t in tasks], [t[3] for t in tasks])):

                if isinstance(result, Exception):
                    node_runner.error(f"Task for {row_label.real_value} {qm_input.molecule.formula} failed: {result}")
                    success_flag.real_value = False
                else:
                    node_runner.info(f"Task for {row_label.real_value} {qm_input.molecule.formula} completed successfully")
                    success_flag.real_value = True
                    job_id = StringData(field_name="task_id", value=str(result.job_id))
                    await context.db.save(job_id)
                    result_section.append((row_label, result.all_spectra, result.deviation , job_id))

                await context.db.save(success_flag)
            if one_job_failed:
                return node_runner.fail("One or more tasks failed")
        return node_runner.succeed()
    except Exception as e:
        logger.exception(f"Error computing spectra: {str(e)}")
        return node_runner.fail(str(e))


@node(parameters=Parameters(recompute_artifacts=True))
async def fake_compute_uv_vis_spectrum(qm_input: QMInput, experimental_spectrum: ArrayStorage,
                                  excited_state_functional: FunctionalModel,
                                  excited_state_basis: BasisSetModel,
                                  protocol_name: StringData, spc_low: FloatData, spc_high: FloatData,
                                  **kwargs) -> SimstackResult:
    """
    Fake version of compute_uv_vis_spectrum for testing.

    Returns:
        SimstackResult: The result of the fake computation.
            result (molecular_qm_models.Molecule): The molecule object.
    """
    node_runner = NodeRunner("compute_spectra",logger,**kwargs)
    node_runner.result = qm_input.molecule
    node_runner.info(f"running qm_input: {qm_input.molecule.smiles}")
    return node_runner.succeed()

@node(parameters=Parameters(recompute_artifacts=True))
async def compute_uv_vis_spectrum(qm_input: QMInput, experimental_spectrum: ArrayStorage,
                                  excited_state_functional: FunctionalModel,
                                  excited_state_basis: BasisSetModel,
                                  protocol_name: StringData, spc_low: FloatData, spc_high: FloatData,
                                  **kwargs) -> SimstackResult:
    """
    Computes the UV-Vis spectrum based on quantum mechanical input, experimental spectrum data, and
    functional and basis set models for excited states. The function interpolates theoretical and
    experimental spectra, normalizes them, calculates the root mean square deviation (RMSD), and
    stores relevant results.

    Parameters:
    qm_input (QMInput): The input containing quantum mechanical parameters required for calculation.
    experimental_spectrum (ArrayStorage): The experimental spectrum data provided as an array storage.
    excited_state_functional (FunctionalModel): The functional model used for excited state calculations.
    excited_state_basis (BasisSetModel): The basis set model used for excited state calculations.
    protocol_name (StringData): The name of the computational protocol to be utilized.
    spc_low (FloatData): The lower bound of the spectrum in eV or nm depending on the context.
    spc_high (FloatData): The upper bound of the spectrum in eV or nm depending on the context.
    **kwargs: Additional keyword arguments passed to the NodeRunner and computational functions.

    Returns:
    SimstackResult: The result of the spectrum computation, encapsulated in a SimstackResult object.

    SimstackResult:
    deviation (FloatData): The root-mean-square deviation (RMSD) between the theoretical and experimental spectra.

    Called Nodes: vb_spectra

    Raises:
    Exception: If an error occurs during the computation of the UV-Vis spectrum or normalization,
    logs the error and returns a failed computation result.
    """
    node_runner = kwargs.get("node_runner", NodeRunner("compute_spectra",logger,**kwargs))
    try:
        await init_artifacts()
        if not qm_input.molecule.formula:
            qm_input.molecule.make_formula()
        if not qm_input.molecule.formula:
            raise ValueError("molecule.formula is missing and could not be computed")
        node_runner.log(f"Computing UV-Vis Spectrum for molecule: {qm_input.molecule.formula}")
        node_runner.custom_name = qm_input.molecule.formula
        experimental_thresholds = process_experimental_spectrum(experimental_spectrum.get_array(),
                                                                task_id=node_runner.task_id)
        node_runner.min_exp_ev = FloatData(field_name="exp_min (eV)", value=experimental_thresholds['freq_low_eV'])
        node_runner.max_exp_ev = FloatData(field_name="exp_max (ev)", value=experimental_thresholds['freq_high_eV'])
        node_runner.min_exp_nm = FloatData(field_name="exp_min (nm)",
                                           value=1239.84 / experimental_thresholds['freq_low_eV'])
        node_runner.max_exp_nm = FloatData(field_name="exp_max (nm)",
                                           value=1239.84 / experimental_thresholds['freq_high_eV'])

        node_runner.log(f"Experimental Range: {node_runner.min_exp_ev.value} - {node_runner.max_exp_ev.value} eV")
        fc_classes_input = FC_ClassesInput(spcmin=max(experimental_thresholds['freq_low_eV']-spc_low.value,0.0),
                                           spcmax=experimental_thresholds['freq_high_eV']+spc_high.value)
        node_runner.log(f"Fitting Energy Range: {fc_classes_input.spcmin} - {fc_classes_input.spcmax} eV")
        node_runner.info(f"excited state functional: {excited_state_functional}")
        result = await vb_spectra(qm_input, excited_state_functional, excited_state_basis,
                                              protocol_name, spc_low, spc_high, fc_classes_input,**kwargs)

        node_runner.excited_states_result = result.excited_state_gaussian_result
        node_runner.all_spectra = result.all_spectra
        theory_spectrum = result.all_spectra.get_array()
        exp_spectrum = experimental_spectrum.get_array()

        # Convert theory spectrum from eV to nm
        theory_wavelengths_nm = 1239.84 / theory_spectrum[0]
        theory_spectrum_nm = np.vstack((theory_wavelengths_nm, theory_spectrum[1]))

        exp_values, theory_values = await normalize_spectra(exp_spectrum, theory_spectrum_nm)

        # Calculate RMSD
        rmsd = np.sqrt(np.mean((theory_values - exp_values) ** 2))
        logger.info(f"RMSD between theoretical and experimental spectra: {rmsd}")

        node_runner.deviation = FloatData(field_name="deviation", value=rmsd)
        node_runner.job_id = StringData(field_name="task_id", value=str(node_runner.task_id))
        return node_runner.succeed()
    except Exception as e:
        logger.exception(f"Error computing spectra: {str(e)}")
        return node_runner.fail(str(e))


async def normalize_spectra(exp_spectrum: ndarray[tuple[()], Any], theory_spectrum) -> tuple[float | Any, float | Any]:
    # Find min/max values
    # for both spectra
    min_freq = min(np.min(theory_spectrum[0]), np.min(exp_spectrum[0]))
    max_freq = max(np.max(theory_spectrum[0]), np.max(exp_spectrum[0]))

    # Create interpolation points
    new_freqs = np.linspace(min_freq, max_freq, 100)

    # Interpolate both spectra
    theory_interp = interp1d(theory_spectrum[0], theory_spectrum[1], kind='linear', fill_value='extrapolate')
    exp_interp = interp1d(exp_spectrum[0], exp_spectrum[1], kind='linear', fill_value='extrapolate')

    # Calculate interpolated values
    theory_values = theory_interp(new_freqs)
    exp_values = exp_interp(new_freqs)

    # normalize
    theory_values = theory_values / (sum(theory_values) * (max_freq - min_freq))
    exp_values = exp_values / (sum(exp_values) * (max_freq - min_freq))
    return exp_values, theory_values


#
# @node
# async def compute_many_spectra(data_dir: StringData, **kwargs) -> SimstackResult:
#     """
#     Asynchronous function to compute the UV-vis spectra for a collection of molecules.
#
#     This function processes a set of SMILES files within the provided data directory, computes their
#     UV-vis spectra using predefined computational methods, and handles the results or potential errors.
#     The function relies on auxiliary files (e.g., `.txt` and `_solv.txt`) for experimental data and the
#     specification of solvents. Missing input files are logged as warnings.
#
#     Parameters:
#         data_dir (StringData): Directory containing SMILES files to process.
#         **kwargs: Additional keyword arguments passed to the processing nodes.
#
#     Returns:
#         SimstackResult: The final result indicating whether the operation was successful.
#
#     SimstackResult:
#         status (str): "success" if the operation completed successfully, "failure" otherwise.
#
#     Called Nodes: compute_uv_vis_spectrum
#
#     Raises:
#         Exceptions raised during the operation are logged, and the corresponding tasks are marked as failures.
#
#     Note:
#         The computation is performed asynchronously, and tasks are executed in parallel for performance efficiency.
#     """
#     node_runner = NodeRunner("compute_many_spectra",logger,**kwargs)
#     data_dir = Path(__file__).parent /  data_dir.value
#     smiles_files = list(data_dir.glob('*.smiles'))
#     tasks = []
#     for smiles_file in ['Acetophenone.smiles']:
#         node_runner.info(f"processing: {smiles_file}")
#         txt_file = smiles_file.parent / (smiles_file.stem + '.txt')
#         solvent_file = smiles_file.parent / (smiles_file.stem + '_solv.txt')
#         if txt_file.exists() and solvent_file.exists():
#             experimental_data = np.loadtxt(txt_file, skiprows=1)
#             experimental_data = experimental_data[:, [0, 1]].T
#             experimental_spectrum = ArrayStorage(name="experimental_spectrum")
#             experimental_spectrum.set_array(experimental_data)
#
#             with open(smiles_file, "r") as f:
#                 smile_string = f.read()
#
#             with open(solvent_file, "r") as f:
#                 solvent_string = f.read()
#
#             solvent = StringData(field_name="solvent", value=solvent_string)
#             molecule = smiles_to_molecule(smile_string)
#             molecule.smiles = smile_string
#             molecule.formula = compute_iupac_name(molecule)
#             tasks.append(compute_uv_vis_spectrum(molecule, experimental_spectrum, solvent, **kwargs))
#
#         else:
#             node_runner.warning(f"Missing input files for {smiles_file}")
#             continue
#
#
#
#     # Wait for all spectra computations to complete
#     if tasks:
#         results = await asyncio.gather(*tasks, return_exceptions=True)
#
#         # Process results or handle exceptions
#         for i, result in enumerate(results):
#             if isinstance(result, Exception):
#                 logger.error(f"Task {i} failed: {result}")
#             else:
#                 logger.info(f"Task {i} completed successfully")
#
#
#     return node_runner.succeed()

def generate_water_uv_spectrum(n_points=1000):
    # Generate wavelength range from 200 to 800 nm (UV-Vis range)
    wavelengths = np.linspace(200, 800, n_points)

    # Water has weak absorption bands in UV-Vis:
    # ~167 nm (primary band)
    # ~190 nm (secondary band)
    # Rest is mostly transparent
    peaks = [167, 190]
    intensities = [1.0, 0.5]  # Relative intensities
    widths = [10, 15]  # Peak widths

    # Generate spectrum as sum of Gaussian peaks
    spectrum = np.zeros_like(wavelengths)
    for peak, intensity, width in zip(peaks, intensities, widths):
        spectrum += intensity * norm.pdf(wavelengths, peak, width)

    # Add background absorption
    spectrum += 0.05 * np.exp(-wavelengths / 100)

    # Normalize and combine into array
    spectrum = spectrum / np.max(spectrum)
    return np.vstack((wavelengths, spectrum))
#
# async def main_all():
#     await init()
#     await compute_many_spectra(StringData(value="data"))

@node(recompute_artifacts=True)
async def process_one_file(filepath: StringData, **kwargs) -> SimstackResult:
    """
    Process a single experimental spectrum file and create a dataset for it.

    Returns:
        SimstackResult: The result containing the created dataset.
            dataset (simstack.models.datasettuple.DataSetTuple): The created dataset.
    """
    node_runner = kwargs.get("node_runner")

    smiles_file = Path(filepath.value)
    txt_file = smiles_file.parent / (smiles_file.stem + '.txt')
    solvent_file = smiles_file.parent / (smiles_file.stem + '_solv.txt')

    if not smiles_file.exists() or not txt_file.exists():
        raise FileNotFoundError("Required input files not found")

    with open(smiles_file, "r") as f:
        smile_string = f.read().strip()

    molecule = smiles_to_molecule(smile_string)
    molecule.smiles = smile_string
    molecule.formula = compute_iupac_name(molecule)

    experimental_data = np.loadtxt(txt_file, skiprows=1)
    experimental_data = experimental_data[:,[0,1]].T
    experimental_spectrum = ArrayStorage(name="experimental_spectrum")
    experimental_spectrum.set_array(experimental_data)

    with open(solvent_file, "r") as f:
        solvent_string = f.read().strip()

    solvent = StringData(field_name="solvent", value=solvent_string)

    result = await compute_uv_vis_spectrum(molecule, experimental_spectrum, solvent, **kwargs)
    node_runner.result = result
    return node_runner.succeed()

async def init_artifacts():
    """Register plot artifact mappings using this module's import path."""
    if not context.initialized:
        await context.initialize(path=__file__)
    spectra_artifact_mapping = ArtifactMapping(
        name="spectra_artifact_mapping",
        regex_pattern=r".*\.vb_spectra\.(iterative_refinement|fc_classes)$",
        function_mapping=f"{__name__}.fcc_classes_data"
    )
    await register_artifact_mapping(spectra_artifact_mapping)
    all_plots_mapping = ArtifactMapping(
        name="all_spectra_artifact_mapping",
        regex_pattern=r".*\.vb_spectra$",
        function_mapping=f"{__name__}.vb_spectra_plots"
    )
    await register_artifact_mapping(all_plots_mapping)
    spectra_plot_mapping = ArtifactMapping(
        name="spectra_plot_mapping",
        regex_pattern=r".*\.compute_uv_vis_spectrum$",
        function_mapping=f"{__name__}.exp_vs_computed_spectra"
    )
    await register_artifact_mapping(spectra_plot_mapping)
    many_spectra_table_mapping = ArtifactMapping(
        name="many_spectra_table_mapping",
        regex_pattern=r".*\.compute_many_spectra$",
        function_mapping=f"{__name__}.make_summary_table"
    )
    await register_artifact_mapping(many_spectra_table_mapping)


# ArtifactMapping.function_mapping is still the pre-extraction import path in
# existing MongoDB rows. Keep that path importable for create_artifacts.
_LEGACY_RUN_VB_SPECTRA_MODULE = "examples.science.electronic_structure.spectra.run_vb_spectra"
_legacy_parent = ""
for _legacy_part in _LEGACY_RUN_VB_SPECTRA_MODULE.split("."):
    _legacy_parent = f"{_legacy_parent}.{_legacy_part}" if _legacy_parent else _legacy_part
    sys.modules.setdefault(_legacy_parent, types.ModuleType(_legacy_parent))
_legacy_module = sys.modules[_LEGACY_RUN_VB_SPECTRA_MODULE]
_legacy_module.fcc_classes_data = fcc_classes_data
_legacy_module.vb_spectra_plots = vb_spectra_plots
_legacy_module.exp_vs_computed_spectra = exp_vs_computed_spectra
_legacy_module.make_summary_table = make_summary_table


def spectrum_plot_artifact(name, wavelengths, intensities):
    plot_data = [
        {"frequency": float(wavelength), "intensity": float(intensity)}
        for wavelength, intensity in zip(wavelengths, intensities)
    ]
    if not plot_data:
        raise ValueError(f"{name} plot_data is empty")
    freq_range = compute_frequency_range_95_percent(
        np.asarray(wavelengths, dtype=float),
        np.asarray(intensities, dtype=float),
    )
    return ArtifactModel(
        name=name,
        path="none",
        data={
            "plot_data": plot_data,
            "xmin": float(freq_range["xmin"]),
            "xmax": float(freq_range["xmax"]),
        },
    )


def compute_frequency_range_95_percent(frequencies, intensities):
    """
    Compute frequency range that contains 95% of the integral.
    
    Args:
        frequencies: Array of frequency values
        intensities: Array of intensity values
    
    Returns:
        dict: Contains xmin, xmax for 95% integral range
    """
    # Sort by frequency to ensure proper ordering
    sorted_indices = np.argsort(frequencies)
    frequencies_sorted = frequencies[sorted_indices]
    intensities_sorted = intensities[sorted_indices]
    
    # Calculate the total integral
    total_integral = trapezoid(intensities_sorted, frequencies_sorted)
    
    # Calculate cumulative integral
    cumulative_integral = np.zeros_like(intensities_sorted)
    for i in range(1, len(intensities_sorted)):
        cumulative_integral[i] = trapezoid(intensities_sorted[:i+1], frequencies_sorted[:i+1])
    
    # Normalize cumulative integral to range [0, 1]
    cumulative_integral = cumulative_integral / total_integral
    
    # Find thresholds where 2.5% and 97.5% of intensity is contained (95% between them)
    threshold_low = 0.025
    threshold_high = 0.975
    
    # Find frequencies corresponding to these thresholds
    idx_low = np.argmin(np.abs(cumulative_integral - threshold_low))
    idx_high = np.argmin(np.abs(cumulative_integral - threshold_high))
    
    freq_min = frequencies_sorted[idx_low]
    freq_max = frequencies_sorted[idx_high]
    
    return {
        'xmin': freq_min,
        'xmax': freq_max,
        'total_integral': total_integral,
        'cumulative_fraction_at_low': cumulative_integral[idx_low],
        'cumulative_fraction_at_high': cumulative_integral[idx_high]
    }


async def main1():
    await context.initialize()
    filename = "Toluene.smiles"
    parameters = Parameters(recompute_artifacts=True)
    input_smiles_file = Path(__file__).parent / "photochemcad_files" / filename
    # np.savetxt("test_data/water_uv_spectrum.txt", generate_water_uv_spectrum().T)
    await process_one_file(StringData(field_name="smiles_file", value=str(input_smiles_file)), parameters=parameters)


async def main():
    await context.initialize()
    await compute_spectra_job()

if __name__ == "__main__":
    asyncio.run(main())