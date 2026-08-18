"""FCclasses3 calculation input model (ported from examples spectra/fc_classes)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from odmantic import Model
from pydantic import model_validator

from simstack.models import simstack_model
from simstack.models.file_list import FileListIO
from simstack.util.ui_tools import ui_hide_fields


class FCClassesProperty(str, Enum):
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


class FCClassesModel(str, Enum):
    AS = "AS"
    ASF = "ASF"
    AH = "AH"
    VG = "VG"
    VGF = "VGF"
    VH = "VH"


class FCClassesMethod(str, Enum):
    TI = "TI"
    TD = "TD"


class FCClassesDipole(str, Enum):
    FC = "FC"
    HTi = "HTi"
    HTf = "HTf"


class FCClassesBroadening(str, Enum):
    GAU = "GAU"
    LOR = "LOR"
    VOI = "VOI"


class FCClassesNormalModes(str, Enum):
    COMPUTE = "COMPUTE"
    READ = "READ"
    IMPLICIT = "IMPLICIT"


class FCClassesCoords(str, Enum):
    CARTESIAN = "CARTESIAN"
    INTERNAL = "INTERNAL"


@simstack_model
class FCClassesInput(Model):
    """Input parameters for an ``fcclasses3`` vibronic spectrum calculation."""

    field_name: str = "FCClassesInput"
    property: FCClassesProperty = FCClassesProperty.OPA
    model: FCClassesModel = FCClassesModel.VG
    dipole: FCClassesDipole = FCClassesDipole.FC
    temp: float = 300.0
    broadfun: FCClassesBroadening = FCClassesBroadening.GAU
    hwhm: float = 0.05
    method: FCClassesMethod = FCClassesMethod.TD
    spcmin: float = 1.0
    spcmax: float = 7.0
    normal_modes: FCClassesNormalModes = FCClassesNormalModes.COMPUTE
    coords: FCClassesCoords = FCClassesCoords.INTERNAL
    rm_coord: Optional[str] = None
    rm_coord_inds: Optional[str] = None
    state1_file: Optional[str] = None
    state2_file: Optional[str] = None
    eldip_file: Optional[str] = None
    file_list_io: Optional[FileListIO] = None
    state_number: int = 1

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        from simstack.util.generate_ui_schema import generate_ui_schema

        schema = generate_ui_schema(cls)
        ui_hide_fields(
            schema,
            [
                "state1_file",
                "state2_file",
                "eldip_file",
                "file_list_io",
                "state_number",
                "rm_coord",
                "rm_coord_inds",
            ],
        )
        return schema

    def input_file(self) -> str:
        """Generate the FCclasses3 ``fcc.inp`` body (without state/dipole paths)."""
        lines = [
            "$$$",
            f"PROPERTY     =   {self.property.value}  ; OPA/EMI/ECD/CPL/RR/TPA/TPCD/MCD/IC/NR0",
            f"MODEL        =   {self.model.value}     ; AS/ASF/AH/VG/VGF/VH",
            f"DIPOLE       =   {self.dipole.value}    ; FC/HTi/HTf",
            f"TEMP         =   {self.temp:.2f}        ; (temperature in K)",
            f"BROADFUN     =   {self.broadfun.value}  ; GAU/LOR/VOI",
            f"HWHM         =   {self.hwhm:.2f}        ; (broadening width in eV)",
            f"METHOD       =   {self.method.value}    ; TI/TD",
            f"SPCMIN       =   {self.spcmin:.1f}",
            f"SPCMAX       =   {self.spcmax:.1f}",
            ";VIBRATIONAL ANALYSIS",
            f"NORMALMODES  =   {self.normal_modes.value}   ; COMPUTE/READ/IMPLICIT",
            f"COORDS       =   {self.coords.value} ; CARTESIAN/INTERNAL",
        ]
        if self.rm_coord:
            lines.append(f"RM_COORD     =   {self.rm_coord}")
        if self.rm_coord_inds:
            lines.append(f"RM_COORD_INDS=   {self.rm_coord_inds}")
        return "\n".join(lines) + "\n"
