# NASA C-MAPSS Dataset Provenance and Specifications

## 1. Overview and Citation
The **Commercial Modular Aero-Propulsion System Simulation (C-MAPSS)** dataset was created and released by the Prognostics Center of Excellence (PCoE) at NASA Ames Research Center.

- **Creators:** Ashok Saxena, Kai Goebel (NASA Ames Research Center), Wolfgang Simon, Neil Eklund (General Electric Global Research)
- **Publication:** *Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation*, Proceedings of the 1st International Conference on Prognostics and Health Management (PHM08), Denver CO, 2008.
- **Repository:** NASA Prognostics Data Repository / Open NASA Data
- **License / Terms of Use:** Public Domain (NASA Open Data Policy). For academic and benchmark usage, appropriate citation of Saxena et al. (2008) is requested.

## 2. Simulation Characteristics
The C-MAPSS software simulates a realistic large commercial turbofan aircraft engine (approx. 90,000 lb thrust class). The engine model comprises:
1. **Fan (F)**
2. **Low-Pressure Compressor (LPC)**
3. **High-Pressure Compressor (HPC)**
4. **High-Pressure Turbine (HPT)**
5. **Low-Pressure Turbine (LPT)**
6. **Nozzle and Bypass Duct**

Degradation is simulated through synthetic wear and operational contamination injected into module health parameters, particularly HPC efficiency and flow capacity degradation, and HPT efficiency degradation.

## 3. Subsets Overview
The original NASA benchmark contains four sub-datasets:

| Dataset | Operating Conditions | Fault Modes | Train Units | Test Units |
|---|---|---|---|---|
| **FD001** (Target MVP) | 1 (Sea Level) | 1 (HPC Degradation) | 100 | 100 |
| **FD002** | 6 (Six flight conditions) | 1 (HPC Degradation) | 260 | 259 |
| **FD003** | 1 (Sea Level) | 2 (HPC + Fan Degradation) | 100 | 100 |
| **FD004** | 6 (Six flight conditions) | 2 (HPC + Fan Degradation) | 249 | 248 |

TelemetryX V1 focuses on **FD001**, which provides the foundational benchmark for single-condition turbofan degradation.

## 4. File Structure and Roles
In FD001, data is packaged across three canonical text files:
1. `train_FD001.txt`: Complete run-to-failure sequences for 100 engine units. Telemetry runs from cycle 1 until catastrophic failure threshold.
2. `test_FD001.txt`: Truncated engine operating sequences for 100 units. The time series is stopped at an unspecified cycle prior to system failure.
3. `RUL_FD001.txt`: A single column of 100 integer values containing the actual Remaining Useful Life (RUL in cycles) for each corresponding test unit at its final recorded test cycle.

## 5. Local source identity and verification

The committed `data/samples` files are generated synthetic C-MAPSS-shaped fixtures. Their generator is `scripts/generate_synthetic_cmapss.py` (seed 42; default 15 training units and 10 test units). They are not NASA's original FD001 distribution and cannot establish official benchmark accuracy.

Original NASA files must be obtained separately and imported into a fresh dataset version. The importer records SHA-256 over the exact uploaded bytes, role, filename, parser report, row count and engine count. Dataset detail exposes these values. Line endings and whitespace affect byte hashes, even when telemetry values are equivalent. This repository does not assert canonical official-distribution checksums.

Preparing seals a version. Experiment manifests reference its checksum and persist separate feature snapshots with train/validation unit IDs, scaler parameters and snapshot checksums. Changed inputs require a new version. Synthetic source records identify the generator path and data kind explicitly.
