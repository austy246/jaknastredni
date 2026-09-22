from pathlib import Path

import openpyxl
import pytest

from jaknastredni import cermat_mz, db

FIXED_HEADER = [
    "TŘÍDĚNÍ", "ROK", "REDIZO", "NÁZEV ŠKOLY", "ADRESA ŠKOLY",
    "TYP ŠKOLY", "TYP ŠKOLY - NÁZEV", "SMO16", "SMO16 - NÁZEV",
    "KRAJ", "KRAJ - NÁZEV",
]
CELKEM_HEADER = ["PŘIHLÁŠENI", "KONALI", "USPĚLI", "NEUSPĚLI", "NEKONALI",
                 "PODÍL ÚSPĚŠNÝCH (%)", "ČISTÁ NEÚSPĚŠNOST (%)",
                 "HRUBÁ NEÚSPĚŠNOST (%)", "NEÚČAST (%)"]
PREDMET_HEADER = ["PŘIHLÁŠENI", "KONALI", "USPĚLI", "NEUSPĚLI", "NEKONALI",
                  "PRŮMĚRNÝ % SKÓR", "SMĚRODATNÁ ODCHYLKA % SKÓRU",
                  "PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ", "PODÍL ÚSPĚŠNÝCH (%)",
                  "ČISTÁ NEÚSPĚŠNOST (%)"]
VOLITELNY_HEADER = PREDMET_HEADER + ["PODÍL VOLBY PŘEDMĚTU (%)"]


def _header(layout: str) -> list[str]:
    prefix = ["entita_id_row", "id_row"] if layout == "new" else []
    return (prefix + FIXED_HEADER + CELKEM_HEADER + PREDMET_HEADER
            + VOLITELNY_HEADER * 6)  # MA, AJ, NJ, RJ, FJ, SJ


def _celkem(prihlaseni, konali, uspeli, neuspeli, nekonali, uspesnost, neuspesnost):
    return [prihlaseni, konali, uspeli, neuspeli, nekonali, uspesnost, neuspesnost, neuspesnost * 2, 100 - uspesnost]


def _predmet(prihlaseni, konali, uspeli, neuspeli, nekonali, skor, odchylka, percentil, uspesnost, neuspesnost):
    return [prihlaseni, konali, uspeli, neuspeli, nekonali, skor, odchylka, percentil, uspesnost, neuspesnost]


def _volitelny(*args, volba):
    return _predmet(*args) + [volba]


NIC = ["-"] * 11  # nepřihlášen nikdo (volitelný blok, 11 sloupců); pro CJ/CELKEM se prvních N použije


def _prefix(layout: str, tridebni: str, redizo: str) -> list:
    return [f"{tridebni}_{redizo}", tridebni] if layout == "new" else []


def _skola_radek(layout, tridebni, rok, redizo, nazev, smo16, smo16_nazev, blocks: dict) -> list:
    fixed = [tridebni, rok, redizo, nazev, f"Adresa {redizo}", "SS", "Střední škola",
             smo16, smo16_nazev, "CZ010", "Hlavní město Praha"]
    row = _prefix(layout, tridebni, redizo) + fixed
    for predmet, size in [("CELKEM", 9), ("CJ", 10), ("MA", 11), ("AJ", 11), ("NJ", 11), ("RJ", 11), ("FJ", 11), ("SJ", 11)]:
        vals = blocks.get(predmet, NIC[:size])
        assert len(vals) == size
        row.extend(vals)
    return row


def _sum_row(layout, tridebni, rok, label) -> list:
    """Nešolní souhrnný řádek (total/typ_skoly/kraj), který se má při importu ignorovat."""
    fixed = [tridebni, rok, "x", "x", "x", "SS", "Střední škola", label, label, "CZ010", "Praha"]
    row = _prefix(layout, tridebni, "x") + fixed
    for _predmet, size in [("CELKEM", 9), ("CJ", 10), ("MA", 11), ("AJ", 11), ("NJ", 11), ("RJ", 11), ("FJ", 11), ("SJ", 11)]:
        row.extend(NIC[:size])
    return row


def build_workbook(path: Path, rok: int, layout: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = str(rok)
    ws.append(["MATURITNÍ ZKOUŠKA - SPOLEČNÁ ČÁST - VÝSLEDKY"] + [None] * (len(_header(layout)) - 1))
    ws.append(_header(layout))

    # školní řádky za referenční školu (REDIZO 600006573)
    ws.append(_skola_radek(layout, "redizo", rok, "600006573", "Obchodní akademie", "CELKEM", "CELKEM", {
        "CELKEM": _celkem(116, 113, 111, 2, 3, 95.6896551724138, 1.76991150442478),
        "CJ": _predmet(116, 113, 112, 1, 3, 62.5, 12.1, 55.3, 99.1, 0.88),
        "MA": _volitelny(27, 26, 26, 0, 1, 58.0, 15.0, 48.0, 100.0, 0.0, volba=23.3),
        "AJ": _volitelny(89, 87, 86, 1, 2, 70.0, 10.0, 60.0, 98.9, 1.1, volba=76.7),
    }))
    ws.append(_skola_radek(layout, "redizo_smo16", rok, "600006573", "Obchodní akademie", "LYC", "LYCEUM", {
        "CELKEM": _celkem(89, 87, 86, 1, 2, 98.9, 1.1),
        "CJ": _predmet(89, 87, 87, 0, 2, 63.0, 11.5, 56.0, 100.0, 0.0),
        "MA": _volitelny(22, 22, 22, 0, 0, 60.0, 14.0, 50.0, 100.0, 0.0, volba=24.7),
        "AJ": _volitelny(67, 65, 64, 1, 2, 71.0, 9.5, 61.0, 98.5, 1.5, volba=75.3),
    }))
    ws.append(_skola_radek(layout, "redizo_smo16", rok, "600006573", "Obchodní akademie", "SEK", "SEKRETÁŘKA", {
        "CELKEM": _celkem(27, 26, 25, 1, 1, 96.2, 3.8),
    }))

    # druhá škola, pro ověření počtu řádků a filtru
    ws.append(_skola_radek(layout, "redizo", rok, "600012345", "Gymnázium Testovací", "CELKEM", "CELKEM", {
        "CELKEM": _celkem(50, 48, 45, 3, 2, 93.75, 6.25),
        "CJ": _predmet(50, 48, 47, 1, 2, 65.0, 13.0, 58.0, 97.9, 2.1),
    }))
    ws.append(_skola_radek(layout, "redizo_smo16", rok, "600012345", "Gymnázium Testovací", "GY4", "GYMNÁZIUM 4LETÉ", {
        "CELKEM": _celkem(50, 48, 45, 3, 2, 93.75, 6.25),
    }))

    # souhrnné/krajové řádky, které se mají při filtru ignorovat
    ws.append(_sum_row(layout, "total", rok, "CELKEM"))
    ws.append(_sum_row(layout, "typ_skoly", rok, "GYM"))
    ws.append(_sum_row(layout, "kraj", rok, "CZ010"))
    ws.append(_sum_row(layout, "kraj_smo16", rok, "CZ010_LYC"))

    wb.create_sheet("vysvetlivky").append(["popis", "vysvětlivka"])
    wb.save(path)


@pytest.fixture
def old_file(tmp_path):
    path = tmp_path / "MZ2017j_SC_skolobory.xlsx"
    build_workbook(path, 2017, layout="old")
    return path


@pytest.fixture
def new_file(tmp_path):
    path = tmp_path / "MZ2026j_SC_skolobory.xlsx"
    build_workbook(path, 2026, layout="new")
    return path


def test_parse_new_layout_row_counts(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    # 2 skoly: (CELKEM + LYC + SEK) * 8 predmetu + (CELKEM + GY4) * 8 predmetu
    assert len(rows) == (3 + 2) * 8
    assert all(r["redizo"] in ("600006573", "600012345") for r in rows)


def test_parse_old_layout_row_counts(old_file):
    rows = list(cermat_mz.parse(old_file, "j"))
    assert len(rows) == (3 + 2) * 8


def test_reference_school_values_new_layout(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    r = next(r for r in rows if r["redizo"] == "600006573" and r["smo16"] == "CELKEM" and r["predmet"] == "CELKEM")
    assert (r["prihlaseni"], r["konali"], r["uspeli"]) == (116, 113, 111)
    assert r["neuspeli"] == 2 and r["nekonali"] == 3
    assert r["prumerny_skor"] is None  # CELKEM blok skór nemá
    assert r["rok"] == 2026 and r["obdobi"] == "j"


def test_reference_school_values_old_layout(old_file):
    rows = list(cermat_mz.parse(old_file, "j"))
    r = next(r for r in rows if r["redizo"] == "600006573" and r["smo16"] == "CELKEM" and r["predmet"] == "CELKEM")
    assert (r["prihlaseni"], r["konali"], r["uspeli"]) == (116, 113, 111)


def test_subject_with_score_and_volba(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    ma = next(r for r in rows if r["redizo"] == "600006573" and r["smo16"] == "CELKEM" and r["predmet"] == "MA")
    assert ma["prumerny_skor"] == 58.0
    assert ma["podil_volby_predmetu"] == 23.3
    cj = next(r for r in rows if r["redizo"] == "600006573" and r["smo16"] == "CELKEM" and r["predmet"] == "CJ")
    assert cj["podil_volby_predmetu"] is None  # ČJ je povinný, nemá podíl volby


def test_unfilled_subject_is_null(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    nj = next(r for r in rows if r["redizo"] == "600006573" and r["smo16"] == "CELKEM" and r["predmet"] == "NJ")
    assert nj["prihlaseni"] is None and nj["konali"] is None


def test_summary_rows_are_excluded(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    assert all(r["redizo"] != "000000000" for r in rows)
    assert not any(r["redizo"] == "x" for r in rows)


def test_smo16_celkem_marks_whole_school_row(new_file):
    rows = list(cermat_mz.parse(new_file, "j"))
    smo16_values = {r["smo16"] for r in rows if r["redizo"] == "600006573"}
    assert smo16_values == {"CELKEM", "LYC", "SEK"}


def test_import_and_idempotency(new_file):
    conn = db.connect(":memory:")
    rows = list(cermat_mz.parse(new_file, "j"))
    stats1 = cermat_mz.import_rows(conn, rows, url="http://x", soubor=new_file, rok=2026, obdobi="j")
    assert stats1["maturita"] == len(rows)
    n_after_first = conn.execute("SELECT COUNT(*) FROM maturita").fetchone()[0]

    stats2 = cermat_mz.import_rows(conn, rows, url="http://x", soubor=new_file, rok=2026, obdobi="j")
    n_after_second = conn.execute("SELECT COUNT(*) FROM maturita").fetchone()[0]
    assert n_after_first == n_after_second
    assert conn.execute("SELECT COUNT(*) FROM import_run WHERE zdroj = 'cermat_mz'").fetchone()[0] == 2

    r = conn.execute(
        "SELECT prihlaseni, konali, uspeli FROM maturita"
        " WHERE redizo = '600006573' AND rok = 2026 AND obdobi = 'j' AND smo16 = 'CELKEM' AND predmet = 'CELKEM'"
    ).fetchone()
    assert tuple(r) == (116, 113, 111)


def test_jen_praha_filter(new_file):
    conn = db.connect(":memory:")
    rows = list(cermat_mz.parse(new_file, "j"))
    cermat_mz.import_rows(conn, rows, jen_redizo={"600006573"})
    redizos = {r[0] for r in conn.execute("SELECT DISTINCT redizo FROM maturita")}
    assert redizos == {"600006573"}


def test_parse_roky_range():
    assert cermat_mz._parse_roky("2015-2017") == [2015, 2016, 2017]
    assert cermat_mz._parse_roky("2026") == [2026]
    assert cermat_mz._parse_roky("2015,2020") == [2015, 2020]
