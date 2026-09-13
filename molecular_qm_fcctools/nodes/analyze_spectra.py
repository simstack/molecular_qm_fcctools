import asyncio
from datetime import datetime
from typing import Any

import numpy as np
from scipy.signal import find_peaks

from odmantic import ObjectId
from simstack.core.context import context
from simstack.core.definitions import TaskStatus
from simstack.core.node import node_from_database

from simstack.models import ModelMapping, NodeRegistry, DataSetMetadata, DataSet, DataSetSection, StringData, FloatData
from simstack.models.charts_artifact import ChartArtifactModel, AGChartTitleConfig, AGLineSeriesConfig, \
    AGChartAxisConfig, AGScatterSeriesConfig

import logging
logger = logging.getLogger(__name__)

def _signal_mask(y: np.ndarray, rel: float = 1e-3) -> np.ndarray:
    """
    Returns a boolean mask where |y| is "significant".
    rel is relative to max(|y|). If max is 0, mask is all False.
    """
    y = np.asarray(y, dtype=float)
    m = float(np.max(np.abs(y))) if y.size else 0.0
    if m == 0.0:
        return np.zeros_like(y, dtype=bool)
    return np.abs(y) > (rel * m)

async def get_completed_compute_uv_vis_entries() -> list[NodeRegistry]:

    entries = await context.db.find(
        NodeRegistry,
        (NodeRegistry.name == "compute_uv_vis_spectrum")
        & (NodeRegistry.status == TaskStatus.COMPLETED),
        )



    return list(entries)


async def load_node_inputs(registry_entry: NodeRegistry) -> dict[str, Any] | None:
    """
    Build: node_inputs[name] = model_loaded_from_database

    - registry_entry.input_references contains the references to input data
    - we reverse-lookup ModelMapping to get the shorthand `name`
    """
    db = context.db

    node_inputs: dict[str, Any] = {}
    for ref in registry_entry.input_references:
        table_mapping = ref.variable_mapping
        obj_id = ref.reference
        if table_mapping == "simstack.models.models.ArrayStorage":
            table_mapping = "simstack.models.array_storage.ArrayStorage"
        elif table_mapping == "simstack.models.models.StringData":
             table_mapping = "simstack.models.base_types.StringData"
        model_mapping = await db.find_one(
            ModelMapping, ModelMapping.mapping == table_mapping
        )
        if model_mapping is None:
            logger.error(f"Could not resolve ModelMapping for mapping='{table_mapping}'")
            return None

        model_obj = await context.db.find_one_by_model_name(table_mapping, obj_id)
        node_inputs[model_mapping.name] = model_obj

    return node_inputs


async def load_node_outputs(registry_entry: NodeRegistry) -> dict[str, Any] | None:
    """
    Build: node_outputs[name] = model_loaded_from_database

    - registry_entry.results_references contains the references to result data
    """
    db = context.db

    node_outputs: dict[str, Any] = {}

    for ref in registry_entry.results_references:
        table_mapping = ref.variable_mapping
        obj_id = ref.reference
        result_name = ref.variable_name

        if table_mapping == "simstack.models.models.ArrayStorage":
            table_mapping = "simstack.models.array_storage.ArrayStorage"

        # Choose a stable dict key for this output
        key = (result_name or "").strip()
        if not key:
            model_mapping = await db.find_one(
                ModelMapping, ModelMapping.mapping == table_mapping
            )
            if model_mapping is None:
                logger.error(f"Could not resolve ModelMapping for mapping='{table_mapping}'")
                return None
            key = model_mapping.name

        model_obj = await context.db.find_one_by_model_name(table_mapping, obj_id)

        # Avoid silent overwrites if multiple outputs share the same key
        if key in node_outputs:
            disambiguated_key = f"{key}__{str(obj_id)}"
            node_outputs[disambiguated_key] = model_obj
        else:
            node_outputs[key] = model_obj

    return node_outputs

def shift_1d_zero_pad(a: np.ndarray, shift: int) -> np.ndarray:
    out = np.zeros_like(a)
    if shift == 0:
        out[:] = a
    elif shift > 0:
        # move right; zeros on the left
        out[shift:] = a[:-shift]
    else:
        # move left; zeros on the right
        s = -shift
        out[:-s] = a[s:]
    return out

def _split_xy(spectrum: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Accept spectra in either shape:
      - (N, 2): columns are [x, y]
      - (2, N): rows are [x, y]

    Returns:
      x, y as (N,) float arrays
    """
    spectrum = np.asarray(spectrum)
    if spectrum.ndim != 2:
        raise ValueError(f"Expected 2D spectrum array, got {spectrum.shape}")

    if spectrum.shape[1] == 2:  # (N, 2)
        x = spectrum[:, 0]
        y = spectrum[:, 1]
    elif spectrum.shape[0] == 2:  # (2, N)
        x = spectrum[0, :]
        y = spectrum[1, :]
    else:
        raise ValueError(
            f"Expected spectrum shape (N,2) or (2,N), got {spectrum.shape}"
        )

    x = x.astype(float, copy=False).ravel()
    y = y.astype(float, copy=False).ravel()

    if x.shape != y.shape:
        raise ValueError(f"x and y must have same shape, got x={x.shape}, y={y.shape}")

    return x, y

async def plot_spectra(formula: str, theory_spectrum: np.ndarray, exp_spectrum: np.ndarray, data_section:DataSetSection) -> None:
    x_exp, y_exp_raw = _split_xy(exp_spectrum)
    x_th, y_th_raw = _split_xy(theory_spectrum)

    # Convert x_th from eV to nm
    x_th = 1239.84 / x_th

    # Ensure x is increasing for interpolation
    exp_order = np.argsort(x_exp)
    th_order = np.argsort(x_th)
    x_exp = x_exp[exp_order]
    y_exp_raw = y_exp_raw[exp_order]
    x_th = x_th[th_order]
    y_th_raw = y_th_raw[th_order]

    # 1) Restrict to the *x-range overlap* first (independent of intensities)
    x_lo = max(float(np.min(x_exp)), float(np.min(x_th)))
    x_hi = min(float(np.max(x_exp)), float(np.max(x_th)))
    if not np.isfinite(x_lo) or not np.isfinite(x_hi) or x_hi <= x_lo:
        logger.warning(
            "No x-range overlap between experimental and theory grids; skipping entry."
        )
        return

    # 2) Create uniform grid of 200 points between x_lo and x_hi
    x_cmp = np.linspace(x_lo, x_hi, 1000)

    # 3) Interpolate both experimental and theory y onto uniform grid
    y_exp_cmp = np.interp(x_cmp, x_exp, y_exp_raw, left=0.0, right=0.0)
    y_th_cmp = np.interp(x_cmp, x_th, y_th_raw, left=0.0, right=0.0)

    # Normalize intensities on the full overlap region such that integral is one
    # Use trapezoidal integration to compute integral over x-range

    exp_integral = np.trapezoid(y_exp_cmp, x_cmp)
    th_integral = np.trapezoid(y_th_cmp, x_cmp)

    # Normalize by integral (handle zero integral case)
    y_exp_cmp = y_exp_cmp / exp_integral if exp_integral != 0 else y_exp_cmp
    y_th_cmp = y_th_cmp / th_integral if th_integral != 0 else y_th_cmp

    # Compute 99% bounds based on cumulative integrals
    # Use trapezoidal cumulative integration
    cumsum_exp = np.concatenate([[0.0], np.cumsum(0.5 * (y_exp_cmp[:-1] + y_exp_cmp[1:]) * np.diff(x_cmp))])
    cumsum_th = np.concatenate([[0.0], np.cumsum(0.5 * (y_th_cmp[:-1] + y_th_cmp[1:]) * np.diff(x_cmp))])

    # Normalize cumulative sums to [0, 1]
    if cumsum_exp[-1] > 0:
        cumsum_exp = cumsum_exp / cumsum_exp[-1]
    if cumsum_th[-1] > 0:
        cumsum_th = cumsum_th / cumsum_th[-1]

    # Find indices where cumulative integral is between 0.5% and 99.5%
    idx_exp_lo = np.searchsorted(cumsum_exp, 0.02)
    idx_exp_hi = np.searchsorted(cumsum_exp, 0.95)
    idx_th_lo = np.searchsorted(cumsum_th, 0.02)
    idx_th_hi = np.searchsorted(cumsum_th, 0.98)

    # Take the union of bounds (most conservative: widest range that captures 99% for both)
    idx_lo = min(idx_exp_lo, idx_th_lo)
    idx_hi = max(idx_exp_hi, idx_th_hi)

    # Ensure valid range
    idx_lo = max(0, idx_lo)
    idx_hi = min(len(x_cmp) - 1, idx_hi)

    if idx_hi <= idx_lo:
        logger.warning("99% bounds calculation resulted in empty range; skipping entry.")
        return

    # Extract 99% bounded region
    x_cmp_99 = x_cmp[idx_lo:idx_hi + 1]
    y_exp_99 = y_exp_cmp[idx_lo:idx_hi + 1]
    y_th_99 = y_th_cmp[idx_lo:idx_hi + 1]

    x_min_99 = float(x_cmp_99[0])
    x_max_99 = float(x_cmp_99[-1])

    # Plot raw spectra (99% bounds region)
    raw_chart_data = [
        {"x": float(x), "exp": float(ye), "th": float(yt)}
        for x, ye, yt in zip(x_cmp_99, y_exp_99, y_th_99)
    ]
    raw_chart = ChartArtifactModel(
        parent_id=ObjectId(),
        title=AGChartTitleConfig(
            text=f"{formula} Experimental vs Theory (99% bounds: {x_min_99:.2f} - {x_max_99:.2f})"),
        series=[
            AGLineSeriesConfig(type="line", xKey="x", yKey="exp", title="Experimental (raw)", data=raw_chart_data),
            AGLineSeriesConfig(type="line", xKey="x", yKey="th", title="Theory (raw)", data=raw_chart_data),
        ],
        axes=[
            AGChartAxisConfig(type="number", position="bottom", title="X"),
            AGChartAxisConfig(type="number", position="left", title="Intensity"),
        ]
    )
    await context.db.save(raw_chart)

    # Create separate plots for each shift
    ds = max(1, len(y_th_99) // 50)
    shifts = []
    rmsds = []
    for shift in range(ds, len(y_th_99), ds):
        shifted_theory_values = shift_1d_zero_pad(y_th_99, shift)

        # Important: RMSD should compare shifted vs exp (not unshifted)
        rmsd = -np.sqrt(np.mean((shifted_theory_values - y_exp_99) ** 2))
        shifts.append(shift)
        rmsds.append(rmsd)
        #
        # fig, ax = plt.subplots(figsize=(10, 6))
        # ax.plot(x_cmp_99, y_exp_99, label="Experimental", linewidth=2, color="black")
        # ax.plot(
        #     x_cmp_99,
        #     shifted_theory_values,
        #     label=f"Theory (shift={shift}, RMSD={rmsd:.4g})",
        #     linewidth=2,
        #     color="blue",
        #     alpha=0.7,
        # )
        # ax.set_xlabel("X")
        # ax.set_ylabel("Normalized Intensity")
        # ax.set_title(f"Experimental vs Theory with shift={shift} (99% bounds: {x_min_99:.2f} - {x_max_99:.2f})")
        # ax.legend()
        # ax.grid(True, alpha=0.3)
        # plt.tight_layout()
        # plt.show()

    # Plot RMSD vs shift
    rmsd_chart_data = [
        {"shift": int(s), "rmsd": float(r)}
        for s, r in zip(shifts, rmsds)
    ]
    rmsd_chart = ChartArtifactModel(
        parent_id=ObjectId(),
        title=AGChartTitleConfig(text="RMSD vs Shift"),
        series=[
            AGScatterSeriesConfig(type="scatter", xKey="shift", yKey="rmsd", title="RMSD", data=rmsd_chart_data),
            AGLineSeriesConfig(type="line", xKey="shift", yKey="rmsd", title="RMSD (line)", data=rmsd_chart_data),
        ],
        axes=[
            AGChartAxisConfig(type="number", position="bottom", title="Shift (index)"),
            AGChartAxisConfig(type="number", position="left", title="RMSD"),
        ]
    )
    await context.db.save(rmsd_chart)

    # Find local maxima in RMSD curve
    peaks, _ = find_peaks(rmsds)

    if len(peaks) == 0:
        logger.warning("No local maxima found in RMSD curve; skipping entry.")
        return

    # Get RMSD values at peaks and sort by descending RMSD
    peak_rmsds = [(shifts[i], rmsds[i]) for i in peaks]
    peak_rmsds_sorted = sorted(peak_rmsds, key=lambda x: x[1], reverse=True)

    # Select top 2 maxima
    top_2_maxima = peak_rmsds_sorted[:2]

    # Plot shifted curves for the 2 highest maxima
    shifted_charts = []
    shift_vals = []
    for shift_val, rmsd_val in top_2_maxima:
        shifted_theory_values = shift_1d_zero_pad(y_th_99, shift_val)
        shift_vals.append(shift_val)
        shifted_chart_data = [
            {"x": float(x), "exp": float(ye), "th_shifted": float(yts)}
            for x, ye, yts in zip(x_cmp_99, y_exp_99, shifted_theory_values)
        ]
        shifted_chart = ChartArtifactModel(
            parent_id=ObjectId(),
            title=AGChartTitleConfig(
                text=f"{formula} with shift={shift_val} (Local Maximum, 99% bounds: {x_min_99:.2f} - {x_max_99:.2f})"
            ),
            series=[
                AGLineSeriesConfig(type="line", xKey="x", yKey="exp", title="Experimental", data=shifted_chart_data),
                AGLineSeriesConfig(
                    type="line",
                    xKey="x",
                    yKey="th_shifted",
                    title=f"Theory (shift={shift_val}, RMSD={rmsd_val:.4g})",
                    data=shifted_chart_data
                ),
            ],
            axes=[
                AGChartAxisConfig(type="number", position="bottom", title="X"),
                AGChartAxisConfig(type="number", position="left", title="Normalized Intensity"),
            ]
        )
        await context.db.save(shifted_chart)
        shifted_charts.append(shifted_chart)

    formula_data = StringData(field_name="formula", value=formula)
    await context.db.save(formula_data)
    if len(shifted_charts) < 2:
        shifted_charts.append(shifted_charts[0])
        shift_vals.append(shift_vals[0])

    sv1 = FloatData(field_name="shift_val_1", value=shift_vals[0])
    await context.db.save(sv1)
    sv2 = FloatData(field_name="shift_val_2", value=shift_vals[1])
    await context.db.save(sv2)
    data_section.append((formula_data, rmsd_chart, raw_chart, sv1, sv2, shifted_charts[0], shifted_charts[1]))

async def analyze_spectra():
    await context.initialize()

    meta_data = DataSetMetadata(field_name="spectra-analysis", data = {
        "created_at": datetime.now()
    })

    dataset = DataSet(field_name="spectra-analysis", metadata=meta_data)
    data_section = DataSetSection()
    dataset["results"] = data_section
    
    completed_entries = await get_completed_compute_uv_vis_entries()
    count = 0
    for entry in completed_entries:
        node = await node_from_database(entry)
        if node is None:
            continue

        node_inputs = await load_node_inputs(entry)
        if node_inputs is None:
            continue

        node_outputs = await load_node_outputs(entry)
        if node_outputs is None:
            continue

        try:
            theory_spectrum = node_outputs["result"].get_array()
            exp_spectrum = node_inputs["ArrayStorage"].get_array()
        except Exception as e:
            if "QMInput" in node_inputs:
                logger.error(f"No results for molecule {node_inputs['QMInput'].name}. Created: {entry.completed_at}")
                #entry.status = TaskStatus.SUBMITTED
                #await context.db.save(entry)
                continue
            if "Molecule" in node_inputs:
                mol_name = node_inputs["Molecule"].formula
                logger.error(f"Old Input Format for molecule {mol_name}. Created: {entry.completed_at}")
                continue
            logger.error(f"No results for entry {entry.id}. Created: {entry.completed_at}")
            continue

        if "Molecule" in node_inputs:
            logger.error(f"Old Input Format for molecule {node_inputs['Molecule'].formula}. Created: {entry.completed_at}")
            continue


        # node_inputs is now: { "<mapping_name>": <loaded_model_instance>, ... }
        # use it as needed:
        # print(node_inputs.keys())


    
    await dataset.save(context.db)

if __name__ == "__main__":
    asyncio.run(analyze_spectra())