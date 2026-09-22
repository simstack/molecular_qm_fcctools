import numpy as np
from odmantic import ObjectId
from scipy.integrate import trapezoid
from typing import Optional
import logging
logger = logging.getLogger(__name__)

def normalize_and_find_thresholds(wavelengths, intensities):
    """
    Normalize the integral of the spectrum to 1.0 and find frequency thresholds
    where 98% of the intensity is contained.

    Args:
        wavelengths: Array of wavelengths in nm
        intensities: Array of intensity values

    Returns:
        dict: Contains normalized_intensities, freq_low_eV, freq_high_eV, and integral
    """
    # Sort by wavelength to ensure proper ordering
    sorted_indices = np.argsort(wavelengths)
    wavelengths_sorted = wavelengths[sorted_indices]
    intensities_sorted = intensities[sorted_indices]

    # Calculate the integral using trapezoidal rule
    integral = trapezoid(intensities_sorted, wavelengths_sorted)

    # Normalize intensities so integral equals 1.0
    normalized_intensities = intensities_sorted / integral

    # Calculate cumulative integral
    cumulative_integral = np.zeros_like(normalized_intensities)
    for i in range(1, len(normalized_intensities)):
        cumulative_integral[i] = trapezoid(normalized_intensities[:i + 1], wavelengths_sorted[:i + 1])

    # Find thresholds where 1% and 99% of intensity is contained (98% between them)
    threshold_low = 0.01
    threshold_high = 0.99

    # Find wavelengths corresponding to these thresholds
    idx_low = np.argmin(np.abs(cumulative_integral - threshold_low))
    idx_high = np.argmin(np.abs(cumulative_integral - threshold_high))

    wavelength_low = wavelengths_sorted[idx_low]
    wavelength_high = wavelengths_sorted[idx_high]

    # Convert wavelengths to frequencies in eV
    # E(eV) = hc/λ = 1239.84 eV·nm / λ(nm)
    freq_low_eV = 1239.84 / wavelength_high  # Note: higher wavelength = lower energy
    freq_high_eV = 1239.84 / wavelength_low  # Note: lower wavelength = higher energy

    return {
        'normalized_intensities': normalized_intensities,
        'wavelengths_sorted': wavelengths_sorted,
        'freq_low_eV': freq_low_eV,
        'freq_high_eV': freq_high_eV,
        'freq_low_nm': wavelength_high,  # Corresponding wavelength
        'freq_high_nm': wavelength_low,  # Corresponding wavelength
        'integral': integral,
        'wavelength_low': wavelength_low,
        'wavelength_high': wavelength_high,
        'cumulative_fraction_at_low': cumulative_integral[idx_low],
        'cumulative_fraction_at_high': cumulative_integral[idx_high]
    }


def eV_to_nm(energy_eV):
    """
    Convert energy in eV to wavelength in nm

    Args:
        energy_eV: Energy in electron volts

    Returns:
        float: Wavelength in nanometers
    """
    return 1239.84 / energy_eV


def spectrum_x_to_nm(x_values):
    """
    Return spectrum x-axis values in nm.

    FCclasses spectra are stored in eV (typical UV–Vis range is below 20 eV).
    Plot artifacts and experimental curves already in nm have minima above 50 nm.
    """
    x_values = np.asarray(x_values, dtype=float)
    if x_values.size == 0:
        raise ValueError("spectrum x values are empty")
    if np.any(x_values <= 0) or not np.all(np.isfinite(x_values)):
        raise ValueError("spectrum x values must be positive and finite")
    x_min = float(np.min(x_values))
    x_max = float(np.max(x_values))
    if x_max < 20.0:
        return eV_to_nm(x_values)
    if x_min > 50.0:
        return x_values
    raise ValueError(
        f"spectrum x-axis values [{x_min}, {x_max}] are not unambiguously eV or nm"
    )


def nm_to_eV(wavelength_nm):
    """
    Convert wavelength in nm to energy in eV

    Args:
        wavelength_nm: Wavelength in nanometers

    Returns:
        float: Energy in electron volts
    """
    return 1239.84 / wavelength_nm



def process_experimental_spectrum(data_array, task_id: Optional[ObjectId] = None):
    """
    Process experimental spectrum data to normalize and find thresholds.

    Args:
        data_array: 2D array with shape (2, n) where the first row is wavelengths, the second is intensities
        task_id: Optional task identifier for logging or tracking purposes

    Returns:
        dict: Processed spectrum information
    """
    wavelengths = data_array[0]
    intensities = data_array[1]

    result = normalize_and_find_thresholds(wavelengths, intensities)

    logger.info(f"experimental spectrum: task_id: {task_id}Original integral: {result['integral']:.6f}")
    logger.info(f"experimental spectrum: task_id: {task_id}Frequency range containing 98% of intensity:")
    logger.info(f"experimental spectrum: task_id: {task_id}  Low threshold (1%): {result['freq_low_eV']:.3f} eV = {result['freq_low_nm']:.1f} nm")
    logger.info(f"experimental spectrum: task_id: {task_id}  High threshold (99%): {result['freq_high_eV']:.3f} eV = {result['freq_high_nm']:.1f} nm")
    logger.info(f"experimental spectrum: task_id: {task_id}  Energy range: {result['freq_high_eV'] - result['freq_low_eV']:.3f} eV")
    logger.info(f"experimental spectrum: task_id: {task_id}  Wavelength range: {result['freq_high_nm'] - result['freq_low_nm']:.1f} nm")

    return result

