import os
import numpy as np
import imageio.v3 as iio
import json


class HPTLC_extracter():

    main_folder_path = 'HPTLC_data/'
    stardard_eluants = ['LPDS', 'MPDS', 'HPDS']
    standard_observations = ['254nm', '366nm', 'visible', 'developer']
    half_window = 25
    extra = 50

    def __init__(self, path, names, length, front, X_offset, Y_offset, inter_spot_dist, eluant, observation):

        if not eluant in HPTLC_extracter.stardard_eluants:
            raise ValueError('Only LPDS, MPDS, or HPDS, are accepted as standard eluants.')

        if not observation in HPTLC_extracter.standard_observations:
            raise ValueError('Only 254nm, 366nm, visible, or developer, are accepted as standard observation.')

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

        if not os.path.isdir(HPTLC_extracter.main_folder_path):
            os.makedirs(HPTLC_extracter.main_folder_path)

        if not os.path.isdir(f"{HPTLC_extracter.main_folder_path}/raw/"):
            os.makedirs(f"{HPTLC_extracter.main_folder_path}/raw/")

        if not os.path.isdir(f"{HPTLC_extracter.main_folder_path}/standard/"):
            os.makedirs(f"{HPTLC_extracter.main_folder_path}/standard/")

        # Create an empty dict for new objects that have not been studied yet.
        dico = {}
        for elu in HPTLC_extracter.stardard_eluants:
            sub_dico = {}
            for obs in HPTLC_extracter.standard_observations:
                sub_sub_dico = {}
                for channel in ['R', 'G', 'B']:
                    sub_sub_dico[channel] = []
                sub_dico[obs] = sub_sub_dico
            dico[elu] = sub_dico
                
        # Convert Python to JSON  
        json_object = json.dumps(dico, indent = 2) 

        for name in self.names:
            for folder in ['raw', 'standard']:
                path_name = f"{HPTLC_extracter.main_folder_path}/{folder}/{name}.json"
                if not os.path.isfile(path_name):
                    with open(path_name, "w") as outfile:
                        outfile.write(json_object)

    @staticmethod
    def convert_image_to_array(path, length, X_offset, Y_offset, front, inter_spot_dist, names, save=False):
        
        image = iio.imread(os.path.normpath(path))
        pixel_size = length/np.shape(image)[1]
        half_window = HPTLC_extracter.half_window
        extra = HPTLC_extracter.extra
        space = inter_spot_dist/pixel_size

        all_samples = []
        for n in range(len(names)):
            center = int(X_offset/pixel_size + n * inter_spot_dist/pixel_size)
            bottom = int(np.shape(image)[0] - Y_offset/pixel_size + extra)
            top = int(bottom - front/pixel_size - extra)
        
            rectangle = image[bottom:top:-1, center - half_window : center + half_window, :3]
            averaged = np.mean(rectangle, axis=1)
            all_samples.append(averaged)

            if save:
                if not os.path.isdir('single_hptlc'):
                    os.makedirs('single_hptlc')
                np.savetxt(f"single_hptlc/{names[n]}.csv", averaged, delimiter=",")

        if save==False:
            return np.array(all_samples)


    def extract_samples(self):

        self.create_product_folder()
        all_sample = self.convert_image_to_array(self.path, self.length,
                                                 self.X_offset, self.Y_offset,
                                                 self.front, self.inter_spot_dist,
                                                 self.names)

        # For the raw data
        for idx, sample in enumerate(all_sample):
            save_path = f"{HPTLC_extracter.main_folder_path}/raw/{self.names[idx]}.json"

            # Read previous already existing data
            with open(save_path, 'r') as openfile:
                json_object = json.load(openfile)

            # Add or replace with the new info
            for idx2, channel in enumerate(['R', 'G', 'B']):
                json_object[self.eluant][self.observation][channel] = list(sample[:, idx2])

            # Save again
            json_dico = json.dumps(json_object, indent = 2) 
            with open(save_path, "w") as outfile:
                outfile.write(json_dico)

        #Same for the normalized data
        for idx, sample in enumerate(all_sample):

            norm_sample = self.normalize(sample)
            save_path = f"{HPTLC_extracter.main_folder_path}/standard/{self.names[idx]}.json"

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
    def normalize(sample):

        from scipy.signal import find_peaks
        from pybaselines import Baseline

        sign = HPTLC_extracter.peak_or_holes(sample)
        all_peaks = []
        norm_sample = []
        
        for i in range(3):
            baseline_fitter = Baseline()
            bkg, _ = baseline_fitter.asls(sign * sample[:, i], lam=1e7)
            new = sign * sample[:, i] - bkg
            norm_sample.append(new)
        
            arg_peaks = find_peaks(new, prominence=3)
            all_peaks.append(new[arg_peaks[0]])
        
        flatten_peaks = [item for row in all_peaks for item in row]
        
        # We normalize for the absolute maximum peak to be equal to 1.
        if len(flatten_peaks)>0:
            norm_factor = max(flatten_peaks)
        
        # If no peak is detected, we don't normalize in order to not overfit the noise.
        else:
            norm_factor = 1

        norm_sample = sign * np.array(norm_sample).T/norm_factor
        return norm_sample

    @staticmethod
    def peak_or_holes(sample):
        shifted = sample - np.median(sample, axis=0)
        summed = np.sum(shifted)
    
        # If most of the signal is above the median, it is peaks
        if summed>0:
            return 1
    
        # Else most of the data is below, it is holes
        else:
            return -1


def main():

    import config
    
    hptlc = HPTLC_extracter(config.path, config.names,
                            config.length, config.front, config.X_offset,
                            config.Y_offset, config.inter_spot_dist,
                            config.eluant, config.observation)

    hptlc.extract_samples()

def single():

    import config

    HPTLC_extracter.convert_image_to_array(config.path, config.length, 
                                           config.X_offset, config.Y_offset, 
                                           config.front, config.inter_spot_dist, 
                                           config.names, True)

def show_curve():

    import config
    import matplotlib.pyplot as plt 
    
    for path in config.show:

        # Read previous already existing data
        with open(path, 'r') as openfile:
            json_object = json.load(openfile)
        
        colors = ['r', 'g', 'b']
        RGB = ['R', 'G', 'B']

        for i in range(3):
            curve = json_object[config.eluant][config.observation][RGB[i]]
            plt.plot(curve, color=colors[i])

        plt.title(path)
        plt.show()

    
    
    
    
    
    
    
    
