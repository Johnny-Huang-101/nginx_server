"""

Builds a consolidated OCME Business record.

This will look at a case and verify if there is a _O1 present.

If so, it will then join available records in this order.

O -> T -> B -> D -> X -> A 

If autopsy_type is Administrative Review then it will not pull A

If B, D, X are not available, it will skip.

"""


import os, tempfile
import re
import tempfile
import logging
from datetime import datetime, date
from typing import Dict, Optional, Tuple, List, Union

from flask import current_app
from sqlalchemy import and_, or_, exists, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from pypdf import PdfMerger, PdfReader

import pikepdf

from lims import db
from lims.models import Cases, Records  # Must expose fields noted below

logger = logging.getLogger(__name__)

# Policy cutoff for requiring T* in standard cases
CUTOFF_DATE = date(2025, 1, 25)

# Discipline-status gate applies only to cases with entry date ON/AFTER this date
DISCIPLINE_GATE_START = date(2025, 1, 1)

def _discipline_gate_applicable(case: "Cases") -> bool:
    """
    Apply the discipline-status gate based on fa_case_entry_date only.
    - Apply when fa_case_entry_date >= 2025-01-01
    - Skip when fa_case_entry_date < 2025-01-01 (legacy)
    Assumption: fa_case_entry_date is never NULL (per your DB).
    """
    d = getattr(case, "fa_case_entry_date")
    if isinstance(d, datetime):
        d = d.date()
    apply_gate = isinstance(d, date) and d >= DISCIPLINE_GATE_START
    try:
        current_app.logger.info(

        )
    except Exception:
        pass
    return apply_gate

# Merge orders
_ORDER_STANDARD = ["O", "A", "T", "B", "D", "X"]
_ORDER_ADMIN    = ["O", "T", "B", "D", "X"]  # A excluded

# Matches codes like "_T2", "_A10" etc.
_SUFFIX_RE = re.compile(r"^_([A-Z])(\d+)$")


# ----------------- PATH HELPERS -----------------

def _records_root() -> str:
    root = current_app.config.get("RECORDS_ROOT_FS")
    if root:
        return root
    return os.path.join(current_app.root_path, "static", "filesystem", "records")


def _case_dir(case_number: str) -> str:
    return os.path.join(_records_root(), case_number)


def _pdf_path_by_convention(case_number: str, suffix_code: str) -> Optional[str]:
    """
    Expected file: <case_number><suffix_code>.pdf
    Tolerates case-insensitive .pdf extension by scanning when needed.
    """
    casedir = _case_dir(case_number)
    expected = f"{case_number}{suffix_code}.pdf"
    candidate = os.path.join(casedir, expected)
    if os.path.isfile(candidate):
        return candidate

    if not os.path.isdir(casedir):
        return None

    target_base = f"{case_number}{suffix_code}".lower()
    for fname in os.listdir(casedir):
        base, ext = os.path.splitext(fname)
        if base.lower() == target_base and ext.lower() == ".pdf":
            return os.path.join(casedir, fname)
    return None


# ----------------- RECORD LOOKUPS (record_name-based) -----------------

def _codes_for_letter(case_id: int, letter: str) -> List[Tuple[str, int]]:
    """
    Return list of (code, version) for this letter, derived from Records.record_name.
    record_name looks like: "<case_number>_<SUFFIX>" where SUFFIX ~ r"[A-Z]\d+".
    We return code like "_T2".
    """
    recs = Records.query.filter(Records.case_id == case_id).all()
    out: List[Tuple[str, int]] = []
    for r in recs:
        rn = getattr(r, "record_name", "") or ""
        if "_" not in rn:
            continue
        tail = rn.rsplit("_", 1)[-1]   # e.g. "T2"
        code = f"_{tail}"              # e.g. "_T2"
        m = _SUFFIX_RE.match(code)
        if not m:
            continue
        L, num = m.group(1), int(m.group(2))
        if L == letter:
            out.append((code, num))
    return out

def _norm_text(s):
    return None if s is None else str(s).strip().lower()

def _is_blank(s):
    return s is None or (isinstance(s, str) and s.strip() == "")

_READY = "ready for dissemination"

def _discipline_status_review(case):
    """
    Returns:
      blockers: any non-blank discipline whose value != 'Ready for Dissemination' (case-insensitive)
      all_blank: True iff all four watched fields are blank/None/whitespace
    """
    status_fields = ["toxicology_status", "biochemistry_status", "drug_status", "external_status"]

    blockers = {}
    saw_non_empty = False

    for f in status_fields:
        raw = _get_attr_ci(case, f)
        if _is_blank(raw):
            continue
        saw_non_empty = True
        if _norm_text(raw) != _READY:
            blockers[f] = raw

    all_blank = not saw_non_empty
    return blockers, all_blank

def _get_attr_ci(obj, name: str):
    """Case-insensitive getattr. Tries exact first, then scans attributes case-insensitively."""
    # 1) fast path – exact name
    if hasattr(obj, name):
        return getattr(obj, name)

    # 2) case-insensitive scan
    lname = name.lower()
    for attr in dir(obj):
        if attr.lower() == lname:
            try:
                return getattr(obj, attr)
            except Exception:
                pass
    return None

def _best_code(case_id: int, letter: str) -> Optional[str]:
    """
    Highest numeric version per letter (e.g., _T2 over _T1). Returns full code like "_T2".
    """
    candidates = _codes_for_letter(case_id, letter)
    if not candidates:
        return None
    code, _ = max(candidates, key=lambda it: it[1])
    return code


def _latest_record_by_name(case_id: int, record_name: str) -> Optional["Records"]:
    return (
        Records.query
        .filter(Records.case_id == case_id, Records.record_name == record_name)
        .order_by(Records.create_date.desc())
        .first()
    )


def _has_r1(case_id: int, case_number: str) -> bool:
    """
    SQL Server–friendly existence check: attempt to fetch one id.
    """
    return (
        db.session.query(Records.id)
        .filter(Records.case_id == case_id,
                Records.record_name == f"{case_number}_R1")
        .limit(1).first()
        is not None
    )


def _latest_r(case_id: int, case_number: str, which: str) -> Optional["Records"]:
    """
    which in {"R1","R2"}
    """
    return _latest_record_by_name(case_id, f"{case_number}_{which}")


def _is_admin_review(case: "Cases") -> bool:
    at = getattr(case, "autopsy_type", None)
    return isinstance(at, str) and at.strip().lower() == "administrative review"


def _requires_T_standard(case: "Cases") -> bool:
    """
    Standard (non-admin) rule:
      require T when fa_case_entry_date >= CUTOFF_DATE or is NULL.
      T optional only if date < cutoff.
    """
    d = getattr(case, "fa_case_entry_date", None)
    if d is None:
        return True
    if isinstance(d, datetime):
        d = d.date()
    return d >= CUTOFF_DATE


def _eligible_letters_for_case(case: "Cases") -> Tuple[List[str], List[str]]:
    """
    Returns (order, required_letters) for this case.
    """
    if _is_admin_review(case):
        order = _ORDER_ADMIN          # O, T, B, D, X
        required = ["O"]              # A excluded; T/B/D/X optional
    else:
        order = _ORDER_STANDARD       # O, T, B, D, X, A
        required = ["O", "A"]
        if _requires_T_standard(case):
            required.append("T")
    return order, required


# ----------------- MERGE (Preserve signatures) + BOOKMARKS -----------------


def _merge_with_bookmarks(case_number: str,
                          parts: List[Tuple[str, str]],
                          out_path: str) -> None:
    """
    Merge parts into out_path using pikepdf:
      - Do NOT flatten: preserves signature widgets & their appearance streams (images).
      - Add top-level bookmarks: "<case_number>_<SUFFIX>" with explicit GoTo destinations.
      - Try setting /AcroForm/NeedAppearances = true on the OUTPUT doc (guarded).
      - Atomic save (tmp -> replace).
    """
    out = pikepdf.Pdf.new()
    try:
        # Track start page index for each component and create bookmarks after copying pages
        bookmarks: List[Tuple[str, int]] = []
        page_start = 0

        for code, path in parts:
            src_path = path
            try:
                # Try to open with pikepdf; if it fails, treat as unreadable.
                with pikepdf.open(src_path) as src:
                    pass
            except Exception as e:
                # If it's the required 'O' part, abort; otherwise, just skip it.
                if code.upper().startswith("_O"):
                    logger.error("[Build] Required part %s unreadable (%s); aborting.", code, path)
                    raise
                else:
                    logger.warning("[Build] Skipping unreadable optional part %s (%s): %s", code, path, e)
                    continue

            # If we reach here, it's readable—append pages and add a bookmark
            with pikepdf.open(src_path) as src:
                out.pages.extend(src.pages)
                title = f"{case_number}_{code.lstrip('_')}"
                bookmarks.append((title, page_start))
                page_start += len(src.pages)
                # Add bookmarks with explicit destinations (GoTo)
        # Use /Fit (fit whole page) for broad compatibility; switch to /XYZ if you prefer keeping zoom.
        with out.open_outline() as outline:
            for title, start in bookmarks:
                # pikepdf page helper -> underlying indirect object for destination
                page_obj = getattr(out.pages[start], "obj", out.pages[start])

                # --- Option A: Fit whole page ---
                dest = pikepdf.Array([page_obj, pikepdf.Name("/Fit")])

                # If your pikepdf prefers indirects, wrap the array
                try:
                    dest = out.make_indirect(dest)
                except Exception:
                    pass

                item = pikepdf.OutlineItem(title)
                item.destination = dest
                outline.root.append(item)

        # Encourage viewers to render widget appearances
        try:
            root_dict = out.Root  # Catalog
            if "/AcroForm" in root_dict:
                root_dict["/AcroForm"]["/NeedAppearances"] = pikepdf.Boolean(True)
            else:
                root_dict["/AcroForm"] = out.make_indirect(
                    pikepdf.Dictionary({"/NeedAppearances": pikepdf.Boolean(True)})
                )
        except Exception:
            pass

        # Atomic save
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=os.path.dirname(out_path))
        tmp_path = tmp.name
        tmp.close()
        try:
            out.save(
                tmp_path,
                linearize=False,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        except Exception:
            # Fallback for older pikepdf versions
            out.save(tmp_path, linearize=False, compress_streams=True)

        os.replace(tmp_path, out_path)

    finally:
        out.close()



# ----------------- SOURCE RESOLUTION -----------------

def _resolve_sources(case: "Cases") -> Optional[List[Tuple[str, str]]]:
    """
    Choose highest version per eligible letter for this case, enforce required letters,
    and return list of (code, absolute_path) in merge order.
    """
    case_id = getattr(case, "id")
    case_number = getattr(case, "case_number", str(case_id))

    order, required = _eligible_letters_for_case(case)

    # Highest version per letter (e.g., '_T2')
    best: Dict[str, Optional[str]] = {L: _best_code(case_id, L) for L in set(order)}

    # Required presence
    for L in required:
        if not best.get(L):
            return None

    # Resolve to filesystem paths in order
    parts: List[Tuple[str, str]] = []
    for L in order:
        code = best.get(L)
        if not code:
            if L not in required:
                continue
            return None
        p = _pdf_path_by_convention(case_number, code)
        if p and os.path.isfile(p):
            parts.append((code, p))
        else:
            if L not in required:
                continue
            return None

    return parts if parts else None


# ----------------- WRITE BUNDLES -----------------

def _write_bundle(case: "Cases", target_code: str, parts: List[Tuple[str, str]]) -> Optional["Records"]:
    case_id = getattr(case, "id")
    case_number = getattr(case, "case_number", str(case_id))

    out_dir = _case_dir(case_number)
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"{case_number}_{target_code}.pdf"
    out_full = os.path.join(out_dir, out_name)
    rname = f"{case_number}_{target_code}"

    rec_num = None
    m = re.match(r"R(\d+)$", target_code)
    if m:
        rec_num = int(m.group(1))

    existing = _latest_record_by_name(case_id, rname)

    if target_code == "R1" and existing is not None:
        return None

    _merge_with_bookmarks(case_number, parts, out_full)

    now_local = datetime.now()

    try:
        if existing is None:
            # double-check no concurrent creator
            existing = (
                Records.query
                .filter(Records.record_name == rname, Records.case_id == case_id)
                .first()
            )

        if existing is None:
            rec = Records(
                case_id=case_id,
                record_name=rname,      # "<case>_R1" / "<case>_R2"
                record_number=rec_num,  # 1 for R1, 2 for R2
                record_type=13,
                created_by="ZZZ",
                create_date=now_local,
                db_status='Active'
            )
            db.session.add(rec)
            db.session.flush()         # get rec.id / surface errors
            db.session.commit()        # <-- EAGER COMMIT

            return rec
        else:
            existing.record_name = rname
            existing.record_number = rec_num
            existing.record_type = 13
            existing.created_by = "ZZZ"
            existing.create_date = now_local
            existing.db_status='Active'
            db.session.flush()
            db.session.commit()        # <-- EAGER COMMIT
            return existing

    except IntegrityError as ie:
        db.session.rollback()
        print(f"[Build][ERROR] IntegrityError writing Records for {rname}: {ie}")
        return None
    except SQLAlchemyError as se:
        db.session.rollback()
        print(f"[Build][ERROR] SQLAlchemyError writing Records for {rname}: {se}")
        return None



# ----------------- PUBLIC API: R1 -----------------

def build_r1_for_case(case: "Cases") -> Optional["Records"]:
    case_id = getattr(case, "id")
    case_number = getattr(case, "case_number", str(case_id))

    if _has_r1(case_id, case_number):
        return None

    parts = _resolve_sources(case)
    if not parts:
        return None

    # Run the discipline-status gate only for new-enough cases
    if _discipline_gate_applicable(case):
        blockers, all_blank = _discipline_status_review(case)

        # Block if any non-blank discipline is not exactly RFD
        if blockers:
            return None

        # If ALL are blank, only allow when case.case_status == "No Testing Requested"
        cs = _norm_text(getattr(case, "case_status", None))
        if all_blank and cs != "no testing requested":
            current_app.logger.info(
                "Skipping _R1 for case %s; all statuses blank and case_status != 'No Testing Requested' (case_status=%r)",
                case_number, getattr(case, "case_status", None),
            )
            return None

    rec = _write_bundle(case, "R1", parts)
    return rec



def build_missing_r1_records(limit: Optional[int] = None) -> int:
    """
    Batch: create _R1 for cases likely to qualify and lacking <case>_R1.
    Prefilter: (has any O for that case) OR (is Admin Review), and NO <case>_R1.
    """
    has_O_any = exists().where(and_(
        Records.case_id == Cases.id,
        Records.record_name.like(Cases.case_number + "_O%")
    ))
    is_admin = func.lower(Cases.autopsy_type) == "administrative review"
    has_R1 = exists().where(and_(
        Records.case_id == Cases.id,
        Records.record_name == (Cases.case_number + "_R1")
    ))

    q = Cases.query.filter(or_(has_O_any, is_admin), ~has_R1).order_by(Cases.id.asc())
    if limit:
        q = q.limit(limit)

    created = 0
    for case in q:
        rec = build_r1_for_case(case)
        if rec:
            created += 1

    db.session.commit()
    return created


def build_r1_for_case_number(case_number: str) -> Dict[str, object]:
    case = Cases.query.filter(Cases.case_number == case_number).first()
    if not case:
        return {"case_number": case_number, "created": False, "reason": "case_not_found"}

    if _has_r1(getattr(case, "id"), case_number):
        return {"case_number": case_number, "created": False, "reason": "already_has_R1"}

    parts = _resolve_sources(case)
    if not parts:
        return {"case_number": case_number, "created": False, "reason": "requirements_not_met"}

    if _discipline_gate_applicable(case):
        blockers, all_blank = _discipline_status_review(case)
        if blockers:
            return {
                "case_number": case_number,
                "created": False,
                "reason": "discipline_status_blockers",
                "details": {k: str(v) for k, v in blockers.items()},
            }

        cs = _norm_text(getattr(case, "case_status", None))
        if all_blank and cs != "no testing requested":
            return {
                "case_number": case_number,
                "created": False,
                "reason": "all_status_blank_and_case_status_not_ntr",
                "case_status": getattr(case, "case_status", None),
            }

    # Always build if we reached here (either gate passed or gate skipped)
    rec = _write_bundle(case, "R1", parts)
    db.session.commit()
    return {"case_number": case_number, "created": True, "record_id": getattr(rec, "id", None)}


# ----------------- PUBLIC API: R2 -----------------

def _any_newer_sources_than_r1(case: "Cases") -> bool:
    case_id = getattr(case, "id")
    case_number = getattr(case, "case_number", str(case_id))
    latest_r1 = _latest_r(case_id, case_number, "R1")
    if not latest_r1:
        return False

    r1_dt = latest_r1.create_date or datetime.min
    order, _required = _eligible_letters_for_case(case)
    letters = set(order)

    # Only consider these letters for this case; case-aware record_name
    ors = [Records.record_name.like(case_number + f"_{L}%") for L in letters]

    return (
        db.session.query(Records.id)
        .filter(
            Records.case_id == case_id,
            or_(*ors),
            Records.create_date > r1_dt
        )
        .limit(1)
        .first()
        is not None
    )


def build_or_update_r2_for_case(case: "Cases") -> Optional["Records"]:
    case_id = getattr(case, "id")
    case_number = getattr(case, "case_number", str(case_id))

    if not _latest_r(case_id, case_number, "R1"):
        return None

    if not _any_newer_sources_than_r1(case):
        return None

    parts = _resolve_sources(case)
    if not parts:
        return None

    rec = _write_bundle(case, "R2", parts)  # will create or update
    return rec


def build_missing_or_outdated_r2_records(limit: Optional[int] = None) -> int:
    """
    Batch: for cases that already have <case>_R1, create or update <case>_R2 when sources are newer than _R1.
    """
    has_R1 = exists().where(and_(
        Records.case_id == Cases.id,
        Records.record_name == (Cases.case_number + "_R1")
    ))

    q = Cases.query.filter(has_R1).order_by(Cases.id.asc())
    if limit:
        q = q.limit(limit)

    changed = 0
    for case in q:
        rec = build_or_update_r2_for_case(case)
        if rec:
            changed += 1

    db.session.commit()
    return changed


def build_r2_for_case_number(case_number: str) -> Dict[str, object]:
    case = Cases.query.filter(Cases.case_number == case_number).first()
    if not case:
        return {"case_number": case_number, "updated": False, "reason": "case_not_found"}

    case_id = getattr(case, "id")
    if not _latest_r(case_id, case_number, "R1"):
        return {"case_number": case_number, "updated": False, "reason": "no_R1_baseline"}

    if not _any_newer_sources_than_r1(case):
        return {"case_number": case_number, "updated": False, "reason": "no_newer_sources"}

    parts = _resolve_sources(case)
    if not parts:
        return {"case_number": case_number, "updated": False, "reason": "requirements_not_met"}

    rec = _write_bundle(case, "R2", parts)
    db.session.commit()
    return {"case_number": case_number, "updated": True, "record_id": getattr(rec, "id", None)}


# ----------------- NIGHTLY MAINTENANCE (R1 then R2) -----------------

def build_reports_maintenance(limit_r1: Optional[int] = None,
                              limit_r2: Optional[int] = None) -> Dict[str, int]:
    """
    Nightly run:
      1) Create missing <case>_R1 bundles
      2) Create or refresh <case>_R2 bundles when newer sources exist
    """
    print(f"-=-=-=-[Starting Decedent Report Generation]-=-=-=-")
    r1 = build_missing_r1_records(limit=limit_r1)
    r2 = build_missing_or_outdated_r2_records(limit=limit_r2)
    print(f"-=-=-=-[Decedent Report Complete] (R1 created={r1}, R2 created/updated={r2})-=-=-=-")
    return {"r1_created": r1, "r2_created_or_updated": r2}
