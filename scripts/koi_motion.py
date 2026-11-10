
from bisect import bisect_left
from pathlib import Path
import math
from PIL import Image

SOURCE = Path("koi/koi.gif")
OUTPUT = Path("koi/koi-explorer.gif")

# Swimming area and animation settings
WIDTH, HEIGHT = 480, 320
FRAMES = 180
FRAME_MS = 80

# Direction the fish's head faces in its original image.
# Options: "up", "down", "left", "right"
HEAD_DIRECTION = "up"

# Natural tail movement
TAIL_SWING_PIXELS = 4.0
TAIL_CYCLES = 9

# Waypoints spread across the swimming area.
# The fish follows smooth curves between these points.
WAYPOINTS = [
    (0.19, 0.24),
    (0.39, 0.13),
    (0.76, 0.23),
    (0.86, 0.44),
    (0.77, 0.73),
    (0.52, 0.86),
    (0.22, 0.74),
    (0.13, 0.50),
    (0.33, 0.36),
    (0.65, 0.42),
    (0.69, 0.60),
    (0.43, 0.65),
]


def catmull_rom(p0, p1, p2, p3, u):
    """Generate a smooth swimming curve."""
    u2 = u * u
    u3 = u2 * u

    return tuple(
        0.5 * (
            2 * b
            + (-a + c) * u
            + (2*a - 5*b + 4*c - d) * u2
            + (-a + 3*b - 3*c + d) * u3
        )
        for a, b, c, d in zip(p0, p1, p2, p3)
    )


def course(s):
    """Calculate a position along the closed route."""
    n = len(WAYPOINTS)
    s %= n

    j = int(s)
    u = s - j

    return catmull_rom(
        *[WAYPOINTS[(j+k) % n] for k in (-1, 0, 1, 2)],
        u
    )


def constant_speed_positions(frame_count):
    """Keep the fish moving smoothly at near-constant speed."""
    samples = 3600

    pts = [
        course(len(WAYPOINTS) * i / samples)
        for i in range(samples + 1)
    ]

    distances = [0.0]

    for a, b in zip(pts, pts[1:]):
        distance = math.hypot(
            b[0] - a[0],
            b[1] - a[1]
        )
        distances.append(distances[-1] + distance)

    total = distances[-1]
    positions = []

    for i in range(frame_count):
        target = total * i / frame_count
        ix = max(1, bisect_left(distances, target))

        fraction = (
            (target - distances[ix - 1])
            / max(1e-10, distances[ix] - distances[ix - 1])
        )

        a = pts[ix - 1]
        b = pts[ix]

        x = a[0] + fraction * (b[0] - a[0])
        y = a[1] + fraction * (b[1] - a[1])

        positions.append((x, y))

    return positions


def bend_tail(sprite, phase):
    """Wave the fish's tail while keeping its head steady."""

    if HEAD_DIRECTION in ("left", "right"):
        transpose = (
            Image.Transpose.ROTATE_270
            if HEAD_DIRECTION == "left"
            else Image.Transpose.ROTATE_90
        )

        inverse = (
            Image.Transpose.ROTATE_90
            if HEAD_DIRECTION == "left"
            else Image.Transpose.ROTATE_270
        )

        upright = sprite.transpose(transpose)

    elif HEAD_DIRECTION == "down":
        upright = sprite.transpose(
            Image.Transpose.ROTATE_180
        )
        inverse = Image.Transpose.ROTATE_180

    else:
        upright = sprite
        inverse = None

    w, h = upright.size
    extra = math.ceil(TAIL_SWING_PIXELS) + 2

    result = Image.new(
        "RGBA",
        (w + 2 * extra, h),
        (0, 0, 0, 0)
    )

    for y in range(h):
        fraction = y / max(1, h - 1)

        # Head is steady; tail moves progressively more.
        strength = max(
            0.0,
            (fraction - 0.32) / 0.68
        ) ** 2

        shift = round(
            TAIL_SWING_PIXELS
            * strength
            * math.sin(phase - 1.8 * fraction)
        )

        strip = upright.crop((0, y, w, y + 1))
        result.paste(strip, (extra + shift, y))

    return (
        result.transpose(inverse)
        if inverse else result
    )


def main():
    if HEAD_DIRECTION not in (
        "up", "down", "left", "right"
    ):
        raise ValueError("Invalid HEAD_DIRECTION")

    if not SOURCE.exists():
        raise FileNotFoundError(
            "Missing koi/koi.gif. Generate the original koi first."
        )

    source = Image.open(SOURCE)
    source.seek(0)

    # Preserve the koi appearance produced by Git Koi.
    sprite = source.convert("RGBA")

    bounds = sprite.getchannel("A").getbbox()

    if not bounds:
        raise ValueError("Source koi image is empty")

    sprite = sprite.crop(bounds)

    # Fit into the area while retaining original proportions.
    scale = min(
        1.0,
        96 / sprite.width,
        110 / sprite.height
    )

    if scale < 1.0:
        sprite = sprite.resize(
            (
                max(1, round(sprite.width * scale)),
                max(1, round(sprite.height * scale))
            ),
            Image.Resampling.NEAREST
        )

    positions = constant_speed_positions(FRAMES)
    frames = []

    head_angles = {
        "right": 0,
        "up": 90,
        "left": 180,
        "down": 270
    }

    diagonal = math.hypot(
        sprite.width + 2 * TAIL_SWING_PIXELS + 6,
        sprite.height
    )

    margin = math.ceil(diagonal / 2) + 8

    for i, (nx, ny) in enumerate(positions):

        previous = positions[(i - 1) % FRAMES]
        following = positions[(i + 1) % FRAMES]

        dx = following[0] - previous[0]
        dy = following[1] - previous[1]

        # Head follows the movement direction.
        heading = math.degrees(math.atan2(-dy, dx))

        turn = heading - head_angles[HEAD_DIRECTION]

        # Generate side-to-side tail movement.
        phase = (
            2 * math.pi * TAIL_CYCLES * i / FRAMES
        )

        fish = bend_tail(sprite, phase)

        # Rotate the fish to swim head-first.
        fish = fish.rotate(
            turn,
            resample=Image.Resampling.BICUBIC,
            expand=True
        )

        cx = margin + nx * (WIDTH - 2 * margin)
        cy = margin + ny * (HEIGHT - 2 * margin)

        x = round(cx - fish.width / 2)
        y = round(cy - fish.height / 2)

        # Keep the fish within the swimming area.
        x = max(0, min(WIDTH - fish.width, x))
        y = max(0, min(HEIGHT - fish.height, y))

        canvas = Image.new(
            "RGBA",
            (WIDTH, HEIGHT),
            (0, 0, 0, 0)
        )

        canvas.alpha_composite(fish, (x, y))
        frames.append(canvas)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        disposal=2,
        optimize=False
    )

    print(
        f"Natural koi animation generated: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
