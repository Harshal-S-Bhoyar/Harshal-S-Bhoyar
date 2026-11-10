#!/usr/bin/env python3
"""
koi_motion.py - make a koi fish swim along a wandering (non-circular) path.

Fixes three common problems:
  1. Size changing   -> the sprite is scaled ONCE, then only rotated. Every frame
                        is pasted by its CENTER, so nothing is re-measured or resized.
  2. Side-body swim  -> the fish is turned to face the direction it is moving
                        (the heading comes from the path's velocity).
  3. Circle motion   -> the path is a Lissajous-style curve (different x/y
                        frequencies), which loops seamlessly but is not a circle.

Edit the CONFIG block below. Only HEAD_DIRECTION and the paths usually need changing.
"""

import math
import sys

import numpy as np
from PIL import Image

# ----------------------------- CONFIG ---------------------------------------
INPUT_PATH = "assets/koi.png"      # source image (PNG with transparency is best; GIF's first frame is used)
OUTPUT_PATH = "assets/koi.gif"     # GIF that the README will show

# Which way the fish's HEAD points in the ORIGINAL image: "up", "down", "left", "right"
HEAD_DIRECTION = "up"

CANVAS_W, CANVAS_H = 800, 300      # size of the final GIF
BACKGROUND = (12, 36, 58)          # water color (RGB). A solid color avoids ugly GIF edge fringes.

FISH_LENGTH = 110                  # fish length in pixels. Fixed for the whole animation.
FRAMES = 90                        # more frames = smoother
FRAME_MS = 50                      # milliseconds per frame

# Path shape: x moves 1 cycle, y moves 2 cycles over the loop -> a gentle figure-8 / S-curve
PATH_MARGIN_X = 0.36               # fraction of canvas width used for horizontal swing
PATH_MARGIN_Y = 0.30               # fraction of canvas height used for vertical swing
PATH_WOBBLE = 0.12                 # extra small wiggle so it never looks mechanical

# Tail wave
TAIL_AMPLITUDE = 0.11              # side-to-side tail sway as a fraction of fish length
TAIL_WAVES = 1.1                   # how many S-bends fit along the body
TAIL_CYCLES_PER_LOOP = 6           # tail flaps per full loop (must be an integer for a seamless loop)
# -----------------------------------------------------------------------------


def load_sprite(path):
    """Load the image, make the background transparent if it has none, crop tight."""
    img = Image.open(path)
    img.seek(0)                     # first frame only (for GIFs)
    img = img.convert("RGBA")
    arr = np.array(img)

    # If the image has no transparency at all, treat the corner color as background.
    if arr[..., 3].min() == 255:
        corner = arr[0, 0, :3].astype(int)
        diff = np.abs(arr[..., :3].astype(int) - corner).sum(axis=2)
        arr[..., 3] = np.where(diff < 40, 0, 255)

    img = Image.fromarray(arr)
    bbox = img.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox()
    if bbox is None:
        sys.exit("Source image looks empty (fully transparent).")
    return img.crop(bbox)


def face_right(img, head):
    """Rotate so the head points RIGHT (+x). Everything after this assumes that."""
    # PIL rotates counter-clockwise by the given degrees.
    angle = {"right": 0, "up": -90, "left": 180, "down": 90}[head.lower()]
    return img.rotate(angle, expand=True, resample=Image.BICUBIC) if angle else img


def scale_once(img, length):
    """Scale so the fish's length (now horizontal) equals `length`. Done ONCE."""
    w, h = img.size
    s = length / w
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def wave_tail(sprite, t, amp_px, waves, phase_offset):
    """
    Bend the fish with a traveling wave. Head is on the RIGHT, tail on the LEFT.
    Each pixel column is shifted up/down. The wave is ~0 at the head and grows
    toward the tail, which is how real fish swim. Output size NEVER changes.
    """
    arr = np.array(sprite)
    h, w = arr.shape[:2]
    pad = int(math.ceil(amp_px)) + 2
    out = np.zeros((h + 2 * pad, w, 4), dtype=np.uint8)

    for x in range(w):
        u = 1.0 - x / (w - 1)                    # 0 at head, 1 at tail
        envelope = u ** 1.6                      # head stays calm, tail swings most
        dy = amp_px * envelope * math.sin(2 * math.pi * (waves * u) - t + phase_offset)
        dy = int(round(dy))
        out[pad + dy: pad + dy + h, x] = arr[:, x]

    return Image.fromarray(out)


def path_point(p):
    """Position and velocity at loop progress p in [0, 1). Seamless when p wraps."""
    w = 2 * math.pi * p
    cx, cy = CANVAS_W / 2, CANVAS_H / 2
    ax, ay = CANVAS_W * PATH_MARGIN_X, CANVAS_H * PATH_MARGIN_Y
    wob = PATH_WOBBLE

    x = cx + ax * math.sin(w) + ax * wob * math.sin(3 * w + 1.3)
    y = cy + ay * math.sin(2 * w + 0.6) + ay * wob * math.sin(5 * w)

    dx = ax * math.cos(w) + ax * wob * 3 * math.cos(3 * w + 1.3)
    dy = 2 * ay * math.cos(2 * w + 0.6) + ay * wob * 5 * math.cos(5 * w)
    return x, y, dx, dy


def main():
    sprite = scale_once(face_right(load_sprite(INPUT_PATH), HEAD_DIRECTION), FISH_LENGTH)
    amp_px = TAIL_AMPLITUDE * FISH_LENGTH

    frames = []
    prev_heading = None

    for i in range(FRAMES):
        p = i / FRAMES
        x, y, dx, dy = path_point(p)

        # Heading = direction of travel. Unwrap so it never spins the long way round.
        heading = math.atan2(dy, dx)
        if prev_heading is not None:
            while heading - prev_heading > math.pi:
                heading -= 2 * math.pi
            while heading - prev_heading < -math.pi:
                heading += 2 * math.pi
        prev_heading = heading

        t = 2 * math.pi * TAIL_CYCLES_PER_LOOP * p
        bent = wave_tail(sprite, t, amp_px, TAIL_WAVES, 0.0)

        # Screen y points DOWN, so a positive atan2 angle is clockwise on screen.
        # PIL rotates counter-clockwise, hence the minus sign.
        rotated = bent.rotate(-math.degrees(heading), expand=True, resample=Image.BICUBIC)

        frame = Image.new("RGBA", (CANVAS_W, CANVAS_H), BACKGROUND + (255,))
        # Paste by the CENTER of the rotated image, so the fish never jumps or shifts.
        px = round(x - rotated.width / 2)
        py = round(y - rotated.height / 2)
        frame.paste(rotated, (px, py), rotated)
        frames.append(frame.convert("RGB"))

    # One shared palette for all frames -> no color flicker between frames.
    palette_src = frames[len(frames) // 2].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    gif_frames = [f.quantize(palette=palette_src, dither=Image.Dither.NONE) for f in frames]

    gif_frames[0].save(
        OUTPUT_PATH,
        save_all=True,
        append_images=gif_frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=False,
        disposal=1,
    )
    print(f"Wrote {OUTPUT_PATH}: {len(gif_frames)} frames, {CANVAS_W}x{CANVAS_H}")


if __name__ == "__main__":
    main()
