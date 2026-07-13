# HPTLC Extractor

This small python package has been made to enable the conversion from HTPLC image to json files, with the aim of creating standardize databases and studying relationships within.

## Installation

The tool was developped in Python 3.8. It requires python to be install on your machine.


In order to use HPTLC_extractor, simply download and extract the ZIP file localy. Then, from the terminal, you can install the required python packages by moving to the location of the HTPLC_extractor folder and running the following command:

```sh
pip install -r requirements.txt
```

## How to use it

You are ready to use with a simple command. On your terminal you can execute:

```sh
streamlit run app.py
```

This starts with an empty database — nothing is bundled or shared between clones.
Everything you extract is written locally to `HPTLC_data/` (auto-created on first
use, and ignored by git, so it never gets mixed up with the project's source code).

## Trying it out

`example_data/HPDS_254nm.png` is a real plate photo included in the repo so you can
see the pipeline work end to end without needing your own photo yet:

1. Run the app and open **Spectractor**.
2. Set eluant to `HPDS` and observation to `254nm` (the default plate geometry and
   product names already match this photo, no need to change anything else).
3. Upload `example_data/HPDS_254nm.png` and click **Extract spectra**.
4. Check the result on the **Visualiser** and **Distances** pages.

From there, replace the plate geometry / product names on the Spectractor page with
your own and start building your own local database.
