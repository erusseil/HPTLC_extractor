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
    extra = 50
    baseline_lam = 1e4
    peak_prominence = 3

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
    def convert_image_to_array(path, length, X_offset, Y_offset, front, inter_spot_dist, names, save=False):

        HPTLC_extracter.check_bckg_exists(names)

        bckg_arg = np.where(np.array(names) == '')[0][0]
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

            if n != bckg_arg:
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
            if self.names[idx] != '':
                save_path = f"{self.main_folder_path}/raw/{self.names[idx]}.json"
    
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
            if self.names[idx] != '':
                norm_sample = self.normalize(sample, self.resolution, self.baseline_lam, self.peak_prominence)
                save_path = f"{self.main_folder_path}/standard/{self.names[idx]}.json"
    
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
    def normalize(sample, resolution, baseline_lam, peak_prominence):

        from scipy.signal import find_peaks
        from pybaselines import Baseline

        sign = HPTLC_extracter.peak_or_holes(sample)
        all_peaks = []
        norm_sample = []
        
        for i in range(3):
            sub = HPTLC_extracter.subsample(sample[:, i], resolution)
            norm_baseline = np.ptp(sub)

            baseline_fitter = Baseline()
            bkg, _ = baseline_fitter.derpsalsa(sign * sub, lam=baseline_lam/norm_baseline)
            new = sign * sub - bkg
            norm_sample.append(new)
        
            arg_peaks = find_peaks(new, prominence=peak_prominence)
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
    def subsample(sample, nbins):

        # Calculate the bin indices for each element
        bin_edges = np.linspace(0, len(sample), nbins + 1, endpoint=True)
        bin_indices = np.floor(np.linspace(0, nbins, len(sample))).astype(int)
        
        # Aggregate values by bin using `np.bincount`
        binned_array = np.bincount(bin_indices, weights=sample) / np.bincount(bin_indices)
        
        return binned_array

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

    
    
    
    
    
    
    
    
