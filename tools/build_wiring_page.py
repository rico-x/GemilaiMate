#!/usr/bin/env python3
"""Build the wiring pages: wiring scheme (SVG), 3D view and harness tables from one connection model.

docs/wiring.html covers carrier v0.1 (hardware/carrier/connections.csv). docs/shield-wiring.html covers the
shield (hardware/shield/connections.csv and design.json): ADS1115, TXS0102 and MAX31855 stand in sockets, only
cable harnesses leave the board. Modules, harness notes and the reference mains wiring are described below.
--check fails if a page is out of date; --fragment PATH also writes the carrier page without the document
wrapper (for publishing as an Artifact).
"""
import argparse, base64, csv, json, html, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "tools/wiring_template.html"
S = 6.0                                   # 2D: px per mm

esc = html.escape

def route(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

def read_pins(path):
    """Connector pins (J*, JP*) and DevKit socket pins (U1) in mm from connections.csv."""
    pins, u1 = {}, []
    for r in csv.DictReader(path.open()):
        if r["Reference"].startswith("J"):
            pins[(r["Reference"], r["Pin"])] = (float(r["x_mm"]), float(r["y_mm"]), r["Pin name"], r["Net"])
        elif r["Reference"] == "U1":
            u1.append((float(r["x_mm"]), float(r["y_mm"])))
    return pins, u1

WIRE_LABEL = {"5v": "+5 В", "3v3": "+3,3 В", "gnd": "GND", "data": "I²C / SPI", "analog": "давление (аналог)",
              "pump": "помпа: ZC / PSM", "valve": "клапан: управление", "btn": "кнопки", "L": "сеть L",
              "N": "сеть N", "load": "нагрузка (коммутируемая L)", "tc": "термопара K", "water": "вода", "ble": "BLE"}

MAINS_ROWS = [
    ("M1", "Сеть L → T2A → БП L; сеть N → БП N", "L, N", "AWG18; предохранитель T2A в держателе 5×20"),
    ("M2", "Сеть L, N → RobotDyn AC-IN", "L, N", "AWG18; N нужен диммеру для детектора нуля"),
    ("M3", "RobotDyn LOAD → переключатель, «GM» полюса помпы", "коммутируемая L", "AWG18"),
    ("M4", "Сеть L → SSR → переключатель, «GM» полюса клапана", "L, коммутируемая L", "AWG18; ток SSR ≤ 2 А"),
    ("M5", "Штатные выходы помпы и клапана → «штат» своих полюсов", "коммутируемая L",
     "AWG18; штатные разъёмы снять с помпы и клапана и надеть на переходники, провода не резать"),
    ("M6", "Общие выводы полюсов → помпа и катушка клапана Brew", "коммутируемая L", "AWG18; RC-снаббер параллельно катушке — по месту"),
    ("—", "PE, N помпы и клапана, нагрев, пар, термоблок", "—", "без изменений, штатная плата"),
]

# Mode switch: one E-TEN1322 toggle, two poles (ON-OFF-ON). Each pole: C to the load, «штат» to the stock output,
# «GM» to RobotDyn / SSR. The middle position disconnects pump and valve from both.
SWITCH_RULE = ("<b>Переключатель режима</b> E-TEN1322: 2 полюса ВКЛ-ВЫКЛ-ВКЛ, 15 А 250 В~, отверстие M12. «Штат» — помпа "
               "и клапан от штатной платы, «GM» — от RobotDyn и SSR, середина — отключены от обоих (первая проверка в машине "
               "без воды). Переключать без пролива. Положения подписать, винтовые клеммы закрыть.")

# =====================================================================================================
# carrier v0.1: all modules on harnesses
# =====================================================================================================
C_X0, C_Y0 = 430.0, 390.0                 # 2D: carrier origin
M_CARRIER = {
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
              pins={"L": (1240, 225)},
              d3=dict(c=(168, -86), size=(95, 40, 40), color="#2e3a2f", shape="pump")),
 "stock": dict(t="Штатная плата Gemilai", s="нагрев и пар — без изменений", box=(1090, 420, 190, 130), zone="machine",
               pins={"PUMP": (1160, 420), "VALVE": (1170, 550)},
               d3=dict(c=(168, 4), size=(80, 55, 2), color="#2f6d3a", shape="pcb")),
 "valve": dict(t="Клапан Brew (3WV)", s="катушка 230 В", box=(1090, 760, 150, 80), zone="machine",
               pins={"L": (1240, 800)},
               d3=dict(c=(162, 86), size=(30, 28, 38), color="#a7adb1", shape="valve")),
 "swp": dict(t="Режим", s="полюс помпы", box=(1290, 175, 95, 100), zone="mains",
             pins={"GM": (1338, 175), "C": (1290, 225), "штат": (1338, 275)},
             d3=dict(c=(212, -7), size=(16, 14, 14), color="#d9622b", shape="toggle", label="Переключатель режима")),
 "swv": dict(t="Режим", s="полюс клапана", box=(1290, 750, 95, 100), zone="mains",
             pins={"штат": (1338, 750), "C": (1290, 800), "GM": (1338, 850)},
             d3=dict(c=(212, 7), size=(16, 14, 14), color="#d9622b", shape="box", nolabel=True)),
 "boiler": dict(t="Бойлер", s="термопара в M3 сверху", box=(690, 905, 170, 75), zone="machine",
                pins={"TC": (755, 905)},
                d3=dict(c=(-112, 112), size=(56, 56, 42), color="#c4c8cb", shape="boiler")),
}

H_CARRIER = [
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

# mains / machine links (reference architecture)
L_BUS, N_BUS, L_COL = 60, 95, 1065
WATER = [(800, 200), (800, 178), (1140, 178)]

def carrier():
    rev = shield_revision()
    return dict(
        key="carrier", out=REPO / "docs/wiring.html", csv=REPO / "hardware/carrier/connections.csv",
        tex=REPO / "hardware/carrier/previews/board-top.png", size=(90, 46), x0=C_X0, y0=C_Y0, view=(1400, 1000),
        chan_top=(306, 384), chan_bot=(674, 728), M=M_CARRIER, H=H_CARRIER, onboard=[], col="Carrier",
        aria="Схема подключения GemilaiMate: carrier в центре, модули питания, помпы и датчика давления сверху, "
             "АЦП, термопара, кнопки и SSR клапана снизу, сетевая часть 230 вольт по верхнему краю и справа.",
        zone=['<path class="zone-mains" d="M10 20 H1390 V880 H1045 V170 H10 Z"/>',
              '<text class="zone-label" x="22" y="140">230 В · сетевая часть</text>',
              '<text class="zone-label" x="22" y="157">только на обесточенной машине</text>',
              '<text class="zone-label" x="1378" y="42" text-anchor="end">машина Gemilai 3007Z</text>',
              '<text class="zone-label lv" x="22" y="195">5 В / 3,3 В · низковольтная часть</text>'],
        mains=[
            dict(id="M1", t="L → предохранитель T2A → БП", kind="L", pts=[(320, L_BUS), (320, 160)], fuse=(320, 118)),
            dict(id="M1", t="N → БП", kind="N", pts=[(350, N_BUS), (350, 160)]),
            dict(id="M2", t="L → RobotDyn AC-IN", kind="L", pts=[(630, L_BUS), (630, 160)]),
            dict(id="M2", t="N → RobotDyn AC-IN", kind="N", pts=[(655, N_BUS), (655, 160)]),
            dict(id="M3", t="RobotDyn LOAD → переключатель, GM", kind="load", pts=[(715, 160), (715, 135), (1338, 135), (1338, 175)]),
            dict(id="M4", t="L → SSR", kind="L", pts=[(L_COL, L_BUS), (L_COL, 765), (1050, 765)]),
            dict(id="M4", t="SSR → переключатель, GM", kind="load", pts=[(1050, 800), (1070, 800), (1070, 868), (1338, 868), (1338, 850)]),
            dict(id="M6", t="переключатель → помпа", kind="load", pts=[(1290, 225), (1240, 225)]),
            dict(id="M6", t="переключатель → клапан", kind="load", pts=[(1290, 800), (1240, 800)]),
        ],
        bus=[dict(kind="L", pts=[(205, L_BUS), (L_COL, L_BUS)]), dict(kind="N", pts=[(205, N_BUS), (655, N_BUS)])],
        junctions=[(320, L_BUS), (630, L_BUS), (350, N_BUS), (L_COL, L_BUS)],
        stock=[dict(t="M5: штатный выход помпы → переключатель", pts=[(1160, 420), (1160, 330), (1338, 330), (1338, 275)]),
               dict(t="M5: штатный выход клапана → переключатель", pts=[(1170, 550), (1170, 640), (1338, 640), (1338, 750)])],
        decor=['<text class="note-lab" x="1168" y="385">штатный выход помпы</text>',
               '<text class="note-lab" x="1168" y="399">разъём снять с помпы</text>',
               '<text class="note-lab" x="1178" y="600">штатный выход клапана</text>',
               '<text class="note-lab" x="1178" y="614">разъём снять с клапана</text>',
               '<polyline class="mech" points="1375,275 1375,750"/>',
               '<text class="note-lab" transform="translate(1389,512) rotate(-90)" text-anchor="middle">один переключатель, два полюса</text>',
               f'<polyline class="w w-water" points="{route(WATER)}"/>',
               '<circle cx="1150" cy="178" r="10" class="tee"/><text class="note-lab" x="1166" y="182">тройник: помпа → OPV</text>',
               '<text class="note-lab" x="905" y="172">вода, G1/4</text>',
               '<polyline class="w w-tc" points="735,830 735,905"/><polyline class="w w-tc" points="775,830 775,905"/>',
               '<text class="note-lab" x="784" y="872">термопара K</text>'],
        devkit_dx=0, board_extra=[],
        titles=[(68.5, 31, "carrier v0.1"), (68.5, 33.6, "90 × 46 мм")],
        notes=['<text class="note-lab" x="1092" y="735">RC-снаббер параллельно</text>',
               '<text class="note-lab" x="1092" y="749">катушке — по месту</text>',
               '<text class="note-lab" x="1110" y="282">N помпы и клапана — штатные</text>'],
        d3_mains=[
            dict(h="M1", title="Сеть → БП", a="src:L", b=["psu", "L"], kind="L"),
            dict(h="M1", title="Сеть → БП", a="src:N", b=["psu", "N"], kind="N"),
            dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:L", b=["rd", "AC-IN L"], kind="L"),
            dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:N", b=["rd", "AC-IN N"], kind="N"),
            dict(h="M3", title="RobotDyn LOAD → переключатель, GM", a=["rd", "LOAD"], b=["swp", "GM"], kind="load"),
            dict(h="M4", title="Сеть → SSR", a="src:L", b=["ssr", "L"], kind="L"),
            dict(h="M4", title="SSR → переключатель, GM", a=["ssr", "OUT"], b=["swv", "GM"], kind="load"),
            dict(h="M6", title="Переключатель → помпа", a=["swp", "C"], b=["pump", "L"], kind="load"),
            dict(h="M6", title="Переключатель → клапан", a=["swv", "C"], b=["valve", "L"], kind="load"),
            dict(h="TC", title="Термопара K → бойлер", a=["max", "T+"], b=["boiler", "TC"], kind="tc"),
            dict(h="TC", title="Термопара K → бойлер", a=["max", "T−"], b=["boiler", "TC"], kind="tc"),
            dict(h="W", title="Вода: датчик → тройник помпа/OPV", a=["ps", "G1/4"], b=["pump", "L"], kind="water"),
            dict(h="M5", title="Штатный выход помпы → переключатель, штат", a=["stock", "PUMP"], b=["swp", "штат"], kind="stock"),
            dict(h="M5", title="Штатный выход клапана → переключатель, штат", a=["stock", "VALVE"], b=["swv", "штат"], kind="stock"),
        ],
        src=[-150, -10],
        board3d=dict(label="carrier v0.1 · ESP32-S3", labelPos=[-12, 24, 4], connLabelY=13, labelDx={},
                     views=dict(iso=[[-30, 230, 300], [10, 0, 8]], top=[[10, 470, 9], [10, 0, 8]]), ground=[520, 360, 15, 10]),
        texts=dict(
            TITLE="Подключение GemilaiMate", H1="Подключение GemilaiMate", STAMP="Прототип · не собран · сеть по референсу",
            LEAD="Жгуты carrier: цельный корпус J5 1×4 и J6 1×3 с гнездовыми контактами и красной меткой контакта 1. "
                 "Отдельные одноконтактные вилки не использовать. Корпуса без ключа: до питания проверить ориентацию "
                 "и прозвонить цепи. Корпус J6 shield 1×5 здесь не применяется.",
            NAV=f'<a href="shield-wiring.html">Второй вариант: shield v{rev} · 90×75 мм</a> · '
                '<a href="shield.html">рендеры и распиновка shield</a>',
            META="GemilaiMate v{version} · carrier v0.1 · Gemilai 3007Z · {nh} низковольтных жгутов, {nw} проводов",
            CAPTION="Каждый провод идёт от контакта разъёма carrier к выводу модуля в том порядке, как на модуле. "
                    "Перекрещенные пары в жгутах J2 и J8 — так и должно быть: порядок выводов на модулях отличается "
                    "от порядка на carrier. Сетевая часть заштрихована.",
            NOTE3D="Плата carrier, разъёмы и DevKit — в реальном масштабе. Модули и узлы машины — примерные габариты, "
                   "размещение условное: замеров Gemilai 3007Z нет.",
            RULES=[
                "<b>JP1 1–2</b> в рабочем режиме. Для USB-прошивки контроллера JP1 снять, внешние 5 В и USB не объединять.",
                "<b>JP3 1–2</b> — Vin модуля MAX31855 от 5 В. Вывод 3Vo никуда не подключать.",
                "<b>J10</b> не подключать: нагрев остаётся на штатной плате.",
                "<b>J8</b> — только независимые сухие контакты на GND. Штатную цепь кнопок не подключать, пока не выяснены её схема и изоляция.",
                "<b>J2</b>: порядок выводов ADS1115 другой. J2.5 → A0, J2.6 → ADDR; ALRT и A1–A3 свободны.",
                "<b>J7</b>: выводы TXS0102 подключать по маркировке модуля, а не по порядку на разъёме.",
                "<b>J9</b>: кабель USB-C только для питания дисплея. VBUS и GND определить прозвонкой, а не по цвету жил.",
                "<b>J5</b>: Z-C — логический сигнал 0–5 В. Z-C и PSM свить с GND и вести отдельно от сетевых проводов.",
                "<b>Термопара</b>: спай изолирован от корпуса (прозвонить), полярность T+ / T− по маркировке.",
                SWITCH_RULE,
                "<b>230 В</b>: только на обесточенной машине, с сохранением штатных защит и PE. Низковольтные жгуты не связывать с сетевыми.",
            ],
            SRC="Страница генерируется <code>tools/build_wiring_page.py</code> из hardware/carrier/connections.csv; "
                "пояснения — по docs/interfaces.md, docs/assembly.md и docs/bench.md. Сетевая часть — по переделке "
                "Turin Legato V2 (GaggiMate, обсуждение #222), с переключателем режима вместо параллельного подключения."),
    )

# =====================================================================================================
# shield: ADS1115 / TXS0102 / MAX31855 in sockets, six harnesses leave the board
# =====================================================================================================
SH = REPO / "hardware/shield"

def shield_design():
    return json.loads((SH / "design.json").read_text())

def shield_revision():
    return json.loads((SH / "revision.json").read_text())["revision"]

SSR_Y = [390 + y * S for y in (50.8, 55.88, 60.96)]     # J6 contacts 1/3/5: SSR inputs face them directly
M_SHIELD = {
 "psu": M_CARRIER["psu"] | dict(d3=dict(c=(-50, -90), size=(60, 36, 24), color="#d9dcd8", shape="box")),
 "disp": M_CARRIER["disp"] | dict(d3=dict(c=(5, -100), size=(62, 62, 9), color="#1d1f22", shape="disk")),
 "ps": dict(t="XDB401", s="0–1,6 МПа · 0,5–4,5 В", box=(450, 905, 100, 100), zone="lv",
            pins={"+5V": (470, 905), "GND": (495, 905), "OUT": (520, 905), "G1/4": (450, 990)},
            d3=dict(c=(-40, 85), size=(22, 55, 22), color="#b9c0c4", shape="sensor", flip=True)),
 "btn": dict(t="Кнопки", s="Brew · Steam", box=(565, 905, 92, 90), zone="lv",
             pins={"BREW": (577, 905), "COM1": (595, 905), "STEAM": (619, 905), "COM2": (637, 905)},
             d3=dict(c=(-8, 85), size=(26, 16, 6), color="#2a2d30", shape="buttons")),
 "rd": dict(t="RobotDyn 16A", s="диммер помпы", box=(662, 905, 140, 150), zone="straddle",
            pins={"VCC": (680, 905), "GND": (698, 905), "Z-C": (716, 905), "PSM": (734, 905),
                  "AC-IN N": (662, 1020), "AC-IN L": (662, 1040), "LOAD": (802, 1040)},
            d3=dict(c=(22, 112), size=(52, 72, 22), color="#1f5fa8", shape="dimmer", flip=True)),
 "ssr": dict(t="SSR клапана", s="G3MB · High 5V", box=(990, 670, 155, 120), zone="straddle",
             pins={"DC+": (990, SSR_Y[0]), "DC−": (990, SSR_Y[1]), "CH1": (990, SSR_Y[2]), "L": (1145, 700), "OUT": (1145, 760)},
             d3=dict(c=(85, 18), size=(26, 34, 18), color="#1f5fa8", shape="ssr")),
 "boiler": dict(t="Бойлер", s="термопара в M3 сверху", box=(815, 905, 140, 75), zone="machine",
                pins={"TC": (885, 905)},
                d3=dict(c=(80, 100), size=(56, 56, 42), color="#c4c8cb", shape="boiler")),
 "stock": dict(t="Штатная плата Gemilai", s="нагрев · пар · термоблок", box=(1185, 400, 200, 130), zone="machine",
               pins={"PUMP": (1378, 530), "VALVE": (1335, 530)},
               d3=dict(c=(170, -40), size=(80, 55, 2), color="#2f6d3a", shape="pcb")),
 "valve": dict(t="Клапан Brew", s="катушка 230 В", box=(1185, 715, 100, 80), zone="machine",
               pins={"L": (1285, 755)},
               d3=dict(c=(160, 40), size=(30, 28, 38), color="#a7adb1", shape="valve")),
 "swv": dict(t="Режим", s="клапан", box=(1295, 705, 73, 100), zone="mains",
             pins={"штат": (1335, 705), "C": (1295, 755), "GM": (1335, 805)},
             d3=dict(c=(212, 50), size=(16, 14, 14), color="#d9622b", shape="toggle", label="Переключатель режима")),
 "swp": dict(t="Режим", s="помпа", box=(1295, 885, 73, 100), zone="mains",
             pins={"штат": (1368, 900), "GM": (1295, 960), "C": (1335, 985)},
             d3=dict(c=(212, 64), size=(16, 14, 14), color="#d9622b", shape="box", nolabel=True)),
 "pump": dict(t="Помпа", s="вибрационная", box=(1185, 1005, 195, 70), zone="machine",
              pins={"L": (1335, 1005)},
              d3=dict(c=(165, 115), size=(95, 40, 40), color="#2e3a2f", shape="pump")),
}

H_SHIELD = [
 ("J1", "Питание 5 В", "psu", [("1", "+V", "5v", "+5V"), ("2", "−V", "gnd", "GND")],
  "AWG22 и короче; внешний БП на стенде, ограничение тока при первом включении. Жгут выходит вверх."),
 ("J9", "Питание дисплея", "disp", [("1", "VBUS", "5v", "+5V"), ("2", "GND", "gnd", "GND")],
  "Кабель USB-C только для питания. Жилы VBUS/GND прозвонить, на PA/Grove 5 В не подавать."),
 ("J4", "Датчик давления", "ps", [("1", "+5V", "5v", "+5V"), ("2", "GND", "gnd", "GND"), ("3", "OUT", "analog", "PRESSURE_RAW")],
  "Цвета жил датчика — по его паспорту, прозвонить до подключения. Жгут выходит вниз; J4 сдвинут вправо от крепёжного отверстия."),
 ("J8", "Кнопки", "btn", [("1", "BREW", "btn", "BREW_CONTACT"), ("3", "COM1", "gnd", "GND"), ("2", "STEAM", "btn", "STEAM_CONTACT"), ("4", "COM2", "gnd", "GND")],
  "Только независимые сухие контакты на GND. Штатную цепь кнопок не подключать, пока её схема и изоляция не проверены."),
 ("J5", "Диммер помпы", "rd", [("1", "VCC", "5v", "+5V"), ("2", "GND", "gnd", "GND"), ("3", "Z-C", "pump", "ZC_RAW"), ("4", "PSM", "pump", "PUMP_PWM")],
  "Цельный корпус DuPont 1×4, штыревые контакты, красная метка контакта 1 к квадратной площадке. Ключа нет: ориентацию "
  "проверить до питания. Z-C и PSM свить с GND, вести отдельно от сетевых проводов. RobotDyn — на своей опоре, не над платой."),
 ("J6", "SSR клапана", "ssr", [("1", "DC+", "5v", "+5V"), ("3", "DC−", "gnd", "GND"), ("5", "CH1", "valve", "VALVE_IN")],
  "Цельный корпус DuPont 1×5: контакты только в позициях 1, 3, 5, позиции 2 и 4 пустые; красная метка контакта 1. "
  "Провода — к штатной винтовой клемме SSR, без перепайки. Ток входа SSR измерить на стенде."),
]

# Modules standing in shield sockets; outline/height come from design.json, colours match the carrier page.
ONBOARD = [
 dict(id="ads", ref="J2", t="ADS1115", s="АЦП давления · 0x48", color="#1f5fa8",
      note="Модуль ставится в гнездо J2, VDD — у квадратной площадки слева. ADDR на GND, адрес 0x48, давление на A0; ALRT и A1–A3 не подключены."),
 dict(id="txs", ref="J7", t="TXS0102", s="уровни I²C 3,3↔5 В", color="#5b3f9e",
      note="Две отдельные гребёнки 1×5, межрядье 12,70 мм — допущение до замера. Ряд A (3,3 В) — у метки «A 3V3» и квадратной "
           "площадки, ряд B (5 В) — у «B 5V». Поворот на 180° подаёт 5 В на VCCA. G не подключён."),
 dict(id="max", ref="J3", t="MAX31855", s="термопара K", color="#9e2a3a",
      tc=[("T+", 66.08, 68.2), ("T−", 71.08, 68.2)], terminal=(64.08, 65.6, 73.08, 70.36),
      note="VIN — контакт 1 справа, подпись читается «CLK ... VIN». 3Vo — выход, не подключать. JP3 1–2 только после проверки "
           "VIN 5 В и уровней DO. Термопара — к клеммам модуля, кабель вниз."),
]

def devkit_dx(path):
    """DevKit socket centre in mm; the 2D DevKit drawing is laid out for the carrier position."""
    xs = [x for x, _ in read_pins(path)[1]]
    return round((min(xs) + max(xs)) / 2, 2)

def shield():
    d = shield_design(); rev = shield_revision()
    parts = {c["ref"]: c for c in d["parts"]}
    occ = {o["id"]: o["bbox_mm"] for o in d["mechanical_profiles"]["occupied"]}
    W, Hh = d["size_mm"]; cx, cz = W / 2, Hh / 2
    X0, Y0 = C_X0, C_Y0
    onboard = []
    for o in ONBOARD:
        a, b, c, e = parts[o["ref"]]["rect"]
        onboard.append(o | dict(rect=(a, b, c, e), top=occ[o["ref"] + "-module"][5]))
    plugs, wire_y = [], {}
    for ref in ["J1", "J9", "J4", "J8", "J5", "J6"]:
        a, b, c, e = parts[ref]["rect"]; z0, z1 = occ[ref + "-mated-plug"][2], occ[ref + "-mated-plug"][5]
        pin1 = next(p for p in parts[ref]["pins"] if p["number"] == "1")
        plugs.append(dict(box=[round(a - cx, 2), round(b - cz, 2), round(c - cx, 2), round(e - cz, 2)], y0=z0, y1=z1,
                          pin1=[round(pin1["x"] - cx, 2), round(pin1["y"] - cz, 2)] if ref in ("J5", "J6") else None))
        wire_y[ref] = round(1.6 + z1 + 0.3, 2)
    ka, kb, kc, ke = d["mechanical_access"][0]["rect_mm"]
    tc = next(o for o in onboard if o["id"] == "max")["tc"]
    tcx = [X0 + x * S for _, x, _ in tc]; tcy = Y0 + tc[0][2] * S
    extra = []
    for o in onboard:
        a, b, c, e = o["rect"]; mx, my = X0 + (a + c) / 2 * S, Y0 + (b + e) / 2 * S
        extra.append(f'<rect x="{X0 + a * S:.1f}" y="{Y0 + b * S:.1f}" width="{(c - a) * S:.1f}" height="{(e - b) * S:.1f}" rx="2" class="devkit"/>'
                     f'<text class="dev-title" x="{mx:.1f}" y="{my:.1f}" text-anchor="middle">{esc(o["t"])}</text>'
                     f'<text class="dev-sub" x="{mx:.1f}" y="{my + 15:.1f}" text-anchor="middle">в гнезде {o["ref"]}</text>')
    for (name, x, y), px in zip(tc, tcx):
        extra.append(f'<circle cx="{px:.1f}" cy="{tcy:.1f}" r="3.4" class="mpin"/>'
                     f'<text class="dev-sub" x="{px:.1f}" y="{tcy - 8:.1f}" text-anchor="middle">{name}</text>')
    extra.append(f'<rect x="{X0 + ka * S:.1f}" y="{Y0 + kb * S:.1f}" width="{(kc - ka) * S:.1f}" height="{(ke - kb) * S:.1f}" class="keep"/>'
                 f'<text class="keep-lab" x="{X0 + ka * S + 8:.1f}" y="{Y0 + kb * S + 18:.1f}">доступ к USB</text>'
                 f'<text class="keep-lab" x="{X0 + ka * S + 8:.1f}" y="{Y0 + kb * S + 33:.1f}">не занимать</text>')
    bottom = Y0 + Hh * S
    return dict(
        key="shield", out=REPO / "docs/shield-wiring.html", csv=SH / "connections.csv",
        tex=SH / "previews/board-top.png", size=(W, Hh), x0=X0, y0=Y0, view=(1400, 1100),
        chan_top=(306, 384), chan_bot=(bottom + 8, bottom + 58), M=M_SHIELD, H=H_SHIELD, onboard=onboard, col="Shield",
        aria="Схема подключения shield GemilaiMate: shield в центре с АЦП, преобразователем уровней и модулем термопары "
             "в гнёздах; блок питания и дисплей сверху, датчик давления, кнопки, диммер и бойлер снизу, SSR справа; "
             "сетевая часть 230 вольт по краям.",
        zone=['<path class="zone-mains" fill-rule="evenodd" d="M10 20 H1390 V1095 H10 Z M250 170 V1012 H1075 V170 Z"/>',
              '<text class="zone-label" x="22" y="1072">230 В · сетевая часть</text>',
              '<text class="zone-label" x="22" y="1089">только на обесточенной машине</text>',
              '<text class="zone-label" x="1378" y="42" text-anchor="end">машина Gemilai 3007Z</text>',
              '<text class="zone-label lv" x="700" y="195">5 В / 3,3 В · низковольтная часть</text>'],
        mains=[
            dict(id="M1", t="L → предохранитель T2A → БП", kind="L", pts=[(320, L_BUS), (320, 160)], fuse=(320, 118)),
            dict(id="M1", t="N → БП", kind="N", pts=[(350, N_BUS), (350, 160)]),
            dict(id="M2", t="N → RobotDyn AC-IN", kind="N", pts=[(150, 118), (150, 1020), (662, 1020)]),
            dict(id="M2", t="L → RobotDyn AC-IN", kind="L", pts=[(120, 118), (120, 1040), (662, 1040)]),
            dict(id="M3", t="RobotDyn LOAD → переключатель, GM", kind="load", pts=[(802, 1040), (1150, 1040), (1150, 960), (1295, 960)]),
            dict(id="M4", t="L → SSR", kind="L", pts=[(1160, L_BUS), (1160, 700), (1145, 700)]),
            dict(id="M4", t="SSR → переключатель, GM", kind="load", pts=[(1145, 760), (1170, 760), (1170, 825), (1335, 825), (1335, 805)]),
            dict(id="M6", t="переключатель → клапан", kind="load", pts=[(1295, 755), (1285, 755)]),
            dict(id="M6", t="переключатель → помпа", kind="load", pts=[(1335, 985), (1335, 1005)]),
        ],
        bus=[dict(kind="L", pts=[(205, L_BUS), (1160, L_BUS)]), dict(kind="N", pts=[(205, N_BUS), (350, N_BUS)])],
        junctions=[(320, L_BUS), (1160, L_BUS)],
        stock=[dict(t="M5: штатный выход клапана → переключатель", pts=[(1335, 530), (1335, 705)]),
               dict(t="M5: штатный выход помпы → переключатель", pts=[(1378, 530), (1378, 900), (1368, 900)])],
        decor=['<text class="note-lab" x="1327" y="600" text-anchor="end">штатный выход клапана</text>',
               '<text class="note-lab" x="1327" y="614" text-anchor="end">разъём снять с клапана</text>',
               '<text class="note-lab" transform="translate(1374,617) rotate(-90)" text-anchor="middle">штатный выход помпы</text>',
               '<polyline class="mech" points="1355,805 1355,885"/>',
               '<text class="note-lab" x="1349" y="849" text-anchor="end">один переключатель</text>',
               '<text class="bus-label L" x="104" y="140">L</text><text class="bus-label N" x="156" y="140">N</text>',
               f'<polyline class="w w-water" points="{route([(450, 990), (426, 990)])}"/>',
               '<text class="note-lab" x="420" y="994" text-anchor="end">вода G1/4 → тройник помпа/OPV</text>',
               f'<polyline class="w w-tc" points="{route([(tcx[0], tcy), (tcx[0], 905)])}"/>'
               f'<polyline class="w w-tc" points="{route([(tcx[1], tcy), (tcx[1], 905)])}"/>',
               f'<text class="note-lab" x="{tcx[1] + 9:.1f}" y="872">термопара K</text>'],
        devkit_dx=devkit_dx(SH / "connections.csv") - devkit_dx(REPO / "hardware/carrier/connections.csv"), board_extra=extra,
        titles=[(68.5, 31, f"shield v{rev}"), (68.5, 33.6, f"{W} × {Hh} мм")],
        notes=['<text class="note-lab" x="1185" y="690">RC-снаббер параллельно</text>',
               '<text class="note-lab" x="1185" y="704">катушке — по месту</text>',
               '<text class="note-lab" x="1185" y="1092">N помпы и клапана — штатные</text>'],
        d3_mains=[
            dict(h="M1", title="Сеть → БП", a="src:L", b=["psu", "L"], kind="L"),
            dict(h="M1", title="Сеть → БП", a="src:N", b=["psu", "N"], kind="N"),
            dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:L", b=["rd", "AC-IN L"], kind="L", via=[[-150, 150]]),
            dict(h="M2", title="Сеть → RobotDyn AC-IN", a="src:N", b=["rd", "AC-IN N"], kind="N", via=[[-143, 143]]),
            dict(h="M3", title="RobotDyn LOAD → переключатель, GM", a=["rd", "LOAD"], b=["swp", "GM"], kind="load"),
            dict(h="M4", title="Сеть → SSR", a="src:L", b=["ssr", "L"], kind="L", via=[[-140, -150], [125, -150], [125, 0]]),
            dict(h="M4", title="SSR → переключатель, GM", a=["ssr", "OUT"], b=["swv", "GM"], kind="load"),
            dict(h="M6", title="Переключатель → клапан", a=["swv", "C"], b=["valve", "L"], kind="load"),
            dict(h="M6", title="Переключатель → помпа", a=["swp", "C"], b=["pump", "L"], kind="load"),
            dict(h="TC", title="Термопара K → бойлер", a=["max", "T+"], b=["boiler", "TC"], kind="tc"),
            dict(h="TC", title="Термопара K → бойлер", a=["max", "T−"], b=["boiler", "TC"], kind="tc"),
            dict(h="W", title="Вода: датчик → тройник помпа/OPV", a=["ps", "G1/4"], b=["pump", "L"], kind="water", via=[[-60, 168], [110, 168]]),
            dict(h="M5", title="Штатный выход клапана → переключатель, штат", a=["stock", "VALVE"], b=["swv", "штат"], kind="stock"),
            dict(h="M5", title="Штатный выход помпы → переключатель, штат", a=["stock", "PUMP"], b=["swp", "штат"], kind="stock"),
        ],
        src=[-140, -60],
        board3d=dict(label=f"shield v{rev} · ESP32-S3", labelPos=[-5, 27, -17], connLabelY=25, labelDx={"J6": 7},
                     views=dict(iso=[[-20, 280, 345], [35, 0, 12]], top=[[25, 520, 21], [25, 0, 20]]), ground=[440, 380, 30, 10],
                     sockets=["J2", "J3", "J7", "J5", "J6"], socketH=8.5, plugs=plugs, wireY=wire_y,
                     mounts=[[x - cx, y - cz] for x, y in d["mounts_mm"]],
                     headD=d["mechanical_profiles"]["fasteners"]["head_diameter_max_mm"],
                     keep=[dict(box=[ka - cx, kb - cz, kc - cx, ke - cz], h=14, t="USB · не занимать")]),
        texts=dict(
            TITLE="Подключение shield GemilaiMate", H1="Подключение shield",
            STAMP="Прототип · не собран · модули не замерены",
            LEAD="ADS1115, TXS0102 и MAX31855 стоят в гнёздах shield и соединены с платой без проводов. Наружу идут шесть "
                 "жгутов: J1, J9 вверх, J4, J8, J5 вниз, J6 вправо. J5 — цельный корпус 1×4, J6 — 1×5 с контактами "
                 "1/3/5, оба со штыревыми контактами и красной меткой контакта 1. RobotDyn и SSR крепятся отдельно, "
                 "не над платой.",
            NAV='<a href="wiring.html">Первый вариант: carrier v0.1 · 90×46 мм</a> · '
                '<a href="shield.html">рендеры, маркировка и шаблон 1:1 shield</a>',
            META=f"GemilaiMate v{{version}} · shield v{rev} · Gemilai 3007Z · {{nh}} низковольтных жгутов, {{nw}} проводов · "
                 f"3 модуля в гнёздах",
            CAPTION="ADS1115, TXS0102 и MAX31855 вставлены в гнёзда J2, J7 и J3 — проводов к ним нет. Каждый провод жгута "
                    "идёт от контакта разъёма shield к выводу модуля. Перекрещенная пара в J8 — так и должно быть: порядок "
                    "выводов на кнопках отличается от порядка на разъёме. Сетевая часть заштрихована, зелёный пунктир — "
                    "зона доступа к USB.",
            NOTE3D="Плата shield, гнёзда, DevKit, модули в гнёздах, ответные колодки и головки M3 — номинальные размеры из "
                   "design.json, реальные клоны и колодки не замерены. Прозрачный объём слева — доступ к USB. Внешние "
                   "модули и узлы машины — примерные габариты, размещение условное: замеров Gemilai 3007Z нет.",
            RULES=[
                "<b>JP1 1–2</b> в рабочем режиме. Для USB-прошивки контроллера JP1 снять, внешние 5 В и USB не объединять.",
                "<b>JP3 1–2</b> — VIN MAX31855 от 5 В, только после проверки уровней DO. Вывод 3Vo никуда не подключать.",
                "<b>J10</b> не подключать: нагрев остаётся на штатной плате.",
                "<b>Модули в гнёздах</b> — по квадратной площадке 1 и меткам. До установки измерить питание на пустых гнёздах; "
                "TXS, ADS, MAX ставить по одному, ESP32 последним.",
                "<b>J7</b>: ряд A (3,3 В) у метки «A 3V3», ряд B (5 В) у «B 5V». Поворот на 180° подаёт +5 В на VCCA.",
                "<b>J3</b>: VIN — контакт 1 справа, подпись читается «CLK ... VIN».",
                "<b>J5 / J6</b>: цельные корпуса с красной меткой контакта 1, у J6 позиции 2 и 4 пустые. Ключа нет — "
                "ориентацию сверить с квадратной площадкой.",
                "<b>J8</b> — только независимые сухие контакты на GND. Штатную цепь кнопок не подключать, пока не выяснены её схема и изоляция.",
                "<b>J9</b>: кабель USB-C только для питания дисплея. VBUS и GND определить прозвонкой, а не по цвету жил.",
                "<b>USB</b>: слева от ESP32 держать свободным коридор −30…4,8 мм для штекеров обоих портов.",
                "<b>Крепёж</b>: четыре M3 с головкой ≤ 5,5 мм, без шайб; модули — прижимами по docs/retention.md.",
                SWITCH_RULE,
                "<b>230 В</b>: только на обесточенной машине. RobotDyn и SSR — на собственных опорах, не над платой; "
                "низковольтные жгуты не связывать с сетевыми.",
            ],
            SRC="Страница генерируется <code>tools/build_wiring_page.py</code> из hardware/shield/connections.csv и "
                "design.json; пояснения — по docs/shield.md, docs/harnesses.md и docs/retention.md. Сетевая часть — по "
                "переделке Turin Legato V2 (GaggiMate, обсуждение #222), с переключателем режима вместо параллельного подключения."),
    )

# =====================================================================================================
# shared generator
# =====================================================================================================
def lv_routes(v):
    """Orthogonal routes per harness that avoid self-crossings where the pin order allows."""
    out = []
    right = v["x0"] + v["size"][0] * S
    for ref, title, mod, wires, note in v["H"]:
        rows = []
        for pin, mpin, kind, net in wires:
            x, y, *_ = v["pins"][(ref, pin)]
            cx, cy = v["x0"] + x * S, v["y0"] + y * S
            mx, my = v["M"][mod]["pins"][mpin]
            rows.append((cx, cy, mx, my, pin, mpin, kind, net))
        segs = []
        if rows[0][2] > right:                      # module beside the right edge: run straight out
            for i, (cx, cy, mx, my, pin, mpin, kind, net) in enumerate(sorted(rows, key=lambda r: r[1])):
                xm = right + 8 + i * 5
                pts = [(cx, cy), (mx, cy)] if abs(cy - my) < 0.5 else [(cx, cy), (xm, cy), (xm, my), (mx, my)]
                segs.append(dict(pin=pin, mpin=mpin, kind=kind, net=net, pts=pts))
            out.append(dict(ref=ref, title=title, mod=mod, note=note, segs=segs))
            continue
        top = rows[0][3] < v["y0"]                   # module above the board
        rows.sort(key=lambda r: r[0])
        shift = sum(r[2] - r[0] for r in rows)
        n = len(rows)
        lo, hi = v["chan_top"] if top else v["chan_bot"]
        gap = min(7.0, (hi - lo) / max(n, 1))
        for i, (cx, cy, mx, my, pin, mpin, kind, net) in enumerate(rows):
            k = (n - 1 - i) if shift > 0 else i
            ym = lo + 4 + k * gap
            if top:   # module pin (above) -> board pin (below)
                pts = [(mx, my), (mx, ym), (cx, ym), (cx, cy)]
            else:     # board pin (above) -> module pin (below)
                pts = [(cx, cy), (cx, ym), (mx, ym), (mx, my)]
            segs.append(dict(pin=pin, mpin=mpin, kind=kind, net=net, pts=pts))
        out.append(dict(ref=ref, title=title, mod=mod, note=note, segs=segs))
    return out

def pin_rows(pts):
    """Split a two-row breakout socket into its rows; single-row connectors stay whole."""
    ys = sorted({p[1] for p in pts}); xs = {p[0] for p in pts}
    return [[p for p in pts if p[1] == y] for y in ys] if len(ys) > 1 and len(xs) > 1 else [pts]

# ---------- SVG ----------
def svg(v):
    X0, Y0, (W, Hh), M = v["x0"], v["y0"], v["size"], v["M"]
    dx = v["devkit_dx"]
    o = []
    a = o.append
    a(f'<svg viewBox="0 0 {v["view"][0]} {v["view"][1]}" role="img" aria-label="{v["aria"]}" class="scheme">')
    a('<defs><pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      '<line x1="0" y1="0" x2="0" y2="10" class="hatch-line"/></pattern>'
      '<marker id="dot" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5">'
      '<circle cx="3" cy="3" r="2.6" class="end-dot"/></marker></defs>')
    # zones
    for z in v["zone"]:
        a(z)
    # mains source
    a('<g class="mains-src"><rect x="20" y="38" width="176" height="80" rx="4" class="box machine"/>'
      '<text class="m-title" x="32" y="60">Сеть 230 В</text>'
      '<text class="m-sub" x="32" y="78">после выключателя</text><text class="m-sub" x="32" y="93">и защиты машины</text>'
      '<text class="m-sub" x="32" y="108">PE — корпус, без изменений</text></g>')
    a(f'<text class="bus-label L" x="208" y="{L_BUS - 6}">L</text><text class="bus-label N" x="208" y="{N_BUS - 6}">N</text>')
    for b in v["bus"]:
        a(f'<polyline class="w w-{b["kind"]} bus" points="{route(b["pts"])}"/>')
    for mw in v["mains"]:
        a(f'<polyline class="w w-{mw["kind"]} mains" points="{route(mw["pts"])}"><title>{esc(mw["id"])}: {esc(mw["t"])}</title></polyline>')
        if "fuse" in mw:
            fx, fy = mw["fuse"]
            a(f'<rect x="{fx - 9}" y="{fy - 13}" width="18" height="26" rx="2" class="fuse"/>'
              f'<text class="pin-lab" x="{fx + 14}" y="{fy + 4}">T2A</text>')
    for x, y in v["junctions"]:
        a(f'<circle cx="{x}" cy="{y}" r="3.6" class="junction"/>')
    # stock outputs (dashed, to verify)
    for s in v["stock"]:
        a(f'<polyline class="w stock" points="{route(s["pts"])}"><title>{esc(s["t"])}</title></polyline>')
    # water, thermocouple and other notes of this layout
    for d in v["decor"]:
        a(d)
    # board with DevKit and modules standing in sockets
    a(f'<g class="carrier"><rect x="{X0}" y="{Y0}" width="{W * S}" height="{Hh * S}" rx="6" class="pcb"/>')
    a(f'<rect x="{X0 + (3.5 + dx) * S}" y="{Y0 + 7.6 * S}" width="{62.8 * S}" height="{28 * S}" rx="3" class="devkit"/>')
    a(f'<rect x="{X0 + (47.9 + dx) * S}" y="{Y0 + 12.0 * S}" width="{18.4 * S}" height="{19.2 * S}" rx="2" class="wroom"/>')
    a(f'<text class="dev-title" x="{X0 + (9 + dx) * S}" y="{Y0 + 19 * S}">ESP32-S3 DevKit N8R8 · контроллер</text>')
    a(f'<text class="dev-sub" x="{X0 + (9 + dx) * S}" y="{Y0 + 22.6 * S}">в гнёздах, ряд A · USB слева</text>')
    a(f'<text class="dev-sub" x="{X0 + (50 + dx) * S}" y="{Y0 + 33.5 * S}">антенна</text>')
    for e in v["board_extra"]:
        a(e)
    a("".join(f'<text class="pcb-title" x="{X0 + x * S}" y="{Y0 + y * S}">{t}</text>' for x, y, t in v["titles"]) + '</g>')
    # connectors
    onboard = {ob["ref"] for ob in v["onboard"]}
    groups = {}
    for (ref, pin), (x, y, pname, net) in v["pins"].items():
        groups.setdefault(ref, []).append((x, y))
    for ref, pts in sorted(groups.items()):
        boxes = []
        for row in pin_rows(pts):
            xs = [X0 + p[0] * S for p in row]; ys = [Y0 + p[1] * S for p in row]
            x0, x1, y0, y1 = min(xs) - 7, max(xs) + 7, min(ys) - 7, max(ys) + 7
            a(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="2" class="conn"/>')
            for x, y in zip(xs, ys):
                a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.1" class="pin"/>')
            boxes.append((x0, x1, y0, y1, ys[0]))
        x0, x1, y0, y1, yf = boxes[0]
        top = yf < Y0 + 20 * S
        if ref in onboard:    # the module drawn over the socket already names it
            continue
        if ref == "J10":
            a(f'<text class="conn-lab" x="{x0 - 6:.1f}" y="{y0 + 11:.1f}" text-anchor="end">J10</text>'
              f'<text class="pcb-note" x="{x0 - 6:.1f}" y="{y0 + 25:.1f}" text-anchor="end">не подключать</text>')
        elif top:
            a(f'<text class="conn-lab" x="{(x0 + x1) / 2:.1f}" y="{y1 + 15:.1f}" text-anchor="middle">{ref}{" 1–2" if ref.startswith("JP") else ""}</text>')
        else:
            a(f'<text class="conn-lab" x="{(x0 + x1) / 2:.1f}" y="{y0 - 6:.1f}" text-anchor="middle">{ref}</text>')
    for ref, lab in (("JP1", "JP1 1–2"), ("JP3", "JP3 1–2")):
        x1, y1, *_ = v["pins"][(ref, "1")]; x2, *_ = v["pins"][(ref, "2")]
        x1, y1, x2 = X0 + x1 * S, Y0 + y1 * S, X0 + x2 * S
        a(f'<rect x="{x1 - 7:.1f}" y="{y1 - 7:.1f}" width="{x2 - x1 + 14:.1f}" height="14" rx="2" class="jumper"/>')
    # harness wires
    for r in v["routes"]:
        a(f'<g class="harness" data-h="{r["ref"]}" tabindex="0"><title>{r["ref"]} — {esc(r["title"])}</title>')
        for sg in r["segs"]:
            a(f'<polyline class="w w-{sg["kind"]}" points="{route(sg["pts"])}"/>')
        a('</g>')
    # modules
    for mid, m in M.items():
        cls = {"lv": "box", "straddle": "box", "mains": "box", "machine": "box machine"}[m["zone"]]
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
        tx = x + w / 2 - (14 if mid == "ssr" and v["key"] == "carrier" else 0)
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
            elif side_bot and y < Y0:
                a(f'<text class="pin-lab" transform="translate({px - 3.5},{py - 8}) rotate(-90)">{esc(lab)}</text>')
            elif side_bot:
                a(f'<text class="pin-lab" x="{px}" y="{py - 8}" text-anchor="middle">{esc(lab)}</text>')
            elif side_r:
                a(f'<text class="pin-lab" x="{px - 6}" y="{py + 4}" text-anchor="end">{esc(lab)}</text>')
            elif side_l:
                a(f'<text class="pin-lab" x="{px + 6}" y="{py + 4}">{esc(lab)}</text>')
        a('</g>')
    for n in v["notes"]:
        a(n)
    a('</svg>')
    return "".join(o)

# ---------- harness tables ----------
def tables(v):
    o = []
    for r in v["routes"]:
        m = v["M"][r["mod"]]
        o.append(f'<section class="hcard" id="h-{r["ref"]}"><header><span class="ref">{r["ref"]}</span>'
                 f'<h3>{esc(r["title"])}</h3><span class="to">→ {esc(m["t"])}</span></header>'
                 f'<div class="tbl"><table><thead><tr><th>{v["col"]}</th><th>Цепь</th><th>Модуль</th><th>Провод</th></tr></thead><tbody>')
        for sg in sorted(r["segs"], key=lambda s: int(s["pin"])):
            o.append(f'<tr><td class="mono">{r["ref"]}.{sg["pin"]}</td><td class="mono">{esc(sg["net"])}</td>'
                     f'<td class="mono">{esc(sg["mpin"])}</td><td><span class="sw sw-{sg["kind"]}"></span>{esc(WIRE_LABEL[sg["kind"]])}</td></tr>')
        o.append(f'</tbody></table></div><p class="hnote">{esc(r["note"])}</p></section>')
    for ob in v["onboard"]:
        pins = sorted(((int(p), name, net) for (ref, p), (x, y, name, net) in v["pins"].items() if ref == ob["ref"]))
        o.append(f'<section class="hcard" id="h-{ob["ref"]}"><header><span class="ref">{ob["ref"]}</span>'
                 f'<h3>{esc(ob["t"])} в гнезде</h3><span class="to">без проводов · {esc(ob["s"])}</span></header>'
                 f'<div class="tbl"><table><thead><tr><th>{v["col"]}</th><th>Вывод модуля</th><th>Цепь</th></tr></thead><tbody>')
        for p, name, net in pins:
            o.append(f'<tr><td class="mono">{ob["ref"]}.{p}</td><td class="mono">{esc(name)}</td>'
                     f'<td class="mono">{esc(net) if net != "NC" else "не подключён"}</td></tr>')
        o.append(f'</tbody></table></div><p class="hnote">{esc(ob["note"])}</p></section>')
    o.append('<section class="hcard mains-card" id="h-mains"><header><span class="ref haz">230 В</span><h3>Сетевая часть</h3>'
             '<span class="to">по референсной переделке</span></header><div class="tbl"><table><thead><tr><th>№</th><th>Соединение</th><th>Провод</th><th>Примечание</th></tr></thead><tbody>')
    for a_, b, c, d in MAINS_ROWS:
        o.append(f'<tr><td class="mono">{a_}</td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>')
    o.append('</tbody></table></div><p class="hnote">Питание и диммер — по переделке Turin Legato V2 из обсуждения GaggiMate #222. '
             'Вместо параллельного подключения к штатным выходам помпа и клапан идут через переключатель режима E-TEN1322: '
             'одновременно управлять ими штатная плата и GemilaiMate не могут. Для Gemilai 3007Z клеммы, защиту и поведение '
             'штатных выходов нужно проверить по конкретной машине. Все работы — на обесточенной машине.</p></section>')
    return "".join(o)

# ---------- 3D data ----------
def d3data(v):
    W, Hh = v["size"]; cx0, cz0 = W / 2, Hh / 2
    mods = {}
    for mid, m in v["M"].items():
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
        mods[mid] = dict(t=d.get("label", m["t"]), s=m["s"], c=d["c"], size=d["size"], color=d["color"], shape=d["shape"],
                         pins=pins, machine=m["zone"] in ("machine", "mains"))
        for flag in ("flip", "nolabel"):
            if d.get(flag):
                mods[mid][flag] = True
    for ob in v["onboard"]:
        a, b, c, e = ob["rect"]
        mod = dict(t=ob["t"], s=ob["s"], c=[round((a + c) / 2 - cx0, 2), round((b + e) / 2 - cz0, 2)],
                   size=[round(c - a, 2), round(e - b, 2), round(1.6 + ob["top"], 2)], color=ob["color"], shape="onboard",
                   ref=ob["ref"], rect=[round(a - cx0, 2), round(b - cz0, 2), round(c - cx0, 2), round(e - cz0, 2)],
                   pins={n: [round(x - cx0, 2), round(1.6 + ob["top"], 2), round(y - cz0, 2)] for n, x, y in ob.get("tc", [])}, machine=False)
        if "terminal" in ob:
            t0, u0, t1, u1 = ob["terminal"]
            mod["terminal"] = [round(t0 - cx0, 2), round(u0 - cz0, 2), round(t1 - cx0, 2), round(u1 - cz0, 2)]
        mods[ob["id"]] = mod
    conns = {}
    for (ref, pin), (x, y, pname, net) in v["pins"].items():
        conns.setdefault(ref, {})[pin] = [round(x - cx0, 2), round(y - cz0, 2)]
    wires = []
    for r in v["routes"]:
        for sg in r["segs"]:
            wires.append(dict(h=r["ref"], title=r["title"], a=[r["ref"], sg["pin"]], b=[r["mod"], sg["mpin"]],
                              kind=sg["kind"], net=sg["net"]))
    u1 = v["u1"]; xs = [x for x, _ in u1]; ys = sorted({y for _, y in u1})
    board = dict(size=[W, Hh], sockets=[], socketH=8.5, plugs=[], wireY={}, mounts=[], headD=5.5, keep=[],
                 devkit=dict(x=round((min(xs) + max(xs)) / 2 - cx0, 2), zTop=round(ys[0] - cz0, 2), zRow=round(ys[1] - cz0, 2)))
    board.update(v["board3d"])
    return dict(mods=mods, conns=conns, wires=wires, mains=v["d3_mains"], src=v["src"],
                jumpers=[["JP1", "1", "2"], ["JP3", "1", "2"]], labels=WIRE_LABEL, board=board)

def build(v):
    v["pins"], v["u1"] = read_pins(v["csv"])
    v["routes"] = lv_routes(v)
    nwires = sum(len(r["segs"]) for r in v["routes"])
    t = v["texts"]
    tex = base64.b64encode(v["tex"].read_bytes()).decode()
    meta = t["META"].format(version=(REPO / "VERSION").read_text().strip(), nh=len(v["routes"]), nw=nwires)
    body = TEMPLATE.read_text()
    for key in ("TITLE", "H1", "STAMP", "LEAD", "NAV", "CAPTION", "NOTE3D", "SRC"):
        body = body.replace(f"%%{key}%%", t[key])
    body = (body.replace("%%META%%", meta)
            .replace("%%RULES%%", "\n      ".join(f"<li>{li}</li>" for li in t["RULES"]))
            .replace("%%SVG%%", svg(v))
            .replace("%%TABLES%%", tables(v))
            .replace("%%D3%%", json.dumps(d3data(v), ensure_ascii=False))
            .replace("%%BOARD_TEX%%", "data:image/png;base64," + tex))
    head, rest = body.split("</style>", 1)
    page = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head + "</style>\n</head>\n<body>" + rest + "</body>\n</html>\n")
    return page, body, len(v["routes"]), nwires


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if a page differs from a fresh build")
    ap.add_argument("--fragment", type=Path, help="also write the carrier page without the document wrapper")
    args = ap.parse_args()
    for v in (carrier(), shield()):
        page, body, nh, nwires = build(v)
        out = v["out"]
        if args.check:
            if not out.exists() or out.read_text() != page:
                sys.exit(f"{out.relative_to(REPO)} is out of date: run python tools/build_wiring_page.py")
            print("PASS", out.relative_to(REPO), "matches connections.csv and the generator")
            continue
        out.write_text(page)
        if args.fragment and v["key"] == "carrier":
            args.fragment.write_text(body)
        print("written", out.relative_to(REPO), len(page), "bytes;", nh, "harnesses,", nwires, "LV wires")


if __name__ == "__main__":
    main()
