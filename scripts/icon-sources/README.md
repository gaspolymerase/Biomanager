# Vendored icon sources

SVGs that the icon sprite is built from but that do not come from the Font
Awesome package. Kept in the repo so `scripts/build-icons.py` works
offline.

| File | Origin | Author | Licence |
| --- | --- | --- | --- |
| `mouse.svg` | [game-icons.net](https://game-icons.net/1x1/delapouite/rat.html) (`rat`) | Delapouite | CC BY 3.0 |
| `fly.svg` | [game-icons.net](https://game-icons.net/1x1/delapouite/fly.html) | Delapouite | CC BY 3.0 |

Both were drawn as white glyphs on a black plate; the build strips the
plate and the hard-coded fill so they inherit `currentColor`.

Hand-drawing these two was tried three times and failed: a mouse silhouette
collapses to a blob below ~24px unless the ears, snout and tail are all
resolved, which is more drawing than an icon of this size can carry.
