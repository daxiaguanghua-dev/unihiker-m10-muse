"""Draw the mobile-readable SDK-token handoff illustration."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
OUT = HERE / "images" / "sdk-token-terminal-handoff.png"
FONT = "C:/Windows/Fonts/segoeui.ttf"
BOLD = "C:/Windows/Fonts/segoeuib.ttf"
MONO = "C:/Windows/Fonts/consola.ttf"

BG = "#F8FAF5"
INK = "#16392B"
MUTED = "#60756A"
GREEN = "#15583E"
PALE = "#EAF2EA"
LINE = "#CDDDD0"
BLUE = "#336BCA"


def font(size: int, bold: bool = False, mono: bool = False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, size)


def draw() -> None:
    im = Image.new("RGB", (1000, 1310), BG)
    d = ImageDraw.Draw(im)
    d.text((68, 48), "TOKEN HANDOFF", fill=GREEN, font=font(31, bold=True))
    d.text((68, 102), "Paste it on your computer,", fill=INK, font=font(53, bold=True))
    d.text((68, 172), "into the M10 session.", fill=INK, font=font(53, bold=True))
    d.text((70, 249), "The AI tool prepares the installer. You keep the token.", fill=MUTED, font=font(28))

    # Step 1: account website; the sample token is deliberately masked.
    d.rounded_rectangle((68, 328, 932, 618), radius=25, fill="#FFFFFF", outline=LINE, width=3)
    d.rounded_rectangle((69, 329, 931, 391), radius=25, fill=PALE)
    d.rectangle((69, 364, 931, 391), fill=PALE)
    d.text((101, 342), "01  MUSE GADGETS · ACCOUNT", fill=GREEN, font=font(31, bold=True))
    d.text((101, 416), "SDK tokens", fill=INK, font=font(43, bold=True))
    d.rounded_rectangle((101, 490, 735, 568), radius=13, fill="#F3F7F3", outline=LINE, width=2)
    d.text((130, 507), "mgst_••••••••••••••••", fill=INK, font=font(36, mono=True))
    d.text((765, 512), "COPY", fill=BLUE, font=font(32, bold=True))

    # A directional cue preserves the reading order on a narrow screen.
    d.line((500, 639, 500, 681), fill=GREEN, width=10)
    d.polygon(((477, 676), (500, 710), (523, 676)), fill=GREEN)
    d.text((534, 656), "PASTE ONCE", fill=GREEN, font=font(28, bold=True))

    # Step 2: terminal displayed on the computer, running on the M10.
    d.rounded_rectangle((68, 731, 932, 1089), radius=25, fill="#15231C")
    d.rounded_rectangle((69, 732, 931, 796), radius=24, fill="#20352A")
    d.rectangle((69, 772, 931, 796), fill="#20352A")
    for x, color in ((107, "#E99085"), (139, "#EAC980"), (171, "#8DD2A2")):
        d.ellipse((x, 756, x + 17, 773), fill=color)
    d.text((220, 744), "02  COMPUTER → M10 TERMINAL", fill="#DDEBDF", font=font(31, bold=True))
    d.text((106, 828), "$ bash install.sh", fill="#B7E7C6", font=font(42, mono=True))
    d.text((106, 906), "Muse SDK token (mgst_...;", fill="#F0F5EC", font=font(34, mono=True))
    d.text((106, 957), "input hidden):", fill="#F0F5EC", font=font(34, mono=True))
    d.rectangle((422, 967, 441, 997), fill="#7CE4A4")
    d.text((106, 1036), "Paste → Enter · no characters appear", fill="#9FD7B0", font=font(30))

    d.rounded_rectangle((68, 1131, 932, 1208), radius=16, fill=PALE)
    d.text((94, 1151), "03  THEN PAIR THE M10 IN THE MUSE APP", fill=GREEN, font=font(32, bold=True))
    d.text((69, 1251), "Illustration · no real token or app screenshot is shown.", fill=MUTED, font=font(26))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    draw()
