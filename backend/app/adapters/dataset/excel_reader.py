"""Read the course workbook into plain rows (header name → cell value)."""

from pathlib import Path

from openpyxl import load_workbook

from app.adapters.dataset.catalog_parser import SheetData, SheetRow


def read_workbook(path: Path) -> dict[str, SheetData]:
    """Return every sheet keyed by name. The first row is the header; empty rows are skipped."""
    # read_only streams rows instead of loading the whole file; data_only reads formula results.
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheets: dict[str, SheetData] = {}
        for worksheet in workbook.worksheets:
            rows = worksheet.iter_rows(values_only=True)
            header = next(rows, ())
            columns = tuple(str(name).strip() if name is not None else "" for name in header)
            data = [
                SheetRow(
                    number=number,
                    values={
                        column: value
                        for column, value in zip(columns, values, strict=False)
                        if column
                    },
                )
                for number, values in enumerate(rows, start=2)
                if any(value is not None for value in values)
            ]
            sheets[worksheet.title] = SheetData(worksheet.title, columns, data)
        return sheets
    finally:
        workbook.close()
