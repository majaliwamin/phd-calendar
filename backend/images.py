"""Image validation/conversion (no web framework dependency, so it is unit-testable)."""
import io
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF = True
except Exception:
    HEIF = False
MAX = 15_000_000

def to_jpeg(data, name=""):
    from PIL import Image, ImageOps
    if len(data) > MAX:
        raise ValueError("Image is larger than 15 MB. Choose a smaller photo.")
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        heic = name.lower().endswith((".heic", ".heif"))
        raise ValueError("HEIC/HEIF needs the optional package: pip install pillow-heif. Meanwhile choose a JPG/PNG or use the camera."
                         if heic and not HEIF else "This file is not a readable image (use JPG, PNG, WebP or HEIC).")
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3]); im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((1024, 1024)); b = io.BytesIO(); im.save(b, "JPEG", quality=90)
    return b.getvalue()
