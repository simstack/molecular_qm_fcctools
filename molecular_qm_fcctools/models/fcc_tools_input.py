"""CLI option models for fcc_tools programs (see fcc_tools_man.pdf)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from odmantic import Model
from pydantic import model_validator

from simstack.models import simstack_model
from simstack.util.ui_tools import ui_hide_fields


class FccFileFormat(str, Enum):
    """Common ``-ft*`` format hints; leave unset to auto-detect."""

    GAUSSIAN_FCHK = "gaussian_fchk"
    GAUSSIAN_LOG = "gaussian_log"
    MOLPRO = "molpro"
    MOLCAS = "molcas"
    OPENMOLCAS = "openmolcas"
    TURBOMOL = "turbomol"
    GAMESS = "gamess"
    PSI4 = "psi4"
    ORCA = "orca"
    QCHEM = "qchem"
    GROMACS = "gromacs"
    MOLDEN = "molden"
    CFOUR = "cfour"
    CP2K = "cp2k"
    FCC = "fcc"


class FccBroadening(str, Enum):
    GAU = "Gau"
    LOR = "Lor"
    VOI = "Voi"


class FccProperty(str, Enum):
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


class ConvoluteRRType(str, Enum):
    ONE_D = "1D"
    TWO_D = "2D"


def _append_flag(args: list[str], flag: str, value: object | None) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        if value:
            args.append(flag)
        return
    if isinstance(value, Enum):
        args.extend([flag, str(value.value)])
        return
    args.extend([flag, str(value)])


@simstack_model
class GenFccStateInput(Model):
    """Options for ``gen_fcc_state`` (state-file generation from QM outputs)."""

    field_name: str = "GenFccStateInput"
    file_format: Optional[FccFileFormat] = None
    hessian_file: Optional[str] = None
    hessian_format: Optional[FccFileFormat] = None
    gradient_file: Optional[str] = None
    gradient_format: Optional[FccFileFormat] = None
    energy_file: Optional[str] = None
    energy_format: Optional[FccFileFormat] = None
    mass_file: Optional[str] = None
    output_file: Optional[str] = None
    filter_atoms: Optional[str] = None
    write_modes: bool = False
    write_fcc2: bool = False
    output_fcc2: Optional[str] = None
    output_masses: Optional[str] = None
    force_real: bool = False

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
                "hessian_file",
                "gradient_file",
                "energy_file",
                "mass_file",
                "output_fcc2",
                "output_masses",
            ],
        )
        return schema

    def cli_args(self, input_path: str) -> list[str]:
        args = ["gen_fcc_state", "-i", input_path]
        _append_flag(args, "-fts", self.file_format)
        _append_flag(args, "-ih", self.hessian_file)
        _append_flag(args, "-fth", self.hessian_format)
        _append_flag(args, "-ig", self.gradient_file)
        _append_flag(args, "-ftg", self.gradient_format)
        _append_flag(args, "-ie", self.energy_file)
        _append_flag(args, "-fte", self.energy_format)
        _append_flag(args, "-im", self.mass_file)
        _append_flag(args, "-o", self.output_file)
        _append_flag(args, "-filt", self.filter_atoms)
        _append_flag(args, "-write-modes", self.write_modes)
        _append_flag(args, "-write-fcc2", self.write_fcc2)
        _append_flag(args, "-ofcc2", self.output_fcc2)
        _append_flag(args, "-om", self.output_masses)
        _append_flag(args, "-force-real", self.force_real)
        return args


@simstack_model
class GenFccDipfileInput(Model):
    """Options for ``gen_fcc_dipfile`` (ELDIP / MAGDIP / NAC generation)."""

    field_name: str = "GenFccDipfileInput"
    file_format: Optional[FccFileFormat] = None
    initial_state: Optional[int] = None
    final_state: Optional[int] = None
    eldip_file: Optional[str] = None
    magdip_file: Optional[str] = None
    nac_file: Optional[str] = None
    filter_atoms: Optional[str] = None
    write_derivatives: bool = False
    write_nac: bool = False

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        from simstack.util.generate_ui_schema import generate_ui_schema

        return generate_ui_schema(cls)

    def cli_args(self, input_path: str) -> list[str]:
        args = ["gen_fcc_dipfile", "-i", input_path]
        _append_flag(args, "-ft", self.file_format)
        _append_flag(args, "-Si", self.initial_state)
        _append_flag(args, "-Sf", self.final_state)
        _append_flag(args, "-oe", self.eldip_file)
        _append_flag(args, "-om", self.magdip_file)
        _append_flag(args, "-on", self.nac_file)
        _append_flag(args, "-filt", self.filter_atoms)
        _append_flag(args, "-der", self.write_derivatives)
        _append_flag(args, "-nac", self.write_nac)
        return args


@simstack_model
class ReconvoluteTDInput(Model):
    """Options for ``reconvolute_TD``."""

    field_name: str = "ReconvoluteTDInput"
    hwhm: float = 0.05
    broadening: Optional[FccBroadening] = None
    corr_file: Optional[str] = None
    damp: bool = False
    property: Optional[FccProperty] = None
    energy_shift: Optional[float] = None
    fcc_out: Optional[str] = "fcc.out"

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        from simstack.util.generate_ui_schema import generate_ui_schema

        return generate_ui_schema(cls)

    def cli_args(self) -> list[str]:
        args = ["reconvolute_TD", "-hwhm", str(self.hwhm)]
        _append_flag(args, "-f", self.corr_file)
        _append_flag(args, "-brd", self.broadening)
        _append_flag(args, "-damp", self.damp)
        _append_flag(args, "-prop", self.property)
        _append_flag(args, "-Eshift", self.energy_shift)
        _append_flag(args, "-fccout", self.fcc_out)
        return args


@simstack_model
class ReconvoluteTIInput(Model):
    """Options for ``reconvolute_TI``."""

    field_name: str = "ReconvoluteTIInput"
    hwhm: float = 0.05
    broadening: Optional[FccBroadening] = None
    spectrum_file: Optional[str] = None
    property: Optional[FccProperty] = None
    energy_shift: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        from simstack.util.generate_ui_schema import generate_ui_schema

        return generate_ui_schema(cls)

    def cli_args(self) -> list[str]:
        args = ["reconvolute_TI", "-hwhm", str(self.hwhm)]
        _append_flag(args, "-f", self.spectrum_file)
        _append_flag(args, "-brd", self.broadening)
        _append_flag(args, "-prop", self.property)
        _append_flag(args, "-Eshift", self.energy_shift)
        return args


@simstack_model
class ConvoluteRRInput(Model):
    """Options for ``convolute_RR``."""

    field_name: str = "ConvoluteRRInput"
    hwhm: float = 10.0
    spectrum_type: ConvoluteRRType = ConvoluteRRType.ONE_D
    broadening: Optional[FccBroadening] = None
    spectrum_file: Optional[str] = None
    resolution: Optional[float] = None
    incident_freq: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def ensure_fieldname(cls, data):
        if isinstance(data, dict) and "field_name" not in data:
            data["field_name"] = cls.__name__
        return data

    @classmethod
    def ui_schema(cls) -> dict:
        from simstack.util.generate_ui_schema import generate_ui_schema

        return generate_ui_schema(cls)

    def cli_args(self) -> list[str]:
        args = [
            "convolute_RR",
            "-type",
            self.spectrum_type.value,
            "-hwhm",
            str(self.hwhm),
        ]
        _append_flag(args, "-f", self.spectrum_file)
        _append_flag(args, "-brd", self.broadening)
        _append_flag(args, "-resol", self.resolution)
        _append_flag(args, "-wI", self.incident_freq)
        return args
