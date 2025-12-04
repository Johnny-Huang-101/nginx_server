import re
from datetime import datetime
import pandas as pd

def convert_to_quarter(date):
    quarters = {
        'Jan': 'Q1',
        'Feb': 'Q1',
        'Mar': 'Q1',
        'Apr': 'Q2',
        'May': 'Q2',
        'Jun': 'Q2',
        'Jul': 'Q3',
        'Aug': 'Q3',
        'Sep': 'Q3',
        'Oct': 'Q4',
        'Nov': 'Q4',
        'Dec': 'Q4',
    }
    month = re.findall('(.+)-', date)[0]
    quarter = quarters[month]
    date = date.replace(month, quarter)

    return date


def get_pending_tests(Tests, Assays):

    assay_df = pd.DataFrame([item.__dict__ for item in Assays.query.filter(Assays.num_tests != None)])
    pending_tests = pd.DataFrame()
    if len(assay_df):
        assay_dict = dict(zip(assay_df['id'], assay_df['assay_name']))
        limit_dict = dict(zip(assay_df['id'], assay_df['num_tests']))
        pending_tests_query = Tests.query.filter(Tests.test_status == 'Pending')
        pending_tests = {}
        if pending_tests_query.count():
            pending_tests = pd.DataFrame([item.__dict__ for item in pending_tests_query])
            pending_tests = pending_tests[pending_tests['assay_id'] != 0]
            pending_tests = pending_tests['assay_id'].value_counts().reset_index()
            pending_tests.columns = ['assay_id', 'counts']
            pending_tests['assay_name'] = pending_tests['assay_id'].replace(assay_dict)
            pending_tests['limit'] = pending_tests['assay_id'].replace(limit_dict)
            # pending_tests['limit'] = pending_tests['limit'].replace()
            pending_tests['limit'] = pending_tests['limit'].astype(int)
            pending_tests['ready'] = pending_tests['counts'] >= pending_tests['limit']
            pending_tests = pending_tests.to_dict(orient='index')

    return pending_tests


def get_case_statuses(cases, sort_dict):
    case_statuses = pd.DataFrame()
    # cases_incomplete = cases[cases['case_status'] != 'T1 Complete']

    for case_type, df in cases.groupby('case_type_name'):
    # for case_type, df in cases_incomplete.groupby('case_type_name'):
        counts = df['case_status'].value_counts().reset_index()
        counts['Case Type'] = case_type
        case_statuses = pd.concat([case_statuses, counts])

    # print(case_statuses)
    # case_statuses.columns = ['Status', 'Cases', 'Case Type']
    if not case_statuses.empty:
        case_statuses.columns = ['Status', 'Cases', 'Case Type']
    else:
        case_statuses = pd.DataFrame(columns=['Status', 'Cases', 'Case Type'])

    case_statuses['Order'] = case_statuses['Status'].replace(sort_dict)
    case_statuses = case_statuses.sort_values(by=['Order', 'Case Type'], ascending=[False, True])

    # status_counts = cases_incomplete['case_status'].value_counts().reset_index()
    # status_counts = cases['case_status'].value_counts().reset_index()

    if 'case_status' in cases.columns:
        status_counts = cases['case_status'].value_counts().reset_index()
    else:
        status_counts = pd.DataFrame(columns=['case_status', 'count'])
    status_counts.columns = ['Status', 'Cases']
    status_counts['Order'] = status_counts['Status'].replace(sort_dict)
    status_counts = status_counts.sort_values(by='Order', ascending=False)

    return case_statuses, status_counts
