"""Průvodce výběrem střední školy — z odpovědí uchazeče udělá pořadí nabídek.

Návrh UX (proč zrovna tyhle otázky, jak se počítá skóre, co se uživateli
ukazuje a proč) je v [`docs/pruvodce-ux.md`](../docs/pruvodce-ux.md).
Tenhle modul je výpočetní jádro: čte hotovou databázi (`data/jaknastredni.db`,
viz README „Rychlý start"), nic nestahuje a do databáze nezapisuje.

Základní jednotka není škola, ale **nabídka** = škola × obor (IZO × KKOV).
Na jedné škole se dá přihláška podat na konkrétní obor a čísla (kapacita,
poměr přihlášek, hranice přijetí) jsou oborová, ne školní — kdybychom
řadili školy, průměrovali bychom dohromady gymnázium a učňovský obor.
Výsledek se pak zobrazuje jako 5 nabídek, protože přihlášky se podávají na
obory, ne na školy.

Tři kroky:

1. `nacti_nabidky()` — poskládá z databáze seznam nabídek s metrikami
   (hranice přijetí 2024–2026, poměr přihlášek, školné, maturity, inspekce).
2. `ohodnot()` — tvrdé filtry (ze které třídy se hlásím, typ vzdělání,
   oblast zájmu, dostupné školné, jazyk) a pak průhledné vážené skóre.
3. `portfolio()` — z ohodnocených nabídek vybere trojici na přihlášky
   (sen / realistická / jistota), protože přihlášky se podávají tři.

Každé číslo, které průvodce ukáže, musí jít dohledat ke zdroji — proto má
`Vysledek` pole `duvody` (proč se nabídka objevila) i `varovani` (co data
neříkají). Žádná „proprietární skóre obtížnosti" jako u agregátorů
(README, zdroj 6) — vzorec je v dokumentaci a v `SLOZKY_SKORE`.

Použití:
    python -m jaknastredni.pruvodce --db data/jaknastredni.db          # interaktivně
    python -m jaknastredni.pruvodce --db data/jaknastredni.db --profil profil.json
    python -m jaknastredni.pruvodce --db data/jaknastredni.db --profil profil.json --json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

from . import db, oblasti

log = logging.getLogger(__name__)

# Roky JPZ v novém formátu (tabulka prijimaci_rizeni), od nejnovějšího.
# Váha při odhadu hranice přijetí: nejnovější rok váží nejvíc.
ROKY_JPZ: dict[int, float] = {2026: 3.0, 2025: 2.0, 2024: 1.0}

# Meziroční rozptyl hranice přijetí (min. % skór přijatých, škála 0–200)
# spočítaný z dat: směrodatná odchylka meziroční změny je 20,4 bodu,
# medián |změny| 12 bodů, p90 32 bodů (598 dvojic škola×obor 2024→2025 a
# 2025→2026). Odhad šance proto nikdy nepoužívá menší nejistotu než tohle —
# viz docs/pruvodce-ux.md, oddíl „Šance na přijetí".
SIGMA_ZAKLAD = 18.0
SIGMA_JEDEN_ROK = 24.0   # jen jeden rok dat = ještě větší nejistota
SIGMA_MAX = 32.0

# Váhy složek skóre. Priorita zvolená uchazečem svou složku zdvojnásobí
# (viz PRIORITY a _vahy_profilu).
SLOZKY_SKORE: dict[str, float] = {
    "zajem": 3.0,           # shoda oboru s tím, co uchazeče zajímá
    "dosazitelnost": 2.5,   # reálnost přijetí podle očekávaného skóre
    "kvalita": 1.5,         # maturitní výsledky školy, posun žáků, inspekce
    "blizkost": 1.5,        # městská část
    "cena": 1.0,            # školné
    "prostredi": 1.0,       # velikost školy, jazyky, vybavení dle priorit
}

# Priority, ze kterých uchazeč vybírá max. 3 (klíč -> (popisek, složka skóre)).
PRIORITY: dict[str, tuple[str, str]] = {
    "jistota": ("Jistota, že mě vezmou", "dosazitelnost"),
    "kvalita": ("Kvalita výuky a výsledky maturit", "kvalita"),
    "blizkost": ("Ať to mám blízko", "blizkost"),
    "cena": ("Co nejnižší školné", "cena"),
    "jazyky": ("Hodně jazyků", "prostredi"),
    "maly_kolektiv": ("Menší škola, osobní přístup", "prostredi"),
    "sport": ("Sportovní zázemí", "prostredi"),
    "umeni": ("Umělecké a kreativní zaměření", "prostredi"),
    "praxe": ("Praxe a rychlé uplatnění", "prostredi"),
}

# Školy zřízené pro žáky se zdravotním postižením se do běžného výsledku
# nehodí — pro uchazeče bez odpovídajícího doporučení ŠPZ nejsou volbou a
# v pětici zabírají místo. Databáze žádný příznak „speciální škola" nemá
# (rejstřík MŠMT rozlišuje jen `druh`), proto se poznají podle názvu; je to
# heuristika, ale na pražských datech přesná (6 z 238 organizací, ručně
# zkontrolováno). Uchazeč si je může vyžádat přes `Profil.specialni_potreby`.
VZOR_SKOLY_PRO_ZP = re.compile(
    r"pro (sluchově|zrakově|tělesně|mentálně) postižené"
    r"|škola speciální|speciální škola"
    r"|pro žáky se speciálními",
    re.IGNORECASE,
)

# Pásma portfolia přihlášek (šance na přijetí). Tři přihlášky = tři role.
PASMA_PORTFOLIA: dict[str, tuple[float, float]] = {
    "sen": (0.10, 0.45),
    "realisticka": (0.45, 0.82),
    "jistota": (0.82, 1.01),
}


# --------------------------------------------------------------------------
# Datové struktury
# --------------------------------------------------------------------------

@dataclass
class Profil:
    """Odpovědi uchazeče. Všechno kromě `trida` je volitelné."""

    trida: int = 9                       # ze které třídy ZŠ se hlásí (5/7/9)
    typy: list[str] = field(default_factory=list)      # kódy z oblasti.TYPY
    oblasti_zajmu: list[str] = field(default_factory=list)  # klíče oblasti.OBLASTI
    obvody: list[str] = field(default_factory=list)    # 'Praha 6', …
    skor_cj: float | None = None         # očekávaný % skór ČJ (0–100)
    skor_ma: float | None = None         # očekávaný % skór MA (0–100)
    skolne_max: int | None = None        # Kč/rok; None = nerozhoduje, 0 = jen bezplatné
    jazyk: str | None = None             # požadovaný jazyk ('N', 'Š', 'F', …)
    prospech: float | None = None        # průměr známek na výstupním vysvědčení ZŠ
    specialni_potreby: bool = False      # zahrnout školy zřízené pro žáky se ZP
    priority: list[str] = field(default_factory=list)  # klíče PRIORITY, max 3

    @property
    def skor(self) -> float | None:
        """Očekávaný součet % skóru ČJ + MA (škála 0–200, jako CERMAT)."""
        if self.skor_cj is None or self.skor_ma is None:
            return None
        return self.skor_cj + self.skor_ma

    @classmethod
    def z_json(cls, data: dict[str, Any]) -> "Profil":
        neznama = set(data) - set(cls.__dataclass_fields__)
        if neznama:
            raise ValueError(f"neznámá pole profilu: {sorted(neznama)}")
        return cls(**data)


@dataclass
class Nabidka:
    """Jedna nabídka = škola (IZO) × obor (KKOV), se vším, co o ní víme."""

    izo: str
    redizo: str
    skola: str
    organizace: str
    kod_kkov: str
    obor: str
    typ: str | None                      # G8/G6/G4/LYC/M/L0/H/…
    trida_prihlasky: int
    obvody: tuple[str, ...]              # sídlo + místa výuky
    adresa: str
    zrizovatel_verejny: bool
    jen_pro_zp: bool = False             # škola zřízená pro žáky se zdravotním postižením
    # Přijímací řízení (CERMAT JPZ 2024+, 1. kolo, agregace přes zaměření)
    hranice: dict[int, float] = field(default_factory=dict)   # rok -> min. % skór přijatých
    prumer_prijatych: dict[int, float] = field(default_factory=dict)
    poptavka: dict[int, float] = field(default_factory=dict)  # rok -> přihlášky/kapacita
    kapacita: int | None = None          # z CERMAT = kolik se letos otevírá míst
    prihlasky: int | None = None
    prijati: int | None = None
    # Pozn.: `obor.kapacita` z rejstříku MŠMT se tu záměrně nepoužívá — je to
    # nejvyšší povolený počet žáků oboru přes všechny ročníky (u čtyřletého
    # oboru zhruba 4× roční nábor), ne počet míst pro letošní přijímačky.
    zamereni: tuple[str, ...] = ()
    # infoabsolvent.cz / Atlas školství (tabulka web_profil)
    skolne: int | None = None
    plan_prijmout: int | None = None
    loni_prihlaseni: int | None = None
    loni_prijati: int | None = None       # jen Atlas; infoabsolvent má plán, ne přijaté
    doporuceny_prospech: float | None = None   # jen Atlas
    lekarska_prohlidka: bool | None = None     # jen Atlas: PLP u oboru
    zdroje_profilu: tuple[str, ...] = ()
    jazyky: str | None = None
    pocet_jazyku: int | None = None
    dod: str | None = None
    prihlasky_do: str | None = None
    dalsi_kriteria: str | None = None
    talentova_zkouska: bool = False
    skolni_zkousky: tuple[str, ...] = ()   # ústní/písemná/praktická nad rámec JPZ
    velikost_skoly: int | None = None    # střed pásma z infoabsolventu
    vybaveni: str | None = None
    # Kvalita (CERMAT MZ, ČŠI)
    maturita_uspesnost: float | None = None   # podíl úspěšných (%), průměr 3 let
    maturita_percentil: float | None = None   # průměrný percentil ČJ, poslední rok
    maturita_rok: int | None = None
    posun: float | None = None                # percentil maturity − percentil JPZ o 4 roky dřív
    posun_roky: tuple[int, int] | None = None
    inspekce_datum: str | None = None
    inspekce_url: str | None = None
    www: str | None = None

    @property
    def nazev(self) -> str:
        """Název, pod kterým školu uchazeč zná (organizace je ten „oficiální")."""
        return self.organizace

    @property
    def typ_popis(self) -> str:
        return oblasti.popis_typu(self.typ)


@dataclass
class Vysledek:
    """Ohodnocená nabídka — co se zobrazí na kartě."""

    nabidka: Nabidka
    skore: float
    slozky: dict[str, float]
    sance: float | None
    sance_zdroj: str
    duvody: list[str]
    varovani: list[str]

    def do_dictu(self) -> dict[str, Any]:
        d = asdict(self.nabidka)
        d["skore"] = round(self.skore, 1)
        d["slozky"] = {k: round(v, 3) for k, v in self.slozky.items()}
        d["sance"] = None if self.sance is None else round(self.sance, 3)
        d["sance_zdroj"] = self.sance_zdroj
        d["duvody"] = self.duvody
        d["varovani"] = self.varovani
        return d


# --------------------------------------------------------------------------
# Načtení nabídek z databáze
# --------------------------------------------------------------------------

def nacti_nabidky(conn: sqlite3.Connection) -> list[Nabidka]:
    """Poskládá z databáze všechny denní nabídky pražských SŠ s metrikami."""
    conn.row_factory = sqlite3.Row
    nabidky: dict[tuple[str, str], Nabidka] = {}

    obvody_izo = _obvody_podle_izo(conn)
    for r in conn.execute(
        """
        SELECT b.izo, s.redizo, s.nazev AS skola, o.nazev AS organizace,
               b.kod_kkov, b.nazev AS obor,
               o.obvod_prahy, o.ulice, o.cislo_domovni, o.cislo_orientacni,
               o.typ_zrizovatele
          FROM obor b
          JOIN skola s ON s.izo = b.izo
          JOIN organizace o ON o.redizo = s.redizo
         WHERE s.druh IN ('C00', 'E00')
           AND b.dobihajici = 0
           AND (b.forma = '10' OR b.forma IS NULL)
        """
    ):
        typ = oblasti.typ_oboru(r["kod_kkov"])
        if typ in oblasti.TYPY_MIMO_ZS:
            continue        # nástavby a VOŠ nejsou pro žáka ZŠ
        klic = (r["izo"], r["kod_kkov"])
        if klic in nabidky:
            continue        # tentýž obor ve víc délkách/jazycích = jedna nabídka
        nabidky[klic] = Nabidka(
            izo=r["izo"],
            redizo=r["redizo"],
            skola=r["skola"],
            organizace=r["organizace"],
            kod_kkov=r["kod_kkov"],
            obor=r["obor"],
            typ=typ,
            trida_prihlasky=oblasti.trida_prihlasky(typ),
            obvody=obvody_izo.get(r["izo"], ()) or ((r["obvod_prahy"],) if r["obvod_prahy"] else ()),
            adresa=_adresa(r),
            zrizovatel_verejny=str(r["typ_zrizovatele"] or "") in ("1", "2", "3", "7"),
            jen_pro_zp=bool(VZOR_SKOLY_PRO_ZP.search(r["organizace"] or "")),
        )

    _doplnit_prijimacky(conn, nabidky)
    _doplnit_web_profil(conn, nabidky)
    _doplnit_kvalitu(conn, nabidky)
    return list(nabidky.values())


def _adresa(r: sqlite3.Row) -> str:
    cislo = "/".join(str(x) for x in (r["cislo_domovni"], r["cislo_orientacni"]) if x)
    return " ".join(x for x in (r["ulice"], cislo) if x) or (r["obvod_prahy"] or "")


def _obvody_podle_izo(conn: sqlite3.Connection) -> dict[str, tuple[str, ...]]:
    """Všechny městské části, kde škola skutečně učí (sídlo + místa výuky).

    50 pražských SŠ učí v jiném obvodu, než kde sídlí právnická osoba —
    pro „ať to mám blízko" je rozhodující místo výuky, ne sídlo.
    """
    out: dict[str, set[str]] = {}
    for r in conn.execute(
        """
        SELECT s.izo, COALESCE(m.obvod_prahy, o.obvod_prahy) AS obvod
          FROM skola s
          JOIN organizace o ON o.redizo = s.redizo
     LEFT JOIN misto_vyuky m ON m.izo = s.izo
         WHERE s.druh IN ('C00', 'E00')
        """
    ):
        if r["obvod"]:
            out.setdefault(r["izo"], set()).add(r["obvod"])
    return {k: tuple(sorted(v)) for k, v in out.items()}


def _doplnit_prijimacky(conn: sqlite3.Connection, nabidky: dict[tuple[str, str], Nabidka]) -> None:
    """Metriky z CERMAT JPZ 2024+ (1. kolo), agregované přes zaměření oboru.

    Jedna nabídka (IZO × KKOV) může mít v datech víc řádků (zaměření, délky,
    jazyky studia — viz `docs/datovy-model.md`, tabulka `prijimaci_rizeni`).
    Hranice přijetí se přes ně počítá **váženým průměrem podle počtu
    přijatých**, ne minimem: minimum by bralo nejsnáze dostupné zaměření a
    šanci systematicky nadhodnocovalo. Jednotlivá zaměření se přitom pamatují
    v `Nabidka.zamereni`, aby šla zobrazit na kartě.
    """
    # (rok -> [součet hodnot × váha, součet vah]) pro každou agregovanou metriku
    agregace: dict[tuple[str, str], dict[str, dict[int, list[float]]]] = {}
    posledni_rok = max(ROKY_JPZ)

    for r in conn.execute(
        """
        SELECT p.izo, p.kod_kkov, p.rok, p.zamereni_oboru,
               p.kapacita, p.prihlasky_celkem, p.prijati, p.index_poptavky,
               p.skor_prijati_min_cjma, p.skor_prijati_prumer_cjma
          FROM prijimaci_rizeni p
         WHERE p.kolo = 1
        """
    ):
        klic = (r["izo"], r["kod_kkov"])
        nab = nabidky.get(klic)
        if nab is None:
            continue
        rok = r["rok"]
        a = agregace.setdefault(klic, {"hranice": {}, "prumer": {}, "poptavka": {}})
        # Váhou je počet přijatých (u poptávky kapacita) — zaměření, kam se
        # dostalo 90 lidí, má na hranici školy větší vliv než to s 8 přijatými.
        vaha_prijati = float(max(r["prijati"] or 0, 1))
        vaha_kapacita = float(max(r["kapacita"] or 0, 1))
        _pricti_vazene(a["hranice"], rok, r["skor_prijati_min_cjma"], vaha_prijati)
        _pricti_vazene(a["prumer"], rok, r["skor_prijati_prumer_cjma"], vaha_prijati)
        _pricti_vazene(a["poptavka"], rok, r["index_poptavky"], vaha_kapacita)
        if rok == posledni_rok:
            if r["zamereni_oboru"]:
                nab.zamereni = tuple(sorted(set(nab.zamereni) | {r["zamereni_oboru"]}))
            nab.kapacita = _secti(nab.kapacita, r["kapacita"])
            nab.prihlasky = _secti(nab.prihlasky, r["prihlasky_celkem"])
            nab.prijati = _secti(nab.prijati, r["prijati"])

    for klic, a in agregace.items():
        nab = nabidky[klic]
        nab.hranice = _dokonci_vazene(a["hranice"])
        nab.prumer_prijatych = _dokonci_vazene(a["prumer"])
        nab.poptavka = _dokonci_vazene(a["poptavka"])


def _secti(soucasne: int | None, pridat: int | None) -> int | None:
    if pridat is None:
        return soucasne
    return (soucasne or 0) + pridat


def _pricti_vazene(kam: dict[int, list[float]], rok: int, hodnota: float | None, vaha: float) -> None:
    if hodnota is None:
        return
    polozka = kam.setdefault(rok, [0.0, 0.0])
    polozka[0] += hodnota * vaha
    polozka[1] += vaha


def _dokonci_vazene(kam: dict[int, list[float]]) -> dict[int, float]:
    return {rok: soucet / vahy for rok, (soucet, vahy) in kam.items() if vahy}


# Pořadí zdrojů v tabulce `web_profil`: co načte dřívější zdroj, pozdější už
# nepřepíše (jen doplní, co chybí). infoabsolvent je první, protože jeho
# oborová tabulka je nejpodrobnější (README, zdroj 5); Atlas školství doplňuje
# pole, která infoabsolvent nemá vůbec — doporučený prospěch a **skutečný**
# počet loni přijatých (infoabsolvent má jen plán, README, zdroj 4).
PORADI_ZDROJU: tuple[str, ...] = ("infoabsolvent", "atlas")


def _doplnit_web_profil(conn: sqlite3.Connection, nabidky: dict[tuple[str, str], Nabidka]) -> None:
    """Školné, plán/skutečnost přijetí, jazyky, DOD a kritéria z `web_profil`.

    Bere **všechny** zdroje v tabulce, ne jen infoabsolvent: každý zdroj se
    načte v posledním staženém snapshotu a doplní jen to, co zatím chybí
    (pořadí v `PORADI_ZDROJU`). Když Atlas v databázi není, je to no-op —
    průvodce běží dál jen nad infoabsolventem.
    """
    podle_redizo: dict[str, list[Nabidka]] = {}
    for nab in nabidky.values():
        podle_redizo.setdefault(nab.redizo, []).append(nab)

    # Pořadí zdrojů musí určit SQL, ne náhoda — „vyhrává první zdroj" jinak
    # nedává smysl. Neznámý zdroj (nový scraper) se zařadí nakonec.
    poradi = " ".join(f"WHEN '{z}' THEN {i}" for i, z in enumerate(PORADI_ZDROJU))
    for r in conn.execute(
        f"""
        SELECT w.zdroj, w.redizo, w.data
          FROM web_profil w
          JOIN (SELECT redizo, zdroj, MAX(stazeno) AS stazeno
                  FROM web_profil GROUP BY redizo, zdroj) n
            ON n.redizo = w.redizo AND n.zdroj = w.zdroj AND n.stazeno = w.stazeno
         ORDER BY CASE w.zdroj {poradi} ELSE {len(PORADI_ZDROJU)} END
        """
    ):
        cilove = podle_redizo.get(r["redizo"])
        if not cilove:
            continue
        data = json.loads(r["data"])
        for nab in cilove:
            if r["zdroj"] not in nab.zdroje_profilu:
                nab.zdroje_profilu = (*nab.zdroje_profilu, r["zdroj"])
            nab.velikost_skoly = nab.velikost_skoly or _velikost_skoly(data.get("velikost_skoly"))
            nab.vybaveni = nab.vybaveni or data.get("vybaveni_a_nabidka")
            nab.dod = nab.dod or _prvni(data, "den_otevrenych_dveri", "dny_otevrenych_dveri")
            nab.www = nab.www or data.get("www")
            nab.jazyky = nab.jazyky or data.get("cizi_jazyky")
        for o in data.get("obory", []):
            # Atlas u oboru formu studia neuvádí vůbec (nemá pro ni sloupec),
            # infoabsolvent ano — chybějící hodnota proto projde. Spojovacím
            # klíčem je KKOV; u Atlasu může být None (obor bez uvedeného kódu),
            # pak se prostě nespáruje.
            if (o.get("forma_studia") or "").lower() not in ("denní", "denni", ""):
                continue
            for nab in cilove:
                if nab.kod_kkov != o.get("kod_kkov"):
                    continue
                _doplnit_obor(nab, o)


def _prvni(data: dict[str, Any], *klice: str) -> Any:
    """První neprázdná hodnota z uvedených klíčů.

    Každý scraper pojmenovává svoje pole podle toho, jak se jmenují na jeho
    webu — infoabsolvent má `den_otevrenych_dveri` a `letos_plan_prijmout`,
    Atlas `dny_otevrenych_dveri` a `planovany_pocet_prijmout`. Přejmenovávat
    je ve scraperech by rozbilo vazbu na zdroj, takže se aliasy řeší až tady.
    """
    for k in klice:
        hodnota = data.get(k)
        if hodnota not in (None, ""):
            return hodnota
    return None


def _doplnit_obor(nab: Nabidka, o: dict[str, Any]) -> None:
    """Přenese oborová pole z JSON blobu `web_profil` do nabídky.

    Pole `loni_prijati` (skutečný počet přijatých) a `doporuceny_prospech` má
    jen Atlas školství, `pocet_povinnych_jazyku` a rozepsané složky přijímacího
    řízení (`prijimaci_rizeni`) jen infoabsolvent — chybějící klíč zůstane
    None. Nic se nepřepisuje: vyhrává první zdroj, který hodnotu měl.
    """
    if nab.skolne is None:
        nab.skolne = o.get("skolne_rocne")
    nab.plan_prijmout = nab.plan_prijmout or _prvni(
        o, "letos_plan_prijmout", "planovany_pocet_prijmout"
    )
    nab.loni_prihlaseni = nab.loni_prihlaseni or o.get("loni_prihlaseni")
    nab.loni_prijati = nab.loni_prijati or o.get("loni_prijati")
    nab.pocet_jazyku = nab.pocet_jazyku or o.get("pocet_povinnych_jazyku")
    nab.jazyky = o.get("vyucovane_jazyky") or nab.jazyky
    if nab.doporuceny_prospech is None:
        nab.doporuceny_prospech = _prospech(o.get("doporuceny_prospech"))
    if nab.lekarska_prohlidka is None:
        nab.lekarska_prohlidka = o.get("plp")
    pr = o.get("prijimaci_rizeni") or {}
    nab.prihlasky_do = nab.prihlasky_do or pr.get("prihlasky_podejte_do")
    nab.dalsi_kriteria = nab.dalsi_kriteria or pr.get("jina_kriteria_prijimani")
    if _kona_se(pr.get("talentova_zkouska")):
        nab.talentova_zkouska = True
    zkousky = {
        "ústní zkouška": pr.get("ustni_zkouska"),
        "písemná zkouška": pr.get("pisemna_zkouska"),
        "praktická zkouška": pr.get("prakticka_zkouska"),
    }
    nab.skolni_zkousky = nab.skolni_zkousky or tuple(
        f"{nazev} ({popis})" for nazev, popis in zkousky.items() if _kona_se(popis)
    )


def _kona_se(hodnota: Any) -> bool:
    """Koná se daná zkouška?

    Pozor na past scrapovaných dat: infoabsolvent do políčka píše doslova
    ``"nekoná se"``, což je neprázdný — tedy pravdivý — řetězec. Pouhé
    ``if pr.get("talentova_zkouska")`` by talentovku přiřklo skoro každému
    oboru (549 ze 743 řádků má přesně tuhle hodnotu).
    """
    if not hodnota:
        return False
    return "nekoná se" not in str(hodnota).lower()


def _prospech(hodnota: Any) -> float | None:
    """Doporučený průměrný prospěch z Atlasu — číslo, nebo text typu „do 2,0"."""
    if hodnota is None:
        return None
    if isinstance(hodnota, (int, float)):
        return float(hodnota)
    m = re.search(r"(\d+[.,]?\d*)", str(hodnota))
    return float(m.group(1).replace(",", ".")) if m else None


def _velikost_skoly(text: str | None) -> int | None:
    """Ze `SŠ 251 - 300 žáků` udělá střed pásma (275). Neuvedeno -> None."""
    if not text:
        return None
    m = re.search(r"SŠ\s*([\d\s]+)\s*[-–]\s*([\d\s]+)", text)
    if not m:
        return None
    try:
        od = int(m.group(1).replace(" ", ""))
        do = int(m.group(2).replace(" ", ""))
    except ValueError:
        return None
    return (od + do) // 2


def _doplnit_kvalitu(conn: sqlite3.Connection, nabidky: dict[tuple[str, str], Nabidka]) -> None:
    """Maturitní výsledky (CERMAT MZ), posun žáků a poslední inspekce ČŠI.

    Maturita i inspekce jsou v datech na úrovni **organizace (REDIZO)**, ne
    oboru — CERMAT u maturity IZO ani KKOV neuvádí (README, zdroj 2). Čísla
    tedy platí za celou školu a na kartě se tak i popisují.
    """
    podle_redizo: dict[str, list[Nabidka]] = {}
    for nab in nabidky.values():
        podle_redizo.setdefault(nab.redizo, []).append(nab)

    # Úspěšnost = průměr posledních 3 ročníků (jeden slabý ročník ještě nic
    # neznamená, zvlášť u malých škol).
    uspesnost: dict[str, list[float]] = {}
    for r in conn.execute(
        """
        SELECT redizo, rok, podil_uspesnych
          FROM maturita
         WHERE obdobi = 'jap' AND smo16 = 'CELKEM' AND predmet = 'CELKEM'
           AND podil_uspesnych IS NOT NULL
           AND rok >= (SELECT MAX(rok) - 2 FROM maturita)
        """
    ):
        uspesnost.setdefault(r["redizo"], []).append(r["podil_uspesnych"])

    percentil: dict[str, tuple[int, float]] = {}
    for r in conn.execute(
        """
        SELECT redizo, rok, prumerny_percentil
          FROM maturita
         WHERE obdobi = 'jap' AND smo16 = 'CELKEM' AND predmet = 'CJ'
           AND prumerny_percentil IS NOT NULL
         ORDER BY rok
        """
    ):
        percentil[r["redizo"]] = (r["rok"], r["prumerny_percentil"])

    # Posun: percentil maturity v roce Y proti percentilu JPZ téže školy v roce
    # Y−4 (tedy zhruba tentýž ročník na vstupu a na výstupu). Hrubý ukazatel
    # „přidané hodnoty" — školní úroveň, míchá obory, viz docs/pruvodce-ux.md.
    posun: dict[str, tuple[float, int, int]] = {}
    for r in conn.execute(
        """
        SELECT j.redizo, j.rok AS rok_jpz, m.rok AS rok_mz,
               m.prumerny_percentil - AVG(j.prumerny_percentil_cj) AS posun
          FROM jpz_skupina j
          JOIN maturita m ON m.redizo = j.redizo AND m.rok = j.rok + 4
           AND m.obdobi = 'jap' AND m.smo16 = 'CELKEM' AND m.predmet = 'CJ'
           AND m.prumerny_percentil IS NOT NULL
         WHERE j.prumerny_percentil_cj IS NOT NULL AND j.konali_cj >= 15
         GROUP BY j.redizo, j.rok
         ORDER BY j.rok
        """
    ):
        posun[r["redizo"]] = (r["posun"], r["rok_jpz"], r["rok_mz"])

    inspekce: dict[str, tuple[str, str | None]] = {}
    for r in conn.execute(
        "SELECT redizo, MAX(datum_od) AS datum, portal_url FROM inspekce GROUP BY redizo"
    ):
        inspekce[r["redizo"]] = (r["datum"], r["portal_url"])

    for redizo, cilove in podle_redizo.items():
        for nab in cilove:
            if redizo in uspesnost:
                nab.maturita_uspesnost = statistics.mean(uspesnost[redizo])
            if redizo in percentil:
                nab.maturita_rok, nab.maturita_percentil = percentil[redizo]
            if redizo in posun:
                p, rok_jpz, rok_mz = posun[redizo]
                nab.posun, nab.posun_roky = p, (rok_jpz, rok_mz)
            if redizo in inspekce:
                nab.inspekce_datum, nab.inspekce_url = inspekce[redizo]


# --------------------------------------------------------------------------
# Šance na přijetí
# --------------------------------------------------------------------------

def odhad_hranice(nab: Nabidka) -> tuple[float, float] | None:
    """Očekávaná hranice přijetí pro příští rok a její nejistota (sigma).

    Vážený průměr hranic za 2024–2026 (nejnovější rok váží 3×, viz `ROKY_JPZ`).
    Sigma vychází z meziročního rozptylu naměřeného v datech (`SIGMA_ZAKLAD`);
    u škol, kde se hranice mezi roky hodně hýbe, se zvětší na skutečné rozpětí.
    Vrací None, když škola hranici v žádném roce nevykázala.
    """
    body = {rok: h for rok, h in nab.hranice.items() if rok in ROKY_JPZ}
    if not body:
        return None
    vahy = sum(ROKY_JPZ[rok] for rok in body)
    stred = sum(h * ROKY_JPZ[rok] for rok, h in body.items()) / vahy
    if len(body) == 1:
        return stred, SIGMA_JEDEN_ROK
    rozpeti = max(body.values()) - min(body.values())
    return stred, min(max(SIGMA_ZAKLAD, rozpeti), SIGMA_MAX)


def sance_prijeti(nab: Nabidka, skor: float | None) -> tuple[float | None, str]:
    """Odhad pravděpodobnosti přijetí (0–1) a slovní zdroj odhadu.

    Tři úrovně podle toho, co o nabídce víme:

    1. **Známá hranice přijetí** (min. % skór posledního přijatého, CERMAT
       2024+): normální rozdělení kolem očekávané hranice — jak moc je
       uchazečův skór nad/pod ní v poměru k meziročnímu rozptylu.
    2. **Jen poměr přihlášek ku kapacitě** (`index_poptavky`): hrubý odhad
       z pásem, posunutý podle toho, jak silný uchazeč je proti průměru.
    3. **Nic z toho** (typicky učňovské obory bez JPZ): None — karta pak
       ukáže „data chybí", ne vymyšlené procento.

    Odhad nikdy nejde na 0 % ani 100 %: škola si přidává vlastní kritéria
    (prospěch, talentovka, pohovor), která v datech nejsou.
    """
    odhad = odhad_hranice(nab)
    if odhad is not None and skor is not None:
        stred, sigma = odhad
        p = _normalni_cdf((skor - stred) / sigma)
        return _omez(p), f"z hranice přijetí {stred:.0f}/200 b. (roky {_roky(nab.hranice)})"

    poptavka = _posledni(nab.poptavka)
    if poptavka is not None:
        zaklad = _sance_z_poptavky(poptavka)
        if skor is not None:
            zaklad += (skor - 110) / 400      # silnější uchazeč má navrch
        return _omez(zaklad), f"z poměru přihlášek ku kapacitě ({poptavka:.1f}×)"

    # Obory bez JPZ (typicky učňovské, písmeno H/E) — tam je jediné číslo,
    # které o náročnosti něco říká, loňský poměr přihlášených ku přijatým.
    # Skutečně přijaté má z webových zdrojů jen Atlas školství; infoabsolvent
    # uvádí plán přijmout, což poptávku podhodnocuje, když škola plán nenaplní.
    if nab.loni_prihlaseni and (nab.loni_prijati or nab.plan_prijmout):
        mista = nab.loni_prijati or nab.plan_prijmout or 0
        pomer = nab.loni_prihlaseni / max(mista, 1)
        zdroj = "loni přijatých" if nab.loni_prijati else "loňského plánu přijmout"
        return _omez(_sance_z_poptavky(pomer)), f"z loňského poměru přihlášek ({pomer:.1f}×, {zdroj})"

    if nab.plan_prijmout:
        return None, "škola nemá v datech JPZ (přijímačky bez jednotné zkoušky)"
    return None, "chybí data o přijímacím řízení"


def _sance_z_poptavky(poptavka: float) -> float:
    for mez, p in ((0.9, 0.92), (1.2, 0.80), (2.0, 0.60), (4.0, 0.35)):
        if poptavka <= mez:
            return p
    return 0.18


def _normalni_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _omez(p: float, dolni: float = 0.03, horni: float = 0.97) -> float:
    return max(dolni, min(horni, p))


def _posledni(hodnoty: dict[int, float]) -> float | None:
    return hodnoty[max(hodnoty)] if hodnoty else None


def _roky(hodnoty: dict[int, float]) -> str:
    return ", ".join(str(r) for r in sorted(hodnoty))


# --------------------------------------------------------------------------
# Ohodnocení
# --------------------------------------------------------------------------

def _vahy_profilu(profil: Profil) -> dict[str, float]:
    vahy = dict(SLOZKY_SKORE)
    for p in profil.priority[:3]:
        if p in PRIORITY:
            vahy[PRIORITY[p][1]] *= 2.0
    return vahy


def projde_filtrem(nab: Nabidka, profil: Profil) -> bool:
    """Tvrdé filtry — na co se uchazeč objektivně nemůže/nechce hlásit."""
    if nab.trida_prihlasky != profil.trida:
        return False
    if not profil.specialni_potreby and (nab.jen_pro_zp or nab.typ == "C"):
        # Praktická škola (typ C) i školy zřízené pro žáky se zdravotním
        # postižením předpokládají doporučení školského poradenského zařízení.
        return False
    if profil.typy and nab.typ not in profil.typy:
        return False
    if profil.oblasti_zajmu:
        if not set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu):
            return False
    if profil.skolne_max is not None and (nab.skolne or 0) > profil.skolne_max:
        return False
    if profil.jazyk and not _uci_jazyk(nab, profil.jazyk):
        return False
    return True


def _uci_jazyk(nab: Nabidka, jazyk: str) -> bool:
    """Učí se na škole daný jazyk? Kód je zkratka z infoabsolventu (A/N/Š/F/R/I/L)."""
    if not nab.jazyky:
        return False
    return bool(re.search(rf"(^|[\s,(]){re.escape(jazyk)}($|[\s,)])", nab.jazyky))


def ohodnot(profil: Profil, nabidky: Iterable[Nabidka]) -> list[Vysledek]:
    """Seřadí nabídky podle shody s profilem. Vrací všechny, co prošly filtrem."""
    vybrane = [n for n in nabidky if projde_filtrem(n, profil)]
    if not vybrane:
        return []

    vahy = _vahy_profilu(profil)
    # Kvalita se normalizuje proti tomu, co je v nabídce skutečně k mání —
    # percentil maturit se mezi gymnázii a učňáky liší o desítky bodů, takže
    # absolutní práh by u odborných oborů „vypnul" celou složku.
    percentily = [n.maturita_percentil for n in vybrane if n.maturita_percentil is not None]
    mez_dolni = min(percentily) if percentily else 0.0
    mez_horni = max(percentily) if percentily else 100.0

    vysledky: list[Vysledek] = []
    for nab in vybrane:
        p, zdroj = sance_prijeti(nab, profil.skor)
        slozky = {
            "zajem": _skore_zajem(nab, profil),
            "dosazitelnost": _skore_dosazitelnost(p, nab, profil),
            "kvalita": _skore_kvalita(nab, mez_dolni, mez_horni),
            "blizkost": _skore_blizkost(nab, profil),
            "cena": _skore_cena(nab, profil),
            "prostredi": _skore_prostredi(nab, profil),
        }
        skore = 100.0 * sum(slozky[k] * vahy[k] for k in slozky) / sum(vahy.values())
        vysledky.append(
            Vysledek(
                nabidka=nab,
                skore=skore,
                slozky=slozky,
                sance=p,
                sance_zdroj=zdroj,
                duvody=_duvody(nab, profil, slozky, p),
                varovani=_varovani(nab, profil, p),
            )
        )
    vysledky.sort(key=lambda v: v.skore, reverse=True)
    return vysledky


def _skore_zajem(nab: Nabidka, profil: Profil) -> float:
    if not profil.oblasti_zajmu:
        return 0.5
    shoda = set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu)
    if not shoda:
        return 0.0
    # Obor, který patří do jedné oblasti a ta je zvolená, sedí přesněji než
    # obor rozkročený mezi pět oblastí, z nichž jednu uchazeč zaškrtl.
    return min(1.0, 0.6 + 0.4 * len(shoda) / max(len(oblasti.oblasti_oboru(nab.kod_kkov)), 1))


def _skore_dosazitelnost(p: float | None, nab: Nabidka, profil: Profil) -> float:
    """Reálnost přijetí. Nad 40 % šance plný bod, pod tím lineárně dolů.

    Není to „čím jistější, tím lepší" — cílem je nezahltit výsledek školami,
    kam uchazeč nemá reálnou šanci, ne tlačit ho do podprůměrné školy.
    Rozložení rizika řeší `portfolio()`, ne tohle skóre.

    Doporučený prospěch (Atlas školství) se nepoužívá jako tvrdý filtr —
    je to doporučení školy, ne podmínka — ale horší průměr skóre srazí:
    školy si prospěch obvykle promítají do vlastních bodů (`dalsi_kriteria`).
    """
    zaklad = 0.4 if p is None else min(1.0, p / 0.4)
    if profil.prospech is not None and nab.doporuceny_prospech is not None:
        o_kolik = profil.prospech - nab.doporuceny_prospech
        if o_kolik > 0:
            zaklad *= max(0.4, 1.0 - o_kolik / 2.0)
    return zaklad


def _skore_kvalita(nab: Nabidka, mez_dolni: float, mez_horni: float) -> float:
    slozky: list[float] = []
    if nab.maturita_percentil is not None and mez_horni > mez_dolni:
        slozky.append((nab.maturita_percentil - mez_dolni) / (mez_horni - mez_dolni))
    if nab.maturita_uspesnost is not None:
        slozky.append(min(1.0, max(0.0, (nab.maturita_uspesnost - 70) / 30)))
    if nab.posun is not None:
        slozky.append(min(1.0, max(0.0, (nab.posun + 10) / 20)))
    return statistics.mean(slozky) if slozky else 0.5


def _skore_blizkost(nab: Nabidka, profil: Profil) -> float:
    if not profil.obvody:
        return 0.5
    if set(nab.obvody) & set(profil.obvody):
        return 1.0
    sousedi = {s for o in profil.obvody for s in oblasti.SOUSEDNI_OBVODY.get(o, ())}
    return 0.6 if set(nab.obvody) & sousedi else 0.2


def _skore_cena(nab: Nabidka, profil: Profil) -> float:
    skolne = nab.skolne
    if skolne is None:
        return 0.5
    if skolne == 0:
        return 1.0
    strop = profil.skolne_max or 60000
    return max(0.0, 1.0 - skolne / max(strop, 1)) * 0.8


def _skore_prostredi(nab: Nabidka, profil: Profil) -> float:
    """Složka řízená prioritami — bez zvolené priority je neutrální."""
    slozky: list[float] = []
    vybaveni = (nab.vybaveni or "").lower()
    for p in profil.priority[:3]:
        if p == "jazyky":
            pocet = nab.pocet_jazyku or (len(nab.jazyky.split(",")) if nab.jazyky else 0)
            slozky.append(min(1.0, pocet / 3))
        elif p == "maly_kolektiv":
            if nab.velikost_skoly:
                slozky.append(min(1.0, max(0.0, (600 - nab.velikost_skoly) / 500)))
        elif p == "sport":
            slozky.append(1.0 if re.search(r"hřišt|tělocvičn|sportovn|bazén", vybaveni) else 0.2)
        elif p == "umeni":
            slozky.append(1.0 if re.search(r"uměleck|ateliér|hudebn|divadeln", vybaveni) else 0.2)
        elif p == "praxe":
            slozky.append(1.0 if nab.typ in ("H", "E", "L0") else (0.6 if nab.typ == "M" else 0.2))
    return statistics.mean(slozky) if slozky else 0.5


def _duvody(nab: Nabidka, profil: Profil, slozky: dict[str, float], p: float | None) -> list[str]:
    """Proč se nabídka objevila — čte se pod kartou jako odrážky."""
    out: list[str] = []
    if profil.oblasti_zajmu and slozky["zajem"] > 0:
        shoda = set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu)
        popisky = ", ".join(oblasti.OBLASTI[k][0] for k in sorted(shoda))
        out.append(f"Obor patří do: {popisky}")
    if profil.prospech is not None and nab.doporuceny_prospech is not None:
        if profil.prospech <= nab.doporuceny_prospech:
            out.append(
                f"Tvůj průměr {profil.prospech:.1f} vyhovuje doporučenému prospěchu "
                f"{nab.doporuceny_prospech:.1f}"
            )
    if profil.obvody and set(nab.obvody) & set(profil.obvody):
        out.append(f"Je v preferované části: {', '.join(sorted(set(nab.obvody) & set(profil.obvody)))}")
    if nab.skolne == 0:
        out.append("Bez školného")
    elif nab.skolne:
        out.append(f"Školné {nab.skolne:,} Kč/rok".replace(",", " "))
    if nab.maturita_uspesnost is not None:
        out.append(
            f"Maturitu složí {nab.maturita_uspesnost:.0f} % žáků školy (průměr posledních 3 let)"
        )
    if nab.posun is not None and nab.posun > 2:
        rok_jpz, rok_mz = nab.posun_roky or (0, 0)
        out.append(
            f"Žáci se za studium posunuli o {nab.posun:+.0f} percentilu "
            f"(přijímačky {rok_jpz} → maturita {rok_mz}, celá škola)"
        )
    if nab.velikost_skoly:
        out.append(f"Velikost školy zhruba {nab.velikost_skoly} žáků")
    return out


def _varovani(nab: Nabidka, profil: Profil, p: float | None) -> list[str]:
    """Co data neříkají — stejně důležité jako důvody, proč ano."""
    out: list[str] = []
    if p is None:
        out.append("Šanci na přijetí nejde z dat odhadnout — u oboru chybí výsledky JPZ.")
    elif not nab.hranice:
        out.append(
            "Škola nevykázala hranici přijetí, šance je jen odhad z poměru přihlášek ku kapacitě."
        )
    elif len(nab.hranice) == 1:
        out.append("Hranice přijetí je známá jen za jeden rok — odhad je nejistý.")
    if nab.hranice and len(nab.hranice) >= 2:
        rozpeti = max(nab.hranice.values()) - min(nab.hranice.values())
        if rozpeti >= 25:
            out.append(
                f"Hranice přijetí mezi roky skáče o {rozpeti:.0f} bodů "
                f"({', '.join(f'{r}: {h:.0f}' for r, h in sorted(nab.hranice.items()))})."
            )
    if (
        profil.prospech is not None
        and nab.doporuceny_prospech is not None
        and profil.prospech > nab.doporuceny_prospech
    ):
        out.append(
            f"Škola doporučuje průměrný prospěch do {nab.doporuceny_prospech:.1f}, "
            f"ty máš {profil.prospech:.1f} — není to podmínka, ale body za prospěch ztratíš."
        )
    if nab.dalsi_kriteria:
        out.append(f"Škola přidává vlastní kritéria: {nab.dalsi_kriteria}")
    if nab.talentova_zkouska:
        out.append("Obor má talentovou zkoušku — přihláška se podává dřív (do 30. 11.).")
    if nab.lekarska_prohlidka:
        out.append("Obor vyžaduje potvrzení od lékaře (PLP) — objednat se včas.")
    if nab.maturita_uspesnost is None and oblasti.s_maturitou(nab.typ):
        out.append("Škola nemá v datech CERMAT maturitní výsledky (malá škola nebo nový obor).")
    if nab.inspekce_datum and nab.inspekce_datum < "2019-01-01":
        out.append(f"Poslední inspekce ČŠI je z {nab.inspekce_datum} — starší než 7 let.")
    if not nab.zrizovatel_verejny and nab.skolne == 0:
        out.append("Soukromá škola s nulovým školným v datech — ověřit přímo u školy.")
    return out


def vyber_top(vysledky: list[Vysledek], pocet: int = 5, max_na_skolu: int = 1) -> list[Vysledek]:
    """Prvních `pocet` nabídek, ale nejvýš `max_na_skolu` od jedné školy.

    Bez tohohle omezení se do pětice dostane dvakrát táž průmyslovka se
    dvěma příbuznými obory — pro uchazeče je to jedna a ta samá volba a
    pětice se tím ochudí o skutečné alternativy. Omezuje se na organizaci
    (REDIZO), ne na IZO: jedna právnická osoba může mít víc škol na stejné
    adrese a pro uchazeče je to pořád „ta samá škola".
    """
    out: list[Vysledek] = []
    pocty: dict[str, int] = {}
    for v in vysledky:
        redizo = v.nabidka.redizo
        if pocty.get(redizo, 0) >= max_na_skolu:
            continue
        pocty[redizo] = pocty.get(redizo, 0) + 1
        out.append(v)
        if len(out) == pocet:
            break
    return out


def poznamky(profil: Profil, vysledky: list[Vysledek]) -> list[str]:
    """Co uchazeči říct o samotném výsledku — hlavně nesplněná přání.

    Filtr může tiše „sníst" celé kritérium (v Praze 6 a 7 prostě není
    bezplatný IT obor) a uživatel pak nechápe, proč výsledek vypadá,
    jak vypadá. Radši to napsat, než nechat člověka hádat.
    """
    out: list[str] = []
    if not vysledky:
        return ["Žádná nabídka neprošla filtrem — zkus ubrat podmínky."]

    if profil.obvody and not any(set(v.nabidka.obvody) & set(profil.obvody) for v in vysledky):
        out.append(
            f"V {', '.join(profil.obvody)} nic, co by odpovídalo ostatním podmínkám, není — "
            "ukazuju nejbližší okolí."
        )
    if profil.skor is None:
        out.append(
            "Bez očekávaného skóru z přijímaček je šance jen hrubý odhad z poměru "
            "přihlášek — zkus průvodce znovu po přijímačkách nanečisto."
        )
    bez_dat = sum(1 for v in vysledky if v.sance is None)
    if bez_dat:
        out.append(
            f"U {bez_dat} z {len(vysledky)} vyhovujících nabídek nejsou data o přijímacím "
            "řízení (obory bez jednotné zkoušky) — šance se u nich neodhaduje."
        )
    return out


# --------------------------------------------------------------------------
# Portfolio přihlášek
# --------------------------------------------------------------------------

def portfolio(vysledky: list[Vysledek]) -> dict[str, Vysledek | None]:
    """Z ohodnocených nabídek vybere trojici na tři přihlášky.

    Od roku 2024 se podávají až 3 přihlášky a o umístění rozhoduje centrální
    algoritmus podle pořadí priorit — vyplatí se proto seřadit je **upřímně
    podle toho, kam uchazeč opravdu chce**, ne taktizovat. Riziko se
    nerozkládá pořadím, ale skladbou: jedna ambiciózní, jedna realistická a
    jedna, kde je přijetí velmi pravděpodobné (jinak hrozí 2. kolo).
    Výběr v každém pásmu = nejvyšší skóre shody, ne nejvyšší šance.
    """
    out: dict[str, Vysledek | None] = {}
    pouzite: set[str] = set()      # REDIZO, ne IZO×KKOV
    for role, (dolni, horni) in PASMA_PORTFOLIA.items():
        kandidati = [
            v for v in vysledky
            if v.sance is not None
            and dolni <= v.sance < horni
            and v.nabidka.redizo not in pouzite
        ]
        vybrany = max(kandidati, key=lambda v: v.skore) if kandidati else None
        if vybrany is not None:
            # Tři přihlášky na jednu školu nejsou rozložené riziko. Dedupe je
            # na organizaci (REDIZO), ne na oboru — dva obory téže školy padnou
            # obvykle společně (stejná kritéria, stejné pořadí uchazečů).
            pouzite.add(vybrany.nabidka.redizo)
        out[role] = vybrany
    return out


# --------------------------------------------------------------------------
# CLI — interaktivní průvodce
# --------------------------------------------------------------------------

def _zeptej_se_vyber(
    otazka: str, moznosti: list[tuple[str, str]], vic: bool = False, povinne: bool = False
) -> list[str]:
    print(f"\n{otazka}")
    for i, (_, popis) in enumerate(moznosti, 1):
        print(f"  {i}) {popis}")
    napoveda = "čísla oddělená čárkou, Enter = nezáleží" if vic else "číslo"
    while True:
        odpoved = input(f"> [{napoveda}]: ").strip()
        if not odpoved:
            if povinne:
                print("   Tahle odpověď je potřeba.")
                continue
            return []
        try:
            indexy = [int(x) for x in odpoved.replace(" ", "").split(",") if x]
            vybrane = [moznosti[i - 1][0] for i in indexy if 1 <= i <= len(moznosti)]
        except ValueError:
            vybrane = []
        if not vybrane:
            print("   Nerozumím, zkus čísla ze seznamu.")
            continue
        return vybrane if vic else vybrane[:1]


def _zeptej_se_cislo(otazka: str, maximum: float) -> float | None:
    while True:
        odpoved = input(f"{otazka} ").strip().replace(",", ".")
        if not odpoved:
            return None
        try:
            hodnota = float(odpoved)
        except ValueError:
            print("   Zadej číslo, nebo nech prázdné.")
            continue
        if 0 <= hodnota <= maximum:
            return hodnota
        print(f"   Musí být mezi 0 a {maximum:.0f}.")


def prubeh_pruvodce() -> Profil:
    """Interaktivní dotazník v terminálu — referenční průchod otázkami."""
    print("Průvodce výběrem střední školy v Praze")
    print("(Enter = přeskočit, na ničem kromě první otázky netrvám.)")

    trida = int(
        _zeptej_se_vyber(
            "1) Ze které třídy se hlásíš?",
            [("5", "z 5. třídy (osmiletá gymnázia)"),
             ("7", "ze 7. třídy (šestiletá gymnázia)"),
             ("9", "z 9. třídy (vše ostatní)")],
            povinne=True,
        )[0]
    )

    typy_pro_tridu = [
        (kod, popis) for kod, (popis, td, _) in oblasti.TYPY.items()
        if td == trida and kod not in oblasti.TYPY_MIMO_ZS
    ]
    typy = _zeptej_se_vyber("2) Jaký typ vzdělání tě zajímá?", typy_pro_tridu, vic=True)

    oblasti_zajmu = _zeptej_se_vyber(
        "3) Které oblasti tě baví?",
        [(k, popis) for k, (popis, _) in oblasti.OBLASTI.items()],
        vic=True,
    )

    obvody = _zeptej_se_vyber(
        "4) Kde by to mělo být? (kde bydlíš / kam se ti dobře jezdí)",
        [(f"Praha {i}", f"Praha {i}") for i in range(1, 11)],
        vic=True,
    )

    print("\n5) Jak ti vyjdou přijímačky? Zadej očekávaný % skór z JPZ")
    print("   (např. z přijímaček nanečisto; 0–100 za každý předmět, Enter = nevím).")
    skor_cj = _zeptej_se_cislo("   Český jazyk [0-100]:", 100)
    skor_ma = _zeptej_se_cislo("   Matematika  [0-100]:", 100)

    # Otázku na prospěch zvládne odpovědět každý (na rozdíl od otázky 5) a
    # školy ho promítají do vlastních bodů. Využije se, jen když je v
    # databázi Atlas školství — ten jediný doporučený prospěch uvádí.
    prospech = _zeptej_se_cislo(
        "\n6) Jaký máš průměr na vysvědčení? [1-5, Enter = přeskočit]:", 5
    )

    skolne = _zeptej_se_vyber(
        "7) Kolik můžete dát za školné?",
        [("0", "jen školy bez školného"),
         ("30000", "do 30 000 Kč/rok"),
         ("80000", "do 80 000 Kč/rok"),
         ("", "nerozhoduje")],
    )
    skolne_max = int(skolne[0]) if skolne and skolne[0] else None

    priority = _zeptej_se_vyber(
        "8) Co je pro tebe nejdůležitější? (vyber až 3)",
        [(k, popis) for k, (popis, _) in PRIORITY.items()],
        vic=True,
    )[:3]

    jazyk = _zeptej_se_vyber(
        "9) Chceš mít jistotu konkrétního jazyka?",
        [("N", "němčina"), ("Š", "španělština"), ("F", "francouzština"),
         ("R", "ruština"), ("I", "italština"), ("", "nezáleží")],
    )

    return Profil(
        trida=trida,
        typy=typy,
        oblasti_zajmu=oblasti_zajmu,
        obvody=obvody,
        skor_cj=skor_cj,
        skor_ma=skor_ma,
        skolne_max=skolne_max,
        jazyk=jazyk[0] if jazyk and jazyk[0] else None,
        prospech=prospech,
        priority=priority,
    )


def vypis_kartu(poradi: int, v: Vysledek, role: str | None = None) -> None:
    nab = v.nabidka
    hlavicka = f"{poradi}. {nab.nazev}"
    if role:
        hlavicka += f"   [{role}]"
    print("\n" + hlavicka)
    print(f"   {nab.obor} ({nab.kod_kkov}, {nab.typ_popis})")
    print(f"   {nab.adresa}, {', '.join(nab.obvody) or 'Praha'}"
          + (f" · {nab.www}" if nab.www else ""))
    sance = "neznámá" if v.sance is None else f"{v.sance * 100:.0f} %"
    print(f"   Shoda {v.skore:.0f}/100 · šance na přijetí {sance} ({v.sance_zdroj})")
    if nab.hranice:
        print("   Hranice přijetí: "
              + ", ".join(f"{r}: {h:.0f}/200 b." for r, h in sorted(nab.hranice.items())))
    if nab.prihlasky and nab.kapacita:
        print(f"   Přijímačky {max(ROKY_JPZ)}: {nab.prihlasky} přihlášek na {nab.kapacita} míst"
              + (f", přijato {nab.prijati}" if nab.prijati else ""))
    if nab.plan_prijmout:
        print(f"   Letos škola plánuje přijmout {nab.plan_prijmout} žáků")
    if nab.skolni_zkousky:
        print(f"   Škola má navíc: {', '.join(nab.skolni_zkousky)}")
    for d in v.duvody:
        print(f"   + {d}")
    for w in v.varovani:
        print(f"   ! {w}")
    if nab.dod:
        print(f"   Den otevřených dveří: {nab.dod}")
    if nab.inspekce_url:
        print(f"   Inspekční zprávy ČŠI: {nab.inspekce_url}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/jaknastredni.db", help="cesta k databázi")
    ap.add_argument("--profil", help="JSON s odpověďmi (jinak se průvodce zeptá interaktivně)")
    ap.add_argument("--pocet", type=int, default=5, help="kolik škol zobrazit (výchozí 5)")
    ap.add_argument("--json", action="store_true", help="výstup jako JSON místo karet")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    cesta = Path(args.db)
    if not cesta.exists():
        print(f"Databáze {cesta} neexistuje — spusť nejdřív: python -m jaknastredni.build_db",
              file=sys.stderr)
        return 2

    profil = (
        Profil.z_json(json.loads(Path(args.profil).read_text(encoding="utf-8")))
        if args.profil else prubeh_pruvodce()
    )

    conn = db.connect(cesta)
    try:
        nabidky = nacti_nabidky(conn)
    finally:
        conn.close()
    log.debug("nabídek v databázi: %d", len(nabidky))

    vysledky = ohodnot(profil, nabidky)
    if not vysledky:
        print("\nŽádná nabídka neprošla filtrem. Zkus ubrat podmínky "
              "(víc městských částí, vyšší školné, víc oblastí).", file=sys.stderr)
        return 1

    nejlepsi = vyber_top(vysledky, args.pocet)
    trojice = portfolio(vysledky)
    hlasky = poznamky(profil, vysledky)

    if args.json:
        print(json.dumps(
            {
                "profil": asdict(profil),
                "celkem_vyhovuje": len(vysledky),
                "poznamky": hlasky,
                "doporucene": [v.do_dictu() for v in nejlepsi],
                "portfolio": {
                    role: (v.do_dictu() if v else None) for role, v in trojice.items()
                },
            },
            ensure_ascii=False, indent=2,
        ))
        return 0

    print(f"\n=== Vyhovuje {len(vysledky)} nabídek, tady je {len(nejlepsi)} nejlepších ===")
    for h in hlasky:
        print(f"  ({h})")
    for i, v in enumerate(nejlepsi, 1):
        vypis_kartu(i, v)

    print("\n=== Návrh tří přihlášek ===")
    print("Pořadí priorit vyplň podle toho, kam opravdu chceš — algoritmus "
          "přijímaček tě nikdy nepotrestá za to, že sis na 1. místo dal sen.")
    popisky = {"sen": "sen", "realisticka": "realistická", "jistota": "jistota"}
    duvod_prazdna = {
        "sen": "na všechno, co ti sedí, máš velkou šanci — zkus rozšířit filtr "
               "(další obory, celá Praha) a mířit výš",
        "realisticka": "mezi nabídkami není nic se střední šancí — buď máš na všechno, "
                       "nebo je všechno hodně nad tvoje skóre",
        "jistota": "nic, kam by tě vzali skoro jistě — přidej záložní obor, jinak "
                   "hrozí 2. kolo",
    }
    for i, (role, v) in enumerate(trojice.items(), 1):
        if v is None:
            print(f"\n{i}. [{popisky[role]}] — {duvod_prazdna[role]}.")
        else:
            vypis_kartu(i, v, role=popisky[role])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
