import os

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
    baseline_key = "vis_baseline_removed"
    baseline_removed = st.session_state.get(baseline_key, True)

    bands_key = "vis_show_bands"
    show_bands = st.session_state.get(bands_key, False)

    # Bands always show the raw, unaligned crop, so aligning the curve above
    # while a band is shown would throw off the visual correlation between
    # the two — force alignment off whenever a band is displayed.
    alignment_key = "vis_show_alignment"
    show_alignment = baseline_removed and not show_bands and st.session_state.get(alignment_key, False)

    aligned_curves = compare.get_alignment(eluant, obs) if show_alignment else None

    fig = hptlc.show_curve(sample_name, eluant, obs, name2=name2, baseline_removed=baseline_removed,
                            aligned_curves=aligned_curves, channels=channels, show_bands=show_bands)
    st.pyplot(fig, use_container_width=True)

    if show_alignment:
        shown = [n for n in (sample_name, name2) if n and aligned_curves and n in aligned_curves]
        if shown:
            deltas = " · ".join(f"{n}: {aligned_curves[n]['delta']:+.4f}" for n in shown)
            st.caption(
                f"Migration-axis shift applied — {deltas} (translation over the curve's "
                "normalized [0, 1] domain; positive = shifted later). Recomputed from the "
                "current database, same as when distances are recomputed."
            )
        else:
            st.caption("No alignment to show — the selected sample(s) have no data for this combo.")

    st.toggle(
        "Baseline-corrected", value=baseline_removed, key=baseline_key,
        help="Turn off to see the curve as background-subtracted only, before baseline "
             "removal — useful for judging how well the correction is working.",
    )
    st.toggle(
        "Show migration-axis alignment", value=show_alignment, key=alignment_key,
        disabled=(not baseline_removed) or show_bands,
        help="Show the curves after the same shift-only alignment used when computing "
             "distances, so you can check the correction against the raw curves above. "
             "Only available on baseline-corrected curves, since that's what distances "
             "are computed from, and disabled while showing the extraction band, since "
             "the band is always the raw, unaligned crop.",
    )
    st.toggle(
        "Show extraction band", value=show_bands, key=bands_key,
        help="Show the actual photographed strip each curve was averaged from, stretched "
             "to line up column-for-column with the curve above it. Only available for "
             "samples extracted after this feature was added — older extractions have "
             "nothing saved to show. Turns off migration-axis alignment while active, "
             "since the band shown is always the raw, unaligned crop.",
    )
