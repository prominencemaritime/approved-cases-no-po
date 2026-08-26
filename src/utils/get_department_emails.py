# src/utils/get_department_emails.py

from typing import List, Optional, Iterable
from functools import lru_cache
from pathlib import Path
import pandas as pd
from dataclasses import dataclass
import logging

from src.db_utils import validate_query_file, query_to_df


logger = logging.getLogger(__name__)


_QUERIES_DIR = Path(__file__).resolve().parents[2] / 'queries'
_QUERY = validate_query_file(_QUERIES_DIR / 'DepartmentEmails.sql')


_DEPARTMENT_BY_CODE = {
            "BRE": "Repairs",
            "CHP": "Charts",
            "CLS": "Technical",
            "CRW": "Crew",
            "CSE": "Technical",
            "FWD": "Forwarding",
            "HRM": "HR",
            "HSQ": "HSSQE",
            "ICT": "ICT",
            "INS": "Claims-Insurance",
            "LUB": "Paint Lubs",
            "MAR": "Marine",
            "PNT": "Paint Lubs",
            "RMW": "Technical",
            "SPC": "Spares",
            "SPR": "Spares",
            "SUP": "Supplies"
}


class DepartmentNotFoundError(Exception):
    pass


class DuplicateDepartmentError(Exception):
    pass


@dataclass(frozen=True)
class DepartmentEmails:
    primary: str
    secondary: str | None = None


def get_department(category: str) -> str:
    """Return department_name given a category (pc.name) or a bare category code."""
    if not category or not str(category).strip():
        raise DepartmentNotFoundError("Empty category")

    cat = str(category).strip()
    code = cat.split('-', 1)[0].strip().upper()

    try:
        return _DEPARTMENT_BY_CODE[code]
    except KeyError:
        raise DepartmentNotFoundError(
            f"Department associated to category {category!r} (code {code!r}) not found"
        ) from None


@lru_cache(maxsize=None)
def get_emails(department_name: str) -> DepartmentEmails:
    """
    Extract a list of department emails from department name

    Example:

        >> emails = lambda category: get_emails(get_department(category))

        >> emails('CLS-Cargo Gear & Elevator')
        DepartmentEmails(primary='technical@prominencemaritime.com', secondary=None)

        >> emails(category).primary
        'technical@prominencemaritime.com'

    """
    df = query_to_df(_QUERY, params={'department_name': department_name})

    if df.empty:
        raise DepartmentNotFoundError(f"Department '{department_name}' not found")
    if len(df) > 1:
        raise DuplicateDepartmentError(f"Duplicate department '{department_name}'")

    required_cols = {'primary_email', 'secondary_email'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing columns: {required_cols - set(df.columns)}")

    row = df.iloc[0]

    if pd.isna(row['primary_email']):
        raise ValueError("Primary email is null")

    return DepartmentEmails(
        primary=str(row['primary_email']),
        secondary=str(row['secondary_email']) if pd.notna(row['secondary_email']) else None
    )


def emails_from_category(category: str) -> DepartmentEmails:
    """
    Example:

        >> emails_from_category('CLS-Cargo Gear & Elevator')
        DepartmentEmails(primary='technical@prominencemaritime.com', secondary=None)

        >> emails_from_category(category).primary
        'technical@prominencemaritime.com'
    """
    return get_emails(get_department(category))


def departments_from_category_codes(
    category_codes: Optional[str],
    delimiter: str = '|',
) -> List[str]:
    """
    Map an aggregated category-code string (e.g. 'CHP|SPR') to unique department names.

    Unmappable codes are logged and skipped rather than raising, so one bad
    category cannot suppress an entire alert run.
    """
    if not category_codes or not str(category_codes).strip():
        return []

    departments = []
    for code in str(category_codes).split(delimiter):
        code = code.strip()
        if not code:
            continue
        try:
            dept = get_department(code)
        except DepartmentNotFoundError:
            logger.warning("Unmapped category code %r -- skipping", code)
            continue
        if dept not in departments:
            departments.append(dept)

    return sorted(departments)


def get_email_list(department_name: str) -> List[str]:
    """
    Convert to the list format to override 'to' field in dict _load_email_routing() in src/core/config.py
    """
    result = get_emails(department_name)
    return [x for x in (result.primary, result.secondary) if x is not None]
