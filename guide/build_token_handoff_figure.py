"""Draw the SDK-token handoff illustration used by the article."""

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
    im = Image.new("RGB", (1800, 830), BG)
    d = ImageDraw.Draw(im)
    d.text((80, 46), "TOKEN HANDOFF", fill=GREEN, font=font(27, bold=True))
    d.text((80, 91), "Copy once. Paste on your computer.", fill=INK, font=font(56, bold=True))
    d.text((82, 165), "The AI tool handles setup; the credential stays in your hands.", fill=MUTED, font=font(30))

    # Website card: the token is intentionally masked in this illustration.
    d.rounded_rectangle((80, 235, 757, 585), radius=26, fill="#FFFFFF", outline=LINE, width=3)
    d.rounded_rectangle((81, 236, 756, 294), radius=25, fill=PALE)
    d.rectangle((81, 270, 756, 294), fill=PALE)
    d.text((115, 248), "01  MUSE GADGETS", fill=GREEN, font=font(29, bold=True))
    d.text((115, 322), "Account  →  SDK tokens", fill=INK, font=font(36, bold=True))
    d.rounded_rectangle((115, 395, 607, 470), radius=12, fill="#F3F7F3", outline=LINE, width=2)
    d.text((139, 412), "mgst_••••••••••••••••", fill=INK, font=font(34, mono=True))
    d.rounded_rectangle((115, 497, 355, 555), radius=12, fill=BLUE)
    d.text((162, 505), "COPY TOKEN", fill="#FFFFFF", font=font(29, bold=True))

    # Transfer arrow is visual only: the token never enters the AI chat.
    d.line((772, 407, 847, 407), fill=GREEN, width=10)
    d.polygon(((838, 385), (875, 407), (838, 429)), fill=GREEN)
    d.text((769, 449), "PASTE", fill=GREEN, font=font(25, bold=True))

    # Terminal card reproduces the installer's hidden-input prompt, no secret.
    d.rounded_rectangle((895, 235, 1720, 585), radius=26, fill="#15231C")
    d.rounded_rectangle((896, 236, 1719, 294), radius=25, fill="#20352A")
    d.rectangle((896, 270, 1719, 294), fill="#20352A")
    for x, color in ((932, "#E99085"), (960, "#EAC980"), (988, "#8DD2A2")):
        d.ellipse((x, 258, x + 13, 271), fill=color)
    d.text((1030, 248), "02  COMPUTER → M10 TERMINAL", fill="#DDEBDF", font=font(29, bold=True))
    d.text((935, 328), "$ bash install.sh", fill="#B7E7C6", font=font(39, mono=True))
    d.text((935, 395), "Muse SDK token (mgst_...;", fill="#F0F5EC", font=font(31, mono=True))
    d.text((935, 439), "input hidden):", fill="#F0F5EC", font=font(31, mono=True))
    d.rectangle((1226, 446, 1244, 474), fill="#7CE4A4")
    d.text((935, 512), "Paste → Enter. Nothing appears on screen.", fill="#9FD7B0", font=font(29))

    # The role boundary is the point of the diagram.
    d.line((80, 646, 1720, 646), fill=LINE, width=3)
    steps = [
        (80, "AI PREPARES INSTALLER"),
        (658, "PASTE IN M10 SESSION"),
        (1244, "MUSE APP PAIRS M10"),
    ]
    for idx, (x, label) in enumerate(steps, start=1):
        d.ellipse((x, 674, x + 50, 724), fill=GREEN)
        d.text((x + 16, 682), str(idx), fill="#FFFFFF", font=font(28, bold=True))
        d.text((x + 68, 684), label, fill=INK, font=font(26, bold=True))
    d.text((80, 762), "Illustration · the actual token is never shown or sent to the AI chat.", fill=MUTED, font=font(24))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    draw()
