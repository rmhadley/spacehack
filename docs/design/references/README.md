# Ship-layout reference corpus (doc 40 phase 6c/6d)

Top-down doors-view schematics — the blessed genre (the user's
frigate was translated from the FTL Slug). One or two per hull
class; the agent transcribes the silhouette into the JSON spec,
the user walks the deck.

**References are fetched on demand and kept LOCAL — never
committed** (other games' art does not enter this repo; this dir
is gitignored for images). The URL is the durable record.

| Hull class | Reference | Source |
|---|---|---|
| frigate | FTL Slug doors-view + the user's hand art (`shipideas.txt`, untracked) | https://ftl.fandom.com/wiki/Slug_Cruiser |
| cruiser | FTL Mantis Cruiser A systems view ("The Gila Monster" — blade-armed, reads raider) | https://static.wikia.nocookie.net/ftl/images/f/fb/MantisASystems.png/revision/latest?cb=20141124210132 |

Fetch pattern: the fandom api.php lists image URLs (page HTML is
Cloudflare-gated; static.wikia.nocookie.net is not).
