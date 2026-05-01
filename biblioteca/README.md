# biblioteca — Visual Imagery Neurofeedback

Real-time EEG visual imagery decoding with per-subject neural cards.
This branch is the data-collection rebuild; the offline analysis code
(v3 contrastive training, FBCSP baselines, etc.) lives elsewhere.

The full methodology is documented in [`experiment.md`](./experiment.md).

## Setup

```bash
pip install -r requirements.txt
python scripts/generate_audio_cues.py     # one-time: writes assets/audio/*.mp3
# add 5 image exemplars per class to assets/images/{cat,wrench,house}/{1..5}.png
```

## Run

**Real EEG (LSL outlet must already be streaming):**

```bash
python server.py
# open http://127.0.0.1:8000
```

**Simulated EEG (no hardware needed, for development):**

```bash
EEG_SIMULATE=1 python server.py
```

## Smoke tests

Both run fully offline; no LSL or hardware required.

```bash
python -m src.config_session              # validates config/default.yaml
python scripts/test_simulated_ingest.py   # end-to-end inlet → epoch → cov → RQA
python scripts/test_card_lifecycle.py     # build → freeze → score → save → load
```

## Data layout

Each session writes to `data/<subject_id>/<session_id>/`:

```
data/S001/20260430T140530/
├── config.json              # snapshot of session config (reproducibility)
├── ica/
│   ├── ica-ica.fif         # full MNE ICA solution
│   ├── ica_unmixing.npy    # unmixing matrix (used by realtime path)
│   ├── ica_bad_components.npy
│   └── ica_components.json # per-component label + confidence
├── card_cat.npz             # frozen neural card per class
├── card_wrench.npz
├── card_house.npz
├── trial_log.json           # per-trial metadata + scores
├── likerts.csv              # block likert + flagged trials
├── markers.csv              # full LSL marker stream
└── session_summary.json     # H1 probe accuracy + per-class progress
```

## Phase progression

1. **ICA_CAL** — 4 substeps (eyes open / closed / blink / jaw), then Fit ICA
2. **PERCEPTION** — ~10 blocks of 9 trials (3/class), no audio cues
3. **ACQUISITION** — anchor + 9-trial blocks until ≥ 30 high-quality trials/class
4. **AWAITING_FREEZE** — explicit `freeze_cards` checkpoint (irreversible)
5. **FEEDBACK** — frozen card; subject sees similarity bars during rest
6. **PROBE** — frozen card, no feedback; this is the H1 measurement

## Pre-registered hypotheses

- **H1**: Probe argmax accuracy > 1/3 chance (binomial per-subject; group t-test).
- **H2**: Feedback similarity 2nd half > 1st half (paired test).
- **H3**: H2 effect correlates with H1 accuracy across subjects (Pearson).

## Architecture

```
            browser (frontend/)
              ↓ websocket
       FastAPI server.py
              ↓
  src/session.py  ← phase machine + WS protocol
       ↓                 ↓                ↓
 marker_outlet    eeg_ingest      preprocessing
       ↓                 ↓                ↓
   LSL outlet     LSL inlet       features → neural_card
```

Browser drives all trial timing; the server emits LSL markers via
`pylsl.local_clock()` (the same clock the EEG inlet uses for sample
timestamps), so epoch alignment to markers is exact.

## Open dependencies

Before running on a real subject:

- Confirm sample rate of the custom 16-ch headset (`config/default.yaml`)
- Confirm reference / bias electrode placement
- Confirm LSL stream name + whether channel labels are populated in XML

## Marker code reference

See `src/markers.py`. The frontend mirrors these in `frontend/config.js` —
when you change one, change both.
