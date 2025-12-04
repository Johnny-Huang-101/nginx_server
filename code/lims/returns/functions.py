from lims.models import *
from sqlalchemy import case

from flask import request
def get_form_choices(form, agency_id=None, division_id=None, dest_agency_id=None, dest_division_id=None, item=None):
    if request.method == 'GET':
         cases = [
        (str(case.id), case.case_number)
        for case in Cases.query
            .filter(Cases.create_date >= datetime(2025, 1, 1))
            .order_by(case((Cases.case_type == 7, 0), else_=1), Cases.case_type.asc(),Cases.id.desc()).all()]
    else:
        cases = [
        (case.id, case.case_number)
        for case in Cases.query
            .filter(Cases.create_date >= datetime(2025, 1, 1))
            .order_by(case((Cases.case_type == 7, 0), else_=1), Cases.case_type.asc(),Cases.id.desc()).all()]
    form.case_id.choices = cases

    if form.no_case.data:
        form.case_id.render_kw = {'disabled': True}

    # ✅ Only pre-populate .data in update mode AND only on GET
    if item and request.method == 'GET':
        if hasattr(item, "case_id") and isinstance(item.case_id, str):
            form.case_id.data = [cid.strip() for cid in item.case_id.split(",") if cid.strip()]

    # returning agency
    agencies = [(agency.id, agency.name) for agency in Agencies.query.filter_by(db_status='Active')]
    agencies.insert(0, (0, 'Please select an agency'))
    form.returning_agency.choices = agencies

    if form.returning_agency.data:
        agency_id = form.returning_agency.data

    if agency_id:
        divisions = [(division.id, division.name) for division in Divisions.query.filter_by(agency_id=agency_id)]
        divisions.insert(0, (0, 'Please select a division'))
    else:
        divisions = [(0, '---')]

    form.returning_division.choices = divisions

    if form.returning_division.data:
        division_id = form.returning_division.data

    if division_id:
        personnel = [
            (personnel.id, personnel.full_name)
            for personnel in Personnel.query.filter_by(division_id=division_id, status_id='1')
        ]
        personnel.insert(0, (0, 'Please select a personnel'))
    else:
        personnel = [(0, '---')]

    form.returning_personnel.choices = personnel

    if hasattr(form, 'returned_specimens'):
        form.returned_specimens.choices = [(-1, "No previously released evidence.")]

    return form
