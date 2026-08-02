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

## How to play

### The basics

1. **Create a character** — pick a species, then a class. Your choices set
   your starting skills, reputation, and credits.
2. **Explore the city** — move with the **vim keys** (`h j k l` for
   cardinal directions, `y u b n` for diagonals). Walk into buildings and
   NPCs to interact.
3. **Find work** — the guild halls and the bar have mission boards
   (deliveries, bounties, smuggling, salvage). You can hold up to 5 missions.
4. **Launch** — walk into your ship at the spaceport, then fly the system.
   Bump into planets to land, or jump gates to travel between systems.
5. **Survive** — combat is turn-based. Manage your AP, power, shields, and
   ammo. When AP hits 0, the enemy takes their turn.

### Controls

| Key | Action |
|-----|--------|
| `h j k l` / `y u b n` | Move (cardinals / diagonals) |
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
toggles weapons on/off · `S` cycles shield regen · `W` waits.

**Tip:** press `?` in-game for a complete guide covering combat math, trade
formulas, missions, and more.

## Credits

- Built on [python-tcod](https://github.com/HexDecimal/python-tcod)
- Typeface: [Hack](https://github.com/source-foundry/Hack) (MIT)
- Fallback tileset: DejaVu Sans Mono (CP437)

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2026 rmhadley.
See the `LICENSE` file for the full text.
