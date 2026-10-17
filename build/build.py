#!/usr/bin/env python3
"""Build the SIENA Solutions business card.

Everything comes from card.config.json; the card size is set there in ONE place ("size").
    python3 build/build.py              # build the size in card.config.json
    python3 build/build.py 90x50        # build another size for comparison (config unchanged)

Outputs to output/<size>/:
    *-print-cmyk.pdf  front/back, trim + bleed + crop marks, CMYK, TrimBox/BleedBox set
    *-preview.png     front/back on screen (trim size, no bleed)
    *-overview.png    front and back side by side, for sharing
The background glow is pre-rendered at BG_PPI and placed as an image, so the print RIP gets a smooth,
high-resolution gradient; text stays vector with static fonts embedded (assets/fonts).
Needs: playwright (node), ghostscript, python packages segno + pikepdf + pillow.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import pikepdf
import segno
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PX_PER_MM = 8              # design units used in design/*.html
SLUG_MM = 10               # white margin around the trim that holds the crop marks
MARK_LEN_MM = 5
MARK_WIDTH_MM = 0.0882     # 0.25 pt
BG_PPI = 600


def parse_size(s):
    m = re.fullmatch(r'\s*([\d.]+)\s*x\s*([\d.]+)\s*(mm|in)?\s*', s)
    if not m:
        sys.exit(f'Bad size "{s}": use e.g. 85x55, 90x50 or 3.5x2in')
    k = 25.4 if m.group(3) == 'in' else 1
    return float(m.group(1)) * k, float(m.group(2)) * k


def card_css(w, h, bleed):
    fonts = (ROOT / 'assets' / 'fonts').as_uri()
    return f'''
@font-face{{font-family:'Inter';src:url({fonts}/Inter-Regular.ttf)}}
@font-face{{font-family:'JetBrains Mono';src:url({fonts}/JetBrainsMono-Regular.ttf)}}
:root{{--card-w:{(w + 2 * bleed) * PX_PER_MM}px;--card-h:{(h + 2 * bleed) * PX_PER_MM}px;--bleed:{bleed * PX_PER_MM}px}}
.card{{box-sizing:border-box;width:var(--card-w);height:var(--card-h);overflow:hidden;color:#E8F6FF;font-family:'Inter',system-ui,sans-serif}}
.mono{{font-family:'JetBrains Mono',ui-monospace,monospace}}
.label{{font-size:15px;letter-spacing:.16em;color:#7F93B3}}
.value{{font-size:21px;line-height:1.25;white-space:nowrap}}
.qr{{width:132px;height:132px;border-radius:6px;overflow:hidden}}
.qr svg{{display:block;width:100%;height:100%}}'''


def fill(side, cfg, qr_svg):
    html = (ROOT / 'design' / f'{side}.html').read_text()
    for key, val in {'ASSETS': (ROOT / 'assets').as_uri(), 'PHONE': cfg['phone_display'],
                     'EMAIL': cfg['email'], 'WEBSITE': cfg['website'],
                     'LOCATION': cfg['location'], 'QR_SVG': qr_svg}.items():
        html = html.replace('{{' + key + '}}', val)
    return html


def page(head_css, body):
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<style>body{{margin:0}}{head_css}</style></head><body>{body}</body></html>')


def crop_marks(w, h, bleed):
    t, g, L, s = SLUG_MM, bleed, MARK_LEN_MM, MARK_WIDTH_MM
    marks = []
    for x in (t, t + w):            # vertical marks above and below each trim edge
        for y in (t - g - L, t + h + g):
            marks.append((x - s / 2, y, s, L))
    for y in (t, t + h):            # horizontal marks left and right
        for x in (t - g - L, t + w + g):
            marks.append((x, y - s / 2, L, s))
    return ''.join(f'<div style="position:absolute;left:{x}mm;top:{y}mm;width:{a}mm;height:{b}mm;background:#000"></div>'
                   for x, y, a, b in marks)


def main():
    cfg = json.loads((ROOT / 'card.config.json').read_text())
    size_name = sys.argv[1] if len(sys.argv) > 1 else cfg['size']
    w, h = parse_size(size_name)
    bleed = float(cfg['bleed_mm'])
    out = ROOT / 'output' / size_name
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='siena-card-') as d:
        build(cfg, size_name, w, h, bleed, out, Path(d))


def dither(png):
    # +-1 level of noise hides 8-bit banding in the dark gradient
    a = np.asarray(Image.open(png).convert('RGB'), dtype=np.int16)
    a += np.random.default_rng(1).integers(-1, 2, size=a.shape[:2], dtype=np.int16)[..., None]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(png, dpi=(BG_PPI, BG_PPI))


def render(jobs, tmp, name):
    (tmp / name).write_text(json.dumps(jobs))
    subprocess.run(['node', str(ROOT / 'build' / 'render.js'), str(tmp / name)], check=True)


def build(cfg, size_name, w, h, bleed, out, tmp):
    qr = segno.make(cfg['whatsapp_link'], error='m')
    qr_svg = qr.svg_inline(dark='#03050D', light='#E8F6FF', border=3, omitsize=True)

    # 1. Backgrounds (gradient + front hairline) at BG_PPI, bleed included
    bg_jobs = []
    for side in ('front', 'back'):
        bg = tmp / f'{side}-bg.html'
        bg.write_text(page(card_css(w, h, bleed) + '.card>:not(.bg-keep){visibility:hidden}', fill(side, cfg, qr_svg)))
        bg_jobs.append({'type': 'png', 'html': str(bg), 'selector': '.card', 'scale': BG_PPI / 25.4 / PX_PER_MM,
                        'out': str(tmp / f'{side}-bg.png')})
    render(bg_jobs, tmp, 'bg-jobs.json')
    for j in bg_jobs:
        dither(j['out'])

    jobs = []
    scale = 96 / 25.4 / PX_PER_MM
    pw, ph = w + 2 * SLUG_MM, h + 2 * SLUG_MM
    for side in ('front', 'back'):
        # 2. Screen preview: trim size, no bleed
        prev = tmp / f'{side}-preview.html'
        prev.write_text(page(card_css(w, h, 0), fill(side, cfg, qr_svg)))
        jobs.append({'type': 'png', 'html': str(prev), 'selector': '.card',
                     'out': str(out / f'SIENA-card-{side}-{size_name}-preview.png')})
        # 3. Print page: bleed box scaled from design px to real mm, crop marks in the slug
        bw, bh = w + 2 * bleed, h + 2 * bleed
        body = (f'<div style="position:relative;width:{pw}mm;height:{ph}mm;background:#fff;overflow:hidden">'
                f'<div style="position:absolute;left:{SLUG_MM - bleed}mm;top:{SLUG_MM - bleed}mm;width:{bw}mm;height:{bh}mm;overflow:hidden">'
                f'<div style="transform:scale({scale});transform-origin:0 0">{fill(side, cfg, qr_svg)}</div></div>'
                f'{crop_marks(w, h, bleed)}</div>')
        pr = tmp / f'{side}-print.html'
        bg_css = f'.card{{background:url({(tmp / f"{side}-bg.png").as_uri()}) 0 0/100% 100% no-repeat !important}}.bg-keep{{visibility:hidden}}'
        pr.write_text(page(f'@page{{size:{pw}mm {ph}mm;margin:0}}' + card_css(w, h, bleed) + bg_css, body))
        jobs.append({'type': 'pdf', 'html': str(pr), 'width_mm': pw, 'height_mm': ph,
                     'out': str(tmp / f'{side}-rgb.pdf')})

    # 4. Overview sheet for sharing
    figs = ''.join(f'<figure><div class="c">{fill(s, cfg, qr_svg)}</div><figcaption>{s.upper()} · {w:g} × {h:g} mm</figcaption></figure>'
                   for s in ('front', 'back'))
    ov = tmp / 'overview.html'
    ov.write_text(page(card_css(w, h, 0) + """
#sheet{display:inline-flex;gap:56px;padding:72px;background:linear-gradient(160deg,#D6DAE2,#BFC5D0)}
figure{margin:0;display:flex;flex-direction:column;gap:14px}
.c{border-radius:10px;overflow:hidden;box-shadow:0 2px 4px rgba(10,20,50,.18),0 18px 40px rgba(10,20,50,.28)}
figcaption{font-family:'JetBrains Mono',monospace;font-size:14px;letter-spacing:.18em;color:#4A5873}""",
                       f'<div id="sheet">{figs}</div>'))
    jobs.append({'type': 'png', 'html': str(ov), 'selector': '#sheet',
                 'out': str(out / f'SIENA-card-{size_name}-overview.png')})
    render(jobs, tmp, 'jobs.json')

    pt = 72 / 25.4
    for side in ('front', 'back'):
        final = out / f'SIENA-card-{side}-{size_name}-print-cmyk.pdf'
        subprocess.run(['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite',
                        '-dCompatibilityLevel=1.6', '-sColorConversionStrategy=CMYK',
                        '-sProcessColorModel=DeviceCMYK', '-dAutoRotatePages=/None',
                        '-dDownsampleColorImages=false', '-dAutoFilterColorImages=false',
                        '-sColorImageFilter=FlateEncode', '-dEmbedAllFonts=true',
                        f'-sOutputFile={final}', str(tmp / f'{side}-rgb.pdf')], check=True)
        with pikepdf.open(final, allow_overwriting_input=True) as pdf:
            p = pdf.pages[0]
            p.TrimBox = pikepdf.Array([SLUG_MM * pt, SLUG_MM * pt, (SLUG_MM + w) * pt, (SLUG_MM + h) * pt])
            p.BleedBox = pikepdf.Array([(SLUG_MM - bleed) * pt, (SLUG_MM - bleed) * pt,
                                        (SLUG_MM + w + bleed) * pt, (SLUG_MM + h + bleed) * pt])
            pdf.save(final)
        print('wrote', final.relative_to(ROOT))


if __name__ == '__main__':
    main()
