#!/usr/bin/env bash
# OPTIONAL. You do not need any of this for the MVP: the pack already has synthetic slides,
# the demo photo and 30 real J006 photos. Run this only if you want more real images.
#
# Run from the repo root:   bash fixtures/sources/fetch_sources.sh
# Everything lands in fixtures/sources/downloads/ (gitignored). Check each license in README.md.
set -euo pipefail
mkdir -p fixtures/sources/downloads
cd fixtures/sources/downloads

echo "1/3  Original full-resolution J006 photos (no license: local testing only, ~720 MB)"
if [ ! -d j006 ]; then
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/epigeneticstoocean/oyster_larvae_photo_analysis j006
  (cd j006 && git sparse-checkout set J006_B1)
fi

echo "2/3  PLOS ONE 2018 figures (CC0): healthy, diseased and dead Pacific oyster larvae"
mkdir -p plos-vibrio-cc0
for g in g001 g002; do
  url="https://journals.plos.org/plosone/article/figure/image?download&size=large&id=10.1371/journal.pone.0199475.$g"
  curl -fL -o "plos-vibrio-cc0/pone.0199475.$g.png" "$url" \
    || echo "   Could not download $g. Open https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0199475 and use Download under the figure."
done

echo "3/3  ZooCAMNet (CC BY 4.0): plankton crops incl. Bivalvia and veliger classes (~3 GB)"
echo "     Needs a free Hugging Face account. First click 'Agree' on"
echo "     https://huggingface.co/datasets/project-oceania/zoocamnet"
if command -v hf >/dev/null 2>&1; then
  hf auth login
  hf download project-oceania/zoocamnet --repo-type dataset --local-dir zoocamnet
elif command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli login
  huggingface-cli download project-oceania/zoocamnet --repo-type dataset --local-dir zoocamnet
else
  echo "     Skipped: install the CLI with 'uv tool install huggingface_hub' (or pip), then re-run."
fi
echo "     Afterwards keep only the Bivalvia and veliger classes; delete the rest to save space."

cat <<'MANUAL'

Manual downloads (need a browser or a free account):
  - Mendeley M-Count, settled mussel larvae (CC BY 4.0): https://data.mendeley.com/datasets/9cs8pnhkxj/1  -> "Download All"
  - LUMCON protocol figures (CC BY 4.0): https://www.protocols.io/view/the-shell-seeker-oyster-larvae-sampling-with-the-p-dip74drn.html
  - LUMCON EcoTaxa training set (check license on export): https://ecotaxa.obs-vlfr.fr/prj/13814
  - Roboflow LARVAE_TRAIN (CC BY 4.0): https://universe.roboflow.com/colabs-workspace-bluu9/larvae_train/dataset/
  - Frontiers in Zoology Fig 1 (check license): https://frontiersinzoology.biomedcentral.com/articles/10.1186/s12983-018-0259-8/figures/1
MANUAL
echo "Done."
