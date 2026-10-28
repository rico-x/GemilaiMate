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

Проект имеет собственную историю Git и один актуальный набор материалов. Автоматического слияния или отслеживания исходного проекта нет. Полезные исправления переносятся вручную/патчем с адаптацией имён, проверкой лицензии и повторением тестов. При изменении кода обновлять `VERSION`, документацию, отчёты и согласованную пару прошивок; публиковать только текущие артефакты с явно указанным статусом аппаратных испытаний.
