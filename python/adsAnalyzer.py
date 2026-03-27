import csv
import datetime as dt
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


MONTH_NAME_TO_NUM = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _today_yyyymmdd() -> str:
    return dt.datetime.now().strftime("%Y%m%d")


def _desktop_dir() -> Path:
    return Path.home() / "Desktop"


def _find_input_dir() -> Path:
    desktop = _desktop_dir()
    direct = desktop / "Input"
    if direct.exists() and direct.is_dir():
        return direct
    dated = desktop / f"INPUT-{_today_yyyymmdd()}"
    dated.mkdir(parents=True, exist_ok=True)
    return dated


def _get_output_dir() -> Path:
    out = _desktop_dir() / f"OUTPUT-{_today_yyyymmdd()}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _find_input_csvs(input_dir: Path) -> List[Path]:
    candidates = []
    for p in input_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".csv":
            continue
        name_l = p.name.lower()
        if "advertentierapport" in name_l or "ad report" in name_l:
            candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def _line_is_component_csv_header(line: str) -> bool:
    """Oude UI: Item status/type; nieuwe export: Asset association (Asset status/type)."""
    has_level = "Niveau" in line or re.search(r"(^|,)\s*Level\s*(,|$)", line) is not None
    if not has_level:
        return False
    old = ("Itemstatus" in line or "Item status" in line) and (
        "Itemtype" in line or "Item type" in line
    ) and (re.search(r"(^|,)\s*Item\s*(,|$)", line) is not None)
    new = ("Asset status" in line) and ("Asset type" in line) and (
        re.search(r"(^|,)\s*Asset\s*(,|$)", line) is not None
    )
    return old or new


def _find_component_header(lines: Sequence[str]) -> Tuple[Optional[int], str]:
    for i, line in enumerate(lines):
        if _line_is_component_csv_header(line):
            return i, line
    return None, ""


def _find_component_csvs(input_dir: Path) -> List[Path]:
    candidates = []
    for p in input_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() != ".csv":
            continue
        name_l = p.name.lower()
        lines = _read_first_lines(p, max_lines=30, encoding="utf-8-sig")
        if any(_line_is_component_csv_header(line) for line in lines):
            candidates.append(p)
        elif "asset association" in name_l or "koppelingsrapport" in name_l:
            candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def _read_first_lines(path: Path, max_lines: int = 50, encoding: str = "utf-8-sig") -> List[str]:
    with open(path, "r", encoding=encoding, errors="replace") as f:
        lines = []
        for _ in range(max_lines):
            line = f.readline()
            if not line:
                break
            lines.append(line.rstrip("\n"))
        return lines


def _detect_delimiter(header_line: str) -> str:
    # Most exports are comma-separated; use Sniffer when possible.
    import csv as _csv

    try:
        dialect = _csv.Sniffer().sniff(header_line, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        return ","


def _find_header_and_date_lines(lines: Sequence[str]) -> Tuple[int, Optional[str]]:
    header_idx = None
    date_line = None
    for i, line in enumerate(lines):
        if (
            ("Advertentietype" in line and "Advertentiestatus" in line)
            or ("Ad type" in line and "Ad status" in line)
        ):
            header_idx = i
        if date_line is None:
            if "-" in line:
                # e.g. "15 december 2025 - 15 maart 2026"
                m = re.search(
                    r"(\d{1,2})\s+([A-Za-zçéèêëàâäôöüùûîï]+)\s+(\d{4})\s*-\s*(\d{1,2})\s+([A-Za-zçéèêëàâäôöüùûîï]+)\s+(\d{4})",
                    line,
                )
                if m:
                    date_line = line.strip()
    if header_idx is None:
        raise ValueError("Kon de headerregel niet vinden (kolom 'Advertentietype' ontbreekt).")
    return header_idx, date_line


def _parse_date_range(date_line: str) -> Tuple[dt.date, dt.date]:
    m = re.search(
        r"(\d{1,2})\s+([A-Za-zçéèêëàâäôöüùûîï]+)\s+(\d{4})\s*-\s*(\d{1,2})\s+([A-Za-zçéèêëàâäôöüùûîï]+)\s+(\d{4})",
        date_line,
    )
    if not m:
        raise ValueError(f"Kon datumrange niet parsen: {date_line}")

    d1, mon1, y1, d2, mon2, y2 = m.groups()
    d1_i = int(d1)
    d2_i = int(d2)
    mon1_l = mon1.lower()
    mon2_l = mon2.lower()
    if mon1_l not in MONTH_NAME_TO_NUM:
        raise ValueError(f"Onbekende maand in datumrange: {mon1}")
    if mon2_l not in MONTH_NAME_TO_NUM:
        raise ValueError(f"Onbekende maand in datumrange: {mon2}")

    start = dt.date(int(y1), MONTH_NAME_TO_NUM[mon1_l], d1_i)
    end = dt.date(int(y2), MONTH_NAME_TO_NUM[mon2_l], d2_i)
    return start, end


def _clean_cell(v: Optional[str]) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _is_missing(v: Optional[str]) -> bool:
    s = _clean_cell(v)
    return s == "" or s == "--"


def _is_filled(v: Optional[str]) -> bool:
    return not _is_missing(v)


def _pin_in_allowed(pin_val: Optional[str], allowed: Iterable[int]) -> bool:
    """
    Export kan pinwaarden als '1', '2', '3' bevatten maar soms ook als '1.0'.
    """
    s = _clean_cell(pin_val)
    if not s or s == "--":
        return False
    s = s.replace(",", ".")
    try:
        n = int(float(s))
    except ValueError:
        return False
    return n in set(allowed)


def _bool_to_binary(v: bool) -> int:
    return 1 if v else 0


def _resolve_col(fieldnames: Sequence[str], options: Sequence[str]) -> Optional[str]:
    lookup = {f.strip().lower(): f for f in fieldnames}
    for opt in options:
        k = opt.strip().lower()
        if k in lookup:
            return lookup[k]
    return None


def _component_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    lines = _read_first_lines(path, max_lines=80, encoding="utf-8-sig")
    header_idx, header_line = _find_component_header(lines)
    if header_idx is None:
        raise ValueError(f"Kon component-header niet vinden in bestand: {path.name}")

    delimiter = _detect_delimiter(header_line)
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for _ in range(header_idx):
            f.readline()
        reader = csv.DictReader(f, delimiter=delimiter, quotechar='"')
        for row in reader:
            yield row


def _get_component_fieldnames(path: Path) -> List[str]:
    lines = _read_first_lines(path, max_lines=80, encoding="utf-8-sig")
    header_idx, header_line = _find_component_header(lines)
    if header_idx is None:
        return []
    delimiter = _detect_delimiter(header_line)
    reader = csv.reader([header_line], delimiter=delimiter, quotechar='"')
    for fields in reader:
        return [f.strip() for f in fields]
    return []


def _parse_website_info_item(item: str) -> Tuple[str, List[str]]:
    s = _clean_cell(item)
    if not s:
        return "", []
    if ":" not in s:
        return "", [v.strip() for v in s.split(",") if v.strip()]
    info_type, rest = s.split(":", 1)
    values = [v.strip() for v in rest.split(",") if v.strip()]
    return info_type.strip(), values


def _structured_snippet_values_from_asset_blob(blob: str) -> List[str]:
    """Waarden uit structured_snippet_asset { values: ... } (export gebruikt soms "" of ")."""
    out: List[str] = []
    for pattern in (
        r'values:\s*""((?:[^""\\]|\\.)*)""',  # ruwe export / sommige downloads
        r'values:\s*"((?:[^"\\]|\\.)*)"',  # na csv.DictReader (enkele quotes)
    ):
        for m in re.finditer(pattern, blob):
            val = m.group(1).replace(r"\'", "'").replace(r'\"', '"')
            val = val.strip()
            if val and val not in out:
                out.append(val)
        if out:
            break
    return out


def analyze_components(input_csv_path: Path) -> List[Dict[str, object]]:
    levels: Dict[str, Dict[str, object]] = {}
    fieldnames = _get_component_fieldnames(input_csv_path)
    rows_iter = _component_csv_rows(input_csv_path)

    item_status_col = _resolve_col(fieldnames, ["Itemstatus", "Item status", "Asset status"])
    level_col = _resolve_col(fieldnames, ["Niveau", "Level"])
    itemtype_col = _resolve_col(fieldnames, ["Itemtype", "Item type", "Asset type"])
    item_col = _resolve_col(fieldnames, ["Item", "Asset"])
    if not item_status_col or not level_col or not itemtype_col or not item_col:
        raise ValueError(f"CSV mist componentkolommen in bestand: {input_csv_path.name}")

    def _ensure_level(level: str) -> Dict[str, object]:
        if level not in levels:
            levels[level] = {
                "callouts": [],
                "sitelinks": [],
                "website_values": [],
            }
        return levels[level]

    for row in rows_iter:
        item_status = _clean_cell(row.get(item_status_col))
        if item_status.lower() not in ("aangezet", "enabled"):
            continue

        level_raw = _clean_cell(row.get(level_col))
        level_l = level_raw.lower()
        if level_l in ("campaign", "campagne"):
            level = "Campaign"
        elif level_l in ("ad group", "adgroup", "advertentiegroep"):
            level = "Adgroup"
        elif level_l == "account":
            level = "Account"
        else:
            level = "Onbekend"

        itemtype = _clean_cell(row.get(itemtype_col)).lower()
        item = _clean_cell(row.get(item_col))
        if not item:
            continue

        bucket = _ensure_level(level)

        if itemtype in ("highlight", "callout"):
            callouts = bucket["callouts"]
            if item not in callouts:
                callouts.append(item)
            continue

        if itemtype in ("sitelink", "site link"):
            sitelink = _clean_cell(item)
            sitelinks = bucket["sitelinks"]
            if sitelink not in sitelinks:
                sitelinks.append(sitelink)
            continue

        if itemtype in ("website-informatie", "structured snippet"):
            values = _structured_snippet_values_from_asset_blob(item)
            if not values:
                _, values = _parse_website_info_item(item)
            website_values = bucket["website_values"]
            for value in values:
                if value not in website_values:
                    website_values.append(value)
            continue

    rows: List[Dict[str, object]] = []
    for level in sorted(levels.keys()):
        bucket = levels[level]
        out: Dict[str, object] = {
            "Account": _bool_to_binary(level == "Account"),
            "Campaign": _bool_to_binary(level == "Campaign"),
            "Adgroup": _bool_to_binary(level == "Adgroup"),
        }

        for i in range(1, 21):
            out[f"Sitelinks {i}"] = _bool_to_binary(i <= len(bucket["sitelinks"]))

        for i in range(1, 21):
            out[f"Callouts {i}"] = _bool_to_binary(i <= len(bucket["callouts"]))

        website_values = bucket["website_values"]
        for i in range(1, 11):
            out[f"Structured Snippets {i}"] = _bool_to_binary(
                i <= len(website_values) and _is_filled(website_values[i - 1])
            )

        rows.append(out)
    return rows


def _csv_rows(
    path: Path,
) -> Iterable[Dict[str, str]]:
    # Detect encoding (best-effort) by reading a small sample with utf-8-sig first.
    # If it fails badly, user can adjust by editing script.
    lines = _read_first_lines(path, max_lines=80, encoding="utf-8-sig")
    header_idx, date_line = _find_header_and_date_lines(lines)
    header_line = lines[header_idx]
    delimiter = _detect_delimiter(header_line)

    # Re-open and stream from header line
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for _ in range(header_idx):
            f.readline()
        reader = csv.DictReader(f, delimiter=delimiter, quotechar='"')
        for row in reader:
            yield row


def _get_header_fieldnames(path: Path) -> List[str]:
    lines = _read_first_lines(path, max_lines=80, encoding="utf-8-sig")
    header_idx, _ = _find_header_and_date_lines(lines)
    header_line = lines[header_idx]
    delimiter = _detect_delimiter(header_line)
    # Parse header line into fields using csv reader
    reader = csv.reader([header_line], delimiter=delimiter, quotechar='"')
    for fields in reader:
        return [f.strip() for f in fields]
    return []


def analyze_ads(input_csv_path: Path) -> List[Dict[str, object]]:
    # Parse first lines for date range
    first_lines = _read_first_lines(input_csv_path, max_lines=80, encoding="utf-8-sig")
    _, date_line = _find_header_and_date_lines(first_lines)
    if not date_line:
        raise ValueError(f"Datumrange niet gevonden in bestand: {input_csv_path}")
    _parse_date_range(date_line)

    fieldnames = _get_header_fieldnames(input_csv_path)
    ad_type_col = _resolve_col(fieldnames, ["Advertentietype", "Ad type"])
    ad_status_col = _resolve_col(fieldnames, ["Advertentiestatus", "Ad status"])
    campaign_col = _resolve_col(fieldnames, ["Campagne", "Campaign"])
    adgroup_col = _resolve_col(fieldnames, ["Advertentiegroep", "Ad group"])
    pad1_col = _resolve_col(fieldnames, ["Pad 1", "Path 1"])
    pad2_col = _resolve_col(fieldnames, ["Pad 2", "Path 2"])
    if not all([ad_type_col, ad_status_col, campaign_col, adgroup_col, pad1_col, pad2_col]):
        raise ValueError(f"CSV mist basis advertentiekolommen in bestand: {input_csv_path.name}")

    headline_cols = []
    headline_pin_cols = []
    for i in range(1, 16):
        h = _resolve_col(fieldnames, [f"Kop {i}", f"Headline {i}"])
        hp = _resolve_col(fieldnames, [f"Positie kop {i}", f"Headline {i} position"])
        if not h or not hp:
            raise ValueError(f"CSV mist headlinekolommen in bestand: {input_csv_path.name}")
        headline_cols.append(h)
        headline_pin_cols.append(hp)

    desc_cols = []
    desc_pin_cols = []
    for i in range(1, 5):
        d = _resolve_col(fieldnames, [f"Beschrijving {i}", f"Description {i}"])
        dp = _resolve_col(fieldnames, [f"Positie beschrijving {i}", f"Description {i} position"])
        if not d or not dp:
            raise ValueError(f"CSV mist beschrijvingskolommen in bestand: {input_csv_path.name}")
        desc_cols.append(d)
        desc_pin_cols.append(dp)

    rsa_rows = []

    # Stream rows
    for row in _csv_rows(input_csv_path):
        advertentietype = _clean_cell(row.get(ad_type_col))
        advertentiestatus = _clean_cell(row.get(ad_status_col))
        if advertentietype.lower() not in ("responsieve zoekadvertentie", "responsive search ad"):
            continue
        if advertentiestatus.lower() not in ("aangezet", "enabled"):
            # Keep strict to your definition of "active"
            continue

        campagne = _clean_cell(row.get(campaign_col))
        adgroup = _clean_cell(row.get(adgroup_col))

        row_result: Dict[str, object] = {
            "Campagne": campagne,
            "Advertentiegroep": adgroup,
        }

        for i in range(1, 16):
            row_result[f"K{i}"] = _bool_to_binary(_is_filled(row.get(headline_cols[i - 1])))
            row_result[f"P{i}"] = _bool_to_binary(
                _pin_in_allowed(row.get(headline_pin_cols[i - 1]), allowed=[1, 2, 3])
            )

        for j in range(1, 5):
            row_result[f"B{j}"] = _bool_to_binary(_is_filled(row.get(desc_cols[j - 1])))
            row_result[f"PB{j}"] = _bool_to_binary(
                _pin_in_allowed(row.get(desc_pin_cols[j - 1]), allowed=[1, 2])
            )

        row_result["Pad1"] = _bool_to_binary(_is_filled(row.get(pad1_col)))
        row_result["Pad2"] = _bool_to_binary(_is_filled(row.get(pad2_col)))
        rsa_rows.append(row_result)

    return rsa_rows


def _write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_ads_matrix_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    headers = ["Campagne", "Advertentiegroep"]
    for i in range(1, 16):
        headers.extend([f"K{i}", f"P{i}"])
    for j in range(1, 5):
        headers.extend([f"B{j}", f"P{j}"])
    headers.extend(["Pad1", "Pad2"])

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            values: List[object] = [row.get("Campagne", ""), row.get("Advertentiegroep", "")]
            for i in range(1, 16):
                values.append(row.get(f"K{i}", 0))
                values.append(row.get(f"P{i}", 0))
            for j in range(1, 5):
                values.append(row.get(f"B{j}", 0))
                values.append(row.get(f"PB{j}", 0))
            values.append(row.get("Pad1", 0))
            values.append(row.get("Pad2", 0))
            writer.writerow(values)


def _write_component_sections_csv(path: Path, component_rows: List[Dict[str, object]]) -> None:
    def _zero_row(size: int) -> List[int]:
        return [0] * size

    level_values: Dict[str, Dict[str, List[int]]] = {
        "Account": {
            "Sitelinks": _zero_row(20),
            "Call outs": _zero_row(20),
            "Structured Snippets": _zero_row(10),
        },
        "Campaign": {
            "Sitelinks": _zero_row(20),
            "Call outs": _zero_row(20),
            "Structured Snippets": _zero_row(10),
        },
        "Adgroup": {
            "Sitelinks": _zero_row(20),
            "Call outs": _zero_row(20),
            "Structured Snippets": _zero_row(10),
        },
    }

    for row in component_rows:
        if int(row.get("Account", 0)) == 1:
            level_key = "Account"
        elif int(row.get("Campaign", 0)) == 1:
            level_key = "Campaign"
        elif int(row.get("Adgroup", 0)) == 1:
            level_key = "Adgroup"
        else:
            continue

        for i in range(1, 21):
            if int(row.get(f"Sitelinks {i}", 0)) == 1:
                level_values[level_key]["Sitelinks"][i - 1] = 1
            if int(row.get(f"Callouts {i}", 0)) == 1:
                level_values[level_key]["Call outs"][i - 1] = 1
        for i in range(1, 11):
            if int(row.get(f"Structured Snippets {i}", 0)) == 1:
                level_values[level_key]["Structured Snippets"][i - 1] = 1

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["Sitelinks"] + list(range(1, 21)))
        writer.writerow(["Account"] + level_values["Account"]["Sitelinks"])
        writer.writerow(["Campaign"] + level_values["Campaign"]["Sitelinks"])
        writer.writerow(["Adgroup"] + level_values["Adgroup"]["Sitelinks"])

        writer.writerow(["Call outs"] + list(range(1, 21)))
        writer.writerow(["Account"] + level_values["Account"]["Call outs"])
        writer.writerow(["Campaign"] + level_values["Campaign"]["Call outs"])
        writer.writerow(["Adgroup"] + level_values["Adgroup"]["Call outs"])

        writer.writerow(["Structured Snippets"] + list(range(1, 11)))
        writer.writerow(["Account"] + level_values["Account"]["Structured Snippets"])
        writer.writerow(["Campaign"] + level_values["Campaign"]["Structured Snippets"])
        writer.writerow(["Adgroup"] + level_values["Adgroup"]["Structured Snippets"])


def main() -> None:
    input_dir = _find_input_dir()
    output_dir = _get_output_dir()
    input_csvs = _find_input_csvs(input_dir)
    component_csvs = _find_component_csvs(input_dir)

    all_rows: List[Dict[str, object]] = []
    for input_csv in input_csvs:
        try:
            all_rows.extend(analyze_ads(input_csv))
        except ValueError as e:
            # Inputmap kan meerdere rapporttypes bevatten; sla niet-advertentiebestanden over.
            print(f"Overgeslagen ({input_csv.name}): {e}")

    all_rows.sort(
        key=lambda r: (
            str(r.get("Campagne", "")),
            str(r.get("Advertentiegroep", "")),
        )
    )
    output_path = output_dir / "advertenties_asset_matrix.csv"
    _write_ads_matrix_csv(output_path, all_rows)
    print(f"Analyse klaar. Resultaat geschreven naar: {output_path}")

    component_rows: List[Dict[str, object]] = []
    for component_csv in component_csvs:
        try:
            component_rows.extend(analyze_components(component_csv))
        except ValueError as e:
            print(f"Overgeslagen ({component_csv.name}): {e}")

    component_output_path = output_dir / "componenten_asset_matrix.csv"
    _write_component_sections_csv(component_output_path, component_rows)
    print(f"Analyse klaar. Resultaat geschreven naar: {component_output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fout: {e}", file=sys.stderr)
        sys.exit(1)

