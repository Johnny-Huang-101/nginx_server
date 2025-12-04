import re
from sqlalchemy import and_, or_
from collections import defaultdict
from datetime import datetime
import pandas as pd
from lims.models import *
import numpy as np
from pandas.api.types import CategoricalDtype

def get_pending_tests(Tests, Assays, discipline):
    all_assays = pd.DataFrame([a.__dict__ for a in Assays.query.all()])
    pending_tests = pd.DataFrame()

    assay_order = ['QTON-BL', 'QTON-UR', 'LCQD-BL', 'LCQD-UR', 'GCET-FL', 'LCFS-BL', 'LCCI-BL']

    if not all_assays.empty:
        assay_dict = dict(zip(all_assays['id'], all_assays['assay_name']))

        # Only build limit dict from assays with num_tests
        assays_with_limits = all_assays[all_assays['num_tests'].notnull()]
        limit_dict = dict(zip(assays_with_limits['id'], assays_with_limits['num_tests']))

        pending_tests_query = Tests.query.filter(
            Tests.test_status == 'Pending',
            Tests.assay.has(Assays.discipline == discipline)
        )
        if pending_tests_query.count():
            pending_tests = pd.DataFrame([item.__dict__ for item in pending_tests_query])
            pending_tests = pending_tests[pending_tests['assay_id'] != 0]

            pending_tests = pending_tests['assay_id'].value_counts().reset_index()
            pending_tests.columns = ['assay_id', 'counts']

            pending_tests['assay_name'] = pending_tests['assay_id'].replace(assay_dict)
            pending_tests['limit'] = pending_tests['assay_id'].replace(limit_dict)
            pending_tests['limit'] = pending_tests['limit'].fillna(0).astype(int)
            pending_tests['ready'] = pending_tests['counts'] >= pending_tests['limit']

            # Reorder: custom order first, then alphabetical
            df = pending_tests.copy()

            # Separate fixed and remaining
            fixed = df[df['assay_name'].isin(assay_order)].copy()
            remaining = df[~df['assay_name'].isin(assay_order)].copy()

            # Apply manual order
            cat_type = CategoricalDtype(categories=assay_order, ordered=True)
            fixed['assay_name'] = fixed['assay_name'].astype(cat_type)
            fixed = fixed.sort_values('assay_name')

            # Alphabetical sort for others
            remaining = remaining.sort_values('assay_name')

            # Combine
            df = pd.concat([fixed, remaining])
            pending_tests = df.to_dict(orient='index')

    return pending_tests


def format_date_by(date_obj, date_by):
    if date_by == 'Year':
        return date_obj.strftime('%Y')
    elif date_by == 'Quarter':
        q = (date_obj.month - 1) // 3 + 1
        return f"Q{q} {date_obj.year}"
    return date_obj.strftime('%b %Y')

from collections import defaultdict

def calculate_tat_percentages(case_type_ids, start_date, end_date, date_by, discipline):
    """
    Chunked version to avoid SQL Server's 2100-parameter limit.
    - Keeps function name/signature and key variable names the same.
    - Batches Records/Cases queries by ID in safe chunks.
    - Uses ESCAPE in LIKE so '_' is literal.
    """
    CHUNK_SIZE = 900  # well under 2100 even with other params
    def _chunks(seq, size=CHUNK_SIZE):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")

    # 1) Get all matching case IDs first (single query; safe)
    case_id_rows = (
        db.session.query(Cases.id)
        .filter(
            Cases.case_type.in_(case_type_ids),
            start_attr.isnot(None),
            start_attr >= start_date,
            start_attr <= end_date,
            Cases.db_status != 'Removed',
            Cases.case_status != 'No Testing Requested'
        )
        .all()
    )
    case_ids = [row[0] for row in case_id_rows]

    if not case_ids:
        return pd.DataFrame(columns=[
            "Month", "15-Day %", "30-Day %", "45-Day %", "60-Day %", "90-Day %", "Still Open %"
        ])

    # 2) Pull T1 records in CHUNKS of case_ids
    t1_lookup = {}
    for id_chunk in _chunks(case_ids):
        rows = (
            db.session.query(Records.case_id, Records.create_date)
            .filter(
                Records.case_id.in_(id_chunk),
                # LITERAL underscore: compiles to LIKE '%\_T1' ESCAPE '\'
                Records.record_name.like('%\\_T1', escape='\\')
            )
            .all()
        )
        # If multiple _T1 per case exist and you care about earliest/latest,
        # adjust here; by default latest wins due to overwrite.
        for cid, cdate in rows:
            t1_lookup[cid] = cdate

    # 3) Pull the Cases themselves in CHUNKS (avoid giant IN)
    cases = []
    for id_chunk in _chunks(case_ids):
        cases.extend(
            db.session.query(Cases)
            .filter(Cases.id.in_(id_chunk))
            .all()
        )

    # 4) Aggregate to monthly percentages
    tat_data, open_data = [], []
    for case in cases:
        start_date_val = getattr(case, f"{discipline.lower()}_start_date")
        if not start_date_val:
            continue
        group_key = format_date_by(start_date_val, date_by)
        t1_date = t1_lookup.get(case.id)
        if t1_date:
            tat_days = (t1_date.date() - start_date_val.date()).days
            tat_data.append({'month': group_key, 'tat_days': tat_days})
        else:
            open_data.append(group_key)

    closed_grouped, open_grouped = defaultdict(list), defaultdict(int)
    for e in tat_data:
        closed_grouped[e['month']].append(e['tat_days'])
    for m in open_data:
        open_grouped[m] += 1

    all_months = sorted(set(closed_grouped) | set(open_grouped))

    rows_out = []
    for month in all_months:
        closed = closed_grouped.get(month, [])
        open_count = open_grouped.get(month, 0)
        total = len(closed)

        if total == 0 and open_count == 0:
            continue

        if total == 0:
            pct_15 = pct_30 = pct_45 = pct_60 = pct_90 = 0.0
        else:
            pct_15 = round(100 * sum(d <= 15 for d in closed) / total, 1)
            pct_30 = round(100 * sum(d <= 30 for d in closed) / total, 1)
            pct_45 = round(100 * sum(d <= 45 for d in closed) / total, 1)
            pct_60 = round(100 * sum(d <= 60 for d in closed) / total, 1)
            pct_90 = round(100 * sum(d <= 90 for d in closed) / total, 1)

        denom = total + open_count
        pct_open = round(100 * open_count / denom, 1) if denom else 0.0

        rows_out.append({
            "Month": month,
            "15-Day %": pct_15,
            "30-Day %": pct_30,
            "45-Day %": pct_45,
            "60-Day %": pct_60,
            "90-Day %": pct_90,
            "Still Open %": pct_open
        })

    return pd.DataFrame(rows_out)


def calculate_median_tat_by_month(case_type_ids, start_date, end_date, date_by, discipline):
    # 1) Build the date attribute we group by (Toxicology/Biochemistry/etc.)
    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")

    # 2) Subquery for case IDs that meet the filters (no giant Python list of IDs)
    selected_case_ids = db.session.query(Cases.id).filter(
        Cases.case_type.in_(case_type_ids),
        start_attr.isnot(None),
        start_attr >= start_date,
        start_attr <= end_date,
        Cases.db_status != 'Removed'
    )

    # 3) Fetch cases using IN (SELECT ...), safe for SQL Server param limits
    cases = db.session.query(Cases).filter(Cases.id.in_(selected_case_ids)).all()

    # 4) Pull all matching _T1 Records for those cases (escape '_' as literal)
    t1_records = (
        db.session.query(Records.case_id, Records.create_date)
        .filter(
            Records.case_id.in_(selected_case_ids),
            Records.record_name.like('%\\_T1', escape='\\'),
            Records.create_date >= start_date,
            Records.create_date <= end_date
        )
        .all()
    )

    # 5) Fast lookup: case_id -> T1 record create_date
    t1_lookup = {cid: cdate for (cid, cdate) in t1_records}

    # 6) Compute TATs per month (based on the case's start_attr)
    tat_by_month = defaultdict(list)
    for case in cases:
        t1_date = t1_lookup.get(case.id)
        if not t1_date:
            continue
        start_date_val = getattr(case, f"{discipline.lower()}_start_date")
        tat_days = (t1_date.date() - start_date_val.date()).days
        group_key = format_date_by(start_date_val, date_by)
        tat_by_month[group_key].append(tat_days)

    # 7) Median per bucket → DataFrame
    result = []
    for month in sorted(tat_by_month.keys()):
        days_list = tat_by_month[month]
        median_tat = int(np.median(days_list))
        result.append({"Month": month, "Median TAT": median_tat})

    return pd.DataFrame(result)


def calculate_case_volume_by_month(case_type_ids, start_date, end_date, date_by, discipline):
    # Filter cases
    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")
    cases = Cases.query.filter(
        Cases.case_type.in_(case_type_ids),
        start_attr.isnot(None),
        start_attr >= start_date,
        start_attr <= end_date,
        Cases.db_status != 'Removed'
    ).all()

    # Organize counts by month and case type
    data = defaultdict(lambda: defaultdict(int))  # {month: {case_type_code: count}}

    for case in cases:
        start_date_val = getattr(case, f"{discipline.lower()}_start_date")
        group_key = format_date_by(start_date_val, date_by)
        case_code = case.type.code if case.type and case.type.code else "Unknown"
        data[group_key][case_code] += 1

        # Normalize data into DataFrame
    if date_by == 'Year':
        all_months = sorted(data.keys(), key=lambda x: datetime.strptime(x, '%Y'))
    elif date_by == 'Quarter':
        def parse_quarter(qstr):
            q, y = qstr.replace('Q', '').split()
            return datetime(int(y), (int(q) - 1) * 3 + 1, 1)
        all_months = sorted(data.keys(), key=parse_quarter)
    else:
        all_months = sorted(data.keys(), key=lambda x: datetime.strptime(x, '%b %Y'))

    all_case_types = sorted({ct for month_data in data.values() for ct in month_data.keys()})

    rows = []
    for month in all_months:
        row = {'Month': month}
        for ct in all_case_types:
            row[ct] = data[month].get(ct, 0)
        rows.append(row)

    return pd.DataFrame(rows)

def get_open_closed_case_data(case_type_ids, start_date, end_date, date_by, discipline):
    from collections import defaultdict
    from datetime import datetime

    CHUNK_SIZE = 900  # well below SQL Server's 2100 parameter cap
    def _chunks(seq, size=CHUNK_SIZE):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    # Cutoff for B cases
    b_case_cutoff = datetime(2025, 3, 1)

    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")

    # 1) Filter cases (single parameterized query on scalar filters)
    filtered_cases = Cases.query.filter(
        Cases.case_type.in_(case_type_ids),
        start_attr.isnot(None),
        start_attr >= start_date,
        start_attr <= end_date,
        Cases.case_status != 'No Testing Requested',
        Cases.db_status != 'Removed'
    ).all()

    # 2) Exclude 'B' cases before cutoff (done in Python to keep SQL simple)
    filtered_cases = [
        case for case in filtered_cases
        if not (case.type and case.type.code == 'B' and getattr(case, f"{discipline.lower()}_start_date") < b_case_cutoff)
    ]

    case_ids = [c.id for c in filtered_cases]
    if not case_ids:
        return None, None, None

    # 3) Fetch all _T1 case_ids in CHUNKS (avoids 2100-param error)
    t1_case_ids = set()
    for id_chunk in _chunks(case_ids):
        rows = (
            Records.query
            .filter(
                Records.case_id.in_(id_chunk),
                # IMPORTANT: make '_' literal (LIKE '%\_T1' ESCAPE '\')
                Records.record_name.like('%\\_T1', escape='\\')
            )
            .with_entities(Records.case_id)
            .distinct()
            .all()
        )
        # rows are Row objects or tuples -> normalize to ints
        t1_case_ids.update([r[0] if not hasattr(r, "case_id") else r.case_id for r in rows])

    # 4) Count Open/Closed by month
    grouped = defaultdict(lambda: {"Open": 0, "Closed": 0})
    for case in filtered_cases:
        start_date_val = getattr(case, f"{discipline.lower()}_start_date")
        group_key = format_date_by(start_date_val, date_by)
        if case.id in t1_case_ids:
            grouped[group_key]["Closed"] += 1
        else:
            grouped[group_key]["Open"] += 1

    # 5) Order the buckets based on date_by
    if date_by == 'Year':
        months = sorted(grouped.keys(), key=lambda x: datetime.strptime(x, "%Y"))
    elif date_by == 'Quarter':
        def parse_quarter(qstr):
            q, y = qstr.replace('Q', '').split()
            return datetime(int(y), (int(q) - 1) * 3 + 1, 1)
        months = sorted(grouped.keys(), key=parse_quarter)
    else:
        months = sorted(grouped.keys(), key=lambda x: datetime.strptime(x, "%b %Y"))

    open_counts = [grouped[m]["Open"] for m in months]
    closed_counts = [grouped[m]["Closed"] for m in months]

    return months, open_counts, closed_counts



def get_raw_tat_data(case_type_ids, start_date, end_date, date_by, discipline):
    # --- config ---
    CHUNK_SIZE = 900  # << safe headroom vs 2100 cap
    def _chunks(seq, size=CHUNK_SIZE):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    # Step 1: Pull cases in range (single query on scalar filters)
    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")
    cases = Cases.query.filter(
        Cases.case_type.in_(case_type_ids),
        start_attr.isnot(None),
        start_attr >= start_date,
        start_attr <= end_date,
        Cases.db_status != 'Removed',
        Cases.case_status != "No Testing Requested",
        ~and_(
            Cases.type.has(CaseTypes.code == "B"),
            getattr(Cases, f"{discipline.lower()}_start_date") < datetime(2025, 3, 1)
        )
    ).all()

    case_ids = [c.id for c in cases]
    if not case_ids:
        return pd.DataFrame(columns=["Month", "tat_days", "case_id", "is_closed"])

    # Step 2: Fetch _T1 records in CHUNKS (avoid huge IN param list)
    t1_lookup = {}
    for id_chunk in _chunks(case_ids):
        rows = (
            Records.query
            .with_entities(Records.case_id, Records.create_date)
            .filter(
                Records.case_id.in_(id_chunk),
                # literal underscore: LIKE '%\_T1' ESCAPE '\'
                Records.record_name.like('%\\_T1', escape='\\'),
                Records.create_date >= start_date,
                Records.create_date <= end_date
            )
            .all()
        )
        for cid, cdate in rows:
            # if duplicates exist and you care about earliest/ latest, adjust here
            t1_lookup[cid] = cdate

    # Step 3: Assemble TAT data
    data = []
    for case in cases:
        start_date_val = getattr(case, f"{discipline.lower()}_start_date")
        group_key = format_date_by(start_date_val, date_by)
        t1_date = t1_lookup.get(case.id)

        if t1_date:
            tat_days = (t1_date.date() - start_date_val.date()).days
            data.append({
                "Month": group_key,
                "tat_days": tat_days,
                "case_id": case.id,
                "is_closed": True
            })
        else:
            data.append({
                "Month": group_key,
                "tat_days": None,
                "case_id": case.id,
                "is_closed": False
            })

    return pd.DataFrame(data)



def calculate_avg_days_open_per_month(case_type_ids, start_date, end_date, db_session, date_by, discipline):
    CHUNK_SIZE = 900
    def _chunks(seq, size=CHUNK_SIZE):
        for i in range(0, len(seq), size):
            yield seq[i:i+size]

    # Step 1: Get all valid cases in range
    start_attr = getattr(Cases, f"{discipline.lower()}_start_date")
    cases = db_session.query(Cases).filter(
        Cases.create_date >= start_date,
        Cases.create_date <= end_date,
        Cases.case_type.in_(case_type_ids),
        start_attr.isnot(None),
        Cases.db_status == 'Active'
    ).all()

    # Step 2: Exclude 'B' and 'No Testing Requested'
    cases = [c for c in cases if c.type.code != 'B' and c.case_status != 'No Testing Requested']

    # Step 3: Find closed case IDs (with _T1) in CHUNKS
    case_ids = [c.id for c in cases]
    closed_case_ids = set()
    for chunk in _chunks(case_ids):
        closed_chunk = db_session.query(Records.case_id).filter(
            Records.case_id.in_(chunk),
            Records.record_name.like('%\\_T1', escape='\\'),
            Records.db_status == 'Active'
        ).all()
        closed_case_ids.update([c[0] for c in closed_chunk])

    # Step 4: Gather open cases with avg days
    today = datetime.now().date()
    monthly_data = defaultdict(list)

    for c in cases:
        start_date_val = getattr(c, f"{discipline.lower()}_start_date")
        if c.id not in closed_case_ids:
            days_open = (today - start_date_val.date()).days
            group_key = format_date_by(start_date_val, date_by)
            monthly_data[group_key].append(days_open)

    # Step 5: Build DataFrame
    all_months = pd.date_range(start=start_date, end=end_date, freq='MS').strftime('%b %Y')
    result = []
    for m in all_months:
        days = monthly_data.get(m, [])
        avg = round(sum(days)/len(days), 1) if days else 0
        result.append({'Month': m, 'Avg Open Days': avg})

    return pd.DataFrame(result)


