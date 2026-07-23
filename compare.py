import numpy as np
import networkx as nx
import pandas as pd
import os
import threading
import hptlc
import skfda
from skfda.preprocessing.dim_reduction import FPCA
from scipy.optimize import minimize
import math

# Bounds for the migration-axis correction (see align_channels): a solvent
# front that runs a little long or short at the plate's edges doesn't just
# delay a curve, it can compress or stretch it slightly too. Both are kept
# tight so the fit can't explain away a real difference between two samples
# as if it were geometric distortion.
STRETCH_BOUNDS = (0.9, 1.1)
SHIFT_BOUNDS = (-0.05, 0.05)
ALIGNMENT_MAX_ITER = 5

n_components = 5 #Per representation (curve value, curve derivative) — the
                  #two get concatenated into a total_components-length
                  #feature vector, not n_components alone.
total_components = 2 * n_components
main_folder_path = hptlc.HPTLC_extracter.main_folder_path

def get_file_names():
    files = []
    for file in os.listdir(f"{main_folder_path}/standard/"):
        if file.endswith(".json"):
            files.append(file)
    files.sort()
    no_extension_files = [k[:-5] for k in files]
    return files, no_extension_files
    
def create_feature_tables():

    files, no_extension_files = get_file_names()
    
    if not os.path.isdir(f"{main_folder_path}/features/"):
        os.makedirs(f"{main_folder_path}/features/")

    indexes = []
    for elu in hptlc.HPTLC_extracter.standard_eluants:
        for obs in hptlc.HPTLC_extracter.standard_observations:
            indexes.append(elu + "_" + obs)

    empty = pd.DataFrame(data=None, index=range(total_components), columns=indexes)

    for file in no_extension_files:
        if not os.path.isfile(f"{main_folder_path}/features/{file}.csv"):
            empty.to_csv(f"{main_folder_path}/features/{file}.csv", index=False)


def load_standard_curves(elu, obs):
    """Every sample's (R, G, B) standard curves for one combo that actually
    have data for it — the population used both to fit distances and to
    check alignment against."""
    files, no_extension_files = get_file_names()

    names, all_r, all_g, all_b = [], [], [], []
    for file, name in zip(files, no_extension_files):
        curve = pd.read_json(f"{main_folder_path}/standard/{file}")[elu][obs]
        if all(len(curve[c]) > 0 for c in ["R", "G", "B"]):
            names.append(name)
            all_r.append(curve['R'])
            all_g.append(curve['G'])
            all_b.append(curve['B'])

    return names, np.array(all_r), np.array(all_g), np.array(all_b)


def _warp(curve, grid_points, stretch, shift):
    """Evaluate `curve` (defined on grid_points, which runs from the origin
    at 0 to the migration front at 1) at stretch * t + shift for every t —
    i.e. resample it as if the plate's migration axis were rescaled and
    offset. Points that land outside the curve's original range are held
    at that edge's own value rather than extrapolated (numpy's default
    out-of-range behavior for interp)."""
    return np.interp(stretch * grid_points + shift, grid_points, curve)


def compute_affine_params(combined, grid_points):
    """Per-sample (stretch, shift) that best aligns each row of `combined`
    (the R+G+B signal) to the population's mean, within STRETCH_BOUNDS /
    SHIFT_BOUNDS. Iterates the template the same way shift-only registration
    does: re-estimate the population mean from the current best alignment,
    re-fit every sample against it, repeat.
    """
    n_samples = combined.shape[0]
    stretches = np.ones(n_samples)
    shifts = np.zeros(n_samples)

    for _ in range(ALIGNMENT_MAX_ITER):
        warped = np.array([_warp(combined[i], grid_points, stretches[i], shifts[i])
                            for i in range(n_samples)])
        template = warped.mean(axis=0)

        for i in range(n_samples):
            def cost(params, i=i):
                stretch, shift = params
                return np.sum((_warp(combined[i], grid_points, stretch, shift) - template) ** 2)

            result = minimize(cost, x0=[stretches[i], shifts[i]],
                               bounds=[STRETCH_BOUNDS, SHIFT_BOUNDS], method="L-BFGS-B")
            stretches[i], shifts[i] = result.x

    return stretches, shifts


def apply_affine(r, g, b, grid_points, stretches, shifts):
    """Apply each sample's (stretch, shift) to all three channels alike —
    the correction is a single physical migration-axis distortion shared by
    all three, not something specific to one channel."""
    n_samples = r.shape[0]
    channels = []
    for channel in (r, g, b):
        channels.append(np.array([_warp(channel[i], grid_points, stretches[i], shifts[i])
                                   for i in range(n_samples)]))
    return channels


def align_channels(r, g, b, grid_points):
    """Warp each sample's R/G/B curves by one shared, per-sample
    stretch-and-shift along the migration axis, so an uneven solvent front
    (which can both delay and slightly compress/stretch the whole spectrum,
    not just one channel) doesn't get mistaken for a different compound by
    the FPCA/distance steps downstream.
    """
    stretches, shifts = compute_affine_params(r + g + b, grid_points)
    return apply_affine(r, g, b, grid_points, stretches, shifts)


def get_alignment(elu, obs):
    """Per-sample (stretch, shift) and aligned curves for one combo,
    computed exactly as `update_fpca` does it — lets the Visualiser show
    what the migration-axis correction actually did, for sanity-checking.

    Returns a dict keyed by sample name, or {} if no sample has data yet.
    """
    names, r, g, b = load_standard_curves(elu, obs)
    if not names:
        return {}

    grid_points = np.linspace(0, 1, r.shape[1])
    stretches, shifts = compute_affine_params(r + g + b, grid_points)
    r_aligned, g_aligned, b_aligned = apply_affine(r, g, b, grid_points, stretches, shifts)

    return {
        name: {"stretch": stretches[i], "delta": shifts[i],
               "R": r_aligned[i], "G": g_aligned[i], "B": b_aligned[i]}
        for i, name in enumerate(names)
    }


def compute_derivative(matrix, grid_points):
    """First derivative of each row along its own axis, computed per channel
    (R, G, B separately) before concatenation — differentiating straight
    through a concatenated R/G/B vector would create a fake spike at every
    channel boundary, where the value jumps discontinuously.

    A near-constant or slowly-drifting difference between two curves has a
    derivative close to zero almost everywhere, while a real peak's sharp
    rise and fall survives strongly — the point of fitting FPCA on this
    alongside the raw curve, not instead of it.
    """
    dt = grid_points[1] - grid_points[0]
    return np.gradient(matrix, dt, axis=1)


def _fit_fpca_features(data_matrix):
    """Fit FPCA on a (n_samples, n_points) matrix and return its
    n_components-length coefficient vector per sample."""
    fd = skfda.representation.grid.FDataGrid(
        data_matrix=data_matrix,
        grid_points=np.linspace(0, 1, data_matrix.shape[1])
    )
    fpca = FPCA(n_components=n_components)
    fpca.fit(fd)
    return fpca.transform(fd)


def update_fpca(elu, obs):

    # Create new tables in case a new molecule was added
    create_feature_tables()
    included_files, r, g, b = load_standard_curves(elu, obs)

    if len(included_files) > 0:

        grid_points = np.linspace(0, 1, r.shape[1])
        r, g, b = align_channels(r, g, b, grid_points)
        value_matrix = np.concatenate([r, g, b], axis=1)

        derivative_matrix = np.concatenate(
            [compute_derivative(r, grid_points), compute_derivative(g, grid_points),
             compute_derivative(b, grid_points)],
            axis=1,
        )
        # Same normalization as the curves themselves: each sample's own
        # combined R+G+B is divided by that sample's own max abs (not a
        # single constant shared across the whole population) — otherwise
        # the derivative's naturally larger numeric scale would dominate the
        # combined feature vector's Euclidean distance by sheer magnitude,
        # not by being more informative, and every sample's normalization
        # would shift depending on who else happens to be in the database.
        derivative_matrix = derivative_matrix / np.max(np.abs(derivative_matrix), axis=1, keepdims=True)

        coefficients = np.concatenate([
            _fit_fpca_features(value_matrix),
            _fit_fpca_features(derivative_matrix),
        ], axis=1)

        # Update with new coeffiecients (only for samples that had data for this combo)
        for idx, file in enumerate(included_files):
            previous = pd.read_csv(f"{main_folder_path}/features/{file}.csv")
            previous[f'{elu}_{obs}'] = coefficients[idx]
            previous.to_csv(f"{main_folder_path}/features/{file}.csv", index=False)


def update_all_fpca(progress_callback=None):
    combos = [
        (elu, obs)
        for elu in hptlc.HPTLC_extracter.standard_eluants
        for obs in hptlc.HPTLC_extracter.standard_observations
    ]

    for idx, (elu, obs) in enumerate(combos):
        update_fpca(elu, obs)
        if progress_callback:
            progress_callback(idx + 1, len(combos), elu, obs)

    compute_global_distances()


# A full recompute takes long enough at real database sizes (tens of
# seconds once every eluant/observation combo has data — measured, not
# guessed) that it can't run synchronously after every single upload
# without freezing that user's page, and there's no manual trigger anymore
# either — every extraction just kicks this off in the background. This
# tiny lock only protects the two flags below (not the recompute itself),
# so checking is_recompute_running() is always instant.
_recompute_state_lock = threading.Lock()
_recompute_running = False
_recompute_pending = False


def is_recompute_running():
    with _recompute_state_lock:
        return _recompute_running


def recompute_in_background():
    """Trigger a full recompute without ever blocking the caller — meant to
    be called right after every extraction. An extraction that lands while
    one is already running doesn't start a second one racing on the same
    feature/distance files; it just marks that the database changed again,
    so the current pass restarts once more with the latest data as soon as
    it finishes, instead of the new sample being silently left out."""
    global _recompute_running, _recompute_pending

    with _recompute_state_lock:
        if _recompute_running:
            _recompute_pending = True
            return
        _recompute_running = True

    def _run():
        global _recompute_running, _recompute_pending
        try:
            while True:
                update_all_fpca()
                with _recompute_state_lock:
                    if not _recompute_pending:
                        break
                    _recompute_pending = False
        finally:
            with _recompute_state_lock:
                _recompute_running = False
                _recompute_pending = False

    threading.Thread(target=_run, daemon=True).start()


def compute_specific_distances():

    files, no_extension_files = get_file_names()
    
    if not os.path.isdir(f"{main_folder_path}/distances/"):
        os.makedirs(f"{main_folder_path}/distances/")

    for elu in hptlc.HPTLC_extracter.standard_eluants:
        for obs in hptlc.HPTLC_extracter.standard_observations:
            coefs = []
            for file in no_extension_files:
                coefs.append(pd.read_csv(f"{main_folder_path}/features/{file}.csv")[f"{elu}_{obs}"].values)

            distances = []
            for f1 in coefs:
                f1_dists = []
                for f2 in coefs:
                    if (any(np.isnan(f1))) | (any(np.isnan(f2))):
                        f1_dists.append(np.nan)
                    else:
                        f1_dists.append(round(math.dist(f1, f2), 4))
                distances.append(f1_dists)

            final = pd.DataFrame(data=distances, columns=no_extension_files, index=no_extension_files)
            final.to_csv(f"{main_folder_path}/distances/{elu}_{obs}.csv")
                
def compute_global_distances():

    files, no_extension_files = get_file_names()

    compute_specific_distances()
    all_distances = []
    for elu in hptlc.HPTLC_extracter.standard_eluants:
        for obs in hptlc.HPTLC_extracter.standard_observations:
            all_distances.append(pd.read_csv(f"{main_folder_path}/distances/{elu}_{obs}.csv").iloc[:, 1:].values)

    global_distance = np.nanmean(all_distances, axis=0)
    global_df = pd.DataFrame(data=global_distance, columns=no_extension_files, index=no_extension_files)
    global_df.to_csv(f"{main_folder_path}/distances/average_distances.csv")


def build_graph(thresh):
    """Build the similarity graph from the average distance matrix.

    Returns (G, labels, edges, scaled_weights), or (None, None, None, None)
    if no sample pair is close enough to be linked at this threshold.
    """

    matrix = pd.read_csv(main_folder_path + 'distances/average_distances.csv')
    m = np.array(matrix)[:, 1:]
    m_contiunous = m.copy().astype(float)

    link, nolink = m <= thresh, (m > thresh) | np.isnan(m_contiunous)
    m[nolink] = 0
    m[link] = 1
    m = m.astype(int)

    G = nx.from_numpy_array(m)

    edges, distances = [], []
    # Iterate over the nodes and add weights from the distance matrix
    for i in list(G.nodes):
        for j in list(G[i]):
            if (m[i, j] != 0) & (i<j):  # Look only if there is an egde on all of the matrix (because it is symmetrical)
                edges.append((i, j))
                distances.append(m_contiunous[i, j])

    if distances == []:
        return None, None, None, None

    # A perfect match (distance 0) would divide by zero under 1/distance;
    # give it a weight just above the strongest real (nonzero) match instead.
    nonzero_distances = [d for d in distances if d > 0]
    max_real_weight = 1 / min(nonzero_distances) if nonzero_distances else 1.0
    edge_weights = [(1 / d) if d > 0 else max_real_weight * 1.1 for d in distances]

    # The scaling is temporary and a better one should be chosen once more data is available
    min_weight = min(edge_weights)
    max_weight = max(edge_weights)
    if max_weight == min_weight:
        scaled_weights = [3.0 for _ in edge_weights]
    else:
        scaled_weights = [0.5 + 5 * (weight - min_weight) / (max_weight - min_weight) for weight in edge_weights]

    labels = dict(matrix['Unnamed: 0'])
    return G, labels, edges, scaled_weights


def plotly_distance_graph(G, labels, edges, scaled_weights):

    import plotly.graph_objects as go

    pos = nx.forceatlas2_layout(G, seed=42, strong_gravity=True)  # positions for all nodes

    edge_traces = []
    for (i, j), weight in zip(edges, scaled_weights):
        x0, y0 = pos[i]
        x1, y1 = pos[j]
        edge_traces.append(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode="lines",
            line=dict(width=weight, color="#94A3B8"),
            hoverinfo="skip",
            showlegend=False,
        ))

    node_x = [pos[n][0] for n in G.nodes]
    node_y = [pos[n][1] for n in G.nodes]
    node_text = [labels[n] for n in G.nodes]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(size=24, color="#0F766E", line=dict(width=1.5, color="#134E4A")),
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=10, b=10),
        height=650,
        plot_bgcolor="white",
    )
    return fig
