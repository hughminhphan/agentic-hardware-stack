---
name: python-netlist-kicad
description: Design PCBs as Python netlists (parts, pins, nets, datasheet rules as checks), compile them to a KiCad 10 project, autoroute signals with Freerouting, run ERC/DRC with kicad-cli, then have a second agent review with kicad-happy. Humans keep high-voltage creepage and first power-up. Use for "design a board", "add a part to the board", "regenerate the KiCad project", "route the board", "is this board ready to order".
---

# Python netlist to KiCad

Agents are bad at clicking around a schematic editor and good at writing code. So the board is code: a Python file
with every part, pin and net, and the datasheet rules written as checks. A generator compiles it into a KiCad 10
project in seconds. Then each layer of checking catches what the one before can't:

| Layer | Catches |
|---|---|
| checks in the board script | what you wrote down (datasheet limits, pin coverage, cross-board connector pinouts) |
| kicad-cli ERC / DRC with schematic parity | electrical rule and copper errors, schematic and PCB out of sync |
| a second agent with kicad-happy | what you didn't write down (power tree, decoupling, ESD, connector polarity, DFM) |
| an independent agent reading the board against the CAD | fit: a board can be ERC 0, DRC 0 and still not go in the robot |
| you | high voltage creepage, polarity against a real plug, first power-up |

On the robot build kicad-happy caught a battery connector wired backwards, and the independent CAD read caught an
encoder board that was electrically perfect but physically couldn't be fitted. Neither shows up in ERC or DRC.

## 1. The board script

`example_board.py` here is a small runnable one. The shape:

- `P = {ref: (kind, value, sheet, {pin: net}, note)}` built with a `part()` helper that refuses duplicate refs.
  `kind` picks the symbol/footprint, `value` carries the package and is what the BOM and sourcing match on, `sheet`
  splits the schematic, `note` says why (cite the datasheet figure or table).
- `NC = {ref: [pins]}` for pins left open on purpose, `DNP = {refs}` for parts drawn but not fitted.
- `checks()` returns errors and the script exits non-zero on any. Typical checks: no single-pin nets; every IC pin
  connected or in NC; supply inside the datasheet range; caps at or above the datasheet minimum; worst-case currents
  and voltages under part ratings (the robot's 250 V kicker checks its cap against 246.9 V worst case and the flyback
  transformer against its saturation current); strap pins at the right level; the mating connector on the other
  board has the same pinout (load the other board's script and compare pin by pin).
- When a bug gets found in review, add the check that would have caught it, so it can't come back.
- Optional: write a `SCHEMATIC.md` summary from the same data for humans.

## 2. Part map

A `part_def(kind, value, pins)` table maps each kind to a KiCad library symbol, a footprint (package parsed from the
value, e.g. `0402`) and pin aliases (script pin names to symbol pin numbers). Unknown kinds stop the build with a
clear error rather than guessing. Parts KiCad doesn't ship get a generated symbol and footprint in a project library,
built from the datasheet land pattern and marked VERIFY until checked; `easyeda2kicad --full --lcsc_id=C...` is the
quick way to get one to cross-check against.

## 3. The generator

One command, e.g. `python3 kicad_gen.py board/board.py [--sch-only | --place | --route]`. Mine isn't in this repo
(about 1,100 lines tied to one robot's parts), so here is how it works, which is enough for an agent to write yours.
Spike it on your smallest board first: a 9-part board went from script to routed, ERC 0 / DRC 0 project in about 8 s.

- **Schematic** written as S-expressions (KiCad files are plain text). Library symbols are copied from KiCad's stock
  libraries into the sheet, placed on a grid per sheet, a label at every pin end and no wires: local labels for nets
  on one sheet, global labels for nets crossing sheets, power symbols for GND and rails, no-connect flags on `NC`
  pins, a `PWR_FLAG` on every net that feeds a power input from a connector or resistor. Ugly but correct, and ERC
  clean. If a human later redraws a sheet for readability, stop regenerating it and instead check the drawn sheet
  against the script (export its netlist with `kicad-cli sch export netlist` and compare pin by pin).
- **Pad nets** come from `kicad-cli sch export netlist`, so PCB net names always match the schematic.
- **PCB** built with KiCad's bundled Python (`pcbnew`): load footprints, set the net on every pad, set each
  footprint's `KIID_PATH` to its symbol's UUID (that is what makes schematic parity pass), outline and mounting holes,
  zones, net classes, design rules.
- **Placement** lives in a sidecar `pcb_layout.py` next to the board script: `OUTLINE`, `HOLES`, `PLACE`
  ({ref: x, y, rot, side}), `ZONES`, `KEEPOUTS`, `TRACKS`, `VIAS`, `NETCLASSES`, `DRU` (custom rules text),
  `NO_AUTOROUTE`. Take the outline and holes from the CAD model so the board and the enclosure agree.
- Files are overwritten in place. Keep the repo in git and commit before every agent session. One writer at a time.

## 4. Routing

- Power, motor phases and anything high voltage: scripted copper (pours, explicit tracks and vias in `pcb_layout.py`).
- Signals: `pcbnew.ExportSpecctraDSN`, drop the `NO_AUTOROUTE` nets from the DSN, then Freerouting headless:
  ```bash
  java -Djava.awt.headless=true -jar freerouting.jar --gui.enabled=false -de board.dsn -do board.ses -mp 20
  ```
  then `pcbnew.ImportSpecctraSES`, add pours, fill zones.
- Freerouting is not deterministic. Run a few tries with the DSN shuffled, score each by DRC (errors, unconnected),
  keep the best.

## 5. ERC / DRC

```bash
kicad-cli sch erc --severity-all -o erc.rpt board.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity -o drc.rpt board.kicad_pcb
kicad-cli pcb render --side top --quality high -w 1600 -h 1600 -o board-top.png board.kicad_pcb
```

Target: ERC 0, DRC 0 errors, 0 unconnected, 0 parity issues. Look at the renders: the agent should too.

## 6. Second agent review

Install [kicad-happy](https://github.com/aklofas/kicad-happy) (MIT) as a Claude Code plugin and run its review in a
fresh session that didn't design the board. Separately, brief an independent read-only reviewer with the datasheets,
the KiCad files and the CAD script, and tell it not to trust code comments: every finding cites a datasheet page or a
file line. Findings come back as BLOCKER / SHOULD / NIT; fix, add checks, rerun.

## 7. What stays human

- **High voltage.** None of these tools enforce creepage until you write the rule. Put it in the `DRU` as a KiCad
  custom rule per IPC-2221B for your voltage (the robot's 250 V kicker uses 1.25 mm external clearance and creepage
  on its HV net class), keep autorouting out of the HV zone, pours only.
- **Polarity.** Check every power connector footprint against a real plug before the first power-up.
- **Bring-up breaks.** Ship each section isolated (0R links left unfitted, normally-open solder jumpers) so the first
  board can be powered and measured one block at a time.
- **The order.** The agent prepares the fab package; you check it and pay.

## Tools

KiCad 10 with `kicad-cli`, Freerouting 2.5+ (needs Java), kicad-happy, easyeda2kicad. Konnect is useful when the agent
needs to inspect or edit a live KiCad session over its IPC API. Install lines are in the repo README.
