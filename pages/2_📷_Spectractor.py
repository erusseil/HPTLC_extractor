import os

import streamlit as st
from PIL import Image, ImageDraw

import hptlc
import ui

IMAGE_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/images/"
os.makedirs(IMAGE_PATH, exist_ok=True)

st.set_page_config(page_title="Spectractor", page_icon="📷", layout="wide")
ui.render_header(
    "Spectractor",
    icon="📷",
    subtitle="Upload plate photos, check the spot alignment, then extract spectra.",
)

settings = ui.load_settings()


def draw_spot_overlay(image, windows):
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    for window in windows:
        is_bckg = window["name"] == "bckg"
        color = "#F97316" if is_bckg else "#0F766E"
        draw.rectangle(
            [window["left"], window["top"], window["right"], window["bottom"]],
            outline=color, width=3,
        )
        if window["name"]:
            draw.text((window["left"], max(0, window["top"] - 18)), window["name"], fill=color)
    return overlay


def run_extraction(files_info, names, length, front, X_offset, Y_offset, inter_spot_dist, eluant, observation):
    extractor = hptlc.HPTLC_extracter(names, length, front, X_offset, Y_offset, inter_spot_dist)
    progress = st.progress(0.0, text="Starting extraction...")
    results = []
    for i, (filename, file_path) in enumerate(files_info):
        try:
            extractor.extract_one_image(file_path, eluant, observation)
            results.append((filename, True, ""))
            st.session_state["last_extracted_eluant"] = eluant
            st.session_state["last_extracted_obs"] = observation
            st.session_state["extract_nonce"] = st.session_state.get("extract_nonce", 0) + 1
        except Exception as e:
            results.append((filename, False, str(e)))
        progress.progress((i + 1) / len(files_info), text=f"Extracted {filename} ({i + 1}/{len(files_info)})")
    progress.empty()

    for filename, ok, err in results:
        if ok:
            st.success(f"{filename} — extracted")
        else:
            st.error(f"{filename} — failed: {err}")

    if any(ok for _, ok, _ in results):
        st.page_link("pages/3_📈_Visualiser.py", label="→ Go check the extracted curves", icon="📈")


@st.dialog("⚠️ Overwrite existing data?")
def confirm_overwrite_dialog(affected_names, files_info, names, length, front,
                              X_offset, Y_offset, inter_spot_dist, eluant, observation):
    st.write(
        f"**{len(affected_names)} product(s)** already have data for **{eluant} / {observation}**: "
        f"{', '.join(affected_names)}."
    )
    st.write("Extracting now will overwrite it. There's no automatic backup yet, "
              "so this can't be undone from within the app.")

    col1, col2 = st.columns(2)
    if col1.button("Cancel", use_container_width=True):
        st.rerun()
    if col2.button("Yes, overwrite", type="primary", use_container_width=True):
        run_extraction(files_info, names, length, front, X_offset, Y_offset, inter_spot_dist, eluant, observation)


settings_col, preview_col = st.columns([1, 2])

with settings_col:
    st.subheader("Plate geometry")
    length = st.number_input("Length (mm)", value=settings["length"], min_value=0.0, step=1.0,
                              help="Full length of the plate.")
    front = st.number_input("Front (mm)", value=settings["front"], min_value=0.0, step=1.0,
                             help="Distance from the spot line to the solvent front.")
    X_offset = st.number_input("X offset (mm)", value=settings["X_offset"], min_value=0.0, step=0.5,
                                format="%.1f",
                                help="Distance from the left edge of the plate to the center of the first spot.")
    Y_offset = st.number_input("Y offset (mm)", value=settings["Y_offset"], min_value=0.0, step=0.5,
                                format="%.1f",
                                help="Distance from the bottom edge of the plate to the center of the spots.")
    inter_spot_dist = st.number_input("Inter-spot distance (mm)", value=settings["inter_spot_dist"],
                                       min_value=0.0, step=0.5, format="%.1f")

    names_input = st.text_area(
        "Product names (comma-separated, in plate order)",
        settings["names"],
        help="Exactly one name must be 'bckg' — the empty track used to calibrate the background.",
    )
    names = [n.strip() for n in names_input.split(",") if n.strip()]

    if st.button("💾 Save these as default", use_container_width=True):
        ui.save_settings({
            "length": length, "front": front, "X_offset": X_offset,
            "Y_offset": Y_offset, "inter_spot_dist": inter_spot_dist,
            "names": names_input,
        })
        st.toast("Saved — these values will be pre-filled next time.")

    st.divider()

    n_bckg = names.count("bckg")
    names_valid = n_bckg == 1
    if n_bckg == 0:
        st.error("One of the names must be exactly `bckg` (the empty track) — none found.")
    elif n_bckg > 1:
        st.error(f"Exactly one name must be `bckg` — found {n_bckg}.")
    else:
        st.success(f"{len(names)} spots, background track OK.")

    non_bckg = [n for n in names if n != "bckg"]
    dupes = sorted({n for n in non_bckg if non_bckg.count(n) > 1})
    if dupes:
        st.warning(f"Duplicate names will overwrite each other's data: {', '.join(dupes)}")

with preview_col:
    st.subheader("Upload & check alignment")

    PICK_ONE = "— select —"
    with st.container(border=True):
        st.markdown("**🧭 Which condition is this upload for?**")
        cond_cols = st.columns(2)
        eluant_choice = cond_cols[0].selectbox("Eluant used", [PICK_ONE] + hptlc.HPTLC_extracter.standard_eluants)
        obs_choice = cond_cols[1].selectbox("Observation", [PICK_ONE] + hptlc.HPTLC_extracter.standard_observations)

    eluant = None if eluant_choice == PICK_ONE else eluant_choice
    observation = None if obs_choice == PICK_ONE else obs_choice
    condition_selected = eluant is not None and observation is not None

    if not condition_selected:
        st.warning("Select both the eluant and observation before extracting.")

    uploader_label = (f"Upload PNG plate photo(s) for {eluant} / {observation}"
                       if condition_selected else "Upload PNG plate photo(s)")
    uploaded_files = st.file_uploader(uploader_label, type=["png"], accept_multiple_files=True)

    files_info = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            saved_path = os.path.join(IMAGE_PATH, uploaded_file.name)
            with open(saved_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            files_info.append((uploaded_file.name, os.path.abspath(saved_path)))

            image = Image.open(saved_path)
            try:
                windows = hptlc.HPTLC_extracter.compute_spot_windows(
                    (image.height, image.width), length, X_offset, Y_offset,
                    front, inter_spot_dist, names,
                )
                st.image(draw_spot_overlay(image, windows),
                         caption=f"{uploaded_file.name} — check the boxes line up with the spots",
                         use_container_width=True)
            except ValueError as e:
                st.error(f"{uploaded_file.name}: {e}")
                st.image(image, caption=uploaded_file.name, use_container_width=True)

    can_extract = names_valid and bool(files_info) and condition_selected
    if st.button("🧪 Extract spectra", disabled=not can_extract, use_container_width=True):
        affected_names = ui.get_names_with_existing_data(names, eluant, observation)
        if affected_names:
            confirm_overwrite_dialog(affected_names, files_info, names, length, front,
                                      X_offset, Y_offset, inter_spot_dist, eluant, observation)
        else:
            run_extraction(files_info, names, length, front, X_offset, Y_offset, inter_spot_dist, eluant, observation)
