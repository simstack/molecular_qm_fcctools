import asyncio

from molecular_qm_util import compute_smiles
from molecular_qm_fcctools.nodes.analyze_spectra import (
    get_completed_compute_uv_vis_entries,
    load_node_inputs,
    load_node_outputs,
    plot_spectra,
)
from simstack.core.context import context
from simstack.core.definitions import TaskStatus
from simstack.core.node import node_from_database
from simstack.models import DataSet, DataSetMetadata, DataSetSection, BooleanData, StringData
import logging
logger = logging.getLogger("SpectraDataset")

async def fix_spectra_dataset():
    await context.initialize()
    completed_entries = await get_completed_compute_uv_vis_entries()


    entries_dict = {}
    for entry in completed_entries:
        node = await node_from_database(entry)
        if node is None:
            continue

        node_inputs = await load_node_inputs(entry)
        if node_inputs is None:
            continue

        if "QMInput" in node_inputs:
            print(f"Found QMInput {node_inputs['QMInput'].molecule.formula} with status: {entry.status}")
            molecule = node_inputs['QMInput'].molecule
            key = compute_smiles(molecule)
            if key in entries_dict:
                print(f"    **** Found duplicate entry for {key} {molecule.formula}")
                continue
            if entry.status == TaskStatus.COMPLETED:
                node_outputs = await load_node_outputs(entry)
                if node_outputs is None:
                    print(f"   **** No outputs for {key}")
                    continue
                if "all_spectra" not in node_outputs:
                    print(f"   **** No result for {key} {molecule.formula}")
                    continue
                print(f"   **** Saved result for {key} {molecule.formula}")
                entries_dict[key] = { "entry" : entry, "matching": False, "name": molecule.formula, "inputs": node_inputs, "outputs": node_outputs, "date": f"{entry.completed_at:%Y-%m-%d %H:%M:%S}" }
        elif "Molecule" in node_inputs:
            print(f"Found deprecated entry with Molecule: {node_inputs['Molecule'].formula} as input")


    spectra_dataset = await context.db.find_one(DataSet, DataSet.field_name == "PhotoChemCad Spectra")

    new_metadata = spectra_dataset.metadata.data.copy()
    new_metadata["dispersion_correction"] = "NA"
    new_metadata["ex_state_dispersion_correction"] = "NA"
    metadata = DataSetMetadata(field_name="PhotoChemCad Spectra II", data= spectra_dataset.metadata.data | {})
    new_dataset = DataSet(field_name="spectra", metadata=metadata)
    input_section = DataSetSection()
    experiment_section = DataSetSection()
    result_section = DataSetSection()
    analysis_section = DataSetSection()

    new_dataset["spectra"] = input_section
    new_dataset["exp_range"] = experiment_section
    new_dataset["results"] = result_section
    new_dataset["analysis"] = analysis_section

    first_match = True

    old_input_section = spectra_dataset["spectra"]
    old_experiment_section = spectra_dataset["exp_range"]

    for index, row in enumerate(old_input_section):
        started_flag, success_flag, molecule_name, solvent, molecule, experimental_spectrum = row
        smiles = compute_smiles(molecule)
        if smiles in entries_dict:
            print(f"Matching NodeEntry for {molecule.smiles} ")
            entries_dict[smiles]["matching"] = True
            inputs = entries_dict[smiles]["inputs"]
            outputs = entries_dict[smiles]["outputs"]
            qm_input = inputs["QMInput"]
            excited_state_functional = str(inputs["FunctionalModel"].functional.functional)
            ect_dispersion_correction = str(inputs["FunctionalModel"].functional.dispersion_correction.real_value)
            if first_match:
                metadata.data["functional"] = str(qm_input.functional.functional)
                metadata.data["dispersion_correction"] = str(qm_input.functional.dispersion_correction.real_value)
                metadata.data["basis_set"] = str(qm_input.basis_set.basis_set)
                metadata.data["excited_state_functional"] = excited_state_functional
                metadata.data["ex_state_dispersion_correction"] = ect_dispersion_correction
                metadata.data["spc_low"] = 0.5
                metadata.data["spc_high"] = 1.5
                first_match = False
            else:
                assert metadata.data["functional"] == str(qm_input.functional.functional), f"Functional mismatch for {molecule.formula}"
                assert metadata.data["basis_set"] == str(qm_input.basis_set.basis_set), f"Basis set mismatch for {molecule.formula}"
                assert metadata.data["dispersion_correction"] == str(qm_input.functional.dispersion_correction.real_value), f"Dispersion correction mismatch for {molecule.formula}"
                assert metadata.data["excited_state_functional"] == excited_state_functional, f"Ex-state functional mismatch for {molecule.formula}"
                assert metadata.data["ex_state_dispersion_correction"] == ect_dispersion_correction, f"Ex-state dispersion correction mismatch for {molecule.formula}"

            new_row_label = StringData(field_name="row_label",value=smiles)
            new_started_flag = BooleanData(field_name="started",value=True)
            new_success_flag = BooleanData(field_name="success",value=True)
            new_molecule_name = StringData(field_name="molecule_name",value=qm_input.molecule.formula)
            await context.db.save(new_row_label)
            await context.db.save(new_started_flag)
            await context.db.save(new_success_flag)
            await context.db.save(new_molecule_name)
            input_section.append((new_row_label, new_started_flag, new_success_flag, new_molecule_name, solvent, molecule, experimental_spectrum))
            old_experiment_row = old_experiment_section[index]
            experiment_section.append((new_row_label, *old_experiment_row))
            results_id = StringData(field_name="results_id", value=str(entries_dict[smiles]["entry"].id))
            await context.db.save(results_id)
            result_section.append((new_row_label, outputs["all_spectra"],outputs["deviation"], results_id))

            await plot_spectra(molecule.formula, outputs["all_spectra"].get_array(), inputs["ArrayStorage"].get_array(), analysis_section)

        else:
            print(f"No NodeEntry for {molecule.formula}")
            new_row_label = StringData(field_name="row_label", value=smiles)
            new_started_flag = BooleanData(field_name="started", value=False)
            new_success_flag = BooleanData(field_name="success", value=False)
            new_molecule_name = StringData(field_name="molecule_name", value=molecule.formula)
            await context.db.save(new_row_label)
            await context.db.save(new_started_flag)
            await context.db.save(new_success_flag)
            await context.db.save(new_molecule_name)
            input_section.append(
                (new_row_label, new_started_flag, new_success_flag, new_molecule_name, solvent, molecule, experimental_spectrum))

    await context.db.save(new_dataset)
    print("Missing entries:")
    for key, value in entries_dict.items():
        if not value["matching"]:
            print(f"{key} not found {value['name']}")



async def add_missing_analysis_data(**kwargs):
    await context.initialize()
    spectra_dataset = await context.db.find_one(DataSet, DataSet.field_name == "spectra")

    spectra_section = spectra_dataset["spectra"]
    analysis_section = spectra_dataset["analysis"]
    result_section = spectra_dataset["results"]

    def _norm_label(x) -> str:
        return x.value if isinstance(x, StringData) else str(x)

    # Build a lookup: row_label -> (formula, experimental_spectrum_array)
    exp_by_label: dict[str, tuple[str, object]] = {}
    for row in spectra_section:
        row_label, started_flag, success_flag, molecule_name, solvent, molecule, experimental_spectrum = row
        label = _norm_label(row_label)
        formula = molecule_name.value if isinstance(molecule_name, StringData) else str(molecule_name)
        exp_by_label[label] = (formula, experimental_spectrum.get_array())

    # Collect existing analysis labels
    existing_labels: set[str] = set()
    for row in analysis_section:
        row_label = row[0]
        existing_labels.add(_norm_label(row_label))

    added = 0
    skipped_missing_exp = 0
    for row in result_section:
        row_label, all_spectra, deviation, results_id = row
        label = _norm_label(row_label)

        if label in existing_labels:
            continue

        exp_info = exp_by_label.get(label)
        if exp_info is None:
            skipped_missing_exp += 1
            continue

        formula, exp_spectrum_array = exp_info
        logger.info(f"Adding analysis for {formula} with label {label}")
        # plot_spectra is the thing that appends the derived analysis row(s) into analysis_section
        await plot_spectra(
            formula=formula,
            theory_spectrum=all_spectra.get_array(),
            exp_spectrum=exp_spectrum_array,
            data_section=analysis_section,
        )
        existing_labels.add(label)
        added += 1

    await context.db.save(spectra_dataset)
    print(f"Added analysis for {added} result rows via plot_spectra.")
    if skipped_missing_exp:
        print(f"Skipped {skipped_missing_exp} rows (no matching experimental spectrum in 'spectra' section).")


if __name__ == '__main__':
    asyncio.run(add_missing_analysis_data())
