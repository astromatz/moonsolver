"""Richtet ein Mondfoto gegen den Render aus und beschriftet es.

Modell: Foto = Aehnlichkeitstransformation des Renders (Massstab, Drehung,
optional Spiegelung, Verschiebung). Gesucht wird ueber Drehung x Spiegelung x
Massstab. Pro Drehung wird der Render einmal gedreht und transformiert, pro
Massstab das (rechteckige) Foto skaliert; die Verschiebung liefert eine
normierte Kreuzkorrelation per FFT, die lokale Varianz des Renders kommt aus
Integralbildern. Danach Verfeinerung in einem Ausschnitt um das Optimum.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy import fft
from scipy.ndimage import affine_transform, gaussian_filter, zoom

from .data import MOON_RADIUS_KM, gazetteer
from .geometry import MoonView
from .render import Frame, render

WORKERS = max(1, (os.cpu_count() or 4) - 1)


@dataclass(frozen=True)
class Solution:
    theta_deg: float    # Drehung Render -> Foto
    mirror: bool        # Foto ist seitenverkehrt
    radius_px: float    # Mondradius im Foto
    center_x: float     # Scheibenmitte im Foto (darf ausserhalb liegen)
    center_y: float
    score: float        # normierte Kreuzkorrelation, 1 = perfekt

    def to_photo(self, view: MoonView, lat_deg, lon_deg):
        """Selenografische Koordinaten -> Fotopixel (x, y, sichtbar)."""
        x, y, vis = Frame(view, 0.0, 0.0, self.radius_px).project(lat_deg, lon_deg)
        rt = _rot(self.theta_deg).T
        px = rt[0, 0] * x + rt[0, 1] * y
        py = rt[1, 0] * x + rt[1, 1] * y
        if self.mirror:
            px = -px
        return px + self.center_x, py + self.center_y, vis

    def scaled(self, k: float) -> "Solution":
        return Solution(self.theta_deg, self.mirror, self.radius_px * k,
                        self.center_x * k, self.center_y * k, self.score)


@dataclass(frozen=True)
class Label:
    name: str
    x: float
    y: float
    diameter_px: float


def _rot(theta_deg: float) -> np.ndarray:
    t = math.radians(theta_deg)
    return np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])


@lru_cache(maxsize=8)
def _render_cached(view: MoonView, r_ref: int):
    return render(view, r_ref)


def _box(ii: np.ndarray, h: int, w: int) -> np.ndarray:
    """Summen ueber alle h x w Fenster aus einem Integralbild (mit Nullzeile/-spalte)."""
    return ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]


def _subpix(a, b, c):
    d = a - 2 * b + c
    return 0.0 if abs(d) < 1e-12 else float(np.clip(0.5 * (a - c) / d, -0.5, 0.5))


def _match_angle(img, frame: Frame, phi, window, photo, scales, mirror):
    """Alle Massstaebe fuer eine Drehung phi. window = (x0, y0, w, h) im gedrehten Render."""
    c = np.array([frame.cx, frame.cy])
    x0, y0, ww, wh = window
    # gedrehtes Renderfenster: rotated_xy -> render_xy = R(-phi) (rotated_xy - c) + c
    rm = _rot(-phi)
    swap = np.array([[0, 1], [1, 0]])
    mat = swap @ rm @ swap
    off = swap @ (rm @ (np.array([x0, y0], float) - c) + c)
    win = affine_transform(img, mat, off, output_shape=(wh, ww), order=1, cval=0.0)

    src = photo[:, ::-1] if mirror else photo
    ph, pw = src.shape
    sizes = [(max(2, round(ph * s)), max(2, round(pw * s))) for s in scales]
    mh = max(z[0] for z in sizes)
    mw = max(z[1] for z in sizes)
    big = np.zeros((wh + 2 * mh, ww + 2 * mw), np.float64)
    big[mh:mh + wh, mw:mw + ww] = win
    shape = (fft.next_fast_len(big.shape[0] + mh), fft.next_fast_len(big.shape[1] + mw))
    F = fft.rfft2(big, shape, workers=1)
    ii = np.pad(big, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ii2 = np.pad(big * big, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    out = []
    for s, (th, tw) in zip(scales, sizes):
        t = src
        if s < 1:
            t = gaussian_filter(t, max(0.0, 0.5 / s - 0.5))
        t = zoom(t, (th / ph, tw / pw), order=1)
        t = t - t.mean()
        var_t = float((t * t).sum())
        if var_t < 1e-9:
            continue
        n = th * tw
        corr = fft.irfft2(F * np.conj(fft.rfft2(t, shape, workers=1)), shape, workers=1)
        sf = _box(ii, th, tw)
        sf2 = _box(ii2, th, tw)
        corr = corr[:sf.shape[0], :sf.shape[1]]
        var_f = sf2 - sf * sf / n
        ncc = np.where(var_f > n * 1e-4, corr / np.sqrt(np.maximum(var_f, 1e-12) * var_t), -1.0)
        r, q = np.unravel_index(int(np.argmax(ncc)), ncc.shape)
        dr = _subpix(ncc[r - 1, q], ncc[r, q], ncc[r + 1, q]) if 0 < r < ncc.shape[0] - 1 else 0.0
        dq = _subpix(ncc[r, q - 1], ncc[r, q], ncc[r, q + 1]) if 0 < q < ncc.shape[1] - 1 else 0.0
        # Lage des (skalierten) Fotos im gedrehten Render
        o = np.array([q + dq - mw + x0, r + dr - mh + y0])
        # Fotopixel -> Patchpixel (zoom richtet die Eckpixel aufeinander aus), ggf. gespiegelt
        kx, ky = (tw - 1) / (pw - 1), (th - 1) / (ph - 1)
        fm = np.diag([-kx if mirror else kx, ky])
        b = np.array([kx * (pw - 1) if mirror else 0.0, 0.0])
        a = rm @ fm
        tvec = rm @ (b + o - c) + c
        center = np.linalg.solve(a, c - tvec)
        out.append(Solution(-phi, mirror, frame.r / ((kx + ky) / 2), float(center[0]), float(center[1]),
                            float(ncc[r, q])))
    return out


def _search(photo, view, r_ref, phis, scales, mirrors, window=None):
    img, frame = _render_cached(view, r_ref)
    win = window or (0, 0, img.shape[1], img.shape[0])
    jobs = [(phi, m) for m in mirrors for phi in phis]
    with ThreadPoolExecutor(WORKERS) as ex:
        res = ex.map(lambda j: _match_angle(img, frame, j[0], win, photo, scales, j[1]), jobs)
        out = [s for r in res for s in r]
    out.sort(key=lambda s: -s.score)
    return out


def prepare(photo_rgb: np.ndarray, max_dim: int) -> tuple[np.ndarray, float]:
    """Graustufen 0..1, auf max_dim verkleinert. Gibt Bild und Faktor (klein/original)."""
    g = np.asarray(photo_rgb, dtype=np.float32)
    if g.ndim == 3:
        g = g[..., :3].mean(axis=2)
    f = min(1.0, max_dim / max(g.shape))
    if f < 1:
        g = gaussian_filter(g, 0.5 / f)
        g = zoom(g, f, order=1)
        f = (g.shape[1] - 1) / (photo_rgb.shape[1] - 1)  # zoom richtet Eckpixel aus
    g = g - g.min()
    return g / max(float(g.max()), 1e-6), f


def _window_for(sol: Solution, frame: Frame, shape, margin: float):
    """Bereich im (um -theta) gedrehten Render, in dem das Foto liegen muss."""
    h, w = shape
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], float)
    s = frame.r / sol.radius_px
    rel = corners - [sol.center_x, sol.center_y]
    if sol.mirror:
        rel[:, 0] = -rel[:, 0]
    pts = rel * s + [frame.cx, frame.cy]  # im gedrehten Render ist das Foto achsparallel
    lo = pts.min(0) - margin * s * max(h, w)
    hi = pts.max(0) + margin * s * max(h, w)
    x0, y0 = int(math.floor(lo[0])), int(math.floor(lo[1]))
    return (x0, y0, int(math.ceil(hi[0])) - x0, int(math.ceil(hi[1])) - y0)


def _distinct(cands, n):
    picked = []
    for c in cands:
        if all(abs((c.theta_deg - o.theta_deg + 180) % 360 - 180) > 8 or c.mirror != o.mirror
               or abs(math.log(c.radius_px / o.radius_px)) > 0.2 for o in picked):
            picked.append(c)
        if len(picked) == n:
            break
    return picked


def _refine(photo, view, sol: Solution, d_theta, steps_theta, d_log, steps_scale, margin, r_max=1024):
    r_ref = int(min(r_max, max(64, 2 ** math.floor(math.log2(sol.radius_px)))))
    _, frame = _render_cached(view, r_ref)
    phis = -(sol.theta_deg + np.linspace(-d_theta, d_theta, steps_theta))
    s0 = r_ref / sol.radius_px
    scales = s0 * np.exp(np.linspace(-d_log, d_log, steps_scale))
    win = _window_for(sol, frame, photo.shape, margin)
    return _search(photo, view, r_ref, phis, scales, (sol.mirror,), win)[0]


def _coarse(photo_rgb, view, dim, r_lo, r_hi, step_r, step_deg, r_cap, mirrors):
    """Grobsuche. Radien in Vielfachen der Bildgroesse. Gibt Kandidaten in Originalpixeln."""
    small, f1 = prepare(photo_rgb, dim)
    d = max(small.shape)
    radii = d * np.exp(np.arange(math.log(r_lo), math.log(r_hi) + 1e-9, math.log(step_r)))
    level = lambda r: int(min(r_cap, max(32, 2 ** math.floor(math.log2(r)))))  # noqa: E731
    cands = []
    for r_ref in sorted({level(r) for r in radii}):
        rs = [r for r in radii if level(r) == r_ref]
        cands += _search(small, view, r_ref, np.arange(0, 360, step_deg), [r_ref / r for r in rs], mirrors)
    return [c.scaled(1 / f1) for c in sorted(cands, key=lambda s: -s.score)]


def _finish(photo_rgb, view, cands, n) -> Solution:
    mid, f2 = prepare(photo_rgb, 512)
    refined = [_refine(mid, view, c.scaled(f2), 6, 9, 0.12, 9, 0.25) for c in _distinct(cands, n)]
    best = max(refined, key=lambda s: s.score)
    return _refine(mid, view, best, 1.5, 7, 0.03, 7, 0.08).scaled(1 / f2)


GOOD_SCORE = 0.9  # ab hier gilt die schnelle Suche als sicher


def solve(photo_rgb: np.ndarray, view: MoonView, *, mirrors=(False, True)) -> Solution:
    # Schnell (ca. 40 s): Foto auf 160 px, alle Massstaebe vom kleinen Mond bis zum tiefen Ausschnitt
    best = _finish(photo_rgb, view, _coarse(photo_rgb, view, 160, 1 / 6, 8, 1.15, 6.0, 256, mirrors), 4)
    if best.score >= GOOD_SCORE:
        return best
    # Ausschnitte ohne Rand brauchen eine feinere Grobsuche (ca. 2 min): 256 px, Radius >= halbe Bildgroesse
    alt = _finish(photo_rgb, view, _coarse(photo_rgb, view, 256, 0.5, 8, 1.12, 5.0, 512, mirrors), 4)
    return alt if alt.score > best.score else best


def labels(sol: Solution, view: MoonView, width: int, height: int, *, min_diameter_px: float = 12) -> list[Label]:
    feats = [f for f in gazetteer() if f.code in ("AA", "SF")]
    lat = np.array([f.lat_deg for f in feats])
    lon = np.array([f.lon_deg for f in feats])
    x, y, vis = sol.to_photo(view, lat, lon)
    la, lo = np.radians(lat), np.radians(lon)
    up = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    vis = vis & (up @ view.sun_dir > 0.02)  # nur beleuchtete Seite
    scale = sol.radius_px / MOON_RADIUS_KM
    out = []
    for f, xi, yi, v in zip(feats, x, y, vis):
        dpx = f.diameter_km * scale
        if v and 0 <= xi < width and 0 <= yi < height and dpx >= min_diameter_px:
            out.append(Label(f.name, float(xi), float(yi), float(dpx)))
    return out


def locate(sol: Solution, view: MoonView, names: list[str]) -> dict[str, tuple[float, float]]:
    by = {f.name: f for f in gazetteer()}
    res = {}
    for n in names:
        f = by.get(n)
        if f:
            x, y, _ = sol.to_photo(view, f.lat_deg, f.lon_deg)
            res[n] = (float(x), float(y))
    return res
