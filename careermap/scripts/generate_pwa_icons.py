"""CareerMap PWA Icon Generator.
Generates responsive app icons for iOS Safari, Web App Manifest, and Favicon.
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ICONS_DIR = STATIC_DIR / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

def create_careermap_icon(size: int, is_maskable: bool = False) -> Image.Image:
    # Create RGBA canvas
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(size * 0.05) if not is_maskable else int(size * 0.12)
    radius = int(size * 0.22) if not is_maskable else 0

    # Background rounded rectangle or full fill for maskable
    bg_color = (15, 23, 42, 255)  # #0f172a slate-900
    if is_maskable:
        draw.rectangle([0, 0, size, size], fill=bg_color)
    else:
        draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=radius, fill=bg_color)

    # Inner circular glowing accent gradient simulation
    center_x = size // 2
    center_y = size // 2
    accent_r = int((size - 2 * margin) * 0.38)
    
    # Outer circle cyan rim
    rim_box = [center_x - accent_r, center_y - accent_r, center_x + accent_r, center_y + accent_r]
    draw.ellipse(rim_box, fill=(2, 132, 199, 255)) # #0284c7 sky-600

    # Inner circle gradient depth
    inner_r = int(accent_r * 0.90)
    inner_box = [center_x - inner_r, center_y - inner_r, center_x + inner_r, center_y + inner_r]
    draw.ellipse(inner_box, fill=(3, 105, 161, 255)) # #0369a1 sky-700

    # Draw bold letter 'C' and pinpoint compass needle
    # Semi-donut arc for 'C'
    c_outer_r = int(inner_r * 0.68)
    c_inner_r = int(inner_r * 0.36)
    stroke_w = c_outer_r - c_inner_r

    # Use arc/pie to draw 'C' opening to the right
    draw.arc(
        [center_x - c_outer_r, center_y - c_outer_r, center_x + c_outer_r, center_y + c_outer_r],
        start=40, end=320, fill=(255, 255, 255, 255), width=stroke_w
    )

    # Accent star/dot at the opening of C (representing map pinpoint / dental beacon)
    dot_x = int(center_x + c_outer_r * 0.58)
    dot_y = center_y
    dot_r = max(2, int(stroke_w * 0.32))
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=(56, 189, 248, 255))

    return img

def main():
    sizes = {
        "icon-192.png": (192, False),
        "icon-512.png": (512, False),
        "icon-maskable-512.png": (512, True),
        "apple-touch-icon.png": (180, False),
        "apple-touch-icon-180x180.png": (180, False),
        "favicon.png": (32, False),
    }

    print("Generating CareerMap PWA Icons...")
    for filename, (size, is_maskable) in sizes.items():
        img = create_careermap_icon(size, is_maskable)
        
        # Save in icons/ directory
        target_path = ICONS_DIR / filename
        img.save(target_path, "PNG", optimize=True)
        print(f"  [OK] Saved {target_path.name} ({size}x{size})")

        # Also save 192 & 512 at root of static for backwards compatibility
        if filename in ["icon-192.png", "icon-512.png", "apple-touch-icon.png"]:
            root_static_path = STATIC_DIR / filename
            img.save(root_static_path, "PNG", optimize=True)
            print(f"  [OK] Root mirror saved {root_static_path.name}")

    print("All CareerMap PWA icons generated successfully!")

if __name__ == "__main__":
    main()
