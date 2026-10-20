"""Example board script: a USB-powered 3.3 V LDO with a power LED.

Run: python3 example_board.py   (runs the checks, prints the netlist, exits 1 on any error)

This is the design source. A generator reads P / NC / DNP and writes the KiCad project; it never invents
connectivity. Every datasheet rule the design depends on is a check below, so a later edit that breaks one fails
the build instead of reaching the fab.
"""
import sys
from collections import defaultdict

P = {}          # ref: (kind, value, sheet, {pin: net}, note)
NC = {}         # ref: [pins deliberately left unconnected]
DNP = set()     # refs on the schematic but not fitted


def part(ref, kind, value, sheet, pins, note=""):
    assert ref not in P, f"duplicate ref {ref}"
    P[ref] = (kind, value, sheet, pins, note)


VBUS, V33, GND = "VBUS", "+3V3", "GND"

# datasheet numbers the checks use (cite the revision you read)
LDO_VIN_MAX = 6.0        # AP2112K absolute max input
LDO_IOUT_MAX = 0.6       # A
LDO_C_MIN = 1.0e-6       # input and output caps, ceramic
LED_VF, LED_IF_MAX = 2.0, 0.020
V_USB_MAX = 5.25         # USB 2.0 VBUS upper limit
LOAD_A = 0.25            # what the rest of the design draws from +3V3

part("J1", "connector", "USB-C receptacle (power only)", "power",
     {"VBUS": VBUS, "GND": GND, "CC1": "CC1", "CC2": "CC2"})
part("R1", "res", "5.1k 0402 (CC1 pull-down)", "power", {"1": "CC1", "2": GND}, "sink advertisement, USB-C spec")
part("R2", "res", "5.1k 0402 (CC2 pull-down)", "power", {"1": "CC2", "2": GND})
part("U1", "ldo", "AP2112K-3.3 (SOT-23-5)", "power",
     {"VIN": VBUS, "GND": GND, "EN": VBUS, "VOUT": V33}, "EN tied to VIN: always on")
NC["U1"] = ["NC"]
part("C1", "cap", "1 uF 10 V X5R 0402", "power", {"1": VBUS, "2": GND}, "LDO input cap")
part("C2", "cap", "1 uF 10 V X5R 0402", "power", {"1": V33, "2": GND}, "LDO output cap")
part("R3", "res", "1k 0402 (LED)", "power", {"1": V33, "2": "LED_A"})
part("D1", "led", "green 0603", "power", {"A": "LED_A", "K": GND})
part("TP1", "testpad", "+3V3", "power", {"1": V33})

LDO_PINS = {"VIN", "GND", "EN", "VOUT", "NC"}


def farads(value):
    num, unit = value.split()[:2]
    return float(num) * {"pF": 1e-12, "nF": 1e-9, "uF": 1e-6}[unit]


def ohms(value):
    num = value.split()[0]
    return float(num[:-1]) * 1e3 if num.endswith("k") else float(num)


def checks():
    errs = []
    nets = defaultdict(list)
    for ref, (_, _, _, pins, _) in P.items():
        for pin, net in pins.items():
            nets[net].append(f"{ref}.{pin}")
    # connectivity: no single-pin nets, every IC pin is connected or listed as NC
    for net, conns in nets.items():
        if len(conns) < 2:
            errs.append(f"net {net} has one connection: {conns}")
    missing = LDO_PINS - set(P["U1"][3]) - set(NC.get("U1", []))
    if missing:
        errs.append(f"U1 pins not connected and not NC: {sorted(missing)}")
    # datasheet rules
    if V_USB_MAX > LDO_VIN_MAX:
        errs.append(f"VBUS {V_USB_MAX} V exceeds the LDO's {LDO_VIN_MAX} V max")
    if LOAD_A > LDO_IOUT_MAX:
        errs.append(f"load {LOAD_A} A exceeds the LDO's {LDO_IOUT_MAX} A")
    for net in (VBUS, V33):
        caps = [r for r, (k, val, _, pins, _) in P.items() if k == "cap" and set(pins.values()) == {net, GND}]
        if sum(farads(P[r][1]) for r in caps if r not in DNP) < LDO_C_MIN:
            errs.append(f"{net}: less than {LDO_C_MIN * 1e6:.0f} uF of ceramic next to the LDO")
    i_led = (3.3 - LED_VF) / ohms(P["R3"][1])
    if i_led > LED_IF_MAX:
        errs.append(f"LED current {i_led * 1e3:.1f} mA over {LED_IF_MAX * 1e3:.0f} mA")
    if P["U1"][3]["EN"] not in (VBUS, "EN"):
        errs.append("U1 EN must be driven (tied to VIN or a GPIO net)")
    return nets, errs


if __name__ == "__main__":
    nets, errs = checks()
    for net, conns in sorted(nets.items()):
        print(f"{net:<8} {' '.join(conns)}")
    for e in errs:
        print("ERROR", e)
    print(f"{len(P)} parts, {len(nets)} nets, {len(errs)} errors")
    sys.exit(1 if errs else 0)
