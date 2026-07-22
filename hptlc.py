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
    baseline_correction_enabled = False #Both baseline fitters tried so far (fabc's own
                                         #auto-classification and the onset/offset-anchored
                                         #version) could fabricate values that were never in
                                         #the photo (e.g. driving points negative in valleys
                                         #between peaks), which is a worse problem than the
                                         #residual drift they were removing. Disabled for now
                                         #in favor of background subtraction alone; revisit
                                         #if drift turns out to matter once real cross-plate
                                         #photos come in — e.g. with a full empty-plate photo
                                         #as a per-column background reference instead of one
                                         #bckg track. Both fit_baseline* methods are left
                                         #intact below so this is a one-line flip back on.
    constant_shift_correction_enabled = True #A single scalar subtracted from each channel
                                         #(the median of its confirmed-background regions),
                                         #not a fitted curve — can't invent shape the way the
                                         #two baseline fitters above did, so it's a much lower
                                         #risk way to remove a track that's just sitting at the
                                         #wrong overall level.
    onset_noise_fraction = 0.03 #Leading fraction of the curve used to estimate the noise
                                 #floor when detecting where the first real signal begins.
                                 #Kept small (matching the `extra` margin) so a genuine early
                                 #peak doesn't get folded into the noise estimate itself.
    onset_threshold_sigma = 4 #How many standard deviations above the noise floor a point
                               #must reach to count as the start of a real signal.
    onset_min_consecutive = 3 #Number of consecutive points that must clear the threshold,
                               #so a single noise spike doesn't get mistaken for signal onset.
    offset_noise_fraction = 0.2 #Wider than onset_noise_fraction: the trailing "no signal"
                               #region can be much longer than a few percent of the curve
                               #(often most of it), and a short reference window sampled
                               #right at the very end can look artificially quiet by chance
                               #relative to that whole span — one ordinary-sized wiggle
                               #elsewhere then reads as "signal" and stops the confirmed
                               #region far earlier than it should. A wider reference gives a
                               #more representative noise estimate for that long span. Not
                               #used for onset, where a wide window risks folding a genuine
                               #early peak into the noise estimate itself.

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

            if HPTLC_extracter.baseline_correction_enabled:
                baseline_fit = HPTLC_extracter.fit_baseline(background_corrected, lam)
                background_corrected = background_corrected - baseline_fit

            if HPTLC_extracter.constant_shift_correction_enabled:
                background_corrected = HPTLC_extracter.constant_shift_correction(background_corrected)

            norm_sample.append(background_corrected)

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
    def detect_signal_onset(sample, noise_fraction=None):
        """Index where a real signal first rises out of the noise.

        The leading fraction of the curve is guaranteed to be compound-free
        (the migration front hasn't reached it yet), so its variability is
        a good estimate of pure noise. Onset is the first run of several
        consecutive points that clears a threshold above that noise floor.
        Returns 0 if no clear onset is found (nothing to force flat).

        noise_fraction overrides onset_noise_fraction — used by
        detect_signal_offset, which needs a wider reference window (see
        offset_noise_fraction).
        """
        if noise_fraction is None:
            noise_fraction = HPTLC_extracter.onset_noise_fraction

        n = len(sample)
        noise_len = max(5, int(n * noise_fraction))
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
    def detect_signal_offset(sample):
        """Index after which the signal has permanently returned to the
        noise floor — the mirror of detect_signal_onset, scanning from the
        migration front backward instead of from the origin forward, with a
        wider noise reference (offset_noise_fraction) since that trailing
        span tends to be much longer than onset's leading margin. Returns
        len(sample) if no such point is found (nothing to force flat, same
        convention as detect_signal_onset returning 0)."""
        n = len(sample)
        reversed_onset = HPTLC_extracter.detect_signal_onset(
            sample[::-1], noise_fraction=HPTLC_extracter.offset_noise_fraction
        )
        if reversed_onset == 0:
            return n
        return n - reversed_onset

    @staticmethod
    def fit_baseline_legacy_fabc_auto(sample, baseline_lam):
        """The original baseline fit: fabc decides point-by-point which
        values count as baseline using its own automatic (continuous
        wavelet transform based) classification. Kept only so the newer
        fit_baseline below can be reverted to this in one line if needed —
        not called anywhere by default."""

        from pybaselines import Baseline

        baseline_fitter = Baseline()
        baseline, _ = baseline_fitter.fabc(sample, lam=baseline_lam)

        onset = HPTLC_extracter.detect_signal_onset(sample)
        if onset > 0:
            baseline[:onset] = np.median(sample[:onset])

        median = np.median(sample - baseline)
        return baseline - median

    @staticmethod
    def fit_baseline(sample, baseline_lam):
        """fabc's own automatic point classification is a hard, per-point
        decision (via a continuous wavelet transform threshold) — ordinary
        pixel noise can flip a borderline point between "baseline" and
        "signal" for two otherwise near-identical curves, making the fitted
        baseline (and so the corrected curve) less reproducible than it
        should be. Instead of trusting that classification, anchor it
        ourselves: the leading and trailing regions outside
        [onset, offset) are guaranteed compound-free by the same noise-floor
        logic already used for onset detection, so treat only those as
        baseline and have fabc smooth through just them (weights_as_mask
        skips its own classification entirely), leaving the possibly-peak
        region in between to be interpolated across rather than classified.
        """

        from pybaselines import Baseline

        onset = HPTLC_extracter.detect_signal_onset(sample)
        offset = HPTLC_extracter.detect_signal_offset(sample)

        mask = np.ones(len(sample))
        mask[onset:offset] = 0

        baseline_fitter = Baseline()
        baseline, _ = baseline_fitter.fabc(sample, lam=baseline_lam, weights=mask, weights_as_mask=True)

        # Same reasoning as before: force the confirmed-flat regions to
        # their own median rather than trust the smoother's value right at
        # the boundary, which can still be pulled toward the excluded
        # region by the smoothing regularization.
        if onset > 0:
            baseline[:onset] = np.median(sample[:onset])
        if offset < len(sample):
            baseline[offset:] = np.median(sample[offset:])

        #Shift for median to be at zero
        median = np.median(sample - baseline)
        return baseline - median

    @staticmethod
    def constant_shift_correction(sample):
        """Re-center a curve to zero using only its confirmed-background
        regions (before onset, after offset) — a single scalar shift, never
        a fitted curve, so unlike the two baseline fitters above it can't
        invent shape that wasn't in the photo. Meant for the case where a
        whole track just sits at a slightly different overall level than
        another (e.g. a long, low-amplitude offset spanning most of the
        curve) without assuming anything about how that level drifts within
        the curve itself.

        The confirmed-background region after offset is then flattened to
        exactly zero. There's no real signal there by construction (that's
        what "confirmed background" means), so any remaining wiggle is pure
        pixel noise — left alone, a derivative computed downstream would
        pick up fake spikes from that noise instead of just the real peaks
        in between. The leading region before onset is only re-centered,
        not flattened the same way: forcing it flat right up against where
        a genuine peak begins created a visible, artificial-looking cliff
        at the transition. The region between onset and offset (possibly
        real signal) is never touched either way.
        """
        onset = HPTLC_extracter.detect_signal_onset(sample)
        offset = HPTLC_extracter.detect_signal_offset(sample)

        background_points = np.concatenate([sample[:onset], sample[offset:]])
        if len(background_points) == 0:
            return sample

        shifted = sample - np.median(background_points)
        shifted[offset:] = 0.0
        return shifted

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


def _derivative_curve(curve):
    """(R, G, B) -> their derivatives, normalized by their own shared max
    abs (all three channels together) — the same scheme compare.py uses to
    build the derivative-based FPCA features (each sample normalized by its
    own max, not one constant for the whole database), so what's shown here
    matches what actually feeds the distance calculation."""
    r, g, b = (np.asarray(curve[0]), np.asarray(curve[1]), np.asarray(curve[2]))
    grid_points = np.linspace(0, 1, len(r))
    dt = grid_points[1] - grid_points[0]
    dr, dg, db = np.gradient(r, dt), np.gradient(g, dt), np.gradient(b, dt)

    max_abs = np.max(np.abs(np.concatenate([dr, dg, db])))
    if max_abs == 0:
        return dr, dg, db
    return dr / max_abs, dg / max_abs, db / max_abs


def _warp_band(band, stretch, shift):
    """Apply the same per-sample migration-axis stretch+shift used for the
    curve (see compare.compute_affine_params) to a band image's columns, so
    it stays visually lined up with the (also warped) curve above it instead
    of showing the raw, unaligned crop next to an aligned curve. Edges held
    flat, same as the curve warp — never stretched/shifted content invented
    beyond what the crop actually shows."""
    resolution = band.shape[1]
    grid_points = np.linspace(0, 1, resolution)
    warped_points = stretch * grid_points + shift

    warped = np.empty(band.shape, dtype=np.float64)
    for row in range(band.shape[0]):
        for channel in range(band.shape[2]):
            warped[row, :, channel] = np.interp(warped_points, grid_points, band[row, :, channel])

    return np.clip(np.round(warped), 0, 255).astype(np.uint8)


def _band_data_uri(band):
    """Encode a band array as a base64 PNG data URI, for embedding via
    Plotly's layout.images — see the comment where it's used for why that's
    preferred over a go.Image trace here."""
    import base64
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(band).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def show_curve(name1, elu, obs, name2=None, baseline_removed=True, aligned_curves=None, channels="RGB",
               show_bands=False, show_derivative=False):
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
    photographed strip the curve was averaged from. If aligned_curves is
    also given, the band is warped by that same sample's stretch/shift so
    it stays lined up with the aligned curve above it.

    show_derivative plots the rate of change of whatever's being shown
    (post-alignment if alignment is on) instead of its value.

    Returns a Plotly figure (not matplotlib) so the caller gets interactive
    zoom/pan for free via st.plotly_chart.
    """

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    labels = ["R", "G", "B"] if channels == "RGB" else [channels]

    def get_curve(name):
        if aligned_curves and name in aligned_curves:
            c = aligned_curves[name]
            return c['R'], c['G'], c['B']
        return HPTLC_extracter.get_display_curve(name, elu, obs, baseline_removed)

    curve1 = get_curve(name1)
    curve2 = get_curve(name2) if name2 else None

    if show_derivative:
        curve1 = _derivative_curve(curve1)
        if curve2 is not None:
            curve2 = _derivative_curve(curve2)

    bands = []
    if show_bands:
        for name in (name1, name2):
            if name:
                band = HPTLC_extracter.get_spot_band(name, elu, obs)
                if band is not None:
                    if aligned_curves and name in aligned_curves:
                        info = aligned_curves[name]
                        band = _warp_band(band, info["stretch"], info["delta"])
                    bands.append((name, band))

    n_band_rows = len(bands)
    if n_band_rows:
        row_heights = [4] + [1] * n_band_rows
        total = sum(row_heights)
        row_heights = [h / total for h in row_heights]
        fig = make_subplots(rows=1 + n_band_rows, cols=1, shared_xaxes=True,
                             row_heights=row_heights, vertical_spacing=0.15 / (1 + n_band_rows),
                             subplot_titles=[""] + [name for name, _ in bands])
    else:
        fig = make_subplots(rows=1, cols=1)

    # Scale from what the full RGB view would show for the sample(s)
    # actually on screen, with the same margin matplotlib's autoscale used
    # to add — so a single flat channel still reads as flat relative to this
    # sample's (or this comparison's) own real dynamic range, rather than
    # autoscaling to whatever tiny noise happens to be on screen, and a
    # comparison against a second sample gets its own range too.
    reference_values = [_channel_value(curve1, label) for label in ["R", "G", "B"]]
    if curve2 is not None:
        reference_values += [_channel_value(curve2, label) for label in ["R", "G", "B"]]
    all_ref = np.concatenate(reference_values)
    if all_ref.size == 0:
        yrange = [-1.05, 1.05]  # nothing to show (no data for this combo); a stable default
    else:
        data_min, data_max = float(np.min(all_ref)), float(np.max(all_ref))
        margin = 0.05 * (data_max - data_min) if data_max > data_min else 0.05
        yrange = [data_min - margin, data_max + margin]

    for label in labels:
        fig.add_trace(go.Scatter(y=_channel_value(curve1, label), mode="lines",
                                  line=dict(color=_CHANNEL_COLORS[label]),
                                  name=f"{name1} ({label})"), row=1, col=1)

    if curve2 is not None:
        for label in labels:
            fig.add_trace(go.Scatter(y=_channel_value(curve2, label), mode="lines",
                                      line=dict(color=_CHANNEL_PASTELS[label], dash="dash"),
                                      name=f"{name2} ({label})"), row=1, col=1)

    # Each band is resized to `resolution` columns (hptlc.HPTLC_extracter.
    # resolution), the same point count as the curve above, so a column here
    # lines up with the same x position on the curve — and shared_xaxes
    # keeps them in sync when zooming/panning the curve.
    #
    # Embedded via layout.images (sizing="stretch"), not a go.Image trace:
    # go.Image hardcodes its y-axis to scale-anchor to its x-axis so the
    # image's true pixel aspect ratio is always preserved, which then
    # shrinks the whole figure's width to fit that ratio inside the row's
    # short height. layout.images has no such constraint, so the band
    # freely fills its row instead of dictating the plot's overall width.
    for row_idx, (name, band) in enumerate(bands, start=2):
        fig.update_xaxes(range=[0, band.shape[1]], row=row_idx, col=1)
        fig.update_yaxes(range=[0, 1], visible=False, row=row_idx, col=1)
        fig.add_layout_image(
            source=_band_data_uri(band), xref=f"x{row_idx}", yref=f"y{row_idx}",
            x=0, y=1, sizex=band.shape[1], sizey=1,
            xanchor="left", yanchor="top", sizing="stretch", layer="above",
        )

    fig.update_yaxes(range=yrange, title_text=("d(intensity)/dt, normalized" if show_derivative else "intensity"),
                      row=1, col=1)
    fig.update_layout(
        height=520 + 140 * n_band_rows,
        margin=dict(l=10, r=10, t=30 if n_band_rows else 10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig
