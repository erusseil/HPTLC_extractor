#Setup of the machine
length = 200.0 #Length of the plate
front = 70.0 #Distance from the spot to the front
X_offset = 20.9 #Distance from the left of the plate, to the center of the first spot
Y_offset = 8.0 #Distance from the bottom of the plate, to the center of the spots
inter_spot_dist = 11.3 #Distance between two spot centers

# Names of the products. They should be in the same order as deposited on the plate. One of them MUST be an empty string.
# It indicates the place of the empty track that will be used to remove the background.

names = ['sample_0',
 'sample_1',
 'sample_2',
 'sample_3',
 'sample_4',
 'sample_5',
 'sample_6',
 '',
 'sample_8',
 'sample_9',
 'sample_10',
 'sample_11',
 'sample_12',
 'sample_13',
 'sample_14']

# Path to the experiment folder (must leave the r before the string if using Windows path)
# Must contain images of the form: eluant_observation.png (for example MDPS_254nm.png)
path = r"C:\Users\Haris\Desktop\HPTLC_extractor\Images"


# Curve visualization, i.e. using show_curve().
# Indicate eluant and observation that you want to look at
#NB: A list of files can be input for multiple visualization at once
eluant = 'LPDS'
observation = '366nm'
show = [r"C:\Users\Haris\Desktop\HPTLC_extractor\HPTLC_data\standard\sample_1.json"]

compute_distances = ["sample_2", "sample_3"]
show_n_best = 5
