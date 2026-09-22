"""Známé hodnoty číselníků MŠMT.

Oficiální číselníky (AKDT, RAFS, RADS, BBJK, ...) nejsou v JSON schématu
ani nebyly online dohledány. Hodnoty níže jsou odvozené z dat rejstříku;
``overeno=True`` jen tam, kde je význam potvrzený na konkrétním záznamu.
"""

# (ciselnik, kod, nazev, overeno)
ZNAME_KODY: list[tuple[str, str, str, bool]] = [
    # AKDT – druh školy / školského zařízení
    ("AKDT", "A00", "Mateřská škola", False),
    ("AKDT", "B00", "Základní škola", False),
    ("AKDT", "C00", "Střední škola", True),
    ("AKDT", "E00", "Konzervatoř / vyšší odborná škola (odhad)", False),
    ("AKDT", "G21", "Školní družina (odhad)", False),
    ("AKDT", "G22", "Školní klub (odhad)", False),
    ("AKDT", "L11", "Školní jídelna (odhad)", False),
    ("AKDT", "L13", "Školní jídelna – výdejna (odhad)", False),
    # RAFS – forma vzdělávání
    ("RAFS", "10", "Denní (odhad)", False),
    ("RAFS", "22", "Dálková (odhad)", False),
    ("RAFS", "23", "Distanční (odhad)", False),
    ("RAFS", "24", "Kombinovaná (odhad)", False),
    ("RAFS", "30", "Večerní (odhad)", False),
    # RADS – délka vzdělávání (kód = roky × 10, odhad z dat)
    ("RADS", "10", "1 rok", False),
    ("RADS", "20", "2 roky", False),
    ("RADS", "30", "3 roky", False),
    ("RADS", "35", "3,5 roku", False),
    ("RADS", "40", "4 roky", True),
    ("RADS", "50", "5 let", False),
    ("RADS", "60", "6 let", False),
    ("RADS", "80", "8 let", False),
    ("RADS", "90", "9 let (odhad)", False),
    # BBJK – měrná jednotka kapacity
    ("BBJK", "01", "Žáci / studenti", True),
    # BAZS – typ zřizovatele
    ("BAZS", "7", "Kraj / hl. m. Praha (odhad)", False),
]
