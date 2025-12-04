from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from datetime import datetime, time, timedelta
import statistics

import plotly.graph_objects as go
import plotly.io as pio

# Models
from lims.models import Users, Cases

from sqlalchemy import or_, func

inv_dashboard = Blueprint('inv_dashboard', __name__, template_folder='templates')

# ---------- Plot helpers ----------
def _static_pie(labels, values):
    color_map = {
        'Scene arrival': '#007bff',
        'Identification': '#28a745',
        'Next Of Kin': '#ffc107',
        'Closed': '#6c757d',
    }
    colors = [color_map.get(lbl, '#999999') for lbl in labels]
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        textinfo='percent',
        hovertemplate='%{label}: %{value} (%{percent})<extra></extra>',
        marker=dict(colors=colors),
        hole=0.3
    )])
    fig.update_layout(
        width=350, height=350,
        margin=dict(t=20, b=20, l=20, r=20),
        showlegend=True,
        legend=dict(orientation='h', yanchor='top', y=-0.15, x=0.5, xanchor='center')
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def _empty_box():
    fig = go.Figure()
    fig.update_layout(
        xaxis_title='Days Open',
        margin=dict(t=30, l=40, r=30, b=40),
        height=400, width=1200,
        showlegend=False
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)

def _empty_tat_graph():
    fig = go.Figure()
    for name in ['15 Days', '30 Days', '45 Days', '60 Days', '90 Days', 'Still Open %']:
        fig.add_trace(go.Scatter(x=[], y=[], mode='lines+markers', name=name))
    fig.update_layout(
        xaxis_title='Month', yaxis_title='%',
        yaxis=dict(range=[0, 110]),
        height=500, width=1200,
        margin=dict(t=30, b=40, l=40, r=30),
    )
    return fig.to_html(full_html=False)

# ---------- Formatting helpers ----------
def _fmt_hm(td: timedelta) -> str:
    """Hh Mm (Scene arrival)."""
    total_minutes = int(td.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m"

def _fmt_dh(td: timedelta) -> str:
    """Dd Hh (Identification, NOK, Closed)."""
    total_hours = int(td.total_seconds() // 3600)
    days = total_hours // 24
    hours = total_hours % 24
    return f"{days}d {hours}h"

def _parse_nok_dt(nok_date, nok_time_str):
    """Combine nok_notify_date (date/datetime) + nok_notify_time ('HHMM' or 'HMM') into a datetime."""
    if not nok_date or not nok_time_str:
        return None
    s = nok_time_str.strip()
    if not s.isdigit():
        return None
    if len(s) == 3:
        hh = int(s[0])
        mm = int(s[1:3])
    else:
        s = s.zfill(4)[:4]
        hh = int(s[:2])
        mm = int(s[2:])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    base_date = nok_date.date() if hasattr(nok_date, "date") else nok_date
    return datetime.combine(base_date, time(hh, mm))

# ---------- Route ----------
@inv_dashboard.route('/inv_dashboard', methods=['GET', 'POST'])
@login_required
def get_inv_dashboard():
    selected_year_str = request.args.get('year')
    # default to current year if not explicitly chosen
    current_year = datetime.now().year
    year_for_filter = int(selected_year_str) if selected_year_str else current_year
    year_start = datetime(year_for_filter, 1, 1)
    year_end = datetime(year_for_filter + 1, 1, 1)  # exclusive

    # Interval param for 12h/1d/2d/5d/10d
    interval = (request.args.get('interval') or '1').strip()
    if interval == '12h':
        threshold_days = 0.5  # 12 hours
    else:
        try:
            threshold_days = float(int(interval))
        except (TypeError, ValueError):
            threshold_days = 1.0

    # ----- Build dropdown list: ONLY INV users -----
    inv_users = (Users.query
                      .filter(Users.permissions == 'INV')
                      .order_by(Users.full_name.asc())
                      .all())
    inv_user_ids = {str(u.id) for u in inv_users}

    # ----- Selection logic -----
    user_id_arg = (request.args.get('user_id') or '').strip()
    current_is_inv = str(current_user.id) in inv_user_ids

    if not user_id_arg:
        selected_inv_user_id = str(current_user.id) if current_is_inv else 'all'
    elif user_id_arg == 'all':
        selected_inv_user_id = 'all'
    elif user_id_arg in inv_user_ids:
        selected_inv_user_id = user_id_arg
    else:
        selected_inv_user_id = str(current_user.id) if current_is_inv else 'all'

    # ===== Scope cases by primary_investigator ↔ Users.personnel_id =====
    inv_personnel_ids = [u.personnel_id for u in inv_users if u.personnel_id is not None]

    selected_user_personnel_id = None
    if selected_inv_user_id != 'all':
        for u in inv_users:
            if str(u.id) == selected_inv_user_id:
                selected_user_personnel_id = u.personnel_id
                break

    if selected_user_personnel_id:
        cases_scope_q = Cases.query.filter(Cases.primary_investigator == selected_user_personnel_id)
    else:
        if inv_personnel_ids:
            cases_scope_q = Cases.query.filter(Cases.primary_investigator.in_(inv_personnel_ids))
        else:
            cases_scope_q = Cases.query.filter(Cases.id == -1)  # empty

    # Exclude case numbers that start with "NC-" (case/space insensitive)
    cases_scope_q = cases_scope_q.filter(
        or_(
            Cases.case_number.is_(None),
            ~func.trim(Cases.case_number).ilike('nc-%')
        )
    )


    # Pull ALL case objects (tables need many fields)
    cases = cases_scope_q.all()

    now = datetime.now()

    # ---- Counters for left/right (split by fa_case_entry_date age) ----
    left_scene_open = right_scene_open = 0
    left_ident_open = right_ident_open = 0
    left_nok_open = right_nok_open = 0
    left_closed = right_closed = 0

    # TAT lists for MEANS
    tat_scene_left, tat_scene_right = [], []
    tat_ident_left, tat_ident_right = [], []
    tat_nok_left, tat_nok_right = [], []
    tat_closed_left, tat_closed_right = [], []

    # ---- Tables buckets (ALL limited to current/selected year) ----
    scene_arrival_cases = []             # open scene (year-limited)
    identification_cases_le = []         # open ident, ≤ interval, year-limited
    identification_cases_gt = []         # open ident, > interval, year-limited
    next_of_kin_cases_le = []            # (excluded logic may make these empty)
    next_of_kin_cases_gt = []            # (excluded logic may make these empty)
    closed_cases_le = []                 # closed, ≤ interval, year-limited
    closed_cases_current_year = []       # closed with fa_inv_end_datetime within year window

    for case in cases:
        atype = (case.autopsy_type or '').strip().lower()
        exclude_atype = atype in ('indigent', 'administrative review')
        inv_start = case.fa_inv_start_datetime
        scene_dept = case.fa_scene_dept_datetime
        ident_dt   = case.fa_ident_datetime
        inv_end    = case.fa_inv_end_datetime
        entry      = case.fa_case_entry_date

        # Must have entry date and be within the year window for counts/tables
        if not entry or not (year_start <= entry < year_end):
            continue

        age_days = (now - entry).total_seconds() / 86400.0
        is_left = age_days <= threshold_days

        # ---------- Scene arrival ----------
        if not exclude_atype:
            if scene_dept is None:
                # OPEN (counts + table)
                if is_left:
                    left_scene_open += 1
                else:
                    right_scene_open += 1
                scene_arrival_cases.append(case)
            else:
                # CLOSED → TAT = scene_dept - inv_start
                if inv_start:
                    td = scene_dept - inv_start
                    if td.total_seconds() >= 0:
                        (tat_scene_left if is_left else tat_scene_right).append(td)

        # ---------- Identification ----------
        if not exclude_atype:
            if ident_dt is None:
                if is_left:
                    left_ident_open += 1
                    identification_cases_le.append(case)
                else:
                    right_ident_open += 1
                    identification_cases_gt.append(case)
            else:
                if inv_start:
                    td = ident_dt - inv_start
                    if td.total_seconds() >= 0:
                        (tat_ident_left if is_left else tat_ident_right).append(td)

        # ---------- Next Of Kin (EXCLUDE certain cases) ----------
        # Exclude: autopsy_type in {"Indigent","Administrative"} (case-insensitive) OR missing date/time
        exclude_nok = (
            atype in ('indigent', 'administrative') or
            case.nok_notify_date is None or
            not case.nok_notify_time
        )

        if not exclude_nok:
            nok_dt = _parse_nok_dt(case.nok_notify_date, case.nok_notify_time)
            if nok_dt is None:
                # malformed time -> exclude entirely
                pass
            else:
                # NOK is considered CLOSED when both date+time exist
                if inv_start:
                    td = nok_dt - inv_start
                    if td.total_seconds() >= 0:
                        (tat_nok_left if is_left else tat_nok_right).append(td)
                # We no longer treat missing NOK date/time as "open"; excluded entirely.

        # ---------- Closed ----------
        if inv_start and inv_end:
            if is_left:
                left_closed += 1
                closed_cases_le.append(case)
            else:
                right_closed += 1
            td = inv_end - inv_start
            if td.total_seconds() >= 0:
                (tat_closed_left if is_left else tat_closed_right).append(td)
            # Closed in current (or selected) year?
            if year_start <= inv_end < year_end:
                closed_cases_current_year.append(case)

        case.nok_dt = _parse_nok_dt(case.nok_notify_date, case.nok_notify_time)  # transient attribute
        if case.nok_dt and case.fa_inv_start_datetime:
            secs = (case.nok_dt - case.fa_inv_start_datetime).total_seconds()
            if secs >= 0:
                total_hours = int(secs // 3600)
                d, h = divmod(total_hours, 24)
                case.nok_from_inv_dh = f"{d}d {h}h"
            else:
                case.nok_from_inv_dh = '—'
        else:
            case.nok_from_inv_dh = ''

    # Compute MEAN TATs and format
    def _mean_fmt(tats, mode='dh'):
        if not tats:
            return "-"
        mean_seconds = statistics.mean([td.total_seconds() for td in tats])
        td = timedelta(seconds=mean_seconds)
        return _fmt_hm(td) if mode == 'hm' else _fmt_dh(td)

    left_scene_closed_tat  = _mean_fmt(tat_scene_left, mode='hm')
    right_scene_closed_tat = _mean_fmt(tat_scene_right, mode='hm')

    left_ident_closed_tat  = _mean_fmt(tat_ident_left, mode='dh')
    right_ident_closed_tat = _mean_fmt(tat_ident_right, mode='dh')

    left_nok_closed_tat    = _mean_fmt(tat_nok_left, mode='dh')
    right_nok_closed_tat   = _mean_fmt(tat_nok_right, mode='dh')

    # NEW: Closed TATs to display in boxes
    left_closed_tat   = _mean_fmt(tat_closed_left, mode='dh')
    right_closed_tat  = _mean_fmt(tat_closed_right, mode='dh')

    # Totals (Closed included; NOK "open" is intentionally always 0 due to exclusion)
    left_total_count  = left_scene_open + left_ident_open + left_nok_open + left_closed
    right_total_count = right_scene_open + right_ident_open + right_nok_open + right_closed
    overall_total_count = left_total_count + right_total_count

    # Pies (right excludes Closed)
    pie_chart_left = _static_pie(
        labels=['Scene arrival', 'Identification', 'Next Of Kin', 'Closed'],
        values=[left_scene_open, left_ident_open, left_nok_open, left_closed]
    )
    pie_chart_right = _static_pie(
        labels=['Scene arrival', 'Identification', 'Next Of Kin'],
        values=[right_scene_open, right_ident_open, right_nok_open]
    )

    # Chart placeholders (kept for layout parity)
    box_plot_left  = _empty_box()
    box_plot_right = _empty_box()
    tat_graph = _empty_tat_graph() if selected_year_str else None

    return render_template(
        'inv_dashboard/inv_dashboard.html',
        # filters
        inv_users=inv_users,
        selected_inv_user_id=selected_inv_user_id,
        interval=interval,
        threshold_days=threshold_days,
        year=selected_year_str,

        # charts
        pie_chart_left=pie_chart_left,
        pie_chart_right=pie_chart_right,
        box_plot_left=box_plot_left,
        box_plot_right=box_plot_right,
        tat_graph=tat_graph,

        # counts (left / ≤ interval)
        left_scene_arrival_count=left_scene_open,
        left_identification_count=left_ident_open,
        left_next_of_kin_count=left_nok_open,   # likely 0 due to exclusion rule
        left_closed_count=left_closed,
        left_total_count=left_total_count,

        # counts (right / > interval)
        right_scene_arrival_count=right_scene_open,
        right_identification_count=right_ident_open,
        right_next_of_kin_count=right_nok_open, # likely 0 due to exclusion rule
        right_closed_count=right_closed,        # not in right pie
        right_total_count=right_total_count,

        # overall
        overall_total_count=overall_total_count,

        # per-section CLOSED counts + mean TAT text
        left_scene_arrival_closed_count=len(tat_scene_left),
        left_scene_arrival_tat=left_scene_closed_tat,
        left_identification_closed_count=len(tat_ident_left),
        left_identification_tat=left_ident_closed_tat,
        left_next_of_kin_closed_count=len(tat_nok_left),
        left_next_of_kin_tat=left_nok_closed_tat,

        right_scene_arrival_closed_count=len(tat_scene_right),
        right_scene_arrival_tat=right_scene_closed_tat,
        right_identification_closed_count=len(tat_ident_right),
        right_identification_tat=right_ident_closed_tat,
        right_next_of_kin_closed_count=len(tat_nok_right),
        right_next_of_kin_tat=right_nok_closed_tat,

        # NEW: closed TATs for boxes
        left_closed_tat=left_closed_tat,
        right_closed_tat=right_closed_tat,

        # tables (all current-year limited)
        scene_arrival_cases=scene_arrival_cases,
        identification_cases_le=identification_cases_le,
        identification_cases_gt=identification_cases_gt,
        next_of_kin_cases_le=next_of_kin_cases_le,
        next_of_kin_cases_gt=next_of_kin_cases_gt,
        closed_cases_le=closed_cases_le,
        closed_cases_current_year=closed_cases_current_year,

        # misc
        datetime=datetime,
        current_user=current_user,
        year_start=year_start, year_end=year_end
    )
