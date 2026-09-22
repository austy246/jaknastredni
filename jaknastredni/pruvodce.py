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
import dataclasses
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from . import db, oblasti
from .cermat_uchazeci import PASMO_BEZ_JPZ

log = logging.getLogger(__name__)

# Roky JPZ v novém formátu (tabulka prijimaci_rizeni), od nejnovějšího.
# Váha při odhadu hranice přijetí: nejnovější rok váží nejvíc.
ROKY_JPZ: dict[int, float] = {2026: 3.0, 2025: 2.0, 2024: 1.0}

# Meziroční rozptyl hranice přijetí (min. % skór přijatých, škála 0–200)
# spočítaný z dat: směrodatná odchylka meziroční změny je 20,4 bodu,
# medián |změny| 12 bodů, p90 32 bodů (598 dvojic škola×obor 2024→2025 a
# 2025→2026). Odhad šance proto nikdy nepoužívá menší nejistotu než tohle —
# viz docs/pruvodce-ux.md, oddíl „Šance na přijetí".
# Empirická míra přijetí (tabulka `prijimacky_pasmo`, importér
# `jaknastredni.cermat_uchazeci`) je přednostní zdroj odhadu šance. Okno je
# ±10 bodů kolem uchazečova skóru; když v něm není dost věcně posouzených
# přihlášek, rozšíří se na ±20 a teprve pak se sáhne po odhadu z hranice.
# MIN_VZOREK drží odhad mimo pásma, kde by o něm rozhodovali tři lidé.
OKNO_PASMA = 10
OKNO_PASMA_SIROKE = 20
MIN_VZOREK = 10
# Síla smršťování k modelovému odhadu: u vzorku 10 má naměřený podíl váhu
# 10/15, u vzorku 100 váhu 100/105. Brání tomu, aby "0 ze 12" znamenalo
# tvrdou nulu — škola může letos vzít víc lidí, kritéria se mění.
SMRSTENI = 5.0

SIGMA_ZAKLAD = 18.0
SIGMA_JEDEN_ROK = 24.0   # jen jeden rok dat = ještě větší nejistota
SIGMA_MAX = 32.0

# Váhy složek skóre. Priorita zvolená uchazečem svou složku zdvojnásobí
# (viz PRIORITY a _vahy_profilu).
SLOZKY_SKORE: dict[str, float] = {
    "zajem": 3.0,           # shoda oboru s tím, co uchazeče zajímá
    "typ": 3.0,             # typ vzdělání odvozený z osobnostních otázek
    "dosazitelnost": 2.5,   # reálnost přijetí podle očekávaného skóre
    "kvalita": 1.5,         # maturitní výsledky školy, posun žáků, inspekce
    "blizkost": 1.5,        # městská část
    "cena": 1.0,            # školné
    "prostredi": 1.0,       # velikost školy, vybavení dle priorit
    "jazyk": 1.0,           # vyučuje škola jazyk, který uchazeč chce?
}

# Priority, ze kterých uchazeč vybírá max. 3 (klíč -> (popisek, složka skóre)).
PRIORITY: dict[str, tuple[str, str]] = {
    "jistota": ("Jistota, že mě vezmou", "dosazitelnost"),
    "kvalita": ("Kvalita výuky a výsledky maturit", "kvalita"),
    "blizkost": ("Ať to mám blízko", "blizkost"),
    "cena": ("Co nejnižší školné", "cena"),
    "jazyky": ("Hodně jazyků", "jazyk"),
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

# Otázky na přípravu. Záměrně se **neptají na odhodlání** („jak moc se budeš
# připravovat?" odpoví každý „hodně" a odpověď nemá informační hodnotu), ale
# na chování, které už probíhá, a na čas, který reálně je. Slouží k jedinému:
# nastavit výchozí polohu posuvníku zlepšení a upozornit, když se plán a cíl
# rozcházejí. **Žádný převod hodin na body z nich nepočítáme** — data, která
# by ho podložila, neexistují a vymýšlet si ho je přesně to, co u agregátorů
# kritizujeme (README, zdroj 6).
PRIPRAVA_OTAZKY: dict[str, tuple[str, dict[str, tuple[str, float]]]] = {
    "priprava_ted": ("Připravuješ se na přijímačky už teď?", {
        "ne":         ("Zatím vůbec", 0.0),
        "obcas":      ("Občas, když si vzpomenu", 0.5),
        "pravidelne": ("Pravidelně každý týden", 1.0),
    }),
    "hodin_tydne": ("Kolik hodin týdně na to reálně máš?", {
        "do1":    ("Do hodiny", 0.25),
        "2az3":   ("2–3 hodiny", 0.5),
        "4az6":   ("4–6 hodin", 0.8),
        "7plus":  ("7 a víc", 1.0),
    }),
    "kurz": ("Chodíš na přípravný kurz nebo doučování?", {
        "ne":      ("Ne", 0.0),
        "chystam": ("Chystám se", 0.5),
        "ano":     ("Ano", 1.0),
    }),
}

# Návrh, o kolik bodů **v každém předmětu** (z 50) posunout posuvník podle
# odpovědí. Je to pravidlo palce pro výchozí polohu, ne předpověď — uživatel
# si ho má přenastavit. Škála: 0 = nedělá nic, 1 = připravuje se naplno.
MAX_NAVRH_BODU = 10

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
    # Zaměření uvnitř oblasti (klíče oblasti.ZAMERENI) — „baví ho IT" je na
    # výběr ze 60 IT nabídek pořád hrubé síto, tohle rozliší programování od
    # sítí nebo herní grafiky. Prázdné = podle zaměření se neřadí.
    zamereni: list[str] = field(default_factory=list)
    obvody: list[str] = field(default_factory=list)    # 'Praha 6', …
    skor_cj: float | None = None         # očekávaný % skór ČJ (0–100)
    skor_ma: float | None = None         # očekávaný % skór MA (0–100)
    skolne_max: int | None = None        # Kč/rok; None = nerozhoduje, 0 = jen bezplatné
    jazyk: str | None = None             # požadovaný jazyk ('N', 'Š', 'F', …)
    # Jazyk normálně jen váží. Jako tvrdý filtr vyhazoval třetinu nabídky
    # (138 -> 90) a měnil 3 z 5 škol v pětici — na otázku, která vypadá
    # jako detail na konci formuláře, je to moc. Kdo na jazyku opravdu
    # trvá, zapne si `jazyk_povinny`.
    jazyk_povinny: bool = False
    prospech: float | None = None        # průměr známek na výstupním vysvědčení ZŠ
    specialni_potreby: bool = False      # zahrnout školy zřízené pro žáky se ZP
    talentove: bool = False              # zahrnout obory s talentovou zkouškou
    # Zlepšení v **bodech na předmět** (z 50), ne na dvousetbodové škále —
    # rodič uvažuje v bodech z přijímaček, ne v procentech skóru.
    zlepseni_bodu: float = 0.0
    priprava_ted: str | None = None      # 'ne' / 'obcas' / 'pravidelne'
    hodin_tydne: str | None = None       # 'do1' / '2az3' / '4az6' / '7plus'
    kurz: str | None = None              # 'ne' / 'chystam' / 'ano'
    # Osobnostní otázky, ze kterých se typ vzdělání **odvozuje**, místo aby
    # se na něj průvodce ptal přímo (viz oblasti.OSOBNOSTNI_OTAZKY).
    po_skole: str | None = None          # 'vysoka' / 'prace' / 'nevim'
    rozhodnuto: str | None = None        # 'obor' / 'otevreno' / 'nevim'
    praxe: str | None = None             # 'hodne' / 'stredne' / 'teorie'
    typy_vyloucene: list[str] = field(default_factory=list)  # co uchazeč nechce
    priority: list[str] = field(default_factory=list)  # klíče PRIORITY, max 3

    @property
    def hledana_zamereni(self) -> set[str]:
        """Zvolená zaměření, která patří k některé ze zvolených oblastí.

        Formulář nabízí jen zaměření ke zvoleným oblastem, ale profil se dá
        poskládat i ručně (a uchazeč si může oblast odškrtnout až potom).
        Zaměření mimo zvolené oblasti by jinak sráželo obory, na které se
        vůbec neptá.
        """
        if not self.oblasti_zajmu:
            return set()
        zvolene = set(self.oblasti_zajmu)
        return {k for k in self.zamereni
                if k in oblasti.ZAMERENI and zvolene & set(oblasti.ZAMERENI[k][1])}

    @property
    def osobnostni(self) -> dict[str, str | None]:
        """Odpovědi na osobnostní otázky ve tvaru, který čeká `oblasti`."""
        return {"po_skole": self.po_skole, "rozhodnuto": self.rozhodnuto, "praxe": self.praxe}

    @property
    def priprava(self) -> dict[str, str | None]:
        return {"priprava_ted": self.priprava_ted, "hodin_tydne": self.hodin_tydne,
                "kurz": self.kurz}

    @property
    def skor(self) -> float | None:
        """Očekávaný součet % skóru ČJ + MA (škála 0–200, jako CERMAT).

        Zahrnuje `zlepseni_bodu`: bod navíc v jednom předmětu z 50 je
        +2 % skóru v něm, a protože se počítá do obou předmětů, +4 na
        dvousetbodové škále. Strop 50 bodů na předmět se nepřekročí.
        """
        if self.skor_cj is None or self.skor_ma is None:
            return None
        pridat = self.zlepseni_bodu / 50 * 100
        return min(100.0, self.skor_cj + pridat) + min(100.0, self.skor_ma + pridat)

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
    zamereni: tuple[str, ...] = ()       # texty zaměření z CERMATu
    svp: str | None = None               # název ŠVP (infoabsolvent) — co škola
                                         # pod obecným kódem KKOV doopravdy učí
    # Rozpoznaná zaměření (klíče oblasti.ZAMERENI). `zamereni_kody` jsou
    # z textů **o oboru** (název, ŠVP, zaměření z CERMATu), `zamereni_skoly`
    # z volného popisu **celé školy** — ten platí pro všechny její obory
    # dohromady, takže je to slabší signál a skóre ho váží míň.
    zamereni_kody: tuple[str, ...] = ()
    zamereni_skoly: tuple[str, ...] = ()
    # Naměřená míra přijetí z CERMAT souborů uchazečů 2024+:
    # pásmo % skóru (dolní mez, -1 = obor bez JPZ) -> rok -> (přijato,
    # věcně posouzeno). Rok se drží zvlášť, aby šel novější vážit výš.
    pasma: dict[int, dict[int, tuple[int, int]]] = field(default_factory=dict)
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
    termin_jpz: str | None = None        # text termínů jednotné zkoušky ze scrapu
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
    dalsi_obory: list[str] = field(default_factory=list)

    def do_dictu(self) -> dict[str, Any]:
        d = asdict(self.nabidka)
        d["skore"] = round(self.skore, 1)
        d["slozky"] = {k: round(v, 3) for k, v in self.slozky.items()}
        d["sance"] = None if self.sance is None else round(self.sance, 3)
        d["sance_zdroj"] = self.sance_zdroj
        d["duvody"] = self.duvody
        d["varovani"] = self.varovani
        d["dalsi_obory"] = self.dalsi_obory
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
    _doplnit_pasma(conn, nabidky)
    _doplnit_web_profil(conn, nabidky)
    _doplnit_kvalitu(conn, nabidky)
    _doplnit_zamereni(nabidky)
    return list(nabidky.values())


def _doplnit_zamereni(nabidky: dict[tuple[str, str], Nabidka]) -> None:
    """Dopočítá rozpoznaná zaměření ze všech textů, které o nabídce máme.

    Běží až nakonec, protože skládá dohromady tři zdroje: název oboru
    z rejstříku, název ŠVP a název oboru z webových profilů (ty doplnil
    `_doplnit_obor`) a texty zaměření z CERMATu (`_doplnit_prijimacky`).

    Zaměření, které je doložené u oboru, se zároveň škrtne ze slabšího
    školního seznamu — aby se tentýž signál nezapočítal dvakrát a aby
    `zamereni_skoly` opravdu znamenalo „škola to uvádí, ale u tohohle
    oboru to doložené nemáme".
    """
    for nab in nabidky.values():
        nab.zamereni_kody = tuple(sorted(set(nab.zamereni_kody) | set(
            oblasti.zamereni_textu(nab.obor, nab.svp, *nab.zamereni))))
        nab.zamereni_skoly = tuple(sorted(set(nab.zamereni_skoly) - set(nab.zamereni_kody)))


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


def _doplnit_pasma(conn: sqlite3.Connection, nabidky: dict[tuple[str, str], Nabidka]) -> None:
    """Naměřená míra přijetí po bodových pásmech (CERMAT soubory uchazečů).

    Klíčem je REDIZO + KKOV (soubory uchazečů IZO neuvádějí), takže víc škol
    jedné organizace se stejným oborem sdílí jedna čísla — v pražských datech
    vzácné, viz komentář u tabulky v schema.sql.

    Bere jen **1. kolo**: druhé kolo je jiná hra (zbylá místa, jiná skladba
    uchazečů) a míchat je dohromady by zkreslilo. Roky 2024–2026 se sčítají,
    protože jeden ročník dává u malých oborů vzorek několika lidí.
    """
    podle_redizo_kkov: dict[tuple[str, str], list[Nabidka]] = {}
    for nab in nabidky.values():
        podle_redizo_kkov.setdefault((nab.redizo, nab.kod_kkov), []).append(nab)

    for r in conn.execute(
        """
        SELECT redizo, kod_kkov, rok, pasmo_od,
               SUM(prijato) AS prijato,
               SUM(prijato + nedostatecna_kapacita + nesplneni_podminek) AS posouzeno
          FROM prijimacky_pasmo
         WHERE kolo = 1
         GROUP BY redizo, kod_kkov, rok, pasmo_od
        """
    ):
        for nab in podle_redizo_kkov.get((r["redizo"], r["kod_kkov"]), ()):
            if r["posouzeno"]:
                nab.pasma.setdefault(r["pasmo_od"], {})[r["rok"]] = (r["prijato"] or 0, r["posouzeno"])


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
            # Volný popis školy je jediné místo, kde se dá vyčíst, že se pod
            # kódem `18-20-M/01` učí zrovna správa sítí — v žádném číselníku
            # to není. Platí ale pro celou školu, ne pro konkrétní obor.
            nab.zamereni_skoly = tuple(sorted(set(nab.zamereni_skoly) | set(
                oblasti.zamereni_textu(data.get("vybaveni_a_nabidka"),
                                       data.get("doplnujici_informace")))))
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
    nab.svp = nab.svp or o.get("svp_nazev")
    # Atlas dává ŠVP do závorky za obecný název („Elektrotechnika
    # (Automatizace a robotika)"), infoabsolvent zvlášť — brát se musí obojí.
    nab.zamereni_kody = tuple(sorted(set(nab.zamereni_kody) | set(
        oblasti.zamereni_textu(o.get("nazev_oboru"), o.get("svp_nazev")))))
    nab.pocet_jazyku = nab.pocet_jazyku or o.get("pocet_povinnych_jazyku")
    nab.jazyky = o.get("vyucovane_jazyky") or nab.jazyky
    if nab.doporuceny_prospech is None:
        nab.doporuceny_prospech = _prospech(o.get("doporuceny_prospech"))
    if nab.lekarska_prohlidka is None:
        nab.lekarska_prohlidka = o.get("plp")
    pr = o.get("prijimaci_rizeni") or {}
    nab.prihlasky_do = nab.prihlasky_do or pr.get("prihlasky_podejte_do")
    nab.termin_jpz = nab.termin_jpz or pr.get("terminy_jednotne_zkousky")
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


def _prevazuje_bez_jpz(nab: Nabidka) -> bool:
    """Rozhoduje o přijetí na tenhle obor něco jiného než jednotná zkouška?

    Pozná se podle toho, že uchazečů **bez** % skóru je aspoň tolik co
    s ním: u oborů s výučním listem se JPZ nekoná, takže bodovaní uchazeči
    jsou jen ti, kdo si vedle toho podali i maturitní obor. Odhadovat z nich
    šanci by bylo nejen nepřesné, ale i nemonotonní — nad jejich rozsahem
    by odhad spadl na úplně jiný zdroj.
    """
    bez = nab.pasma.get(PASMO_BEZ_JPZ)
    if not bez:
        return False
    pocet_bez = sum(n for _p, n in bez.values())
    pocet_s = sum(n for pasmo, podle_roku in nab.pasma.items() if pasmo != PASMO_BEZ_JPZ
                  for _p, n in podle_roku.values())
    return pocet_bez >= pocet_s


def _monotonni_pasma(pasma: dict[int, dict[int, tuple[int, int]]]) -> dict[int, tuple[float, int]]:
    """Vyhladí naměřené míry přijetí tak, aby se skórem neklesaly.

    Skutečná šance na přijetí je v bodech neklesající — víc bodů uchazeči
    uškodit nemůže. Naměřená čísla ale neklesající nejsou: v pásmu, kde je
    osm lidí, rozhodne jeden. Bez vyhlazení pak průvodce ukáže nesmysl typu
    „se 140 body máš 90 %, se 156 body 79 %" a rozumně ztratí důvěru.

    Používá se **PAVA** (pool adjacent violators) — standardní řešení
    isotonické regrese: dokud je nějaké pásmo nižší než to před ním, slijí
    se do jednoho bloku se společným (vahou váženým) podílem. Váha je počet
    věcně posouzených přihlášek, takže velká pásma táhnou malá, ne naopak.

    Vrací pásmo -> (vyhlazený podíl, skutečný počet posouzených přihlášek).
    """
    body: list[tuple[int, float, float, int]] = []
    for pasmo, podle_roku in sorted(pasma.items()):
        if pasmo == PASMO_BEZ_JPZ:
            continue
        vaz_prijato = vaz_posouzeno = 0.0
        posouzeno = 0
        for rok, (p, n) in podle_roku.items():
            vaha = ROKY_JPZ.get(rok, 1.0)
            vaz_prijato += p * vaha
            vaz_posouzeno += n * vaha
            posouzeno += n
        if vaz_posouzeno:
            body.append((pasmo, vaz_prijato / vaz_posouzeno, vaz_posouzeno, posouzeno))

    bloky: list[list] = []      # [[pásma], součet vah×podíl, součet vah]
    for pasmo, podil, vaha, _n in body:
        bloky.append([[pasmo], podil * vaha, vaha])
        while len(bloky) >= 2 and (bloky[-2][1] / bloky[-2][2]) > (bloky[-1][1] / bloky[-1][2]):
            posledni = bloky.pop()
            bloky[-1][0] += posledni[0]
            bloky[-1][1] += posledni[1]
            bloky[-1][2] += posledni[2]

    vzorky = {pasmo: n for pasmo, _p, _v, n in body}
    out: dict[int, tuple[float, int]] = {}
    for pasma_bloku, soucet, vaha in bloky:
        podil = soucet / vaha
        for pasmo in pasma_bloku:
            out[pasmo] = (podil, vzorky[pasmo])
    return out


def _empiricka_sance(nab: Nabidka, skor: float | None,
                     ) -> tuple[float, int, int, int | None] | None:
    """(vážený podíl přijatých, přijato, posouzeno, okno), nebo None.

    Sčítá pásma v okně ±`OKNO_PASMA` kolem uchazečova skóru; když je vzorek
    menší než `MIN_VZOREK`, zkusí širší okno a teprve pak to vzdá. Skór
    `None` znamená obor bez jednotné zkoušky — sáhne se do pásma
    `PASMO_BEZ_JPZ`, kde jsou uchazeči, kteří JPZ nekonali.
    """
    if not nab.pasma:
        return None

    bez_jpz = nab.pasma.get(PASMO_BEZ_JPZ)
    if skor is not None and bez_jpz and _prevazuje_bez_jpz(nab):
        # Obor, kde většina uchazečů jednotnou zkoušku vůbec nekoná (typicky
        # výuční list). Pár bodovaných uchazečů, co se sem hlásili vedle
        # maturitního oboru, o přijetí nevypovídá — vybírá se podle něčeho
        # jiného. Skór proto ignorujeme a použijeme míru přijetí za obor.
        skor = None

    if skor is None:
        # Obor bez jednotné zkoušky — jediné pásmo, vyhlazovat není co.
        data = bez_jpz
        if not data:
            return None
        vaz_prijato = vaz_posouzeno = 0.0
        prijato = posouzeno = 0
        for rok, (p, n) in data.items():
            vaha = ROKY_JPZ.get(rok, 1.0)
            vaz_prijato += p * vaha
            vaz_posouzeno += n * vaha
            prijato += p
            posouzeno += n
        if not posouzeno:
            return None
        return vaz_prijato / vaz_posouzeno, prijato, posouzeno, None

    vyhlazena = _monotonni_pasma(nab.pasma)
    if vyhlazena:
        # Nad (pod) rozsahem naměřených pásem se skór **neextrapoluje** ani
        # nepropadne na slabší zdroj odhadu — vezme se krajní hodnota
        # vyhlazené křivky. Propadnutí na poměr přihlášek by znamenalo, že
        # uchazeč se 150 body má menší šanci než se 140, což je nesmysl a
        # v datech to dělalo skoky přes 40 procentních bodů.
        skor = min(max(skor, min(vyhlazena)), max(vyhlazena))
    # O tom, jestli se naměřená data použijí, se rozhoduje **jednou za
    # nabídku**, ne zvlášť pro každé skóre. Kdyby o tom rozhodoval vzorek
    # v okolí uchazečova skóru, přepnul by odhad uprostřed rozsahu na jinou
    # metodu — a na tom přepnutí vznikne útes: „se 170 body 95 %, se 180
    # body 52 %". V pražských datech to dělalo přes sto takových skoků.
    # Buď o nabídce data máme, nebo ne.
    celkem = sum(n for _p, n in vyhlazena.values())
    if celkem < MIN_VZOREK:
        return None
    moje_pasmo = max((p for p in vyhlazena if p <= skor), default=min(vyhlazena))
    podil, _n = vyhlazena[moje_pasmo]
    # Vzorek „v okolí" je jen pro text na kartě, na číslo nemá vliv.
    v_okoli = sum(n for pasmo, (_p, n) in vyhlazena.items()
                  if moje_pasmo - OKNO_PASMA <= pasmo <= moje_pasmo + OKNO_PASMA)
    return podil, round(podil * max(v_okoli, 1)), max(v_okoli, 1), celkem


def sance_prijeti(nab: Nabidka, skor: float | None) -> tuple[float | None, str]:
    """Odhad pravděpodobnosti přijetí (0–1) a slovní zdroj odhadu.

    Čtyři úrovně podle toho, co o nabídce víme:

    1. **Naměřený podíl přijatých** v okolí uchazečova skóru (CERMAT soubory
       uchazečů 2024+, tabulka `prijimacky_pasmo`). Tohle není model, ale
       pozorování: ze 124 lidí s podobným skórem se jich dostalo tolik a
       tolik. Smršťuje se k úrovni 2 podle velikosti vzorku (`SMRSTENI`), ať
       „0 z 12" neznamená tvrdou nulu.
    2. **Známá hranice přijetí** (min. % skór posledního přijatého): normální
       rozdělení kolem očekávané hranice. Pozor, je to ocasová hodnota —
       proti naměřeným datům vychází systematicky optimisticky (u některých
       škol až o 40 procentních bodů), proto je až druhá.
    3. **Poměr přihlášek ku kapacitě** (`index_poptavky`), případně loňský
       poměr přihlášených ku přijatým z Atlasu — hrubý odhad z pásem.
    4. **Nic z toho**: None — karta ukáže „data chybí", ne vymyšlené číslo.

    Odhad nikdy nejde na 0 % ani 100 %: škola si přidává vlastní kritéria
    (prospěch, talentovka, pohovor), která v datech nejsou.
    """
    odhad = odhad_hranice(nab)
    modelova = None
    if odhad is not None and skor is not None:
        stred, sigma = odhad
        modelova = _omez(_normalni_cdf((skor - stred) / sigma))

    empiricka = _empiricka_sance(nab, skor)
    if empiricka is not None:
        podil, prijato, vzorek, celkem = empiricka
        kotva = modelova if modelova is not None else podil
        # Váha smrštění je **celkový** vzorek nabídky, ne lokální: konstantní
        # váha drží výsledek monotonní (konvexní kombinace dvou neklesajících
        # funkcí), kdežto váha měnící se se skórem ji zase rozbije.
        vaha = celkem if celkem is not None else vzorek
        p = (podil * vaha + SMRSTENI * kotva) / (vaha + SMRSTENI)
        kde = (f"±{OKNO_PASMA} b." if celkem is not None else "bez jednotné zkoušky")
        return _omez(p), (f"naměřeno: přijato {prijato} z {vzorek} uchazečů "
                          f"s podobným skórem ({kde}, 1. kola 2024–2026)")

    if modelova is not None:
        stred, _sigma = odhad
        return modelova, f"z hranice přijetí {stred:.0f}/200 b. (roky {_roky(nab.hranice)})"

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
    if nab.typ in profil.typy_vyloucene:
        return False
    if nab.talentova_zkouska and not profil.talentove:
        # Talentovka je jiná vstupní brána, ne nižší laťka: obor s ní má
        # hranici JPZ nižší proto, že se vybírá podle talentu, ne podle
        # menšího zájmu. Kdo na talentovky nechodí, tam nemá co dělat —
        # a v pětici by zabíral místo. 52 nabídek (48 uměleckých, 4 sportovní
        # gymnázia). Přihláška se navíc podává dřív, do 30. 11.
        return False
    if profil.oblasti_zajmu:
        if not set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu):
            return False
    if profil.skolne_max is not None and not _vejde_se_do_skolneho(nab, profil.skolne_max):
        return False
    if profil.jazyk and profil.jazyk_povinny and not _uci_jazyk(nab, profil.jazyk):
        return False
    return True


def _vejde_se_do_skolneho(nab: Nabidka, strop: int) -> bool:
    """Vejde se nabídka do zadaného stropu školného?

    Past: chybějící údaj **nesmí** projít jako nula. Školné u oboru často
    chybí i u škol, které si účtují statisíce (PORG má u gymnázia 199 100 Kč,
    ale u pedagogického oboru v datech nic) — filtr „jen do 30 tisíc" by pak
    takovou školu tiše propustil. U veřejného zřizovatele je neuvedené
    školné bezpečně nula (kraj ani obec školné nevybírají), u soukromého a
    církevního je to neznámá, a ta se do stropu nevejde.
    """
    if nab.skolne is not None:
        return nab.skolne <= strop
    return nab.zrizovatel_verejny


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
    preference = oblasti.preference_typu(profil.osobnostni)
    # Preference typu se normalizuje proti tomu, co prošlo filtrem — stejně
    # jako `kvalita`. Surové hodnoty se u jedné nabídky mačkají do pásma
    # kolem 0,75 (průměr ze tří tabulek táhne ke středu) a složka pak
    # prakticky nic neřídila: přepnutí z „půjdu na vysokou" na „chci rovnou
    # pracovat" neměnilo v pětici ani jeden obor. Po roztažení na plný
    # rozsah rozhoduje pořadí typů, ne jejich absolutní hodnota.
    hodnoty_typu = [preference.get(n.typ, 0.5) for n in vybrane]
    typ_dolni, typ_horni = min(hodnoty_typu), max(hodnoty_typu)
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
            "typ": _normalizuj(preference.get(nab.typ, 0.5), typ_dolni, typ_horni),
            "dosazitelnost": _skore_dosazitelnost(p, nab, profil),
            "kvalita": _skore_kvalita(nab, mez_dolni, mez_horni),
            "blizkost": _skore_blizkost(nab, profil),
            "cena": _skore_cena(nab, profil),
            "prostredi": _skore_prostredi(nab, profil),
            "jazyk": _skore_jazyk(nab, profil),
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


def _normalizuj(hodnota: float, dolni: float, horni: float) -> float:
    """Roztáhne hodnotu na 0–1 podle rozsahu, který je mezi kandidáty k mání."""
    if horni <= dolni:
        return 0.5
    return (hodnota - dolni) / (horni - dolni)


def _skore_zajem(nab: Nabidka, profil: Profil) -> float:
    """Jak dobře obor sedí na zájem — hrubě oblastí, jemně zaměřením."""
    if not profil.oblasti_zajmu:
        return 0.5
    shoda = set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu)
    if not shoda:
        return 0.0
    # Obor, který patří do jedné oblasti a ta je zvolená, sedí přesněji než
    # obor rozkročený mezi pět oblastí, z nichž jednu uchazeč zaškrtl.
    zaklad = min(1.0, 0.6 + 0.4 * len(shoda) / max(len(oblasti.oblasti_oboru(nab.kod_kkov)), 1))
    return zaklad * _shoda_zamereni(nab, profil)


# Násobek skóre zájmu podle toho, jak doložená je shoda v zaměření. Shoda
# u oboru nechává skóre být, shoda jen v popisu školy ho srazí jemně
# (škola to učí, ale u tohohle oboru to doložené nemáme) a doložené **jiné**
# zaměření hodně — takový obor se jmenuje stejně, ale učí něco jiného.
SHODA_ZAMERENI = {"obor": 1.0, "skola": 0.9, "nevime": 0.8, "jine": 0.6}


def _shoda_zamereni(nab: Nabidka, profil: Profil) -> float:
    """Kolikrát se skóre zájmu vynásobí podle shody v zaměření (viz SHODA_ZAMERENI).

    Bez zvolených zaměření vrací 1,0 — průvodce se podle nich pak vůbec
    neřadí a chová se jako dřív.
    """
    hledane = profil.hledana_zamereni
    if not hledane:
        return 1.0
    return SHODA_ZAMERENI[_uroven_zamereni(nab, hledane)]


def _uroven_zamereni(nab: Nabidka, hledane: set[str]) -> str:
    if set(nab.zamereni_kody) & hledane:
        return "obor"
    if set(nab.zamereni_skoly) & hledane:
        return "skola"
    if nab.zamereni_kody:
        return "jine"
    return "nevime"


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
        if p == "maly_kolektiv":
            if nab.velikost_skoly:
                slozky.append(min(1.0, max(0.0, (600 - nab.velikost_skoly) / 500)))
        elif p == "sport":
            slozky.append(1.0 if re.search(r"hřišt|tělocvičn|sportovn|bazén", vybaveni) else 0.2)
        elif p == "umeni":
            slozky.append(1.0 if re.search(r"uměleck|ateliér|hudebn|divadeln", vybaveni) else 0.2)
        elif p == "praxe":
            slozky.append(1.0 if nab.typ in ("H", "E", "L0") else (0.6 if nab.typ == "M" else 0.2))
    return statistics.mean(slozky) if slozky else 0.5


def _skore_jazyk(nab: Nabidka, profil: Profil) -> float:
    """Učí škola jazyk, který uchazeč chce? Bez požadavku je složka neutrální."""
    if not profil.jazyk:
        return 0.5
    if not nab.jazyky:
        return 0.4        # údaj chybí — netrestat plnou vahou, ale ani odměnit
    return 1.0 if _uci_jazyk(nab, profil.jazyk) else 0.15


def _duvody(nab: Nabidka, profil: Profil, slozky: dict[str, float], p: float | None) -> list[str]:
    """Proč se nabídka objevila — čte se pod kartou jako odrážky."""
    out: list[str] = []
    if profil.oblasti_zajmu and slozky["zajem"] > 0:
        shoda = set(oblasti.oblasti_oboru(nab.kod_kkov)) & set(profil.oblasti_zajmu)
        popisky = ", ".join(oblasti.OBLASTI[k][0] for k in sorted(shoda))
        out.append(f"Obor patří do: {popisky}")
    out.extend(_duvody_zamereni(nab, profil))
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


def _popis_zamereni(kody: Iterable[str]) -> str:
    return ", ".join(oblasti.popis_zamereni(k) for k in sorted(kody))


def _duvody_zamereni(nab: Nabidka, profil: Profil) -> list[str]:
    """Věta o zaměření — a hlavně o tom, odkud se ví.

    Zaměření není v číselníku, vytáhlo se z textů (`oblasti.ZAMERENI`).
    Uchazeč proto musí na kartě vidět, jestli to má doložené u oboru, jen
    z popisu školy, nebo vůbec — jinak by heuristiku četl jako fakt.
    """
    hledane = profil.hledana_zamereni
    if not hledane:
        return [f"Škola u oboru uvádí ŠVP \u201e{nab.svp}\u201c"] if nab.svp and nab.svp != nab.obor else []
    uroven = _uroven_zamereni(nab, hledane)
    if uroven == "obor":
        kde = (f"ŠVP \u201e{nab.svp}\u201c" if nab.svp and nab.svp != nab.obor
               else "v popisu oboru")
        return [f"Sedí na tvoje zaměření ({_popis_zamereni(set(nab.zamereni_kody) & hledane)}) — {kde}"]
    if uroven == "skola":
        return [f"Škola {_popis_zamereni(set(nab.zamereni_skoly) & hledane)} uvádí ve svém popisu, "
                f"ale u tohohle oboru to doložené nemáme"]
    return []       # co zaměření nesedí, patří mezi varování, ne mezi důvody


def _varovani_zamereni(nab: Nabidka, profil: Profil) -> list[str]:
    """Druhá půlka `_duvody_zamereni` — to, co mluví proti."""
    hledane = profil.hledana_zamereni
    if not hledane:
        return []
    uroven = _uroven_zamereni(nab, hledane)
    if uroven == "jine":
        return [f"Obor je podle popisu spíš {_popis_zamereni(nab.zamereni_kody)}, "
                f"ne to zaměření, které jsi vybral."]
    if uroven == "nevime":
        return ["O bližším zaměření tohohle oboru nemáme data — v pořadí je proto "
                "níž než obory, kde zaměření doložené je."]
    return []


def _varovani(nab: Nabidka, profil: Profil, p: float | None) -> list[str]:
    """Co data neříkají — stejně důležité jako důvody, proč ano."""
    out: list[str] = _varovani_zamereni(nab, profil)
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

    Vynechaný obor ale **nesmí zmizet beze stopy** — jinak se uchazeč
    nedozví, že táž škola nabízí i obor, který by chtěl víc (nebo na který
    má výrazně vyšší šanci). Zapíše se proto do `dalsi_obory` té nabídky,
    která se zobrazila. Proto se prochází celý seznam, ne jen prvních pět.
    """
    out: list[Vysledek] = []
    zobrazene: dict[str, list[Vysledek]] = {}
    for v in vysledky:
        redizo = v.nabidka.redizo
        uz_zobrazene = zobrazene.setdefault(redizo, [])
        if len(uz_zobrazene) >= max_na_skolu:
            posledni = uz_zobrazene[-1]
            if len(posledni.dalsi_obory) < 3:
                sance = "šance neznámá" if v.sance is None else f"šance {v.sance * 100:.0f} %"
                posledni.dalsi_obory.append(f"{v.nabidka.obor} ({v.nabidka.kod_kkov}, {sance})")
            continue
        if len(out) < pocet:
            uz_zobrazene.append(v)
            out.append(v)
    return out


def poznamky(profil: Profil, vysledky: list[Vysledek],
             vsechny_nabidky: list[Nabidka] | None = None) -> list[str]:
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
    doporucene = oblasti.doporucene_typy(profil.osobnostni, profil.trida)
    if doporucene and any(profil.osobnostni.values()):
        out.append("Podle odpovědí ti sedí: "
                   + ", ".join(oblasti.popis_typu(t) for t in doporucene)
                   + ". Ostatní typy se nevyřadily, jen jsou níž.")
    if not profil.talentove:
        out.append("Obory s talentovou zkouškou (umělecké, sportovní gymnázia) jsem vynechal "
                   "— mají jinou vstupní zkoušku a dřívější přihlášku. Zapni je, pokud "
                   "syn/dcera sport nebo umění dělá závodně.")
    if profil.skolne_max is not None:
        vynechane = sum(1 for n in vsechny_nabidky or ()
                        if n.skolne is None and not n.zrizovatel_verejny)
        if vynechane:
            out.append(f"{vynechane} nabídek soukromých škol jsem vynechal, protože u nich "
                       "školné v datech chybí — nešlo ověřit, že se do stropu vejdou.")
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

    # Otázky 2–4: typ vzdělání se neptá přímo, odvozuje se (viz
    # oblasti.OSOBNOSTNI_OTAZKY). Čtrnáctiletý netuší, co je „lyceum".
    osobnostni: dict[str, str | None] = {}
    for i, (klic, (otazka, varianty)) in enumerate(oblasti.OSOBNOSTNI_OTAZKY.items(), start=2):
        odpoved = _zeptej_se_vyber(
            f"{i}) {otazka}",
            [(kod, popis) for kod, (popis, _) in varianty.items()],
        )
        osobnostni[klic] = odpoved[0] if odpoved else None

    oblasti_zajmu = _zeptej_se_vyber(
        "5) Které oblasti tě baví?",
        [(k, popis) for k, (popis, _) in oblasti.OBLASTI.items()],
        vic=True,
    )

    # Doplňující otázka, ne samostatné číslo: nabízí se jen zaměření ke
    # zvoleným oblastem, takže bez odpovědi na 5) nemá co ukázat. „Baví ho
    # IT" je pořád 60 pražských nabídek od programování po herní grafiku.
    nabizena = oblasti.zamereni_oblasti(oblasti_zajmu)
    zamereni = _zeptej_se_vyber(
        "5b) A co konkrétně z toho? (Enter = nezáleží, projdeme celou oblast)",
        [(k, oblasti.ZAMERENI[k][0]) for k in nabizena],
        vic=True,
    ) if nabizena else []

    mestske_casti = _zeptej_se_vyber(
        "6) Kde bydlíte? (městská část, klidně víc)",
        [(f"Praha {i}", f"Praha {i}") for i in range(1, 23)],
        vic=True,
    )
    # Data MŠMT znají jen správní obvody Praha 1–10, lidé svoji MČ.
    obvody = sorted({oblasti.obvod(mc) for mc in mestske_casti})

    print("\n7) Jak ti vyjdou přijímačky? Zadej body z přijímaček nanečisto")
    print("   (0–50 za každý předmět, jako na skutečné JPZ; Enter = nevím).")
    body_cj = _zeptej_se_cislo("   Český jazyk [0-50]:", 50)
    body_ma = _zeptej_se_cislo("   Matematika  [0-50]:", 50)
    # CERMAT pracuje s % skórem 0–100 za předmět, uchazeč s body z 50.
    skor_cj = None if body_cj is None else body_cj / 50 * 100
    skor_ma = None if body_ma is None else body_ma / 50 * 100
    if skor_cj is not None and skor_ma is not None:
        print(f"   => {skor_cj + skor_ma:.0f} z 200 bodů % skóru")

    prospech = _zeptej_se_cislo(
        "\n8) Jaký máš průměr na vysvědčení? [1-5, Enter = přeskočit]:", 5)

    skolne = _zeptej_se_vyber(
        "9) Kolik můžete dát za školné?",
        [("0", "jen školy bez školného"),
         ("30000", "do 30 000 Kč/rok"),
         ("80000", "do 80 000 Kč/rok"),
         ("", "nerozhoduje")],
    )
    skolne_max = int(skolne[0]) if skolne and skolne[0] else None

    priority = _zeptej_se_vyber(
        "10) Co je pro tebe nejdůležitější? (vyber až 3)",
        [(k, popis) for k, (popis, _) in PRIORITY.items()],
        vic=True,
    )[:3]

    jazyk = _zeptej_se_vyber(
        "11) Chceš mít jistotu konkrétního jazyka?",
        [("N", "němčina"), ("Š", "španělština"), ("F", "francouzština"),
         ("R", "ruština"), ("I", "italština"), ("", "nezáleží")],
    )

    talentove = _zeptej_se_vyber(
        "12) Děláš sport nebo umění závodně (chodil bys na talentovky)?",
        [("", "ne"), ("ano", "ano, ukaž i obory s talentovou zkouškou")],
    )

    # Otázky 13–15: příprava. Neptáme se „jak moc se budeš snažit" — to
    # odpoví každý „hodně". Ptáme se na chování, které už běží, a na čas.
    priprava: dict[str, str | None] = {}
    for i, (klic, (otazka, varianty)) in enumerate(PRIPRAVA_OTAZKY.items(), start=13):
        odpoved = _zeptej_se_vyber(
            f"{i}) {otazka}", [(kod, popis) for kod, (popis, _) in varianty.items()])
        priprava[klic] = odpoved[0] if odpoved else None

    return Profil(
        trida=trida,
        oblasti_zajmu=oblasti_zajmu,
        zamereni=zamereni,
        obvody=obvody,
        skor_cj=skor_cj,
        skor_ma=skor_ma,
        skolne_max=skolne_max,
        jazyk=jazyk[0] if jazyk and jazyk[0] else None,
        prospech=prospech,
        priority=priority,
        talentove=bool(talentove and talentove[0]),
        priprava_ted=priprava.get("priprava_ted"),
        hodin_tydne=priprava.get("hodin_tydne"),
        kurz=priprava.get("kurz"),
        po_skole=osobnostni.get("po_skole"),
        rozhodnuto=osobnostni.get("rozhodnuto"),
        praxe=osobnostni.get("praxe"),
    )


def scenare_zlepseni(profil: Profil, nabidky: list[Nabidka],
                     kroky_bodu: tuple[float, ...] = (0, 3, 6, 10),
                     ) -> list[tuple[float, int, list[tuple[str, float | None]]]]:
    """Jak se šance mění, když se uchazeč do přijímaček zlepší.

    `kroky_bodu` jsou **body na předmět** (z 50), ne procenta skóru — rodič
    uvažuje v bodech z přijímaček nanečisto. Dřív se CLI a web v téhle
    jednotce rozcházely: stejně vypadající „+8" znamenalo v každém z nich
    něco jiného.

    Vrací pro každý krok (body na předmět, celkový % skór, [(popis, šance)]).
    """
    if profil.skor_cj is None or profil.skor_ma is None:
        return []
    out = []
    for krok in kroky_bodu:
        varianta = dataclasses.replace(profil, zlepseni_bodu=profil.zlepseni_bodu + krok)
        skor = varianta.skor
        out.append((krok, round(skor),
                    [(f"{n.organizace[:34]} ({n.kod_kkov})", sance_prijeti(n, skor)[0])
                     for n in nabidky]))
    return out


# Termíny přijímacího řízení. Datum se bere ze scrapu infoabsolventu (pole
# `terminy_jednotne_zkousky` a `prihlasky_podejte_do` u oborů) — v datech je
# ročník, pro který se zrovna scrapovalo, takže se posune na nejbližší
# budoucí výskyt téhož dne a měsíce. Ptát se uchazeče „kdy máš přijímačky"
# nemá smysl, když to víme přesně.
_DATUM = re.compile(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})")


def _nejblizsi_termin(texty: Iterable[str | None], dnes: date) -> date | None:
    """Nejčastější datum z textů, posunuté na nejbližší budoucí výskyt."""
    nalezene: list[date] = []
    for text in texty:
        if not text:
            continue
        m = _DATUM.search(text)
        if not m:
            continue
        den, mesic, rok = (int(x) for x in m.groups())
        try:
            nalezene.append(date(rok, mesic, den))
        except ValueError:
            continue
    if not nalezene:
        return None
    nejcastejsi = statistics.mode([(d.month, d.day) for d in nalezene])
    mesic, den = nejcastejsi
    for rok in (dnes.year, dnes.year + 1):
        try:
            kandidat = date(rok, mesic, den)
        except ValueError:
            continue
        if kandidat >= dnes:
            return kandidat
    return None


def terminy(nabidky: Iterable[Nabidka], dnes: date | None = None) -> dict[str, Any]:
    """Termín přihlášky, termín JPZ a kolik týdnů do nich zbývá."""
    dnes = dnes or date.today()
    nabidky = list(nabidky)
    prihlasky = _nejblizsi_termin((n.prihlasky_do for n in nabidky), dnes)
    jpz = _nejblizsi_termin((n.termin_jpz for n in nabidky), dnes)
    return {
        "dnes": dnes,
        "prihlasky_do": prihlasky,
        "jpz": jpz,
        "tydnu_do_prihlasky": None if prihlasky is None else (prihlasky - dnes).days // 7,
        "tydnu_do_jpz": None if jpz is None else (jpz - dnes).days // 7,
    }


def navrh_zlepseni(profil: Profil) -> tuple[float, str]:
    """Kolik bodů na předmět navrhnout jako výchozí polohu posuvníku.

    **Není to předpověď.** Žádná veřejná data nevážou hodiny přípravy na
    body z JPZ — soubory uchazečů CERMAT obsahují výsledek, ne přípravu.
    Je to pravidlo palce, které jen posune posuvník tam, kde ho uchazeč
    nejspíš chce mít, a vrátí k tomu větu, aby bylo vidět, na čem stojí.
    Uživatel si to má přenastavit.
    """
    slozky = [
        varianty[odpoved][1]
        for klic, (_otazka, varianty) in PRIPRAVA_OTAZKY.items()
        if (odpoved := profil.priprava.get(klic)) in varianty
    ]
    if not slozky:
        return 0.0, "Bez odpovědí na přípravu posuvník nikam neposouvám."
    miraz = statistics.mean(slozky)
    body = round(MAX_NAVRH_BODU * miraz)
    if body == 0:
        return 0.0, ("Podle odpovědí se zatím nepřipravuješ — beru dnešní body "
                     "jako výchozí. Posuvníkem si zkus, co by udělalo zlepšení.")
    return float(body), (
        f"Podle odpovědí navrhuju počítat s +{body:.0f} body v každém předmětu. "
        "Je to pravidlo palce, ne předpověď — kolik bodů příprava reálně přinese, "
        "z veřejných dat nikdo neví. Přenastav si to."
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
    if v.dalsi_obory:
        print(f"   Táž škola nabízí i: {'; '.join(v.dalsi_obory)}")
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
    hlasky = poznamky(profil, vysledky, nabidky)

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

    t = terminy(nabidky)
    if t["jpz"] or t["prihlasky_do"]:
        casti = []
        if t["prihlasky_do"]:
            casti.append(f"přihlášky do {t['prihlasky_do'].strftime('%d. %m. %Y')}"
                         f" ({t['tydnu_do_prihlasky']} týdnů)")
        if t["jpz"]:
            casti.append(f"jednotná zkouška {t['jpz'].strftime('%d. %m. %Y')}"
                         f" ({t['tydnu_do_jpz']} týdnů)")
        print("\n=== Kolik je času ===")
        print("  " + " · ".join(casti))
        print("  Termín přihlášky je ta tvrdší deadline — trojice škol musí být hotová dřív.")

    navrh, veta = navrh_zlepseni(profil)
    if veta:
        print(f"\n{veta}")
        if navrh and not profil.zlepseni_bodu:
            print(f"  (Spusť znovu s \"zlepseni_bodu\": {navrh:.0f} v profilu, "
                  "ať vidíš pětici pro ten cíl.)")

    print(f"\n=== Vyhovuje {len(vysledky)} nabídek, tady je {len(nejlepsi)} nejlepších ===")
    for h in hlasky:
        print(f"  ({h})")
    for i, v in enumerate(nejlepsi, 1):
        vypis_kartu(i, v)

    scenare = scenare_zlepseni(profil, [v.nabidka for v in nejlepsi])
    if scenare:
        print("\n=== Co udělá příprava ===")
        print("Šance u pětice výše podle toho, o kolik bodů se zlepšíš "
              "v KAŽDÉM předmětu (z 50):")
        hlavicka = " " * 40 + "".join(f"{f'+{k:.0f} b.':>10}" for k, _, _ in scenare)
        print(hlavicka)
        print(" " * 40 + "".join(f"{f'({c}/200)':>10}" for _, c, _ in scenare))
        for i, (popis, _) in enumerate(scenare[0][2]):
            radek = f"{popis[:38]:<40}"
            for _krok, _celkem, hodnoty in scenare:
                p_ = hodnoty[i][1]
                radek += f"{('—' if p_ is None else f'{p_ * 100:.0f} %'):>10}"
            print(radek)

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
