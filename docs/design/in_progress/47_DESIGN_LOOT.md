# DESIGN: Loot — Dropped-Loot Polish + Interesting Finds

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Draft opened 2026-09-19; nothing below is
settled until a refine session says so.

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

### B. Rarity — one uniform model (phase 2 candidate)

No loot rarity exists today; the two live tier systems (enemy
`tier` gating equipment via `tech_level`; shop stocking via
`tech_level`) don't cover it. Options:

- **(i) Authored rates tables per source** (recommended): one
  `1-in-N` dict per drop source — the exact shape of dig
  `DOOR_RATES` (`data/digs/__init__.py:67-71`) — gating a
  rare-roll pass. `TradeGood.rarity` gets deleted (dead field,
  consume-or-remove resolved as remove). Rarity stays in authored
  data where it's tunable at playtest, and catalogs stay purely
  descriptive.
- (ii) Revive `TradeGood.rarity` as a spawn weight every pool roll
  reads. One field drives everything, but it only covers trade
  goods, and it hides tuning inside catalog rows.

`DigLootSpec` expands in place per SETTLED 35: fields for a rare
cache variant, an out-of-produce pool, and rate overrides —
per-planet authoring through `dig_*` spec fields, planets inherit
defaults.

### C. New loot (phase 3 candidates)

- **Multi-purpose ship modules** — the user's seed note, verbatim
  lineage: "A shield generator AND cargo space all in one module
  slot?" `ModuleSpec` (`data/modules/__init__.py:14-45`) already
  expresses multi-axis bonuses; legendary modules = 2-3 bonus axes
  at strong-but-not-shop values, never shop-stockable. Placement
  follows the environment-as-gate principle: deep-dive bottoms and
  far-side wrecks — the trip is the check. Doc 43 already expects
  "legendary loot" aboard (`43_DESIGN_FAR_SIDE.md:59`). All
  names/descriptions are PROSE GATE.
- **Ordinary dungeon loot pads** — the surface doc 42 ceded.
  Distinct from teaching pads (knowledge): VALUABLE pads (salvage
  logs, manifests) — pickups with trade/credit worth, consume or
  keep-and-sell. Exact economy shape open.
- **Credits pickups** — open question: no direct-money drop exists
  today (credits arrive only through trade). Credit chips as a
  sixth payload shape would change the economy's texture; worth
  deciding once, early.
- **Kill-drop spice**: tier-gated equipment already scales with
  enemy tier; the rarity pass (B) is what makes kills interesting
  again. No separate mechanism proposed.

## Open questions (for the refine)

1. Colour-by-category palette — which categories get which
   accents, and does mission cargo stay cyan?
2. Rarity model (i) vs (ii) above.
3. Do credits pickups exist? (If yes: their payload shape, and
   what drops them.)
4. Are legendary modules sellable? (Quest goods are never
   sellable by ruling; legendaries aren't quest goods, but a
   sellable legendary converts deep-dive risk into a credit
   printer.)
5. Generic derelicts: cache their interiors (uniform with every
   other interior) or keep one-shot as the derelict identity —
   and if kept, does the player get to know the stakes before
   leaving?
6. Does the space-path silent eviction get a log line?
7. Scope check: is the polish pass (A) its own phase/commit
   before any new loot, or do they land together?

## Phases (skeleton — restructured at refine like doc 42's were)

1. **Polish** — colour language, discard-drops, ground cap, rare
   pickup modal (modal arrives with rarity if phased). Playtest
   checklist carries the guide-diff item (guide's pickup row /
   any colour language that becomes how-to-play).
2. **Rarity + richer tables** — rates tables, `TradeGood.rarity`
   removal, `DigLootSpec` expansion, wreck pool enrichment.
3. **Interesting loot** — legendary modules (+ doc-43 hookup),
   valuable pads, credits (if ruled in). Prose gate before any
   data strings land.
