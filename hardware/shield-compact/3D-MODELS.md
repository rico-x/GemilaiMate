# 3D models for revision 0.3.0

The PCB and local footprint libraries use project-relative model paths. Standard component STEP models are bundled from KiCad libraries; see the [KiCad library licence](https://www.kicad.org/libraries/license/).

`USB_C_HRO_nominal.wrl` is a nominal maximum envelope (8.94 × 7.35 × 3.26 mm) made from the [HRO drawing](https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948). It is not a detailed manufacturer STEP. The standard footprint's named STEP is [missing upstream](https://gitlab.com/kicad/code/kicad/-/issues/22139); no different connector model has been renamed to impersonate this part.

ADS1115, MAX31855 and CJMCU models are nominal clone envelopes. Their received boards, pin rows and heights have not been measured. All DNP components have their 3D models hidden; assembly drawings retain their outlines and DNP markings.
