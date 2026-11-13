"""Load the course dataset (Excel) into PostgreSQL.

Usage, inside the backend container::

    python -m app.scripts.seed

Invalid rows are skipped and logged with sheet, row number and reason. Valid rows
are upserted in one transaction: if anything unexpected fails, nothing is loaded.
Running it again with the same file leaves the same data.
"""

import logging
import sys
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.dataset.catalog_parser import DatasetStructureError, ParsedCatalog, parse_catalog
from app.adapters.dataset.excel_reader import read_workbook
from app.adapters.persistence.catalog_loader import load_catalog
from app.adapters.persistence.session import get_session_factory
from app.config import get_settings

logger = logging.getLogger("seed")


def run_seed(dataset_path: Path, session_factory: sessionmaker[Session]) -> ParsedCatalog:
    """Validate the workbook and upsert its valid rows in a single transaction."""
    catalog = parse_catalog(read_workbook(dataset_path))
    for sheet in catalog.sheets():
        for rejected in sheet.rejected:
            logger.warning(
                "Rejected %s row %d: %s", rejected.sheet, rejected.row_number, rejected.reason
            )
    with session_factory() as session, session.begin():
        load_catalog(session, catalog)
    return catalog


def format_summary(catalog: ParsedCatalog) -> str:
    lines = [f"{'Sheet':<16}{'Read':>8}{'Loaded':>8}{'Rejected':>10}"]
    for sheet in catalog.sheets():
        lines.append(
            f"{sheet.sheet:<16}{sheet.read:>8}{len(sheet.records):>8}{len(sheet.rejected):>10}"
        )
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    dataset_path = Path(get_settings().dataset_path)
    if not dataset_path.is_file():
        logger.error(
            "Dataset not found at %s. Copy the course Excel into data/ at the repository root.",
            dataset_path,
        )
        return 1

    logger.info("Loading %s", dataset_path)
    try:
        catalog = run_seed(dataset_path, get_session_factory())
    except DatasetStructureError as error:
        logger.error("The workbook does not have the expected structure: %s", error)
        return 1
    except Exception:
        logger.exception("Load failed; the transaction was rolled back and nothing was loaded")
        return 1

    print(format_summary(catalog))
    return 0


if __name__ == "__main__":
    sys.exit(main())
