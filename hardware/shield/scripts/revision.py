"""Shield revision and design date: the one place to bump a revision.

Scripts, CAM timestamps, pages and the docs check read hardware/shield/revision.json.
"""
import json, re
from pathlib import Path

_DATA = json.loads((Path(__file__).resolve().parents[1] / 'revision.json').read_text())
REVISION = _DATA['revision']
DATE = _DATA['date']
ARCHIVE = f'gemilaimate-shield-v{REVISION}-prototype.zip'

_STAMP = re.compile(r'(\d{4}-\d{2}-\d{2})([T ])(\d{2}:\d{2}:\d{2})([+-]\d{2}:?\d{2}|Z)?')

def pin_timestamps(text):
    """Replace generation timestamps with the revision date so a rebuild is byte-identical."""
    return _STAMP.sub(lambda m: f'{DATE}{m.group(2)}00:00:00' + ('+00:00' if m.group(4) else ''), text)
