# -*- coding: utf-8 -*-
"""quranworld.py — the motif engine: a reverent world for each ayah.

What this is, said plainly so it can never be mistaken:
  * These worlds are IMPRESSIONS keyed to images and themes NAMED in a verse
    (time, dawn, loss, refuge, light, a path, abundance, the whisper...). They
    are a quiet aid to contemplation. They are NOT the meaning of the ayah —
    its true meaning is with Allah alone — and they never claim to be.
  * NOTHING IS DEPICTED. No Allah, no prophets, no companions, no figure of any
    kind. Only abstract low-poly forms: light, sand, water, stone, arcs, stars.
    If a form cannot be drawn without a figure, it is not drawn.
  * The words shown on the sky are the authentic Arabic from quran.py — never
    altered, never paraphrased, never rendered as an image.

The engine is deterministic: the same ayah always yields the same world, built
from a seed of surah:ayah, so nothing shifts under the reader's feet.
"""
from __future__ import annotations
import math
import random

# each motif: a palette + one abstract form + a motion feel
MOTIFS = {
    "mercy":     {"sky": (0.03, 0.05, 0.09), "ground": (0.05, 0.09, 0.12),
                  "ring": (0.48, 0.78, 0.80), "form": "canopy", "motion": "calm"},
    "light":     {"sky": (0.05, 0.06, 0.10), "ground": (0.09, 0.10, 0.13),
                  "ring": (0.88, 0.84, 0.55), "form": "beam", "motion": "drift"},
    "lord":      {"sky": (0.02, 0.03, 0.06), "ground": (0.06, 0.06, 0.10),
                  "ring": (0.62, 0.62, 0.95), "form": "column", "motion": "calm"},
    "worlds":    {"sky": (0.01, 0.02, 0.05), "ground": (0.03, 0.04, 0.09),
                  "ring": (0.52, 0.62, 0.92), "form": "orb", "motion": "orbit"},
    "path":      {"sky": (0.03, 0.05, 0.06), "ground": (0.10, 0.11, 0.10),
                  "ring": (0.88, 0.80, 0.46), "form": "path", "motion": "calm"},
    "time":      {"sky": (0.06, 0.05, 0.04), "ground": (0.12, 0.10, 0.07),
                  "ring": (0.87, 0.72, 0.42), "form": "hourglass", "motion": "drift"},
    "loss":      {"sky": (0.02, 0.02, 0.03), "ground": (0.05, 0.05, 0.06),
                  "ring": (0.52, 0.52, 0.58), "form": "faded", "motion": "calm"},
    "patience":  {"sky": (0.03, 0.05, 0.05), "ground": (0.07, 0.10, 0.09),
                  "ring": (0.56, 0.82, 0.62), "form": "ripple", "motion": "pulse"},
    "truth":     {"sky": (0.03, 0.05, 0.08), "ground": (0.07, 0.09, 0.12),
                  "ring": (0.72, 0.86, 0.90), "form": "column", "motion": "calm"},
    "dawn":      {"sky": (0.09, 0.045, 0.045), "ground": (0.12, 0.09, 0.08),
                  "ring": (0.98, 0.70, 0.42), "form": "arc", "motion": "rise"},
    "darkness":  {"sky": (0.012, 0.012, 0.02), "ground": (0.03, 0.03, 0.05),
                  "ring": (0.36, 0.36, 0.52), "form": "dim", "motion": "calm"},
    "refuge":    {"sky": (0.02, 0.04, 0.05), "ground": (0.06, 0.09, 0.10),
                  "ring": (0.52, 0.80, 0.86), "form": "canopy", "motion": "calm"},
    "abundance": {"sky": (0.04, 0.05, 0.04), "ground": (0.08, 0.10, 0.07),
                  "ring": (0.82, 0.86, 0.52), "form": "orbs", "motion": "drift"},
    "one":       {"sky": (0.02, 0.03, 0.06), "ground": (0.06, 0.06, 0.10),
                  "ring": (0.72, 0.72, 1.0), "form": "column", "motion": "calm"},
    "whisper":   {"sky": (0.02, 0.02, 0.04), "ground": (0.04, 0.04, 0.07),
                  "ring": (0.46, 0.40, 0.62), "form": "motes", "motion": "drift"},
    "anger":     {"sky": (0.07, 0.03, 0.03), "ground": (0.10, 0.06, 0.05),
                  "ring": (0.95, 0.42, 0.32), "form": "ember", "motion": "rise"},
    "water":     {"sky": (0.02, 0.04, 0.06), "ground": (0.05, 0.09, 0.12),
                  "ring": (0.52, 0.72, 0.92), "form": "pool", "motion": "calm"},
    "soul":      {"sky": (0.03, 0.03, 0.05), "ground": (0.07, 0.07, 0.10),
                  "ring": (0.82, 0.60, 0.92), "form": "heart", "motion": "pulse"},
}

# keyword -> motif (matched against the English translation of the verse)
KEYWORDS = {
    "merciful": "mercy", "mercy": "mercy", "compassion": "mercy",
    "light": "light", "guide": "path", "guidance": "path", "straight": "path",
    "path": "path", "way": "path",
    "lord": "lord", "sovereign": "lord", "king": "lord", "god": "lord",
    "worlds": "worlds", "world": "worlds",
    "time": "time", "epoch": "time", "day": "time", "declining": "time",
    "loss": "loss", "lost": "loss", "astray": "loss", "cut off": "loss",
    "patience": "patience", "patient": "patience",
    "truth": "truth", "righteous": "truth", "deeds": "truth",
    "daybreak": "dawn", "dawn": "dawn", "favor": "dawn", "morning": "dawn",
    "darkness": "darkness", "night": "darkness", "settles": "darkness",
    "refuge": "refuge", "seeks": "refuge", "envi": "refuge", "evil": "refuge",
    "abundance": "abundance", "granted": "abundance", "kawthar": "abundance",
    "one": "one", "eternal": "one", "equivalent": "one", "begets": "one",
    "born": "one", "refuge,": "one",
    "whisper": "whisper", "whisperer": "whisper", "breasts": "whisper",
    "jinn": "whisper", "retreating": "whisper",
    "anger": "anger", "blowers": "anger", "knots": "anger", "envy": "anger",
    "water": "water", "rain": "water",
    "soul": "soul", "heart": "soul", "breast": "soul",
}

# the base character of each surah, so a world is never soulless
SURAH_THEME = {1: "mercy", 103: "time", 108: "abundance",
               112: "one", 113: "dawn", 114: "refuge"}


def _scatter(seed, n, rmin, rmax):
    rnd = random.Random(seed * 13 + 7)
    out = []
    for _ in range(n):
        a = rnd.random() * 2 * math.pi
        r = rmin + rnd.random() * (rmax - rmin)
        out.append((r * math.cos(a), r * math.sin(a), rnd.uniform(0, 2 * math.pi)))
    return out


def _motifs_for(surah, ayah):
    text = " " + (ayah.get("en") or "").lower() + " "
    found = []
    for kw in sorted(KEYWORDS, key=len, reverse=True):
        if kw in text and KEYWORDS[kw] not in found:
            found.append(KEYWORDS[kw])
    base = SURAH_THEME.get(surah["number"])
    if base and base not in found:
        found.insert(0, base)
    return (found or ["mercy"])[:3]


def recipe(surah, ayah):
    """Deterministically weave one ayah's named images into a world recipe."""
    seed = int(surah["number"]) * 1000 + int(ayah["n"])
    motifs = _motifs_for(surah, ayah)
    primary = MOTIFS[motifs[0]]
    ring = primary["ring"]
    props = [{"kind": primary["form"], "x": 0.0, "z": 0.0, "s": 2.4, "ph": 0.0,
              "col": ring, "central": True},
             {"kind": "ring", "x": 0.0, "z": 0.0, "s": 11.0, "ph": 0.0, "col": ring}]
    kinds = [MOTIFS[m]["form"] for m in motifs]
    cols = [MOTIFS[m]["ring"] for m in motifs]
    for i, (x, z, ph) in enumerate(_scatter(seed, 12, 10.0, 26.0)):
        props.append({"kind": kinds[i % len(kinds)], "x": x, "z": z, "s": 1.0,
                      "ph": ph, "col": cols[i % len(cols)]})
    return {"seed": seed, "sky": primary["sky"], "ground": primary["ground"],
            "ring": ring, "motifs": motifs, "props": props,
            "motion": primary.get("motion", "calm")}


def sky_text(surah, ayah):
    """The words to write on the sky — authentic Arabic, never altered."""
    return {"arabic": ayah["ar"], "transliteration": ayah["tr"],
            "translation": ayah["en"],
            "ref": f"{surah['number']}:{ayah['n']}  {surah['name']} "
                   f"\u2014 {surah['translation']}"}


def describe(reci):
    """A plain, honest caption of what the world is made of."""
    names = ", ".join(reci["motifs"])
    return f"a reverent impression of the verse's named images ({names})"