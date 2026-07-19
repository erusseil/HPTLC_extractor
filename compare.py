import numpy as np
import networkx as nx
import pandas as pd
import os
import hptlc
import skfda
from skfda.preprocessing.dim_reduction import FPCA
from skfda.preprocessing.registration import LeastSquaresShiftRegistration
import math

n_components = 5
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

    empty = pd.DataFrame(data=None, index=range(n_components), columns=indexes)

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


def compute_shifts(r, g, b, grid_points):
    """Per-sample translation (in the curve's normalized [0, 1] domain) that
    best aligns the combined R+G+B signal to the population's mean.

    Estimated from the combined signal — using all three channels' info
    rather than picking one arbitrarily — since the shift itself is a single
    physical migration-distance offset shared by all three.
    """
    combined_fd = skfda.FDataGrid(data_matrix=r + g + b, grid_points=grid_points,
                                   extrapolation="bounds")
    shift_registration = LeastSquaresShiftRegistration(extrapolation="bounds")
    shift_registration.fit_transform(combined_fd)
    return shift_registration.deltas_


def apply_shifts(r, g, b, grid_points, deltas):
    """Translate each channel by its sample's shift. Translation only —
    curves are never stretched or compressed — and points that shift past
    the original edge are filled with that edge's own value rather than
    extrapolated.
    """
    rgb_fd = skfda.FDataGrid(data_matrix=np.stack([r, g, b], axis=-1), grid_points=grid_points,
                              extrapolation="bounds")
    aligned = rgb_fd.shift(deltas, extrapolation="bounds").data_matrix
    return aligned[:, :, 0], aligned[:, :, 1], aligned[:, :, 2]


def align_channels(r, g, b, grid_points):
    """Shift each sample's R/G/B curves by one shared, per-sample translation
    along the migration axis, so an uneven solvent front (which shifts the
    whole spectrum, not just one channel) doesn't get mistaken for a
    different compound by the FPCA/distance steps downstream.
    """
    deltas = compute_shifts(r, g, b, grid_points)
    return apply_shifts(r, g, b, grid_points, deltas)


def get_alignment(elu, obs):
    """Per-sample shift and aligned curves for one combo, computed exactly
    as `update_fpca` does it — lets the Visualiser show what the
    migration-axis correction actually did, for sanity-checking.

    Returns a dict keyed by sample name, or {} if no sample has data yet.
    """
    names, r, g, b = load_standard_curves(elu, obs)
    if not names:
        return {}

    grid_points = np.linspace(0, 1, r.shape[1])
    deltas = compute_shifts(r, g, b, grid_points)
    r_aligned, g_aligned, b_aligned = apply_shifts(r, g, b, grid_points, deltas)

    return {
        name: {"delta": deltas[i], "R": r_aligned[i], "G": g_aligned[i], "B": b_aligned[i]}
        for i, name in enumerate(names)
    }


def update_fpca(elu, obs):

    # Create new tables in case a new molecule was added
    create_feature_tables()
    included_files, r, g, b = load_standard_curves(elu, obs)

    if len(included_files) > 0:

        grid_points = np.linspace(0, 1, r.shape[1])
        r, g, b = align_channels(r, g, b, grid_points)

        data_matrix = np.concatenate([r, g, b], axis=1)

        fd = skfda.representation.grid.FDataGrid(
            data_matrix=data_matrix,
            grid_points=np.linspace(0, 1, data_matrix.shape[1])
        )

        fpca = FPCA(n_components=n_components)
        fpca.fit(fd)
        coefficients = fpca.transform(fd)

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
