#!/usr/bin/env python3
"""
Goodies Deck Dimensions: leest master-sheet (Deck + pending), vult template-afbeelding
met width/length/wheelbase/tail/nose per SKU en slaat afbeeldingen op op de Desktop.
"""

import logging
import os
import re
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image, ImageDraw, ImageFont

SPREADSHEET_ID = "1G_N9q4reoEU564t191xl2orFZxKcm7x6a64QrCZ0A2U"
SHEET_NAME = "master"
COL_CATEGORY = 3   # D
COL_PT03_STATUS = 24  # Y

KEY_FILENAME = "goodies-product-pipeline-d210b257a429.json"
ENV_KEY_PATH = "GOODIES_KEY_PATH"

# Kolommen in de sheet; moeten exact zo heten (hoofdletters in sheet mogen)
COLUMN_NAMES = ("sku", "model", "width", "length", "wheelbase", "tail", "nose")

# Posities op de template (x, y) = middelpunt van de tekst; oorsprong linksboven
LABEL_POSITIONS = {
    "length": (983, 564),
    "width": (88, 990),
    "tail": (390, 1419),
    "wheelbase": (983, 1419),
    "nose": (1583, 1419),
}

OUTPUT_DIR_NAME = "output_pt03"
PT03_URL_PREFIX = "https://goodiesboardshop.com/cdn/shop/files/"
FONT_SIZE = 48  # aanpasbaar indien nodig
TEXT_COLOR = (0, 0, 0)  # zwart


def setup_logging() -> None:
    """Logger naar terminal."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )


def get_project_dir() -> str:
    """Projectmap (automation) voor assets."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def get_template_path() -> str:
    return os.path.join(get_project_dir(), "assets", "background", "dimension-deck-template.jpg")


def get_font_path() -> str:
    return os.path.join(get_project_dir(), "assets", "fonts", "BebasNeue-Regular.ttf")


def get_output_dir() -> str:
    """Outputmap op Desktop; wordt aangemaakt indien nodig."""
    desktop = os.path.expanduser("~/Desktop")
    path = os.path.join(desktop, OUTPUT_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def find_key_path() -> Tuple[str, List[str]]:
    """Zoekt het key-bestand. Werkt op MacBook (Gebruikers) en iMac (Users)."""
    tried: List[str] = []

    env_path = os.environ.get(ENV_KEY_PATH)
    if env_path:
        p = os.path.expanduser(env_path)
        tried.append(p)
        if os.path.isfile(p):
            return p, tried

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    for base in (project_dir, os.path.dirname(project_dir)):
        path = os.path.join(base, "keys", KEY_FILENAME)
        tried.append(path)
        if os.path.isfile(path):
            return path, tried

    home = os.path.expanduser("~")
    for rel in ("automation/dev/keys", "dev/keys"):
        path = os.path.join(home, rel, KEY_FILENAME)
        tried.append(path)
        if os.path.isfile(path):
            return path, tried

    for prefix in ("/Users/kristiaankremer", "/Gebruikers/kristiaankremer"):
        for rel in ("automation/dev/keys", "dev/keys"):
            path = os.path.join(prefix, rel, KEY_FILENAME)
            tried.append(path)
            if os.path.isfile(path):
                return path, tried

    return "", tried


def col_index_to_letter(col: int) -> str:
    """0-based kolomindex naar A1-kolomletter(s), bijv. 0 -> A, 25 -> Z, 26 -> AA."""
    result = ""
    while col >= 0:
        result = chr(col % 26 + ord("A")) + result
        col = col // 26 - 1
    return result


def get_sheet_data(service: Any) -> List[List[Any]]:
    """Haalt alle rijen op van tabblad master."""
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:Z")
        .execute()
    )
    return result.get("values", [])


def find_column_indices(headers: List[Any]) -> Optional[Dict[str, int]]:
    """Vindt kolomindices; kolomnamen moeten exact overeenkomen (case-insensitive)."""
    indices: Dict[str, int] = {}
    header_lower = [str(h).strip().lower() if h else "" for h in headers]
    for name in COLUMN_NAMES:
        try:
            indices[name] = header_lower.index(name.lower())
        except ValueError:
            return None
    return indices


def is_deck_pending(row: List[Any]) -> bool:
    """True als category == 'Deck' en pt03_status == 'pending'."""
    if len(row) <= max(COL_CATEGORY, COL_PT03_STATUS):
        return False
    category = (row[COL_CATEGORY] or "").strip()
    status = (row[COL_PT03_STATUS] or "").strip().lower()
    return category == "Deck" and status == "pending"


def cell(row: List[Any], col: int) -> str:
    """Waarde van cel of lege string als buiten bereik."""
    return (row[col] if col < len(row) else "").strip()


def sanitize_description(description: str) -> str:
    """Lowercase, spaties → underscore, leestekens en vreemde tekens (o.a. haakjes) verwijderd."""
    s = description.strip().lower().replace(" ", "_")
    s = re.sub(r"[^\w\-]", "", s)  # alleen letters, cijfers, underscore, hyphen
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "image"


def make_filename(model: str, sku: str) -> str:
    """Bestandsnaam: model-sku-pt03.jpg (model gesanitized); zonder model: sku-pt03.jpg."""
    sku_clean = re.sub(r"[^\w\-]", "", sku.strip().lower()) or "sku"
    if not (model or "").strip():
        return f"{sku_clean}-pt03.jpg"
    desc = sanitize_description(model)
    return f"{desc}-{sku_clean}-pt03.jpg"


def draw_dimension_image(
    template_path: str,
    font_path: str,
    values: Dict[str, str],
    output_path: str,
    log: logging.Logger,
) -> None:
    """Template openen, waarden op posities tekenen, opslaan."""
    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except OSError:
        log.warning("Font niet geladen, gebruik default.")
        font = ImageFont.load_default()

    for label, (x, y) in LABEL_POSITIONS.items():
        text = values.get(label, "").strip() or "—"
        if label == "width":
            # Width: tekst 90° rechtsom (clockwise), gecentreerd op (x, y)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = max(tw, th) // 2
            size = tw + 2 * pad, th + 2 * pad
            layer = Image.new("RGBA", size, (255, 255, 255, 0))
            layer_draw = ImageDraw.Draw(layer)
            cx, cy = size[0] // 2, size[1] // 2
            layer_draw.text((cx, cy), text, font=font, fill=(*TEXT_COLOR, 255), anchor="mm")
            rotated = layer.rotate(-90, expand=True)
            px = x - rotated.width // 2
            py = y - rotated.height // 2
            img.paste(rotated, (px, py), rotated)
        else:
            draw.text((x, y), text, font=font, fill=TEXT_COLOR, anchor="mm")

    img.save(output_path, "JPEG", quality=95)
    log.info("  Opgeslagen: %s", os.path.basename(output_path))


def update_sheet_row(
    service: Any,
    sheet_row: int,
    col_pt03_path: int,
    col_pt03_status: int,
    filename: str,
) -> None:
    """Werkt één rij in de sheet bij: pt03_path en pt03_status."""
    path_value = PT03_URL_PREFIX + filename
    range_path = f"{SHEET_NAME}!{col_index_to_letter(col_pt03_path)}{sheet_row}"
    range_status = f"{SHEET_NAME}!{col_index_to_letter(col_pt03_status)}{sheet_row}"
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "valueInputOption": "RAW",
            "data": [
                {"range": range_path, "values": [[path_value]]},
                {"range": range_status, "values": [["processed"]]},
            ],
        },
    ).execute()


def write_error_txt(output_dir: str, message: str) -> None:
    """Schrijft error.txt in de outputmap met foutbeschrijving."""
    path = os.path.join(output_dir, "error.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(message)


def update_sheet_row_status_error(
    service: Any,
    sheet_row: int,
    col_pt03_status: int,
) -> None:
    """Zet pt03_status op 'error' voor één rij."""
    range_status = f"{SHEET_NAME}!{col_index_to_letter(col_pt03_status)}{sheet_row}"
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_status,
        valueInputOption="RAW",
        body={"values": [["error"]]},
    ).execute()


def main() -> None:
    log = logging.getLogger(__name__)
    setup_logging()
    t0 = time.perf_counter()

    try:
        _run(log)
    finally:
        elapsed = time.perf_counter() - t0
        log.info("Duur: %.1f s", elapsed)


def _run(log: logging.Logger) -> None:
    log.info("Goodies Deck Dimensions – start")
    key_path, tried_paths = find_key_path()
    if not key_path:
        log.error("Key-bestand niet gevonden. Zet %s of plaats key in een van de zoekpaden.", ENV_KEY_PATH)
        for p in tried_paths:
            log.error("  %s", p)
        sys.exit(1)

    log.info("Sheet ophalen...")
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=credentials)
    data = get_sheet_data(service)

    if len(data) < 2:
        log.error("Geen data in sheet.")
        sys.exit(1)

    indices = find_column_indices(data[0])
    if not indices:
        log.error("Kolommen niet gevonden; verwacht: %s", ", ".join(COLUMN_NAMES))
        sys.exit(1)

    header_lower = [str(h).strip().lower() if h else "" for h in data[0]]
    try:
        col_pt03_path = header_lower.index("pt03_path")
        col_pt03_status = header_lower.index("pt03_status")
    except ValueError:
        log.error("Kolommen pt03_path en/of pt03_status niet gevonden in sheet.")
        sys.exit(1)

    matching = [
        (sheet_row, row)
        for sheet_row, row in enumerate(data[1:], start=2)
        if is_deck_pending(row)
    ]
    if not matching:
        log.warning("Geen rijen met category='Deck' en pt03_status='pending'. Stoppen.")
        sys.exit(0)

    template_path = get_template_path()
    font_path = get_font_path()
    if not os.path.isfile(template_path):
        log.error("Template niet gevonden: %s", template_path)
        sys.exit(1)
    if not os.path.isfile(font_path):
        log.error("Font niet gevonden: %s", font_path)
        sys.exit(1)

    output_dir = get_output_dir()
    log.info("Outputmap: %s", output_dir)
    log.info("Afbeeldingen genereren voor %d record(s)...", len(matching))

    for sheet_row, row in matching:
        sku = cell(row, indices["sku"])
        model = cell(row, indices["model"])
        values = {
            "width": cell(row, indices["width"]),
            "length": cell(row, indices["length"]),
            "wheelbase": cell(row, indices["wheelbase"]),
            "tail": cell(row, indices["tail"]),
            "nose": cell(row, indices["nose"]),
        }
        filename = make_filename(model, sku)
        output_path = os.path.join(output_dir, filename)
        log.info("  SKU: %s -> %s", sku, filename)
        try:
            draw_dimension_image(template_path, font_path, values, output_path, log)
            update_sheet_row(
                service, sheet_row, col_pt03_path, col_pt03_status, filename
            )
        except Exception as e:
            log.exception("  Fout voor SKU %s: %s", sku, e)
            write_error_txt(output_dir, traceback.format_exc())
            update_sheet_row_status_error(service, sheet_row, col_pt03_status)

    log.info("Klaar. %d afbeelding(en) in %s", len(matching), output_dir)


if __name__ == "__main__":
    main()
