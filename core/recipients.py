"""Recipient loading for TXT, CSV and XLSX sources."""

import csv
from pathlib import Path


EMAIL_COLUMN_NAMES = {"email", "e-mail", "mail", "email_address", "recipient"}


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        email = row.get("email", "").lower()
        if email and email not in seen:
            seen.add(email)
            result.append(row)
    return result


def load(path: str, deduplicate: bool = True) -> tuple[list[dict[str, str]], list[str]]:
    """Load rows and return (rows, columns). TXT produces only an email column."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        emails = [line.strip() for line in file_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        rows = [{"email": email} for email in emails]
        return (_dedupe(rows) if deduplicate else rows), ["email"]

    if suffix == ".csv":
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("CSV file has no header row")
            columns = [c.strip() for c in reader.fieldnames]
            rows = [{k.strip(): _clean(v) for k, v in row.items() if k is not None} for row in reader]
    elif suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return [], []
        columns = [_clean(v) for v in values[0]]
        rows = []
        for values_row in values[1:]:
            rows.append({columns[i]: _clean(values_row[i]) for i in range(len(columns)) if columns[i]})
        workbook.close()
    else:
        raise ValueError("Supported recipient files: .txt, .csv, .xlsx")

    email_column = next((c for c in columns if c.lower() in EMAIL_COLUMN_NAMES), None)
    if not email_column:
        raise ValueError("Recipient file must contain an email column (e.g. email)")
    for row in rows:
        row["email"] = row.get(email_column, "").strip()
    return (_dedupe(rows) if deduplicate else rows), columns + ([] if "email" in columns else ["email"])


def count_duplicates(rows: list[dict[str, str]]) -> int:
    """Return the number of rows removed by email-based de-duplication."""
    seen: set[str] = set()
    duplicates = 0
    for row in rows:
        email = row.get("email", "").strip().lower()
        if not email:
            continue
        if email in seen:
            duplicates += 1
        else:
            seen.add(email)
    return duplicates


def validate(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return valid and invalid rows using a practical email sanity check."""
    valid, invalid = [], []
    for row in rows:
        email = row.get("email", "")
        if email and "@" in email and "." in email.rsplit("@", 1)[-1]:
            valid.append(row)
        else:
            invalid.append(row)
    return valid, invalid
