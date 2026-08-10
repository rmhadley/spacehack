# spacehack

```
####### #######  #####   #####  ####### ##   ##  #####   #####  ##   ##
##      ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ##
####### ####### ####### ##      #####   ####### ####### ##      #####
     ## ##   ## ##   ## ##   ## ##      ##   ## ##   ## ##   ## ##  ##
####### ##   ## ##   ##  #####  ####### ##   ## ##   ##  #####  ##   ##
```

**A traditional ASCII-art sci-fi roguelike.** The year is 2200. Humankind has spread
across more than a dozen star systems linked by jump gates of unknown origin —
and you're a freelance pilot trying to make a living on the frontier.

Trade, smuggle, hunt bounties, and upgrade your ship across 13 star systems.
Death is permanent.

## Gameplay

<a href="docs/space_combat.gif"><img src="docs/space_combat.gif" alt="Space combat" width="400"></a>
<a href="docs/boarding_ground_combat.gif"><img src="docs/boarding_ground_combat.gif" alt="Boarding a derelict scout and ground combat" width="400"></a>

*Space combat (left) and boarding a derelict scout for ground combat (right).*

## Disclaimer

This project has been an experiment/resarch project of mine to learn/explore
using 100% free AI tools to design and build a playable game.

- I know python enough to follow the code generally, but I accepted that the AI
  will generate code that I do not understand fully.
- I modifed very little code, but I reviewed code and forced coding architecture
  where I thought it mattered.
- I modified through AI design docs which you can see in the repo. Then had the
  AI execute the design docs in phases.
- AI slop is most present in the stroy/plot/lore text. I'm enjoying this process
  enough that I do plan on replacing 99% of that AI slop output.
- Cloning the repo and using freebuff or your favorite free AI codign platform
  should allow any new features/modifications to your personal desires with ease
- I run freebuff in a docker jail to help protect it from accessing anything
  outside of the repo.

## Docker jail for freebuff

1. build the docker cache image
2. make a function in your rc file (example is from my .zshrc)
3. call `freejail`

```
docker run -it --name freebuff_builder node:18-slim sh -c "apt-get update && apt-get install -y git python3 python3-venv python3-pip && npm install -g freebuff"
docker commit freebuff_builder freejail-cached:latest

freejail () {
	docker run -it -v ~/code/spacehack:/workspace -w /workspace freejail-cached:latest sh -c "apt-get update && apt-get install -y git python3 python3-venv python3-pip && npm install -g freebuff && python3 -m venv --copies .docker_venv && . ./.docker_venv/bin/activate && pip install -e . && freebuff"
}
```

Then you can just call `freejail` to launch the editor.

## Features

- **A living universe** — 13 star systems connected by jump gates, each with
  its own planets, stations, economy, and dangers
- **Choose your legend** — pick a species (Human, Martian) and class
  (Pirate, Merchant, Bounty Hunter) that shape your starting skills and credits
- **Walk the cities** — guild halls, bars, spaceports, and terminals in every
  port town; talk to NPCs, take missions, refuel, repair, and rearm
- **Space combat** — turn-based dogfights with lasers, plasma cannons, and
  missiles (ammo is scarce and persistent — buy more at the mechanic)
- **Ground combat** — board derelict wrecks and explore planets on foot,
  with personal weapons, armor, and fog of war
- **Missions for every temperament** — deliveries, bounties, smuggling runs,
  salvage operations, and shady bar work. Boards refill each month
- **Dynamic trade** — buy low on producer worlds, sell high where it's
  consumed. Prices shift with supply and demand
- **Factions & reputation** — your standing with four factions gates pay,
  prices, and who's willing to trade with you
- **Deep progression** — earn XP, spend skill points on ship or ground
  skills, and unlock traits as you level
- **Permadeath** — one ship, one life. The frontier doesn't forgive

## Get the game

### Prebuilt (recommended)

Grab the latest release for your platform from the
**[Releases](https://github.com/rmhadley/spacehack/releases)** page:

- **macOS** — `spacehack-macos.zip` (a `.app` bundle)
- **Windows** — `spacehack-windows.zip` (a standalone `.exe`)

> The builds are unsigned, so macOS may warn "unidentified developer" —
> right-click the app and choose **Open**, or run
> `xattr -dr com.apple.quarantine /path/to/spacehack.app` to clear the
> quarantine flag (or System Settings → Privacy & Security → "Open Anyway").

### From source

Requires **Python 3.10+**. macOS / Linux:

```bash
git clone https://github.com/rmhadley/spacehack.git
cd spacehack
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m spacehack
```

Windows (from the repo folder):

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -e .
run_spacehack.bat
```

Linux/macOS can also just run `./run_spacehack` after `pip install -e .`.

## Text rendering comparison spike

To compare the current tcod bitmap text with an optional Pygame font renderer
without changing the game, install the visual extra and run the standalone
spike:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[visual]'
python tools/text_render_spike.py
```

The left panel is the current game bitmap; the right panel uses a system
monospace font. Use `--view merchant` to compare the Merchant Guild delivery
selection screen specifically. Use `--no-aa`, `--size`, `--scale`, or `--font`
to explore alternatives. Pygame and NumPy are optional and are not required
to run the game.
On macOS/Homebrew, use the virtual-environment commands above rather than
installing into the system Python; otherwise PEP 668 may report an
`externally-managed-environment` error.

### Live Merchant Pygame experiment

The first in-game migration experiment is opt-in. Install the visual extra,
then launch the game with `SPACEHACK_PYGAME_MERCHANT=1` and visit the Merchant
Guild. The game pauses its tcod modal, opens the real Merchant offerings flow
in a Pygame window, and returns the normal accept/back result to gameplay:

```bash
SPACEHACK_PYGAME_MERCHANT=1 python -m spacehack
```

The experiment matches the game canvas at `1600x960` and starts with a more
compact `24px` font; it will reduce the font further if the selected content
needs it. Press **ESC** to close the experiment window and return to the game.
If Pygame is missing or cannot open a window, the normal tcod Merchant modal
is used instead. Clear the variable to return to the unchanged tcod path:

```bash
python -m spacehack
```

This is intentionally a temporary second-window seam while the presentation
migration begins; the world grid, save data, mission logic, and every other
screen still belong to the existing tcod renderer.

### Live Quest Log Pygame experiment

The Quest Log can also be previewed with the readable Pygame font by enabling
its opt-in worker:

```bash
SPACEHACK_PYGAME_QUEST_LOG=1 python -m spacehack
```

The worker receives a presentation-only snapshot generated by the existing
Quest Log renderer, so mission details, deadlines, statuses, and message-log
content remain authoritative. Arrow keys / `j` / `k` navigate, `A` begins
abandon confirmation, `ENTER` confirms, and `ESC` backs out. Press `?` to open
the normal in-game guide. If Pygame is unavailable or the worker fails, the
existing tcod Quest Log opens instead. Clear the variable to disable it.

This is still a comparison seam: the tcod context, gameplay state, save/load,
and all mission mutations remain owned by the main game process.

### Live Ship Buy Pygame experiment

The Ship Buy modal can be previewed with the same readable Pygame renderer:

```bash
SPACEHACK_PYGAME_SHIP_BUY=1 python -m spacehack
```

It preserves the normal affordability, trade-in pricing, purchase, back, and
quit outcomes. Press `?` for the guide. If the optional worker is unavailable,
the existing tcod Ship Buy modal is used automatically.

### Live read-only modal Pygame batch

The read-only presentation batch previews the Faction Standings, Ship Loadout,
and Navigation Map screens with the same natural-font worker used by the
individual experiments:

```bash
SPACEHACK_PYGAME_READONLY=1 python -m spacehack
```

It captures each screen from its existing tcod renderer, so faction values,
ship statistics, map bodies, HUD messages, and colors remain authoritative.
Press `ESC` to return. Press `?` for the normal guide. If the worker is
unavailable or returns an invalid result, the original tcod modal opens
instead. Clear the variable to disable the batch.

### Live interactive-menu Pygame batch

The next migration batch previews mission offerings, planet interaction, and
ordinary NPC talk with the natural-font selectable worker:

```bash
SPACEHACK_PYGAME_INTERACTIVE=1 python -m spacehack
```

Mission rows return the selected offering, planet rows return `LAND`,
`EXPLORE`, or `BACK`, and NPC rows return delivery or work choices. The main
process still owns mission acceptance, cargo delivery, quest progression, and
world transitions. NPCs with a live main-quest choice intentionally remain on
the original tcod path until that stateful dialogue flow is migrated safely.
`ESC` backs out, `?` opens the normal guide, and unavailable or malformed
workers fall back to tcod. Clear the variable to disable this batch.

### Live exploration-frame Pygame preview

The migration preview shows the active city, space, or dungeon grid plus the
existing HUD and message log in the same isolated Pygame worker. It uses the
real map tiles, fog-of-war, entity footprints, camera, draw ordering, and
current gameplay stats, while tcod remains the active input/modal owner:

```bash
SPACEHACK_PYGAME_WORLD=1 python -m spacehack
```

Close the preview window or unset the variable to return to the unchanged
single-window tcod path. This is still a comparison seam, not yet the final
unified window; the Pygame preview receives draw commands only and cannot
mutate game state.

## How to play

### The basics

1. **Create a character** — pick a species, then a class. Your choices set
   your starting skills, reputation, and credits.
2. **Explore the city** — move with the **arrow keys**, the **vim keys**
   (`h j k l` cardinals, `y u b n` diagonals), or the **numpad**. Walk
   into buildings and NPCs to interact.
3. **Find work** — the guild halls and the bar have mission boards
   (deliveries, bounties, smuggling, salvage). You can hold up to 5 missions.
4. **Launch** — walk into your ship at the spaceport, then fly the system.
   Bump into planets to land, or jump gates to travel between systems.
5. **Survive** — combat is turn-based. Manage your AP, power, shields, and
   ammo. When AP hits 0, the enemy takes their turn.

### Controls

| Key | Action |
|-----|--------|
| `Arrows` / `h j k l` / `numpad` | Move (cardinals / diagonals) |
| `G` | Auto-navigate to a selected target (space) |
| `M` | Navigation map (space) |
| `T` | Comms panel — hail nearby ships (space) |
| `I` | Cargo hold |
| `C` | Character screen (level, skills, traits) |
| `F` | Faction standings |
| `Q` | Quest log |
| `?` | **In-game guide** — full documentation, always available |
| `.` | Wait one turn |
| `ESC` | Quit / back |

**Combat:** `TAB` cycles targets · `F` fires all active weapons · `1-9`
toggles weapons on/off · `S` cycles shield regen · `W` waits. Move with
arrows, vim keys, or numpad.

**Tip:** press `?` in-game for a complete guide covering combat math, trade
formulas, missions, and more.

## Credits

- Built on [python-tcod](https://github.com/HexDecimal/python-tcod)
- Typeface: [Hack](https://github.com/source-foundry/Hack) (MIT)
- Fallback tileset: DejaVu Sans Mono (CP437)

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2026 rmhadley.
See the `LICENSE` file for the full text.
