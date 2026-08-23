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

## Install

`pyproject.toml` is the Hatch Python package (nodes and models). It does **not**
build FCclasses3; that needs `gfortran`, which a normal host install does not
provide.

```bash
uv pip install .
```

The Fortran tools (`fcclasses3`, `gen_fcc_state`, `gen_fcc_dipfile`,
`reconvolute_TD`, `reconvolute_TI`, `convolute_RR`) are compiled in the Docker
image from `vendor/fcclasses3-3.0.4.tar.gz`. The image installs the Python
package from `pyproject.docker`.

Shared deps install from git (see `pyproject.toml` / `pyproject.docker`):
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

## GHCR / Apptainer

On push to `main`, GitHub Actions builds the Docker image, converts it to a
`.sif`, and publishes both to GHCR:

| Kind | Reference |
|------|-----------|
| Docker | `ghcr.io/simstack/molecular-qm-fcctools:latest` |
| Apptainer SIF | `oras://ghcr.io/simstack/molecular-qm-fcctools-sif:latest` |

On a remote machine **with Apptainer**, pull the pre-built SIF (no Fortran
compiler needed):

```bash
# Public package: no login.
# Private package: create a GitHub PAT with read:packages, then:
#   echo "$GHCR_TOKEN" | apptainer registry login -u YOUR_GITHUB_USER --password-stdin docker://ghcr.io

apptainer pull molecular_qm_fcctools.sif \
  oras://ghcr.io/simstack/molecular-qm-fcctools-sif:latest
```

If you only need the Docker image and will convert locally:

```bash
# docker
docker pull ghcr.io/simstack/molecular-qm-fcctools:latest

# or let Apptainer pull the Docker image and write a SIF
apptainer pull molecular_qm_fcctools.sif \
  docker://ghcr.io/simstack/molecular-qm-fcctools:latest
```

Private GHCR images need `docker login ghcr.io` (or the Apptainer login above)
with a token that has `read:packages`. Then:

```bash
apptainer run molecular_qm_fcctools.sif
```

### 2FA-only machines

Interactive `gh auth login` / browser 2FA will not work on those hosts. Create a
**classic PAT** (or fine-grained token with `contents: read` and `read:packages`)
on a machine where you can complete 2FA, put it in a file, and download the SIF
from the rolling GitHub Release over HTTPS:

```bash
# ~/.github_token is a PAT; chmod 600. No interactive 2FA on this host.
curl -fL \
  -H "Authorization: Bearer $(cat ~/.github_token)" \
  -o molecular_qm_fcctools.sif \
  https://github.com/simstack/molecular_qm_fcctools/releases/download/container-sif/molecular_qm_fcctools.sif
```

If the repository is private, GitHub may 302 through the API. Then:

```bash
GH_TOKEN=$(cat ~/.github_token) gh release download container-sif \
  -R simstack/molecular_qm_fcctools \
  -p 'molecular_qm_fcctools.sif'
```

The same PAT can be used non-interactively for Apptainer/GHCR:

```bash
export APPTAINER_DOCKER_USERNAME=YOUR_GITHUB_USER
export APPTAINER_DOCKER_PASSWORD=$(cat ~/.github_token)
apptainer pull molecular_qm_fcctools.sif \
  oras://ghcr.io/simstack/molecular-qm-fcctools-sif:latest
```

## Upstream notes

- FCclasses3: <http://www.iccom.cnr.it/en/fcclasses/>
- fcc_tools: <https://github.com/jcerezochem/fcc_tools>
