"""Parametric box + lid: a minimal example of the one-script Fusion build pattern.

Run inside Fusion through the Fusion MCP (fusion_mcp_execute, featureType "script") with a tiny loader:

    def run(_context):
        PATH = '/absolute/path/to/build_box.py'
        g = {'__name__': 'fusion_build'}
        exec(compile(open(PATH, encoding='utf-8').read(), PATH, 'exec'), g)
        g['main']('build')      # or 'report'

main('build', reset=False) clears the active design and rebuilds every part.
main('report') prints masses and interferences.

Every size is a user parameter (Modify, Change Parameters). Sketch dimensions are linked to the parameters by
expression; positions are computed from the parameters when the script runs, so after a parameter change rerun
main('build'). One component per part, one timeline group per part, every cut limited to its own body.
"""
import adsk.core, adsk.fusion

app = adsk.core.Application.get()
P3 = adsk.core.Point3D.create
VI = adsk.core.ValueInput
FO = adsk.fusion.FeatureOperations
DIM = adsk.fusion.DimensionOrientations
DOC_NAME = 'Box Example'   # the build refuses to run on any other document

PARAMS = [  # name, expression, comment
    ('box_w', '60 mm', 'Outer width (x)'),
    ('box_d', '40 mm', 'Outer depth (y)'),
    ('box_h', '25 mm', 'Outer height of the box body (z)'),
    ('wall', '2 mm', 'Wall and lid thickness'),
    ('hole_d', '6 mm', 'Cable hole in the lid'),
]

DES = None


def v(name):
    """Parameter value in Fusion's internal units (cm for lengths)."""
    return DES.userParameters.itemByName(name).value


def ensure_params(reset=False):
    up = DES.userParameters
    for name, expr, comment in PARAMS:
        p = up.itemByName(name)
        if p is None:
            up.add(name, VI.createByString(expr), 'mm', comment)
        elif reset:
            p.expression = expr
            p.comment = comment


class Group:
    """Everything built inside the `with` block becomes one named timeline group."""
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start = DES.timeline.count
        return self

    def __exit__(self, et, ev, tb):
        end = DES.timeline.count - 1
        if et is None and end > self.start:
            DES.timeline.timelineGroups.add(self.start, end).name = self.name
        return False


def new_comp(parent, name):
    occ = parent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ.component


def rect(sk, w_expr, d_expr):
    """Fully constrained rectangle from the sketch origin. API rectangles come with no H/V constraints, so draw 4 lines."""
    L = sk.sketchCurves.sketchLines
    w, d = v(w_expr), v(d_expr)
    l0 = L.addByTwoPoints(P3(0, 0, 0), P3(w, 0, 0))
    l1 = L.addByTwoPoints(l0.endSketchPoint, P3(w, d, 0))
    l2 = L.addByTwoPoints(l1.endSketchPoint, P3(0, d, 0))
    l3 = L.addByTwoPoints(l2.endSketchPoint, l0.startSketchPoint)
    gc = sk.geometricConstraints
    gc.addHorizontal(l0); gc.addHorizontal(l2); gc.addVertical(l1); gc.addVertical(l3)
    gc.addCoincident(l0.startSketchPoint, sk.originPoint)
    dims = sk.sketchDimensions
    dims.addDistanceDimension(l0.startSketchPoint, l0.endSketchPoint, DIM.HorizontalDimensionOrientation,
                              P3(w / 2, -0.5, 0)).parameter.expression = w_expr
    dims.addDistanceDimension(l1.startSketchPoint, l1.endSketchPoint, DIM.VerticalDimensionOrientation,
                              P3(w + 0.5, d / 2, 0)).parameter.expression = d_expr


def extrude(c, prof, dist_expr, op, bodies=None):
    ext = c.features.extrudeFeatures
    inp = ext.createInput(prof, op)
    inp.setDistanceExtent(False, VI.createByString(dist_expr))   # the bool is "symmetric", not "flip"
    if bodies:
        inp.participantBodies = list(bodies)   # without this a cut also hits bodies in OTHER components
    return ext.add(inp)


def part_box(root):
    with Group('Box'):
        c = new_comp(root, 'Box')
        sk = c.sketches.add(c.xYConstructionPlane)
        rect(sk, 'box_w', 'box_d')
        f = extrude(c, sk.profiles.item(0), 'box_h', FO.NewBodyFeatureOperation)
        body = f.bodies.item(0)
        body.name = 'Box'
        faces = adsk.core.ObjectCollection.create()
        faces.add(f.endFaces.item(0))                               # open the top
        sh = c.features.shellFeatures.createInput(faces, False)
        sh.insideThickness = VI.createByString('wall')
        c.features.shellFeatures.add(sh)


def part_lid(root):
    with Group('Lid'):
        c = new_comp(root, 'Lid')
        pi = c.constructionPlanes.createInput()
        pi.setByOffset(c.xYConstructionPlane, VI.createByString('box_h'))
        top = c.constructionPlanes.add(pi)
        top.name = 'Lid underside'
        sk = c.sketches.add(top)
        rect(sk, 'box_w', 'box_d')
        lid = extrude(c, sk.profiles.item(0), 'wall', FO.NewBodyFeatureOperation).bodies.item(0)
        lid.name = 'Lid'
        hs = c.sketches.add(top)
        circ = hs.sketchCurves.sketchCircles.addByCenterRadius(P3(v('box_w') / 2, v('box_d') / 2, 0), v('hole_d') / 2)
        hs.sketchDimensions.addDiameterDimension(circ, P3(v('box_w') / 2 + 1, v('box_d') / 2 + 1, 0)).parameter.expression = 'hole_d'
        extrude(c, hs.profiles.item(0), 'wall', FO.CutFeatureOperation, bodies=[lid])


PARTS = [part_box, part_lid]


def clear():
    tl = DES.timeline
    for i in range(tl.timelineGroups.count - 1, -1, -1):
        try:
            tl.timelineGroups.item(i).deleteMe(False)   # throws on groups whose items are already gone
        except Exception:
            pass
    root = DES.rootComponent
    for i in range(root.occurrences.count - 1, -1, -1):
        root.occurrences.item(i).deleteMe()


def build(reset=False):
    ensure_params(reset)
    clear()
    root = DES.rootComponent
    for fn in PARTS:
        fn(root)
    print('built', [f.__name__ for f in PARTS], 'timeline', DES.timeline.count)


def report():
    root = DES.rootComponent
    acc = adsk.fusion.CalculationAccuracy.MediumCalculationAccuracy
    total = 0.0
    for occ in root.occurrences:
        m = occ.getPhysicalProperties(acc).mass * 1000
        total += m
        print('%-24s %8.1f g' % (occ.name, m))
    print('TOTAL %.1f g' % total)
    ents = adsk.core.ObjectCollection.create()
    for occ in root.occurrences:
        ents.add(occ)
    ii = DES.createInterferenceInput(ents)
    ii.areCoincidentFacesIncluded = False      # the lid sits on the box: touching faces are not a clash
    res = DES.analyzeInterference(ii)
    print('interferences:', res.count)
    for r in res:
        print('  %s | %s  %.2f mm3' % (r.entityOne.name, r.entityTwo.name, r.interferenceBody.volume * 1000))


def main(cmd='build', reset=False):
    global DES
    if not app.activeDocument.name.startswith(DOC_NAME):
        raise RuntimeError('active document is not %r: refusing to touch it' % DOC_NAME)
    DES = adsk.fusion.Design.cast(app.activeProduct)
    DES.designType = adsk.fusion.DesignTypes.ParametricDesignType
    if cmd == 'build':
        build(reset)
    elif cmd == 'report':
        report()
