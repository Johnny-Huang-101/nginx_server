import os
from flask import current_app, jsonify
from sqlalchemy import or_
from wtforms import ValidationError
from lims.models import *
from lims.locations.functions import location_dict
from lims.evidence_comments.functions import sort_comments
from werkzeug.utils import secure_filename
from pathlib import Path
import pikepdf

def get_case_number_by_case_id(case_id):
    case = Cases.query.filter_by(id=case_id).first()
    return case.case_number if case else None

def get_case_id_by_case_number(case_number):
    case = Cases.query.filter_by(case_number=case_number).first()
    return case.id if case else None

def get_type_id_from_abbrev(abbrev):
    record_type = RecordTypes.query.filter_by(suffix=abbrev).first()
    return record_type.id if record_type else None

def get_form_choices(form, case_id=None):

    if case_id:
        case = Cases.query.get(case_id)
        form.case_id.choices = [(case.id, case.case_number)]

    else:
        cases = [(item.id, item.case_number) for item in Cases.query.order_by(Cases.create_date.desc())]
        cases.insert(0, (0, 'Please select a case'))
        form.case_id.choices = cases

    record_types = [(r_type.id, r_type.name) for r_type in
                RecordTypes.query.filter_by(db_status='Active').order_by(RecordTypes.name)]
    record_types.insert(0, (0, 'Please select an agency'))
    form.record_type.choices = record_types

    return form

def process_form(form):
    """
    Runs AFTER form.validate() succeeded.
    - Normalizes filename
    - Sets record_name from file stem
    - Uses record_type already inferred in form.validate()
    Returns kwargs consumed by add_item(...)
    """
    fs = form.file.data
    filename = secure_filename(getattr(fs, "filename", "") or "")
    stem = form.record_name.data or Path(filename).stem # uses what was done in validator, if not set, it's done here

    case_number = get_case_number_by_case_id(form.case_id.data)

    base = os.path.join(current_app.config['FILE_SYSTEM'], 'records')
    dest_dir = os.path.join(base, case_number)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, filename)
    fs.save(dest_path)

    kwargs = {}
    kwargs["record_name"] = stem
    kwargs["record_type"] = int(form.record_type.data) if form.record_type.data else None
    kwargs["record_number"] = int(form.record_number.data) if form.record_number.data else None

    return kwargs
