"""Assemble board-captured screens into article figures; no UI is synthesized."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SHOTS = HERE / 'screenshots'
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
FONT = 'C:/Windows/Fonts/arial.ttf'
font = ImageFont.truetype(FONT, 22)


def grid(name, items):
    canvas = Image.new('RGB', (1040, 1420), '#e9ece6')
    draw = ImageDraw.Draw(canvas)
    for index, (filename, caption) in enumerate(items):
        picture = Image.open(SHOTS / filename).convert('RGB').resize((480, 640), Image.Resampling.NEAREST)
        x = 20 + (index % 2) * 520
        y = 20 + (index // 2) * 700
        canvas.paste(picture, (x, y))
        draw.text((x + 8, y + 648), caption, fill='#202d29', font=font)
    target = OUT / name
    canvas.save(target, optimize=True)
    print(target)


grid('dashboard-overview.png', [
    ('live-01-system.png', '01  System'),
    ('live-02-connection.png', '02  Connection'),
    ('live-03-sensors.png', '03  Sensors'),
    ('live-04-sound.png', '04  Sound & I/O'),
])
grid('work-overview.png', [
    ('05-work-ready.png', 'Ready'),
    ('06-recording.png', 'Recording'),
    ('07-sending.png', 'Sending'),
    ('10-reply-page1.png', 'Muse reply'),
])
