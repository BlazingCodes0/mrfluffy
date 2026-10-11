# -*- coding: utf-8 -*-
"""quran.py — the Word, carried into the wire as data.

House rule, and it never bends: THE BOOK IS THE WORD OF ALLAH. It is the
greatest of sanctities, and this file holds a faithful local copy of a
published mushaf — not a paraphrase, not a summary, not a single invented
letter. The Arabic here is the Qur'an; the transliteration and the translation
are only a door for a reader who does not yet read Arabic.

Sources (queried algorithmically, then copied here byte-for-byte):
    Arabic:         alquran.cloud · edition "quran-uthmani"  (Hafs · al-rasm
                    al-'Uthmani — the script of the printed mushaf)
    Transliteration: alquran.cloud · edition "en.transliteration"
    Translation:    alquran.cloud · edition "en.sahih"  (Saheeh International)

Nothing here is depicted. Islam forbids imaging Allah, the prophets and the
companions — no such image exists or could ever be produced here. This room
holds words only, on light.
"""

SURAS = [
    {
        "number": 1,
        "name": "Al-Faatiha",
        "arabic_name": "سُورَةُ ٱلْفَاتِحَةِ",
        "translation": "The Opening",
        "meccan": True,
        "about": ("The Opening — the seven oft-repeated verses, recited in "
                  "every unit of the prayer. The Qur'an opens with it."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
             "tr": "Bismillaahir Rahmaanir Raheem",
             "en": "In the name of Allah, the Entirely Merciful, the "
                   "Especially Merciful."},
            {"n": 2, "ar": "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ",
             "tr": "Alhamdu lillaahi Rabbil 'aalameen",
             "en": "[All] praise is [due] to Allah, Lord of the worlds -"},
            {"n": 3, "ar": "ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
             "tr": "Ar-Rahmaanir-Raheem",
             "en": "The Entirely Merciful, the Especially Merciful,"},
            {"n": 4, "ar": "مَٰلِكِ يَوْمِ ٱلدِّينِ",
             "tr": "Maaliki Yawmid-Deen",
             "en": "Sovereign of the Day of Recompense."},
            {"n": 5, "ar": "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
             "tr": "Iyyaaka na'budu wa lyyaaka nasta'een",
             "en": "It is You we worship and You we ask for help."},
            {"n": 6, "ar": "ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ",
             "tr": "Ihdinas-Siraatal-Mustaqeem",
             "en": "Guide us to the straight path -"},
            {"n": 7, "ar": "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ "
                          "غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ",
             "tr": "Siraatal-lazeena an'amta 'alaihim ghayril-maghdoobi "
                   "'alaihim wa lad-daaalleen",
             "en": "The path of those upon whom You have bestowed favor, not "
                   "of those who have evoked [Your] anger or of those who are "
                   "astray."},
        ],
    },
    {
        "number": 103,
        "name": "Al-Asr",
        "arabic_name": "سُورَةُ العَصۡرِ",
        "translation": "The Declining Day",
        "meccan": True,
        "about": ("By Time — how humankind is saved, and how it is lost, "
                  "in three verses."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ وَٱلْعَصْرِ",
             "tr": "Wal' asr",
             "en": "By time,"},
            {"n": 2, "ar": "إِنَّ ٱلْإِنسَٰنَ لَفِى خُسْرٍ",
             "tr": "Innal insaana lafee khusr",
             "en": "Indeed, mankind is in loss,"},
            {"n": 3, "ar": "إِلَّا ٱلَّذِينَ ءَامَنُوا۟ وَعَمِلُوا۟ "
                          "ٱلصَّٰلِحَٰتِ وَتَوَاصَوْا۟ بِٱلْحَقِّ "
                          "وَتَوَاصَوْا۟ بِٱلصَّبْرِ",
             "tr": "Il lal lazeena aamanu wa 'amilus saali haati wa tawa saw "
                   "bil haqqi wa tawa saw bis sabr",
             "en": "Except for those who have believed and done righteous "
                   "deeds and advised each other to truth and advised each "
                   "other to patience."},
        ],
    },
    {
        "number": 108,
        "name": "Al-Kawthar",
        "arabic_name": "سُورَةُ الكَوۡثَرِ",
        "translation": "Abundance",
        "meccan": True,
        "about": ("Al-Kawthar — the abundance given; the briefest surah of "
                  "the Book, comfort against those who taunt."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ "
                          "إِنَّآ أَعْطَيْنَٰكَ ٱلْكَوْثَرَ",
             "tr": "Innaa a'taina kal kauthar",
             "en": "Indeed, We have granted you, [O Muhammad], al-Kawthar."},
            {"n": 2, "ar": "فَصَلِّ لِرَبِّكَ وَٱنْحَرْ",
             "tr": "Fa salli li rabbika wanhar",
             "en": "So pray to your Lord and sacrifice [to Him alone]."},
            {"n": 3, "ar": "إِنَّ شَانِئَكَ هُوَ ٱلْأَبْتَرُ",
             "tr": "Inna shani-aka huwal abtar",
             "en": "Indeed, your enemy is the one cut off."},
        ],
    },
    {
        "number": 112,
        "name": "Al-Ikhlaas",
        "arabic_name": "سُورَةُ الإِخۡلَاصِ",
        "translation": "Sincerity",
        "meccan": True,
        "about": ("Al-Ikhlas — the purity of faith: the oneness of Allah, "
                  "in four verses. The Prophet (peace be upon him) is "
                  "reported to have said it equals a third of the Qur'an."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ "
                          "قُلْ هُوَ ٱللَّهُ أَحَدٌ",
             "tr": "Qul huwal laahu ahad",
             "en": 'Say, "He is Allah, [who is] One,'},
            {"n": 2, "ar": "ٱللَّهُ ٱلصَّمَدُ",
             "tr": "Allah hus-samad",
             "en": "Allah, the Eternal Refuge."},
            {"n": 3, "ar": "لَمْ يَلِدْ وَلَمْ يُولَدْ",
             "tr": "Lam yalid wa lam yoolad",
             "en": "He neither begets nor is born,"},
            {"n": 4, "ar": "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ",
             "tr": "Wa lam yakul-lahu kufuwan ahad",
             "en": 'Nor is there to Him any equivalent."'},
        ],
    },
    {
        "number": 113,
        "name": "Al-Falaq",
        "arabic_name": "سُورَةُ الفَلَقِ",
        "translation": "The Dawn",
        "meccan": True,
        "about": ("Al-Falaq — with 114, one of the two refuges "
                  "(al-Mu'awwidhatan): seeking refuge with Allah from the "
                  "harm of all that He created."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ "
                          "قُلْ أَعُوذُ بِرَبِّ ٱلْفَلَقِ",
             "tr": "Qul a'uzoo bi rabbil-falaq",
             "en": 'Say, "I seek refuge in the Lord of daybreak'},
            {"n": 2, "ar": "مِن شَرِّ مَا خَلَقَ",
             "tr": "Min sharri ma khalaq",
             "en": "From the evil of that which He created"},
            {"n": 3, "ar": "وَمِن شَرِّ غَاسِقٍ إِذَا وَقَبَ",
             "tr": "Wa min sharri ghasiqin iza waqab",
             "en": "And from the evil of darkness when it settles"},
            {"n": 4, "ar": "وَمِن شَرِّ ٱلنَّفَّٰثَٰتِ فِى ٱلْعُقَدِ",
             "tr": "Wa min sharrin-naffaa-thaati fil 'uqad",
             "en": "And from the evil of the blowers in knots"},
            {"n": 5, "ar": "وَمِن شَرِّ حَاسِدٍ إِذَا حَسَدَ",
             "tr": "Wa min shar ri haasidin iza hasad",
             "en": 'And from the evil of an envier when he envies."'},
        ],
    },
    {
        "number": 114,
        "name": "An-Naas",
        "arabic_name": "سُورَةُ النَّاسِ",
        "translation": "Mankind",
        "meccan": True,
        "about": ("An-Nas — the second refuge, against the retreating "
                  "whisperer that sows into the breast of mankind."),
        "ayahs": [
            {"n": 1, "ar": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ "
                          "قُلْ أَعُوذُ بِرَبِّ ٱلنَّاسِ",
             "tr": "Qul a'uzu birabbin naas",
             "en": 'Say, "I seek refuge in the Lord of mankind,'},
            {"n": 2, "ar": "مَلِكِ ٱلنَّاسِ",
             "tr": "Malikin naas",
             "en": "The Sovereign of mankind."},
            {"n": 3, "ar": "إِلَٰهِ ٱلنَّاسِ",
             "tr": "Ilaahin naas",
             "en": "The God of mankind,"},
            {"n": 4, "ar": "مِن شَرِّ ٱلْوَسْوَاسِ ٱلْخَنَّاسِ",
             "tr": "Min sharril was waasil khannaas",
             "en": "From the evil of the retreating whisperer -"},
            {"n": 5, "ar": "ٱلَّذِى يُوَسْوِسُ فِى صُدُورِ ٱلنَّاسِ",
             "tr": "Al lazee yuwas wisu fee sudoorin naas",
             "en": "Who whispers [evil] into the breasts of mankind -"},
            {"n": 6, "ar": "مِنَ ٱلْجِنَّةِ وَٱلنَّاسِ",
             "tr": "Minal jinnati wan naas",
             "en": 'From among the jinn and mankind."'},
        ],
    },
]

SOURCES = {
    "arabic": "alquran.cloud · quran-uthmani (Hafs · Uthmani script)",
    "transliteration": "alquran.cloud · en.transliteration",
    "translation": "alquran.cloud · en.sahih (Saheeh International)",
}

# The small beginning: six short surahs a new reader can live with. The data
# structure above accepts any surah — growth is just adding chapters.
ORDER = [1, 103, 108, 112, 113, 114]


def all_suras():
    """The curated reading order, in the order a beginner reads them."""
    by_num = {s["number"]: s for s in SURAS}
    return [by_num[n] for n in ORDER if n in by_num]