import csv
import shutil
from pathlib import Path

from jaknastredni import build_db, db

MSMT_FIXTURE = Path(__file__).parent / "fixtures" / "rssz-praha-vzorek.jsonld"


def test_nejnovejsi_picks_lexicographically_last(tmp_path):
    for name in ["a-2025-01-01.jsonld", "a-2026-09-22.jsonld", "a-2020-05-01.jsonld"]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    latest = build_db._nejnovejsi(tmp_path.glob("*.jsonld"))
    assert latest.name == "a-2026-09-22.jsonld"


def test_nejnovejsi_empty_returns_none(tmp_path):
    assert build_db._nejnovejsi(tmp_path.glob("*.jsonld")) is None


def test_build_msmt_from_local_fixture(tmp_path):
    raw_dir = tmp_path / "raw"
    (raw_dir / "msmt").mkdir(parents=True)
    shutil.copy(MSMT_FIXTURE, raw_dir / "msmt" / "RSSZ-Hl-m-Praha-2026-09-22.jsonld")

    conn = db.connect(":memory:")
    build_db._build_msmt(conn, raw_dir)
    assert conn.execute("SELECT COUNT(*) FROM organizace").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM import_run WHERE zdroj = 'msmt'").fetchone()[0] == 1


def test_build_csi_from_local_csv(tmp_path):
    raw_dir = tmp_path / "raw"
    csi_dir = raw_dir / "csi"
    csi_dir.mkdir(parents=True)
    path = csi_dir / "inspekcni_zpravy-2026-09-22.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["REDIZO", "Jmeno", "DatumOd", "DatumDo", "LinkIZ", "PortalLink"])
        w.writerow(["600006573", "Obchodní akademie", "2020-01-01T00:00:00.0000000",
                    "2020-01-10T00:00:00.0000000", "https://example.cz/a.pdf", "https://example.cz/a"])

    conn = db.connect(":memory:")
    build_db._build_csi(conn, raw_dir)
    assert conn.execute("SELECT COUNT(*) FROM inspekce").fetchone()[0] == 1
    row = conn.execute("SELECT * FROM inspekce WHERE redizo = '600006573'").fetchone()
    assert row["nazev"] == "Obchodní akademie"


def test_build_all_skips_missing_sources_without_error(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    conn = db.connect(":memory:")
    build_db.build_all(conn, raw_dir)  # nesmí spadnout, i když je data/raw/ prázdné
    for table in ("organizace", "maturita", "jpz_skupina", "prijimaci_rizeni", "inspekce", "web_profil"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
