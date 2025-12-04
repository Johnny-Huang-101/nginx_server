from flask import request, Blueprint, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import Bar, Figure
from plotly.subplots import make_subplots
from lims.dashboard.forms import CaseFilter, SpecialProjectForm
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

from lims.dashboard.functions import convert_to_quarter, get_pending_tests, get_case_statuses
from jinja2 import Template
# Set item variables

dashboard = Blueprint('dashboard', __name__)
conn = db.engine.connect().connection

sort_dict = {'Submitted': '1',
             'Testing': '2',
             'Drafting': '3',
             'CR1': '4',
             'CR2': '5',
             'DR': '6',
             }

@dashboard.route(f'/dashboard', methods=['GET', 'POST'])
@login_required
def get_dashboard():
    # To redirect to home page while dashboard is being worked on

    disciplines = ['toxicology', 'biochemistry', 'histology']

    cases = Cases.query.all()

    for case in cases:
        updated = False  # track if we need to commit this case

        for discipline in disciplines:
            start_attr = f"{discipline}_start_date"
            end_attr = f"{discipline}_end_date"
            tat_attr = f"{discipline}_tat"
            status_attr = f"{discipline}_status"

            start_date = getattr(case, start_attr, None)
            end_date = getattr(case, end_attr, None)

            # If both start and end dates exist, calculate TAT
            if start_date and end_date:
                tat = (end_date - start_date).days
                setattr(case, tat_attr, tat)
                updated = True

                # Get all tests linked to this case
                tests = Tests.query.filter_by(case_id=case.id).all()

                # Check if all tests are either Finalized or Cancelled
                if all(test.test_status in ['Finalized', 'Cancelled'] for test in tests):
                    setattr(case, status_attr, 'Disseminated')
                    updated = True

        if updated:
            db.session.add(case)

    db.session.commit()


    db.session.commit()

    current_user.dashboard_discipline = 'Toxicology'
    db.session.commit()

    start = datetime.now()

    form = CaseFilter()
    end_date = datetime.today()
    # start_date = datetime(2021, 1, 1)
    start_date = datetime.today()-dt.timedelta(days=365)
    date_by = 'Month'
    selected_traces = [15, 30, 45, 60, 90]
    form.case_type.choices = [(item.id, item.code) for item in CaseTypes.query.order_by(CaseTypes.accession_level)]
    case_type_str = 'All'

    # Write logic for case discipline here
    # check for discipline by tests (need some sort of array since it can be multiple disciplines)
    # make an if statment where IF someone tries to make user dashboard_discipline to something without cases
        # it will error out, put them at toxicology, and alert them that discipline has no cases
    # query so it just pulls cases that have tests with that discipline
    # the error logic for discipline choice should be when a discipline is selected

    discipline = current_user.dashboard_discipline
    
    start_date_col = getattr(Cases, f"{discipline.lower()}_start_date")
    tat_col = f"{discipline.lower()}_turn_around_time"

    testing_cases = Cases.query.join(Tests).join(Assays).filter(
        Cases.case_status == 'Testing',
        start_date_col >= start_date,
        start_date_col <= end_date
    ).all()
    testing_case_count = len(testing_cases)

    # Query for drafting cases within the date range and the current discipline
    drafting_cases = Cases.query.join(Tests).join(Assays).filter(
        Cases.case_status == 'Drafting',
        start_date_col >= start_date,
        start_date_col <= end_date
    ).all()
    drafting_case_count = len(drafting_cases)

    # Query for CR1 cases within the date range and the current discipline
    cr_one_cases = Cases.query.join(Tests).join(Assays).filter(
        Cases.case_status == 'CR1',
        start_date_col >= start_date,
        start_date_col <= end_date
    ).all()
    cr_one_case_count = len(cr_one_cases)

    # Query for CR2 cases within the date range and the current discipline
    cr_two_cases = Cases.query.join(Tests).join(Assays).filter(
        Cases.case_status == 'CR2',
        start_date_col >= start_date,
        start_date_col <= end_date
    ).all()
    cr_two_case_count = len(cr_two_cases)

    # Query for CR cases within the date range and the current discipline
    cr_cases = Reports.query.filter(
        Reports.report_status == 'Ready for CR',
        Reports.discipline == discipline
    ).all()
    cr_cases_count = len(cr_cases)

    # Query for DR cases within the date range and the current discipline
    dr_cases = Reports.query.filter_by(report_status='Ready for DR').filter(Reports.discipline == discipline, Reports.db_status == 'Active').all()
    dr_case_count = len(dr_cases)

# Get the dynamically-named discipline_status column from the Cases model
    discipline_status_col = getattr(Cases, f"{discipline.lower()}_status", None)

    # Count how many cases have "Ready for Drafting" for that discipline
    ready_for_drafting_count = 0
    testing_status_count = 0
    if discipline_status_col is not None:
        ready_for_drafting_count = Cases.query.filter(discipline_status_col == 'Ready for Drafting').count()
        testing_status_count = Cases.query.filter(discipline_status_col == 'Testing', Cases.db_status == 'Active').count()
        testing_case_count = testing_status_count
        drafting_case_count = ready_for_drafting_count
    report_status_counts = {


        'Ready for DR': Reports.query.filter_by(report_status='Ready for DR').filter(Reports.discipline == discipline, Reports.db_status == 'Active').count(),
        'Ready for CR': Reports.query.filter_by(report_status='Ready for CR').filter(Reports.discipline == discipline, Reports.db_status == 'Active').count(),
        'Ready for Drafting': ready_for_drafting_count
    }
    dr_case_count = report_status_counts['Ready for DR']
    report_status_fig = go.Figure(data=[
        Bar(
            x=list(report_status_counts.values()),
            y=list(report_status_counts.keys()),
            orientation='h',
            text=list(report_status_counts.values()),
            textposition='auto',
            marker_color='#cc5500'
        )
    ])
    report_status_fig.update_layout(
        xaxis_title="Reports",
        yaxis_title="Status",
        height=500,
        margin=dict(l=150, r=20, t=30, b=30),
    )
    report_status_graph = report_status_fig.to_html(full_html=False, config={"displayModeBar": False})

    testing_fig = go.Figure(data=[
    Bar(
        x=[testing_status_count],
        y=['Testing'],
        orientation='h',
        text=[testing_status_count],
        textposition='auto',
        marker_color='steelblue'
    )
    ])
    testing_fig.update_layout(
        xaxis_title="Cases",
        yaxis_title="Status",
        height=200,
        margin=dict(l=150, r=20, t=30, b=30),
    )
    testing_status_graph = testing_fig.to_html(full_html=False, config={"displayModeBar": False})

    # testing_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'Testing',
    #     Assays.discipline == discipline
    # ).all()
    # testing_case_count = len(testing_cases)
    #
    # drafting_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'Drafting',
    #     Assays.discipline == discipline
    # ).all()
    # drafting_case_count = len(drafting_cases)
    #
    # cr_one_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'CR1',
    #     Assays.discipline == discipline
    # ).all()
    # cr_one_case_count = len(cr_one_cases)
    #
    # cr_two_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'CR2',
    #     Assays.discipline == discipline
    # ).all()
    # cr_two_case_count = len(cr_two_cases)
    #
    # cr_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'CR',
    #     Assays.discipline == discipline
    # ).all()
    # cr_cases_count = len(cr_cases)
    #
    # dr_cases = Cases.query.join(Tests).join(Assays).filter(
    #     Cases.case_status == 'DR',
    #     Assays.discipline == discipline
    # ).all()
    # dr_case_count = len(dr_cases)
    special_projects = SpecialProjects.query.all()
    # Tally Board

    pending_dict = get_pending_tests(Tests, Assays)

    # Get case type dictionary

    case_types = pd.DataFrame([item.__dict__ for item in CaseTypes.query.order_by(CaseTypes.code.asc())])
    case_type_dict = dict(
        zip(
            case_types['id'], case_types['code'].astype(str) + " - " + case_types['name'].astype(str)
        )
    )

    # Create color dictionary for figures
    color_dict = dict(zip(case_types['code'].astype(str) + " - " + case_types['name'].astype(str),
                          px.colors.qualitative.Prism))

    if request.method == 'GET':
        query = Cases.query.outerjoin(Tests).outerjoin(Assays).filter(sa.and_(
            start_date_col >= start_date,
            start_date_col <= end_date))
        #     Assays.discipline == discipline  # Filter by the current user's discipline
        # ))

    # elif request.method == 'POST':
    #     start_date = form.start_date.data
    #     end_date = form.end_date.data
    #     # selected_traces = form.tat_traces.data
    #     date_by = form.date_by.data
    #
    #     # if len(form.tat_traces.data) == 0:
    #     #     selected_traces = [x[0] for x in form.tat_traces.choices]
    #
    #     if len(form.case_type.data) == 0:
    #         query = db.session.query(Cases).filter(sa.and_(
    #             start_date_col >= start_date,
    #             start_date_col <= end_date
    #         ))
    #     else:
    #         query = db.session.query(Cases).filter(sa.and_(
    #             start_date_col >= start_date,
    #             start_date_col <= end_date,
    #             Cases.case_type.in_(form.case_type.data)
    #         ))
    #         case_types_lst = [dict(form.case_type.choices).get(x) for x in form.case_type.data]
    #         case_type_str = ", ".join(case_types_lst)

    if request.method == 'POST':
        start_date = form.start_date.data
        end_date = form.end_date.data
        date_by = form.date_by.data
        selected_case_types = form.case_type.data
        case_type_condition = True if not selected_case_types else Cases.case_type.in_(selected_case_types)

        testing_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'Testing',
            Assays.discipline == discipline,

        ).all()
        testing_case_count = len(testing_cases)

        # Query for drafting cases within the date range and the current discipline
        drafting_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'Drafting',
            Assays.discipline == discipline,
        ).all()
        drafting_case_count = len(drafting_cases)

        # Query for CR1 cases within the date range and the current discipline
        cr_one_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR1',
            Assays.discipline == discipline,
        ).all()
        cr_one_case_count = len(cr_one_cases)

        # Query for CR2 cases within the date range and the current discipline
        cr_two_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR2',
            Assays.discipline == discipline,
        ).all()
        cr_two_case_count = len(cr_two_cases)

        # Query for CR cases within the date range and the current discipline
        cr_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR',
            Assays.discipline == discipline,
        ).all()
        cr_cases_count = len(cr_cases)

        # Query for DR cases within the date range and the current discipline
        dr_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'DR',
            Assays.discipline == discipline,

        ).all()
        dr_case_count = len(dr_cases)

        if len(form.case_type.data) == 0:
            query = Cases.query.outerjoin(Tests).outerjoin(Assays).filter(sa.and_(
                # Assays.discipline == discipline,  # Add discipline filter
            ))
            query_two = Cases.query.outerjoin(Tests).outerjoin(Assays).filter(sa.and_(
                Assays.discipline == discipline
            ))
        else:
            query = Cases.query.join(Tests).join(Assays).filter(sa.and_(
                start_date_col >= start_date,
                start_date_col <= end_date,
                Cases.case_type.in_(form.case_type.data),
                # Assays.discipline == discipline  # Add discipline filter
            ))
            case_types_lst = [dict(form.case_type.choices).get(x) for x in form.case_type.data]
            case_type_str = ", ".join(case_types_lst)

    # Only add discipline filter when there are tests in the database
    if query.count():
        query.filter(Assays.discipline == discipline)

    cases = pd.DataFrame([item.__dict__ for item in query])
    cases['case_type_name'] = cases['case_type'].replace(case_type_dict)

    case_statuses, status_counts = get_case_statuses(cases, sort_dict)
    static_case_statuses = db.session.query(
        Cases.case_status, Cases.case_type, func.count(Cases.id).label("Cases")
    ).join(Tests).join(Assays).filter(
        Assays.discipline == discipline  # Only filtering by discipline, no date filter
    ).group_by(Cases.case_status, Cases.case_type).all()
    cases = cases[~cases[f'{discipline.lower()}_start_date'].isna()]

    if date_by in ['Month', 'Quarter']:
        format_str = '%b-%y'
    elif date_by == 'Year':
        format_str = '%Y'
    cases['Date'] = cases[f'{discipline.lower()}_start_date'].dt.strftime(format_str)
    if date_by == 'Quarter':
        cases['Date'] = cases['Date'].map(lambda x: convert_to_quarter(x))
        format_str = 'Q%m-%y'
    cases['case_type_name'] = cases['case_type'].replace(case_type_dict)
    cases['turn_around_time'] = cases['turn_around_time'].map(lambda x: 0 if not x else x)
    cases['turn_around_time'] = cases['turn_around_time'].fillna(0)
    #closed_cases = cases[(~cases['case_close_date'].isna())]
    closed_cases = cases[cases['case_status'] == 'T1 Complete']
    # print(closed_cases['turn_around_time'])
    open_cases = cases[~cases['case_number'].isin(closed_cases['case_number'])]
    closed_cases = closed_cases[closed_cases['turn_around_time'].astype(int) > 0]
    closed_cases.sort_values(by=[f'{discipline.lower()}_start_date'], inplace=True)
    #open_cases = cases[cases['case_close_date'].isna()]
    #open_cases['case_type_name'] = open_cases['case_type'].replace(case_type_dict)
    submitted = cases['Date'].value_counts(sort=False)
    closed = closed_cases['Date'].value_counts(sort=False)
    closed.name = 'Closed'
    no_closed = [x for x in submitted.index if x not in closed.index]
    for x in no_closed:
        closed[x] = 0

    opened = open_cases['Date'].value_counts()
    opened.name = 'Open'

    closed_cases.loc[:, 'turn_around_time'] = closed_cases['turn_around_time'].astype(int)

    avg_tat = closed_cases.groupby('Date', sort=False).mean()['turn_around_time'].astype(int)
    avg_tat.name = "Avg TAT"
    median_tat = closed_cases.groupby('Date', sort=False).median()['turn_around_time'].astype(int)
    median_tat.name = 'Median TAT'

    open_closed = pd.DataFrame()
    open_closed.index = submitted.index
    open_closed = pd.concat([closed, opened], axis=1)

    counts = pd.DataFrame()
    counts.index = submitted.index

    open_counts = pd.DataFrame()
    open_counts.index = submitted.index
    open_counts = pd.concat([open_counts, open_cases['Date'].value_counts()], axis=1)
    open_counts.reset_index(inplace=True)
    open_counts.columns = ['Date', 'Cases']

    open_case_types = pd.DataFrame()
    #open_case_types.index = submitted.index

    submitted_case_types = pd.DataFrame()
    submitted_case_types.index = submitted.index
    submitted_case_types = pd.concat([submitted_case_types, submitted], axis=1)
    submitted_case_types.columns = ['Submitted']


    for x in selected_traces:
        df = closed_cases[closed_cases['turn_around_time'] < x]
        df_counts = df['Date'].value_counts(sort=False)
        df_counts.name = x
        counts = pd.concat([counts, df_counts], axis=1)
        counts[x] = counts[x].replace(np.nan, 0)
        counts[x] = counts[x].astype(int)

    counts.index.name = 'Date'
    counts.reset_index(inplace=True)
    counts = counts.replace(np.nan, 0)
    counts_melt = counts.melt(id_vars='Date', var_name='Days', value_name='Cases')
    counts_melt['Cases'] = counts_melt['Cases'].replace(np.nan, 0)
    counts_melt['Submitted'] = counts_melt['Date'].replace(submitted)
    counts_melt['Closed'] = counts_melt['Date'].replace(closed)
    counts_melt['%'] = round(counts_melt['Cases'] / counts_melt['Date'].replace(closed) * 100, 1)
    counts_melt['Year'] = pd.to_datetime(counts_melt['Date'], format=format_str).dt.year
    counts_melt['Month'] = pd.to_datetime(counts['Date'], format=format_str).dt.month
    counts_melt.sort_values(by=['Year', 'Month', 'Days'], inplace=True)

    open_closed.index.name = 'Date'
    open_closed.reset_index(inplace=True)
    open_closed = open_closed.replace(np.nan, 0)
    open_closed_melt = open_closed.melt(id_vars='Date', var_name='Status', value_name='Cases')
    open_closed_melt['Cases'] = open_closed_melt['Cases'].replace(np.nan, 0)
    open_closed_melt['Submitted'] = open_closed_melt['Date'].replace(submitted)
    open_closed_melt['Year'] = pd.to_datetime(open_closed_melt['Date'], format=format_str).dt.year
    open_closed_melt['Month'] = pd.to_datetime(open_closed_melt['Date'], format=format_str).dt.month
    open_closed_melt.sort_values(by=['Year', 'Month','Status'], inplace=True)

    counts.set_index('Date', inplace=True)
    counts = pd.concat([submitted, opened, closed, avg_tat, median_tat, counts], axis=1)

    counts.columns = ['Submitted', 'Open', 'Closed', 'Avg TAT', 'Median TAT', '<15', '<30', '<45', '<60', '<90']
    counts['<15 (%)'] = round(counts['<15']/counts['Closed']*100, 1)
    counts['<30 (%)'] = round(counts['<30'] / counts['Closed'] * 100, 1)
    counts['<45 (%)'] = round(counts['<45'] / counts['Closed'] * 100, 1)
    counts['<60 (%)'] = round(counts['<60'] / counts['Closed'] * 100, 1)
    counts['<90 (%)'] = round(counts['<90'] / counts['Closed'] * 100, 1)
    if len(counts) > 1:
        totals = counts.sum()
        average = counts.mean().round(1)
        median = counts.median().round(1)
        max = counts.max()
        min = counts.min()
        counts.loc['Total',:] = totals
        counts.loc['Average',:] = average
        counts.loc['Median', :] = median
        counts.loc['Min', :] = min
        counts.loc['Max', : ] = max

    counts.replace(np.nan, 0, inplace=True)
    counts = counts.astype({'Submitted': int,
                            'Open': int,
                            'Closed': int,
                            'Avg TAT': int,
                            'Median TAT': int,
                            '<15': int,
                            '<30': int,
                            '<45': int,
                            '<60': int,
                            '<90': int,})


    avg_tat = avg_tat.reset_index()
    avg_tat.columns = ['Date', 'Avg TAT']

    median_tat = median_tat.reset_index()
    median_tat.columns = ['Date', 'Median TAT']

    # totals = pd.DataFrame()
    # totals['Total'] = counts.sum().astype(int)
    # totals['Average'] = counts.mean().astype(int)


    counts_dict = counts.to_dict(orient='index')
    #totals_dict = totals.to_dict()


    for case_type, df in open_cases.groupby('case_type_name'):
        case_type_counts = df['Date'].value_counts()
        case_type_counts = case_type_counts.reset_index()
        case_type_counts.columns = ['Date', 'Cases']
        case_type_counts['Case Type'] = case_type
        #case_type_counts.name = case_type
        #open_case_types = pd.concat([open_case_types, case_type_counts], axis=1)
        open_case_types = pd.concat([open_case_types, case_type_counts])


    #open_case_types.index.name = 'Date'
    #open_case_types.reset_index(inplace=True)

    if len(open_case_types) > 0:
        open_case_types = open_case_types.replace(np.nan, 0)
        open_case_types['Submitted'] = open_case_types['Date'].replace(submitted)
        open_case_types['Year'] = pd.to_datetime(open_case_types['Date'], format=format_str).dt.year
        open_case_types['Month'] = pd.to_datetime(open_case_types['Date'], format=format_str).dt.month
        open_case_types.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)
        # open_case_types_melt = open_case_types.melt(id_vars='Date', var_name='Case Type', value_name='Cases')
        # open_case_types_melt['Cases'] = open_case_types_melt['Cases'].replace(np.nan, 0)
        # open_case_types_melt['Submitted'] =open_case_types_melt['Date'].replace(submitted)
        # open_case_types_melt['Year'] = pd.to_datetime(open_case_types_melt['Date'], format=format_str).dt.year
        # open_case_types_melt['Month'] = pd.to_datetime(open_case_types_melt['Date'], format=format_str).dt.month
        # open_case_types_melt.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)


    for case_type, df in cases.groupby('case_type_name'):
        case_type_counts = df['Date'].value_counts()
        case_type_counts.name = case_type
        submitted_case_types = pd.concat([submitted_case_types, case_type_counts], axis=1)

    submitted_case_types.index.name = 'Date'
    submitted_case_types.reset_index(inplace=True)
    submitted_case_types = submitted_case_types.replace(np.nan, 0)
    submitted_case_types_melt = submitted_case_types.melt(id_vars='Date', var_name='Case Type', value_name='Cases')
    submitted_case_types_melt = submitted_case_types_melt[submitted_case_types_melt['Case Type'] != 'Submitted']
    submitted_case_types_melt['Cases'] = submitted_case_types_melt['Cases'].replace(np.nan, 0)
    submitted_case_types_melt['Submitted'] =submitted_case_types_melt['Date'].replace(submitted)
    submitted_case_types_melt['Year'] = pd.to_datetime(submitted_case_types_melt['Date'], format=format_str).dt.year
    submitted_case_types_melt['Month'] = pd.to_datetime(submitted_case_types_melt['Date'], format=format_str).dt.month
    submitted_case_types_melt.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)
    submitted_case_types.set_index('Date', inplace=True)
    if len(submitted_case_types) > 1:
        totals = submitted_case_types.sum()
        average = submitted_case_types.mean().round(1)
        median = submitted_case_types.median()
        max = submitted_case_types.max()
        min = submitted_case_types.min()
        submitted_case_types.loc['Total', :] = totals
        submitted_case_types.loc['Average', :] = average
        submitted_case_types.loc['Median', :] = median
        submitted_case_types.loc['Min', :] = min
        submitted_case_types.loc['Max', :] = max

    submitted_case_types.replace(np.nan, 0, inplace=True)
    submitted_case_types = submitted_case_types.astype(int)
    case_type_headings = submitted_case_types.columns

    submitted_cases_dict = submitted_case_types.to_dict(orient='index')

    submitted = submitted.reset_index()
    submitted['Status'] = 'Submitted'
    submitted.columns = ['Date', 'Cases', 'Status']

    #counts_melt = counts_melt[counts_melt['Days'].isin(selected_traces)]

    open_cases = Cases.query.filter(Cases.case_number.in_(open_cases['case_number']))
    # Replace 'CR1' and 'CR2' with 'CR'
    case_statuses['Status'] = case_statuses['Status'].replace({'CR1': 'CR', 'CR2': 'CR'})

    # Group by the new status and sum the cases
    case_statuses_combined = case_statuses.groupby(['Status', 'Case Type']).agg({'Cases': 'sum'}).reset_index()

    # Filter out 'Testing', 'Submitted', and 'T1 Complete' from the DataFrame
    case_statuses_combined = case_statuses_combined[
        ~case_statuses_combined['Status'].isin(['Testing', 'Submitted', 'T1 Complete'])]



    # Print to verify the combined 'CR' status
    # print(case_statuses_combined['Status'].unique())
    # print(case_statuses_combined)

    data_max = case_statuses_combined['Cases'].max()
    x_axis_max = 10 if data_max < 10 else data_max

    # Ensure 'CR' is in the category orders and legend settings
    category_orders = {
        'Status': [status for status in sort_dict.keys() if
                   status not in ['Testing', 'Submitted', 'T1 Complete', 'CR1', 'CR2']],
        'Case Type': list(case_type_dict.values())
    }
    if 'CR' not in category_orders['Status']:
        insert_position = len(category_orders['Status']) - 1
        category_orders['Status'].insert(insert_position, 'CR')

    aggregated_counts = case_statuses_combined.groupby('Status')['Cases'].sum().reset_index()

    static_case_statuses_df = pd.DataFrame(static_case_statuses, columns=["Status", "Case Type", "Cases"])

    # Group by status and combine `CR1` and `CR2` into `CR`, if needed
    static_case_statuses_df['Status'] = static_case_statuses_df['Status'].replace({'CR1': 'CR', 'CR2': 'CR'})
    static_case_statuses_combined = static_case_statuses_df.groupby(['Status', 'Case Type']).agg(
        {'Cases': 'sum'}).reset_index()

    # Convert to DataFrame for Plotly
    static_aggregated_counts = static_case_statuses_combined.groupby('Status')['Cases'].sum().reset_index()

    # Proceed with creating the figure
    fig = px.bar(
        data_frame=aggregated_counts,
        x='Cases',
        y='Status',
        orientation='h',
        labels={"x": "Cases", "y": ""},
        category_orders=category_orders,
        color_discrete_sequence=['gray']
    )
    fig.add_trace(go.Scatter(
        x=aggregated_counts['Cases'],
        y=aggregated_counts['Status'],
        text=aggregated_counts['Cases'],
        mode='text',
        name='Total',
        textposition='middle right',
        textfont=dict(color='blue'),
        showlegend=False
    ))
    fig.update_layout(
        xaxis=dict(
            range=[0, x_axis_max]
        ),
        hovermode='y unified',
        height=500,
        width=1000,
        showlegend=False,  # This will hide the legend
        margin=dict(t=0)
    )
    fig.update_yaxes(title_text="Status", range=[-0.5, len(category_orders['Status']) - 0.5])
    fig.update_traces(hovertemplate="%{x}: %{x}")

    # Generate HTML for the tally board
    tally_board = fig.to_html(config={'displayModeBar': False})
    # New separate graph for "Testing" status
    testing_fig = px.bar(data_frame=case_statuses[case_statuses['Status'] == 'Testing'],
                         x='Cases',
                         y='Status',
                         color='Case Type',
                         orientation='h',
                         labels={
                             "x": "",
                             "y": "",
                         },
                         color_discrete_map=color_dict)
    testing_fig.add_trace(go.Scatter(
        x=status_counts[status_counts['Status'] == 'Testing']['Cases'],
        y=status_counts[status_counts['Status'] == 'Testing']['Status'],
        text=status_counts[status_counts['Status'] == 'Testing']['Cases'],
        mode='text',
        name='Total',
        textposition='middle right',
        textfont=dict(
            color='blue',
        ),
        showlegend=False
    ))
    testing_fig.update_layout(hovermode='y unified', height=230, showlegend=False, xaxis_title="",yaxis_title="",
                              legend=dict(
                                  x=1,
                                  xanchor='right',
                                  yanchor='bottom',
                                  y=0,
                                  bgcolor='rgba(0,0,0,0)',
                              ),
                              width=1000,
                              margin=dict(b=0)
                              )
    testing_fig.update_yaxes(range=[-0.5, 0.5])
    testing_fig.update_traces(hovertemplate="%{x}: %{x}")
    testing_tally_board = testing_fig.to_html(config={'displayModeBar': False})

    if request.method == 'POST':
        start_date = form.start_date.data
        end_date = form.end_date.data
        date_by = form.date_by.data
        selected_case_types = form.case_type.data
        case_type_condition = True if not selected_case_types else Cases.case_type.in_(selected_case_types)

        testing_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'Testing',
            Assays.discipline == discipline,

        ).all()
        testing_case_count = len(testing_cases)

        # Query for drafting cases within the date range and the current discipline
        drafting_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'Drafting',
            Assays.discipline == discipline,
        ).all()
        drafting_case_count = len(drafting_cases)

        # Query for CR1 cases within the date range and the current discipline
        cr_one_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR1',
            Assays.discipline == discipline,
        ).all()
        cr_one_case_count = len(cr_one_cases)

        # Query for CR2 cases within the date range and the current discipline
        cr_two_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR2',
            Assays.discipline == discipline,
        ).all()
        cr_two_case_count = len(cr_two_cases)

        # Query for CR cases within the date range and the current discipline
        cr_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'CR',
            Assays.discipline == discipline,
        ).all()
        cr_cases_count = len(cr_cases)

        # Query for DR cases within the date range and the current discipline
        dr_cases = Cases.query.join(Tests).join(Assays).filter(
            Cases.case_status == 'DR',
            Assays.discipline == discipline,

        ).all()
        dr_case_count = len(dr_cases)

        if len(form.case_type.data) == 0:
            query = db.session.query(Cases).join(Tests).join(Assays).filter(sa.and_(
                start_date_col >= start_date,
                start_date_col <= end_date,
                Assays.discipline == discipline,  # Add discipline filter
            ))
            query_two = db.session.query(Cases).join(Tests).join(Assays).filter(sa.and_(
                Assays.discipline == discipline
            ))
        else:
            query = db.session.query(Cases).join(Tests).join(Assays).filter(sa.and_(
                start_date_col >= start_date,
                start_date_col <= end_date,
                Cases.case_type.in_(form.case_type.data),
                Assays.discipline == discipline  # Add discipline filter
            ))
            case_types_lst = [dict(form.case_type.choices).get(x) for x in form.case_type.data]
            case_type_str = ", ".join(case_types_lst)

    cases = pd.DataFrame([item.__dict__ for item in query])
    cases['case_type_name'] = cases['case_type'].replace(case_type_dict)

    case_statuses, status_counts = get_case_statuses(cases, sort_dict)
    static_case_statuses = db.session.query(
        Cases.case_status, Cases.case_type, func.count(Cases.id).label("Cases")
    ).join(Tests).join(Assays).filter(
        Assays.discipline == discipline  # Only filtering by discipline, no date filter
    ).group_by(Cases.case_status, Cases.case_type).all()
    cases = cases[~cases[f'{discipline.lower()}_start_date'].isna()]

    if date_by in ['Month', 'Quarter']:
        format_str = '%b-%y'
    elif date_by == 'Year':
        format_str = '%Y'
    cases['Date'] = cases[f'{discipline.lower()}_start_date'].dt.strftime(format_str)
    if date_by == 'Quarter':
        cases['Date'] = cases['Date'].map(lambda x: convert_to_quarter(x))
        format_str = 'Q%m-%y'
    cases['case_type_name'] = cases['case_type'].replace(case_type_dict)
    cases['turn_around_time'] = cases['turn_around_time'].map(lambda x: 0 if not x else x)
    cases['turn_around_time'] = cases['turn_around_time'].fillna(0)
    # closed_cases = cases[(~cases['case_close_date'].isna())]
    closed_cases = cases[cases['case_status'] == 'T1 Complete']
    # print(closed_cases['turn_around_time'])
    open_cases = cases[~cases['case_number'].isin(closed_cases['case_number'])]
    closed_cases = closed_cases[closed_cases['turn_around_time'].astype(int) > 0]
    closed_cases.sort_values(by=[f'{discipline.lower()}_start_date'], inplace=True)
    # open_cases = cases[cases['case_close_date'].isna()]
    # open_cases['case_type_name'] = open_cases['case_type'].replace(case_type_dict)
    submitted = cases['Date'].value_counts(sort=False)
    closed = closed_cases['Date'].value_counts(sort=False)
    closed.name = 'Closed'
    no_closed = [x for x in submitted.index if x not in closed.index]
    for x in no_closed:
        closed[x] = 0

    opened = open_cases['Date'].value_counts()
    opened.name = 'Open'

    closed_cases.loc[:, 'turn_around_time'] = closed_cases['turn_around_time'].astype(int)

    avg_tat = closed_cases.groupby('Date', sort=False).mean()['turn_around_time'].astype(int)
    avg_tat.name = "Avg TAT"
    median_tat = closed_cases.groupby('Date', sort=False).median()['turn_around_time'].astype(int)
    median_tat.name = 'Median TAT'

    open_closed = pd.DataFrame()
    open_closed.index = submitted.index
    open_closed = pd.concat([closed, opened], axis=1)

    counts = pd.DataFrame()
    counts.index = submitted.index

    open_counts = pd.DataFrame()
    open_counts.index = submitted.index
    open_counts = pd.concat([open_counts, open_cases['Date'].value_counts()], axis=1)
    open_counts.reset_index(inplace=True)
    open_counts.columns = ['Date', 'Cases']

    open_case_types = pd.DataFrame()
    # open_case_types.index = submitted.index

    submitted_case_types = pd.DataFrame()
    submitted_case_types.index = submitted.index
    submitted_case_types = pd.concat([submitted_case_types, submitted], axis=1)
    submitted_case_types.columns = ['Submitted']

    for x in selected_traces:
        df = closed_cases[closed_cases['turn_around_time'] < x]
        df_counts = df['Date'].value_counts(sort=False)
        df_counts.name = x
        counts = pd.concat([counts, df_counts], axis=1)
        counts[x] = counts[x].replace(np.nan, 0)
        counts[x] = counts[x].astype(int)

    counts.index.name = 'Date'
    counts.reset_index(inplace=True)
    counts = counts.replace(np.nan, 0)
    counts_melt = counts.melt(id_vars='Date', var_name='Days', value_name='Cases')
    counts_melt['Cases'] = counts_melt['Cases'].replace(np.nan, 0)
    counts_melt['Submitted'] = counts_melt['Date'].replace(submitted)
    counts_melt['Closed'] = counts_melt['Date'].replace(closed)
    counts_melt['%'] = round(counts_melt['Cases'] / counts_melt['Date'].replace(closed) * 100, 1)
    counts_melt['Year'] = pd.to_datetime(counts_melt['Date'], format=format_str).dt.year
    counts_melt['Month'] = pd.to_datetime(counts['Date'], format=format_str).dt.month
    counts_melt.sort_values(by=['Year', 'Month', 'Days'], inplace=True)

    open_closed.index.name = 'Date'
    open_closed.reset_index(inplace=True)
    open_closed = open_closed.replace(np.nan, 0)
    open_closed_melt = open_closed.melt(id_vars='Date', var_name='Status', value_name='Cases')
    open_closed_melt['Cases'] = open_closed_melt['Cases'].replace(np.nan, 0)
    open_closed_melt['Submitted'] = open_closed_melt['Date'].replace(submitted)
    open_closed_melt['Year'] = pd.to_datetime(open_closed_melt['Date'], format=format_str).dt.year
    open_closed_melt['Month'] = pd.to_datetime(open_closed_melt['Date'], format=format_str).dt.month
    open_closed_melt.sort_values(by=['Year', 'Month', 'Status'], inplace=True)

    counts.set_index('Date', inplace=True)
    counts = pd.concat([submitted, opened, closed, avg_tat, median_tat, counts], axis=1)

    counts.columns = ['Submitted', 'Open', 'Closed', 'Avg TAT', 'Median TAT', '<15', '<30', '<45', '<60', '<90']
    counts['<15 (%)'] = round(counts['<15'] / counts['Closed'] * 100, 1)
    counts['<30 (%)'] = round(counts['<30'] / counts['Closed'] * 100, 1)
    counts['<45 (%)'] = round(counts['<45'] / counts['Closed'] * 100, 1)
    counts['<60 (%)'] = round(counts['<60'] / counts['Closed'] * 100, 1)
    counts['<90 (%)'] = round(counts['<90'] / counts['Closed'] * 100, 1)
    if len(counts) > 1:
        totals = counts.sum()
        average = counts.mean().round(1)
        median = counts.median().round(1)
        max = counts.max()
        min = counts.min()
        counts.loc['Total', :] = totals
        counts.loc['Average', :] = average
        counts.loc['Median', :] = median
        counts.loc['Min', :] = min
        counts.loc['Max', :] = max

    counts.replace(np.nan, 0, inplace=True)
    counts = counts.astype({'Submitted': int,
                            'Open': int,
                            'Closed': int,
                            'Avg TAT': int,
                            'Median TAT': int,
                            '<15': int,
                            '<30': int,
                            '<45': int,
                            '<60': int,
                            '<90': int, })

    avg_tat = avg_tat.reset_index()
    avg_tat.columns = ['Date', 'Avg TAT']

    median_tat = median_tat.reset_index()
    median_tat.columns = ['Date', 'Median TAT']

    # totals = pd.DataFrame()
    # totals['Total'] = counts.sum().astype(int)
    # totals['Average'] = counts.mean().astype(int)

    counts_dict = counts.to_dict(orient='index')
    # totals_dict = totals.to_dict()

    for case_type, df in open_cases.groupby('case_type_name'):
        case_type_counts = df['Date'].value_counts()
        case_type_counts = case_type_counts.reset_index()
        case_type_counts.columns = ['Date', 'Cases']
        case_type_counts['Case Type'] = case_type
        # case_type_counts.name = case_type
        # open_case_types = pd.concat([open_case_types, case_type_counts], axis=1)
        open_case_types = pd.concat([open_case_types, case_type_counts])

    # open_case_types.index.name = 'Date'
    # open_case_types.reset_index(inplace=True)

    if len(open_case_types) > 0:
        open_case_types = open_case_types.replace(np.nan, 0)
        open_case_types['Submitted'] = open_case_types['Date'].replace(submitted)
        open_case_types['Year'] = pd.to_datetime(open_case_types['Date'], format=format_str).dt.year
        open_case_types['Month'] = pd.to_datetime(open_case_types['Date'], format=format_str).dt.month
        open_case_types.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)
        # open_case_types_melt = open_case_types.melt(id_vars='Date', var_name='Case Type', value_name='Cases')
        # open_case_types_melt['Cases'] = open_case_types_melt['Cases'].replace(np.nan, 0)
        # open_case_types_melt['Submitted'] =open_case_types_melt['Date'].replace(submitted)
        # open_case_types_melt['Year'] = pd.to_datetime(open_case_types_melt['Date'], format=format_str).dt.year
        # open_case_types_melt['Month'] = pd.to_datetime(open_case_types_melt['Date'], format=format_str).dt.month
        # open_case_types_melt.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)

    for case_type, df in cases.groupby('case_type_name'):
        case_type_counts = df['Date'].value_counts()
        case_type_counts.name = case_type
        submitted_case_types = pd.concat([submitted_case_types, case_type_counts], axis=1)

    submitted_case_types.index.name = 'Date'
    submitted_case_types.reset_index(inplace=True)
    submitted_case_types = submitted_case_types.replace(np.nan, 0)
    submitted_case_types_melt = submitted_case_types.melt(id_vars='Date', var_name='Case Type', value_name='Cases')
    submitted_case_types_melt = submitted_case_types_melt[submitted_case_types_melt['Case Type'] != 'Submitted']
    submitted_case_types_melt['Cases'] = submitted_case_types_melt['Cases'].replace(np.nan, 0)
    submitted_case_types_melt['Submitted'] = submitted_case_types_melt['Date'].replace(submitted)
    submitted_case_types_melt['Year'] = pd.to_datetime(submitted_case_types_melt['Date'], format=format_str).dt.year
    submitted_case_types_melt['Month'] = pd.to_datetime(submitted_case_types_melt['Date'], format=format_str).dt.month
    submitted_case_types_melt.sort_values(by=['Year', 'Month', 'Case Type'], inplace=True)
    submitted_case_types.set_index('Date', inplace=True)
    if len(submitted_case_types) > 1:
        totals = submitted_case_types.sum()
        average = submitted_case_types.mean().round(1)
        median = submitted_case_types.median()
        max = submitted_case_types.max()
        min = submitted_case_types.min()
        submitted_case_types.loc['Total', :] = totals
        submitted_case_types.loc['Average', :] = average
        submitted_case_types.loc['Median', :] = median
        submitted_case_types.loc['Min', :] = min
        submitted_case_types.loc['Max', :] = max

    submitted_case_types.replace(np.nan, 0, inplace=True)
    submitted_case_types = submitted_case_types.astype(int)
    case_type_headings = submitted_case_types.columns

    submitted_cases_dict = submitted_case_types.to_dict(orient='index')

    submitted = submitted.reset_index()
    submitted['Status'] = 'Submitted'
    submitted.columns = ['Date', 'Cases', 'Status']

    # counts_melt = counts_melt[counts_melt['Days'].isin(selected_traces)]

    open_cases = Cases.query.filter(Cases.case_number.in_(open_cases['case_number']))
    # Replace 'CR1' and 'CR2' with 'CR'
    case_statuses['Status'] = case_statuses['Status'].replace({'CR1': 'CR', 'CR2': 'CR'})

    # Group by the new status and sum the cases
    case_statuses_combined = case_statuses.groupby(['Status', 'Case Type']).agg({'Cases': 'sum'}).reset_index()

    # Filter out 'Testing', 'Submitted', and 'T1 Complete' from the DataFrame
    case_statuses_combined = case_statuses_combined[
        ~case_statuses_combined['Status'].isin(['Testing', 'Submitted', 'T1 Complete'])]

    # Print to verify the combined 'CR' status
    # print(case_statuses_combined['Status'].unique())
    # print(case_statuses_combined)

    data_max = case_statuses_combined['Cases'].max()
    print(f'data max ===== {data_max}')
    x_axis_max = 10 if data_max < 10 else data_max

    # Ensure 'CR' is in the category orders and legend settings
    category_orders = {
        'Status': [status for status in sort_dict.keys() if
                   status not in ['Testing', 'Submitted', 'T1 Complete', 'CR1', 'CR2']],
        'Case Type': list(case_type_dict.values())
    }
    if 'CR' not in category_orders['Status']:
        insert_position = len(category_orders['Status']) - 1
        category_orders['Status'].insert(insert_position, 'CR')

    aggregated_counts = case_statuses_combined.groupby('Status')['Cases'].sum().reset_index()

    static_case_statuses_df = pd.DataFrame(static_case_statuses, columns=["Status", "Case Type", "Cases"])

    # Group by status and combine `CR1` and `CR2` into `CR`, if needed
    static_case_statuses_df['Status'] = static_case_statuses_df['Status'].replace({'CR1': 'CR', 'CR2': 'CR'})
    static_case_statuses_combined = static_case_statuses_df.groupby(['Status', 'Case Type']).agg(
        {'Cases': 'sum'}).reset_index()

    fig_start = datetime.now()

    fig = px.bar(data_frame=case_statuses,
                 x='Cases',
                 y='Status',
                 color='Case Type',
                 orientation='h',
                 labels={
                     "x": "Cases",
                     "y": "",
                 },
                 category_orders={'Status': ['Submitted', 'Testing', 'Drafting', 'CR1', 'CR2', 'DR'],
                                  'Case Type': case_type_dict.values()},
                 color_discrete_map=color_dict)
    fig.add_trace(go.Scatter(
        x=status_counts['Cases'],
        y=status_counts['Status'],
        text=status_counts['Cases'],
        mode='text',
        name='Total',
        textposition='middle right',
        textfont=dict(
            color='blue',
        ),
        showlegend=False
    ))
    fig.update_layout(hovermode='y unified', height=600, width=2000,
                      legend=dict(
                          x=1,
                          xanchor='right',
                          yanchor='bottom',
                          y=0,
                          bgcolor='rgba(0,0,0,0)',
                      ),
                      )
    fig.update_yaxes(range=[-0.5, len(sort_dict)-1.5])
    fig.update_traces(hovertemplate="%{x}: %{x}")

    fig = px.line(counts_melt, x="Date", y="%", color='Days', height=600,
                  hover_data={'Date': False}, markers=True, line_shape='spline')
    fig.update_traces(hovertemplate='%{y}')
    fig.add_hline(90, line_dash="dot",
                  annotation_text="90%",
                  annotation_position="bottom right")
    fig.update_layout(legend_traceorder="normal",
                      hovermode='x unified',
                      yaxis_range=[-5, 105]
                      )

    scatter = px.box(
        closed_cases,
        x='Date',
        y='turn_around_time',
        color='case_type_name',
        color_discrete_map=color_dict,
        labels=dict(turn_around_time="Turnaround Time (days)"),
        category_orders={'Date': submitted['Date'],
            'case_type_name': case_type_dict.values(),
                         }
        #color='case_type_name',
    )

    scatter.add_trace(go.Scatter(
        x=avg_tat['Date'],
        y=avg_tat['Avg TAT'],
        text=avg_tat['Avg TAT'],
        mode='lines+markers',
        name='Avg Turnaround Time',
        line_color='black',
        line_width=0.5,
        #mode="lines+text",
        #textposition="top left",
        #textfont=dict(
        #    color='blue',
        #),

    ))
    scatter.add_trace(go.Scatter(
        x=median_tat['Date'],
        y=median_tat['Median TAT'],
        text=median_tat['Median TAT'],
        mode='lines+markers',
        name='Median Turnaround Time',
        line_color='gray',
        line_width=0.5,
        line = dict(dash='dot')
        #mode="lines+text",
        #textposition="top left",
        #textfont=dict(
        #    color='blue',
        #),

    ))
    scatter.update_layout(legend=dict(title='Case Type'),
                          height=600,
                          )

    bar = px.bar(open_closed_melt, x="Date", y="Cases", color='Status',height=600, hover_data={'Date': False})
    bar.add_trace(go.Scatter(
        x=submitted['Date'],
        y=submitted['Cases'],
        text=submitted['Cases'],
        name='Submitted',
        mode='text',
        textposition='top center',
        textfont=dict(
            color='blue',
        ),
        showlegend=False
    ))
    bar.update_layout(legend_traceorder="normal",
                      hovermode='x unified',
                      uniformtext_mode='hide',
                      legend_itemclick=False,
                      legend_itemdoubleclick=False,
                      height=500
                      )
    bar.update_traces(hovertemplate='%{y}')


    # open_bar = px.bar(open_case_types, x="Date", y="Cases", color='Case Type',
    #                   height=500, hover_data={'Date': False},
    #                   color_discrete_map=color_dict,
    #                   category_orders={'Date': submitted['Date'],
    #                                    'Case Type': case_type_dict.values(),
    #                                    },
    #                   )
    # open_bar.add_trace(go.Scatter(
    #     x=open_counts['Date'],
    #     y=open_counts['Cases'],
    #     text=open_counts['Cases'],
    #     mode='text',
    #     name='Open',
    #     textposition='top center',
    #     textfont=dict(
    #         color='blue',
    #     ),
    #     showlegend=False
    # ))
    # open_bar.update_layout(legend_traceorder="normal",
    #                   hovermode='x unified',
    #                   height=500
    #                   )
    # open_bar.update_traces(hovertemplate='%{y}')

    submitted_bar = px.bar(submitted_case_types_melt, x="Date", y="Cases", color='Case Type',
                      height=600, hover_data={'Date': False},
                      color_discrete_map=color_dict, text_auto=True)

    submitted_bar.add_trace(go.Scatter(
        x=submitted['Date'],
        y=submitted['Cases'],
        text=submitted['Cases'],
        mode='text',
        name='Submitted',
        textposition='top center',
        textfont=dict(
            color='blue',
        ),
    ))
    submitted_bar.update_layout(legend_traceorder="normal",
                      hovermode='x unified',
                      height=600
                      )
    submitted_bar.update_traces(hovertemplate='%{y}')

    tat = fig.to_html(config={'scrollZoom': True, 'modeBarButtonsToRemove': [ 'zoom', 'pan', 'select', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale', 'lasso']})
    scatter_html = scatter.to_html(config={'scrollZoom': True, 'toImageButtonOptions': {'filename': "Hello"}})
    bar_html = bar.to_html(config={'displayModeBar': False})
    # open_bar_html = open_bar.to_html(config={'displayModeBar': False})
    submitted_bar_html = submitted_bar.to_html(config={'displayModeBar': False})

    testing_tally = Cases.query.join(Tests).join(Assays).filter(
        Cases.case_status == 'Testing',
        Assays.discipline == discipline,
        start_date_col >= start_date,
        start_date_col <= end_date
    ).order_by(start_date_col).all()


    # print(start_date)
    # print(end_date)
    # print(form.case_type.data)

    # print(f"Figure Generation: {datetime.now()-fig_start}")

    return render_template('dashboard.html',
                           form=form,
                           pending_dict=pending_dict,
                           tally_board=tally_board,
                           tat=tat,
                           scatter_html=scatter_html,
                           bar_html=bar_html,
                           # open_bar_html=open_bar_html,
                           submitted_bar_html=submitted_bar_html,
                           start_date=start_date,
                           end_date=end_date,
                           case_type_str=case_type_str,
                           counts_dict=counts_dict,
                           submitted_cases_dict=submitted_cases_dict,
                           case_type_headings=case_type_headings,
                           open_cases=open_cases,
                           testing_cases=testing_cases,
                           testing_tally=testing_tally,
                           testing_case_count=testing_case_count,
                           drafting_cases=drafting_cases,
                           drafting_case_count=drafting_case_count,
                           cr_one_cases=cr_one_cases,
                           cr_one_case_count=cr_one_case_count,
                           cr_two_cases=cr_two_cases,
                           cr_two_case_count=cr_two_case_count,
                           dr_cases=dr_cases,
                           dr_case_count=dr_case_count,
                           testing_tally_board=testing_tally_board,
                           special_projects=special_projects,
                           current_user=current_user,
                           cr_cases=cr_cases,
                           cr_cases_count=cr_cases_count,
                           current_date=datetime.now(),
                            report_status_graph=report_status_graph,
                            testing_status_graph=testing_status_graph,
                           )


@dashboard.route('/add_special_project', methods=['GET', 'POST'])
@login_required
def add_special_project():
    form = SpecialProjectForm()
    if request.method == 'POST' and form.validate_on_submit():
        special_project = SpecialProjects(
            special_project_name=form.special_project_name.data,
            num_items=form.num_items.data,
            num_completed=form.num_completed.data
        )
        db.session.add(special_project)
        db.session.commit()
        # return jsonify({'success': True})
        return redirect(url_for('dashboard.get_dashboard'))
    return render_template('add_special_project.html', form=form)


@dashboard.route('/change_discipline/<string:discipline>', methods=['POST'])
@login_required
def change_discipline(discipline):
    # Validate if the chosen discipline is correct
    valid_disciplines = ['Toxicology', 'Histology', 'Biochemistry']
    if discipline not in valid_disciplines:
        return redirect(url_for('dashboard.get_dashboard'))

    # Query to find cases that have tests with the chosen discipline
    cases_with_discipline = Cases.query.join(Tests).join(Assays).filter(
        Assays.discipline == discipline,
        Tests.case_id == Cases.id
    ).all()

    # Check if there are any cases with the selected discipline
    if not cases_with_discipline:
        # No cases found, switch discipline to 'Toxicology' and show error message
        current_user.dashboard_discipline = 'Toxicology'
        db.session.commit()
        flash(f"No cases with {discipline}.", "error")
    else:
        # Cases exist, update the user's discipline
        current_user.dashboard_discipline = discipline
        db.session.commit()

    return redirect(url_for('dashboard.get_dashboard'))