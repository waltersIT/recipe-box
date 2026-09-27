"""Generates sample recipe screenshots and PDFs for tests (no copyrighted content)."""

import io

from PIL import Image, ImageDraw, ImageFont

TITLE = "Weeknight Lemon Chicken"
INGREDIENTS = [
    "2 lb chicken thighs",
    "1 1/2 tsp kosher salt",
    "3 tbsp olive oil",
    "4 cloves garlic, minced",
    "1/2 cup chicken stock",
    "2 lemons, juiced",
]
STEPS = [
    "1. Season the chicken with salt and let it rest for 15 minutes.",
    "2. Heat the oil in a large skillet and sear the chicken until golden, about 6 minutes per side.",
    "3. Add the garlic, stock and lemon juice, then simmer until the sauce thickens.",
]


def _font(size):
    for path in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw, text, font, width):
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def two_column_card() -> Image.Image:
    """A recipe card: title across the top, ingredients left, steps right."""
    image = Image.new("RGB", (1400, 900), "white")
    draw = ImageDraw.Draw(image)
    title, head, body = _font(52), _font(34), _font(26)
    draw.text((60, 40), TITLE, font=title, fill="black")
    draw.text((60, 120), "Prep Time: 15 mins   Cook Time: 25 mins   Serves 4", font=body, fill="#444")
    draw.text((60, 200), "Ingredients", font=head, fill="black")
    y = 260
    for item in INGREDIENTS:
        draw.text((60, y), item, font=body, fill="black")
        y += 44
    draw.text((620, 200), "Instructions", font=head, fill="black")
    y = 260
    for step in STEPS:
        for line in _wrap(draw, step, body, 720):
            draw.text((620, y), line, font=body, fill="black")
            y += 38
        y += 22
    return image


def image_bytes(image: Image.Image, fmt="PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def scanned_pdf() -> bytes:
    """An image-only PDF (like a scan), so it has no text layer."""
    buffer = io.BytesIO()
    two_column_card().save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def text_pdf() -> bytes:
    """A PDF with a real text layer and a two-column layout."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, height - 60, TITLE)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, height - 85, "Prep Time: 15 mins   Cook Time: 25 mins   Serves 4")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 125, "Ingredients")
    pdf.drawString(300, height - 125, "Instructions")
    pdf.setFont("Helvetica", 11)
    y = height - 148
    for item in INGREDIENTS:
        pdf.drawString(50, y, item)
        y -= 18
    y = height - 148
    for step in STEPS:
        words, line = step.split(), ""
        for word in words:
            if pdf.stringWidth(f"{line} {word}".strip(), "Helvetica", 11) > 260:
                pdf.drawString(300, y, line)
                y -= 15
                line = word
            else:
                line = f"{line} {word}".strip()
        pdf.drawString(300, y, line)
        y -= 24
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def phone_screenshots() -> list[Image.Image]:
    """Two overlapping phone screenshots of a blog-style recipe card."""
    width = 828
    page = Image.new("RGB", (width, 2600), "white")
    draw = ImageDraw.Draw(page)
    big, head, body, small = _font(54), _font(40), _font(32), _font(26)
    y = 40

    def text(value, font, x=40, fill="black", gap=16):
        nonlocal y
        for line in _wrap(draw, value, font, width - x - 40):
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + gap

    text(TITLE, big)
    text("★★★★★ 4.9 from 212 votes", small, fill="#b8860b")
    draw.rounded_rectangle((40, y, 330, y + 60), radius=12, fill="#e8e0d4")
    draw.text((70, y + 14), "Jump to Recipe", font=small, fill="black")
    y += 100
    text("Bright, garlicky chicken that's on the table in forty minutes.", body)
    y += 20
    for x, label in ((40, "PREP TIME"), (300, "COOK TIME"), (560, "TOTAL TIME")):
        draw.text((x, y), label, font=small, fill="#666")
    y += 44
    for x, value in ((40, "15 mins"), (300, "25 mins"), (560, "40 mins")):
        draw.text((x, y), value, font=body, fill="black")
    y += 70
    text("Servings: 4", body)
    y += 20
    text("Ingredients", head)
    text("1x 2x 3x", small, fill="#666")
    for item in INGREDIENTS[:4] + ["1/2 cup low-sodium chicken stock or dry white wine, at room temperature"] + INGREDIENTS[5:]:
        draw.rectangle((40, y + 6, 64, y + 30), outline="black", width=2)
        text(item, body, x=86, gap=12)
    y += 30
    text("Instructions", head)
    for step in STEPS:
        text(step, body, gap=12)
        y += 14
    y += 20
    text("Notes", head)
    text("Leftovers keep for 3 days in the fridge.", body)
    page = page.crop((0, 0, width, y + 40))

    status = _font(28)

    def frame(top, bottom):
        shot = Image.new("RGB", (width, bottom - top + 170), "white")
        shot.paste(page.crop((0, top, width, bottom)), (0, 120))
        d = ImageDraw.Draw(shot)
        d.text((60, 20), "9:41", font=status, fill="black")
        d.text((700, 20), "82%", font=status, fill="black")
        d.text((300, 70), "example.com", font=status, fill="#555")
        return shot

    split = page.height // 2
    return [frame(0, split + 200), frame(split - 200, page.height)]
