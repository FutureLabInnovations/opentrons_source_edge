# Notes — Low-Volume Transfer Optimization (UriSeek)

Session record of the scripts and analysis so far.

## 1. Existing protocol scripts (provided by user)

### Script A — `UriSeek V1 mastermix preparation`
- **Robot:** Flex, apiLevel 2.24. 8-channel 1000 (right) + 8-channel 50 (left), both in `SINGLE` nozzle layout (H1).
- **Purpose:** builds 6 mastermixes in a 96-well PCR plate on a temperature module (4 °C), distributing single-tube reagents into columns so a later 8-channel protocol can run.
- **Defines a custom liquid class `PEG_25`** for viscous reagents (3 pipette/tiprack combos: 1000/1000µL, 1000/200µL, 50/50µL).
- **Mastermixes:** MM1 (3'-adapter + H2O), MM2 (3' ligation enz+buffer), MM3 (SR RT primer dilution), MM4 (5' adapter buffer+enz), MM5 (reverse transcription), MM6 (PCR).
- **Low-volume risk points:** distribute of 5–6 µL adapter/primer via legacy `distribute`; PEG_25 class has `pre_wet=False`, `touch_tip` off, `blowout` off, `air_gap=0`.

### Script B — `UriSeek V1 library preparation`
- **Robot:** Flex, apiLevel 2.24. 8-channel 50 (left) + 8-channel 1000 (right). Thermocycler + temperature module + gripper moves.
- **Purpose:** full automated library prep across 4 sample columns (2,5,8,11): 3'-adapter+H2O, 3' ligation, SR RT primer hybridization, 5'-adapter ligation, reverse transcription, PCR (23 cycles). Beads clean-up + size selection remain manual.
- **Reuses the same `PEG_25` custom liquid class.**
- **Critical low-volume steps identified:**
  - **5'-adapter 1 µL** via legacy `transfer` (`new_tip='never'`, no pre-wet/touch-tip/blow-out/air-gap) → biggest error source.
  - **Index primers 2.5 µL** with weak mixing (`mix_before=(3,3)`, `mix_after=(1,30)`).
  - **5' ligation mix 3.5 µL** via PEG_25 (pre_wet off).
  - Glycerol-50 enzymes (RT, ligase, RNase inh.) pipetted with a class tuned for PEG, no pre-wet.

## 2. Root-cause link to observed problems (adapter dimers / no product)
- Systematic **over-dispensing at 1–2 µL** (+30–63 %D, CV up to 74% per user's Run A/B/C data) distorts the insert:adapter molar ratio.
- Too much adapter → **adapter dimers**; too little enzyme (under-dispense in glycerol) → **no ligation / no product**.
- Mixed-volume ordering (Run B/C) is worse than sequential (Run A) → the library protocol jumps between volumes = worst case.

## 3. Recommended fixes (not yet applied to the protocols)
- **Primary:** redesign to avoid <3 µL steps (dilute 5'-adapter 1:5 → pipette 5 µL; use mastermixes).
- Enable in `PEG_25`: `pre_wet=True`, slower `flow_rate_by_volume` at low end, `air_gap>0`, `touch_tip` on, `blowout` on at destination.
- Add a **separate glycerol-50 liquid class** (even slower, longer delays, higher push-out) for enzymes.
- Improve index-primer mixing (`mix_before=(5,6)`, `mix_after=(5,30)`).
- Group transfers by volume; always fresh tip per reagent.

## 4. Added this session
- **`dual_dye_volume_verificatie.xlsx`** — Excel calculation sheet for dual-dye low-volume (~1 µL) verification on a normal plate reader (BioTek Epoch).
  - Dyes: **Brilliant Blue FCF @630 nm** (volume dye, high ε) + **Tartrazine @450 nm** (pathlength dye); optional 750 nm reference.
  - Ratiometric method with crosstalk correction `k`, empirical calibration constant `K`, per-column stats (mean/%D/SD/CV) with red/orange/green conditional formatting mirroring the user's Run A/B/C tables.
  - Reken-logic validated by physical simulation (agreement ~1e-16 µL).
- **`build_verificatie_rekensheet.py`** — reproducible generator for the xlsx.

## 5. Open / next steps
- (Optional) Opentrons protocol to auto-fill the verification plate (200 µL pre-fill + 1 µL test dispense across columns).
- Apply the liquid-class fixes above to Scripts A & B once verification confirms the correction values.
- Gravimetric cross-check at 10 µL to anchor the photometric calibration.

## 6. Balance / verification hardware notes
- 1 µL water = 1 mg; ISO 8655 allows ±50 µg. Needs **micro/ultra-micro balance** (0.1–1 µg readability) + evaporation trap — semi-micro (10 µg) is marginal, analytical (100 µg) unusable.
- **Artel MVS** (dual-dye ratiometric, 0.01–350 µL, per-channel) is the purpose-built option but €15–25K.
- DIY dual-dye on an existing Epoch (this session's sheet) is the low-cost route for relative QC / tuning `correction_by_volume`.
