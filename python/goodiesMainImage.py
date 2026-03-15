#!/usr/bin/env python3
"""
Goodies Main Image: afbeeldingen met BOTTOM of FRONT in de naam (jpg etc., geen png)
worden vrijstaand gemaakt en op 2000x2000 px PNG gezet in output_main/png/ op de Desktop.

Vrijstaand maken vereist rembg + onnxruntime (pip install "rembg[cpu]").
Op macOS moet je 13.4 of nieuwer draaien; oudere versies kunnen een
libc++-fout geven bij het laden van onnxruntime.
"""

import argparse
import logging
import os
import sys
from typing import List, Tuple

from PIL import Image
from tqdm import tqdm

# rembg vereist onnxruntime; importeer die eerst zodat we een duidelijke foutmelding kunnen geven
def _check_onnxruntime() -> bool:
    """Probeer onnxruntime te laden. Bij falen (bv. macOS 13.2 vs wheel voor 13.4+) duidelijke uitleg."""
    try:
        import onnxruntime as ort  # noqa: F401
        return True
    except (ImportError, OSError) as e:
        err = str(e).lower()
        if "macos" in err or "13.4" in err or "symbol not found" in err or "libc++" in err or "built for" in err:
            print("Fout: onnxruntime kan niet laden op deze macOS-versie.")
            print("De huidige wheel is gebouwd voor macOS 13.4 of nieuwer; je draait Ventura 13.2.")
            print("")
            print("Oplossing: upgrade macOS naar 13.4 of nieuwer (Systeeminstellingen → Software-update).")
            print("Daarna opnieuw: pip install \"rembg[cpu]\" en dit script draaien.")
        else:
            print("Fout: onnxruntime niet beschikbaar.", e)
            print('Installeer in je venv met: pip install "rembg[cpu]"')
            if ".venv" not in sys.executable:
                print("Tip: draai je wel in de venv? Gebruik: source .venv/bin/activate  en dan  python goodiesMainImage.py")
        sys.exit(1)
    return False

rembg_remove = None
rembg_new_session = None
if _check_onnxruntime():
    try:
        from rembg import remove as rembg_remove
        from rembg import new_session as rembg_new_session
    except Exception:
        pass  # wordt later afgevangen

INPUT_DIR_NAME = "input_main"
OUTPUT_DIR_NAME = "output_main"
OUTPUT_PNG_SUBDIR = "png"
CANVAS_SIZE = (2000, 2000)
MARGIN = 20  # Rand in pixels (boven/onder bij portret, links/rechts bij landschap)


def setup_logging() -> None:
    """Logger naar terminal."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )


def get_input_dir() -> str:
    """Map input_main op de Desktop."""
    desktop = os.path.expanduser("~/Desktop")
    return os.path.join(desktop, INPUT_DIR_NAME)


def get_output_png_dir() -> str:
    """Map output_main/png op de Desktop; wordt aangemaakt indien nodig."""
    desktop = os.path.expanduser("~/Desktop")
    output_main = os.path.join(desktop, OUTPUT_DIR_NAME)
    png_dir = os.path.join(output_main, OUTPUT_PNG_SUBDIR)
    os.makedirs(png_dir, exist_ok=True)
    return png_dir


def is_bottom_or_front(filename: str) -> bool:
    """True als bestandsnaam BOTTOM of FRONT bevat (case-insensitive)."""
    upper = (filename or "").upper()
    return "BOTTOM" in upper or "FRONT" in upper


# Modellen voor achtergrond verwijderen (rembg).
REMBG_MODELS = ("u2net", "u2net_cloth_seg", "u2net_human_seg", "isnet-general-use", "birefnet-general", "birefnet-general-lite", "silueta")
# Bij --compare: deze modellen allemaal proberen, modelnaam in bestandsnaam (bv. bestand_u2net.png).
COMPARE_MODELS = ("u2net", "u2net_cloth_seg", "isnet-general-use", "birefnet-general")


def make_vrijstaand_and_canvas(
    input_path: str,
    output_path: str,
    log: logging.Logger,
    *,
    model: str = "u2net",
    alpha_matting: bool = False,
    post_process_mask: bool = False,
) -> None:
    """Verwijdert achtergrond, plaatst resultaat zo groot mogelijk op 2000x2000 met 20px rand (boven/onder bij portret, links/rechts bij landschap)."""
    if rembg_remove is None or rembg_new_session is None:
        raise RuntimeError("rembg met CPU-backend niet beschikbaar. Installeer met: pip install \"rembg[cpu]\"")
    img = Image.open(input_path).convert("RGB")
    session = rembg_new_session(model)
    no_bg = rembg_remove(
        img,
        session=session,
        alpha_matting=alpha_matting,
        post_process_mask=post_process_mask,
    )
    if no_bg.mode != "RGBA":
        no_bg = no_bg.convert("RGBA")

    w, h = no_bg.size
    cw, ch = CANVAS_SIZE
    # Zo groot mogelijk met 20px rand: portret (h>=w) → rand boven/onder; landschap (w>h) → rand links/rechts
    inner_w = cw - 2 * MARGIN
    inner_h = ch - 2 * MARGIN

    if h >= w:
        # Portret: vul hoogte (boven en onder 20px), breedte volgt uit verhouding
        new_h = inner_h
        new_w = int(round(w * inner_h / h))
    else:
        # Landschap: vul breedte (links en rechts 20px), hoogte volgt uit verhouding
        new_w = inner_w
        new_h = int(round(h * inner_w / w))

    no_bg = no_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
    # Plaatsing: portret gecentreerd horizontaal op y=MARGIN; landschap gecentreerd verticaal op x=MARGIN
    if h >= w:
        x = (cw - new_w) // 2
        y = MARGIN
    else:
        x = MARGIN
        y = (ch - new_h) // 2

    canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    canvas.paste(no_bg, (x, y), no_bg)

    canvas.save(output_path, "PNG")
    log.info("  Opgeslagen: %s", os.path.basename(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Goodies Main Image: maak BOTTOM/FRONT-afbeeldingen (jpg etc.) uit input_main vrijstaand naar output_main/png/.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--model",
        choices=REMBG_MODELS,
        default="u2net",
        help="Model voor achtergrond verwijderen: u2net (standaard), u2net_cloth_seg (kleding), isnet-general-use, etc.",
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="Alpha matting voor zachtere randen (langzamer, vaak betere kwaliteit).",
    )
    parser.add_argument(
        "--post-process-mask",
        action="store_true",
        help="Masker na bewerking gladder maken (minder ruwe randen).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Alle vergelijkingsmodellen proberen per bestand; bestandsnaam wordt bv. bestand_u2net.png, bestand_u2net_cloth_seg.png, etc.",
    )
    args = parser.parse_args()

    log = logging.getLogger(__name__)
    setup_logging()

    log.info("Goodies Main Image – start")

    input_dir = get_input_dir()
    if not os.path.isdir(input_dir):
        log.warning("Inputmap bestaat niet: %s", input_dir)
        input_files = []
    else:
        input_files = [
            f
            for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f)) and f != ".DS_Store"
        ]

    log.info("Inputmap %s: %d bestand(en).", input_dir, len(input_files))
    log.info("")

    # BOTTOM/FRONT: vrijstaand maken en in 2000x2000 PNG zetten in output_main/png/
    # Alleen niet-PNG (bijv. jpg) verwerken; PNG-bestanden overslaan
    bottom_front_all = [f for f in input_files if is_bottom_or_front(f)]
    bottom_front = [f for f in bottom_front_all if os.path.splitext(f)[1].lower() != ".png"]
    skipped_png = len(bottom_front_all) - len(bottom_front)
    if skipped_png:
        log.info("%d BOTTOM/FRONT PNG-bestand(en) overgeslagen (alleen jpg etc. worden vrijstaand gemaakt).", skipped_png)
    if bottom_front:
        log.info("")
        if rembg_remove is None:
            log.error("Vrijstaand maken vereist rembg met CPU-backend, maar die is niet beschikbaar.")
            log.error("Installeer met: pip install \"rembg[cpu]\"")
            log.error("Daarna opnieuw dit script draaien.")
            sys.exit(1)
        else:
            png_dir = get_output_png_dir()
            jobs: List[Tuple[str, str, str, bool, bool]] = []
            for filename in sorted(bottom_front):
                base, _ = os.path.splitext(filename)
                input_path = os.path.join(input_dir, filename)
                if args.compare:
                    for model in COMPARE_MODELS:
                        output_path = os.path.join(png_dir, f"{base}_{model}.png")
                        jobs.append((input_path, output_path, model, args.alpha_matting, args.post_process_mask))
                else:
                    output_path = os.path.join(png_dir, base + ".png")
                    jobs.append((input_path, output_path, args.model, args.alpha_matting, args.post_process_mask))

            log.info("Vrijstaand maken: %d bestand(en) -> %d taak/taken -> %s", len(bottom_front), len(jobs), png_dir)
            if args.compare:
                log.info("Vergelijkingsmodus: per bestand %d varianten (modelnaam in bestandsnaam).", len(COMPARE_MODELS))
            log.info("")

            for input_path, output_path, model, alpha_matting, post_process_mask in tqdm(jobs, desc="Vrijstaand", unit="img"):
                try:
                    make_vrijstaand_and_canvas(
                        input_path,
                        output_path,
                        log,
                        model=model,
                        alpha_matting=alpha_matting,
                        post_process_mask=post_process_mask,
                    )
                except Exception as e:
                    err_msg = str(e).lower()
                    if "onnxruntime" in err_msg or "backend" in err_msg:
                        log.error("rembg kan geen CPU-backend gebruiken (onnxruntime ontbreekt of werkt niet).")
                        log.error("Installeer opnieuw met: pip install \"rembg[cpu]\"")
                        log.error("Draai daarna dit script opnieuw.")
                        sys.exit(1)
                    tqdm.write(f"  Fout bij {os.path.basename(input_path)}: {e}")

    log.info("")
    log.info("Klaar.")


if __name__ == "__main__":
    main()
