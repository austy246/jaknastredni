"""Export nabídek a konstant průvodce do JSON pro webový prototyp.

Webový průvodce (`web/index.html`) je statická stránka bez serveru —
potřebuje tedy data i pravidla hodnocení předpočítaná v souboru. Tenhle
skript je vytáhne z hotové databáze:

    python -m jaknastredni.export_web --db data/jaknastredni.db -o web/data.js

Výstup je JavaScript přiřazení (`window.JNS_DATA = {...}`), ne čistý JSON,
aby stránka fungovala i otevřená z disku (`file://`), kde `fetch()` na
lokální soubor prohlížeče blokují.

**Zdrojem pravdy o hodnocení zůstává `jaknastredni/pruvodce.py`.** Exportují
se proto i všechny konstanty (váhy složek, sigma, pásma portfolia, oblasti
zájmu, typy vzdělání) — stránka je čte z dat a nemá je opsané u sebe, takže
změna váhy v Pythonu se projeví i ve webu po přegenerování. Duplikovaný
v JavaScriptu zůstává jen tvar vzorce; viz `docs/pruvodce-ux.md`,
oddíl „Webový prototyp".

Soubor `web/data.js` se neverzuje (stejně jako `data/jaknastredni.db`) —
je to odvozený artefakt, viz README, „Rozhodnutí o vývoji a ukládání dat".
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from . import db, oblasti, pruvodce

log = logging.getLogger(__name__)

# Pole nabídky, která web nepotřebuje — vynechávají se, aby soubor nenabobtnal.
VYNECHAT = {"prumer_prijatych", "skola", "zdroje_profilu", "pasma"}


def nabidka_do_dictu(nab: pruvodce.Nabidka) -> dict[str, Any]:
    """Nabídka jako slovník bez prázdných a nepotřebných polí.

    Surová pásma (`pasma`) se neexportují — místo nich jde ven už
    **vyhlazená monotonní křivka** (`fit`) a celkový vzorek (`fit_n`).
    Isotonickou regresi tak nemusí umět i JavaScript: stránka jen najde
    své pásmo a smrští hodnotu k modelovému odhadu, stejně jako Python.
    Zároveň to znamená, že vyhlazení má jednu jedinou implementaci.
    """
    d = asdict(nab)
    for pole in VYNECHAT:
        d.pop(pole, None)
    # ŠVP se na kartě ukazuje jako „co se pod tím obecným kódem doopravdy
    # učí" — když se jmenuje stejně jako obor, neříká nic a jen zabírá.
    if d.get("svp") == nab.obor:
        d.pop("svp", None)
    vyhlazena = pruvodce._monotonni_pasma(nab.pasma) if nab.pasma else {}
    celkem = sum(n for _p, n in vyhlazena.values())
    if vyhlazena and celkem >= pruvodce.MIN_VZOREK:
        # Ke každému pásmu jde i jeho vzorek: bez něj web nemá z čeho spočítat
        # „kolik uchazečů s podobným skórem" (okolí ±OKNO_PASMA) a musel by
        # místo toho hlásit celkový vzorek nabídky — tedy jiné číslo, než
        # ukáže `pruvodce.py` na tomtéž profilu.
        # Šest desetinných míst, ne čtyři: při čtyřech se podíl lišil od
        # Pythonu až o 5e-5, což se přes smrštění a `min(1, p/0,4)` roztáhlo
        # na 2e-3 bodu skóre — dost na to, aby si web se dvěma skoro
        # vyrovnanými nabídkami prohodil pořadí. Stojí to ~30 kB.
        d["fit"] = {str(pasmo): [round(podil, 6), n] for pasmo, (podil, n) in sorted(vyhlazena.items())}
        d["fit_n"] = celkem
    # Obory bez jednotné zkoušky. Podíl se **váží roky** (`ROKY_JPZ`), takže
    # ho nejde poskládat z holých součtů — musí ven spočítaný. Bere se
    # rovnou z `_empiricka_sance`, ať má vážení jednu implementaci; dokud si
    # ho JavaScript počítal z totálů sám, lišil se web od Pythonu až o 7
    # procentních bodů šance (SPŠE Ječná, elektrotechnika: 0,33 vs 0,40).
    emp = pruvodce._empiricka_sance(nab, None) if nab.pasma else None
    if emp is not None:
        podil, prijato, posouzeno, _celkem = emp
        d["bez_jpz"] = [prijato, posouzeno, round(podil, 6)]
        d["bez_jpz_prevazuje"] = pruvodce._prevazuje_bez_jpz(nab)
    return {k: v for k, v in d.items() if not _prazdne(v)}


def _prazdne(v: Any) -> bool:
    """Má se pole vynechat z exportu?

    Past: v Pythonu je ``0 == False``, takže ``v not in (..., False)``
    zahodí i **nulu**. U školného to znamenalo, že soukromá škola s nulovým
    školným přišla v JSONu o údaj, web ho četl jako „neznámé" a školu
    vyřadil z filtru na cenu — deset nabídek navíc oproti Pythonu.
    Test na False musí být identitou, ne rovností.
    """
    return v is None or v is False or (isinstance(v, (str, tuple, list, dict)) and len(v) == 0)


def export(conn) -> dict[str, Any]:
    """Data pro webový prototyp: nabídky + všechny konstanty hodnocení."""
    nabidky = pruvodce.nacti_nabidky(conn)
    return {
        # Datum generování patří na stránku: nasazená verze může být týdny
        # stará a uchazeč nemá jak poznat, jestli čte letošní, nebo loňská data.
        "vygenerovano": date.today().strftime("%-d. %-m. %Y"),
        "nabidky": [nabidka_do_dictu(n) for n in nabidky],
        "konstanty": {
            "roky_jpz": pruvodce.ROKY_JPZ,
            "sigma_zaklad": pruvodce.SIGMA_ZAKLAD,
            "sigma_jeden_rok": pruvodce.SIGMA_JEDEN_ROK,
            "sigma_max": pruvodce.SIGMA_MAX,
            "smrsteni": pruvodce.SMRSTENI,
            "shoda_zamereni": pruvodce.SHODA_ZAMERENI,
            "min_vzorek": pruvodce.MIN_VZOREK,
            "okno_pasma": pruvodce.OKNO_PASMA,
            "max_navrh_bodu": pruvodce.MAX_NAVRH_BODU,
            "slozky_skore": pruvodce.SLOZKY_SKORE,
            "parametry": pruvodce.PARAMETRY,
            "omez": list(pruvodce.OMEZ),
            "sance_z_poptavky": pruvodce.SANCE_Z_POPTAVKY,
            "zajem_pridana_oblast": pruvodce.ZAJEM_PRIDANA_OBLAST,
            "rezerva_zvolenych": pruvodce.REZERVA_ZVOLENYCH,
            "pocet_doporucenych": pruvodce.POCET_DOPORUCENYCH,
            "rezerva_oblasti": pruvodce.REZERVA_OBLASTI,
            "vaha_podilu_zamereni": oblasti.VAHA_PODILU_ZAMERENI,
            "sirka_rozhodnuto": oblasti.SIRKA_ROZHODNUTO,
            "sirka_otevreno": oblasti.SIRKA_OTEVRENO,
            "prah_siroky_vyber": oblasti.PRAH_SIROKY_VYBER,
            "priority": {k: {"popis": p, "slozka": s} for k, (p, s) in pruvodce.PRIORITY.items()},
            "pasma_portfolia": pruvodce.PASMA_PORTFOLIA,
        },
        "priprava": {
            klic: {"otazka": otazka,
                   "varianty": {kod: {"popis": popis, "mira": mira}
                                for kod, (popis, mira) in varianty.items()}}
            for klic, (otazka, varianty) in pruvodce.PRIPRAVA_OTAZKY.items()
        },
        "terminy": {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in pruvodce.terminy(nabidky).items()},
        "osobnostni": {
            klic: {"otazka": otazka,
                   "varianty": {kod: {"popis": popis, "typy": typy}
                                for kod, (popis, typy) in varianty.items()}}
            for klic, (otazka, varianty) in oblasti.OSOBNOSTNI_OTAZKY.items()
        },
        "ciselniky": {
            "oblasti": {k: {"popis": p, "skupiny": list(s)} for k, (p, s) in oblasti.OBLASTI.items()},
            # Bez regulárních výrazů: zaměření se rozpoznávají při exportu
            # (`Nabidka.zamereni_kody`), stránka už dostává hotové kódy
            # a potřebuje jen popisek a to, u které oblasti se na ně ptát.
            "zamereni": {k: {"popis": p, "oblasti": list(o)}
                         for k, (p, o, _vzor) in oblasti.ZAMERENI.items()},
            "typy": {k: {"popis": p, "trida": t, "maturita": m} for k, (p, t, m) in oblasti.TYPY.items()},
            "skupiny": oblasti.SKUPINY,
            "sousedni_obvody": {k: list(v) for k, v in oblasti.SOUSEDNI_OBVODY.items()},
            "mc_na_obvod": oblasti.MC_NA_OBVOD,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/jaknastredni.db", help="cesta k databázi")
    ap.add_argument("-o", "--out", default="web/data.js", help="výstupní soubor")
    ap.add_argument("--json", action="store_true", help="čistý JSON místo window.JNS_DATA = …")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    cesta = Path(args.db)
    if not cesta.exists():
        print(f"Databáze {cesta} neexistuje — spusť nejdřív: python -m jaknastredni.build_db",
              file=sys.stderr)
        return 2

    conn = db.connect(cesta)
    try:
        data = export(conn)
    finally:
        conn.close()

    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if not args.json:
        text = f"window.JNS_DATA = {text};\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    log.info("%s: %d nabídek, %.0f kB", out, len(data["nabidky"]), len(text.encode("utf-8")) / 1024)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
