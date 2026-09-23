"""Převod kódů KKOV na to, čemu rozumí uchazeč.

Kód oboru (KKOV, např. ``63-41-M/02``) nese dvě informace, které průvodce
(`jaknastredni.pruvodce`) potřebuje pro filtrování:

- **první dvojčíslí** = skupina oborů vzdělání (``63`` = Ekonomika a
  administrativa). Skupin je v pražské nabídce 27 — na to, aby si je
  uchazeč proklikal ve formuláři, jich je moc, proto je tenhle modul
  seskupuje do 11 „oblastí zájmu" (`OBLASTI`). Jedna skupina může patřit do
  víc oblastí (``34`` Polygrafie je řemeslo i média), to je záměr — filtr
  má radši nabídnout víc než uchazeči obor schovat.
- **písmeno za lomítkem a poslední dvojčíslí** = typ a délka vzdělání
  (``K/81`` = osmileté gymnázium, ``M`` = čtyřletý maturitní obor, ``H`` =
  tříletý obor s výučním listem). Z něj plyne i **ze které třídy ZŠ** se na
  obor hlásí — klíčová první otázka průvodce.

Názvy skupin odpovídají oficiální soustavě oborů vzdělání (nařízení vlády
č. 211/2010 Sb.); v databázi je ale `ciselnik` jen pro číselníky MŠMT
z rejstříku (AKDT, RAFS, …), skupiny KKOV v datech nikde nejsou, proto
jsou tady natvrdo. Ověřeno proti reálným názvům oborů v pražském snapshotu
(viz `docs/pruvodce-ux.md`, oddíl „Oblasti zájmu").
"""
from __future__ import annotations

import re
from typing import Iterable

# První dvojčíslí KKOV -> název skupiny oborů vzdělání.
SKUPINY: dict[str, str] = {
    "16": "Ekologie a ochrana životního prostředí",
    "18": "Informatické obory",
    "21": "Hornictví a hutnictví",
    "23": "Strojírenství a strojírenská výroba",
    "26": "Elektrotechnika, telekomunikační a výpočetní technika",
    "28": "Technická chemie a chemie silikátů",
    "29": "Potravinářství a potravinářská chemie",
    "31": "Textilní výroba a oděvnictví",
    "32": "Kožedělná a obuvnická výroba",
    "33": "Zpracování dřeva a výroba hudebních nástrojů",
    "34": "Polygrafie, zpracování papíru, filmu a fotografie",
    "36": "Stavebnictví, geodézie a kartografie",
    "37": "Doprava a spoje",
    "39": "Speciální a interdisciplinární obory",
    "41": "Zemědělství a lesnictví",
    "43": "Veterinářství a veterinární prevence",
    "53": "Zdravotnictví",
    "61": "Filozofie, teologie",
    "63": "Ekonomika a administrativa",
    "64": "Podnikání v oborech, odvětví",
    "65": "Gastronomie, hotelnictví a turismus",
    "66": "Obchod",
    "68": "Právo, právní a veřejnosprávní činnost",
    "69": "Osobní a provozní služby",
    "72": "Publicistika, knihovnictví a informatika",
    "74": "Tělesná kultura, tělovýchova a sport",
    "75": "Pedagogika, učitelství a sociální péče",
    "78": "Obecně odborná příprava (lycea)",
    "79": "Obecná příprava (gymnázia)",
    "82": "Umění a užité umění",
}

# Oblast zájmu (to, co se ptáme uchazeče) -> (popisek, skupiny KKOV).
# Pořadí je pořadí ve formuláři: nejdřív to, co má v Praze největší nabídku.
OBLASTI: dict[str, tuple[str, tuple[str, ...]]] = {
    "vseobecne": ("Všeobecné vzdělání (gymnázium, lyceum)", ("79", "78")),
    # „Humanitní" není skupina KKOV, ale je to první slovo, kterým uchazeč
    # svůj zájem popíše (ověřeno na reálné odpovědi). Skládá se z oborů,
    # kde se pracuje s jazykem, člověkem a společností — gymnázia a lycea
    # taky, protože na humanitní VŠ vedou hlavně ony.
    "humanitni": ("Humanitní obory, jazyky, společnost", ("79", "78", "68", "72", "75", "61")),
    "it": ("IT, počítače, elektronika", ("18", "26")),
    "technika": ("Technika, strojírenství, doprava", ("23", "26", "28", "37", "39")),
    "remesla": ("Stavebnictví a řemesla", ("36", "33", "31", "32", "34", "21")),
    "ekonomika": ("Ekonomika, obchod, podnikání", ("63", "64", "66", "37")),
    "pravo": ("Právo, veřejná správa, bezpečnost", ("68",)),
    "zdravi": ("Zdravotnictví a péče o člověka", ("53", "43", "69", "74")),
    "pedagogika": ("Pedagogika a sociální práce", ("75", "61")),
    "umeni": ("Umění, design, média", ("82", "72", "34")),
    "gastro": ("Gastronomie, hotelnictví, cestovní ruch", ("65", "29")),
    "priroda": ("Příroda, zemědělství, ekologie", ("16", "41", "43", "28")),
}

# Typ vzdělání odvozený z písmene KKOV + poslední dvojčíslí.
# (kód typu) -> (popisek, ze které třídy ZŠ se hlásí, končí maturitou?)
TYPY: dict[str, tuple[str, int, bool]] = {
    "G8": ("osmileté gymnázium", 5, True),
    "G6": ("šestileté gymnázium", 7, True),
    "G4": ("čtyřleté gymnázium", 9, True),
    "LYC": ("lyceum", 9, True),
    "M": ("čtyřletý maturitní obor (SOŠ)", 9, True),
    "L0": ("maturitní obor s odborným výcvikem", 9, True),
    "L5": ("nástavbové studium (po vyučení)", 0, True),
    "H": ("tříletý obor s výučním listem", 9, False),
    "E": ("obor s výučním listem (nižší nároky)", 9, False),
    "J": ("obor bez maturity i výučního listu", 9, False),
    "C": ("praktická škola", 9, False),
    "N": ("vyšší odborná škola", 0, False),
    "P": ("konzervatoř", 5, True),
}

# Typy, které do průvodce pro žáka ZŠ nepatří (nástavby, VOŠ).
TYPY_MIMO_ZS = ("L5", "N")

# Odvození typu vzdělání z osobnostních otázek místo přímé volby.
#
# Čtrnáctiletý obvykle neví, jestli chce „lyceum" nebo „čtyřletý maturitní
# obor" — tahle slova mu nic neříkají a ptát se na ně rovnou znamená nutit
# ho k rozhodnutí, kvůli kterému za průvodcem přišel. Ptáme se proto na tři
# věci, na které odpovědět umí, a typ z nich **odvodíme a ukážeme jako
# zjištění**, ne jako vstup.
#
# Každá odpověď dává každému typu skóre 0–1; výsledek je průměr přes
# zodpovězené otázky (nezodpovězené se přeskočí, nesnižují nic).
OSOBNOSTNI_OTAZKY: dict[str, tuple[str, dict[str, tuple[str, dict[str, float]]]]] = {
    "po_skole": ("Co chceš dělat, až tuhle školu doděláš?", {
        "vysoka":   ("Jít na vysokou nebo vyšší odbornou",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.6, "L0": 0.3,
                      "H": 0.05, "E": 0.05, "J": 0.05}),
        "prace":    ("Jít rovnou pracovat",
                     {"G8": 0.1, "G6": 0.1, "G4": 0.1, "LYC": 0.4, "M": 0.8, "L0": 0.9,
                      "H": 1.0, "E": 0.9, "J": 0.6}),
        "nevim":    ("Ještě nevím",
                     {"G8": 0.8, "G6": 0.8, "G4": 0.8, "LYC": 1.0, "M": 0.8, "L0": 0.6,
                      "H": 0.4, "E": 0.3, "J": 0.3}),
    }),
    "rozhodnuto": ("Víš už, čemu se chceš věnovat?", {
        "obor":     ("Vím to docela přesně",
                     {"G8": 0.3, "G6": 0.3, "G4": 0.3, "LYC": 0.6, "M": 1.0, "L0": 1.0,
                      "H": 1.0, "E": 0.9, "J": 0.6}),
        "otevreno": ("Chci si nechat otevřené dveře",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.5, "L0": 0.3,
                      "H": 0.2, "E": 0.2, "J": 0.2}),
        "nevim":    ("Nevím",
                     {"G8": 0.7, "G6": 0.7, "G4": 0.7, "LYC": 1.0, "M": 0.7, "L0": 0.5,
                      "H": 0.4, "E": 0.4, "J": 0.4}),
    }),
    "praxe": ("Jak moc chceš dělat věci rukama a chodit na praxi?", {
        "hodne":    ("Hodně — teorie u tabule mě nebaví",
                     {"G8": 0.05, "G6": 0.05, "G4": 0.05, "LYC": 0.3, "M": 0.6, "L0": 1.0,
                      "H": 1.0, "E": 1.0, "J": 0.8}),
        # Gymnázium tu mělo 0,5 — půl cesty k „hodně praxe". Jenže kdo
        # odpoví „něco od obojího", gymnázium tím nevylučuje (laboratoře,
        # projekty, informatika tam jsou), a protože se typ normalizuje
        # proti kandidátům, dělalo z 0,5 proti lyceu 0,9 plnou nulu:
        # s „jen všeobecné vzdělání" vyšlo deset lyceí a žádné gymnázium.
        "stredne":  ("Něco od obojího",
                     {"G8": 0.75, "G6": 0.75, "G4": 0.75, "LYC": 0.9, "M": 1.0, "L0": 0.8,
                      "H": 0.5, "E": 0.4, "J": 0.4}),
        "teorie":   ("Radši se učím a přemýšlím",
                     {"G8": 1.0, "G6": 1.0, "G4": 1.0, "LYC": 0.9, "M": 0.6, "L0": 0.2,
                      "H": 0.1, "E": 0.1, "J": 0.1}),
    }),
}


# Zaměření uvnitř oboru — to, co dva obory se stejným kódem KKOV odlišuje.
#
# Kód KKOV je na rozhodování hrubý: `18-20-M/01` (Informační technologie)
# mají v Praze desítky škol a učí pod ním všechno od programování přes
# správu sítí po herní grafiku. SPŠE Ječná má pod ním ŠVP „Programování
# a digitální technologie", SPŠE V Úžlabině ŠVP „Informační technologie"
# a v popisu školy „správce serverových služeb operačních systémů
# a počítačových sítí". Rozdíl, podle kterého se uchazeč rozhoduje, je
# přitom **jen v těchhle textech** — v žádném číselníku není.
#
# Proto se zaměření hledá klíčovými slovy v názvu oboru, názvu ŠVP
# (infoabsolvent), zaměření z CERMATu a v popisu školy. Je to heuristika,
# ne číselník: co škola do textu nenapsala, průvodce nepozná, a naopak
# zmínka v popisu školy ještě neznamená, že se to učí zrovna v tomhle
# oboru (viz `Nabidka.zamereni_skoly`, které se proto váží slabší).
#
# (kód) -> (popisek, oblasti zájmu, kde se na zaměření ptáme, regulární výraz)
ZAMERENI: dict[str, tuple[str, tuple[str, ...], str]] = {
    # IT a elektro
    "programovani": ("Programování a vývoj aplikací", ("it",),
                     r"programov|vývoj (?:aplikac|softwar|her)|softwar|kódování|algoritm"),
    "site": ("Počítačové sítě, servery, hardware", ("it",),
             r"počítačov\w* sít|síťov\w* (?:učebn|technolog|infrastrukt|administr)|"
             r"\bsít[ěí]\b|server|cisco|hardware|správ\w* (?:sít|počítač)"),
    "kyber": ("Kybernetická bezpečnost", ("it", "pravo"),
              r"kybernetick|kyberbezpeč|informační bezpečnost|bezpečnost (?:dat|it|informac)"),
    "web": ("Web a digitální marketing", ("it", "umeni", "ekonomika"),
            r"webov\w* (?!stránk)|tvorb\w* web|internetov\w* aplikac|digitální marketing"),
    "grafika": ("Grafika, hry, multimédia", ("it", "umeni"),
                r"herní|počítačov\w* grafik|grafick|\bgame\b|3d|multimédi|animac|"
                r"vizuální efekt"),
    "robotika": ("Robotika a automatizace", ("it", "technika"),
                 r"robotik|robotick|automatizac|mechatronik|řídicí systém|\bplc\b|cnc"),
    "elektro": ("Elektronika a elektrotechnika", ("it", "technika"),
                r"elektronik|elektrotechnik|slaboproud|silnoproud|energetik|"
                r"zabezpečovací|inteligentní budov"),
    # Technika a řemesla
    "strojirenstvi": ("Strojírenství a obrábění", ("technika", "remesla"),
                      r"strojírenst|strojní|obrábě|svařov|zámečn|nástrojař"),
    "auto": ("Auto, doprava, letectví", ("technika",),
             r"automobil|motorov\w* vozid|autotronik|autome|dopravn|letec|železnič|logistik"),
    "stavebnictvi": ("Stavebnictví a architektura", ("remesla", "technika", "umeni"),
                     r"stavebnict|stavitel|architekt|zedn|instalatér|truhlář|tesař|"
                     r"geodéz|interiér"),
    # Ekonomika, právo, služby
    "ekonomika_ucetnictvi": ("Ekonomika, účetnictví, finance", ("ekonomika",),
                             r"účetnict|ekonomik|finanč|bankovn|pojišťovnict|daň"),
    "management": ("Management, podnikání, obchod", ("ekonomika",),
                   r"management|podnikán|\bbusiness\b|obchodn[íě]|marketing|"
                   r"personáln|logistik"),
    "cestovni_ruch": ("Cestovní ruch a hotelnictví", ("gastro", "ekonomika"),
                      r"cestovní ruch|hotelnict|turism|průvodcovsk"),
    "gastronomie": ("Vaření, cukrařina, obsluha", ("gastro",),
                    r"kuchař|číšník|cukrář|pekař|gastronom|barman|řezník|potravinář"),
    "pravo_verejna_sprava": ("Právo a veřejná správa", ("pravo",),
                             r"právn|\bprávo\b|veřejnosprávn|veřejn\w* správ|justič|notář"),
    "bezpecnost": ("Bezpečnost, policie, záchranáři", ("pravo", "zdravi"),
                   r"bezpečnostní (?:prac|slož|služb)|policejn|požárn|záchranář|"
                   r"kriminalistik|ochrana osob"),
    # Člověk, zdraví, pedagogika
    "zdravotnictvi": ("Zdravotnictví a laboratoře", ("zdravi",),
                      r"zdravotnick|ošetřovatel|\bsestr|laboratorn|farmaceut|"
                      r"asistent zubn|nutriční|masér|fyzioterap"),
    "socialni": ("Sociální práce a péče", ("pedagogika", "zdravi"),
                 r"sociáln|pečovatel|charitativ"),
    "pedagogika_deti": ("Práce s dětmi, předškolní pedagogika", ("pedagogika",),
                        r"předškoln|pedagogik|vychovatel|učitel|mateřsk\w* škol"),
    "sport": ("Sport a tělesná výchova", ("zdravi", "vseobecne"),
              r"sportovn|tělesn\w* (?:výchov|kultur)|atletik|fotbal|hokej|basketbal|"
              r"volejbal|házen|plaván|triatlon|\brugby\b|trenér"),
    "krasa": ("Kadeřnictví, kosmetika, péče o vzhled", ("zdravi",),
              r"kadeřn|kosmetič|kosmetik|vizážist|nehtov|péče o vzhled"),
    # Humanitní, jazyky, umění
    "jazyky": ("Jazyky a dvojjazyčné studium", ("humanitni", "vseobecne"),
               r"jazyk|dvojjazyč|bilingv|anglick\w* (?:program|sekc|výuk)|"
               r"německ\w* (?:program|sekc|výuk)|španěl|francouz|italsk|"
               r"international|worldwide|\bap diploma|baccalaur|mezinárodn\w* maturit"),
    "spolecenske_vedy": ("Společenské vědy, humanitní zaměření", ("humanitni", "vseobecne"),
                         r"humanitn|společensk\w* věd|filozof|psycholog|historie|"
                         r"mezinárodní vztah"),
    "prirodni_vedy": ("Přírodní vědy a matematika", ("vseobecne", "priroda", "it"),
                      r"přírodovědn|přírodní věd|matematik|fyzik|chemi|biolog|"
                      r"technick\w* lyceum|geograf"),
    "media": ("Média, žurnalistika, film, foto", ("umeni", "humanitni"),
              r"žurnalist|mediáln|\bmédi|filmov|fotograf|televizn|reklam|"
              r"polygraf|tisk"),
    "umeni_design": ("Výtvarno, design, užité umění", ("umeni", "vseobecne"),
                     r"výtvarn|esteticko|\bart econ\b|design|užit\w* umění|uměleckořemesln|restaurov|"
                     r"malb|sochař|kerami|sklář|šperk|odě[vy]|módn|scénograf"),
    "hudba_divadlo": ("Hudba, tanec, divadlo", ("umeni",),
                      r"hudebn|tanečn|divadeln|zpěv|konzervatoř|herect"),
    # Zaměření gymnázií a lyceí. Ptáme se na ně u „Všeobecného vzdělání",
    # protože IT/ekonomická zaměření výš se týkají odborných oborů: kdo chce
    # gymnázium s rozšířenou informatikou, nechce tím říct „programátorskou
    # průmyslovku" — a naopak.
    "informatika": ("Informatika a programování (gymnázium, lyceum)", ("vseobecne",),
                    r"informatik|programov|robotik|výpočetní techni|"
                    r"technologie a jejich aplikac|\bit gymnázium|moderních technologi|esport"),
    "ekonomie": ("Ekonomie a podnikání (gymnázium, lyceum)", ("vseobecne",),
                 r"ekonomi|\becon\b|podnikav|finanční gramotn"),
    # V datech jen Meda (budoucí lékaři, psychologové) — ale je to přesně
    # profilace, kvůli které se na gymnázium hlásí, a jinde ji nenajde.
    "medicina": ("Příprava na medicínu a psychologii (gymnázium)", ("vseobecne",),
                 r"lékař|medicín|psycholog"),
    # Příroda
    "priroda_zvirata": ("Příroda, zvířata, zemědělství", ("priroda",),
                        r"veterin|zeměděl|zahradni|chov|lesnict|ekolog|"
                        r"životní\w* prostřed|rybář"),
}

_ZAMERENI_RE: dict[str, "re.Pattern[str]"] = {
    kod: re.compile(vzor, re.IGNORECASE) for kod, (_p, _o, vzor) in ZAMERENI.items()
}


def zamereni_textu(*texty: str | None) -> tuple[str, ...]:
    """Kódy zaměření, na která v daných textech sedí klíčová slova.

    Texty se spojí do jednoho a hledá se ve všech najednou — na pořadí ani
    na tom, ze kterého pole slovo přišlo, nezáleží. Prázdné a None se
    ignorují, takže jde volat i s poli, která u dané školy chybí.
    """
    spojeno = " \n ".join(t for t in texty if t)
    if not spojeno.strip():
        return ()
    return tuple(kod for kod, vzor in _ZAMERENI_RE.items() if vzor.search(spojeno))


# Pole „vybavení a nabídka" z infoabsolventu je zaškrtávací seznam, který mají
# skoro všechny školy stejný: „multimediální jazyková učebna" dělala zaměření
# `media` a `jazyky` 89 a 80 školám, „zájmový kroužek sportovní, umělecký,
# přírodovědný" `sport` 78 a `prirodni_vedy` 36 — u gymnázií tím zaměření
# „z popisu školy" byla skoro jen šum. Tyhle položky se zahodí, zbytek
# (např. „síťové učebny s vlastními servery", „kroužek programování") zůstane.
_SUM_VYBAVENI = re.compile(
    r"^(?:zájmov\w* kroužek\s*)?(?:sportovní|umělecký|technický|přírodovědný|jazykov\w*)?$"
    r"|jazykov\w* učebn|multimediáln|tělocvičn|hřiště|sportovní (?:hal|areál|klub)",
    re.IGNORECASE)


def zamereni_vybaveni(text: str | None) -> tuple[str, ...]:
    """`zamereni_textu` pro seznam vybavení — bez standardních položek."""
    if not text:
        return ()
    polozky = [p.strip() for p in re.split(r"[,;\n]", text)]
    return zamereni_textu(", ".join(p for p in polozky if p and not _SUM_VYBAVENI.search(p)))


def zamereni_oblasti(oblasti_zajmu: "Iterable[str]") -> tuple[str, ...]:
    """Zaměření, na která má smysl se ptát u zvolených oblastí zájmu.

    Formulář nemá uchazeči nabídnout všech 31 zaměření — jen ta, která
    patří k oblastem, co zaškrtl. Pořadí drží pořadí v `ZAMERENI`.
    """
    zvolene = set(oblasti_zajmu)
    return tuple(kod for kod, (_p, obl, _v) in ZAMERENI.items() if zvolene & set(obl))


def popis_zamereni(kod: str) -> str:
    return ZAMERENI[kod][0] if kod in ZAMERENI else kod


# Šířka výběru — kolik toho uchazeč zaškrtl, jako **měření** odpovědi na
# otázku `rozhodnuto`.
#
# Kdo zaškrtne osm zaměření z jedenácti, tím řekl „ještě nevím" spolehlivěji,
# než jak na to umí odpovědět u otázky, která se ho na to ptá přímo. Je to
# chování, ne sebehodnocení, a u čtrnáctiletého je chování lepší důkaz.
# Proto šířka výběru u `preference_typu` **nahrazuje** odpověď na
# `rozhodnuto`: je to táž otázka, jen líp změřená. S ostatními dvěma
# otázkami (`po_skole`, `praxe`) se dál průměruje, takže nepřebíjí všechno.
#
# Měří se dvě věci a váží se v poměru 3:1:
#
# - **Podíl zaměření** (`zvolená / nabízená`), ne jejich počet. Čtyři ze
#   čtyř nabízených je něco úplně jiného než čtyři z osmadvaceti — absolutní
#   počet by trestal uchazeče, kterým formulář nabídl užší výběr.
# - **Počet oblastí**, protože šířka *uvnitř* jedné oblasti není nerozhodnost.
#   Kdo zaškrtne všech sedm IT zaměření, neříká „nevím, co chci" — říká
#   „chci IT, je mi jedno jaké", a tomu sedí široká průmyslovka, ne
#   gymnázium. Nerozhodnost je teprve šířka napříč oblastmi.
VAHA_PODILU_ZAMERENI = 0.75
# Od jaké šířky se pořadí začne posouvat a kde je posun naplno. Pod dolní
# mezí se chová jako „vím to docela přesně", nad horní jako „chci si nechat
# otevřené dveře" — tedy přesně varianty otázky `rozhodnuto`, jejichž
# tabulky se mezi těmi mezemi interpolují.
SIRKA_ROZHODNUTO, SIRKA_OTEVRENO = 0.25, 0.75
# Od jaké šířky se uchazeče ptáme, jestli chce vidět i gymnázia a lycea,
# když si oblast „Všeobecné vzdělání" sám nezaškrtl.
PRAH_SIROKY_VYBER = 0.5


def sirka_vyberu(oblasti_zajmu: "Iterable[str]", zamereni: "Iterable[str]") -> float | None:
    """Jak široce má uchazeč zaškrtnuto (0 = úzce, 1 = skoro všechno).

    Vrací None, když se nedá nic změřit — uchazeč nezaškrtl žádnou oblast,
    nebo k jeho oblastem formulář žádná zaměření nenabízí. None znamená
    „neřaď podle toho", ne „zaškrtl úzce".
    """
    zvolene_oblasti = list(dict.fromkeys(oblasti_zajmu))
    if not zvolene_oblasti:
        return None
    nabizena = zamereni_oblasti(zvolene_oblasti)
    if not nabizena:
        return None
    # Jen zaměření, na která se u zvolených oblastí vůbec ptáme (stejné
    # pravidlo jako `Profil.hledana_zamereni`) — jinak by ručně poskládaný
    # profil mohl podílem přelézt jedničku.
    zvolena = {k for k in zamereni if k in nabizena}
    podil_zamereni = len(zvolena) / len(nabizena)
    # Jedna oblast = 0, dvě = 0,5, tři a víc = 1. Kdo si vybral tři oblasti
    # z dvanácti, už nevybírá směr, jen vylučuje.
    podil_oblasti = min(1.0, (len(zvolene_oblasti) - 1) / 2)
    return (VAHA_PODILU_ZAMERENI * podil_zamereni
            + (1 - VAHA_PODILU_ZAMERENI) * podil_oblasti)


def tabulka_sirky(sirka: float) -> dict[str, float]:
    """Tabulka typů odvozená ze šířky výběru.

    Interpoluje mezi tabulkami variant `obor` („vím to docela přesně") a
    `otevreno` („chci si nechat otevřené dveře") otázky `rozhodnuto` — ta
    je na tohle už nakalibrovaná, takže šířka nepřináší žádná nová čísla,
    jen jiný způsob, jak se na tutéž otázku dostat odpověď.
    """
    varianty = OSOBNOSTNI_OTAZKY["rozhodnuto"][1]
    presne, otevreno = varianty["obor"][1], varianty["otevreno"][1]
    t = (sirka - SIRKA_ROZHODNUTO) / (SIRKA_OTEVRENO - SIRKA_ROZHODNUTO)
    t = min(1.0, max(0.0, t))
    return {typ: presne.get(typ, 0.3) * (1 - t) + otevreno.get(typ, 0.3) * t
            for typ in set(presne) | set(otevreno)}


def preference_typu(odpovedi: dict[str, str | None],
                    sirka: float | None = None) -> dict[str, float]:
    """Z osobnostních odpovědí udělá skóre 0–1 pro každý typ vzdělání.

    `odpovedi` mapuje klíč otázky (`po_skole`, `rozhodnuto`, `praxe`) na
    zvolenou variantu; None nebo chybějící klíč se přeskočí. Když uchazeč
    neodpoví nic, vrátí pro všechny typy 0,5 — tedy „nevím, neřaď podle
    toho", ne „nic ti nesedí".

    `sirka` (0–1 z `sirka_vyberu`) **nahradí odpověď na `rozhodnuto`**, i
    když ji uchazeč vyplnil: zaškrtaná políčka jsou lepší důkaz než to, co
    o sobě u té otázky tvrdí. Viz komentář u `sirka_vyberu`.
    """
    tabulky = [
        varianty[odpoved][1]
        for klic, (_popis, varianty) in OSOBNOSTNI_OTAZKY.items()
        if (odpoved := odpovedi.get(klic)) in varianty
        and not (klic == "rozhodnuto" and sirka is not None)
    ]
    if sirka is not None:
        tabulky.append(tabulka_sirky(sirka))
    typy = [t for t in TYPY if t not in TYPY_MIMO_ZS]
    if not tabulky:
        return {t: 0.5 for t in typy}
    return {t: sum(tab.get(t, 0.3) for tab in tabulky) / len(tabulky) for t in typy}


def doporucene_typy(odpovedi: dict[str, str | None], trida: int = 9,
                    prah: float = 0.75, sirka: float | None = None) -> list[str]:
    """Typy, které podle odpovědí sedí nejlíp — pro větu „vyšlo ti…".

    Filtruje na typy dostupné z dané třídy a vrací je seřazené od nejlepší
    shody; `prah` je podíl nejvyššího skóre, pod který se už typ neuvádí.
    """
    skore = {t: s for t, s in preference_typu(odpovedi, sirka).items()
             if trida_prihlasky(t) == trida}
    if not skore:
        return []
    nejlepsi = max(skore.values())
    return [t for t, s in sorted(skore.items(), key=lambda x: -x[1])
            if s >= nejlepsi * prah]


def skupina(kod_kkov: str) -> str:
    """Vrátí první dvojčíslí kódu KKOV (skupinu oborů), např. ``63``."""
    return kod_kkov[:2]


def nazev_skupiny(kod_kkov: str) -> str:
    """Název skupiny oborů pro daný kód KKOV (neznámá skupina -> kód)."""
    return SKUPINY.get(skupina(kod_kkov), f"skupina {skupina(kod_kkov)}")


def oblasti_oboru(kod_kkov: str) -> tuple[str, ...]:
    """Klíče oblastí zájmu, do kterých obor spadá (může jich být víc)."""
    sk = skupina(kod_kkov)
    return tuple(k for k, (_, skupiny) in OBLASTI.items() if sk in skupiny)


def typ_oboru(kod_kkov: str) -> str | None:
    """Kód typu vzdělání (``G8``, ``M``, ``H``, …) z kódu KKOV.

    Formát KKOV je ``NN-NN-P/DD``: ``P`` je písmeno typu, ``DD`` poslední
    dvojčíslí. U gymnázií (``K``) rozlišuje délku (``81``/``61``/``41``),
    u ``L`` odlišuje obory s odborným výcvikem (``L/0x``) od nástaveb
    (``L/5x``). Vrací ``None``, pokud kód nemá očekávaný tvar.
    """
    if len(kod_kkov) < 10 or kod_kkov[6] != "-" and "/" not in kod_kkov:
        return None
    try:
        pismeno = kod_kkov.split("/")[0][-1].upper()
        dvojcisli = kod_kkov.split("/")[1][:2]
    except IndexError:
        return None
    if pismeno == "K":
        return {"81": "G8", "61": "G6", "41": "G4"}.get(dvojcisli, "G4")
    if pismeno == "L":
        return "L5" if dvojcisli.startswith("5") else "L0"
    if pismeno in ("M", "H", "E", "J", "C", "N", "P"):
        # Lyceum je maturitní obor (M) ve skupině 78 — pro uchazeče je to ale
        # jiná volba než odborná SOŠ, proto vlastní typ.
        if pismeno == "M" and skupina(kod_kkov) == "78":
            return "LYC"
        return pismeno
    return None


def popis_typu(typ: str | None) -> str:
    """Lidský popis typu vzdělání."""
    if typ is None:
        return "neznámý typ oboru"
    return TYPY.get(typ, (typ, 0, False))[0]


def trida_prihlasky(typ: str | None) -> int:
    """Ze které třídy ZŠ se na daný typ hlásí (0 = ne ze ZŠ)."""
    if typ is None:
        return 9
    return TYPY.get(typ, ("", 9, False))[1]


def s_maturitou(typ: str | None) -> bool:
    """Končí daný typ vzdělání maturitou?"""
    if typ is None:
        return False
    return TYPY.get(typ, ("", 0, False))[2]


# Pražské městské části (Praha 1–22) -> správní obvod, pod který spadají.
# V datech MŠMT (`organizace.obvod_prahy`, `misto_vyuky.obvod_prahy`) je jen
# deset správních obvodů Praha 1–10, jenže lidé se identifikují se svou
# **městskou částí** („bydlíme v Praze 12"). Bez tohohle překladu by uchazeč
# z Modřan svoji volbu ve formuláři vůbec nenašel. Ověřeno proti datům:
# školy v Modřanech a na Kamýku mají v rejstříku `obvod_prahy = 'Praha 4'`.
MC_NA_OBVOD: dict[str, str] = {
    **{f"Praha {i}": f"Praha {i}" for i in range(1, 11)},
    "Praha 11": "Praha 4",    # Chodov, Háje
    "Praha 12": "Praha 4",    # Modřany, Kamýk, Komořany
    "Praha 13": "Praha 5",    # Stodůlky, Nové Butovice
    "Praha 14": "Praha 9",    # Černý Most, Kyje
    "Praha 15": "Praha 10",   # Hostivař, Horní Měcholupy
    "Praha 16": "Praha 5",    # Radotín
    "Praha 17": "Praha 6",    # Řepy
    "Praha 18": "Praha 9",    # Letňany
    "Praha 19": "Praha 9",    # Kbely
    "Praha 20": "Praha 9",    # Horní Počernice
    "Praha 21": "Praha 9",    # Újezd nad Lesy
    "Praha 22": "Praha 10",   # Uhříněves
}


def obvod(mestska_cast: str) -> str:
    """Správní obvod pro městskou část; neznámou hodnotu vrátí beze změny."""
    return MC_NA_OBVOD.get(mestska_cast.strip(), mestska_cast.strip())


# Sousednost pražských správních obvodů (Praha 1–10). Používá se jako hrubá
# náhrada dojezdové doby MHD, dokud není naimportované GTFS (README, zdroj 12):
# škola v sousedním obvodu se nezahazuje, jen dostane nižší skóre blízkosti.
SOUSEDNI_OBVODY: dict[str, tuple[str, ...]] = {
    "Praha 1": ("Praha 2", "Praha 5", "Praha 6", "Praha 7", "Praha 8"),
    "Praha 2": ("Praha 1", "Praha 3", "Praha 4", "Praha 5", "Praha 10"),
    "Praha 3": ("Praha 2", "Praha 8", "Praha 9", "Praha 10"),
    "Praha 4": ("Praha 2", "Praha 5", "Praha 9", "Praha 10"),
    "Praha 5": ("Praha 1", "Praha 2", "Praha 4", "Praha 6"),
    "Praha 6": ("Praha 1", "Praha 5", "Praha 7"),
    "Praha 7": ("Praha 1", "Praha 6", "Praha 8"),
    "Praha 8": ("Praha 1", "Praha 3", "Praha 7", "Praha 9"),
    "Praha 9": ("Praha 3", "Praha 8", "Praha 10"),
    "Praha 10": ("Praha 2", "Praha 3", "Praha 4", "Praha 9"),
}
