# pip install pillow pillow-heif

import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

INPUT_FOLDER = Path.home() / "Desktop" / "heic_input"
OUTPUT_FOLDER = Path.home() / "Desktop" / "jpg_output"
JPEG_QUALITY = 95
ALLOWED_EXTENSIONS = {".heic", ".heif"}
ZIP_EXTENSION = ".zip"


def is_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in ALLOWED_EXTENSIONS
        and not path.name.startswith("._")
        and "__MACOSX" not in path.parts
    )


def collect_images(folder: Path, recursive: bool = False) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(path for path in iterator if is_image(path))


def collect_zips(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ZIP_EXTENSION
    )


def output_path(stem: str, index: int, total: int) -> Path:
    if total == 1 or index == 1:
        filename = f"{stem}.jpg"
    else:
        filename = f"{stem}_{index}.jpg"
    return OUTPUT_FOLDER / filename


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


def extract_zip(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"unsafe path in {zip_path.name}: {info.filename}")
            target = destination.joinpath(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def convert_group(images: list[Path], stem: str) -> tuple[int, int]:
    converted = 0
    failures = 0
    total = len(images)
    for index, source in enumerate(images, start=1):
        destination = output_path(stem, index, total)
        print(f"Processing image {index} of {total}: {source.name} -> {destination.name}")
        try:
            convert_image(source, destination)
            converted += 1
            print(f"Saved: {destination.name}")
        except Exception as error:
            failures += 1
            print(f"Error: failed to convert {source.name}: {error}")
    return converted, failures


def process_zip(zip_path: Path, index: int, total: int) -> tuple[int, int]:
    print(f"Unpacking zip {index} of {total}: {zip_path.name}")
    stem = zip_path.stem
    if not stem:
        print(f"Error: no filename before .zip in {zip_path.name}")
        return 0, 1
    try:
        with tempfile.TemporaryDirectory(prefix="heic2jpg_") as temp_dir:
            extract_zip(zip_path, Path(temp_dir))
            images = collect_images(Path(temp_dir), recursive=True)
            noun = "image" if len(images) == 1 else "images"
            print(f"Found {len(images)} {noun} in {zip_path.name}")
            if not images:
                print(f"Error: no HEIC or HEIF files found in {zip_path.name}")
                return 0, 1
            print(f"Output filename base: {stem}")
            return convert_group(images, stem)
    except (zipfile.BadZipFile, ValueError, OSError) as error:
        print(f"Error: failed to unpack {zip_path.name}: {error}")
        return 0, 1


def main() -> None:
    started = time.perf_counter()
    print("Starting script...")
    print(f"Input folder: {INPUT_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"JPEG quality: {JPEG_QUALITY}")

    INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    zips = collect_zips(INPUT_FOLDER)
    images = collect_images(INPUT_FOLDER)
    zip_noun = "zip file" if len(zips) == 1 else "zip files"
    image_noun = "image" if len(images) == 1 else "images"
    print(f"Found {len(zips)} {zip_noun}")
    print(f"Found {len(images)} {image_noun}")

    if not zips and not images:
        print(f"Error: no zip, HEIC, or HEIF files found in {INPUT_FOLDER}")
        sys.exit(1)

    converted = 0
    failures = 0

    for index, zip_path in enumerate(zips, start=1):
        zip_converted, zip_failures = process_zip(zip_path, index, len(zips))
        converted += zip_converted
        failures += zip_failures

    if images:
        loose_noun = "image" if len(images) == 1 else "images"
        print(f"Processing {len(images)} loose {loose_noun}")
        for index, source in enumerate(images, start=1):
            destination = OUTPUT_FOLDER / f"{source.stem}.jpg"
            print(f"Processing image {index} of {len(images)}: {source.name} -> {destination.name}")
            try:
                convert_image(source, destination)
                converted += 1
                print(f"Saved: {destination.name}")
            except Exception as error:
                failures += 1
                print(f"Error: failed to convert {source.name}: {error}")

    elapsed = time.perf_counter() - started
    print(f"Finished processing {converted} images")
    if failures:
        print(f"Failed: {failures}")
    print(f"Total execution time: {elapsed:.2f} seconds")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
