import streamlit as st
from PIL import Image
import os
import hptlc


files_path = []

IMAGE_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/images/"
os.makedirs(IMAGE_PATH, exist_ok=True)


st.set_page_config(layout="wide")

title_cols = st.columns(3)
title_cols[0].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)
title_cols[1].markdown("<h2 style='text-align: center; color: black; font-size: 53px;'>Spectractor</h2>", unsafe_allow_html=True)
title_cols[2].markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)


with col1:
    uploaded_files = st.file_uploader("Upload a PNG file", type=["png"], accept_multiple_files=True)
    if uploaded_files:
        files_path = []
        for uploaded_file in uploaded_files:
            # Extract original filename
            filename = uploaded_file.name
            saved_path = os.path.join(IMAGE_PATH, filename)
            with open(saved_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        
            files_path.append(f"{os.path.abspath(saved_path)}")
        
            image = Image.open(saved_file := saved_path)
            st.image(image, caption=f"Loaded from {saved_file}", use_container_width=True)


with col2:
    length = st.number_input("Length (mm)", value=200.0, min_value=0.0, step=1.0)
    front = st.number_input("Front (mm)", value=70.0, min_value=0.0, step=1.0)
    X_offset = st.number_input("X offset (mm)", value=17.5, min_value=0.0, step=0.5)
    Y_offset = st.number_input("Y offset (mm)", value=8.0, min_value=0.0, step=0.5)
    inter_spot_dist = st.number_input("Inter-spot distance (mm)", value=11.0, min_value=0.0, step=0.5)
    
    
    # Names as comma-separated
    names_input = st.text_area("Enter names (comma-separated)", "c0, c1, c2, c3, c4, c5, c6, c7, bckg, c9, c10, c11, c12, c13, c14, c15")
    names = [n.strip() for n in names_input.split(",") if n.strip()]

with col3:
    st.write("Summary:", names)

extractor = hptlc.HPTLC_extracter(names,
                            length, front, X_offset,
                            Y_offset, inter_spot_dist)


with col2:
    ## Add button to apply HPTLC_extracter
    if st.button("Extract spectra"):
        with st.spinner("Processing..."):
            for file_path in files_path:
                extractor.extract_one_image(file_path)

st.markdown("""<hr style="border: none; height: 1px; background-color: black;" />""",unsafe_allow_html=True)





