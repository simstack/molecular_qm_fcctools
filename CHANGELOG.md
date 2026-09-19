# CHANGELOG

<!-- version list -->

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
