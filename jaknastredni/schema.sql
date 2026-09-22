-- Datový model jaknastredni (SQLite).
-- Popis a zdůvodnění: docs/datovy-model.md
-- Konvence: identifikátory REDIZO/IZO jsou TEXT (mají vedoucí nuly),
-- data jsou ISO řetězce (YYYY-MM-DD), boolean je INTEGER 0/1.

PRAGMA foreign_keys = ON;

-- Evidence každého běhu importu (odkud, kdy, kolik).
CREATE TABLE IF NOT EXISTS import_run (
    id              INTEGER PRIMARY KEY,
    zdroj           TEXT    NOT NULL,       -- 'msmt', 'cermat_jpz', 'cermat_mz', 'csi', ...
    url             TEXT,
    soubor          TEXT,                   -- lokální cesta k surovému souboru
    sha256          TEXT,
    datum_vystupu   TEXT,                   -- datum dat podle zdroje (u MŠMT pole datumVystupu)
    stazeno_utc     TEXT    NOT NULL,
    pocet_zaznamu   INTEGER,
    poznamka        TEXT
);

-- Kódy z číselníků MŠMT (AKDT, RAFS, RADS, BBJK, ...). Oficiální číselníky
-- nejsou online dohledané; hodnoty s overeno=1 jsou potvrzené z dat.
CREATE TABLE IF NOT EXISTS ciselnik (
    ciselnik    TEXT NOT NULL,
    kod         TEXT NOT NULL,
    nazev       TEXT NOT NULL,
    overeno     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ciselnik, kod)
);

-- Právnická osoba (zřizovaný subjekt), klíč REDIZO. Jedna organizace může
-- provozovat víc škol/zařízení (např. SPŠ + VOŠ).
CREATE TABLE IF NOT EXISTS organizace (
    redizo                  TEXT PRIMARY KEY,
    ico                     TEXT,
    nazev                   TEXT NOT NULL,
    zkraceny_nazev          TEXT,
    kraj                    TEXT,
    pravni_forma            TEXT,       -- číselník BBPF
    typ_zrizovatele         TEXT,       -- číselník BAZS
    ulice                   TEXT,
    cislo_domovni           INTEGER,
    typ_cisla_domovniho     TEXT,
    cislo_orientacni        INTEGER,
    dodatek_orientacniho    TEXT,
    obec                    TEXT,
    cast_obce               TEXT,
    obvod_prahy             TEXT,       -- 'Praha 10'
    psc                     TEXT,
    kod_ruian               INTEGER,
    okres                   TEXT,       -- CZ010A
    orp                     TEXT,       -- CZ01100
    emaily                  TEXT,       -- JSON pole
    platnost_neurcita       INTEGER,
    reditel_jmeno           TEXT,
    reditel_od              TEXT,
    aktualizovano           TEXT NOT NULL   -- datumVystupu snapshotu, ze kterého řádek pochází
);

CREATE TABLE IF NOT EXISTS zrizovatel (
    redizo      TEXT NOT NULL REFERENCES organizace(redizo) ON DELETE CASCADE,
    poradi      INTEGER NOT NULL,
    druh_osoby  TEXT,               -- 'PO' / 'FO'
    nazev       TEXT NOT NULL,
    ico         TEXT,
    pravni_forma TEXT,
    PRIMARY KEY (redizo, poradi)
);

-- Škola / školské zařízení, klíč IZO. Sem se napojují CERMAT výsledky
-- (od 2024 mají IZO), obory a kapacity.
CREATE TABLE IF NOT EXISTS skola (
    izo                 TEXT PRIMARY KEY,
    redizo              TEXT NOT NULL REFERENCES organizace(redizo) ON DELETE CASCADE,
    nazev               TEXT NOT NULL,
    druh                TEXT NOT NULL,      -- číselník AKDT; 'C00' = střední škola
    jazyk               TEXT,               -- číselník NAJS
    datum_zapisu        TEXT,
    datum_zahajeni      TEXT,
    aktualizovano       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_skola_redizo ON skola(redizo);
CREATE INDEX IF NOT EXISTS ix_skola_druh   ON skola(druh);

CREATE TABLE IF NOT EXISTS skola_kapacita (
    izo                     TEXT NOT NULL REFERENCES skola(izo) ON DELETE CASCADE,
    merna_jednotka          TEXT NOT NULL,  -- číselník BBJK; '01' = žáci (odvozeno z dat)
    nejvyssi_povoleny_pocet INTEGER NOT NULL,
    PRIMARY KEY (izo, merna_jednotka)
);

CREATE TABLE IF NOT EXISTS misto_vyuky (
    izo                     TEXT NOT NULL REFERENCES skola(izo) ON DELETE CASCADE,
    id_mista                TEXT NOT NULL,
    typ                     TEXT,           -- číselník AKDT (typ místa)
    ulice                   TEXT,
    cislo_domovni           INTEGER,
    typ_cisla_domovniho     TEXT,
    cislo_orientacni        INTEGER,
    dodatek_orientacniho    TEXT,
    obec                    TEXT,
    cast_obce               TEXT,
    obvod_prahy             TEXT,
    psc                     TEXT,
    kod_ruian               INTEGER,
    PRIMARY KEY (izo, id_mista, typ)
);

-- Obor vzdělání zapsaný v rejstříku u dané školy. Kód KKOV je spojovací
-- klíč na CERMAT JPZ 2024+ a na weby škol.
CREATE TABLE IF NOT EXISTS obor (
    id              INTEGER PRIMARY KEY,
    izo             TEXT NOT NULL REFERENCES skola(izo) ON DELETE CASCADE,
    kod_kkov        TEXT NOT NULL,      -- '63-41-M/02'
    nazev           TEXT NOT NULL,
    forma           TEXT,               -- číselník RAFS; '10' = denní (odvozeno)
    delka           TEXT,               -- číselník RADS; '40' = 4 roky (odvozeno)
    jazyk           TEXT,               -- číselník RAJO
    kapacita        INTEGER,
    merna_jednotka  TEXT,
    dobihajici      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (izo, kod_kkov, forma, delka, jazyk)
);
CREATE INDEX IF NOT EXISTS ix_obor_kkov ON obor(kod_kkov);

-- Maturitní výsledky po školách (CERMAT MZ, agregovaná data 2015+).
-- REDIZO je bez cizího klíče na organizace: CERMAT zahrnuje i školy mimo
-- Prahu a mezitím zaniklé školy, které v rejstříku MŠMT nejsou; filtrování
-- na Prahu se dělá JOINem v dotazech, ne omezením při importu.
CREATE TABLE IF NOT EXISTS maturita (
    redizo                  TEXT    NOT NULL,
    rok                     INTEGER NOT NULL,
    obdobi                  TEXT    NOT NULL,   -- 'j' jarní, 'jap' jaro+podzim
    smo16                   TEXT    NOT NULL,   -- skupina oborů; 'CELKEM' = celá škola
    predmet                 TEXT    NOT NULL,   -- 'CELKEM','CJ','MA','AJ','NJ','RJ','FJ','SJ'
    prihlaseni              INTEGER,
    konali                  INTEGER,
    uspeli                  INTEGER,
    neuspeli                INTEGER,
    nekonali                INTEGER,
    prumerny_skor           REAL,               -- PRŮMĚRNÝ % SKÓR (chybí u předmětu CELKEM)
    smerodatna_odchylka     REAL,               -- SMĚRODATNÁ ODCHYLKA % SKÓRU
    prumerny_percentil      REAL,               -- PRŮMĚRNÉ PERCENTILOVÉ UMÍSTĚNÍ
    podil_uspesnych         REAL,               -- PODÍL ÚSPĚŠNÝCH (%)
    cista_neuspesnost       REAL,               -- ČISTÁ NEÚSPĚŠNOST (%)
    podil_volby_predmetu    REAL,               -- jen u volitelných předmětů (ne CJ, ne CELKEM)
    PRIMARY KEY (redizo, rok, obdobi, smo16, predmet)
);
CREATE INDEX IF NOT EXISTS ix_maturita_redizo ON maturita(redizo);

-- Inspekční zprávy ČŠI (opendata.csicr.cz, dataset 69). Bez cizího klíče na
-- organizace: dataset zahrnuje všechny typy škol/zařízení v celé ČR od roku
-- 2003, i školy mimo Prahu a mezitím zaniklé, které v rejstříku MŠMT nejsou;
-- filtrování na Prahu se dělá JOINem v dotazech (nebo --jen-praha při importu).
CREATE TABLE IF NOT EXISTS inspekce (
    redizo      TEXT NOT NULL,
    datum_od    TEXT NOT NULL,      -- začátek inspekční činnosti, ISO YYYY-MM-DD
    nazev       TEXT NOT NULL,      -- název školy v době inspekce (ne osobní údaj)
    datum_do    TEXT,               -- konec inspekční činnosti; NULL, pokud chybí/nevalidní
    pdf_url     TEXT,               -- přímý odkaz na PDF zprávy (LinkIZ)
    portal_url  TEXT,               -- odkaz na stránku školy na portal.csicr.cz
    PRIMARY KEY (redizo, datum_od)
);
CREATE INDEX IF NOT EXISTS ix_inspekce_redizo ON inspekce(redizo);

-- Pohled: střední školy s organizací (nejčastější dotaz).
CREATE VIEW IF NOT EXISTS v_stredni_skola AS
SELECT s.izo, s.redizo, o.nazev AS organizace, s.nazev AS skola, s.druh,
       o.obvod_prahy, o.ulice, o.cislo_domovni, o.cislo_orientacni, o.psc,
       o.typ_zrizovatele, o.ico,
       (SELECT nejvyssi_povoleny_pocet FROM skola_kapacita k
         WHERE k.izo = s.izo AND k.merna_jednotka = '01') AS kapacita_zaku,
       (SELECT COUNT(*) FROM obor b WHERE b.izo = s.izo AND b.dobihajici = 0) AS pocet_oboru
FROM skola s JOIN organizace o ON o.redizo = s.redizo
WHERE s.druh IN ('C00', 'E00');
