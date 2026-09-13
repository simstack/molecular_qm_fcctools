from datetime import datetime
from pathlib import Path

import numpy as np

from molecular_qm_util import compute_iupac_name, smiles_to_molecule

from molecular_qm_fcctools.nodes.spectra_analysis import process_experimental_spectrum
from simstack.core.context import context
from simstack.core.node import node
from simstack.core.node_runner import NodeRunner
from simstack.core.simstack_result import SimstackResult
from simstack.models import Parameters, FloatData, StringData, BooleanData
from simstack.models.array_storage import ArrayStorage
from simstack.models import DataSetTupleSection, DataSetTuple
from simstack.models.dataset_metadata import DataSetMetadata
import logging

logger = logging.getLogger("DatasetMaker")

@node(parameters=Parameters(force_rerun=True))
async def make_dataset(**kwargs) -> SimstackResult:
    """
    Create a dataset of UV spectra from PhotoChemCad files.

    Returns:
        SimstackResult: The result of the dataset creation.
            dataset (simstack.models.datasettuple.DataSetTuple): The created dataset.
    """
    node_runner: NodeRunner | None = kwargs.get('node_runner', None)
    dataset = None
    #dataset = await context.db.find_one(DataSet, DataSet.field_name == "PhotoChemCad Spectra")
    #dataset.clear()

    if dataset:
        spectra_section = dataset["spectra"]
        range_section = dataset["exp_range"]
    else:
        meta_data = DataSetMetadata(field_name="spectra3", data= {
            "description": "UV spectra of molecules",
            "source": "PhotoChemCad",
            "created_at": datetime.now(),
            "protocol_name": "NA",
            "basis_set": "NA",
            "functional": "NA",
            "excited_state_basis": "NA",
            "excited_state_functional": "NA",
            "low_spc_threshold": 0.5,
            "high_spc_threshold": 1.0,
        })

        old_datasets = await context.db.engine.find(DataSetTuple, DataSetTuple.field_name == "spectra3")
        for dataset in old_datasets:
            await context.db.delete(dataset)

        dataset = DataSetTuple(field_name="PhotoChemCad Spectra", metadata=meta_data)
        spectra_section = DataSetTupleSection()
        range_section = DataSetTupleSection()
        dataset["spectra"] = spectra_section
        dataset["exp_range"] = range_section

    assert len(spectra_section) == len(range_section)

    existing = set()
    for records in spectra_section:
        existing.add((records[0].real_value, records[1].real_value))

    data_dir = Path(__file__).parent / "photochemcad_files"
    smiles_files = list(data_dir.glob('*.smiles'))

    for smiles_file in smiles_files:
        logger.info(f"processing: {smiles_file}")
        txt_file = smiles_file.parent / (smiles_file.stem + '.txt')
        solvent_file = smiles_file.parent / (smiles_file.stem + '_solv.txt')

        if not solvent_file.exists() or not txt_file.exists():
            raise FileNotFoundError("Required input files not found")

        with open(smiles_file, "r") as f:
            smile_string = f.read().strip()

        if smile_string is None or smile_string == "" :
            logger.warning(f"Skipping invalid SMILES: {smiles_file.stem}")
            continue

        logger.info(f"smiles: {smile_string}")
        molecule_name = StringData(field_name="molecule", value=f"{smiles_file.stem}")

        with open(solvent_file, "r") as f:
            solvent_string = f.read().strip()

        if solvent_string is None or solvent_string == "":
            logger.warning(f"Skipping invalid solvent: {solvent_file.stem}")
            continue

        solvent = StringData(field_name="solvent", value=solvent_string)

        if (molecule_name.value,solvent_string) in existing:
            logger.info(f"Skipping existing: {molecule_name.value} in solvent: {solvent_string}")
            continue

        name = await context.db.save(molecule_name)
        solvent = await context.db.save(solvent)

        try:
            molecule = smiles_to_molecule(smile_string)
            if not molecule:
                logger.warning(f"Failed to convert SMILES: {smile_string}")
                continue
        except Exception as e:
            logger.error(f"Failed to convert SMILES {smile_string}: {e}")
            continue
        molecule.smiles = smile_string

        xyz_file = smiles_file.parent / (smiles_file.stem + '.xyz')
        molecule.to_file(xyz_file)

        try:
            molecule.formula = compute_iupac_name(molecule)
        except:
            node_runner.warning(f"Missing formula for {molecule_name.value}")
            molecule.formula = molecule_name.value
        molecule = await context.db.save(molecule)

        experimental_data = np.loadtxt(txt_file, skiprows=1)
        experimental_data = experimental_data[:, [0, 1]].T
        experimental_spectrum = ArrayStorage(name="experimental_spectrum")
        experimental_spectrum.set_array(experimental_data)
        experimental_spectrum = await context.db.save(experimental_spectrum)

        started_flag = BooleanData(field_name="started", value=False)
        started_flag = await context.db.save(started_flag)
        success_flag = BooleanData(field_name="success", value=False)
        success_flag = await context.db.save(success_flag)
        spectra_section.append((started_flag, success_flag, molecule_name,solvent, molecule, experimental_spectrum))
        ranges = process_experimental_spectrum(experimental_data, task_id=node_runner.task_id)

        freq_low_eV = FloatData(field_name="freq_low_eV", value=ranges["freq_low_eV"])
        freq_high_eV = FloatData(field_name="freq_high_eV", value=ranges["freq_high_eV"])
        freq_low_eV = await context.db.save(freq_low_eV)
        freq_high_eV = await context.db.save(freq_high_eV)

        wavelength_low_nm = FloatData(field_name="wavelength_low_nm", value=ranges["wavelength_low"])
        wavelength_high_nm = FloatData(field_name="wavelength_high_nm", value=ranges["wavelength_high"])
        wavelength_low_nm = await context.db.save(wavelength_low_nm)
        wavelength_high_nm = await context.db.save(wavelength_high_nm)

        range_section.append((name, freq_low_eV, freq_high_eV, wavelength_low_nm, wavelength_high_nm))

    await context.db.save(dataset)
    node_runner.dataset = dataset
    return node_runner.succeed()

async def main():
    await context.initialize(path=__file__)
    await make_dataset()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())