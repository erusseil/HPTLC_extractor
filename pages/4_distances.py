import streamlit as st
from PIL import Image
import os
import hptlc
import compare
import pandas as pd

    

st.set_page_config(layout="wide")

title_cols = st.columns(3)
title_cols[0].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)
title_cols[1].markdown("<h2 style='text-align: center; color: black; font-size: 53px;'>Distances</h2>", unsafe_allow_html=True)
title_cols[2].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)


col1, col2 = st.columns(2)

with col1:
    if st.button("Recompute all distances"):
        with st.spinner("Processing..."):
            compare.update_all_fpca()
    
    threshold = st.number_input("Graph connexion threshold", value=0.05, min_value=0.0, max_value=1.0, step=0.01)
    
    
    if st.button("Compute full graph"):
        compare.produce_full_graph(threshold)
        st.image(f"{hptlc.HPTLC_extracter.main_folder_path}/distances/summary_graph.png", width="content")


with col2:
    average_table = pd.read_csv(f"{hptlc.HPTLC_extracter.main_folder_path}/distances/average_distances.csv")
    current_distances = list(average_table.columns[1:].values)
    current_distances.sort()

    mol1 = st.selectbox("First product", current_distances)
    mol2 = st.selectbox("Second product", current_distances)

    average = average_table[average_table["Unnamed: 0"]==mol1][mol2].iloc[0]

    score = st.markdown(f""" <span style='font-size: 23px;
    font-weight: bold;
    '>Average distance between the two samples: {average}</span>""",
        unsafe_allow_html=True
    )

    elus = hptlc.HPTLC_extracter.standard_eluants
    obss = hptlc.HPTLC_extracter.standard_observations

    table = []
    for elu in elus:
        row = []
        for obs in obss:
            full = pd.read_csv(f"{hptlc.HPTLC_extracter.main_folder_path}/distances/{elu}_{obs}.csv")
            row.append(full[full['Unnamed: 0']==mol1][mol2].iloc[0])
        table.append(row)

    pd_table = pd.DataFrame(data=table, columns=obss, index=elus)
    st.table(pd_table)