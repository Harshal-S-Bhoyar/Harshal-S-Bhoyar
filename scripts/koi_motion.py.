"""Move git-koi's transparent animation through a bounded, looping swimming area."""
from pathlib import Path
from PIL import Image
import math

SOURCE = Path('koi/koi.gif')
DEST = Path('koi/koi-explorer.gif')
WIDTH, HEIGHT = 400, 260
FRAMES = 180
FRAME_MS = 80


def path_point(t):
    """Multi-frequency closed curve: broad turns, loops, and exploratory sweeps."""
    x = 0.57 * math.sin(t) + 0.29 * math.sin(3*t + 0.45) + 0.14 * math.sin(5*t + 0.9)
    y = 0.52 * math.sin(2*t + 0.4) + 0.30 * math.sin(3*t - 0.65) + 0.18 * math.sin(4*t + 1.3)
    return x, y


def main():
    if not SOURCE.exists():
        raise FileNotFoundError('Missing koi/koi.gif; run git-koi first.')
    original = Image.open(SOURCE)
    if original.n_frames < 1:
        raise ValueError('The original koi GIF contains no frames.')

    frames = []
    # Bound the whole fish, including animated tail, inside the canvas.
    max_fish_w, max_fish_h = 104, 88
    for i in range(FRAMES):
        original.seek(i % original.n_frames)
        sprite = original.convert('RGBA')
        alpha = sprite.getchannel('A')
        bounds = alpha.getbbox()
        if bounds is None:
            raise ValueError('Empty source fish frame')
        sprite = sprite.crop(bounds)
        scale = min(1.0, max_fish_w/sprite.width, max_fish_h/sprite.height)
        if scale < 1:
            sprite = sprite.resize(
                (max(1, round(sprite.width*scale)), max(1, round(sprite.height*scale))),
                Image.Resampling.NEAREST,
            )

        t = 2 * math.pi * i / FRAMES
        px, py = path_point(t)
        # Allow the center to approach the edges without cutting off the fish.
        travel_x = (WIDTH - sprite.width) / 2 - 6
        travel_y = (HEIGHT - sprite.height) / 2 - 6
        x = round((WIDTH - sprite.width) / 2 + px * travel_x)
        y = round((HEIGHT - sprite.height) / 2 + py * travel_y)
        image = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        image.alpha_composite(sprite, (x, y))
        frames.append(image)

    DEST.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        DEST, save_all=True, append_images=frames[1:],
        duration=FRAME_MS, loop=0, disposal=2, optimize=True,
        transparency=0,
    )
    print(f'Created {DEST} ({WIDTH}x{HEIGHT}; {FRAMES} frames)')


if __name__ == '__main__':
    main()
