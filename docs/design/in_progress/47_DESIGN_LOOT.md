# DESIGN: Loot — Dropped-Loot Polish + Interesting Finds

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Draft opened 2026-09-19; the user's four
polish notes are recorded as rulings below — everything else stays
open until a refine session says so.

Companions: `42_DESIGN_LORE_RUMOR.md` (this doc inherits its
deferrals); `19_DESIGN_GROUND_AMMO_AND_FIELD_ITEMS.md` (field-item
model); `43_DESIGN_FAR_SIDE.md` (a legendary consumer);
`SYSTEMS.md` "Loot" / "Quest loot security" entries.

## The lineage this doc serves

Doc 42 explicitly deferred three surfaces here:

- **SETTLED 21 (user, 2026-09-12):** "Let's just focus on the
  system. The legendary loot will be a new phase or even a new
  design doc. I'm thinking like: multi-purpose ship modules. A
  shield generator AND cargo space all in one module slot?"
  Dungeons shipped with placeholder loot until then.
- **SETTLED 35:** the dig-site cache loot is "a pluggable config,
  not a hardcoded pile" — "the future loot doc expands this config
  in place" (`data/digs/__init__.py` `DigLootSpec` docstring says
  the same: "no code change, just fields").
- **Phase-5 stop point (2026-09-14):** "no ordinary dungeon loot
  pads (the truth pad is the ONLY in-dungeon pad — the future loot
  doc owns that surface)". The in-dungeon pad surface is ours.

Plus the standing ask (2026-09-19): **a polish pass on how dropped
loot currently works, then new, more interesting loot.**

## Rulings — the user's polish notes (2026-09-19, verbatim)

> 1. Loot should make sense. If you kill a pirate with a kinetic
>    pistol, it should drop a kinetic pistol and ammo for it.
> 2. I want a loot quality system. Right now all loot is static.
>    You can equip yourself from stores with basic things. But I
>    want more interesting variants of the base loot.
> 3. Ship module loot needs to be a thing. I want to be able to
>    find and loot a shield generator. Possibly makes sense when
>    raiding a ship or a derelict.
> 4. Legendary loot will be the rarest quality loot and found in
>    the RNG delves you discover from datapads/rumors. Multi stat
>    ship modules.

What each rules, grounded:

1. **Diegetic drops — the kit you fought is the kit that drops.**
   The enemy's actual weapon already exists at runtime:
   `NpcCharSpec.weapons[0]` or a seeded `weapon_pick` roll,
   resolved into `GroundEnemyInstance.weapon_id` at first
   engagement (`combat/_rules_ground.py:170-174`). On kill, that
   weapon drops, plus a stack of its `ammo_type` field items
   (`GroundWeaponSpec.ammo_type`; melee/infinite weapons drop no
   ammo). Authored pools (`equipment_loot_pool` etc.) become what
   they carried BEYOND their weapon — armor, sidearms — not a
   random replacement for it. Monsters (no `weapons`) keep their
   pools unchanged.
2. **A quality tier system on loot.** Shops stock the base items;
   interesting variants come from LOOT — that's the economy's new
   identity. Load-bearing fact: owned gear has NO per-instance
   state today — `StoredGroundEquipment` is a frozen
   `(item_type, item_id)` pair (`ground_equipment.py:85-89`) and
   ship storage holds plain module ids (`ship.py:139`). Variants
   therefore need item INSTANCES (a quality field on the stored
   item, resolved against an authored quality table) — see B
   below. Field items (ammo/consumables) are stacks and stay
   unvarianted.
3. **Modules are loot.** A new module payload shape (pickup → ship
   global storage), sourced from boarding captures and derelicts.
   Two feeders, both diegetic: room-typed wreck pools gain module
   entries (`slot_type` "engine"/"system" maps naturally onto
   engine_room/systems rooms), and — the strong form — a boarded
   ship drops from ITS OWN `modules` list, which already rides
   into combat on every `EnemyInstance` (`combat/_stats.py:257`):
   raid the ship that was actually flying that shield generator.
4. **Legendary = the rarest quality tier, RNG delves only.** The
   dig sites discovered from datapads/rumors (doc 42 phase 4) are
   the exclusive source; the legendary form is multi-stat ship
   modules (the SETTLED 21 seed note). Placement follows
   environment-as-gate: the delve's danger self-selects.

## Current state — the audit (2026-09-19, code-anchored)

One representation: every floor item is a `world.Entity` with
`char="%"` and a `loot_data` dict (`world.py:320-362`). Five
payload shapes dispatch at `loot.py:605-619`: trade goods
(`good_id`+`quantity` → hold), equipment (`item_type`/`item_id` →
Expedition Pack), field-item stacks (+`quantity`), quest caches
(`goods` list, secured, never sellable), and pads (`teaches` /
`reveals_site`, consumed on pickup).

**Where loot comes from:**

- Ground kills (`combat/_rules_ground.py:740-767`): 1-2 trade
  goods + 0-1 tier-gated equipment + 0-N field items, all on the
  corpse tile; maybe a site-reveal pad. Drop pools live on
  `NpcCharSpec` (`data/npc_chars/`).
- Space kills: exterior debris via `_spawn_loot_drops`
  (`combat/_actions.py:154-193`), capped at 30 entities
  (oldest evicted — silently).
- Authored wreck/delve interiors: `loot_budget` → ≤4 scatter
  passes over per-room pools (`dungeon_layout.py:19-26, 306-347`).
- Dig sites: `DigLootSpec` placeholder — the planet's own
  `produces`, tier+floor-scaled qty (`digs.py:324-357`).

**Pickup:** `P` → 9-cell find → single-take or "CHOOSE LOOT"
modal (`loot.py:26-93`). Feedback is log lines only. Full pack
opens a drop-one chooser whose "drop" spawns a floor entity.

**The warts (each is a polish candidate):**

1. **One undifferentiated glyph.** Every loot is `%`; fg colour
   encodes the SOURCE (gold = kills/pads/quest, green = authored
   containers/caches, cyan = mission cargo), which tells the
   player nothing about the CONTENT. You can't tell a rifle from
   rations from a data pad without pressing P.
2. **Discard destroys** (`character_screen.py:491-502`): the
   character screen deletes items, while the pack-full swap drops
   them to the floor — two behaviors for the same verb, and the
   destructive one wins.
3. **No ground-loot cap** — only the space path enforces
   `_MAX_LOOT_ENTITIES = 30`. A big ground fight stacks entities
   without bound (all on corpse tiles).
4. **No examine** of floor loot; the chooser label (name + count)
   is the only pre-commit information.
5. **Generic derelicts are one-shot** (`game_interactions.py:
   686-698`): interior never cached — leave, and any floor loot
   left inside is gone. Boarding/salvage/main-quest interiors all
   persist (`ctx.interiors`); derelicts are the outlier.
6. **`TradeGood.rarity` is a dead field** (zero consumers,
   SYSTEMS.md flags it) — a rarity half-system that never landed.
7. **Vendor-trash identity.** Kill drops and scatter are trade
   goods → hold → sell. The only decisions loot poses today are
   pack space and detour cost. (This is the "interesting" gap.)

## First-pass shape (for review — nothing settled)

### A. Presentation + behavior polish (phase 1 candidates)

- **Colour = category, not source.** Keep `%` as the loot family
  glyph; recolour by payload category, identically at every
  constructor site (kill drops, scatter, caches, pads, mission
  cargo, pack-full drops — seven spawn paths; the parallel-twins
  rule applies, audit them all). A player learns the palette once
  and reads a floor at a glance. Exact colours from the existing
  Palette accents; source distinctions that matter (mission cargo)
  keep their distinct colour.
- **Discard drops, never deletes.** One drop mechanism everywhere
  (uniform with the pack-full swap). The floor entity already
  round-trips save/load.
- **Ground cap parity**: same 30-entity oldest-eviction the space
  path uses.
- **Rare pickups get a modal beat** (common ones stay log lines):
  the penalties-are-modals ruling read symmetrically — gains the
  player must not miss get a modal. Applies once rarity exists.

### B. The quality system (ruled in — model open)

Quality tiers exist on loot; shops stock base items only. What's
open is the mechanism:

- **(i) Instance quality field (recommended):** stored items gain
  a `quality` (default base); an authored quality table gives
  each tier a name token and stat modifiers, resolved when the
  item is equipped/read. One mechanism covers weapons, armor,
  AND modules; catalogs stay descriptive (base stats only);
  quality rides existing save/load per instance. Cost: the
  instance shape changes everywhere ids are treated as identity
  (pack, ship storage, choosers, equip paths, tests).
- (ii) Authored variant rows (`kinetic_pistol_mk2`…): no
  instance state, registries unchanged — but every catalog ×
  every tier multiplies rows, pools must enumerate variants, and
  tech-tier filtering/shop exclusion fight the flat registries.

Quality RATES live in authored `1-in-N` tables per drop source —
the exact shape of dig `DOOR_RATES` (`data/digs/__init__.py:
67-71`) — tunable at playtest. Legendary never rolls outside RNG
delve bottoms (ruling 4). `TradeGood.rarity` gets deleted either
way (dead field; consume-or-remove resolved as remove — trade
goods are cargo value, not gear, and don't variant).

`DigLootSpec` expands in place per SETTLED 35: fields for quality
rates, a rare cache variant, an out-of-produce pool, and the
legendary bottom-floor guarantee — per-planet authoring through
`dig_*` spec fields, planets inherit defaults.

### C. New loot (ruled in — shapes open)

- **Ship modules as loot** (ruling 3): new payload shape
  (`{"item_type": "module", "item_id": …}` → ship global
  storage), from boarding captures + derelicts via room-typed
  pools (engine rooms → engine-slot modules, systems rooms →
  system-slot), and the diegetic strong form: boarded ships drop
  from their own live `modules` list. Modules are quality-variant
  gear (ruling 2) — a found shield generator can be a good one.
- **Legendary multi-stat modules** (rulings 4 + SETTLED 21):
  `ModuleSpec` already expresses multi-axis bonuses; legendaries
  = 2-3 bonus axes, delve-exclusive, never shop-stockable. Doc 43
  expects "legendary loot" aboard the far-side find
  (`43_DESIGN_FAR_SIDE.md:59`) — that hookup stays doc 43's.
  Names/descriptions are PROSE GATE.
- **Ordinary dungeon loot pads** — the surface doc 42 ceded.
  Distinct from teaching pads (knowledge): VALUABLE pads (salvage
  logs, manifests) with trade/credit worth. Exact economy shape
  open.
- **Credits pickups** — still open (see questions): no direct-
  money drop exists today; credit chips would change the
  economy's texture.

## Open questions (for the refine)

1. Quality model (i) instance field vs (ii) variant rows —
   recommendation on the table is (i).
2. The quality ladder itself: how many tiers between base and
   legendary, their name tokens (PROSE GATE), and what a tier
   modifies (flat bumps? multipliers? a bonus re-roll?) — per
   item family or one table?
3. Diegetic kit (ruling 1): does the weapon ALWAYS drop, or roll?
   And do authored equipment pools shrink to armor/sidearms, or
   retire entirely for weaponed NPCs?
4. Do found modules sell (is there module sellback at all?), and
   does quality multiply sell value? Includes the legendary
   sellability question — a sellable legendary converts delve
   risk into a credit printer.
5. Colour-by-category palette — which categories get which
   accents, and does mission cargo stay cyan?
6. Do credits pickups exist? (If yes: payload shape and sources.)
7. Generic derelicts: cache their interiors (uniform with every
   other interior) or keep one-shot as the derelict identity —
   and if kept, does the player get to know the stakes before
   leaving?
8. Does the space-path silent eviction get a log line?
9. Scope check: is the polish pass (A + ruling 1) its own
   phase/commit before quality/modules, or do they land together?

## Phases (skeleton — restructured at refine like doc 42's were)

1. **Polish** — colour language, discard-drops, ground cap,
   diegetic kit drops (ruling 1). Playtest checklist carries the
   guide-diff item.
2. **Quality system** — instance field (or ruling otherwise),
   quality table, per-source rates, `TradeGood.rarity` removal,
   rare-pickup modal, `DigLootSpec` expansion.
3. **Modules as loot** — payload shape, boarding/derelict pools,
   boarded-ship `modules` drops, shop-vs-loot economy check.
4. **Legendary + pads (+ credits if ruled in)** — delve-bottom
   legendary guarantee, multi-stat module authoring (PROSE GATE),
   valuable pads, doc-43 hookup. Prose gate before any data
   strings land.
