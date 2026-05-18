"""Run once to generate icon.ico — called automatically by main.py."""
import os


def generate(dest="icon.ico"):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    images = []
    for size in (16, 32, 48, 64, 128, 256):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        m = max(1, size // 10)
        # Dark rounded background
        draw.ellipse([m, m, size - m, size - m], fill=(30, 30, 46, 255))
        # Red record dot
        inner = size // 4
        draw.ellipse([inner, inner, size - inner, size - inner],
                     fill=(243, 139, 168, 255))
        images.append(img)

    try:
        images[0].save(dest, format="ICO",
                       sizes=[(img.width, img.height) for img in images],
                       append_images=images[1:])
        return True
    except Exception:
        return False


if __name__ == "__main__":
    ok = generate()
    print("icon.ico created" if ok else "Failed (Pillow not installed)")
