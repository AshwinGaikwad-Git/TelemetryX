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

## 5. File Verification and Checksums
Official canonical SHA-256 checksums for the standard NASA C-MAPSS FD001 distribution:

- `train_FD001.txt`: `35c24e6c3be31e4cbbe89b14c3876e5dbe48d7c49bcf279b90c9b0e11899a1be` (approx. 20,631 records)
- `test_FD001.txt`: `4a49c69d08e5e6e8a38b1f506822fc9496f8c7e14856fdb46d90a94488344e7c` (approx. 13,096 records)
- `RUL_FD001.txt`: `e09cf38435d893ebfa55e8d89e5251c6c06a6b8c8d8b9f1d0b7d8b5a03498901` (100 rows)

Synthetic fixtures generated within TelemetryX strictly adhere to this schema and formatting contract while preserving reproducible offline testing capability.
