import os

import pandas as pd
import streamlit as st

import compare
import hptlc
import ui

DISTANCES_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/distances/"

st.set_page_config(page_title="Distances", page_icon="🕸️", layout="wide")
ui.render_header(
    "Distances",
    icon="🕸️",
    subtitle="Recompute similarity across the database and explore the graph.",
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Recompute")
    if st.button("🔁 Recompute all distances", use_container_width=True):
        progress = st.progress(0.0, text="Starting...")

        def on_progress(done, total, elu, obs):
            progress.progress(done / total, text=f"Updating FPCA for {elu} / {obs} ({done}/{total})")

        try:
            compare.update_all_fpca(progress_callback=on_progress)
            progress.empty()
            st.success("Distances recomputed.")
        except Exception as e:
            progress.empty()
            st.error(
                "Recompute failed — the feature tables in HPTLC_data/features/ look "
                f"inconsistent and may need to be regenerated ({e})."
            )

    st.subheader("Similarity graph")
    threshold = st.number_input(
        "Graph connection threshold", value=0.05, min_value=0.0, max_value=1.0, step=0.01,
        help="Samples with an average distance below this value are linked.",
    )

    if st.button("🕸️ Compute full graph", use_container_width=True):
        if not os.path.isfile(f"{DISTANCES_PATH}/average_distances.csv"):
            st.warning("No distances yet — recompute them first.")
        else:
            G, labels, edges, scaled_weights = compare.build_graph(threshold)
            if G is None:
                st.warning("The linking threshold is too low, or the samples are too different — no graph could be built.")
            else:
                st.plotly_chart(compare.plotly_distance_graph(G, labels, edges, scaled_weights), use_container_width=True)

with col2:
    st.subheader("Pairwise comparison")
    if not os.path.isfile(f"{DISTANCES_PATH}/average_distances.csv"):
        st.info("No distances yet — recompute them from the left panel first.")
    else:
        average_table = pd.read_csv(f"{DISTANCES_PATH}/average_distances.csv")
        current_distances = sorted(average_table.columns[1:])

        mol1 = st.selectbox("First product", current_distances)
        mol2 = st.selectbox("Second product", current_distances)

        average = average_table[average_table["Unnamed: 0"] == mol1][mol2].iloc[0]
        st.metric("Average distance between the two samples", f"{average:.4f}")

        elus = hptlc.HPTLC_extracter.standard_eluants
        obss = hptlc.HPTLC_extracter.standard_observations

        table = []
        for elu in elus:
            row = []
            for obs in obss:
                full = pd.read_csv(f"{DISTANCES_PATH}/{elu}_{obs}.csv")
                row.append(full[full['Unnamed: 0'] == mol1][mol2].iloc[0])
            table.append(row)

        pd_table = pd.DataFrame(data=table, columns=obss, index=elus)
        st.table(pd_table)
