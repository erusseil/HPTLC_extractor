import os
import numpy as np
import imageio.v3 as iio
import json


class HPTLC_extracter():

    main_folder_path = 'HPTLC_data/'
    stardard_eluants = ['LPDS', 'MPDS', 'HPDS']
    standard_observations = ['254nm', '366nm', 'visible', 'developer']
    half_window = 25
    resolution = 500
    extra = 0.03 #Extra length to add top and bottom in percent of the migration length

    def __init__(self, path, names, length, front, X_offset, Y_offset, inter_spot_dist, eluant, observation):

        if not eluant in self.stardard_eluants:
            raise ValueError('Only LPDS, MPDS, or HPDS, are accepted as standard eluants.')

        if not observation in self.standard_observations:
            raise ValueError('Only 254nm, 366nm, visible, or developer, are accepted as standard observation.')

        self.check_bckg_exists(names)

        self.names = names
        self.path = os.path.normpath(path)
        self.length = length
        self.front = front
        self.X_offset = X_offset
        self.Y_offset = Y_offset
        self.inter_spot_dist = inter_spot_dist
        self.eluant = eluant
        self.observation = observation
        
    def create_product_folder(self):

        if not os.path.isdir(self.main_folder_path):
            os.makedirs(self.main_folder_path)

        if not os.path.isdir(f"{self.main_folder_path}/raw/"):
            os.makedirs(f"{self.main_folder_path}/raw/")

        if not os.path.isdir(f"{self.main_folder_path}/standard/"):
            os.makedirs(f"{self.main_folder_path}/standard/")

        # Create an empty dict for new objects that have not been studied yet.
        # The standardize dict do not contain the original background used to normalize them.
        dico = {}
        dico_std = {}

        for elu in self.stardard_eluants:
            sub_dico = {}
            sub_dico_std = {}
            for obs in self.standard_observations:
                sub_sub_dico = {}
                sub_sub_dico_std = {}
                for channel in ['R', 'G', 'B']:
                    sub_sub_dico[channel] = []
                    sub_sub_dico_std[channel] = []

                sub_sub_dico['background'] = {}
                for channel in ['R', 'G', 'B']:
                    sub_sub_dico['background'][channel] = []  

                sub_dico[obs] = sub_sub_dico
                sub_dico_std[obs] = sub_sub_dico_std
            dico[elu] = sub_dico
            dico_std[elu] = sub_dico_std
                
        # Convert Python to JSON  
        json_object = json.dumps(dico, indent = 2)
        json_object_std = json.dumps(dico_std, indent = 2)

        for name in self.names:
            if not name == '':            
                path_name = f"{self.main_folder_path}/raw/{name}.json"
                if not os.path.isfile(path_name):
                    with open(path_name, "w") as outfile:
                        outfile.write(json_object)

                path_name_std = f"{self.main_folder_path}/standard/{name}.json"
                if not os.path.isfile(path_name_std):
                    with open(path_name_std, "w") as outfile:
                        outfile.write(json_object_std)

    @staticmethod
    def convert_image_to_array(path, length, X_offset, Y_offset, front, inter_spot_dist, names):

        HPTLC_extracter.check_bckg_exists(names)

        bckg_arg = np.where(np.array(names) == '')[0][0]
        image = iio.imread(os.path.normpath(path))
        pixel_size = length/np.shape(image)[1]
        half_window = HPTLC_extracter.half_window
        extra = int(HPTLC_extracter.extra * front/pixel_size)
        space = inter_spot_dist/pixel_size

        all_samples = []
        for n in range(len(names)):
            center = int(X_offset/pixel_size + n * inter_spot_dist/pixel_size)
            bottom = min(np.shape(image)[0], int(np.shape(image)[0] - Y_offset/pixel_size + extra))
            top = max(0, int(bottom - front/pixel_size - 2 * extra))
        
            rectangle = image[bottom:top:-1, center - half_window : center + half_window, :3]
            averaged = np.mean(rectangle, axis=1)

            if n != bckg_arg:
                all_samples.append(averaged)

            else:
                bckg = averaged

        return np.array(all_samples), bckg


    def extract_samples(self):

        self.create_product_folder()
        all_sample, bckg = self.convert_image_to_array(self.path, self.length,
                                                 self.X_offset, self.Y_offset,
                                                 self.front, self.inter_spot_dist,
                                                 self.names)

        # For the raw data
        idx = 0
        for k in range(len(self.names)):
            if self.names[k] != '':
                sample = all_sample[idx]
                save_path = f"{self.main_folder_path}/raw/{self.names[k]}.json"
                idx += 1
    
                # Read previous already existing data
                with open(save_path, 'r') as openfile:
                    json_object = json.load(openfile)
    
                # Add or replace with the new info
                for idx2, channel in enumerate(['R', 'G', 'B']):
                    json_object[self.eluant][self.observation][channel] = list(sample[:, idx2])
                    json_object[self.eluant][self.observation]['background'][channel] = list(bckg[:, idx2])
                
    
                # Save again
                json_dico = json.dumps(json_object, indent = 2) 
                with open(save_path, "w") as outfile:
                    outfile.write(json_dico)

        #Same for the normalized data
        idx = 0
        for k in range(len(self.names)):
            if self.names[k] != '':
                sample = all_sample[idx]
                norm_sample = self.normalize(sample, bckg, self.resolution)
                save_path = f"{self.main_folder_path}/standard/{self.names[k]}.json"
                idx += 1

                # Read previous already existing data
                with open(save_path, 'r') as openfile:
                    json_object = json.load(openfile)
    
                # Add or replace with the new info
                for idx2, channel in enumerate(['R', 'G', 'B']):
                    json_object[self.eluant][self.observation][channel] = list(norm_sample[:, idx2])
    
                # Save again
                json_dico = json.dumps(json_object, indent = 2) 
                with open(save_path, "w") as outfile:
                    outfile.write(json_dico)
   
    @staticmethod
    def normalize(sample, background, resolution):

        from scipy.signal import find_peaks

        norm_sample = []
        
        for i in range(3):
            sub = sample[:, i]
            bkg = background[:, i]
            new = HPTLC_extracter.subsample(sub - bkg, resolution)
            norm_sample.append(new)

        norm_sample = np.array(norm_sample).T / np.max(np.abs(norm_sample))

        return norm_sample

    @staticmethod
    def subsample(sample, nbins):

        # Calculate the bin indices for each element
        bin_edges = np.linspace(0, len(sample) + 1, nbins)
        bin_indices = np.floor(np.linspace(0, nbins - 1, len(sample))).astype(int)

        # Aggregate values by bin using `np.bincount`
        binned_array = np.bincount(bin_indices, weights=sample) / np.bincount(bin_indices)
        
        return binned_array

    @staticmethod
    def check_bckg_exists(names):
        if not "" in names:
            message = "\n\n!!!ERROR!!!\nThe name list must contain one empty string that corresponds to the empty track. This empty track is necessary to calibrate the background profile.\n!!!ERROR!!!\n"
            raise ValueError(message)

def main():

    import config
    
    hptlc = HPTLC_extracter(config.path, config.names,
                            config.length, config.front, config.X_offset,
                            config.Y_offset, config.inter_spot_dist,
                            config.eluant, config.observation)

    hptlc.extract_samples()

def show_curve():

    import config
    import matplotlib.pyplot as plt 
    
    for path in config.show:

        # Read previous already existing data
        with open(path, 'r') as openfile:
            json_object = json.load(openfile)
        
        colors = ['r', 'g', 'b']
        RGB = ['R', 'G', 'B']
        
        plt.figure()
        for i in range(3):
            curve = json_object[config.eluant][config.observation][RGB[i]]
            plt.plot(curve, color=colors[i])

        plt.title(path)
    
    plt.show()

    
    
    
    
    
    
    
    
