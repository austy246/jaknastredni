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
    vyhlazena = pruvodce._monotonni_pasma(nab.pasma) if nab.pasma else {}
    celkem = sum(n for _p, n in vyhlazena.values())
    if vyhlazena and celkem >= pruvodce.MIN_VZOREK:
        d["fit"] = {str(pasmo): round(podil, 4) for pasmo, (podil, _n) in sorted(vyhlazena.items())}
        d["fit_n"] = celkem
    bez_jpz = nab.pasma.get(pruvodce.PASMO_BEZ_JPZ) if nab.pasma else None
    if bez_jpz:
        prijato = sum(p for p, _n in bez_jpz.values())
        posouzeno = sum(n for _p, n in bez_jpz.values())
        if posouzeno:
            d["bez_jpz"] = [prijato, posouzeno]
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
        "nabidky": [nabidka_do_dictu(n) for n in nabidky],
        "konstanty": {
            "roky_jpz": pruvodce.ROKY_JPZ,
            "sigma_zaklad": pruvodce.SIGMA_ZAKLAD,
            "sigma_jeden_rok": pruvodce.SIGMA_JEDEN_ROK,
            "sigma_max": pruvodce.SIGMA_MAX,
            "smrsteni": pruvodce.SMRSTENI,
            "min_vzorek": pruvodce.MIN_VZOREK,
            "okno_pasma": pruvodce.OKNO_PASMA,
            "max_navrh_bodu": pruvodce.MAX_NAVRH_BODU,
            "slozky_skore": pruvodce.SLOZKY_SKORE,
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
