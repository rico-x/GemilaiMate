# Component dimensions and mechanical fit

PCB outline: **75 x 60 mm**, 4 copper layers. This report covers every fitted footprint and the three plug-in daughterboards.

## Fit status

- The component body sizes in the CSV come from manufacturer package drawings when a fixed MPN is selected; generic package envelopes are explicitly marked nominal. KiCad DRC checks the routed footprints and board-edge clearances.
- The ADS1115, MAX31855 and CJMCU-0102 are breakout boards, not fixed bare components. Their clones have not been measured. Their nominal outlines are included in the CAD, but mechanical fit is **not confirmed** until the actual boards, pin rows, terminal, and headers are measured.
- The Harwin M20 sockets provide an 8.5 mm socket body above the carrier PCB. The matching 2.54 mm header plastic gives a nominal daughterboard underside height of about 11.04 mm. Check the selected male headers and actual parts together before building. Optional expansion headers use standard 2.54 mm pitch for easier hand assembly.
- RobotDyn and SSR remain off-board, separately mounted modules. Their footprints and 230 V conductors are intentionally not placed on this low-voltage shield.
- Overall height in the Gemilai case is not cleared: no case-envelope measurement exists. The 75 x 60 mm outline is a design choice, not proof it fits the machine.

## PCB components

See [component-dimensions.csv](../hardware/shield-compact/reports/component-dimensions.csv) for all references, MPN examples, footprints, body envelopes, side, and confidence. Values describe component bodies, not the larger KiCad courtyard.

## Before ordering

1. Print [assembly-top.svg](../hardware/shield-compact/previews/assembly-top.svg) and [board-bottom.svg](../hardware/shield-compact/previews/board-bottom.svg) at 1:1.
2. Measure the received ADS1115, MAX31855, and CJMCU boards including soldered headers, thermocouple terminal, and component overhangs. Confirm CJMCU row pitch and polarity.
3. Place the real modules in the print and check clearances above and below the shield, cable exits, USB access, mounts, and machine-case envelope.
4. Only then freeze mechanical dimensions for fabrication.
