"""Testy průvodce výběrem školy.

Fixtura je malá umělá databáze (4 školy, 5 nabídek — IT obor se dělí na dvě
zaměření, takže průvodce jich vidí 5) poskládaná ze stejných
tabulek jako ostrá databáze — testy tedy nepotřebují `data/jaknastredni.db`
ani syrová data. Čísla jsou vymyšlená, ale ve tvaru, v jakém je ukládají
importéry (% skór 0–200, REDIZO jako text s vedoucí nulou, školné v Kč).
"""
from __future__ import annotations

import json

import pytest

from jaknastredni import db, export_web, oblasti, pruvodce


# --------------------------------------------------------------------------
# oblasti.py — odvození typu a oblasti z kódu KKOV
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kod, typ, trida",
    [
        ("79-41-K/81", "G8", 5),
        ("79-41-K/61", "G6", 7),
        ("79-41-K/41", "G4", 9),
        ("78-42-M/02", "LYC", 9),      # lyceum je M, ale skupina 78 => vlastní typ
        ("18-20-M/01", "M", 9),
        ("23-45-L/01", "L0", 9),
        ("64-41-L/51", "L5", 0),       # nástavba - ne pro žáka ZŠ
        ("23-51-H/01", "H", 9),
        ("41-52-E/01", "E", 9),
    ],
)
def test_typ_a_trida_z_kkov(kod, typ, trida):
    assert oblasti.typ_oboru(kod) == typ
    assert oblasti.trida_prihlasky(oblasti.typ_oboru(kod)) == trida


def test_obor_muze_byt_ve_vic_oblastech():
    # Elektrotechnika (26) je IT i technika - filtr ji má najít pod obojím.
    assert set(oblasti.oblasti_oboru("26-41-M/01")) >= {"it", "technika"}


def test_neznamy_kod_nespadne():
    assert oblasti.typ_oboru("nesmysl") is None
    assert oblasti.oblasti_oboru("99-99-M/01") == ()


# --------------------------------------------------------------------------
# Fixtura databáze
# --------------------------------------------------------------------------

def _skola(conn, redizo, izo, nazev, obvod, zrizovatel="7"):
    conn.execute(
        "INSERT INTO organizace (redizo, nazev, obvod_prahy, ulice, typ_zrizovatele, aktualizovano)"
        " VALUES (?,?,?,?,?,'2026-09-22')",
        (redizo, nazev, obvod, "Testovací 1", zrizovatel),
    )
    conn.execute(
        "INSERT INTO skola (izo, redizo, nazev, druh, aktualizovano)"
        " VALUES (?,?,?,'C00','2026-09-22')",
        (izo, redizo, nazev),
    )


def _obor(conn, izo, kod, nazev):
    conn.execute(
        "INSERT INTO obor (izo, kod_kkov, nazev, forma, dobihajici) VALUES (?,?,?,'10',0)",
        (izo, kod, nazev),
    )


def _pz(conn, izo, redizo, kod, rok, *, kapacita, prihlasky, prijati, hranice=None,
        zamereni="", poptavka=None, forma="den", delka="4", jazyk="CJ"):
    conn.execute(
        """INSERT INTO prijimaci_rizeni
           (izo, kod_kkov, rocnik, rok, kolo, zamereni_oboru, forma_vzdelavani,
            delka_studia, jazyk_studia, redizo, kapacita, index_poptavky,
            prihlasky_celkem, prijati, skor_prijati_min_cjma)
           VALUES (?,?,9,?,1,?,?,?,?,?,?,?,?,?,?)""",
        (izo, kod, rok, zamereni, forma, delka, jazyk, redizo, kapacita,
         poptavka if poptavka is not None else prihlasky / kapacita,
         prihlasky, prijati, hranice),
    )


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    # 1) Gymnázium, velmi žádané, stabilní vysoká hranice.
    _skola(c, "600000001", "100000001", "Gymnázium Testovací", "Praha 6")
    _obor(c, "100000001", "79-41-K/41", "Gymnázium")
    for rok, hranice in ((2024, 150.0), (2025, 156.0), (2026, 154.0)):
        _pz(c, "100000001", "600000001", "79-41-K/41", rok,
            kapacita=30, prihlasky=400, prijati=30, hranice=hranice)
    # 2) Průmyslovka s IT oborem, dostupná, dvě zaměření v jednom KKOV —
    #    průvodce z nich udělá dvě samostatné nabídky (viz `_rozdel_na_zamereni`).
    _skola(c, "600000002", "100000002", "SPŠ Testovací", "Praha 9")
    _obor(c, "100000002", "18-20-M/01", "Informační technologie")
    _pz(c, "100000002", "600000002", "18-20-M/01", 2026, zamereni="programování",
        kapacita=60, prihlasky=120, prijati=60, hranice=100.0)
    _pz(c, "100000002", "600000002", "18-20-M/01", 2026, zamereni="sítě",
        kapacita=10, prihlasky=20, prijati=10, hranice=60.0)
    # 3) Soukromé gymnázium se školným, málo přihlášek.
    _skola(c, "600000003", "100000003", "Soukromé gymnázium", "Praha 4", zrizovatel="5")
    _obor(c, "100000003", "79-41-K/41", "Gymnázium")
    _pz(c, "100000003", "600000003", "79-41-K/41", 2026,
        kapacita=30, prihlasky=24, prijati=24, hranice=None, poptavka=0.8)
    c.execute(
        "INSERT INTO web_profil (redizo, zdroj, stazeno, data) VALUES (?,?,?,?)",
        ("600000003", "infoabsolvent", "2026-09-22", json.dumps({
            "velikost_skoly": "SŠ 101 - 150 žáků",
            "cizi_jazyky": "anglický (A), německý (N)",
            "obory": [{
                "kod_kkov": "79-41-K/41", "forma_studia": "Denní",
                "skolne_rocne": 90000, "letos_plan_prijmout": 30,
                "pocet_povinnych_jazyku": 2, "vyucovane_jazyky": "A, N",
                "prijimaci_rizeni": {
                    # Past scrapovaných dat: "nekoná se" je pravdivý řetězec.
                    "talentova_zkouska": "nekoná se",
                    "ustni_zkouska": "pohovor",
                    "jina_kriteria_prijimani": "body za prospěch",
                },
            }],
        }, ensure_ascii=False)),
    )
    # 4) Učňovský obor bez JPZ - šance se nedá odhadnout z CERMAT.
    _skola(c, "600000004", "100000004", "SOU Testovací", "Praha 10")
    _obor(c, "100000004", "23-51-H/01", "Strojní mechanik")
    c.commit()
    return c


# --------------------------------------------------------------------------
# Načtení nabídek
# --------------------------------------------------------------------------

def test_nacti_nabidky_zaklad(conn):
    nabidky = {(n.izo, n.kod_kkov, n.zamereni_nazev): n for n in pruvodce.nacti_nabidky(conn)}
    assert len(nabidky) == 5      # 4 obory, z toho IT ve dvou zaměřeních
    gympl = nabidky[("100000001", "79-41-K/41", "")]
    assert gympl.typ == "G4" and gympl.trida_prihlasky == 9
    assert gympl.hranice == {2024: 150.0, 2025: 156.0, 2026: 154.0}
    assert gympl.obvody == ("Praha 6",)
    assert gympl.zrizovatel_verejny is True


def test_zamereni_je_samostatna_nabidka(conn):
    """Dřív se z hranic 100 a 60 počítal vážený průměr 94 — a platil pro obojí."""
    it = {n.zamereni_nazev: n for n in pruvodce.nacti_nabidky(conn)
          if n.kod_kkov == "18-20-M/01"}
    assert set(it) == {"programování", "sítě"}
    assert it["programování"].hranice[2026] == 100.0
    assert it["sítě"].hranice[2026] == 60.0
    # Kapacita a přihlášky se taky nesčítají přes zaměření.
    assert (it["programování"].kapacita, it["programování"].prijati) == (60, 60)
    assert (it["sítě"].kapacita, it["sítě"].prijati) == (10, 10)
    # Na kartě se obor od sesterského pozná jen podle zaměření.
    assert it["sítě"].obor_plny == "Informační technologie — sítě"


def test_co_rozlisit_nejde_se_porad_sleva(conn):
    """Co klíč nerozliší (tady jazyk studia), musí se slít jako dřív.

    V pražské denní nabídce už taková dvojice není, ale kód na ni pořád
    musí být připravený — jinak by jeden z řádků tiše zmizel.
    """
    _pz(conn, "100000001", "600000001", "79-41-K/41", 2026, jazyk="AJ",
        kapacita=10, prihlasky=30, prijati=10, hranice=60.0)
    conn.commit()
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    # (154*30 + 60*10) / 40 = 130.5 — vážený průměr podle přijatých, ne minimum.
    assert gympl.hranice[2026] == pytest.approx((154 * 30 + 60 * 10) / 40, abs=0.1)


def test_jina_nez_denni_forma_do_hranice_nepatri(conn):
    """Regrese: dálkové studium má jinou hranici a mísilo se do denní.

    Českoslovanská akademie má pod `63-41-M/02` denní hranici 108 a dálkovou
    40; SŠ gastronomická u `65-42-M/01` denní 108 a kombinovanou 14. Průvodce
    je pro žáky ZŠ, tedy o denním studiu — nedenní řádky do něj nepatří.
    """
    _pz(conn, "100000001", "600000001", "79-41-K/41", 2026, forma="dal", delka="5",
        kapacita=30, prihlasky=30, prijati=10, hranice=40.0)
    conn.commit()
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    assert gympl.hranice[2026] == 154.0        # ne vážený průměr se 40
    assert gympl.kapacita == 30


def test_zamereni_pobocky_mimo_prahu_se_vyradi(conn):
    """PORG vede třídy v Brně a Ostravě pod pražským IZO — do pětice nepatří."""
    conn.execute(
        "INSERT INTO misto_vyuky (izo, id_mista, obec, obvod_prahy) VALUES (?,?,?,NULL)",
        ("100000001", "m1", "Brno"),
    )
    _pz(conn, "100000001", "600000001", "79-41-K/41", 2026, zamereni="8leté PORG Brno",
        kapacita=26, prihlasky=30, prijati=26, hranice=80.0)
    _pz(conn, "100000001", "600000001", "79-41-K/41", 2026, zamereni="Praha 4",
        kapacita=26, prihlasky=90, prijati=26, hranice=150.0)
    conn.commit()
    zamereni = {n.zamereni_nazev for n in pruvodce.nacti_nabidky(conn)
                if n.redizo == "600000001"}
    assert "8leté PORG Brno" not in zamereni
    assert "Praha 4" in zamereni


def test_nekona_se_neni_talentovka(conn):
    """Regrese: `"nekoná se"` je neprázdný řetězec, takže pravdivý."""
    soukrome = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000003")
    assert soukrome.talentova_zkouska is False
    assert soukrome.skolni_zkousky == ("ústní zkouška (pohovor)",)
    assert soukrome.skolne == 90000
    assert soukrome.velikost_skoly == 125


def test_kapacita_je_z_cermat_ne_z_rejstriku(conn):
    """`obor.kapacita` z rejstříku je celková, ne letošní nábor — nesmí se použít."""
    conn.execute("UPDATE obor SET kapacita = 999 WHERE izo = '100000001'")
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    assert gympl.kapacita == 30


# --------------------------------------------------------------------------
# Šance na přijetí
# --------------------------------------------------------------------------

def test_sance_roste_se_skorem(conn):
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    slaby, _ = pruvodce.sance_prijeti(gympl, 100.0)
    tak_tak, _ = pruvodce.sance_prijeti(gympl, 154.0)
    silny, _ = pruvodce.sance_prijeti(gympl, 190.0)
    assert slaby < 0.15 < tak_tak < 0.85 < silny
    # Uchazeč přesně na hranici má zhruba 50 % — škola si přidává vlastní body.
    assert tak_tak == pytest.approx(0.5, abs=0.1)


def test_sance_nikdy_neni_jistota(conn):
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    assert pruvodce.sance_prijeti(gympl, 200.0)[0] <= 0.97
    assert pruvodce.sance_prijeti(gympl, 0.0)[0] >= 0.03


def test_sance_z_poptavky_kdyz_chybi_hranice(conn):
    soukrome = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000003")
    p, zdroj = pruvodce.sance_prijeti(soukrome, 120.0)
    assert p > 0.8 and "poměru přihlášek" in zdroj


def test_sance_bez_dat_je_none(conn):
    ucnak = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000004")
    p, zdroj = pruvodce.sance_prijeti(ucnak, 120.0)
    assert p is None and zdroj


def test_bez_skoru_se_pouzije_poptavka(conn):
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    p, zdroj = pruvodce.sance_prijeti(gympl, None)
    assert p is not None and "poměru přihlášek" in zdroj


# --------------------------------------------------------------------------
# Filtry a skóre
# --------------------------------------------------------------------------

def test_filtr_tridy(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    # Z 5. třídy (osmiletá gymnázia) v téhle fixtuře není nic.
    assert pruvodce.ohodnot(pruvodce.Profil(trida=5), nabidky) == []
    assert len(pruvodce.ohodnot(pruvodce.Profil(trida=9), nabidky)) == 5


def test_filtr_skolneho(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    zdarma = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=0), nabidky)
    assert all(v.nabidka.redizo != "600000003" for v in zdarma)
    s_penezi = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=100000), nabidky)
    assert any(v.nabidka.redizo == "600000003" for v in s_penezi)


def test_filtr_oblasti(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    it = pruvodce.ohodnot(pruvodce.Profil(trida=9, oblasti_zajmu=["it"]), nabidky)
    assert [v.nabidka.kod_kkov for v in it] == ["18-20-M/01", "18-20-M/01"]
    assert {v.nabidka.zamereni_nazev for v in it} == {"programování", "sítě"}


def test_jazyk_vazi_ale_nefiltruje(conn):
    """Jazyk vyhazoval třetinu nabídky — nově jen zvýhodní školu, která ho učí."""
    nabidky = pruvodce.nacti_nabidky(conn)
    bez = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=100000), nabidky)
    s_nemcinou = pruvodce.ohodnot(
        pruvodce.Profil(trida=9, jazyk="N", skolne_max=100000), nabidky)
    assert len(s_nemcinou) == len(bez)        # nic se nevyhodilo
    uci = next(v for v in s_nemcinou if v.nabidka.redizo == "600000003")
    neuci = next(v for v in s_nemcinou if v.nabidka.redizo == "600000001")
    assert uci.slozky["jazyk"] == 1.0 and neuci.slozky["jazyk"] < 0.5
    # Kdo na jazyku trvá, zapne si tvrdý filtr.
    povinne = pruvodce.ohodnot(
        pruvodce.Profil(trida=9, jazyk="N", jazyk_povinny=True, skolne_max=100000), nabidky)
    assert [v.nabidka.redizo for v in povinne] == ["600000003"]


def test_priorita_zvysi_vahu_sve_slozky(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    bez = pruvodce._vahy_profilu(pruvodce.Profil(trida=9))
    s_blizkosti = pruvodce._vahy_profilu(pruvodce.Profil(trida=9, priority=["blizkost"]))
    assert s_blizkosti["blizkost"] == 2 * bez["blizkost"]
    # Víc než 3 priority se ignoruje.
    prehnane = pruvodce._vahy_profilu(
        pruvodce.Profil(trida=9, priority=["blizkost", "cena", "kvalita", "jistota"])
    )
    assert prehnane["dosazitelnost"] == bez["dosazitelnost"]


def test_blizkost_preferuje_zvoleny_obvod(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    profil = pruvodce.Profil(trida=9, obvody=["Praha 9"], priority=["blizkost"], skolne_max=0)
    poradi = pruvodce.ohodnot(profil, nabidky)
    assert poradi[0].nabidka.obvody == ("Praha 9",)
    assert poradi[0].slozky["blizkost"] == 1.0


def test_vysledek_nese_duvody_i_varovani(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    v = pruvodce.ohodnot(
        pruvodce.Profil(trida=9, oblasti_zajmu=["vseobecne"], skolne_max=100000), nabidky
    )
    soukrome = next(x for x in v if x.nabidka.redizo == "600000003")
    assert any("Školné" in d for d in soukrome.duvody)
    assert any("hranici přijetí" in w for w in soukrome.varovani)


# --------------------------------------------------------------------------
# Výběr pětice a portfolia
# --------------------------------------------------------------------------

def test_vyber_top_neopakuje_skolu(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    # Druhý obor na téže škole (stejné REDIZO) se do pětice nedostane dvakrát.
    _obor(conn, "100000002", "26-41-M/01", "Elektrotechnika")
    conn.commit()
    vysledky = pruvodce.ohodnot(pruvodce.Profil(trida=9), pruvodce.nacti_nabidky(conn))
    top = pruvodce.vyber_top(vysledky, pocet=5, max_na_skolu=1)
    assert len({v.nabidka.redizo for v in top}) == len(top)


def test_portfolio_rozlozi_riziko(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    profil = pruvodce.Profil(trida=9, skor_cj=70, skor_ma=70, skolne_max=100000)
    trojice = pruvodce.portfolio(pruvodce.ohodnot(profil, nabidky))
    assert set(trojice) == {"sen", "realisticka", "jistota"}
    # Se skórem 140 je gymnázium (hranice ~154) sen a soukromé gymnázium jistota.
    assert trojice["sen"] is not None and trojice["sen"].nabidka.redizo == "600000001"
    assert trojice["jistota"] is not None
    assert trojice["jistota"].sance >= 0.82
    # Táž nabídka nesmí figurovat ve dvou rolích.
    vybrane = [v.nabidka.izo for v in trojice.values() if v]
    assert len(vybrane) == len(set(vybrane))


def test_poznamky_hlasi_nesplnene_prani(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    profil = pruvodce.Profil(trida=9, obvody=["Praha 1"], skor_cj=50, skor_ma=50)
    hlasky = pruvodce.poznamky(profil, pruvodce.ohodnot(profil, nabidky))
    assert any("Praha 1" in h for h in hlasky)


def test_profil_z_json_odmitne_nezname_pole():
    with pytest.raises(ValueError, match="neznámá pole"):
        pruvodce.Profil.z_json({"trida": 9, "vyska": 180})


# --------------------------------------------------------------------------
# Školy zřízené pro žáky se zdravotním postižením
# --------------------------------------------------------------------------

def test_skoly_pro_zp_se_bez_vyzadani_nenabizeji(conn):
    _skola(conn, "600000005", "100000005", "Střední škola pro sluchově postižené", "Praha 5")
    _obor(conn, "100000005", "23-51-H/01", "Strojní mechanik")
    _obor(conn, "100000004", "78-62-C/02", "Praktická škola dvouletá")
    conn.commit()
    nabidky = pruvodce.nacti_nabidky(conn)
    assert any(n.jen_pro_zp for n in nabidky)

    bezne = pruvodce.ohodnot(pruvodce.Profil(trida=9), nabidky)
    assert all(not v.nabidka.jen_pro_zp for v in bezne)
    assert all(v.nabidka.typ != "C" for v in bezne)

    s_podporou = pruvodce.ohodnot(
        pruvodce.Profil(trida=9, specialni_potreby=True), nabidky
    )
    assert any(v.nabidka.jen_pro_zp for v in s_podporou)


def test_portfolio_nedava_tri_prihlasky_na_jednu_skolu(conn):
    # Druhý, snáz dostupný obor téže školy, aby padl do jiného pásma šance.
    _obor(conn, "100000001", "78-42-M/02", "Lyceum")
    _pz(conn, "100000001", "600000001", "78-42-M/02", 2026,
        kapacita=30, prihlasky=40, prijati=30, hranice=60.0)
    conn.commit()
    profil = pruvodce.Profil(trida=9, oblasti_zajmu=["vseobecne"], skor_cj=75, skor_ma=75)
    trojice = pruvodce.portfolio(pruvodce.ohodnot(profil, pruvodce.nacti_nabidky(conn)))
    redizo = [v.nabidka.redizo for v in trojice.values() if v]
    assert len(redizo) == len(set(redizo))


# --------------------------------------------------------------------------
# Export pro webový prototyp
# --------------------------------------------------------------------------

def test_export_nezahodi_nulove_skolne(conn):
    """Regrese: v Pythonu je `0 == False`, takže test na prázdnotu zahodil nulu.

    Soukromá škola s nulovým školným pak v JSONu údaj neměla, web ho četl
    jako „neznámé" a vyřadil ji z filtru na cenu — 10 nabídek rozdílu proti
    Pythonu, přičemž obě strany počítaly „správně".
    """
    from jaknastredni import export_web

    conn.execute("UPDATE organizace SET typ_zrizovatele = '5' WHERE redizo = '600000002'")
    conn.commit()
    nabidka = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000002")
    nabidka.skolne = 0
    assert export_web.nabidka_do_dictu(nabidka)["skolne"] == 0
    # Prázdné hodnoty se vynechat mají, False taky.
    assert not export_web._prazdne(0)
    assert export_web._prazdne(None) and export_web._prazdne(False)
    assert export_web._prazdne("") and export_web._prazdne([]) and export_web._prazdne({})


def test_export_web_nese_nabidky_i_konstanty(conn):
    from jaknastredni import export_web

    data = export_web.export(conn)
    assert len(data["nabidky"]) == 5
    # Web nemá mít konstanty opsané u sebe — čte je z exportu.
    assert data["konstanty"]["slozky_skore"] == pruvodce.SLOZKY_SKORE
    assert data["konstanty"]["sigma_zaklad"] == pruvodce.SIGMA_ZAKLAD
    assert set(data["ciselniky"]["oblasti"]) == set(oblasti.OBLASTI)
    # Prázdná pole se vynechávají, ať soubor zbytečně neroste.
    ucnak = next(n for n in data["nabidky"] if n["redizo"] == "600000004")
    assert "hranice" not in ucnak and "skolne" not in ucnak
    assert ucnak["kod_kkov"] == "23-51-H/01"


# --------------------------------------------------------------------------
# Napojení druhého zdroje (Atlas školství)
# --------------------------------------------------------------------------

ATLAS_PROFIL = {
    # Atlas pojmenovává pole podle svého webu: "dny_" místo "den_",
    # "planovany_pocet_prijmout" místo "letos_plan_prijmout".
    "dny_otevrenych_dveri": "5. 11. 2025, 4. 2. 2026",
    "cizi_jazyky": "anglický, německý",
    "obory": [{
        "nazev_oboru": "Strojní mechanik",
        "kod_kkov": "23-51-H/01",
        "typ_ukonceni": "Výuční list",
        "delka_studia": "3 roky",
        # Atlas u oboru NEMÁ forma_studia — nesmí ho to vyřadit.
        "planovany_pocet_prijmout": 24,
        "loni_prihlaseni": 40,
        "loni_prijati": 20,          # skutečně přijatí, ne plán
        "doporuceny_prospech": 2.5,
        "plp": True,
        "ozp": False,
        "skolne_rocne": 0,
    }],
}


def _atlas(conn, redizo, profil=None):
    conn.execute(
        "INSERT INTO web_profil (redizo, zdroj, stazeno, data) VALUES (?,'atlas','2026-09-22',?)",
        (redizo, json.dumps(profil or ATLAS_PROFIL, ensure_ascii=False)),
    )
    conn.commit()


def test_atlas_doplni_pole_ktera_infoabsolvent_nema(conn):
    _atlas(conn, "600000004")
    ucnak = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000004")
    assert ucnak.zdroje_profilu == ("atlas",)
    assert ucnak.doporuceny_prospech == 2.5
    assert ucnak.loni_prijati == 20 and ucnak.loni_prihlaseni == 40
    assert ucnak.lekarska_prohlidka is True
    # Aliasy názvů klíčů mezi zdroji.
    assert ucnak.plan_prijmout == 24
    assert ucnak.dod == "5. 11. 2025, 4. 2. 2026"


def test_atlas_neprepise_hodnoty_z_infoabsolventu(conn):
    """Vyhrává první zdroj v PORADI_ZDROJU, ať SQL vrátí řádky v jakémkoli pořadí."""
    _atlas(conn, "600000003", {
        "dny_otevrenych_dveri": "atlasový termín",
        "obory": [{"kod_kkov": "79-41-K/41", "skolne_rocne": 11111,
                   "planovany_pocet_prijmout": 99, "doporuceny_prospech": 1.5}],
    })
    soukrome = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000003")
    assert soukrome.skolne == 90000          # z infoabsolventu, ne 11111
    assert soukrome.plan_prijmout == 30      # z infoabsolventu, ne 99
    assert soukrome.doporuceny_prospech == 1.5   # tohle má jen Atlas
    assert set(soukrome.zdroje_profilu) == {"infoabsolvent", "atlas"}


def test_prospech_horsi_nez_doporuceny_srazi_skore_a_varuje(conn):
    _atlas(conn, "600000004")
    nabidky = pruvodce.nacti_nabidky(conn)
    dobry = pruvodce.ohodnot(pruvodce.Profil(trida=9, prospech=2.0), nabidky)
    spatny = pruvodce.ohodnot(pruvodce.Profil(trida=9, prospech=4.0), nabidky)

    def najdi(vysledky):
        return next(v for v in vysledky if v.nabidka.redizo == "600000004")

    assert najdi(spatny).slozky["dosazitelnost"] < najdi(dobry).slozky["dosazitelnost"]
    assert any("doporučuje průměr" in w for w in najdi(spatny).varovani)
    assert any("vyhovuje doporučenému prospěchu" in d for d in najdi(dobry).duvody)
    assert any("potvrzení od lékaře" in w for w in najdi(dobry).varovani)


def test_sance_z_atlasu_kdyz_obor_nema_jpz(conn):
    """Obor bez CERMAT dat dostane šanci z loňského poměru přihlášek ku PŘIJATÝM."""
    _atlas(conn, "600000004")
    ucnak = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000004")
    assert not ucnak.hranice and not ucnak.poptavka
    p, zdroj = pruvodce.sance_prijeti(ucnak, 120.0)
    assert p is not None and "loni přijatých" in zdroj
    # 40/20 = 2.0x -> pásmo 60 %, ne 92 % jako kdyby se počítalo z plánu 24.
    assert p == pytest.approx(0.6, abs=0.01)


# --------------------------------------------------------------------------
# Empirická šance, talentovky, sourozenecké obory, školné
# --------------------------------------------------------------------------

def _pasmo(conn, redizo, kkov, rok, pasmo_od, prijato, kapacita_ne=0, podminky_ne=0, vyssi=0):
    conn.execute(
        """INSERT OR REPLACE INTO prijimacky_pasmo
           (redizo, kod_kkov, rok, kolo, pasmo_od, prihlasek, prijato,
            nedostatecna_kapacita, nesplneni_podminek, vyssi_priorita, vzdal_se)
           VALUES (?,?,?,1,?,?,?,?,?,?,0)""",
        (redizo, kkov, rok, pasmo_od,
         prijato + kapacita_ne + podminky_ne + vyssi, prijato, kapacita_ne, podminky_ne, vyssi),
    )
    conn.commit()


def test_empiricka_sance_prebije_odhad_z_hranice(conn):
    """Naměřený podíl je přednostní zdroj — model z hranice je optimistický."""
    for rok in (2024, 2025, 2026):
        _pasmo(conn, "600000001", "79-41-K/41", rok, 150, prijato=0, kapacita_ne=8)
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    assert gympl.pasma[150][2026] == (0, 8)
    p, zdroj = pruvodce.sance_prijeti(gympl, 154.0)
    assert "naměřeno" in zdroj
    # Model sám by dal ~50 % (uchazeč přesně na hranici), naměřeno 0 z 24.
    assert p < 0.2


def test_empiricka_sance_se_smrsti_u_maleho_vzorku(conn):
    """Vzorek pod MIN_VZOREK se nepoužije, i kdyby vypadal jednoznačně."""
    _pasmo(conn, "600000001", "79-41-K/41", 2026, 150, prijato=0, kapacita_ne=3)
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    _p, zdroj = pruvodce.sance_prijeti(gympl, 154.0)
    assert "naměřeno" not in zdroj and "hranice přijetí" in zdroj


def test_novejsi_rok_vazi_vic(conn):
    """Škola, která loni brala mnohem snáz, nesmí být tažena dolů rokem 2024."""
    _pasmo(conn, "600000001", "79-41-K/41", 2024, 150, prijato=0, kapacita_ne=20)
    _pasmo(conn, "600000001", "79-41-K/41", 2026, 150, prijato=20, kapacita_ne=0)
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    p, _ = pruvodce.sance_prijeti(gympl, 152.0)
    assert p > 0.5          # nevážený průměr by dal 0,5; 2026 váží 3×, 2024 1×


def test_talentovky_se_bez_vyzadani_nenabizeji(conn):
    conn.execute(
        "INSERT INTO web_profil (redizo, zdroj, stazeno, data) VALUES (?,?,?,?)",
        ("600000002", "infoabsolvent", "2026-09-22", json.dumps({
            "obory": [{"kod_kkov": "18-20-M/01", "forma_studia": "Denní",
                       "prijimaci_rizeni": {"talentova_zkouska": "hra na nástroj"}}],
        }, ensure_ascii=False)),
    )
    conn.commit()
    nabidky = pruvodce.nacti_nabidky(conn)
    assert any(n.talentova_zkouska for n in nabidky)
    bezne = pruvodce.ohodnot(pruvodce.Profil(trida=9), nabidky)
    assert all(not v.nabidka.talentova_zkouska for v in bezne)
    s_talentem = pruvodce.ohodnot(pruvodce.Profil(trida=9, talentove=True), nabidky)
    assert any(v.nabidka.talentova_zkouska for v in s_talentem)


def test_vyber_top_hlasi_dalsi_obory_teze_skoly(conn):
    """Vynechaný obor nesmí zmizet beze stopy — patří jako poznámka ke kartě."""
    _obor(conn, "100000001", "78-42-M/02", "Lyceum")
    _pz(conn, "100000001", "600000001", "78-42-M/02", 2026,
        kapacita=30, prihlasky=40, prijati=30, hranice=60.0)
    conn.commit()
    vysledky = pruvodce.ohodnot(pruvodce.Profil(trida=9), pruvodce.nacti_nabidky(conn))
    top = pruvodce.vyber_top(vysledky, pocet=5, max_na_skolu=1)
    gympl = next(v for v in top if v.nabidka.redizo == "600000001")
    assert any("78-42-M/02" in d or "79-41-K/41" in d for d in gympl.dalsi_obory)


def test_chybejici_skolne_u_soukrome_skoly_neprojde_stropem(conn):
    """Regrese: neuvedené školné se nesmí brát jako nula."""
    conn.execute("UPDATE organizace SET typ_zrizovatele = '5' WHERE redizo = '600000004'")
    conn.commit()
    nabidky = pruvodce.nacti_nabidky(conn)
    soukroma = next(n for n in nabidky if n.redizo == "600000004")
    assert soukroma.skolne is None and not soukroma.zrizovatel_verejny
    levne = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=30000), nabidky)
    assert all(v.nabidka.redizo != "600000004" for v in levne)
    # Veřejná škola bez uvedeného školného projít smí — kraj školné nevybírá.
    verejna = next(n for n in nabidky if n.redizo == "600000001")
    assert verejna.skolne is None and verejna.zrizovatel_verejny
    assert any(v.nabidka.redizo == "600000001" for v in levne)


# --------------------------------------------------------------------------
# Odvození typu z osobnostních otázek
# --------------------------------------------------------------------------

def test_typ_se_odvodi_z_osobnostnich_otazek():
    akademik = oblasti.preference_typu(
        {"po_skole": "vysoka", "rozhodnuto": "otevreno", "praxe": "teorie"})
    remeslnik = oblasti.preference_typu(
        {"po_skole": "prace", "rozhodnuto": "obor", "praxe": "hodne"})
    assert akademik["G4"] > akademik["H"]
    assert remeslnik["H"] > remeslnik["G4"]
    assert oblasti.doporucene_typy(
        {"po_skole": "prace", "rozhodnuto": "obor", "praxe": "hodne"})[0] == "H"


def test_bez_odpovedi_je_preference_neutralni():
    assert set(oblasti.preference_typu({}).values()) == {0.5}
    assert oblasti.preference_typu({"po_skole": "nesmysl"}) == oblasti.preference_typu({})


def test_preference_typu_meni_poradi(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    remeslnik = pruvodce.Profil(trida=9, po_skole="prace", rozhodnuto="obor", praxe="hodne")
    akademik = pruvodce.Profil(trida=9, po_skole="vysoka", rozhodnuto="otevreno", praxe="teorie")
    ucnak_u_remeslnika = next(v for v in pruvodce.ohodnot(remeslnik, nabidky)
                              if v.nabidka.typ == "H")
    ucnak_u_akademika = next(v for v in pruvodce.ohodnot(akademik, nabidky)
                             if v.nabidka.typ == "H")
    assert ucnak_u_remeslnika.slozky["typ"] > ucnak_u_akademika.slozky["typ"]


def test_mestska_cast_se_prelozi_na_spravni_obvod():
    """Lidé znají svoji MČ (Praha 12), data mají jen správní obvody 1–10."""
    assert oblasti.obvod("Praha 12") == "Praha 4"
    assert oblasti.obvod("Praha 22") == "Praha 10"
    assert oblasti.obvod("Praha 6") == "Praha 6"
    assert oblasti.obvod("neznámo") == "neznámo"
    # Mapa sousednosti nesmí obsahovat obvody, které v datech neexistují.
    v_datech = set(oblasti.MC_NA_OBVOD.values())
    for sousedi in oblasti.SOUSEDNI_OBVODY.values():
        assert set(sousedi) <= v_datech


def test_scenare_zlepseni(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    # Gymnázium má hranici ~154 b.; ze 120 na 160 je vidět skok přes ni.
    profil = pruvodce.Profil(trida=9, skor_cj=60, skor_ma=60)
    gympl = [n for n in nabidky if n.redizo == "600000001"]
    scenare = pruvodce.scenare_zlepseni(profil, gympl, kroky_bodu=(0, 10))
    assert [k for k, _, _ in scenare] == [0, 10]
    # +10 bodů v každém předmětu z 50 = +20 % skóru v každém = +40 celkem.
    assert scenare[1][1] == 160
    assert scenare[1][2][0][1] > scenare[0][2][0][1]    # lepší skór = vyšší šance
    # Bez zadaného skóru nemá scénář co počítat.
    assert pruvodce.scenare_zlepseni(pruvodce.Profil(trida=9), gympl) == []


def test_zlepseni_se_pocita_v_bodech_na_predmet(conn):
    """CLI i web musí „+5 bodů" chápat stejně: na předmět, do obou."""
    p = pruvodce.Profil(trida=9, skor_cj=38, skor_ma=70)
    assert p.skor == 108
    p.zlepseni_bodu = 5
    assert p.skor == 128            # +10 % skóru v každém předmětu
    # Strop 50 bodů na předmět se nepřekročí.
    p2 = pruvodce.Profil(trida=9, skor_cj=96, skor_ma=96, zlepseni_bodu=20)
    assert p2.skor == 200


def test_terminy_se_pocitaji_z_dat(conn):
    """Kdy jsou přijímačky víme z dat — ptát se na to nemá smysl."""
    from datetime import date

    nabidky = pruvodce.nacti_nabidky(conn)
    for n in nabidky:
        n.prihlasky_do, n.termin_jpz = "20.2.2026", "10. 4. 2026 a 13. 4. 2026"
    t = pruvodce.terminy(nabidky, date(2026, 9, 22))
    # Termín z dat je v minulosti -> posune se na nejbližší budoucí výskyt.
    assert t["prihlasky_do"] == date(2027, 2, 20)
    assert t["jpz"] == date(2027, 4, 10)
    assert t["tydnu_do_jpz"] == 28 and t["tydnu_do_prihlasky"] == 21
    # Bez dat se nic nevymýšlí.
    for n in nabidky:
        n.prihlasky_do = n.termin_jpz = None
    assert pruvodce.terminy(nabidky, date(2026, 9, 22))["jpz"] is None


def test_navrh_zlepseni_je_pravidlo_palce_ne_predpoved(conn):
    lenoch = pruvodce.Profil(trida=9, priprava_ted="ne", hodin_tydne="do1", kurz="ne")
    drtic = pruvodce.Profil(trida=9, priprava_ted="pravidelne", hodin_tydne="4az6", kurz="ano")
    assert pruvodce.navrh_zlepseni(lenoch)[0] < pruvodce.navrh_zlepseni(drtic)[0]
    # Bez odpovědí se posuvník nikam neposouvá.
    assert pruvodce.navrh_zlepseni(pruvodce.Profil(trida=9)) == (
        0.0, "Bez odpovědí na přípravu posuvník nikam neposouvám.")
    # Text musí přiznat, že to není předpověď.
    assert "předpověď" in pruvodce.navrh_zlepseni(drtic)[1]


def test_sance_nikdy_neklesa_se_skorem(conn):
    """Víc bodů nesmí nikdy znamenat menší šanci.

    Regrese: naměřená data jsou po pásmech rozkolísaná (v pásmu o osmi
    lidech rozhodne jeden) a odhad navíc přepínal mezi metodami podle toho,
    kolik dat bylo zrovna kolem uchazečova skóru. Na obojím vznikaly skoky
    typu „se 170 body 95 %, se 180 body 52 %". Řeší to isotonická regrese
    (`_monotonni_pasma`) plus rozhodnutí o metodě jednou za nabídku.
    """
    # Rozkolísaná data: pásmo 130 je „lepší" než 140, vzorky jsou malé.
    for pasmo, prijato, ne in [(110, 0, 9), (120, 2, 8), (130, 7, 8),
                               (140, 3, 9), (150, 8, 9), (160, 9, 9)]:
        _pasmo(conn, "600000001", "79-41-K/41", 2026, pasmo, prijato=prijato, kapacita_ne=ne)
    gympl = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000001")
    sance = [pruvodce.sance_prijeti(gympl, s)[0] for s in range(0, 201, 5)]
    assert all(a <= b + 1e-9 for a, b in zip(sance, sance[1:])), sance


def test_vyhlazeni_slije_porusujici_pasma(conn):
    pasma = {110: {2026: (0, 10)}, 120: {2026: (8, 10)}, 130: {2026: (2, 10)}}
    vyhlazena = pruvodce._monotonni_pasma(pasma)
    hodnoty = [vyhlazena[p][0] for p in sorted(vyhlazena)]
    assert hodnoty == sorted(hodnoty)
    # 120 a 130 se slijí do jednoho bloku: (8+2)/(10+10) = 0,5.
    assert vyhlazena[120][0] == pytest.approx(0.5)
    assert vyhlazena[130][0] == pytest.approx(0.5)


def test_obor_bez_jpz_ignoruje_skor(conn):
    """U učňovských oborů rozhoduje něco jiného než jednotná zkouška."""
    _pasmo(conn, "600000004", "23-51-H/01", 2026, pruvodce.PASMO_BEZ_JPZ,
           prijato=40, kapacita_ne=10)
    _pasmo(conn, "600000004", "23-51-H/01", 2026, 80, prijato=1, kapacita_ne=0)
    ucnak = next(n for n in pruvodce.nacti_nabidky(conn) if n.redizo == "600000004")
    assert pruvodce._prevazuje_bez_jpz(ucnak)
    assert (pruvodce.sance_prijeti(ucnak, 80)[0]
            == pytest.approx(pruvodce.sance_prijeti(ucnak, 180)[0]))


# --------------------------------------------------------------------------
# Zaměření uvnitř oboru (oblasti.ZAMERENI)
# --------------------------------------------------------------------------

def test_zamereni_se_najde_v_nazvu_svp_i_v_popisu_skoly():
    assert "programovani" in oblasti.zamereni_textu("Programování a digitální technologie")
    assert "site" in oblasti.zamereni_textu(
        "správce serverových služeb operačních systémů a počítačových sítí")
    assert oblasti.zamereni_textu(None, "") == ()


def test_nabidnou_se_jen_zamereni_ke_zvolenym_oblastem():
    nabizena = oblasti.zamereni_oblasti(["gastro"])
    assert "gastronomie" in nabizena
    assert "programovani" not in nabizena
    assert oblasti.zamereni_oblasti([]) == ()


def _s_popisem(conn, redizo, kod, *, svp=None, popis_skoly=None):
    """Doplní ke škole webový profil s názvem ŠVP a/nebo popisem školy."""
    conn.execute(
        "INSERT INTO web_profil (redizo, zdroj, stazeno, data) VALUES (?,?,?,?)",
        (redizo, "atlas", "2026-09-22", json.dumps({
            "doplnujici_informace": popis_skoly,
            "obory": [{"kod_kkov": kod, "svp_nazev": svp}],
        }, ensure_ascii=False)),
    )
    conn.commit()


def test_zamereni_doložené_u_oboru_je_silnejsi_nez_z_popisu_skoly(conn):
    # Obě školy mají tentýž kód KKOV, ale učí pod ním něco jiného: jedna to
    # má v názvu ŠVP, druhá jen ve volném popisu školy. Přesně tak se liší
    # SPŠE Ječná ("Programování a digitální technologie") od SPŠE V Úžlabině.
    _skola(conn, "600000005", "100000005", "SPŠ S ŠVP", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01", svp="Programování a digitální technologie")
    _skola(conn, "600000006", "100000006", "SPŠ S popisem", "Praha 9")
    _obor(conn, "100000006", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000006", "18-20-M/01",
               popis_skoly="Žáci se učí spravovat počítačové sítě a programovat.")

    podle_izo = {n.izo: n for n in pruvodce.nacti_nabidky(conn)}
    s_svp, s_popisem = podle_izo["100000005"], podle_izo["100000006"]
    assert s_svp.zamereni_kody == ("programovani",)
    assert "programovani" in s_popisem.zamereni_skoly
    assert s_popisem.zamereni_kody == ()

    profil = pruvodce.Profil(oblasti_zajmu=["it"], zamereni=["programovani"])
    assert (pruvodce._skore_zajem(s_svp, profil)
            > pruvodce._skore_zajem(s_popisem, profil))


def test_jine_dolozene_zamereni_srazi_skore_nejvic(conn):
    _skola(conn, "600000005", "100000005", "SPŠ Programátorská", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01", svp="Programování a vývoj aplikací")
    # Tentýž obor, ale nic bližšího o něm nevíme: obecný název KKOV na žádné
    # zaměření nesedí a webový profil škola nemá.
    _skola(conn, "600000007", "100000007", "SPŠ Bez popisu", "Praha 9")
    _obor(conn, "100000007", "18-20-M/01", "Informační technologie")
    podle_izo = {n.izo: n for n in pruvodce.nacti_nabidky(conn)}
    nab, bez_dat = podle_izo["100000005"], podle_izo["100000007"]
    assert bez_dat.zamereni_kody == () and bez_dat.zamereni_skoly == ()

    profil = pruvodce.Profil(oblasti_zajmu=["it"], zamereni=["grafika"])
    assert pruvodce._skore_zajem(nab, profil) < pruvodce._skore_zajem(bez_dat, profil)


def test_bez_zvoleneho_zamereni_se_skore_zajmu_nemeni(conn):
    _skola(conn, "600000005", "100000005", "SPŠ Programátorská", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01", svp="Programování a vývoj aplikací")
    nab = {n.izo: n for n in pruvodce.nacti_nabidky(conn)}["100000005"]
    assert pruvodce._skore_zajem(nab, pruvodce.Profil(oblasti_zajmu=["it"])) == 1.0


def test_zamereni_mimo_zvolene_oblasti_se_ignoruje(conn):
    """Profil složený ručně může mít zaměření k oblasti, kterou uchazeč nezvolil."""
    _skola(conn, "600000005", "100000005", "SPŠ Programátorská", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01", svp="Programování a vývoj aplikací")
    nab = {n.izo: n for n in pruvodce.nacti_nabidky(conn)}["100000005"]
    profil = pruvodce.Profil(oblasti_zajmu=["it"], zamereni=["gastronomie"])
    assert profil.hledana_zamereni == set()
    assert pruvodce._skore_zajem(nab, profil) == 1.0


def test_duvod_rekne_odkud_se_zamereni_vi(conn):
    _skola(conn, "600000005", "100000005", "SPŠ S popisem", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01",
               popis_skoly="Studenti spravují počítačové sítě a servery.")
    nab = {n.izo: n for n in pruvodce.nacti_nabidky(conn)}["100000005"]
    profil = pruvodce.Profil(oblasti_zajmu=["it"], zamereni=["site"])
    duvody = pruvodce._duvody_zamereni(nab, profil)
    assert any("doložené nemáme" in d for d in duvody), duvody
    # Co zaměření nesedí, patří mezi varování, ne mezi důvody.
    jiny = pruvodce.Profil(oblasti_zajmu=["it"], zamereni=["gastronomie", "grafika"])
    assert pruvodce._duvody_zamereni(nab, jiny) == []
    assert any("nemáme data" in v for v in pruvodce._varovani_zamereni(nab, jiny))


def test_export_nese_zamereni_i_ciselnik(conn):
    _skola(conn, "600000005", "100000005", "SPŠ S ŠVP", "Praha 9")
    _obor(conn, "100000005", "18-20-M/01", "Informační technologie")
    _s_popisem(conn, "600000005", "18-20-M/01", svp="Programování a digitální technologie")
    data = export_web.export(conn)
    podle_izo = {n["izo"]: n for n in data["nabidky"]}
    assert podle_izo["100000005"]["zamereni_kody"] == ("programovani",)
    assert podle_izo["100000005"]["svp"] == "Programování a digitální technologie"
    # Regulární výrazy na web nepatří, popisky a oblasti ano.
    ciselnik = data["ciselniky"]["zamereni"]
    assert set(ciselnik["programovani"]) == {"popis", "oblasti"}
    assert data["konstanty"]["shoda_zamereni"]["obor"] == 1.0


def test_export_vynecha_svp_shodne_s_nazvem_oboru(conn):
    _skola(conn, "600000005", "100000005", "Gymnázium Bez ŠVP", "Praha 9")
    _obor(conn, "100000005", "79-41-K/41", "Gymnázium")
    _s_popisem(conn, "600000005", "79-41-K/41", svp="Gymnázium")
    podle_izo = {n["izo"]: n for n in export_web.export(conn)["nabidky"]}
    assert "svp" not in podle_izo["100000005"]


def test_obor_plny_neopakuje_nazev_ani_kod(conn):
    """Zaměření bývá jen opis názvu oboru, občas i s kódem KKOV před ním."""
    def nab(zamereni):
        return pruvodce.Nabidka(
            izo="1", redizo="6", skola="S", organizace="S", kod_kkov="79-41-K/41",
            obor="Gymnázium", typ="G4", trida_prihlasky=9, obvody=(), adresa="",
            zrizovatel_verejny=True, zamereni_nazev=zamereni)
    assert nab("").obor_plny == "Gymnázium"
    assert nab("Gymnázium").obor_plny == "Gymnázium"
    assert nab("79-41-K/81 Gymnázium").obor_plny == "Gymnázium"
    assert nab("79-41-K/81").obor_plny == "Gymnázium"
    assert nab("Výtvarná výchova").obor_plny == "Gymnázium — Výtvarná výchova"


def test_sdilena_namerena_krivka_se_prizna(conn):
    """Pásma jsou klíčovaná REDIZO+KKOV, zaměření v nich není — karta to řekne."""
    for pasmo, prijato, celkem in ((100, 5, 20), (150, 15, 20)):
        conn.execute(
            "INSERT INTO prijimacky_pasmo (redizo, kod_kkov, rok, kolo, pasmo_od,"
            " prihlasek, prijato, nedostatecna_kapacita, nesplneni_podminek,"
            " vyssi_priorita, vzdal_se) VALUES ('600000002','18-20-M/01',2026,1,?,?,?,?,0,0,0)",
            (pasmo, celkem, prijato, celkem - prijato),
        )
    conn.commit()
    it = {n.zamereni_nazev: n for n in pruvodce.nacti_nabidky(conn)
          if n.kod_kkov == "18-20-M/01"}
    assert it["sítě"].pasma_sdileno == 2
    profil = pruvodce.Profil(trida=9, skor_cj=75.0, skor_ma=75.0)
    v = next(v for v in pruvodce.ohodnot(profil, list(it.values()))
             if v.nabidka.zamereni_nazev == "sítě")
    assert any("za celý obor" in x for x in v.varovani), v.varovani
