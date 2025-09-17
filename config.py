#Setup of the machine
length = 200.0 #Length of the plate
front = 70.0 #Distance from the spot to the front
X_offset = 17.5 #Distance from the left of the plate, to the center of the first spot
Y_offset = 8.0 #Distance from the bottom of the plate, to the center of the spots
inter_spot_dist = 11 #Distance between two spot centers

# Names of the products. They should be in the same order as deposited on the plate. One of them MUST be an empty string.
# It indicates the place of the empty track that will be used to remove the background.

names = ['c0',
 'c1',
 'c2',
 'c3',
 'c4',
 'c5',
 'c6',
 'c7',
 '',
 'c9',
 'c10',
 'c11',
 'c12',
 'c13',
 'c14',
 'c15']

# Path to the experiment folder (must leave the r before the string if using Windows path)
# Must contain images of the form: eluant_observation.png (for example MPDS_254nm.png)
path = "/home/etru7215/Documents/other/HPTLC/images/"


# Curve visualization, i.e. using show_curve().
# Indicate eluant and observation that you want to look at
#NB: A list of files can be input for multiple visualization at once
eluant = 'MPDS'
observation = '254nm'
show = ["/home/etru7215/Documents/other/HPTLC/HPTLC_extractor/HPTLC_data/raw/c7.json",
        "/home/etru7215/Documents/other/HPTLC/HPTLC_extractor/HPTLC_data/standard/c7.json"]

compute_distances = ["c0", "c7"]
show_n_best = 5


threshold_graph = 0.05
