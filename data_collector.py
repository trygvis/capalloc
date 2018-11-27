# For collecting part information from documents with part numbers.
# Copyright 2018 Magnus Sollien Sjursen <m@didakt.no>

from decimal import Decimal
from functools import reduce
import re

# Capacitor size codes
# IEC (JEDEC) | EIA
# metric | inch
size_m_to_i = {
    "0402": "01005",
    "0404": "015015",
    "0603": "0201",
    "0505": "0202",
    "0805": "0302",
    "0808": "0303",
    "1310": "0504",
    "1005": "0402",
    "1608": "0603",
    "2012": "0805",
    "2520": "1008",
    "2828": "1111",
    "3216": "1206",
    "3225": "1210",
    "3625": "1410",
    "3838": "1515",
    "4516": "1806",
    "4520": "1808",
    "4532": "1812",
    "4564": "1825",
    "5025": "2010",
    "5050": "2020",
    "5750": "2220",
    "5764": "2225",
    "6432": "2512",
    "6450": "2520",
    "7450": "2920",
    "7563": "3025", # EIA size 3025 found in TDK datasheet.
    "8484": "3333",
    "9210": "4040",
    "100100": "4040",
    "140127": "5550",
    "203153": "8060"}

size_i_to_m = {}
for key in size_m_to_i:
    size_i_to_m[size_m_to_i[key]] = key

class Capacitor:
    def __init__(self):
        self.mpn = None

    def __str__(self):
        return "Capacitor: {}".format(self.mpn)
        
    def __eq__(self, other):
        return self.mpn == other.mpn

class TempChar:
    def __init__(self, code):
        self.code = code
        
        # Analyse temperature characteristic.
        if (code == "C0G" or code == "NP0"):
            min_temp = Decimal(-55)
            max_temp = Decimal(125)
            # (125 - (-55)) °C * 30e-6/°C = 0.54 %
            self.tol = [Decimal(-0.54), Decimal(0.54)]
            self.ceramic_class = "1"
        else:
            self.ceramic_class = "2"
            min_temps = {
                "X": Decimal(-55),
                "Y": Decimal(-30),
                "Z": Decimal(10)}
            min_temp = min_temps[code[0]]

            max_temps = {
                "4": Decimal(65),
                "5": Decimal(85),
                "6": Decimal(105),
                "7": Decimal(125),
                "8": Decimal(150),
                "9": Decimal(200)}
            max_temp = max_temps[code[1]]

            tols = {
                "P": [Decimal(-10), Decimal(10)],
                "R": [Decimal(-15), Decimal(15)],
                # "L": [-15, 15] [-40, 15] above 125°C
                "S": [Decimal(-22), Decimal(22)],
                "T": [Decimal(-33), Decimal(22)],
                "U": [Decimal(-56), Decimal(22)],
                "V": [Decimal(-82), Decimal(22)]}
            self.tol = tols[code[2]]

        self.temp = [min_temp, max_temp]

class CapacitorParser:
    def __init__(self):
        pass

    @staticmethod
    def parse_match(match):
        raise NotImplementedError("No regex match parser has been set.")

# Parser for TDK MLCC MPNs
# Group index: 11123455566778911111
#              00000000000000000012
# Example mpn: CGADN3X7R1E476M230LE
# series       ^^^||||  | |  ||  || CGA
# size            ^|||  | |  ||  || EIA 3025
# thickness        ^||  | |  ||  || 2.30 mm
# voltage condition ^|  | |  ||  || 1.5 x rated voltage
# characteristic     ^^^| |  ||  || X7R
# rated voltage         ^^|  ||  || 25 V
# capacitance             ^^^||  || 47 µF
# tolerance                  ^|  || ±20 %
# thickness                   ^^^|| 2.30 mm
# packaging                      ^| 330 mm reel, 12 mm pitch
# special reserved code           ^ Soft termination
class TdkParser(CapacitorParser):
    regex = re.compile(
        "(CGA)" + \
        "([2-9D])" + \
        "([BCEFHJKLMNP])" + \
        "([1234])" + \
        "(C0G|X7R|X7S|X7T|X8R)" + \
        "(0J|1A|1C|1E|1V|1H|2A|2E|2W|2J|3A|3D|3F)" + \
        "([0-9]{2})" + \
        "([0-9])" + \
        "(J|K|M)" + \
        "([0-9]{3})" + \
        "(A|B|K|L)" + \
        "(E)", \
        re.MULTILINE)

    def __init__(self):
        pass

    @staticmethod
    def parse_match(match):
        c = Capacitor()
        c.m = "TDK"
        c.mpn = reduce(lambda x, y: x + y, match)
        
        c.series = match[0]
        
        # Parameter: Dimension
        sizes = {
            "2": size_i_to_m["0402"],
            "3": size_i_to_m["0603"],
            "4": size_i_to_m["0805"],
            "5": size_i_to_m["1206"],
            "6": size_i_to_m["1210"],
            "7": size_i_to_m["1808"],
            "8": size_i_to_m["1812"],
            "9": size_i_to_m["2220"],
            "D": size_i_to_m["3025"]}
        c.size = sizes[match[1]]

        # Parameter: Thickness
        thicknesses = {
        "B": Decimal(50)/100,
        "C": Decimal(60)/100,
        "E": Decimal(80)/100,
        "F": Decimal(85)/100,
        "H": Decimal(115)/100,
        "J": Decimal(125)/100,
        "K": Decimal(130)/100,
        "L": Decimal(160)/100,
        "M": Decimal(200)/100,
        "N": Decimal(230)/100,
        "P": Decimal(250)/100}
        c.thickness = thicknesses[match[2]]
  
        # Parameter: Thickness
        # In this MPN thickness is defined twice -
        # check if they agree.
        thickness_2 = Decimal(match[9])/Decimal(100)
        if (c.thickness != thickness_2):
            print(match[2])
            print(c.thickness)
            print(thickness_2)
            raise ValueError("Mismatching thicknesses.")

        # Parameter: Voltage condition for life test
        # (ignored) match[3]

        # Parameter: Temperature characteristic
        c.temp = TempChar(match[4])

        # Parameter: Rated voltage
        voltages = {
        "0J": Decimal(   6.3),
        "1A": Decimal(  10.0),
        "1C": Decimal(  16.0),
        "1E": Decimal(  25.0),
        "1V": Decimal(  35.0),
        "1H": Decimal(  50.0),
        "2A": Decimal( 100.0),
        "2E": Decimal( 250.0),
        "2W": Decimal( 450.0),
        "2J": Decimal( 630.0),
        "3A": Decimal(1000.0),
        "3D": Decimal(2000.0),
        "3F": Decimal(3000.0)}
        c.voltage = voltages[match[5]]

        # Parameter: Nominal capacitance
        e = Decimal(match[7]) - Decimal(12)
        c.capVal = Decimal(match[6])*(Decimal(10)**e)

        # Parameter: Capacitance tolerance
        # Consider using python-intervals
        tols = {
        "J": [Decimal(-5), Decimal(5)],
        "K": [Decimal(-10), Decimal(10)],
        "M": [Decimal(-20), Decimal(20)]}
        c.tol = tols[match[8]]

        # Parameter: Packaging style
        # (ignore) match[10]

        # Parameter: Special reserved code
        if (match[11] == "E"):
            c.flexterm = "Soft termination"
        else:
            raise ValueError("Unknown special code \"" + match[11] + "\".")
  
        return c

# Parser for Samsung MLCC MPNs
# Group index: 112234456789111
#              000000000000012
# Example mpn: CL31B106KOHZFNE
# series       ^^| ||  ||||||| CL
# size           ^^||  ||||||| EIA 1206 (3216)
# temp char.       ^|  ||||||| X7R
# capacitance       ^^^||||||| 10 µF
# tolerance            ^|||||| ±10 %
# rated voltage         ^||||| 16 V
# thickness              ^|||| 1.6 mm
# termination             ^||| Ni, Soft termination, Sn 100 %
# product code             ^|| For POWER application
# special                   ^| Reserved code
# packaging                  ^ Embossed, 7" reel
class SamsungParser(CapacitorParser):
    regex = re.compile(
        "(CL)" + \
        "(03|05|10|21|31|32|43|55)" + \
        "([ABCFLPRSTUXY])" + \
        "([0-9][0-9R])" + \
        "([0-9])" + \
        "([ABCDFGJKMZ])" + \
        "([ABCDEGHIJKLOPQR])" + \
        "([3568ACFHIJLQVYU])" + \
        "([ANGZSY])" + \
        "([ABCFLNPW4N])" + \
        "([N6JW])" + \
        "([BCDEFLOPSG])", \
        re.MULTILINE)
        
    def __init__(self):
        pass

    @staticmethod
    def parse_match(match):
        c = Capacitor()
        c.m = "Samsung"
        c.mpn = reduce(lambda x, y: x + y, match)
        c.series = match[0]
  
        # Parameter: Size
        sizes = {
            "03": size_i_to_m["0201"],
            "05": size_i_to_m["0402"],
            "10": size_i_to_m["0603"],
            "21": size_i_to_m["0805"],
            "31": size_i_to_m["1206"],
            "32": size_i_to_m["1210"],
            "43": size_i_to_m["1812"],
            "55": size_i_to_m["2220"]}
        c.size = sizes[match[1]]

        # Parameter: Temperature characteristic
        characteristics = {
            "C": "C0G",
            "P": "P2H",
            "R": "R2H",
            "S": "S2H",
            "T": "T2H",
            "U": "U2J",
            "L": "S2L",
            "A": "X5R",
            "B": "X7R",
            "Y": "X7S",
            "X": "X6S",
            "F": "Y5V"}
        tempchar = characteristics[match[2]]
        c.temp = TempChar(tempchar)
  
        # Parameter: Nominal capacitance
        e = Decimal(match[4]) - Decimal(12)
        c.capVal = Decimal(match[3])*(10**e)

        # Parameter: Capacitance tolerance
        tols = {
            "F": [Decimal(-1), Decimal(1)],
            "G": [Decimal(-2), Decimal(2)],
            "J": [Decimal(-5), Decimal(5)],
            "K": [Decimal(-10), Decimal(10)],
            "M": [Decimal(-20), Decimal(20)],
            "Z": [Decimal(-20), Decimal(80)]}
        c.tol = tols[match[5]]

        # Parameter: Rated voltage
        voltages = {
            "R": Decimal(   4.0),
            "Q": Decimal(   63)/10,
            "P": Decimal(  10.0),
            "O": Decimal(  16.0),
            "A": Decimal(  25.0),
            "L": Decimal(  35.0),
            "B": Decimal(  50.0),
            "C": Decimal( 100.0),
            "D": Decimal( 200.0),
            "E": Decimal( 250.0),
            "G": Decimal( 500.0),
            "H": Decimal( 630.0),
            "I": Decimal(1000.0),
            "J": Decimal(2000.0),
            "K": Decimal(3000.0)}
        c.voltage = voltages[match[6]]
  
        # Parameter: Thickness
        thicknesses = {
            "3": Decimal(30)/100,
            "5": Decimal(50)/100,
            "6": Decimal(60)/100,
            "8": Decimal(80)/100,
            "A": Decimal(65)/100,
            "C": Decimal(85)/100,
            "F": Decimal(125)/100,
            "Q": Decimal(125)/100,
            "Y": Decimal(125)/100,
            "H": Decimal(160)/100,
            "U": Decimal(180)/100,
            "I": Decimal(200)/100,
            "J": Decimal(250)/100,
            "V": Decimal(250)/100,
            "L": Decimal(320)/100}
        c.thickness = thicknesses[match[7]]

        # Parameter: Product and plating method
        # Z:
        # S: Ni, Soft termination, Sn 100 %
        if (match[8] == "Z" or match[8] == "S"):
            c.flexterm = "Soft termination"
        elif (match[8] == "Y"):
            c.flexterm = "Cu/Ag-Epoxy"
  
        # Parameter: Product code (Samsung control code)
        # (ignore) match[10]
        # N: Normal
        # 4: Industrial (Network, power, etc)
        # W: Industrial (Network, power, etc)
        # F: Product for POWER application

        # Parameter: Reserved code
        # (ignore) match[11]
        # N: Reserved code
        # 6: Higher bending strength
        # J: Higher bending strength
        # W: Industrial (Network, power, etc)

        # Parameter: Packaging type
        # (ignore) match[12]
        # E: Embossed type, 7" reel
        # G: Embossed type, 7" reel
        # C: Cardboard type, 7" reel
  
        return c

# Parser for Kemet MLCC MPNs
# Group index: 1222234456789111
#              0000000000000011
# Example mpn: C1206C106M4RACTU
# type         ^|   ||  ||||||
# size          ^^^^||  ||||||
# series            ^|  ||||||
# capacitance        ^^^||||||
# tolerance             ^|||||
# volage                 ^||||
# temperature             ^|||
# failure rate             ^||
# termination               ^|
# packaging                  ^^
class KemetParser(CapacitorParser):
    regex = re.compile(
        "(C)" + \
        "([0-9]{4})" + \
        "([CXFJSYTVW])" + \
        "([0-9][0-9R])" + \
        "([0-9])" + \
        "([BCDFGJKMZ])" + \
        "([798436512ACBDFGZH])" + \
        "([GHJNPRUV])" + \
        "([ABC12])" + \
        "([CL])" + \
        "(TU|7411|7210|TM|7040|7013|7025|7215|7081|7082|" + \
        "7186|7289|7800|7805|7810|7867|9028|9239|3325|AUTO|" + \
        "AUTO7411|AUTO7210|AUTO7289|)", \
        re.MULTILINE)

    def __init__(self):
        pass

    @staticmethod
    def parse_match(match):
        c = Capacitor()
        c.m = "Kemet"
        c.mpn = reduce(lambda x, y: x + y, match)
        c.type = match[0]
        c.size = size_i_to_m[match[1]]
  
        if (match[2] == "C"):
            c.series = "Standard"
        elif(match[2] == "X"):
            c.series = "Flexible termination"
            c.flexterm = "Flexible termination"
        elif (match[2] == "F"):
            c.series = "Open mode"
        elif (match[2] == "J"):
            c.series = "Open mode"
            c.flexterm = "Flexible termination"
        elif (match[2] == "S"):
            c.series = "Floating electrode"
        elif (match[2] == "Y"):
            c.series = "Floating electrode with flexible termination"
            c.flexterm = "Flexible termination"
        elif (match[2] == "V"):
            c.series = "ArcShield"
        elif (match[2] == "W"):
            c.series = "ArcShield with flexible termination"
            c.flexterm = "Flexible termination"
        elif (match[2] == "T"):
            c.series = "COTS"
            if (match[8] == "A"):
                c.design = "MIL-PRF-55681 PDA 8 %"
            elif (match[8] == "B"):
                c.design = "MIL-PRF-556851 PDA 8 %, DPA EIA-469"
            elif (match[8] == "C"):
                c.design = \
                    "MIL-PRF-55681 PDA 8 %, DPA EIA-469, MIL-STD-202 103 A"
        else:
            c.series = match[2]
  
        # Parameter: Nominal capacitance
        if (match[4] == "9"):
            e = Decimal(-13)
        elif (match[4] == "8"):
            e = Decimal(-14)
        else:
            e = Decimal(match[4]) - Decimal(12)
        c.capVal = Decimal(match[3])*(Decimal(10)**e)

        # Parameter: Capacitance tolerance
        tols = {
            "F": [Decimal(-1), Decimal(1)],
            "G": [Decimal(-2), Decimal(2)],
            "J": [Decimal(-5), Decimal(5)],
            "K": [Decimal(-10), Decimal(10)],
            "M": [Decimal(-20), Decimal(20)],
            "Z": [Decimal(-20), Decimal(80)]}
        c.tol = tols[match[5]]
  
        # Parameter: Rated voltage
        voltages = {
            "7": Decimal(4),
            "9": Decimal(63)/10,
            "8": Decimal(10),
            "4": Decimal(16),
            "3": Decimal(25),
            "6": Decimal(35),
            "5": Decimal(50),
            "1": Decimal(100),
            "2": Decimal(200),
            "A": Decimal(250),
            "C": Decimal(500),
            "B": Decimal(630),
            "D": Decimal(1000),
            "F": Decimal(1500),
            "G": Decimal(2000),
            "Z": Decimal(2500),
            "H": Decimal(3000)}
        c.voltage = voltages[match[6]]
  
        # Parameter: Temperature characteristic
        temps = {
            "G": "C0G",
            "H": "X8R",
            "J": "U2J",
            "N": "X8L",
            "P": "X5R",
            "R": "X7R",
            "U": "Z5U",
            "V": "Y5V"}
        tempchar = temps[match[7]]
        c.temp = TempChar(tempchar)
  
        # Parameter: Failure rate / design
        if (hasattr(c, "design")):
            if (match[8] == "A"):
                pass
            elif (match[8] == "1"):
                c.design = "KPS Single chip stack"
            elif (match[8] == "2"):
                c.design = "KPS Double chip stack"

        # Parameter: Termination
        terms = {
            "C": "Sn 100 %",
            "L": "SnPb (Pb > 5 %)"}
        c.term = terms[match[9]]

        # Parameter: Packaging
        packagings = {
            "": "bulk bag",
            "TU": "7\" reel, unmarked",
            "7411": "13\" reel, unmarked",
            "7210": "13\" reel, unmarked",
            "7867": "13\" reel, unmarked",
            "TM": "7\" reel, marked",
            "7013": "7\" reel, marked",
            "7025": "7\" reel, marked",
            "7040": "13\" reel, marked",
            "7215": "13\" reel, marked",
            "7081": "7\" reel, unmarked, 2 mm pitch",
            "7082": "13\" reel, unmarked, 2 mm pitch",
            "7800": "7\" reel, unmarked",
            "7805": "7\" reel, unmarked",
            "7810": "13\" reel, unmarked",
            "9028": "special bulk casette, unmarked",
            "3325": "special bulk casette, marked",
            "7186": "7\" reel, unmarked",
            "7289": "13\" reel, unmarked",
            "AUTO": "7\" reel, plastic, auto grade",
            "AUTO7289": "13\" reel, plastic, auto grade", 
            "AUTO7411": "13\" reel, paper, auto grade", 
            "AUTO7210": "13\" reel, plastic, auto grade"}
        c.pack = packagings[match[10]]
  
        return c

class DataSource:
    def __init__(self, filename, parser):
        self.filename = filename
        self.parser = parser
    
    def parse_data(self):
        f = open(self.filename, 'r', encoding="utf-8")
        s = f.read()
        
        matches = self.parser.regex.findall(s)
        
        items = []
        for match in matches:
            item = self.parser.parse_match(match)
            # Only append new part numbers
            # FIXME: Consider a more efficient algorithm
            if (not item in items):
                items.append(item)

        return items

capacitors = []
data_sources = []
# 554 pcs
data_sources.append(DataSource("data/tdk_flex.capacitor", TdkParser))
# 134 pcs
data_sources.append(DataSource("data/samsung_flex.capacitor", SamsungParser))
data_sources.append(DataSource("data/kemet/c1.html", KemetParser)) # 500 pcs
data_sources.append(DataSource("data/kemet/c2.html", KemetParser)) # 500 pcs
data_sources.append(DataSource("data/kemet/c3.html", KemetParser)) # 500 pcs
data_sources.append(DataSource("data/kemet/c4.html", KemetParser)) # 500 pcs
data_sources.append(DataSource("data/kemet/c5.html", KemetParser)) # 500 pcs
data_sources.append(DataSource("data/kemet/c6.html", KemetParser)) # ? pcs
# 17 pcs
data_sources.append(DataSource("data/kemet/csmall_test.html", KemetParser))

for source in data_sources:
    capacitors += source.parse_data()

for cap in capacitors:
    print(cap)

print(len(capacitors))