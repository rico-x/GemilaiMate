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

Страницу [docs/wiring.html](wiring.html) генерирует `tools/build_wiring_page.py` из `hardware/carrier/connections.csv`, описания модулей и жгутов в самом скрипте и шаблона `tools/wiring_template.html`; текстура платы встраивается из `previews/board-top.png`. После изменения разъёмов, модулей или превью перезапустить скрипт. `tools/check_project.py` вызывает его с `--check` и падает, если страница устарела. `--fragment PATH` дополнительно пишет страницу без обёртки документа для публикации отдельно.

Проект имеет собственную историю Git и один актуальный набор материалов. Автоматического слияния или отслеживания исходного проекта нет. Полезные исправления переносятся вручную/патчем с адаптацией имён, проверкой лицензии и повторением тестов. При изменении кода обновлять `VERSION`, документацию, отчёты и согласованную пару прошивок; публиковать только текущие артефакты с явно указанным статусом аппаратных испытаний.
