The notebook is split into version 2a and 2b

Some parts of 2a are required + useful, where others are not. My suggestion is:

Every cell up to and not including this one:

### ============================================================

### OPTUNA SUBJECT SELECTION + HARDCODED EXCLUSION

### Rank by FBCSP/LDA, pick 25th/50th/75th percentile, REMOVE from eval

### ============================================================

Then run everything in 2b and below

---

Running these as is should actually just replicate my results because I used random seed, so you dont have to run anything if you dont want to, but these are the useful architectural cells to motivate future improvements.
