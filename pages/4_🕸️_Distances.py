import os

import pandas as pd
import streamlit as st

import compare
import hptlc
import ui

DISTANCES_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/distances/"

ui.render_header(
    "Distances",
    icon="🕸️",
    subtitle="Recompute similarity across the database and explore the graph.",
)

col1, col2 = st.columns(2)

with col1:
    if compare.is_recompute_running():
        st.info("Currently recomputing distances.")
    elif ui.distances_are_stale():
        st.warning("New or changed data since the last recompute — the graph and "
                   "tables below don't reflect it yet.")

    st.subheader("Similarity graph")
    threshold = st.slider(
        "Graph connection threshold", value=0.05, min_value=0.0, max_value=0.25, step=0.005,
        format="%.3f",
        help="Samples with an average distance below this value are linked.",
    )

    # Stored in session_state and rendered outside the button's `if`, so it
    # survives reruns triggered by unrelated widgets elsewhere on the page
    # (e.g. the pairwise comparison selectboxes) instead of vanishing the
    # moment anything else on the page is touched.
    if st.button("🕸️ Compute full graph", use_container_width=True):
        if not os.path.isfile(f"{DISTANCES_PATH}/average_distances.csv"):
            st.warning("No distances yet — recompute them first.")
            st.session_state["distances_graph_fig"] = None
        else:
            G, labels, edges, scaled_weights = compare.build_graph(threshold)
            if G is None:
                st.warning("The linking threshold is too low, or the samples are too different — no graph could be built.")
                st.session_state["distances_graph_fig"] = None
            else:
                st.session_state["distances_graph_fig"] = compare.plotly_distance_graph(G, labels, edges, scaled_weights)

    if st.session_state.get("distances_graph_fig") is not None:
        st.plotly_chart(st.session_state["distances_graph_fig"], use_container_width=True)

with col2:
    st.subheader("Pairwise comparison")
    if not os.path.isfile(f"{DISTANCES_PATH}/average_distances.csv"):
        st.info("No distances yet — extract a sample first; distances are recomputed "
                "automatically afterward.")
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
