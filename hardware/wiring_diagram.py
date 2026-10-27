#!/usr/bin/env python3
"""Breadboard-style wiring diagram (Fritzing look): VFD seen from the back + Arduino UNO.

    python wiring_diagram.py            -> ../docs/wiring.svg (+ wiring.png when Playwright + Chrome are available)

Layout trick: the VFD is drawn from the BACK (the side you plug the wires into), so its 2x7 header
sits at the right edge, and the UNO is rotated so its digital header faces it. The pin order then
matches 1:1 and no two wires cross.
"""
import os
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
W, H = 1400, 860

# VFD header (back view): even pins on the outer (right) column, odd on the inner one
X_EVEN, X_ODD, ROW0, ROW_PITCH, PIN_R = 725, 685, 200, 40, 12
# Arduino digital header (rotated 90° CCW: D0 at the top)
AX = 1075

COL = {
    "DB0": "#8e44ad", "DB1": "#2e86de", "DB2": "#10ac84", "DB3": "#84c11f",
    "DB4": "#f6c90e", "DB5": "#ff9f43", "DB6": "#ee5253", "DB7": "#c44569",
    "RS": "#00b8d4", "E": "#ff6bb5", "GND": "#2d3436", "+5V": "#e01e1e",
}


def pin_xy(n):
    row = (14 - n) // 2 if n % 2 == 0 else (13 - n) // 2
    return (X_EVEN if n % 2 == 0 else X_ODD), ROW0 + row * ROW_PITCH


def ard_y(name):
    order = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", None, "D8", "D9", "D10", "D11", "D12", "D13", "GND", "AREF"]
    return 170 + 20 * order.index(name)


def wire(points, color, width=7):
    d = "M " + " L ".join(f"{x},{y}" for x, y in points)
    return (f'<path d="{d}" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="{width + 3}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" '
            f'stroke-linecap="round"/>')


def text(x, y, s, size=15, color="#222", anchor="start", weight="normal", extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="Segoe UI, Arial, sans-serif" {extra}>{escape(str(s))}</text>')


def build():
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#f7f5f0"/>',
         text(40, 50, "VFD Spectrum Analyzer – wiring", 28, weight="bold"),
         text(40, 78, "Noritake CU20029ECPB-W1J seen from the BACK (connector side)  ·  Arduino UNO rotated 90°  ·  8-bit bus", 15, "#555")]

    # --- VFD board (back side) ---
    s.append('<rect x="60" y="120" width="700" height="380" rx="10" fill="#1e7a46" stroke="#13502e" stroke-width="3"/>')
    for hx, hy in ((82, 142), (738, 142), (82, 478), (738, 478)):
        s.append(f'<circle cx="{hx}" cy="{hy}" r="9" fill="#f7f5f0" stroke="#c9a54b" stroke-width="3"/>')
    s.append('<circle cx="260" cy="330" r="62" fill="#2b2b2b" stroke="#111" stroke-width="3"/>')
    s.append('<circle cx="260" cy="330" r="30" fill="#3a3a3a"/>')
    s.append('<rect x="370" y="210" width="150" height="110" rx="4" fill="#222"/>')
    s.append(text(445, 270, "ISE25001", 15, "#bbb", "middle"))
    s.append('<rect x="380" y="370" width="90" height="60" rx="3" fill="#222"/>')
    s.append(text(110, 175, "VFD – back side", 20, "#e8f5e9", weight="bold"))
    s.append(text(110, 200, "(mirror image of the datasheet front view)", 13, "#c8e6c9"))
    s.append(text(110, 470, "JP2 OPEN = M68 mode  ·  JP3 open  ·  JP1 leave as is", 14, "#fff59d"))

    # header outline + pins
    s.append(f'<rect x="{X_ODD - 22}" y="{ROW0 - 22}" width="{X_EVEN - X_ODD + 44}" height="{6 * ROW_PITCH + 44}" '
             f'rx="4" fill="#111" opacity=".85"/>')

    # --- wires: (VFD pin, Arduino pin, colour, label) ---
    sig = [(14, "D2", "DB7"), (13, "D3", "DB6"), (12, "D4", "DB5"), (11, "D5", "DB4"), (10, "D7", "DB3"),
           (9, "D8", "DB2"), (8, "D9", "DB1"), (7, "D10", "DB0"), (6, "D11", "E"), (4, "D12", "RS")]
    channels = [1040 - 22 * i for i in range(len(sig))]       # upper wire -> channel further right
    for (n, a, name), cx in zip(sig, channels):
        px, py = pin_xy(n)
        ay = ard_y(a)
        if n % 2 == 0:
            pts = [(AX, ay), (cx, ay), (cx, py), (px, py)]
        else:                                               # pass below the outer pin, then hook in
            pts = [(AX, ay), (cx, ay), (cx, py + 20), (X_ODD + 20, py + 20), (X_ODD + 20, py), (px, py)]
        s.append(wire(pts, COL[name]))
        ly = py if n % 2 == 0 else py + 20                  # label on the segment entering the header
        s.append(text(X_EVEN + 50, ly - 5, f"{name} → {a}", 11, "#b38f00" if name == "DB4" else COL[name],
                      weight="bold"))

    # R/W (5) -> GND (1) jumper on the inner side, GND / +5V from the supply
    p5, p3, p1, p2 = pin_xy(5), pin_xy(3), pin_xy(1), pin_xy(2)
    s.append(wire([p5, (X_ODD - 22, p5[1]), (X_ODD - 22, p1[1])], COL["GND"]))
    s.append(wire([(X_ODD - 22, 600), (X_ODD - 22, p1[1]), p1], COL["GND"]))
    s.append(wire([(X_EVEN + 22, 600), (X_EVEN + 22, p2[1]), p2], COL["+5V"]))
    # Arduino GND -> supply minus, around the left of the supply
    gy = ard_y("GND")
    s.append(wire([(AX, gy), (1050, gy), (1050, 700), (585, 700), (585, 545), (X_ODD - 22, 545)], COL["GND"]))
    s.append(f'<circle cx="{X_ODD - 22}" cy="545" r="7" fill="{COL["GND"]}"/>')
    s.append(text(800, 693, "GND (common)", 13, "#2d3436", weight="bold"))

    # capacitors right at the connector, across GND / +5V
    s.append(f'<rect x="{X_ODD - 14}" y="560" width="{X_EVEN - X_ODD + 30}" height="26" rx="13" fill="#24366b" stroke="#111" stroke-width="2"/>')
    s.append(f'<rect x="{X_ODD - 14}" y="560" width="10" height="26" rx="5" fill="#b8c4e6"/>')
    s.append(text(X_EVEN + 8, 578, "+", 16, "#fff", "middle", "bold"))
    s.append(text(X_ODD - 32, 579, "1000 µF", 13, "#24366b", "end", "bold"))
    s.append(f'<ellipse cx="{(X_ODD + X_EVEN) / 2}" cy="530" rx="18" ry="11" fill="#e6a23c" stroke="#8a5a12" stroke-width="2"/>')
    s.append(f'<line x1="{X_ODD - 22}" y1="530" x2="{(X_ODD + X_EVEN) / 2 - 18}" y2="530" stroke="#888" stroke-width="3"/>')
    s.append(f'<line x1="{(X_ODD + X_EVEN) / 2 + 18}" y1="530" x2="{X_EVEN + 22}" y2="530" stroke="#888" stroke-width="3"/>')
    s.append(text((X_ODD + X_EVEN) / 2, 535, "104", 11, "#4a3008", "middle", "bold"))
    s.append(text(X_ODD - 32, 535, "100 nF", 13, "#8a5a12", "end", "bold"))

    # pins on top of the wires, number inside
    for n in range(1, 15):
        x, y = pin_xy(n)
        fill = "#9e9e9e" if n == 3 else "#e8c547"
        s.append(f'<circle cx="{x}" cy="{y}" r="{PIN_R}" fill="{fill}" stroke="#5c4a0b" stroke-width="2"/>')
        s.append(text(x, y + 5, n, 13, "#000", "middle", "bold"))
    s.append(text(X_ODD - 40, pin_xy(3)[1] + 5, "NC", 13, "#ddd", "end", "bold"))
    s.append(text(X_ODD - 40, pin_xy(5)[1] + 5, "R/W", 13, "#ddd", "end", "bold"))
    s.append(text((X_ODD + X_EVEN) / 2, ROW0 - 32, "2×7 header", 13, "#e8f5e9", "middle", "bold"))

    # --- power supply ---
    s.append('<rect x="600" y="600" width="230" height="70" rx="8" fill="#3d3d3d" stroke="#111" stroke-width="2"/>')
    s.append(text(715, 630, "5 V power supply", 16, "#fff", "middle", "bold"))
    s.append(text(715, 652, "≥ 1 A  (2 displays: ≥ 3 A)", 13, "#ddd", "middle"))
    for x, lab in ((X_ODD - 22, "−"), (X_EVEN + 22, "+")):
        s.append(f'<rect x="{x - 11}" y="596" width="22" height="16" rx="3" fill="#2e7d32"/>')
        s.append(text(x, 594, lab, 18, "#000", "middle", "bold"))

    # --- Arduino UNO (rotated 90° CCW: digital header on the left, D0 on top) ---
    s.append('<rect x="1060" y="120" width="300" height="420" rx="12" fill="#00979c" stroke="#00686b" stroke-width="3"/>')
    s.append(f'<rect x="{AX - 12}" y="{ard_y("D0") - 12}" width="24" height="{ard_y("AREF") - ard_y("D0") + 24}" rx="3" fill="#1b1b1b"/>')
    for name in ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "GND", "AREF"]:
        y = ard_y(name)
        s.append(f'<rect x="{AX - 5}" y="{y - 5}" width="10" height="10" fill="#c9c9c9"/>')
        s.append(text(AX + 22, y + 5, name, 13, "#fff", weight="bold"))
    s.append(text(1305, 300, "Arduino UNO", 24, "#fff", "middle", "bold", 'transform="rotate(-90 1305 300)"'))
    s.append(text(1340, 300, "(Nano: same D-pins)", 14, "#d0f4f5", "middle", "", 'transform="rotate(-90 1340 300)"'))
    s.append('<rect x="1100" y="520" width="60" height="40" fill="#b0b0b0" stroke="#666"/>')
    s.append(text(1130, 580, "USB → PC", 13, "#333", "middle", "bold"))
    s.append(text(1132, ard_y("D6") + 5, "← E of 2nd display", 11, "#fff9c4"))
    # 5V pin warning
    s.append(text(1345, 470, "5V pin: NOT", 12, "#ffeb3b", "end", "bold"))
    s.append(text(1345, 486, "connected", 12, "#ffeb3b", "end", "bold"))

    # --- notes / legend ---
    notes = [
        "1.  The VFD takes 400 mA (≈ 800 mA at switch-on): power it from the separate 5 V supply, never from the Arduino.",
        "2.  Only GND is shared between the supply, the display and the Arduino. UNO: don't feed the 5 V into its 5V pin.",
        "3.  Capacitors go right at the display connector (pin 1 = GND, pin 2 = +5 V). Mind the electrolytic's polarity.",
        "4.  Two displays: connect everything in parallel except E (pin 6) – left display E → D11, right display E → D6.",
        "5.  Keep the wires short (< 20 cm), especially E. Pin numbering of the header is zig-zag, see the datasheet.",
    ]
    for i, n in enumerate(notes):
        s.append(text(40, 750 + i * 22, n, 14, "#333"))
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    svg_path = os.path.join(OUT, "wiring.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(build())
    print("wrote", os.path.abspath(svg_path))
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            pg.goto("file:///" + os.path.abspath(svg_path).replace("\\", "/"))
            pg.screenshot(path=os.path.join(OUT, "wiring.png"))
            b.close()
        print("wrote", os.path.abspath(os.path.join(OUT, "wiring.png")))
    except Exception as e:
        print("PNG skipped:", e)
