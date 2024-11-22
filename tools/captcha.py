import os
import random
import string
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def generate_captcha(text_length=4):
    # Generates captcha text
    captcha_text = ''.join(random.choices(string.digits, k=text_length))

    # Image parameters
    width, height = 160, 60
    background_color = (255, 255, 255)
    font_size = 42

    # Creates captcha image
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Path to Haunt.ttf font
    font_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts', 'Haunt.ttf')

    # Loads font
    font = ImageFont.truetype(font_path, font_size)

    # Draws captcha symbols
    for i, char in enumerate(captcha_text):
        min_brightness = 0
        max_brightness = 200
        text_color = (
            random.randint(min_brightness, max_brightness),
            random.randint(min_brightness, max_brightness),
            random.randint(min_brightness, max_brightness)
        )
        position = ((width // text_length) * i + 10, (height - font_size) // 2)

        # Rotates symbol
        rotated_char = Image.new('RGBA', (font_size, font_size), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(rotated_char)
        char_draw.text((0, 0), char, font=font, fill=text_color)
        rotated_char = rotated_char.rotate(random.randint(-30, 30), expand=1)

        # Adds symbol to captcha image
        image.paste(rotated_char, position, rotated_char)

    # Adds noise
    for _ in range(int((width * height) * 0.05)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        noise_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.point((x, y), fill=noise_color)

    # Adds lines
    for _ in range(5):
        start_pos = (random.randint(0, width), random.randint(0, height))
        end_pos = (random.randint(0, width), random.randint(0, height))
        line_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.line([start_pos, end_pos], fill=line_color, width=2)

    # Saves image to byte stream
    byte_io = BytesIO()
    image.save(byte_io, 'PNG')
    byte_io.seek(0)

    return captcha_text, byte_io
