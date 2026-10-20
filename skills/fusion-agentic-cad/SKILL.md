---
name: fusion-agentic-cad
description: Drive Autodesk Fusion 360 from Claude Code through Fusion's built-in MCP server. The whole model lives in one parametric Python script run inside the open design; every size is a user parameter, one component and one timeline group per part, and every build ends with an interference check and a mass report. Use for "model this in Fusion", "change the CAD", "rebuild the robot", "check interferences", or any Fusion modelling task.
---

# Fusion agentic CAD

The agent never models in chat. It keeps the model in a Python file, runs that file inside Fusion through the MCP,
reads what came back, edits the file, reruns. A change is one number and a rerun.

## Setup (once)

1. In Fusion: profile menu, Preferences, General, API, tick **Fusion MCP Server** (port 27182). Agents can't click
   Fusion's Qt menus in the background, so do this by hand.
2. Register it in Claude Code:
   ```bash
   claude mcp add --transport http --scope user fusion http://127.0.0.1:27182/mcp
   ```
3. Open Fusion with a design open **before** you start the Claude Code session. MCP tools load at session start; a
   session started before Fusion was up won't see them.

Tools you get:

| Tool | Use |
|---|---|
| `fusion_mcp_execute` | featureType `script` runs Python (`def run(_context)`) against the live design. This is how everything gets built. `readOnly: true` runs inspection scripts, even mid-command |
| `fusion_mcp_read` | screenshots, docs search, API docs |
| `fusion_mcp_update` | undo / redo |

If the tools didn't load, the server still answers plain HTTP: POST JSON-RPC `initialize` to
`http://127.0.0.1:27182/mcp`, keep the `MCP-Session-Id` response header, then `tools/call` `fusion_mcp_execute`.

## The pattern

1. **One script is the source of truth.** The whole model is one `.py` file in your repo. It clears the design and
   rebuilds every part. The Fusion file is an output.
2. **Run it from the file, never paste it into chat.** A tiny loader in `fusion_mcp_execute`:
   ```python
   def run(_context):
       PATH = '/absolute/path/to/build.py'
       g = {'__name__': 'fusion_build'}
       exec(compile(open(PATH, encoding='utf-8').read(), PATH, 'exec'), g)
       g['main']('build')
   ```
3. **Every size is a user parameter.** A `PARAMS` table of (name, expression, comment) at the top, created with
   `userParameters.add`. Derived sizes are expressions of other parameters, and design rules live in them (comment
   the why). Sketch dimensions get `.parameter.expression = 'name'`; positions are computed from the parameters at run time.
4. **One component per part, one timeline group per part.** `addNewComponent` for each part, and a small context
   manager that records `timeline.count` before and after and calls `timelineGroups.add(start, end)`.
5. **Fully constrained sketches, real features.** Lines with H/V constraints and dimension expressions; real
   Extrude, Shell, Fillet, Chamfer, Hole features, so the timeline stays editable by hand.
6. **Rerun on every change.** Edit the parameter or the script, run `main('build')` again. Don't patch the live model.
7. **Finish with a check.** `main('report')`: mass per component (give bought parts real masses: lumped bodies with a
   density tuned to the datasheet weight) and `analyzeInterference` across all occurrences with coincident faces
   excluded. Target 0 interferences. Then export STEP / STL through `design.exportManager`.
8. **Guard the document.** `main` refuses to run unless the active document has the expected name, so a rebuild
   never wipes some other open design.
9. **One writer at a time.** Only one agent runs the build script against a given Fusion document.

`build_box.py` in this folder is a small working example of all of the above: a shelled box and a lid with a hole, five
parameters, two components, two timeline groups, a report. Create a design named "Box Example", point the loader at
the file and run it.

## Gotchas (all hit for real)

**Running scripts**
- A script that raises is rolled back whole by the MCP. Good for safety, but print progress so you know where it died.
- Big builds, STEP export and `analyzeInterference` can outlast the MCP call timeout while Fusion keeps working. Don't
  rerun: check the result with a follow-up `readOnly` script (interference analysis runs fine read-only).
- Without `encoding='utf-8'` in the loader, a file containing a non-ASCII character (Ø) fails with an ascii decode error.
- Fusion's API works in cm internally. Parameters in mm come back from `.value` in cm.

**Sketches**
- `addTwoPointRectangle` / `addCenterPointRectangle` from the API add no horizontal/vertical constraints and no centre
  point. Draw 4 lines and constrain them; for a centre, a sketch point with MidPoint on a construction diagonal.
- On `xZConstructionPlane`, sketch +Y maps to world -Z (Z-up). Use negative sketch Y for upright parts.
- On the YZ plane, sketch horizontal is not model Y. Check `sketch.modelToSketchSpace` before attaching width/height
  expressions (a 34 x 14 plate came out 14 x 34).

**Features**
- Cut extrudes and Holes hit bodies in other components unless `participantBodies = [own body]` is set. Set it on
  every cut and hole.
- `ExtrudeFeatureInput.setDistanceExtent(isSymmetric, dist)`: the bool is symmetric, not flip. For a direction use
  `setOneSideExtent(DistanceExtentDefinition.create(v), ExtentDirections.NegativeExtentDirection)`.
- `HoleInput.setPositionByPlaneAndOffsets`: the offsets drive the real hole, but `HoleFeature.position` still reports
  the seed point. Check the face bounding box instead.

**Assemblies**
- Root component name can't be set from a script.
- `MoveFeatureInput.defineAsRotate` rejects a nested component's construction axis ("Invalid entity"). Use
  `defineAsFreeMove` with a rotation `Matrix3D`. Circular patterns accept that axis fine.
- A nested occurrence's `transform2` must be set on `child.createForAssemblyContext(parentOcc)`. For instanced
  sub-assemblies, create every `addExistingComponent` instance at identity first, then set each `transform2`, then
  `design.snapshots.add()`. Setting the first one before instancing left them all rotated wrong.
- `occurrence.boundingBox` of nested proxies reads as zeros. Use body bounding boxes.

**Timeline and rebuilds**
- `timeline.count` counts a collapsed group as one item, so start/end per part still works.
- Rebuilding in place: delete the root occurrences, and wrap `TimelineGroup.deleteMe` in try/except: it throws on
  groups whose items are already gone, and a dead group can linger (harmless).
