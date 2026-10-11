# -*- coding: utf-8 -*-
"""quran.py — the Word, carried into the wire as data.

House rule, and it never bends: THE BOOK IS THE WORD OF ALLAH. It is the
greatest of sanctities, and this file holds a faithful local copy of a
published mushaf — not a paraphrase, not a summary, not a single invented
letter. The Arabic here is the Qur'an; the transliteration and the translation
are only a door for a reader who does not yet read Arabic.

The whole Book is carried: all 114 surahs, 6236 ayahs, in a local data file
`quran_data.json` (queried algorithmically from the source below, then copied
here byte-for-byte — the file is the local copy, this module just opens it).

Sources:
    Arabic:          alquran.cloud · edition "quran-uthmani"  (Hafs · al-rasm
                     al-'Uthmani — the script of the printed mushaf)
    Transliteration: alquran.cloud · edition "en.transliteration"
    Translation:     alquran.cloud · edition "en.sahih"  (Saheeh International)

Nothing here is depicted. Islam forbids imaging Allah, the prophets and the
companions — no such image exists or could ever be produced here. This room
holds words only, on light.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "quran_data.json")

with open(_DATA, encoding="utf-8") as _f:
    _BLOB = json.load(_f)

# SURAS: every surah, in mushaf order (1..114). Each surah is a dict:
#   number, name, arabic_name, translation, meccan,
#   about  (a short factual note), and ayahs:
#       [{n, ar (the Qur'an), tr (transliteration), en (translation)}, ...]
SURAS = _BLOB["suras"]

_BY_NUMBER = {s["number"]: s for s in SURAS}

SOURCES = {
    "arabic": "alquran.cloud · quran-uthmani (Hafs · Uthmani script)",
    "transliteration": "alquran.cloud · en.transliteration",
    "translation": "alquran.cloud · en.sahih (Saheeh International)",
}

# The full reading order: the mushaf itself, Al-Faatiha through An-Naas.
ORDER = [s["number"] for s in SURAS]


def surah(number):
    """One surah by its mushaf number (1..114), or None."""
    return _BY_NUMBER.get(number)


def all_suras():
    """Every surah, in the order of the mushaf (all 114)."""
    return [s for s in SURAS]
