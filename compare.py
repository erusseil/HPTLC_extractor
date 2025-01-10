import json
import numpy as np
from os import listdir
from os.path import isfile, join
import pandas as pd
import os
import hptlc
import config
import warnings

def mesure_distances(main_folder_path, name):

    # Open sample of interest
    with open(f"{main_folder_path}/standard/{name}", 'r') as openfile:
        main_object = json.load(openfile)

    all_col_names = [f'{elu}_{obs}' for elu in main_object for obs in main_object[elu]]
    others = [f for f in listdir(main_folder_path+"/standard/") if isfile(join(main_folder_path+"/standard/", f))]
    others.remove(name)

    all_distances = []
    for other in others:
        with open(f"{main_folder_path}/standard/{other}", 'r') as openfile:
            other_object = json.load(openfile)


        distances = []
        for elu in main_object:
            for obs in main_object[elu]:
                main_data = main_object[elu][obs]
                other_data = other_object[elu][obs]
                
                if (other_data['R'] != []) & (main_data['R'] != []):
    
                    other_to_compare = np.array([other_data['R'],
                                                    other_data['G'],
                                                    other_data['B']])
                    main_to_compare = np.array([main_data['R'],
                                                    main_data['G'],
                                                    main_data['B']])
                    
                    distances.append(compute_single_distance_dtw(np.array(main_to_compare), np.array(other_to_compare)))

                else:
                    distances.append(np.nan)

        all_distances.append(distances)

    new_others = [k[:-5] for k in others if k[-5:]=='.json']

    if not os.path.isdir(main_folder_path + "/distances"):
        os.makedirs(main_folder_path + "/distances")

    to_dump = pd.DataFrame(data={"Name":new_others})

    for idx, col_name in enumerate(all_col_names):
        to_dump[col_name] = np.array(all_distances)[:, idx]

    df = to_dump.iloc[:, 1:]

    # Create a mean normalized so that each column weighs the same
    warnings.filterwarnings(action='ignore', message='Mean of empty slice')
    col_normed = df / np.nanmean(df, axis=0)
    norm_mean = np.nanmean(col_normed, axis=1)
    
    to_dump['Normalized distance'] = np.round(norm_mean, 4)
    to_dump['Mean distance'] = np.round(np.nanmean(df, axis=1), 4)
    to_dump = to_dump.sort_values("Normalized distance")
    to_dump = to_dump[['Name', "Normalized distance", "Mean distance"] + all_col_names]
    save_name = main_folder_path + '/distances/' + name[:-5] if name[-5:]=='.json' else name
    to_dump.to_csv(save_name + ".csv", index=False)
    

def compute_single_distance(data1, data2):
    diff = abs(data1 - data2)
    distance = np.sum(diff)/np.shape(data1)[1]
    return np.round(distance, 4)

def compute_single_distance_dtw(data1, data2):
    import dtw

    datas = (data1, data2)
    ds = []
    for order in [[0, 1], [1, 0]]:
        for i in range(3):
            # Find the dtw map mapping because data 1 and 2. Then use it to compute the squared difference of the two remapped profiles.
            # Because the mapping of data 1 to data 2 is not exactly the same as data 2 to data 1, we do it twice and average.
        
            dtw_map = dtw.dtw(datas[order[0]][i], datas[order[1]][i], keep_internals=True, 
                step_pattern=dtw.rabinerJuangStepPattern(6, "c"))
            ds.append(np.mean(np.square(datas[order[0]][i][dtw_map.index1] - datas[order[1]][i][dtw_map.index2])))

    return np.round(np.mean(ds), 6)


def compute_summary_matrix(main_folder_path):

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
    distance_df.to_csv(main_folder_path + '/distances/summary_matrix.csv')


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

def compute_all_distances(main_folder_path):

    path = main_folder_path + '/standard/'
    all_files = [f for f in listdir(path) if isfile(join(path, f))]
    for name in all_files:
            mesure_distances(main_folder_path, name)

    compute_summary_matrix(main_folder_path)
    
def main():
    
    main_folder_path = hptlc.HPTLC_extracter.main_folder_path

    for name in config.compute_distances:
        mesure_distances(main_folder_path, name)
        show_results(main_folder_path, name, n=config.show_n_best)

        