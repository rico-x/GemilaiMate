"""Initialize wx only on a graphical host; pcbnew itself works headlessly."""
import os
import sys
import wx


def application():
    # wxGTK may abort the process before Python can catch an exception if X
    # is absent. Do not construct wx.App on a headless Linux build worker.
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        return None
    return wx.App(False)
