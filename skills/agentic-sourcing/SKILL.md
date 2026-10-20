---
name: agentic-sourcing
description: Source the parts for a scripted PCB from JLCPCB and LCSC with live stock and prices, resolve passives automatically, decide which parts JLC places and which are hand-fit, and write the JLC fab package plus one LCSC cart. The human checks and pays. Use for "source the BOM", "find an LCSC part for X", "is this in stock at JLC", "make the JLC order files", "build the LCSC cart".
---

# Agentic sourcing

Sourcing is where a one-night design turns into a week of waiting, so the agent does the lookups and the human only
checks the cart. Everything here runs off the same board scripts as `python-netlist-kicad`: the part `value` string
is what gets matched.

## 1. Look things up live

`jlc_lookup.py` (in this folder) searches the JLCPCB parts library and reads lcsc.com stock and price ladders:

```bash
python3 jlc_lookup.py "10k 0402 1%" 5     # code, MPN, maker, package, Basic/Ext (P = preferred), JLC stock
python3 jlc_lookup.py --lcsc C25744       # lcsc.com stock + price ladder
```

Things the agent should know:
- JLC part types: **Basic** (no fee), **preferred extended** (no feeder fee on Economic assembly), **extended** (a
  fee per unique part). Swapping to Basic/preferred is the cheapest cost pass you can do.
- JLC stock and lcsc.com stock are separate pools. A Basic part JLC has plenty of can be 0 on lcsc.com, so a part you
  hand-fit (bought from LCSC) may need a same-spec substitute in the cart while the schematic keeps the JLC code.
- Never trust a code from memory or search snippets. Every LCSC code goes through the lookup for the exact MPN and
  package, and gets a status string with the date it was checked.

## 2. Sourcing table

A `sourcing.py` next to the generator maps value regexes to `(MPN, LCSC code, status)`. First match wins, so cost
swaps go at the top. The generator writes MPN, LCSC and the status into each symbol's fields, which means the BOM
comes straight out of `kicad-cli sch export bom`. Status words worth standardising:

| Status | Meaning |
|---|---|
| `JLC basic / pref / ext, verified <date>` | the lookup returned this code for this exact MPN and package that day |
| `... stock 0` | listed but nothing in stock that day |
| `substitute ... VERIFY` | the design's example part isn't at JLC; this is a stocked equivalent a human must confirm |
| `not at JLC` | hand-solder or buy elsewhere |
| `UNRESOLVED` | fails the fab step |

## 3. Passives by script

Resistors and capacitors without a table entry get resolved automatically: parse value, package, tolerance (or
voltage and dielectric for caps) from the value string, search JLC, keep only rows whose description matches exactly,
reject Y5V/Z5U, require stock over 100, prefer Basic, then the best-stocked Extended. Cache the hits in a JSON file so
reruns are offline and the choice doesn't drift.

## 4. Who places what

Write the assembly rule down and let the script apply it per part. The one that worked for small runs on JLC Economic
assembly: JLC places a part only if it is SMD, on the top side, Basic or preferred, has an LCSC code and JLC has stock
for the order. Everything else is hand-fit and goes in the LCSC cart. Exceptions are explicit, per ref, with the reason
(`JLC_EXT_OK = {"U1": "QFN, centred joint, worth the fee"}`), and so are parts you choose to hand-fit (`HAND_FIT`).
Bring-up links that ship unfitted are DNP for JLC but still go in the cart.

## 5. Fab package

A `fab.py` per board, all through `kicad-cli`:
- Gerbers (copper, paste, silk, mask, edge cuts) and Excellon drill, zipped.
- `bom-jlc.csv` (Comment, Designator, Footprint, LCSC Part #) and `cpl-jlc.csv` (Designator, Mid X, Mid Y, Layer,
  Rotation) for the parts JLC places, from `kicad-cli sch export bom` and `pcb export pos`.
- `handfit.csv` with the reason per part and live lcsc.com stock and price.
- A summary with an assembly estimate from JLC's published price model (setup, stencil, per-joint, per extended part).
- Fail loudly on anything unresolved, out of stock or bottom-side in the CPL.
- JLC rotation offsets aren't applied: check every polarised part in JLC's placement preview before paying.

Then one LCSC cart across all boards: merge equal codes, add spares (cheap passives +10% with a minimum of 5,
everything else +1), round up to the LCSC minimum order, price from the live ladder, flag lines where stock is short.

## 6. Rules for the agent

- Nothing gets paid for without the human's yes. The agent builds the files, the cart CSV and the exact links; the
  human uploads, checks the preview and checks out.
- Fan research out to subagents (datasheets, alternatives, cheaper sources) and keep the main session for decisions.
- Always look for the cheaper equivalent, and say what changed and why in the status string.
