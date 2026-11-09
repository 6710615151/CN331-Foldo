# Design assets

| File | Where | Notes |
| --- | --- | --- |
| `logo-mark.png` | Sidebar, top bar, navbar, footer, auth panel, landing hero | `partials/logo_mark.html` (384 × 384) |
| `hero-illustration.png` | Landing hero only | 1400 × 1300. The PNG itself still contains a red “แก้อยู่” placeholder label near the bottom — replace with the final export. |
| `favicon.ico`, `favicon-192.png`, `apple-touch-icon.png` | `<head>` of every page (`partials/head_icons.html`) and `/favicon.ico` | Generated from `logo-mark.png` |
| `geo/*.svg` | 3D-geometric illustrations (`partials/geo_art.html`) | `dashboard`, `auth`, `error`, `empty`. Animated with CSS inside the SVG; motion stops under `prefers-reduced-motion`. |

Icons are not image files: they are CSS masks in `static/css/icons.css`
(`partials/icon.html`), coloured by `currentColor`.

Brand colours (tokens in `static/css/styles.css`): background `#06143D`, surface
`#0D2460`, electric blue `#145BFF`, lime `#C4F500`, purple `#702EFF`, magenta
`#EC20B8`, pink `#FF3D9A`, text `#FFFFFF` / `#AFC0E8`.
