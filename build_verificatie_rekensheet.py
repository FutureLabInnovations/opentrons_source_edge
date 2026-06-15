"""
Genereert een Excel-rekensheet voor dual-dye volume-verificatie bij laag volume.

Methode: ratiometrische fotometrie (Artel-principe) met goedkope food dyes.
  - Volume-dye:     Brilliant Blue FCF  (lees @ 630 nm)
  - Pathlength-dye: Tartrazine          (lees @ 450 nm, in de pre-fill)
  - Referentie:     @ 750 nm (blanco-venster, optioneel, haalt krassen/condens eruit)

Kernformule (per well):
  net630   = A630 - A750
  net450   = A450 - A750
  tar_corr = net450 - k * net630          (k = A450/A630 van PURE blauw -> crosstalk)
  ratio    = net630 / tar_corr
  Volume   = K * ratio                    (K = calibratieconstante)

Waarom dit werkt: A630 ~ gedispenseerd volume (totaalvolume valt weg, want hogere
pathlength * lagere concentratie = constant). De ratio met tartrazine corrigeert
voor well-tot-well variatie in welgeometrie/meniscus.
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

# ----- Stijlen -----
H1     = Font(bold=True, size=14, color="FFFFFF")
H2     = Font(bold=True, size=11)
BOLD   = Font(bold=True)
ITAL   = Font(italic=True, color="555555")
hdr_fill   = PatternFill("solid", fgColor="305496")
input_fill = PatternFill("solid", fgColor="FFF2CC")   # geel = invoer
calc_fill  = PatternFill("solid", fgColor="E2EFDA")    # groen = berekend
center = Alignment(horizontal="center", vertical="center")
thin   = Side(style="thin", color="BBBBBB")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

ROWS = ["A", "B", "C", "D", "E", "F", "G", "H"]   # 8 kanalen
COLS = list(range(1, 13))                          # 12 replicaten/kolommen

def grid_input(ws, title, default=0.0):
    """8x12 invoerraster, wells A1..H12. Data in Excel-rij 3..10, kolom B..M."""
    ws["A1"] = title
    ws["A1"].font = H2
    ws["A2"] = "rij \\ kolom"
    ws["A2"].font = BOLD
    for c in COLS:
        cell = ws.cell(row=2, column=1 + c, value=c)
        cell.font = BOLD; cell.alignment = center; cell.fill = hdr_fill
        cell.font = Font(bold=True, color="FFFFFF")
    for ri, r in enumerate(ROWS):
        ws.cell(row=3 + ri, column=1, value=r).font = BOLD
        ws.cell(row=3 + ri, column=1).alignment = center
        for c in COLS:
            cell = ws.cell(row=3 + ri, column=1 + c, value=default)
            cell.fill = input_fill; cell.border = border
            cell.number_format = "0.000"
    ws.column_dimensions["A"].width = 12

# =====================================================================
# SHEET 1: UITLEG
# =====================================================================
ws = wb.active
ws.title = "Uitleg"
ws.column_dimensions["A"].width = 100
uitleg = [
    ("Dual-dye volume-verificatie rekensheet (laag volume, ~1 uL)", H1, "305496"),
    ("", None, None),
    ("DOEL: nauwkeurigheid (%D) en precisie (CV) meten van lage-volume transfers,", ITAL, None),
    ("per kanaal, met goedkope food dyes op een gewone plate reader (bv. BioTek Epoch).", ITAL, None),
    ("", None, None),
    ("KLEURSTOFFEN", H2, None),
    ("  - Volume-dye:     Brilliant Blue FCF (FD&C Blue 1) -> lees @ 630 nm. Hoge epsilon = top gevoeligheid bij 1 uL.", None, None),
    ("  - Pathlength-dye: Tartrazine (FD&C Yellow 5)       -> lees @ 450 nm. Zit in de pre-fill, meet vloeistofhoogte.", None, None),
    ("  - Referentie:     @ 750 nm (optioneel) -> blanco-venster, haalt krassen/condens/verstrooiing eruit.", None, None),
    ("", None, None),
    ("WERKWIJZE", H2, None),
    ("  1. Pre-fill elke well met 200 uL tartrazine-oplossing (+0.01% Tween-20).", None, None),
    ("  2. CALIBRATIE: dispenseer een NAUWKEURIG bekend volume (bv. 10 uL, gravimetrisch geverifieerd)", None, None),
    ("     blauw-stock in een paar wells. Vul tabblad 'Parameters' in -> sheet berekent K.", None, None),
    ("  3. Meet eenmalig k (crosstalk): lees PURE blauw-oplossing @450 en @630, vul k = A450/A630 in.", None, None),
    ("  4. METING: dispenseer je testvolume (bv. 1 uL) blauw in alle wells, mix, lees @630/@450/@750.", None, None),
    ("  5. Plak de reader-export in de tabbladen 'A630', 'A450' en 'A750'.", None, None),
    ("  6. Lees resultaten af in 'Volumes' en 'Statistiek'.", None, None),
    ("", None, None),
    ("FORMULE (per well)", H2, None),
    ("  net630   = A630 - A750", None, None),
    ("  net450   = A450 - A750", None, None),
    ("  tar_corr = net450 - k * net630          (corrigeert blauw-staart bij 450 nm)", None, None),
    ("  ratio    = net630 / tar_corr", None, None),
    ("  Volume   = K * ratio                    (K uit calibratie)", None, None),
    ("", None, None),
    ("KLEURCODES: geel = jij vult in   |   groen = automatisch berekend", ITAL, None),
    ("In 'Statistiek': %D en CV worden rood (>10%), oranje (5-10%) of groen (<5%).", ITAL, None),
    ("", None, None),
    ("TIP: als je GEEN tartrazine/750 gebruikt (alleen blauw), laat die rasters op 0 staan en", ITAL, None),
    ("gebruik de simpele modus: zet in Parameters 'k'=0; de pathlength-correctie vervalt dan.", ITAL, None),
]
for i, (txt, font, fill) in enumerate(uitleg, start=1):
    c = ws.cell(row=i, column=1, value=txt)
    if font: c.font = font
    if fill: c.fill = PatternFill("solid", fgColor=fill)

# =====================================================================
# SHEET 2: PARAMETERS + CALIBRATIE
# =====================================================================
ws = wb.create_sheet("Parameters")
ws.column_dimensions["A"].width = 42
ws.column_dimensions["B"].width = 16
ws.column_dimensions["C"].width = 40

def prow(r, label, value, fmt=None, fill=None, note=""):
    ws.cell(row=r, column=1, value=label).font = BOLD
    c = ws.cell(row=r, column=2, value=value)
    if fmt: c.number_format = fmt
    if fill: c.fill = fill
    c.border = border; c.alignment = center
    if note:
        ws.cell(row=r, column=3, value=note).font = ITAL

ws["A1"] = "PARAMETERS"; ws["A1"].font = H1; ws["A1"].fill = hdr_fill
ws["A1"].font = H1

ws["A3"] = "Vaste / fysische constanten"; ws["A3"].font = H2
prow(4, "epsilon Brilliant Blue @630 (M-1 cm-1)", 130000, "0", input_fill, "literatuur ~130.000")
prow(5, "epsilon Tartrazine @450 (M-1 cm-1)", 27300, "0", input_fill, "informatief; K vangt dit op")
prow(6, "Blauw-stock concentratie (mg/mL)", 1.0, "0.000", input_fill, "~1 mg/mL geeft ~0.5 OD bij 1 uL in 200 uL")
prow(7, "Tartrazine pre-fill conc (mg/mL)", 0.030, "0.000", input_fill, "tune tot A450 ~0.5-1.0 OD")
prow(8, "Pre-fill volume V_pre (uL)", 200, "0", input_fill, "")
prow(9, "Doelvolume / target (uL)", 1.0, "0.000", input_fill, "wat je probeert te dispenseren")
prow(10, "Welgeometrie oppervlak (cm2)", 0.3217, "0.0000", input_fill, "96-well flat ~0.32 cm2 (informatief)")

ws["A12"] = "Crosstalk-correctie"; ws["A12"].font = H2
prow(13, "k = A450/A630 van PURE blauw", 0.100, "0.000", input_fill,
     "Meet 1x: lees pure blauw-oplossing @450 en @630. Zet 0 voor simpele modus.")

ws["A15"] = "CALIBRATIE  ->  bepaalt constante K"; ws["A15"].font = H2
prow(16, "Bekend gedispenseerd volume V_cal (uL)", 10.0, "0.000", input_fill,
     "Gebruik nauwkeurig/gravimetrisch geverifieerd volume")
prow(17, "Gemeten A630 (calibratie-well)", 0.500, "0.000", input_fill, "")
prow(18, "Gemeten A450 (calibratie-well)", 0.800, "0.000", input_fill, "")
prow(19, "Gemeten A750 (calibratie-well)", 0.000, "0.000", input_fill, "laat 0 indien niet gebruikt")
# afgeleide calibratie-waarden
ws.cell(row=20, column=1, value="  net630_cal = A630-A750").font = ITAL
ws.cell(row=20, column=2, value="=B17-B19").fill = calc_fill
ws.cell(row=21, column=1, value="  net450_cal = A450-A750").font = ITAL
ws.cell(row=21, column=2, value="=B18-B19").fill = calc_fill
ws.cell(row=22, column=1, value="  tar_corr_cal = net450 - k*net630").font = ITAL
ws.cell(row=22, column=2, value="=B21-B13*B20").fill = calc_fill
ws.cell(row=23, column=1, value="  ratio_cal = net630/tar_corr").font = ITAL
ws.cell(row=23, column=2, value="=IFERROR(B20/B22,\"\")").fill = calc_fill

ws["A25"] = "K (calibratieconstante)"; ws["A25"].font = Font(bold=True, size=12)
kc = ws.cell(row=25, column=2, value="=IFERROR(B16/B23,\"\")")
kc.fill = PatternFill("solid", fgColor="C6E0B4"); kc.font = Font(bold=True, size=12)
kc.number_format = "0.0000"; kc.border = border; kc.alignment = center
ws.cell(row=25, column=3, value="Volume = K * ratio  (wordt door 'Volumes' gebruikt)").font = ITAL

# Handige named refs (via celcoordinaten in formules)
K_CELL      = "Parameters!$B$25"
K_CROSSTALK = "Parameters!$B$13"
TARGET_CELL = "Parameters!$B$9"

# =====================================================================
# SHEETS 3-5: RUWE METINGEN
# =====================================================================
ws630 = wb.create_sheet("A630")
grid_input(ws630, "Ruwe absorbantie @ 630 nm  (Brilliant Blue = volume-dye)   -- plak reader-export hier", 0.0)
ws450 = wb.create_sheet("A450")
grid_input(ws450, "Ruwe absorbantie @ 450 nm  (Tartrazine = pathlength-dye)    -- plak reader-export hier", 0.0)
ws750 = wb.create_sheet("A750")
grid_input(ws750, "Ruwe absorbantie @ 750 nm  (referentie/blanco -- optioneel, laat 0 indien ongebruikt)", 0.0)

# =====================================================================
# SHEET 6: VOLUMES (berekend)
# =====================================================================
wsv = wb.create_sheet("Volumes")
wsv["A1"] = "Berekend gedispenseerd volume per well (uL)"
wsv["A1"].font = H2
wsv["A2"] = "rij \\ kolom"; wsv["A2"].font = BOLD
for c in COLS:
    cell = wsv.cell(row=2, column=1 + c, value=c)
    cell.font = Font(bold=True, color="FFFFFF"); cell.alignment = center; cell.fill = hdr_fill
for ri, r in enumerate(ROWS):
    wsv.cell(row=3 + ri, column=1, value=r).font = BOLD
    wsv.cell(row=3 + ri, column=1).alignment = center
    for c in COLS:
        col_letter = get_column_letter(1 + c)
        er = 3 + ri
        net630 = f"('A630'!{col_letter}{er}-'A750'!{col_letter}{er})"
        net450 = f"('A450'!{col_letter}{er}-'A750'!{col_letter}{er})"
        tarcorr = f"({net450}-{K_CROSSTALK}*{net630})"
        ratio = f"{net630}/{tarcorr}"
        formula = f"=IFERROR({K_CELL}*({ratio}),\"\")"
        cell = wsv.cell(row=er, column=1 + c, value=formula)
        cell.fill = calc_fill; cell.border = border; cell.number_format = "0.000"
        cell.alignment = center
wsv.column_dimensions["A"].width = 12
wsv["A12"] = "Tip: lege/0 cellen in de invoer geven lege cellen hier (IFERROR).".replace("0", "nul")
wsv["A12"].font = ITAL

# =====================================================================
# SHEET 7: STATISTIEK (per kolom)
# =====================================================================
wss = wb.create_sheet("Statistiek")
wss["A1"] = "Statistiek per kolom (replicaten = 8 kanalen A-H)"
wss["A1"].font = H1; wss["A1"].fill = hdr_fill; wss["A1"].font = H1
wss["A3"] = "Kolom"; wss["A3"].font = BOLD
for c in COLS:
    cell = wss.cell(row=3, column=1 + c, value=c)
    cell.font = Font(bold=True, color="FFFFFF"); cell.alignment = center; cell.fill = hdr_fill

stat_rows = [
    (4, "Gemiddelde (uL)", "0.000"),
    (5, "%D (afwijking)", "0.0%"),
    (6, "SD (uL)", "0.000"),
    (7, "CV", "0.0%"),
]
for r, label, fmt in stat_rows:
    wss.cell(row=r, column=1, value=label).font = BOLD
for ci, c in enumerate(COLS):
    col_letter = get_column_letter(1 + c)
    rng = f"Volumes!{col_letter}3:{col_letter}10"
    # Gemiddelde
    m = wss.cell(row=4, column=1 + c, value=f"=IFERROR(AVERAGE({rng}),\"\")")
    m.number_format = "0.000"; m.alignment = center; m.border = border
    mcell = f"{get_column_letter(1+c)}4"
    # %D
    d = wss.cell(row=5, column=1 + c,
                 value=f"=IFERROR(({mcell}-{TARGET_CELL})/{TARGET_CELL},\"\")")
    d.number_format = "0.0%"; d.alignment = center; d.border = border
    # SD
    s = wss.cell(row=6, column=1 + c, value=f"=IFERROR(STDEV({rng}),\"\")")
    s.number_format = "0.000"; s.alignment = center; s.border = border
    scell = f"{get_column_letter(1+c)}6"
    # CV
    cv = wss.cell(row=7, column=1 + c, value=f"=IFERROR({scell}/{mcell},\"\")")
    cv.number_format = "0.0%"; cv.alignment = center; cv.border = border

wss.column_dimensions["A"].width = 18

# Conditionele opmaak (zoals jullie Run A/B/C tabellen)
red    = PatternFill("solid", fgColor="F8696B")
orange = PatternFill("solid", fgColor="FFC000")
green  = PatternFill("solid", fgColor="C6E0B4")
for row_idx in (5, 7):  # %D en CV
    rng = f"{get_column_letter(2)}{row_idx}:{get_column_letter(13)}{row_idx}"
    # rood als |waarde| > 10%
    wss.conditional_formatting.add(rng,
        CellIsRule(operator="greaterThan", formula=["0.10"], fill=red))
    wss.conditional_formatting.add(rng,
        CellIsRule(operator="lessThan", formula=["-0.10"], fill=red))
    # oranje 5-10%
    wss.conditional_formatting.add(rng,
        CellIsRule(operator="between", formula=["0.05", "0.10"], fill=orange))
    wss.conditional_formatting.add(rng,
        CellIsRule(operator="between", formula=["-0.10", "-0.05"], fill=orange))
    # groen < 5%
    wss.conditional_formatting.add(rng,
        CellIsRule(operator="between", formula=["-0.05", "0.05"], fill=green))

wss["A10"] = "Rood = |%D| of CV > 10%   |   Oranje = 5-10%   |   Groen = < 5%"
wss["A10"].font = ITAL

# Samenvatting over alle wells
wss["A12"] = "Totaaloverzicht (alle wells)"; wss["A12"].font = H2
allrng = "Volumes!B3:M10"
wss["A13"] = "Gemiddelde (uL)"; wss["A13"].font = BOLD
wss["B13"] = f"=IFERROR(AVERAGE({allrng}),\"\")"; wss["B13"].number_format = "0.000"
wss["A14"] = "Globale %D"; wss["A14"].font = BOLD
wss["B14"] = f"=IFERROR((B13-{TARGET_CELL})/{TARGET_CELL},\"\")"; wss["B14"].number_format = "0.0%"
wss["A15"] = "Globale SD (uL)"; wss["A15"].font = BOLD
wss["B15"] = f"=IFERROR(STDEV({allrng}),\"\")"; wss["B15"].number_format = "0.000"
wss["A16"] = "Globale CV"; wss["A16"].font = BOLD
wss["B16"] = "=IFERROR(B15/B13,\"\")"; wss["B16"].number_format = "0.0%"

# Tabbladvolgorde
wb.move_sheet("Uitleg", -wb.sheetnames.index("Uitleg"))

out = "/home/user/opentrons_source_edge/dual_dye_volume_verificatie.xlsx"
wb.save(out)
print("Opgeslagen:", out)
print("Tabbladen:", wb.sheetnames)
