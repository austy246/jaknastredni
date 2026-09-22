"""Testy průvodce výběrem školy.

Fixtura je malá umělá databáze (4 školy, 5 nabídek) poskládaná ze stejných
tabulek jako ostrá databáze — testy tedy nepotřebují `data/jaknastredni.db`
ani syrová data. Čísla jsou vymyšlená, ale ve tvaru, v jakém je ukládají
importéry (% skór 0–200, REDIZO jako text s vedoucí nulou, školné v Kč).
"""
from __future__ import annotations

import json

import pytest

from jaknastredni import db, oblasti, pruvodce


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
        zamereni="", poptavka=None):
    conn.execute(
        """INSERT INTO prijimaci_rizeni
           (izo, kod_kkov, rocnik, rok, kolo, zamereni_oboru, forma_vzdelavani,
            delka_studia, jazyk_studia, redizo, kapacita, index_poptavky,
            prihlasky_celkem, prijati, skor_prijati_min_cjma)
           VALUES (?,?,9,?,1,?,'denní','4','CJ',?,?,?,?,?,?)""",
        (izo, kod, rok, zamereni, redizo, kapacita,
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
    # 2) Průmyslovka s IT oborem, dostupná, dvě zaměření v jednom KKOV.
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
    nabidky = {(n.izo, n.kod_kkov): n for n in pruvodce.nacti_nabidky(conn)}
    assert len(nabidky) == 4
    gympl = nabidky[("100000001", "79-41-K/41")]
    assert gympl.typ == "G4" and gympl.trida_prihlasky == 9
    assert gympl.hranice == {2024: 150.0, 2025: 156.0, 2026: 154.0}
    assert gympl.obvody == ("Praha 6",)
    assert gympl.zrizovatel_verejny is True


def test_hranice_se_pres_zamereni_vazi_poctem_prijatych(conn):
    """Zaměření s 60 přijatými má na hranici větší vliv než to s 10."""
    it = next(n for n in pruvodce.nacti_nabidky(conn) if n.kod_kkov == "18-20-M/01")
    # (100*60 + 60*10) / 70 = 94.3 — ne prostý průměr 80 a ne minimum 60.
    assert it.hranice[2026] == pytest.approx((100 * 60 + 60 * 10) / 70, abs=0.1)
    assert it.kapacita == 70 and it.prijati == 70
    assert set(it.zamereni) == {"programování", "sítě"}


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
    assert len(pruvodce.ohodnot(pruvodce.Profil(trida=9), nabidky)) == 4


def test_filtr_skolneho(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    zdarma = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=0), nabidky)
    assert all(v.nabidka.redizo != "600000003" for v in zdarma)
    s_penezi = pruvodce.ohodnot(pruvodce.Profil(trida=9, skolne_max=100000), nabidky)
    assert any(v.nabidka.redizo == "600000003" for v in s_penezi)


def test_filtr_oblasti(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    it = pruvodce.ohodnot(pruvodce.Profil(trida=9, oblasti_zajmu=["it"]), nabidky)
    assert [v.nabidka.kod_kkov for v in it] == ["18-20-M/01"]


def test_filtr_jazyka(conn):
    nabidky = pruvodce.nacti_nabidky(conn)
    nemcina = pruvodce.ohodnot(pruvodce.Profil(trida=9, jazyk="N", skolne_max=100000), nabidky)
    assert [v.nabidka.redizo for v in nemcina] == ["600000003"]


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

def test_export_web_nese_nabidky_i_konstanty(conn):
    from jaknastredni import export_web

    data = export_web.export(conn)
    assert len(data["nabidky"]) == 4
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
