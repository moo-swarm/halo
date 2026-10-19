#!/usr/bin/env python3
"""Build the Halo assistant avatar: a comet orbiting through a rotating ring.

The comet circles in a plane perpendicular to the ring, so on screen its path
collapses to a line from the ring's edge (through the gap) to the centre.
At both ends it is a bare point; the tail grows with its sideways speed.
Inbound it flies in front of the ring and larger, outbound behind and smaller.
The ring creeps while the gap holds the comet and sweeps round while the comet
is at the centre, making exactly one turn per cycle, so the loop is seamless
and the comet never touches the ring.

Writes assets/avatar/halo-comet.svg (SMIL, works in <img>) and
assets/avatar/halo-comet-static.svg (a single frame).
"""
import math
from pathlib import Path

SIZE = 512
C = SIZE / 2
R = 168            # ring radius
BAND = 48          # ring thickness
GAP = 44           # half-width of the gap, degrees
AXIS = -45         # screen angle of the comet's line (edge at top-right)
DWELL = 0.25       # no ratchet clicks while the comet is within this phase of the gap
CREEP = 0.15       # share of the turn done by the steady creep (the ring never stops)
CLICKS = 3         # ratchet clicks per turn, all while the comet is near the centre
SNAP = 0.8         # share of each click slot spent moving; the rest is creep only
LAG = 0.8          # dust tail = the orbit arc this far (rad, at full speed) behind the head
ION_LAG = 0.9      # the thinner ion tail trails a little further
DEPTH = 0.38       # head scale swing front/back
DUR = 6            # seconds per cycle
SAMPLES = 96
STATIC_T = 0.25
SEGMENTS = 90

# Colour wheel behind the ring, cyclic (first stop == last). It turns the other
# way at a constant rate, so colour flows against the ring's own motion.
RING_STOPS = [(0, "#1e3a8a"), (0.25, "#4f46e5"), (0.5, "#2563eb"), (0.7, "#60a5fa"),
              (0.82, "#e0f2fe"), (0.92, "#60a5fa"), (1, "#1e3a8a")]
COLOR_TURNS = -1   # colour wheel turns per cycle (negative: against the ring)


def lerp_hex(a, b, u):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * u):02x}" for x, y in zip(pa, pb))


def ring_color(u):
    for (u0, c0), (u1, c1) in zip(RING_STOPS, RING_STOPS[1:]):
        if u <= u1:
            return lerp_hex(c0, c1, (u - u0) / (u1 - u0))
    return RING_STOPS[-1][1]


def smootherstep(u):
    u = min(max(u, 0), 1)
    return u * u * u * (u * (u * 6 - 15) + 10)


def ring_turn(t):
    """Fraction of the ring's single turn done by phase t. Like a ratchet the ring
    always creeps and snaps forward in clicks, but only while the comet is near
    the centre, so the comet passes the gap without ever touching the ring."""
    u = min(max((t - DWELL) / (1 - 2 * DWELL), 0), 1)
    k = min(int(u * CLICKS), CLICKS - 1)
    click = smootherstep((u * CLICKS - k) / SNAP)
    return CREEP * t + (1 - CREEP) * (k + click) / CLICKS


def state(t):
    th = 2 * math.pi * t
    s = math.sin(th)
    return {
        "ring": 360 * ring_turn(t),
        "x": R / 2 * (1 + math.cos(th)),
        "head": 1 + DEPTH * s,
        # The tail is the orbit just behind the head, seen edge-on, so it never
        # leaves the edge-centre line and shrinks to nothing at both ends.
        "dust": R / 2 * (1 + math.cos(th - LAG * abs(s))) - R / 2 * (1 + math.cos(th)),
        "ion": R / 2 * (1 + math.cos(th - ION_LAG * abs(s))) - R / 2 * (1 + math.cos(th)),
        "opacity": 0.78 + 0.22 * s,
        "front": t < 0.5,
    }


def f(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def polar(a, r=R):
    a = math.radians(a)
    return C + r * math.cos(a), C + r * math.sin(a)


def ring_mask():
    """The ring's shape: an arc with round ends, leaving the gap at angle 0."""
    x0, y0 = polar(GAP)
    x1, y1 = polar(360 - GAP)
    return (f'<path d="M{f(x0)} {f(y0)}A{R} {R} 0 1 1 {f(x1)} {f(y1)}" fill="none" '
            f'stroke="#fff" stroke-width="{BAND}" stroke-linecap="round"/>')


def color_wheel():
    """A full annulus coloured round the circle, seen only through the ring."""
    step = 360 / SEGMENTS
    parts = []
    for i in range(SEGMENTS):
        x0, y0 = polar(i * step)
        x1, y1 = polar((i + 1) * step + 1.2)
        parts.append(f'<path d="M{f(x0)} {f(y0)}A{R} {R} 0 0 1 {f(x1)} {f(y1)}" '
                     f'stroke="{ring_color((i + 0.5) / SEGMENTS)}"/>')
    return "\n      ".join(parts)


DEFS = f"""<defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="60%">
      <stop offset="0" stop-color="#16233f"/>
      <stop offset="1" stop-color="#0b1120"/>
    </radialGradient>
    <radialGradient id="coma">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.1" stop-color="#fffaf0"/>
      <stop offset="0.3" stop-color="#ffe9b8" stop-opacity="0.7"/>
      <stop offset="0.6" stop-color="#f8c977" stop-opacity="0.25"/>
      <stop offset="1" stop-color="#f59e0b" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="dust" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff4dc" stop-opacity="0.95"/>
      <stop offset="0.45" stop-color="#fcd9a0" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#f5b764" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="ion" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#f0f9ff" stop-opacity="0.95"/>
      <stop offset="0.55" stop-color="#7dd3fc" stop-opacity="0.7"/>
      <stop offset="1" stop-color="#38bdf8" stop-opacity="0"/>
    </linearGradient>
    <filter id="dustBlur" filterUnits="userSpaceOnUse" x="-220" y="-90" width="440" height="180">
      <feGaussianBlur stdDeviation="3.5"/>
    </filter>
    <filter id="ionBlur" filterUnits="userSpaceOnUse" x="-220" y="-40" width="440" height="80">
      <feGaussianBlur stdDeviation="1"/>
    </filter>
    <mask id="ringMask" maskUnits="userSpaceOnUse" x="0" y="0" width="{SIZE}" height="{SIZE}">
      RING_SHAPE
    </mask>
    <filter id="ringGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="7" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <path id="dustShape" d="M0 -0.35C0.35 -0.6 0.75 -1 1 -0.9L1 0.9C0.75 1 0.35 0.6 0 0.35Z" fill="url(#dust)"/>
    <path id="ionShape" d="M0 -1C0.4 -0.6 0.8 -0.2 1 0C0.8 0.2 0.4 0.6 0 1Z" fill="url(#ion)"/>
  </defs>"""


def anim(attr, values, kind=None):
    vals = ";".join(values)
    if kind:
        return (f'<animateTransform attributeName="transform" type="{kind}" values="{vals}" '
                f'dur="{DUR}s" repeatCount="indefinite"/>')
    return f'<animate attributeName="{attr}" values="{vals}" dur="{DUR}s" repeatCount="indefinite"/>'


def comet(layer, animated, st):
    """One depth layer of the comet. layer: 'front' or 'back'.
    Nucleus inside a soft coma, a broad warm dust tail and a thin blue ion tail."""
    ss = [state((i / SAMPLES) % 1) for i in range(SAMPLES + 1)]

    def g(kind, value, body):
        if animated:
            return f"<g>{anim(None, [value(x) for x in ss], kind)}{body}</g>"
        return f'<g transform="{kind}({value(st)})">{body}</g>'

    head = g("scale", lambda x: f(x["head"]),
             '<circle r="44" fill="url(#coma)"/><circle r="5.5" fill="#ffffff"/>')
    dust = g("scale", lambda x: f"{f(x['dust'])} {f(18 * x['head'])}", '<use href="#dustShape"/>')
    ion = g("scale", lambda x: f"{f(x['ion'])} {f(3.5 * x['head'])}", '<use href="#ionShape"/>')
    body = f'<g filter="url(#dustBlur)">{dust}</g><g filter="url(#ionBlur)">{ion}</g>{head}'
    if animated:
        body = f'<g>{anim("opacity", [f(x["opacity"]) for x in ss])}{body}</g>'
    else:
        body = f'<g opacity="{f(st["opacity"])}">{body}</g>'
    moving = g("translate", lambda x: f"{f(x['x'])} 0", body)
    if animated:
        flip = "1;0;1" if layer == "front" else "0;1;0"
        return (f'<g transform="translate({C} {C}) rotate({AXIS})" opacity="{flip[0]}">'
                f'<animate attributeName="opacity" values="{flip}" keyTimes="0;0.5;1" calcMode="discrete" '
                f'dur="{DUR}s" repeatCount="indefinite"/>{moving}</g>')
    visible = st["front"] == (layer == "front")
    return f'<g transform="translate({C} {C}) rotate({AXIS})" opacity="{1 if visible else 0}">{moving}</g>'


def build(animated):
    st = state(STATIC_T)
    if animated:
        rots = [f"{f(AXIS + state(i / SAMPLES)['ring'] if i < SAMPLES else AXIS + 360)} {C} {C}"
                for i in range(SAMPLES + 1)]
        shape = f'<g>{anim(None, rots, "rotate")}{ring_mask()}</g>'
        wheel_open = (f'<g><animateTransform attributeName="transform" type="rotate" '
                      f'values="0 {C} {C};{360 * COLOR_TURNS} {C} {C}" dur="{DUR}s" repeatCount="indefinite"/>')
    else:
        shape = f'<g transform="rotate({f(AXIS + st["ring"])} {C} {C})">{ring_mask()}</g>'
        wheel_open = f'<g transform="rotate({f(360 * COLOR_TURNS * STATIC_T)} {C} {C})">'
    defs = DEFS.replace("RING_SHAPE", shape)
    title = "Halo — AI assistant" + ("" if animated else " (static)")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}" role="img" aria-label="{title}">
  <title>{title}</title>
  {defs}
  <rect width="{SIZE}" height="{SIZE}" fill="url(#bg)"/>
  {comet("back", animated, st)}
  <g filter="url(#ringGlow)">
    <g mask="url(#ringMask)" fill="none" stroke-width="{BAND + 8}">
      {wheel_open}
      {color_wheel()}
      </g>
    </g>
  </g>
  {comet("front", animated, st)}
</svg>
"""


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "avatar"
    out.mkdir(parents=True, exist_ok=True)
    (out / "halo-comet.svg").write_text(build(True))
    (out / "halo-comet-static.svg").write_text(build(False))
    print("wrote", out)
