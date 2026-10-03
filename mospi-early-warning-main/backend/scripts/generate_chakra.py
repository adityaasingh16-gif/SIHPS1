"""Render the Ashoka Chakra to a square, transparent, high-resolution PNG.

Geometry is generated rather than traced: 24 spokes on a 15-degree pitch, each
a tapered wedge running from the outer edge of the hub to the inner edge of the
rim, inside a double rim circle. Drawn at 4x and downsampled with LANCZOS so
the spoke edges stay clean when the browser scales the image down to the 44px
masthead slot.
"""

import math
import os

from PIL import Image, ImageDraw

NAVY = (0, 0, 128, 255)  # India Navy Blue, the flag's chakra colour
SPOKES = 24
FINAL = 1024
SS = 4  # supersample factor

OUT = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "public", "chakra.png"
)


def render(size: int = FINAL) -> Image.Image:
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    c = S / 2.0

    # Radii as fractions of the half-canvas, so the mark scales cleanly.
    rim_outer = 0.945 * c
    rim_inner = 0.882 * c
    spoke_tip = 0.855 * c
    hub = 0.212 * c
    rim_w = max(2, int(0.0175 * S))

    # Double rim: two concentric circles, the flag's outer and inner band.
    d.ellipse(
        [c - rim_outer, c - rim_outer, c + rim_outer, c + rim_outer],
        outline=NAVY, width=rim_w,
    )
    d.ellipse(
        [c - rim_inner, c - rim_inner, c + rim_inner, c + rim_inner],
        outline=NAVY, width=rim_w,
    )

    # Each spoke is a quadrilateral: a wider foot at the hub tapering to a
    # narrow tip at the rim. Half-angles are set so neighbouring spokes leave a
    # visible gap at the hub but converge at the tip.
    half_foot = math.radians(4.6)
    half_tip = math.radians(1.55)

    def pt(r, a):
        return (c + r * math.cos(a), c + r * math.sin(a))

    for i in range(SPOKES):
        a = 2 * math.pi * i / SPOKES - math.pi / 2  # first spoke at 12 o'clock
        d.polygon(
            [
                pt(hub, a - half_foot),
                pt(spoke_tip, a - half_tip),
                pt(spoke_tip, a + half_tip),
                pt(hub, a + half_foot),
            ],
            fill=NAVY,
        )

    # Central hub, drawn last so it sits cleanly over the spoke feet.
    d.ellipse([c - hub, c - hub, c + hub, c + hub], fill=NAVY)

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = os.path.abspath(OUT)
    im = render()
    im.save(out, "PNG", optimize=True)
    print(f"wrote {out}")
    print(f"  size   {im.size}  mode {im.mode}")
    a = im.getchannel("A")
    print(f"  alpha  {a.getextrema()}  transparent {100*(a.getpixel((0,0))==0):.0f}% corner")
    print(f"  bbox   {a.getbbox()}")
    print(f"  bytes  {os.path.getsize(out):,}")
