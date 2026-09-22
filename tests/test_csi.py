from pathlib import Path

import pytest

from jaknastredni import csi, db

HEADER = "REDIZO,Jmeno,DatumOd,DatumDo,LinkIZ,PortalLink\r\n"

# Referenční škola (stejná jako v ostatních testech/README), s běžnou inspekcí.
ROW_OK = (
    '"600006573","Obchodní akademie, Praha 10, Heroldovy sady 1",'
    '"2017-10-03T00:00:00.0000000","2017-10-06T23:59:59.9990000",'
    '"https://portal.csicr.cz/Files/Get/739cc2311d474c6e9541fb02a8ddf665",'
    '"https://portal.csicr.cz/School/600006573"\r\n'
)
# Druhá škola, mimo Prahu (pro test --jen-praha).
ROW_MIMO_PRAHU = (
    '"600140849","Základní škola Tršice","2016-06-07T00:00:00.0000000",'
    '"2016-07-14T23:59:59.9990000",'
    '"https://portal.csicr.cz/Files/Get/06466373b7d949f6af7b9519fb12bd9e",'
    '"https://portal.csicr.cz/School/600140849"\r\n'
)
# REDIZO kratší než 9 znaků, jak přichází z jiných zdrojů (msmt/cermat_mz mají
# stejnou konvenci doplnění nulami zleva).
ROW_REDIZO_KRATSI = (
    '"691007667","Mateřská škola Myšičky","2016-07-11T00:00:00.0000000",'
    '"2016-07-12T23:59:59.9990000",'
    '"https://portal.csicr.cz/Files/Get/fa58715c889645e2be4800d094312e98",'
    '"https://portal.csicr.cz/School/691007667"\r\n'
)
# Chybějící DatumDo (edge case zmíněný v zadání) - platný záznam, jen bez konce.
ROW_BEZ_DATUM_DO = (
    '"600012345","Škola bez konce inspekce","2020-01-15T00:00:00.0000000",'
    '"",'
    '"https://portal.csicr.cz/Files/Get/aaaa",'
    '"https://portal.csicr.cz/School/600012345"\r\n'
)
# Sentinelové "navěky platné" DatumDo (2203/3000) - technický artefakt ČŠI.
ROW_SENTINEL_DATUM_DO = (
    '"600000273","Soukromá mateřská škola "" KORÁLEK "", spol. s r.o.",'
    '"2003-05-21T00:00:00.0000000","2203-05-22T00:00:00.0000000",'
    '"https://portal.csicr.cz/Files/Get/A9FCD1C0?db=Archive",'
    '"https://portal.csicr.cz/School/600000273"\r\n'
)
# Neúplný/rozbitý řádek - prázdné REDIZO, musí se přeskočit, ne spadnout.
ROW_BEZ_REDIZO = (
    '"","Nejaká škola bez REDIZO","2019-01-01T00:00:00.0000000",'
    '"2019-01-03T00:00:00.0000000","https://portal.csicr.cz/Files/Get/bbbb",'
    '"https://portal.csicr.cz/School/x"\r\n'
)
# Nesmyslné/nevalidní DatumOd - musí se přeskočit (je součástí primárního klíče).
ROW_SPATNY_DATUM_OD = (
    '"600099999","Další škola","neni-datum","2019-01-03T00:00:00.0000000",'
    '"https://portal.csicr.cz/Files/Get/cccc","https://portal.csicr.cz/School/x"\r\n'
)

CSV_TEXT = (
    HEADER + ROW_OK + ROW_MIMO_PRAHU + ROW_REDIZO_KRATSI + ROW_BEZ_DATUM_DO
    + ROW_SENTINEL_DATUM_DO + ROW_BEZ_REDIZO + ROW_SPATNY_DATUM_OD
)


@pytest.fixture
def csv_file(tmp_path) -> Path:
    path = tmp_path / "inspekcni_zpravy-2026-09-22.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def test_parse_valid_rows_and_skip_stats(csv_file):
    stats: dict[str, int] = {}
    rows = list(csi.parse(csv_file, stats=stats))
    # 5 platných řádků (OK, mimo Prahu, kratší REDIZO, bez DatumDo, sentinel);
    # 2 přeskočené (bez REDIZO, špatné DatumOd).
    assert len(rows) == 5
    assert stats == {"celkem": 7, "preskoceno": 2}


def test_redizo_normalized_to_nine_digits(csv_file):
    rows = list(csi.parse(csv_file))
    r = next(r for r in rows if r["nazev"].startswith("Mateřská škola Myšičky"))
    assert r["redizo"] == "691007667"
    assert len(r["redizo"]) == 9


def test_reference_school_row(csv_file):
    rows = list(csi.parse(csv_file))
    r = next(r for r in rows if r["redizo"] == "600006573")
    assert r["nazev"] == "Obchodní akademie, Praha 10, Heroldovy sady 1"
    assert r["datum_od"] == "2017-10-03"
    assert r["datum_do"] == "2017-10-06"
    assert r["pdf_url"] == "https://portal.csicr.cz/Files/Get/739cc2311d474c6e9541fb02a8ddf665"
    assert r["portal_url"] == "https://portal.csicr.cz/School/600006573"


def test_missing_datum_do_is_null(csv_file):
    rows = list(csi.parse(csv_file))
    r = next(r for r in rows if r["redizo"] == "600012345")
    assert r["datum_od"] == "2020-01-15"
    assert r["datum_do"] is None


def test_sentinel_datum_do_becomes_null(csv_file):
    rows = list(csi.parse(csv_file))
    r = next(r for r in rows if r["redizo"] == "600000273")
    assert r["datum_od"] == "2003-05-21"
    assert r["datum_do"] is None  # 2203 je technický artefakt, ne skutečné datum
    assert "KORÁLEK" in r["nazev"]  # zdvojené uvozovky v CSV se správně rozbalí


def test_rows_without_redizo_or_bad_date_are_skipped(csv_file):
    rows = list(csi.parse(csv_file))
    assert all(r["redizo"] != "" for r in rows)
    assert not any(r["redizo"] == "600099999" for r in rows)


def test_missing_columns_raise():
    with pytest.raises(ValueError):
        list(csi.parse("REDIZO,Jmeno\r\n1,2\r\n"))


def test_import_and_idempotency(csv_file):
    conn = db.connect(":memory:")
    stats: dict[str, int] = {}
    rows = list(csi.parse(csv_file, stats=stats))

    result1 = csi.import_rows(conn, rows, url="http://x", soubor=csv_file, preskoceno=stats["preskoceno"])
    assert result1["inspekce"] == 5
    n_after_first = conn.execute("SELECT COUNT(*) FROM inspekce").fetchone()[0]
    assert n_after_first == 5

    result2 = csi.import_rows(conn, rows, url="http://x", soubor=csv_file, preskoceno=stats["preskoceno"])
    n_after_second = conn.execute("SELECT COUNT(*) FROM inspekce").fetchone()[0]
    assert result2["inspekce"] == 5
    assert n_after_second == n_after_first  # idempotentní, ne duplicitní řádky

    assert conn.execute("SELECT COUNT(*) FROM import_run WHERE zdroj = 'csi'").fetchone()[0] == 2

    r = conn.execute(
        "SELECT nazev, datum_do, pdf_url FROM inspekce WHERE redizo = '600006573' AND datum_od = '2017-10-03'"
    ).fetchone()
    assert r["nazev"] == "Obchodní akademie, Praha 10, Heroldovy sady 1"
    assert r["datum_do"] == "2017-10-06"


def test_jen_praha_filter(csv_file):
    conn = db.connect(":memory:")
    conn.execute(
        "INSERT INTO organizace (redizo, nazev, aktualizovano) VALUES ('600006573', 'Obchodní akademie', '2026-09-22')"
    )
    rows = list(csi.parse(csv_file))
    csi.import_rows(conn, rows, jen_redizo={"600006573"})
    redizos = {r[0] for r in conn.execute("SELECT DISTINCT redizo FROM inspekce")}
    assert redizos == {"600006573"}
