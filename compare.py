import json
import numpy as np
import networkx as nx
from os import listdir
from os.path import isfile, join
import pandas as pd
import os
import hptlc
import config
import warnings
import time
import skfda
from skfda.preprocessing.dim_reduction import FPCA
import glob
import math

n_components = 5


def get_file_names(main_folder_path):
    files = []
    for file in os.listdir(f"{main_folder_path}/standard/"):
        if file.endswith(".json"):
            files.append(file)
    files.sort()
    no_extension_files = [k[:-5] for k in files]
    return files, no_extension_files
    
def create_feature_tables(main_folder_path):

    files, no_extension_files = get_file_names(main_folder_path)
    
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


def update_fpca(main_folder_path, elu, obs):

    # Create new tables in case a new molecule was added
    create_feature_tables(main_folder_path)
    files, no_extension_files = get_file_names(main_folder_path)

    all_curves = []
    for file in files:
        curve = pd.read_json(f"{main_folder_path}/standard/{file}")[elu][obs]
        empty = [len(curve[col])==0 for col in ["R", "G", "B"]]
        if not any(empty):
            all_curves.append(curve['R']+curve['G']+curve['B'])

    data_matrix = np.array(all_curves)

    if np.size(data_matrix)>0:

        fd = skfda.representation.grid.FDataGrid(
            data_matrix=data_matrix,
            grid_points=np.linspace(0, 1, data_matrix.shape[1])
        )
        
        fpca = FPCA(n_components=n_components)
        fpca.fit(fd)
        coefficients = fpca.transform(fd)
    
        # Update with new coeffiecients
        for idx, file in enumerate(no_extension_files):
            previous = pd.read_csv(f"{main_folder_path}/features/{file}.csv")
            previous[f'{elu}_{obs}'] = coefficients[idx]
            previous.to_csv(f"{main_folder_path}/features/{file}.csv", index=False)

def compute_specific_distances(main_folder_path):

    files, no_extension_files = get_file_names(main_folder_path)
    
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
                
def compute_global_distances(main_folder_path):

    files, no_extension_files = get_file_names(main_folder_path)

    compute_specific_distances(main_folder_path)
    all_distances = []
    for elu in hptlc.HPTLC_extracter.standard_eluants:
        for obs in hptlc.HPTLC_extracter.standard_observations:
            all_distances.append(pd.read_csv(f"{main_folder_path}/distances/{elu}_{obs}.csv").iloc[:, 1:].values)

    global_distance = np.nanmean(all_distances, axis=0)
    global_df = pd.DataFrame(data=global_distance, columns=no_extension_files, index=no_extension_files)
    global_df.to_csv(f"{main_folder_path}/distances/average_distances.csv")


def show_results(main_folder_path, name, n=5):

    #In case the user inputs a file
    if name[-4:]=='.csv':
        name = name[:-4]

    df = pd.read_csv(f"{main_folder_path}/distances/{name}.csv")

    ord_dist, ord_others = df['Normalized distance'], df['Name']

    print(f"\nSamples most similar to {name}:\n")
    for i in range(min(n, len(ord_others))):
        print(f"{ord_others[i]} : {ord_dist[i]:.2f}")

    print('___________________\n')


def produce_full_graph(main_folder_path, thresh):

    matrix = pd.read_csv(main_folder_path + 'distances/average_distances.csv')
    m = np.array(matrix)[:, 1:]
    m_contiunous = m.copy().astype(float)

    link, nolink = (m<=thresh) & (m!=0), (m>thresh) | (m==thresh)
    m[nolink] = 0
    m[link] = 1
    m = m.astype(int)

    G = nx.from_numpy_array(m)

    edge_weights = []
    # Iterate over the nodes and add weights from the distance matrix
    for i in list(G.nodes):
        for j in list(G[i]):
            if (m[i, j] != 0) & (i<j):  # Look only if there is an egde on all of the matrix (because it is symmetrical)
                edge_weights.append(1/(m_contiunous[i, j]))  # Assign distance as edge weight

    if edge_weights == []:
        print("The linking threshold is too low or the samples are too different. No link has been created. No graph has been computed")

    else:
        # The scaling is temporary and a better one should be chosen once more data is available
        min_weight = min(edge_weights)
        max_weight = max(edge_weights)
        scaled_weights = [0.5 + 5 * (weight - min_weight) / (max_weight - min_weight) for weight in edge_weights]

        plot_distance_graph(G, dict(matrix['Unnamed: 0']), scaled_weights, main_folder_path + 'distances/summary_graph.png')


def plot_distance_graph(G, labels, scaled_weights, save_path):

    import matplotlib.pyplot as plt

    pos = nx.forceatlas2_layout(G, seed=42, strong_gravity=True)  # positions for all nodes

    plt.figure(figsize=(10,10))
    nx.draw(G, pos=pos)

    # nodes
    options = {"edgecolors": "tab:gray", "node_size": 2000, "alpha": 0.9}
    nx.draw_networkx_nodes(G, pos, **options)

    # edges
    nx.draw_networkx_edges(G, pos, width=scaled_weights, alpha=1)
    nx.draw_networkx_labels(G, pos, labels, font_size=16, font_color="black")

    plt.axis("off")
    plt.savefig(save_path)
    plt.show()


def matrix_and_graph():

    main_folder_path = hptlc.HPTLC_extracter.main_folder_path
    path = main_folder_path + '/distances/'
    all_files = [f for f in listdir(path) if isfile(join(path, f))]

    dfs = []
    for file in all_files:
        dfs.append(pd.read_csv(path + file))

    sample_names = [k[:-4] for k in all_files]

    # Create an empty dictionary to hold the final distance matrix
    distance_matrix = {name: {name: 0 for name in sample_names} for name in sample_names}

    # Iterate over each dataframe and populate the distance matrix
    for idx, df in enumerate(dfs):
        sample_name = sample_names[idx]
        for _, row in df.iterrows():
            other_sample = row['Name']
            distance = row['Normalized distance']
            distance_matrix[sample_name][other_sample] = distance
            distance_matrix[other_sample][sample_name] = distance  # for symmetry

    # Convert the dictionary to a DataFrame
    distance_df = pd.DataFrame(distance_matrix)
    distance_df.to_csv(main_folder_path + '/distances/analysis/summary_matrix.csv')

    thresh = config.threshold_graph
    produce_full_graph(main_folder_path, thresh)


def main():

    main_folder_path = hptlc.HPTLC_extracter.main_folder_path

    for elu in hptlc.HPTLC_extracter.standard_eluants:
        for obs in hptlc.HPTLC_extracter.standard_observations:
            update_fpca(main_folder_path, elu, obs)

    compute_global_distances(main_folder_path)
    produce_full_graph(main_folder_path, config.threshold_graph)


if __name__=="__main__":
    main()
