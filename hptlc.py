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
            path_name = f"{HPTLC_extracter.main_folder_path}/{name}.json"
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

        
        for idx, sample in enumerate(all_sample):
            save_path = f"{HPTLC_extracter.main_folder_path}{self.names[idx]}.json"

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
        
        curve = np.loadtxt(os.path.normpath(path), delimiter=",")
        colors = ['r', 'g', 'b']

        for i in range(3):
            plt.plot(curve[:, i], color=colors[i])

        plt.title(path)
        plt.ylim(0, 255)
        plt.show()

    
    
    
    
    
    
    
    
