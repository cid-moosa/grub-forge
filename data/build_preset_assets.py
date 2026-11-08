"""
GRUB Forge - Theme Asset & Distro Icon Generator
Generates high-resolution 1080p authentic wallpapers and crisp icons for:
Kali Linux, Arch Linux, Debian, Fedora, Ubuntu, and Cyber Glow.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


def create_kali_wallpaper(out_path: Path):
    """Generates authentic Kali Linux cyber-dragon dark wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (8, 12, 22, 255))
    draw = ImageDraw.Draw(img)

    # 1. Background radial glow in top-center
    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    center_x, center_y = w // 2, int(h * 0.38)
    for r in range(500, 0, -25):
        alpha = int(45 * (1.0 - (r / 500.0)))
        glow_draw.ellipse(
            [center_x - r, center_y - int(r * 0.7), center_x + r, center_y + int(r * 0.7)],
            fill=(0, 180, 216, alpha)
        )
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=40))
    img.alpha_composite(glow_img)

    # 2. Subtle cyber grid lines
    grid_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_img)
    for x in range(0, w, 60):
        grid_draw.line([(x, 0), (x, h)], fill=(0, 180, 216, 12), width=1)
    for y in range(0, h, 60):
        grid_draw.line([(0, y), (w, y)], fill=(0, 180, 216, 12), width=1)
    img.alpha_composite(grid_img)

    # 3. Kali Dragon Emblem Vector Path (curves & wings)
    emblem_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    e_draw = ImageDraw.Draw(emblem_img)
    cx, cy = w // 2, int(h * 0.28)

    # Outer decorative hexagonal tech frame
    hex_pts = []
    r_hex = 110
    for i in range(6):
        ang = math.radians(60 * i - 30)
        hex_pts.append((cx + r_hex * math.cos(ang), cy + r_hex * math.sin(ang)))
    e_draw.polygon(hex_pts, outline=(0, 245, 212, 180), width=3)

    # Inner decorative ring
    e_draw.ellipse([cx - 85, cy - 85, cx + 85, cy + 85], outline=(0, 180, 216, 140), width=2)

    # Kali Dragon stylized silhouette polygon
    dragon_pts = [
        (cx, cy - 55),
        (cx + 15, cy - 40),
        (cx + 45, cy - 35),
        (cx + 65, cy - 10),
        (cx + 50, cy + 20),
        (cx + 35, cy + 15),
        (cx + 25, cy + 35),
        (cx + 40, cy + 55),
        (cx + 10, cy + 45),
        (cx, cy + 60),
        (cx - 10, cy + 45),
        (cx - 40, cy + 55),
        (cx - 25, cy + 35),
        (cx - 35, cy + 15),
        (cx - 50, cy + 20),
        (cx - 65, cy - 10),
        (cx - 45, cy - 35),
        (cx - 15, cy - 40),
    ]
    e_draw.polygon(dragon_pts, fill=(0, 245, 212, 220), outline=(255, 255, 255, 240), width=2)

    # Inner eye/core glow
    e_draw.ellipse([cx - 6, cy - 25, cx + 6, cy - 13], fill=(255, 255, 255, 255))

    img.alpha_composite(emblem_img)

    # 4. Vignette border darkening
    vig_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vig_draw = ImageDraw.Draw(vig_img)
    vig_draw.rectangle([0, 0, w, h], outline=(4, 6, 12, 220), width=18)
    img.alpha_composite(vig_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def create_arch_wallpaper(out_path: Path):
    """Generates authentic Arch Linux dark minimalist wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (14, 16, 24, 255))

    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    cx, cy = w // 2, int(h * 0.28)
    for r in range(400, 0, -20):
        alpha = int(40 * (1.0 - (r / 400.0)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(23, 147, 209, alpha))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=35))
    img.alpha_composite(glow_img)

    # Arch Triangle Logo
    arch_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    a_draw = ImageDraw.Draw(arch_img)
    tri_pts = [
        (cx, cy - 70),
        (cx + 65, cy + 55),
        (cx + 35, cy + 45),
        (cx + 10, cy + 30),
        (cx, cy + 45),
        (cx - 10, cy + 30),
        (cx - 35, cy + 45),
        (cx - 65, cy + 55),
    ]
    a_draw.polygon(tri_pts, fill=(23, 147, 209, 230), outline=(137, 220, 235, 255), width=2)
    img.alpha_composite(arch_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def create_debian_wallpaper(out_path: Path):
    """Generates Debian cosmic crimson spiral wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (20, 10, 16, 255))

    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    cx, cy = w // 2, int(h * 0.28)
    for r in range(420, 0, -20):
        alpha = int(45 * (1.0 - (r / 420.0)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(215, 10, 83, alpha))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=35))
    img.alpha_composite(glow_img)

    # Debian Spiral
    deb_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d_draw = ImageDraw.Draw(deb_img)
    spiral_pts = []
    for deg in range(0, 720, 10):
        rad = math.radians(deg)
        dist = 8 + (deg * 0.08)
        px = cx + dist * math.cos(rad)
        py = cy + dist * math.sin(rad)
        spiral_pts.append((px, py))
    if len(spiral_pts) > 1:
        d_draw.line(spiral_pts, fill=(245, 60, 120, 230), width=6)
    img.alpha_composite(deb_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def create_fedora_wallpaper(out_path: Path):
    """Generates Fedora horizon geometric sapphire wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (14, 22, 38, 255))

    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    cx, cy = w // 2, int(h * 0.28)
    for r in range(400, 0, -20):
        alpha = int(45 * (1.0 - (r / 400.0)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(41, 100, 230, alpha))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=35))
    img.alpha_composite(glow_img)

    # Fedora Infinity / F logo
    f_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    f_draw = ImageDraw.Draw(f_img)
    f_draw.ellipse([cx - 50, cy - 40, cx + 15, cy + 25], outline=(90, 160, 255, 230), width=10)
    f_draw.ellipse([cx - 15, cy - 25, cx + 50, cy + 40], outline=(41, 100, 230, 230), width=10)
    img.alpha_composite(f_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def create_ubuntu_wallpaper(out_path: Path):
    """Generates Ubuntu Yaru aubergine-orange wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (38, 14, 30, 255))

    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    cx, cy = w // 2, int(h * 0.28)
    for r in range(400, 0, -20):
        alpha = int(45 * (1.0 - (r / 400.0)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(233, 84, 32, alpha))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=35))
    img.alpha_composite(glow_img)

    u_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    u_draw = ImageDraw.Draw(u_img)
    u_draw.ellipse([cx - 45, cy - 45, cx + 45, cy + 45], outline=(233, 84, 32, 240), width=8)
    for i in range(3):
        ang = math.radians(120 * i - 30)
        px = cx + 45 * math.cos(ang)
        py = cy + 45 * math.sin(ang)
        u_draw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=(255, 255, 255, 255))
    img.alpha_composite(u_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def create_cyber_glow_wallpaper(out_path: Path):
    """Generates Catppuccin Mocha cybernetic matrix wallpaper."""
    w, h = 1920, 1080
    img = Image.new("RGBA", (w, h), (17, 17, 27, 255))

    glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow_img)
    cx, cy = w // 2, int(h * 0.28)
    for r in range(450, 0, -25):
        alpha = int(40 * (1.0 - (r / 450.0)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(137, 180, 250, alpha))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=40))
    img.alpha_composite(glow_img)

    c_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(c_img)
    # Hexagon icon
    pts = []
    for i in range(6):
        a = math.radians(60 * i)
        pts.append((cx + 55 * math.cos(a), cy + 55 * math.sin(a)))
    c_draw.polygon(pts, outline=(137, 180, 250, 240), width=3)
    c_draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(166, 227, 161, 230))
    img.alpha_composite(c_img)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)


def generate_distro_icons(icons_dir: Path):
    """Generates crisp 48x48 RGBA distro icons."""
    icons_dir.mkdir(parents=True, exist_ok=True)

    def new_canvas():
        return Image.new("RGBA", (48, 48), (0, 0, 0, 0))

    # 1. Kali icon (blue/cyan dragon silhouette)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    pts = [(24, 6), (36, 16), (42, 28), (34, 38), (24, 42), (14, 38), (6, 28), (12, 16)]
    d.polygon(pts, fill=(0, 245, 212, 255), outline=(0, 180, 216, 255), width=2)
    d.ellipse([21, 16, 27, 22], fill=(255, 255, 255, 255))
    im.save(icons_dir / "kali.png")

    # 2. Arch icon (cyan triangular peak)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    pts = [(24, 6), (42, 42), (32, 38), (24, 32), (16, 38), (6, 42)]
    d.polygon(pts, fill=(23, 147, 209, 255), outline=(137, 220, 235, 255), width=2)
    im.save(icons_dir / "arch.png")

    # 3. Debian icon (crimson spiral)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    pts = []
    for deg in range(0, 540, 15):
        rad = math.radians(deg)
        dist = 4 + (deg * 0.035)
        pts.append((24 + dist * math.cos(rad), 24 + dist * math.sin(rad)))
    d.line(pts, fill=(215, 10, 83, 255), width=3)
    im.save(icons_dir / "debian.png")

    # 4. Fedora icon (blue infinity F)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    d.ellipse([8, 14, 28, 34], outline=(90, 160, 255, 255), width=4)
    d.ellipse([20, 14, 40, 34], outline=(41, 100, 230, 255), width=4)
    im.save(icons_dir / "fedora.png")

    # 5. Ubuntu icon (orange circle with 3 dots)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    d.ellipse([8, 8, 40, 40], outline=(233, 84, 32, 255), width=4)
    for i in range(3):
        ang = math.radians(120 * i)
        px = 24 + 16 * math.cos(ang)
        py = 24 + 16 * math.sin(ang)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(255, 255, 255, 255))
    im.save(icons_dir / "ubuntu.png")

    # 6. Windows icon (4 blue quadrants)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    d.polygon([(8, 12), (22, 10), (22, 22), (8, 22)], fill=(0, 164, 239, 255))
    d.polygon([(26, 9), (40, 7), (40, 22), (26, 22)], fill=(0, 164, 239, 255))
    d.polygon([(8, 26), (22, 26), (22, 38), (8, 36)], fill=(0, 164, 239, 255))
    d.polygon([(26, 26), (40, 26), (40, 41), (26, 39)], fill=(0, 164, 239, 255))
    im.save(icons_dir / "windows.png")

    # 7. Generic Linux icon (Tux penguin egg badge)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    d.ellipse([14, 8, 34, 40], fill=(240, 240, 240, 255), outline=(30, 30, 40, 255), width=3)
    d.ellipse([18, 18, 30, 36], fill=(255, 255, 255, 255))
    d.polygon([(21, 16), (27, 16), (24, 22)], fill=(250, 180, 20, 255))
    im.save(icons_dir / "linux.png")

    # 8. Gear icon (UEFI / settings)
    im = new_canvas()
    d = ImageDraw.Draw(im)
    d.ellipse([12, 12, 36, 36], outline=(166, 173, 200, 255), width=5)
    d.ellipse([20, 20, 28, 28], fill=(166, 173, 200, 255))
    im.save(icons_dir / "gear.png")


def generate_theme_configs(themes_dir: Path):
    """Generates theme.txt and slice graphics for each bundled theme."""
    configs = {
        "kali": {
            "title": "Kali GNU/Linux (Rolling)",
            "title_color": "#00f5d4",
            "desktop_color": "#080c16",
            "item_color": "#cdd6f4",
            "selected_item_color": "#ffffff",
            "hl_bg": "#0077b6",
            "hl_border": "#00f5d4",
        },
        "arch": {
            "title": "Arch Linux",
            "title_color": "#1793d1",
            "desktop_color": "#0e1018",
            "item_color": "#a6adc8",
            "selected_item_color": "#ffffff",
            "hl_bg": "#1e2230",
            "hl_border": "#1793d1",
        },
        "debian": {
            "title": "Debian GNU/Linux 12 (Bookworm)",
            "title_color": "#d70a53",
            "desktop_color": "#101018",
            "item_color": "#cdd6f4",
            "selected_item_color": "#ffffff",
            "hl_bg": "#2b111e",
            "hl_border": "#d70a53",
        },
        "fedora": {
            "title": "Fedora Linux 41",
            "title_color": "#51a2da",
            "desktop_color": "#0a1424",
            "item_color": "#cdd6f4",
            "selected_item_color": "#ffffff",
            "hl_bg": "#142d4c",
            "hl_border": "#51a2da",
        },
        "ubuntu": {
            "title": "Ubuntu 24.04 LTS",
            "title_color": "#e95420",
            "desktop_color": "#181016",
            "item_color": "#cdd6f4",
            "selected_item_color": "#ffffff",
            "hl_bg": "#3c1828",
            "hl_border": "#e95420",
        },
        "cyber_glow": {
            "title": "GRUB Boot Menu",
            "title_color": "#89b4fa",
            "desktop_color": "#11111b",
            "item_color": "#cdd6f4",
            "selected_item_color": "#ffffff",
            "hl_bg": "#313244",
            "hl_border": "#89b4fa",
        }
    }

    for tid, cfg in configs.items():
        tdir = themes_dir / tid
        tdir.mkdir(parents=True, exist_ok=True)
        txt_path = tdir / "theme.txt"
        theme_body = f"""# GRUB Forge Theme Configuration - {tid.capitalize()}
title-text: "{cfg['title']}"
title-font: "Unifont Regular 18"
title-color: "{cfg['title_color']}"
desktop-image: "background.png"
desktop-color: "{cfg['desktop_color']}"
message-font: "Unifont Regular 14"
message-color: "{cfg['item_color']}"
terminal-font: "Unifont Regular 14"

+ boot_menu {{
    left = 20%
    top = 25%
    width = 60%
    height = 50%
    item_font = "Unifont Regular 16"
    item_color = "{cfg['item_color']}"
    selected_item_font = "Unifont Bold 16"
    selected_item_color = "{cfg['selected_item_color']}"
    selected_item_pixmap_style = "highlight_*.png"
    item_height = 36
    item_padding = 8
    item_spacing = 6
}}

+ label {{
    top = 78%
    left = 20%
    width = 60%
    align = "center"
    id = "__timeout__"
    text = "The highlighted entry will be executed automatically in %d seconds."
    color = "{cfg['title_color']}"
    font = "Unifont Regular 14"
}}
"""
        txt_path.write_text(theme_body, encoding="utf-8")


if __name__ == "__main__":
    base = Path(__file__).parent
    themes = base / "themes"
    create_kali_wallpaper(themes / "kali" / "background.png")
    create_arch_wallpaper(themes / "arch" / "background.png")
    create_debian_wallpaper(themes / "debian" / "background.png")
    create_fedora_wallpaper(themes / "fedora" / "background.png")
    create_ubuntu_wallpaper(themes / "ubuntu" / "background.png")
    create_cyber_glow_wallpaper(themes / "cyber_glow" / "background.png")
    generate_distro_icons(base / "icons" / "distros")
    generate_theme_configs(themes)
    print("Assets successfully generated!")
