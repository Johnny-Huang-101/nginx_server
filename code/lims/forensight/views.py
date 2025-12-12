# lims/forensight/views.py

from datetime import date, datetime

import sqlalchemy as sa
from flask import Blueprint, render_template, request as flask_request, redirect, url_for
from flask_login import login_required
from markupsafe import escape

from lims import db
from lims.forensight.forms import (
    ForenSightFilterForm,
    AUTOPSY_TYPE_CHOICES,
    MANNER_CHOICES,
    DISCIPLINE_CHOICES,
    RESULT_STATUS_CHOICES,
    CASE_STATUS_CHOICES,
)
from lims.models import (
    Cases,
    CaseTypes,
    Genders,
    Races,
    SpecimenTypes,
    DrugClasses,
    Components,
    DeathTypes,
    Zipcodes,
    Results,
    ReportResults,
)

import folium
from folium.plugins import MarkerCluster
from folium import Figure, IFrame
from flask import url_for

from collections import Counter
import plotly.graph_objs as go
import plotly.io as pio



forensight = Blueprint("forensight", __name__, template_folder="templates")


# ---------- helpers ----------

def _all_selected(choices):
    return [v for (v, _label) in choices]


def _created_col_fallback():
    """
    Choose a created/created_at/created_on column if it exists on Cases;
    fall back to fa_case_entry_date so the expression always resolves.
    """
    for col_name in ("created_at", "created_on", "create_date", "created"):
        if hasattr(Cases, col_name):
            return getattr(Cases, col_name)
    return Cases.fa_case_entry_date


def _format_name(first, middle, last):
    parts = []
    if last:
        parts.append(escape(last))
    if first or middle:
        if last:
            parts.append(", ")
        if first:
            parts.append(escape(first))
        if middle:
            parts.append(f" {escape(middle)}")
    return "".join(parts) if parts else "—"


def _case_url(case_id):
    """
    Build an absolute URL so it works inside the iframe popup.
    Adjust endpoint if needed.
    """
    try:
        return url_for("cases.view", case_id=case_id, )
    except Exception:
        base = flask_request.host_url.rstrip("/")
        return f"{base}/cases/{case_id}"


def _gender_color(g):
    g = (g or "").lower()
    if g.startswith("m"):
        return "blue"
    if g.startswith("f"):
        return "red"
    return "gray"


def _build_component_case_filter(selected_components, logic_op, reported_choice, selected_statuses):
    """
    Returns a subquery of case_ids that satisfy the component filters.

    selected_components: list[int]
    logic_op: "AND" or "OR"
    reported_choice: "Yes", "No", or ""
    selected_statuses: list[str] (used when reported_choice == "No")

    Semantics:
    - If no components: return None (no filter).
    - If reported_results == "Yes":
        Case must have Results with those components that are linked to ReportResults.
    - If reported_results == "No":
        Case must have Results with those components whose result_status is in selected_statuses
        (if any are specified).
    - AND: case must have ALL selected components.
    - OR: case must have at least one selected component.
    """
    if not selected_components:
        return None

    # Base: Results rows restricted by components, optionally by ReportResults or result_status
    if reported_choice == "Yes":
        # Only results that appear in report_results
        base = (
            db.session.query(
                Results.case_id.label("case_id"),
                Results.component_id.label("component_id"),
            )
            .join(ReportResults, ReportResults.result_id == Results.id)
            .filter(Results.component_id.in_(selected_components))
        )
    else:
        # Work directly off Results; restrict by status if explicitly using raw (No)
        base = (
            db.session.query(
                Results.case_id.label("case_id"),
                Results.component_id.label("component_id"),
            )
            .filter(Results.component_id.in_(selected_components))
        )
        if reported_choice == "No":
            # Only consider rows whose result_status matches selected_statuses (if any)
            if selected_statuses:
                base = base.filter(Results.result_status.in_(selected_statuses))
        # If reported_choice == "" we'll just treat as "any result with that component" (no extra filter)

    bs = base.subquery()

    # AND vs OR logic
    if logic_op == "AND" and len(selected_components) > 1:
        # Require at least one qualifying row for EACH selected component
        counts = (
            db.session.query(
                bs.c.case_id.label("case_id"),
                sa.func.count(sa.distinct(bs.c.component_id)).label("cnt"),
            )
            .group_by(bs.c.case_id)
            .subquery()
        )
        case_ids_q = db.session.query(counts.c.case_id).filter(
            counts.c.cnt >= len(selected_components)
        )
    else:
        # OR (or single component): at least one match is enough
        case_ids_q = db.session.query(sa.distinct(bs.c.case_id))

    return case_ids_q.subquery()

def _age_bucket(age):
    if age is None:
        return "Unknown"
    try:
        a = int(age)
    except(TypeError, ValueError):
        return "Unknown"
    if a < 15:
        return "0-14"
    elif a < 25:
        return "15-24"
    elif a < 35:
        return "25-34"
    elif a < 45:
        return "35-44"
    elif a < 55:
        return "45-54"
    elif a < 65:
        return "55-64"
    else:
        return ">= 65"
    
def _top8_with_all_others(counter: Counter):
    total = sum(counter.values())
    if total == 0:
        return [], []

    items = counter.most_common()
    top = items[:8]

    labels = [lbl for (lbl, _cnt) in top]
    counts = [cnt for (_lbl, cnt) in top]

    if len(items) > 8:
        other = total - sum(counts)
        if other > 0:
            labels.append("All others")
            counts.append(other)

    return labels, counts


# consistent palette, similar to your example
PIE_COLORS = [
    "#3366CC",  # blue
    "#FF9900",  # orange
    "#FFCC00",  # yellow
    "#AAAAAA",  # gray
    "#66A3E0",  # light blue
    "#109618",  # green
    "#DC3912",  # red
    "#990099",  # purple
    "#5C5C5C",  # reuse for "All others" or extra
]


def _make_pie_html(labels, counts, title):
    if not labels or not counts:
        return None

    total = float(sum(counts))
    if total <= 0:
        return None

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=counts,
                hole=0.3,                 # small center
                textinfo="percent",
                textposition="inside",     # keep labels inside to save space
                insidetextorientation="auto",
                hovertemplate="%{label}<br>%{percent:.1%}<extra></extra>",
                marker=dict(colors=PIE_COLORS[: len(labels)]),
            )
        ]
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", y=0.98),
        # Tight side margins so the pie can use the full width
        margin=dict(l=10, r=10, t=40, b=90),
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=-0.22,
            yanchor="top",
        ),
        height=520,   # <-- larger overall -> larger pie
    )

    return pio.to_html(fig, full_html=False, include_plotlyjs=False)


# ---------- route ----------

@forensight.route("/forensight", methods=["GET", "POST"])
@login_required
def filters_view():
    form = ForenSightFilterForm()

    # ----- static choices -----
    form.case_status.choices     = CASE_STATUS_CHOICES
    form.disciplines.choices     = DISCIPLINE_CHOICES
    form.result_status.choices   = RESULT_STATUS_CHOICES
    form.autopsy_type.choices    = AUTOPSY_TYPE_CHOICES
    form.manner_of_death.choices = MANNER_CHOICES

    # ----- dynamic: genders / races -----
    g_rows = db.session.query(Genders.id, Genders.name).order_by(Genders.name.asc()).all()
    r_rows = db.session.query(Races.id, Races.name).order_by(Races.name.asc()).all()
    form.genders.choices = [(gid, gname) for gid, gname in g_rows]
    form.races.choices   = [(rid, rname) for rid, rname in r_rows]

    # ----- dynamic: case types -----
    ct_rows = db.session.query(CaseTypes.id, CaseTypes.code).order_by(CaseTypes.code.asc()).all()
    form.case_types.choices = [(cid, code) for cid, code in ct_rows]

    # ----- dynamic: drug classes -----
    dc_rows = db.session.query(DrugClasses.id, DrugClasses.name).order_by(DrugClasses.name.asc()).all()
    form.drug_class.choices = [("", "— Select —")] + [(str(did), dname) for did, dname in dc_rows]

    # ----- dynamic: components (all; UI filters by drug class) -----
    comp_rows = (
        db.session.query(Components.id, Components.name, Components.drug_class_id)
        .order_by(Components.name.asc())
        .all()
    )
    form.components.choices = [(cid, cname) for (cid, cname, _dcid) in comp_rows]
    components_payload = [
        {"id": cid, "name": cname, "drug_class_id": (dcid if dcid is not None else None)}
        for (cid, cname, dcid) in comp_rows
    ]

    # ----- dynamic: death types -----
    dt_rows = db.session.query(DeathTypes.id, DeathTypes.name).order_by(DeathTypes.name.asc()).all()
    form.death_types.choices = [(did, dname) for did, dname in dt_rows]

    # ----- dynamic: zipcodes -----
    zips = db.session.query(Zipcodes.zipcode).order_by(Zipcodes.zipcode.asc()).all()
    zip_choices = [(z[0], z[0]) for z in zips]
    form.fixed_address_location.choices = zip_choices
    form.death_location.choices         = zip_choices

    # ----- dynamic: specimen types -----
    st_rows = (
        db.session.query(SpecimenTypes.id, SpecimenTypes.name, SpecimenTypes.discipline)
        .order_by(SpecimenTypes.name.asc())
        .all()
    )
    specimen_types_payload = [
        {"id": sid, "name": sname, "disciplines": (sdisc or "")}
        for (sid, sname, sdisc) in st_rows
    ]
    form.specimen_types.choices = [(sid, sname) for (sid, sname, _disc) in st_rows]

    # ================== defaults on GET ==================
    if flask_request.method == "GET":
        form.from_date.data = date(2025, 1, 1)
        form.to_date.data   = date.today()

        form.case_status.data = ["Closed"]

        form.genders.data = [gid for (gid, _n) in form.genders.choices]
        form.races.data   = [rid for (rid, _n) in form.races.choices]

        form.case_types.data      = [cid for (cid, _c) in form.case_types.choices]
        form.disciplines.data     = _all_selected(DISCIPLINE_CHOICES)
        form.specimen_types.data  = [sid for (sid, _n) in form.specimen_types.choices]
        form.components.data      = []            # user picks; nothing pre-selected
        form.component_logic.data = "OR"          # default when it appears

        form.reported_results.data = "Yes"        # default to reported-only
        form.result_status.data    = []           # JS disables until NO is chosen

        form.autopsy_type.data    = _all_selected(AUTOPSY_TYPE_CHOICES)
        form.death_types.data     = [did for (did, _n) in form.death_types.choices]
        form.manner_of_death.data = _all_selected(MANNER_CHOICES)

        form.fixed_address.data            = "Yes"
        form.fixed_address_location.data   = [z for (z, _l) in zip_choices]
        form.death_location.data           = [z for (z, _l) in zip_choices]

    # Reset
    if form.clear.data and form.validate_on_submit():
        return redirect(url_for("forensight.filters_view"))

    # ================== outputs ==================
    cases    = []   # all filtered cases (for charts later)
    pm_cases = []   # PM-only subset (for map)
    map_html = None
    gender_pie_html = race_pie_html = age_pie_html = deathloc_pie_html = None
    # ================== POST / APPLY ==================
    if form.validate_on_submit() and form.submit.data:
        # ---- shared filters ----
        from_dt = form.from_date.data
        to_dt   = form.to_date.data
        if to_dt:
            to_dt = datetime.combine(to_dt, datetime.max.time())

        selected_gender_ids   = form.genders.data or []
        selected_autopsy      = form.autopsy_type.data or []
        selected_death_types  = form.death_types.data or []
        selected_mods         = form.manner_of_death.data or []
        selected_death_zips   = form.death_location.data or []

        selected_components   = form.components.data or []          # [int]
        component_logic       = (form.component_logic.data or "OR").upper()
        reported_choice       = (form.reported_results.data or "").strip()
        selected_statuses     = form.result_status.data or []

        created_col     = _created_col_fallback()
        index_date_expr = sa.case(
            (CaseTypes.code == "PM", Cases.fa_case_entry_date),
            else_=created_col,
        )

        # ---- base: all cases (for future charts) ----
        q_all = (
            db.session.query(
                Cases.id,
                Cases.case_number,
                Cases.first_name,
                Cases.middle_name,
                Cases.last_name,
                Cases.latitude,
                Cases.longitude,
                Cases.age_years,
                Cases.death_zip,
                Genders.name.label("gender_name"),
                Races.name.label("race_name"),
                CaseTypes.code.label("case_type_code"),
                index_date_expr.label("index_date"),
            )
            .outerjoin(CaseTypes, CaseTypes.id == Cases.case_type)
            .outerjoin(Genders, Genders.id == Cases.gender_id)
            .outerjoin(Races, Races.id == Cases.race_id)
        )

        if from_dt:
            q_all = q_all.filter(index_date_expr >= from_dt)
        if to_dt:
            q_all = q_all.filter(index_date_expr <= to_dt)
        if selected_gender_ids:
            q_all = q_all.filter(Cases.gender_id.in_(selected_gender_ids))

        # ---- PM map base (PM-only; PM-specific filters) ----
        q_pm = (
            db.session.query(
                Cases.id,
                Cases.case_number,
                Cases.first_name,
                Cases.middle_name,
                Cases.last_name,
                Cases.cod_a,
                Cases.manner_of_death,
                Cases.latitude,
                Cases.longitude,
                Genders.name.label("gender"),
                CaseTypes.code.label("case_type_code"),
                Cases.fa_case_entry_date.label("pm_index_date"),
                Cases.death_type_id.label("death_type_id"),
                Cases.death_zip.label("death_zip"),
            )
            .join(CaseTypes, CaseTypes.id == Cases.case_type)
            .outerjoin(Genders, Genders.id == Cases.gender_id)
            .filter(CaseTypes.code == "PM")
            .filter(Cases.fa_case_entry_date.isnot(None))
            .filter(Cases.latitude.isnot(None), Cases.longitude.isnot(None))
        )

        if from_dt:
            q_pm = q_pm.filter(Cases.fa_case_entry_date >= from_dt)
        if to_dt:
            q_pm = q_pm.filter(Cases.fa_case_entry_date <= to_dt)
        if selected_gender_ids:
            q_pm = q_pm.filter(Cases.gender_id.in_(selected_gender_ids))

        # PM-only filters (autopsy type, death type, manner, death address)
        if selected_autopsy:
            q_pm = q_pm.filter(Cases.autopsy_type.in_(selected_autopsy))
        if selected_death_types:
            q_pm = q_pm.filter(Cases.death_type_id.in_(selected_death_types))
        if selected_mods:
            q_pm = q_pm.filter(Cases.manner_of_death.in_(selected_mods))
        if selected_death_zips:
            q_pm = q_pm.filter(Cases.death_zip.in_(selected_death_zips))

        # ---- Component-based case filter (applies to ALL cases; PM map is subset) ----
        comp_case_ids_subq = _build_component_case_filter(
            selected_components=selected_components,
            logic_op=component_logic,
            reported_choice=reported_choice,
            selected_statuses=selected_statuses,
        )

        if comp_case_ids_subq is not None:
            q_all = q_all.filter(Cases.id.in_(comp_case_ids_subq))
            q_pm  = q_pm.filter(Cases.id.in_(comp_case_ids_subq))

        # ---- finalize all-cases dataset ----
        rows_all = q_all.order_by(index_date_expr.asc()).all()
        cases = [
            {
                "id": r.id,
                "case_number": r.case_number,
                "first_name": r.first_name,
                "middle_name": r.middle_name,
                "last_name": r.last_name,
                "gender": r.gender_name or "Unknown",
                "race": r.race_name or "Unknown",
                "case_type_code": r.case_type_code or "",
                "index_date": r.index_date,
                "lat": r.latitude,
                "lon": r.longitude,
                "age_years": r.age_years,
                "death_zip": r.death_zip,
            }
            for r in rows_all
        ]

        # ---- finalize PM-only dataset for map ----
        rows_pm = q_pm.order_by(Cases.fa_case_entry_date.asc()).all()
        pm_cases = [
            {
                "id": r.id,
                "case_number": r.case_number,
                "first_name": r.first_name,
                "middle_name": r.middle_name,
                "last_name": r.last_name,
                "cod_a": r.cod_a,
                "manner_of_death": r.manner_of_death,
                "lat": r.latitude,
                "lon": r.longitude,
                "gender": r.gender or "Unknown",
                "case_type_code": r.case_type_code or "",
                "index_date": r.pm_index_date,
                "death_zip": r.death_zip,
                "death_type_id": r.death_type_id,
            }
            for r in rows_pm
        ]

        # ---- build PM-only map (if any) ----
        if pm_cases:
            center = (37.7749, -122.4194)  # SF
            fig = Figure(width="100%", height="800px")  # taller map
            fmap = folium.Map(
                location=center,
                zoom_start=12,
                tiles="CartoDB positron",
                control_scale=True,
            )
            fmap.add_to(fig)
            mc = MarkerCluster().add_to(fmap)

            for c in pm_cases:
                date_txt = (
                    c["index_date"].strftime("%Y-%m-%d %H:%M")
                    if c["index_date"]
                    else "—"
                )
                name_txt = _format_name(
                    c.get("first_name"),
                    c.get("middle_name"),
                    c.get("last_name"),
                )
                case_label = (
                    escape(c["case_number"])
                    if c["case_number"]
                    else str(c["id"])
                )
                href = _case_url(c["id"])
                cod_a_txt = escape(c.get("cod_a") or "—")
                mod_txt = escape(c.get("manner_of_death") or "—")

                html = f"""
                <div style="min-width: 360px; line-height:1.4;">
                  <div><b>Case (PM):</b>
                    <a href="{href}" target="_blank" rel="noopener">{case_label}</a>
                  </div>
                  <div><b>Name:</b> {name_txt}</div>
                  <div><b>COD (A):</b> {cod_a_txt}</div>
                  <div><b>Manner of Death:</b> {mod_txt}</div>
                  <div><b>Date:</b> {escape(date_txt)}</div>
                </div>
                """

                iframe = IFrame(html=html, width=420, height=160)
                popup = folium.Popup(iframe, max_width=480)

                folium.CircleMarker(
                    location=(c["lat"], c["lon"]),
                    radius=6,
                    color=_gender_color(c["gender"]),
                    fill=True,
                    fill_opacity=0.85,
                    popup=popup,
                ).add_to(mc)

            map_html = fig.render()
        else:
            map_html = None

        gender_pie_html = race_pie_html = age_pie_html = deathloc_pie_html = None

        if cases:
            # ---- Gender ----
            g_counter = Counter()
            for c in cases:
                lbl = c.get("gender") or "Unknown"
                g_counter[lbl] += 1
            g_labels, g_counts = _top8_with_all_others(g_counter)
            gender_pie_html = _make_pie_html(g_labels, g_counts, "Gender")

            # ---- Race ----
            # We don't currently store race name in cases; you can:
            # 1) join Races in q_all, or
            # 2) treat missing as Unknown.
            # Assuming you adjust q_all to include Races.name.label("race_name"):
            #   add Cases.race_id join and store in cases.
            # For now, I'll assume you did that and stored "race" in cases.
            r_counter = Counter()
            for c in cases:
                lbl = c.get("race") or "Unknown"
                r_counter[lbl] += 1
            r_labels, r_counts = _top8_with_all_others(r_counter)
            race_pie_html = _make_pie_html(r_labels, r_counts, "Race")

            # ---- Age ----
            a_counter = Counter()
            for c in cases:
                bucket = _age_bucket(c.get("age_years"))
                a_counter[bucket] += 1
            a_labels, a_counts = _top8_with_all_others(a_counter)
            age_pie_html = _make_pie_html(a_labels, a_counts, "Age")

            # ---- Death Location (by death_zip) ----
            d_counter = Counter()
            for c in cases:
                dz = c.get("death_zip")
                lbl = (dz or "").strip() or "Unknown"
                d_counter[lbl] += 1
            d_labels, d_counts = _top8_with_all_others(d_counter)
            deathloc_pie_html = _make_pie_html(d_labels, d_counts, "Death Location (Zip)")

    # ================== render ==================
    return render_template(
        "forensight/view.html",
        form=form,
        specimen_types_payload=specimen_types_payload,
        components_payload=components_payload,
        cases=cases,
        pm_cases=pm_cases,
        map_html=map_html,
        gender_pie_html=gender_pie_html,
        race_pie_html=race_pie_html,
        age_pie_html=age_pie_html,
        deathloc_pie_html=deathloc_pie_html,
    )