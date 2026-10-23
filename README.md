# agentic hardware stack

i designed two robocup ssl style soccer robots in one night with agents doing the cad and the pcbs. this is the stack and the skills i used. claude code drives fusion 360 through its built-in mcp for the mechanical side, and every circuit board is a python file that compiles into a kicad project, gets autorouted, checked and reviewed by a second agent. steal whatever's useful. the build posts on my instagram walk through the robot, the fusion side and the kicad side.

## the stack

| tool | what it does in the loop | link | install | licence |
|---|---|---|---|---|
| Claude Code | the agent. runs everything below (i used Opus 5.5 at xhigh effort) | [claude.com/claude-code](https://claude.com/claude-code) | `curl -fsSL https://claude.ai/install.sh \| bash` | proprietary (Anthropic) |
| Fusion 360 + its MCP server | the cad. the agent runs one parametric python script inside the open design | [autodesk.com/fusion](https://www.autodesk.com/products/fusion-360) | turn on Preferences, General, API, "Fusion MCP Server", then `claude mcp add --transport http --scope user fusion http://127.0.0.1:27182/mcp` | proprietary (Autodesk) |
| KiCad 10 + kicad-cli | the eda. schematic, pcb, ERC, DRC, renders, gerbers, all scriptable | [kicad.org](https://www.kicad.org) | `brew install --cask kicad` | GPL-3.0 |
| Konnect | mcp bridge into a running KiCad 10 (IPC api) when the agent needs to look at or nudge a live board | [github.com/mixelpixx/Konnect](https://github.com/mixelpixx/Konnect) | binary from Releases, then `claude mcp add konnect -- ~/.local/bin/konnect && konnect init` | AGPL-3.0 |
| kicad-happy | the second agent's review skills: power tree, decoupling, ESD, connectors, BOM, DFM, EMC | [github.com/aklofas/kicad-happy](https://github.com/aklofas/kicad-happy) | in Claude Code: `/plugin marketplace add aklofas/kicad-happy` then `/plugin install kicad-happy@kicad-happy` | MIT |
| Freerouting | autoroutes the signal nets through Specctra DSN/SES, headless | [github.com/freerouting/freerouting](https://github.com/freerouting/freerouting) | `brew install openjdk` + the jar from Releases | GPL-3.0 |
| pcbparts | mcp for parts: parametric JLC search, live stock, LCSC or MPN lookup, alternatives, pinouts, KiCad footprints, reference boards. hosted, no key | [pcbparts.dev](https://pcbparts.dev) | `claude mcp add -s user --transport http pcbparts https://pcbparts.dev/mcp` | MIT |
| easyeda2kicad | pulls a symbol and footprint by LCSC part number when KiCad doesn't ship one | [github.com/uPesy/easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py) | `uv tool install easyeda2kicad` | AGPL-3.0 |
| kicad-jlcpcb-tools | optional KiCad plugin for JLC BOM/CPL if you'd rather not script fab files | [github.com/Bouni/kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) | KiCad Plugin and Content Manager, custom repo URL from its README | MIT |

the third party tools aren't vendored here. install them from their own repos, they keep their own licences. `konnect init` installs Konnect's own Claude skills (konnect, kicad-schematic, kicad-pcb and friends), those are AGPL and come from Konnect, not from me.

## the loop

1. **cad as code.** the agent writes the whole robot as one parametric python script, every size a user parameter, and runs it in Fusion through the mcp. change a number, rerun, the model follows.
2. **check the cad.** every build ends with an interference check and a mass report with real masses on the bought parts.
3. **boards as code.** each pcb is a python file: every part, pin and net, with the datasheet rules written as checks that fail the build.
4. **compile to kicad.** one script turns that into a KiCad 10 project, placement comes from a sidecar file, Freerouting does the signals, power and high voltage copper is scripted.
5. **check, then review.** kicad-cli runs ERC and DRC (target 0 / 0 / 0 with schematic parity), then a second agent reviews with kicad-happy and an independent agent reads the board against the cad. a human (me) owns high voltage creepage and the first power-up.
6. **source and fab.** the agent looks up live JLC and LCSC stock, picks parts, writes the gerbers, BOM, CPL and one LCSC cart. i check the order and pay myself.

## skills

| skill | what it's for |
|---|---|
| [fusion-agentic-cad](skills/fusion-agentic-cad/SKILL.md) | drive Fusion 360 from Claude Code: setup, the one-script pattern, the gotchas, a small example build |
| [python-netlist-kicad](skills/python-netlist-kicad/SKILL.md) | boards as python netlists with datasheet checks, compiled to KiCad 10, routed, checked and reviewed |
| [agentic-sourcing](skills/agentic-sourcing/SKILL.md) | live JLC/LCSC part lookup, passives resolved by script, the hand-fit vs JLC-placed rule, the fab package |

install a skill by linking its folder into your Claude Code skills dir:

```bash
git clone https://github.com/hughminhphan/agentic-hardware-stack.git
mkdir -p ~/.claude/skills
ln -s "$PWD/agentic-hardware-stack/skills/fusion-agentic-cad" ~/.claude/skills/
ln -s "$PWD/agentic-hardware-stack/skills/python-netlist-kicad" ~/.claude/skills/
ln -s "$PWD/agentic-hardware-stack/skills/agentic-sourcing" ~/.claude/skills/
```

## licence

my files here are MIT (see [LICENSE](LICENSE)). every linked tool keeps its own licence, listed in the table above.
