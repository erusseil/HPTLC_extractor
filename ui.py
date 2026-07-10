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


def get_names_with_existing_data(names, eluant, observation):
    """Which of the given (non-bckg) names already have non-empty raw or
    standard data for this eluant/observation combo — used to warn before
    overwriting. Checks both folders since extract_one_image writes raw
    first, then standard, so a name can have one without the other if a
    prior extraction failed partway through."""
    main_folder_path = hptlc.HPTLC_extracter.main_folder_path
    existing = []
    for name in names:
        if name == "bckg":
            continue
        has_data = False
        for folder in ("standard", "raw"):
            path = f"{main_folder_path}/{folder}/{name}.json"
            if not os.path.isfile(path):
                continue
            with open(path, "r") as f:
                data = json.load(f)
            curve = data.get(eluant, {}).get(observation, {})
            if curve and all(len(curve.get(c, [])) > 0 for c in ["R", "G", "B"]):
                has_data = True
                break
        if has_data:
            existing.append(name)
    return existing


def distances_are_stale():
    """True if any sample's standard data is newer than the last computed
    average_distances.csv (or if that file doesn't exist yet but samples do)."""
    main_folder_path = hptlc.HPTLC_extracter.main_folder_path
    standard_dir = f"{main_folder_path}/standard/"
    distances_path = f"{main_folder_path}/distances/average_distances.csv"

    if not os.path.isdir(standard_dir):
        return False

    sample_files = [f for f in os.listdir(standard_dir) if f.endswith(".json")]
    if not sample_files:
        return False

    if not os.path.isfile(distances_path):
        return True

    distances_mtime = os.path.getmtime(distances_path)
    return any(
        os.path.getmtime(os.path.join(standard_dir, f)) > distances_mtime
        for f in sample_files
    )
