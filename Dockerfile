# Build from this capability repository:
#   docker build -t molecular-qm-fcctools:latest .
# From simstack-model:
#   docker build -t molecular-qm-fcctools:latest -f molecular_qm_fcctools/Dockerfile molecular_qm_fcctools
#
# Dual-use: capability tree is not installable on host (no pyproject.toml).
# In the image, pyproject.docker is renamed and the package is pip-installed;
# models / util / simstack come from git (see pyproject.docker).
FROM mambaorg/micromamba:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    build-essential \
    gfortran \
    libblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

RUN micromamba install -y -n base -c conda-forge setuptools && \
    micromamba clean --all --yes

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/opt/conda/bin:/root/.local/bin:$PATH"

WORKDIR /app

# simstack requires Python>=3.12
RUN micromamba install -y -n base -c conda-forge \
    python=3.12.12 \
    numpy \
    openbabel \
    && micromamba clean --all --yes

# Capability tree (includes vendored FCclasses tarball).
COPY . /build/molecular_qm_fcctools

# Build FCclasses3 (+ bundled fcc_tools) from the vendored tarball.
RUN mkdir -p /opt/fcclasses3_src && \
    tar -xzf /build/molecular_qm_fcctools/vendor/fcclasses3-3.0.4.tar.gz \
        -C /opt/fcclasses3_src --strip-components=1 && \
    cd /opt/fcclasses3_src && \
    ./configure --prefix=/opt/fcclasses3 FC=gfortran F77=gfortran && \
    make && \
    make install && \
    test -x /opt/fcclasses3/bin/fcclasses3 && \
    test -x /opt/fcclasses3/bin/gen_fcc_state && \
    test -x /opt/fcclasses3/bin/gen_fcc_dipfile && \
    test -x /opt/fcclasses3/bin/reconvolute_TD && \
    test -x /opt/fcclasses3/bin/reconvolute_TI && \
    test -x /opt/fcclasses3/bin/convolute_RR
ENV FCCLASSES3=/opt/fcclasses3
ENV FCCTOOLS=/opt/fcclasses3
ENV PATH="${FCCLASSES3}/bin:${PATH}"

ENV UV_PYTHON=/opt/conda/bin/python
ENV UV_PROJECT_ENVIRONMENT=/opt/conda
ENV PATH="/opt/conda/bin:/root/.local/bin:${FCCLASSES3}/bin:$PATH"

# Install capability package + git deps (see pyproject.docker).
WORKDIR /build/molecular_qm_fcctools
# molecular_qm_util imports pymatgen at install time. Pip, not conda:
# conda-forge pymatgen pulls a large X11/matplotlib stack.
RUN uv pip install --system pymatgen "setuptools>=80.9.0"
RUN cp pyproject.docker pyproject.toml \
 && uv pip install --system . \
 && python -c "import simstack, molecular_qm_models, molecular_qm_util, molecular_qm_fcctools; \
print('simstack', simstack.__file__); \
print('models', molecular_qm_models.__file__); \
print('fcctools', molecular_qm_fcctools.__file__)"

WORKDIR /app
ENTRYPOINT ["python", "-m", "simstack.core.run_node"]
