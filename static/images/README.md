# Design assets

The UI currently shows dashed **asset slots** (`partials/asset_slot.html`,
`partials/logo_mark.html`) wherever a designer graphic belongs. To ship a
graphic, export it into this folder and replace the slot include with an
`<img>` (keep `alt=""` for decorative images, which all of these are):

```django
{% load static %}
<img class="foldo-asset-img foldo-hero__art" src="{% static 'images/hero-illustration.png' %}" alt="">
```

Export at 2× the listed size (PNG/WebP) or as SVG.

| File (suggested)            | Where                                   | Template                          | Size (1×)      |
| --------------------------- | --------------------------------------- | --------------------------------- | -------------- |
| `logo-mark.svg`             | Navbar and footer                       | `partials/logo_mark.html`         | 32 × 32        |
| `hero-graphic.png`          | Landing hero — large graphic behind and overlapping the headline (keep the left ~40% calm so the text stays readable) | `core/landing.html` | 1600 × 1000 |

Brand colours: navy `#0B1530`, electric blue `#1D4ED8`, lime `#B8F34A`,
text `#F5F7FB`.
