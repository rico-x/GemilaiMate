from pathlib import Path
import os, datetime
Import("env")
root = Path(env["PROJECT_DIR"]).parent
version = root.joinpath("VERSION").read_text().strip()
epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
now = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc) if epoch else datetime.datetime.now(datetime.timezone.utc)
root.joinpath("firmware/src/version.h").write_text(
    '#pragma once\n#define BUILD_PROJECT_VERSION "v' + version + '"\n' +
    '#define BUILD_TIMESTAMP "' + now.strftime("%Y-%m-%dT%H:%M:%SZ") + '"\n')
