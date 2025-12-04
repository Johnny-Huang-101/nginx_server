from flask import request, Blueprint, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import Bar, Figure
from plotly.subplots import make_subplots
from lims.dashboard.forms import *
from lims.models import *
import pandas as pd
from lims import db
import numpy as np
import sqlalchemy as sa
from sqlalchemy import func, distinct
from sqlalchemy.dialects.postgresql import array_agg
from datetime import datetime
import datetime as dt
import json
import os
from sqlalchemy.sql import text
import re
import plotly.io as pio

from lims.dashboard.functions import *

from collections import defaultdict
# Set item variables
dashboard = Blueprint('dashboard', __name__)
conn = db.engine.connect().connection

def parse_group_date(date_str, date_by):
    if date_by == 'Year':
        return datetime.strptime(date_str, '%Y')
    elif date_by == 'Quarter':
        if not date_str.startswith('Q'):
            raise ValueError(f"Expected 'Quarter' format like 'Q1 2025', got: {date_str}")
        q, y = date_str.replace('Q', '').split()
        return datetime(int(y), (int(q) - 1) * 3 + 1, 1)
    else:
        return datetime.strptime(date_str, '%b %Y')


#from flask import url_for
from sqlalchemy import and_

def _label_for(obj):
    """Best-effort display name for any model instance."""
    for attr in ("report_name", "packet_name", "case_number", "name", "title", "accession_number"):
        if hasattr(obj, attr) and getattr(obj, attr):
            return getattr(obj, attr)
    return f"ID {getattr(obj, 'id', '?')}"

def _url_for(obj):
    """Best-effort URL builder per common modules; extend as needed."""
    m = obj.__class__.__name__
    try:
        if m == "Reports":
            return url_for('reports.view', item_id=obj.id, view_only=False)
        if m == "Cases":
            return url_for('cases.view', item_id=obj.id)
        if m == "Records":
            return url_for('records.view', item_id=obj.id)
        if m == "Tests":
            return url_for('tests.view', item_id=obj.id)
        if m == "Batches":
            return url_for('batches.view', item_id=obj.id)
        if m == "LitigationPackets":
            return url_for('litigation_packets.view', item_id=obj.id)
        if m == "Containers":
            return url_for('containers.view', item_id=obj.id)
        if m == "Specimens":
            return url_for('specimens.view', item_id=obj.id)
    except Exception:
        pass
    return None

# NEW: tiny helper to read case id/number if present (does not change existing behavior)
def _case_meta(obj):
    cid = getattr(obj, "case_id", None)
    cnum = None
    try:
        case_rel = getattr(obj, "case", None)
        if case_rel is not None:
            cnum = getattr(case_rel, "case_number", None)
    except Exception:
        pass
    return cid, cnum

def collect_user_locks(initials, limit_per_module=50):
    """
    Query every model that has a 'locked_by' column (and optional db_status)
    and return only modules with at least one row for the current user.

    For Containers/Specimens, we ALSO include a 'by_case' list you can use to
    render grouped accession_numbers by case number—without changing existing output.
    """
    # Register candidate models here (add/remove freely)
    lockables = [Reports, Cases, Records, Tests, Batches, Containers, Specimens]
    try:
        from lims.models import LitigationPackets
        lockables.append(LitigationPackets)
    except Exception:
        pass

    results = []
    for Model in lockables:
        if not hasattr(Model, "locked_by"):
            continue

        q = Model.query.filter(Model.locked_by == initials)
        if hasattr(Model, "db_status"):
            q = q.filter(Model.db_status != 'Removed')

        # Avoid COUNT(*) scans; just try to fetch up to N+1 items.
        items = q.order_by(Model.id.desc()).limit(limit_per_module + 1).all()
        if not items:
            continue

        module_name = Model.__name__

        # Build the SAME flat list you already render
        flat_items = []
        for it in items[:limit_per_module]:
            flat_items.append({
                "id": it.id,
                # For Containers/Specimens this will naturally be accession_number because of _label_for
                "label": _label_for(it),
                "url": _url_for(it)
            })

        bucket = {
            "module": module_name,
            "items": flat_items,
            "has_more": len(items) > limit_per_module
        }

        # NEW: only for Containers/Specimens, also provide a grouped view
        if module_name in ("Containers", "Specimens"):
            groups = {}  # case_label -> list of {"label","url"}
            order_keys = {}  # case_label -> (case_number or "", case_id or 0) for stable sorting

            for it in items[:limit_per_module]:
                cid, cnum = _case_meta(it)
                case_label = cnum if cnum else (f"Case {cid}" if cid is not None else "Case ?")
                label = getattr(it, "accession_number", None) or _label_for(it)
                row = {"label": label, "url": _url_for(it)}

                groups.setdefault(case_label, []).append(row)
                order_keys.setdefault(case_label, (cnum or "", cid or 0))

            # Turn into a sorted list of groups; also sort items by label inside each case
            by_case = []
            for case_label, rows in groups.items():
                rows_sorted = sorted(rows, key=lambda r: (r["label"] or ""))
                by_case.append({
                    "case_label": case_label,
                    "rows": rows_sorted
                })
            by_case.sort(key=lambda g: order_keys.get(g["case_label"], ("", 0)))

            bucket["by_case"] = by_case

        results.append(bucket)

    return results

@dashboard.app_template_filter('attr')
def jinja_attr(obj, name):
    """Safe getattr for Jinja: {{ obj|attr('field_name') }}"""
    try:
        return getattr(obj, name)
    except Exception:
        return None

@dashboard.app_template_filter('has_attr')
def jinja_has_attr(obj, name):
    """Boolean: {{ obj|has_attr('field_name') }}"""
    return getattr(obj, name, None) is not None



@dashboard.route(f'/dashboard', methods=['GET', 'POST'])
@login_required
def get_dashboard():
    discipline = current_user.dashboard_discipline
    pending_dict = get_pending_tests(Tests, Assays, discipline)
    # discipline = 'Toxicology'

    form = CaseFilter()
    form.case_type.choices = [(item.id, item.code) for item in CaseTypes.query.order_by(CaseTypes.accession_level)]
    if not current_user.dashboard_discipline:
        current_user.dashboard_discipline = 'Toxicology'
        db.session.commit()
    
    # --- Handle Form Defaults ---
    if not form.start_date.data:
        form.start_date.data = datetime(2025, 1, 1).date()
    if not form.end_date.data:
        form.end_date.data = datetime.now().date()
    if not form.case_type.data:
        form.case_type.data = [
            ct.id for ct in CaseTypes.query.filter(CaseTypes.code.in_(['PM', 'M', 'D', 'X', 'P', 'C', 'N'])).all()
        ]
    if not form.date_by.data:
        form.date_by.data = 'Month'

    start_date = form.start_date.data
    end_date = form.end_date.data
    selected_case_types = form.case_type.data

    # Dynamic attribute name like "toxicology_status"
    discipline_status_attr = f"{discipline.lower()}_status"


    reports_cases = Cases.query.filter(
        Cases.db_status == 'Active',
        Cases.create_date > datetime(2025, 1, 1)
    ).all()



    # --- Query Reports in Chunks ---
    case_ids = [c.id for c in reports_cases]
    chunk_size = 900
    reports_by_case = defaultdict(list)
    for i in range(0, len(case_ids), chunk_size):
        chunk = case_ids[i:i + chunk_size]
        chunk_reports = Reports.query.filter(
            Reports.case_id.in_(chunk),
            Reports.db_status == 'Active',
            Reports.discipline == discipline
        ).all()
        for r in chunk_reports:
            reports_by_case[r.case_id].append(r)

    # --- BULK-LOAD TESTS FOR THESE CASES (avoids N+1) ---
    tests_by_case = defaultdict(list)
    if case_ids:
        for i in range(0, len(case_ids), 900):  # safe headroom for SQL Server
            chunk = case_ids[i:i+900]
            rows = (db.session.query(Tests)
                    .filter(
                        Tests.case_id.in_(chunk),
                        Tests.db_status == 'Active',
                        ~Tests.test_status.in_(['Withdrawn', 'Cancelled', 'Finalized'])
                    )
                    .all())
            for t in rows:
                tests_by_case[t.case_id].append(t)


    # --- Count Statuses ---
    testing_count = 0
    drafting_count = 0
    cr_count = 0
    dr_count = 0

    testing_cases = []
    drafting_cases = []
    cr_cases = []
    cr_cases_reverted = []
    cr_cases_original = []
    dr_cases = []


    for case in reports_cases:
        case_status = getattr(case, discipline_status_attr, None)
        case_reports = reports_by_case.get(case.id, [])
        active_reports = [r for r in case_reports if r.db_status == 'Active']

        reverted_report = next((r for r in active_reports if r.report_status == 'Ready for CR' and r.reverted_by), None)
        if reverted_report:
            cr_count += 1
            cr_cases_reverted.append({'case': case, 'report': reverted_report})
            continue

        original_report = next((r for r in active_reports if r.report_status == 'Ready for CR' and r.reverted_by is None), None)
        if original_report:
            cr_count += 1
            cr_cases_original.append({'case': case, 'report': original_report})
            continue

        dr_report = next((r for r in active_reports if r.report_status == 'Ready for DR'), None)
        if dr_report:
            dr_count += 1
            dr_cases.append({'case': case, 'report': dr_report})
            continue

        # if any(r.report_status == 'Ready for DR' for r in active_reports):
        #     dr_count += 1
        #     dr_cases.append(case)
        if any(r.report_status == 'Ready for CR' for r in active_reports):
            cr_count += 1
            cr_cases.append(case)
        elif case_status == 'Ready for Drafting':
            if (
                not case_reports or
                all(r.report_status == 'Finalized' for r in case_reports) or
                all(r.db_status != 'Active' for r in case_reports)
            ):
                drafting_count += 1
                drafting_cases.append(case)
        elif case_status == 'Testing':
            # O(1) lookup instead of a per-case query
            relevant_tests = tests_by_case.get(case.id, [])

            assay_names = []
            for t in relevant_tests[:2]:
                if t.assay and t.assay.assay_name:
                    name = t.assay.assay_name
                    if t.test_status == 'Processing':
                        name = f"<span style='color: darkgray;'>{name}</span>"
                    assay_names.append(name)

            if len(relevant_tests) > 2:
                assay_str = ">2"
            elif assay_names:
                assay_str = f"{', '.join(assay_names)}"
            else:
                assay_str = ""

            testing_cases.append({
                'case': case,
                'days': (
                    (datetime.now() - case.toxicology_alternate_start_date).days
                    if case.toxicology_alternate_start_date
                    else (datetime.now() - case.toxicology_start_date).days
                ),
                'assays': assay_str
            })
            testing_count += 1
    # --- Create Independent Bar Chart for Testing ---
    fig_testing = go.Figure(data=[
        go.Bar(
            x=[testing_count],
            y=['Testing'],
            orientation='h',
            marker_color='#a0a0a0',  # muted gray
            text=[testing_count],
            textposition='outside',
            name='Testing'
        )
    ])
    fig_testing.update_layout(
        height=85,
        width=745,
        margin=dict(l=80, r=20, t=20, b=20),
        showlegend=False
    )
    testing_bar_html = pio.to_html(fig_testing, full_html=False)

    # --- Create Separate Bar Chart for CR/DR/Drafting ---
    fig_reports = go.Figure(data=[
        go.Bar(
            x=[dr_count, cr_count, drafting_count],
            y=['DR', 'CR', 'Drafting'],
            orientation='h',
            marker_color=['#6c757d', '#007bff', '#17a2b8'],  # muted gray, blue, teal
            text=[dr_count, cr_count, drafting_count],
            textposition='outside',
            name='Workflow Status'
        )
    ])
    fig_reports.update_layout(
        height=190,
        width=745,
        margin=dict(l=80, r=20, t=20, b=40),
        xaxis_title='Count',
        yaxis_title='Status',
        showlegend=False
    )
    status_bar_html = pio.to_html(fig_reports, full_html=False)

    # Map selected case type IDs to names
    selected_case_type_names = []
    if form.case_type.data:
        selected_case_type_names = [
            ct.code for ct in CaseTypes.query.filter(CaseTypes.id.in_(form.case_type.data)).all()
        ]

    # Example months for x-axis (you’ll later generate this dynamically)
    months = ["Jan 2025", "Feb 2025", "Mar 2025", "Apr 2025", "May 2025", "Jun 2025"]
    # Pull form data
    case_type_ids = form.case_type.data
    start_date = form.start_date.data
    end_date = form.end_date.data

    date_by = form.date_by.data
    tat_df = calculate_tat_percentages(case_type_ids, start_date, end_date, date_by, discipline)

    # Sort months chronologically
    tat_df['Month'] = tat_df['Month'].apply(lambda x: parse_group_date(x, date_by))
    tat_df = tat_df.sort_values('Month')
    if date_by == 'Quarter':
        tat_df['Month'] = tat_df['Month'].dt.to_period('Q').apply(lambda p: f"Q{p.quarter} {p.year}")
    elif date_by == 'Year':
        tat_df['Month'] = tat_df['Month'].dt.strftime('%Y')
    else:
        tat_df['Month'] = tat_df['Month'].dt.strftime('%b %Y')



    months = tat_df['Month'].tolist()
    tat_15 = tat_df['15-Day %'].tolist()
    tat_30 = tat_df['30-Day %'].tolist()
    tat_45 = tat_df['45-Day %'].tolist()
    tat_60 = tat_df['60-Day %'].tolist()
    tat_90 = tat_df['90-Day %'].tolist()
    tat_open = tat_df["Still Open %"].tolist()
        # Create graph
    tat_fig = go.Figure()


    tat_fig.add_trace(go.Scatter(x=months, y=tat_15, mode='lines+markers', name='15 Days', line=dict(color='blue')))
    tat_fig.add_trace(go.Scatter(x=months, y=tat_30, mode='lines+markers', name='30 Days', line=dict(color='red')))
    tat_fig.add_trace(go.Scatter(x=months, y=tat_45, mode='lines+markers', name='45 Days', line=dict(color='green')))
    tat_fig.add_trace(go.Scatter(
        x=months, y=tat_60, mode='lines+markers',
        name='60 Days',
        line=dict(color='purple'),
        visible='legendonly'
    ))
    tat_fig.add_trace(go.Scatter(
        x=months, y=tat_90, mode='lines+markers',
        name='90 Days',
        line=dict(color='gold'),
        visible='legendonly'
    ))
    tat_fig.add_trace(go.Scatter(
    x=months, y=tat_open, mode='lines+markers',
    name='Open',
    line=dict(color='black', dash='dot')
))

        # 90% reference line
    tat_fig.add_shape(
        type="line",
        x0=-0.5,
        y0=90,
        x1=len(months) - 0.5,
        y1=90,
        line=dict(color="black", width=2, dash="dot")
    )

    # Annotation for 90% line
    tat_fig.add_annotation(
        x=len(months) - 1,
        y=90,
        text="90%",
        showarrow=False,
        font=dict(color="black", size=12),
        xanchor="left",
        yanchor="top"
    )
    tat_fig.update_layout(
        xaxis_title=date_by,
        yaxis_title="%",
        yaxis=dict(range=[0, 110]),
        height=500,
        width=1500,
        margin=dict(t=40, b=40, l=40, r=40),
    )

    tat_graph = tat_fig.to_html(full_html=False)


    # TAT MEDIAN
    df_median = calculate_median_tat_by_month(case_type_ids, start_date, end_date, date_by, discipline)
    # SORT MONTHS PROPERLY
    df_median["Month"] = df_median["Month"].apply(lambda x: parse_group_date(x, date_by))

    df_median = df_median.sort_values("Month")
    df_median["Month"] = df_median["Month"].dt.strftime("%b %Y")

    months = df_median["Month"].tolist()
    medians = df_median["Median TAT"].tolist()

    median_fig = go.Figure()

    median_fig.add_trace(go.Scatter(
        x=months,
        y=medians,
        mode='lines+markers',
        name='Median TAT',
        line=dict(color='darkorange')
    ))

    median_fig.update_layout(
        title='Median Turnaround Time',
        xaxis_title=date_by,
        yaxis_title='Days',
        height=500,
        width=1500,
        margin=dict(t=40, b=40, l=40, r=40),
    )

    median_graph = median_fig.to_html(full_html=False)

    case_type_colors = {
        'B': '#6C4E8A',     # Muted dark purple
        'D': '#669999',     # Muted teal
        'M': '#A9D0A9',     # Soft green
        'N': '#E6C36D',     # Muted gold
        'P': '#E9A25F',     # Soft orange
        'PM': '#B86B45',    # Muted burnt orange
        'Q': '#BBA0D6',     # Soft purple
        'R': '#DCDCDC',     # Light gray
        'X': '#6E6E6E'      # Muted dark gray
}

    code_to_name = {ct.code: ct.name for ct in CaseTypes.query.all()}
    legend_labels = {code: f"{code} - {code_to_name.get(code, '')}" for code in case_type_colors.keys()}

    # SUBMITTED CASES GRAPH
    df_volume = calculate_case_volume_by_month(case_type_ids, start_date, end_date, date_by, discipline)
    df_volume["Month"] = df_volume["Month"].apply(lambda x: parse_group_date(x, date_by))
    df_volume = df_volume.sort_values("Month")
    if date_by == 'Quarter':
        df_volume["Month"] = df_volume["Month"].dt.to_period('Q').apply(lambda p: f"Q{p.quarter} {p.year}")
    elif date_by == 'Year':
        df_volume["Month"] = df_volume["Month"].dt.strftime('%Y')
    else:
        df_volume["Month"] = df_volume["Month"].dt.strftime('%b %Y')

    months = df_volume['Month'].tolist()

    months = df_volume['Month'].tolist()
    case_type_codes = [col for col in df_volume.columns if col != 'Month']

    volume_fig = go.Figure()


    for code in case_type_codes:
        volume_fig.add_trace(go.Bar(
            x=months,
            y=df_volume[code],
            name=legend_labels.get(code, code),
            marker_color=case_type_colors.get(code, 'lightgray'),
            text=df_volume[code],  # Label per segment
            textposition='inside',
            insidetextanchor='middle'
        ))

    totals = df_volume[case_type_codes].sum(axis=1)
    volume_fig.add_trace(go.Scatter(
        x=months,
        y=totals,
        text=totals.astype(str),
        mode='text',
        textposition='top center',
        showlegend=False
    ))

    volume_fig.update_layout(
        barmode='stack',
        xaxis_title=date_by,
        yaxis_title='Number of Cases',
        height=500,
        width=1500,
        margin=dict(t=40, b=40, l=40, r=40)
    )
    volume_graph = volume_fig.to_html(full_html=False)

    months, open_counts, closed_counts = get_open_closed_case_data(
        case_type_ids=form.case_type.data,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        date_by=date_by,
        discipline=discipline
    )

    if months:
        fig_oc = go.Figure()

        fig_oc.add_trace(go.Bar(
            x=months,
            y=open_counts,
            name='Open',
            marker_color='#A9D0A9',
            text=open_counts,
            textposition='inside',
            insidetextanchor='middle'
        ))

        fig_oc.add_trace(go.Bar(
            x=months,
            y=closed_counts,
            name='Closed',
            marker_color='rgb(96, 96, 96)',
            text=closed_counts,
            textposition='inside',
            insidetextanchor='middle'
        ))


        fig_oc.update_layout(
            barmode='stack',
            xaxis_title=date_by,
            yaxis_title="Case Count",
            height=500,
            width=1500,
            margin=dict(t=40, b=40, l=40, r=40),
            legend_title_text="Case Status"
        )

        open_closed_barchart = fig_oc.to_html(full_html=False)
    # Step 1: Filter relevant case IDs (with toxicology_start_date)
    case_ids = db.session.query(Cases.id).filter(
        getattr(Cases, f"{discipline.lower()}_start_date").isnot(None)
    ).all()
    case_ids = [c[0] for c in case_ids]

    # Step 2: Remove any that have a _T1 record (i.e., keep only open cases)
    open_case_ids = set(case_ids)
    if case_ids:
        for i in range(0, len(case_ids), 1000):
            chunk = case_ids[i:i+1000]
            closed_ids = db.session.query(Records.case_id).filter(
                Records.case_id.in_(chunk),
                Records.record_name.like('%\\_T1', escape='\\')
            ).all()
            open_case_ids -= {c[0] for c in closed_ids}

    # Step 3: Query open case objects sorted by toxicology_start_date
    # and apply extra filtering conditions
    open_cases = Cases.query.filter(
        Cases.create_date > datetime(2025, 1, 1),
        Cases.id.in_(open_case_ids),
        Cases.case_status != "No Testing Requested",
        Cases.case_type.in_(selected_case_types),
        Cases.db_status != 'Removed'
    ).order_by(getattr(Cases, f"{discipline.lower()}_start_date").asc())


    df_box = get_raw_tat_data(case_type_ids, start_date, end_date, date_by, discipline)
    box_plot = go.Figure()

    colors_tat = [
        '#2E86AB',  # clinical blue
        '#66A182',  # soft green
        '#F6C85F',  # lab yellow
        '#D96C75',  # muted red
        '#A069C7',  # violet
        '#5D6D7E',  # cool gray
        '#B8B8B8',  # light gray
        '#FF8C42',  # orange
        '#9BC53D',  # green-yellow
        '#E15D44'   # coral red
    ]

    months_sorted = sorted(df_box['Month'].unique(), key=lambda x: parse_group_date(x, date_by))


    for i, month in enumerate(months_sorted):
        color = colors_tat[i % len(colors_tat)]
        month_data = df_box[df_box['Month'] == month]
        box_plot.add_trace(go.Box(
            y=month_data['tat_days'],
            x=[month] * len(month_data),
            name="Box Plots" if i == 0 else month,
            boxpoints='outliers',
            marker_color=color,
            line=dict(width=1),
            width=0.5,
            legendgroup='TAT',
            showlegend=(i == 0),
            yaxis='y1'
        ))




    # Add median/mean overlay lines
    monthly_stats = df_box.groupby('Month')['tat_days'].agg(['median', 'mean']).reset_index()
    monthly_stats['SortKey'] = monthly_stats['Month'].apply(lambda x: parse_group_date(x, date_by))
    monthly_stats = monthly_stats.sort_values('SortKey')
    monthly_stats = monthly_stats.drop(columns='SortKey')



    avg_open_df = calculate_avg_days_open_per_month(case_type_ids, start_date, end_date, db.session, date_by, discipline)

    # --- Median Line ---
    box_plot.add_trace(go.Scatter(
        x=monthly_stats['Month'],
        y=monthly_stats['median'],
        name='Median TAT',
        mode='lines+markers',
        line=dict(dash='solid', color='blue'),
        marker=dict(symbol='circle', size=8),
        yaxis='y1'
    ))

    # --- Mean Line ---
    box_plot.add_trace(go.Scatter(
        x=monthly_stats['Month'],
        y=monthly_stats['mean'],
        name='Average TAT',
        mode='lines+markers',
        line=dict(dash='dot', color='blue'),
        marker=dict(symbol='diamond', size=8),
        yaxis='y1'
    ))

    # --- Open Case Counts Line (Dotted Black) ---
    # Build discipline-specific date attribute dynamically
    date_attr = getattr(Cases, f"{discipline.lower()}_start_date")

    # Query all cases in range for that discipline
    all_cases = Cases.query.filter(
        date_attr.isnot(None),
        date_attr >= start_date,
        date_attr <= end_date,
        Cases.create_date > datetime(2025, 1, 1),
        Cases.case_type.in_(case_type_ids),
        Cases.db_status != 'Removed',
        Cases.case_status != 'No Testing Requested'
    ).all()
    open_pct_by_month = []

    for month in months_sorted:
        month_cases = [
            case for case in all_cases
            if format_date_by(getattr(case, f"{discipline.lower()}_start_date", None), date_by) == month
        ]

        case_ids = [c.id for c in month_cases]
        closed_case_ids = {
            r.case_id for r in Records.query
            .filter(
                Records.case_id.in_(case_ids),
                Records.record_name.like('%\\_T1', escape='\\')
            ).all()
        }

        total = len(month_cases)
        closed = len(closed_case_ids)
        open = total - closed

        open_pct = (open / total) * 100 if total > 0 else 0
        open_pct_by_month.append(open_pct)


    box_plot.add_trace(go.Scatter(
        x=months_sorted,
        y=open_pct_by_month,
        name='Open Cases (%)',
        mode='lines+markers',
        line=dict(dash='dot', color='black'),
        marker=dict(symbol='square', size=8),
        yaxis='y2'
    ))

    # --- Layout with Dual Y-Axis ---
    box_plot.update_layout(
        xaxis_title=date_by,
        yaxis=dict(
            title='TAT (Days)',
            side='left',
            showgrid=False
        ),
        yaxis2=dict(
            title='Case Count %',
            overlaying='y',
            side='right',
            range=[0, 110],
            showgrid=False
        ),
        height=650,
        width=1500,
        boxmode='group',
        margin=dict(t=40, b=40, l=40, r=40)
    )
    box_plot_html = pio.to_html(box_plot, full_html=False)



    thresholds = [15, 30, 45, 60, 90]
    table_rows = []

    # Ensure Month column is datetime sortable
    df_box["Month_dt"] = df_box["Month"].apply(lambda x: parse_group_date(x, date_by))

    months = df_box.sort_values("Month_dt")["Month"].unique()

    for month in months:
        group = df_box[df_box["Month"] == month]
        group_closed = group[group["is_closed"]]
        group_open = group[~group["is_closed"]]

        row = {
            "Date": month,
            "Submitted": len(group),
            "Closed": len(group_closed),
            "Open": len(group_open)
        }

        if not group_closed.empty:
            row["Avg TAT"] = round(group_closed["tat_days"].mean(), 1)
            row["Median TAT"] = round(group_closed["tat_days"].median(), 1)
            for t in thresholds:
                count = (group_closed["tat_days"] < t).sum()
                pct = round((count / len(group_closed)) * 100, 1)
                row[f"<{t}"] = count
                row[f"<{t} (%)"] = pct
        else:
            row["Avg TAT"] = ""
            row["Median TAT"] = ""
            for t in thresholds:
                row[f"<{t}"] = 0
                row[f"<{t} (%)"] = 0.0

        table_rows.append(row)

    tat_table_df = pd.DataFrame(table_rows)

    # Summary Rows
    count_cols = [f"<{t}" for t in thresholds]
    percent_cols = [f"<{t} (%)" for t in thresholds]

    totals = tat_table_df[["Submitted", "Closed", "Open"] + count_cols].sum(numeric_only=True)
    total_closed = totals["Closed"]

    # Pull all closed case TATs from df_box
    closed_tats_all = df_box[df_box["is_closed"]]["tat_days"]

    # Add Avg and Median TAT to totals row
    totals["Avg TAT"] = round(closed_tats_all.mean(), 1) if not closed_tats_all.empty else ""
    totals["Median TAT"] = round(closed_tats_all.median(), 1) if not closed_tats_all.empty else ""

    # Fill in percentage columns
    for t in thresholds:
        count = totals[f"<{t}"]
        pct = round((count / total_closed) * 100, 1) if total_closed > 0 else 0.0
        totals[f"<{t} (%)"] = pct

    totals["Date"] = "Total"


    # --- Other summaries ---
    averages = tat_table_df.select_dtypes(include=["float", "int"]).mean(numeric_only=True).round(1)
    medians = tat_table_df.select_dtypes(include=["float", "int"]).median(numeric_only=True).round(1)
    mins = tat_table_df.select_dtypes(include=["float", "int"]).min(numeric_only=True)
    maxs = tat_table_df.select_dtypes(include=["float", "int"]).max(numeric_only=True)

    averages["Date"] = "Average"
    medians["Date"] = "Median"
    mins["Date"] = "Min"
    maxs["Date"] = "Max"

    # Combine summary rows
    summary_df = pd.DataFrame([totals, averages, medians, mins, maxs])
    tat_table_df = pd.concat([tat_table_df, summary_df], ignore_index=True)

    # Final output for Jinja2
    tat_counts_dict = tat_table_df.set_index("Date").to_dict(orient="index")



    # Step 1: Melt the wide-format volume dataframe into long format
    submitted_case_types_melt = df_volume.melt(id_vars='Month', var_name='Case Type', value_name='Cases')
    submitted_case_types_melt.rename(columns={'Month': 'Date'}, inplace=True)

    if date_by == 'Quarter':
        submitted_case_types_melt = submitted_case_types_melt[submitted_case_types_melt['Date'].str.startswith('Q')]
        submitted_case_types_melt['Date'] = submitted_case_types_melt['Date'].apply(lambda d: parse_group_date(d, 'Quarter'))
    elif date_by == 'Year':
        submitted_case_types_melt['Date'] = submitted_case_types_melt['Date'].apply(lambda d: datetime.strptime(d, '%Y'))
    else:
        submitted_case_types_melt['Date'] = submitted_case_types_melt['Date'].apply(lambda d: datetime.strptime(d, '%b %Y'))


    # Step 3: Pivot back to wide format for the table
    table_df = submitted_case_types_melt.pivot_table(
        index='Date',
        columns='Case Type',
        values='Cases',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Step 4: Reformat date back to 'Month Year' string
    table_df['Date'] = pd.to_datetime(table_df['Date'], errors='coerce')

    table_df['Date'] = table_df['Date'].dt.strftime('%b %Y')

    # Step 5: Optional summary rows
    if len(table_df) > 1:
        numeric_data = table_df.drop('Date', axis=1)

        # Total (cast to int)
        table_df.loc['Total'] = numeric_data.sum(numeric_only=True).astype(int)
        table_df.loc['Total', 'Date'] = 'Total'

        # Average (1 decimal place)
        table_df.loc['Average'] = numeric_data.mean(numeric_only=True).round(1)
        table_df.loc['Average', 'Date'] = 'Average'

        # Median (1 decimal place)
        table_df.loc['Median'] = numeric_data.median(numeric_only=True).round(1)
        table_df.loc['Median', 'Date'] = 'Median'

        # Min (cast to int)
        table_df.loc['Min'] = numeric_data.min(numeric_only=True).astype(int)
        table_df.loc['Min', 'Date'] = 'Min'

        # Max (cast to int)
        table_df.loc['Max'] = numeric_data.max(numeric_only=True).astype(int)
        table_df.loc['Max', 'Date'] = 'Max'


    # Convert to dict for the template
    submitted_case_table = table_df.to_dict(orient='index')
    submitted_case_columns = list(table_df.columns[1:])  # exclude 'Date'


    # processing batches 
    processing_batches = Batches.query.filter(Batches.batch_status == 'Processing', Batches.db_status == 'Active').order_by(Batches.create_date).all()

    # SMALL TAT % GRAPH

    custom_case_codes = ['D', 'M', 'X', 'P', 'C', 'PM', 'N']

    custom_start_date = datetime(2025, 1, 1).date()
    custom_end_date = datetime.now().date()
    custom_date_by = 'Month'

    custom_case_type_ids = [
        ct.id for ct in CaseTypes.query.filter(CaseTypes.code.in_(custom_case_codes)).all()
    ]

    custom_tat_df = calculate_tat_percentages(custom_case_type_ids, custom_start_date, custom_end_date, custom_date_by, discipline)

    custom_tat_df['Month'] = custom_tat_df['Month'].apply(lambda x: parse_group_date(x, custom_date_by))
    custom_tat_df = custom_tat_df.sort_values('Month')
    custom_tat_df['Month'] = custom_tat_df['Month'].dt.strftime('%b %Y')

    months_small = custom_tat_df['Month'].tolist()
    tat_15_s = custom_tat_df['15-Day %'].tolist()
    tat_30_s = custom_tat_df['30-Day %'].tolist()
    tat_45_s = custom_tat_df['45-Day %'].tolist()
    tat_60_s = custom_tat_df['60-Day %'].tolist()
    tat_90_s = custom_tat_df['90-Day %'].tolist()
    tat_open_s = custom_tat_df['Still Open %'].tolist()

    custom_tat_fig = go.Figure()
    custom_tat_fig.add_trace(go.Scatter(x=months_small, y=tat_15_s, mode='lines+markers', name='15 Days', line=dict(color='blue')))
    custom_tat_fig.add_trace(go.Scatter(x=months_small, y=tat_30_s, mode='lines+markers', name='30 Days', line=dict(color='red')))
    custom_tat_fig.add_trace(go.Scatter(x=months_small, y=tat_45_s, mode='lines+markers', name='45 Days', line=dict(color='green')))
    custom_tat_fig.add_trace(go.Scatter(
        x=months_small, y=tat_60_s, mode='lines+markers',
        name='60 Days', line=dict(color='purple'),
        visible='legendonly'
    ))
    custom_tat_fig.add_trace(go.Scatter(
        x=months_small, y=tat_90_s, mode='lines+markers',
        name='90 Days', line=dict(color='gold'),
        visible='legendonly'
    ))
    custom_tat_fig.add_trace(go.Scatter(
        x=months_small, y=tat_open_s, mode='lines+markers',
        name='Open', line=dict(color='black', dash='dot')
    ))

    # Add 90% ref line
    custom_tat_fig.add_shape(
        type="line",
        x0=-0.5, y0=90,
        x1=len(months_small) - 0.5, y1=90,
        line=dict(color="black", width=2, dash="dot")
    )
    custom_tat_fig.add_annotation(
        x=len(months_small) - 1,
        y=90,
        text="90%",
        showarrow=False,
        font=dict(color="black", size=12),
        xanchor="left",
        yanchor="top"
    )

    custom_tat_fig.update_layout(
        title_text='Turn Around Times for D, M, X, P, C, PM, N Cases',
        xaxis_title='Month',
        yaxis_title='%',
        yaxis=dict(range=[0, 110]),
        height=300,
        width=850,
        margin=dict(t=30, b=30, l=40, r=40)
    )

    custom_tat_graph = custom_tat_fig.to_html(full_html=False)


    # -=-=-=-=- PACKETS BAR GRAPH -=-=-=-=-
    litigation_packets = LitigationPackets.query.filter(
        LitigationPackets.db_status == 'Active',
        LitigationPackets.packet_status.in_(['Created', 'Ready for PP', 'Ready for PR', 'Waiting for Declaration'])
    )

    created_count = sum(1 for lp in litigation_packets if lp.packet_status == 'Created')
    ready_pp_count = sum(1 for lp in litigation_packets if lp.packet_status == 'Ready for PP')
    ready_pr_count = sum(1 for lp in litigation_packets if lp.packet_status == 'Ready for PR')
    waiting_for_declaration = sum(1 for lp in litigation_packets if lp.packet_status == 'Waiting for Declaration')
    created_packets = LitigationPackets.query.filter_by(packet_status='Created', db_status='Active').all()
    ready_pp_packets = LitigationPackets.query.filter_by(packet_status='Ready for PP', db_status='Active').all()
    ready_pr_packets = LitigationPackets.query.filter_by(packet_status='Ready for PR', db_status='Active').all()
    waiting_for_dec_packets = LitigationPackets.query.filter_by(packet_status='Waiting for Declaration', db_status='Active').all()


    # Reverse the order: Created on top, Ready for PR on bottom
    statuses = ['Created', 'Ready for PP', 'Waiting for Dec', 'Ready for PR']
    counts = [created_count,  ready_pp_count,waiting_for_declaration, ready_pr_count]
    colors = ['#ffc107', '#28a745', '#17a2b8']

    # Reverse all three lists
    statuses = statuses[::-1]
    counts = counts[::-1]
    colors = colors[::-1]

    fig_litigation_packets = go.Figure(data=[
        go.Bar(
            x=counts,
            y=statuses,
            orientation='h',
            marker_color=colors,
            text=counts,
            textposition='outside',
            name='Litigation Packet Status'
        )
    ])

    fig_litigation_packets.update_layout(
        height=190,
        width=745,
        margin=dict(l=80, r=20, t=20, b=40),
        xaxis_title='Count',
        showlegend=False
    )

    litigation_status_bar_html = pio.to_html(fig_litigation_packets, full_html=False)

    user_locks = collect_user_locks(current_user.initials)

    return render_template(
                            'dashboard.html',
                            form=form,
                            pending_dict=pending_dict,
                            status_bar=status_bar_html,
                            testing_bar=testing_bar_html,
                            testing_cases=testing_cases,
                            cr_cases=cr_cases,
                            dr_cases=dr_cases,
                            selected_case_type_names=selected_case_type_names,
                            tat_graph=tat_graph,
                            median_graph=median_graph,
                            volume_graph=volume_graph,
                            open_closed_barchart=open_closed_barchart,
                            open_cases=open_cases,
                            box_plot=box_plot_html,
                            submitted_case_table=submitted_case_table,
                            submitted_case_columns=submitted_case_columns,
                            counts_dict=tat_counts_dict,
                            cr_cases_reverted=cr_cases_reverted,
                            cr_cases_original=cr_cases_original,
                            processing_batches=processing_batches,
                            drafting_cases=drafting_cases,
                            custom_tat_graph=custom_tat_graph,
                            litigation_status_bar=litigation_status_bar_html,
                            created_packets=created_packets,
                            ready_pp_packets=ready_pp_packets,
                            ready_pr_packets=ready_pr_packets,
                            waiting_for_dec_packets=waiting_for_dec_packets,
                            user_locks=user_locks
                        )


@dashboard.route('/dashboard/update_discipline', methods=['POST'])
@login_required
def update_discipline():
    new_discipline = request.form.get('discipline')
    if new_discipline in ['Toxicology', 'Biochemistry', 'Drug', 'External']:
        current_user.dashboard_discipline = new_discipline
        db.session.commit()
    return redirect(url_for('dashboard.get_dashboard'))

