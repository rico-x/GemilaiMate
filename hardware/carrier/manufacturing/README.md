# GemilaiMate carrier v0.1 - manufacturing

Use `gerber-drill.zip` for the actual 90x46 mm, two-layer FR-4 board. Separate PTH and NPTH Excellon files are included. F.Paste is included for optional SMD assembly. See ../../../docs/manufacturing.md for materials, budget and CAM requirements.

`BOM-SMD.csv`: 20 placements, 6 types; examples of approved-package MPNs, substitutes require parameter/pinout confirmation. All SMD are on Top. `BOM-THT.csv`: 103 solder contacts with ONE lower socket row populated; DevKit installed last.

`CPL-SMD.csv`: mm; lower-left board corner is (0,0), X right, Y up. Rotation follows KiCad, currently all 0 degrees. Verify U3 SOT-23-5 DBV orientation by pin 1 on page 2 of ../mounting-template-1to1.pdf. `positions-kicad.csv` is raw upper-left KiCad data with negative Y; do not mix coordinate origins.

The manufacturer must agree on rails/panel/fiducials and stencil apertures; bare-board Gerbers contain no production panel. Copper, antenna keep-out, outline and mounting holes must not be modified without review. Compact legend contains 0.8 mm text; agree on readability and assemble using the enlarged drawing. Front/back silkscreen includes Rico-X and the project URL.

Hardware is unbuilt and unvalidated. This is a prototype package. Obtain a quotation/CAM preview before starting production.
