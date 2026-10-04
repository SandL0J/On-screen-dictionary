"""
Ekran Sözlüğü için çoklu çözünürlüklü Windows uygulama ikonu (.ico) üretici.
16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256 boyutlarını tek .ico dosyasına gömer.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def create_app_icon(output_path: Path):
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []

    for width, height in sizes:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Yuvarlak köşeli modern lacivert/indigo arka plan
        pad = max(1, width // 16)
        draw.rounded_rectangle(
            [pad, pad, width - pad, height - pad],
            radius=max(2, width // 4),
            fill=(30, 41, 59, 255), # slate-800
            outline=(99, 102, 241, 255), # indigo-500
            width=max(1, width // 24)
        )

        # "DE" harf logosu
        font_size = int(width * 0.45)
        try:
            # Sistemde arial veya segoui varsa dene
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = "DE"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (width - text_w) // 2
        text_y = (height - text_h) // 2 - max(1, width // 16)

        draw.text((text_x, text_y), text, fill=(248, 250, 252, 255), font=font)

        # Küçük bayrak renk vurgusu (Almanya bayrağı renk şeridi)
        stripe_h = max(1, height // 16)
        stripe_y = height - pad - stripe_h - max(1, height // 16)
        stripe_w = width - (pad * 4)
        stripe_x = pad * 2
        segment_w = stripe_w // 3

        draw.rectangle([stripe_x, stripe_y, stripe_x + segment_w, stripe_y + stripe_h], fill=(0, 0, 0, 255))
        draw.rectangle([stripe_x + segment_w, stripe_y, stripe_x + 2 * segment_w, stripe_y + stripe_h], fill=(220, 38, 38, 255))
        draw.rectangle([stripe_x + 2 * segment_w, stripe_y, stripe_x + stripe_w, stripe_y + stripe_h], fill=(234, 179, 8, 255))

        images.append(img)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        output_path,
        format="ICO",
        sizes=sizes,
        append_images=images[:-1]
    )
    print(f"[+] İkon başarıyla üretildi: {output_path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "app_icon.ico"
    create_app_icon(out)
