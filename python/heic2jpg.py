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

VINTED_FOLDER = Path.home() / "Desktop" / "vinted"
JPEG_QUALITY = 95
ALLOWED_EXTENSIONS = {".heic", ".heif"}
ZIP_EXTENSION = ".zip"


def collect_zips(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == ZIP_EXTENSION
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


def extract_images(zip_path: Path, destination: Path) -> list[Path]:
    extracted = []
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"unsafe path in {zip_path.name}: {info.filename}")
            if "__MACOSX" in member.parts or member.name.startswith("._"):
                continue
            if member.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            target = destination.joinpath(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
            print(f"Extracted: {member.name}")
    return extracted


def process_zip(zip_path: Path, temp_dir: Path) -> tuple[int, int, int]:
    print(f"Unzipping: {zip_path.name}")
    stem = zip_path.stem
    if not stem:
        print(f"Error: no filename before .zip in {zip_path.name}")
        return 0, 0, 1

    try:
        images = extract_images(zip_path, temp_dir / stem)
    except (zipfile.BadZipFile, ValueError, OSError) as error:
        print(f"Error: failed to unpack {zip_path.name}: {error}")
        return 0, 0, 1

    if not images:
        print(f"Error: no HEIC or HEIF files found in {zip_path.name}")
        return 0, 0, 1

    converted = 0
    failures = 0
    for index, source in enumerate(images, start=1):
        destination = VINTED_FOLDER / f"{stem}-{index:02d}.jpg"
        print(f"Converting: {source.name} -> {destination.name}")
        try:
            convert_image(source, destination)
            converted += 1
            print(f"Saved: {destination.name}")
        except Exception as error:
            failures += 1
            print(f"Error: failed to convert {source.name}: {error}")

    if failures:
        print(f"Kept zip file: {zip_path.name}")
        return len(images), converted, failures

    zip_path.unlink()
    print(f"Deleted zip file: {zip_path.name}")
    return len(images), converted, 0


def main() -> None:
    started = time.perf_counter()
    print("Starting HEIC to JPG conversion...")

    VINTED_FOLDER.mkdir(parents=True, exist_ok=True)
    print(f"Found Vinted folder: {VINTED_FOLDER}")

    zips = collect_zips(VINTED_FOLDER)
    if not zips:
        print(f"Error: no zip files found in {VINTED_FOLDER}")
        sys.exit(1)

    extracted = 0
    converted = 0
    failures = 0

    with tempfile.TemporaryDirectory(prefix="heic2jpg_") as temp_dir:
        for zip_path in zips:
            zip_extracted, zip_converted, zip_failures = process_zip(zip_path, Path(temp_dir))
            extracted += zip_extracted
            converted += zip_converted
            failures += zip_failures

    print(f"Extracted {extracted} HEIC file(s) from zip archive(s)")
    print(f"Found {extracted} HEIC file(s)")
    print(f"Finished processing {converted} images")
    if failures:
        print(f"Failed: {failures}")
    elapsed = time.perf_counter() - started
    print(f"Total execution time: {elapsed:.2f} seconds")

    if failures or converted == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
