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

-- Výsledky jednotné přijímací zkoušky (JPZ) po školách a oborových skupinách,
-- CERMAT „starý formát" 2017–2023 (od 2024 nahrazeno mnohem granulárnější
-- tabulkou prijimaci_rizeni podle IZO+KKOV). Bez IZO a bez KKOV — jen hrubá
-- „oborová skupina" (GY8, GY4, LYC, 4LETÉ OBORY, ...). Metrika úspěšnosti je
-- průměrné percentilové umístění (0–100), ne bodové skóre. Stejně jako
-- maturita bez cizího klíče na organizace (školy mimo Prahu, zaniklé školy);
-- filtrování na Prahu se dělá JOINem, nebo --jen-praha při importu.
CREATE TABLE IF NOT EXISTS jpz_skupina (
    redizo                  TEXT    NOT NULL,
    skupina_oboru           TEXT    NOT NULL,   -- 'GY8','GY6','GY4','LYC','4LETÉ OBORY','SEK','NAS',...
    rocnik                  INTEGER NOT NULL,
    rok                     INTEGER NOT NULL,
    prihlaseni_cj           INTEGER,
    konali_cj               INTEGER,
    prumerny_percentil_cj   REAL,
    smerodatna_odchylka_cj  REAL,
    prihlaseni_ma           INTEGER,
    konali_ma               INTEGER,
    prumerny_percentil_ma   REAL,
    smerodatna_odchylka_ma  REAL,
    PRIMARY KEY (redizo, skupina_oboru, rocnik, rok)
);
CREATE INDEX IF NOT EXISTS ix_jpz_skupina_redizo ON jpz_skupina(redizo);

-- Scrapovaný doplňkový profil školy (infoabsolvent.cz, případně Atlas
-- školství) — pole, která rejstřík MŠMT nemá: přijímací kritéria, školné,
-- dny otevřených dveří, jazyky, vybavení, loňský poměr přihlášených/plánu
-- přijmout. Bez cizího klíče na organizace (stejný důvod jako u maturity —
-- nechceme, aby scraper spadl na REDIZO, které v lokálním snapshotu MŠMT
-- zrovna chybí). `data` je JSON objekt, ne rozepsané sloupce (viz
-- docs/datovy-model.md, tabulka web_profil). Osobní údaje se do `data`
-- neukládají (žádné jméno ředitele/adresy fyzických osob) — to už řeší
-- organizace.reditel_jmeno.
CREATE TABLE IF NOT EXISTS web_profil (
    redizo      TEXT NOT NULL,
    zdroj       TEXT NOT NULL,      -- 'infoabsolvent', případně později 'atlas'
    stazeno     TEXT NOT NULL,      -- ISO datum stažení (YYYY-MM-DD)
    url         TEXT,
    data        TEXT NOT NULL,      -- JSON objekt s naparsovanými poli
    PRIMARY KEY (redizo, zdroj, stazeno)
);
CREATE INDEX IF NOT EXISTS ix_web_profil_redizo ON web_profil(redizo);

-- Výsledky jednotné přijímací zkoušky (CERMAT JPZ, nový formát 2024+).
-- Jeden řádek = škola (IZO) × obor (KKOV) × zaměření × forma × délka ×
-- jazyk studia × ročník (ZŠ, ze kterého se hlásí) × rok × kolo. Bez cizího
-- klíče na skola(izo)/organizace(redizo) — stejný důvod jako u `maturita`:
-- CERMAT zahrnuje i školy mimo Prahu a mezitím zaniklé; filtr na Prahu se
-- dělá JOINem v dotazech, nebo `--jen-praha` při importu.
-- Klíč (izo, kod_kkov, rocnik, rok, kolo) sám o sobě NENÍ jednoznačný — školy
-- nabízející víc zaměření/forem/délek/jazyků pod jedním KKOV mají víc řádků
-- (ověřeno na reálných datech 2024–2026, ~2 % řádků), proto je rozšířený o
-- zamereni_oboru, forma_vzdelavani, delka_studia, jazyk_studia — stejný
-- princip jako u tabulky `obor`. Podrobně: docs/research/cermat.md, oddíl 13.
CREATE TABLE IF NOT EXISTS prijimaci_rizeni (
    izo                             TEXT    NOT NULL,
    kod_kkov                        TEXT    NOT NULL,
    rocnik                          INTEGER NOT NULL,
    rok                             INTEGER NOT NULL,
    kolo                            INTEGER NOT NULL,
    zamereni_oboru                  TEXT    NOT NULL DEFAULT '',
    forma_vzdelavani                TEXT    NOT NULL,
    delka_studia                    TEXT    NOT NULL,
    jazyk_studia                    TEXT    NOT NULL,
    redizo                          TEXT    NOT NULL,
    id_so                           TEXT,       -- CERMAT UUID nabídky (sdílené mezi zaměřeními); u prihlasky/kapacity 2024-2025 přejmenováno na IS_SO, viz cermat.md odd. 13
    id_sof                          TEXT,       -- CERMAT UUID řádku (zaměření); ověřeno jako spolehlivý spojovací klíč mezi vysledky/prihlasky/kapacity
    kapacita                        INTEGER,
    index_poptavky                  REAL,       -- PŘIHLÁŠKY CELKEM / KAPACITA
    prihlasky_celkem                INTEGER,
    prihlasky_priorita_1            INTEGER,
    prihlasky_priorita_2            INTEGER,
    prihlasky_priorita_3            INTEGER,
    prihlasky_priorita_4            INTEGER,
    prihlasky_priorita_5            INTEGER,
    prijati                         INTEGER,
    prijati_priorita_1              INTEGER,
    prijati_priorita_2              INTEGER,
    prijati_priorita_3              INTEGER,
    prijati_priorita_4              INTEGER,
    prijati_priorita_5              INTEGER,
    konali_cjma                     INTEGER,    -- konali ČJ i MA (všichni přihlášení)
    konali_cj                       INTEGER,
    konali_ma                       INTEGER,
    skor_prumer_cjma                REAL,       -- % skór, všichni přihlášení
    skor_prumer_cj                  REAL,
    skor_prumer_ma                  REAL,
    skor_min_cjma                   REAL,
    skor_min_cj                     REAL,
    skor_min_ma                     REAL,
    skor_max_cjma                   REAL,
    skor_max_cj                     REAL,
    skor_max_ma                     REAL,
    percentil_prumer_cjma           REAL,
    percentil_prumer_cj             REAL,
    percentil_prumer_ma             REAL,
    percentil_min_cjma              REAL,
    percentil_min_cj                REAL,
    percentil_min_ma                REAL,
    percentil_max_cjma              REAL,
    percentil_max_cj                REAL,
    percentil_max_ma                REAL,
    konali_prijati_cjma             INTEGER,    -- totéž, jen za přijaté uchazeče
    konali_prijati_cj               INTEGER,
    konali_prijati_ma               INTEGER,
    skor_prijati_prumer_cjma        REAL,
    skor_prijati_prumer_cj          REAL,
    skor_prijati_prumer_ma          REAL,
    skor_prijati_min_cjma           REAL,
    skor_prijati_min_cj             REAL,
    skor_prijati_min_ma             REAL,
    skor_prijati_max_cjma           REAL,
    skor_prijati_max_cj             REAL,
    skor_prijati_max_ma             REAL,
    percentil_prijati_prumer_cjma   REAL,
    percentil_prijati_prumer_cj     REAL,
    percentil_prijati_prumer_ma     REAL,
    percentil_prijati_min_cjma      REAL,
    percentil_prijati_min_cj        REAL,
    percentil_prijati_min_ma        REAL,
    percentil_prijati_max_cjma      REAL,
    percentil_prijati_max_cj        REAL,
    percentil_prijati_max_ma        REAL,
    neprijati_vyssi_priorita        INTEGER,    -- nepřijat, přijat na vyšší prioritu
    neprijati_nedostatecna_kapacita INTEGER,
    neprijati_nesplneni_podminek    INTEGER,
    neprijati_vzdal_se              INTEGER,
    PRIMARY KEY (izo, kod_kkov, rocnik, rok, kolo, zamereni_oboru, forma_vzdelavani, delka_studia, jazyk_studia)
);
CREATE INDEX IF NOT EXISTS ix_prijimaci_rizeni_izo    ON prijimaci_rizeni(izo);
CREATE INDEX IF NOT EXISTS ix_prijimaci_rizeni_redizo ON prijimaci_rizeni(redizo);
CREATE INDEX IF NOT EXISTS ix_prijimaci_rizeni_kkov   ON prijimaci_rizeni(kod_kkov);

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

-- Empirická úspěšnost přijetí podle bodového pásma, spočítaná ze souborů
-- uchazečů CERMAT (`PZ{rok}_kolo{k}_uchazeci_prihlasky_vysledky.xlsx`, 2024+).
-- Jeden zdrojový řádek = jeden uchazeč s % skórem a až pěti přihláškami
-- (REDIZO + KKOV + forma + přijat/nepřijat + důvod nepřijetí); tady se
-- agreguje na (škola × obor × rok × kolo × pásmo skóre), protože průvodce
-- potřebuje jen míru přijetí, ne jednotlivé uchazeče — a agregace drží
-- databázi malou (surové soubory zůstávají v data/raw/, viz README).
--
-- Proč to existuje vedle `prijimaci_rizeni`: ta má jen *minimální* skór
-- přijatého, což je ocasová hodnota (často jeden uchazeč, který se dostal
-- na body za prospěch). Odhad šance postavený na ní je systematicky
-- optimistický — měřeno proti téhle tabulce až o 40 procentních bodů.
-- Podrobně: docs/pruvodce-ux.md, oddíl „Šance na přijetí".
--
-- Klíč je REDIZO, ne IZO: soubory uchazečů IZO neuvádějí. Právnická osoba
-- se dvěma školami nabízejícími tentýž KKOV se proto slije do jednoho řádku
-- (v pražských datech vzácné). Stejně jako ostatní CERMAT tabulky bez
-- cizího klíče na `organizace` — filtr na Prahu se dělá JOINem.
--
-- `pasmo_od` je dolní mez pásma % skóru ČJ+MA (0, 5, 10, …, 195) na škále
-- 0–200; hodnota **-1** znamená „uchazeč JPZ nekonal" (obory s výučním
-- listem H/E jednotnou zkoušku nemají — v roce 2026 to bylo 37 004 ze
-- 156 210 uchazečů).
CREATE TABLE IF NOT EXISTS prijimacky_pasmo (
    redizo                  TEXT    NOT NULL,
    kod_kkov                TEXT    NOT NULL,
    rok                     INTEGER NOT NULL,
    kolo                    INTEGER NOT NULL,
    pasmo_od                INTEGER NOT NULL,   -- -1 = bez JPZ, jinak 0/5/…/195
    prihlasek               INTEGER NOT NULL,   -- všechny přihlášky v pásmu
    prijato                 INTEGER NOT NULL,
    nedostatecna_kapacita   INTEGER NOT NULL,   -- nepřijat: nevešel se
    nesplneni_podminek      INTEGER NOT NULL,   -- nepřijat: nesplnil podmínky
    vyssi_priorita          INTEGER NOT NULL,   -- nepřijat: přijat na vyšší prioritu
    vzdal_se                INTEGER NOT NULL,
    PRIMARY KEY (redizo, kod_kkov, rok, kolo, pasmo_od)
);
CREATE INDEX IF NOT EXISTS ix_prijimacky_pasmo_redizo ON prijimacky_pasmo(redizo);
CREATE INDEX IF NOT EXISTS ix_prijimacky_pasmo_kkov   ON prijimacky_pasmo(kod_kkov);
