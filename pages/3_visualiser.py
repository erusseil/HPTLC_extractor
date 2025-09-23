import streamlit as st
from PIL import Image
import os
import hptlc 


def file_selector(label, folder_path=f"{hptlc.HPTLC_extracter.main_folder_path}/standard/", with_null=False):
    filenames = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            filenames.append(filename)
    filenames.sort()
    if with_null:
        filenames = ["Nothing"] + filenames

    selected_filename = st.selectbox(label, filenames)
    return os.path.join(folder_path, selected_filename)

st.set_page_config(layout="wide")

title_cols = st.columns(3)
title_cols[0].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)
title_cols[1].markdown("<h2 style='text-align: center; color: black; font-size: 53px;'>Visualiser</h2>", unsafe_allow_html=True)
title_cols[2].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)


col1, col2 = st.columns(2)

with col1:
    
    filename1 = file_selector("Show molecule:")
    
    eluant = st.selectbox(
        "Eluant:",
        hptlc.HPTLC_extracter.standard_eluants,
    )
    
    obs = st.selectbox(
        "Observation:",
        hptlc.HPTLC_extracter.standard_observations,
    )


    col1.markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)
    filename2 = file_selector('Compare with:', with_null=True)

col2.pyplot(hptlc.show_curve(filename1, eluant, obs, path2=filename2), use_container_width=True)