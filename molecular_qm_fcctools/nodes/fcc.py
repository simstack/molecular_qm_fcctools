import os
import shutil
from pathlib import Path

from simstack.core.simstack_result import SimstackResult
from simstack.core.hash import complex_hash_function
from simstack.core.node import node
from simstack.core.node_runner import NodeRunner
from simstack.models.array_storage import ArrayStorage
from simstack.models.files import FileStack

import logging

from simstack.models import ArrayList, IntData

logger = logging.getLogger("FCCNode")


def _copy_to_cwd_if_needed(node_runner: NodeRunner, local_file: Path) -> Path | None:
    """
    Copy `local_file` into the current working directory *only if* it is a different file.
    Returns the copied file path (to later clean up) or None if no copy was needed.
    """


    cwd = Path.cwd()
    src = local_file.absolute()
    dst = (cwd / local_file.name).absolute()

    node_runner.info(f"Copying {local_file} to cwd {cwd} from {src} to {dst}")

    # If they resolve to the same path, it's definitely the same file.
    if src == dst:
        node_runner.info(f"Input already in cwd: {src}")
        return None

    # If destination exists, check if both paths point to the same file on disk.
    # (On Windows, samefile requires the target to exist.)
    if dst.exists():
        try:
            if os.path.samefile(src, dst):
                node_runner.info(f"Source and destination are the same file: {src}")
                return None
        except OSError:
            node_runner.warning(f"Could not check if {src} and {dst} are the same file")
            # If samefile can't decide (permissions, network FS quirks), fall back to copying.
            pass

    shutil.copy2(src, dst)
    node_runner.info(f"Copied {src} to {dst}")
    return dst


@node
def fcc_state(file_stack: FileStack, state_number: IntData, **kwargs) -> SimstackResult:
    """
    Process FC state.

    Returns:
        SimstackResult: The result of the FCC state processing.
            file_stack (simstack.models.files.FileStack): The generated FCC state file.
    """
    node_runner = kwargs["node_runner"]
    state_number = state_number.value
    node_runner.custom_name = f"state{state_number}"
    node_runner.info(f"fcc_state started for {state_number}")
    local_file = file_stack.get()

    node_runner.info(f"fcc_state downloaded to {local_file}")

    # Copy file to cwd if it's not already there (and not the same file)
    file_to_cleanup = _copy_to_cwd_if_needed(node_runner, local_file)

    node_runner.info(f"{file_stack.id} downloaded to {local_file} for state: {state_number}")
    file_stack_hash = complex_hash_function(file_stack)
    node_runner.info(f"FileStack hash: {file_stack_hash}")

    input_name = Path(local_file.name)
    if input_name.suffix.lower() == ".chk":
        return node_runner.fail(
            "gen_fcc_state requires a Gaussian formatted checkpoint (.fchk), "
            f"not binary {input_name}"
        )

    success = node_runner.subprocess(
        "gen_fcc_state",
        ["gen_fcc_state", "-i", str(input_name), "-o", "gaussian.fcc"],
    )
      
    if not success or not os.path.exists("gaussian.fcc"):
        details = "\n".join(
            part for part in (node_runner.last_stdout, node_runner.last_stderr) if part
        ).strip()
        message = "fcc_state failed or gaussian.fcc file not found"
        if details:
            message = f"{message}\n{details}"
        return node_runner.fail(message)
        
    if not node_runner.subprocess(f"mv_file.{state_number}.fcc",
                            f"mv gaussian.fcc gaussian.{state_number}.fcc"):
        if file_to_cleanup and file_to_cleanup.exists():
            file_to_cleanup.unlink()
            node_runner.info(f"Deleted local file: {file_to_cleanup}")
        return node_runner.fail("could not move output file")
    node_runner.file_stack = FileStack.from_local_file(f"gaussian.{state_number}.fcc", in_memory=False, is_hashable=True,
                                                       secure_source=True)

    if file_to_cleanup and file_to_cleanup.exists():
        file_to_cleanup.unlink()
        node_runner.info(f"Deleted local file: {file_to_cleanup}")

    return node_runner.succeed()


@node
def fcc_dipole(file_stack: FileStack, state_number: IntData, **kwargs) -> SimstackResult:
    """
    Process FC dipole.

    Returns:
        SimstackResult: The result of the FCC dipole processing.
            file_stack (simstack.models.files.FileStack): The generated FCC dipole file.
    """
    node_runner = NodeRunner(name="fcc_dipole", logger=logger, **kwargs)
    state_number = state_number.value
    node_runner.custom_name = f"state{state_number}"

    local_file = file_stack.get(local_dir=Path("../../../spectra"))

    # Copy file to cwd if it's not already there (and not the same file)
    file_to_cleanup = _copy_to_cwd_if_needed(node_runner, local_file)

    node_runner.info(f"{file_stack.id} downloaded to {local_file} for state: {state_number}")

    input_name = Path(local_file.name)
    if input_name.suffix.lower() == ".chk":
        return node_runner.fail(
            "gen_fcc_dipfile requires a Gaussian formatted checkpoint (.fchk), "
            f"not binary {input_name}"
        )

    success = node_runner.subprocess(
        "gen_fcc_dipfile",
        ["gen_fcc_dipfile", "-i", str(input_name), "-oe", "gaussian.eldip"],
    )

    if not success or not os.path.exists("gaussian.eldip"):
        details = "\n".join(
            part for part in (node_runner.last_stdout, node_runner.last_stderr) if part
        ).strip()
        message = "fcc_dipole failed or gaussian.eldip file not found"
        if details:
            message = f"{message}\n{details}"
        return node_runner.fail(message)

    outfile = f"gaussian.{state_number}.eldip"

    if not node_runner.subprocess(f"copy to {outfile}", f"cp gaussian.eldip {outfile}"):
        return node_runner.fail("could not copy to outfile")

    node_runner.file_stack = FileStack.from_local_file(outfile, in_memory=True, is_hashable=True, secure_source=True)
    #node_runner.files.append(file_stack)

    if file_to_cleanup and file_to_cleanup.exists():
        file_to_cleanup.unlink()
        node_runner.info(f"Deleted local file: {file_to_cleanup}")
    return node_runner.succeed()


@node
def fcc_make_plot(spectra_list: ArrayList, **kwargs) -> SimstackResult:
    """
    Performs spectral data plotting, interpolation, and aggregation operations for given spectra
    contained in the provided list. The function processes each spectrum individually, calculates
    a new common grid for data points, interpolates values on that grid, and sums or averages
    them as needed, writing the resulting aggregated spectrum to an output file. The function
    returns a SimstackResult, containing metadata and processed spectrum storage.

    Parameters:
        spectra_list (ArrayList): A list of spectra to be processed. Each spectrum must be capable of
            providing array data via the `get_array()` method. The array must be organized in such a way
            that the first column represents the x-axis values and the second column represents the y-axis
            values.
        **kwargs (dict): Additional keyword arguments to configure the internal NodeRunner instance.

    Returns:
        SimstackResult: A result object containing metadata, aggregated spectrum storage, and relevant files.

    SimstackResult:
        allspectra (ArrayStorage): An ArrayStorage object containing the aggregated spectrum data.

    """
    node_runner = kwargs.get("node_runner", NodeRunner("fcc_make_plot",logger,**kwargs))
    try:
        import numpy as np
        from scipy import interpolate
        do_average = False
        local_dir = Path("../../../spectra")

        xs = []
        ys = []
        xmax = -100.
        xmin = 9999999.
        dx = 99999.
        nfiles = spectra_list.length
        for spectrum in spectra_list:

            node_runner.info(f"fcc-make-plot plotting data in file: {str(spectrum.name)}")

            # try:
            #     data = np.loadtxt(file_in)
            # except:
            #     raise BaseException('File not found: ' + str(file_in))
            data = spectrum.get_array()
            xs.append(data[:, 0])
            ys.append(data[:, 1])

            xmax = max(xmax, xs[-1].max())
            xmin = min(xmin, xs[-1].min())
            d = (xs[-1][-1] - xs[-1][0]) / len(xs[-1])
            dx = min(d, dx)

        node_runner.info(f"Range: {xmin}, {xmax}  with dx= {dx}")

        # Get new common grid (x)
        xnew = np.arange(xmin, xmax, dx)
        ynew = np.zeros(len(xnew))

        # Now sum all data over such grid after interpolation
        for x, y in zip(xs, ys):
            # Interpolate
            f = interpolate.interp1d(x, y, fill_value=0.0, bounds_error=False)
            ynew += f(xnew)

        # Take the average if requested
        if do_average:
            ynew /= float(nfiles)

        # Print sum
        with open("all_spectra.dat", 'w') as f:
            for xi, yi in zip(xnew, ynew):
                print(xi, yi, file=f)

        node_runner.info(f"all_spectra.dat written with {len(xnew)} points")
        
        # Create an ArrayStorage to hold the spectra
        spectra_array = np.array([xnew, ynew])
        all_spectra_array = ArrayStorage(name="all_spectra", array=spectra_array)
        all_spectra_array.set_array(spectra_array)

        node_runner.all_spectra = all_spectra_array
        node_runner.info_files.append(FileStack.from_local_file(f"all_spectra.dat", in_memory=True, is_hashable=True,
                                secure_source=True))
        node_runner.array_storage = all_spectra_array

    #node_runner.files.append(state_file)
        return node_runner.succeed()

    except Exception as e:
        return node_runner.fail(f"Error {str(e)}")
