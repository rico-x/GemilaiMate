#!/usr/bin/env python3
"""Build docs/wiring.html: wiring scheme (SVG), 3D view and harness tables from one connection model.

Carrier pins come from hardware/carrier/connections.csv; modules, harness notes and the reference mains
wiring are described below. --check fails if docs/wiring.html is out of date; --fragment PATH also writes
the page body without the document wrapper (for publishing as an Artifact).
"""
import argparse, base64, csv, json, html, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/wiring.html"
TEMPLATE = REPO / "tools/wiring_template.html"

# ---------- carrier connector pins (mm, from connections.csv) ----------
pins_mm = {}
for r in csv.DictReader((REPO / "hardware/carrier/connections.csv").open()):
    if r["Reference"].startswith("J"):
        pins_mm[(r["Reference"], r["Pin"])] = (float(r["x_mm"]), float(r["y_mm"]), r["Pin name"], r["Net"])

S, CX0, CY0 = 6.0, 430.0, 390.0          # 2D: px per mm and carrier origin
def cpx(ref, pin):
    x, y, *_ = pins_mm[(ref, pin)]
    return (CX0 + x * S, CY0 + y * S)

# ---------- modules (2D boxes, pins, 3D placement) ----------
M = {
 "psu": dict(t="БП 5 В / 2 А", s="изолированный, заводской", box=(290, 160, 150, 120), zone="straddle",
             pins={"L": (320, 160), "N": (350, 160), "+V": (400, 280), "−V": (420, 280)},
             d3=dict(c=(-78, -78), size=(60, 36, 24), color="#d9dcd8", shape="box")),
 "disp": dict(t="LilyGo T-RGB 2.1", s="дисплей · связь по BLE", circle=(540, 232, 50), zone="lv",
              pins={"VBUS": (532, 292), "GND": (548, 292)},
              d3=dict(c=(-22, -86), size=(62, 62, 9), color="#1d1f22", shape="disk")),
 "rd": dict(t="RobotDyn 16A", s="диммер помпы", box=(610, 160, 130, 140), zone="straddle",
            pins={"AC-IN L": (630, 160), "AC-IN N": (655, 160), "LOAD": (715, 160),
                  "VCC": (622, 300), "GND": (640, 300), "Z-C": (658, 300), "PSM": (676, 300)},
            d3=dict(c=(30, -92), size=(52, 72, 22), color="#1f5fa8", shape="dimmer")),
 "ps": dict(t="XDB401", s="0–1,6 МПа · 0,5–4,5 В", box=(760, 200, 80, 100), zone="lv",
            pins={"+5V": (775, 300), "GND": (795, 300), "OUT": (815, 300), "G1/4": (800, 200)},
            d3=dict(c=(80, -82), size=(22, 55, 22), color="#b9c0c4", shape="sensor")),
 "ads": dict(t="ADS1115", s="АЦП давления · 0x48", box=(380, 735, 185, 90), zone="lv",
             pins={n: (395 + 18 * i, 735) for i, n in enumerate(["VDD", "GND", "SCL", "SDA", "ADDR", "ALRT", "A0", "A1", "A2", "A3"])},
             d3=dict(c=(-46, 70), size=(28, 17, 3), color="#1f5fa8", shape="pcb")),
 "txs": dict(t="TXS0102", s="уровни I²C 3,3↔5 В", box=(572, 735, 118, 80), zone="lv",
             pins={n: (582 + 14 * i, 735) for i, n in enumerate(["VCCA", "GND", "A1", "A2", "VCCB", "OE", "B1", "B2"])},
             d3=dict(c=(-13, 70), size=(16, 14, 3), color="#5b3f9e", shape="pcb")),
 "max": dict(t="MAX31855", s="термопара K", box=(698, 735, 108, 95), zone="lv",
             pins={"Vin": (708, 735), "3Vo": (724, 735), "GND": (740, 735), "DO": (756, 735), "CS": (772, 735), "CLK": (788, 735),
                   "T+": (735, 830), "T−": (775, 830)},
             d3=dict(c=(17, 72), size=(24, 19, 3), color="#9e2a3a", shape="pcb")),
 "btn": dict(t="Кнопки", s="Brew · Steam", box=(814, 735, 92, 90), zone="lv",
             pins={"BREW": (826, 735), "COM1": (844, 735), "STEAM": (868, 735), "COM2": (886, 735)},
             d3=dict(c=(47, 76), size=(26, 16, 6), color="#2a2d30", shape="buttons")),
 "ssr": dict(t="SSR клапана", s="G3MB · High 5V", box=(916, 735, 134, 95), zone="straddle",
             pins={"DC+": (930, 735), "DC−": (948, 735), "CH1": (966, 735), "L": (1050, 765), "OUT": (1050, 800)},
             d3=dict(c=(80, 76), size=(26, 34, 18), color="#1f5fa8", shape="ssr")),
 "pump": dict(t="Помпа", s="вибрационная", box=(1090, 190, 150, 70), zone="machine",
              pins={"L": (1110, 190)},
              d3=dict(c=(168, -86), size=(95, 40, 40), color="#2e3a2f", shape="pump")),
 "stock": dict(t="Штатная плата Gemilai", s="нагрев · пар · термоблок — без изменений", box=(1090, 420, 290, 130), zone="machine",
               pins={"PUMP": (1160, 420), "VALVE": (1170, 550)},
               d3=dict(c=(168, 4), size=(80, 55, 2), color="#2f6d3a", shape="pcb")),
 "valve": dict(t="Клапан Brew (3WV)", s="катушка 230 В", box=(1090, 760, 150, 80), zone="machine",
               pins={"L": (1090, 800)},
               d3=dict(c=(162, 86), size=(30, 28, 38), color="#a7adb1", shape="valve")),
 "boiler": dict(t="Бойлер", s="термопара в M3 сверху", box=(690, 905, 170, 75), zone="machine",
                pins={"TC": (755, 905)},
                d3=dict(c=(-112, 112), size=(56, 56, 42), color="#c4c8cb", shape="boiler")),
}

# ---------- low-voltage harnesses ----------
H = [
 ("J1", "Питание 5 В", "psu", [("1", "+V", "5v", "+5V"), ("2", "−V", "gnd", "GND")],
  "AWG22 и короче; внешний БП на стенде, ограничение тока при первом включении."),
 ("J9", "Питание дисплея", "disp", [("1", "VBUS", "5v", "+5V"), ("2", "GND", "gnd", "GND")],
  "Кабель USB-C только для питания. Жилы VBUS/GND прозвонить, на PA/Grove 5 В не подавать."),
 ("J5", "Диммер помпы", "rd", [("1", "VCC", "5v", "+5V"), ("2", "GND", "gnd", "GND"), ("3", "Z-C", "pump", "ZC_RAW"), ("4", "PSM", "pump", "PUMP_PWM")],
  "Z-C и PSM свить с GND, вести отдельно от сетевых проводов. Z-C — логика 0–5 В."),
 ("J4", "Датчик давления", "ps", [("1", "+5V", "5v", "+5V"), ("2", "GND", "gnd", "GND"), ("3", "OUT", "analog", "PRESSURE_RAW")],
  "Цвета жил датчика — по его паспорту, прозвонить до подключения."),
 ("J2", "АЦП ADS1115", "ads", [("1", "VDD", "5v", "+5V"), ("2", "GND", "gnd", "GND"), ("3", "SCL", "data", "SCL_5V"), ("4", "SDA", "data", "SDA_5V"),
                               ("5", "A0", "analog", "PRESSURE"), ("6", "ADDR", "gnd", "GND")],
  "Порядок на модуле другой: J2.5 → A0 (7-й вывод), J2.6 → ADDR (5-й). ALRT, A1–A3 свободны. Модуль ставить рядом с J2."),
 ("J7", "Преобразователь I²C", "txs", [("1", "VCCA", "3v3", "+3V3"), ("2", "GND", "gnd", "GND"), ("3", "A1", "data", "SCL_3V3"), ("4", "A2", "data", "SDA_3V3"),
                                       ("5", "VCCB", "5v", "+5V"), ("6", "OE", "3v3", "+3V3"), ("7", "B1", "data", "SCL_5V"), ("8", "B2", "data", "SDA_5V")],
  "Выводы модуля подписаны по маркировке TXS0102; на плате модуля они в другом порядке и в два ряда."),
 ("J3", "Термопара MAX31855", "max", [("1", "Vin", "5v", "TC_VIN (JP3 1–2 → +5V)"), ("2", "GND", "gnd", "GND"), ("3", "DO", "data", "TC_DO"),
                                       ("4", "CS", "data", "TC_CS"), ("5", "CLK", "data", "TC_SCK")],
  "JP3 в положении 1–2 (Vin 5 В). Вывод 3Vo не подключать. Термопару — к клеммам T+/T− с соблюдением полярности."),
 ("J8", "Кнопки", "btn", [("1", "BREW", "btn", "BREW_CONTACT"), ("3", "COM1", "gnd", "GND"), ("2", "STEAM", "btn", "STEAM_CONTACT"), ("4", "COM2", "gnd", "GND")],
  "Только независимые сухие контакты на GND. Штатную цепь кнопок не подключать, пока её схема и изоляция не проверены."),
 ("J6", "SSR клапана", "ssr", [("1", "DC+", "5v", "+5V"), ("2", "DC−", "gnd", "GND"), ("3", "CH1", "valve", "VALVE_IN")],
  "Вход SSR питается от буфера AHCT125 через R13. Ток входа SSR измерить на стенде."),
]

# ---------- mains / machine links (reference architecture) ----------
L_BUS, N_BUS, L_COL = 60, 95, 1065
MAINS = [
 dict(id="M1", t="L → предохранитель T2A → БП", kind="L", pts=[(320, L_BUS), (320, 160)], fuse=(320, 118)),
 dict(id="M1", t="N → БП", kind="N", pts=[(350, N_BUS), (350, 160)]),
 dict(id="M2", t="L → RobotDyn AC-IN", kind="L", pts=[(630, L_BUS), (630, 160)]),
 dict(id="M2", t="N → RobotDyn AC-IN", kind="N", pts=[(655, N_BUS), (655, 160)]),
 dict(id="M3", t="RobotDyn LOAD → помпа", kind="load", pts=[(715, 160), (715, 135), (1110, 135), (1110, 190)]),
 dict(id="M4", t="L → SSR", kind="L", pts=[(L_COL, L_BUS), (L_COL, 765), (1050, 765)]),
 dict(id="M4", t="SSR → клапан", kind="load", pts=[(1050, 800), (1090, 800)]),
]
BUS = [dict(kind="L", pts=[(205, L_BUS), (L_COL, L_BUS)]), dict(kind="N", pts=[(205, N_BUS), (655, N_BUS)])]
JUNCTIONS = [(320, L_BUS), (630, L_BUS), (350, N_BUS)]
STOCK = [dict(t="штатный выход помпы ∥", pts=[(1160, 420), (1160, 260)], lab=(1170, 345)),
         dict(t="штатный выход клапана ∥", pts=[(1170, 550), (1170, 760)], lab=(1180, 660))]
WATER = [(800, 200), (800, 178), (1262, 178), (1262, 214)]

WIRE_LABEL = {"5v": "+5 В", "3v3": "+3,3 В", "gnd": "GND", "data": "I²C / SPI", "analog": "давление (аналог)",
              "pump": "помпа: ZC / PSM", "valve": "клапан: управление", "btn": "кнопки", "L": "сеть L",
              "N": "сеть N", "load": "нагрузка (коммутируемая L)", "tc": "термопара K", "water": "вода", "ble": "BLE"}

esc = html.escape

def route(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

def lv_routes():
    """Orthogonal routes per harness that avoid self-crossings where the pin order allows."""
    out = []
    for ref, title, mod, wires, note in H:
        rows = []
        for pin, mpin, kind, net in wires:
            cx, cy = cpx(ref, pin)
            mx, my = M[mod]["pins"][mpin]
            rows.append((cx, cy, mx, my, pin, mpin, kind, net))
        top = rows[0][3] < CY0                      # module above the carrier
        rows.sort(key=lambda r: r[0])
        shift = sum(r[2] - r[0] for r in rows)
        n = len(rows)
        lo, hi = (306, 384) if top else (674, 728)
        gap = min(7.0, (hi - lo) / max(n, 1))
        segs = []
        for i, (cx, cy, mx, my, pin, mpin, kind, net) in enumerate(rows):
            k = (n - 1 - i) if shift > 0 else i
            ym = lo + 4 + k * gap
            if top:   # module pin (above) -> carrier pin (below)
                pts = [(mx, my), (mx, ym), (cx, ym), (cx, cy)]
            else:     # carrier pin (above) -> module pin (below)
                pts = [(cx, cy), (cx, ym), (mx, ym), (mx, my)]
            segs.append(dict(pin=pin, mpin=mpin, kind=kind, net=net, pts=pts))
        out.append(dict(ref=ref, title=title, mod=mod, note=note, segs=segs))
    return out

ROUTES = lv_routes()

# ---------- SVG ----------
def svg():
    o = []
    a = o.append
    a('<svg viewBox="0 0 1400 1000" role="img" aria-label="Схема подключения GemilaiMate: carrier в центре, '
      'модули питания, помпы и датчика давления сверху, АЦП, термопара, кнопки и SSR клапана снизу, '
      'сетевая часть 230 вольт по верхнему краю и справа." class="scheme">')
    a('<defs><pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      '<line x1="0" y1="0" x2="0" y2="10" class="hatch-line"/></pattern>'
      '<marker id="dot" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5">'
      '<circle cx="3" cy="3" r="2.6" class="end-dot"/></marker></defs>')
    # zones
    a('<path class="zone-mains" d="M10 20 H1390 V880 H1045 V170 H10 Z"/>')
    a('<text class="zone-label" x="22" y="140">230 В · сетевая часть</text>')
    a('<text class="zone-label" x="22" y="157">только на обесточенной машине</text>')
    a('<text class="zone-label" x="1378" y="42" text-anchor="end">машина Gemilai 3007Z</text>')
    a('<text class="zone-label lv" x="22" y="195">5 В / 3,3 В · низковольтная часть</text>')
    # mains source
    a('<g class="mains-src"><rect x="20" y="38" width="176" height="80" rx="4" class="box machine"/>'
      '<text class="m-title" x="32" y="60">Сеть 230 В</text>'
      '<text class="m-sub" x="32" y="78">после выключателя</text><text class="m-sub" x="32" y="93">и защиты машины</text>'
      '<text class="m-sub" x="32" y="108">PE — корпус, без изменений</text></g>')
    a(f'<text class="bus-label L" x="208" y="{L_BUS - 6}">L</text><text class="bus-label N" x="208" y="{N_BUS - 6}">N</text>')
    for b in BUS:
        a(f'<polyline class="w w-{b["kind"]} bus" points="{route(b["pts"])}"/>')
    for mw in MAINS:
        a(f'<polyline class="w w-{mw["kind"]} mains" points="{route(mw["pts"])}"><title>{esc(mw["id"])}: {esc(mw["t"])}</title></polyline>')
        if "fuse" in mw:
            fx, fy = mw["fuse"]
            a(f'<rect x="{fx - 9}" y="{fy - 13}" width="18" height="26" rx="2" class="fuse"/>'
              f'<text class="pin-lab" x="{fx + 14}" y="{fy + 4}">T2A</text>')
    for x, y in JUNCTIONS:
        a(f'<circle cx="{x}" cy="{y}" r="3.6" class="junction"/>')
    a(f'<circle cx="{L_COL}" cy="{L_BUS}" r="3.6" class="junction"/>')
    # stock outputs (dashed, to verify)
    for s in STOCK:
        a(f'<polyline class="w stock" points="{route(s["pts"])}"/><text class="note-lab" x="{s["lab"][0]}" y="{s["lab"][1]}">{esc(s["t"])}</text>')
    a(f'<text class="note-lab" x="1180" y="{660 + 15}">Y-переходник, проверить</text>')
    a(f'<text class="note-lab" x="1170" y="{345 + 15}">Y-переходник, проверить</text>')
    # water
    a(f'<polyline class="w w-water" points="{route(WATER)}"/>')
    a('<circle cx="1262" cy="225" r="10" class="tee"/><text class="note-lab" x="1278" y="222">тройник</text>'
      '<text class="note-lab" x="1278" y="237">помпа → OPV</text>')
    a('<text class="note-lab" x="905" y="172">вода, G1/4</text>')
    # thermocouple
    a('<polyline class="w w-tc" points="735,830 735,905"/><polyline class="w w-tc" points="775,830 775,905"/>')
    a('<text class="note-lab" x="784" y="872">термопара K</text>')
    # carrier
    a(f'<g class="carrier"><rect x="{CX0}" y="{CY0}" width="{90 * S}" height="{46 * S}" rx="6" class="pcb"/>')
    a(f'<rect x="{CX0 + 3.5 * S}" y="{CY0 + 7.6 * S}" width="{62.8 * S}" height="{28 * S}" rx="3" class="devkit"/>')
    a(f'<rect x="{CX0 + 47.9 * S}" y="{CY0 + 12.0 * S}" width="{18.4 * S}" height="{19.2 * S}" rx="2" class="wroom"/>')
    a(f'<text class="dev-title" x="{CX0 + 9 * S}" y="{CY0 + 19 * S}">ESP32-S3 DevKit N8R8 · контроллер</text>')
    a(f'<text class="dev-sub" x="{CX0 + 9 * S}" y="{CY0 + 22.6 * S}">в гнёздах, ряд A · USB слева</text>')
    a(f'<text class="dev-sub" x="{CX0 + 50 * S}" y="{CY0 + 33.5 * S}">антенна</text>')
    a(f'<text class="pcb-title" x="{CX0 + 68.5 * S}" y="{CY0 + 31 * S}">carrier v0.1</text>'
      f'<text class="pcb-title" x="{CX0 + 68.5 * S}" y="{CY0 + 33.6 * S}">90 × 46 мм</text></g>')
    # connectors
    groups = {}
    for (ref, pin), (x, y, pname, net) in pins_mm.items():
        groups.setdefault(ref, []).append((x, y))
    for ref, pts in sorted(groups.items()):
        xs = [CX0 + p[0] * S for p in pts]; ys = [CY0 + p[1] * S for p in pts]
        x0, x1, y0, y1 = min(xs) - 7, max(xs) + 7, min(ys) - 7, max(ys) + 7
        a(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="2" class="conn"/>')
        for x, y in zip(xs, ys):
            a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.1" class="pin"/>')
        top = ys[0] < CY0 + 20 * S
        if ref == "J10":
            a(f'<text class="conn-lab" x="{x0 - 6:.1f}" y="{y0 + 11:.1f}" text-anchor="end">J10</text>'
              f'<text class="pcb-note" x="{x0 - 6:.1f}" y="{y0 + 25:.1f}" text-anchor="end">не подключать</text>')
        elif top:
            a(f'<text class="conn-lab" x="{(x0 + x1) / 2:.1f}" y="{y1 + 15:.1f}" text-anchor="middle">{ref}{" 1–2" if ref.startswith("JP") else ""}</text>')
        else:
            a(f'<text class="conn-lab" x="{(x0 + x1) / 2:.1f}" y="{y0 - 6:.1f}" text-anchor="middle">{ref}</text>')
    for ref, lab in (("JP1", "JP1 1–2"), ("JP3", "JP3 1–2")):
        x1, y1 = cpx(ref, "1"); x2, _ = cpx(ref, "2")
        a(f'<rect x="{x1 - 7:.1f}" y="{y1 - 7:.1f}" width="{x2 - x1 + 14:.1f}" height="14" rx="2" class="jumper"/>')
    # BLE
    # harness wires
    for r in ROUTES:
        a(f'<g class="harness" data-h="{r["ref"]}" tabindex="0"><title>{r["ref"]} — {esc(r["title"])}</title>')
        for sg in r["segs"]:
            a(f'<polyline class="w w-{sg["kind"]}" points="{route(sg["pts"])}"/>')
        a('</g>')
    # modules
    for mid, m in M.items():
        cls = {"lv": "box", "straddle": "box", "machine": "box machine"}[m["zone"]]
        if "circle" in m:
            cx, cy, rr = m["circle"]
            a(f'<g class="module" data-m="{mid}"><circle cx="{cx}" cy="{cy}" r="{rr}" class="{cls} round"/>'
              f'<circle cx="{cx}" cy="{cy}" r="{rr - 9}" class="screen"/>'
              f'<rect x="{cx - 14}" y="{cy + rr - 2}" width="28" height="10" rx="3" class="usb"/>'
              f'<text class="m-title light" x="{cx}" y="{cy - 2}" text-anchor="middle">{esc(m["t"])}</text>'
              f'<text class="m-sub light" x="{cx}" y="{cy + 14}" text-anchor="middle">связь по BLE</text>'
              f'<text class="pin-lab" x="{cx + 20}" y="{cy + rr + 7}">USB-C</text></g>')
            continue
        x, y, w, h = m["box"]
        a(f'<g class="module" data-m="{mid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" class="{cls}"/>')
        ty = y + h / 2 - 2 if mid not in ("ads", "txs", "max", "btn", "ssr", "psu", "rd", "ps") else y + h / 2 + 8
        tx = x + w / 2 - (14 if mid == "ssr" else 0)
        if mid in ("rd", "psu", "ps"):
            ty = y + h / 2 - 6
        a(f'<text class="m-title" x="{tx}" y="{ty}" text-anchor="middle">{esc(m["t"])}</text>')
        a(f'<text class="m-sub" x="{tx}" y="{ty + 16}" text-anchor="middle">{esc(m["s"])}</text>')
        for pn, (px, py) in m["pins"].items():
            side_top = abs(py - y) < 1; side_bot = abs(py - (y + h)) < 1; side_r = abs(px - (x + w)) < 1; side_l = abs(px - x) < 1
            a(f'<circle cx="{px}" cy="{py}" r="3.4" class="mpin"/>')
            if mid in ("pump", "valve", "stock", "boiler"):
                continue
            lab = pn
            if side_top:      # labels run into the box, rotated for dense pin rows
                a(f'<text class="pin-lab" transform="translate({px + 3.5},{py + 8}) rotate(90)">{esc(lab)}</text>')
            elif side_bot and y < CY0:
                a(f'<text class="pin-lab" transform="translate({px - 3.5},{py - 8}) rotate(-90)">{esc(lab)}</text>')
            elif side_bot:
                a(f'<text class="pin-lab" x="{px}" y="{py - 8}" text-anchor="middle">{esc(lab)}</text>')
            elif side_r:
                a(f'<text class="pin-lab" x="{px - 6}" y="{py + 4}" text-anchor="end">{esc(lab)}</text>')
            elif side_l:
                a(f'<text class="pin-lab" x="{px + 6}" y="{py + 4}">{esc(lab)}</text>')
        a('</g>')
    a('<text class="note-lab" x="1110" y="858">RC-снаббер параллельно катушке — по месту</text>')
    a('<text class="note-lab" x="1110" y="282">N помпы и клапана — штатные</text>')
    a('</svg>')
    return "".join(o)

# ---------- harness tables ----------
def tables():
    o = []
    for r in ROUTES:
        m = M[r["mod"]]
        o.append(f'<section class="hcard" id="h-{r["ref"]}"><header><span class="ref">{r["ref"]}</span>'
                 f'<h3>{esc(r["title"])}</h3><span class="to">→ {esc(m["t"])}</span></header>'
                 '<div class="tbl"><table><thead><tr><th>Carrier</th><th>Цепь</th><th>Модуль</th><th>Провод</th></tr></thead><tbody>')
        for sg in sorted(r["segs"], key=lambda s: int(s["pin"])):
            o.append(f'<tr><td class="mono">{r["ref"]}.{sg["pin"]}</td><td class="mono">{esc(sg["net"])}</td>'
                     f'<td class="mono">{esc(sg["mpin"])}</td><td><span class="sw sw-{sg["kind"]}"></span>{esc(WIRE_LABEL[sg["kind"]])}</td></tr>')
        o.append(f'</tbody></table></div><p class="hnote">{esc(r["note"])}</p></section>')
    mains_rows = [
        ("M1", "Сеть L → T2A → БП L; сеть N → БП N", "L, N", "AWG18; предохранитель T2A в держателе 5×20"),
        ("M2", "Сеть L, N → RobotDyn AC-IN", "L, N", "AWG18; N нужен диммеру для детектора нуля"),
        ("M3", "RobotDyn LOAD → клемма помпы", "коммутируемая L", "AWG18; параллельно штатному выходу через Y-переходник"),
        ("M4", "Сеть L → SSR → клемма клапана Brew", "L, коммутируемая L", "AWG18; RC-снаббер по месту; ток SSR ≤ 2 А"),
        ("—", "PE, нагрев, пар, термоблок", "—", "без изменений, штатная плата"),
    ]
    o.append('<section class="hcard mains-card" id="h-mains"><header><span class="ref haz">230 В</span><h3>Сетевая часть</h3>'
             '<span class="to">по референсной переделке</span></header><div class="tbl"><table><thead><tr><th>№</th><th>Соединение</th><th>Провод</th><th>Примечание</th></tr></thead><tbody>')
    for a_, b, c, d in mains_rows:
        o.append(f'<tr><td class="mono">{a_}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>')
    o.append('</tbody></table></div><p class="hnote">Схема повторяет переделку Turin Legato V2 из обсуждения GaggiMate #222. '
             'Для Gemilai 3007Z клеммы, защиту и поведение штатных выходов нужно проверить по конкретной машине. '
             'Все работы — на обесточенной машине.</p></section>')
    return "".join(o)

# ---------- 3D data ----------
def d3data():
    mods = {}
    for mid, m in M.items():
        d = m["d3"]
        if "circle" in m:
            cx, cy, rr = m["circle"]; bx, by, bw, bh = cx - rr, cy - rr, 2 * rr, 2 * rr
        else:
            bx, by, bw, bh = m["box"]
        w, dpt, h = d["size"]
        pins = {}
        for pn, (px, py) in m["pins"].items():
            fx = (px - bx) / bw - 0.5; fz = (py - by) / bh - 0.5
            pins[pn] = [round(d["c"][0] + fx * w, 2), round(h, 2), round(d["c"][1] + fz * dpt, 2)]
        mods[mid] = dict(t=m["t"], s=m["s"], c=d["c"], size=d["size"], color=d["color"], shape=d["shape"], pins=pins,
                         machine=m["zone"] == "machine")
    conns = {}
    for (ref, pin), (x, y, pname, net) in pins_mm.items():
        conns.setdefault(ref, {})[pin] = [round(x - 45, 2), round(y - 23, 2)]
    wires = []
    for r in ROUTES:
        for sg in r["segs"]:
            wires.append(dict(h=r["ref"], title=r["title"], a=[r["ref"], sg["pin"]], b=[r["mod"], sg["mpin"]],
                              kind=sg["kind"], net=sg["net"]))
    mains = [
        dict(h="M1", title="Сеть → БП", a="src:L", b=["psu", "L"], kind="L"),
        dict(h="M1", title="Сеть → БП", a="src:N", b=["psu", "N"], kind="N"),
        dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:L", b=["rd", "AC-IN L"], kind="L"),
        dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:N", b=["rd", "AC-IN N"], kind="N"),
        dict(h="M3", title="RobotDyn LOAD → помпа", a=["rd", "LOAD"], b=["pump", "L"], kind="load"),
        dict(h="M4", title="Сеть → SSR", a="src:L", b=["ssr", "L"], kind="L"),
        dict(h="M4", title="SSR → клапан", a=["ssr", "OUT"], b=["valve", "L"], kind="load"),
        dict(h="TC", title="Термопара K → бойлер", a=["max", "T+"], b=["boiler", "TC"], kind="tc"),
        dict(h="TC", title="Термопара K → бойлер", a=["max", "T−"], b=["boiler", "TC"], kind="tc"),
        dict(h="W", title="Вода: датчик → тройник помпа/OPV", a=["ps", "G1/4"], b=["pump", "L"], kind="water"),
        dict(h="S", title="Штатный выход помпы (∥, проверить)", a=["stock", "PUMP"], b=["pump", "L"], kind="stock"),
        dict(h="S", title="Штатный выход клапана (∥, проверить)", a=["stock", "VALVE"], b=["valve", "L"], kind="stock"),
    ]
    return dict(mods=mods, conns=conns, wires=wires, mains=mains, src=[-150, -10],
                jumpers=[["JP1", "1", "2"], ["JP3", "1", "2"]], labels=WIRE_LABEL)

def build():
    nwires = sum(len(r["segs"]) for r in ROUTES)
    tex = base64.b64encode((REPO / "hardware/carrier/previews/board-top.png").read_bytes()).decode()
    body = (TEMPLATE.read_text()
            .replace("%%SVG%%", svg())
            .replace("%%TABLES%%", tables())
            .replace("%%D3%%", json.dumps(d3data(), ensure_ascii=False))
            .replace("%%BOARD_TEX%%", "data:image/png;base64," + tex)
            .replace("%%VERSION%%", (REPO / "VERSION").read_text().strip())
            .replace("%%NH%%", str(len(ROUTES)))
            .replace("%%NW%%", str(nwires)))
    head, rest = body.split("</style>", 1)
    page = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head + "</style>\n</head>\n<body>" + rest + "</body>\n</html>\n")
    return page, body, nwires


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if docs/wiring.html differs from a fresh build")
    ap.add_argument("--fragment", type=Path, help="also write the page without the document wrapper")
    args = ap.parse_args()
    page, body, nwires = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != page:
            sys.exit("docs/wiring.html is out of date: run python tools/build_wiring_page.py")
        print("PASS wiring page matches connections.csv and the generator")
        return
    OUT.write_text(page)
    if args.fragment:
        args.fragment.write_text(body)
    print("written", OUT.relative_to(REPO), len(page), "bytes;", len(ROUTES), "harnesses,", nwires, "LV wires")


if __name__ == "__main__":
    main()
