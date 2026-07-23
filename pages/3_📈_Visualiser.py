import os

import pandas as pd
import streamlit as st

import compare
import hptlc
import ui

STANDARD_PATH = f"{hptlc.HPTLC_extracter.main_folder_path}/standard/"


def file_selector(label, folder_path=STANDARD_PATH, with_null=False):
    filenames = [f[:-5] for f in os.listdir(folder_path) if f.endswith(".json")]
    filenames.sort()
    if with_null:
        filenames = ["Nothing"] + filenames
    return st.selectbox(label, filenames)


ui.render_header(
    "Visualiser",
    icon="📈",
    subtitle="Inspect an extracted curve, optionally compared to another sample.",
)

coverage = ui.get_coverage()

col1, col2 = st.columns(2)

with col1:
    sample_name = file_selector("Show molecule:")
    coverage_row = coverage.loc[sample_name] if sample_name in coverage.index else None

    # Keyed on the extraction nonce so a fresh extraction forces these
    # widgets to pick up the new default instead of keeping whatever was
    # previously selected (Streamlit selectboxes otherwise "remember" their
    # displayed value once mounted, ignoring later session_state writes).
    nonce = st.session_state.get("extract_nonce", 0)
    last_eluant = st.session_state.get("last_extracted_eluant")
    last_obs = st.session_state.get("last_extracted_obs")
    eluant_index = (hptlc.HPTLC_extracter.standard_eluants.index(last_eluant)
                    if last_eluant in hptlc.HPTLC_extracter.standard_eluants else 0)
    obs_index = (hptlc.HPTLC_extracter.standard_observations.index(last_obs)
                 if last_obs in hptlc.HPTLC_extracter.standard_observations else 0)

    eluant = st.selectbox("Eluant:", hptlc.HPTLC_extracter.standard_eluants,
                           index=eluant_index, key=f"vis_eluant_{nonce}")

    def obs_label(obs):
        if coverage_row is not None and not coverage_row.get(f"{eluant}_{obs}", True):
            return f"{obs} (no data)"
        return obs

    obs = st.selectbox("Observation:", hptlc.HPTLC_extracter.standard_observations,
                        index=obs_index, format_func=obs_label, key=f"vis_obs_{nonce}")

    if coverage_row is not None and not coverage_row.get(f"{eluant}_{obs}", True):
        st.info(f"No extracted data yet for **{sample_name}** under **{eluant} / {obs}** — the plot will be empty.")

    col1.divider()
    compare_name = file_selector("Compare with:", with_null=True)
    name2 = None if compare_name == "Nothing" else compare_name

with col2:
    channels = st.selectbox("Channel(s) to plot:", hptlc.CHANNEL_CHOICES,
                             help="Luminance is the unweighted average of R, G and B.")

    # Read before rendering the plot so the toggles can be placed below it
    # while still reflecting the current click on this same render.
    bands_key = "vis_show_bands"
    show_bands = st.session_state.get(bands_key, False)

    alignment_key = "vis_show_alignment"
    show_alignment = st.session_state.get(alignment_key, False)

    derivative_key = "vis_show_derivative"
    show_derivative = st.session_state.get(derivative_key, False)

    aligned_curves = compare.get_alignment(eluant, obs) if show_alignment else None

    fig = hptlc.show_curve(sample_name, eluant, obs, name2=name2,
                            aligned_curves=aligned_curves, channels=channels, show_bands=show_bands,
                            show_derivative=show_derivative)
    st.plotly_chart(fig, use_container_width=True)

    # Built from the same series show_curve just plotted (never re-derived
    # independently), so it always matches what's on screen — full curves
    # regardless of any zoom/pan applied in the chart above, since that's
    # purely a client-side view and never touches this underlying data.
    series = hptlc.get_channel_series(sample_name, eluant, obs, name2=name2,
                                       aligned_curves=aligned_curves, channels=channels,
                                       show_derivative=show_derivative)
    csv_bytes = pd.DataFrame({col: pd.Series(values) for col, values in series.items()}
                              ).to_csv(index_label="index").encode("utf-8")
    filename = "_".join([
        sample_name, *([f"vs_{name2}"] if name2 else []), eluant, obs, channels,
        *(["aligned"] if show_alignment else []), *(["derivative"] if show_derivative else []),
    ]) + ".csv"
    st.download_button("⬇️ Download as CSV", data=csv_bytes, file_name=filename, mime="text/csv",
                        use_container_width=True)

    if show_alignment:
        shown = [n for n in (sample_name, name2) if n and aligned_curves and n in aligned_curves]
        if shown:
            corrections = " · ".join(
                f"{n}: ×{aligned_curves[n]['stretch']:.3f} {aligned_curves[n]['delta']:+.4f}"
                for n in shown
            )
            st.caption(
                f"Migration-axis correction applied — {corrections} (stretch around the "
                "curve's normalized [0, 1] domain, then a shift; stretch >1 = elongated, "
                "positive shift = later). Recomputed from the current database, same as "
                "when distances are recomputed."
            )
        else:
            st.caption("No alignment to show — the selected sample(s) have no data for this combo.")

    st.toggle(
        "Show migration-axis alignment", value=show_alignment, key=alignment_key,
        help="Show the curves after the same shift-only alignment used when computing "
             "distances, so you can check the correction against the raw curves above. "
             "If the extraction band is also shown, it's warped by the same stretch/shift "
             "so the two stay lined up.",
    )
    st.toggle(
        "Show extraction band", value=show_bands, key=bands_key,
        help="Show the actual photographed strip each curve was averaged from, stretched "
             "to line up column-for-column with the curve above it (and warped to match "
             "if migration-axis alignment is also on). Only available for samples "
             "extracted after this feature was added — older extractions have nothing "
             "saved to show.",
    )
    st.toggle(
        "Show derivative", value=show_derivative, key=derivative_key,
        help="Plot the rate of change instead of the value — a flat offset between two "
             "curves nearly cancels out, while a sharp peak still stands out clearly. This "
             "is one of the two views combined into the distance calculation (the other "
             "being the plain curve above), shown here so you can see how it behaves.",
    )
