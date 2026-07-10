import streamlit as st

import ui

st.set_page_config(
    page_title="HPTLC_extractor",
    page_icon="🧪",
    layout="wide",
)

ui.render_header(
    "HPTLC Extractor",
    icon="🧪",
    subtitle="Turn HPTLC plate photos into spectra, and compare samples across your database.",
)

coverage = ui.get_coverage()
n_samples = len(coverage)
n_combos = coverage.shape[1] if n_samples else 12
n_filled = int(coverage.sum().sum()) if n_samples else 0
n_possible = n_samples * n_combos if n_samples else 0
coverage_pct = f"{100 * n_filled / n_possible:.0f}%" if n_possible else "—"

metric_cols = st.columns(3)
metric_cols[0].metric("Samples in database", n_samples)
metric_cols[1].metric("Eluant × observation combos tracked", n_combos)
metric_cols[2].metric("Data coverage", coverage_pct)

if ui.distances_are_stale():
    st.warning("New or changed data since the last recompute — the similarity graph and "
               "distances on the Distances page don't reflect it yet.")

st.subheader("Guided workflow")
step_cols = st.columns(3)
with step_cols[0]:
    st.page_link("pages/2_📷_Spectractor.py", label="**1. Spectractor**", icon="📷")
    st.caption("Upload plate photos, check spot alignment, and extract spectra.")
with step_cols[1]:
    st.page_link("pages/3_📈_Visualiser.py", label="**2. Visualiser**", icon="📈")
    st.caption("Inspect an extracted curve, optionally compared to another sample.")
with step_cols[2]:
    st.page_link("pages/4_🕸️_Distances.py", label="**3. Distances**", icon="🕸️")
    st.caption("Recompute similarity across the database and explore the graph.")

st.divider()

st.subheader("Sample coverage")
st.caption("Which samples already have extracted data, for each eluant / observation combination.")

if n_samples == 0:
    st.info("No samples yet — head to **Spectractor** to upload your first plate photo.")
else:
    st.dataframe(
        coverage.replace({True: "✅", False: ""}),
        use_container_width=True,
    )
