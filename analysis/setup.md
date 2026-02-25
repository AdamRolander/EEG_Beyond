Download dataset: https://www.nature.com/articles/s41597-025-06512-5?fromPaywallRec=false#data-availability

conda env create -f environment.yml
conda activate eeg-tricontrastive

cd ~/beyond_contrastive/dataset
for f in sub-\*.zip; do unzip -n "$f"; done

conda install -c conda-forge optuna
