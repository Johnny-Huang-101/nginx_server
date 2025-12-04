# Application Imports
from flask import request, Blueprint, render_template, jsonify, flash, abort, redirect, \
    url_for, current_app
from flask_login import login_required, current_user
from lims.models import ReportResults, Cases
from lims.forms import Attach, Import
from lims.report_results.forms import Add, Update
from lims.report_results.functions import get_form_choices, get_results, get_disciplines, add_report_results
from lims import db, app
from werkzeug.utils import secure_filename
from lims.view_templates.views import *
import os
import docx2pdf
import pythoncom
from datetime import datetime
import pandas as pd
import numpy as np

# Set item variables
item_type = 'Report Results'
item_name = 'Report Results'
table = ReportResults
table_name = 'report_results'
name = 'id'
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'list'
default_kwargs = {
    'template': template,
    'redirect': redirect_to
}

blueprint = Blueprint('report_results', __name__)


#### ADD #####
@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    case_id = request.args.get('item_id', type=int)
    discipline = request.args.get('discipline')
    form, new_kwargs = get_form_choices(Add(), case_id, discipline)
    kwargs.update(new_kwargs)

    if case_id:
        kwargs['case_id'] = case_id
        result_args = get_results(form.specimen_id.choices[0][0])
        kwargs['results'] = result_args['results']
        if discipline:
            kwargs['discipline'] = discipline

    if request.method == 'POST':
        result_ids = form.result_id.data
        for result_id in result_ids:
            kwargs['result_id'] = result_id
            primary = ""
            observed = ""
            qualitative = ""
            if result_id in form.primary_result_id.data:
                primary = "Y"
            if result_id in form.observed_result_id.data:
                observed = "Y"
            if result_id in form.qualitative_result_id.data:
                qualitative = "y"

            kwargs['primary_result'] = primary
            kwargs['observed_result'] = observed
            kwargs['qualitative_result'] = qualitative

            add_report_results(kwargs)

        case = Cases.query.get(form.case_id.data)
        discipline = form.discipline.data
        draft_number = table.query.filter_by(case_id=case.id, discipline=discipline).count()+1
        kwargs['report_status'] = 'Draft Created'
        kwargs['dtaft_number'] = draft_number
        kwargs['draft_name'] = f"{case.case_number}_{discipline[0]}{draft_number}"

        # Set discipline status on the case level to drafting

        setattr(case, f"{discipline.lower()}_status", 'Drafting')
    _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _add

# @blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
# @login_required
# def add():
#     kwargs = default_kwargs.copy()
#     case_id = request.args.get('item_id', type=int)
#     discipline = request.args.get('discipline')
#     form, new_kwargs = get_form_choices(Add(), case_id, discipline)
#     kwargs.update(new_kwargs)
#
#     if case_id:
#         kwargs['case_id'] = case_id
#         result_args = get_results(form.specimen_id.choices[0][0])
#         kwargs['results'] = result_args['results']
#
#     if request.method == 'POST':
#         result_ids = form.result_id.data
#         for result_id in result_ids:
#             kwargs['result_id'] = result_id
#             primary = ""
#             if result_id in form.primary_result_id.data:
#                 primary = "Y"
#             kwargs['primary_result'] = primary
#
#             add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
#
#         return redirect(url_for('drafts.view_list'))
#
#     _add = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
#
#     return _add

# #### EDIT #####
# @blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
# @login_required
# def edit(item_id):
#     form = Edit()
#     _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)
#
#     return _edit
#
#
# ##### APPROVE #####
# @blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
# @login_required
# def approve(item_id):
#     form = Approve()
#     _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)
#
#     return _approve


##### UPDATE #####
@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()
    form = Update()
    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _update

##### UNLOCK #####
@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):

    _unlock = unlock_item(item_id, table, name, request.referrer)

    return _unlock

##### REVERT CHANGES #####
@blueprint.route(f'/{table_name}/revert_changes/')
@login_required
def revert_changes():

    item_id = request.args.get('item_id', 0, type=int)
    field = request.args.get('field_name', type=str)
    field_value = request.args.get('field_value', type=str)
    field_type = request.args.get('field_type', type=str)
    multiple = request.args.get('multiple', type=str)

    print(field)
    print(field_value)
    print(field_type)
    print(multiple)

    _revert_changes = revert_item_changes(item_id, field, field_value, item_name, field_type, multiple)

    return _revert_changes

##### REMOVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):

    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


##### APPROVE REMOVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):

    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)

    return _approve_remove


##### REJECT REMOVE #####
@blueprint.route(f'/{table_name}/<int:item_id>/reject_remove', methods=['GET', 'POST'])
@login_required
def reject_remove(item_id):

    _reject_remove = reject_remove_item(item_id, table, table_name, item_name, name)

    return _reject_remove

##### RESTORE #####
@blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
@login_required
def restore(item_id):

    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


##### DELETE #####
@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item

#### DELETE ALL #####
@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():

    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():
    query = request.args.get('query')

    items = ReportResults.query

    _view_list = view_items(table, item_name, item_type, table_name, query=query, items=items)

    return _view_list


@blueprint.route(f'/{table_name}/import/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    _import = import_items(form, table, table_name, item_name)

    return _import


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():

    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    _attach = attach_items(form, item_id, table, item_name, table_name, name)

    return _attach


# @blueprint.route(f'/{table_name}/get_specimens/', methods=['GET', 'POST'])
# @login_required
# def get_specimens_json():
#     case_id = request.args.get('case_id', type=int)
#     response = get_specimens(case_id)
#
#     return response

@blueprint.route(f'/{table_name}/get_disciplines/', methods=['GET', 'POST'])
@login_required
def get_disciplines_json():
    case_id = request.args.get('case_id', type=int)
    response = get_disciplines(case_id)

    return response

@blueprint.route(f'/{table_name}/get_results/', methods=['GET', 'POST'])
@login_required
def get_results_json():
    specimen_id = request.args.get('specimen_id', type=int)
    response = get_results(specimen_id)

    return jsonify(response)


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    alias = f"{getattr(item, name)}"

    _view = view_item(item, alias, item_name, table_name)
    return _view
