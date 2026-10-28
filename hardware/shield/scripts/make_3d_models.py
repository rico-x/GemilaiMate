#!/usr/bin/env python3
"""Write the simplified VRML parts used by the carrier 3D view (DevKit body, jumper caps).

The DevKit is a visual stand-in: PCB 62.74 x 25.4 mm, header plastic, two USB-C and BOOT/RESET.
The ESP32-S3-WROOM-1 module itself comes from the KiCad library. Geometry is relative to U1 pin 1,
in VRML axes (x right, y up = -footprint y, z up) and KiCad VRML units of 0.1 inch.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'GemilaiMate.3dshapes'
ROW = 22.86                      # lower socket row A, mm from the upper row
SOCKET, HEADER = 8.5, 2.54       # female socket height, DevKit male header plastic
BASE = SOCKET + HEADER           # DevKit PCB underside above the carrier
END_USB, END_ANT = -61.44, 1.30  # DevKit ends relative to pin 1 (USB left, antenna right)


def box(center, size, color):
    (x, y, z), (sx, sy, sz) = center, size
    u = 2.54
    return (f'Transform {{ translation {x/u:.4f} {y/u:.4f} {z/u:.4f} children Shape {{\n'
            f' appearance Appearance {{ material Material {{ diffuseColor {color} specularColor 0.3 0.3 0.3 shininess 0.4 }} }}\n'
            f' geometry Box {{ size {sx/u:.4f} {sy/u:.4f} {sz/u:.4f} }} }} }}\n')


def devkit():
    yc = -ROW / 2
    parts = [box(((END_USB + END_ANT) / 2, yc, BASE + 0.8), (END_ANT - END_USB, 25.4, 1.6), '0.08 0.08 0.10')]
    parts += [box((-26.67, y, SOCKET + HEADER / 2), (55.88, 2.54, HEADER), '0.05 0.05 0.05') for y in (0.0, -ROW)]
    parts += [box((END_USB + 3.3, yc + dy, BASE + 3.2), (7.4, 8.9, 3.2), '0.75 0.75 0.78') for dy in (-5.2, 5.2)]
    for dy in (-9.0, 9.0):
        parts.append(box((END_USB + 12.0, yc + dy, BASE + 2.4), (4.0, 3.0, 1.6), '0.85 0.85 0.85'))
        parts.append(box((END_USB + 12.0, yc + dy, BASE + 3.4), (1.6, 1.4, 0.6), '0.15 0.15 0.15'))
    return parts


def main():
    OUT.mkdir(exist_ok=True)
    for name, parts in [('DevKit_ESP32-S3_N8R8_simplified.wrl', devkit()),
                        ('Jumper_Cap_P2.54mm.wrl', [box((1.27, 0, 5.6), (5.0, 2.5, 6.0), '0.95 0.80 0.10')])]:
        (OUT / name).write_text('#VRML V2.0 utf8\n' + ''.join(parts))
        print('written', OUT / name)


if __name__ == '__main__':
    main()
