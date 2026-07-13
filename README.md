# HPTLC Extractor

HPTLC (High-Performance Thin-Layer Chromatography) lets you separate the different
compounds in a sample by letting them migrate up a plate, but comparing plates by
eye — across different photos, lighting, and runs — is subjective and doesn't
scale. This tool turns a simple photo of a developed plate into a quantitative,
comparable measurement: for each spot on the plate, it reads the colour intensity
along the migration track, corrects it for background and baseline drift, and
turns it into a normalized curve (one per RGB channel). Every sample you extract
this way is added to a local database, and the tool can then compute how similar
any two samples are and draw a similarity graph across your whole collection —
turning "these two spots look alike" into an actual, repeatable number.

## 1. Install Python

You need Python 3.9 or newer. To check whether you already have it, open a
terminal (Command Prompt / PowerShell on Windows, Terminal on macOS/Linux) and run:

```sh
python3 --version
```

If that fails, download and install Python from [python.org](https://www.python.org/downloads/)
(on Windows, tick **"Add Python to PATH"** during install), then try again — on
Windows the command is usually `python` instead of `python3`.

## 2. Get the code

Either download this repository as a ZIP from GitHub (green **Code** button →
**Download ZIP**, then extract it), or, if you have `git` installed, clone it:

```sh
git clone https://github.com/erusseil/HPTLC_extractor.git
```

Then move into the folder in your terminal:

```sh
cd HPTLC_extractor
```

## 3. Create a virtual environment and install dependencies

A virtual environment keeps this project's packages separate from anything else
on your computer, so it's worth the one extra step:

```sh
python3 -m venv hptlc_env
```

Activate it — the command differs by OS:

```sh
# macOS / Linux
source hptlc_env/bin/activate

# Windows (PowerShell)
hptlc_env\Scripts\Activate.ps1
```

You'll know it worked because your terminal prompt now starts with `(hptlc_env)`.
Do this activation step every time you come back to work on this project in a
new terminal. Then install the required packages:

```sh
pip install -r requirements.txt
```

## 4. Run the app

```sh
streamlit run app.py
```

A browser tab should open automatically at `http://localhost:8501`. If it
doesn't, copy that address into your browser manually. Leave the terminal
window open while you use the app — closing it stops the app.

Each install of this project keeps its **own, independent database** on your
computer — nothing is bundled or shared between clones, and nothing is sent
anywhere over the internet.

## 5. Try it with the example plate

`example_data/HPDS_254nm.png` is a real plate photo included in the repo so you
can see the whole pipeline work before using your own data:

1. In the app, open **Spectractor** in the sidebar.
2. Under "Which condition is this upload for?", set eluant to `HPDS` and
   observation to `254nm` (the default plate geometry and product names shown
   on the page already match this exact photo — no need to change anything).
3. Upload `example_data/HPDS_254nm.png` and click **Extract spectra**.
4. Open **Visualiser** to see the extracted curves, and **Distances** to
   recompute similarity and see the graph.

## 6. Building your own database

Once you're ready to use your own plate photos:

1. On the **Spectractor** page, fill in your plate's actual geometry (length,
   front, spot offsets, spacing — all in mm) and the list of product names in
   plate order, with exactly one entry named `bckg` for the empty background
   track. Click **💾 Save these as default** so you don't have to retype them
   for every photo.
2. Pick the eluant and observation the photo corresponds to, upload it, check
   that the preview boxes line up with the actual spots, and extract.
3. Repeat for every plate/eluant/observation combination you have. The
   **Dashboard** page shows which combinations already have data for which
   samples.
4. On the **Distances** page, click **🔁 Recompute all distances** whenever
   you've added new data, to refresh the similarity graph and pairwise
   comparisons.

All of this is written locally to a `HPTLC_data/` folder that's created
automatically the first time you run the app (and is never tracked by git, so
your data and the project's source code stay separate). To back up or move
your database, simply copy that folder.
