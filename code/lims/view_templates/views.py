"""
DO NOT REMOVE!!!!!
 -import sqlalchemy as sa
 -Blueprint
 -login_required

These are not used in this file but are used in every module and we're importing everything from this file
in views.py i.e., from lims.view_templates.views import *

"""

# General Imports
import os
import json
import pytz
import pandas as pd
import sqlite3
import numpy as np
import glob
from pytz import timezone
from datetime import datetime, timedelta
from pathlib import Path
import sqlalchemy as sa
# Flask Imports
from flask import render_template, url_for, flash, Blueprint, \
    redirect, request, abort, jsonify, session, Markup, \
    current_app, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy import inspect, Integer, String, DateTime, Float, Boolean, Date, Text
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError
# Application Imports
from lims import app
from lims import db
from lims.models import Modifications, Attachments, AttachmentTypes, Services, CommentInstances, module_definitions
import shutil, stat


# from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
# from reportlab.lib.pagesizes import letter, landscape, portrait
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib import colors
# from reportlab.pdfbase import pdfmetrics
import csv
from xml.sax.saxutils import escape


def sanitize_notes_for_pdf(text: str) -> str:
    """
    Escape special characters for ReportLab Paragraphs.
    Replace newlines with <br/> for line breaks.
    """
    if not text:
        return ''
    # Escape <, >, &, etc.
    text = escape(text)
    # Replace newlines with <br/>
    text = text.replace('\n', '<br/>')
    return text


def convert_csv_to_pdf(csv_path, pdf_path,
                       orientation='landscape',   # 'landscape' or 'portrait'
                       font_name='Helvetica',
                       font_size=8,
                       max_cols_per_page=None):  # set (e.g.) 10 to force column-chunking
    """
    Convert CSV -> nicely formatted PDF table.
    If there are too many columns, set max_cols_per_page to chunk into multiple tables/pages.
    """
    # --- read CSV ---
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = [r for r in reader]
    if not rows:
        raise ValueError("CSV is empty")

    # --- page setup ---
    pagesize = landscape(letter) if orientation == 'landscape' else portrait(letter)
    page_width, page_height = pagesize
    left_margin = right_margin = 20
    top_margin = bottom_margin = 20
    avail_width = page_width - left_margin - right_margin

    # --- styles ---
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle('body', parent=styles['Normal'],
                                fontName=font_name, fontSize=font_size, leading=font_size + 2)
    header_style = ParagraphStyle('header', parent=styles['Normal'],
                                  fontName=font_name, fontSize=font_size, leading=font_size + 2,
                                  alignment=1,wordWrap='CJK')  # centered header

    # --- helpers ---
    num_cols = max(len(r) for r in rows)
    if max_cols_per_page:
        cols_per_chunk = min(max_cols_per_page, num_cols)
    else:
        cols_per_chunk = num_cols

    def build_table_for_col_range(start_col, end_col):
        """Build a Table object for column slice [start_col, end_col)."""
        # build flowables (Paragraph) for each cell, header uses header_style

        table_data = []
        for row_i, r in enumerate(rows):
            cells = []
            for c in range(start_col, end_col):
                val = str(r[c]) if c < len(r) else ''
                style = header_style if row_i == 0 else body_style

                safe_val = sanitize_notes_for_pdf(val)
                cells.append(Paragraph(safe_val, style))
            table_data.append(cells)

        # estimate col widths by measuring the widest string in each column
        col_widths = []
        for c in range(start_col, end_col):
            widest = 0
            for r in rows:
                text = str(r[c]) if c < len(r) else ''
                w = pdfmetrics.stringWidth(text, font_name, font_size)
                if w > widest:
                    widest = w
            widest += 8  # small padding
            col_widths.append(widest)

        total_w = sum(col_widths)
        min_col_w = 30

        if total_w > avail_width:
            # scale down proportionally, respect min width
            scale = avail_width / total_w
            col_widths = [max(min_col_w, w * scale) for w in col_widths]
            # if rounding causes overflow, shave off from largest until it fits
            while sum(col_widths) > avail_width:
                i = col_widths.index(max(col_widths))
                col_widths[i] = max(min_col_w, col_widths[i] - 1)
        else:
            # expand to use full width evenly
            extra = avail_width - total_w
            if extra > 0:
                add_each = extra / len(col_widths)
                col_widths = [w + add_each for w in col_widths]


        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)

        # styling
        ts = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')),  # header bg
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), font_size),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ])
        # alternating row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                ts.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)

        tbl.setStyle(ts)
        return tbl

    # --- assemble document ---
    doc = SimpleDocTemplate(pdf_path, pagesize=pagesize,
                            leftMargin=left_margin, rightMargin=right_margin,
                            topMargin=top_margin, bottomMargin=bottom_margin)
    elements = []
    start = 0
    while start < num_cols:
        end = min(start + cols_per_chunk, num_cols)
        elements.append(build_table_for_col_range(start, end))
        start = end
        if start < num_cols:
            elements.append(PageBreak())

    doc.build(elements)



# today = datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')).strftime("%Y-%m-%d")
today = datetime.today()
within30d = datetime.today()+timedelta(days=35)

# Statuses to filter out when counting pending items
ignore_statuses = ['Active', 'Removed']


def add_item(form, table, item_type, item_name, table_name, requires_approval,
             name, function='Add', alias=None, admin_only=False, default_header=True,
             display_flash_message=True,custom_flash_message=None,
             exit_route=None, auto_approved_fields=[], **kwargs):
    """

    Add item to the database. Has both GET and POST requests.

    GET: render form template.
    POST: process form and redirect.

    Parameters
    ----------
    form (FlaskForm):
        Instance of the form to be displayed and processed.
    table (db.Model):
        The database table that will be added to
    item_type (str):
        The plain english name (singular) to be displayed in the form header. e.g. Add Agency
    item_name (str)
        The plain english name (plural) to be added to the modifications table i.e., Agencies
    table_name (str):
        The snake cased module/route name for redirecting.
    requires_approval (bool):
        If the item should go through the approval process.
    name (str):
        The property of the database which is used for display.
    function (str): 'Add'
        The function string.
    admin_only (bool): True
        Whether access to the form should be restricted to only 'Admin' and 'Owner'.
    default_header (bool): True
        Shows the default header (i.e., "Add <item_type>". If you want to have a custom header
        set this to False and add the custom header within the header block of the modules'
        form.html file.
    display_flash_message (bool): True
        Whether to display a flash message.
    custom_flash_message (tuple): None
        Set a custom flash message. This takes in a tuple (message, status)
        e.g. custom_flash_message = ('This is a flash message', 'success'). The
        message can also be a Markup object so you can apply HTML styling. e.g.
        custom_flash_message = (Markup('This is a <b>BOLD WORD</b>'), 'success').
        Statuses include success (green), warning (yellow), error (red)
    exit_route (str): None
        routing on "Exit" button click. Use url_for.
    auto_approved_fields (list): Empty
        Fields that are automatically approved even if the module requires approval.
    kwargs (dict):
        Any other keyword parameters. Can be used to add non-form values (such as calculated
        values based on form input). These parameters will be available in the template.

    Returns
    -------

    BaseResponse

    """

    def render():

        # Get template from kwargs
        if kwargs.get('template'):
            template = f"{table_name}/{kwargs['template']}"
        else:
            template = f"{table_name}/form.html"
        return render_template(
            template,
            function=function,
            item_dict=item_dict,
            item_id=None,
            form=form,
            table_name=table_name,
            item_name=item_name,
            item_type=item_type,
            today=today,
            approved_fields=json.dumps([]),
            required_fields=required_fields,
            errors_json=json.dumps(errors),
            errors=errors,
            pending_fields=json.dumps([]),
            default_header=default_header,
            exit_route=exit_route,
            kwargs=kwargs
        )

    # Get permissions of current user. If admin_only == True, and the user
    # does not have Admin or Owner permissions.
    # The first user will initially not have an account and will need to a
    # add themselves to the database thus they will not have any permissions.
    if current_user.is_active:
        permissions = current_user.permissions
        if admin_only:
            if permissions not in ['Admin', 'Owner']:
                abort(403)
        elif permissions == 'View':
            abort(403)

    # Errors dictionary is passed into the template for validation handling.
    # Empty dictionary Initialised empty and passed into template to prevent
    # JavaScript exceptions when no there are no form errors
    errors = {}
    # For edit/approve/update, the header of the form will be "Edit {alisas}"
    item_dict = None

    # Get list of required fields to pass to form so a red'*' is added
    required_fields = json.dumps([field.name for field in form if field.flags.required])

    if 'request' in kwargs.keys():
        request.method = kwargs['request']

    # Append ignore fields in kwargs to always ignored fields (submit, communications and csrf token)
    ignore_fields = ['submit', 'communications', 'csrf_token']
    if 'ignore_fields' in kwargs.keys():
        ignore_fields += kwargs['ignore_fields']

    if not exit_route:
        exit_route = url_for(f"{table_name}.view_list")

    # If form is validated on submit
    if request.method == 'POST':
        if form.validate_on_submit():

            # field_data is what is passed into the table it the combination of
            # data from the form and kwargs. Kwargs are added after
            field_data = {}

            # This is to handle the first user of the database

            if 'initials' in kwargs.keys() and kwargs['initials'] == "AI System":
                initials = "AI System"
            elif current_user.is_active:
                initials = current_user.initials
            else:
                initials = kwargs['initials']

            # if requires_approval is True, set db_status and modification_status to 'Pending'.
            # Also set pending_submitter to the submitting user's (current_user) initials.
            # If requires_approval is False, set db_status to 'Active and modification_status to 'Approved'
            # if requires_approval:
            #     db_status = 'Pending'
            #     pending_submitter = current_user.initials
            # else:
            #     db_status = 'Active'
            #     pending_submitter = None

            # Initialise default values that apply across all tables
            field_data.update({'locked': False,
                               'create_date': datetime.now(),
                               'created_by': initials,
                               'revision': 0,
                               # 'db_status': db_status,
                               # 'pending_submitter': pending_submitter
                               })

            # pending_fields counter to determine the db_status and pending submitter of the item after
            # going through each form field.
            pending_fields = 0

            # Add non-blank form field data to Modifications table
            form_data = {}
            for field in form:
                if field.data:
                    # if the field name is not in ignore_fields and is a property of the item defined in models.py,
                    # Add a modification entry. We also want to store information about imported/uploaded files.
                    # The raw form data in addition to what the user sees is added to the modification entry.
                    if (hasattr(table, field.name) or field.type == 'FileField'):
                        if field.name in kwargs.keys():
                            data = kwargs[field.name]
                        else:
                            data = field.data

                        if field.type == 'SelectField':
                            data_text = dict(field.choices).get(data)
                        elif field.type == 'SelectMultipleField':
                            if isinstance(data, list):
                                # if field is a SelectMultipleField, data is stored as a list.
                                # Join elements in the list with a comma.
                                data_text = ", ".join(map(str, [dict(field.choices).get(x) for x in data]))
                                data = ", ".join(map(str, data))
                            else:
                                data_text = dict(field.choices).get(data)
                        elif field.type in ['DateField', 'NullableDateField']:
                            data = datetime.combine(data, datetime.min.time())
                            data_text = data.strftime('%m/%d/%Y')
                        elif field.type == 'FileField':
                            if field.name not in kwargs.keys():
                                data = data.filename
                            data_text = data
                        else:
                            data_text = data

                        if field.name not in ignore_fields:
                            # If the item does not require approval, set the modification status to approved
                            # the reviewer to the current user and the review date as the time of submission
                            # when no Users exist, replace line above with block below.
                            try:
                                submitted_by = current_user.id
                            except AttributeError:
                                submitted_by = None

                            # If the module requires approval set the modification_status to 'Pending' and increment
                            # the pending_fields counter unless the field name is in auto_approved_fields.
                            if requires_approval and field.name not in auto_approved_fields:
                                modification_status = 'Pending'
                                pending_fields += 1
                            else:
                                modification_status = 'Approved'

                            # If the modification_status is approved, set the reviewed_by and review_date to the current
                            # user, else leave blank.
                            if modification_status == 'Approved':
                                reviewed_by = current_user.id
                                review_date = datetime.now()
                            else:
                                reviewed_by = None
                                review_date = None

                            # Since the item has not been added yet, we are going to get the record id by finding
                            # the length of table and incrementing by 1.
                            record_id = table.get_next_id()

                            # Create the modification item
                            modification = Modifications(
                                event='CREATED',
                                status=modification_status,
                                table_name=item_name,
                                record_id=record_id,
                                revision=0,
                                field=field.label.text,
                                field_name=field.name,
                                new_value=data,
                                new_value_text=data_text,
                                # submitted_by=current_user.id,
                                # when no Users exist, replace line above with block below
                                submitted_by=submitted_by,
                                submitted_date=datetime.now(),
                                reviewed_by=reviewed_by,
                                review_date=review_date
                            )
                            # Add modification item
                            db.session.add(modification)

                        form_data[field.name] = data

            # if there are pending fields, set db_status 'Pending'.
            # Also set pending_submitter to the submitting user's (current_user) initials.
            # If requires_approval is False, set db_status to 'Active and modification_status to 'Approved'
            if pending_fields:
                field_data['db_status'] = 'Pending'
                field_data['pending_submitter'] = current_user.initials
            else:
                field_data['db_status'] = 'Active'
                field_data['pending_submitter'] = None

            field_data.update(form_data)

            # Add any kwargs to field_data dictionary. This will overwrite any values with the same key.
            if kwargs:
                field_data.update(kwargs)
            print(field_data)
            # Create and add the database item.
            item = table(**field_data)
            # print(f'ALL ITEM {type(field_data)} DATA= {field_data}')

            db.session.add(item)

            # Commit the session, if a duplicate value is added where there is a unique constraint,
            # raise IntegrityError and return user to the form.
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error_message = f"<b>{item_type}</b> with the following values already exists!"
                print(form)
                if hasattr(form, 'unique_fields'):
                    error_message += "<ul>"
                    for field_name in form.unique_fields:
                        field = form[field_name]
                        value = field.data
                        if field.type in ['SelectField', 'SelectMultipleField']:
                            value = dict(field.choices).get(value)
                        error_message += f"<li><b>{field.label.text}</b>: {value}</li>".replace("*", "")
                    error_message += "</ul>"

                errors = {'unique_failed': Markup(error_message)}
                form = render_form(form)
                return render()
                # print("Error: There is a duplicate item.")
                # return redirect(request.referrer)

            # Get the alias of the item which is the item's value for the property defined in 'name'.
            if not alias:
                if isinstance(name, list):
                    alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
                else:
                    alias = getattr(item, name)

            # Set messages to be flashed after submission.
            if display_flash_message:
                if table_name == 'locations':
                    prefix = "Locations: "
                else:
                    prefix = ""

                if custom_flash_message:
                    message, status = custom_flash_message
                else:
                    if not pending_fields:
                        message, status = Markup(f"{prefix}<b>{alias}</b> was successfully added to <b>{item_name}</b>."), "success"
                    else:
                        message, status = Markup(f"{prefix}<b>{alias}</b> will be added to <b>{item_name}</b> pending review and approval."), "warning"

                flash(message, status)

            # # Get number of pending and locked items for notification badge and review alert
            # if hasattr(table, 'db_status'):
            #     session['action_items'][table_name] = table.query.filter(
            #         table.db_status.not_in(ignore_statuses)).count()
            #     session['action_items'][table_name] += table.query.filter_by(locked=True).count()

            # Redirect user after form submission. The default is to redirect to view_list.
            # if 'view', redirect them to the items view page. If 'list', redirect them to the
            # items list view.
            redirect_url = url_for(f"{table_name}.view_list")

            if kwargs.get("redirect"):
                if kwargs['redirect'] == 'view':
                    redirect_url = url_for(f"{table_name}.view", item_id=item.id)
                elif kwargs['redirect'] == 'list':
                    redirect_url = url_for(f"{table_name}.view_list")
                else:
                    redirect_url = kwargs['redirect']

            return redirect(redirect_url)


        else:
            # If the form has errors, re-render the form and pass in the errors dictionary
            kwargs.update(form.data)
            form = render_form(form, kwargs)
            errors = form.errors
            print(form.errors)

    # Render form
    elif request.method == 'GET':
        form = render_form(form, kwargs)

    # Render Add Form
    return render()


def edit_item(form, item_id, table, item_type, item_name, table_name,
              name, function='Edit', alias=None, admin_only=False, locking=True,
              default_header=True, display_flash_message=True, custom_flash_message=None,
              exit_route=None, **kwargs):
    """

    Edit existing item that requires approval. Has both GET and POST requests.

    GET: render form template.
    POST: process form and redirect.

    Parameters
    ----------
    form (FlaskForm):
        Instance of the form to be displayed and processed.
    item_id (int):
        The id of the item to be edited.
    table (db.Model):
        The database table that will be added to.
    item_type (str):
        The plain english name (singular) to be displayed in the form header. e.g. Add Agency.
    item_name (str)
        The plain english name (plural) used to query the Modifications table. Additionally, it
        is used for the path tree at the top of the page.
    table_name (str):
        The snake cased module/route name for redirecting.
    name (str):
        The property of the database which is used for display.
    function (str): 'Edit'
        The function string.
    alias (str): None
        Set the alias manually
    admin_only (bool): False
        Whether access to the form should be restricted to only 'Admin' and 'Owner'.
    locking (bool): True
        Whether to lock the item when the form is accessed.
    default_header (bool): True
        Shows the default header (i.e., "Edit <alias>". If you want to have a custom header
        set this to False and add the custom header within the header block of the modules'
        form.html file.
    display_flash_message (bool): True
        Whether to display a flash message.
    custom_flash_message (tuple): None
        Set a custom flash message. This takes in a tuple (message, status)
        e.g. custom_flash_message = ('This is a flash message', 'success'). The
        message can also be a Markup object so you can apply HTML styling. e.g.
        custom_flash_message = (Markup('This is a <b>BOLD WORD</b>'), 'success').
        Statuses include success (green), warning (yellow), error (red)
    exit_route (str): None
        routing on "Exit" button click. Use url_for. Defaults to the returning to the item page
    kwargs (dict):
        Any other keyword parameters. Can be used to add non-form values (such as calculated
        values based on form input). These parameters will be available in the template.

    Returns
    -------
    BaseResponse

    """

    def render():
        # Get template from kwargs
        template = f"{table_name}/{kwargs['template']}"

        return render_template(
            template,
            function=function,
            form=form,
            item=item,
            item_id=item_id,
            table_name=table_name,
            item_type=item_type,
            item_name=item_name,
            item_dict=item_dict,
            alias=alias,
            mods=mods,
            approved_fields=json.dumps(approved_fields),
            pending_fields=json.dumps(pending_fields),
            required_fields=json.dumps(required_fields),
            errors_json=json.dumps(errors),
            errors=errors,
            default_header=default_header,
            exit_route=exit_route,
            kwargs=kwargs
        )

    # If user only has view permissions, abort
    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)
    elif permissions == 'View':
        abort(403)

    # Get the item to be updated. If the item does not exist, raise 404 Not Found error.
    item = table.query.get_or_404(item_id)

    # if the item is locked and the current_user is not the person who locked it, abort
    if item.locked:
        if item.locked_by != current_user.initials:
            abort(403)

    # If the current user is not the pending submitter, abort. This also prevents access to the form
    # if an item does use the approval process.
    if item.pending_submitter != current_user.initials:
        abort(403)

    # Convert the item to a dictionary to pass into form
    item_dict = item.__dict__.copy()

    # Get the alias of the item
    if not alias:
        if isinstance(name, list):
            alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        else:
            alias = getattr(item, name)

    # Initialise containers
    errors = {}
    pending_fields = []
    approved_fields = []
    mod_dict = {}

    # Get pending and approved modifications
    mods = Modifications.query.filter_by(table_name=item_name, record_id=str(item_id)). \
        filter(Modifications.status.in_(['Pending', 'Approved']))

    # Get event, i.e., CREATED or UPDATED
    pending_mod = mods.filter_by(status='Pending').first()
    if pending_mod:
        event = pending_mod.event

    # Iterate through modifications and populate dictionaries/lists
    for mod in mods:
        mod_dict[mod.field_name] = mod
        if mod.status == 'Pending':
            pending_fields.append(mod.field_name)
        else:
            approved_fields.append(mod.field_name)

    # Get required fields to display red *
    required_fields = [field.name for field in form if field.flags.required]

    # Set the route when the exit button is clicked.
    if not exit_route:
        exit_route = url_for(f"{table_name}.unlock", item_id=item_id)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            # Append user-defined fields to ignore when adding modifications
            ignore_fields = ['submit', 'communications', 'csrf_token']
            if 'ignore_fields' in kwargs.keys():
                ignore_fields += kwargs['ignore_fields']

            # initialise new data counter
            new_data = 0

            # Get form data and append it with kwargs
            form_data = form.data
            form_data.update(kwargs)

            for field in form:
                # if the form has a field name that is the same as a table property name
                if hasattr(item, field.name):
                    # Default the revision number for the modification entry to zero
                    revision = -1
                    # if there is an existing modification for this field, get that revision number
                    mod = mod_dict.get(field.name)
                    if mod:
                        revision = int(mod.revision)

                    # get the new and original values
                    new_value, new_value_text, original_value, original_value_text = get_values(item, field, form_data[field.name])
                    form_data[field.name] = new_value

                    if (new_value != original_value) and (field.name not in pending_fields) and (field.name not in approved_fields):
                        if field.name not in ignore_fields:
                            # increment field revision else 0 for new field
                            revision += 1
                            new_data += 1

                            # Create the modification item and add to table
                            modification = Modifications(
                                event=event,
                                status="Pending",
                                table_name=item_name,
                                record_id=str(item.id),
                                revision=revision,
                                field=field.label.text,
                                field_name=field.name,
                                original_value=original_value,
                                original_value_text=original_value_text,
                                new_value=new_value,
                                new_value_text=new_value_text,
                                submitted_by=current_user.id,
                                submitted_date=datetime.now(),
                            )

                            db.session.add(modification)

                    # If the value is different and the field did have data
                    elif (original_value != new_value) and (field.name in pending_fields):
                        # If the new value is the same as the most recent modification's original value
                        # (i.e., the value has been reverted), delete the modification
                        if mod.original_value == new_value:
                            db.session.delete(mod)
                            # Get the previous mod i.e. the one prior to the current pending modification
                            # and roll-back the status to approved (will have a status of either revised or reverted).
                            prev_mod = Modifications.query.filter_by(
                                table_name=item_name,
                                record_id=str(item_id),
                                field_name=field.name,
                                revision=revision-1).first()

                            # If the previous modifications status was either
                            # 'Revised' or 'Reverted, set status to 'Pending'
                            # and clear reviewer data
                            if prev_mod and (prev_mod.status in ['Revised', 'Reverted']):
                                prev_mod.status = 'Approved'
                                # prev_mod.reviewed_by = current_user.id
                                # prev_mod.review_date = datetime.now()

                        # if the new value is different to the original value but not the same as a previous
                        # modification, set the modifications new_value and new_value_text. Increment new_data.
                        else:
                            new_data += 1
                            mod.new_value = new_value
                            mod.new_value_text = new_value_text
                            mod.submitted_date = datetime.now()

            # Set the item's new values
            for field, data in form_data.items():
                if hasattr(item, field):
                    setattr(item, field, data)

            # Get the items alias
            if not alias:
                if isinstance(name, list):
                    alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
                else:
                    alias = getattr(item, name)


            # Get the most recent modification
            last_mod = Modifications.query.filter_by(table_name=item_name, record_id=str(item_id)). \
                order_by(Modifications.submitted_date.desc()).first()

            # If there was new data submitted in the edit form, update the item
            # modify date and modifier with current time and user.
            if new_data:
                item.modify_date = datetime.now()
                item.modified_by = current_user.initials
                message, status = Markup(f"<b>{alias}</b> has been edited and will be added pending review and approval."), "warning"
            # If the latest modification is still pending, set the item modify date
            # and modifier as the submission time and submitter.
            elif last_mod.status == 'Pending':
                item.modify_date = last_mod.submitted_date
                item.modified_by = last_mod.submitter.initials
                message, status = Markup(f"<b>{alias}</b> will be added pending review and approval."), "warning"
            # If the latest modification is approved set the item modify date and modifer as the
            # modification approver. Also set the item db status to 'Active'.
            else:
                item.modify_date = last_mod.review_date
                item.modified_by = last_mod.reviewer.initials
                item.communications = None
                item.pending_submitter = None
                item.db_status = 'Active'
                message, status = Markup(f"Changes to <b>{alias}</b> undone"), "success"

            # Commit the session, if a duplicate value is added where there is a unique constraint,
            # raise IntegrityError and return user to the form.
            try:
                # Unlock item on form submission
                item.locked = False
                item.locked_by = None
                item.lock_date = None
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error_message = f"<b>{item_type}</b> with the following values already exists!"
                print(form)
                if hasattr(form, 'unique_fields'):
                    error_message += "<ul>"
                    for field_name in form.unique_fields:
                        field = form[field_name]
                        value = field.data
                        if field.type in ['SelectField', 'SelectMultipleField']:
                            value = dict(field.choices).get(value)
                        error_message += f"<li><b>{field.label.text}</b>: {value}</li>".replace("*", "")
                    error_message += "</ul>"

                errors = {'unique_failed': Markup(error_message)}
                form = render_form(form)
                return render()

            if custom_flash_message:
                message, status = custom_flash_message
            if display_flash_message:
                flash(message, status)

            # Redirect user after form submission. The default is to redirect to view_list.
            # if 'view', redirect them to the items view page. If 'list', redirect them to the
            # items list view.
            redirect_url = url_for(f"{table_name}.view_list")
            if "redirect" in kwargs.keys():
                if kwargs['redirect'] == 'view':
                    redirect_url = url_for(f"{table_name}.view", item_id=item.id)
                elif kwargs['redirect'] == 'list':
                    redirect_url = url_for(f"{table_name}.view_list")
                else:
                    redirect_url = kwargs['redirect']

            return redirect(redirect_url)

        else:
            # If the form has errors, re-render the form and pass in the errors dictionary
            kwargs.update(form.data)
            form = render_form(form, kwargs, item, mod_dict, approved_fields)
            errors = form.errors
            print(form.errors)

    # Render form
    elif request.method == 'GET':

        # # Get the alias of the item
        # if not alias:
        #     if isinstance(name, list):
        #         alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        #     else:
        #         alias = getattr(item, name)

        form = render_form(form, kwargs, item, mod_dict, approved_fields)

        # if locking = True, lock item.
        if locking:
            item.locked = True
            item.locked_by = current_user.initials
            item.lock_date = datetime.now()
            db.session.commit()

    return render()


def approve_item(form, item_id, table, item_type, item_name, table_name,
                 name, function='Approve', alias=None, admin_only=False, locking=True,
                 default_header=True, set_item_active=True, display_flash_message=True,
                 custom_flash_message=None, exit_route=None, **kwargs):
    """

    Approve existing item that requires approval. Has both GET and POST requests.

    GET: render form template.
    POST: process form and redirect.

    Parameters
    ----------
    form (FlaskForm):
        Instance of the form to be displayed and processed.
    item_id (int):
        The id of the item to be approved.
    table (db.Model):
        The database table that will be added to.
    item_type (str):
        The plain english name (singular) to be displayed in the form header. e.g. Add Agency.
    item_name (str)
        The plain english name (plural) to be added to the modifications table i.e., Agencies.
    table_name (str):
        The snake cased module/route name for redirecting.
    name (str):
        The property of the database which is used for display.
    function (str): 'Approve'
        The function string.
    alias (str): None
        Set the alias manually.
    admin_only (bool): False
        Whether access to the form should be restricted to only 'Admin' and 'Owner'.
    locking (bool): True
        Whether to lock the item when the form is accessed.
    default_header (bool): True
        Shows the default header (i.e., "Approve <alias>". If you want to have a custom header
        set this to False and add the custom header within the header block of the modules'
        form.html file.
    set_item_active (bool) : True
        If the item is fully approved, set whether the item's db_status is set
        to 'Active' and the item's pending_submitter field is cleared. This is currently
        only used in Cases such that if a case is approved, but it still has pending
        containers/specimens, the case will still be pending.
    display_flash_message (bool): True
        Whether to display a flash message.
    custom_flash_message (tuple): None
        Set a custom flash message. This takes in a tuple (message, status)
        e.g. custom_flash_message = ('This is a flash message', 'success'). The
        message can also be a Markup object so you can apply HTML styling. e.g.
        custom_flash_message = (Markup('This is a <b>BOLD WORD</b>'), 'success').
        Statuses include success (green), warning (yellow), error (red)
    exit_route (str): None
        routing on "Exit" button click. Use url_for. Defaults to the returning to the item page
        through the unlock function.
    kwargs (dict):
        Any other keyword parameters. Can be used to add non-form values (such as calculated
        values based on form input). These parameters will be available in the template.

    Returns
    -------
    BaseResponse

    """

    def render():
        # Get template from kwargs
        if kwargs['template']:
            template = f"{table_name}/{kwargs['template']}"
            print(f'TEMPLATE == {template}')
            return render_template(
                template,
                function=function,
                form=form,
                item=item,
                item_id=item_id,
                table_name=table_name,
                item_type=item_type,
                item_name=item_name,
                item_dict=item_dict,
                alias=alias,
                mods=mods,
                mod_dict=mod_dict,
                approved_fields=json.dumps(approved_fields),
                pending_fields=json.dumps(pending_fields),
                required_fields=json.dumps(required_fields),
                errors_json=json.dumps(errors),
                errors=errors,
                default_header=default_header,
                exit_route=exit_route,
                kwargs=kwargs
            )

    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)
    elif permissions == 'View':
        abort(403)


    # Get the item to be updated. If the item does not exist, raise 404 Not Found error.
    item = table.query.get_or_404(item_id)

    # if the item is locked and the current_user is not the person who locked it, abort
    if item.locked:
        if item.locked_by != current_user.initials:
            abort(403)

    # If the current user is the pending submitter, abort. This also prevents access to the form
    #     # if an item does use the approval process.
    if (item.pending_submitter == current_user.initials) or (not item.pending_submitter):
        abort(403)

    # Convert the item to a dictionary to pass into form
    item_dict = item.__dict__.copy()

    # Get the alias of the item
    if not alias:
        if isinstance(name, list):
            alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        else:
            alias = getattr(item, name)

    # Initialise containers
    errors = {}
    pending_fields = []
    approved_fields = []
    mod_dict = {}

    # Get pending and approved modifications
    mods = Modifications.query.filter_by(table_name=item_name, record_id=str(item_id)). \
        filter(Modifications.status.in_(['Pending', 'Approved']))

    # Get event, i.e., CREATED or UPDATED
    pending_mod = mods.filter_by(status='Pending').first()
    if pending_mod:
        event = pending_mod.event

    # Iterate through modifications and populate dictionaries/lists
    for mod in mods:
        mod_dict[mod.field_name] = mod
        if mod.status == 'Pending':
            pending_fields.append(mod.field_name)
        else:
            approved_fields.append(mod.field_name)

    # Get required fields to display red *
    required_fields = [field.name for field in form if field.flags.required]


    # Set the route when the exit button is clicked.
    if not exit_route:
        exit_route = url_for(f"{table_name}.unlock", item_id=item_id)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            # Append user-defined fields to ignore when adding modifications
            ignore_fields = ['submit', 'communications', 'csrf_token']
            if 'ignore_fields' in kwargs.keys():
                ignore_fields += kwargs['ignore_fields']

            # initialise new data counter
            new_data = 0
            # Get the number of required fields
            n_required = len(required_fields)
            # Initialize number of required fields passed
            required_passed = 0

            form_data = form.data
            form_data.update(kwargs)
            print(form_data)
            for field in form:
                # if the form has a field name that is the same as a table property name
                if hasattr(item, field.name):
                    # Default the revision number for the modification entry to zero
                    revision = -1
                    # if there is an existing modification for this field, get that revision number
                    mod = mod_dict.get(field.name)
                    if mod:
                        revision = int(mod.revision)

                    # get the new and original values
                    new_value, new_value_text, original_value, original_value_text = get_values(item, field, form_data[field.name])
                    form_data[field.name] = new_value

                    # If the field did not previously have data, create new modification entry
                    if (original_value != new_value) and (field.name not in approved_fields) and (field.name not in ignore_fields):

                        revision += 1
                        new_data += 1

                        # If the new_value is equal to the pending modifications original value,
                        # set the modifications status to 'Reverted'. If the value is not the same
                        # as the original value, set the pending modifications status to revised.
                        if mod:
                            if new_value == mod.original_value:
                                mod.status = 'Reverted'
                            else:
                                mod.status = 'Revised'
                            mod.reviewed_by = current_user.id
                            mod.review_date = datetime.now()

                        # Create the modification item and add to table
                        modification = Modifications(
                            event=event,
                            status='Pending',
                            table_name=item_name,
                            record_id=str(item.id),
                            revision=revision,
                            field=field.label.text,
                            field_name=field.name,
                            original_value=original_value,
                            original_value_text=original_value_text,
                            new_value=new_value,
                            new_value_text=new_value_text,
                            submitted_by=current_user.id,
                            submitted_date=datetime.now(),
                        )
                        db.session.add(modification)

                    # if the new value is equal to original value i.e., the value
                    # was approved by the reviewer.
                    else:
                        # if the field is required, increment required_passed
                        if field.flags.required:
                            required_passed += 1
                        if field.name in pending_fields:
                            mod.status = 'Approved'
                            mod.reviewed_by = current_user.id
                            mod.review_date = datetime.now()

            # Set the item's new values
            for field, data in form_data.items():
                if hasattr(item, field):
                    setattr(item, field, data)

            if not alias:
                # Get the items alias
                if isinstance(name, list):
                    alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
                else:
                    alias = getattr(item, name)

            # if there is new data and the number of required fields have been approved,
            # set the status to 'Active with pending changes'
            if new_data and (required_passed == n_required):
                # item.revision = revision + 1
                item.db_status = "Active With Pending Changes"
                item.pending_submitter = current_user.initials
                message, status = Markup(f"<b>{alias}</b> now approved for use with changes pending."), "warning"

            # if there is no new data (i.e., everything has been approved)
            elif new_data == 0:
                if set_item_active:
                    item.db_status = "Active"
                    item.pending_submitter = None
                    item.communications = None
                message, status = Markup(f"<b>{alias}</b> approved with all details complete!"), "success"

            # if there is new data and not all required fields have been approved
            else:
                item.pending_submitter = current_user.initials
                message, status = Markup(f"<b>{alias}</b> will be added pending review and approval."), "warning"

            item.modify_date = datetime.now()
            item.modified_by = current_user.initials

            # Commit the session, if a duplicate value is added where there is a unique constraint,
            # raise IntegrityError and return user to the form.
            try:
                # Unlock item on form submission
                item.locked = False
                item.locked_by = None
                item.lock_date = None
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error_message = f"<b>{item_type}</b> with the following values already exists!"
                print(form)
                if hasattr(form, 'unique_fields'):
                    error_message += "<ul>"
                    for field_name in form.unique_fields:
                        field = form[field_name]
                        value = field.data
                        if field.type in ['SelectField', 'SelectMultipleField']:
                            value = dict(field.choices).get(value)
                        error_message += f"<li><b>{field.label.text}</b>: {value}</li>".replace("*", "")
                    error_message += "</ul>"

                errors = {'unique_failed': Markup(error_message)}
                form = render_form(form)
                return render()

            if custom_flash_message:
                message, status = custom_flash_message
            if display_flash_message:
                flash(message, status)

            # Redirect user after form submission. The default is to redirect to view_list.
            # if 'view', redirect them to the items view page. If 'list', redirect them to the
            # items list view.
            redirect_url = url_for(f"{table_name}.view_list")
            if "redirect" in kwargs.keys():
                if kwargs['redirect'] == 'view':
                    redirect_url = url_for(f"{table_name}.view", item_id=item.id)
                elif kwargs['redirect'] == 'list':
                    redirect_url = url_for(f"{table_name}.view_list")
                else:
                    redirect_url = kwargs['redirect']

            return redirect(redirect_url)

        else:
            kwargs.update(form.data)
            form = render_form(form, kwargs, item, mod_dict, 'Approve')
            errors = form.errors
            print(form.errors)

    # Render form
    elif request.method == 'GET':

        if item.pending_submitter == current_user.initials:
            abort(403)
        # # Get the alias of the item
        # if not alias:
        #     if isinstance(name, list):
        #         alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        #     else:
        #         alias = getattr(item, name)

        form = render_form(form, kwargs, item, mod_dict, 'Approve')

        if locking:
            # Lock item on form opening
            item.locked = True
            item.locked_by = current_user.initials
            item.lock_date = datetime.now()

        db.session.commit()

    return render()



def update_item(form, item_id, table, item_type, item_name, table_name,
                requires_approval, name, function='Update', alias=None,
                admin_only=False, locking=True,default_header=True,
                display_flash_message=True,custom_flash_message=None,
                exit_route=None, auto_approved_fields=[] , **kwargs):

    """

    Update existing item. Has both GET and POST requests.

    GET: render form template.
    POST: process form and redirect.

    Parameters
    ----------
    form (FlaskForm):
        Instance of the form to be displayed and processed.
    item_id (int):
        The id of the item to be updated.
    table (db.Model):
        The database table that will be added to.
    item_type (str):
        The plain english name (singular) to be displayed in the form header. e.g. Add Agency.
    item_name (str)
        The plain english name (plural) to be added to the modifications table i.e., Agencies.
    table_name (str):
        The snake cased module/route name for redirecting.
    requires_approval (bool):
        If the item should go through the approval process.
    name (str):
        The property of the database which is used for display (i.e., alias).
    function (str): 'Update'
        The function string.
    alias (str): None
        Set the alias manually.
    admin_only (bool): False
        Whether access to the form should be restricted to only 'Admin' and 'Owner'.
    locking (bool): True
        Whether to lock the item when the form is accessed.
    default_header (bool): True
        Shows the default header (i.e., "Update <alias>". If you want to have a custom header
        set this to False and add the custom header within the header block of the modules'
        form.html file.
    display_flash_message (bool): True
        Whether to display a flash message.
    custom_flash_message (tuple): None
        Set a custom flash message. This takes in a tuple (message, status)
        e.g. custom_flash_message = ('This is a flash message', 'success'). The
        message can also be a Markup object so you can apply HTML styling. e.g.
        custom_flash_message = (Markup('This is a <b>BOLD WORD</b>'), 'success').
        Statuses include success (green), warning (yellow), error (red)
    exit_route (str): None
        routing on "Exit" button click. Use url_for. Defaults to the returning to the item page.
    auto_approved_fields (list): Empty
        Fields that are automatically approved even if the module requires approval.
    kwargs (dict):
        Any other keyword parameters. Can be used to add non-form values (such as calculated
        values based on form input). These parameters will be available in the template.

    Returns
    -------

    BaseResponse

    """

    def render():
        # Get template from kwargs
        template = f"{table_name}/{kwargs['template']}"

        return render_template(
            template,
            form=form,
            item=item,
            item_id=item_id,
            table_name=table_name,
            item_type=item_type,
            item_name=item_name,
            function=function,
            item_dict=item_dict,
            alias=alias,
            mods=mods,
            approved_fields=json.dumps(approved_fields),
            pending_fields=json.dumps(pending_fields),
            required_fields=json.dumps(required_fields),
            errors_json=json.dumps(errors),
            errors=errors,
            default_header=default_header,
            exit_route=exit_route,
            kwargs=kwargs
        )

    print('Approved Fields: ', auto_approved_fields)
    # Get permissions of current user. If admin_only == True, and the user
    # does not have Admin or Owner permissions.
    # The first user will initially not have an account and will need to a
    # add themselves to the database thus they will not have any permissions.
    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)
    elif permissions == 'View':
        abort(403)

    # Get the item to be updated. If the item does not exist, raise 404 Not Found error.
    item = table.query.get_or_404(item_id)

    # if the item is locked and the current_user is not the person who locked it, abort
    if item.locked:
        if item.locked_by != current_user.initials:
            abort(403)

    # Convert the item to a dictionary to pass into form
    item_dict = item.__dict__.copy()

    # Get the alias of the item
    if not alias:
        if isinstance(name, list):
            alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        else:
            alias = getattr(item, name)


    # Initialise containers
    errors = {}
    pending_fields = []
    approved_fields = []
    mod_dict = {}


    # Get approved modifications. On update, there should be no pending modifications.
    mods = Modifications.query.filter_by(record_id=str(item_id),
                                         status='Approved',
                                         table_name=item_name)

    # Iterate through modifications and populate dictionaries/lists
    for mod in mods:
        mod_dict[mod.field_name] = mod
        # if mod.field == "File":
        #     mod_dict['import'] = mod
        # else:
        #     mod_dict[mod.field_name] = mod

    # Get required fields to display red *
    required_fields = [field.name for field in form if field.flags.required]

    if not exit_route:
        exit_route = url_for(f"{table_name}.unlock", item_id=item_id)

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            # Append user-defined fields to ignore when adding modifications
            ignore_fields = ['submit', 'communications', 'csrf_token']
            if 'ignore_fields' in kwargs.keys():
                ignore_fields += kwargs['ignore_fields']

            # initialise new data counter
            new_data = 0
            # Initialize number of required fields changed
            required_changed = 0

            form_data = form.data
            form_data.update(kwargs)

            for field in form:
                # if the form has a field name that is the same as a table property name
                if hasattr(item, field.name):

                    # If the module requires approval and the field is not in approved_fields
                    # set the status to pending, else set it to approved.
                    if requires_approval and field.name not in auto_approved_fields:
                        status = 'Pending'
                    else:
                        status = 'Approved'

                    # Default the revision number for the modification entry to zero
                    revision = 0

                    # if there is an existing modification for this field, get that revision number
                    mod = mod_dict.get(field.name)
                    if mod:
                        revision = int(mod.revision)
                        revision += 1

                    # get the new and original values
                    new_value, new_value_text, original_value, original_value_text = get_values(item, field, form_data[field.name])
                    form_data[field.name] = new_value

                    # If the field did not previously have data, create new modification entry
                    if (new_value != original_value) and (field.name not in ignore_fields):

                        # # Set new_value in form_data, required for SelectMultipleField
                        # form_data[field.name] = new_value

                        # If there is new data and the field is not in auto_approved_fields.
                        # increment new_data
                        if field.name not in auto_approved_fields:
                            new_data += 1

                        # if a required field has been changed, increment required_changed
                        if field.flags.required:
                            required_changed += 1

                        # if status = 'Approved' i.e., no approval required, set the reviewer and review data.
                        if status == 'Approved':
                            reviewed_by = current_user.id
                            review_date = datetime.now()
                        else:
                            reviewed_by = None
                            review_date = None

                        # if there is an existing modification for the field, set the modification
                        # of the last approved field to 'revised'
                        if mod:
                            mod.status = 'Revised'

                        # Create the modification item and add to table
                        modification = Modifications(
                            event='UPDATED',
                            status=status,
                            table_name=item_name,
                            record_id=str(item.id),
                            revision=revision,
                            field=field.label.text,
                            field_name=field.name,
                            original_value=original_value,
                            original_value_text=original_value_text,
                            new_value=new_value,
                            new_value_text=new_value_text,
                            submitted_by=current_user.id,
                            submitted_date=datetime.now(),
                            reviewed_by=reviewed_by,
                            review_date=review_date
                        )

                        db.session.add(modification)

            # Set the item's new values
            print(form_data)
            for field, data in form_data.items():
                if hasattr(item, field):
                    setattr(item, field, data)

            if not alias:
                # Get the items alias
                if isinstance(name, list):
                    alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
                else:
                    alias = getattr(item, name)
                print(name)
                print(alias)

            # if there is new data
            if new_data:
                item.modify_date = datetime.now()
                item.modified_by = current_user.initials

            message = None
            item.pending_submitter = None

            if not requires_approval:
                if table_name == 'locations':
                    prefix = "Locations: "
                else:
                    prefix = ""

                if new_data != 0:
                    message, status = Markup(f"{prefix}<b>{alias}</b> updated successfully"), "success"
                else:
                    message, status = Markup(f"{prefix}No changes made to <b>{alias}</b>."), "success"

            if requires_approval:
                if new_data:
                    item.pending_submitter = current_user.initials
                    if required_changed != 0:
                        item.db_status = "Changes Pending"
                        message, status = Markup(f"<b>{alias}</b> is now out of circulation pending approval of changes"), "warning"

                    if (new_data != 0) and (required_changed == 0):
                        item.db_status = "Active With Pending Changes"
                        message, status = Markup(f"<b>{alias}</b> has changes pending approval."), "warning"
                else:
                    message, status = Markup(f"<b>{alias}</b> updated successfully"), "success"

            # Commit the session, if a duplicate value is added where there is a unique constraint,
            # raise IntegrityError and return user to the form.
            try:
                # Unlock item on form submission
                item.locked = False
                item.locked_by = None
                item.lock_date = None
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error_message = f"<b>{item_type}</b> with the following values already exists!"
                print(form)
                if hasattr(form, 'unique_fields'):
                    error_message += "<ul>"
                    for field_name in form.unique_fields:
                        field = form[field_name]
                        value = field.data
                        if field.type in ['SelectField', 'SelectMultipleField']:
                            value = dict(field.choices).get(value)
                        error_message += f"<li><b>{field.label.text}</b>: {value}</li>".replace("*", "")
                    error_message += "</ul>"

                errors = {'unique_failed': Markup(error_message)}
                form = render_form(form)
                return render()

            if custom_flash_message:
                message, status = custom_flash_message
            if display_flash_message:
                flash(message, status)

            # Redirect user after form submission. The default is to redirect to view_list.
            # if 'view', redirect them to the items view page. If 'list', redirect them to the
            # items list view.
            redirect_url = url_for(f"{table_name}.view_list")
            if kwargs.get("redirect"):
                if kwargs['redirect'] == 'view':
                    redirect_url = url_for(f"{table_name}.view", item_id=item.id)
                elif kwargs['redirect'] == 'list':
                    redirect_url = url_for(f"{table_name}.view_list")
                else:
                    redirect_url = kwargs['redirect']

            return redirect(redirect_url)

        else:
            kwargs.update(form.data)
            form = render_form(form, kwargs, item, mod_dict)
            errors = form.errors
            print(form.errors)

    elif request.method == 'GET':

        # if not alias:
        #     # Get the alias of the item
        #     if isinstance(name, list):
        #         alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        #     else:
        #         alias = getattr(item, name)

        form = render_form(form, kwargs, item, mod_dict)

        # if locking = True, lock item.
        if locking:
            item.locked = True
            item.locked_by = current_user.initials
            item.lock_date = datetime.now()
            db.session.commit()

    return render()


def render_form(form, kwargs=None, item=None, mod_dict=None, function=None, approved_fields=None):
    """

    Sets the HTML elements of the form. If the form is being rendered for edit, approve
    or update, set the form's data using the item data.
    - Items with data will have a tooltip in the label showing modification data
    - Approved fields will be disabled
    - Pending fields will have a yellow background

    Parameters
    ----------
    form (FlaskForm): None
        Instance of the form to be displayed and processed.
    kwargs (dict): None
        dictionary of kwargs passed in through views.py.
    item (db.Model): None
        the item being edited, approved or updated.
    mod_dict (dict): None
        dictionary containing the modification objects.
    approved_fields (list): None
        list of approved field names.

    Returns
    -------
    form (FlaskForm)

    """

    # Iterate through the form's fields except for the csrf_token and submit fields.
    for field in form:
        if field.name not in ['csrf_token', 'submit']:
            # Define the default options of form element
            render_kw = {
                'class': 'form-control',  # Bootstrap form field styling
            }

            if field.type in ['DateField', 'NullableDateField']:
                render_kw['type'] = 'date'
            if field.type == 'BooleanField':
                render_kw['class'] = 'form-check-input'
            # if an item has been passed in i.e., on edit, approve or update.
            # Set the field's data with the item's data
            if item:
                if hasattr(item, field.name):
                    if field.name != 'communications':
                        field_data = getattr(item, field.name)
                        # If the field is a SelectMultipleField, convert the comma-separated string
                        # to a list. SelectMultipleField data needs to be a list
                        if field.type == 'SelectMultipleField':
                            if not isinstance(field_data, int):
                                if field_data:
                                    if ", " in field_data:
                                        field.data = field_data.split(", ")
                                    else:
                                        field.data = field_data.split("; ")
                        else:
                            field.data = field_data
                    # Set the communication field's data if in the 'Edit function'
                    elif field.name == 'communications' and function != 'Approve':
                        field.data = getattr(item, field.name)


            # if field name is in kwargs (if it isn't it will return None), set the field data with that value
            if kwargs:
                # The "is not None" cannot be removed since it will ignore blank values which is not what we want.
                if kwargs.get(field.name) is not None:
                    field.data = kwargs[field.name]

            # append any user-defined render_kw arguments provided in forms.py
            # to the render_kw dictionary
            if field.render_kw:
                for k, v in field.render_kw.items():
                    # if the parameter is class, append
                    if k == 'class':
                        if field.render_kw.get('class'):
                            render_kw['class'] += f" {field.render_kw['class']}"
                        else:
                            render_kw[k] = v
                    else:
                        render_kw[k] = v

            if kwargs:
                # if kwargs has disabled fields, disable those fields.
                if kwargs.get('disable_fields'):
                    if field.name in kwargs['disable_fields']:
                        render_kw['disabled'] = True

            # if the field is in the forms error dictionary, append the bootstrap
            # is-invalid class to highlight field red.
            if form.errors.get(field.name):
                render_kw['class'] += ' is-invalid'

            # if there is a modification for the field, set the tooltip text
            if mod_dict:
                if mod_dict.get(field.name):
                    mod = mod_dict[field.name]
                    if not mod.original_value:
                        tooltip = f"None > {mod.new_value_text}<br>"
                    else:
                        tooltip = f"{mod.original_value_text} > {mod.new_value_text}<br>"

                    tooltip += f"Submitted: {mod.submitter.initials} ({mod.submitted_date.strftime('%m/%d/%Y %H:%M')})<br>"

                    # if the field is approved, disable the field
                    if item.db_status != 'Active':
                        if mod.status == 'Approved':
                            tooltip += f"Approved: {mod.reviewer.initials} ({mod.review_date.strftime('%m/%d/%Y %H:%M')})"
                            render_kw['disabled'] = True
                            if field.type in ["SelectField", "SelectMultipleField"]:
                                render_kw['class'] += " select-disabled"

                        # if the field is pending, set the background color to yellow
                        if mod.status == 'Pending' and not render_kw.get('disabled'):
                            render_kw['style'] = "background-color: #fff3cd"
                            if field.type in ['SelectField', 'SelectMultipleField']:
                                # specific css class to handle select
                                render_kw['class'] += " select-pending"
                        # else:
                        #     render_kw['class'] += " disabled-pending"

                    # The tooltip needs to be set as the "title" parameter
                    render_kw['tooltip-text'] = tooltip

            # set the field's render_kw
            field.render_kw = render_kw

            # print(field.name, " ", field.render_kw)

    return form


def get_values(item, field, value, ignore_original_values=False, form_data=None, ):
    """

    Get an item's new value and original value. Both have a raw and user-friendly values. The purposes
    for this is that when comparing whether a items original value is the same (or different)
    For example, a SelectField's value may be stored as an integer (e.g. 3), but what the user sees
    is "California Highway Patrol". The original_value would be 3 and the original_value_text would
    be "California Highway Patrol".

    Parameters
    ----------
    item (db.Model):
        the item being edited, approved or updated.
    field (wtf.fields.Field):
        the form's field.
    ignore_original_values (bool): False
        Ignore any original data. This is primarily a work around to ignore original
        values when importing data from FA.
    form_data (dict):
        dictionary containing the new form_data.

    Returns
    -------

    new_value (str):
        the item's new value as provided by the form.
    new_value_text (str):
        the item's new value converted to user-friendly format.
    original_value (str):
        the item's new value as provided by the form.
    original_value_text (str):
        the item's original value converted to user-friendly format.

    """

    original_value = None
    original_value_text = None
    if item and not ignore_original_values:
        original_value = getattr(item, field.name) # value frmo our DB
        # if field.type not in ['DateField', 'NullableDateField']:
 
        original_value_text = original_value
     
        # else:
        #     original_value_text = original_value.strftime('%m/%d/%Y')

    new_value = value # value from FA import file
    new_value_text = new_value

    if field.type in ['HiddenField'] and isinstance(item.__table__.columns[field.name].type,DateTime):
        if new_value:
            if isinstance(new_value, str):
                try:
                    new_value = datetime.strptime(new_value, '%Y-%m-%d %H:%M:%S.%f')  # remove .%f in sqlite
                except ValueError:
                    new_value = datetime.strptime(new_value, '%Y-%m-%d %H:%M:%S')
                new_value_text = new_value.strftime('%m/%d/%Y')
            if original_value:
                original_value = original_value#.date()
                original_value_text = original_value.strftime('%m/%d/%Y')

    if field.type in ['DateField', 'NullableDateField']:
        if new_value:

            if not isinstance(new_value, datetime):  # already a datetime
                new_value = datetime.combine(new_value, datetime.min.time())

            # new_value = datetime.combine(new_value, datetime.min.time()) # → 2025-09-25 00:00:00
            new_value_text = new_value.strftime('%m/%d/%Y')
            if original_value:
                original_value = original_value
                original_value_text = original_value.strftime('%m/%d/%Y')
        else:
            new_value = None
            new_value_text = None
            if original_value:
                original_value = original_value
                original_value_text = original_value.strftime('%m/%d/%Y')






    if field.type == 'SelectField':
        original_value_text = dict(field.choices).get(original_value)
        if new_value:
            new_value_text = dict(field.choices).get(new_value)
        else:
            new_value = None
            new_value_text = None

    if field.type in ['FloatField', 'NullableFloatField']:
        if not new_value:
            new_value_text = None
        if not original_value:
            original_value_text = None

    if field.type == 'FileField':
        try:
            new_value = secure_filename(field.data.filename)
            new_value_text = new_value
        except AttributeError:
            new_value = None
            new_value_text = None

    if isinstance(new_value, list):
        if new_value:
            new_value_text = ", ".join([dict(field.choices).get(x) for x in new_value])
            new_value = ', '.join(map(str, new_value))
        else:
            new_value = None
            new_value_text = None
        if original_value:
            if ', ' in original_value:
                original_value_text = ", ".join([dict(field.choices).get(x) for x in original_value.split(", ")])
            elif "; " in original_value:
                original_value_text = ", ".join([dict(field.choices).get(x) for x in original_value.split("; ")])
            else:
                original_value_text = original_value

    if not original_value:
        original_value = None

    if not new_value:
        new_value = None

    print(f"{field.name} new: {new_value} ({type(new_value)})")
    print(f"{field.name} new_text: {new_value_text} ({type(new_value_text)})")
    print(f"{field.name} original: {original_value} ({type(original_value)})")
    print(f"{field.name} original_text: {original_value_text} ({type(original_value_text)})")

    return new_value, new_value_text, original_value, original_value_text


def lock_item(item_id, table, name, redirect_to=None):
    """

    Lock an item manually.

    Parameters
    ----------
    item_id (int):
        the id of the item to be locked.
    table (db.Model):
        the database table.
    name (str):
        the property of the item to display in flash messaging.
    redirect_to:
        the url to redirect the user to.

    Returns
    -------

    BaseResponse:
        Redirect to given URL
    """

    item = table.query.get_or_404(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    # If the item is not locked, abort 403
    if item.locked is True:
        abort(403)
    # if the current user did not lock the form or the current user does not have admin/owner permissions, abort 403
    if current_user.permissions not in ['Owner', 'Admin']:
        abort(403)

    # Set locked to False and clear locked_by and lock_date
    item.locked = True
    item.locked_by = current_user.initials
    item.lock_date = datetime.now()
    db.session.commit()

    # Flash message
    flash(Markup(f"<b>{alias}</b> locked!"), "success")

    # if no url is given for the redirect
    if not redirect_to:
        # Get the path/url of the where the request came from.
        # path will be a list of the tree after the IP address.
        # e.g. ['agencies'],  ['agencies', '26'], ['agencies','26', 'update']
        path = request.referrer[len(request.url_root):].split('/')
        if len(path) == 3:
            # if the item is being unlocked by exiting the form, redirect them to the items
            # view page. If we use request.referrer here (i.e. reload the page)
            # it will just render the form again.
            redirect_to = f"{request.url_root}{'/'.join(path[:-1])}"
        else:
            # Reload the page
            redirect_to = request.referrer

    return redirect(redirect_to)

def unlock_item(item_id, table, name, redirect_to=None):
    """

    Unlock an item manually.

    Parameters
    ----------
    item_id (int):
        the id of the item to be unlocked.
    table (db.Model):
        the database table.
    name (str):
        the property of the item to display in flash messaging.
    redirect_to: None
        the url to redirect the user to.

    Returns
    -------

    BaseResponse:
        Redirect to given URL

    """
    print(redirect_to)
    item = table.query.get_or_404(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    # If the item is not locked, abort 403
    # if item.locked is False:
    #     abort(403)
    # if the current user did not lock the form or the current user does not have admin/owner permissions, abort 403

    if item.locked:
        if item.locked_by != current_user.initials and current_user.permissions not in ['Owner', 'Admin']:
            abort(403)


    # Flash message
    if item.locked:
        flash(Markup(f"<b>{alias}</b> unlocked!"), "success")

    # Set locked to False and clear locked_by and lock_date
    item.locked = False
    item.locked_by = None
    item.lock_date = None
    db.session.commit()



    # if no url is given for the redirect
    if not redirect_to:
        # Get the path/url of the where the request came from.
        # path will be a list of the tree after the IP address.
        # e.g. ['agencies'],  ['agencies', '26'], ['agencies','26', 'update']
        path = request.referrer[len(request.url_root):].split('/')
        if len(path) == 3:
            # if the item is being unlocked by exiting the form, redirect them to the items
            # view page. If we use request.referrer here (i.e. reload the page)
            # it will just render the form again.
            redirect_to = f"{request.url_root}{'/'.join(path[:-1])}"
        else:
            # Reload the page
            redirect_to = request.referrer

    return redirect(redirect_to)


def revert_item_changes(item_id, field_name, field_value, item_name, field_type, multiple):
    """

    When the revert button on the form is clocked, get the item's previous value for that field.

    Parameters
    ----------
    item_id (int):
        the id of the item.
    field_name (str):
        the name of the field.
    field_value (str):
        the value currently in the form's the field.
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    field_type (str):
        the field's type.
    multiple (bool):
       whether the SelectField is a SelectMultipleField.

    Returns
    -------
    JSON:
        the item's previous value.
    """

    # Get the pending modification for that field
    mod = Modifications.query.filter_by(
        record_id=str(item_id),
        field_name=field_name,
        status='Pending',
        table_name=item_name
    ).first()

    # set the new_value and original_value from the modification
    new_value = mod.new_value
    original_value = mod.original_value

    # if multiple is true, convert item's data for that field to a list
    if multiple == 'true':
        field_value = ", ".join(field_value.split(','))

    # if the field_value == new_value i.e. the field has not been changed
    # set the value of the field as the original value. If the field is a
    # SelectField and the previous value is None, leave the current value
    if field_value == new_value:
        if multiple == 'true':
            value = original_value.split(', ')
        elif field_type == 'SELECT':
            if not original_value:
                value = new_value
            else:
                value = original_value
        else:
            value = original_value

    # if the the user has changed the field value, return the value which was in the
    # field when the page was rendered (i.e., the new_value).
    else:
        if multiple == 'true':
            value = new_value.split('; ')
        else:
            value = new_value

    return jsonify(value=value)


def remove_item(item_id, table, table_name, item_name, name, requires_approval=True, remove_reason=None):
    """

    Administratively remove an item. This does not delete an item from the database. It changes
    the item's status to removed. Removing an item requires approval unless the user removing an item has 'Admin' or
    'Owner' permissions.


    Parameters
    ----------
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        the property of the item to display in flash messaging.

    Returns
    -------
    BaseResponse:
        Redirect to the item's view page
    """


    item = table.query.get_or_404(item_id)
    # Get the alias for the item
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    if remove_reason is None:
        # set the item's 'remove_reason' property to the value that was submitted in the modal
        remove_reason = request.form.get('reason')
    # If there is no text abort - this prevents someone using the URL to remove the item.
    if not remove_reason:
        abort(403)

    item.remove_reason = remove_reason

    # If the user removing the item is Admin or Owner or requires_approval is False, override the review process
    if not requires_approval or current_user.permissions in ['Admin', 'Owner']:
        item.db_status = "Removed"
        item.modify_date = datetime.now()
        item.modified_by = current_user.initials
        # Clear pending_submitter and locked columns
        item.pending_submitter = None
        item.locked = None
        item.locked_by = None
        item.lock_date = None

        # Set the values for the modification entry. The modification will automatically be approved for
        # 'Admin' and 'Owner'.
        mod_status = 'Approved'
        review_date = datetime.now()
        reviewed_by = current_user.id

        flash(Markup(f"<b>{alias}</b> has been removed."), "error")


    else:
        # set the item's db_status to 'Removal pending' and update the item's modify_date and
        # modified_by properties.
        item.pending_submitter = None
        item.db_status = "Removal Pending"
        item.modify_date = datetime.now()
        item.modified_by = current_user.initials

        mod_status = 'Pending'
        review_date = None
        reviewed_by = None

        # Flash message
        flash(Markup(f'<b>{alias}</b> will be removed pending approval.'), "warning")

    # Create the modification item and add to table
    modification = Modifications(
        event='REMOVED',
        status=mod_status,
        table_name=item_name,
        record_id=str(item.id),
        revision=0,
        field_name='remove_reason',
        field="Remove Reason",
        new_value=remove_reason,
        new_value_text=remove_reason,
        submitted_by=current_user.id,
        submitted_date=datetime.now(),
        review_date=review_date,
        reviewed_by=reviewed_by
    )
    db.session.add(modification)
    db.session.commit()

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


def approve_remove_item(item_id, table, table_name, item_name, name, admin_only=True):
    """

    Approve the removal of an item.

    Parameters
    ----------
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        the property of the item to display in flash messaging.
    admin_only (bool): True
        Removal can only be approved by 'Admin' or 'Owner'.

    Returns
    -------

    BaseResponse:
        Redirect to the item's view page

    """

    if admin_only:
        if current_user.permissions not in ['Owner', 'Admin']:
            abort(403)


    item = table.query.get_or_404(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)


    if item.modified_by == current_user.initials:
        abort(403)

    # abort if the current_user was the user who marked the item for removal or the current
    # user only has view_permissions
    mod = Modifications.query.filter_by(record_id=str(item_id), event='REMOVED',
                                        status='Pending', table_name=item_name).first()

    if mod.submitter.initials == current_user.initials:
        abort(403)
    # Set the removal modification status to 'Approved' and update the reviewed_by and
    # review_date details
    if mod:
        mod.status = 'Approved'
        mod.reviewed_by = current_user.id
        mod.review_date = datetime.now()

    # Set the item's db_status to removed and update the item's modify_date and
    # modified_by properties
    item.db_status = "Removed"
    item.modify_date = datetime.now()
    item.modified_by = current_user.initials

    # Clear pending_submitter and locked columns
    item.pending_submitter = None
    item.locked = None
    item.locked_by = None
    item.lock_date = None

    db.session.commit()

    # Get number of pending and locked items for notification badge and review alert
    # if hasattr(table, 'db_status'):
    #     session['action_items'][table_name] = table.query.filter(table.db_status.not_in(ignore_statuses)).count()
    #     session['action_items'][table_name] += table.query.filter_by(locked=True).count()

    flash(Markup(f"{alias} has been removed."), "error")

    return redirect(url_for(f'{table_name}.view', item_id=item_id))

def reject_remove_item(item_id, table, table_name, item_name, name, admin_only=False):
    """

    Reject the removal of an item.

    Parameters
    ----------
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        the property of the item to display in flash messaging.
    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.

    Returns
    -------

    BaseResponse:
        Redirect to the item's view page

    """

    if admin_only:
        if current_user.permissions not in ['Owner', 'Admin']:
            abort(403)

    item = table.query.get_or_404(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    # abort if the current_user was the user who marked the item for removal or the current
    # user only has view_permissions
    if (item.modified_by == current_user.initials) or (current_user.permissions == 'View'):
        abort(403)

    mod = Modifications.query.filter_by(record_id=str(item_id), event='REMOVED',
                                        status='Pending', table_name=item_name).first()

    # Set the removal modification status to 'Rejected' and update the reviewed_by and
    # review_date details
    mod.status = 'Rejected'
    mod.review_date = datetime.now()
    mod.reviewed_by = current_user.id

    # Set the item's db_status to 'Active and update the item's modify_date and
    # modified_by properties. Clear the remove_reason property.
    item.db_status = 'Active'
    item.modify_date = datetime.now()
    item.modified_by = current_user.initials
    item.remove_reason = None
    db.session.commit()

    # Get number of pending and locked items for notification badge and review alert
    # if hasattr(table, 'db_status'):
    #     session['action_items'][table_name] = table.query.filter(table.db_status.not_in(ignore_statuses)).count()
    #     session['action_items'][table_name] += table.query.filter_by(locked=True).count()

    flash(Markup(f"<b>{alias}</b> request for removal has been rejected."), "warning")

    return redirect(url_for(f'{table_name}.view', item_id=item_id))


def restore_item(item_id, table, table_name, item_name, name):
    """

    Restore a removed item. Users with Admin or Owner permissions can only restore an item.

    Parameters
    ----------
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        the property of the item to display in flash messaging.


    Returns
    -------
    BaseResponse:
        Redirect to the item's view page

    """

    if current_user.permissions not in ['Admin','Owner']:
        abort(403)

    item = table.query.get_or_404(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    # Set item's status to Active and update modify_date and modified_properties. Clear remove_reason
    item.db_status = "Active"
    item.modify_date = datetime.now()
    item.modified_by = current_user.initials
    item.remove_reason = None

    # Add modification for the restoring of the item
    modification = Modifications(
        event='RESTORED',
        status='Approved',
        table_name=item_name,
        record_id=str(item.id),
        revision=0,
        submitted_by=current_user.id,
        submitted_date=datetime.now(),
        reviewed_by=current_user.id,
        review_date=datetime.now(),

    )

    db.session.add(modification)
    db.session.commit()

    # Get number of pending and locked items for notification badge and review alert
    # if hasattr(table, 'db_status'):
    #     session['action_items'][table_name] = table.query.filter(table.db_status.not_in(ignore_statuses)).count()
    #     session['action_items'][table_name] += table.query.filter_by(locked=True).count()

    # Flash message
    flash(Markup(f"<b>{alias}</b> restored!"), "success")

    return redirect(url_for(f'{table_name}.view_list'))


def delete_item(form, item_id, table, table_name, item_name, name, admin_only=True, keep_modifications=True,
                redirect_url=None, **kwargs):
    """

    Completely delete an item from the database.

    Users with Admin or Owner permissions can only delete an item.

    Parameters
    ----------
    form (FlaskForm):
        the form object to get the field names.
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        the property of the item to display in flash messaging.
    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.
    keep_modifications (bool): True
        When an item is deleted, keep the modifications for that item and set the record_id as the item's alias
    redirect_url (int):


    Returns
    -------

    """

    if admin_only:
        if current_user.permissions not in ['Owner', 'Admin']:
            abort(403)
    item = table.query.get_or_404(item_id)

    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    if 'request' in kwargs.keys():
        request.method = 'POST'

    if request.method == 'POST':
        mods = Modifications.query.filter_by(table_name=item_name,
                                             record_id=str(item_id))

        if keep_modifications:
            for mod in mods:
                mod.event = 'DELETED'
                mod.record_id = alias
                mod.reviewed_by = current_user.id
                mod.review_date = datetime.now()
        else:
            mods.delete()

        db.session.delete(item)
        db.session.commit()

        flash(Markup(f"<b>{alias}</b> has been permanently removed."), "error")
        if redirect_url is None:
            return redirect(url_for(f'{table_name}.view_list'))
        else:
            return redirect(redirect_url)

    return render_template('delete_confirmation.html',
                           item=item,
                           table_name=table_name,
                           item_name=item_name,
                           alias=alias,
                           )


def delete_items(table, table_name, item_name, name=None, delete_items_allowed=False):
    """

    OWNER ONLY

    WARNING: THIS IS IRREVERSIBLE. PLEASE MAKE SURE YOU EXPORT THE TABLE YOU ARE DELETING AS A BACKUP
    SO YOU CAN REIMPORT LATER.

    Delete an entire table.


    Parameters
    ----------
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    name (str):
        The property of the database which is used for display.
    delete_items_allowed (bool): False
        Whether the delete_all function can be used. If a table needs to be deleted, go to that modules
        delete_all() function in views.py and set delete_items_allowed=True.
    Returns
    -------

    """

    if current_user.permissions != 'Owner':
        abort(403)
    # delete_items_allowed = True
    if delete_items_allowed:

        # Delete modifications
        Modifications.query.filter_by(table_name=item_name).delete()
        # Delete items in the table
        table.query.delete()
        db.session.commit()
    else:
        flash("This function has been disabled. If you wish to delete this table, please see the development team.", 'error')

    return redirect(url_for(f'{table_name}.view_list'))


def import_items(form, table, table_name, item_name, df=None, add_form=None,
                 filename=None, savename=None,name=None, dtype=None, html_file=None,
                 default_header=True, file_modification=True, admin_only=True, redirect_url=None):
    """
    Import items from a comma-separated value (.csv) file into the database.
    Headers in the import file need to match the db.Model's properties.

    Imported files are saved in the LIMS' file system:
    ../lims/static/filesystem/imports.

    Parameters
    ----------
    form (FlaskForm):
        The import form located in lims/forms.py
    table (db.Model):
        the database table.
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    df (DataFrame): None
        the .csv file imported as pandas DataFrame. If None, the dataframe is generated from the imported file.
        If you need to process the dataframe before import, do this within import_file() in the module's views.py
    filename (str): None
        the imported file's file name.
    savename (str): None
        the name used to save the file. This the filename + "_YYYYMMDDHHmm"
    name (str):
        The property of the database which is used for display.
    dtype (dict):
        dictionary containing the header names and corresponding data type.
    redirect_url (str or url_for): None
        Url to redirect form after submission or on exit.
    Returns
    -------

    """
    # Set default route for when the exit button is clicked as the request referrer
    # Otherwise set to it to the redirect_url if not None.
    exit_route = request.referrer
    if redirect_url:
        exit_route = redirect_url

    if admin_only:
        if current_user.permissions not in ['Admin', 'Owner']:
            abort(403)

    # Set the folder to store imports and create directory if it doesn't exist
    import_path = os.path.join(current_app.config['FILE_SYSTEM'], 'imports')
    os.makedirs(import_path, exist_ok=True)

    errors = {}
    kwargs = {}
    required_fields = ['file']

    fields = []
    if add_form:
        fields = [field.name for field in add_form]

    print(fields)

    if request.method == 'POST':
        if form.validate_on_submit():

            float_cols_to_cast_as_str = [('scope','limit_of_detection'), ('assays','sample_volume')]

            # Get the import file
            f = form.file.data
            # Get the file's name
            if not filename:
                filename = f.filename
            # Create the name to save the file as
            if not savename:
                savename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
            # Save the .csv file in the "imports" folder of the filesystem
            path = os.path.join(import_path, savename)
            # If no dataframe is passed
            if not isinstance(df, pd.DataFrame):
                f.save(path)
                # Read the csv file
                if table_name in ['tests', 'batch_constituents']:
                    df = pd.read_csv(path, dtype=dtype, keep_default_na=False, na_values=[''])
                else:
                    df = pd.read_csv(path, dtype=dtype)

                for tbl,col in float_cols_to_cast_as_str:
                    if tbl == table_name and col in df.columns:
                        print(f"converting {tbl} {col} to a str")
                        df[col] = df[col].apply(lambda x: f"{x:.15g}" if pd.notnull(x) else None)
                        
            if '_sa_instance_state' in df.columns:
                df.drop('_sa_instance_state', axis=1, inplace=True)

            # Reorder df based on decreasing 'id' if id column in df
            if 'id' in df.columns:
                df.sort_values(by='id', inplace=True)
            else:
                next_id = table.get_next_id()
                df['id'] = range(next_id, next_id+len(df))

            date_cols = []
            # Get column (name and types) data for table. when importing a pandas dataframe, empty cells
            # are represented as nan (np.nan) and cannot be imported into the database. This converts np.nans
            # To the correct null value for the data type.
            inst = inspect(table)
            columns = [x for x in inst.mapper.columns]

            for column in columns:
                if column.name in df.columns:
                    # if the column
                    # if isinstance(column.type, Integer):
                    #     df[column.name].replace(np.nan, None, inplace=True)
                    if isinstance(column.type, DateTime):
                        df[column.name] = pd.to_datetime(df[column.name], errors='ignore')
                        date_cols.append(column.name)
                    # if isinstance(column.type, String):
                    #     # df[column.name].fillna("", inplace=True)
                    #     df[column.name].replace(np.nan, None, inplace=True)
                    if isinstance(column.type, Boolean):
                        df[column.name].fillna(False, inplace=True)
                    # if isinstance(column.type, Text):
                    #     df[column.name].replace(np.nan, None, inplace=True)

            field_data = {}
            # if the imported table does not already have db_status, create_date or created_by columns,
            # set them as the current time and submitting user, respectively.
            if 'db_status' not in df.columns:
                field_data['db_status'] = 'Active'
            if 'create_date' not in df.columns:
                field_data['create_date'] = datetime.now()
            if 'created_by' not in df.columns:
                field_data['created_by'] = current_user.initials

            # Iterate through the df rows
            # for idx, row in df.iterrows():
            #     # only add rows to the database if id is not already present
            #     if not table.query.get(row['id']):
            #         item_dict = {}
            #
            #         # If the column is a date column, set null values to None
            #         for col, val in row.iteritems():
            #             if pd.isnull(val):
            #                 val = None
            #             if isinstance(val, str):
            #                 val = val.replace("\r\n", '<br>')
            #             # Add the value to item_dict with the column as the key
            #             item_dict[col] = val
            #         field_data.update(item_dict)
            #         item = table(**field_data)
            #
            #         # if the table has data, get the id of the most recent entry and increment by 1,
            #         # else start the id at 1 and increment
            #         # if row['id']:
            #         #     record_id = row['id']
            #         # elif table.query.count():
            #         #     record_id = table.query.order_by(table.id.desc()).first().id + 1
            #         # else:
            #         #     record_id = table.query.count() + 1
            #
            #         record_id = str(row['id'])
            #
            #         modification = Modifications(
            #             event='IMPORTED',
            #             # status='Approved',
            #             status="Imported",
            #             table_name=item_name,
            #             record_id=record_id,
            #             revision=0,
            #             field="File",
            #             field_name="file_name",
            #             original_value=filename,
            #             original_value_text=filename,
            #             new_value=savename,
            #             new_value_text=savename,
            #             submitted_by=current_user.id,
            #             submitted_date=datetime.now(),
            #             reviewed_by=current_user.id,
            #             review_date=datetime.now()
            #         )
            #         db.session.add(modification)
            #         db.session.add(item)
            #
            #         if name:
            #             # Restore id to deleted mods
            #             alias = row[name]
            #             mods = Modifications.query.filter_by(table_name=item_name, record_id=alias)
            #             if mods.count():
            #                 for mod in mods:
            #                     mod.record_id = row['id']

            for idx, row in df.iterrows():

                item_dict = {}
                record_id = str(row['id'])
                item = table.query.get(int(row['id']))
                # If the column is a date column, set null values to None
                for col, val in row.iteritems():
                    if pd.isnull(val):
                        val = None
                    if isinstance(val, str):
                        val = val.replace("\r\n", '<br>')
                    # Add the value to item_dict with the column as the key
                    item_dict[col] = val

                    if col in fields:
                        field = add_form[col]
                        new_value, new_value_text, original_value, original_value_text = get_values(item, field, val)

                        if "date" in col and new_value:
                            new_value = new_value.date()

                        new_data = True
                        if new_value == original_value:
                            new_data = False
                        if new_data:
                            revision = Modifications.get_next_revision(item_name, record_id, field.name)

                            prev_mod = Modifications.query.filter_by(
                                table_name=item_name,
                                record_id=record_id,
                                field_name=field.name,
                                revision=revision - 1
                            ).first()

                            if prev_mod:
                                prev_mod.status = 'Revised'

                            modification = Modifications(
                                event='IMPORTED',
                                status="Imported",
                                table_name=item_name,
                                record_id=record_id,
                                revision=revision,
                                field=field.label.text,
                                field_name=field.name,
                                original_value=original_value,
                                original_value_text=original_value_text,
                                new_value=new_value,
                                new_value_text=new_value_text,
                                submitted_by=current_user.id,
                                submitted_date=datetime.now(),
                                reviewed_by=current_user.id,
                                review_date=datetime.now()
                            )
                            db.session.add(modification)

                    if not item:
                        field_data.update(item_dict)
                        item = table(**field_data)
                        db.session.add(item)
                    else:
                        setattr(item, col, val)

                if file_modification:
                    modification = Modifications(
                        event='IMPORTED',
                        # status='Approved',
                        status="Imported",
                        table_name=item_name,
                        record_id=record_id,
                        revision=0,
                        field="File",
                        field_name="file_name",
                        original_value=filename,
                        original_value_text=filename,
                        new_value=savename,
                        new_value_text=savename,
                        submitted_by=current_user.id,
                        submitted_date=datetime.now(),
                        reviewed_by=current_user.id,
                        review_date=datetime.now()
                    )
                    db.session.add(modification)

                if name:
                    # Restore id to deleted mods
                    alias = row[name]
                    mods = Modifications.query.filter_by(table_name=item_name, record_id=alias)
                    if mods.count():
                        for mod in mods:
                            mod.record_id = row['id']

            if not redirect_url:
                redirect_url = url_for(f'{table_name}.view_list')

            db.session.commit()
            flash(Markup(f"<b>{filename}</b> successfully imported!"), "success")
            return redirect(redirect_url)
        else:
            errors = form.errors
            form = render_form(form, kwargs)

    elif request.method == 'GET':
        form = render_form(form, kwargs)

    if not html_file:
        html_file = 'import.html'

    return render_template(html_file,
                           form=form,
                           function='Import',
                           item_name=item_name,
                           errors=json.dumps(errors),
                           pending_fields=json.dumps([]),
                           required_fields=json.dumps(required_fields),
                           default_header=default_header,
                           exit_route=exit_route,
                           )


def export_items(table, admin_only=False):
    """

    Exports the database table to .csv format. The file name is the
    __tablename__ property appended with the current datetime.

    File is sent to the downloads folder in the browser.

    Parameters
    ----------
    table (db.Model):
        the database table.
    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.

    Returns
    -------

    send_file (Response);

    """

    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)

    # Set the folder to store exports and create directory if it doesn't exist
    export_path = os.path.join(current_app.config['FILE_SYSTEM'], 'exports')
    os.makedirs(export_path, exist_ok=True)


    if table.__tablename__ == 'cases' and permissions != 'Admin':
        # Raw SQL export without touching encryption logic
        sql = text("SELECT * FROM cases")
        result = db.session.execute(sql)
        query = result.mappings().all()
        df = pd.DataFrame(query)
    else:
        df = pd.DataFrame([item.__dict__ for item in table.query])

    # Create pandas dataframe from all items in the table
    # df = pd.DataFrame([item.__dict__ for item in table.query])

    inst = inspect(table)
    # Get the property tables
    columns = [x.name for x in inst.mapper.columns]
    # for i in inspect(table).mapper.columns:
    #     print(i.name)
    #     if len(list(i.foreign_keys)) != 0:
    #         print(list(i.foreign_keys)[0].column.table)

    # Move the id column to the start of the dataframe
    idx = columns.index('id')
    columns.pop(idx)
    columns.insert(0, 'id')
    df = df[columns]

    if 'case_id' in df.columns:
        rows = db.session.execute(text("SELECT id AS case_id, case_number FROM cases")).mappings().all()
        case_map = {r['case_id']: r['case_number'] for r in rows}
        df['Case Number (DELETE)'] = df['case_id'].map(case_map)

        cols = [c for c in df.columns if c != 'Case Number (DELETE)']
        cols.insert(1, 'Case Number (DELETE)')
        df = df[cols]

    if 'test_id' in df.columns:
        rows = db.session.execute(text("SELECT id, test_id, test_name FROM tests")).mappings().all()
        test_id_map = {r['id']: r['test_id'] for r in rows}
        test_name_map = {r['id']: r['test_name'] for r in rows}

        df['Test ID (DELETE)'] = df['test_id'].map(test_id_map)
        df['Test Name (DELETE)'] = df['test_id'].map(test_name_map)

        cols = [c for c in df.columns if c != 'Test ID (DELETE)']
        cols.insert(2, 'Test ID (DELETE)')
        cols.insert(3, 'Test Name (DELETE)')
        df = df[cols]

    # Sort the dataframe based on descending id
    df.sort_values(by='id', ascending=False, inplace=True)
    # Get the name of the table
    name = table.__tablename__
    # Save the .csv in the export folder in the LIMS file_system
    path = os.path.join(export_path, f'{name}.csv')
    df.to_csv(path, index=False, date_format='%m/%d/%Y %H:%M')

    return send_file(path,
                     mimetype='"text/csv"',
                     as_attachment=True,
                     download_name=f'{name}_{datetime.now().strftime("%Y%M%d%H%M")}.csv'
                     )


def attach_items(form, item_id, table, item_name, table_name, name, alias=None,
                 description=None, source=None, admin_only=False, default_header=True, redirect_url=None, file_path = None, pdf_path= None):
    """

    Add attachments to an item. The attachments folder is sub-divided into each item_type/module
    which is further divided into folders per item_id. Files are saved into the item_id's folder
    under the relevant item_type.

    Folders are only created for an item_type/module or item_id when necessary.

    Multiple files can be attached at once and any file type can be added as an attachments

    Parameters
    ----------
    form (FlaskForm):
        the instance of the Attachment form in lims/forms.py.
    item_id (int):
        the id of the item.
    table (db.Model):
        the database table.
    item_name (str):
        the plain English name of the item (e.g. Agencies, Case Types).
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    name (str):
        The property of the database which is used for display.
    description (str): None
        Description to add to the form. If None, the form description will be added if any.
    source (str): None
        Source (i.e. module) that the attachment is coming from.
    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.
    default_header (bool): True
        Whether to use the default header i.e., "Attach files to <alias>".
    redirect_url (str or url_for): None
        Url to redirect form after submission or on exit.
    Returns
    -------

    """
    
    # Set default route for when the exit button is clicked as the request referrer
    # Otherwise set to it to the redirect_url if not None.
    exit_route = request.referrer
    if redirect_url:
        exit_route = redirect_url

    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)

    item = table.query.get(item_id)
    if not alias:
        if isinstance(name, list):
            alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
        else:
            alias = getattr(item, name)

    alias = str(alias)

    # Get attachment types based on the table_name
    form.type_id.choices = [(item.id, item.name) for item in AttachmentTypes.query.filter(
        AttachmentTypes.source == item_name, AttachmentTypes.db_status != 'Removed')]
    form.type_id.choices += [(item.id, item.name) for item in AttachmentTypes.query.filter(
                                AttachmentTypes.source == 'Global', AttachmentTypes.db_status != 'Removed')]
    form.type_id.choices.insert(0, (0, 'Please select a type'))

    required_fields = json.dumps([field.name for field in form if field.flags.required])
    kwargs = {}
    errors = {}
    # Set the folder to store exports and create directory if it doesn't exist
    attachments_path = os.path.join(current_app.config['FILE_SYSTEM'], 'attachments')
    os.makedirs(attachments_path, exist_ok=True)

    # If the item_type/module does not have a folder in the attachments folder, create a folder for
    # that item_type/module
    modules_with_folders = [Path(file).name for file in glob.glob(f"{attachments_path}/*")]
    table_attachments_path = os.path.join(attachments_path, item_name)
    if table_name not in modules_with_folders:
        os.makedirs(table_attachments_path, exist_ok=True)

    # If there is no folder corresponding to the item_id within that modules file,
    # create the folder.
    item_attachments_path = os.path.join(table_attachments_path, str(item_id))
    items_with_attachments = [Path(file).name for file in glob.glob(f"{item_attachments_path}/*")]
    if item_id not in items_with_attachments:
        os.makedirs(item_attachments_path, exist_ok=True)

    # initialise default field_data
    field_data = {'db_status': 'Active',
                  'create_date': datetime.now(),
                  'created_by': current_user.initials,
                  'revision': 0,
                  }

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            
            if not file_path and not request.files.getlist('files'):
                form.files.errors.append('You must upload at least one file if file_path is not provided.')
                kwargs.update(form.data)
                form = render_form(form, kwargs)
                errors = form.errors
                return render_template(f'attach.html',
                        form=form,
                        item=item,
                        table_name=table_name,
                        item_name=item_name,
                        function='Attach',
                        alias=alias,
                        pending_fields=[],
                        approved_fields=[],
                        required_fields=json.dumps(required_fields),
                        errors=errors,
                        errors_json=json.dumps(errors),
                        default_header=default_header,
                        exit_route=exit_route,
                        file_path=file_path
                        )

            
            # If description is not passed into the function use form data, if any
            if not description:
                if form.description.data:
                    description = form.description.data
            # If source is not passed into the function use the item_name
            if not source:
                source = item_name

            # Replace characters in alias
            replace_dict = {
                ' | ': '_',
                ' ': '_',
                '/': '-'
            }

            for k, v in replace_dict.items():
                alias = alias.replace(k, v)
            
            files = []

            # print(file_path)
            # print(pdf_path)
            if file_path:

                pdf_path = str(pdf_path).replace(".csv", ".pdf")

                if os.path.exists(file_path):
                    convert_csv_to_pdf(file_path, pdf_path)
                    os.remove(file_path)
                    files = [pdf_path]  # Use the PDF now

            else:
                files = request.files.getlist('files')

            for file in files:
                att_type = AttachmentTypes.query.get(form.type_id.data).name

                if isinstance(file, str):
                    # This is a real file_path from disk
                    fname = os.path.basename(file)
                    fname = fname.replace('#', '-')
                    alias = alias.replace("->", "__").replace(" ", "")
                    save_name = f"Attachment-{source}-{att_type}-{alias}_{fname}"
                    path = os.path.join(item_attachments_path, save_name)
                    shutil.copy(file, path)
                else:
                    # This is a file uploaded via form (werkzeug FileStorage)
                    fname = file.filename.replace('#', '-')
                    alias = alias.replace("->", "__").replace(" ", "")
                    save_name = f"Attachment-{source}-{att_type}-{alias}_{fname}"
                    path = os.path.join(item_attachments_path, save_name)
                    file.save(path)

                item_dict = {
                    'table_name': item_name,
                    'record_id': item_id,
                    'name': fname,
                    'save_name': save_name,
                    'path': path,
                    'description': description,
                    'type_id': form.type_id.data,
                    'source': source,
                }

                item_dict.update(field_data)
                item = Attachments(**item_dict)
                db.session.add(item)
                db.session.commit()

            if not redirect_url:
                redirect_url = url_for(f'{table_name}.view', item_id=item_id)

            return redirect(redirect_url)

        else:
            print(form.errors)
            kwargs.update(form.data)
            form = render_form(form, kwargs)
            errors = form.errors

    elif request.method == 'GET':
        form = render_form(form)
    
    return render_template(f'attach.html',
                           form=form,
                           item=item,
                           table_name=table_name,
                           item_name=item_name,
                           function='Attach',
                           alias=alias,
                           pending_fields=[],
                           approved_fields=[],
                           required_fields=json.dumps(required_fields),
                           errors=errors,
                           errors_json=json.dumps(errors),
                           default_header=default_header,
                           exit_route=exit_route,
                           file_path=str(file_path).replace('.csv', '.pdf') if file_path else None
                           )



def export_item_attachments(table, item_name, item_id, name, admin_only=False):
    """

    Parameters
    ----------
    table
    item_name
    item_id
    name (str):

    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.

    Returns
    -------

    """

    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner']:
            abort(403)

    temp_path = os.path.join(current_app.config['FILE_SYSTEM'], 'temp')
    os.makedirs(temp_path, exist_ok=True)
    # Remove any folders in the temp folder
    tmp_zip_folders = glob.glob(f"{temp_path}\*.zip")
    for folder in tmp_zip_folders:
        os.remove(folder)

    item = table.query.get(item_id)
    if isinstance(name, list):
        alias = " - ".join([getattr(item, x) for x in name if getattr(item, x)])
    else:
        alias = getattr(item, name)

    output_path = os.path.join(temp_path, f"{alias}")
    os.makedirs(output_path, exist_ok=True)

    # Attachments
    attachments_path = Path(os.path.join(current_app.config['FILE_SYSTEM'], 'attachments', item_name, str(item_id)))

    for file in glob.glob(f"{attachments_path}\*"):
        shutil.copy(file, output_path)

    # Services attachments
    service_ids = [x for x in Services.query.filter_by(equipment_type=item_name, equipment_id=item.id)]

    if service_ids:
        for service in service_ids:
            service_name = f"Service {service.service_date.strftime('%m-%d-%Y')} - {service.service_types}"
            service_folder = os.path.join(output_path, service_name)

            service_attachments_path = Path(os.path.join(
                current_app.config['FILE_SYSTEM'],
                'attachments',
                'services',
                str(service.id)
            ))

            files = glob.glob(f"{service_attachments_path}\*")
            if len(files):
                os.makedirs(service_folder, exist_ok=True)
                for file in files:
                    shutil.copy(file, service_folder)

    # Zip file
    shutil.make_archive(output_path, 'zip', output_path)

    # Remove folder
    shutil.rmtree(output_path, onerror=lambda func, path, _: (os.chmod(path, stat.S_IWRITE), func(path)))

    export_path = os.path.join(current_app.config['FILE_SYSTEM'], 'exports')
    os.makedirs(export_path, exist_ok=True)

    return send_file(f"{output_path}.zip",
                     as_attachment=True,
                     download_name=f'{alias}.zip')


def view_items(table, item_name, item_type, table_name, length=100, items=None, template_file=None,
               filter_message=None, order_by=None, admin_only=False, view_only=False, show_default_alerts=True,
               normal_alerts=None, warning_alerts=None, danger_alerts=None,
               delete_ok=False, add_item_button=True, export_buttons=True, import_file_button=True,
               id_column=True, delete_column=True, locked_column=True, create_date_column=True,
               created_by_column=True, modify_date_column=True, modified_by_column=True,
               remove_reason_column=True, pending_submitter_column=True, db_status_column=True, **kwargs):

    """

    View the list of items in a database table

    Parameters
    ----------
    table (db.Model):
        the database table.
    item_name (str):
        the plain English plural name of the item (e.g. Agencies, Case Types).
    item_type (str):
         the plain English singular name of the item (e.g. Agency, Case Type)
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    length (int): 100
        the number of items to load per page.
    items (SQLAlchemy.Query): None
        custom subset of the table to display.
    template (str): None
        which template HTML file to use. If None, Default is list.html.
    order_by (list): None
        apply custom sorting to the database table. Sorted by id in descending order by
        default. This argument takes a list of column names in the order you wish for them
        to be sorted. i.e.  ['case_status', 'last_name'].By default, this will assort the
        columns in ascending order. You can sort in descending order by adding "desc" or "DESC"
        to the column name. i.e. "case_status DESC" or "case_status desc".
    admin_only (bool): False
        Whether the list view only accessible by users with permissions of 'Admin' or 'Owner'.
    view_only (bool): False
        Whether the user can add items from the list view.
    show_default_alerts: True:
        whether to show the default alerts.
    normal_alerts (List): None
        List of tuples containing (url_for, number, text) to display in the "normal" (i.e., blue) alert box.
        E.g., (url_for('cases.view_list', query='needs-tests'), 5, 'that need test addition')
        will create an alert that says "<link>5 items<link> that need test additions". Where
        clicking on "5 items" will filter the database baseed on the 'needs-test' query.
    warning_alerts (List): None
        Similar to normal_alerts but will display the alerts in a warning alerts box (yellow box).
    danger_alerts (List): None
        Similar to normal_alerts but will display the alerts in a danger alerts box (red box).
    delete_ok (bool): False
        whether to show the delete button to users with "User" permissions.
    add_item_button (bool): False
        Whether to show the Add <item_type> button. Can be turned off for join tables
        i.e. Modifications, CommentInstances, etc.
    export_buttons (bool): True
        Whether to show the Export button.
    import_file_button (bool): True
        Whether to include the Import <item_name> button.
    id_column (bool): True
        show the "ID" column.
    delete_column (bool): True
        show the "Delete" column.
    locked_column (bool): True
        show the "Locked" column.
    create_date_column (bool): True
        show the "Created Date" column.
    created_by_column (bool): True
        show the "Created By" column.
    modify_date_column (bool): True
        show the "Modify Date" column.
    modified_by_column (bool): True
        show the "Modified By" column.
    remove_reason_column (bool): True
        Show the "Remove Reason" column.
    pending_submitter_column (bool): True
        Show the  "Pending Submitter" column.
    db_status_column (bool): True
        Show the "DB Status" column.
    kwargs (dict):
        custom arguments to be accessible in the list view.

    Returns
    -------

    """

    # Get permissions of current user. If admin_only == True, and the user
    # does not have Admin or Owner permissions, abort.
    permissions = current_user.permissions
    if admin_only:
        if permissions not in ['Admin', 'Owner', 'ADM-Management']:
            abort(403)
    elif permissions == 'View':
        abort(403)

    # By default, the number of items per page is based on what is passed into
    # the length parameter of this function. That length is overriden when length
    # is provided through the length selection form (i.e. Show X entries per page)
    # on the view list or as an argument in the URL.
    if request.form.get('length'):
        length = request.form.get('length', type=int)
    if request.args.get('length'):
        length = request.args.get('length', type=int)

    # Can be deleted after refactoring kwargs['length'] to length in list.html
    kwargs['length'] = length
    # Filter the table for pending or locked items
    query = request.args.get('query')
    query_type = request.args.get('query_type')
    if not items:
        if query == 'pending':
            items = table.query.filter(table.db_status.not_in(ignore_statuses))
            filter_message = Markup('You are currently viewing <b>items that require approval</b>')
        elif query == 'pending-by-user':
            items = table.query.filter_by(pending_submitter=current_user.initials)
            filter_message = Markup('You are currently viewing <b>items submitted by you that require approval</b>')
        elif query == 'removal-pending':
            items = table.query.filter_by(db_status='Removal Pending')
            filter_message = Markup('You are currently viewing <b>items with removal requiring approval</b>')
        elif query == 'locked':
            items = table.query.filter_by(locked=True)
            filter_message = Markup('You are currently viewing <b>locked items</b>')
        elif query == 'locked-by-user':
            items = table.query.filter_by(locked_by=current_user.initials)
            filter_message = Markup('You are currently viewing <b>items locked by you</b>')
        elif query == 'non-obsolete':
            items = table.query.filter(table.status_id != 4)
            filter_message = Markup('You are currently viewing <b>non-obsolete items</b>')
        elif query == 'removed':
            items = table.query.filter_by(db_status='Removed')
            filter_message = Markup('You are currently viewing <b>removed items</b>')
        elif query == 'finalized':
            items = table.query.filter_by(db_status='Finalized')
            filter_message = Markup('You are currently viewing <b>active items</b')
        else:
            try:
                items = table.query.filter(table.db_status != 'Removed')
            except AttributeError:
                items = db.session.query(table)

    # if custom sorters are provided, create the order_by statement
    if order_by:
        order_by = text(", ".join(map(str, order_by)))
    else:
        order_by = table.id.desc()

    # Get the requested page number
    page = request.args.get('page', 1, type=int)
    # If length == -1, show all items on a single page, else show only the items
    # defined in the length variable. Sort/order the items according to the order_by
    # statement.
    if length == -1:
        items = items.order_by(order_by).paginate(page=page, per_page=len(items.all()), max_per_page=None)
    else:
        items = items.order_by(order_by).paginate(page=page, per_page=length, max_per_page=None)

    ### ALERTS

    normal_alerts_lst = []
    warning_alerts_lst = []
    danger_alerts_lst = []

    removed_items = 0


    # Default NORMAL alerts (pending and locked)
    # n_pending = 0
    if show_default_alerts:
        if hasattr(table, 'db_status'):
            n_pending = table.query.filter(table.db_status.not_in(ignore_statuses)).count()
            n_user_pending = table.query.filter_by(pending_submitter=current_user.initials).count()
            if n_pending:
                pending_alerts = [(url_for(f"{table_name}.view_list", query='pending'), n_pending, Markup('that <b>require approval</b>'))]
                if n_user_pending:
                    pending_alerts.append((url_for(f"{table_name}.view_list", query='pending-by-user'), n_user_pending, Markup('<b>submitted by you</b>')))
                normal_alerts_lst.append(pending_alerts)


            n_pending_removal = table.query.filter_by(db_status='Removal Pending').count()
            if n_pending_removal:
                danger_alerts_lst.append(
           [(url_for(f"{table_name}.view_list", query='removal-pending'), n_pending_removal, Markup('with <b>removal requiring approval</b>'))]
                )

            # Get the number of removed items
            removed_items = table.query.filter_by(db_status='Removed').count()

        # Get the number of locked items
        # n_locked = 0


        if hasattr(table, 'locked'):
            n_locked = table.query.filter_by(locked=True, db_status='Active').count()
            n_user_locked = table.query.filter_by(locked_by=current_user.initials, db_status='Active').count()
            if n_locked:
                locked_alerts = [
                    (url_for(f"{table_name}.view_list", query='locked'), n_locked, Markup('that are <b>locked</b>'))]
                if n_user_locked:
                    locked_alerts.append((url_for(f"{table_name}.view_list", query='locked-by-user'), n_user_locked,
                                          Markup('<b>locked by you</b>')))
                normal_alerts_lst.append(locked_alerts)

              
    if normal_alerts:
        # Only add custom alerts if not 0
        normal_alerts_lst += [[x] for x in normal_alerts if x[1]]
    # Default WARNING Alerts
    if warning_alerts:
        # Only add custom alerts if not 0
        warning_alerts_lst += [[x] for x in warning_alerts if x[1]]
    # Default DANGER Alerts
    if danger_alerts:
        # Only add custom alerts if not 0
        danger_alerts_lst += [[x] for x in danger_alerts if x[1]]

    alerts = {
        'primary': normal_alerts_lst,
        'warning': warning_alerts_lst,
        'danger': danger_alerts_lst
    }

    print(f'ALERTS: {alerts.items()}')


    if not template_file:
        template_file = f'{table_name}/list.html'

    print(f"{current_user.initials} opened {item_name} - {datetime.now()}")
    return render_template(
        template_file,
        table_name=table_name,
        item_type=item_type,
        items=items,
        view_only=view_only,
        delete_ok=delete_ok,
        add_item_button=add_item_button,
        import_file_button=import_file_button,
        export_buttons=export_buttons,
        id_column=id_column,
        delete_column=delete_column,
        locked_column=locked_column,
        create_date_column=create_date_column,
        created_by_column=created_by_column,
        modify_date_column=modify_date_column,
        modified_by_column=modified_by_column,
        remove_reason_column=remove_reason_column,
        pending_submitter_column=pending_submitter_column,
        db_status_column=db_status_column,
        length=length,
        item_name=item_name,
        query=query,
        query_type=query_type,
        filter_message=filter_message,
        db=db,
        permissions=permissions,
        today=today,
        within30d=within30d,
        alerts=alerts,
        removed_items=removed_items,
        kwargs=kwargs,
    )


def view_item(item, alias, item_name, table_name, template_file=None, admin_only=False,
              view_only=False, creator_only_update=False, default_header=True, default_buttons=True,
              add_comment_button=True, show_comments=True, show_attachments=True, show_modifications=True,
              custom_attachments=None, export_attachments=True, **kwargs):
    """

    View the item page. By default, attachments and modifications are shown.

    If a related table is to be shown (e.g. when viewing an agency, show all divisions
    and personnel for that agency), pass the query object as a kwarg.

    Example:
        divisions = Divisions.query.filter_by(agency_id=agency_id)
        personnel = Personnel.query.filter_by(agency_id=agency_id)

        view_item(item, alias, item_name, table_name,
        divisions=divisions, personnel=personnel
        )

    Parameters
    ----------
    item (db.Model):
        the item
    alias (str):
        the name of the item.
    item_name (str):
        the plain English plural name of the item (e.g. Agencies, Case Types).
    table_name (str):
        The snake cased module/route name for redirecting (i.e. 'agencies', 'case_types').
    template_file (str): None
        The html file to use for rendering.
    admin_only (bool): False
        Item view only accessible by users with permissions of admin-level permissions.
    view_only (bool): False
       User can interact with the item.
    creator_only_update: False
        Only the creator can update the item.
    default_header (bool): True
        Use the default header text (i.e. alias)
    default_buttons (bool): True
        Show default buttons (Add/Update, Attach, Remove, Delete, Lock/Unlock.
    add_comment_button (bool): True
        Show the "Add Comment" button.
    show_comments (bool): True
        show the comments table.
    show_attachments (bool): True
        Show the attachments table.
    show_modifications (bool): True:
        Show the modifications table.
    custom_attachments (Query): None
        Custom attachment query.
    export_attachments (bool): True
        Add buttons to allow the exporting of attachments.
    kwargs (dict):
        custom keyword arguments to be accessible in the list view.

    Returns
    -------

    BaseResponse

    """

    # Get permissions of current user. If admin_only == True, and the user
    # does not have Admin or Owner permissions, abort.
    permissions = current_user.permissions
    if permissions not in ['Admin', 'Owner', 'ADM-Management'] and admin_only:
        abort(403)
    elif permissions == 'View':
        abort(403)

    # if not view_only:
    #     view_only = request.args.get('view_only', type=bool)

    services = Services.query.filter_by(equipment_type=item_name, equipment_id=item.id).order_by(Services.service_date.desc())

    attachments = custom_attachments
    if show_attachments and not custom_attachments:
        # Get the attachments for the item
        # Get the service ids for the item
        service_ids = [x.id for x in Services.query.filter_by(equipment_type=item_name, equipment_id=item.id)]
        print(service_ids)
        # Create query expressions. Gets attachments for that specific item and any attachments to linked services
        # Only relevant for resources, will be ignored for any other modules.
        expressions = (
            sa.and_(Attachments.record_id == item.id, Attachments.table_name == item_name),
            sa.and_(Attachments.table_name == 'Services', Attachments.record_id.in_(service_ids))
        )
        attachments = Attachments.query.filter(sa.or_(*expressions)).order_by(Attachments.create_date.desc())


    # Comments
    comments = CommentInstances.query.filter_by(comment_item_type=item_name, comment_item_id=item.id)

    modifications = Modifications.query.filter_by(record_id=str(item.id), table_name=item_name).order_by(Modifications.id.desc())
    pending_mods = modifications.filter_by(status='Pending').all()
    pending_fields = json.dumps([item.field_name for item in pending_mods])
    # Generate modification tooltips (hover behaviour) for item fields
    tooltip_mods = modifications.filter(Modifications.status.in_(['Pending', 'Approved', 'Imported']))
    mod_tooltips = {}
    for mod in tooltip_mods:
        # if mod.field != "Reason":
        #     if mod.original_value_text == "":
        #         tooltip = f"{mod.new_value_text}<br>"
        #     elif mod.new_value_text == "":
        #         tooltip = f"{mod.original_value_text} > [None]<br>"
        #     else:
        #         tooltip = f"{mod.original_value_text} > {mod.new_value_text}<br>"
        #
        #     tooltip += f"Submitted: {mod.submitter.initials} ({mod.submitted_date.strftime('%m/%d/%Y %H:%M')})<br>"
        #
        #     if mod.status == 'Approved':
        #         tooltip += f"Approved: {mod.reviewer.initials} ({mod.review_date.strftime('%m/%d/%Y %H:%M')})"
        #
        #     mod_tooltips[mod.field_name] = tooltip

        if mod.field != "Reason":
            # print(mod.field, ": ", mod.original_value)
            # print(mod.field, ": ", mod.original_value_text)
            if not mod.original_value_text:
                tooltip = f"None > {mod.new_value_text}<br>"
            elif not mod.new_value_text:
                tooltip = f"{mod.original_value_text} > None<br>"
            else:
                tooltip = f"{mod.original_value_text} > {mod.new_value_text}<br>"

            if mod.status == 'Imported':
                tooltip += "Imported: "
            else:
                tooltip += "Submitted: "

            tooltip += f"{mod.submitter.initials} ({mod.submitted_date.strftime('%m/%d/%Y %H:%M')})"

            if mod.status == 'Approved':
                tooltip += f"<br>Approved: {mod.reviewer.initials} ({mod.review_date.strftime('%m/%d/%Y %H:%M')})"

            mod_tooltips[mod.field_name] = tooltip

    if template_file:
        template = f"{table_name}/{template_file}"
    else:
        template = f'{table_name}/view.html'

    # Get the url of view page. This can be used to redirect the user
    # back to the view page for global routes.
    redirect_url = request.url

    if current_user.permissions == 'ADM-Management':
        view_only = True

    print(f"{current_user.initials} opened {alias} - {datetime.now().strftime('%m/%d/%Y %H:%M')}")

    print(f"\033[1;32m template: {template} \033[0m")
    return render_template(
        template,
        permissions=permissions,
        item=item,
        item_name=item_name,
        table_name=table_name,
        alias=alias,
        view_only=view_only,
        creator_only_update=creator_only_update,
        default_header=default_header,
        default_buttons=default_buttons,
        add_comment_button=add_comment_button,
        show_comments=show_comments,
        show_attachments=show_attachments,
        export_attachments=export_attachments,
        attachments=attachments,
        show_modifications=show_modifications,
        modifications=modifications,
        services=services,
        comments=comments,
        mod_tooltips=mod_tooltips,
        pending_mods=pending_mods,
        pending_fields=pending_fields,
        redirect_url=redirect_url,
        module_definitions=module_definitions,
        kwargs=kwargs
    )
