"""Render synthetic bright-field microscope photos of oyster larvae on a counting slide.

Synthetic images, not photographs. Every image comes with a ground-truth JSON file
(position, outline polygon, class, shell length and gut fullness of every larva), so
the analysis engine can be tested against known answers.

Usage
  python tools/gen_slides.py fixtures/slides            # the 5 default test slides
  python tools/gen_slides.py OUT --spec specs.json      # render a list of custom slides
  python tools/gen_slides.py OUT --count 30             # default slides, 30 larvae each

A spec (one JSON object per slide, all keys optional except name):
  {"name": "t03-today", "seed": 7, "stage": "umbo", "grid": true,
   "counts": {"live": 43, "abnormal": 5, "dead": 15},   # exact class counts
   "mean_len_um": 128, "sd_len_um": 20,                  # exact for live + abnormal
   "gut": 0.18,                                          # exact mean over live larvae
   "clumps": 0}
Without "counts", use "n" plus "p_dead" and "p_abnormal" (random draw).

Classes in the truth file: "live", "abnormal", "dead". Clump members are live and share
a "clump" id. Stages: "d" (D-stage), "umbo", "eyed".
Also importable: from gen_slides import make_slide.
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

GENERATOR_VERSION = "gen-slides-2"
W, H = 1600, 1200
UM_PER_PX = 1.6          # 1 mm = 625 px, so the photo covers 2.56 x 1.92 mm
CHAMBER_DEPTH_MM = 1.0   # Sedgewick-Rafter chamber


def d_shape(L, Hh, rng, abnormal=False, umbo=False):
    """Polygon (local px coords, centred) for a D-shaped or umbo larva."""
    a, b = L / 2, Hh / 2
    pts = []
    n = 72
    phase = rng.uniform(0, 2 * math.pi)
    for i in range(n):
        t = 2 * math.pi * i / n
        x = a * math.cos(t)
        y = b * math.sin(t) + 0.06 * Hh
        hinge = -b * (0.66 if not umbo else 0.86)  # straight hinge at the top
        if y < hinge:
            y = hinge
            if umbo and abs(x) < 0.22 * L:
                y -= (0.22 * L - abs(x)) * 0.35
        if abnormal:
            r = 1 + 0.13 * math.sin(3 * t + phase) + 0.07 * math.sin(5 * t + 2 * phase)
            if math.cos(t - phase) > 0.85:
                r *= 0.78  # indented / malformed valve
            x *= r
            y *= r
        pts.append((x, y))
    return pts


def rot(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def mask_from_poly(pts, size, ss=4):
    img = Image.new("L", (size * ss, size * ss), 0)
    d = ImageDraw.Draw(img)
    off = size / 2
    d.polygon([((x + off) * ss, (y + off) * ss) for x, y in pts], fill=255)
    img = img.resize((size, size), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def ellipse_mask(size, cx, cy, ax, by, ang, ss=4):
    img = Image.new("L", (size * ss, size * ss), 0)
    d = ImageDraw.Draw(img)
    pts = []
    c, s = math.cos(ang), math.sin(ang)
    for i in range(48):
        t = 2 * math.pi * i / 48
        x, y = ax * math.cos(t), by * math.sin(t)
        pts.append(((x * c - y * s + cx + size / 2) * ss, (x * s + y * c + cy + size / 2) * ss))
    d.polygon(pts, fill=255)
    img = img.resize((size, size), Image.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def blur(m, r):
    im = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255.0


def erode(m, r):
    im = Image.fromarray((m * 255).astype(np.uint8))
    k = 2 * int(r) + 1
    return np.asarray(im.filter(ImageFilter.MinFilter(k)), dtype=np.float32) / 255.0


def render_larva(T, cx, cy, L_px, cls, rng, gut_full, stage):
    """Darken the transmission map T in place. Returns the outline polygon in image px."""
    Hh = L_px * (0.84 if stage != "umbo" else 0.9)
    umbo = stage in ("umbo", "eyed")
    pts = d_shape(L_px, Hh, rng, abnormal=(cls == "abnormal"), umbo=umbo)
    ang = rng.uniform(0, 2 * math.pi)
    pts = rot(pts, ang)
    size = int(L_px * 1.5) + 8
    size += size % 2
    M = mask_from_poly(pts, size)
    rimw = max(1.5, L_px * 0.035)
    inner = erode(M, rimw)
    R = blur(np.clip(M - inner, 0, 1), 0.8)
    if cls == "dead":  # empty shell: faint, hollow, rim only
        ts = np.array([0.975, 0.965, 0.95])
        tr = np.array([0.72, 0.70, 0.67])
        tissue = np.zeros_like(M)
        gut = np.zeros_like(M)
        tt = tg = np.array([1, 1, 1])
    else:
        ts = np.array([0.90, 0.84, 0.72])
        tr = np.array([0.58, 0.52, 0.42])
        tscale = 0.72 if cls != "abnormal" else rng.uniform(0.45, 0.62)
        tcx = rng.uniform(-0.04, 0.04) * L_px
        tcy = 0.05 * Hh + (rng.uniform(0.05, 0.12) * Hh if cls == "abnormal" else 0)
        c, s = math.cos(ang), math.sin(ang)
        tx, ty = tcx * c - tcy * s, tcx * s + tcy * c
        tissue = ellipse_mask(size, tx, ty, L_px / 2 * tscale, Hh / 2 * tscale * 0.92, ang)
        tissue = blur(tissue * M, 1.5)
        tt = np.array([0.80, 0.70, 0.52])
        gsc = 0.13 + 0.10 * gut_full  # digestive gland: dark when fed
        gx, gy = (-0.04 * L_px) * c - (-0.02 * Hh) * s, (-0.04 * L_px) * s + (-0.02 * Hh) * c
        gut = ellipse_mask(size, gx, gy, L_px * gsc, Hh * gsc * 0.85, ang + 0.4)
        gut = blur(gut * tissue, 1.2) * gut_full
        tg = np.array([0.52, 0.50, 0.34])
    eye = np.zeros_like(M)
    if stage == "eyed" and cls != "dead":
        ex, ey = 0.18 * L_px, 0.12 * Hh
        c, s = math.cos(ang), math.sin(ang)
        eye = ellipse_mask(size, ex * c - ey * s, ex * s + ey * c, L_px * 0.035, L_px * 0.035, 0)
    x0, y0 = int(round(cx - size / 2)), int(round(cy - size / 2))
    poly = [[round(x + size / 2 + x0, 1), round(y + size / 2 + y0, 1)] for x, y in pts[::2]]
    x1, y1 = x0 + size, y0 + size
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = size - max(0, x1 - W), size - max(0, y1 - H)
    if sx1 <= sx0 or sy1 <= sy0:
        return poly
    sl = (slice(y0 + sy0, y0 + sy1), slice(x0 + sx0, x0 + sx1))
    lsl = (slice(sy0, sy1), slice(sx0, sx1))
    for ch in range(3):
        f = (1 - M[lsl] * (1 - ts[ch]))
        f *= (1 - R[lsl] * (1 - tr[ch]))
        f *= (1 - tissue[lsl] * (1 - tt[ch]))
        f *= (1 - gut[lsl] * (1 - tg[ch]))
        f *= (1 - eye[lsl] * 0.85)
        T[sl + (ch,)] *= f
    return poly


def _exact(values, target_mean, target_sd=None, lo=None, hi=None):
    """Shift (and scale) values so their mean (and SD) hit the targets exactly."""
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return v
    for _ in range(4):
        if target_sd is not None and len(v) > 1 and v.std(ddof=1) > 0:
            v = target_mean + (v - v.mean()) / v.std(ddof=1) * target_sd
        else:
            v = v + (target_mean - v.mean())
        if lo is not None or hi is not None:
            v = np.clip(v, lo if lo is not None else -np.inf, hi if hi is not None else np.inf)
    return v


def make_slide(name, out, seed=1, n=40, mean_len_um=150, sd_len_um=15, p_dead=0.05,
               p_abnormal=0.05, gut=0.7, stage="umbo", grid=True, clumps=1, counts=None):
    """Render one slide to OUT/NAME.jpg plus OUT/NAME.json (ground truth). Returns the truth dict."""
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    vign = 1 - 0.10 * r ** 2
    base = np.array([234, 230, 221], np.float32)
    grad = 1 + 0.04 * (xx / W - 0.5)
    bg = base[None, None, :] * (vign * grad)[..., None]
    T = np.ones((H, W, 3), np.float32)

    grid_info = None
    if grid:  # Sedgewick-Rafter grid, 1 mm squares
        sp = 1000 / UM_PER_PX
        ox, oy = rng.uniform(80, sp - 80), rng.uniform(80, sp - 80)
        g = np.zeros((H, W), np.float32)
        for x in np.arange(ox, W, sp):
            xi = int(round(x))
            g[:, max(0, xi - 1):xi + 2] = 1
        for y in np.arange(oy, H, sp):
            yi = int(round(y))
            g[max(0, yi - 1):yi + 2, :] = 1
        g = blur(g, 0.9)
        for ch, t in enumerate([0.62, 0.62, 0.66]):
            T[..., ch] *= 1 - g * (1 - t)
        grid_info = {"spacing_px": round(sp, 2), "offset_x": round(ox, 1), "offset_y": round(oy, 1)}

    for _ in range(int(rng.integers(140, 260))):  # algae cells and small debris
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        rr = rng.uniform(1.6, 3.6)
        sz = 14
        m = ellipse_mask(sz, 0, 0, rr, rr * rng.uniform(0.7, 1.0), rng.uniform(0, 3))
        x0, y0 = int(x) - sz // 2, int(y) - sz // 2
        if x0 < 0 or y0 < 0 or x0 + sz > W or y0 + sz > H:
            continue
        col = [0.80, 0.84, 0.70] if rng.random() < 0.7 else [0.75, 0.72, 0.68]
        for ch in range(3):
            T[y0:y0 + sz, x0:x0 + sz, ch] *= 1 - m * (1 - col[ch])
    for _ in range(int(rng.integers(6, 14))):  # elongated debris
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        sz = 60
        m = ellipse_mask(sz, 0, 0, rng.uniform(14, 26), rng.uniform(1.5, 3), rng.uniform(0, 3))
        x0, y0 = int(x) - sz // 2, int(y) - sz // 2
        if x0 < 0 or y0 < 0 or x0 + sz > W or y0 + sz > H:
            continue
        for ch, t in enumerate([0.72, 0.70, 0.66]):
            T[y0:y0 + sz, x0:x0 + sz, ch] *= 1 - m * (1 - t)

    # Which classes, which lengths, which gut values
    if counts:
        classes = (["live"] * int(counts.get("live", 0)) + ["abnormal"] * int(counts.get("abnormal", 0))
                   + ["dead"] * int(counts.get("dead", 0)))
        rng.shuffle(classes)
    else:
        u = rng.random(n)
        classes = ["dead" if v < p_dead else ("abnormal" if v < p_dead + p_abnormal else "live") for v in u]
    k_alive = [i for i, c in enumerate(classes) if c != "dead"]
    lengths = np.maximum(60, rng.normal(mean_len_um, sd_len_um, len(classes)))
    if counts and k_alive:
        lengths[k_alive] = _exact(lengths[k_alive], mean_len_um, sd_len_um, lo=60)
    guts = np.zeros(len(classes))
    k_live = [i for i, c in enumerate(classes) if c == "live"]
    k_abn = [i for i, c in enumerate(classes) if c == "abnormal"]
    guts[k_live + k_abn] = np.clip(rng.normal(gut, 0.12, len(k_live) + len(k_abn)), 0, 1)
    if counts and k_live:
        guts[k_live] = _exact(guts[k_live], gut, lo=0, hi=1)

    truth, placed = [], []

    def free(x, y, rad):
        return all((px - x) ** 2 + (py - y) ** 2 >= (pr + rad + 6) ** 2 for px, py, pr in placed)

    tries = 0
    for i, cls in enumerate(classes):
        L_um = float(lengths[i])
        L = L_um / UM_PER_PX
        rad = L * 0.55
        while tries < len(classes) * 400:
            tries += 1
            x, y = rng.uniform(rad + 4, W - rad - 4), rng.uniform(rad + 4, H - rad - 4)
            if free(x, y, rad):
                break
        else:
            raise RuntimeError(f"{name}: no room for {len(classes)} larvae; lower the count")
        g = float(guts[i])
        poly = render_larva(T, x, y, L, cls, rng, g, stage)
        placed.append((x, y, rad))
        truth.append({"id": len(truth) + 1, "x": round(x, 1), "y": round(y, 1), "len_um": round(L_um, 1),
                      "cls": cls, "clump": None, "gut": round(g, 3) if cls != "dead" else None, "poly": poly})

    k = 0
    while k < clumps and tries < len(classes) * 800 + 2000:  # touching pairs of live larvae
        tries += 1
        L_um = float(max(60, rng.normal(mean_len_um, sd_len_um)))
        L = L_um / UM_PER_PX
        rad = L * 1.1
        x, y = rng.uniform(rad + 4, W - rad - 4), rng.uniform(rad + 4, H - rad - 4)
        if not free(x, y, rad):
            continue
        a = rng.uniform(0, 2 * math.pi)
        d = L * 0.42
        for j in (-1, 1):
            cx, cy = x + j * d * math.cos(a), y + j * d * math.sin(a)
            g = float(np.clip(rng.normal(gut, 0.12), 0, 1))
            poly = render_larva(T, cx, cy, L, "live", rng, g, stage)
            truth.append({"id": len(truth) + 1, "x": round(cx, 1), "y": round(cy, 1), "len_um": round(L_um, 1),
                          "cls": "live", "clump": k, "gut": round(g, 3), "poly": poly})
        placed.append((x, y, rad))
        k += 1

    img = bg * T
    img += rng.normal(0, 2.2, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    Image.fromarray(img).filter(ImageFilter.GaussianBlur(0.6)).save(os.path.join(out, name + ".jpg"), quality=88)

    singles_alive = [t for t in truth if t["cls"] != "dead" and t["clump"] is None]
    live_singles = [t for t in truth if t["cls"] == "live" and t["clump"] is None]
    lens = np.array([t["len_um"] for t in singles_alive]) if singles_alive else np.array([])
    c = {"live": 0, "abnormal": 0, "dead": 0}
    for t in truth:
        c[t["cls"]] += 1
    meta = {
        "name": name, "synthetic": True, "generator": GENERATOR_VERSION, "seed": seed,
        "w": W, "h": H, "um_per_px": UM_PER_PX, "chamber_depth_mm": CHAMBER_DEPTH_MM,
        "photo_volume_ml": round(W * H * (UM_PER_PX / 1000) ** 2 * CHAMBER_DEPTH_MM / 1000, 6),
        "grid": grid_info, "stage": stage, "counts": c, "clumps": k,
        "mean_len_um": round(float(lens.mean()), 1) if len(lens) else None,
        "sd_len_um": round(float(lens.std(ddof=1)), 1) if len(lens) > 1 else None,
        "gut_mean_live": round(float(np.mean([t["gut"] for t in live_singles])), 3) if live_singles else None,
        "truth": truth,
    }
    with open(os.path.join(out, name + ".json"), "w") as f:
        json.dump(meta, f)
    return meta


# Default test slides at realistic densities (a concentrated sample gives about 20-50 larvae
# per field of view). name, seed, n, mean, sd, p_dead, p_abnormal, gut, stage, grid, clumps
DEFAULT_SLIDES = [
    ("slide-healthy-umbo", 11, 42, 168, 13, 0.03, 0.04, 0.85, "umbo", True, 1),
    ("slide-vibrio-suspect", 12, 46, 124, 22, 0.24, 0.08, 0.15, "umbo", True, 1),
    ("slide-low-omega", 13, 44, 96, 9, 0.08, 0.22, 0.6, "d", False, 1),
    ("slide-d-stage", 14, 50, 78, 6, 0.02, 0.03, 0.7, "d", True, 2),
    ("slide-eyed", 15, 22, 292, 22, 0.04, 0.03, 0.8, "eyed", False, 1),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", default="fixtures/slides")
    ap.add_argument("--spec", help="JSON file with a list of slide specs")
    ap.add_argument("--count", type=int, help="override the larva count of the default slides")
    a = ap.parse_args()
    if a.spec:
        with open(a.spec) as f:
            specs = json.load(f)
        for s in specs:
            s = dict(s)
            name = s.pop("name")
            meta = make_slide(name, a.out, **s)
            print(name, meta["counts"])
        return
    for name, seed, n, mean, sd, pd, pa, gut, stage, grid, clumps in DEFAULT_SLIDES:
        meta = make_slide(name, a.out, seed=seed, n=a.count or n, mean_len_um=mean, sd_len_um=sd,
                          p_dead=pd, p_abnormal=pa, gut=gut, stage=stage, grid=grid, clumps=clumps)
        print(name, sum(meta["counts"].values()), meta["counts"])


if __name__ == "__main__":
    main()
