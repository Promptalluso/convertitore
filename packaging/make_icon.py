"""Create original platform icons for the working app name."""

import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent


def base_icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = size // 16
    draw.rounded_rectangle((inset, inset, size - inset, size - inset),
                           radius=size // 5, fill="#F97331")
    page = (int(size * .27), int(size * .22), int(size * .69), int(size * .77))
    draw.rounded_rectangle(page, radius=size // 22, fill="#FFF9F1")
    draw.rectangle((int(size * .34), int(size * .37), int(size * .62), int(size * .41)), fill="#F97331")
    draw.rectangle((int(size * .34), int(size * .48), int(size * .57), int(size * .52)), fill="#F97331")
    draw.polygon([(int(size * .62), int(size * .60)), (int(size * .76), int(size * .60)),
                  (int(size * .76), int(size * .54)), (int(size * .87), int(size * .68)),
                  (int(size * .76), int(size * .82)), (int(size * .76), int(size * .75)),
                  (int(size * .62), int(size * .75))], fill="#29221F")
    return image


def main() -> None:
    image = base_icon(1024)
    image.save(HERE / "icon.png")
    image.save(HERE / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin":
        iconset = HERE / "Convertitore.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            image.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            image.resize((size * 2, size * 2), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "icon.icns")], check=True)


if __name__ == "__main__":
    main()
