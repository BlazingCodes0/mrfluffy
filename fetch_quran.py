# -*- coding: utf-8 -*-
"""fetch_quran.py — rebuild `quran_data.json` from the published source.

House rule: the Book is the word of Allah; nothing here is invented, paraphrased
or edited. This script only *copies* the mushaf from alquran.cloud, byte for
byte, into the local data file the room reads (`quran_data.json`). Run it only
to refresh that copy:

    python3 fetch_quran.py

    Arabic:          quran-uthmani (Hafs · al-rasm al-'Uthmani)
    Transliteration: en.transliteration
    Translation:     en.sahih (Saheeh International)
"""
import json
import os
import urllib.request

API = "https://api.alquran.cloud/v1/quran/"
EDITIONS = {"ar": "quran-uthmani", "tr": "en.transliteration", "en": "en.sahih"}
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quran_data.json")

# hand-written notes kept for the six small surahs the room began with.
CURATED_ABOUT = {
    1: ("The Opening — the seven oft-repeated verses, recited in every unit of "
        "the prayer. The Qur'an opens with it."),
    103: "By Time — how humankind is saved, and how it is lost, in three verses.",
    108: ("Al-Kawthar — the abundance given; the briefest surah of the Book, "
          "comfort against those who taunt."),
    112: ("Al-Ikhlaas — the purity of faith: the oneness of Allah, in four verses. "
          "The Prophet (peace be upon him) is reported to have said it equals a "
          "third of the Qur'an."),
    113: ("Al-Falaq — with 114, one of the two refuges (al-Mu'awwidhatan): seeking "
          "refuge with Allah from the harm of all that He created."),
    114: ("An-Nas — the second refuge, against the retreating whisperer that sows "
          "into the breast of mankind."),
}


def fetch(edition):
    with urllib.request.urlopen(API + edition, timeout=60) as r:
        return json.load(r)["data"]["surahs"]


def main():
    ar = fetch(EDITIONS["ar"])
    tr = fetch(EDITIONS["tr"])
    en = fetch(EDITIONS["en"])
    assert len(ar) == len(tr) == len(en) == 114

    suras = []
    for sa, st, se in zip(ar, tr, en):
        assert sa["number"] == st["number"] == se["number"]
        assert len(sa["ayahs"]) == len(st["ayahs"]) == len(se["ayahs"])
        ayahs = []
        for a, t, e in zip(sa["ayahs"], st["ayahs"], se["ayahs"]):
            assert a["numberInSurah"] == t["numberInSurah"] == e["numberInSurah"]
            ayahs.append({"n": a["numberInSurah"],
                          "ar": a["text"].lstrip("\ufeff"),
                          "tr": t["text"].lstrip("\ufeff"),
                          "en": e["text"].lstrip("\ufeff")})
        meccan = sa["revelationType"] == "Meccan"
        suras.append({
            "number": sa["number"],
            "name": sa["englishName"],
            "arabic_name": sa["name"],
            "translation": sa["englishNameTranslation"],
            "meccan": meccan,
            "about": CURATED_ABOUT.get(sa["number"]) or (
                f"A {'Meccan' if meccan else 'Medinan'} surah of {len(ayahs)} "
                f"verses. (Surah {sa['number']} of 114.)"),
            "ayahs": ayahs,
        })

    with open(DEST, "w", encoding="utf-8") as f:
        json.dump({"source": {"provider": "alquran.cloud", **EDITIONS},
                   "suras": suras}, f, ensure_ascii=False, indent=1)
    total = sum(len(s["ayahs"]) for s in suras)
    print(f"wrote {DEST} · {len(suras)} surahs · {total} ayahs · "
          f"{os.path.getsize(DEST)} bytes")


if __name__ == "__main__":
    main()
