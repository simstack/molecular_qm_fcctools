import os
import numpy as np
from enum import Enum
from pathlib import Path
from typing import Optional

from odmantic import Model
from pydantic import model_validator

from simstack.core.simstack_result import SimstackResult
from simstack.core.node import node
from simstack.core.node_runner import NodeRunner
from simstack.models import simstack_model
from simstack.models.array_storage import ArrayStorage
from simstack.models.file_list import FileListIO
from simstack.models.files import FileStack
from simstack.util.ui_tools import ui_hide_fields

import logging


logger = logging.getLogger("fc_classes")


class FC_ClassesProperty(str, Enum):
    OPA = "OPA"
    EMI = "EMI"
    ECD = "ECD"
    CPL = "CPL"
    RR = "RR"
    TPA = "TPA"
    TPCD = "TPCD"
    MCD = "MCD"
    IC = "IC"
    NR0 = "NR0"



class FC_ClassesModel(str, Enum):
    AS = "AS"  # Absorption Spectrum
    ASF = "ASF"  # Absorption Spectrum with Fermi's Golden Rule
    AH = "AH"  # Absorption Spectrum with Harmonic Oscillator
    VG = "VG"  # Vibrational Gating
    VGF = "VGF"  # Vibrational Gating with Fermi's Golden Rule
    VH = "VH"  # Vibrational Gating with Harmonic Oscillator

class FC_ClassesMethod(str, Enum):
    TI = "TI"  # Time-independent
    TD = "TD"  # Time-dependent


class FC_ClassesDipole(str, Enum):
    FC = "FC"  # Franck-Condon
    HTi = "HTi"  # Herzberg-Teller isotropic
    HTf = "HTf"  # Herzberg-Teller full



class FC_ClassesBroadening(str, Enum):
    GAU = "GAU"  # Gaussian
    LOR = "LOR"  # Lorentzian
    VOI = "VOI"  # Voigt

    def __str__(self):
        return self.value

class FC_ClassesNormalModes(str, Enum):
    COMPUTE = "COMPUTE"  # Compute normal modes
    READ = "READ"  # Read normal modes from file
    IMPLICIT = "IMPLICIT"  # Implicit normal modes


class FC_ClassesCoords(str,  Enum):
    CARTESIAN = "CARTESIAN"  # Cartesian coordinates
    INTERNAL = "INTERNAL"  # Internal coordinates

@simstack_model
class FC_ClassesInput(Model):
    """
    Model for the input parameters of the fc_classes node.
    """
    field_name: str = "FC_ClassesInput"
    property: FC_ClassesProperty = FC_ClassesProperty.OPA
    model: FC_ClassesModel = FC_ClassesModel.VG
    dipole: FC_ClassesDipole = FC_ClassesDipole.FC
    temp: float = 300.0  # Temperature in Kelvin
    broadfun: FC_ClassesBroadening = FC_ClassesBroadening.GAU
    hwhm: float = 0.05  # Half-width at half maximum in eV
    method: FC_ClassesMethod = FC_ClassesMethod.TD  # Time-dependent or time-independent
    spcmin: float = 1.0  # Minimum spectrum value
    spcmax: float = 7.0  # Maximum spectrum value

    normal_modes: FC_ClassesNormalModes = FC_ClassesNormalModes.COMPUTE  # Normal modes handling
    coords: FC_ClassesCoords = FC_ClassesCoords.INTERNAL  # Coordinate system, either "CARTESIAN" or "INTERNAL"
    rm_coord: Optional[str] = None  # Coordinate removal specification
    rm_coord_inds: Optional[str] = None  # Indices for coordinate removal

    state1_file: Optional[str] = None  # Path to state 1 file
    state2_file: Optional[str] = None  # Path to state 2 file
    eldip_file: Optional[str] = None  # Path to electronic dipole file

    file_list_io: Optional[FileListIO] = None  # must be set before calling the node
    state_number: int = 1 # State number for the calculation

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        """Ensure fieldname is set for existing documents"""
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        """
        Generate the UI schema for the fc_classes input model.
        """
        from simstack.util.generate_ui_schema import generate_ui_schema

        ui_schema = generate_ui_schema(cls)
        ui_hide_fields(ui_schema, ["state1_file", "state2_file", "eldip_file", "file_list_io", "state_number",
                                   "rm_coord", "rm_coord_inds"])
        return ui_schema

    def input_file(self):
        """
        Generate the input file content for the fc_classes node.
        """
        string = "$$$\n"
        string += f"PROPERTY     =   {self.property.value}  ; OPA/EMI/ECD/CPL/RR/TPA/TPCD/MCD/IC/NR0\n"
        string += f"MODEL        =   {self.model.value}     ; AS/ASF/AH/VG/VGF/VH\n"
        string += f"DIPOLE       =   {self.dipole.value}    ; FC/HTi/HTf\n"
        string += f"TEMP         =   {self.temp:.2f}        ; (temperature in K)\n"
        string += f"BROADFUN     =   {self.broadfun.value}  ; GAU/LOR/VOI\n"
        string += f"HWHM         =   {self.hwhm:.2f}        ; (broadening width in eV)\n"
        string += f"METHOD       =   {self.method.value}    ; TI/TD\n"
        string += f"SPCMIN       =   {self.spcmin:.1f}\n"
        string += f"SPCMAX       =   {self.spcmax:.1f}\n"
        string += ";VIBRATIONAL ANALYSIS\n"
        string += f"NORMALMODES  =   {self.normal_modes.value}   ; COMPUTE/READ/IMPLICIT\n"
        string += f"COORDS       =   {self.coords.value} ; CARTESIAN/INTERNAL\n"
        if self.rm_coord:
            string += f"RM_COORD     =   {self.rm_coord}\n"
        if self.rm_coord_inds:
            string += f"RM_COORD_INDS=   {self.rm_coord_inds}\n"
        return string


@node
def fc_classes(fc_classes_input: FC_ClassesInput, **kwargs) -> SimstackResult:
    """
    Run FC_Classes for spectra calculation.

    Returns:
        SimstackResult: The result of the FC_Classes calculation.
            int_td_spectrum (simstack.models.array_storage.ArrayStorage): Intensity TD spectrum.
            ls_td_spectrum (simstack.models.array_storage.ArrayStorage): Line shape TD spectrum.
            files (list[simstack.models.files.FileStack]): List of output files.
    """
    node_runner = NodeRunner("fc_classes", logger= logger, **kwargs)
    local_files = []
    try:
        node_runner.custom_name = f"state{fc_classes_input.state_number}"
        state_number = fc_classes_input.state_number
        file_list_io = fc_classes_input.file_list_io

        node_runner.info(f"processing spectra for state: {state_number}")


        file_list = file_list_io.file_list

        if len(file_list) != 3:
            return node_runner.fail(f"input file list must have exactly 3 files")

        state1_path = file_list[0].get()
        state2_path = file_list[1].get()
        eldip_path = file_list[2].get()

        local_files = [state1_path, state2_path, eldip_path]

        with open("fcc.inp", "w") as input_file:
            input_file.write(fc_classes_input.input_file())
            input_file.write(f"STATE1_FILE = {state1_path}\n")
            input_file.write(f"STATE2_FILE = {state2_path}\n")
            input_file.write(f"ELDIP_FILE = {eldip_path}\n")

        node_runner.info_files.append(FileStack.from_local_file("fcc.inp", in_memory=True, is_hashable=True, secure_source=True))
        result_ok = node_runner.subprocess("fcclasses3", ["fcclasses3", "fcc.inp"])

        if not os.path.exists("fcc.out"):
            return node_runner.fail(f"fcc.out not found")

        file_stack = FileStack.from_local_file("fcc.out", in_memory=True, is_hashable=True, secure_source=True)
        node_runner.info_files.append(file_stack)

        if not result_ok:
            return node_runner.fail("fc_classes failed")

        for name in ["Int_TD", "LS_TD"]:
            if not os.path.exists(f"spec_{name}.dat"):
                return node_runner.fail(f"spec_Int_TD.dat not found")
            # Read spectrum data into numpy array
            spectrum_data = np.loadtxt(f"spec_{name}.dat")
            # Convert x-values from eV to nm (wavelength = 1239.8/energy)

            array_storage = ArrayStorage(name=f"spec_{name}_{state_number}")
            array_storage.set_array(spectrum_data)
            node_runner.__setattr__(f"{name.lower()}_spectrum", array_storage)

            file_name = f"spec_{name}_{state_number}.dat"
            if not node_runner.subprocess("copy outfile", f"cp spec_{name}.dat {file_name}"):
                return node_runner.fail(f"could not copy to {file_name}")

            node_runner.files.append(FileStack.from_local_file(file_name, in_memory=True, is_hashable=True, secure_source=True))
        return node_runner.succeed()
    except Exception as e:
        return node_runner.fail(f"Error: {str(e)}")
    finally:
        for file in local_files:
            if file.exists():
                file.unlink()
