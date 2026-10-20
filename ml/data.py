"""NASA C-MAPSS dataset acquisition and parsing.

Source: NASA PCoE "Turbofan Engine Degradation Simulation Data Set" (Saxena et al., 2008).
Simulated commercial turbofan data, not defence-specific.
"""
import hashlib
import io
import os
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

DATASET_URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
# sha256 of the outer archive as downloaded and verified on 2026-10-20.
DATASET_SHA256 = "c9c5dec12a945a82e8bb4446589d7fb3cc057b5e5d81fa1a12e25ee9912ad3b2"
INNER_ZIP = "6. Turbofan Engine Degradation Simulation Data Set/CMAPSSData.zip"

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIRECTORY", ROOT / "data" / "raw"))

SETTINGS = ["setting_1", "setting_2", "setting_3"]
SENSORS = [f"s{i}" for i in range(1, 22)]
COLUMNS = ["unit", "cycle", *SETTINGS, *SENSORS]

# Sensor descriptions/units from Saxena et al. (2008), Table 2. R = degrees Rankine.
SENSOR_META = {
    "s1": ("T2", "Total temperature at fan inlet", "degR"),
    "s2": ("T24", "Total temperature at LPC outlet", "degR"),
    "s3": ("T30", "Total temperature at HPC outlet", "degR"),
    "s4": ("T50", "Total temperature at LPT outlet", "degR"),
    "s5": ("P2", "Pressure at fan inlet", "psia"),
    "s6": ("P15", "Total pressure in bypass-duct", "psia"),
    "s7": ("P30", "Total pressure at HPC outlet", "psia"),
    "s8": ("Nf", "Physical fan speed", "rpm"),
    "s9": ("Nc", "Physical core speed", "rpm"),
    "s10": ("epr", "Engine pressure ratio (P50/P2)", "ratio"),
    "s11": ("Ps30", "Static pressure at HPC outlet", "psia"),
    "s12": ("phi", "Ratio of fuel flow to Ps30", "pps/psi"),
    "s13": ("NRf", "Corrected fan speed", "rpm"),
    "s14": ("NRc", "Corrected core speed", "rpm"),
    "s15": ("BPR", "Bypass ratio", "ratio"),
    "s16": ("farB", "Burner fuel-air ratio", "ratio"),
    "s17": ("htBleed", "Bleed enthalpy", "count"),
    "s18": ("Nf_dmd", "Demanded fan speed", "rpm"),
    "s19": ("PCNfR_dmd", "Demanded corrected fan speed", "rpm"),
    "s20": ("W31", "HPT coolant bleed", "lbm/s"),
    "s21": ("W32", "LPT coolant bleed", "lbm/s"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dataset(data_dir: Path = DATA_DIR) -> Path:
    """Download + verify + extract C-MAPSS if missing. Returns the CMAPSSData directory."""
    target = data_dir / "CMAPSSData"
    if (target / "train_FD001.txt").exists():
        return target
    data_dir.mkdir(parents=True, exist_ok=True)
    archive = data_dir / "cmapss.zip"
    if not archive.exists():
        urllib.request.urlretrieve(DATASET_URL, archive)
    digest = sha256(archive)
    if digest != DATASET_SHA256:
        raise RuntimeError(f"C-MAPSS archive checksum mismatch: {digest}")
    with zipfile.ZipFile(archive) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read(INNER_ZIP))) as inner:
            inner.extractall(target)
    return target


def read_split(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None)
    if df.shape[1] != len(COLUMNS):
        raise ValueError(f"{path.name}: expected {len(COLUMNS)} columns, got {df.shape[1]}")
    df.columns = COLUMNS
    df = df.astype({"unit": int, "cycle": int})
    if df.isna().any().any():
        raise ValueError(f"{path.name}: contains missing values")
    if not df.groupby("unit")["cycle"].apply(lambda c: (c.diff().dropna() == 1).all()).all():
        raise ValueError(f"{path.name}: cycles are not contiguous per unit")
    return df


def load_fd(subset: str = "FD001", data_dir: Path | None = None):
    """Return (train, test, test_rul) for a C-MAPSS subset. test_rul is indexed by unit."""
    d = data_dir or ensure_dataset()
    train = read_split(d / f"train_{subset}.txt")
    test = read_split(d / f"test_{subset}.txt")
    values = pd.read_csv(d / f"RUL_{subset}.txt", header=None, names=["rul"])["rul"].to_numpy()
    rul = pd.Series(values, index=range(1, len(values) + 1), name="rul")
    if len(rul) != test["unit"].nunique():
        raise ValueError("RUL file length does not match number of test units")
    return train, test, rul


def add_rul_target(df: pd.DataFrame, cap: int | None) -> pd.DataFrame:
    """Run-to-failure target: cycles remaining until each unit's last recorded cycle."""
    out = df.copy()
    out["rul"] = out.groupby("unit")["cycle"].transform("max") - out["cycle"]
    if cap is not None:
        out["rul"] = out["rul"].clip(upper=cap)
    return out
