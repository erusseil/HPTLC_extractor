#Setup of the machine
length = 80.0 #Length of the plate
front = 70.0 #Distance from the spot to the front
X_offset = 22.0 #Distance from the left of the plate, to the center of the first spot
Y_offset = 8.0 #Distance from the bottom of the plate, to the center of the spots
inter_spot_dist = 12.0 #Distance between two spot centers

# Names of the products. They should be in the same order as deposited on the plate.
names = ['sample_0',
 'sample_1',
 'sample_2',
 'sample_3',
 'sample_4',
 'sample_5',
 'sample_6',
 'sample_7',
 'sample_8',
 'sample_9',
 'sample_10',
 'sample_11',
 'sample_12',
 'sample_13']

# Path to the image
path = 'images/Data test p-anisaldehyde Visible.png'

# Scientific variables
# NB: This is only required for the production of the standardize database, i.e. using main()
eluant = 'LPDS'
observation = 'visible'

# Curve visualization, i.e. using show_curve()
#NB: A list of files can be input for multiple visualization at once
show = ['single_hptlc/sample_1.csv',
       'single_hptlc/sample_4.csv',
       'single_hptlc/sample_10.csv']


