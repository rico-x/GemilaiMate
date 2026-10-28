# USB-прошивка GemilaiMate v0.1.0

**Реальная прошивка ещё не выполнялась.** Controller: ESP32-S3 N8R8, 8 MB Flash. Display: LilyGo T-RGB 2.1, 16 MB Flash. Нужны обе сборки GemilaiMate: они используют собственные BLE-идентификаторы. Смешанные пары с другими прошивками не проверены.

Скачать и распаковать текущий `GemilaiMate-v0.1.0-firmware.zip` из Releases. Внутри находятся `flash.py`, `manifest.json`, controller/display и инструкция. Альтернатива - собрать пакет из исходников по docs/development.md.

В каталоге распакованного пакета:

```sh
python3 -m venv .flash-venv
.flash-venv/bin/python -m pip install esptool==4.9.0
.flash-venv/bin/python flash.py controller --port /dev/cu.usbmodemTEST --fresh
.flash-venv/bin/python flash.py display --port /dev/cu.usbmodemTEST --fresh
```

Порт в примере условный: подставить фактический порт одной подключённой платы. Без `--flash` скрипт только проверяет файлы и печатает план; порт не открывается. Для реальной записи добавить `--flash` к команде нужной платы после подготовки стенда. В Windows использовать фактический COM-порт и Python из созданного venv.

`--fresh` записывает bootloader, разметку, OTA-данные, приложение и для дисплея LittleFS. **NVS эта опция не стирает.** Если нужен полный сброс, `--erase-all --fresh` стирает также NVS, Wi-Fi/BLE, настройки, профили и историю. Хеши всех выбранных файлов проверяются до стирания. Без `--fresh` обновляется только app0; применять лишь при соответствующей разметке и OTA-слоте.

Из исходного репозитория можно вызвать `python tools/flash.py controller --package releases/firmware --port ... --fresh`. Проверка прошивальщика: `python tools/test_flash.py`.

Первую запись выполнять на ESP32 отдельно от carrier/кофемашины. При USB контроллера снять JP1; при USB дисплея отключить J9. Проверить схему питания конкретного клона перед объединением USB и внешних 5 В. При необходимости входа в загрузчик: BOOT, RESET, отпустить BOOT. Встроенного сетевого обновления в этой версии нет.
