# Larvae photos: what exists, what's in this repo, how to use it

**You don't need anything from this page for the MVP.** The repo already has the synthetic test
slides (`fixtures/slides`), the demo photo (`fixtures/demo`) and 30 real photos
(`fixtures/real/j006`). This page records where real photos come from and their licenses.

Searched Nov 1, 2026: GitHub (repo and code search), Zenodo, Hugging Face, Mendeley Data,
protocols.io, Roboflow, PLOS, MDPI, BMC, NOAA, US EPA, Wikimedia Commons and university reports.

## Bottom line

- **What exists openly:** high-magnification photos of single larvae, figures in open-access
  papers, and large sets of single-object plankton crops that include bivalve larvae.
- **What doesn't exist openly:** low-magnification "counting slide" photos with dozens of oyster
  larvae per view, the kind a hatchery tech takes. The groups that have them (MIT Sea Grant/ARC,
  Louisiana Sea Grant, the 2021 Kakehi study) haven't released their images.
- **So:** test the engine on the synthetic slides (known answers) plus the real photos below.
  In the demo, show only photos you have rights to.

## Already in the repo (`fixtures/real/j006/`, gitignored)

| Folder | What | Count | License | Use |
|---|---|---|---|---|
| `fixtures/real/j006/` | Real bright-field microscope photos of oyster larvae, high magnification, 1–2 larvae each, with real clutter: air bubbles, counting-grid lines, scratches, debris, dark exposures. Species and µm-per-pixel not stated. From [epigeneticstoocean/oyster_larvae_photo_analysis](https://github.com/epigeneticstoocean/oyster_larvae_photo_analysis). | 30 photos, 34 whole larvae + 1 cut off at the edge, all alive | **None stated** (all rights reserved by default) | Local testing only: detection, sizing, rejecting bubbles and grid lines. Ask the authors before showing them publicly. |

`labels.json` has per-photo counts and a list of distractors, counted by eye from thumbnails
(verify before treating them as ground truth). `contact-sheet.jpg` shows all 30 at a glance.

## Openly licensed: OK in your demo, with credit

| Source | What | License | How to get it |
|---|---|---|---|
| [PLOS ONE 2018, "Factors affecting infection of corals and larval oysters by *Vibrio coralliilyticus*"](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0199475) | Fig 1: Pacific oyster larvae healthy, swimming, diseased, diseased with released velar cells, and dead (50 µm scale bar). Fig 2: infected larvae with protruding velum. This matches our live / abnormal / dead classes. | **CC0 public domain** | `bash fixtures/sources/fetch_sources.sh`, or "Download" under each figure |
| [ZooCAMNet on Hugging Face](https://huggingface.co/datasets/project-oceania/zoocamnet) | 1.29 million plankton images from the Bay of Biscay. Classes include **Bivalvia (~2,500 training images)** and **veliger (127)**. One object per image. | **CC BY 4.0** | Free Hugging Face login, accept the conditions, then `bash fixtures/sources/fetch_sources.sh` (~3 GB) |
| [LUMCON "The Shell Seeker" protocol (protocols.io)](https://www.protocols.io/view/the-shell-seeker-oyster-larvae-sampling-with-the-p-dip74drn.html) | Fig 3 "Oyster larvae through the microscope" and Fig 7 "Larva characteristics". Links to the [EcoTaxa LUMCON Oyster Larvae Training Set 2024](https://ecotaxa.obs-vlfr.fr/prj/13814) of identified bivalve larva images. | Protocol: **CC BY 4.0**. EcoTaxa set: license not shown, so check when you export (free account). | Manual |
| [Mendeley Data: M-Count (PNNL, 2025)](https://data.mendeley.com/datasets/9cs8pnhkxj/1) | Camera photos of settled mussel larvae (*Mytilus galloprovincialis*) on test plates, hundreds per cm². Not oysters and not microscope, but a good dense-counting stress test. | **CC BY 4.0** | Manual ("Download All") |
| [Frontiers in Zoology 2018, Pacific oyster nervous system development, Fig 1](https://frontiersinzoology.biomedcentral.com/articles/10.1186/s12983-018-0259-8/figures/1) | Light micrographs of Pacific oyster larvae from trochophore to pediveliger (20 µm scale bars). Good for checking stage sizes. | Open-access journal. Confirm the license line on the article page. | Manual |
| [Roboflow: LARVAE_TRAIN](https://universe.roboflow.com/colabs-workspace-bluu9/larvae_train/dataset/) | Labeled larvae images, classes "d", "larvae", "s". Species not stated, so look at the images first. | **CC BY 4.0** | Free Roboflow account, export |

## Testing only: ask permission before showing publicly

| Source | What | Terms |
|---|---|---|
| [EurekAlert: ~12-day-old oyster larvae under the microscope (Laura Spencer / UW)](https://www.eurekalert.org/multimedia/909644) | A University of Washington microscope photo | "Credit required", licensed content |
| [Tristyn19/Oyster_Seed_Counting](https://github.com/Tristyn19/Oyster_Seed_Counting) | 8 short videos of oyster *seed* (post-larval), for a future seed mode | No license |

## Look, don't copy (copyrighted, good for learning what stages look like)

- [NT Government (Australia), blacklip rock oyster hatchery protocol](https://nt.gov.au/__data/assets/pdf_file/0020/1072244/hatchery-protocol-black-rock-oyster-report-123.pdf), Fig 7: D-veliger → umbo → eyed → pediveliger → spat, with measurements. © NT Government 2021, no reproduction without permission.
- [University of Essex, "Quantification and staging of oyster larvae"](https://tracegasbiology.essex.ac.uk/pdfs/REPORT%20Oyster%20Larvae%202016.pdf), Fig 1A: Pacific oyster from D-stage to settlement. No license stated.

## Checked, nothing usable

Wikimedia Commons (no oyster larva micrographs found), other GitHub oyster-larvae repos (code and
charts only), NOAA photo library (fish larvae, people at microscopes), US EPA bivalve test method
(no images), PLOS ONE 2009 and 2011 acidification papers (figures are charts), and MDPI 2020 *Vibrio*
larvae paper (charts and maps).

## How to use these in the build

1. **Automated tests:** synthetic slides from `tools/gen_slides.py` (exact answers), plus `fixtures/real/j006` checked against `labels.json`.
2. **Tuning junk rejection:** the J006 bubbles, grid lines and scratches are realistic hard cases.
3. **Demo video:** synthetic slides (labeled synthetic), or CC0/CC BY images with credit on screen.
   One option: build "composite slides" by placing real CC-licensed larva crops (ZooCAMNet, PLOS CC0)
   on a real background, and label them as composites.
4. **If you ever want true counting-slide photos:** one email to a UW shellfish lab is the fastest
   free route.
