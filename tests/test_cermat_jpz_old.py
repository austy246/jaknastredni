from pathlib import Path

import openpyxl
import pytest

from jaknastredni import cermat_jpz_old, db

FIXED_HEADER = [
    "REDIZO / KRAJ / OBOROVÁ SKUPINA", "OBOROVÁ SKUPINA", "ROČNÍK",
    "NÁZEV ŠKOLY", "ADRESA ŠKOLY", "KRAJ (KÓD)", "KRAJ (NÁZEV)", "ZŘIZOVATEL",
]

# varianta 2017/2018/2019/2021/2022/2023: jeden sloupec NEKONALI
ABSENCE_HEADER_SIMPLE = ["NEKONALI"]
# varianta 2020: tři sloupce místo jednoho (viz cermat.md, oddíl 5 a 13)
ABSENCE_HEADER_2020 = ["OMLUVENI", "NEOMLUVENI", "VYLOUČENI"]

METRIKY_HEADER = ["PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ", "SMĚRODATNÁ ODCHYLKA (PERCENTIL. UMÍSTĚNÍ)"]


def _header(variant: str) -> list[str]:
    absence = ABSENCE_HEADER_2020 if variant == "2020" else ABSENCE_HEADER_SIMPLE
    blok = ["PŘIHLÁŠENI", "KONALI"] + absence + METRIKY_HEADER
    return FIXED_HEADER + blok + blok  # ČJ blok, MA blok


def _blok(variant: str, prihlaseni, konali, percentil, odchylka, *, absence=None) -> list:
    """absence: hodnota pro NEKONALI (variant != '2020') nebo trojice
    (OMLUVENI, NEOMLUVENI, VYLOUČENI) pro variant == '2020'."""
    if variant == "2020":
        if absence is None:
            absence_vals = [0, 0, 0]
        elif isinstance(absence, (list, tuple)):
            absence_vals = list(absence)
        else:
            absence_vals = [absence, 0, 0]
    else:
        absence_vals = [absence if absence is not None else 0]
    return [prihlaseni, konali] + absence_vals + [percentil, odchylka]


def _skola_radek(variant, redizo, skupina, rocnik, nazev, cj_blok, ma_blok) -> list:
    fixed = [redizo, skupina, rocnik, nazev, f"Adresa {redizo}", "CZ010", "Hlavní město Praha", 7]
    return fixed + cj_blok + ma_blok


def _sum_radek(variant, label_first_col, skupina, rocnik, cj_blok, ma_blok) -> list:
    """Krajský/celorepublikový souhrnný řádek - první sloupec je text, ne
    číslo, a musí se při importu vyfiltrovat."""
    fixed = [label_first_col, skupina, rocnik, None, None, "CZ010", "Hlavní město Praha", None]
    return fixed + cj_blok + ma_blok


def build_workbook(path: Path, rok: int, variant: str = "simple") -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"JPZ{rok}"
    header = _header(variant)
    ws.append([f"JPZ {rok} - VÝSLEDKY ŠKOL A OBOROVÝCH SKUPIN V RÁMCI ŠKOL"] + [None] * (len(header) - 1))
    ws.append(header)

    # celorepublikový a krajský souhrnný řádek (musí se vyfiltrovat)
    ws.append(_sum_radek(variant, "4LETÉ OBORY CELKEM", "4LETÉ OBORY", 9,
                          _blok(variant, 50000, 49000, 50.0, 28.8),
                          _blok(variant, 50000, 49000, 50.0, 28.8)))
    ws.append(_sum_radek(variant, "Hlavní město Praha", "4LETÉ OBORY", 9,
                          _blok(variant, 6000, 5900, 58.0, 27.0),
                          _blok(variant, 6000, 5900, 58.0, 27.0)))

    # referenční škola (REDIZO 600006573, Obchodní akademie), obor 4LETÉ OBORY
    ws.append(_skola_radek(variant, 600006573, "4LETÉ OBORY", 9, "Obchodní akademie",
                            _blok(variant, 232, 232, 66.4, 22.6, absence=0),
                            _blok(variant, 232, 232, 66.0, 21.4, absence=0)))
    # druhá škola, jiná oborová skupina
    ws.append(_skola_radek(variant, 600012345, "GY4", 9, "Gymnázium Testovací",
                            _blok(variant, 60, 58, 55.0, 25.0, absence=2),
                            _blok(variant, 60, 58, 52.0, 24.0, absence=2)))
    # stejná škola, druhý ročník/obor (ověření klíče redizo+skupina+rocnik)
    ws.append(_skola_radek(variant, 600006573, "SEK", 9, "Obchodní akademie",
                            _blok(variant, 72, 72, 56.2, 23.9, absence=0),
                            _blok(variant, 72, 72, 58.5, 22.1, absence=0)))
    # škola bez uchazečů z matematiky -> "-" pro celý MA blok
    ws.append(_skola_radek(variant, 600099999, "NAS", 3, "Nástavbové studium",
                            _blok(variant, 10, 10, 45.0, 20.0, absence=0),
                            ["-"] * len(_blok(variant, 0, 0, 0, 0))))

    wb.create_sheet("ciselniky").append(["skupina", "nazev"])
    wb.save(path)


@pytest.fixture
def simple_file(tmp_path):
    path = tmp_path / "JPZ2017_skoly-skolobory_vysledky.xlsx"
    build_workbook(path, 2017, variant="simple")
    return path


@pytest.fixture
def variant_2020_file(tmp_path):
    path = tmp_path / "JPZ2020_skoly-skolobory_vysledky.xlsx"
    build_workbook(path, 2020, variant="2020")
    return path


def test_parse_filters_summary_rows(simple_file):
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    assert len(rows) == 4  # jen školní řádky, ne celorepublikový/krajský souhrn
    assert all(r["redizo"] in ("600006573", "600012345", "600099999") for r in rows)


def test_reference_school_values(simple_file):
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    r = next(r for r in rows if r["redizo"] == "600006573" and r["skupina_oboru"] == "4LETÉ OBORY")
    assert r["rocnik"] == 9
    assert (r["prihlaseni_cj"], r["konali_cj"]) == (232, 232)
    assert r["prumerny_percentil_cj"] == 66.4
    assert r["smerodatna_odchylka_cj"] == 22.6
    assert (r["prihlaseni_ma"], r["konali_ma"]) == (232, 232)
    assert r["prumerny_percentil_ma"] == 66.0
    assert r["rok"] == 2017


def test_key_distinguishes_skupina(simple_file):
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    skupiny = {(r["redizo"], r["skupina_oboru"]) for r in rows if r["redizo"] == "600006573"}
    assert skupiny == {("600006573", "4LETÉ OBORY"), ("600006573", "SEK")}


def test_unfilled_subject_is_null(simple_file):
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    r = next(r for r in rows if r["redizo"] == "600099999")
    assert r["prihlaseni_ma"] is None and r["konali_ma"] is None
    assert r["prumerny_percentil_ma"] is None
    # ČJ blok pro tuhle školu vyplněný je
    assert r["prihlaseni_cj"] == 10


def test_2020_absence_variant_parses_same_metrics(variant_2020_file):
    """2020 má tři sloupce absence (OMLUVENI/NEOMLUVENI/VYLOUČENI) místo
    jednoho NEKONALI - parser je nepoužívá, ale musí zvládnout mapování podle
    jména bez pádu a dát správné hodnoty přihlášení/konali/percentil."""
    rows = list(cermat_jpz_old.parse(variant_2020_file, 2020))
    assert len(rows) == 4
    r = next(r for r in rows if r["redizo"] == "600006573" and r["skupina_oboru"] == "4LETÉ OBORY")
    assert (r["prihlaseni_cj"], r["konali_cj"]) == (232, 232)
    assert r["prumerny_percentil_cj"] == 66.4
    assert r["rok"] == 2020


def test_simple_and_2020_variant_give_same_row_count(simple_file, variant_2020_file):
    rows_simple = list(cermat_jpz_old.parse(simple_file, 2017))
    rows_2020 = list(cermat_jpz_old.parse(variant_2020_file, 2020))
    assert len(rows_simple) == len(rows_2020)


def test_import_and_idempotency(simple_file):
    conn = db.connect(":memory:")
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    stats1 = cermat_jpz_old.import_rows(conn, rows, url="http://x", soubor=simple_file, rok=2017)
    assert stats1["jpz_skupina"] == len(rows)
    n_after_first = conn.execute("SELECT COUNT(*) FROM jpz_skupina").fetchone()[0]

    stats2 = cermat_jpz_old.import_rows(conn, rows, url="http://x", soubor=simple_file, rok=2017)
    n_after_second = conn.execute("SELECT COUNT(*) FROM jpz_skupina").fetchone()[0]
    assert n_after_first == n_after_second
    assert conn.execute("SELECT COUNT(*) FROM import_run WHERE zdroj = 'cermat_jpz_old'").fetchone()[0] == 2

    r = conn.execute(
        "SELECT prihlaseni_cj, konali_cj, prumerny_percentil_cj FROM jpz_skupina"
        " WHERE redizo = '600006573' AND rok = 2017 AND skupina_oboru = '4LETÉ OBORY' AND rocnik = 9"
    ).fetchone()
    assert tuple(r) == (232, 232, 66.4)


def test_jen_praha_filter(simple_file):
    conn = db.connect(":memory:")
    rows = list(cermat_jpz_old.parse(simple_file, 2017))
    cermat_jpz_old.import_rows(conn, rows, jen_redizo={"600006573"})
    redizos = {r[0] for r in conn.execute("SELECT DISTINCT redizo FROM jpz_skupina")}
    assert redizos == {"600006573"}


def test_parse_roky_range():
    assert cermat_jpz_old._parse_roky("2017-2023") == list(range(2017, 2024))
    assert cermat_jpz_old._parse_roky("2020") == [2020]
    assert cermat_jpz_old._parse_roky("2017,2020") == [2017, 2020]
