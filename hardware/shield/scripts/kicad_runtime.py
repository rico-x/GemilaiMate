"""Initialize wx only on a graphical host; pcbnew itself works headlessly."""
import hashlib
import os
import sys
import wx


def application():
    # wxGTK may abort the process before Python can catch an exception if X
    # is absent. Do not construct wx.App on a headless Linux build worker.
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        return None
    return wx.App(False)


def seed_uuids(script):
    """Give items created by this script reproducible UUIDs.

    KiCad sorts saved tracks by UUID, so random UUIDs also reorder the board file
    and the Gerber objects on every rebuild. Each script uses its own seed so the
    UUIDs it adds never repeat those already saved by an earlier step.
    """
    import pcbnew
    pcbnew.KIID.SeedGenerator(int(hashlib.sha256(script.encode()).hexdigest()[:8], 16))
