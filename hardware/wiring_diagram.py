#!/usr/bin/env python3
"""Breadboard-style wiring diagram from real pictures: a photo of the VFD's back + the Arduino UNO
graphic from the Fritzing parts library (CC-BY-SA 3.0), both at the same real-world scale.

    python wiring_diagram.py   -> ../docs/wiring.svg (self-contained) + ../docs/wiring.png (needs Playwright + Chrome)

Layout trick: the VFD is shown from the BACK (the side you plug the wires into), so its 2x7 header
sits at the right edge, and the UNO is rotated 90° so its digital header faces it. The pin order
then matches 1:1 and no two wires cross.
"""
import base64, os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "..", "docs")
W, H = 2560, 1180

# --- VFD photo (back side, header on the right), 10.96 px/mm ---
VX, VY = 40, 200                        # photo position
PHOTO_W, PHOTO_H = 1525, 471
X_EVEN, X_ODD = VX + 1500, VX + 1472    # header columns: even pins on the board edge
ROW_PITCH = 27.8                        # 2.54 mm
ROW0 = VY + 233 - 3 * ROW_PITCH         # pins 13/14

# --- Arduino UNO (Fritzing breadboard SVG, 212.372 x 151.2 units, 0.1" = 7.2 units) ---
U = 3.54                                # px per SVG unit (same mm scale as the photo)
UNO_W, UNO_H = 212.372, 151.2
AX0, AY0 = 1960, 230                    # top-left of the rotated board
UNO_PINS = {"D2": 183.57, "D3": 176.37, "D4": 169.17, "D5": 161.97, "D6": 154.77, "D7": 147.57,
            "D8": 136.05, "D9": 128.85, "D10": 121.65, "D11": 114.45, "D12": 107.25, "D13": 100.05,
            "GND": 92.85, "AREF": 85.65}   # x of the top header pins (y = 7.2)

COL = {
    "DB0": "#8e44ad", "DB1": "#2e86de", "DB2": "#10ac84", "DB3": "#7cb518",
    "DB4": "#e1b000", "DB5": "#ff8c1a", "DB6": "#ee5253", "DB7": "#c44569",
    "RS": "#00a8c6", "E": "#ff5fa8", "GND": "#222", "+5V": "#e01e1e",
}


def pin_xy(n):
    row = (14 - n) // 2 if n % 2 == 0 else (13 - n) // 2
    return (X_EVEN if n % 2 == 0 else X_ODD), ROW0 + row * ROW_PITCH


def ard_xy(name):
    """Pin position after rotating the board 90° CCW (header on the left, D0 on top)."""
    return AX0 + 7.2 * U, AY0 + (UNO_W - UNO_PINS[name]) * U


def data_uri(path, mime):
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def wire(points, color, width=7):
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (f'<path d="{d}" fill="none" stroke="#000" stroke-opacity=".45" stroke-width="{width + 3}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" '
            f'stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="#fff" stroke-opacity=".25" stroke-width="2" '
            f'stroke-linejoin="round" transform="translate(-1.5,-1.5)"/>')


def end(x, y, color):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" stroke="#000" stroke-width="2"/>'


def text(x, y, s, size=16, color="#222", anchor="start", weight="normal", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="Segoe UI, Arial, sans-serif" {extra}>{escape(str(s))}</text>')


def tag(x, y, s, color):
    w = 9 * len(s) + 12
    return (f'<rect x="{x:.1f}" y="{y - 10:.1f}" width="{w}" height="20" rx="10" fill="{color}" stroke="#000" '
            f'stroke-opacity=".4"/>' + text(x + w / 2, y + 5, s, 13, "#fff", "middle", "bold"))


def build():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#f4f1ea"/>',
         text(40, 70, "VFD Spectrum Analyzer – wiring", 40, weight="bold"),
         text(40, 110, "Noritake CU20029ECPB-W1J seen from the BACK (connector side)   ·   Arduino UNO rotated 90°"
                       "   ·   8-bit bus   ·   to scale", 20, "#555")]

    # pictures
    s.append(f'<image x="{VX}" y="{VY}" width="{PHOTO_W}" height="{PHOTO_H}" '
             f'href="{data_uri(os.path.join(ASSETS, "vfd_back.jpg"), "image/jpeg")}"/>')
    uno = data_uri(os.path.join(ASSETS, "arduino_uno_rev3_fritzing.svg"), "image/svg+xml")
    # rotate -90° about the origin, then move: (x, y) -> (y, W - x)
    s.append(f'<g transform="translate({AX0},{AY0 + UNO_W * U}) rotate(-90) scale({U})">'
             f'<image width="{UNO_W}" height="{UNO_H}" href="{uno}"/></g>')

    # 2x7 header drawn over the photo (the real one has plugs on it)
    hx0, hy0 = X_ODD - 15, ROW0 - 15
    s.append(f'<rect x="{hx0}" y="{hy0}" width="{X_EVEN - X_ODD + 30}" height="{6 * ROW_PITCH + 30}" rx="3" '
             f'fill="#141414" stroke="#000"/>')
    for n in range(1, 15):
        x, y = pin_xy(n)
        s.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#d4b13a" stroke="#7a5f10"/>')

    # --- signal wires: (VFD pin, Arduino pin, signal) ---
    sig = [(14, "D2", "DB7"), (13, "D3", "DB6"), (12, "D4", "DB5"), (11, "D5", "DB4"), (10, "D7", "DB3"),
           (9, "D8", "DB2"), (8, "D9", "DB1"), (7, "D10", "DB0"), (6, "D11", "E"), (4, "D12", "RS")]
    channels = [1915 - 19 * i for i in range(len(sig))]     # upper wire -> channel further right
    for i, ((n, a, name), cx) in enumerate(zip(sig, channels)):
        px, py = pin_xy(n)
        ax, ay = ard_xy(a)
        if n % 2 == 0:
            approach = py
            pts = [(ax, ay), (cx, ay), (cx, py), (px, py)]
        else:                                               # pass between the outer pins, then hook in
            approach = py + ROW_PITCH / 2
            mid = (X_ODD + X_EVEN) / 2
            pts = [(ax, ay), (cx, ay), (cx, approach), (mid, approach), (mid, py), (px, py)]
        s.append(wire(pts, COL[name]))
        s.append(end(px, py, COL[name]))
        s.append(end(ax, ay, COL[name]))
        s.append(tag(VX + PHOTO_W + 12 + (i % 2) * 60, approach, name, COL[name]))

    # --- power: R/W (5) -> GND (1) jumper, supply, capacitors ---
    p5, p1, p2 = pin_xy(5), pin_xy(1), pin_xy(2)
    gx, vx = X_ODD - 20, X_EVEN + 22                # GND / +5V rails left and right of the header
    sup_y = 860
    s.append(wire([p5, (gx, p5[1]), (gx, sup_y)], COL["GND"]))
    s.append(wire([p1, (gx, p1[1])], COL["GND"]))
    s.append(wire([p2, (vx, p2[1]), (vx, sup_y)], COL["+5V"]))
    for p, c in ((p5, "GND"), (p1, "GND"), (p2, "+5V")):
        s.append(end(*p, COL[c]))
    s.append(tag(gx - 78, p5[1], "R/W", "#555"))
    s.append(text(gx - 12, pin_xy(3)[1] + 5, "NC", 14, "#fff", "end", "bold"))

    # Arduino GND -> supply minus (around the left of the supply)
    ax, ay = ard_xy("GND")
    s.append(wire([(ax, ay), (1700, ay), (1700, 990), (1340, 990), (1340, 830), (gx, 830)], COL["GND"]))
    s.append(end(ax, ay, COL["GND"]))
    s.append(f'<circle cx="{gx}" cy="830" r="8" fill="{COL["GND"]}"/>')
    s.append(tag(1460, 990, "GND (common)", "#333"))

    # capacitors across the rails, right at the connector
    cy1, cy2 = 735, 785
    s.append(f'<line x1="{gx}" y1="{cy1}" x2="{vx}" y2="{cy1}" stroke="#9a9a9a" stroke-width="3"/>')
    s.append(f'<ellipse cx="{(gx + vx) / 2}" cy="{cy1}" rx="17" ry="12" fill="#e9a23b" stroke="#8a5a12" stroke-width="2"/>')
    s.append(text((gx + vx) / 2, cy1 + 4, "104", 11, "#4a3008", "middle", "bold"))
    s.append(text(gx - 14, cy1 + 5, "100 nF", 17, "#8a5a12", "end", "bold"))
    s.append(f'<line x1="{gx}" y1="{cy2}" x2="{vx}" y2="{cy2}" stroke="#9a9a9a" stroke-width="3"/>')
    s.append(f'<rect x="{gx + 8}" y="{cy2 - 15}" width="{vx - gx - 16}" height="30" rx="6" fill="#1f2f6b" stroke="#0c143a" stroke-width="2"/>')
    s.append(f'<rect x="{gx + 8}" y="{cy2 - 15}" width="12" height="30" rx="4" fill="#c6cff0"/>')
    s.append(text(vx - 18, cy2 + 6, "+", 18, "#fff", "middle", "bold"))
    s.append(text(gx - 14, cy2 + 5, "1000 µF", 17, "#1f2f6b", "end", "bold"))

    # power supply
    s.append(f'<rect x="{gx - 120}" y="{sup_y}" width="{vx - gx + 240}" height="90" rx="10" fill="#2f2f2f" stroke="#000" stroke-width="2"/>')
    s.append(text((gx + vx) / 2, sup_y + 50, "5 V power supply", 22, "#fff", "middle", "bold"))
    s.append(text((gx + vx) / 2, sup_y + 76, "≥ 1 A  (two displays: ≥ 3 A)", 16, "#ccc", "middle"))
    for x, lab in ((gx, "−"), (vx, "+")):
        s.append(f'<rect x="{x - 12}" y="{sup_y - 4}" width="24" height="18" rx="3" fill="#2e7d32"/>')
        s.append(text(x + (-22 if lab == "−" else 22), sup_y + 12, lab, 24, "#000", "middle", "bold"))

    # Arduino notes
    d6x, d6y = ard_xy("D6")
    s.append(text(1990, 150, "D6 = E of the 2nd (right) display, optional", 16, "#555"))
    s.append(f'<line x1="2110" y1="158" x2="{d6x - 4}" y2="{d6y - 4}" stroke="#555" stroke-width="1.5" stroke-dasharray="5 4"/>')
    s.append(text(2510, 1000, "UNO 5V pin: NOT connected", 18, "#c62828", "end", "bold"))
    s.append(text(2510, 1024, "USB → PC (data only)", 18, "#333", "end"))

    # notes
    notes = [
        "1.  The VFD takes 400 mA (≈ 800 mA at switch-on): power it from the separate 5 V supply, never from the Arduino.",
        "2.  Only GND is shared between the supply, the display and the Arduino. UNO: never feed the 5 V into its 5V pin.",
        "3.  Capacitors go right at the display connector, across pin 1 (GND) and pin 2 (+5 V). Mind the polarity.",
        "4.  Display jumpers: JP2 OPEN (M68 mode), JP3 open, JP1 as from the factory.  Two displays: all in parallel except E.",
        "5.  Keep the wires short (< 20 cm), especially E.",
    ]
    for i, n in enumerate(notes):
        s.append(text(40, 760 + i * 30, n, 19, "#333"))
    s.append(text(40, H - 24, "Arduino UNO graphic: Fritzing parts library, CC-BY-SA 3.0 (fritzing.org)  ·  VFD photo: own", 14, "#888"))
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
