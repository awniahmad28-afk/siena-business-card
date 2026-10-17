# SIENA Solutions — business card

Direction C ("Glow & Services"): logo and services on the front; contact details and a WhatsApp QR code on the back.

## Files for the printer

`output/<size>/`

| File | What it is |
| --- | --- |
| `SIENA-card-front-<size>-print-cmyk.pdf` | Front, print-ready: 3 mm bleed, crop marks, CMYK, fonts embedded, TrimBox/BleedBox set |
| `SIENA-card-back-<size>-print-cmyk.pdf` | Back, same settings |
| `SIENA-card-front-<size>-preview.png` / `…back…` | Screen previews (trim size, about 400 dpi) |
| `SIENA-card-<size>-overview.png` | Front and back side by side, for sharing |

85 × 55 mm and 90 × 50 mm are both built so you can compare them.

## Changing the size or details

Everything is set in `card.config.json`:

- `size`: `"85x55"`, `"90x50"`, `"3.5x2in"` or any `WxH` in mm
- `bleed_mm`: the bleed your printer asks for
- phone, WhatsApp link (used for the QR code), email, website and location

Then rebuild:

```sh
python3 build/build.py          # the size in card.config.json
python3 build/build.py 90x50    # another size, for comparison
```

Needs Node with Playwright, Ghostscript, and the Python packages `segno`, `pikepdf`, `pillow` and `numpy`.

The layout lives in `design/front.html` and `design/back.html` (8 px = 1 mm). Logos are in `assets/` and are used unchanged. The fonts in `assets/fonts/` are Inter and JetBrains Mono, both under the SIL Open Font License.

## Before printing

Confirm the size, bleed, CMYK profile, paper and finish with your printer. The CMYK conversion uses Ghostscript's default profile; if the printer supplies a profile or a rich-black recipe, rebuild with it. Ask the logo designer for a vector logo (.ai, .eps, .svg or vector PDF), especially if you want spot gloss or foil.
