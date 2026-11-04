#!/usr/bin/env python3
"""Generate the GitHub Pages landing page and the Compact overview, purchase and assembly pages.

Everything is derived from hardware/shield-compact (design.json, manufacturing CSVs, manifest, previews),
so the pages cannot drift from the board; --check fails when a committed page is stale.
Standard library only: the Pages workflow runs it on a bare runner.
"""
from pathlib import Path
import argparse, base64, csv, html, json, re, sys, urllib.parse

R = Path(__file__).resolve().parents[1]
H = R / "hardware/shield-compact"
M = H / "manufacturing"
PV = H / "previews"
GH = "https://github.com/Rico-X/GemilaiMate"
BLOB, TREE, RAW = GH + "/blob/main/", GH + "/tree/main/", GH + "/raw/main/"
PAGES = "https://rico-x.github.io/GemilaiMate/"
esc = html.escape

BASE_PORTS = ("J4", "J5", "J6", "J7", "J8", "J9")        # enough for the stock Gemilai 3007Z
MODULE_NAMES = {"J_ADS": "ADS1115", "J_TC": "MAX31855", "J_LEVEL": "CJMCU-0102"}
# Packages the paid kit from docs/purchase-kit.md already covers (29.10.2026), see docs/compact-purchase-delta.md
OLD_KIT = {"100nF 50V X7R": 100, "10k 1%": 100, "1k 1%": 100, "SN74LVC1G17DBVR": 10, "0R": 100}
CAUTION = {
    "U1": "Голый модуль <b>N16R8</b>. DevKit, N8R8, N16 без R8, WROOM-2 и ESP-WROOM-32 не подходят",
    "J1": "Только <b>HRO TYPE-C-31-M-12</b>; USB4085 и «USB-C 16 pin» не совместимы",
    "U3": "SOT-223, выводы 1 IN · 2 GND/таб · 3 OUT. AMS1117 — другая распиновка",
    "U6": "<b>SOIC-14</b> (суффикс D/DR). DIP-14 (N) не встанет",
    "U7": "<b>PCA9634D</b>, SOIC-20W. PCA9685 — другая микросхема",
    "R8": "<b>1,58 кОм 1%</b> задаёт ID=4. 1,2 кОм от carrier не подходит",
    "F1": "PTC 1206 на <b>0,5 А</b>, не стеклянный 5×20",
    "F2": "PTC 1206 на <b>1,5 А</b>, не стеклянный 5×20",
    "C6": "Диэлектрик C0G/NP0",
    "U4": "SOT-23-5 (DBV), не путать с U5",
    "U5": "SOT-23-5 (DBV), не путать с U4",
    "D3": "Однонаправленный SMAJ5.0<b>A</b>",
    "Q2": "N-канальный MOSFET в SOT-23",
    "R27": "Перемычка 0 Ом",
}
WIRE_NOTE = ("PH (SPH-002T-P0.5L): провод <b>24–28 AWG</b>, изоляция Ø0,8–1,5 мм. XH (SXH-001T-P0.6): до 22 AWG. "
             "Провод 22 AWG в контакты PH не обжимается.")


# ---------------------------------------------------------------- data

def load():
    d = json.loads((H / "design.json").read_text())
    rev = json.loads((H / "revision.json").read_text())
    man = json.loads((M / "manifest.json").read_text())
    rows = lambda name: list(csv.DictReader((M / name).open(encoding="utf-8")))
    parts = {c["designator"]: c for c in d["parts"]}
    under = {}
    for ref, s in d["module_sockets"].items():
        x0, y0, x1, y1 = s["body_rect_mm"]
        for c in d["parts"]:
            if c["side"] == "front" and x0 < c["x"] < x1 and y0 < c["y"] < y1 and c["ref"] not in d["module_sockets"]:
                under[c["designator"]] = MODULE_NAMES[ref]
    return dict(d=d, rev=rev["revision"], date=rev["date"], man=man, parts=parts, under=under,
                smd=rows("BOM-SMD.csv"), tht=rows("BOM-THT.csv"), ext=rows("BOM-EXTERNAL.csv"),
                harn=rows("HARNESSES.csv"), pinout=rows("PINOUT.csv"))


def pkg(fp):
    fp = fp.split(":")[-1]
    for key, name in (("ESP32-S3-WROOM", "модуль 18×25,5"), ("USB_C", "USB-C 16P SMD"), ("SOIC-20W", "SOIC-20W 7,5 мм"),
                      ("SOIC-14", "SOIC-14 3,9 мм"), ("SOT-223", "SOT-223"), ("SOT-23-6", "SOT-23-6"),
                      ("SOT-23-5", "SOT-23-5"), ("SOT-23", "SOT-23"), ("D_SMA", "SMA"), ("TL3342", "TL3342 SMD"),
                      ("_0805_", "0805"), ("_1206_", "1206"), ("JST_XH", "JST XH"), ("JST_PH", "JST PH")):
        if key in fp:
            return name
    return fp


def orient(c):
    ref = c["designator"]
    if ref == "U1":
        return "антенна наружу за верхний край"
    if ref == "J1":
        return "штырьки корпуса в отверстия, разъём к нижнему краю"
    if ref == "U3":
        return "широкий таб — к контуру таба"
    if ref.startswith("D"):
        return "полоса катода к черте шелкографии"
    if ref.startswith(("U", "Q")):
        return "вывод 1 к точке шелкографии"
    if ref.startswith("SW"):
        return "по площадкам; прозвонить после пайки"
    if ref.startswith("J"):
        return "квадратная площадка — контакт 1"
    return "любая"


def img(name, alt):
    data = base64.b64encode((PV / name).read_bytes()).decode()
    return f'<img alt="{esc(alt)}" loading="lazy" src="data:image/png;base64,{data}">'


def fnum(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- board map (true scale, mm)

def part_rect(c, d):
    if c["designator"] == "U1":
        return d["module_body"]
    pads = c.get("physical_pads") or c["pins"]
    xs, ys = [p["x"] for p in pads], [p["y"] for p in pads]
    fp = c["footprint"]
    m = 1.9 if "JST" in fp else 1.3 if ("D_SMA" in fp or "socket" in fp) else 0.7
    return [min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m]


def board_map(D, refs=(), side="front", probes=(), title=""):
    d = D["d"]
    W, Hh = d["size_mm"]
    fx = (lambda x: W - x) if side == "back" else (lambda x: x)
    refs, probes = list(refs), list(probes)
    out = [f'<svg viewBox="-3 -10 {W + 6} {Hh + 15}" role="img" aria-label="{esc(title)}">',
           f'<rect class="m-board" x="0" y="0" width="{W}" height="{Hh}" rx="1"/>']
    x0, y0, x1, y1 = d["module_body"]
    out.append(f'<rect class="m-ant" x="{fnum(min(fx(x0), fx(x1)))}" y="{y0}" width="{fnum(x1 - x0)}" height="{fnum(-y0)}"/>')
    out.append(f'<text class="m-side" x="{fnum(min(fx(x0), fx(x1)) + 1)}" y="-2.6">антенна</text>')
    r = d["mount_keepout_radius_mm"] / 2.2
    for x, y in d["mounts_mm"]:
        out.append(f'<circle class="m-hole" cx="{fnum(fx(x))}" cy="{y}" r="{fnum(r)}"/>')
    hi, labels = [], []
    for c in d["parts"]:
        ref = c["designator"]
        if (c["side"] != side and ref not in probes) or (c["dnp"] and ref not in refs + probes):
            continue
        a, b, e, f = part_rect(c, d)
        a, e = sorted((fx(a), fx(e)))
        box = f'x="{fnum(a)}" y="{fnum(b)}" width="{fnum(e - a)}" height="{fnum(f - b)}"'
        if ref in refs:
            hi.append(f'<rect class="m-hi" {box} rx=".3"><title>{esc(ref)} · {esc(c["value"])}</title></rect>')
            pads = c.get("physical_pads") or c["pins"]
            p1 = next((p for p in pads if p["number"] == "1"), None)
            if ref[0] in "UQDJ" and ref != "U1" and p1:
                hi.append(f'<circle class="m-pin1" cx="{fnum(fx(p1["x"]))}" cy="{fnum(p1["y"])}" r=".55"/>')
            labels.append(f'<text class="m-lab" x="{fnum((a + e) / 2)}" y="{fnum(b - .55)}" text-anchor="middle">{esc(ref)}</text>')
        elif ref in probes:
            hi.append(f'<rect class="m-pin1" {box} rx=".3" opacity=".85"/>')
            left = a > 12        # probe labels sit beside the pad, so neighbouring probes (TP5 above J4) stay readable
            labels.append(f'<text class="m-lab" x="{fnum(a - .6 if left else e + .6)}" y="{fnum((b + f) / 2 + .75)}" '
                          f'text-anchor="{"end" if left else "start"}">{esc(ref)}</text>')
        else:
            out.append(f'<rect class="m-part" {box} rx=".3"/>')
    if side == "front":
        for ref, s in d["module_sockets"].items():
            a, b, e, f = s["body_rect_mm"]
            out.append(f'<rect class="m-mod" x="{fnum(a)}" y="{fnum(b)}" width="{fnum(e - a)}" height="{fnum(f - b)}"/>')
            out.append(f'<text class="m-modl" x="{fnum(a + .6)}" y="{fnum(f - .7)}">{MODULE_NAMES[ref]}</text>')
    out += hi + labels
    out.append(f'<text class="m-side" x="{W / 2}" y="{Hh + 4}" text-anchor="middle">'
               f'{"ВИД СВЕРХУ" if side == "front" else "ВИД СНИЗУ · ЗЕРКАЛЬНО"} · {W}×{Hh} ММ</text></svg>')
    return "".join(out)


# ---------------------------------------------------------------- page shell

def nav(current):
    items = [("index.html", "Все платы"), ("compact.html", "Compact"), ("compact-wiring.html", "подключение и 3D"),
             ("compact-purchase.html", "закупка"), ("compact-assembly.html", "монтаж")]
    return " · ".join(f"<b>{t}</b>" if h == current else f'<a href="{h}">{t}</a>' for h, t in items)


def page(D, *, title, desc, h1, lead, stamp, current, meta, body, script=""):
    t = (R / "tools/compact_pages_template.html").read_text()
    footer = (f'GemilaiMate · Rico-X · <a href="{GH}">github.com/Rico-X/GemilaiMate</a>. Страница собрана '
              f'<code>tools/build_compact_pages.py</code> из файлов Compact {D["rev"]} ({D["date"]}). '
              'Код основан на GaggiMate (jniebuhr и участники); лицензии — в NOTICE.md и LICENSE.md.')
    for k, v in (("TITLE", title), ("DESC", desc), ("H1", h1), ("LEAD", lead), ("STAMP", stamp), ("NAV", nav(current)),
                 ("META", meta), ("BODY", body), ("FOOTER", footer), ("SCRIPT", script)):
        t = t.replace(f"%%{k}%%", v)
    return t


def meta(D):
    m = D["man"]
    return (f'Compact {D["rev"]} · {m["board_size_mm"][0]}×{m["board_size_mm"][1]} мм · {m["copper_layers"]} слоя · '
            f'{m["thickness_mm"]} мм · {m["copper_oz"]} oz · {m["smd_placements"]} SMD · KiCad {m["kicad_version"]}')


STAMP = "Прототип · в железе не собран · модули не замерены"


# ---------------------------------------------------------------- landing

def landing(D):
    def stats(board):
        p = R / f"hardware/{board}/manufacturing/CPL-SMD.csv"
        return sum(1 for _ in csv.DictReader(p.open(encoding="utf-8")))
    sizes = ('<figure class="sizes"><svg viewBox="-2 -12 132 92" role="img" '
             'aria-label="Три платы в одном масштабе, совмещены по левому верхнему углу">'
             '<rect class="s-c" x="0" y="0" width="90" height="46"/>'
             '<rect class="s-s" x="0" y="0" width="90" height="75"/>'
             '<rect class="s-x" x="0" y="0" width="76" height="61" fill-opacity=".55"/>'
             '<rect class="s-x" x="7" y="-7.15" width="18" height="7.15" fill-opacity=".25" stroke-dasharray="1.2 .8"/>'
             '<text x="92" y="44">carrier 90×46</text><text x="92" y="74">shield 90×75</text>'
             '<text class="s-xt" x="44" y="58">Compact 76×61</text><text x="27" y="-3" class="s-xt">антенна WROOM</text>'
             '</svg><figcaption>Габариты текстолита в одном масштабе. Compact на 31% меньше shield по площади; '
             'антенна WROOM выступает за край на 7 мм.</figcaption></figure>')
    cards = [
        dict(cls="", name="Carrier v0.1", ver="90×46 мм · 2 слоя · DevKit на жгутах",
             text="Исходная плата: ESP32-S3 DevKit N8R8 в гнёздах, ADS1115/MAX31855/TXS0102 и силовые модули — на жгутах. "
                  f"{stats('carrier')} SMD-установок. Прошивка <code>controller</code>, ID=3.",
             links=[("wiring.html", "Подключение и 3D", True), (BLOB + "docs/assembly.md", "Сборка", False),
                    (TREE + "hardware/carrier", "KiCad", False),
                    (BLOB + "hardware/carrier/manufacturing/gerber-drill.zip", "Gerber", False)]),
        dict(cls="", name="Shield v0.2.4", ver="90×75 мм · 2 слоя · модули в гнёздах",
             text="DevKit N8R8 и три измерительных модуля вставляются в гнёзда — вместо трёх жгутов. RobotDyn и SSR — "
                  f"на управляющих жгутах. {stats('shield')} SMD-установок. Прошивка <code>controller</code>, ID=3.",
             links=[("shield-wiring.html", "Подключение и 3D", True), ("shield.html", "Рендеры и распиновка", False),
                    (BLOB + "docs/shield.md", "Сборка", False), (TREE + "hardware/shield", "KiCad", False)]),
        dict(cls=" now", name=f"Compact {D['rev']}", ver="76×61 мм · 2 слоя · WROOM на плате",
             text="ESP32-S3-WROOM-1-N16R8 и USB-C распаяны на плате, модули в гнёздах сверху, все кабельные JST снизу. "
                  f"Паяется вручную: 0805/1206, SOT-23, SOIC. {D['man']['smd_placements']} SMD-установок. "
                  "Прошивка <code>controller-compact</code>, ID=4.",
             links=[("compact.html", "Обзор и распиновка", True), ("compact-wiring.html", "Подключение и 3D", False),
                    ("compact-purchase.html", "Закупка", False), ("compact-assembly.html", "Пошаговый монтаж", False)]),
    ]
    cards_html = "".join(
        f'<section class="sheet card{c["cls"]}"><div class="ver">{c["ver"]}</div><h2>{c["name"]}</h2><p>{c["text"]}</p>'
        '<ul class="links">' + "".join(f'<li><a{" class=primary" if p else ""} href="{h}">{t}</a></li>'
                                       for h, t, p in c["links"]) + "</ul></section>" for c in cards)
    table = (
        '<section class="sheet"><h2>Сравнение</h2><div class="scroll"><table>'
        '<tr><th></th><th>Carrier v0.1</th><th>Shield v0.2.4</th><th>Compact ' + D["rev"] + '</th></tr>'
        '<tr><td>Текстолит</td><td>90×46 мм</td><td>90×75 мм</td><td>76×61 мм + антенна 7 мм</td></tr>'
        '<tr><td>Контроллер</td><td>DevKit N8R8 в гнёздах</td><td>DevKit N8R8 в гнёздах</td><td>WROOM-1-N16R8 на плате</td></tr>'
        '<tr><td>ADS1115 / MAX31855 / TXS0102</td><td>на жгутах</td><td>в гнёздах</td><td>в гнёздах</td></tr>'
        '<tr><td>Жгуты базовой машины</td><td>9 жгутов, 37 проводов</td><td>6 жгутов, 18 проводов</td><td>6 жгутов, 18 проводов</td></tr>'
        '<tr><td>USB</td><td>на DevKit</td><td>на DevKit</td><td>USB-C на плате, только прошивка</td></tr>'
        '<tr><td>Цель прошивки</td><td><code>controller</code>, ID=3</td><td><code>controller</code>, ID=3</td>'
        '<td><code>controller-compact</code>, ID=4</td></tr>'
        f'<tr><td>SMD</td><td>{stats("carrier")} шт.</td><td>{stats("shield")} шт.</td>'
        f'<td>{D["man"]["smd_placements"]} шт., в том числе WROOM и USB-C с шагом 0,5 мм</td></tr>'
        '<tr><td>Статус</td><td colspan="3">Файлы проверены (ERC/DRC, воспроизводимая сборка). Ни одна плата не собиралась '
        'и не испытывалась в машине.</td></tr></table></div></section>')
    common = (
        '<section class="sheet"><h2>Общее для всех плат</h2><ul>'
        f'<li>Прошивка: <a href="{GH}/releases/tag/v0.1.0">релиз v0.1.0</a> для carrier/shield; для Compact пакет '
        f'собирается из исходников (<a href="{BLOB}docs/development.md">сборка</a>).</li>'
        f'<li><a href="{BLOB}docs/flashing.md">Прошивка через USB</a> и <a href="{BLOB}docs/bench.md">низковольтный стенд</a> '
        '— до установки в машину.</li>'
        f'<li><a href="{BLOB}docs/validation.md">Статус проверок и открытые вопросы</a>, '
        f'<a href="{BLOB}docs/components.md">общие комплектующие</a>.</li>'
        '<li>Сеть 230 В на платы не заходит: нагрев остаётся на штатной плате Gemilai, помпа и клапан коммутируются '
        'внешними RobotDyn и SSR.</li></ul></section>')
    body = (f'<div class="grid2"><section class="sheet">{sizes}</section>{common}</div>'
            f'<div class="grid3">{cards_html}</div>{table}')
    return page(D, title="GemilaiMate — варианты плат", desc="Три варианта платы GemilaiMate для Gemilai 3007Z: carrier, "
                "shield и Compact — подключение, 3D, закупка и монтаж.",
                h1="GemilaiMate · платы", current="index.html", stamp="Прототипы · в железе не собраны",
                lead="Управление проливом Gemilai 3007Z на прошивке, основанной на GaggiMate. Три независимых варианта "
                     "низковольтной платы; GPIO и логика прошивки общие, отличаются компоновка, контроллер и сборка.",
                meta="GemilaiMate v0.1.0 · carrier v0.1 · shield v0.2.4 · Compact " + D["rev"] + " · Rico-X",
                body=body)


# ---------------------------------------------------------------- Compact overview

def overview(D):
    m, d = D["man"], D["d"]
    specs = [("Текстолит", f'{m["board_size_mm"][0]}×{m["board_size_mm"][1]} мм'),
             ("Слои", f'{m["copper_layers"]} · FR-4 {m["thickness_mm"]} мм · {m["copper_oz"]} oz'),
             ("Контроллер", "ESP32-S3-WROOM-1-N16R8"), ("Память", "16 MB Flash · 8 MB PSRAM"),
             ("USB", "HRO TYPE-C-31-M-12 · прошивка"), ("Модули в гнёздах", "ADS1115 · MAX31855 · CJMCU-0102"),
             ("Кабели", "JST PH/XH снизу · 6 базовых"), ("SMD", f'{m["smd_placements"]} установок, 0805+'),
             ("Дорожка / зазор", f'{fnum(m["minimum_track_mm"])} / {fnum(m["minimum_copper_clearance_mm"])} мм'),
             ("Переход", f'{fnum(m["via_diameter_drill_mm"][0])} / {fnum(m["via_diameter_drill_mm"][1])} мм'),
             ("Крепёж", "4 × M2 нейлон, головка ≤ 4 мм"), ("Прошивка", "controller-compact · ID=4")]
    spec_html = '<div class="specs">' + "".join(f"<div><b>{k}</b><span>{esc(v)}</span></div>" for k, v in specs) + "</div>"
    links = ('<ul class="links">'
             '<li><a class="primary" href="compact-assembly.html">Пошаговый монтаж</a></li>'
             '<li><a href="compact-purchase.html">Закупка</a></li><li><a href="compact-wiring.html">Подключение и 3D</a></li>'
             f'<li><a href="{RAW}hardware/shield-compact/manufacturing/gemilaimate-compact-{D["rev"]}-PROTOTYPE.zip">Gerber ZIP</a></li>'
             f'<li><a href="{RAW}hardware/shield-compact/previews/assembly-1to1.pdf">Сборочный 1:1 сверху</a></li>'
             f'<li><a href="{RAW}hardware/shield-compact/previews/assembly-bottom-1to1.pdf">1:1 снизу</a></li>'
             f'<li><a href="{TREE}hardware/shield-compact">KiCad-проект</a></li>'
             f'<li><a href="{BLOB}docs/compact-shield.md">Описание и ограничения</a></li></ul>')
    renders = (
        '<section class="sheet"><h2>Рендеры</h2><div class="grid2">'
        f'<figure>{img("assembled-front.png", "Compact в сборе, вид спереди")}<figcaption>Сборка: WROOM, SMD и три модуля в '
        'гнёздах. Модули — номинальные габариты продавцов, реальные клоны не замерены.</figcaption></figure>'
        f'<figure>{img("assembled-back.png", "Compact, вид снизу")}<figcaption>Снизу только кабельные JST PH/XH. J10 '
        '(нагрев) не устанавливается.</figcaption></figure>'
        f'<figure>{img("assembled-top.png", "Compact, вид сверху")}<figcaption>Вид сверху: часть SMD уходит под модули, '
        'поэтому SMD паяются до гнёзд.</figcaption></figure></div></section>')
    marks = (
        '<section class="sheet"><h2>Сборочные виды</h2><p>Экспорт F.Fab/B.Fab и шелкографии из текущей PCB: все позиционные '
        'обозначения, вывод 1 и полярность. Для пайки удобнее печать 1:1 из PDF.</p><div class="grid2">'
        f'<figure>{img("assembly-top.png", "Сборочный вид сверху")}<figcaption>Сверху.</figcaption></figure>'
        f'<figure>{img("assembly-bottom.png", "Сборочный вид снизу")}<figcaption>Снизу, зеркально: так плата лежит '
        'перевёрнутой на столе.</figcaption></figure></div></section>')
    tables = []
    for c in d["parts"]:
        if not c["designator"].startswith("J") or c["dnp"] or c["designator"] == "J1":
            continue
        rows = "".join(f'<tr><td class="num">{p["number"]}</td><td>{esc(p["name"])}</td>'
                       f'<td class="mono">{esc(p["net"] or "— не подключён")}</td></tr>' for p in c["pins"])
        where = "сверху, гнездо модуля" if c["side"] == "front" else "снизу, кабель"
        tag = ('<span class="tag base">база</span>' if c["designator"] in BASE_PORTS else
               '<span class="tag opt">опция</span>' if c["side"] == "back" else '<span class="tag base">модуль</span>')
        tables.append(f'<div id="{c["designator"]}"><h3>{c["designator"]} · {esc(c["value"])} {tag}</h3>'
                      f'<p class="note">{esc(c["mpn"])} · {where}</p><div class="scroll"><table>'
                      f'<tr><th class="num">Конт.</th><th>Вывод</th><th>Цепь</th></tr>{rows}</table></div></div>')
    pins = ('<section class="sheet"><h2>Распиновка разъёмов и гнёзд</h2><p>Контакт 1 — квадратная площадка. Порядок '
            'контактов кабеля совпадает с таблицей; цвет провода значения не имеет. Пустые позиции не подключать.</p>'
            f'<div class="grid3">{"".join(tables)}</div></section>')
    body = (f'<section class="sheet"><h2>Коротко</h2>{spec_html}{links}</section>'
            '<p class="warn"><b>Не проверено в железе.</b> ERC/DRC, воспроизводимая сборка и сверка CAM пройдены; плата не '
            'изготавливалась, USB-прошивка и работа в машине не проверялись. До заказа приложить реальные модули и '
            'разъёмы к печати 1:1.</p>' + renders + marks + pins)
    return page(D, title=f"GemilaiMate Compact {D['rev']}", desc="Compact Shield GemilaiMate: рендеры, сборочные виды, "
                "распиновка разъёмов и ссылки на производственные файлы.",
                h1=f"Compact Shield {D['rev']}", current="compact.html", stamp=STAMP, meta=meta(D),
                lead="Самая маленькая из трёх плат GemilaiMate: ESP32-S3-WROOM и USB-C распаяны на плате, ADS1115, "
                     "MAX31855 и CJMCU-0102 вставляются в гнёзда сверху, кабели — снизу. Сеть 230 В на плату не заходит.",
                body=body)


# ---------------------------------------------------------------- purchase

def search_query(row):
    """Marketplace query: package + value for passives, the example MPN for everything else."""
    v, fp, refs = row["Value"], row["Footprint"], row["Designators"]
    size = "0805" if "_0805_" in fp else "1206" if "_1206_" in fp else ""
    if refs.startswith("R") and size:
        v = v.replace(" 1%", "")
        return f'{size} {v[:-1] + " ohm" if v.endswith("R") else v} 1% resistor'
    if refs.startswith("C") and size:
        return f"{size} {v} capacitor"
    return row["MPN_example"].split(",")[0]


def purchase(D):
    parts = D["parts"]
    smd_rows = []
    for i, r in enumerate(D["smd"]):
        refs = r["Designators"].split()
        q = int(r["Quantity_1_PCB"])
        small = not any(x in r["Footprint"] for x in ("WROOM", "USB_C", "SOIC", "TL3342"))
        note = next((CAUTION[x] for x in refs if x in CAUTION), "")
        under = sorted({D["under"][x] for x in refs if x in D["under"]})
        if under:
            note += ("; " if note else "") + "часть под " + ", ".join(under)
        stock = OLD_KIT.get(r["Value"], 0)
        qa = urllib.parse.quote(search_query(r).replace(" ", "-"))
        ql = urllib.parse.quote(r["MPN_example"].split(",")[0])
        smd_rows.append(
            f'<tr data-q="{q}" data-small="{int(small)}" data-stock="{stock}" data-key="smd{i}">'
            f'<td><input type="checkbox" aria-label="Куплено: {esc(r["Value"])}"></td>'
            f'<td><b>{esc(r["Value"])}</b><div class="note">{note}</div></td><td class="fp">{esc(pkg(r["Footprint"]))}</td>'
            f'<td class="refs">{esc(" ".join(refs))}</td><td class="mono">{esc(r["MPN_example"])}</td>'
            f'<td class="num">{q}</td><td class="num tot">{q}</td><td class="num buy">{q}</td>'
            f'<td class="noprint srch"><a href="https://www.aliexpress.com/w/wholesale-{qa}.html">Ali</a> · '
            f'<a href="https://www.lcsc.com/search?q={ql}">LCSC</a></td></tr>')
    smd = ('<section class="sheet" id="smd"><h2>SMD на плату</h2><p>Все SMD — сверху. Корпуса строго как в таблице: '
           'площадки рассчитаны на ручную пайку, 0603 и TSSOP не подходят. «С запасом» добавляет процент к мелочи '
           '(резисторы, конденсаторы, SOT, SMA) и округляет вверх.</p><div class="scroll"><table id="smdt">'
           '<tr><th></th><th>Номинал</th><th>Корпус</th><th>Позиции</th><th>Пример MPN</th><th class="num">На 1</th>'
           '<th class="num">Итого</th><th class="num">Купить</th><th class="noprint">Поиск</th></tr>'
           + "".join(smd_rows) + '</table></div><p class="note" id="smdsum"></p></section>')

    groups = {}
    for r in D["tht"]:
        groups.setdefault(r["MPN_example"], []).append(r)
    tht_rows = []
    for i, (mpn, rows) in enumerate(groups.items()):
        refs = [r["Reference"] for r in rows]
        per = 2 if mpn.startswith("2 x") else 1
        base = sum(per for x in refs if x in BASE_PORTS or parts[x]["side"] == "front")
        allq = per * len(refs)
        c = parts[refs[0]]
        if c["side"] == "front":
            row_pins = len(c["pins"]) // per
            desc = f'Гнездо 1×{row_pins} 2,54 мм{" ×2" if per == 2 else ""} · {MODULE_NAMES[c["ref"]]}'
        else:
            desc = f'{pkg(c["footprint"])} {len(c["pins"])} конт., вертикальный'
        refs_html = " ".join(f'<b>{x}</b>' if (x in BASE_PORTS or parts[x]["side"] == "front") else x for x in refs)
        tht_rows.append(
            f'<tr data-base="{base}" data-all="{allq}" data-key="tht{i}"><td><input type="checkbox" aria-label="Куплено: {esc(mpn)}"></td>'
            f'<td>{esc(desc)}</td><td class="mono">{esc(mpn.replace("2 x ", ""))}</td><td class="refs">{refs_html}</td>'
            f'<td>{"сверху" if rows[0]["Side"] == "front" else "снизу"}</td>'
            f'<td class="num per">{base}</td><td class="num tot">{base}</td></tr>')
    tht = ('<section class="sheet" id="tht"><h2>Разъёмы и гнёзда на плату</h2>'
           '<div class="controls"><label><input type="radio" name="ports" value="base" checked> базовая машина: '
           'J4–J9</label><label><input type="radio" name="ports" value="all"> все порты (ALT, ToF, Alba, RGBW, свет)</label></div>'
           '<div class="scroll"><table id="thtt"><tr><th></th><th>Деталь</th><th>Пример MPN</th><th>Позиции</th><th>Сторона</th>'
           '<th class="num">На 1</th><th class="num">Итого</th></tr>' + "".join(tht_rows) + '</table></div>'
           '<p class="note">Жирным — позиции базовой сборки. J10 (нагрев) не устанавливается. Гнёзда модулей можно нарезать из '
           'полос 1×40 2,54 мм: 26 контактов на плату; высота гнезда ≥ 8,5 мм, межрядье CJMCU 12,70 мм проверить по '
           'модулю. DuPont-разъёмы не заменяют JST PH/XH.</p></section>')

    hrows, housings, contacts = [], {}, {}
    for r in D["harn"]:
        base = r["PCB_reference"] in BASE_PORTS
        n, kind = r["Contacts"].split(" x ")
        for store, key, k in ((housings, r["Housing"], 1), (contacts, kind, int(n))):
            v = store.setdefault(key, [0, 0])
            v[0] += k * base
            v[1] += k
        tag = '<span class="tag base">база</span>' if base else '<span class="tag opt">опция</span>'
        hrows.append(f'<tr class="{"" if base else "opt"}"><td class="refs">{r["PCB_reference"]}</td><td>{esc(r["Function"])}</td>'
                     f'<td class="mono">{r["Housing"]}</td><td class="mono">{esc(r["Contacts"])}</td>'
                     f'<td class="mono">{esc(r["Pin_1_to_N"])}</td><td>{tag}</td></tr>')
    summary = "".join(f'<tr><td class="mono">{k}</td><td class="num">{b}</td><td class="num">{a}</td></tr>'
                      for k, (b, a) in list(housings.items()) + list(contacts.items()))
    harn = ('<section class="sheet" id="harness"><h2>Ответные корпуса и контакты — на одну машину</h2>'
            '<p>Жгуты нужны одной кофемашине, а не каждой плате. Порядок проводов — по столбцу «Контакт 1…N».</p>'
            '<div class="grid2"><div class="scroll"><table><tr><th>Порт</th><th>Назначение</th><th>Корпус</th><th>Контакты</th>'
            '<th>Контакт 1…N</th><th></th></tr>' + "".join(hrows) + '</table></div>'
            '<div><div class="scroll"><table><tr><th>Позиция</th><th class="num">База</th><th class="num">Все порты</th></tr>'
            + summary + f'</table></div><p class="note">{WIRE_NOTE} Контактов брать с запасом на ошибки обжима: '
            'для PH около 50 шт. В PHR-6 RobotDyn заняты только позиции 1–4.</p></div></div></section>')

    erows = "".join(f'<tr><td>{esc(r["Item"])}</td><td class="num">{r["Quantity_per_assembled_controller"]}</td>'
                    f'<td class="mono">{esc(r["MPN_example"])}</td><td class="mono">{esc(r["Dimensions_mm"])}</td>'
                    f'<td class="note">{esc(r["Note"])}</td></tr>' for r in D["ext"])
    ext = ('<section class="sheet" id="external"><h2>Модули и крепёж — на один контроллер</h2>'
           '<p>Вставные модули съёмные: один комплект можно переставлять между опытными платами. Дисплей, датчики, '
           'RobotDyn, SSR и БП общие для всех трёх плат — см. <a href="' + BLOB + 'docs/components.md">комплектующие</a>.</p>'
           '<div class="scroll"><table><tr><th>Позиция</th><th class="num">Шт.</th><th>Пример</th><th>Размер, мм</th>'
           f'<th>Примечание</th></tr>{erows}</table></div></section>')

    m = D["man"]
    pcb = ('<section class="sheet" id="pcb"><h2>Печатная плата</h2><div class="specs">'
           + "".join(f"<div><b>{k}</b><span>{v}</span></div>" for k, v in (
               ("Размер", f'{m["board_size_mm"][0]}×{m["board_size_mm"][1]} мм'), ("Слои", f'{m["copper_layers"]}, FR-4'),
               ("Толщина / медь", f'{m["thickness_mm"]} мм / {m["copper_oz"]} oz'),
               ("Мин. дорожка", f'{fnum(m["minimum_track_mm"])} мм (7,9 mil)'),
               ("Мин. зазор", f'{fnum(m["minimum_copper_clearance_mm"])} мм (класс 8 mil)'),
               ("Переход", f'{fnum(m["via_diameter_drill_mm"][0])}/{fnum(m["via_diameter_drill_mm"][1])} мм, закрыт маской'),
               ("Покрытие", "HASL или ENIG"), ("Монтаж", "без монтажа")))
           + '</div><ul class="links"><li><a class="primary" href="' + RAW +
           f'hardware/shield-compact/manufacturing/gemilaimate-compact-{D["rev"]}-PROTOTYPE.zip">Gerber ZIP {D["rev"]}</a></li>'
           f'<li><a href="{BLOB}hardware/shield-compact/manufacturing/BOM-SMD.csv">BOM-SMD.csv</a></li>'
           f'<li><a href="{BLOB}hardware/shield-compact/manufacturing/BOM-THT.csv">BOM-THT.csv</a></li>'
           f'<li><a href="{BLOB}hardware/shield-compact/manufacturing/CPL-SMD.csv">CPL-SMD.csv</a></li>'
           f'<li><a href="{BLOB}hardware/shield-compact/manufacturing/HARNESSES.csv">HARNESSES.csv</a></li></ul>'
           '<p class="note">Минимальная партия у фабрик обычно 5 плат. ENIG даёт ровнее площадки под USB-C и WROOM. '
           'Carrier и shield имеют другую разводку — их Gerber сюда не подходит.</p></section>')
    cautions = ('<section class="sheet"><h2>Частые ошибки закупки</h2><ul>'
                '<li><b>ESP32-S3 DevKit</b> не ставится на Compact — нужен голый WROOM-1-<b>N16R8</b>.</li>'
                '<li><b>SN74AHCT125N</b> (DIP-14) не встанет на U6 — нужен SN74AHCT125<b>DR</b> (SOIC-14).</li>'
                '<li><b>AMS1117</b> не заменяет AP7361C-33E-13: другая распиновка.</li>'
                '<li><b>R8 = 1,58 кОм</b>: от него зависит определение платы (ID=4).</li>'
                '<li>Предохранители F1/F2 — <b>PTC 1206</b>; F1 на 0,5 А и F2 на 1,5 А не перепутать.</li>'
                '<li>Нужен точный <b>HRO TYPE-C-31-M-12</b>; другие 16-контактные USB-C отличаются посадкой.</li>'
                '<li>Старый крепёж M3 не входит в отверстия Ø2,2 мм — нужен нейлоновый <b>M2</b>.</li>'
                f'<li>{WIRE_NOTE}</li></ul></section>')
    controls = ('<section class="sheet noprint"><h2>Расчёт количества</h2><div class="controls">'
                '<label>Плат собрать <input class="ctl" type="number" id="boards" min="1" max="50" value="1"></label>'
                '<label>Запас на мелочь, % <input class="ctl" type="number" id="spare" min="0" max="100" value="10"></label>'
                '<label><input type="checkbox" id="stock"> вычесть остатки прежнего комплекта '
                f'(<a href="{BLOB}docs/purchase-kit.md">purchase-kit</a>)</label>'
                '<button class="ctl" type="button" onclick="window.print()">Печать списка</button></div>'
                '<p class="note">Отметки «куплено» хранятся только в этом браузере. Карточки поиска — подсказка, а не '
                'проверенный продавец: сверять корпус, номинал и отзывы. Цены и наличие на странице не указаны.</p></section>')
    script = r"""<script>
(() => {
  const KEY = 'gm-compact-purchase-v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  function calc() {
    const n = Math.max(1, Math.min(50, parseInt($('#boards').value) || 1));
    const spare = Math.max(0, parseFloat($('#spare').value) || 0) / 100, useStock = $('#stock').checked;
    let lines = 0, pcs = 0;
    $$('#smdt tr[data-q]').forEach(tr => {
      const tot = +tr.dataset.q * n;
      let buy = tr.dataset.small === '1' ? Math.ceil(tot * (1 + spare) - 1e-9) : tot;
      if (useStock) buy = Math.max(0, buy - +tr.dataset.stock);
      tr.querySelector('.tot').textContent = tot; tr.querySelector('.buy').textContent = buy;
      if (buy) { lines++; pcs += buy; }
    });
    $('#smdsum').textContent = `К покупке: ${lines} позиций, ${pcs} шт. на ${n} ${n === 1 ? 'плату' : n < 5 ? 'платы' : 'плат'}.`;
    const all = document.querySelector('input[name=ports]:checked').value === 'all';
    $$('#thtt tr[data-base]').forEach(tr => {
      const per = +(all ? tr.dataset.all : tr.dataset.base);
      tr.querySelector('.per').textContent = per; tr.querySelector('.tot').textContent = per * n;
    });
  }
  $$('tr[data-key] input[type=checkbox]').forEach(cb => {
    const tr = cb.closest('tr'), k = tr.dataset.key;
    cb.checked = !!saved[k]; tr.classList.toggle('done', cb.checked);
    cb.addEventListener('change', () => {
      saved[k] = cb.checked; tr.classList.toggle('done', cb.checked);
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    });
  });
  ['#boards', '#spare', '#stock'].forEach(s => $(s).addEventListener('input', calc));
  $$('input[name=ports]').forEach(r => r.addEventListener('change', calc));
  calc();
})();
</script>"""
    body = controls + pcb + smd + tht + harn + ext + cautions
    return page(D, title=f"Закупка Compact {D['rev']} — GemilaiMate", desc="Деталировка закупки для Compact Shield GemilaiMate: "
                "PCB, SMD, разъёмы, жгуты и модули с расчётом количества.",
                h1=f"Закупка Compact {D['rev']}", current="compact-purchase.html", stamp=STAMP, meta=meta(D),
                lead="Всё, что нужно для одной или нескольких плат: печатная плата, SMD по позициям, разъёмы и гнёзда, "
                     "ответные корпуса жгутов и вставные модули. Количества пересчитываются под число плат.",
                body=body, script=script)


# ---------------------------------------------------------------- assembly

def steps(D):
    parts = D["parts"]
    smd = [c["designator"] for c in D["d"]["parts"] if c["side"] == "front" and not c["dnp"]
           and not c["footprint"].endswith("_socket")]
    power = ["F1", "F2", "D1", "D2", "D3", "U3", "C1", "C2", "C16"]
    mcu = ["U1", "C3", "C4", "C5", "R5", "R6", "SW1", "SW2"]
    usb = ["J1", "U2", "R1", "R2", "R3", "R4"]
    ident = ["R7", "R8", "C6", "R9", "C9"]
    logic = ["U4", "U5", "U6", "U7", "Q1", "Q2", "Q3"]
    done = set(power + mcu + usb + ident + logic)
    rest = sorted((x for x in smd if x not in done), key=lambda x: (parts[x]["value"], x[0], int(x[1:])))
    sockets = ["J2", "J3", "J19"]
    jst = list(BASE_PORTS) + [c["designator"] for c in D["d"]["parts"]
                                     if c["side"] == "back" and not c["dnp"] and c["designator"] not in BASE_PORTS]
    return [
        dict(id="prep", title="Подготовка и проверка голой платы", refs=[], probes=["J4", "TP5", "TP6"],
             text=["<b>Инструмент:</b> паяльник с регулировкой и жалами 1–2 мм, флюс-гель без отмывки, припой Ø0,5 мм, "
                   "пинцет, оплётка, лупа или микроскоп, мультиметр, лабораторный БП 5 В с ограничением тока, "
                   "изопропиловый спирт и щётка. Для центральной земли WROOM — нижний подогрев или фен.",
                   "Распечатать <a href=\"" + RAW + "hardware/shield-compact/previews/assembly-1to1.pdf\">сборочный вид 1:1</a> "
                   "при 100% и положить рядом: подписи мелких деталей на шелкографию не поместились.",
                   "Детали держать в подписанных пакетах по одному номиналу; доставать только ту ленту, что паяется сейчас."],
             checks=["Плата без сколов, перемычек и непротравов; маска цела у USB-C и WROOM.",
                     "Прозвонка: J4 контакт 1 (квадратная площадка, +5 В) — GND, и TP5 (+3,3 В) — TP6 (GND) — не короткое замыкание.",
                     "Реальные ADS1115, MAX31855, CJMCU-0102 и JST приложены к печати 1:1 — контуры и шаг совпадают."]),
        dict(id="power", title="Питание: предохранители, диоды, стабилизатор", refs=power, probes=["J4", "TP5", "TP6"],
             text=["Первым паяется узел питания, чтобы проверить 3,3 В до установки дорогого модуля.",
                   "F1 — 0,5 А (USB), F2 — 1,5 А (вход 5 В): не перепутать, корпуса одинаковые.",
                   "D1/D2 SS14 и D3 SMAJ5.0A — полоса катода к черте на шелкографии. U3 — широкий таб к контуру таба."],
             checks=["Подать 5 В от БП с ограничением 50–100 мА щупами на площадки J4: квадратная — «+», вторая — GND.",
                     "TP5 относительно TP6: 3,3 В ±3%. Ток — единицы миллиампер; упор в ограничение — искать замыкание.",
                     "Снять питание, разрядить конденсаторы."]),
        dict(id="mcu", title="ESP32-S3-WROOM, запуск и кнопки", refs=mcu,
             text=["U1 кладётся антенной наружу за верхний край; метка вывода 1 модуля — к метке шелкографии. "
                   "Модуль выровнять по всем трём сторонам площадок до пайки.",
                   "Центральную землю паять нижним подогревом или феном с тонким слоем пасты; боковые выводы — паяльником "
                   "с флюсом. Один паяльник не гарантирует пайку скрытого контакта — это слабое место сборки.",
                   "Затем C3, C4, C5, R5 (EN), R6 (BOOT) и кнопки SW1 RESET, SW2 BOOT."],
             checks=["Под лупой: нет перемычек между выводами WROOM, все галтели смочены.",
                     "Кнопки: в покое разомкнуты, при нажатии замкнуты (прозвонка по площадкам).",
                     "Нет КЗ +3,3 В — GND (TP5–TP6)."]),
        dict(id="usb", title="USB-C и защита", refs=usb,
             text=["J1 HRO TYPE-C-31-M-12: направляющие штырьки корпуса — в отверстия, разъём к нижнему краю. Сначала "
                   "пропаять крепёжные лепестки, затем контакты с обильным флюсом протяжкой; перемычки снять оплёткой.",
                   "U2 USBLC6-2SC6 — вывод 1 к точке. R1/R2 5,1 кОм (CC), R3/R4 22 Ом (D+/D−)."],
             checks=["VBUS — GND, D+ — D−, D± — GND не замкнуты.",
                     "USB к компьютеру (без J4): удерживая BOOT, нажать и отпустить RESET, отпустить BOOT — "
                     "появляется устройство Espressif USB JTAG/serial.",
                     "<code>python -m esptool --port ПОРТ flash_id</code> показывает ESP32-S3 и размер Flash 16MB."]),
        dict(id="id", title="ID платы и вход давления", refs=ident,
             text=["R7 10 кОм и <b>R8 1,58 кОм</b> задают ID=4: по нему оригинальная прошивка выбирает профиль платы. "
                   "C6 10 нФ — C0G.", "R9 1 кОм и C9 100 нФ — RC-фильтр давления на A0 ADS1115."],
             checks=["R8 измерен до пайки: 1,56–1,60 кОм."]),
        dict(id="logic", title="Микросхемы и транзисторы", refs=logic,
             text=["Все корпуса — вывод 1 к точке шелкографии. Для SOIC сначала прихватить один угловой вывод, выровнять, "
                   "затем противоположный угол и остальные.",
                   "U4 (SN74LVC1G17) и U5 (SN74LVC1G125) — одинаковые SOT-23-5 с разной функцией: брать из разных пакетов. "
                   "Q1 MMBT3904 и Q2/Q3 AO3400A — тоже одинаковые SOT-23.",
                   "U6 стоит под CJMCU-0102, U7 — под ADS1115: после установки гнёзд к ним не подобраться."],
             checks=["Под лупой нет перемычек на SOIC; все выводы в припое.", "Каждая микросхема — своей маркировкой и ориентацией."]),
        dict(id="rest", title="Остальные резисторы и конденсаторы", refs=rest,
             text=["Паять по одному номиналу за раз, сверяясь с таблицей и печатью 1:1; ориентация не важна.",
                   "R27, R28, R41 — перемычки 0 Ом. R27/R28 не ставить, если подключается внешняя Alba со своим PCA9634. "
                   "R42 не устанавливать (вариант питания MAX31855 от 5 В).",
                   "Часть деталей уходит под модули — пропуск обнаружится только после снятия гнёзд."],
             checks=["Все позиции из таблицы запаяны; лишних деталей на DNP-местах (R42) нет.",
                     "Номиналы выборочно проверены мультиметром (10 кОм, 100 кОм, 180 Ом)."]),
        dict(id="wash", title="Отмывка, осмотр и включение без модулей", refs=[], probes=["J4", "TP5", "TP6"],
             img=("smd-front.png", "Плата после SMD-этапа: только SMD, без гнёзд и разъёмов"),
             text=["Отмыть флюс спиртом, высушить. Осмотреть плату целиком под лупой, особенно USB-C, WROOM и SOIC."],
             checks=["Нет КЗ: J4.1 — GND, TP5 — TP6.",
                     "5 В на J4 от БП с ограничением 200 мА: 3,3 В на TP5; ток стабилен, ничего не греется.",
                     "Повторить USB-проверку <code>flash_id</code>."]),
        dict(id="sockets", title="Гнёзда модулей сверху", refs=sockets,
             text=["Модули служат кондуктором: вставить гнёзда в плату, в них — штыревые гребёнки, сверху надеть модули "
                   "правильной стороной. Перевернуть сборку на стол модулями вниз и припаять по одному крайнему контакту "
                   "каждого гнезда со стороны низа.",
                   "Проверить, что гнёзда стоят ровно и перпендикулярно, затем допаять остальные контакты. Перевернуть и "
                   "припаять гребёнки к модулям сверху. Модули снять до проверки.",
                   "J2 ADS1115: VDD — квадратная площадка 1. J19 CJMCU-0102: ряд A (3,3 В) — с квадратной площадкой, "
                   "ряд B (5 В) напротив, обе GND на одном торце; межрядье 12,70 мм проверить по модулю. "
                   "J3 MAX31855: VIN — квадратная площадка 1, клемма термопары к нижнему краю."],
             checks=["Подписи выводов на модулях совпадают с подписями шелкографии у каждого гнезда.",
                     "Гнёзда без перекоса, модуль вставляется без усилия."]),
        dict(id="jst", title="Кабельные разъёмы снизу", refs=jst, side="back",
             text=["Разъёмы вставляются <b>со стороны низа</b>, паяются сверху. Ключ и контур — по шелкографии низа; "
                   "контакт 1 — квадратная площадка.",
                   "J4 — единственный XH, J8 — единственный PH на 6 позиций. J10 (нагрев) не ставится. Для базовой машины "
                   "достаточно J4–J9; J11–J15 можно поставить позже.",
                   "Припаять один контакт, проверить, что разъём прижат к плате, затем остальные."],
             checks=["Каждый разъём прижат к плате и стоит своей позицией по шелкографии.",
                     "J4 контакт 2 звонится на TP6 (GND); J4 контакт 1 на GND не звонится."]),
        dict(id="flash", title="Первая прошивка без модулей", refs=[],
             text=["Модули, экран и силовые блоки отключены. Прошивка — цель <code>controller-compact</code> из текущего "
                   "пакета (ID=4) по <a href=\"" + BLOB + "docs/flashing.md\">инструкции</a>:",
                   "<code>python tools/flash.py controller-compact --package releases/firmware --port ПОРТ --fresh</code> — "
                   "сначала без <code>--flash</code> (только проверка), затем с ним. Перед экспериментами сохранить полный "
                   "дамп 16 MB.",
                   "Если загрузчик не запускается сам: удерживать BOOT, нажать и отпустить RESET, отпустить BOOT."],
             probes=["J1", "SW1", "SW2"],
             checks=["Проверка flash.py без <code>--flash</code> прошла, запись завершилась без ошибок.",
                     "После RESET контроллер загружается и снова виден по USB без кнопки BOOT."]),
        dict(id="modules", title="Модули — по одному", refs=sockets,
             img=("assembled-front.png", "Compact в сборе с модулями в гнёздах"),
             text=["Только при снятом питании. Порядок: CJMCU-0102, ADS1115, MAX31855; после каждого — включение от БП "
                   "с ограничением тока и проверка 3,3 В.",
                   "Перевёрнутый CJMCU подаёт 5 В на сторону 3,3 В. Перевёрнутый MAX31855 питается не тем выводом. "
                   "Ориентацию сверять с подписями у гнезда."],
             checks=["CJMCU: ряд A на стороне квадратной площадки, ток и 3,3 В в норме.",
                     "ADS1115: VDD на площадке 1, ток в норме.", "MAX31855: VIN на площадке 1, клемма к краю платы."]),
        dict(id="install", title="Крепление, жгуты и стенд", refs=[], side="back", probes=list(BASE_PORTS),
             text=["Четыре нейлоновых M2 с изолирующими стойками, головка винта ≤ 4 мм. Высота стоек — по разъёмам снизу с "
                   "ответными частями и изгибом провода, подобрать по месту.",
                   "Жгуты — по <a href=\"compact-wiring.html#harness\">таблице подключения</a>: J4 питание, J5 экран, "
                   "J6 давление, J7 кнопки, J8 RobotDyn, J9 SSR клапана. Порядок проводов важнее цвета.",
                   "Дальше — <a href=\"" + BLOB + "docs/bench.md\">низковольтный стенд</a> с эквивалентами нагрузки и только "
                   "потом машина. Работы внутри машины — только с вынутой вилкой: 230 В."],
             checks=["Каждый жгут прозвонен по таблице до подключения.", "Пройден стендовый план до установки в машину."]),
    ]


def step_table(D, refs):
    parts, rows, by = D["parts"], [], {}
    for ref in refs:
        c = parts[ref]
        by.setdefault((c["value"], pkg(c["footprint"]), orient(c)), []).append(ref)
    for (value, p, o), rs in by.items():
        under = sorted({D["under"][x] for x in rs if x in D["under"]})
        rows.append((" ".join(rs), value, p, o + (f"; под {', '.join(under)}" if under else ""), len(rs)))
    return rows


def assembly(D):
    out, toc, md = [], [], []
    st = steps(D)
    md.append(f"# Пошаговый монтаж Compact Shield {D['rev']}\n")
    md.append("**Плата в железе ещё не собиралась.** Порядок рассчитан на ручную пайку: сначала все SMD сверху, затем "
              "гнёзда модулей и кабельные разъёмы, модули — последними. Интерактивная версия с картами позиций и "
              f"отметками: [{PAGES}compact-assembly.html]({PAGES}compact-assembly.html).\n")
    md.append("Печать 1:1: [сверху](../hardware/shield-compact/previews/assembly-1to1.pdf), "
              "[снизу](../hardware/shield-compact/previews/assembly-bottom-1to1.pdf). Закупка: "
              f"[{PAGES}compact-purchase.html]({PAGES}compact-purchase.html), "
              "[разница с прежним комплектом](compact-purchase-delta.md). Ограничения платы: [Compact Shield](compact-shield.md).\n")
    md.append("![Плата после SMD-этапа](../hardware/shield-compact/previews/smd-top.png)\n")
    for i, s in enumerate(st, 1):
        side = s.get("side", "front")
        toc.append(f'<li><a href="#{s["id"]}">{esc(s["title"])}</a></li>')
        rows = step_table(D, s["refs"])
        table = ""
        if rows:
            table = ('<div class="scroll"><table><tr><th>Позиции</th><th>Номинал</th><th>Корпус</th><th>Ориентация</th>'
                     '<th class="num">Шт.</th></tr>' + "".join(
                         f'<tr><td class="refs">{esc(r)}</td><td>{esc(v)}</td><td class="fp">{esc(p)}</td><td>{esc(o)}</td>'
                         f'<td class="num">{n}</td></tr>' for r, v, p, o, n in rows) + "</table></div>")
        checks = "".join(f'<li><input type="checkbox" id="{s["id"]}-{k}"><span><label for="{s["id"]}-{k}">{c}</label></span></li>'
                         for k, c in enumerate(s["checks"]))
        title = f'Шаг {i}: {s["title"]}'
        if side == "front":
            probe_note = {"J4": "J4, TP5 (+3,3 В), TP6 (GND)", "J1": "USB-C J1, RESET SW1, BOOT SW2"}
            cap = ("Бирюзовым — детали шага, оранжевая точка — вывод 1 или катод. " if s["refs"] else "") + \
                  (f'Оранжевым — {probe_note[s["probes"][0]]}. ' if s.get("probes") else "") + \
                  "Пунктир — контуры модулей."
        elif s["refs"]:
            cap = "Вид снизу, зеркально — так плата лежит перевёрнутой. Оранжевая точка — контакт 1."
        else:
            cap = "Вид снизу, зеркально. Оранжевым — разъёмы жгутов базовой машины J4–J9."
        right = f'<figure class="map">{board_map(D, s["refs"], side, s.get("probes", ()), title)}<figcaption>{cap}</figcaption></figure>'
        extra = ""
        if s.get("img"):
            extra = f'<figure>{img(*s["img"])}<figcaption>{esc(s["img"][1])}.</figcaption></figure>'
        out.append(f'<section class="sheet step" id="{s["id"]}"><div><h2><span class="n">{i:02d}</span>{esc(s["title"])}</h2>'
                   + "".join(f"<p>{t}</p>" for t in s["text"]) + table +
                   f'<h3>Проверка</h3><ul class="checks">{checks}</ul></div><div>{right}{extra}</div></section>')
        md.append(f"## {i}. {s['title']}\n")
        md.extend(md_text(t) + "\n" for t in s["text"])
        if rows:
            md.append("| Позиции | Номинал | Корпус | Ориентация | Шт. |\n|---|---|---|---|---:|")
            md.extend(f"| {r} | {v} | {p} | {o} | {n} |" for r, v, p, o, n in rows)
            md.append("")
        md.append("**Проверка:**\n")
        md.extend(f"- [ ] {md_text(c)}" for c in s["checks"])
        md.append("")
    md.append(f"Файл создан `tools/build_compact_pages.py` из `hardware/shield-compact` ревизии {D['rev']}; править генератор, "
              "а не этот текст.\n")
    smd_total = sum(1 for c in D["d"]["parts"] if c["side"] == "front" and not c["dnp"] and not c["footprint"].endswith("_socket"))
    intro = ('<div class="grid2"><section class="sheet"><h2>Порядок</h2><ol>' + "".join(toc) + '</ol>'
             '<p class="progress noprint" id="progress"></p></section>'
             '<section class="sheet"><h2>Перед началом</h2>'
             f'<p>{smd_total} SMD-деталей сверху, затем гнёзда модулей и кабельные JST снизу. Модули ставятся последними: '
             'часть SMD находится под ними.</p>'
             '<p class="warn"><b>Самые трудные места</b> — центральная земля WROOM и USB-C с шагом 0,5 мм. Если нет нижнего '
             'подогрева или фена, WROOM лучше отдать на монтаж.</p>'
             '<p>Каждый шаг заканчивается проверкой: не переходить дальше, пока она не пройдена. Отметки сохраняются только '
             f'в этом браузере. <a href="{BLOB}docs/compact-assembly.md">Текстовая версия</a> лежит в репозитории.</p>'
             '<ul class="links"><li><a class="primary" href="' + RAW + 'hardware/shield-compact/previews/assembly-1to1.pdf">'
             'Печать 1:1 сверху</a></li><li><a href="' + RAW + 'hardware/shield-compact/previews/assembly-bottom-1to1.pdf">'
             '1:1 снизу</a></li><li><a href="compact-purchase.html">Что купить</a></li></ul></section></div>')
    script = r"""<script>
(() => {
  const KEY = 'gm-compact-assembly-v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  const boxes = [...document.querySelectorAll('.checks input')], out = document.getElementById('progress');
  function update() {
    const n = boxes.filter(b => b.checked).length;
    out.textContent = `Проверки пройдены: ${n} из ${boxes.length}`;
  }
  boxes.forEach(b => {
    b.checked = !!saved[b.id]; b.closest('li').classList.toggle('ok', b.checked);
    b.addEventListener('change', () => {
      saved[b.id] = b.checked; b.closest('li').classList.toggle('ok', b.checked);
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
      update();
    });
  });
  update();
})();
</script>"""
    html_page = page(D, title=f"Монтаж Compact {D['rev']} — GemilaiMate", desc="Пошаговый ручной монтаж Compact Shield "
                     "GemilaiMate: порядок пайки, карты позиций, ориентация и проверки после каждого шага.",
                     h1=f"Пошаговый монтаж Compact {D['rev']}", current="compact-assembly.html", stamp=STAMP, meta=meta(D),
                     lead="Ручная сборка от голой платы до первой прошивки: что паять на каждом шаге, где это на плате, как "
                          "сориентировать и чем проверить, прежде чем идти дальше.",
                     body=intro + "".join(out), script=script)
    return html_page, "\n".join(md)


def md_text(t):
    """Light HTML → Markdown for the repository copy of the guide."""
    t = re.sub(r'<a href="([^"]+)">([^<]+)</a>', lambda m: f"[{m.group(2)}]({md_link(m.group(1))})", t)
    t = re.sub(r"</?b>", "**", t)
    t = re.sub(r"</?code>", "`", t)
    return html.unescape(t)


def md_link(url):
    if url.startswith(BLOB + "docs/"):
        return url[len(BLOB + "docs/"):]
    if url.startswith((BLOB, RAW)):
        return "../" + url.split("/main/", 1)[1]
    if not url.startswith("http"):
        return PAGES + url
    return url


# ---------------------------------------------------------------- main

def build():
    D = load()
    a_html, a_md = assembly(D)
    return {R / "docs/index.html": landing(D), R / "docs/compact.html": overview(D),
            R / "docs/compact-purchase.html": purchase(D), R / "docs/compact-assembly.html": a_html,
            R / "docs/compact-assembly.md": a_md}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    stale = []
    for path, text in build().items():
        if a.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(R)))
        else:
            path.write_text(text)
            print(f"written {path.relative_to(R)} {len(text.encode())} bytes")
    if stale:
        sys.exit("stale: " + ", ".join(stale) + " — run tools/build_compact_pages.py")
    if a.check:
        print("PASS landing and Compact pages match hardware/shield-compact")


if __name__ == "__main__":
    main()
