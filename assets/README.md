# Brand assets

Square renders of the site wordmark, for the many places that want one:
directory listings, registry entries, favicons, `Organization.logo` in
structured data.

| File | Use |
|---|---|
| `thirdtrail-square.svg` | source; re-render at any size |
| `thirdtrail-square-1024.png` | general upload |
| `thirdtrail-square-512.png` | where a smaller file matters |

## How these were made

The site wordmark (`src/templates/partials/logo.html` in the application repo)
is 1024x218. These extend the **viewBox** vertically to `0 -403 1024 1024` —
403 being `(1024 - 218) / 2` — so the artwork is centred in a square with
nothing scaled or stretched.

Two substitutions were needed, because the template inherits colour from the
text around it and a standalone file cannot: `currentColor` becomes `#10131A`
(`--fg`, ink) and `var(--bg)` becomes `#FBFBFC` (`--bg`, ground). Both are
Meridian palette values, so these match the site rather than approximating it.

## Caveat

The wordmark is roughly 4.7:1, so a square tile is mostly empty ground and the
lettering is small at typical directory display sizes. These are a stopgap. A
purpose-drawn square icon would serve better everywhere a square is wanted.
