# Разработка и сборка

Для сборки нужен только этот репозиторий, Python 3.12, Node.js 22 или новее с npm, Git при получении исходников и доступ к реестрам обычных внешних библиотек. ZIP исходников также собирается: версия читается из `VERSION`, Git-теги родительского проекта не используются. BLE-библиотека весов включена в `firmware/lib/`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
sh tools/run_host_tests.sh
.venv/bin/python tools/test_flash.py
.venv/bin/python tools/build_release.py
```

`build_release.py` собирает веб-интерфейс, затем controller/display и LittleFS, проверяет образы esptool, создаёт `releases/firmware/` и ZIP текущей версии. Последовательность сохраняет BIN каждой цели до переключения окружения PlatformIO. `--skip-web` допустим только при уже собранном актуальном Web UI. Прямой `pio run -e display` без Web assets завершается ошибкой, чтобы не получить приложение с пустым интерфейсом.

Ручные команды из `firmware/`: `bash scripts/build_webui.sh`, затем `pio run -e controller`, `pio run -e display`, `pio run -e display -t buildfs`. Host-сценарии запускаются отдельным shell-скриптом; дополнительные Unity-тесты: `pio test -e native`.

KiCad 10.0.7 использован для текущих производственных файлов. Открыть `hardware/carrier/gemilaimate-carrier.kicad_pro`; локальные библиотеки находятся рядом. После правки схемы/PCB обязательно повторить ERC, заполнить зоны, DRC с `--schematic-parity` и все уровни важности, сверку GPIO и экспорт производства. Команды экспорта реализованы в `tools/export_hardware.py`. Для скриптов pcbnew нужен Python, поставляемый с KiCad; для PDF и проверки netlist - Python из venv.

3D-модели назначены в посадочных местах PCB и локальной библиотеки: стандартные берутся из `${KICAD10_3DMODEL_DIR}`, собственные - из `hardware/carrier/GemilaiMate.3dshapes/` через `${KIPRJMOD}`. Упрощённый DevKit и колпачки перемычек генерирует `hardware/carrier/scripts/make_3d_models.py`; модуль ESP32-S3-WROOM-1 взят из библиотеки KiCad. Модели влияют только на 3D-вид, не на Gerber. `export_hardware.py` пересоздаёт три рендера `previews/assembled-3d-*.png`.

Страницы подключения [docs/wiring.html](wiring.html) (carrier) и [docs/shield-wiring.html](shield-wiring.html) (shield) генерирует `tools/build_wiring_page.py` из `connections.csv` своего варианта, для shield также из `design.json` (контуры модулей в гнёздах, ответные колодки, крепёж, зона USB). Описания модулей и жгутов — в самом скрипте, шаблон общий: `tools/wiring_template.html`; текстура платы встраивается из `previews/board-top.png`. После изменения разъёмов, модулей или превью перезапустить скрипт. `tools/check_project.py` вызывает его с `--check` и падает, если какая-либо страница устарела. `--fragment PATH` дополнительно пишет страницу carrier без обёртки документа для публикации отдельно. Workflow `.github/workflows/pages.yml` при изменении страниц в `main` публикует их на [GitHub Pages](https://rico-x.github.io/GemilaiMate/wiring.html).

Проект имеет собственную историю Git и один актуальный набор материалов. Автоматического слияния или отслеживания исходного проекта нет. Полезные исправления переносятся вручную/патчем с адаптацией имён, проверкой лицензии и повторением тестов. При изменении кода обновлять `VERSION`, документацию, отчёты и согласованную пару прошивок; публиковать только текущие артефакты с явно указанным статусом аппаратных испытаний.

## Второй аппаратный вариант shield

Carrier v0.1 сохраняется в hardware/carrier. Shield v0.2.4 — в hardware/shield; файл gemilaimate-shield.kicad_pro открывается отдельно, со своими локальными библиотеками. Общая прошивка остаётся v0.1.0, исходники firmware не менялись.

Проверка: `.venv/bin/python tools/check_project.py` проверяет оба варианта. Для восстановления shield из актуального carrier: KiCad Python запускает `hardware/shield/scripts/make_shield.py`, затем `route_shield.py`; обычный Python запускает `make_schematic.py`. Полный электрический/CAM экспорт: `.venv/bin/python tools/export_shield.py --kicad-cli /path/to/kicad-cli --kicad-python /path/to/kicad-python`. Скрипт останавливается при любом ERC/DRC/unconnected/parity и формирует отдельный prototype ZIP.

Для PNG из SVG требуется CairoSVG из requirements-dev.txt и системный Cairo (на macOS Homebrew: cairo). Если динамический загрузчик не находит библиотеку, запускать экспорт с `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:/usr/lib`. Рабочая установленная копия KiCad в текущей сессии находится на смонтированном томе `/Volumes/KiCad/KiCad/KiCad.app`; пути не зашиты в исходники.

`tools/build_shield_page.py` создаёт docs/shield.html и шаблон SVG 1:1 из design.json и текущих рендеров; `--check` выявляет устаревшие файлы. Страница carrier и её 3D сохраняются, shield имеет свою страницу рендеров и отдельную страницу подключения с 3D. Pages публикует все три. Сохранённая нулевая DRC не означает измеренную геометрию модулей: допущения перечислены в module-profiles.json и docs/shield.md.

### Headless Linux rebuild

KiCad 10.0.7 supplies system pcbnew/wx. Create an environment with access to those system modules, then regenerate without DISPLAY:

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install sexpdata==1.0.2 CairoSVG==2.9.1
env -u DISPLAY .venv/bin/python tools/rebuild_shield.py --kicad-python /usr/bin/python3 --kicad-cli /usr/bin/kicad-cli
```

`kicad_runtime.py` imports wx but does not create wx.App on Linux without DISPLAY: wxGTK may abort before a Python exception can be caught. Graphical macOS initialization is preserved. The rebuild checks pad-1 shape, silk outlines/labels, nominal module/plug/cable/M3 envelopes, ERC/DRC/parity, CAM outputs and both pages. Real parts, external power-module placement, retention and machine fit remain unverified.

### Ревизия и воспроизводимость shield

Номер ревизии и дата проекта shield задаются только в [hardware/shield/revision.json](../hardware/shield/revision.json). Скрипты берут их для штампа PCB и схемы, надписи на плате, имени архива, manifest и страниц. `check_shield.py` падает, если в README, docs или `hardware/shield/manufacturing/*.md` упоминается другая версия shield или рядом лежит архив прежней ревизии. Повышение ревизии: правка revision.json, полная пересборка, затем исправление текстов, на которые укажет проверка.

Пересборка из неизменённых исходников на той же сборке KiCad даёт побайтно те же файлы:
- UUID новых объектов KiCad задаются от имени скрипта через `KIID.SeedGenerator`, в схеме — от позиционного обозначения и контакта;
- метки времени в Gerber, Excellon, отчётах ERC/DRC, netlist и SVG приводятся к дате из revision.json;
- ZIP собирается с фиксированными датами записей;
- 3D-рендеры перерисовываются только при изменении PCB (`previews/renders.json`), так как трассировщик лучей не повторяем.

Поэтому дифф ревизии показывает только реальные изменения.

Проверки:
- `tools/verify_cam.py` (нужен только kicad-cli): свежие ERC/DRC сохранённых carrier и shield без нарушений, Gerber/Excellon, выгруженные сейчас из сохранённых PCB, совпадают с закоммиченными, архив и manifest shield согласованы.
- `tools/compare_shield_rebuild.py` после `rebuild_shield.py`: рабочее дерево совпадает с HEAD с точностью до сборки KiCad и меток времени. Если отличается сам файл платы, он сравнивается через pcbnew: дорожки, переходы, площадки и тексты точно, площадь заливок до 0,01 мм².

CI-задача «KiCad 10 reproduction» в контейнере `kicad/kicad:10.0.7` выполняет обе проверки, пересобирая shield с `--no-previews`.

`silk_clearance.py` enumerates every visible front/back silk text and footprint field, requiring its native bounding box to clear every via by 0.15 mm. `check_shield.py` independently compares the report inventory with PCB text objects, so adding a label requires no whitelist update. Track clearance remains mandatory for DC+, MAX31855 and ROBOTDYN CABLE only; other track overlap counts are informational. This cosmetic check supplements the unchanged electrical DRC.

Run `python tools/test_silk_clearance.py` in a Python environment with KiCad's `pcbnew` and `sexpdata`. The four regressions restore the old J2/CH1 positions, add an unlisted back-side label over a via and remove a report entry. All must be rejected; the working PCB is never saved or modified by these tests.
