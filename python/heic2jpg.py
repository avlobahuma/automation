# pip install pillow pillow-heif

import sys
import time
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

INPUT_FOLDER = Path.home() / "Desktop" / "heic_input"
OUTPUT_FOLDER = Path.home() / "Desktop" / "jpg_output"
JPEG_QUALITY = 95
ALLOWED_EXTENSIONS = {".heic", ".heif"}


def collect_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    )


def convert_image(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        icc_profile = image.info.get("icc_profile")
        exif = image.getexif()
        if image.mode != "RGB":
            image = image.convert("RGB")
        save_kwargs = {
            "quality": JPEG_QUALITY,
            "optimize": True,
        }
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        if exif:
            save_kwargs["exif"] = exif
        image.save(destination, "JPEG", **save_kwargs)


def main() -> None:
    started = time.perf_counter()
    print("Starting script...")
    print(f"Input folder: {INPUT_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"JPEG quality: {JPEG_QUALITY}")

    INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    images = collect_images(INPUT_FOLDER)
    print(f"Found {len(images)} images")

    if not images:
        print(f"Error: no HEIC or HEIF files found in {INPUT_FOLDER}")
        sys.exit(1)

    failures = 0
    for index, source in enumerate(images, start=1):
        destination = OUTPUT_FOLDER / f"{source.stem}.jpg"
        print(f"Processing image {index} of {len(images)}: {source.name}")
        try:
            convert_image(source, destination)
            print(f"Saved: {destination.name}")
        except Exception as error:
            failures += 1
            print(f"Error: failed to convert {source.name}: {error}")

    elapsed = time.perf_counter() - started
    converted = len(images) - failures
    print(f"Finished processing {converted} images")
    if failures:
        print(f"Failed: {failures} images")
    print(f"Total execution time: {elapsed:.2f} seconds")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
