from flask import request, Blueprint, render_template, jsonify
from flask_login import login_required, current_user
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from lims.dashboard.forms import CaseFilter
from lims.models import *
from lims.drug_prevalence.forms import DrugFilter
import folium
import pandas as pd
from lims import db
from folium.plugins import MarkerCluster
import numpy as np
import sqlalchemy as sa
from sqlalchemy import func, distinct
from sqlalchemy.dialects.postgresql import array_agg
from datetime import datetime
import json
import os
from sqlalchemy.sql import text

from jinja2 import Template
# Set item variables

drug_prevalence = Blueprint('drug_prevalence', __name__)
@drug_prevalence.route(f'/drug_prevalence', methods=['GET', 'POST'])
@login_required
def get_drug_prevalence():
    px.colors.qualitative.__dict__.keys()
    form = DrugFilter()

    # -------------------- Color palettes --------------------
    palette_muted = [
        "#4878A8","#D58E6D","#6CA27C","#C26565","#9E8DB2",
        "#A38C6D","#CF93B2","#8E8E8E","#B5B867","#6DBFC2",
    ]
    palette_blues = ["#08306B","#08519C","#2171B5","#4292C6","#6BAED6","#9ECAE1","#C6DBEF","#DEEBF7","#F7FBFF","#E0F3F8"]
    palette_greens = ["#00441B","#006D2C","#238B45","#41AE76","#66C2A4","#99D8C9","#CCECE6","#E5F5F9","#F7FCFD","#B2DFDB"]
    palette_grays  = ["#252525","#525252","#737373","#969696","#BDBDBD","#D9D9D9","#F0F0F0","#CCCCCC","#999999","#666666"]
    palette_cool   = ["#1b9e77","#66c2a5","#a6d854","#8da0cb","#e78ac3","#a6cee3","#b2df8a","#fb9a99","#fdbf6f","#cab2d6"]

    palette_selection = form.color_palette.data or 'muted'
    palette_map = {'muted': palette_muted,'blues': palette_blues,'greens': palette_greens,'grays': palette_grays,'cool': palette_cool}
    palette_colors = palette_map.get(palette_selection, palette_muted)

    # Populate specimen type choices for the UI (AJAX will refine)
    form.specimen_type.choices = [
        (str(s.id), f'[{s.code}] {s.name}') for s in SpecimenTypes.query.order_by(SpecimenTypes.name).all()
    ]

    # -------------------- Date field & choices --------------------
    date_format = '%b-%Y'
    date_field_map = {
        'Date of Incident': Cases.date_of_incident,
        'Turn Around Time': Cases.tat_start_date,
        'FA Entry': Cases.fa_case_entry_date,
        'LIMS Create Date': Cases.create_date
    }
    form.component_id.choices = [(item.id, item.name) for item in Components.query.order_by(Components.name)]
    form.case_type.choices    = [(item.id, item.code) for item in CaseTypes.query.order_by(CaseTypes.accession_level)]
    form.date_type.choices    = [('Date of Incident','Date of Incident'),('Turn Around Time','Turn Around time'),('FA Entry','FA Entry'),('LIMS Create Date','LIMS Create Date')]
    form.drug_class.choices   = [(0,'All')] + [(dc.id, dc.name) for dc in DrugClasses.query.order_by(DrugClasses.name)]

    # Case type lookup (id -> "code - name")
    case_types_df = pd.DataFrame([ct.__dict__ for ct in CaseTypes.query.order_by(CaseTypes.code.asc())])
    case_type_dict = dict(zip(case_types_df['id'], case_types_df['code'].astype(str) + " - " + case_types_df['name'].astype(str)))

    counts_pivot_dict, cols = {}, []
    fig = None
    component_name = None

    # -------------------- Resolve POST vs GET defaults --------------------
    if request.method == 'POST':
        selected_field_label  = form.date_type.data
        selected_date_field   = date_field_map[selected_field_label]
        selected_date_labeled = selected_date_field.label('selected_date')
        start_date = form.start_date.data
        end_date   = form.end_date.data
        selected_case_types = form.case_type.data or []
        if form.date_by.data == 'Year':
            date_format = '%Y'

        # Base cases query (by the chosen date field + optional case type filter)
        cases_q = (
            db.session.query(
                Cases.id,
                Cases.case_number,
                selected_date_labeled,
                (CaseTypes.code + ' - ' + CaseTypes.name).label('case_type'),
                Cases.manner_of_death,
                Cases.cod_a,
                Cases.fa_case_comments
            )
            .join(CaseTypes, Cases.case_type == CaseTypes.id)
            .filter(
                selected_date_field.isnot(None),
                selected_date_field >= start_date,
                selected_date_field <= end_date,
                *([Cases.case_type.in_(selected_case_types)] if selected_case_types else [])
            )
        )

        # Component label for header
        component_ids = form.component_id.data or []
        logic_operator = (form.and_or.data or '').strip().upper()
        if len(component_ids) == 1:
            c = Components.query.get(component_ids[0])
            component_name = c.name if c else "Unknown Component"
        elif len(component_ids) > 1:
            comps = Components.query.filter(Components.id.in_(component_ids)).order_by(Components.name).all()
            joiner = f' {logic_operator} ' if logic_operator in ('AND','OR') else ' '
            component_name = joiner.join([c.name for c in comps])
        else:
            component_name = "No Component Selected"

    else:
        selected_field_label = 'Date of Incident'
        form.date_type.data  = selected_field_label
        selected_date_field   = date_field_map[selected_field_label]
        start_date = datetime(datetime.today().year, 1, 1)
        end_date   = datetime.today()
        selected_case_types = []
        ethanol = Components.query.filter(Components.name == 'Ethanol').first()
        if ethanol:
            form.component_id.data = [ethanol.id]
            component_name = ethanol.name
        else:
            component_name = 'Unknown'

        cases_q = (
            db.session.query(
                Cases.id,
                Cases.case_number,
                Cases.date_of_incident.label('selected_date'),
                (CaseTypes.code + ' - ' + CaseTypes.name).label('case_type'),
                Cases.manner_of_death,
                Cases.cod_a,
                Cases.fa_case_comments
            )
            .join(CaseTypes, Cases.case_type == CaseTypes.id)
            .filter(
                Cases.date_of_incident.isnot(None),
                Cases.date_of_incident >= start_date,
                Cases.date_of_incident <= end_date
            )
        )

    # -------------------- Build a DataFrame of cases in date window --------------------
    cases_df = pd.DataFrame(
        cases_q.all(),
        columns=['id','case_number','selected_date','case_type','manner_of_death','cod_a','fa_case_comments']
    )
    if not cases_df.empty:
        cases_df['case_type_name'] = cases_df['case_type'].replace(case_type_dict)
        cases_df['selected_date']  = pd.to_datetime(cases_df['selected_date'], errors='coerce')
        if form.date_by.data == 'Quarter':
            cases_df['Date'] = cases_df['selected_date'].dt.to_period('Q').apply(lambda q: f"Quarter {q.quarter} {q.year}")
        else:
            cases_df['Date'] = cases_df['selected_date'].dt.strftime(date_format)
    else:
        cases_df = pd.DataFrame(columns=['id','case_number','selected_date','case_type','manner_of_death','cod_a','fa_case_comments','case_type_name','Date'])

    # -------------------- Pull qualifying Results baseline from DB (avoid giant IN) --------------------
    selected_components_raw = form.component_id.data or []
    selected_components = [int(x) for x in selected_components_raw]
    logic_operator = (form.and_or.data or '').strip().upper()

    # Resolve the *names* for the selected component ids
    selected_component_names = []
    if selected_components:
        selected_component_names = [
            name for (name,) in db.session.query(Components.name)
            .filter(Components.id.in_(selected_components)).distinct()
        ]


    if str(form.reported_only.data).strip().lower() == 'yes':
        base_q = (
            db.session.query(
                Results.case_id.label('case_id'),
                Results.component_name.label('component_name')
            )
            .join(ReportResults, ReportResults.result_id == Results.id)   # <— requires a reported row
            .join(Tests, Results.test_id == Tests.id)
            .join(Assays, Tests.assay_id == Assays.id)
            .join(Cases, Results.case_id == Cases.id)
            .filter(
                Assays.discipline == form.discipline.data,
                date_field_map[selected_field_label].isnot(None),
                date_field_map[selected_field_label] >= start_date,
                date_field_map[selected_field_label] <= end_date,
            )
        )
    else:
        # Raw-results path (no ReportResults requirement)
        statuses = form.result_status.data or []
        status_filter = []
        if statuses:
            status_filter.append(
                sa.func.lower(sa.func.coalesce(Results.result_status, '')).in_([s.lower() for s in statuses])
            )
        base_q = (
            db.session.query(
                Results.case_id.label('case_id'),
                Results.component_name.label('component_name')
            )
            .join(Tests, Results.test_id == Tests.id)
            .join(Assays, Tests.assay_id == Assays.id)
            .join(Cases, Results.case_id == Cases.id)
            .filter(
                Results.result != 'ND',
                Assays.discipline == form.discipline.data,
                date_field_map[selected_field_label].isnot(None),
                date_field_map[selected_field_label] >= start_date,
                date_field_map[selected_field_label] <= end_date,
                *status_filter
            )
        )

    # Constrain by selected components — by *name*, not id
    if selected_component_names:
        base_q = base_q.filter(Results.component_name.in_(selected_component_names))

    # Build matching cases: AND means a case must have ALL selected component names; else ANY
    if selected_component_names and logic_operator == 'AND' and len(selected_component_names) > 1:
        matching_cases_subq = (
            base_q.group_by(Results.case_id)
                .having(sa.func.count(sa.func.distinct(Results.component_name)) == len(selected_component_names))
                .with_entities(Results.case_id.label('case_id'))
                .subquery()
        )
    else:
        matching_cases_subq = (
            base_q.with_entities(Results.case_id.label('case_id'))
                .distinct()
                .subquery()
        )

    # Restrict cases_df to only those that actually match (JOIN not big IN)
    if not cases_df.empty:
        # fetch valid IDs via join
        valid_cases_ids = [cid for (cid,) in db.session.query(matching_cases_subq.c.case_id).all()]
        cases_df = cases_df[cases_df['id'].isin(valid_cases_ids)]
    else:
        valid_cases_ids = []

    # -------------------- Build "results" frame aligned to the surviving cases --------------------
    # one row per case for graphs/tables
    if not cases_df.empty:
        results_df = cases_df[['id','case_number','case_type_name','Date']].copy()
        results_df.rename(columns={'id':'case_id'}, inplace=True)
    else:
        results_df = pd.DataFrame(columns=['case_id','case_number','case_type_name','Date'])

    # -------------------- Case Type graph: count each case ONCE per Date×CaseType; zero-fill months --------------------
    df_cases = results_df.drop_duplicates(subset=['case_id'])
    counts = (df_cases.groupby(['Date','case_type_name'], sort=False)['case_id']
                     .nunique().reset_index())
    counts.columns = ['Date','Case Type','Cases']

    # Build full time axis for zero-filled months/quarters
    if form.date_by.data == 'Quarter':
        periods = pd.period_range(start=start_date, end=end_date, freq='Q')
        time_axis = pd.DataFrame({
            'Date': [f"Quarter {p.quarter} {p.year}" for p in periods],
            'SortKey': pd.to_datetime([f"{p.year}-{(p.quarter-1)*3+1:02}-01" for p in periods])
        })
    else:
        periods = pd.period_range(start=start_date, end=end_date, freq='M')
        time_axis = pd.DataFrame({
            'Date': [p.to_timestamp().strftime('%b-%Y') for p in periods],
            'SortKey': periods.to_timestamp()
        })

    case_type_names = sorted(counts['Case Type'].unique().tolist()) if not counts.empty else []
    if not case_type_names:
        # fallback so chart renders; use known case types
        case_type_names = sorted(list(set(case_type_dict.values())))

    full_index = pd.MultiIndex.from_product([time_axis['Date'], case_type_names], names=['Date','Case Type'])
    counts_full = counts.set_index(['Date','Case Type']).reindex(full_index).reset_index()
    counts_full['Cases'] = counts_full['Cases'].fillna(0).astype(int)
    counts_full = counts_full.merge(time_axis, on='Date', how='left').sort_values('SortKey')

    color_dict = dict(zip(case_type_names, palette_colors[:len(case_type_names)]))

    fig = px.bar(
        counts_full, x='Date', y='Cases', color='Case Type',
        height=650, hover_data={'Date': False},
        color_discrete_map=color_dict,
        category_orders={'Date': time_axis['Date'].tolist(), 'Case Type': case_type_names}
    )
    fig.update_traces(texttemplate='%{y}', textposition='inside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', hovermode='x unified', height=600, width=1300)
    fig.update_traces(hovertemplate='%{y}')

    totals_full = counts_full.groupby(['Date','SortKey'], as_index=False)['Cases'].sum()
    fig.add_trace(go.Scatter(
        x=totals_full['Date'], y=totals_full['Cases'],
        mode='text', text=totals_full['Cases'], textposition='top center',
        name='Cases', textfont=dict(color='blue'), showlegend=False
    ))

    # Summary table (keep zero months)
    counts_pivot = counts_full.pivot_table(index='Date', values='Cases', columns='Case Type', fill_value=0)
    order_map = dict(zip(time_axis['Date'], time_axis['SortKey']))
    counts_pivot['order'] = counts_pivot.index.map(order_map)
    counts_pivot.sort_values('order', inplace=True)
    counts_pivot.drop(columns=['order'], inplace=True)
    counts_pivot.insert(0, 'Cases', counts_pivot.sum(axis=1))
    cols = counts_pivot.columns

    totals  = counts_pivot.sum()
    averages = counts_pivot.mean().round(1)
    medians  = counts_pivot.median()
    mins     = counts_pivot.min()
    maxs     = counts_pivot.max()

    counts_pivot.loc['Total',  :] = totals
    counts_pivot.loc['Average',:] = averages
    counts_pivot.loc['Median', :] = medians
    counts_pivot.loc['Min',    :] = mins
    counts_pivot.loc['Max',    :] = maxs
    counts_pivot = counts_pivot.fillna(0).astype(int, errors='ignore')
    counts_pivot_dict = counts_pivot.to_dict(orient='index')

    fig_html = fig.to_html() if fig else "<h1>No results to show.</h1>"
    print(f"{current_user.initials} opened Drug Prevalence")

    # =============================================================================
    # CONCENTRATION CHARTS: one per selected component
    # =============================================================================
    fig_conc_html = ""

    # Build the unified time axis (used to show missing months as gaps)
    if form.date_by.data == 'Quarter':
        _periods = pd.period_range(start=start_date, end=end_date, freq='Q')
        _time_axis = pd.DataFrame({
            'Date': [f"Quarter {p.quarter} {p.year}" for p in _periods],
            'SortKey': pd.to_datetime([f"{p.year}-{(p.quarter-1)*3+1:02}-01" for p in _periods]),
        })
    else:
        _periods = pd.period_range(start=start_date, end=end_date, freq='M')
        _time_axis = pd.DataFrame({
            'Date': [p.to_timestamp().strftime('%b-%Y') for p in _periods],
            'SortKey': _periods.to_timestamp(),
        })

    # Normalize selected components
    _raw = form.component_id.data
    if isinstance(_raw, (list, tuple, set)):
        _selected_components = [int(x) for x in _raw if x not in (None, "", "None")]
    else:
        _selected_components = [int(_raw)] if _raw not in (None, "", "None") else []

    if not _selected_components:
        fig_conc_html = "<p style='color:#888'>Select at least one component to see Average/Median concentration by month.</p>"
    else:
        per_component_figs = []

        for comp_id in _selected_components:
            # Always have a dataframe defined
            _df = pd.DataFrame()

            # Component info for the chart title
            _comp_obj  = Components.query.get(comp_id)
            _comp_name = _comp_obj.name if _comp_obj else f"Component {comp_id}"

            if str(form.reported_only.data).strip().lower() == 'yes':
                # Reported-only: pull multiple possible numeric sources (primary/observed/raw)
                _rows = (
                    db.session.query(
                        ReportResults.primary_result.label('primary_result'),
                        ReportResults.observed_result.label('observed_result'),
                        ReportResults.qualitative_result.label('qualitative_result'),
                        Results.concentration.label('raw_concentration'),
                        Results.unit_id.label('unit_id'),
                        selected_date_field.label('selected_date'),
                    )
                    .join(Results, ReportResults.result_id == Results.id)
                    .join(Tests, Results.test_id == Tests.id)
                    .join(Assays, Tests.assay_id == Assays.id)
                    .join(Cases, Results.case_id == Cases.id)
                    .filter(
                        Results.component_id == comp_id,
                        Assays.discipline == form.discipline.data,
                        selected_date_field.isnot(None),
                        selected_date_field >= start_date,
                        selected_date_field <= end_date,
                        sa.or_(
                            ReportResults.primary_result.isnot(None),
                            ReportResults.observed_result.isnot(None),
                            ReportResults.qualitative_result.isnot(None),
                        ),
                    )
                ).all()

                _df = pd.DataFrame(
                    _rows,
                    columns=[
                        'primary_result',
                        'observed_result',
                        'qualitative_result',
                        'raw_concentration',
                        'unit_id',
                        'selected_date',
                    ],
                )

                # Coerce a single numeric "concentration" column
                import re
                _num_re = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

                def _to_float(x):
                    try:
                        if x is None or (isinstance(x, float) and np.isnan(x)):
                            return np.nan
                        if isinstance(x, str):
                            m = _num_re.search(x.replace(',', ''))
                            return float(m.group()) if m else np.nan
                        return float(x)
                    except Exception:
                        return np.nan

                _df['primary_num']  = _df['primary_result'].apply(_to_float)
                _df['observed_num'] = _df['observed_result'].apply(_to_float)
                _df['raw_num']      = _df['raw_concentration'].apply(_to_float)

                # priority: primary_num → raw_num → observed_num
                _df['concentration'] = _df['primary_num']
                _df.loc[_df['concentration'].isna(), 'concentration'] = _df['raw_num']
                _df.loc[_df['concentration'].isna(), 'concentration'] = _df['observed_num']

                _df = _df[['concentration', 'unit_id', 'selected_date']]

            else:
                # Raw results path: use Results.concentration, filter by result_status (if given)
                statuses = form.result_status.data or []
                base_filters = [
                    Results.component_id == comp_id,
                    Assays.discipline == form.discipline.data,
                    selected_date_field.isnot(None),
                    selected_date_field >= start_date,
                    selected_date_field <= end_date,
                    Results.result != 'ND',
                ]
                if statuses:
                    base_filters.append(
                        sa.func.lower(sa.func.coalesce(Results.result_status, '')).in_(
                            [s.lower() for s in statuses]
                        )
                    )

                _rows = (
                    db.session.query(
                        Results.concentration.label('concentration'),
                        Results.unit_id.label('unit_id'),
                        selected_date_field.label('selected_date'),
                    )
                    .join(Tests, Results.test_id == Tests.id)
                    .join(Assays, Tests.assay_id == Assays.id)
                    .join(Cases, Results.case_id == Cases.id)
                    .filter(*base_filters)
                ).all()

                _df = pd.DataFrame(_rows, columns=['concentration', 'unit_id', 'selected_date'])

            # ---- No data after filters? ----
            if _df.empty:
                per_component_figs.append(
                    f"<p style='color:#888'>No numeric concentrations found in the selected window for <b>{_comp_name}</b>.</p>"
                )
                continue

            # Clean + keep numeric concentrations and valid dates
            _df['concentration'] = pd.to_numeric(_df['concentration'], errors='coerce')
            _df['selected_date'] = pd.to_datetime(_df['selected_date'], errors='coerce')
            _df = _df[_df['concentration'].notna() & _df['selected_date'].notna()].copy()

            if _df.empty:
                per_component_figs.append(
                    f"<p style='color:#888'>No numeric concentrations found in the selected window for <b>{_comp_name}</b>.</p>"
                )
                continue

            # Bucket to month/quarter label (we’ll reindex to the full axis for proper order)
            if form.date_by.data == 'Quarter':
                _df['Date'] = _df['selected_date'].dt.to_period('Q').apply(lambda q: f"Quarter {q.quarter} {q.year}")
            else:
                _df['Date'] = _df['selected_date'].dt.strftime('%b-%Y')

            # Aggregate Average/Median per bucket
            _monthly = (
                _df.groupby('Date')['concentration']
                .agg(Average='mean', Median='median')
                .reset_index()
            )

            # Reindex to the unified time axis (keep SortKey) and zero-fill missing months
            _monthly = (
                _time_axis[['Date','SortKey']]
                .merge(_monthly, on='Date', how='left')
                .sort_values('SortKey')
                .assign(
                    Average=lambda d: pd.to_numeric(d['Average'], errors='coerce').fillna(0),
                    Median =lambda d: pd.to_numeric(d['Median'],  errors='coerce').fillna(0),
                )
                .reset_index(drop=True)
            )

            # Y-axis label from first available unit_id
            _y_axis_label = 'Concentration'
            try:
                if _df['unit_id'].notna().any():
                    _u_id  = _df['unit_id'].dropna().iloc[0]
                    _u_obj = Units.query.get(int(_u_id)) if _u_id is not None else None
                    if _u_obj and getattr(_u_obj, 'name', None):
                        _y_axis_label = f'Concentration ({_u_obj.name})'
            except Exception:
                pass

            # Plot: Average (solid) + Median (dashed) with gaps for missing months
            _fig_conc = go.Figure()
            _fig_conc.add_trace(go.Scatter(
                x=_monthly['Date'],
                y=_monthly['Average'],
                mode='lines+markers',
                name='Average Concentration',
                connectgaps=False,
            ))
            _fig_conc.add_trace(go.Scatter(
                x=_monthly['Date'],
                y=_monthly['Median'],
                mode='lines+markers',
                name='Median Concentration',
                line=dict(dash='dash'),
                connectgaps=False,
            ))
            _fig_conc.update_layout(
                title=f'Average and Median Concentration by Month — {_comp_name}',
                xaxis_title='Month' if form.date_by.data != 'Quarter' else 'Quarter',
                yaxis_title=_y_axis_label,
                hovermode='x unified',
                width=1000,
                height=460,
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                xaxis=dict(categoryorder='array', categoryarray=_time_axis['Date'].tolist()),
            )
            per_component_figs.append(_fig_conc.to_html())


        # Combine all component figures (keep them stacked)
        fig_conc_html = "\n".join(per_component_figs) if per_component_figs else "<p style='color:#888'>No concentration charts to display.</p>"
    # =============================================================================
    # END Concentration charts
    # =============================================================================
    # TAB SHOULD BE HERE
    # -------------------- Specimen Type graph (ONLY results for selected components, ONLY in the qualifying cases) --------------------
    selected_specimen_ids = list(map(int, form.specimen_type.data)) if form.specimen_type.data else []
    fig_specimen_html = "<p>No specimen type results after AND/OR filtering.</p>"

    if len(selected_components) > 0 and len(valid_cases_ids) > 0:
        spec_q = (
            db.session.query(
                Results.id.label('result_id'),
                Results.case_id.label('case_id'),
                selected_date_field.label('selected_date'),
                SpecimenTypes.code.label('spec_code'),
                SpecimenTypes.name.label('spec_name')
            )
            .join(Results.test)
            .join(Tests.assay)
            .join(Tests.specimen)
            .join(Specimens.type)
            .join(Results.case)
            .filter(
                Assays.discipline == form.discipline.data,
                selected_date_field.isnot(None),
                selected_date_field >= start_date,
                selected_date_field <= end_date,
                Results.case_id.in_(valid_cases_ids),          # <- only cases used in case graph
                Results.component_id.in_(selected_components), # <- only selected components
                Results.db_status != 'Removed'
            )
        )
        if form.reported_only.data == 'Yes':
            spec_q = spec_q.join(ReportResults, ReportResults.result_id == Results.id).filter(
                sa.or_(
                    ReportResults.primary_result.isnot(None),
                    ReportResults.observed_result.isnot(None),
                    ReportResults.qualitative_result.isnot(None)
                )
            )
        if selected_specimen_ids:
            spec_q = spec_q.filter(SpecimenTypes.id.in_(selected_specimen_ids))

        spec_rows = spec_q.all()
        if spec_rows:
            df_spec = pd.DataFrame(spec_rows, columns=['result_id','case_id','selected_date','spec_code','spec_name'])
            df_spec['selected_date'] = pd.to_datetime(df_spec['selected_date'], errors='coerce')

            if form.date_by.data == 'Quarter':
                df_spec['Date'] = df_spec['selected_date'].dt.to_period('Q').apply(lambda q: f"Quarter {q.quarter} {q.year}")
                periods = pd.period_range(start=start_date, end=end_date, freq='Q')
                time_axis_spec = pd.DataFrame({
                    'Date': [f"Quarter {p.quarter} {p.year}" for p in periods],
                    'SortKey': pd.to_datetime([f"{p.year}-{(p.quarter-1)*3+1:02}-01" for p in periods]),
                })
            else:
                df_spec['Date'] = df_spec['selected_date'].dt.strftime('%b-%Y')
                periods = pd.period_range(start=start_date, end=end_date, freq='M')
                time_axis_spec = pd.DataFrame({
                    'Date': [p.to_timestamp().strftime('%b-%Y') for p in periods],
                    'SortKey': periods.to_timestamp(),
                })

            df_spec['Specimen Type'] = '[' + df_spec['spec_code'] + '] ' + df_spec['spec_name']

            counts_spec = df_spec.groupby(['Date','Specimen Type'], as_index=False)['result_id'].size()
            counts_spec.rename(columns={'size':'Results'}, inplace=True)

            spec_types = sorted(counts_spec['Specimen Type'].unique().tolist())
            if spec_types:
                full_idx = pd.MultiIndex.from_product([time_axis_spec['Date'], spec_types], names=['Date','Specimen Type'])
                counts_spec_full = counts_spec.set_index(['Date','Specimen Type']).reindex(full_idx).reset_index()
                counts_spec_full['Results'] = counts_spec_full['Results'].fillna(0).astype(int)
                counts_spec_full = counts_spec_full.merge(time_axis_spec, on='Date', how='left').sort_values('SortKey')

                fig_spec = px.bar(
                    counts_spec_full, x='Date', y='Results', color='Specimen Type',
                    height=650, title='Results Count by Specimen Type',
                    color_discrete_sequence=palette_colors,
                    category_orders={'Date': time_axis_spec['Date'].tolist(), 'Specimen Type': spec_types}
                )
                fig_spec.update_traces(texttemplate='%{y}', textposition='inside')
                fig_spec.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', hovermode='x unified', width=1300)

                totals_per_date = counts_spec_full.groupby(['Date','SortKey'], as_index=False)['Results'].sum()
                fig_spec.add_trace(go.Scatter(
                    x=totals_per_date['Date'], y=totals_per_date['Results'],
                    mode='text', text=totals_per_date['Results'],
                    textposition='top center', textfont=dict(color='black', size=12),
                    name='Total Results', showlegend=False
                ))

                fig_specimen_html = fig_spec.to_html()

    # -------------------- Cases table: use EXACT cases from case graph --------------------
    _case_ids_for_table = df_cases['case_id'].unique().tolist() if not df_cases.empty else []
    cases_for_table = []
    if _case_ids_for_table:
        cases_for_table = (
            db.session.query(
                Cases.id.label('id'),
                Cases.case_number.label('case_number'),
                selected_date_field.label('selected_date'),
                (CaseTypes.code + ' - ' + CaseTypes.name).label('case_type'),
                Cases.manner_of_death.label('manner_of_death'),
                Cases.cod_a.label('cod_a'),
                Cases.fa_case_comments.label('fa_case_comments'),
            )
            .join(CaseTypes, Cases.case_type == CaseTypes.id)
            .filter(Cases.id.in_(_case_ids_for_table))
            .order_by(selected_date_field.desc())
            .all()
        )

    return render_template(
        'drug_prevalence.html',
        form=form,
        component_name=component_name,
        drug_prevalence_html=fig_html,
        cases=cases_for_table,                 # <- strictly the same cases the graph used
        counts_pivot_dict=counts_pivot_dict,
        cols=cols,
        selected_field_label=selected_field_label,
        fig_conc_html=fig_conc_html,
        fig_specimen_html=fig_specimen_html
    )



@drug_prevalence.route('/drug_prevalence/get_specimen_types', methods=['POST', 'GET'])
@login_required
def get_specimen_types():
    discipline = request.json.get('discipline')
    print("Discipline received from frontend:", discipline)

    specimen_types = SpecimenTypes.query.filter_by(discipline=discipline).order_by(SpecimenTypes.name).all()
    print("Filtered specimen types:", [(s.id, s.name) for s in specimen_types])

    return jsonify([
        {'id': s.id, 'name': f'[{s.code}] {s.name}'} for s in specimen_types
    ])


@drug_prevalence.route('/drug_prevalence/get_components', methods=['POST'])
@login_required
def get_components():
    drug_class_id = request.json.get('drug_class_id')
    if drug_class_id is None or int(drug_class_id) == 0:
        components = Components.query.order_by(Components.name).all()
    else:
        components = Components.query.filter_by(drug_class_id=int(drug_class_id)).order_by(Components.name).all()
    
    return jsonify([{'id': c.id, 'name': c.name} for c in components])
