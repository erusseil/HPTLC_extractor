import streamlit as st
from PIL import Image

# App title
st.title("PNG Viewer")

# File uploader (only PNG files)
uploaded_file = st.file_uploader("Upload a PNG file", type=["png"])

# Display the image if uploaded
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded PNG", use_column_width=True)
else:
    st.info("Please upload a PNG file to display.")
