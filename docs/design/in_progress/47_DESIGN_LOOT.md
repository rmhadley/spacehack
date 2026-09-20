# DESIGN: Loot — Dropped-Loot Polish + Interesting Finds

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Draft opened 2026-09-19; the user's four
polish notes, the full open-question pass, and the phase-2
quality pass (all same day), plus the phase-3 module pass
(2026-09-20), are settled below. Remaining opens are
phase-4-shaped.

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
  player must not miss get a modal. Deferred to phase 4 with the
  legendaries (SETTLED 12).

### B. The quality system (SETTLED 1-2, open-question pass)

Quality tiers exist on loot; shops stock base items only.
Mechanism (settled): stored items gain a `quality` (default
base) — an authored quality table gives each tier a name token
and percentage multipliers, resolved when the item is
equipped/read. One mechanism covers weapons, armor, AND modules;
catalogs stay descriptive (base stats only); quality rides
existing save/load per instance. Cost: the instance shape
changes everywhere ids are treated as identity (pack, ship
storage, choosers, equip paths, sell prices, tests). Design
consequence of the randart ruling: the phase-2 instance field
must anticipate legendary instances carrying a GENERATED
MANIFEST (rolled name + property spread), not just a tier enum —
shape it once so randarts extend it rather than rework it.

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

- **Ship modules as loot** (ruling 3; shape SETTLED 14-16): new
  payload shape (`{"item_type": "module", "item_id": …}` → ship
  global storage), from room-typed pools (engine rooms →
  engine-slot modules, CARGO BAYS → system-slot — no "systems"
  room exists in any layout, SETTLED 15) plus the diegetic
  strong form: an INTACT CAPTURE is stripped of its whole live
  `modules` list at the quality it flew (SETTLED 14/16); dead
  ships yield room scatter only. Modules are quality-variant
  gear (ruling 2) — a found shield generator can be a good one.
- **Legendary randarts** (rulings 4 + SETTLED 1, amended): the
  top rolled tier, delve-exclusive, never shop-stockable. A
  legendary roll generates a randart — name from authored word
  pools, 2-4 rolled bonus axes (the multi-stat form). Doc 43
  expects "legendary loot" aboard the far-side find
  (`43_DESIGN_FAR_SIDE.md:59`) — that hookup stays doc 43's.
  Name-pool fragments and tier tokens are PROSE GATE.
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
   No hand-tuned legendary catalog. Amended same day (user):
   > My ruling on the legendaries rolled is that I want more of a
   > RANDART feel than hand authored uniques. We might add a
   > unique concept later. But first I want randart system.

   Legendary outcomes are RANDARTS (the Qud lineage — doc 39's
   seed notes): a rolled NAME composed from authored word pools
   (the dig-site two-part name pools, `data/digs/__init__.py:
   26-44`, are the in-repo precedent — fragments prose-gated,
   composition seeded so a randart is THE same artifact all run)
   plus a rolled PROPERTY SPREAD — the mash picks 2-4 bonus axes
   with rolled magnitudes (`ModuleSpec` already carries ~11 bonus
   fields to mash; weapons/armor mash their own stat axes).
   Hand-authored uniques are explicitly deferred ("might add a
   unique concept later" — a future doc/phase, the SETTLED 21
   deferral pattern repeating).
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

## Settled — the phase-2 quality pass (2026-09-19)

Four rulings from the quality-system refinement session
(numbering continues the pass above):

10. **Tier tokens (user, verbatim): "modded, overclocked,
    prototype"** — t1/t2/t3, prefixing item names ("Modded
    Kinetic Pistol"; title-cased at the label seam like item
    names). Legendaries carry no token: the rolled randart name
    IS the label (phase 4).
11. **Legendary stays dormant until phase 4.** The ladder table
    carries the legendary multiplier row so sell/read paths ship
    complete, but no phase-2 source can roll it; phase 4 turns on
    delve-bottom rolls and the randart generator together. No
    proto-legendary interim form — a legendary without its rolled
    name is the hand-tuned unique the randart ruling retired.
12. **No rare-pickup modal in phase 2.** The beat defers to
    phase 4, where the legendaries (the modal-worthy event) land;
    t1-t3 pickups stay log lines.
13. **Kit weapons roll quality at NPC EQUIP time (user,
    verbatim):** "yes. but the roll should happen at npc equip
    time. if you get a t3 weapon from an npc, that means the npc
    was firing a t3 weapon at you." The diegetic strong form: the
    enemy's wielded weapon is quality-variant, its combat stats
    scale with the quality, and the kill drops THAT instance — no
    re-roll at death. Beyond-the-weapon extras (armor, sidearms)
    roll at drop time with the same kill-source rates.

## Settled — the phase-3 module pass (2026-09-20)

Three rulings from the module-loot refinement session (numbering
continues the passes above):

14. **Module quality flies with the ship (SETTLED 13, extended
    to space).** Ships in combat roll their installed modules'
    quality at combat entry (KILL rates, per-module, seeded);
    their hull/shield/gunnery/etc. scale with the rolled tiers;
    an intact capture drops THOSE instances — no re-roll. Dead
    ships (wrecks, derelicts, mission salvage — hulls that never
    fought back) roll at interior-build time through the WRECK
    ladder. Two seams, each the space twin of its ground
    precedent: flown modules = the wielded weapon (equip-time),
    room scatter = the carried extras (drop-time).
15. **Room pools: engine_room hosts engine-slot modules,
    cargo_bay hosts system-slot.** No layout edits — the audit
    found NO "systems" room type in any of the eight authored
    ship layouts (only engine_room, mess_hall, personal_storage,
    cargo_bay carry LOOT markers), so system modules take the
    cargo bay (spare-parts-in-crates framing). Data-only pools
    mirroring phase-2's `_ROOM_EQUIPMENT_POOLS` + 1-in-N rate.
16. **The live-`modules` drop is intact captures only — the
    whole installed list.** A captured ship is stripped of
    everything it flew; a destroyed-then-boarded wreck's
    hardware died with the hull, so dead ships (mission wrecks
    and derelicts included) yield room scatter only.
17. **No module is excluded from loot, structurally (user,
    2026-09-20).** The phase-3 pool contents are an authored
    opening guess, not a system ban — every module id can drop
    through the payload, pool, and capture-strip paths, and
    nothing in the build may bar a module from the wild
    ("as long as in 47.3 we aren't excluding the future option
    of these modules being found in the wild"). Themed capture
    sources are ruled WANTED and seeded in doc 48 (same day,
    verbatim): "more detailed ship specs that have modules
    installed that make sense for them and their hull" —
    "Capturing a pirate ship would definitely be a solid path
    to finding a smugglers hold. Capturing a merchant would be
    a solid path to finding a cargo hold."
18. **Scaled stats round fractions UP, always (user, playtest
    ruling 2026-09-20): "Round up always (ceiling)".** Exact
    half-up let a tier round a bump away at small magnitudes —
    a Modded Stun Baton read the same damage 2 as its base
    (2 x 1.15 = 2.3 -> 2). Ceiling in magnitude at both signs:
    every nonzero scaled stat visibly moves at every tier; a
    tier never lands on its base value. Values already rounding
    up are unchanged; the <0.5 fractions (stun baton 2 -> 3,
    Compact Reactor speed 1 -> 2 at t1-3, Armor Plating's -1
    draw -> -2 at t1) gain 1. Sell prices keep their own
    formula (unchanged).

## Remaining opens (phase-4-shaped or authoring-tuned)

- Randart specifics — property spread (axis count, magnitude
  ranges) and whether randarts can carry TRADEOFFS/drawback axes
  (the Qud pattern) or are pure upside; name-pool register
  (call-signs? relic style?). Authored with phase 4; fragments
  PROSE GATE. Hand-authored uniques stay deferred (SETTLED 1
  amendment) — not a phase-4 item.
- Rare-pickup modal shape + strings (SETTLED 12 moved it to
  phase 4) — PROSE GATE with its phase.
- Chip/lockbox names + value curve vs. trade-goods income —
  phase 4; PROSE GATE / playtest.

## Phases (SETTLED 9 — polish first, each phase its own cycle)

- [x] 1. **Polish** — category colour language (brightness arrives
  with phase 2), discard-drops, ground cap parity, diegetic kit
  drops (SETTLED 3: always + pools shrink), derelict one-shot
  SAY-SO (SETTLED 7; wording PROSE GATE). Playtest checklist
  carries the guide-diff item. **CLOSED 2026-09-19** — built in
  five steps (1f188f7, ae06f7e, 8651635, 64dcc63, 782efca; the
  build survived a mid-session PC crash and a reviewer-outage
  fallback), all 9 playtest items PASSED (guide diff: none, as
  expected). SYSTEMS.md audited at close.
- [x] 2. **Quality system** — instance quality through the equip
  round-trip (stored entries + weapon instances + the
  equipped-armor dict migration), the ladder table (three tiers
  + dormant legendary row, SETTLED 1-2/11), NPC equip-time
  weapon rolls (SETTLED 13), per-source drop rates (legendary
  unroll-able until phase 4), sell price × tier multiplier
  (SETTLED 4), quality brightness on glyphs (SETTLED 5), tokens
  modded/overclocked/prototype (SETTLED 10), `TradeGood.rarity`
  removal, `DigLootSpec` quality rates. No rare-pickup modal
  (SETTLED 12 — phase 4).
  **BUILT 2026-09-19** in seven reviewed commits (4080e2e quality
  data module; 596fe7d instance threading; 3f8a896 armor-dict
  migration; f40e82e combat scaling; 9d36095 drop-time rolls;
  4c5a784 labels/brightness/sell; d5f329e rarity removal) — every
  code commit reviewer-gated (three rounds came back
  REQUEST_CHANGES: deadshot chain + HUD readouts unthreaded; false
  test pins + a band-2 tech leak; a stray-async manage-chooser
  regression + reload/attack-line label seams — all fixed and
  re-reviewed). **CLOSED 2026-09-20 — PLAYTEST PASSED** (the only
  feedback: enemies don't scale with site difficulty, which became
  the seed for doc 48); guide entry USER-APPROVED verbatim and
  landed (e496383, one bitmap-gate accommodation: em-dash →
  hyphen). SYSTEMS.md audited at close (quality-system entry
  added; kill-drops, loot presentation, dig-caches, and Absent
  entries amended).
- [ ] 3. **Modules as loot** — payload shape → ship storage,
  room pools (engine_room → engine-slot, cargo_bay →
  system-slot, SETTLED 15), the capture-only live-`modules`
  strip at flown quality (SETTLED 14/16), installed-module
  instances through install/store/sell/save (mechanic economy:
  half catalog × multiplier, SETTLED 4), the module quality
  family row. Brief PROPOSED 2026-09-20 (below).
  **BUILT 2026-09-20** in eight reviewed commits (0e40bcf quality
  family row + effective_module_spec; 3174f81 stored/installed
  instance migration + save migration; cce36ce pickup branch +
  display seam + glyph hue; 187eb02 review fix — _ship_menu stat
  helpers delegated to the shared sums; 32f79fa enemy fly-time
  rolls + boarded_modules stamp; dcda6e5 capture strip at
  engine-room markers; 81452dc wreck room module pools; 7d48d0d
  sell × multiplier + review minors). Two reviewer rounds came
  back REQUEST_CHANGES (the 3174f81 sweep missed the menu readers
  and the buy-path install; the hangar stat helpers silently
  dropped entries) — all fixed and re-reviewed. Playtest
  checklist below; guide entry NOT landed (approval-gated with
  the playtest, phase-2 precedent).
- [ ] 4. **Legendary randarts + credits + pads** — the randart
  generator (seeded name composition from word pools + property
  spread over `ModuleSpec`'s bonus axes), legendary activation
  (delve-bottom rolls turn on, SETTLED 11), the rare-pickup
  modal (SETTLED 12), chips/lockboxes in wrecks/digs (SETTLED 6),
  valuable pads, doc-43 hookup. Prose gate before any data
  strings land.

## Pre-implementation audit — phase 1 (2026-09-19)

**Reuse (verified):**

- Floor items are one representation: `world.Entity(char="%",
  loot_data=…)` — colour is construction-time `fg`; the renderer
  already honors it. No renderer work needed.
- Spawn helpers to build on: `combat/_actions.py`
  `_append_loot_entity` + the three `_spawn_*_at_position`
  functions; `_MAX_LOOT_ENTITIES` + the inline eviction inside
  `_spawn_loot_drops` (the extraction source).
- `on_kill(game_map, enemy: GroundEnemyInstance, ctx)`
  (`combat/_rules_ground.py:740`) — the resolved weapon is
  already on the instance (`enemy.weapon_id`); no entity
  stamping, no `world.py` touch.
- `loot.py` `_drop_expedition_entry_at_loot` /
  `_drop_expedition_stack_at_loot` — the pack-full drop path
  discard reuses (parameterized from loot-position to any
  position).
- Derelict discriminator: every persisted interior stamps
  `location_name` (boarding `:823`, digs `:204`, city, surfaces);
  the generic derelict map never does. The build stamps
  `"Derelict Ship"` explicitly in `_build_generic_derelict` and
  the say-so gates on it at `_handle_dungeon_exit` top.
- Confirm-modal pattern: `_run_pygame_exit_confirm` (game_flow).
- Character-screen context flags have a precedent
  (`in_ground_combat=True` from ground combat — the ONLY combat
  caller; floor always exists there).
- Mode strings: `'space' | 'city' | 'dungeon'`; the C handler
  chain has `state.current_mode` at `_handle_menu_event`.

**Duplication hotspots:**

1. Seven constructor sites each hard-coding `fg` (the wart
   itself) — copy-paste risk grows with every new source.
2. Discard vs pack-full drop: two paths about to spawn pack
   entries as entities.
3. Cap eviction: space's inline block vs the new ground need —
   a born twin.
4. `combat/_rules_ground.py` sits at 999 lines — the kit-drop
   step cannot add lines without breaching the 1000 ratchet.

**DRY strategy:**

1. New leaf module `loot_common.py`: pure table-driven
   `loot_fg(loot_data, mission=…)` + `is_protected_loot(entity)`
   + `enforce_loot_cap(game_map)`; imports only `world` —
   cycle-proof from every constructor site.
2. Discard reuses the pack-full helpers after parameterizing
   the drop position.
3. The cap lives once in `loot_common`, called by both paths —
   and fixes the space path's missing exemption in the same
   commit.
4. `on_kill`'s four drop blocks extract to
   `combat/_actions.spawn_kill_drops(game_map, pos, spec, ctx)` —
   landed 981 lines, ratchet holds, drop sequence reads as one
   unit. The `weapon_id` parameter arrives with step 4 (diegetic
   kit drops).

**Data-first:** `GroundWeaponSpec.loot_droppable: bool = True`
(authored `False` on the four organic monster rows); pool
thinning edits `data/npc_chars/core.py` specs only.

**Audit gap found in review (2026-09-19):** the constructor list
missed `saveload._restore_loot_entities` (`saveload.py:696`) —
the colour authority on load for every non-dungeon map, because
`_save_loot` does not serialize `fg`. Without routing it through
`loot_fg`, all space-map loot reloads gold and heist cargo loses
its cyan. Fixed in commit 1 with a load-path round-trip test;
lesson: colour-authority sweeps must include the restore paths,
not just spawn paths (the parallel-twins rule applies to
save/load twins too).

### Phase 1 — Polish (brief PROPOSED 2026-09-19; BUILT same day;
PLAYTEST PASSED same day — closed, see the Phases queue entry)

**Audit findings the brief stands on** (verified this session):

- C (character screen) is a GLOBAL key — open in space mode too
  (`game_loop.py:392-401` → `_handle_non_movement_event`), so
  Discard needs a no-floor answer.
- Monster weapons are real catalog rows
  (`data/ground_weapons/monsters.py`, `price=0,
  shop_available=False`) — an authored no-drop gate is needed or
  kit drops would scatter Monster Claws.
- Space-path eviction (`combat/_actions.py:154-193`) has NO
  quest/heist/pad exemption — exterior heist cargo can be
  evicted by churn today. The cap step fixes both paths with one
  shared helper.
- Derelict interiors exit via the shared exit-tile handler — the
  say-so hook point. (Audit correction at build: interiors do NOT
  carry `location_name="Derelict Ship"` — that's only a getattr
  fallback; `_enter_boarding_dungeon` stamps the ship's
  `npcspec.name`. The build instead stamps a persisted
  `derelict_interior` flag at the two one-shot constructors —
  `begin_capture_boarding` and `_build_generic_derelict` — with
  save/load twins; cached mission wrecks, digs, city interiors,
  and surfaces are revisit-able and stay unwarned.)

**Scope (files + hook points):**

1. **Category colours** — one pure `loot_fg(loot_data, …)`
  table: equipment → muted steel `(130,145,170)`; field items →
  amber `(200,175,110)`; cargo/trade → gold `(255,215,0)`;
  data/quest pads AND quest caches → pale violet `(190,190,255)`
  (the objective read); mission cargo keeps its cyan (verify
  exact RGB at build). Applied at EVERY constructor:
  `combat/_actions.py` (`_append_loot_entity`, space debris),
  `dungeon_layout.py` `_append_loot`, `digs.py` (caches + both
  pad spawners), `loot.py` (pads, pack-full drops),
  `combat/_space_kills.py` (heist cargo), quest placements in
  `game_interactions.py` / `main_quest/`. Initial values tuned
  at playtest; renderer untouched (entity fg already honored).
2. **Discard drops** — `_discard_pack_item` /
  `_discard_pack_stack` (`character_screen.py:491,692`) pop →
  spawn a floor entity at the player's position via the pack-full
  drop helper (extract the shared drop path if it isn't already
  one function). Space mode (no floor): the Discard row is
  HIDDEN — the verb means "put it on the ground", so where there
  is no ground there is no verb.
3. **Loot cap, both paths** — extract `_enforce_loot_cap(
  game_map)` from the inline eviction, with an exemption
  predicate (`main_quest_step_id` in `loot_data`, entity
  `heist_mission`, `teaches`/`reveals_site` pads); called by
  space `_spawn_loot_drops` AND ground `on_kill` drops. Eviction
  stays silent (SETTLED 8). Fixes the space heist-cargo eviction
  latent bug in the same commit.
4. **Diegetic kit drops** — `on_kill`
  (`combat/_rules_ground.py:740-767`) reads the enemy's resolved
  weapon (the combat state's `weapon_id`; audit the exact
  retrieval at build): spawn THAT weapon (fixed, no pool roll)
  + an ammo stack when `ammo_type` is set (size roll reuses the
  field-drop sizing `1..min(5, stack capacity)`). Gate:
  `GroundWeaponSpec` gains `loot_droppable: bool = True`;
  `data/ground_weapons/monsters.py` rows author `False` (organic
  parts never drop). Pool thinning per the rule — pools become
  beyond-the-weapon extras only (armor, sidearms), applied spec
  by spec in `data/npc_chars/core.py`; monsters untouched.
5. **Derelict say-so** — leaving a derelict interior with floor
  loot still present shows a confirm modal before the loss
  (exit-tile handler gated on the derelict interior); leave
  clean → no prompt. Strings APPROVED 2026-09-19 (user red-lined
  body + choices; title as drafted):
  - Modal title: "ABANDON THE DERELICT?"
  - Body: "This derelict ship is highly unstable, you won't be
    able to safely breach and dock it again."
  - Choices: "Leave" / "Stay"

**Build order:** colours → cap helper → discard → kit drops →
derelict say-so (approved strings land in their own commit,
last).

**Binding rulings:** SETTLED 3/5/7/8 + polish note 1; prose gate
on every new string; quest-loot security (SYSTEMS.md "Quest
loot security") is do-not-break; no payload-shape changes; cap
checks are per-kill O(n) — no per-tick cost.

**Tests:** category→colour mapping parametrized across every
constructor; discard round-trip (pop → floor entity at player →
P restores; space-mode row absence); cap (31st non-exempt evicts
oldest; quest/heist/pad never evicted — both paths); kit drops
(exact weapon + correct `ammo_type` stack; melee → no ammo;
`loot_droppable=False` → nothing; thinned pools respected;
monster pools unchanged); derelict prompt fires only with loot
present (strings pinned post-approval).

**Stop point:** no quality field/tiers/brightness, no module
payload, no `TradeGood.rarity` removal, no sell/economy changes,
no `DigLootSpec` changes, no new payload shapes, no doc-43
content, no SYSTEMS.md work (phase close only).

**Playtest checkpoint** (numbered; SPACEHACK_DEV run):
1. Kill a consortium enforcer: kinetic pistol + pistol rounds on
  the corpse tile + thinner extras; colours read by category.
2. Kill a rock scavenger: no claws on the floor; its usual drops
  unchanged.
3. Kill a knife-wielding pirate/civilian: the knife drops, no
  ammo stack.
4. Dungeon: Discard a pack item → it lands at your feet; P picks
  it back up; save → quit → Continue → still there.
5. Space mode: character screen shows NO Discard row.
6. Spawn a big ground fight (>30 loot entities): oldest plain
  loot evaporates; quest caches/pads/heist cargo never do.
7. Derelict with loot on the floor: leaving shows the confirm;
  leaving clean shows nothing.
8. Regression: P chooser labels, autoexplore cache labels, quest
  cache secure flow, heist cargo exterior pickup, save/load
  round-trip of dropped/discarded items.
9. Guide diff (before/after quoted at handoff): expected NONE —
  colour language explains itself in play; the guide's pickup
  row wording unchanged.

## Pre-implementation audit — phase 2 (2026-09-19)

**Reuse (verified):**

- Equip-time roll site: `_build_enemy_instance`
  (`combat/_rules_ground.py:160-184`) — where `weapons[0]` /
  `weapon_pick` resolve to `weapon_id`; `GroundEnemyInstance`
  is declared in the same module (`:74`), so `weapon_quality`
  is a same-file declared field, no cross-module setattr.
- Enemy attack stats: `_ai_ground.run_ground_enemy_turn(
  enemy_weapon_id=…)` resolves `_find_gw` at `_ai_ground.py:52`
  and threads the spec — the enemy-side scaling seam. Player
  side: `hit_chance` / `damage` (`_rules_ground.py:395,416`)
  read the bare id internally; the CALLERS hold the equipped
  `GroundWeaponInstance` (with quality) — thread from there.
- The armor migration lands inside two sum helpers:
  `sum_armor_defense` / `sum_armor_bonus`
  (`ground_equipment.py:28,48`) — combat (`_rules_ground:198,
  211`), HUD (`hud.py:503`), traits (`trait_screen.py:25`) all
  pass `ctx.equipped_ground_armor.values()` and stay textually
  identical when values become entries.
- Kill drops already flow through `spawn_kill_drops(…,
  weapon_id)` (phase 1) — gains the rolled `weapon_quality`
  parameter.
- `loot_data` serializes wholesale (`saveload.py:248`) and the
  restore path already routes colour through `loot_fg`
  (`saveload.py:699`) — a `quality` key rides save/load free
  and brightness is one function.
- Legacy-migration precedent to copy: `parse_weapon_instance`
  (`ground_equipment.py:145-175`) seeds defaults for older
  shapes (bare string → full instance).
- Sell path pops the entry (`sell_stored`), so quality is in
  hand at `_sell_price` (`menus/_armory.py:63`).

**Duplication hotspots:**

1. Effective-stat reads — player attack, enemy attack, armor
   sums, sell, labels: six sites that could each hand-multiply.
2. Token labels — P chooser, pack rows, armory list, sell rows:
   four screens that could each prefix.
3. Save/load twins — `_save_loot`/`_restore_loot_entities`
   (quality key), and `saveload_ground` parse/serialize for all
   three instance shapes (stored entry, weapon instance,
   equipped-armor dict).

**DRY strategy:**

1. One helper pair in the quality module —
   `effective_weapon_spec(id, quality)` /
   `effective_armor_spec(id, quality)` (`dataclasses.replace`
   copies with scaled fields); callers never multiply inline.
   Catalogs stay descriptive.
2. One `display_name(entry)` label helper; screens never prefix.
3. Ratchet watch: `_rules_ground.py` sits at 981 lines —
   phase-2 edits must be line-neutral or better (the equip-time
   roll is a small pure-helper extraction candidate).

**Data-first:** `src/spacehack/data/quality.py` — tokens,
per-family multiplier rows (weapon + armor now; the module row
lands phase 3 with its consumer), per-source 1-in-N rate tables,
pure `roll_quality` / `quality_multiplier`. No catalog edits.

**Build-discovery amendments (2026-09-19, implementation session):**

- Neither dungeon scatter nor dig caches carry EQUIPMENT today —
  `_LOOT_POOLS` rooms are trade-goods-only and `DigLootSpec` is the
  planet's produces. The WRECK/DIG rate ladders therefore need a
  thin authored equipment presence to have any consumer (playtest
  item 7 tests delve-cache tokens): wreck `personal_storage` and
  `engine_room` gain small `(item_type, item_id)` gear pools with a
  1-in-N presence roll per marker; dig caches gain
  `DigLootSpec.equipment_rate` (1-in-N caches carry gear instead of
  goods) + tier-banded gear pools in `data/digs`. Pools draw from
  existing catalogs — no new prose, no new payload shapes.
- The player-side quality thread: the shared loop already has
  slot-keyed rules entry points (`can_fire`/`consume_shot` in BOTH
  rule sets), so `hit_chance`/`damage` gain an optional
  `quality: int = 0` kwarg in both rule sets (space ignores it) and
  the loop resolves ground quality through a duck-typed
  `player_weapon_quality` rules hook (absent on space → 0).
  `explosive_blast`/`is_explosive` are ground-only (duck-typed in
  the loop) — no space signature change needed.
- Ratchet headroom for the 981-line `_rules_ground.py`:
  `_ground_hit_chance_raw` + `_ground_damage_raw` move to
  `_ground_math.py` (pure math joins pure math) in the combat
  commit. Landed at 986 lines (+5, under the 1000 limit) — later
  phase-2 steps have 14 lines of headroom there, not 19.
- Equip-time rolls gate on `GroundWeaponSpec.loot_droppable` (the
  phase-1 authored organic discriminator): body parts never roll —
  "Modded Monster Claws" is not a thing and monsters shouldn't
  consume roll RNG.
- Re-review findings folded into step 4 (2026-09-19): the deadshot
  chain links (`_ground_deadshot._chain_*`) and the combat HUD
  readouts (weapons panel + target card in `_ground_render`) thread
  the equipped quality too — one weapon, one stat set everywhere the
  player can see or be hit by it. Known accepted behavior:
  `_build_enemy_instance` re-runs on re-engagement, so a survivor of
  a disengaged fight re-rolls its weapon tier (the `weapon_pick`
  class already re-rolled the id the same way — pre-existing
  continuity gap; wounds persist, tiers don't).

### Phase 2 — Quality system (brief PROPOSED 2026-09-19)

**Scope (files + hook points):**

1. **Quality data module** — `src/spacehack/data/quality.py`:
   tokens `("modded", "overclocked", "prototype")` (SETTLED 10,
   user-dictated — the only new prose this phase); multiplier
   rows per family (weapon damage + accuracy contribution,
   armor protection + bonus fields; ~1.15/1.30/1.45-shaped,
   exact values authored then tuned at playtest; the legendary
   row exists but nothing rolls it — SETTLED 11); rate ladders
   `KILL_QUALITY_RATES` (used at BOTH NPC equip time and
   kill-extras drop time — SETTLED 13), `WRECK_QUALITY_RATES`
   (dungeon scatter), `DIG_QUALITY_RATES` (dig caches); pure
   `roll_quality(rates)`, `quality_multiplier(family, quality)`,
   `effective_weapon_spec` / `effective_armor_spec`.
2. **Instance threading** — `StoredGroundEquipment` +
   `quality: int = 0`; `GroundWeaponInstance` + `quality:
   int = 0` (equip/unequip/store/swap/install/displace preserve
   it); `ctx.equipped_ground_armor` becomes
   `dict[str, StoredGroundEquipment]` (`game_context.py:342`
   field type + the `ground_equipment` armor functions + the
   `.get(slot)` readers at `menus/_armory.py:325,515,526,857`
   and `character_screen.py:348,471` now read `.item_id`; the
   two sum helpers multiply per-entry quality internally).
3. **Save/load** — `saveload_ground.py`: serialize/parse all
   three shapes with legacy migration (missing/invalid quality
   → 0; legacy armor dict of bare ids → base entries). Plus the
   loot-entity round-trip (the quality key rides `loot_data`).
4. **NPC equip-time rolls** — `_build_enemy_instance` rolls the
   wielded weapon's quality (KILL rates, seeded) onto
   `GroundEnemyInstance.weapon_quality`; enemy attack scaling
   threads it through `_ai_ground`; `spawn_kill_drops` drops
   the wielded weapon AT its rolled quality (no re-roll).
5. **Drop-time rolls** — kill extras, dungeon-scatter equipment
   entries (`dungeon_layout` pools), dig caches (`DigLootSpec`
   gains quality-rate FIELDS only — rare-cache variant,
   legendary guarantee, out-of-produce pool stay phase 4; the
   thin equipment presence the audit amendment authors
   supersedes this "fields only" limit — the WRECK/DIG ladders
   need something to consume); equipment `loot_data` gains
   `quality`; `loot.py:101` pickup threads it into the stored
   entry.
6. **Presentation + economy** — `display_name(entry)` token
   prefix at the P chooser, pack rows, armory list + sell rows;
   `loot_fg` brightness steps within the equipment hue (SETTLED
   5); `_sell_price` × `quality_multiplier` (int-rounded,
   min 1); `TradeGood.rarity` deleted + its data authors
   cleaned.

**Build order:** quality module + unit tests → instance
threading + save migration → armor-dict migration → combat
scaling (equip-time roll, enemy attack, player attack) →
drop-time rolls + loot_data → labels/brightness/sell →
rarity removal.

**Binding rulings:** SETTLED 1/2/4/5/10-13; shops, starting
gear, quest gear, and mission cargo NEVER variant (base only);
space weapons and installed ship modules don't variant (module
instances are phase 3's payload); the system's name is
"quality" everywhere — `tech_level` owns "tier"
(`tier_filtered_equipment` is the unrelated NPC-drop gate);
quest-loot security do-not-break; deadshot/charger gate on
weapon_id identity (unaffected by quality); prose gate — beyond
the three user-dictated tokens, no new strings (the guide entry
below is the one addition, approval-gated).

**Tests:** multipliers/effective specs parametrized; equip
round-trip preserves quality through store/swap/install/
displace; legacy-save migration for all three shapes;
mixed-quality armor sums; seeded equip-time roll (read RNG via
module attr) with enemy stats scaling; the dropped weapon
carries the same rolled quality (no re-roll); extras/scatter/
dig rolls; token labels; sell × multiplier + rounding;
loot_fg brightness per tier; loot_data save/load round-trip
with quality; TradeGood surface after rarity removal.

**Stop point:** no module payload or module-storage migration
(phase 3), no randart generator/name pools/legendary activation
(phase 4), no rare-pickup modal (phase 4), no chips/lockboxes/
valuable pads, no DigLootSpec rare-cache/guarantee/out-of-
produce fields, no economy re-tuning beyond the authored rate
tables, no SYSTEMS.md edits (phase close only).

**Playtest checkpoint** (numbered; SPACEHACK_DEV run):

1. Seeded fight vs a weaponed NPC whose wielded weapon rolled a
   tier: it hits accordingly, and its corpse drops THAT weapon
   with the token label — not a re-roll.
2. Kill extras occasionally carry tokens; ammo, cargo, and
   quest goods never do.
3. Equip an overclocked weapon: the damage readout scales;
   unequip → the pack row keeps its token; armory transfers
   keep it too.
4. Armory sells variant gear at half catalog × multiplier;
   shop stock never carries tokens.
5. Floor glyphs: the equipment hue brightens by quality; the
   phase-1 category hues are unchanged.
6. A pre-quality save loads clean: all gear base, nothing lost
   (equipped-armor migration included).
7. Delve caches: equipment can carry tokens; rates read thin,
   not absent.
8. Regression: pack-full swap drops keep quality; P chooser
   labels; reload/displacement flows; quest caches secured and
   never variant; heist cargo cyan and unvarianted; deadshot/
   charger with variant weapons; discard-to-floor round-trip.
9. Guide diff: NEW entry (draft below) — approve or red-line
   before it lands; everything else unchanged.

**Guide entry draft (PROSE GATE — for approval with this
brief):**

    QUALITY: Loot weapons and armor can be modded, overclocked,
    or prototype grade — stronger than standard gear and worth
    more to buyers. Shops stock standard only; the better grades
    come off bodies and out of wrecks. What an enemy fought with
    is what drops.

## Pre-implementation audit — phase 3 (2026-09-20)

**Reuse (verified):**

- Ship storage already exists: `ctx.ship_storage` holds
  `StoredEquipment("module", id)` pairs (`ship.py:19-24`,
  `game_context.py:251`) — module loot appends there, no new
  container. The save parse exists (`saveload.py:95-112`).
- The pickup payload is already generic:
  `loot_common.equipment_payload("module", id, quality)` emits
  the shape; the quality key rides `loot_data` wholesale.
  `loot.py:627-633` dispatches by item_type (weapon/armor →
  equipment flow, ammo/consumable → field items, else → trade
  goods) — the module branch inserts there.
- Room-pool pattern: `_ROOM_EQUIPMENT_POOLS` +
  `WRECK_EQUIPMENT_RATE` (`dungeon_layout.py:33-42`) is the
  exact table shape `_ROOM_MODULE_POOLS` mirrors; scatter hooks
  the same per-marker loop in `_scatter_loot`.
- Enemy modules already ride into combat:
  `EnemyInstance.modules=enemy_spec.modules`
  (`combat/_stats.py:258`), and specs carry real lists
  (`data/npc_ships/`: warships 2-5 modules; scouts mostly none —
  so generic derelicts, which reuse `scout_a` at
  `game_interactions.py:693`, feed from room pools exactly as
  SETTLED 16 wants).
- Stat-sum seams: player/enemy module-bonus sums concentrate in
  `combat/_stats.py` (`_calc_max_hull`, `_calc_hull_for_enemy`,
  `_calc_power_gen`, `_calc_max_shields`, skill-bonus sums) and
  `ship.py`'s four helpers (`hull_cur_max`, `effective_speed`,
  `effective_max_cargo`, `smuggler_hold_capacity`) —
  `effective_module_spec` slots under all of them.
- Migration precedents to copy: `parse_weapon_instance`
  (bare-id → instance, `ground_equipment.py:145`) and the
  phase-2 armor-dict migration (callers keep passing the
  collection; sums go quality-aware internally).
- Sell seam: `_sell_price(item_type, item_id)` (`ship.py:356`)
  serves every sell path (stored `menus/_loadout.py:284,323`,
  installed `:353,416`) — gains quality once.

**Duplication hotspots:**

1. Module-bonus sums: ~8 reader functions across `_stats.py` +
   `ship.py` could each hand-multiply quality inline.
2. Token labels: loadout stored rows, ship-slot rows, sell
   choosers, install/log lines — four-plus screens that could
   each prefix.
3. Save/load twins: `StoredEquipment` parse/serialize AND
   `OwnedShip.modules` (new instance shape + legacy bare-id
   migration) — both directions.
4. The capture strip lands in `game_interactions.py` — 997
   lines, 3 lines of ratchet headroom.

**DRY strategy:**

1. One `effective_module_spec(id, quality)` in `data/quality.py`
   with the module family row — callers never multiply inline.
2. One module display-name seam (token prefix + spec.name) next
   to `StoredEquipment` in `ship.py`; screens never prefix.
3. The capture strip is a pure helper (flown instances → floor
   entities at engine-room markers, spawn-adjacent fallback)
   living in `combat/_actions.py`, CALLED from the capture path
   — `game_interactions.py` stays line-neutral.
4. `OwnedShip.modules` becomes entries (the armor-dict pattern:
   `StoredEquipment` items everywhere, `.item_id` at readers) —
   no parallel quality tuple to drift; flown modules on
   `EnemyInstance` follow the same instances-not-parallels
   shape (the `weapon_id`+`weapon_quality` pattern, plural).

**Data-first:** `MODULE_MULTIPLIER_PCT` family row; room pools
`engine_room: (compact_reactor, reactor_mk2)` /
`cargo_bay: (shield_mk1, shield_capacitor, targeting_computer,
expanded_cargo)` + `WRECK_MODULE_RATE` 1-in-N — opening
guesses, tuned at playtest; smuggler holds sit out the authored
pools this phase (SETTLED 17 — an authoring guess, never a
mechanism exclusion; doc 48 seeds the themed capture sources).
No catalog edits.

**Build-discovery amendments (2026-09-20, implementation session):**

- The capture-strip helper lives in `dungeon_layout.py`, not
  `combat/_actions.py` as the DRY sketch placed it: placement
  needs the loot-marker/room-cell internals only that module
  owns. The constraint the sketch protected held — the strip is
  a pure helper, and `game_interactions.py` stays at 998/1000
  (one kwarg threaded into the existing `_load_layout` call).
- The reader sweep was wider than the audit's list: the review
  of 3174f81 caught `_loadout`'s three slot readers and
  `_apply_purchase`'s install still in bare-id shape (crash +
  a str landing in the modules tuple), plus `_ship_menu`'s
  `_effective_shields`/`_effective_power_gen` silently dropping
  entries (swallowed KeyErrors = wrong hangar numbers, no
  crash). Both menu stat helpers now DELEGATE to
  `combat._stats`'s quality-aware sums — the parallel twins
  died rather than gained a quality branch. Lesson: an
  instances-not-parallels migration must sweep the MENUS in the
  same commit as the storage shape, and the test fixture that
  pins the broken screen is the one that keeps the gate green
  through it.
- `start_enemy_turn`'s module shield-regen sum
  (`combat/_actions.py`) is a ninth module-bonus reader the
  audit undercounted ("~8") — now effective-spec-aware.
- The fly-time roll writes `StoredEquipment`, whose third
  positional is AMMO (the ground twin's third is quality) —
  quality must thread as a keyword (caught by test).
- Authored test layouts need `TILE: . = DUNGEON_FLOOR`
  (a bare `.` is VOID without it) and `ENDMAP` (without it,
  directives become map rows). Strip tests isolate from the
  room pool via an autouse 1-in-10^9 rate fixture.

### Phase 3 — Modules as loot (brief PROPOSED 2026-09-20)

**Scope (files + hook points):**

1. **Quality family row** — `data/quality.py`:
   `MODULE_MULTIPLIER_PCT` (the ~115/130/145/220 shape, tuned at
   playtest) + `effective_module_spec(module_id, quality)`
   scaling all ten bonus fields proportionally; NEGATIVE bonuses
   scale in magnitude ("more of what it is" — a prototype Armor
   Plating gives more hull AND a bigger power draw); price,
   tech_level, slot_type untouched.
2. **Instance threading** — `StoredEquipment` gains
   `quality: int = 0`; `OwnedShip.modules` becomes
   `tuple[StoredEquipment, ...]`: `_install_module` takes an
   entry (the buy path constructs base), `store_module` /
   `_remove_module` / `move_installed_equipment_to_storage`
   preserve quality, `can_install_stored_equipment` and the
   slot/find helpers read `.item_id`; reader sweep:
   `ship.py` helpers, `combat/_stats.py` sums, `tutorial.py:268`,
   `_ship_menu`/`_loadout` rows.
3. **Save/load** — `saveload.py`: the StoredEquipment quality
   key (missing/invalid → 0) and the `OwnedShip.modules`
   migration (legacy bare-id tuples → base entries).
4. **Enemy fly-time rolls** — `EnemyInstance`'s flown modules
   become quality-bearing instances rolled at instance build
   (KILL rates, per-module, seeded — SETTLED 14); enemy stat
   builds thread them through `effective_module_spec`
   (`_calc_hull_for_enemy`, `_calc_max_shields`, power/skill
   sums — verify exact sites at build); disengage/re-engage
   re-rolls (the accepted ground continuity gap, space-side).
5. **Capture strip** — the intact-capture interior seeds floor
   entities from the fought instance's (id, quality) pairs at
   engine-room markers (spawn-adjacent fallback): pure helper in
   `combat/_actions.py`, threaded from the combat BOARD path
   through `_consume_boarded_hull` → the capture
   `_load_layout(capture_layout_id, …)` call; dead-ship
   interiors (wrecks, derelicts, mission salvage) NEVER seed
   from the list (SETTLED 16).
6. **Room pools** — `dungeon_layout.py`: `_ROOM_MODULE_POOLS`
   (engine_room → engine-slot, cargo_bay → system-slot) +
   `WRECK_MODULE_RATE` 1-in-N per marker, quality through the
   WRECK ladder, hooking the same marker loop as the equipment
   pools.
7. **Pickup + presentation** — `loot.py`: the module branch in
   `_open_single_loot_pickup` → `_apply_module_loot` appends
   `StoredEquipment("module", id, quality)` to
   `ctx.ship_storage` (no pack check — storage is uncapped like
   bought parts) + one log line (string below, gated);
   `loot_common.loot_fg` treats item_type "module" as equipment
   (hue + quality brightness); the display-name seam covers
   chooser labels, loadout rows, and log lines; module detail
   rows render from the effective spec where a stats line shows
   (match the ground armory's phase-2 behavior).
8. **Economy** — `_sell_price` gains quality: exact
   `(price*pct+100)//200`, min 1 (the armory formula, SETTLED 4);
   shop stock and buy paths stay base.

**Build order:** quality row + effective spec → stored/installed
instance migration + save/load → pickup branch + labels +
loot_fg → fly-time rolls + combat threading → capture strip →
room pools → sell × multiplier → guide (own commit,
approval-gated).

**Binding rulings:** SETTLED 14/15/16/17 + rulings 2/3, SETTLED
4; shops, starting gear, and quest gear never variant; exterior
space kills NEVER drop modules (ruling 3 is raiding, not
debris); smuggler holds sit out this phase's AUTHORED POOLS
only — an authoring guess, never a mechanism exclusion (SETTLED
17: no module id is barred from the payload/pool/capture-strip
paths; themed capture sources are doc 48's loadout re-authoring);
quest-loot security do-not-break; mission salvage steps feed
from room pools only (their ships are dead); no new room types
or layout edits; prose gate — beyond the strings below, no new
prose.

**Tests:** effective module spec parametrized (ten fields,
negative-magnitude scaling, half-up rounding both signs);
install/store/sell/upgrade-transfer round-trips preserve
quality; legacy-save migration (bare-id modules,
quality-less StoredEquipment); seeded fly-time roll scales
enemy hull/shields; the capture strip drops the fought
instances exactly (no re-roll) and dead interiors never strip;
room pool presence + rates (both rooms); pickup → ship_storage;
loot_fg module hue/brightness; sell integer-exact at every
tier; no source can roll legendary.

**Stop point:** no randart generator/name pools/legendary
activation (phase 4), no rare-pickup modal (phase 4), no
chips/lockboxes/valuable pads, no dig-site module sources
(delve legendaries are phase 4's), no enemy loadout re-authoring
by site tier (doc 48 owns that surface), no exterior-kill module
drops, no layout/room-type edits, no SYSTEMS.md work (phase
close only).

**Playtest checkpoint** (numbered; SPACEHACK_DEV run):

1. Fight a warship (gunboat/cruiser) until one rolls a module
   tier: it tanks/hits accordingly; BOARD under capture
   conditions and win — its installed modules lie in the engine
   room with tokens matching what flew against you.
2. Reduce a ship to a dead hull, then board it: room scatter
   only, no installed-list pile (its hardware died with it).
3. Wreck/derelict rooms: engine rooms can yield reactors;
   cargo bays yield shield/targeting gear; token rates read
   thin, not absent.
4. Pick a module up: storage gains it (mechanic STORAGE view),
   log line reads, the glyph shows the equipment hue brightening
   with quality.
5. Install an overclocked Shield Mk. 2: max shields rise by the
   scaled bonus; store it — the token survives; save → quit →
   Continue — quality survives both stored and installed.
6. Mechanic: sell a variant module at half catalog ×
   multiplier; shop stock never carries tokens; the economy
   reads sane (captures don't out-earn their risk).
7. Regression: ground quality flows unchanged; transponder
   clone/capture flow unchanged; derelict one-shot prompt;
   mission salvage steps; ship-upgrade transfer; tutorial
   hints.
8. Guide diff: Ships & Equipment gains the module-loot
   paragraph (draft below) — approve or red-line before it
   lands; everything else unchanged.

**Strings drafts (PROSE GATE — for approval with this brief):**

Pickup log line (follows the `Packed ground equipment: …`
convention; `{name}` carries the token prefix through the
display-name seam):

    Stored ship module: {name}.

Guide entry (lands in "Ships & Equipment" after the mechanic
paragraph):

    Ship modules can be looted as well. Capture an enemy ship
    and you strip the modules it was flying; search wrecks and
    derelicts for spare parts in the engine room and the cargo
    bay. Modules carry the same quality grades as ground gear.
