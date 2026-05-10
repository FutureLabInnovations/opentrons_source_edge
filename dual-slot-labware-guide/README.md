# Dual-Slot Custom Labware — Labware-File-Only Approach

This folder explains how to make a custom labware that physically spans two
deck slots **without modifying the engine, the deck definition, or any other
code in the repo**. The whole solution is one labware JSON file.

The file paths cited below are for **reference only** — do not edit them.

## Why this works at all

The Opentrons protocol engine does **not** validate a labware's
`xDimension` / `yDimension` against the 128 × 85 mm slot footprint at load
time. Conflict checking is slot-level, not geometry-level
(`api/src/opentrons/motion_planning/deck_conflict.py:239-268`).
The load-labware command (`api/src/opentrons/protocol_engine/commands/load_labware.py:143-179`)
checks only that the slot you target isn't already occupied — it never asks
"does this fit?".

So a labware whose `dimensions` describe a ~256 × 85 mm body will load into a
single slot without raising an out-of-bounds error. Existing precedent in the
repo: `shared-data/labware/definitions/2/ev_resin_tips_flex_tall_adapter/1.json`
already declares 130.5 × 98 mm — larger than a slot — and ships in production.

## What you actually do

1. Write one labware JSON definition.
2. Set `dimensions.xDimension` / `yDimension` to the real, multi-slot
   footprint of the labware.
3. Use `cornerOffsetFromSlot` to control which direction the labware extends
   away from its anchor slot.
4. Load it with `protocol.load_labware(name, "C3")` like any other labware.

That's it. No deck definition. No cutout fixtures. No engine changes.

## Worked example: a labware spanning B3 + C3

You want a labware that anchors at C3 (front-right) and extends backwards to
cover B3 as well. Total footprint ~128 × 171 mm (two slots stacked in y, plus
~1 mm gap).

Save the file as `my_dual_slot_labware/1.json` (or upload it as a custom
labware through the Opentrons app — both produce the same effect). The exact
path under `shared-data/labware/definitions/2/...` is only relevant if you
were committing it to the repo, which you said you don't want to.

```json
{
  "ordering": [["A1"]],
  "brand": {
    "brand": "Custom",
    "brandId": ["MY-DUAL-001"]
  },
  "metadata": {
    "displayName": "My Dual-Slot Labware",
    "displayCategory": "wellPlate",
    "displayVolumeUnits": "µL",
    "tags": []
  },
  "dimensions": {
    "xDimension": 128.0,
    "yDimension": 171.0,
    "zDimension": 25.0
  },
  "wells": {
    "A1": {
      "depth": 20.0,
      "totalLiquidVolume": 1000,
      "shape": "circular",
      "diameter": 10.0,
      "x": 64.0,
      "y": 85.5,
      "z": 5.0
    }
  },
  "groups": [
    {
      "metadata": {},
      "wells": ["A1"]
    }
  ],
  "parameters": {
    "format": "irregular",
    "quirks": [],
    "isTiprack": false,
    "isMagneticModuleCompatible": false,
    "loadName": "my_dual_slot_labware"
  },
  "namespace": "custom",
  "version": 1,
  "schemaVersion": 2,
  "cornerOffsetFromSlot": {
    "x": 0,
    "y": 0,
    "z": 0
  }
}
```

### What the numbers do

| Field | Effect |
| --- | --- |
| `dimensions.xDimension` | The labware's real x-extent. Used by visualizers, deck maps, the labware-position-check, and tip-drop fallback logic. Set to the real footprint. |
| `dimensions.yDimension` | Same, in y. For a B3+C3 span, ~171 mm (2 × 85 + 1 mm gap). |
| `dimensions.zDimension` | Real height of the labware. |
| `cornerOffsetFromSlot.{x,y}` | Shifts the labware origin relative to the front-left of the anchor slot. Use this to control which adjacent slot the labware extends into. See "Direction control" below. |
| `wells[*].x`, `wells[*].y` | Well positions are measured from the labware's own front-left corner, **not** from the slot. So a well at the geometric centre of a 128 × 171 mm labware sits at (64, 85.5). |

### Direction control with `cornerOffsetFromSlot`

The slot's anchor point is its front-left corner. By default the labware's
front-left aligns there and the labware extends right (+x) and back (+y).

- To extend **back** from C3 into B3 (the example above): keep `y = 0` and use
  the natural y-extent. The labware extends in +y, which on the Flex moves
  toward the rear of the deck — that's B3.
- To extend **forward** from B3 into C3: set
  `cornerOffsetFromSlot.y = -86` so the labware origin sits in front of the
  anchor slot.
- To extend **left** or **right** between columns 1↔2 or 2↔3: shift `x`
  similarly (a slot is 128 mm wide).

Always sanity-check on the deck map in Protocol Designer or the app before
running on hardware — the offset sign conventions are easy to flip.

## Caveats — read these

The engine does not know the second slot is physically blocked. That has
real consequences:

1. **You must not load anything else in the covered slot.** The engine will
   happily let `protocol.load_labware(..., "B3")` succeed even though your
   dual-slot labware is already covering B3 from C3. There is no warning.
   Protect against this in your own protocol code (e.g. comment, lint, or
   simply leave that slot empty by convention).
2. **Deck-conflict checks won't fire.** The motion planner sees one slot
   occupied (your anchor slot), not two.
3. **Move-labware / off-deck moves**: if you reposition this labware
   mid-run, the engine still tracks only one slot. Plan accordingly.
4. **Pipette/gripper paths**: motion planning uses bounding boxes for
   tip-drop fallback and similar; oversized dimensions help here, but
   collision-avoidance during arbitrary moves is still the protocol
   author's responsibility.
5. **App / Protocol Designer rendering**: most tools draw labware using
   `dimensions` so the visual will correctly show the labware spilling into
   the second slot. Some older tooling may clip — verify visually.

If any of those caveats matter, the only way to get the engine to actively
reserve both slots is the cutout-fixture / `fixtureGroup` route used by the
Thermocycler V2. That requires deck-definition edits, which you've ruled out.

## Files in the codebase you may want to read (don't edit)

| Purpose | Path |
| --- | --- |
| Labware schema v2 reference (real oversized labware in production) | `shared-data/labware/definitions/2/ev_resin_tips_flex_tall_adapter/1.json` |
| Load-labware command | `api/src/opentrons/protocol_engine/commands/load_labware.py` |
| Deck-conflict logic (slot-level only) | `api/src/opentrons/motion_planning/deck_conflict.py` |
| Geometry / bounding-box logic | `api/src/opentrons/protocol_engine/state/geometry.py` |

## Summary

- A labware definition with oversized `xDimension` / `yDimension` loads
  without an out-of-bounds error.
- Use `cornerOffsetFromSlot` to point the overhang at the desired adjacent
  slot.
- The trade-off is that the engine doesn't auto-reserve the covered slot —
  your protocol must leave it empty.
