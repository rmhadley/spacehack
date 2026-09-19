# DESIGN: Loot — Dropped-Loot Polish + Interesting Finds

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Draft opened 2026-09-19; the user's four
polish notes and the full open-question pass (same day) are
settled below. Remaining opens are prose-gated or authoring-tuned.

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

### B. The quality system (SETTLED 1-2, open-question pass)

Quality tiers exist on loot; shops stock base items only.
Mechanism (settled): stored items gain a `quality` (default
base) — an authored quality table gives each tier a name token
and percentage multipliers, resolved when the item is
equipped/read. One mechanism covers weapons, armor, AND modules;
catalogs stay descriptive (base stats only); quality rides
existing save/load per instance. Cost: the instance shape
changes everywhere ids are treated as identity (pack, ship
storage, choosers, equip paths, sell prices, tests).

Quality RATES live in authored `1-in-N` tables per drop source —
the exact shape of dig `DOOR_RATES` (`data/digs/__init__.py:
67-71`) — tunable at playtest. Legendary is the fourth rolled
tier and never rolls outside RNG delve bottoms (ruling 4 +
SETTLED 1/2). `TradeGood.rarity` gets deleted (dead field;
trade goods are cargo value, not gear, and don't variant).

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
- **Legendary multi-stat modules** (rulings 4 + SETTLED 1): the
  top rolled tier, delve-exclusive, never shop-stockable; a
  legendary module roll gains extra bonus axes at roll time.
  Doc 43 expects "legendary loot" aboard the far-side find
  (`43_DESIGN_FAR_SIDE.md:59`) — that hookup stays doc 43's.
  Tier tokens/names are PROSE GATE.
- **Ordinary dungeon loot pads** — the surface doc 42 ceded.
  Distinct from teaching pads (knowledge): VALUABLE pads (salvage
  logs, manifests) with trade/credit worth. Exact economy shape
  open.
- **Credits pickups (SETTLED 6): wrecks/digs only** — chips and
  lockboxes as container loot; kill drops stay trade-goods.

## Settled — the open-question pass (2026-09-19)

All nine questions ruled in one sitting. Numbering matches the
question list they replaced.

1. **Quality model: instance tiers for EVERYTHING.** Stored gear
   gains a rolled quality; even legendaries are rolled outcomes,
   not authored uniques — the top tier of the ladder IS legendary.
   For modules, a legendary-tier roll gains extra bonus axes at
   roll time (the multi-stat form of ruling 4); weapons/armor
   legendaries are their own stats at the top multiplier. No
   hand-tuned legendary catalog; legendary identity comes from
   WHERE it rolled (delve bottoms only) and what it carries.
2. **Ladder: three rolled tiers above base, percentage bumps.**
   base → t1 → t2 → t3 → legendary (the rarest tier, reconcile
   with 1: legendary is the fourth rolled tier, delve-gated).
   One authored per-family table applies ~+15/+30/+45%-style
   multipliers to the stats that matter (weapon damage/accuracy,
   armor protection, module bonuses); legendary sits at the top
   multiplier. Tier name tokens are PROSE GATE.
3. **Kit drops: the weapon ALWAYS drops; pools shrink.** Weaponed
   NPCs drop weapon + rolled-size ammo stack every time; authored
   equipment pools become the beyond-the-weapon extras (armor,
   sidearms), re-tuned thinner. Monsters without weapons keep
   their pools.
4. **Selling: everything sells, legendaries too — quality
   multiplies the price.** (Correction from the user during this
   pass, verified: gear sellback ALREADY exists — armory sells
   ground weapons/armor at half catalog price,
   `menus/_armory.py:63`; the mechanic buys and sells ship
   modules, `menus/_mechanic.py:162`; only ammo/consumables are
   unsellable.) Sell price = half catalog × tier multiplier;
   legendaries carry a high multiplier. Watch-item for playtest:
   delve bottom-runs must not out-earn their risk (tune legendary
   rates/multipliers, not the policy).
5. **Colours: category hue + quality brightness.** Hue answers
   WHAT (equipment / field items / cargo / data; mission cargo
   keeps its own colour); brightness answers HOW GOOD once
   quality lands. Exact colours tuned at playtest.
6. **Credits pickups: yes — wrecks/digs only.** Credit chips /
   lockboxes as container loot in wrecks and dig sites; kill
   drops stay trade-goods — the combat economy keeps its
   vendor-trash identity, containers get immediate-reward texture.
7. **Derelicts: keep one-shot, but SAY SO.** The identity stays;
   the stakes become visible before leaving (exit-door wording or
   log line — PROSE GATE). No caching.
8. **Eviction: stay silent.** The 30-entity space cap evicts
   oldest-first with no line.
9. **Phasing: polish first, own phase.** Phase 1 = presentation +
   behavior warts + diegetic kit drops, implemented and
   playtested before any quality work; then quality → modules →
   legendary/credits, each its own implement+playtest cycle.

## Remaining opens (prose-gated or authoring-tuned)

- Quality tier token words, the derelict warning wording, chip/
  lockbox names — PROSE GATE, proposed with their phases.
- Legendary bonus-axis generation for modules (how many axes,
  value ranges) — authored with phase 4, tuned at playtest.
- Chip/lockbox value curve vs. trade-goods income — playtest.
- Section A leftovers still candidate-not-ruled: discard-drops-to-
  floor, ground cap parity, rare-pickup modal. They ride phase 1
  unless red-lined at its brief.

## Phases (SETTLED 9 — polish first, each phase its own cycle)

1. **Polish** — category colour language (brightness arrives with
   phase 2), discard-drops, ground cap parity, diegetic kit drops
   (SETTLED 3: always + pools shrink), derelict one-shot SAY-SO
   (SETTLED 7; wording PROSE GATE). Playtest checklist carries
   the guide-diff item.
2. **Quality system** — instance quality field on stored gear +
   modules, the ladder table (three tiers + rolled legendary
   top, SETTLED 1-2), per-source rates (legendary delve-only),
   sell price × tier multiplier (SETTLED 4), quality brightness
   on glyphs (SETTLED 5), rare-pickup modal,
   `TradeGood.rarity` removal, `DigLootSpec` expansion.
3. **Modules as loot** — payload shape → ship storage,
   boarding/derelict room pools, boarded-ship live `modules`
   drops, mechanic economy check.
4. **Legendary + credits + pads** — legendary module axis
   generation + delve-bottom guarantee, chips/lockboxes in
   wrecks/digs (SETTLED 6), valuable pads, doc-43 hookup. Prose
   gate before any data strings land.
