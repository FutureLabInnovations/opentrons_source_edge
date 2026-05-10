# Dual-Slot Custom Labware — Option 2: Cutout Fixtures + Addressable Areas

This folder explains how Opentrons represents labware that physically occupies
two deck slots, using the Flex deck's "cutout fixture" / "addressable area"
system. **Nothing in this folder modifies the existing codebase** — the file
paths cited below are for reference only.

## Why this is the right approach

The protocol engine does **not** validate labware `xDimension`/`yDimension`
against a 128×85 mm slot footprint at load time. Conflict prevention is
slot-level, not geometry-level (see `api/src/opentrons/motion_planning/deck_conflict.py`
lines 239-268). So if you simply oversize a labware definition and load it
into one slot, the engine will not know the adjacent slot is physically
blocked, and a user could load conflicting labware on top of it.

Cutout fixtures + addressable areas are the mechanism the codebase already
uses for every multi-slot object on the Flex (Thermocycler V2, Trash Bin,
Waste Chute, Staging Areas). Reusing the pattern means the engine reserves
both slots automatically and refuses to place anything else there.

## The three building blocks

The Flex deck definition lives at
`shared-data/deck/definitions/5/ot3_standard.json`. Three concepts there work
together:

### 1. `cutouts`
Physical mounting points on the deck (e.g. `cutoutA1`, `cutoutB1`,
`cutoutD3`). Each has an `(x, y, z)` position. There is one cutout per slot.

### 2. `cutoutFixtures`
What is currently bolted into a cutout. Each entry declares:

- `id` — fixture name
- `mayMountTo` — which cutouts it can attach to
- `providesAddressableAreas` — for each cutout it can mount to, the list of
  addressable-area IDs that become loadable
- `fixtureGroup` — other fixtures that must be co-mounted (this is the key to
  reserving multiple cutouts)
- `height` — fixture's z-extent

A given cutout can host **only one** fixture at a time, so mounting a fixture
on a cutout reserves it.

### 3. `addressableAreas` (and `locations`)
The named places labware can actually be loaded onto. Each has:

- `id` — e.g. `D4`, `thermocyclerModuleV2`, `movableTrashD3`
- `offsetFromCutoutFixture` — `(x, y, z)` offset from the host cutout's origin
- `boundingBox` — `xDimension`, `yDimension`, `zDimension` of the area

The engine refuses to load a labware onto an addressable area unless some
currently-mounted fixture lists that area in `providesAddressableAreas`. This
is the single chokepoint that makes the system safe.

## Two patterns for a dual-slot labware

There are two patterns already in the codebase. Pick whichever matches your
geometry.

### Pattern A — Wide addressable area, single cutout (Trash Bin pattern)

Used when the labware mounts into one cutout but its bounding box extends past
the slot footprint into structurally empty space (a gap between columns, the
deck edge, etc.) — not into another usable slot.

Reference: `trashBinAdapter` fixture (lines 1136-1160 of `ot3_standard.json`)
and `movableTrashD3` addressable area (lines 277-289). The bounding box is
225 × 78 mm and `offsetFromCutoutFixture` is `[-90.25, 4, 0]`. It mounts to a
single cutout but spans well past one slot's worth of x-space.

This pattern does **not** reserve the adjacent slot's cutout. It only works
because the space the labware extends into is not itself a usable slot.

### Pattern B — Two cutouts reserved by `fixtureGroup` (Thermocycler pattern)

Used when the labware truly straddles two real slots that would otherwise be
independently loadable. **This is what most "dual-slot labware" requirements
actually need.**

Reference: `thermocyclerModuleV2Rear` and `thermocyclerModuleV2Front`
(`ot3_standard.json` lines 1264-1298).

Mechanics:

- Two paired fixtures, one per cutout. Both have matching `fixtureGroup`
  entries that say "if I am mounted, the other must be mounted on its cutout
  too."
- The "rear" fixture provides **no** addressable areas (`"cutoutA1": []`) — its
  entire job is to consume the cutout so nothing else can mount there.
- The "front" fixture provides the **single** addressable area that
  represents the whole assembly (`"thermocyclerModuleV2"`).
- That single addressable area has a bounding box and offset chosen to span
  both slots' footprint.

Result: a protocol that requests the dual-slot labware causes the engine to
require both cutouts be occupied by the paired fixtures. Anything else that
tries to load onto either slot is rejected because neither cutout exposes a
plain `A1` / `B1` addressable area while the pair is mounted.

## Concrete example — a dual-slot labware on B3 + C3

Goal: a custom labware that is ~256 × 85 mm and spans cutouts B3 and C3, with
its origin at the front-left corner of C3 (the more "front" of the two slots
on the right column).

The following JSON would be **added** to the Flex deck definition (or a custom
deck definition that extends it). **Do not edit the existing `ot3_standard.json`
file in this repo** — copy it to your fork or load a custom deck definition.

### a) Two paired cutout fixtures

```json
{
  "id": "myDualSlotFixtureFront",
  "expectOpentronsModuleSerialNumber": false,
  "mayMountTo": ["cutoutC3"],
  "displayName": "My Dual-Slot Labware (front half)",
  "providesAddressableAreas": {
    "cutoutC3": ["myDualSlotArea"]
  },
  "fixtureGroup": {
    "cutoutC3": [
      {
        "cutoutC3": "myDualSlotFixtureFront",
        "cutoutB3": "myDualSlotFixtureRear"
      }
    ]
  },
  "height": 0
},
{
  "id": "myDualSlotFixtureRear",
  "expectOpentronsModuleSerialNumber": false,
  "mayMountTo": ["cutoutB3"],
  "displayName": "My Dual-Slot Labware (rear half)",
  "providesAddressableAreas": {
    "cutoutB3": []
  },
  "fixtureGroup": {
    "cutoutB3": [
      {
        "cutoutC3": "myDualSlotFixtureFront",
        "cutoutB3": "myDualSlotFixtureRear"
      }
    ]
  },
  "height": 0
}
```

The `Rear` half exposes no addressable areas — it exists only to occupy
cutoutB3 so no other fixture (and therefore no labware) can mount there.

### b) One wide addressable area

Add to the deck definition's `locations.addressableAreas` list:

```json
{
  "id": "myDualSlotArea",
  "areaType": "slot",
  "offsetFromCutoutFixture": [0.0, 0.0, 0.0],
  "matingSurfaceUnitVector": [-1, 1, -1],
  "boundingBox": {
    "xDimension": 128.0,
    "yDimension": 171.0,
    "zDimension": 0
  },
  "displayName": "Dual-Slot B3+C3",
  "features": {},
  "compatibleModuleTypes": [],
  "orientation": null
}
```

`yDimension` ≈ 2 × 85 mm + the 1 mm gap between slots. Adjust to match real
slot spacing on your deck definition. The offset places the area's origin at
cutoutC3's anchor.

### c) The labware definition itself

Your labware JSON (the file under `shared-data/labware/definitions/2/...`)
keeps its existing well layout but its `dimensions.xDimension` /
`yDimension` reflect the real ~128 × 171 mm footprint. Nothing special is
needed there — it's the deck definition that does the multi-slot work.

### d) Loading it from a protocol

```python
labware = protocol.load_labware(
    "my_dual_slot_labware",
    location="C3",          # the "front" cutout, where the addressable area lives
)
```

The robot software resolves "C3" → addressable area `myDualSlotArea` (because
the `myDualSlotFixtureFront` is mounted on cutoutC3) and verifies that
`myDualSlotFixtureRear` is mounted on cutoutB3 because the `fixtureGroup`
constraint demands it. If the deck configuration does not have both halves
mounted, the load fails before any motion is planned.

## What this prevents at runtime

With Pattern B in place:

- A second labware cannot be loaded on B3 — neither `B3` nor any other
  addressable area is provided by the rear fixture.
- A second labware cannot be loaded on C3 — only `myDualSlotArea` is provided,
  and that's already taken by your dual-slot labware.
- Tip-drop / waste-disposal logic that picks fallback locations (see comment
  at `api/src/opentrons/protocol_engine/state/geometry.py:1339`) will see the
  big bounding box and route around it.
- Deck-conflict checks (`api/src/opentrons/motion_planning/deck_conflict.py`)
  see both cutouts as occupied.

## Files in the codebase you'll want to read (don't edit)

| Purpose | Path |
| --- | --- |
| Flex deck v5 (cutouts, fixtures, addressable areas) | `shared-data/deck/definitions/5/ot3_standard.json` |
| Load-labware command (where addressable areas are resolved) | `api/src/opentrons/protocol_engine/commands/load_labware.py` |
| Deck-conflict logic | `api/src/opentrons/motion_planning/deck_conflict.py` |
| Geometry / bounding-box reasoning | `api/src/opentrons/protocol_engine/state/geometry.py` |
| Existing dual-cutout precedent | `thermocyclerModuleV2Rear` / `thermocyclerModuleV2Front` in `ot3_standard.json` (lines 1264-1298) |

## Summary

1. Multi-slot labware is expressed in the **deck definition**, not the labware
   definition.
2. Use a pair of cutout fixtures linked by `fixtureGroup` to lock down both
   cutouts.
3. Have the "primary" fixture expose one wide addressable area; have the
   "secondary" fixture expose nothing.
4. Load your labware onto the primary slot; the engine handles reservation
   of the second slot for free.
