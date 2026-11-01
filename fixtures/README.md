# Fixtures

| Folder | What | Use |
|---|---|---|
| `slides/` | 5 synthetic counting-slide photos (1600×1200, 1.6 µm/px, 22–54 larvae each) with `*.json` ground truth: every larva's outline polygon, class (`live`, `abnormal`, `dead`), length and gut. Regenerate with `npm run slides` | Engine tests, and "Use a sample slide" in the app |
| `demo/t03-today.*` | The demo photo for T-03: 43 live, 5 abnormal, 15 dead, mean 128 µm. Identical to the seed's T-03 "today" check | The live demo upload |
| `real/j006/` | 30 real bright-field photos (1–2 larvae each) and `labels.json` | Tests only. **No license**: gitignored; never shown in the app, video or repo |
| `sources/` | Where other larvae photos come from, their licenses, and an optional fetch script | Optional |

Synthetic photos are drawn by `tools/gen_slides.py`, not photographed. Show the "Synthetic sample"
badge whenever one appears in the app or the video.
