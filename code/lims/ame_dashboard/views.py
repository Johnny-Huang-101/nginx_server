from flask import request, Blueprint, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
import plotly.graph_objects as go
import plotly.io as pio
from collections import defaultdict

from jinja2 import Template

from datetime import datetime

from lims.dashboard.functions import format_date_by  # You already use this for Month/Quarter/Year grouping

ame_dashboard = Blueprint('ame_dashboard', __name__)
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


@ame_dashboard.route(f'/ame_dashboard', methods=['GET', 'POST'])
@login_required
def get_ame_dashboard():
    
    # *************************************************************************
    # SCRIPT FOR UPDATING OCME STATUS, PENDING_DC, AND PENDING_AR
    # *************************************************************************

    all_active_cases = Cases.query.filter(Cases.db_status == 'Active').all()

    updated_count = 0
    for case in all_active_cases:
        cod_a = (case.cod_a or "").strip().upper()
        cert_date = case.certificate_report_date
        autopsy_type = (case.autopsy_type or "").strip()

        # Store original values for comparison
        original_pending_dc = case.pending_dc
        original_pending_ar = case.pending_ar
        original_ocme_status = case.ocme_status

        # Logic for pending_dc
        if cod_a == '':
            pending_dc = 'Y'  # Don't change it if blank
        else:
            pending_dc = 'Y' if cod_a == 'PENDING' else 'N'

        # Logic for pending_ar
        if autopsy_type == 'ADMINISTRATIVE REVIEW':
            pending_ar = 'N'
        else:
            pending_ar = 'Y' if cert_date is None else 'N'

        # Apply new values
        case.pending_dc = pending_dc
        case.pending_ar = pending_ar

        # OCME status logic
        if pending_dc == 'N' and pending_ar == 'N':
            new_status = 'Closed'
        else:
            new_status = None

        if case.ocme_status != new_status and new_status:
            case.ocme_status = new_status

        # Track updates
        if (case.pending_dc != original_pending_dc or
            case.pending_ar != original_pending_ar or
            case.ocme_status != original_ocme_status):
            db.session.add(case)
            updated_count += 1

    db.session.commit()
    print(f"Updated {updated_count} case(s) based on cod_a, certificate_report_date, and autopsy_type logic.")

    # *************************************************************************
    # END OF SCRIPT
    # *************************************************************************
        
    selected_year = request.args.get('year')
    selected_days = request.args.get('days')

    # Enforce mutual exclusivity
    if selected_year and selected_days:
        selected_days = None  # Ignore days if year is selected

    # Safely parse `days`
    try:
        days = int(selected_days) if selected_days else 60
    except (ValueError, TypeError):
        days = 60

    # Determine if year filter should be used
    selected_year_raw = request.args.get('year')
    use_year_filter = False
    date_filter_range = None
    if selected_year_raw:
        try:
            selected_year_int = int(selected_year_raw)
            start_date = datetime(selected_year_int, 1, 1)
            end_date = datetime.now() if selected_year_int == datetime.now().year else datetime(selected_year_int, 12, 31)
            date_filter_range = (start_date, end_date)
            use_year_filter = True
        except ValueError:
            flash("Invalid year parameter; showing recent days instead.", "warning")
            use_year_filter = False
            date_filter_range = None
    else:
        cutoff_date = datetime.now() - dt.timedelta(days=days)

    is_indigent = False

    selected_year = request.args.get('year')
    use_year_filter = False

    med_users = Users.query.filter_by(permissions='MED').all()
    if current_user.initials == 'CSL' or current_user.permissions in ['Owner', 'ADM-Management']:
        med_initials = sorted({u.initials for u in med_users if u.initials})
        med_initials += ['All', 'None', 'Indigent']
    else:
        med_initials = [current_user.initials, 'All']

        # One-time parse of initials and days (no redirects)
    selected_initials = (request.args.get('initials', '') or '').replace('+', ' ').strip()
    try:
        days = int(request.args.get('days', 60))
    except (ValueError, TypeError):
        days = 60
    cutoff_date = datetime.now() - dt.timedelta(days=days)

    # Build allowed initials list based on permissions
    med_users = Users.query.filter_by(permissions='MED').all()
    if current_user.initials == 'CSL' or current_user.permissions in ['Owner', 'ADM-Management']:
        med_initials = sorted({u.initials for u in med_users if u.initials})
        med_initials += ['All', 'None', 'Indigent']
    else:
        med_initials = [current_user.initials, 'All']

    # Default initials if none/unknown
    if not selected_initials:
        selected_initials = current_user.initials if current_user.initials in med_initials else med_initials[0]

    target_user = None
    personnel_id = None

    if selected_initials in ['All', 'None', 'Indigent']:
        pass  # handled in base_query selection below
    else:
        target_user = Users.query.filter_by(initials=selected_initials).first()
        if not target_user:
            flash("Unknown initials; defaulting to your initials.", "warning")
            selected_initials = current_user.initials if current_user.initials in med_initials else med_initials[0]
            target_user = Users.query.filter_by(initials=selected_initials).first()

    if selected_initials not in ['All', 'None', 'Indigent']:
        personnel_id = getattr(target_user, 'personnel_id', None)
        if not personnel_id:
            flash("No personnel ID for that user; defaulting to your initials.", "warning")
            selected_initials = current_user.initials if current_user.initials in med_initials else med_initials[0]
            target_user = Users.query.filter_by(initials=selected_initials).first()
            personnel_id = getattr(target_user, 'personnel_id', None)

    # Base query without any redirects
    if selected_initials == 'All':
        user_ids = [u.personnel_id for u in med_users if u.personnel_id]
        base_query = Cases.query.filter(Cases.primary_pathologist.in_(user_ids), Cases.db_status == 'Active')
    elif selected_initials == 'None':
        base_query = Cases.query.filter(Cases.primary_pathologist == None, Cases.db_status == 'Active', ~Cases.fa_case_comments.ilike('%indigent%'))
    elif selected_initials == 'Indigent':
        base_query = Cases.query.filter(Cases.db_status == 'Active', Cases.autopsy_type == 'INDIGENT')
        is_indigent = True
    else:
        base_query = Cases.query.filter(Cases.primary_pathologist == personnel_id, Cases.db_status == 'Active')

    # Split queries
    if use_year_filter:
        cases_lt = base_query.filter(Cases.fa_case_entry_date.between(date_filter_range[0], date_filter_range[1])).all()
        cases_gt = []  # No > section needed if filtering by full year
    else:
        cases_lt = base_query.filter(Cases.fa_case_entry_date >= cutoff_date).all()
        cases_gt = base_query.filter(Cases.fa_case_entry_date < cutoff_date).all()


    def categorize_cases(cases, include_closed=True):
        pending_dc = [c for c in cases if c.pending_dc == 'Y' and (c.autopsy_type or '').strip().lower() != 'administrative review']
        pending_ar = [c for c in cases if c.pending_ar == 'Y']
        closed = [c for c in cases if c.ocme_status == 'Closed'] if include_closed else []
        return pending_dc, pending_ar, closed

    lt_pending_dc, lt_pending_ar, lt_closed = categorize_cases(cases_lt, include_closed=True)
    gt_pending_dc, gt_pending_ar, _ = categorize_cases(cases_gt, include_closed=False)

    lt_pending_dc_admin_review = [
    c for c in cases_lt if (c.autopsy_type or '').strip().lower() == 'administrative review' and c.pending_dc == 'Y'
    ]

    gt_pending_dc_admin_review = [
        c for c in cases_gt if (c.autopsy_type or '').strip().lower() == 'administrative review' and c.pending_dc == 'Y'
    ]

    lt_pending_ar_only = [
        c for c in lt_pending_ar if c.pending_dc == 'N'
    ]

    gt_pending_ar_only = [
        c for c in gt_pending_ar if c.pending_dc == 'N'
    ]


    all_cases = lt_pending_dc + lt_pending_ar + lt_closed + gt_pending_dc + gt_pending_ar
    case_ids = [case.id for case in all_cases]
    reports_by_case = defaultdict(list)
    report_rows = Reports.query.filter(Reports.case_id.in_(case_ids), Reports.db_status == 'Active').all()
    for report in report_rows:
        label = report.report_name.rsplit('_', 1)[-1]
        reports_by_case[report.case_id].append({'id': report.id, 'label': label})

    for case in all_cases:
        case.formatted_reports = reports_by_case.get(case.id, [])

    def create_pie_chart(dc_count, ar_count, closed_count, include_closed):
        labels = ['Pending DC', 'Pending Report']
        values = [dc_count, ar_count]
        colors = ['#007bff', '#28a745']
        if include_closed:
            labels.append('Closed')
            values.append(closed_count)
            colors.append('#6c757d')

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            textinfo='percent',
            hovertext=labels,
            hoverinfo='text+percent',
            marker=dict(colors=colors),
            hole=0.3
        )])
        fig.update_layout(
            width=350,
            height=350,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.2,
                x=0.5,
                xanchor='center',
                traceorder='normal'
            )
        )
        return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

    pie_chart_lt = create_pie_chart(len(lt_pending_dc), len(lt_pending_ar), len(lt_closed), include_closed=True)
    pie_chart_gt = create_pie_chart(len(gt_pending_dc), len(gt_pending_ar), 0, include_closed=False)

    box_data = []
    if lt_pending_dc:
        box_data.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in lt_pending_dc],
            name='Pending DC (<)',
            orientation='h',
            marker_color='#007bff',
            boxmean=True,
            boxpoints='outliers'
        ))
    if lt_pending_ar:
        box_data.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in lt_pending_ar],
            name=f'Pending Report (<) {days}',
            orientation='h',
            marker_color='#28a745',
            boxmean=True,
            boxpoints='outliers'
        ))
    if gt_pending_dc:
        box_data.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in gt_pending_dc],
            name='Pending DC (>)',
            orientation='h',
            marker_color='#6699cc',
            boxmean=True,
            boxpoints='outliers'
        ))
    if gt_pending_ar:
        box_data.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in gt_pending_ar],
            name='Pending Report (>)',
            orientation='h',
            marker_color='#99cc99',
            boxmean=True,
            boxpoints='outliers'
        ))

    box_fig = go.Figure(data=box_data)
    box_fig.update_layout(
        xaxis_title='Days Open',
        margin=dict(t=40, l=50, r=30, b=40),
        height=400,
        width=1500
    )
    box_plot_html = pio.to_html(box_fig, full_html=False, include_plotlyjs=False)

    # Box plot for < days
    box_data_lt = []

    if use_year_filter:
        # Yearly selected — show all cases from that year
        year_pending_ar = [c for c in cases_lt if c.pending_ar == 'Y']
        year_pending_dc = [c for c in cases_lt if c.pending_dc == 'Y' and (c.autopsy_type or '').strip().lower() != 'administrative review']

        if year_pending_ar:
            box_data_lt.append(go.Box(
                x=[(datetime.now() - c.fa_case_entry_date).days for c in year_pending_ar],
                name=f'Pending Report ({selected_year})',
                orientation='h',
                marker_color='#28a745',
                boxmean=True,
                boxpoints='outliers',
                legendrank=2
            ))
        if year_pending_dc:
            box_data_lt.append(go.Box(
                x=[(datetime.now() - c.fa_case_entry_date).days for c in year_pending_dc],
                name=f'Pending DC ({selected_year})',
                orientation='h',
                marker_color='#007bff',
                boxmean=True,
                boxpoints='outliers',
                legendrank=1
            ))
    else:
        # Days selected — show only < days cases
        if lt_pending_ar:
            box_data_lt.append(go.Box(
                x=[(datetime.now() - c.fa_case_entry_date).days for c in lt_pending_ar],
                name=f'Pending Report (<{days}d)',
                orientation='h',
                marker_color='#28a745',
                boxmean=True,
                boxpoints='outliers',
                legendrank=2
            ))
        if lt_pending_dc:
            box_data_lt.append(go.Box(
                x=[(datetime.now() - c.fa_case_entry_date).days for c in lt_pending_dc],
                name=f'Pending DC (<{days}d)',
                orientation='h',
                marker_color='#007bff',
                boxmean=True,
                boxpoints='outliers',
                legendrank=1
            ))

    box_fig_lt = go.Figure(data=box_data_lt)
    box_fig_lt.update_layout(
        xaxis_title='Days Open',
        margin=dict(t=40, l=50, r=30, b=40),
        height=400,
        width=1500
    )
    box_plot_lt_html = pio.to_html(box_fig_lt, full_html=False, include_plotlyjs=False)



    # Box plot for > days
    box_data_gt = []

    if gt_pending_ar:
        box_data_gt.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in gt_pending_ar],
            name='Pending Report (>)',
            orientation='h',
            marker_color='#99cc99',
            boxmean=True,
            boxpoints='outliers',
            legendrank=2
        ))
    if gt_pending_dc:
        box_data_gt.append(go.Box(
            x=[(datetime.now() - c.fa_case_entry_date).days for c in gt_pending_dc],
            name='Pending DC (>)',
            orientation='h',
            marker_color='#6699cc',
            boxmean=True,
            boxpoints='outliers',
            legendrank=1
        ))
    box_fig_gt = go.Figure(data=box_data_gt)
    box_fig_gt.update_layout(
        xaxis_title='Days Open',
        margin=dict(t=40, l=50, r=30, b=40),
        height=400,
        width=1500
    )
    box_plot_gt_html = pio.to_html(box_fig_gt, full_html=False, include_plotlyjs=False)

    # === Closed cases in past 12 months ===
    twelve_months_ago = datetime.now() - dt.timedelta(days=365)
    closed_last_12mo_cases = None
    if selected_initials == 'All':
        closed_last_12mo = Cases.query.filter(
            Cases.primary_pathologist.in_([u.personnel_id for u in med_users if u.personnel_id]),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).count()
        closed_last_12mo_cases = Cases.query.filter(
            Cases.primary_pathologist.in_([u.personnel_id for u in med_users if u.personnel_id]),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).all()
    elif selected_initials == 'None':
        closed_last_12mo = Cases.query.filter(
            Cases.primary_pathologist == None,
            ~Cases.fa_case_comments.ilike('%indigent%'),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).count()
        closed_last_12mo_cases = Cases.query.filter(
            Cases.primary_pathologist == None,
            ~Cases.fa_case_comments.ilike('%indigent%'),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).all()

    elif selected_initials == 'Indigent':
        closed_last_12mo = Cases.query.filter(
            Cases.primary_pathologist == None,
            Cases.fa_case_comments.ilike('%indigent%'),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).count()
        closed_last_12mo_cases = Cases.query.filter(
            Cases.primary_pathologist == None,
            Cases.fa_case_comments.ilike('%indigent%'),
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).all()
    else:
        closed_last_12mo = Cases.query.filter(
            Cases.primary_pathologist == personnel_id,
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).count()

        closed_last_12mo_cases = Cases.query.filter(
            Cases.primary_pathologist == personnel_id,
            Cases.ocme_status == 'Closed',
            Cases.fa_case_entry_date >= twelve_months_ago,
            Cases.db_status == 'Active'
        ).all()
        
    lt_pending_cert_admin_cases = [c for c in cases_lt if c.pending_dc == 'Y' and c.autopsy_type == 'ADMINISTRATIVE REVIEW']
    gt_pending_cert_admin_cases = [c for c in cases_gt if c.pending_dc == 'Y' and c.autopsy_type == 'ADMINISTRATIVE REVIEW']

    lt_pending_cert_display = lt_pending_dc + lt_pending_cert_admin_cases
    gt_pending_cert_display = gt_pending_dc + gt_pending_cert_admin_cases
    def sort_by_days_open(cases):
        return sorted(
            cases,
            key=lambda c: (datetime.now() - c.fa_case_entry_date).days if c.fa_case_entry_date else -1,
            reverse=True
        )
    all_pending_cert_display = sort_by_days_open(lt_pending_cert_display + gt_pending_cert_display)



    def calculate_ame_tat_percentages(start_date, end_date, date_by, selected_initials):
        from collections import defaultdict

        # 1. Query ALL cases (open + closed)
        all_query = Cases.query.filter(
            Cases.autopsy_type != 'ADMINISTRATIVE REVIEW',
            Cases.fa_case_entry_date.isnot(None),
            Cases.fa_case_entry_date >= start_date,
            Cases.fa_case_entry_date <= end_date
        )
        if selected_initials != 'All':
            all_query = all_query.filter(Cases.primary_pathologist == selected_initials)
        all_cases = all_query.all()

        # 2. Query CLOSED cases
        closed_query = all_query.filter(
            Cases.ocme_status == 'Closed',
            Cases.certificate_report_date.isnot(None),
        )
        closed_cases = closed_query.all()

        if not all_cases:
            return pd.DataFrame(columns=["Month", "15-Day %", "30-Day %", "45-Day %", "60-Day %", "90-Day %", "Still Open %"])

        # 3. Group CLOSED TATs
        closed_grouped = defaultdict(list)
        for case in closed_cases:
            group_key = format_date_by(case.fa_case_entry_date, date_by)
            tat_days = (case.certificate_report_date - case.fa_case_entry_date).days
            closed_grouped[group_key].append(tat_days)

        # 4. Group ALL cases by month
        all_grouped = defaultdict(list)
        for case in all_cases:
            group_key = format_date_by(case.fa_case_entry_date, date_by)
            all_grouped[group_key].append(case)

        # 5. Calculate metrics
        result = []
        for group_key in sorted(all_grouped.keys()):
            all_cases_month = all_grouped[group_key]
            closed_tats = closed_grouped.get(group_key, [])

            total_all = len(all_cases_month)
            total_closed = len(closed_tats)
            total_open = total_all - total_closed
            open_pct = round(100 * total_open / total_all, 1) if total_all > 0 else 0.0

            pct_15 = round(100 * sum(d <= 15 for d in closed_tats) / total_closed, 1) if total_closed else 0
            pct_30 = round(100 * sum(d <= 30 for d in closed_tats) / total_closed, 1) if total_closed else 0
            pct_45 = round(100 * sum(d <= 45 for d in closed_tats) / total_closed, 1) if total_closed else 0
            pct_60 = round(100 * sum(d <= 60 for d in closed_tats) / total_closed, 1) if total_closed else 0
            pct_90 = round(100 * sum(d <= 90 for d in closed_tats) / total_closed, 1) if total_closed else 0

            result.append({
                "Month": group_key,
                "15-Day %": pct_15,
                "30-Day %": pct_30,
                "45-Day %": pct_45,
                "60-Day %": pct_60,
                "90-Day %": pct_90,
                "Still Open %": open_pct
            })

        return pd.DataFrame(result)

    tat_graph = None  # Default if year not selected

    if use_year_filter:
        # Define start and end of selected year
        year = int(selected_year)
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)

        date_by = 'Month'  # Only use month grouping for AME
        if selected_initials != 'All':
            tat_df = calculate_ame_tat_percentages(start_date, end_date, date_by, personnel_id)
        else:
            tat_df = calculate_ame_tat_percentages(start_date, end_date, date_by, selected_initials)

        # Prepare and format the month column
        tat_df['Month'] = tat_df['Month'].apply(lambda x: parse_group_date(x, date_by))
        tat_df = tat_df.sort_values('Month')
        tat_df['Month'] = tat_df['Month'].dt.strftime('%b %Y')

        # Extract data
        months = tat_df['Month'].tolist()
        tat_15 = tat_df['15-Day %'].tolist()
        tat_30 = tat_df['30-Day %'].tolist()
        tat_45 = tat_df['45-Day %'].tolist()
        tat_60 = tat_df['60-Day %'].tolist()
        tat_90 = tat_df['90-Day %'].tolist()
        still_open = tat_df['Still Open %'].tolist()

        # Build Plotly figure
        tat_fig = go.Figure()
        tat_fig.add_trace(go.Scatter(x=months, y=tat_15, mode='lines+markers', name='15 Days', line=dict(color='blue')))
        tat_fig.add_trace(go.Scatter(x=months, y=tat_30, mode='lines+markers', name='30 Days', line=dict(color='red')))
        tat_fig.add_trace(go.Scatter(x=months, y=tat_45, mode='lines+markers', name='45 Days', line=dict(color='green')))
        tat_fig.add_trace(go.Scatter(x=months, y=tat_60, mode='lines+markers', name='60 Days', line=dict(color='purple')))
        tat_fig.add_trace(go.Scatter(x=months, y=tat_90, mode='lines+markers', name='90 Days', line=dict(color='gold')))
        tat_fig.add_trace(go.Scatter(
            x=months,
            y=still_open,
            mode='lines+markers',
            name='Still Open %',
            line=dict(color='black', dash='dot')
        ))


        # Add 90% reference line
        tat_fig.add_shape(type="line", x0=-0.5, y0=90, x1=len(months) - 0.5, y1=90, line=dict(color="black", width=2, dash="dot"))
        tat_fig.add_annotation(x=len(months) - 1, y=90, text="90%", showarrow=False, font=dict(color="black", size=12), xanchor="left", yanchor="top")

        tat_fig.update_layout(
            xaxis_title='Month',
            yaxis_title='%',
            yaxis=dict(range=[0, 110]),
            height=500,
            width=1500,
            margin=dict(t=40, b=40, l=40, r=40),
        )

        tat_graph = tat_fig.to_html(full_html=False)



    return render_template('/ame_dashboard/ame_dashboard.html',
        selected_initials=selected_initials,
        days=days,
        med_initials=med_initials,
        pie_chart_lt=pie_chart_lt,
        pie_chart_gt=pie_chart_gt,
        lt_pending_cert_cases=lt_pending_dc,
        lt_pending_autopsy_cases=lt_pending_ar,
        lt_pending_cert_display=lt_pending_cert_display,
        gt_pending_cert_display=gt_pending_cert_display,
        lt_closed_cases=lt_closed,
        gt_pending_cert_cases=gt_pending_dc,
        gt_pending_autopsy_cases=gt_pending_ar,
        box_plot=box_plot_html,
        box_plot_lt=box_plot_lt_html,
        box_plot_gt=box_plot_gt_html,
        closed_last_12mo=closed_last_12mo,
        closed_last_12mo_cases=closed_last_12mo_cases,
        is_indigent=is_indigent,
        year=selected_year,
        tat_graph=tat_graph,
        all_pending_cert_display=all_pending_cert_display,
        lt_counts={
            'dc': len(lt_pending_dc),
            'ar': len(lt_pending_ar) - len(lt_pending_ar_only),
            'closed': len(lt_closed),
            'dc_admin_review': len(lt_pending_dc_admin_review),
            'ar_only': len(lt_pending_ar_only)
        },
        gt_counts={
            'dc': len(gt_pending_dc),
            'ar': len(gt_pending_ar) - len(gt_pending_ar_only),
            'dc_admin_review': len(gt_pending_dc_admin_review),
            'ar_only': len(gt_pending_ar_only)
        }
    )


@ame_dashboard.route('/all_personnel_boxplots')
@login_required
def all_personnel_boxplots():
    if current_user.initials != 'CSL':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('ame_dashboard.get_ame_dashboard'))

    comparison = request.args.get('comparison', '<')
    days = int(request.args.get('days', 60))
    cutoff_date = datetime.now() - dt.timedelta(days=days)

    med_users = Users.query.filter_by(permissions='MED').all()
    all_plots_html = []

    def generate_plot_html(user_label, cases, include_plotlyjs):
        pending_cert_cases = [c for c in cases if c.pending_dc == 'Y']
        pending_autopsy_cases = [c for c in cases if c.pending_ar == 'Y']
        closed_cases = [c for c in cases if c.ocme_status == 'Closed']

        # Box plot
        box_data = []
        if pending_cert_cases:
            days_open_cert = [(datetime.now() - c.fa_case_entry_date).days for c in pending_cert_cases]
            box_data.append(go.Box(
                x=days_open_cert,
                name='Pending DC',
                orientation='h',
                marker_color='#007bff',
                boxmean=True,
                boxpoints='outliers'
            ))
        if pending_autopsy_cases:
            days_open_autopsy = [(datetime.now() - c.fa_case_entry_date).days for c in pending_autopsy_cases]
            box_data.append(go.Box(
                x=days_open_autopsy,
                name='Pending Report',
                orientation='h',
                marker_color='#28a745',
                boxmean=True,
                boxpoints='outliers'
            ))

        # Always render the box plot
        box_fig = go.Figure(data=box_data)
        box_fig.update_layout(
            xaxis_title='Days Open',
            xaxis=dict(range=[0,60]),
            margin=dict(t=40, l=50, r=30, b=40),
            height=350,
            width=1000
        )
        box_plot_html = pio.to_html(box_fig, full_html=False, include_plotlyjs=include_plotlyjs)

        # Pie chart
        pie_fig = go.Figure(data=[go.Pie(
            labels=['Pending DC', 'Pending Report', 'Closed'],
            values=[len(pending_cert_cases), len(pending_autopsy_cases), len(closed_cases)],
            textinfo='label+value',
            hovertext=['Pending Death Certificate', 'Pending Autopsy Report', 'Closed'],
            hoverinfo='text+value',
            marker=dict(colors=['#007bff', '#28a745', '#6c757d']),
            hole=0.3
        )])
        pie_fig.update_layout(
            width=400,
            height=400,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.2,
                x=0.5,
                xanchor='center',
                traceorder='normal'
            )
        )
        pie_chart_html = pio.to_html(pie_fig, full_html=False, include_plotlyjs=include_plotlyjs)

        return {
            'user': user_label,
            'plot_html': box_plot_html,
            'pie_chart': pie_chart_html
        }

    # === "All" (first with JS included) ===
    all_cases = Cases.query.filter(
        Cases.primary_pathologist.isnot(None),
        Cases.fa_case_entry_date <= cutoff_date if comparison == '>' else Cases.fa_case_entry_date >= cutoff_date,
        Cases.db_status == 'Active'
    ).all()
    all_plots_html.append(generate_plot_html("All", all_cases, include_plotlyjs='cdn'))

    # === Per-user ===
    for user in med_users:
        if not user.personnel_id:
            continue
        user_cases = Cases.query.filter(
            Cases.primary_pathologist == user.personnel_id,
            Cases.fa_case_entry_date <= cutoff_date if comparison == '>' else Cases.fa_case_entry_date >= cutoff_date,
            Cases.db_status == 'Active'
        ).all()
        all_plots_html.append(generate_plot_html(user.initials, user_cases, include_plotlyjs=False))

    # === "None" (no primary pathologist) ===
    none_cases = Cases.query.filter(
        Cases.primary_pathologist == None,
        Cases.fa_case_entry_date <= cutoff_date if comparison == '>' else Cases.fa_case_entry_date >= cutoff_date,
        Cases.db_status == 'Active'
    ).all()
    all_plots_html.append(generate_plot_html("None", none_cases, include_plotlyjs=False))

    

    return render_template('/ame_dashboard/box_plots.html',
                           all_plots_html=all_plots_html,
                           comparison=comparison,
                           days=days)


@ame_dashboard.route('/me_data_script')
@login_required
def me_script():
    # Define the target primary_pathologist ID
    target_id = 15

    # Query all active cases for that primary pathologist
    cases = Cases.query.filter(
        Cases.primary_pathologist == target_id,
        Cases.db_status == 'Active'
    ).all()

    updated_count = 0

    # Loop through and update only if certificate is complete
    for case in cases:
        if case.certificate_status == 'Complete':
            case.ocme_status = 'Closed'
            updated_count += 1

    # Commit changes to the database
    db.session.commit()

    print(f"{updated_count} cases updated to 'Closed' status for primary_pathologist ID {target_id}.")

    return url_for("ame_dashboard.get_ame_dashboard")