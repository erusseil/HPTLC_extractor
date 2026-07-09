import json
import os

import pandas as pd
import streamlit as st

import compare
import hptlc

SETTINGS_PATH = os.path.join(hptlc.HPTLC_extracter.main_folder_path, "settings.json")

DEFAULT_SETTINGS = {
    "length": 200.0,
    "front": 70.0,
    "X_offset": 17.5,
    "Y_offset": 8.0,
    "inter_spot_dist": 11.0,
    "names": "c0, c1, c2, c3, c4, c5, c6, c7, bckg, c9, c10, c11, c12, c13, c14, c15",
}


def load_settings():
    """Plate geometry + product names, persisted across sessions."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as f:
            settings.update(json.load(f))
    return settings


def save_settings(settings):
    os.makedirs(hptlc.HPTLC_extracter.main_folder_path, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def render_header(title, icon="", subtitle=None):
    st.title(f"{icon} {title}".strip())
    if subtitle:
        st.caption(subtitle)
    st.divider()


def get_coverage():
    """Per-sample coverage of the 12 eluant/observation combinations.

    Returns a DataFrame indexed by sample name, one boolean column per
    "{eluant}_{observation}" combo, True where that sample already has
    extracted data for it.
    """
    main_folder_path = hptlc.HPTLC_extracter.main_folder_path
    combos = [
        f"{elu}_{obs}"
        for elu in hptlc.HPTLC_extracter.standard_eluants
        for obs in hptlc.HPTLC_extracter.standard_observations
    ]

    if not os.path.isdir(f"{main_folder_path}/standard/"):
        return pd.DataFrame(columns=combos)

    files, no_extension_files = compare.get_file_names()

    rows = {}
    for file, name in zip(files, no_extension_files):
        with open(f"{main_folder_path}/standard/{file}", "r") as f:
            data = json.load(f)
        row = {}
        for elu in hptlc.HPTLC_extracter.standard_eluants:
            for obs in hptlc.HPTLC_extracter.standard_observations:
                curve = data[elu][obs]
                row[f"{elu}_{obs}"] = all(len(curve[c]) > 0 for c in ["R", "G", "B"])
        rows[name] = row

    return pd.DataFrame.from_dict(rows, orient="index", columns=combos)
