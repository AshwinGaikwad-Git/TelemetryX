"""Canonical column names, sensor metadata, and default constants for C-MAPSS."""

# 26 Canonical column names in standard C-MAPSS order
SETTINGS_COLUMNS = [
    "operational_setting_1",
    "operational_setting_2",
    "operational_setting_3",
]

SENSOR_COLUMNS = [f"sensor_{i}" for i in range(1, 22)]

ALL_COLUMNS = ["unit_number", "cycle"] + SETTINGS_COLUMNS + SENSOR_COLUMNS

# Invariant sensors in FD001 that have zero/near-zero variance across all units
FD001_INVARIANT_SENSORS = [
    "sensor_1",
    "sensor_5",
    "sensor_6",
    "sensor_10",
    "sensor_16",
    "sensor_18",
    "sensor_19",
]

# Informative degradation sensors in FD001 (14 sensors)
FD001_INFORMATIVE_SENSORS = [s for s in SENSOR_COLUMNS if s not in FD001_INVARIANT_SENSORS]

# Engineering descriptions for the 21 sensors
SENSOR_DESCRIPTIONS = {
    "sensor_1": "T2 - Total temperature at fan inlet (°R)",
    "sensor_2": "T24 - Total temperature at LPC outlet (°R)",
    "sensor_3": "T30 - Total temperature at HPC outlet (°R)",
    "sensor_4": "T50 - Total temperature at LPT outlet (°R)",
    "sensor_5": "P2 - Pressure at fan inlet (psia)",
    "sensor_6": "P15 - Total pressure in bypass-duct (psia)",
    "sensor_7": "P30 - Total pressure at HPC outlet (psia)",
    "sensor_8": "Nf - Physical fan speed (rpm)",
    "sensor_9": "Nc - Physical core speed (rpm)",
    "sensor_10": "epr - Engine pressure ratio (P50/P2)",
    "sensor_11": "Ps30 - Static pressure at HPC outlet (psia)",
    "sensor_12": "phi - Ratio of fuel flow to Ps30 (pps/psi)",
    "sensor_13": "NRf - Corrected fan speed (rpm)",
    "sensor_14": "NRc - Corrected core speed (rpm)",
    "sensor_15": "BPR - Bypass Ratio",
    "sensor_16": "farB - Burner fuel-air ratio",
    "sensor_17": "htBleed - Bleed Enthalpy (BTU/lbm)",
    "sensor_18": "Nf_dmd - Demanded fan speed (rpm)",
    "sensor_19": "PCNfR_dmd - Demanded corrected fan speed (rpm)",
    "sensor_20": "W31 - HPT coolant bleed (lbm/s)",
    "sensor_21": "W32 - LPT coolant bleed (lbm/s)",
}

DEFAULT_RUL_CAP = 125
DEFAULT_ROLLING_WINDOWS = [5, 15]
