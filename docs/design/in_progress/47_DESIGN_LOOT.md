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

- **Ship modules as loot** (ruling 3): new payload shape
  (`{"item_type": "module", "item_id": …}` → ship global
  storage), from boarding captures + derelicts via room-typed
  pools (engine rooms → engine-slot modules, systems rooms →
  system-slot), and the diegetic strong form: boarded ships drop
  from their own live `modules` list. Modules are quality-variant
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

## Remaining opens (prose-gated or authoring-tuned)

- Quality tier token words, the derelict warning wording, chip/
  lockbox names — PROSE GATE, proposed with their phases.
- Randart specifics — property spread (axis count, magnitude
  ranges) and whether randarts can carry TRADEOFFS/drawback axes
  (the Qud pattern) or are pure upside; name-pool register
  (call-signs? relic style?). Authored with phase 4; fragments
  PROSE GATE. Hand-authored uniques stay deferred (SETTLED 1
  amendment) — not a phase-4 item.
- Chip/lockbox value curve vs. trade-goods income — playtest.
- Section A leftovers still candidate-not-ruled: discard-drops-to-
  floor, ground cap parity. They ride phase 1 unless red-lined at
  its brief; the rare-pickup modal rides phase 2 (needs quality
  to define "rare").

## Phases (SETTLED 9 — polish first, each phase its own cycle)

- [ ] 1. **Polish** — category colour language (brightness arrives
  with phase 2), discard-drops, ground cap parity, diegetic kit
  drops (SETTLED 3: always + pools shrink), derelict one-shot
  SAY-SO (SETTLED 7; wording PROSE GATE). Playtest checklist
  carries the guide-diff item.
- [ ] 2. **Quality system** — instance quality field on stored gear +
  modules, the ladder table (three tiers + rolled legendary
  top, SETTLED 1-2), per-source rates (legendary delve-only),
  sell price × tier multiplier (SETTLED 4), quality brightness
  on glyphs (SETTLED 5), rare-pickup modal,
  `TradeGood.rarity` removal, `DigLootSpec` expansion.
- [ ] 3. **Modules as loot** — payload shape → ship storage,
  boarding/derelict room pools, boarded-ship live `modules`
  drops, mechanic economy check.
- [ ] 4. **Legendary randarts + credits + pads** — the randart
  generator (seeded name composition from word pools + property
  spread over `ModuleSpec`'s bonus axes), delve-bottom
  guarantee, chips/lockboxes in wrecks/digs (SETTLED 6),
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

### Phase 1 — Polish (brief PROPOSED 2026-09-19 — not buildable
until approved)

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
- Derelict interiors carry `location_name="Derelict Ship"` and
  exit via the shared exit-tile handler — the say-so hook point.

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
  clean → no prompt. DRAFT strings (PROSE GATE — approve or
  red-line with the brief):
  - Modal title: "ABANDON THE DERELICT?"
  - Body: "Anything left inside is lost when you leave."
  - Choices: "Leave it" / "Stay a moment"

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
