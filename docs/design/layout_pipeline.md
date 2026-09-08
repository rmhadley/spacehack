# Layout pipeline: source image → game-ready rect hull (doc 40, phase 6c/6d)

This is the instruction set for a fresh session (no context needed) to turn a
top-down ship reference image into a game-ready rect hull using the 6c tools.
Read this file, `tools/trace_reference.py`, and `tools/rect_from_silhouette.py`
before doing anything.

## What the tools guarantee (do not re-implement, do not hand-patch outputs)

| Stage | Tool | Built-in guarantees |
|---|---|---|
| image → silhouette | `tools/trace_reference.py` | diagonal pinch seal (fixpoint), dedent (leftmost hull column at x0, relative indentation preserved), island filter, enclosed-void fill |
| silhouette → rect hull | `tools/rect_from_silhouette.py` | 3×3 quantum decomposition (min rectangle `###/#.#/###`), enclosed-void fill, boundary walls, junction seal, **escape flood check** |

The escape flood is the no-diag rule: the player moves 8-directionally with
corner cutting legal, so the interior must not reach a single void quantum.
The tool FAILS the run if it does. When that happens, fix the SILHOUETTE (or
pass `--seal-phantom` to fill phantom-floor corner-cut entries) — never
hand-patch the rect output.

## Process

1. **View the source image** (multimodal read). Identify the ship's bounding
   box in pixels — this becomes `--crop L,T,R,B`. Tight crop: cut UI panels,
   text, background clutter.
2. **Ask the user** (one batch):
   - canvas size — the quantum grid. Suggest from the image aspect:
     `H = W × (crop_h/crop_w) ÷ 2` (character cells are ~2:1 tall); bigger
     grid = more interior room for rooms. Confirm W (and H if not derived).
   - mirror — is the ship top/bottom symmetric? Symmetric sources must be
     symmetric *before* tracing; an asymmetric source mirror-traced will
     shrink or double (the Mantis lesson).
   - rotation — if the ship climbs or dives in the image, `--rotate` the
     climb angle (e.g. the Mantis needed 14°).
3. **Trace:**
   ```
   python3 tools/trace_reference.py IMAGE --crop L,T,R,B --grid W,H \
       [--rotate DEG] [--mirror] [--close 1-2] [--bright N] \
       --out layout_drafts/<name>_silhouette.txt
   ```
   - `--bright 55` if thin dark parts (nacelles, fins) vanish — check the
     output visually; a lost part is a threshold problem, not a shape one.
   - The tool reports `diag pinches sealed: N` on stderr — the no-diag rule
     already enforced at this stage.
4. **Show the silhouette to the user** for the shape read. Iterate on
   crop/grid/thresholds until blessed. Do not proceed on an unblessed shape.
5. **Rect output:**
   ```
   python3 tools/rect_from_silhouette.py SILHOUETTE.txt \
       --out layout_drafts/<name>_rect.txt \
       --json layout_drafts/<name>_rects.json [--symmetric] [--seal-phantom]
   ```
   - The tool FAILS on an escape (the interior reaching void). `--seal-phantom`
     fills phantom-floor corner-cut entries; otherwise fix the silhouette.
6. **Show the rect output** for the final read. The `.json` rect list is the
   seed of the wall-mode room spec (rooms are subdivided inside these hull
   blocks in the room pass).

## Quality bar (the user's rules from the 6c sessions — binding)

- Smallest brush: `###/#.#/###`. One-cell features don't survive; never
  shrink the ship to fit detail into the brush.
- Whitespace: the leftmost hull column touches x0; other rows keep their
  relative indentation (the tool's dedent does this; never per-line lstrip).
- The reference's character — blades, notches, waist, lobes — must survive
  the quantization. If a feature vanishes: lower `--bright`, enlarge the
  grid, or re-crop. Never hand-patch the rect output.
- Never commit other games' art: reference images stay local
  (`docs/design/references/` is gitignored for images; URLs are the record).
- Naming: generated files go to `layout_drafts/` with clearly separate names;
  never collide with the user's hand-edit lineage.

## Verified examples (for calibration)

- `layout_drafts/cruiser_rect_kestrel.txt` — FTL Kestrel A, 303×96, 38 rects
  (capital scale; the process-proof artifact the user called beautiful).
- `layout_drafts/cruiser_silhouette_symmetric_2x_regenerated.txt` +
  `..._regenerated.json` — FTL Mantis A (rotated 14°, mirrored), the
  symmetric cruiser at deck scale.
- Reference images fetched via the fandom API (page HTML is Cloudflare-gated;
  static.wikia.nocookie.net is not) — see `docs/design/references/README.md`.
