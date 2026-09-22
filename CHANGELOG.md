# CHANGELOG

<!-- version list -->

## v0.6.14 (2026-09-22)

### Bug Fixes

- Add `spectrum_x_to_nm` conversion and integrate with VB spectra processing
  ([`c81f23c`](https://github.com/simstack/molecular_qm_fcctools/commit/c81f23c452f23a6a2c6983cd20f29979890f4ff9))


## v0.6.13 (2026-09-20)

### Bug Fixes

- Refactor fc_classes and fcc_state to improve file handling and test coverage
  ([`7f29fd0`](https://github.com/simstack/molecular_qm_fcctools/commit/7f29fd005fc386945210ca14cdc86efa25e3164d))


## v0.6.12 (2026-09-20)

### Bug Fixes

- Refactor iterative_refinement to use BooleanData for convergence and update artifact mappings
  ([`6e0d382`](https://github.com/simstack/molecular_qm_fcctools/commit/6e0d38259c059fe586e7639645f65bee07964b42))


## v0.6.11 (2026-09-20)

### Bug Fixes

- Remove hardcoded spectra path in fc_classes and simplify file retrieval
  ([`d56241b`](https://github.com/simstack/molecular_qm_fcctools/commit/d56241b3fa0ddf388f26be176f1518aeb40735de))


## v0.6.10 (2026-09-20)

### Bug Fixes

- Use molecule formula as vb_spectra P2 name
  ([`67e5f4e`](https://github.com/simstack/molecular_qm_fcctools/commit/67e5f4e61d6b6bd9a0c444a9354c1f1880f2c272))

### Chores

- Update `molecular_qm_fcctools`
  ([`5273f7a`](https://github.com/simstack/molecular_qm_fcctools/commit/5273f7a8232b0383bcb19ded357ef8850c545a43))


## v0.6.9 (2026-09-20)

### Bug Fixes

- Take gaussian.fchk from QMResult.files only
  ([`863a289`](https://github.com/simstack/molecular_qm_fcctools/commit/863a2897351008adf0352b75e5aaa544aa1c9d4c))


## v0.6.8 (2026-09-20)

### Bug Fixes

- Type annotate `node_runner` and correct spectra list length calculation in FCC plotting
  ([`c87e80c`](https://github.com/simstack/molecular_qm_fcctools/commit/c87e80cd17a841c6711b59dda1f8ea69f8c68772))


## v0.6.7 (2026-09-19)

### Bug Fixes

- Use the injected NodeRunner in fcc_make_plot
  ([#5](https://github.com/simstack/molecular_qm_fcctools/pull/5),
  [`128aee8`](https://github.com/simstack/molecular_qm_fcctools/commit/128aee8c4d388fc7e970186fe8f69cd2fab34871))


## v0.6.6 (2026-09-19)

### Bug Fixes

- Take gaussian.fchk from QMResult.files only
  ([#4](https://github.com/simstack/molecular_qm_fcctools/pull/4),
  [`d699eeb`](https://github.com/simstack/molecular_qm_fcctools/commit/d699eebf06ab959c1b58a4ac1bd4dffc2d348126))


## v0.6.5 (2026-09-19)

### Bug Fixes

- Refactor `_formatted_checkpoint` to streamline parameter handling and update tests
  ([`ff82f8a`](https://github.com/simstack/molecular_qm_fcctools/commit/ff82f8a82c2e87d17639c1702e6464a6bd86d081))


## v0.6.4 (2026-09-19)

### Bug Fixes

- Enforce `.fchk` input requirement in FCC nodes and improve checkpoint handling
  ([#2](https://github.com/simstack/molecular_qm_fcctools/pull/2),
  [`65c217e`](https://github.com/simstack/molecular_qm_fcctools/commit/65c217eea0557d9f219bf9bc0527ee4f6f1a000d))

- Include gen_fcc_state output when gaussian.fcc is missing
  ([#2](https://github.com/simstack/molecular_qm_fcctools/pull/2),
  [`65c217e`](https://github.com/simstack/molecular_qm_fcctools/commit/65c217eea0557d9f219bf9bc0527ee4f6f1a000d))

- Pass formatted .fchk into gen_fcc_state
  ([#2](https://github.com/simstack/molecular_qm_fcctools/pull/2),
  [`65c217e`](https://github.com/simstack/molecular_qm_fcctools/commit/65c217eea0557d9f219bf9bc0527ee4f6f1a000d))


## v0.6.3 (2026-09-19)

### Bug Fixes

- Restore fcc_state and FileStack imports in vb_spectra
  ([`6eeb013`](https://github.com/simstack/molecular_qm_fcctools/commit/6eeb0139377deb70475b4adc87b106a1632e5a5f))


## v0.6.2 (2026-09-17)

### Bug Fixes

- Decorate vb_spectra with @node so the Docker image import check succeeds
  ([`1a96578`](https://github.com/simstack/molecular_qm_fcctools/commit/1a96578bafbd998f66da760ad6d69dce5d06e84c))

### Chores

- Add rdkit dependency to pyproject.toml
  ([`311312a`](https://github.com/simstack/molecular_qm_fcctools/commit/311312a8bab925b8f7da3245bb1b00631c7d1790))

- Update simstack to version 2.1.0.dev214 in lockfile
  ([`2b147c1`](https://github.com/simstack/molecular_qm_fcctools/commit/2b147c15bc91e71572363e61fb4b50a67f6aa88d))

### Refactoring

- Improve logging and streamline parameter handling in FCC and vibrational spectra nodes
  ([`ca3b9f8`](https://github.com/simstack/molecular_qm_fcctools/commit/ca3b9f8b10c46dfc1204ec9d8f94d5374cdfd08a))


## v0.6.1 (2026-09-13)


## v0.6.0 (2026-09-13)

### Features

- Update imports and expose new spectra processing and plotting nodes in module init
  ([`c3663c7`](https://github.com/simstack/molecular_qm_fcctools/commit/c3663c754c7601361d558f385d0b0503ff52618d))


## v0.5.0 (2026-09-13)


## v0.4.0 (2026-09-13)

### Features

- Integrate molecular_qm_gaussian dependency and update imports for spectra nodes
  ([`d76bdac`](https://github.com/simstack/molecular_qm_fcctools/commit/d76bdac9fb11bf0ee5cb1cb59486b25e5f88a17b))


## v0.3.0 (2026-09-13)

### Chores

- Update molecular_qm_util and simstack dependencies to latest revisions
  ([`066fe55`](https://github.com/simstack/molecular_qm_fcctools/commit/066fe55c8f5ab09e5d5f33fcc71044f5d8e76678))

### Features

- Add spectra analysis nodes and multi-line chart support for plotting spectra
  ([`46fa2b1`](https://github.com/simstack/molecular_qm_fcctools/commit/46fa2b1a1f2a9d6bbaed2f5c08758821e8f55561))

### Refactoring

- Remove unused `Optional` imports and improve type annotations for node inputs and return values
  ([`62ea353`](https://github.com/simstack/molecular_qm_fcctools/commit/62ea353433855e5161d57f09b4d1997fcf185378))


## v0.2.0 (2026-08-30)

### Features

- Ensure backward compatibility for simstack workdir paths in Dockerfile
  ([`ae6beed`](https://github.com/simstack/molecular_qm_fcctools/commit/ae6beed12db86517d67c3a1f04a0ca2689825ca8))


## v0.1.0 (2026-08-23)

- Initial Release
