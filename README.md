# Molecular QM fcc_tools / FCclasses3

Python bindings and Simstack nodes for [FCclasses3](http://www.iccom.cnr.it/en/fcclasses/)
and the bundled [fcc_tools](https://github.com/jcerezochem/fcc_tools) helpers
(input generation and spectrum post-processing).

## Nodes

| Node | Upstream tool | Role |
|------|---------------|------|
| `fcclasses3` | `fcclasses3` | Vibronic spectrum / rate calculation |
| `gen_fcc_state` | `gen_fcc_state` | Build FCclasses state files from QM outputs |
| `gen_fcc_dipfile` | `gen_fcc_dipfile` | Build ELDIP / MAGDIP / NAC files |
| `reconvolute_td` | `reconvolute_TD` | Re-broaden a TD spectrum from `corr.dat` |
| `reconvolute_ti` | `reconvolute_TI` | Re-broaden a TI spectrum from `Bin_Spectrum.dat` |
| `convolute_rr` | `convolute_RR` | Convolve resonance-Raman stick / 2D spectra |

Option schemas live under `models/` and mirror the CLI / input flags from the manuals.

## Dual-use

- **Host (`simstack-model`):** not installable — no `pyproject.toml`. Flat tree for
  `create_node_table` / `create_model_table`.
- **Container:** installable — Dockerfile renames `pyproject.docker` → `pyproject.toml`
  and runs `uv pip install .`. Shared deps install from git (see `pyproject.docker`):
  [`molecular_qm_models`](https://github.com/simstack/molecular_qm_models),
  [`molecular_qm_util`](https://github.com/simstack/molecular_qm_util) (`develop-ww`),
  [`simstack`](https://github.com/simstack/simstack) (`fix-git-pull`).

## Local Docker image

The Dockerfile builds FCclasses3 3.0.4 (including fcc_tools) from the vendored tarball
`vendor/fcclasses3-3.0.4.tar.gz` with `gfortran` and system BLAS/LAPACK.

From this repository:

```bash
docker build -t molecular-qm-fcctools:latest .
```

From a simstack-model checkout:

```bash
docker build -t molecular-qm-fcctools:latest -f molecular_qm_fcctools/Dockerfile molecular_qm_fcctools
```

## Upstream notes

- FCclasses3: <http://www.iccom.cnr.it/en/fcclasses/>
- fcc_tools: <https://github.com/jcerezochem/fcc_tools>
