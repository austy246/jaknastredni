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
    # „Humanitní" není skupina KKOV, ale je to první slovo, kterým uchazeč
    # svůj zájem popíše (ověřeno na reálné odpovědi). Skládá se z oborů,
    # kde se pracuje s jazykem, člověkem a společností — gymnázia a lycea
    # taky, protože na humanitní VŠ vedou hlavně ony.
    "humanitni": ("Humanitní obory, jazyky, společnost", ("79", "78", "68", "72", "75", "61")),
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

# Odvození typu vzdělání z osobnostních otázek místo přímé volby.
#
# Čtrnáctiletý obvykle neví, jestli chce „lyceum" nebo „čtyřletý maturitní
# obor" — tahle slova mu nic neříkají a ptát se na ně rovnou znamená nutit
# ho k rozhodnutí, kvůli kterému za průvodcem přišel. Ptáme se proto na tři
# věci, na které odpovědět umí, a typ z nich **odvodíme a ukážeme jako
# zjištění**, ne jako vstup.
#
# Každá odpověď dává každému typu skóre 0–1; výsledek je průměr přes
# zodpovězené otázky (nezodpovězené se přeskočí, nesnižují nic).
OSOBNOSTNI_OTAZKY: dict[str, tuple[str, dict[str, tuple[str, dict[str, float]]]]] = {
    "po_skole": ("Co chceš dělat, až tuhle školu doděláš?", {
        "vysoka":   ("Jít na vysokou nebo vyšší odbornou",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.6, "L0": 0.3,
                      "H": 0.05, "E": 0.05, "J": 0.05}),
        "prace":    ("Jít rovnou pracovat",
                     {"G8": 0.1, "G6": 0.1, "G4": 0.1, "LYC": 0.4, "M": 0.8, "L0": 0.9,
                      "H": 1.0, "E": 0.9, "J": 0.6}),
        "nevim":    ("Ještě nevím",
                     {"G8": 0.8, "G6": 0.8, "G4": 0.8, "LYC": 1.0, "M": 0.8, "L0": 0.6,
                      "H": 0.4, "E": 0.3, "J": 0.3}),
    }),
    "rozhodnuto": ("Víš už, čemu se chceš věnovat?", {
        "obor":     ("Vím to docela přesně",
                     {"G8": 0.3, "G6": 0.3, "G4": 0.3, "LYC": 0.6, "M": 1.0, "L0": 1.0,
                      "H": 1.0, "E": 0.9, "J": 0.6}),
        "otevreno": ("Chci si nechat otevřené dveře",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.5, "L0": 0.3,
                      "H": 0.2, "E": 0.2, "J": 0.2}),
        "nevim":    ("Nevím",
                     {"G8": 0.7, "G6": 0.7, "G4": 0.7, "LYC": 1.0, "M": 0.7, "L0": 0.5,
                      "H": 0.4, "E": 0.4, "J": 0.4}),
    }),
    "praxe": ("Jak moc chceš dělat věci rukama a chodit na praxi?", {
        "hodne":    ("Hodně — teorie u tabule mě nebaví",
                     {"G8": 0.05, "G6": 0.05, "G4": 0.05, "LYC": 0.3, "M": 0.6, "L0": 1.0,
                      "H": 1.0, "E": 1.0, "J": 0.8}),
        "stredne":  ("Něco od obojího",
                     {"G8": 0.5, "G6": 0.5, "G4": 0.5, "LYC": 0.9, "M": 1.0, "L0": 0.8,
                      "H": 0.5, "E": 0.4, "J": 0.4}),
        "teorie":   ("Radši se učím a přemýšlím",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.6, "L0": 0.2,
                      "H": 0.1, "E": 0.1, "J": 0.1}),
    }),
}


def preference_typu(odpovedi: dict[str, str | None]) -> dict[str, float]:
    """Z osobnostních odpovědí udělá skóre 0–1 pro každý typ vzdělání.

    `odpovedi` mapuje klíč otázky (`po_skole`, `rozhodnuto`, `praxe`) na
    zvolenou variantu; None nebo chybějící klíč se přeskočí. Když uchazeč
    neodpoví nic, vrátí pro všechny typy 0,5 — tedy „nevím, neřaď podle
    toho", ne „nic ti nesedí".
    """
    tabulky = [
        varianty[odpoved][1]
        for klic, (_popis, varianty) in OSOBNOSTNI_OTAZKY.items()
        if (odpoved := odpovedi.get(klic)) in varianty
    ]
    typy = [t for t in TYPY if t not in TYPY_MIMO_ZS]
    if not tabulky:
        return {t: 0.5 for t in typy}
    return {t: sum(tab.get(t, 0.3) for tab in tabulky) / len(tabulky) for t in typy}


def doporucene_typy(odpovedi: dict[str, str | None], trida: int = 9,
                    prah: float = 0.75) -> list[str]:
    """Typy, které podle odpovědí sedí nejlíp — pro větu „vyšlo ti…".

    Filtruje na typy dostupné z dané třídy a vrací je seřazené od nejlepší
    shody; `prah` je podíl nejvyššího skóre, pod který se už typ neuvádí.
    """
    skore = {t: s for t, s in preference_typu(odpovedi).items()
             if trida_prihlasky(t) == trida}
    if not skore:
        return []
    nejlepsi = max(skore.values())
    return [t for t, s in sorted(skore.items(), key=lambda x: -x[1])
            if s >= nejlepsi * prah]


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


# Pražské městské části (Praha 1–22) -> správní obvod, pod který spadají.
# V datech MŠMT (`organizace.obvod_prahy`, `misto_vyuky.obvod_prahy`) je jen
# deset správních obvodů Praha 1–10, jenže lidé se identifikují se svou
# **městskou částí** („bydlíme v Praze 12"). Bez tohohle překladu by uchazeč
# z Modřan svoji volbu ve formuláři vůbec nenašel. Ověřeno proti datům:
# školy v Modřanech a na Kamýku mají v rejstříku `obvod_prahy = 'Praha 4'`.
MC_NA_OBVOD: dict[str, str] = {
    **{f"Praha {i}": f"Praha {i}" for i in range(1, 11)},
    "Praha 11": "Praha 4",    # Chodov, Háje
    "Praha 12": "Praha 4",    # Modřany, Kamýk, Komořany
    "Praha 13": "Praha 5",    # Stodůlky, Nové Butovice
    "Praha 14": "Praha 9",    # Černý Most, Kyje
    "Praha 15": "Praha 10",   # Hostivař, Horní Měcholupy
    "Praha 16": "Praha 5",    # Radotín
    "Praha 17": "Praha 6",    # Řepy
    "Praha 18": "Praha 9",    # Letňany
    "Praha 19": "Praha 9",    # Kbely
    "Praha 20": "Praha 9",    # Horní Počernice
    "Praha 21": "Praha 9",    # Újezd nad Lesy
    "Praha 22": "Praha 10",   # Uhříněves
}


def obvod(mestska_cast: str) -> str:
    """Správní obvod pro městskou část; neznámou hodnotu vrátí beze změny."""
    return MC_NA_OBVOD.get(mestska_cast.strip(), mestska_cast.strip())


# Sousednost pražských správních obvodů (Praha 1–10). Používá se jako hrubá
# náhrada dojezdové doby MHD, dokud není naimportované GTFS (README, zdroj 12):
# škola v sousedním obvodu se nezahazuje, jen dostane nižší skóre blízkosti.
SOUSEDNI_OBVODY: dict[str, tuple[str, ...]] = {
    "Praha 1": ("Praha 2", "Praha 5", "Praha 6", "Praha 7", "Praha 8"),
    "Praha 2": ("Praha 1", "Praha 3", "Praha 4", "Praha 5", "Praha 10"),
    "Praha 3": ("Praha 2", "Praha 8", "Praha 9", "Praha 10"),
    "Praha 4": ("Praha 2", "Praha 5", "Praha 9", "Praha 10"),
    "Praha 5": ("Praha 1", "Praha 2", "Praha 4", "Praha 6"),
    "Praha 6": ("Praha 1", "Praha 5", "Praha 7"),
    "Praha 7": ("Praha 1", "Praha 6", "Praha 8"),
    "Praha 8": ("Praha 1", "Praha 3", "Praha 7", "Praha 9"),
    "Praha 9": ("Praha 3", "Praha 8", "Praha 10"),
    "Praha 10": ("Praha 2", "Praha 3", "Praha 4", "Praha 9"),
}
