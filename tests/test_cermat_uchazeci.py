"""Testy importéru souborů uchazečů CERMAT.

Fixtura se generuje v testu přes openpyxl (stejná konvence jako
tests/test_cermat_mz.py a test_cermat_jpz.py) — žádný binární .xlsx v repu.
"""
from __future__ import annotations

import openpyxl
import pytest

from jaknastredni import cermat_uchazeci as cu
from jaknastredni import db

HLAVICKA = (
    ["rok", "kolo", "c_m_procentni_skor", "c_procentni_skor", "m_procentni_skor"]
    + [f"ss{i}_redizo" for i in range(1, 6)]
    + [f"ss{i}_zrizovatel" for i in range(1, 6)]
    + [f"ss{i}_kkov" for i in range(1, 6)]
    + [f"ss{i}_forma" for i in range(1, 6)]
    + [f"ss{i}_zkraceno" for i in range(1, 6)]
    + [f"ss{i}_prijat" for i in range(1, 6)]
    + [f"ss{i}_duvod_neprijeti" for i in range(1, 6)]
)


def _uchazec(skor, prihlasky):
    """Jeden řádek souboru: skór + seznam (redizo, kkov, forma, zkraceno, prijat, duvod)."""
    radek = {"rok": 2026, "kolo": 1, "c_m_procentni_skor": skor,
             "c_procentni_skor": None, "m_procentni_skor": None}
    for i, p in enumerate(prihlasky, 1):
        redizo, kkov, forma, zkraceno, prijat, duvod = p
        radek[f"ss{i}_redizo"] = redizo
        radek[f"ss{i}_zrizovatel"] = "7"
        radek[f"ss{i}_kkov"] = kkov
        radek[f"ss{i}_forma"] = forma
        radek[f"ss{i}_zkraceno"] = zkraceno
        radek[f"ss{i}_prijat"] = prijat
        radek[f"ss{i}_duvod_neprijeti"] = duvod
    return [radek.get(h) for h in HLAVICKA]


def _soubor(tmp_path, radky, *, hlavicka=None, nazev="PZ2026_kolo1_uchazeci_prihlasky_vysledky.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet 1"
    ws.append(hlavicka or HLAVICKA)
    for r in radky:
        ws.append(r)
    wb.create_sheet("legenda").append(["sloupec", "vysvětlivka"])
    path = tmp_path / nazev
    wb.save(path)
    return path


# --------------------------------------------------------------------------
# Pásma
# --------------------------------------------------------------------------

@pytest.mark.parametrize("skor, pasmo", [
    (0, 0), (4, 0), (5, 5), (108, 105), (154.0, 150), (200, 200),
    (None, cu.PASMO_BEZ_JPZ), ("", cu.PASMO_BEZ_JPZ), ("neco", cu.PASMO_BEZ_JPZ),
])
def test_pasmo(skor, pasmo):
    assert cu._pasmo(skor) == pasmo


def test_redizo_doplni_vedouci_nuly():
    assert cu._redizo(600006573.0) == "600006573"
    assert cu._redizo("6573") == "000006573"


# --------------------------------------------------------------------------
# Parsování
# --------------------------------------------------------------------------

def test_parse_agreguje_do_pasem(tmp_path):
    path = _soubor(tmp_path, [
        # dva uchazeči ve stejném pásmu (105) na stejný obor: jeden přijat, jeden ne
        _uchazec(108, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
        _uchazec(106, [("600000001", "79-41-K/41", "den", "2", "2", cu.DUVOD_KAPACITA)]),
        # jiné pásmo
        _uchazec(150, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
    ])
    rows = {(r["pasmo_od"]): r for r in cu.parse(path, 2026, 1)}
    assert rows[105]["prihlasek"] == 2
    assert rows[105]["prijato"] == 1
    assert rows[105]["nedostatecna_kapacita"] == 1
    assert rows[150]["prijato"] == 1
    assert all(r["rok"] == 2026 and r["kolo"] == 1 for r in rows.values())


def test_parse_pocita_vsech_pet_priorit(tmp_path):
    path = _soubor(tmp_path, [
        _uchazec(120, [
            ("600000001", "79-41-K/41", "den", "2", "2", cu.DUVOD_KAPACITA),
            ("600000002", "18-20-M/01", "den", "2", "1", None),
            ("600000003", "63-41-M/02", "den", "2", "2", cu.DUVOD_VYSSI),
        ]),
    ])
    rows = {(r["redizo"], r["kod_kkov"]): r for r in cu.parse(path, 2026, 1)}
    assert len(rows) == 3
    assert rows[("600000001", "79-41-K/41")]["nedostatecna_kapacita"] == 1
    assert rows[("600000002", "18-20-M/01")]["prijato"] == 1
    assert rows[("600000003", "63-41-M/02")]["vyssi_priorita"] == 1


def test_parse_vynecha_nedenni_a_zkracene(tmp_path):
    path = _soubor(tmp_path, [
        _uchazec(120, [
            ("600000001", "79-41-K/41", "dal", "2", "1", None),     # dálkové
            ("600000002", "18-20-M/01", "den", "1", "1", None),     # zkrácené
            ("600000003", "63-41-M/02", "den", "2", "1", None),     # tohle projde
        ]),
    ])
    rows = list(cu.parse(path, 2026, 1))
    assert [r["redizo"] for r in rows] == ["600000003"]


def test_parse_uchazec_bez_skoru_jde_do_pasma_bez_jpz(tmp_path):
    """Obory s výučním listem JPZ nekonají — 24 % uchazečů v ostrých datech."""
    path = _soubor(tmp_path, [
        _uchazec(None, [("600000004", "23-51-H/01", "den", "2", "1", None)]),
    ])
    row = next(iter(cu.parse(path, 2026, 1)))
    assert row["pasmo_od"] == cu.PASMO_BEZ_JPZ and row["prijato"] == 1


def test_parse_snese_sloupec_navic(tmp_path):
    """PZ2026 kolo 2 má oproti ostatním souborům navíc sloupec `rocnik`."""
    hlavicka = HLAVICKA + ["rocnik"]
    radek = _uchazec(120, [("600000001", "79-41-K/41", "den", "2", "1", None)]) + [9]
    path = _soubor(tmp_path, [radek], hlavicka=hlavicka)
    rows = list(cu.parse(path, 2026, 2))
    assert len(rows) == 1 and rows[0]["prijato"] == 1


def test_parse_chybejici_sloupec_spadne_srozumitelne(tmp_path):
    hlavicka = [h for h in HLAVICKA if h != "c_m_procentni_skor"]
    path = _soubor(tmp_path, [[None] * len(hlavicka)], hlavicka=hlavicka)
    with pytest.raises(ValueError, match="c_m_procentni_skor"):
        list(cu.parse(path, 2026, 1))


# --------------------------------------------------------------------------
# Import a dotaz
# --------------------------------------------------------------------------

@pytest.fixture()
def conn(tmp_path):
    c = db.connect(":memory:")
    path = _soubor(tmp_path, [
        # obor A: v pásmu 100-110 se dostal 1 ze 3, ve 150+ všichni
        _uchazec(102, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
        _uchazec(104, [("600000001", "79-41-K/41", "den", "2", "2", cu.DUVOD_KAPACITA)]),
        _uchazec(108, [("600000001", "79-41-K/41", "den", "2", "2", cu.DUVOD_PODMINKY)]),
        _uchazec(152, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
        _uchazec(154, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
        # nepřijat, protože se dostal na vyšší prioritu — do jmenovatele nepatří
        _uchazec(106, [("600000001", "79-41-K/41", "den", "2", "2", cu.DUVOD_VYSSI)]),
        # učňák bez JPZ
        _uchazec(None, [("600000004", "23-51-H/01", "den", "2", "1", None)]),
        _uchazec(None, [("600000004", "23-51-H/01", "den", "2", "2", cu.DUVOD_KAPACITA)]),
    ])
    cu.import_rows(c, cu.parse(path, 2026, 1), soubor=path, rok=2026, kolo=1)
    return c


def test_import_zapise_radky_i_import_run(conn):
    assert conn.execute("SELECT COUNT(*) FROM prijimacky_pasmo").fetchone()[0] > 0
    assert conn.execute(
        "SELECT COUNT(*) FROM import_run WHERE zdroj = 'cermat_uchazeci'").fetchone()[0] == 1


def test_import_je_idempotentni(conn, tmp_path):
    pred = conn.execute("SELECT COUNT(*) FROM prijimacky_pasmo").fetchone()[0]
    path = _soubor(tmp_path, [
        _uchazec(102, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
    ], nazev="znovu.xlsx")
    cu.import_rows(conn, cu.parse(path, 2026, 1), soubor=path, rok=2026, kolo=1)
    assert conn.execute("SELECT COUNT(*) FROM prijimacky_pasmo").fetchone()[0] == pred


def test_mira_prijeti_v_okolí_skoru(conn):
    # okno ±10 kolem 105 pokryje pásma 95-115: přijat 1, posouzeno 3
    podil, vzorek = cu.mira_prijeti(conn, "600000001", "79-41-K/41", 105)
    assert vzorek == 3 and podil == pytest.approx(1 / 3)


def test_mira_prijeti_nepocita_vyssi_prioritu(conn):
    """Kdo se dostal na vyšší prioritu, nebyl věcně posouzen."""
    _podil, vzorek = cu.mira_prijeti(conn, "600000001", "79-41-K/41", 105)
    assert vzorek == 3          # ne 4, přestože v pásmu jsou 4 přihlášky
    assert conn.execute(
        "SELECT SUM(vyssi_priorita) FROM prijimacky_pasmo WHERE pasmo_od = 105").fetchone()[0] == 1


def test_mira_prijeti_vysoke_pasmo(conn):
    podil, vzorek = cu.mira_prijeti(conn, "600000001", "79-41-K/41", 153)
    assert vzorek == 2 and podil == 1.0


def test_mira_prijeti_bez_jpz(conn):
    podil, vzorek = cu.mira_prijeti(conn, "600000004", "23-51-H/01", None)
    assert vzorek == 2 and podil == pytest.approx(0.5)


def test_mira_prijeti_bez_dat_vraci_none(conn):
    assert cu.mira_prijeti(conn, "600000001", "79-41-K/41", 10) is None
    assert cu.mira_prijeti(conn, "999999999", "79-41-K/41", 105) is None


def test_mira_prijeti_filtruje_roky(conn):
    assert cu.mira_prijeti(conn, "600000001", "79-41-K/41", 105, roky=[2026]) is not None
    assert cu.mira_prijeti(conn, "600000001", "79-41-K/41", 105, roky=[2024]) is None


def test_jen_praha_filtruje_redizo(tmp_path):
    c = db.connect(":memory:")
    path = _soubor(tmp_path, [
        _uchazec(120, [("600000001", "79-41-K/41", "den", "2", "1", None)]),
        _uchazec(120, [("600000009", "79-41-K/41", "den", "2", "1", None)]),
    ])
    stats = cu.import_rows(c, cu.parse(path, 2026, 1), soubor=path, rok=2026, kolo=1,
                           jen_redizo={"600000001"})
    assert stats["prijimacky_pasmo"] == 1
