import os

import streamlit as st

import hptlc
import ui

STANDARD_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/standard/"


def file_selector(label, folder_path=STANDARD_PATH, with_null=False):
    filenames = [f for f in os.listdir(folder_path) if f.endswith(".json")]
    filenames.sort()
    if with_null:
        filenames = ["Nothing"] + filenames
    selected_filename = st.selectbox(label, filenames)
    return os.path.join(folder_path, selected_filename)


st.set_page_config(page_title="Visualiser", page_icon="📈", layout="wide")
ui.render_header(
    "Visualiser",
    icon="📈",
    subtitle="Inspect an extracted curve, optionally compared to another sample.",
)

coverage = ui.get_coverage()

col1, col2 = st.columns(2)

with col1:
    filename1 = file_selector("Show molecule:")
    sample_name = os.path.basename(filename1)[:-5]
    coverage_row = coverage.loc[sample_name] if sample_name in coverage.index else None

    eluant = st.selectbox("Eluant:", hptlc.HPTLC_extracter.standard_eluants)

    def obs_label(obs):
        if coverage_row is not None and not coverage_row.get(f"{eluant}_{obs}", True):
            return f"{obs} (no data)"
        return obs

    obs = st.selectbox("Observation:", hptlc.HPTLC_extracter.standard_observations, format_func=obs_label)

    if coverage_row is not None and not coverage_row.get(f"{eluant}_{obs}", True):
        st.info(f"No extracted data yet for **{sample_name}** under **{eluant} / {obs}** — the plot will be empty.")

    col1.divider()
    filename2 = file_selector("Compare with:", with_null=True)

col2.pyplot(hptlc.show_curve(filename1, eluant, obs, path2=filename2), use_container_width=True)
