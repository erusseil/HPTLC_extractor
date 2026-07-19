import os
import numpy as np
import imageio.v3 as iio
import json
from os import listdir
from os.path import isfile, join

class HPTLC_extracter():
    
    main_folder_path = 'HPTLC_data/'
    standard_eluants = ['LPDS', 'MPDS', 'HPDS']
    standard_observations = ['254nm', '366nm', 'visible', 'developer']
    half_window = 25
    resolution = 500
    extra = 0.03 #Extra length to add top and bottom in percent of the migration length
    lam = 1e7 #Value used in the baseline fit
    onset_noise_fraction = 0.03 #Leading fraction of the curve used to estimate the noise
                                 #floor when detecting where the first real signal begins.
                                 #Kept small (matching the `extra` margin) so a genuine early
                                 #peak doesn't get folded into the noise estimate itself.
    onset_threshold_sigma = 4 #How many standard deviations above the noise floor a point
                               #must reach to count as the start of a real signal.
    onset_min_consecutive = 3 #Number of consecutive points that must clear the threshold,
                               #so a single noise spike doesn't get mistaken for signal onset.

    def __init__(self, names, length, front, X_offset, Y_offset, inter_spot_dist):

        self.check_bckg_exists(names)

        self.names = names
        self.length = length
        self.front = front
        self.X_offset = X_offset
        self.Y_offset = Y_offset
        self.inter_spot_dist = inter_spot_dist

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

        for elu in self.standard_eluants:
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
            if not name == 'bckg':
                path_name = f"{self.main_folder_path}/raw/{name}.json"
                if not os.path.isfile(path_name):
                    with open(path_name, "w") as outfile:
                        outfile.write(json_object)

                path_name_std = f"{self.main_folder_path}/standard/{name}.json"
                if not os.path.isfile(path_name_std):
                    with open(path_name_std, "w") as outfile:
                        outfile.write(json_object_std)

    @staticmethod
    def compute_spot_windows(image_shape, length, X_offset, Y_offset, front, inter_spot_dist, names):
        """Pixel rectangle (top, bottom, left, right) sampled for each name on
        the plate, given the plate geometry. Shared by the actual extraction
        and by the spot-preview overlay shown before extracting."""

        HPTLC_extracter.check_bckg_exists(names)

        pixel_size = length / image_shape[1]
        half_window = HPTLC_extracter.half_window
        extra = int(HPTLC_extracter.extra * front / pixel_size)

        windows = []
        for n, name in enumerate(names):
            center = int(X_offset/pixel_size + n * inter_spot_dist/pixel_size)
            bottom = min(image_shape[0], int(image_shape[0] - Y_offset/pixel_size + extra))
            top = max(0, int(bottom - front/pixel_size - 2 * extra))

            if (top > image_shape[0]) | (bottom < 0):
                message = "The inputed height dimensions must be wrong"
                raise ValueError(message)

            if ((center + half_window) > image_shape[1]) | (center < 0):
                message = "The inputed width dimensions must be wrong"
                raise ValueError(message)

            windows.append({
                "name": name,
                "top": top,
                "bottom": bottom,
                "left": center - half_window,
                "right": center + half_window,
            })

        return windows

    @staticmethod
    def convert_image_to_array(path, length, X_offset, Y_offset, front, inter_spot_dist, names):

        image = iio.imread(os.path.normpath(path))
        windows = HPTLC_extracter.compute_spot_windows(
            np.shape(image), length, X_offset, Y_offset, front, inter_spot_dist, names
        )
        bckg_arg = np.where(np.array(names) == 'bckg')[0][0]

        all_samples = []
        all_rectangles = []
        for n, window in enumerate(windows):
            rectangle = image[window["bottom"]:window["top"]:-1, window["left"]:window["right"], :3]
            averaged = np.mean(rectangle, axis=1)

            if n != bckg_arg:
                all_samples.append(averaged)
                all_rectangles.append(rectangle)

            else:
                bckg = averaged

        return np.array(all_samples), bckg, all_rectangles


    @staticmethod
    def save_spot_band(name, rectangle, eluant, observation):
        """Save the raw pixel rectangle a sample's curve was averaged from,
        as a small true-color image — lets chemists see the actual
        photographed spot behind a curve, for sanity-checking the
        extraction itself rather than just trusting the numbers.

        Resized so its length matches `resolution` (the curve's own point
        count) and transposed so migration runs left-to-right, matching how
        the curve is plotted above it. Always the raw crop: unaffected by
        the baseline correction or migration-axis alignment applied to the
        numeric curve, since it's a record of what was actually photographed.
        """
        from PIL import Image

        band_dir = f"{HPTLC_extracter.main_folder_path}/images/bands/{name}"
        os.makedirs(band_dir, exist_ok=True)

        # rectangle is (migration, spot width, 3); swap so migration becomes
        # the horizontal (PIL "width") axis instead of the vertical one.
        transposed = np.transpose(rectangle, (1, 0, 2)).astype(np.uint8)
        band = Image.fromarray(transposed).resize(
            (HPTLC_extracter.resolution, transposed.shape[0]), Image.BILINEAR,
        )
        band.save(f"{band_dir}/{eluant}_{observation}.png")

    @staticmethod
    def get_spot_band(name, eluant, observation):
        """The saved band for this sample/combo as an RGB array, or None if
        it hasn't been extracted yet (e.g. it predates this feature)."""
        from PIL import Image

        path = f"{HPTLC_extracter.main_folder_path}/images/bands/{name}/{eluant}_{observation}.png"
        if not os.path.isfile(path):
            return None
        return np.array(Image.open(path))


    def extract_one_image(self, image_path, eluant, observation):

        self.create_product_folder()

        all_sample, bckg, all_rectangles = self.convert_image_to_array(image_path, self.length,
                                                 self.X_offset, self.Y_offset,
                                                 self.front, self.inter_spot_dist,
                                                 self.names)

        # For the raw data
        idx = 0
        for k in range(len(self.names)):
            if self.names[k] != 'bckg':
                sample = all_sample[idx]
                self.save_spot_band(self.names[k], all_rectangles[idx], eluant, observation)
                save_path = f"{self.main_folder_path}/raw/{self.names[k]}.json"
                idx += 1

                # Read previous already existing data
                with open(save_path, 'r') as openfile:
                    json_object = json.load(openfile)

                # Add or replace with the new info
                for idx2, channel in enumerate(['R', 'G', 'B']):
                    json_object[eluant][observation][channel] = list(sample[:, idx2])
                    json_object[eluant][observation]['background'][channel] = list(bckg[:, idx2])


                # Save again
                json_dico = json.dumps(json_object, indent = 2)
                with open(save_path, "w") as outfile:
                    outfile.write(json_dico)

        #Same for the normalized data
        idx = 0
        for k in range(len(self.names)):
            if self.names[k] != 'bckg':
                sample = all_sample[idx]
                norm_sample = self.normalize(sample, bckg, self.resolution, self.lam)
                save_path = f"{self.main_folder_path}/standard/{self.names[k]}.json"
                idx += 1

                # Read previous already existing data
                with open(save_path, 'r') as openfile:
                    json_object = json.load(openfile)

                # Add or replace with the new info
                for idx2, channel in enumerate(['R', 'G', 'B']):
                    json_object[eluant][observation][channel] = list(norm_sample[:, idx2])

                # Save again
                json_dico = json.dumps(json_object, indent = 2)
                with open(save_path, "w") as outfile:
                    outfile.write(json_dico)

    @staticmethod
    def normalize(sample, background, resolution, lam):

        norm_sample = []
        for i in range(3):
            sub = sample[:, i]
            bkg = background[:, i]
            background_corrected = HPTLC_extracter.subsample(sub - bkg, resolution)
            baseline_fit = HPTLC_extracter.fit_baseline(background_corrected, lam)
            norm_sample.append(background_corrected - baseline_fit)

        norm_sample = np.array(norm_sample).T / np.max(np.abs(norm_sample))

        return norm_sample

    @staticmethod
    def get_pre_baseline_curve(sample, background, resolution):
        """Background-subtracted + resampled curve, before baseline
        correction. Used to visualize what the baseline step removes,
        without touching the extraction/normalize pipeline itself."""

        corrected = []
        for i in range(3):
            sub = sample[:, i]
            bkg = background[:, i]
            corrected.append(HPTLC_extracter.subsample(sub - bkg, resolution))

        corrected = np.array(corrected).T
        return corrected / np.max(np.abs(corrected))

    @staticmethod
    def subsample(sample, nbins):

        if len(sample) < nbins:
            message = (f"Photo resolution too low to resample reliably: the extracted spot "
                       f"window has only {len(sample)} rows, but {nbins} are needed. "
                       f"Use a higher-resolution photo.")
            raise ValueError(message)

        # Calculate the bin indices for each element
        bin_edges = np.linspace(0, len(sample) + 1, nbins)
        bin_indices = np.floor(np.linspace(0, nbins - 1, len(sample))).astype(int)

        # Aggregate values by bin using `np.bincount`
        binned_array = np.bincount(bin_indices, weights=sample) / np.bincount(bin_indices)

        return binned_array

    @staticmethod
    def check_bckg_exists(names):
        if not "bckg" in names:
            message = "The name list must contain one bckg string that corresponds to the empty track. This empty track is necessary to calibrate the background profile."
            raise ValueError(message)

    @staticmethod
    def detect_signal_onset(sample):
        """Index where a real signal first rises out of the noise.

        The leading fraction of the curve is guaranteed to be compound-free
        (the migration front hasn't reached it yet), so its variability is
        a good estimate of pure noise. Onset is the first run of several
        consecutive points that clears a threshold above that noise floor.
        Returns 0 if no clear onset is found (nothing to force flat).
        """
        n = len(sample)
        noise_len = max(5, int(n * HPTLC_extracter.onset_noise_fraction))
        noise_region = sample[:noise_len]
        noise_mean = np.mean(noise_region)
        noise_std = np.std(noise_region)

        threshold = noise_mean + HPTLC_extracter.onset_threshold_sigma * noise_std
        above = sample > threshold

        run = HPTLC_extracter.onset_min_consecutive
        for i in range(len(above) - run + 1):
            if above[i:i + run].all():
                return i
        return 0

    @staticmethod
    def fit_baseline(sample, baseline_lam):

        from pybaselines import Baseline

        baseline_fitter = Baseline()
        baseline, _ = baseline_fitter.fabc(sample, lam=baseline_lam)

        # Nothing has migrated yet before the first real signal, so the
        # curve (and therefore the baseline) must be flat there — force
        # it flat instead of trusting the fit's behavior at that edge.
        # Use the signal's own median over that region as the flat value,
        # not the fit's value right at the boundary: fabc's spline eases
        # into a nearby steep rise smoothly rather than with a sharp
        # corner, so baseline[onset] can already be pulled well above the
        # true flat level by the peak starting right after it.
        onset = HPTLC_extracter.detect_signal_onset(sample)
        if onset > 0:
            baseline[:onset] = np.median(sample[:onset])

        #Shift for median to be at zero
        median = np.median(sample - baseline)
        return baseline - median

    @staticmethod
    def get_display_curve(name, elu, obs, baseline_removed=True):
        """RGB arrays for display: either the final baseline-corrected
        standard curve, or the background-subtracted-only curve computed
        on the fly from raw/ (pre-baseline) — used by the Visualiser's
        baseline-correction toggle."""

        main_folder_path = HPTLC_extracter.main_folder_path

        if baseline_removed:
            with open(f"{main_folder_path}/standard/{name}.json", 'r') as f:
                data = json.load(f)
            curve = data[elu][obs]
            return curve['R'], curve['G'], curve['B']

        with open(f"{main_folder_path}/raw/{name}.json", 'r') as f:
            data = json.load(f)
        raw = data[elu][obs]
        sample = np.array([raw['R'], raw['G'], raw['B']]).T
        background = np.array([raw['background']['R'], raw['background']['G'], raw['background']['B']]).T
        pre_baseline = HPTLC_extracter.get_pre_baseline_curve(sample, background, HPTLC_extracter.resolution)
        return pre_baseline[:, 0], pre_baseline[:, 1], pre_baseline[:, 2]


CHANNEL_CHOICES = ["RGB", "R", "G", "B", "Luminance"]

_CHANNEL_COLORS = {"R": '#c4110e', "G": '#24b00e', "B": '#352db5', "Luminance": '#1F2937'}
_CHANNEL_PASTELS = {"R": '#e86664', "G": '#94d48a', "B": '#a7a4db', "Luminance": '#9CA3AF'}


def _channel_value(curve, label):
    """curve is an (R, G, B) triple (lists or arrays); returns the array for
    one plotted line. Luminance is the unweighted average of the three —
    R, G and B are already comparable normalized intensities, not display
    gamma values, so a plain average is the right "how much signal overall"
    proxy rather than a perceptual luma formula."""
    r, g, b = (np.asarray(curve[0]), np.asarray(curve[1]), np.asarray(curve[2]))
    if label == "R":
        return r
    if label == "G":
        return g
    if label == "B":
        return b
    if label == "Luminance":
        return (r + g + b) / 3
    raise ValueError(f"Unknown channel: {label}")


def show_curve(name1, elu, obs, name2=None, baseline_removed=True, aligned_curves=None, channels="RGB",
               show_bands=False):
    """aligned_curves, if given, is the {name: {"R", "G", "B", ...}} dict
    from compare.get_alignment() — samples present in it are plotted with
    their migration-axis correction applied instead of the raw standard
    curve, so the alignment used for distances can be sanity-checked
    visually. Samples not in it (e.g. no data for this combo) fall back to
    the normal display curve.

    channels selects what to plot: "RGB" for all three channels, "R"/"G"/"B"
    for a single one, or "Luminance" for their unweighted average.

    show_bands adds a row below the curve for each shown sample with a saved
    extraction band (see HPTLC_extracter.save_spot_band) — the actual
    photographed strip the curve was averaged from, always shown as the raw
    crop regardless of baseline correction or alignment.
    """

    import matplotlib.pyplot as plt

    labels = ["R", "G", "B"] if channels == "RGB" else [channels]

    def get_curve(name):
        if aligned_curves and name in aligned_curves:
            c = aligned_curves[name]
            return c['R'], c['G'], c['B']
        return HPTLC_extracter.get_display_curve(name, elu, obs, baseline_removed)

    curve1 = get_curve(name1)
    curve2 = get_curve(name2) if name2 else None

    bands = []
    if show_bands:
        for name in (name1, name2):
            if name:
                band = HPTLC_extracter.get_spot_band(name, elu, obs)
                if band is not None:
                    bands.append((name, band))

    if bands:
        fig, all_axes = plt.subplots(
            1 + len(bands), 1, sharex=True,
            gridspec_kw={"height_ratios": [4] + [1] * len(bands)},
        )
        ax, band_axes = all_axes[0], all_axes[1:]
    else:
        fig, ax = plt.subplots()
        band_axes = []

    # Scale from what the full RGB view would show for the sample(s)
    # actually on screen — plot all three reference channels first, let
    # matplotlib autoscale to them, capture that range, then discard these
    # lines and draw the channel(s) actually requested. That way a single
    # flat channel still reads as flat relative to this sample's (or this
    # comparison's) own real dynamic range, rather than autoscaling to
    # whatever tiny noise happens to be on screen — and a comparison against
    # a second sample gets its own range, since both curves feed the autoscale.
    reference_lines = [ax.plot(_channel_value(curve1, label))[0] for label in ["R", "G", "B"]]
    if curve2 is not None:
        reference_lines += [ax.plot(_channel_value(curve2, label))[0] for label in ["R", "G", "B"]]
    ax.relim()
    ax.autoscale_view()
    ylim = ax.get_ylim()
    for line in reference_lines:
        line.remove()

    for label in labels:
        ax.plot(_channel_value(curve1, label), color=_CHANNEL_COLORS[label],
                 label=f"{name1} ({label})", alpha=0.8)

    if curve2 is not None:
        for label in labels:
            ax.plot(_channel_value(curve2, label), color=_CHANNEL_PASTELS[label],
                     label=f"{name2} ({label})", linestyle="dashed", alpha=1)

    ax.set_ylim(ylim)
    ax.legend()

    # Each band is resized to `resolution` columns (hptlc.HPTLC_extracter.
    # resolution), the same point count as the curve above, so a column here
    # lines up with the same x position on the curve.
    for band_ax, (name, band) in zip(band_axes, bands):
        band_ax.imshow(band, aspect="auto", extent=[0, band.shape[1], 0, 1])
        band_ax.set_yticks([])
        band_ax.set_ylabel(name, rotation=0, ha="right", va="center", fontsize=9)

    return fig
