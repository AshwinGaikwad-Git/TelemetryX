# NASA C-MAPSS FD001 Data Dictionary

## 1. File Layout
Every row in `train_FD001.txt` and `test_FD001.txt` contains 26 space-separated numerical values representing an engine cycle snapshot:
- Column 1: Engine Unit Number (positive integer)
- Column 2: Time in Operational Cycles (positive integer, monotonically increasing per unit)
- Columns 3 to 5: Operational Settings 1 to 3
- Columns 6 to 26: Sensor Measurements 1 to 21

## 2. Operational Settings

| Column Index | Field Name | Description | Nominal Units | FD001 Behavior |
|---|---|---|---|---|
| 3 | `operational_setting_1` | Altitude | Trajectory / Flight envelope | Fixed near sea level (~0.00 ± 0.002) |
| 4 | `operational_setting_2` | Mach Number | Mach velocity ratio | Fixed near sea level (~0.00 ± 0.0005) |
| 5 | `operational_setting_3` | Throttle Resolver Angle (TRA) | Power demand angle (deg) | Fixed at 100.0 |

In FD001, operational settings represent flight condition variation within nominal sensor noise rather than multi-regime switching.

## 3. Telemetry Sensors (Columns 6 to 26)

| Sensor | Symbol / Code | Description | Nominal Units | Degradation Trend in FD001 | Status in Feature Selection |
|---|---|---|---|---|---|
| Sensor 1 | `T2` | Total temperature at fan inlet | °R | Invariant (~518.67) | Dropped (Zero variance) |
| Sensor 2 | `T24` | Total temperature at LPC outlet | °R | Increases with wear | **Selected** |
| Sensor 3 | `T30` | Total temperature at HPC outlet | °R | Increases with wear | **Selected** |
| Sensor 4 | `T50` | Total temperature at LPT outlet | °R | Increases with wear | **Selected** |
| Sensor 5 | `P2` | Pressure at fan inlet | psia | Invariant (~14.62) | Dropped (Zero variance) |
| Sensor 6 | `P15` | Total pressure in bypass-duct | psia | Invariant (~21.61) | Dropped (Zero variance) |
| Sensor 7 | `P30` | Total pressure at HPC outlet | psia | Decreases with wear | **Selected** |
| Sensor 8 | `Nf` | Physical fan speed | rpm | Increases / shifts with wear | **Selected** |
| Sensor 9 | `Nc` | Physical core speed | rpm | Increases with wear | **Selected** |
| Sensor 10 | `epr` | Engine pressure ratio (P50/P2) | — | Invariant (~1.30) | Dropped (Zero variance) |
| Sensor 11 | `Ps30` | Static pressure at HPC outlet | psia | Decreases with wear | **Selected** |
| Sensor 12 | `phi` | Ratio of fuel flow to Ps30 | pps/psi | Decreases / shifts | **Selected** |
| Sensor 13 | `NRf` | Corrected fan speed | rpm | Shifts with wear | **Selected** |
| Sensor 14 | `NRc` | Corrected core speed | rpm | Shifts with wear | **Selected** |
| Sensor 15 | `BPR` | Bypass Ratio | — | Increases with wear | **Selected** |
| Sensor 16 | `farB` | Burner fuel-air ratio | — | Invariant (~0.03) | Dropped (Zero variance) |
| Sensor 17 | `htBleed` | Bleed Enthalpy | BTU/lbm | Increases with wear | **Selected** |
| Sensor 18 | `Nf_dmd` | Demanded fan speed | rpm | Invariant (~2388) | Dropped (Zero variance) |
| Sensor 19 | `PCNfR_dmd` | Demanded corrected fan speed | rpm | Invariant (~100) | Dropped (Zero variance) |
| Sensor 20 | `W31` | High-pressure turbines coolant bleed | lbm/s | Decreases with wear | **Selected** |
| Sensor 21 | `W32` | Low-pressure turbines coolant bleed | lbm/s | Decreases with wear | **Selected** |

### Selected Features Summary
For FD001, 7 sensors (`s1, s5, s6, s10, s16, s18, s19`) exhibit near-zero variance across all cycles and units. The 14 informative sensors (`s2, s3, s4, s7, s8, s9, s11, s12, s13, s14, s15, s17, s20, s21`) carry the physical degradation signatures of High-Pressure Compressor (HPC) wear.
