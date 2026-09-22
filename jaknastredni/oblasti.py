"""Převod kódů KKOV na to, čemu rozumí uchazeč.

Kód oboru (KKOV, např. ``63-41-M/02``) nese dvě informace, které průvodce
(`jaknastredni.pruvodce`) potřebuje pro filtrování:

- **první dvojčíslí** = skupina oborů vzdělání (``63`` = Ekonomika a
  administrativa). Skupin je v pražské nabídce 27 — na to, aby si je
  uchazeč proklikal ve formuláři, jich je moc, proto je tenhle modul
  seskupuje do 11 „oblastí zájmu" (`OBLASTI`). Jedna skupina může patřit do
  víc oblastí (``34`` Polygrafie je řemeslo i média), to je záměr — filtr
  má radši nabídnout víc než uchazeči obor schovat.
- **písmeno za lomítkem a poslední dvojčíslí** = typ a délka vzdělání
  (``K/81`` = osmileté gymnázium, ``M`` = čtyřletý maturitní obor, ``H`` =
  tříletý obor s výučním listem). Z něj plyne i **ze které třídy ZŠ** se na
  obor hlásí — klíčová první otázka průvodce.

Názvy skupin odpovídají oficiální soustavě oborů vzdělání (nařízení vlády
č. 211/2010 Sb.); v databázi je ale `ciselnik` jen pro číselníky MŠMT
z rejstříku (AKDT, RAFS, …), skupiny KKOV v datech nikde nejsou, proto
jsou tady natvrdo. Ověřeno proti reálným názvům oborů v pražském snapshotu
(viz `docs/pruvodce-ux.md`, oddíl „Oblasti zájmu").
"""
from __future__ import annotations

# První dvojčíslí KKOV -> název skupiny oborů vzdělání.
SKUPINY: dict[str, str] = {
    "16": "Ekologie a ochrana životního prostředí",
    "18": "Informatické obory",
    "21": "Hornictví a hutnictví",
    "23": "Strojírenství a strojírenská výroba",
    "26": "Elektrotechnika, telekomunikační a výpočetní technika",
    "28": "Technická chemie a chemie silikátů",
    "29": "Potravinářství a potravinářská chemie",
    "31": "Textilní výroba a oděvnictví",
    "32": "Kožedělná a obuvnická výroba",
    "33": "Zpracování dřeva a výroba hudebních nástrojů",
    "34": "Polygrafie, zpracování papíru, filmu a fotografie",
    "36": "Stavebnictví, geodézie a kartografie",
    "37": "Doprava a spoje",
    "39": "Speciální a interdisciplinární obory",
    "41": "Zemědělství a lesnictví",
    "43": "Veterinářství a veterinární prevence",
    "53": "Zdravotnictví",
    "61": "Filozofie, teologie",
    "63": "Ekonomika a administrativa",
    "64": "Podnikání v oborech, odvětví",
    "65": "Gastronomie, hotelnictví a turismus",
    "66": "Obchod",
    "68": "Právo, právní a veřejnosprávní činnost",
    "69": "Osobní a provozní služby",
    "72": "Publicistika, knihovnictví a informatika",
    "74": "Tělesná kultura, tělovýchova a sport",
    "75": "Pedagogika, učitelství a sociální péče",
    "78": "Obecně odborná příprava (lycea)",
    "79": "Obecná příprava (gymnázia)",
    "82": "Umění a užité umění",
}

# Oblast zájmu (to, co se ptáme uchazeče) -> (popisek, skupiny KKOV).
# Pořadí je pořadí ve formuláři: nejdřív to, co má v Praze největší nabídku.
OBLASTI: dict[str, tuple[str, tuple[str, ...]]] = {
    "vseobecne": ("Všeobecné vzdělání (gymnázium, lyceum)", ("79", "78")),
    "it": ("IT, počítače, elektronika", ("18", "26")),
    "technika": ("Technika, strojírenství, doprava", ("23", "26", "28", "37", "39")),
    "remesla": ("Stavebnictví a řemesla", ("36", "33", "31", "32", "34", "21")),
    "ekonomika": ("Ekonomika, obchod, podnikání", ("63", "64", "66", "37")),
    "pravo": ("Právo, veřejná správa, bezpečnost", ("68",)),
    "zdravi": ("Zdravotnictví a péče o člověka", ("53", "43", "69", "74")),
    "pedagogika": ("Pedagogika a sociální práce", ("75", "61")),
    "umeni": ("Umění, design, média", ("82", "72", "34")),
    "gastro": ("Gastronomie, hotelnictví, cestovní ruch", ("65", "29")),
    "priroda": ("Příroda, zemědělství, ekologie", ("16", "41", "43", "28")),
}

# Typ vzdělání odvozený z písmene KKOV + poslední dvojčíslí.
# (kód typu) -> (popisek, ze které třídy ZŠ se hlásí, končí maturitou?)
TYPY: dict[str, tuple[str, int, bool]] = {
    "G8": ("osmileté gymnázium", 5, True),
    "G6": ("šestileté gymnázium", 7, True),
    "G4": ("čtyřleté gymnázium", 9, True),
    "LYC": ("lyceum", 9, True),
    "M": ("čtyřletý maturitní obor (SOŠ)", 9, True),
    "L0": ("maturitní obor s odborným výcvikem", 9, True),
    "L5": ("nástavbové studium (po vyučení)", 0, True),
    "H": ("tříletý obor s výučním listem", 9, False),
    "E": ("obor s výučním listem (nižší nároky)", 9, False),
    "J": ("obor bez maturity i výučního listu", 9, False),
    "C": ("praktická škola", 9, False),
    "N": ("vyšší odborná škola", 0, False),
    "P": ("konzervatoř", 5, True),
}

# Typy, které do průvodce pro žáka ZŠ nepatří (nástavby, VOŠ).
TYPY_MIMO_ZS = ("L5", "N")


def skupina(kod_kkov: str) -> str:
    """Vrátí první dvojčíslí kódu KKOV (skupinu oborů), např. ``63``."""
    return kod_kkov[:2]


def nazev_skupiny(kod_kkov: str) -> str:
    """Název skupiny oborů pro daný kód KKOV (neznámá skupina -> kód)."""
    return SKUPINY.get(skupina(kod_kkov), f"skupina {skupina(kod_kkov)}")


def oblasti_oboru(kod_kkov: str) -> tuple[str, ...]:
    """Klíče oblastí zájmu, do kterých obor spadá (může jich být víc)."""
    sk = skupina(kod_kkov)
    return tuple(k for k, (_, skupiny) in OBLASTI.items() if sk in skupiny)


def typ_oboru(kod_kkov: str) -> str | None:
    """Kód typu vzdělání (``G8``, ``M``, ``H``, …) z kódu KKOV.

    Formát KKOV je ``NN-NN-P/DD``: ``P`` je písmeno typu, ``DD`` poslední
    dvojčíslí. U gymnázií (``K``) rozlišuje délku (``81``/``61``/``41``),
    u ``L`` odlišuje obory s odborným výcvikem (``L/0x``) od nástaveb
    (``L/5x``). Vrací ``None``, pokud kód nemá očekávaný tvar.
    """
    if len(kod_kkov) < 10 or kod_kkov[6] != "-" and "/" not in kod_kkov:
        return None
    try:
        pismeno = kod_kkov.split("/")[0][-1].upper()
        dvojcisli = kod_kkov.split("/")[1][:2]
    except IndexError:
        return None
    if pismeno == "K":
        return {"81": "G8", "61": "G6", "41": "G4"}.get(dvojcisli, "G4")
    if pismeno == "L":
        return "L5" if dvojcisli.startswith("5") else "L0"
    if pismeno in ("M", "H", "E", "J", "C", "N", "P"):
        # Lyceum je maturitní obor (M) ve skupině 78 — pro uchazeče je to ale
        # jiná volba než odborná SOŠ, proto vlastní typ.
        if pismeno == "M" and skupina(kod_kkov) == "78":
            return "LYC"
        return pismeno
    return None


def popis_typu(typ: str | None) -> str:
    """Lidský popis typu vzdělání."""
    if typ is None:
        return "neznámý typ oboru"
    return TYPY.get(typ, (typ, 0, False))[0]


def trida_prihlasky(typ: str | None) -> int:
    """Ze které třídy ZŠ se na daný typ hlásí (0 = ne ze ZŠ)."""
    if typ is None:
        return 9
    return TYPY.get(typ, ("", 9, False))[1]


def s_maturitou(typ: str | None) -> bool:
    """Končí daný typ vzdělání maturitou?"""
    if typ is None:
        return False
    return TYPY.get(typ, ("", 0, False))[2]


# Sousednost pražských správních obvodů (Praha 1–10). Používá se jako hrubá
# náhrada dojezdové doby MHD, dokud není naimportované GTFS (README, zdroj 12):
# škola v sousedním obvodu se nezahazuje, jen dostane nižší skóre blízkosti.
SOUSEDNI_OBVODY: dict[str, tuple[str, ...]] = {
    "Praha 1": ("Praha 2", "Praha 5", "Praha 6", "Praha 7", "Praha 8"),
    "Praha 2": ("Praha 1", "Praha 3", "Praha 4", "Praha 5", "Praha 10"),
    "Praha 3": ("Praha 2", "Praha 8", "Praha 9", "Praha 10"),
    "Praha 4": ("Praha 2", "Praha 5", "Praha 10", "Praha 11", "Praha 12"),
    "Praha 5": ("Praha 1", "Praha 2", "Praha 4", "Praha 6"),
    "Praha 6": ("Praha 1", "Praha 5", "Praha 7"),
    "Praha 7": ("Praha 1", "Praha 6", "Praha 8"),
    "Praha 8": ("Praha 1", "Praha 3", "Praha 7", "Praha 9"),
    "Praha 9": ("Praha 3", "Praha 8", "Praha 10"),
    "Praha 10": ("Praha 2", "Praha 3", "Praha 4", "Praha 9"),
}
