# Real-Time EEG Imagery Neurofeedback — Experimental Methodology

**Project**: Per-subject "neural cards" for visual mental imagery via real-time EEG feedback
**Status**: Pre-data-collection design specification
**Date**: 2026

This document is the source of truth for the experimental design, infrastructure, and analysis plan. It serves three audiences:

- The experimenter running sessions (operator instructions, recovery procedures)
- Reviewers and collaborators evaluating the methodology
- The eventual paper writeup (pre-registered design and analysis plan)

---

## 1. Background and motivation

### 1.1 The decoding problem

Decoding visual mental imagery from EEG is challenging because the imagery signal is weak, individually variable, and easily confounded by perceptual carryover (afterimages, working-memory traces of recently-shown stimuli). Prior work in this lab (v3 framework: contrastive imagery encoders aligned to CLIP image prototypes, evaluated on a public BIDS dataset of 22 subjects across three categories) demonstrated reliable above-chance decoding (e.g., `tri_sep_attn_clip_image` achieving Cohen's d=4.74 against chance), but absolute accuracies remained modest (mean proto-accuracy ≈ 0.48 for 3-class) and four subjects had to be excluded due to perceptual signal bleeding into the imagery window.

### 1.2 Why a neurofeedback paradigm

This study reframes the problem. Rather than treating imagery as a passive elicitation paradigm, we use real-time neurofeedback to help subjects _learn_ to produce more reproducible neural signatures for each imagery class. The deliverable is not raw classification accuracy but a per-subject "neural card" — a compact, interpretable representation of each imagery class — and evidence that subjects can reproduce it on demand. This design has several advantages:

- **No perceptual carryover**: imagery trials are cued by spoken-word audio with no immediately preceding visual stimulus.
- **Self-report-validated trials**: only high-quality (likert ≥ 4, not flagged-bad) trials contribute to card construction.
- **Subject-specific representation**: each subject's card is built from their own data, with no transferred weights.
- **Diffusion-ready**: cards are stored as serialized representations that can be used post-hoc as conditioning signals for downstream image generation.

### 1.3 Methodological commitments

The design is conservative by intent:

- Imagery signal is never co-mingled with perception in the same trial.
- The model that scores trials is frozen before any feedback is given, eliminating circularity.
- A held-out probe phase with the model frozen and feedback hidden provides the headline accuracy number.
- All raw data (EEG, markers, ratings, flags) is saved per subject for post-hoc analysis.

---

## 2. Hypotheses and pre-registered success metrics

### 2.1 Primary endpoints

**H1 — Probe accuracy above chance.** During the probe phase, with the card frozen and feedback hidden, the per-class similarity scores of trials should classify the cued class above chance (33.3% for 3 classes).
_Test_: per-subject binomial test of probe-trial argmax accuracy vs. 1/3; group-level one-sample t-test of accuracies vs. 1/3.

**H2 — Within-session improvement under feedback.** Feedback-block similarity scores for the cued class should be higher in the second half of the feedback phase than in the first half.
_Test_: per-subject paired t-test of mean cued-class similarity, second-half vs. first-half blocks; group-level meta-analysis.

**H3 — Probe–feedback correlation.** Subjects who show greater improvement under feedback (H2 effect) should achieve higher probe accuracy (H1 effect).
_Test_: across-subject Pearson correlation between H2 effect size and H1 accuracy.

### 2.2 Secondary analyses

- **Perception–imagery alignment**: imagery card centroids should land closer to the same-class perception centroid than to other-class perception centroids (Riemannian distance; embedding distance if encoder added post-hoc).
- **Cluster compactness over time**: average within-class trial-to-centroid distance should decrease over the acquisition phase (learning curve).
- **Feature-level contribution**: probe accuracy decomposed by Riemannian-only, RQA-only, and combined scoring.
- **Cross-session card alignment** (if subject returns): Riemannian distance between session-1 and session-2 centroids of the same class, vs. cross-class baseline.

### 2.3 Exclusion rules

A subject is excluded from H1–H3 if any of the following:

- Fewer than the threshold high-quality trials per class (default: 30) reached during acquisition within the time budget.
- More than 30% of trials marked "bad" by the operator due to artifacts.
- ICA calibration produced unusable results (e.g., all components flagged as artifact).

A trial is excluded from card construction if:

- Its block was rated likert < `block_likert_min` (default: 4).
- It was per-trial-flagged as "bad."
- Its post-ICA epoch fails artifact rejection (peak-to-peak > 150 µV after preprocessing).

---

## 3. Subjects

To be filled in for IRB and per-paper:

- Target N (planned 10).
- Inclusion: normal or corrected-to-normal vision, right-handed, no history of seizure or neurological condition.
- Exclusion: regular psychotropic medication, prior participation in lab studies in past 30 days.
- Screening: short imagery vividness questionnaire (e.g., VVIQ-2) administered before EEG fitting; any subject scoring in the lowest decile is flagged but not excluded.

---

## 4. Apparatus

### 4.1 EEG hardware

- Custom headset (16 channels, primarily over occipital and parieto-occipital cortex) using OpenBCI Cyton+Daisy amplifiers.
- Sample rate: TBD (depends on amp config; assume 250 Hz unless specified).
- Reference / bias: TBD (consult headset builder).
- Stream protocol: Lab Streaming Layer (LSL).

### 4.2 Software stack

- **EEG ingest**: LSL inlet (headset-agnostic). Any LSL EEG outlet with 16 channels is supported; channel labels read from XML metadata.
- **Backend**: Python 3.10+, FastAPI + WebSocket, MNE-Python, pyriemann, scipy.
- **Frontend**: vanilla JS, served as static files. No VR / 3D / WebXR.
- **External services**: optional LabRecorder for redundant XDF capture.

### 4.3 Latency budget

- Per-epoch processing: bandpass + notch + CAR + ICA application + feature extraction + scoring → target < 200 ms.
- Browser feedback display update: trial end → bars updated, target < 350 ms total.

---

## 5. Stimuli

### 5.1 Classes

Three categories, chosen for distinctness in CLIP space and ease of mental imagery:

| Class  | Code | Reason                                            |
| ------ | ---- | ------------------------------------------------- |
| cat    | 100  | Animate, biological motion, common imagery target |
| wrench | 101  | Tool, engages motor/somatosensory simulation      |
| house  | 102  | Scene, engages parahippocampal place areas        |

### 5.2 Exemplars

5 exemplar images per class (15 total). Selected to be:

- Clearly category-typical (no ambiguity).
- Visually varied within class (different poses, angles, instances) to avoid pixel-level memorization.
- Matched in luminance, on-screen size, and contrast across classes to avoid V1-driven decoding.
- Center-anchored on a neutral gray background.

Stored at `assets/images/{class}/{1..5}.png`.

### 5.3 Audio cues

Spoken-word TTS audio (single English word) per class, ~600–800 ms duration, normalized loudness:

- `cat.wav`, `wrench.wav`, `house.wav` in `assets/audio/`.
- Generation: any TTS provider (ElevenLabs, OS native, etc.); store deterministic versions per study.

Why spoken words rather than tones: with 3 classes, three discriminable tones are uncomfortably close under fatigue, and spoken words cue semantic representation directly — exactly the representation we want subjects to elicit.

---

## 6. Procedure

A session has six sequential phases. The full session is approximately 75–90 minutes including breaks.

### 6.1 Phase 0 — Setup (~10 minutes)

Operator-driven, not recorded:

- Headset fitting, impedance check.
- Subject reads instructions, asks questions.
- Brief practice (3 trials/class) with no recording, to familiarize with timing and audio cues.

### 6.2 Phase 1 — ICA calibration (~3 minutes)

Subject sits relaxed while continuous EEG is recorded across four sub-blocks:

1. Eyes open, fixation cross (60 s).
2. Eyes closed (60 s).
3. Deliberate blinks every ~2 s (30 s).
4. Mild jaw clenches every ~5 s + horizontal eye movements (30 s).

LSL markers: `PHASE_ICA_CAL_START` (80) at start, `ICA_CAL_EYES_OPEN` / `ICA_CAL_EYES_CLOSED` / `ICA_CAL_BLINK` / `ICA_CAL_JAW` per sub-block, `PHASE_ICA_CAL_END` (81) at end.

Post-collection (~10–30 s wait):

- Fit Picard ICA on the calibration data after bandpass + notch filtering.
- Auto-label components with `mne-icalabel` (ICLabel model).
- Reject components labeled as "muscle artifact", "eye blink", "heart beat", "line noise", or "channel noise" with confidence ≥ 0.7.
- Save unmixing matrix and bad-component mask to `data/{subj}/{sess}/ica/`.
- All subsequent epochs apply this saved ICA forward (single matrix multiply, near-zero latency).

If the auto-rejection produces obviously wrong results (e.g., all components rejected, or no components rejected when blinks were clearly present), the operator can manually mark components and re-save.

### 6.3 Phase 2 — Perception block (~10 minutes)

Dedicated perception-only data collection. No imagery.

Block structure:

- 10 blocks × 9 trials = 90 trials total (30/class).
- Each trial: fixation (1 s) → image displayed (4 s) → rest (2 s). Total ~7 s/trial, ~63 s/block.
- 9 trials/block, 3 from each class, randomized order, sampled without replacement.
- The exemplar shown rotates within a class — trial 1 of "cat" in block 1 uses cat/1.png, trial 1 of "cat" in block 2 uses cat/2.png, etc., cycling through 5 exemplars.
- Brief operator-paced break between blocks (10–15 s).

Markers: `PHASE_PERCEPTION_START` (82), `BLOCK_START` (30), `TRIAL_START` (1), `FIXATION_ONSET` (10), `PERCEPTION_ONSET` (12) + class code + exemplar code, `PERCEPTION_OFFSET` (13), `REST_ONSET` (16), `TRIAL_END` (2), `BLOCK_END` (31), `PHASE_PERCEPTION_END` (83).

This data is saved as `eeg_perception.fif` and is used for:

- Secondary perception–imagery alignment analysis.
- Optional anchoring of the embedding space if a within-session encoder is added later.
- Archival / re-analysis with future models.

### 6.4 Phase 3 — Acquisition (~15–20 minutes)

The card-building phase. **No feedback shown to the subject.**

Block structure:

- Variable number of blocks until threshold is met.
- Each block opens with an **anchor**: one rotating exemplar per class is displayed for 2 s, with the corresponding audio cue playing alongside, separated by 0.5 s blanks. ~7.5 s anchor total. The exemplar index advances per block; over 5 blocks all 5 exemplars are seen.
- 9 trials/block, 3/class, randomized without replacement.

Trial structure (acquisition / feedback / probe — same throughout):

1. **Fixation** (1 s) — small cross on neutral background.
2. **Audio cue** (~0.7 s) — spoken-word class name. Subject closes eyes (or looks at black screen) at cue onset.
3. **Imagery** (4 s) — black screen, subject imagines the cued class.
4. **Rest** (2 s) — neutral background, eyes open.

End-of-block sequence:

- **Block likert**: subject rates the block 1–5 ("How well did imagery go in this block overall?").
- **Per-trial flagging**: 9 trial boxes shown; subject taps up to 2 as "best" (green) and up to 2 as "bad" (red). Default is neutral.
- Brief rest (~10 s).

Card construction (online, between blocks):

- For each trial, an epoch is extracted from `IMAGERY_ONSET` to `IMAGERY_ONSET + 4 s`, processed (bandpass + notch + CAR + ICA application).
- Eligible trials (block likert ≥ 4, not flagged-bad, peak-to-peak < 150 µV post-ICA) contribute to that class's card.
- Best-flagged trials contribute with weight 2.0; others with weight 1.0.
- The Riemannian centroid is the (weighted) geodesic mean of trial covariance matrices.
- The RQA signature is the (weighted) mean of trial RQA features; the RQA covariance for Mahalanobis distance is fitted per-class.

**Threshold for moving to the next phase**: `threshold_high_quality_per_class` (default 30) trials per class accumulated. The operator can override (move on early or extend) based on observed quality and time budget.

Markers: `PHASE_ACQUISITION_START` (84), `ANCHOR_START` (32), `ANCHOR_IMAGE_ONSET` (33) + class code + exemplar code, `ANCHOR_END` (34), per-trial markers as above, `BLOCK_LIKERT` (50 + value), `TRIAL_FLAG_BEST` (70) + trial idx, `TRIAL_FLAG_BAD` (71) + trial idx, `PHASE_ACQUISITION_END` (85).

### 6.5 Phase 4 — Card freeze

Explicit checkpoint. The operator advances the session past acquisition.

Actions:

- Compute final Riemannian centroid, RQA signature + covariance, scoring scale (σ for Riemannian, k for RQA).
- Compute per-trial training distances; calibrate score normalization so that median training distance maps to similarity 0.5.
- Serialize each class's card to `data/{subj}/{sess}/card_{class}.npz`.
- Mark cards as `frozen=True`. From this point, no card update can happen.
- LSL marker `CARD_FROZEN` (92).

Estimated wait: 5–10 seconds. Subject takes a brief break (~1 minute) while operator visually confirms cards look reasonable (convergence score > 0, n_trials ≥ threshold).

### 6.6 Phase 5 — Feedback (~12 minutes)

Subject performs imagery as before, but now after each trial sees three continuous bars showing per-class similarity:

```
cat:    [████████░░] 0.82
wrench: [███░░░░░░░] 0.31
house:  [██░░░░░░░░] 0.18
```

The bar for the cued class is highlighted; the others provide context (so the subject sees their imagery is class-discriminative, not just "generally strong"). An optional "high / medium / low" overlay can be added based on absolute thresholds (default: high > 0.7, medium 0.4–0.7, low < 0.4).

Block structure:

- 6 blocks (default) × 9 trials = 54 trials total.
- Anchor at block start, identical to acquisition.
- Block likert and per-trial flagging at block end (recorded but not used to update the card — the card is frozen).

The card is **not updated** during feedback — scoring uses the frozen card from Phase 4.

Markers: `PHASE_FEEDBACK_START` (86), trial structure as above, `PHASE_FEEDBACK_END` (87).

### 6.7 Phase 6 — Probe (~10 minutes)

Identical trial structure to feedback, but the feedback bars are **hidden**. This is the held-out evaluation phase.

- 6 blocks × 9 trials = 54 trials.
- No bars shown. Card is frozen. Block likert and flagging still collected for record-keeping but do not affect anything.

The cued-class similarity score is recorded silently per trial; argmax accuracy across the probe phase is the headline H1 number.

Markers: `PHASE_PROBE_START` (88), trial structure as above, `PHASE_PROBE_END` (89).

### 6.8 Phase 7 — Save and complete

- Final session summary computed: probe accuracy, feedback improvement (H2), per-class card statistics, exclusion flags.
- All artifacts written to `data/{subj}/{sess}/`.
- LSL marker `EXP_END` (91).

---

## 7. Data acquisition and output schema

Each session produces a folder `data/{subject_id}/{session_id}/` containing:

```
config.json                  # full SessionConfig dump (immutable record)
ica/
  ica-ica.fif                # full MNE ICA solution
  ica_unmixing.npy           # unmixing matrix used for real-time application
  ica_bad_components.npy     # boolean mask of rejected components
  ica_components.json        # labels + confidence + bad mask (human-readable)
markers.csv                  # all LSL markers w/ timestamps + payload JSON
trial_log.json               # per-trial detailed record
likerts.csv                  # block-level ratings (redundant with trial_log)
flags.csv                    # per-trial flags (redundant with trial_log)
eeg_perception.fif           # raw EEG of perception phase, post-ICA
eeg_acquisition.fif          # raw EEG of acquisition phase, post-ICA
eeg_feedback.fif             # raw EEG of feedback phase, post-ICA
eeg_probe.fif                # raw EEG of probe phase, post-ICA
eeg_calibration.fif          # raw EEG of ICA calibration phase
card_cat.npz                 # serialized frozen card
card_wrench.npz
card_house.npz
encoder/                     # reserved for V2 (within-session or transferred encoder)
session_summary.json         # H1/H2/H3 statistics
```

Per-trial record in `trial_log.json`:

```json
{
  "trial_id": 42,
  "phase": "acquisition",
  "block": 5,
  "block_position": 3,
  "class": "cat",
  "exemplar_idx": 2,
  "fixation_onset_lsl": 12345.678,
  "audio_cue_onset_lsl": 12346.678,
  "imagery_onset_lsl": 12347.378,
  "imagery_offset_lsl": 12351.378,
  "rest_onset_lsl": 12351.378,
  "block_likert": 4,
  "flag_best": false,
  "flag_bad": false,
  "artifact_rejected": false,
  "scores": {
    "cat": { "riemannian": 0.78, "rqa": 0.65, "combined": 0.74 },
    "wrench": { "riemannian": 0.31, "rqa": 0.42, "combined": 0.34 },
    "house": { "riemannian": 0.22, "rqa": 0.3, "combined": 0.24 }
  },
  "argmax_class": "cat",
  "card_frozen_at_trial": false
}
```

XDF redundancy: if the operator runs LabRecorder in parallel and subscribes to the EEG outlet + marker outlet, an XDF file is produced independently. This is optional; our save is complete without it.

---

## 8. The neural card

A card is a per-class object representing the subject's neural signature for that imagery class. It is built from acquisition-phase trials passing eligibility, and is frozen before feedback.

### 8.1 Components

```python
NeuralCard {
  class_name: str
  n_trials: int                      # eligible trials contributing
  riemannian_centroid: ndarray       # SPD matrix (n_ch, n_ch), geodesic mean
  riemannian_sigma: float            # scoring scale: median training distance
  rqa_centroid: ndarray              # (5,) mean of training RQA vectors
  rqa_cov: ndarray                   # (5, 5) for Mahalanobis distance
  rqa_scale: float                   # k for exp(-d^2/k) similarity transform
  embedding_centroid: Optional[ndarray]   # reserved for V2
  per_trial_distances: list          # for diagnostics / convergence curve
  per_trial_metadata: list           # block, trial idx, likert, flags
  convergence_score: float           # 1 - normalized within-class spread
  frozen: bool
  frozen_at: timestamp
  config_snapshot: dict              # parameters used at card construction
}
```

### 8.2 Scoring a new trial

Given a new epoch and the cards for cat / wrench / house:

1. Extract covariance matrix `C_trial` from the cleaned epoch.
2. For each class `c`:
   - `d_riem = riemannian_distance(C_trial, card_c.riemannian_centroid)`
   - `s_riem = exp(-d_riem / card_c.riemannian_sigma)` ∈ (0, 1]
3. Extract RQA vector `r_trial` from PC1 of the cleaned epoch.
4. For each class `c`:
   - `d_rqa = mahalanobis(r_trial, card_c.rqa_centroid, card_c.rqa_cov)`
   - `s_rqa = exp(-d_rqa^2 / card_c.rqa_scale)`
5. Combined: `s_combined = w_riem * s_riem + w_rqa * s_rqa + w_emb * s_emb`
   - V1 defaults: `w_riem = 0.7, w_rqa = 0.3, w_emb = 0.0`.
6. Return `{cat: 0.74, wrench: 0.34, house: 0.24}` for display and logging.

### 8.3 Building / updating the card during acquisition

Online incremental updates after each eligible trial:

- Riemannian centroid: maintain a running list of trial covariance matrices; on update, recompute geodesic mean (cheap for n < ~50).
- RQA centroid: weighted running mean.
- RQA covariance: maintain running Welford accumulator.
- Convergence score: `1 - mean_distance_to_centroid / std_distances` (clipped to [0, 1]).

On freeze:

- All centroids fixed.
- σ and k computed from training-trial distances:
  - `σ = median({d_riem_train})` so that median training trial maps to similarity ≈ 1/e.
  - `k = median({d_rqa_train^2}) / ln(2)` so that median training trial maps to similarity 0.5.
- Cards serialized to disk.

---

## 9. Real-time pipeline

```
LSL EEG outlet → ring buffer (30 s)
                    │
                    ▼
            ┌─────────────────┐
   marker → │  epoch extract  │
            └────────┬────────┘
                     │ epoch (n_ch, n_samples)
                     ▼
            ┌─────────────────┐
            │  bandpass IIR   │  causal, single-pass
            │  notch IIR      │
            │  CAR            │
            │  ICA forward    │  apply saved unmixing × kill bad × inverse
            │  artifact check │
            └────────┬────────┘
                     │ cleaned epoch
                     ▼
            ┌─────────────────┐
            │  cov + RQA      │
            └────────┬────────┘
                     │ features
                     ▼
            ┌─────────────────┐
            │  card scoring   │  per class
            └────────┬────────┘
                     │ scores
                     ▼
              browser display
```

All steps are real-time-safe (no lookahead, no batch operations across trials).

---

## 10. Operator instructions

### Pre-session checklist

- [ ] EEG amp powered, paired, streaming to LSL (verify in LabRecorder or `pylsl` discovery).
- [ ] Stream visible with correct channel count (16) and labels.
- [ ] Web app running (`python server.py`); open in browser.
- [ ] Subject seated, headset gelled, impedances < 20 kΩ (verbose check in OpenBCI GUI).
- [ ] Audio output verified (subject hears cues at comfortable volume).
- [ ] Quiet room, dim lighting, monitor at standard distance.

### Session walkthrough

1. Configure session in browser: subject ID, classes (cat/wrench/house default), threshold (30 default).
2. Click "Start ICA Calibration" → guide subject through eyes-open / closed / blinks / jaw-clench.
3. After ICA fits, review component labels — if obviously wrong (no blinks rejected, all rejected), use manual override.
4. Start perception block — minimal supervision.
5. Start acquisition. Watch progress bar (eligible trials per class). Encourage subject during breaks.
6. When threshold met, freeze cards. Brief subject on what feedback bars mean.
7. Run feedback phase. No coaching during trials.
8. Run probe phase. Hide bars confirmed.
9. Save and back up `data/{subj}/{sess}/`.

### Common failures

- **LSL stream not found**: restart amp + GUI, re-verify stream name.
- **All ICA components rejected**: likely impedance issue; refit headset, redo calibration.
- **Subject fatigue mid-acquisition**: pause, extend breaks, optionally reduce threshold by operator override.
- **Browser disconnects**: WebSocket auto-reconnects; trial state persists server-side.

---

## 11. Known limitations and caveats

- **Self-report bias**: trials are filtered by subject's own quality ratings, which may correlate with extraneous factors (engagement, fatigue) more than with neural-imagery quality per se. Mitigated by per-trial flagging in addition to block likert, but not eliminated.
- **2-class baseline missing**: the original v3 work used 3-way decoding; results here are not directly comparable to typical 2-class motor imagery BCI literature.
- **No cross-subject generalization in V1**: cards are per-subject. A "library" across subjects requires offline alignment work post-hoc.
- **No within-session encoder**: V1 cards are interpretable features only. A learned embedding can be added post-hoc but does not contribute to real-time feedback.
- **Imagery reference-image carryover**: the perception block at session start may bias acquisition imagery in the same session. Block-level anchors during acquisition are brief but not zero. Cross-session replication is the test for whether this carryover matters.

---

## 12. Open parameters TBD before first subject

- EEG sample rate (depends on amp config).
- Reference / bias electrode placement (custom headset).
- LSL stream name pattern.
- Notch frequency (60 Hz US default, 50 Hz EU).
- Final exemplar selection (5 images per class, sourcing pending).

---

## 13. Glossary

- **Card**: per-class neural signature object; includes Riemannian centroid + RQA signature.
- **Acquisition**: card-building phase, no feedback to subject.
- **Feedback**: card-frozen phase, similarity bars shown to subject.
- **Probe**: card-frozen phase, similarity scoring silent (no bars).
- **Anchor**: brief intra-session reminder of class images + audio cues.
- **CAR**: common-average reference (re-reference each sample to the mean across channels).
- **ICA**: Independent Component Analysis; here used for blind source separation to remove ocular and muscle artifacts.
- **RQA**: Recurrence Quantification Analysis; nonlinear-dynamics features computed from a phase-space-embedded signal.
- **Riemannian centroid**: geodesic mean of SPD covariance matrices on the affine-invariant manifold.
