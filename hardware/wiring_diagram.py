#!/usr/bin/env python3
"""Fritzing-style breadboard view: a photo of the VFD's back + Fritzing parts (Arduino UNO, half
breadboard, DC jack, capacitors; CC-BY-SA 3.0), all at the same real-world scale, curved jumper wires.

    python wiring_diagram.py   -> ../docs/wiring.svg (self-contained) + ../docs/wiring.png (needs Playwright + Chrome)

The VFD is shown from the BACK (the side you plug the wires into), so its 2x7 header sits at the
right edge, and the UNO is rotated 90° so its digital header faces it - the pin order matches 1:1.
"""
import base64, os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "..", "docs")
W, H = 2700, 1400

PX_MM = 10.96                           # scale of the VFD photo
PX_IN = PX_MM * 25.4
U = PX_IN / 72                          # Fritzing parts drawn at 72 units per inch
U100 = PX_IN / 100                      # ...and the capacitors at 100 units per inch

# VFD photo (back side, header on the right)
VX, VY, PHOTO_W, PHOTO_H = 40, 60, 1525, 471
X_EVEN, X_ODD = VX + 1500, VX + 1472    # even pins on the board edge
PITCH = 2.54 * PX_MM
ROW0 = VY + 233 - 3 * PITCH             # pins 13/14

# Arduino UNO, rotated 90° CCW (digital header on the left, D0 on top)
UNO_W, UNO_H = 212.372, 151.2
AX0, AY0 = 2060, 120
UNO_PINS = {"D2": 183.57, "D3": 176.37, "D4": 169.17, "D5": 161.97, "D6": 154.77, "D7": 147.57,
            "D8": 136.05, "D9": 128.85, "D10": 121.65, "D11": 114.45, "D12": 107.25, "D13": 100.05,
            "GND": 92.85}

# half breadboard: top rails W (+5 V) and X (GND)
BX, BY = 1010, 760
BB_W, BB_H = 245.037, 151.2
RAIL_Y = {"W": 7.201, "X": 14.4}

JX, JY = 770, 735                       # DC jack

COL = {
    "DB0": "#8e44ad", "DB1": "#2e86de", "DB2": "#10ac84", "DB3": "#7cb518",
    "DB4": "#e8b800", "DB5": "#ff8c1a", "DB6": "#e8413c", "DB7": "#b8336a",
    "RS": "#00a8c6", "E": "#ff5fa8", "GND": "#2b2b2b", "+5V": "#d81e1e",
}


def shade(hex_color, k):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * k))) for c in (r, g, b))


def pin_xy(n):
    row = (14 - n) // 2 if n % 2 == 0 else (13 - n) // 2
    return (X_EVEN if n % 2 == 0 else X_ODD), ROW0 + row * PITCH


def ard_xy(name):
    return AX0 + 7.2 * U, AY0 + (UNO_W - UNO_PINS[name]) * U


def hole(row, col):
    return BX + (25.319 + 7.2 * (col - 1)) * U, BY + RAIL_Y[row] * U


def image(path, mime="image/svg+xml"):
    with open(os.path.join(ASSETS, path), "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def wire(d, color, width=8):
    """Fritzing jumper wire: dark edge, colour, a thin highlight."""
    return (f'<path d="{d}" fill="none" stroke="{shade(color, .55)}" stroke-width="{width + 3}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="{width / 3:.1f}" '
            f'stroke-linecap="round" transform="translate(-1.2,-1.6)"/>')


def wire_end(x, y, color):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{shade(color, .8)}" stroke="{shade(color, .5)}" '
            f'stroke-width="2"/>')


def curve(p0, p1, p2, p3):
    return "M {:.1f},{:.1f} C {:.1f},{:.1f} {:.1f},{:.1f} {:.1f},{:.1f}".format(*p0, *p1, *p2, *p3)


def leg(x0, y0, x1, y1):
    """Bent component leg from the body to a breadboard hole."""
    mid = y1 - 14
    d = f"M {x0:.1f},{y0:.1f} L {x0:.1f},{mid:.1f} L {x1:.1f},{mid + 6:.1f} L {x1:.1f},{y1:.1f}"
    return (f'<path d="{d}" fill="none" stroke="#6b6b6b" stroke-width="6" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="#b9b9b9" stroke-width="3.5" stroke-linejoin="round"/>')


def build():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # --- parts ---
    s.append(f'<image x="{VX}" y="{VY}" width="{PHOTO_W}" height="{PHOTO_H}" href="{image("vfd_back.jpg", "image/jpeg")}"/>')
    s.append(f'<image x="{BX}" y="{BY}" width="{BB_W * U:.1f}" height="{BB_H * U:.1f}" '
             f'href="{image("breadboard_half_fritzing.svg")}"/>')
    s.append(f'<g transform="translate({AX0},{AY0 + UNO_W * U:.1f}) rotate(-90)">'
             f'<image width="{UNO_W * U:.1f}" height="{UNO_H * U:.1f}" href="{image("arduino_uno_rev3_fritzing.svg")}"/></g>')
    s.append(f'<image x="{JX}" y="{JY}" width="{49.884 * U:.1f}" height="{30.065 * U:.1f}" '
             f'href="{image("power_plug_fritzing.svg")}"/>')

    # 2x7 male header on the VFD (the real one is hidden under plugs in the photo)
    for n in range(1, 15):
        x, y = pin_xy(n)
        h = PITCH / 2
        s.append(f'<rect x="{x - h:.1f}" y="{y - h:.1f}" width="{PITCH:.1f}" height="{PITCH:.1f}" fill="#262626" '
                 f'stroke="#0d0d0d" stroke-width="1.5"/>')
        s.append(f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="#e3c35a" stroke="#8d6d14"/>')
    for n, dx in ((1, -26), (13, -32)):                 # silkscreen
        x, y = pin_xy(n)
        s.append(f'<text x="{x + dx}" y="{y + 6:.1f}" font-size="17" fill="#f2f2f2" '
                 f'font-family="Consolas, monospace" font-weight="bold">{n}</text>')

    # --- capacitors on the rails (bent legs) ---
    ex, ey = hole("W", 18)[0] + 3.6 * U - 35.9 * U100, hole("W", 18)[1] - 26 - 93.761 * U100
    for px, row, col in ((20.639, "X", 18), (30.639, "W", 19)):      # left leg = minus stripe
        s.append(leg(ex + px * U100, ey + 93.761 * U100, *hole(row, col)))
    s.append(f'<image x="{ex:.1f}" y="{ey:.1f}" width="{51.183 * U100:.1f}" height="{98.261 * U100:.1f}" '
             f'href="{image("electrolytic_fritzing.svg")}"/>')
    cx, cy = hole("W", 22)[0] + 3.6 * U - 9.419 * U100, hole("W", 22)[1] - 30 - 15.326 * U100
    for px, row, col in ((4.419, "W", 22), (14.419, "X", 23)):
        s.append(leg(cx + px * U100, cy + 15.326 * U100, *hole(row, col)))
    s.append(f'<image x="{cx:.1f}" y="{cy:.1f}" width="{18.836 * U100:.1f}" height="{24.827 * U100:.1f}" '
             f'href="{image("ceramic_fritzing.svg")}"/>')

    wires, ends = [], []

    def add(d, color, *pts):
        wires.append(wire(d, color))
        ends.extend(wire_end(x, y, color) for x, y in pts)

    # --- DC jack -> rails ---
    vcc = (JX + 49.448 * U, JY + 11.652 * U)
    gnd = (JX + 49.448 * U, JY + 18.414 * U)
    w1, x1 = hole("W", 2), hole("X", 1)
    add(curve(vcc, (vcc[0] + 60, vcc[1]), (w1[0] - 50, w1[1] - 40), w1), COL["+5V"], vcc, w1)
    add(curve(gnd, (gnd[0] + 40, gnd[1] + 30), (x1[0] - 30, x1[1] + 30), x1), COL["GND"], gnd, x1)

    # --- VFD power: pin 2 -> +5 V, pins 1 and 5 (R/W) -> GND ---
    p1, p2, p5 = pin_xy(1), pin_xy(2), pin_xy(5)
    h2, h1, h5 = hole("W", 13), hole("X", 12), hole("X", 9)
    add(curve(p2, (p2[0] + 10, p2[1] + 220), (h2[0] + 40, h2[1] - 200), h2), COL["+5V"], p2, h2)
    add(curve(p1, (p1[0] - 5, p1[1] + 220), (h1[0] + 30, h1[1] - 220), h1), COL["GND"], p1, h1)
    add(curve(p5, (p5[0] - 170, p5[1] + 10), (h5[0] - 10, h5[1] - 260), h5), COL["GND"], p5, h5)

    # --- Arduino GND -> GND rail ---
    ag, hg = ard_xy("GND"), hole("X", 25)
    add(curve(ag, (ag[0] - 140, ag[1] + 20), (hg[0] + 20, hg[1] - 200), hg), COL["GND"], ag, hg)

    # --- signal wires: (VFD pin, Arduino pin, signal) ---
    sig = [(14, "D2", "DB7"), (13, "D3", "DB6"), (12, "D4", "DB5"), (11, "D5", "DB4"), (10, "D7", "DB3"),
           (9, "D8", "DB2"), (8, "D9", "DB1"), (7, "D10", "DB0"), (6, "D11", "E"), (4, "D12", "RS")]
    for n, a, name in sig:
        p, q = pin_xy(n), ard_xy(a)
        # inner column: leave between the outer pins first, then curve over to the Arduino
        start = (p[0] + PITCH / 2, p[1] + PITCH / 2) if n % 2 else p
        dx = q[0] - start[0]
        d = curve(start, (start[0] + dx * .45, start[1]), (q[0] - dx * .45, q[1]), q)
        if n % 2:
            d = f"M {p[0]:.1f},{p[1]:.1f} L " + d[2:]
        add(d, COL[name], p, q)

    s += wires + ends
    s.append(f'<text x="40" y="{H - 22}" font-size="14" fill="#9a9a9a" font-family="Segoe UI, Arial, sans-serif">'
             'Parts: Fritzing parts library (CC-BY-SA 3.0)  ·  VFD photo: own</text>')
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    svg_path = os.path.abspath(os.path.join(OUT, "wiring.svg"))
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(build())
    print("wrote", svg_path)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.goto("file:///" + svg_path.replace("\\", "/"))
            pg.screenshot(path=os.path.join(OUT, "wiring.png"))
            b.close()
        print("wrote", os.path.abspath(os.path.join(OUT, "wiring.png")))
    except Exception as e:
        print("PNG skipped:", e)
