# EpicWorlds50 Development Diary

*Jaking Company World Studio*

## Day 1: 2026-10-24, Milestone 1 (pipeline + 5 worlds)

**Goal:** stand up a reusable world pipeline, then prove it on two real-world wonders and three fantasy realms.

### Pipeline (`SourceFiles/pipeline/ew_core.py`)
- Built every system as a function so any world is roughly 150 lines of "art direction" on top of shared tech:
  terrain, paint layers, sculpt layers, GN scatter, water, clouds, birds, flags, particles, atmosphere,
  Mega Landmark rule, camera rig, preview renders, and metadata export.
- Animation is all **drivers + GN Scene Time**, so it loops forever with zero bakes.
- The Mega Landmark rule is enforced in code: `mega_landmark()` asserts ≥100 m, so a world can't build without one.

### Problems hit and fixed
| Problem | Cause | Fix |
|---|---|---|
| First Giza render was almost black | EEVEE (Blender 5.x) treats a **World volume** as infinite, which swallowed the sky and sun | Moved fog into a bounded `AtmosphereFog` volume with height falloff |
| Sand rendered white | Paint colours were authored in sRGB but written to a linear colour attribute | Convert to linear (`c ** 2.2`) in `terrain()` |
| `use_render_emitter` error | Property was removed from ParticleSettings in Blender 5.x | Rely on `show_instancer_for_render = False` |
| Waterfalls had zero width | Vertical polylines have no XY direction | `ribbon()` falls back to a fixed side vector |
| Ocean too heavy | 30×30 tiles at resolution 12 | 400 m tiles at resolution 7 |
| Hero camera blocked | Giza valley temple sat in front of the lens | Moved the hero camera north-east of the causeway |

### Worlds shipped
- **RW01 Giza Plateau**: real-dimension pyramids, Sphinx, 70+ mastabas, causeway, Nile with palms and fields,
  King's Chamber interior with flickering torches, expedition camp with flags.
- **RW02 Mont-Saint-Michel**: tidal bay with ocean waves, ramparts and towers, 110 procedural houses spiralling the
  rock, Gothic abbey with buttresses, spire and gilded archangel, nave interior, gulls, sea spray.
- **FW01 Chocolate Land**: 420 m Cocoa Volcano with a pulsing caramel crater, 3 chocolate rivers and a chocolate
  waterfall, Sugar Road with candy-cane pillars, gingerbread village, hovering marshmallow clouds, secret Truffle Vault.
- **FW02 Crystal Empire**: 640 m Prism Spire with a floating heart core, 4 pulsing energy beams, 3 rings of hex towers,
  40 hovering shards, starlight river, Echo Caves secret.
- **FW03 Sky Kingdom**: floating continents with sculpted undersides, Storm Temple (tip at 707 m) holding a lightning-flashing
  storm orb, rope bridges, waterfalls into the void, orbiting sky-ships, 60 floating lanterns, cloud sea, sunken bell tower.

### Next milestone
Worlds 6–15 (Colosseum, Taj Mahal, Machu Picchu, Angkor Wat, Petra + Cookie Kingdom, Dragon Realm, Underwater Kingdom,
Mechanical World, Moon Civilization), Cycles texture baking, and the first rendered trailers.
