import io
from datetime import timedelta, time, datetime, date
import shutil, stat
import logging
import re
from string import ascii_uppercase

import pandas as pd
from dateutil.parser import isoparse
from sqlalchemy import desc, and_, case, not_, or_
from werkzeug.datastructures import MultiDict
from wtforms.validators import DataRequired

from lims.background.background_auto_import import *
from lims.models import Cases, Personnel, CaseTypes, Specimens, Containers, \
    Tests, RetentionPolicies, Results, Reports, Records, \
    Bookings, Genders, Races, StandardsAndSolutions, Assays, disciplines, BookingInformationProvider, \
    BookingInformationProvided, Divisions, DefaultClients, SpecimenTypes, Users, ContainerTypes, CooledStorage, \
    LitigationPackets, Batches
from lims.cases.forms import Add, Edit, Approve, Update, ImportFA, UpdateRetentionPolicy, AutopsyScan, LitPacket, \
    LitPacketZip, FAExportControlForm, ExportFiltered, UpdateStartDate, UpdateSensitivity, UpdatePriority, Communications
from lims.cases.functions import *
# , \ get_distinct_values, get_to_dict for pt_evals
from lims.pdf_redacting.functions import lit_packet_generation_templates
from lims.containers.forms import Add as ContainerAdd
from lims.containers.functions import get_form_choices as get_container_choices
from lims.evidence_comments.functions import get_form_choices as get_evidence_comments
from lims.evidence_comments.forms import Base as EvForm
from lims.locations.functions import location_dict
from lims.specimen_audit.views import add_specimen_audit
from lims.specimens.forms import Add as SpecimenAdd
from lims.specimens.functions import process_form as specimen_process
from lims.specimens.functions import get_form_choices as get_specimen_choices, process_audit
from lims.view_templates.views import *
from lims.forms import Attach, Import
from pypdf import PdfWriter
from lims.litigation_packets.functions import *
from lims.labels import fields_dict
from wtforms.validators import DataRequired, Optional, ValidationError
from flask import session, current_app, render_template, request, flash, url_for
import difflib
from collections import defaultdict
import base64
import requests


from lims.narratives.forms import AISummary as NarrativeAddForm
from lims.models import Narratives 
from pathlib import Path
# from threading import Lock
# case_locks = {}
from lims.redis_lock import DistributedRedisLock


# Set item global variables
item_type = 'Case'
item_name = 'Cases'
table = Cases
table_name = 'cases'
name = 'case_number'  # This selects what property is displayed in the flash messages
requires_approval = True  # controls whether the approval process is required. Can be set on a view level
ignore_fields = []  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'
redirect_to = 'view'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'ignore_fields': ignore_fields,
    'disable_fields': disable_fields
}

blueprint = Blueprint(table_name, __name__)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    form = get_form_choices(Add(), function='Add')

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            new_kwargs = process_form(form, event='Add')
            kwargs.update(new_kwargs)

            # Ignore age field if both date of birth and date of incident death have been provided.
            if form.date_of_birth.data and form.date_of_incident.data:
                kwargs['ignore_fields'] = ['age']

            # If B case is created, add to StandardsAndSolutions
            if form.case_type.data == CaseTypes.query.filter_by(code='B').first().id:
                data = {
                    'lot': kwargs['case_number'],
                    'solution_type_id': 12,
                    'db_status': 'Pending',
                    'location_type': 'Person',
                    'location': current_user.initials,
                    'create_date': datetime.now(),
                    'created_by': current_user.initials
                }
                item = StandardsAndSolutions(**data)
                db.session.add(item)

            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
            kwargs['case_id'] = Cases.query.order_by(desc(Cases.id)).first().id

            return redirect(url_for('containers.add',
                                    case_id=kwargs['case_id'],
                                    agency_id=form.submitting_agency.data)
                            )

    add_case = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return add_case


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()

    item = table.query.get_or_404(item_id)
    form = get_form_choices(Edit(), agency_id=item.submitting_agency, item=item)
    # disable the case_type field. A case type cannot be changed.
    kwargs['disable_fields'] = ['case_type']

    # Form PM cases (i.e. case_number_type == 'Manual'), disable and ignore the demographic
    # data that is set when imported

    if item.type.case_number_type == 'Manual':
        fields = [
            'case_type', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'age', 'gender_id', 'birth_sex',
            'race_id', 'date_of_incident', 'time_of_incident',
            'submitting_agency', 'submitting_division',
            'alternate_case_reference_number_1', 'alternate_case_reference_number_2'
        ]
        kwargs['ignore_fields'] = fields
        kwargs['disable_fields'] += kwargs['ignore_fields']

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            new_kwargs = process_form(form, item=item)
            kwargs.update(new_kwargs)

            # Ignore age field if both date of birth and date of incident death have been provided.
            if form.date_of_birth.data and form.date_of_incident.data:
                kwargs['ignore_fields'] += ['age']

    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, locking=False, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()

    item = table.query.get_or_404(item_id)
    form = get_form_choices(Approve(), agency_id=item.submitting_agency, item=item)

    # disable the case_type field. A case type cannot be changed.
    kwargs['disable_fields'] = ['case_type']

    # Form PM cases (i.e. case_number_type == 'Manual'), disable and ignore the demographic
    # data that is set when imported
    if item.type.case_number_type == 'Manual':
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'age', 'gender_id', 'birth_sex',
            'race_id', 'date_of_incident', 'time_of_incident',
            'submitting_agency', 'submitting_division',
            'alternate_case_reference_number_1', 'alternate_case_reference_number_2'
        ]
        kwargs['ignore_fields'] = fields
        kwargs['disable_fields'] += kwargs['ignore_fields']

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            new_kwargs = process_form(form, item=item)
            kwargs.update(new_kwargs)

            # Ignore age field if both date of birth and date of incident death have been provided.
            if form.date_of_birth.data and form.date_of_incident.data:
                kwargs['ignore_fields'] += ['age']

            # Execute the approve_item function.
            approve_item(form, item_id, table, item_type, item_name, table_name, name, set_item_active=False, **kwargs)

            # Determine if the case has been approved by seeing if there any pending modifications. Since we don't
            # clear the pending_submitter or make the db_status 'Active' (due to set_item_active = False) this is
            # how we'll determine if the case has been approved.
            case_approved = False
            if not Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending').count():
                case_approved = True

            # Get the number of pending_containers and pending_specimens for the case
            pending_containers = Containers.query.filter(sa.and_(Containers.case_id == item.id,
                                                                 Containers.pending_submitter != None)).count()
            pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == item.id,
                                                               Specimens.pending_submitter != None)).count()

            # if the case approved and there are no pending_containers of pending_specimens.
            if case_approved and not pending_containers and not pending_specimens:

                item.db_status = 'Active'
                item.pending_submitter = None
                item.communications = None
                # clear the review_discipline if all the case contents are approved
                item.review_discipline = None

                # For any containers that had a location_type as 'Evidence Locker', set the evidence_locker occupied to false
                # on approval.
                for container in Containers.query.filter_by(case_id=item_id, location_type='Evidence Lockers'):
                    print(container.location_type)
                    print(container.submission_route)
                    evidence_locker = EvidenceLockers.query.filter_by(
                        equipment_id=container.submission_route).first()
                    print(evidence_locker)
                    evidence_locker.occupied = False

                # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
                # no existing tests this should preserve the case status if updates are made to the case later on after testing
                # has been added
                if (len(form.testing_requested.data) and not item.case_status and Specimens.query.filter_by(
                        case_id=item_id).count()
                        and not Tests.query.filter_by(case_id=item_id).count()):
                    item.case_status = 'Need Test Addition'

                # Unlock the case
                unlock_item(item.id, Cases, name, request.referrer)

                # Unlocked any locked containers and specimens which are locked by the user.
                locked_containers = Containers.query.filter_by(case_id=item_id, locked_by=current_user.initials)
                for container in locked_containers:
                    unlock_item(container.id, Containers, 'accession_number', request.referrer)

                locked_specimens = Specimens.query.filter_by(case_id=item_id, locked_by=current_user.initials)
                for specimen in locked_specimens:
                    unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

                flash(Markup(f"<b>{item.case_number}</b> and its contents fully approved"), 'success')

            return redirect(url_for('cases.view', item_id=item_id))

    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, locking=False,
                            set_item_active=False, **kwargs)

    return _approve


@blueprint.route(f'/{table_name}/<int:item_id>/approve_all', methods=['GET', 'POST'])
@login_required
def approve_all(item_id):
    # Get case and set db_status to active and update modified by and modify date
    case = Cases.query.get(item_id)
    if case.pending_submitter != current_user.initials:
        case.modified_by = current_user.initials
        case.modify_date = datetime.now()
        # Get modifications relating to case and approve them, updating
        # reviewed_by and review_date
        case_mods = Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending').all()

        for mod in case_mods:
            mod.status = "Approved"
            mod.reviewed_by = current_user.id
            mod.review_date = datetime.now()

    # Get containers and set db_status to active and update modified by and modify date
    containers = Containers.query.filter_by(case_id=item_id).filter(
        Containers.pending_submitter != current_user.initials,
        Containers.pending_submitter != None,
    )

    # Only approve the containers for the review_discipline. If there is no review_discipline, all containers
    # will be approved.
    if case.review_discipline:
        containers = containers.filter_by(discipline=case.review_discipline)

    for container in containers:
        if container.pending_submitter:
            container.db_status = 'Active'
            container.modified_by = current_user.initials
            container.modify_date = datetime.now()
            container.pending_submitter = None

            if container.location_type is not None:
                if container.location_type == 'Evidence Lockers':
                    EvidenceLockers.query.filter_by(equipment_id=container.submission_route).occupied = False

            # Set the status, reviewed_by and review_date for all the container modifications
            container_mods = Modifications.query.filter_by(table_name='Containers', record_id=str(container.id),
                                                           status='Pending')
            for mod in container_mods:
                mod.status = "Approved"
                mod.reviewed_by = current_user.id
                mod.review_date = datetime.now()

    # Get specimens and set db_status to active and update modified by and modify date
    specimens = Specimens.query.filter_by(case_id=item_id).filter(
        Specimens.pending_submitter != current_user.initials,
        Specimens.pending_submitter != None,
    )

    # Only approve the specimens for the review_discipline. If there is no review_discipline, all specimens
    # will be approved.
    if case.review_discipline:
        specimens = specimens.filter_by(discipline=case.review_discipline)

    print(specimens.all())
    for specimen in specimens:
        if specimen.pending_submitter:
            specimen.db_status = 'Active'
            specimen.modified_by = current_user.initials
            specimen.modify_date = datetime.now()
            specimen.pending_submitter = None

            # Get modifications relating to specimen and approve them, updating
            # reviewed_by and review_date
            specimen_mods = Modifications.query.filter_by(table_name='Specimens', record_id=str(specimen.id),
                                                          status='Pending')
            for mod in specimen_mods:
                mod.status = "Approved"
                mod.reviewed_by = current_user.id
                mod.review_date = datetime.now()

    # Get the custody type and custody location for each specimen and set the values on the specimen
    # and add to the specimen audit.
    form = request.form.to_dict(flat=False)
    if form:
        for idx, specimen_id in enumerate(form['specimen-id']):
            specimen = Specimens.query.get(specimen_id)
            custody_type = form['custody-type'][idx]
            custody = form['custody'][idx]
            specimen.custody_type = custody_type
            specimen.custody = custody
            add_specimen_audit(destination=custody,
                               reason=f'{current_user.initials} approved the case',
                               o_time=datetime.now(),
                               specimen_id=specimen_id,
                               status='In')

    # Clear the review_discipline
    case.review_discipline = None

    # Unlock the case
    unlock_item(case.id, Cases, name, request.referrer)

    # Unlocked any locked containers and specimens which are locked by the user.
    locked_containers = Containers.query.filter_by(case_id=item_id, locked_by=current_user.initials)
    for container in locked_containers:
        unlock_item(container.id, Containers, 'accession_number', request.referrer)

    locked_specimens = Specimens.query.filter_by(case_id=item_id, locked_by=current_user.initials)
    for specimen in locked_specimens:
        unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

    # Determine if the case has been approved by seeing if there any pending modifications. Since we don't
    # clear the pending_submitter or make the db_status 'Active' (due to set_item_active = False) this is
    # how we'll determine if the case has been approved.
    case_approved = False
    if not Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending').count():
        case_approved = True

    # Get the number of pending_containers and pending_specimens for the case.
    pending_containers = Containers.query.filter(sa.and_(Containers.case_id == case.id,
                                                         Containers.pending_submitter != None)).count()
    pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == case.id,
                                                       Specimens.pending_submitter != None)).count()

    # If all components of the case have been approved. Clear pending_submitter and set the db_status to 'Active'.
    if case_approved and not pending_containers and not pending_specimens:

        case.pending_submitter = None
        case.db_status = 'Active'

        # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
        # no existing tests this should preserve the case status if updates are made to the case later on after testing
        # has been added.
        if (case.testing_requested and not case.case_status and Specimens.query.filter_by(case_id=item_id).count()
                and not Tests.query.filter_by(case_id=item_id).count()):
            case.case_status = 'Need Test Addition'

        # For any containers that had a location_type as 'Evidence Locker', set the evidence_locker occupied to false
        # on approval.
        for container in Containers.query.filter_by(case_id=item_id, location_type='Evidence Lockers'):
            print(container.location_type)
            print(container.submission_route)
            if container.location_type == 'Evidence Lockers':
                evidence_locker = EvidenceLockers.query.filter_by(equipment_id=container.submission_route).first()
                print(evidence_locker)
                evidence_locker.occupied = False

        db.session.commit()

        flash(Markup(f"<b>{case.case_number}</b> and its contents fully approved"), 'success')

        return redirect(url_for('cases.view', item_id=item_id))

    db.session.commit()

    return redirect(url_for(f"{table_name}.view_list"))


@blueprint.route(f'/{table_name}/<int:item_id>/approve_selected', methods=['GET', 'POST'])
@login_required
def approve_selected(item_id):
    form = request.form.to_dict(flat=False)

    # Get whether the case should be approved from the approve_selected_form.
    approve_case = form.get('approve-case')
    if approve_case:
        approve_case = approve_case[0]

    # Get the approved containers and specimens
    approved_containers = Containers.query.filter(Containers.id.in_(map(int, form.get('approved-containers', []))))
    approved_specimens = Specimens.query.filter(Specimens.id.in_(map(int, form.get('approved-specimens', []))))

    # all pending specimen ids are returned in the specimen-id field even if they were not approved and
    # no custody was selected. The custody and custody type fields only show the fields that were submitted.
    # For example, if there are two pending specimens and the second one was approved and the custody was selected
    # the returned values in the form would be:
    # form['specimen-id'] = [1, 2]
    # form['custody-type'] = ['Cooled Storage']
    # form['custody'] = ['09R']
    # Therefore, in order for the specime and custody choices to align, we need to remove the unapproved specimen ids.
    # for spec_id in form['specimen-id']:
    #     if spec_id not in form.get('approved-specimens', []):
    #         form['specimen-id'].remove(spec_id)
    if form.get('specimen-id'):
        for spec_id in form['specimen-id']:
            if spec_id not in form.get('approved-specimens', []):
                form['specimen-id'].remove(spec_id)

    # Get the case and if the case has been approved, update the modified_by and modify_date.
    case = Cases.query.get(item_id)
    if current_user.initials == case.pending_submitter:
        flash(Markup('Case details not approved. You can not approve your own changes'), 'error')
    elif approve_case == 'Yes':
        case = Cases.query.get(item_id)
        case.modified_by = current_user.initials
        case.modify_date = datetime.now()

        flash(Markup(f'<b>{case.case_number}</b> has been approved.'), 'success')

        # Approve all the case's modifications that are pending.
        case_mods = Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending')

        for mod in case_mods:
            mod.status = "Approved"
            mod.reviewed_by = current_user.id
            mod.review_date = datetime.now()

    # For any approved containers set the db_status, modified_by, modify_date and pending_submitter.
    for container in approved_containers:
        container.db_status = 'Active'
        container.modified_by = current_user.initials
        container.modify_date = datetime.now()
        container.pending_submitter = None

        if container.location_type is not None:
            if container.location_type == 'Evidence Lockers':
                EvidenceLockers.query.filter_by(equipment_id=container.submission_route).occupied = False

        flash(Markup(f'<b>{container.accession_number}</b> has been approved.'), 'success')

        # Approve all pending modifications for each container.
        container_mods = Modifications.query.filter_by(table_name='Containers', record_id=str(container.id),
                                                       status='Pending')
        for mod in container_mods:
            mod.status = "Approved"
            mod.reviewed_by = current_user.id
            mod.review_date = datetime.now()

        # For any containers that had a submission_route as an evidence locker, set the evidence_locker occupied to false
        # on approval.
        print(container.location_type)
        print(container.submission_route)
        if container.location_type == 'Evidence Lockers':
            evidence_locker = EvidenceLockers.query.filter_by(equipment_id=container.submission_route).first()
            print(evidence_locker)
            evidence_locker.occupied = False

    # For any approved specimens set the db_status, modified_by, modify_date and pending_submitter.
    for specimen in approved_specimens:
        specimen.db_status = 'Active'
        specimen.modified_by = current_user.initials
        specimen.modify_date = datetime.now()
        specimen.pending_submitter = None

        flash(Markup(f'<b>{specimen.accession_number}</b> has been approved.'), 'success')

        # Approve all pending modifications for each specimen.
        specimen_mods = Modifications.query.filter_by(table_name='Specimens', record_id=str(specimen.id),
                                                      status='Pending')
        for mod in specimen_mods:
            mod.status = "Approved"
            mod.reviewed_by = current_user.id
            mod.review_date = datetime.now()

        # Get the custody type and custody location for each specimen and set the values on the specimen
        # and add to the specimen audit.
        idx = form['specimen-id'].index(str(specimen.id))
        custody_type = form['custody-type'][idx]
        custody = form['custody'][idx]
        specimen.custody_type = custody_type
        specimen.custody = custody
        add_specimen_audit(destination=custody,
                           reason=f'{current_user.initials} approved the specimen',
                           o_time=datetime.now(),
                           specimen_id=specimen.id,
                           status='In')

    # Determine if the case has been approved by seeing if there any pending modifications. Since we don't
    # clear the pending_submitter or make the db_status 'Active' (due to set_item_active = False) this is
    # how we'll determine if the case has been approved.
    case_approved = False
    if not Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending').count():
        case_approved = True

    # Get the number of pending_containers and pending_specimens for the case.
    pending_containers = Containers.query.filter(sa.and_(Containers.case_id == case.id,
                                                         Containers.pending_submitter != None)).count()
    pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == case.id,
                                                       Specimens.pending_submitter != None)).count()

    # If all components of the case have been approved. Clear pending_submitter and set the db_status to 'Active'.
    if case_approved and not pending_containers and not pending_specimens:

        case.pending_submitter = None
        case.db_status = 'Active'
        case.review_discipline = None
        # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
        # no existing tests this should preserve the case status if updates are made to the case later on after testing
        # has been added
        if (case.testing_requested and not case.case_status and Specimens.query.filter_by(case_id=item_id).count()
                and not Tests.query.filter_by(case_id=item_id).count()):
            case.case_status = 'Need Test Addition'

        # For any containers that had a location_type as 'Evidence Locker', set the evidence_locker occupied to false
        # on approval.
        for container in Containers.query.filter_by(case_id=item_id, location_type='Evidence Lockers'):
            print(container.location_type)
            print(container.submission_route)
            if container.location_type == 'Evidence Lockers':
                evidence_locker = EvidenceLockers.query.filter_by(equipment_id=container.submission_route).first()
                print(evidence_locker)
                evidence_locker.occupied = False

        # Unlocking will only happen if all the case components are approved for the approve selected function
        unlock_item(item_id, table, name, request.referrer)

        locked_containers = Containers.query.filter_by(case_id=item_id, locked_by=current_user.initials)
        locked_specimens = Specimens.query.filter_by(case_id=item_id, locked_by=current_user.initials)
        for container in locked_containers:
            unlock_item(container.id, Containers, 'accession_number', request.referrer)

        for specimen in locked_specimens:
            unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

        flash(Markup(f"<b>{case.case_number}</b> and its contents fully approved"), 'success')

        return redirect(url_for('cases.view', item_id=item_id))

    return redirect(url_for('cases.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    kwargs = default_kwargs.copy()

    item = table.query.get_or_404(item_id)
    print(item.submitting_agency)
    form = get_form_choices(Update(), agency_id=item.submitting_agency, item=item)
    kwargs['disable_fields'] = ['case_type']

    # For all cases, prevent the approval process when testing_requested is updated
    auto_approved_fields = ['testing_requested']

    if item.type.case_number_type == 'Manual':
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'age', 'gender_id', 'birth_sex',
            'race_id', 'date_of_incident', 'time_of_incident',
            'submitting_agency', 'submitting_division',
            'alternate_case_reference_number_1', 'alternate_case_reference_number_2',
        ]

        kwargs['ignore_fields'] = fields
        kwargs['disable_fields'] += kwargs['ignore_fields']

        # Remove the submission_division required validator for PM cases so that updated
        # can be made if the primary pathologist/submitting division has not been assigned
        form.submitting_division.validators = []

    if request.method == 'POST':
        if form.is_submitted() and form.validate():
            new_kwargs = process_form(form, item=item)
            kwargs.update(new_kwargs)

            # Ignore age field if both date of birth and date of incident death have been provided.
            if form.date_of_birth.data and form.date_of_incident.data:
                kwargs['ignore_fields'] += ['age']

            unlock(item_id)

    # elif request.method == 'GET':
    #     lock(item_id)

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name,
                          locking=False, auto_approved_fields=auto_approved_fields, **kwargs)

    return _update


@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    containers = Containers.query.filter_by(case_id=item_id)
    specimens = Specimens.query.filter_by(case_id=item_id)
    for container in containers:
        lock_item(container.id, Containers, 'accession_number', request.referrer)
    for specimen in specimens:
        lock_item(specimen.id, Specimens, 'accession_number', request.referrer)

    _lock = lock_item(item_id, table, name, request.referrer)

    return _lock


@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):
    # When the case is unlocked, clear the review_discipline field.
    item = table.query.get(item_id)
    item.review_discipline = None
    admin = False

    form = request.form.to_dict(flat=False)
    if form.get('specimen-id'):
        for idx, specimen_id in enumerate(form['specimen-id']):
            specimen = Specimens.query.get(specimen_id)
            custody_type = form['custody-type'][idx]
            custody = form['custody'][idx]
            specimen.custody_type = custody_type
            specimen.custody = custody
            if form.get('reason'):
                reason = f'{current_user.initials} [Admin Change] {form["reason"][idx]}'
                admin = True
            else:
                reason = f'{current_user.initials} exited the case'
                admin = False
            add_specimen_audit(destination=custody,
                               reason=reason,
                               o_time=datetime.now(),
                               specimen_id=specimen_id,
                               status='In')

    if current_user.permissions in ['Admin', 'Owner']:
        admin = True

    if not admin:
        containers = Containers.query.filter_by(case_id=item_id, locked=True, locked_by=current_user.initials)
        specimens = Specimens.query.filter_by(case_id=item_id, locked=True, locked_by=current_user.initials)

    else:
        containers = Containers.query.filter_by(case_id=item_id, locked=True)
        specimens = Specimens.query.filter_by(case_id=item_id, locked=True)

    for container in containers:
        unlock_item(container.id, Containers, 'accession_number', request.referrer)

    for specimen in specimens:
        unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)

    _unlock = unlock_item(item_id, table, name, request.referrer)

    return redirect(url_for('cases.view_list'))


@blueprint.route(f'/{table_name}/revert_changes/')
@login_required
def revert_changes():
    item_id = request.args.get('item_id', 0, type=int)
    field = request.args.get('field_name', type=str)
    field_value = request.args.get('field_value', type=str)
    field_type = request.args.get('field_type', type=str)
    multiple = request.args.get('multiple', type=str)

    _revert_changes = revert_item_changes(item_id, field, field_value, item_name, field_type, multiple)

    return _revert_changes


@blueprint.route(f'/{table_name}/<int:item_id>/remove', methods=['GET', 'POST'])
@login_required
def remove(item_id):
    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)

    return _approve_remove


@blueprint.route(f'/{table_name}/<int:item_id>/reject_remove', methods=['GET', 'POST'])
@login_required
def reject_remove(item_id):
    _reject_remove = reject_remove_item(item_id, table, table_name, item_name, name)

    return _reject_remove


@blueprint.route(f'/{table_name}/<int:item_id>/restore', methods=['GET', 'POST'])
@login_required
def restore(item_id):
    _restore_item = restore_item(item_id, table, table_name, item_name, name)

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()
    item = table.query.get_or_404(item_id)

    record_ids = []

    narratives = Narratives.query.filter_by(case_id=item_id)
    narrative_ids = [item.id for item in narratives]
    Modifications.query.filter_by(table_name='Narratives').filter(Modifications.record_id.in_(narrative_ids)).delete()
    narratives.delete()

    containers = Containers.query.filter_by(case_id=item_id)
    container_ids = [item.id for item in containers]
    Modifications.query.filter_by(table_name='Containers').filter(Modifications.record_id.in_(container_ids)).delete()
    containers.delete()

    specimens = Specimens.query.filter_by(case_id=item_id)
    specimen_ids = [item.id for item in specimens]
    Modifications.query.filter_by(table_name='Specimens').filter(Modifications.record_id.in_(specimen_ids)).delete()
    specimens.delete()

    specimen_audit = SpecimenAudit.query.filter(SpecimenAudit.specimen_id.in_(specimen_ids))
    specimen_audit.delete()

    tests = Tests.query.filter_by(case_id=item_id)
    test_ids = [item.id for item in tests]
    Modifications.query.filter_by(table_name='Tests').filter(Modifications.record_id.in_(test_ids)).delete()
    tests.delete()

    evidence_comments = EvidenceComments.query.filter_by(case_number=item.id)
    evidence_comments.delete()

    Modifications.query.filter(Modifications.record_id.in_(record_ids)).delete()

    # case_type = CaseTypes.query.get(item.case_type)
    # if case_type.case_number_type == 'Automatic':
    #     case_type.current_case_number -= 1
    # db.session.commit()

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    if current_user.permissions not in ['Owner', 'Admin']:
        abort(403)

    for case_type in CaseTypes.query:
        case_type.current_case_number = case_type.case_number_start

    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items


@blueprint.route(f'/{table_name}/import_file/', methods=['GET', 'POST'])
@login_required
def import_file():
    form = Import()
    df = None
    filename = None
    savename = None
    if request.method == 'POST':
        f = request.files.get('file')
        filename = f.filename
        savename = f"{f.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
        path = os.path.join(current_app.config['FILE_SYSTEM'], 'imports', savename)
        f.save(path)
        df = pd.read_csv(path, dtype={'home_zip': str, 'death_zip': str})
        print(df.info())
        # df['home_zip'] = df['home_zip'].map(lambda x: str(x).split('.')[0])
        # df['death_zip'] = df['death_zip'].map(lambda x: str(x).split('.')[0])
        # df['time_of_incident'] = df['time_of_incident'].replace(np.nan, "")
        # df['time_of_incident'] = df['time_of_incident'].map(lambda x: str(int(x)).rjust(4, '0') if x != "" else "")
        # df['latitude'] = df['latitude'].replace("", np.nan)
        # df['latitude'] = df['latitude'].astype(float)
        # df['longitude'] = df['longitude'].replace("", np.nan)
        # df['longitude'] = df['longitude'].astype(float)

    _import = import_items(form, table, table_name, item_name, df=df, filename=filename, savename=savename)

    return _import


@blueprint.route(f'/{table_name}/export_fa_cases', methods=['GET', 'POST'])
@login_required
def export_fa_cases():      # Configure FA Sync - button available to Admin, Owner, Dev; can customize date range
    form = render_form(FAExportControlForm())
    required_fields = [field.name for field in form if field.flags.required]
    errors = {}
    exit_route = url_for(f'{table_name}.view_list')

    log_rows = []
    control_files = {}
    # Load delayUntil/lastRun from all frequency control files
    for freq in EXPORT_FREQUENCIES:
        control_path = os.path.join(control_dir, f"export-{freq}.json")
        if os.path.exists(control_path):
            with open(control_path, "r") as f:
                control = json.load(f)
                delay_raw = control.get("delayUntil")
                last_raw = control.get("lastRun")
                fmt = "%m/%d/%Y %H:%M:%S"
                delay_dt = isoparse(delay_raw).strftime(fmt) if delay_raw else None
                last_dt = isoparse(last_raw).strftime(fmt) if last_raw else None

                control_files[freq] = {
                    "path": control_path,
                    "delayUntil": delay_dt,
                    "lastRun": last_dt
                }

    if os.path.exists(log_path):
        try:
            df = pd.read_csv(log_path, encoding="utf-8")
            df = df.tail(10)  # Show only the last 10 entries
            date_columns = ["StartDate", "EndDate"]
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%m/%d/%Y")
            df['OutputFile'] = df['OutputFile'].apply(os.path.basename)
            df = df.fillna("")  # replace NaN with empty string
            log_rows = df.to_dict(orient="records")
        except Exception as e:
            flash(f"⚠️ Could not read export log: {e}", "warning")

    if request.method == 'POST':
        if form.validate_on_submit():
            if form.delay_until.data:
                delay_until = form.delay_until.data.isoformat()
            else:
                delay_until = datetime.now().isoformat()

            for freq in EXPORT_FREQUENCIES:
                path = os.path.join(control_dir, f"export-{freq}.json")
                if os.path.exists(path):
                    with open(path, "r") as f:
                        control = json.load(f)
                    control["delayUntil"] = delay_until
                    with open(path, "w") as f:
                        json.dump(control, f, indent=2)
                else:
                    print(f"export-{freq}.json path doesn't exist")

            adhoc_path = os.path.join(control_dir, "export-control.json")
            if os.path.exists(adhoc_path) and form.run_now.data:
                try:
                    with open(adhoc_path, "r") as f:
                        adhoc_control = json.load(f)
                    adhoc_control["runNow"] = True
                    adhoc_control["startDate"] = form.start_date.data.isoformat()
                    adhoc_control["endDate"] = form.end_date.data.isoformat()
                    adhoc_control["initials"] = f"0{current_user.initials}"
                    with open(adhoc_path, "w") as f:
                        json.dump(adhoc_control, f, indent=2)
                    flash("✅ Adhoc export-control.json updated and flagged to run.", "message")
                except Exception as e:
                    flash(f"❌ Failed to update export-control.json: {e}. Force FA Export for Syncing is NOT scheduled.", "message")
            else:
                flash("❌ export-control.json path does not exist. Force FA Export for Syncing is NOT scheduled.", "message")
            return render_template(f'{table_name}/fa_export.html',
                                   form=form,
                                   item=None,
                                   table_name=table_name,
                                   item_name=item_name,
                                   function='Modify/Force Export of Case Data from FA',
                                   alias=None,
                                   pending_fields=[],
                                   approved_fields=[],
                                   required_fields=required_fields,
                                   errors=errors,
                                   errors_json=json.dumps(errors),
                                   default_header=True,
                                   control_files=control_files,
                                   log_rows=log_rows,
                                   exit_route=exit_route)

    return render_template(f'{table_name}/fa_export.html',
                           form=form,
                           item=None,
                           table_name=table_name,
                           item_name=item_name,
                           function='Modify/Force Export of Case Data from FA',
                           alias=None,
                           pending_fields=[],
                           approved_fields=[],
                           required_fields=required_fields,
                           errors=errors,
                           errors_json=json.dumps(errors),
                           default_header=True,
                           control_files=control_files,
                           log_rows=log_rows,
                           exit_route=exit_route)


@blueprint.route(f'/{table_name}/force_export_fa_cases', methods=['GET', 'POST'])
@login_required
def force_export_fa_cases():    # Force FA Sync - URL accessible to all users in nav-bar; most recent day ONLY
    if request.method == 'GET':
        print(f'Force FA Sync started via GET by {current_user.initials}')

        # Construct values
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        adhoc_path = os.path.join(control_dir, "export-control.json")

        if os.path.exists(adhoc_path):
            try:
                with open(adhoc_path, "r") as f:
                    adhoc_control = json.load(f)
                adhoc_control["runNow"] = True
                adhoc_control["startDate"] = yesterday.isoformat()
                adhoc_control["endDate"] = today.isoformat()
                adhoc_control["initials"] = f"0{current_user.initials}"
                with open(adhoc_path, "w") as f:
                    json.dump(adhoc_control, f, indent=2)

                flash("✅ Ad hoc export-control.json updated and flagged to run now.", "message")
            except Exception as e:
                flash(f"❌ Failed to update export-control.json: {e}. Force FA Sync is NOT scheduled.", "message")
        else:
            flash("❌ export-control.json path does not exist. Force FA Sync is NOT scheduled.", "message")

    return redirect(url_for('dashboard.get_dashboard'))

@blueprint.route(f'/{table_name}/import_fa_cases', methods=['GET', 'POST'])
@login_required
def import_fa_cases():
    form = ImportFA()
    form = render_form(form)
    errors = {}

    if request.method == 'POST':
        if form.validate_on_submit():
            file = form.file.data
            filename = file.filename
            savename = f"{file.filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
            path = os.path.join(current_app.config['FILE_SYSTEM'], 'imports', savename)
            file.save(path)
            fa_col_map = os.path.join(current_app.config['FILE_SYSTEM'], "fa_column_mapping.csv")
            impl_date = current_app.config['IMPLEMENTATION_DATE']
            add_form = get_form_choices(Add(), agency_id=1)

            process_import_file(path, filename, savename, fa_col_map, impl_date, add_form)

            return redirect(url_for('dashboard.get_dashboard'))

        else:
            errors = form.errors
            print(errors)

    return render_template(f'{table_name}/fa_import.html',
                           form=form,
                           function='Import',
                           required_fields=json.dumps(['file']),
                           item_name='FA Cases',
                           errors=json.dumps(errors),
                           pending_fields=json.dumps([]),
                           default_header=True)


@blueprint.route(f'/{table_name}/parse_case_number')
@login_required
def parse_case_number():
    case_number = request.args.get('case_number')
    path = request.referrer
    case = Cases.query.filter_by(case_number=case_number).first()
    session['case_search_error'] = ""
    session['case_pending'] = False
    session['pending_case_number'] = ""
    session['pending_case_id'] = ""

    if case is None:
        session['case_search_error'] = f"{case_number} not found!"
        return redirect(path)

    if case.db_status in ['Pending', 'Active with pending changes']:
        session['case_pending'] = True
        session['pending_case_number'] = case.case_number
        session['pending_case_id'] = case.id
        if current_user.initials == case.pending_submitter:
            session['func'] = 'Edit'
        else:
            session['func'] = 'Review'
        return redirect(path)

    case_id = case.id

    return redirect(url_for('cases.view', item_id=case_id))


@blueprint.route(f'/{table_name}/export', methods=['GET'])
def export():
    _export = export_items(table)

    return _export


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):
    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}/<int:item_id>/export_records', methods=['GET'])
def export_records(item_id):
    temp_path = os.path.join(current_app.config['FILE_SYSTEM'], 'temp')

    # Remove any folders in the temp folder
    tmp_zip_folders = glob.glob(f"{temp_path}\*.zip")
    for folder in tmp_zip_folders:
        os.remove(folder)

    item = table.query.get(item_id)
    alias = getattr(item, name)

    output_path = os.path.join(temp_path, f"{alias}")

    writer = PdfWriter()

    # Case records
    records_path = Path(os.path.join(current_app.config['FILE_SYSTEM'], 'records', alias))
    case_path = os.path.join(output_path, 'Case Records')
    os.makedirs(case_path, exist_ok=True)

    for file in glob.glob(f"{records_path}\*"):
        shutil.copy(file, case_path)

        # Merges pdfs together and creates outline

        # if file.split(".")[1] == 'pdf':
        #     reader = PdfReader(file)
        #     num_pages = writer.get_num_pages()
        #     writer.append_pages_from_reader(reader)
        #     writer.add_outline_item(Path(file).name, num_pages)

    # Batch records
    batch_record_path = os.path.join(output_path, 'Batch Records')
    os.makedirs(batch_record_path, exist_ok=True)
    batch_ids = set([test.batch.batch_id for test in Tests.query.filter_by(case_id=item.id)])

    for batch_id in batch_ids:
        batch_records = os.path.join(current_app.config['FILE_SYSTEM'], 'batch_records', batch_id)
        files = glob.glob(f"{batch_records}\*")
        batch_path = os.path.join(batch_record_path, batch_id)
        if files:
            os.makedirs(batch_path, exist_ok=True)
            for file in files:
                shutil.copy(file, batch_path)

                # Merges pdfs together and creates outline

                # if file.split(".")[1] == 'pdf':
                #     reader = PdfReader(file)
                #     num_pages = writer.get_num_pages()
                #     writer.append_pages_from_reader(reader)
                #     writer.add_outline_item(Path(file).name, num_pages)
                #     print(f"{file} appended to pdf")

    # writer.write(os.path.join(output_path, f"{alias}_L1.pdf"))
    # writer.close()

    # Zip file
    shutil.make_archive(output_path, 'zip', output_path)

    # Remove folder
    shutil.rmtree(output_path, onerror=lambda func, path, _: (os.chmod(path, stat.S_IWRITE), func(path)))

    return send_file(f"{output_path}.zip",
                     as_attachment=True,
                     download_name=f'{alias}.zip')

    # return send_file(os.path.join(output_path, f"{alias}_L1.pdf"),
    #          as_attachment=True,
    #          download_name=f'{alias}_L1.pdf')


@blueprint.route(f'/{table_name}/<int:item_id>/attach', methods=['GET', 'POST'])
@login_required
def attach(item_id):
    form = Attach()

    redirect_url = request.args.get('redirect_url')

    print(redirect_url)

    _attach = attach_items(form, item_id, table, item_name, table_name, name, redirect_url=redirect_url)

    return _attach


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    start = time.perf_counter()
    items = None
    filter_message = None
    query = request.args.get('query')
    query_type = request.args.get('query_type')

    # Get filters
    filters = {
        'case_types': CaseTypes.query,
        'case_status': ['None', 'No Testing Requested', 'Need Test Addition', 'Queued', 'In Progress', 'Finalized'],
    }
    order_by = ['cases.create_date DESC']
    # Set alerts
    need_test_addition = table.query.filter_by(case_status='Need Test Addition').count()
    priority_cases = table.query.filter_by(priority='High').count()

    normal_alerts = [
        (url_for('cases.view_list', query='need_tests'), need_test_addition, Markup('that <b>need test additions</b>')),
        (url_for('cases.view_list', query='priority'), priority_cases, Markup('with <b>high priority</b>'))
    ]
    warning_alerts = []
    danger_alerts = []

    # filter based on case_type
    if query_type == 'case_type':
        items = table.query.filter_by(case_type=query)
        case_type = CaseTypes.query.get(query)
        filter_message = Markup(f'You are currently viewing <b>{case_type.code} - {case_type.name}</b> cases')
    # filter based on case_status
    if query_type == 'case_status':
        if query == 'None':
            query = None
        items = table.query.filter_by(case_status=query)
        if query:
            filter_message = Markup(f'You are currently viewing cases which are <b>{query}</b>')
        else:
            filter_message = Markup(f'You are currently viewing cases with <b>no case status</b>')

    # Filter table based on query
    if query == 'need_tests':
        items = table.query.filter_by(case_status='Need Test Addition')
        filter_message = Markup('You are currently viewing cases which <b>need test addition</b>')

    if query == 'priority':
        items = table.query.filter_by(priority='High')
        filter_message = Markup('You are currently viewing cases with <b>high priority/b>')

    if current_user.permissions in ['MED-Autopsy', 'MED', 'INV', 'ADM']:
        items = table.query.join(CaseTypes).filter(CaseTypes.code == 'PM')

    start2 = time.perf_counter()
    _view_list = view_items(table, item_name, item_type, table_name,
                            items=items, filter_message=filter_message,
                            order_by=order_by,
                            normal_alerts=normal_alerts,
                            warning_alerts=warning_alerts, danger_alerts=danger_alerts,
                            locked_column=False, pending_submitter_column=False, disciplines=disciplines,
                            filters=filters)
    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET', 'POST'])
@login_required
def view(item_id):

    start_time = time.time()
    kwargs = {'booking_info_provider': BookingInformationProvider,
              'booking_info_provided': BookingInformationProvided
              }

    item = Cases.query.get_or_404(item_id)

    alias = getattr(item, name)

    ######

    if item.db_status not in ['Active', 'Removed']:
        # Determine if the case has been approved by seeing if there any pending modifications. Since we don't
        # clear the pending_submitter or make the db_status 'Active' (due to set_item_active = False) this is
        # how we'll determine if the case has been approved.
        case_approved = False
        if not Modifications.query.filter_by(table_name='Cases', record_id=str(item_id), status='Pending').count():
            case_approved = True

        # Get the number of pending_containers and pending_specimens for the case
        pending_containers = Containers.query.filter(sa.and_(Containers.case_id == item.id,
                                                             Containers.pending_submitter != None))
        pending_specimens = Specimens.query.filter(sa.and_(Specimens.case_id == item.id,
                                                           Specimens.pending_submitter != None))

        # Get the list of pending submitters for the containers of the case
        pending_submitters = [cont.pending_submitter for cont in pending_containers if
                              cont.pending_submitter != item.pending_submitter]
        # Add the list of pending submitters for the specimens for the case
        pending_submitters += [spec.pending_submitter for spec in pending_specimens if
                               spec.pending_submitter != item.pending_submitter]
        # if there are pending submitters, get the pending submitter for the most pending items.
        if pending_submitters and case_approved:
            pending_submitter = max(set(pending_submitters), key=pending_submitters.count)
            # if the case is approved, set the pending submitter of the case to the most frequent pending submitter.
            item.pending_submitter = pending_submitter
            db.session.commit()

        # if the case approved and there are no pending_containers of pending_specimens.
        if case_approved and not pending_containers.count() and not pending_specimens.count():

            item.db_status = 'Active'
            item.pending_submitter = None
            item.communications = None
            # clear the review_discipline if all the case contents are approved
            item.review_discipline = None

            # if any discipline requested set status to "Need Test Addition" Only if there is specimens, no case_status and
            # no existing tests this should preserve the case status if updates are made to the case later on after testing
            # has been added
            if (item.testing_requested and not item.case_status and Specimens.query.filter_by(
                    case_id=item_id).count()
                    and not Tests.query.filter_by(case_id=item_id).count()):
                item.case_status = 'Need Test Addition'

            # For any containers that had a location_type as 'Evidence Locker', set the evidence_locker occupied to false
            # on approval.
            for container in Containers.query.filter_by(case_id=item_id, location_type='Evidence Lockers'):
                evidence_locker = EvidenceLockers.query.filter_by(
                    equipment_id=container.submission_route).first()
                evidence_locker.occupied = False

            # Unlock the case
            unlock_item(item.id, Cases, name, request.referrer)

            # Unlocked any locked containers and specimens which are locked by the user.
            locked_containers = Containers.query.filter_by(case_id=item_id, locked_by=current_user.initials)
            for container in locked_containers:
                unlock_item(container.id, Containers, 'accession_number', request.referrer)

            locked_specimens = Specimens.query.filter_by(case_id=item_id, locked_by=current_user.initials)
            for specimen in locked_specimens:
                unlock_item(specimen.id, Specimens, 'accession_number', request.referrer)
    ######

    view_only = False
    if item.locked and item.locked_by != current_user.initials:
        view_only = True
    elif ('FLD' not in current_user.permissions and current_user.permissions in ['MED-Autopsy', 'MED', 'INV'] and
          not item.locked):
        view_only = True
        kwargs['add_new'] = True
    elif current_user.permissions in ['FLD', 'Admin', 'Owner'] and not item.locked:
        kwargs['add_new'] = True

    view_only_arg = request.args.get('view_only')
    if view_only_arg == 'True':
        view_only = True
    elif view_only_arg == 'False':
        if view_only:
            abort(403)

    if current_user.permissions in ['ADM-Management', 'ADM']:
        view_only = True

    custody_arg = request.args.get('custody', type=int)
    if custody_arg == 0:
        give_custody = False
    else:
        give_custody = True

    # Get the review discipline for specimen audit
    review_discipline = request.args.get('review_discipline')

    if review_discipline:
        item.review_discipline = review_discipline
        db.session.commit()

    if item.locked_by == current_user.initials:
        if item.review_discipline:
            review_discipline = item.review_discipline

    # Get the discipline to filter tables by
    discipline = request.args.get('discipline')

    name_mods = Modifications.query.filter_by(table_name='Cases', record_id=str(item_id)) \
        .filter(sa.and_(
        Modifications.field_name.in_(['first_name', 'last_name'])))

    first_names_lst = [name_mod.new_value for name_mod in name_mods if name_mod.field_name == 'first_name']
    first_names = ""
    first_names_lst = ['' if name is None else name for name in first_names_lst]
    if len(first_names_lst) > 1:
        first_names = " > ".join(first_names_lst)

    last_names_lst = [name_mod.new_value for name_mod in name_mods if name_mod.field_name == 'last_name']
    last_names = ""
    if len(last_names_lst) > 1:
        last_names = " > ".join(last_names_lst)

    # Get all case related items
    narratives = Narratives.query.filter_by(case_id=item_id, db_status='Active').order_by(case(
        (Narratives.narrative_type == 'Summary (AI)', 1),
        (Narratives.narrative_type == 'Summary', 2),
        (Narratives.narrative_type == 'Initial', 3),
        else_=4
    ))
    containers = db.session.query(Containers).filter(Containers.case_id == item.id)
    specimens = Specimens.query.filter(
        Specimens.case_id == item.id,
    ).order_by(Specimens.accession_number.asc())
    tests = Tests.query.outerjoin(Batches).filter(Tests.case_id == item.id).all()  # .order_by(Batches.extraction_date)

    tests = [t for t in tests if not re.search('SAMQ', t.test_name)]

    # results = db.session.query(Results).join(Components).filter(Results.case_id == item.id).order_by(Components.name)

    if item.type.code == 'PM':
        drug_class_ranks = DrugClasses.pm_rank
    elif item.type.code in ['D', 'M', 'P']:
        drug_class_ranks = DrugClasses.m_d_rank
    elif item.type.code == 'X':
        drug_class_ranks = DrugClasses.x_rank
    else:
        drug_class_ranks = DrugClasses.id

    results = Results.query.join(Components).outerjoin(DrugClasses).filter(Results.case_id == item.id).group_by(
        Results.test_id,
        Results.case_id,
        Results.component_id,
        Results.result,
        Results.result_status,
        Results.component_name,
        Results.scope_id,
        Results.unit_id,
        Results.supplementary_result,
        Results.concentration,
        Results.measurement_uncertainty,
        Results.result_type,
        Results.qualitative,
        Results.qualitative_reason,
        Results.report_reason,
        Results.result_comments_manual,
        Results.sample_comments_manual,
        Results.test_comments_manual,
        Results.component_comments_manual,
        Results.comment_numbers,
        Results.reported,
        Results.primary,
        Results.id,
        Results.db_status,
        Results.locked,
        Results.revision,
        Results.notes,
        Results.communications,
        Results.remove_reason,
        Results.create_date,
        Results.created_by,
        Results.modify_date,
        Results.modified_by,
        Results.locked_by,
        Results.lock_date,
        Results.pending_submitter,
        Results.result_status_updated,
        Results.result_type_updated,
        Results.result_type_update_reason,
        Results.result_status_update_reason,
        case(
            (Results.result_status == 'Confirmed', 1),
            (Results.result_status == 'Saturated', 2),
            (Results.result_status == 'Unconfirmed', 3),
            else_=4
        ),
        drug_class_ranks,
        DrugClasses.name,
        Components.rank
    )

    result_counts = {}

    for result in results:
        if result.result_status in ['Confirmed', 'Saturated']:
            if result.component_name not in result_counts.keys():
                result_counts[result.component_name] = 1
            else:
                result_counts[result.component_name] += 1

    # Component/Assay Summary
    components = []
    for specimen in specimens:
        specimen_test_ids = [test.id for test in Tests.query.filter_by(specimen_id=specimen.id)]
        for result in results.filter(Results.test_id.in_(specimen_test_ids)).distinct(Components.name).group_by(
                Components.name):
            component_dict = {}
            component_dict['specimen'] = result.test.specimen
            component_dict['component'] = result.component
            for status in ['Confirmed', 'Saturated', 'Unconfirmed', 'Trace']:
                assays = {}
                for res in results.filter(Results.result_status == status,
                                          Components.name == result.component.name,
                                          Results.test_id.in_(specimen_test_ids)):
                    assay_name = res.test.assay.assay_name
                    if assay_name not in assays.keys():
                        assays[assay_name] = 1
                    else:
                        assays[assay_name] += 1
                assay_lst = []
                for assay, count in assays.items():
                    assay_lst.append(f"{assay} ({count})")

                component_dict[f'{status.lower()}_results'] = ", ".join(assay_lst)
            components.append(component_dict)

    test_ids = [item.test_id for item in results]
    reports = Reports.query.filter(and_(Reports.case_id == item.id, Reports.db_status != 'Removed'))
    records = Records.query.filter_by(case_id=item.id, db_status='Active')
    bookings = Bookings.query.filter_by(case_id=item.id)
    packets = LitigationPackets.query.filter_by(case_id=item_id)

    # pt_evals = PTResults.query.filter_by(case_id=item.id)
    # pt_evals_as_dict = [get_to_dict(item) for item in pt_evals]
    # distinct_evals = get_distinct_values(pt_evals_as_dict, 'eval_date')

    # creates an array of batch ids, turns into a set to remove duplicates, and retrieves all batches whose id is in the list
    batches = [test.batch_id for test in tests]
    batches = set(batches)
    batches = Batches.query.filter(Batches.id.in_(batches))

    # Apply discipline-based filtering if requested
    if discipline:
        specimens = specimens.join(SpecimenTypes).filter(SpecimenTypes.discipline.contains(discipline))
        container_ids = [specimen.container_id for specimen in specimens]
        containers = containers.filter(Containers.id.in_(container_ids))
        tests = tests.join(Assays).filter(Assays.discipline == discipline)
        results = results.join(Tests).filter(Assays.discipline == discipline)
        reports = reports.filter(and_(reports.discipline == discipline, reports.db_status != 'Removed'))

    # Create comment dictionary for comment tooltips and containers/specimen/narratives comment display
    test_comment_dict = {}
    result_comment_dict = {}
    batches_comment_dict = {}
    container_comment_dict = {}
    specimen_comment_dict = {}
    narrative_comment_dict = {}

    summary = (Narratives.query.filter_by(case_id=item_id, narrative_type='Summary').first()) #for comments from morning notes
    kwargs['summary_id'] = summary.id if summary else None
  


    item_types = {
        'Tests': (test_comment_dict, tests),
        'Results': (result_comment_dict, results),
        'Batches': (batches_comment_dict, batches),
        'Containers': (container_comment_dict, containers),
        'Specimens': (specimen_comment_dict, specimens),
        'Narratives': (narrative_comment_dict, narratives)
    }

    for itype in item_types.keys():
        item_type_dict = item_types[itype][0]
        for i in item_types[itype][1]:
            comments = CommentInstances.query.filter_by(comment_item_type=itype, comment_item_id=i.id,
                                                        db_status='Active') \
                .order_by(CommentInstances.comment_id.desc())
            if comments.count():
                comment_text = '<ul>'
                for comment in comments:
                    comment_text += '<li>'
                    if getattr(comment, 'comment_id'):
                        if comment.comment.code:
                            comment_text += f"{comment.comment.code} - "
                        comment_text += f"{comment.comment.comment}"
                    else:
                        comment_text += f"{comment.comment_text}"

                    comment_text += f" ({comment.created_by})</li>"
                comment_text += "</ul>"
                item_type_dict[i.id] = comment_text
 
    # print(specimen_comment_dict)
    # print(test_comment_dict)
    # print("NARRATIVES:", narrative_comment_dict)

    # Get attachments for the case and related containers, specimens and bookings
    container_ids = [item.id for item in containers]
    specimen_ids = [item.id for item in specimens]
    booking_ids = [item.id for item in bookings]
    report_ids = [item.id for item in reports]
    record_ids = [item.id for item in records]
    packet_ids = [item.id for item in packets]

    case_attachments = Attachments.query.filter_by(table_name=item_name, record_id=str(item_id)).all()
    container_attachments = Attachments.query.filter(Attachments.table_name == 'Containers',
                                                     Attachments.record_id.in_(container_ids)).all()
    specimen_attachments = Attachments.query.filter(Attachments.table_name == 'Specimens',
                                                    Attachments.record_id.in_(specimen_ids)).all()
    booking_attachments = Attachments.query.filter(Attachments.table_name == 'Bookings',
                                                   Attachments.record_id.in_(booking_ids)).all()
    report_attachments = Attachments.query.filter(Attachments.table_name == 'Reports',
                                                  Attachments.record_id.in_(report_ids)).all()
    record_attachments = Attachments.query.filter(Attachments.table_name == 'Records',
                                                  Attachments.record_id.in_(record_ids)).all()
    packet_attachments = Attachments.query.filter(Attachments.table_name == 'Litigation Packets',
                                                  Attachments.record_id.in_(packet_ids)).all()

    attachments = case_attachments + container_attachments + specimen_attachments + booking_attachments + report_attachments + record_attachments + packet_attachments

    # packets = LitigationPackets.query.filter_by(case_id=item_id)

    record_path = os.path.join(current_app.root_path, 'static/filesystem', 'reports')
    pdfs = []
    if os.path.exists(record_path):
        pdfs = [x.split(".")[0] for x in os.listdir(record_path)]
        kwargs['pdfs'] = pdfs
    kwargs['pdfs'] = pdfs

    all_pending_containers = containers.filter(Containers.pending_submitter != None)
    all_pending_specimens = specimens.filter(Specimens.pending_submitter != None)

    # Get pending containers and specimens
    pending_containers = containers.filter(~Containers.pending_submitter.in_([current_user.initials, ""]))
    pending_specimens = specimens.filter(~Specimens.pending_submitter.in_([current_user.initials, ""]))

    if review_discipline:
        all_pending_containers = all_pending_containers.filter_by(discipline=review_discipline)
        all_pending_specimens = all_pending_specimens.filter_by(discipline=review_discipline)
        pending_containers = pending_containers.filter_by(discipline=review_discipline)
        pending_specimens = pending_specimens.filter_by(discipline=review_discipline)

    if not view_only and (item.pending_submitter or pending_containers.count() or pending_specimens.count()):
        if not item.locked:
            item.locked = True
            item.locked_by = current_user.initials
            item.lock_date = datetime.now()
        for container in containers:
            if not container.locked:
                container.locked = True
                container.locked_by = current_user.initials
                container.lock_date = datetime.now()
        for spec in specimens:
            if not spec.locked:
                spec.locked = True
                spec.locked_by = current_user.initials
                spec.lock_date = datetime.now()
                if give_custody:
                    if spec.pending_submitter:
                        if spec.pending_submitter != current_user.initials:
                            if spec.discipline == review_discipline or not review_discipline:
                                spec.custody = current_user.initials
                                spec.custody_type = 'Person'
                                add_specimen_audit(specimen_id=spec.id,
                                                destination=current_user.initials,
                                                reason=f"{current_user.initials} locked pending case to review",
                                                o_time=datetime.now(),
                                                status='Out'
                                                )
        db.session.commit()

    if review_discipline:
        specimens = specimens.filter_by(discipline=review_discipline)
        containers = containers.filter_by(discipline=review_discipline)

    # specimens_in_custody = db.session.query(Specimens).filter(
    #     Specimens.id.in_(specimen_ids_by_discipline),
    #     Specimens.custody == current_user.initials
    # ).all()
    # print(f'Specimens in custody -- {specimens_in_custody}')
    # specimens_in_custody = specimens.filter_by(custody=current_user.initials).all()
    # print(specimens_in_custody)

    specimens_in_custody = Specimens.query.filter(
        Specimens.id.in_(specimen_ids),
        Specimens.custody == current_user.initials,
        Specimens.db_status != 'Removed'
    ).all()

    users_initials = [user.initials for user in Users.query]

    users_initials.extend([user.id for user in Users.query])
    print(f'USER INITIALS: {users_initials}')

    admin_specimens_in_custody = []

    if current_user.permissions in ['Admin', 'Owner']:
        admin_specimens_in_custody = Specimens.query.filter(
            Specimens.id.in_(specimen_ids),
            Specimens.custody.in_(users_initials)
        ).all()

    print(f'ADMIN SPECIMENS: {admin_specimens_in_custody}')

    delete_mod = Modifications.query.filter_by(record_id=str(item_id), event='DELETE',
                                               status='Approved', table_name=item_name).first()

    mods = Modifications.query.filter_by(record_id=str(item.id), table_name=item_name). \
        order_by(Modifications.submitted_date.desc())

    # Get pending modifications for alerts
    pending_mods = Modifications.query.filter_by(
        record_id=str(item_id), status='Pending', table_name=item_name). \
        order_by(Modifications.field)

    # # This will show which fields are pending changes
    # pending_mods = [mod for mod in pending_mods]
    # This says how many fields are pending changes
    case_approved = True
    if pending_mods.count():
        case_approved = False

    pending_submitters = {}
    pending_fields = []
    # n_pending = 0
    for mod in pending_mods:
        pending_submitters[mod.field_name] = mod.submitter.initials
        pending_fields.append(mod.field_name)

    pending_fields = json.dumps(pending_fields)

    # for discipline in disciplines:
    #     discipline = discipline.lower()
    #     kwargs[f'{discipline}_time'] = ""
    #     end = datetime.now()
    #
    #     if getattr(item, f"{discipline}_start_date") is not None:
    #         start = getattr(item, f"{discipline}_start_date")
    #         if getattr(item, f"{discipline}_alternate_start_date") is not None:
    #             start = getattr(item, f"{discipline}_start_date")
    #
    #         if getattr(item, f"{discipline}_start_date") is not None:
    #             start = getattr(item, f"{discipline}_start_date")
    #
    #         if getattr(item, f"{discipline}_end_date") is not None:
    #             end = getattr(item, f"{discipline}_end_date")
    #
    #         td = end - start
    #         kwargs[f'{discipline}_time'] = f"{td.days}d {td.seconds // 3600}h {(td.seconds // 60) % 60}m"

    for d in disciplines:
        d = d.lower()
        kwargs[f'{d}_time'] = ""
        end = datetime.now()

        if getattr(item, f"{d}_start_date") is not None:
            start = getattr(item, f"{d}_start_date")

            # Use alternate start date if it exists
            if getattr(item, f"{d}_alternate_start_date") is not None:
                start = getattr(item, f"{d}_alternate_start_date")

            if getattr(item, f"{d}_end_date") is not None:
                end = getattr(item, f"{d}_end_date")

            td = end - start
            kwargs[f'{d}_time'] = f"{td.days}d {td.seconds // 3600}h"

    kwargs['requests'] = Requests.query.filter(
        or_(
            Requests.case_id.like(f'{item_id},%'),  # Matches item_id at the beginning of comma list
            Requests.case_id.like(f'%, {item_id},%'),  # Matches item_id in the middle
            Requests.case_id.like(f'%, {item_id}'),  # Matches item_id at the end
            Requests.case_id == str(item_id)  # Matches item_id as the only value
        )
    ).all()

    # print(f"{current_user.initials} opened {item.case_number} - {datetime.now()}")
    
    # ALTERNATE START DATE
    # Handle alternate start date form
    alternate_start_date_form = UpdateStartDate()
    if 'alternate_date_submit' in request.form:
        print('alternate start date submitted')

        column_name = alternate_start_date_form.column_name.data
        item_id = request.form.get('item_id')
        item = Cases.query.get(item_id)

        if item and hasattr(item, column_name):
            print("raw form:", request.form.to_dict(flat=False))
            selected_date = getattr(alternate_start_date_form, column_name).data
            time_field_name = column_name.replace('_date', '_time')
            selected_time_field = getattr(alternate_start_date_form, time_field_name, None)
            selected_time = selected_time_field.data if selected_time_field else None
            print(f"date: {selected_date}")
            print(f"time: {selected_time}")

            if selected_date:
                if selected_time:
                    combined = datetime.combine(selected_date, selected_time)
                else:
                    combined = datetime.combine(selected_date, datetime.min.time())
                setattr(item, column_name, combined)
                db.session.commit()
                flash(f"{column_name.replace('_', ' ').title()} updated successfully", "success")
            else:
                flash("No date provided", "danger")
        else:
            flash("Invalid column or item ID", "danger")

        return redirect(url_for('cases.view', item_id=item_id))

    kwargs['alternate_start_date_form'] = alternate_start_date_form

    # UPDATE PRIORITY
    update_priority_form = UpdatePriority()
    if 'priority_submit' in request.form:
        item_id = request.form.get('item_id')
        item = Cases.query.get(item_id)
        item.priority = update_priority_form.priority.data
        db.session.commit()
        flash("Priority updated successfully", "success")
        return redirect(url_for('cases.view', item_id=item_id))

    kwargs['update_priority_form'] = update_priority_form

     # UPDATE SENSITIVITY
    update_sensitivity_form = UpdateSensitivity()
    if 'sensitivity_submit' in request.form:
        item_id = request.form.get('item_id')
        item = Cases.query.get(item_id)
        item.sensitivity = update_sensitivity_form.sensitivity.data
        db.session.commit()
        flash("Sensitivity updated successfully", "success")
        return redirect(url_for('cases.view', item_id=item_id))

    kwargs['update_sensitivity_form'] = update_sensitivity_form

    
        
    _view = view_item(item, alias, item_name, table_name,
                      default_header=False,
                      default_buttons=False,
                      case_approved=case_approved,
                      view_only=view_only,
                      pending_submitters=pending_submitters,
                      delete_mod=delete_mod,
                      pending_mods=pending_mods,
                      pending_fields=json.dumps(pending_fields),
                      first_names=first_names,
                      last_names=last_names,
                      narratives=narratives,
                      containers=containers,
                      specimens=specimens,
                      tests=tests,
                      test_ids=test_ids,
                      components=components,
                      results=results,
                      reports=reports,
                      records=records,
                      bookings=bookings,
                      packets=packets,
                      test_comment_dict=test_comment_dict,
                      result_comment_dict=result_comment_dict,
                      batches_comment_dict=batches_comment_dict,
                      container_comment_dict=container_comment_dict,
                      specimen_comment_dict=specimen_comment_dict,
                      narrative_comment_dict=narrative_comment_dict,
                      custom_attachments=attachments,
                      show_attachments=False,
                      mods=mods,
                      today=datetime.now(),
                      kwargs=kwargs,
                      specimens_in_custody=specimens_in_custody,
                      pending_containers=pending_containers,
                      pending_specimens=pending_specimens,
                      all_pending_containers=all_pending_containers,
                      all_pending_specimens=all_pending_specimens,
                      discipline=discipline,
                      disciplines=disciplines,
                      review_discipline=review_discipline,
                      admin_specimens_in_custody=admin_specimens_in_custody,
                      result_counts=result_counts,
                      give_custody=give_custody,
                      **kwargs,
                      )
    return _view

    # return render_template(
    #     f'{table_name}/view.html',
    #     item=item,
    #     item_id=item.id,
    #     case_approved=case_approved,
    #     view_only=view_only,
    #     pending_submitters=pending_submitters,
    #     delete_mod=delete_mod,
    #     tooltips=tooltips,
    #     pending_mods=pending_mods,
    #     pending_fields=json.dumps(pending_fields),
    #     narratives=narratives,
    #     containers=containers,
    #     specimens=specimens,
    #     tests=tests,
    #     test_ids=test_ids,
    #     results=results,
    #     reports=reports,
    #     records=records,
    #     bookings=bookings,
    #     test_comment_dict=test_comment_dict,
    #     result_comment_dict=result_comment_dict,
    #     attachments=attachments,
    #     mods=mods,
    #     today=datetime.now(),
    #     kwargs=kwargs,
    #     specimens_in_custody=specimens_in_custody,
    #     pending_containers=pending_containers,
    #     pending_specimens=pending_specimens,
    #     discipline=discipline,
    #     form=form,
    #     **kwargs
    #     # pt_evals=distinct_evals,
    # )


@blueprint.route(f'/{table_name}/<int:item_id>/litigation_packet_print', methods=['GET', 'POST'])
@login_required
def litigation_packet(item_id):
    case = Cases.query.get_or_404(item_id)
    containers = db.session.query(Containers).filter(Containers.case_id == item_id)
    specimens = Specimens.query.filter_by(case_id=item_id).order_by(
        Specimens.accession_number.asc())
    generate_pdf(item_id, case, containers, specimens)


@blueprint.route(f'/{table_name}/<int:item_id>/litigation_packet', methods=['GET', 'POST'])
@login_required
def lit_packet_template(item_id):
    item = Cases.query.get_or_404(item_id)
    form = LitPacket()
    return render_template(
        f'{table_name}/lit_packet.html',
        item=item,
    )


@blueprint.route(f'/{table_name}/<int:item_id>/batches_pdf_print', methods=['GET', 'POST'])
@login_required
def batches_pdf_generation(item_id):
    case = Cases.query.get_or_404(item_id)
    generate_batches(item_id, case)
    return redirect(url_for('cases.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/litigation_packet_form', methods=['GET', 'POST'])
@login_required
def lit_packet_form(item_id):
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'generate_zip.html'
    form = LitPacketZip()
    all_cases = Cases.query.all()
    all_templates = LitPacketAdminTemplates.query.all()
    form.case_id.choices = [(case.id, f"{case.case_number}") for case in all_cases]
    form.case_id.data = Cases.query.get(item_id).case_number
    form.template_id.choices = [(templatename.id, f'{templatename.name}') for templatename in all_templates]
    redact = form.redact.data
    remove_pages = form.remove_pages.data
    item_type = 'Litigation Packet'
    item_name = 'Litigation Packets'
    table = LitigationPackets
    table_name = 'litigation_packets'
    name = 'id'  # This selects what property is displayed in the flash messages
    requires_approval = False  # controls whether the approval process is required. Can be set on a view level
    packet_id = request.args.get('packet_id')
    packet = LitigationPackets.query.filter_by(id=packet_id).first()
    packet_name = LitigationPackets.query.get(packet_id).packet_name# litigation_packets


    if form.is_submitted() and form.validate():
        # form.packet_name.data = f'{Cases.query.get(item_id).case_number}_L1'
        # form.case_id = item_id
        req = LitigationPacketRequest( # add packet id and so i can request later
                redact=redact,
                remove_pages=remove_pages,
                template_id=form.template_id.data,
                item_id=item_id,
                requested_by = current_user.initials,
                scheduled_exec = datetime.now(),
                packet_name=packet_name,
                db_status='Active',
                packet_id = packet_id
            )
        
        if form.schedule_generation.data is False:
            #if we wanna schedule, then schedule it. Otherwise just generate it
            req.scheduled_exec = form.scheduled_time.data
            flash(f"Litigation packet generation has been scheduled for {form.scheduled_time.data}", 'success')

        db.session.add(req)
        db.session.commit()
        return redirect(url_for('litigation_packets.view', item_id=packet_id))
        # _lit_packet_form = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)
        # return redirect(url_for('litigation_packets.view_list'))

    scheduled_lit_docs_exist = LitigationPacketRequest.query.filter_by(status='Scheduled').count() > 0

    kwargs['scheduled_lit_docs_exist'] = scheduled_lit_docs_exist
    _lit_packet_form = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _lit_packet_form


@blueprint.route(f'/{table_name}/<int:id>/run_now', methods=['POST'])
@login_required
def run_now(id):
    req = LitigationPacketRequest.query.get_or_404(id)
    req.scheduled_exec = datetime.now()
    db.session.commit()
    flash(f"Packet #{id} marked to run now. Check in a few minutes", "warning")
    return redirect(request.referrer or url_for('litigation_packets.index'))


@blueprint.route(f'/{table_name}/<int:item_id>/litigation_packet_creation', methods=['GET', 'POST'])
@login_required
def lit_packet_generation(item_id):
    kwargs = default_kwargs.copy()
    kwargs['template'] = 'lit_form.html'
    form = LitPacket()
    all_cases = Cases.query.all()
    # all_templates = LitPacketAdminTemplates.query.all()
    form.case_id.choices = [(case.id, f"{case.case_number}") for case in all_cases]
    # form.case_id.data = Cases.query.get(item_id).case_number
    # form.template_id.choices = [(0, 'None')] + [(templatename.id, f'{templatename.name}') for templatename in all_templates]
    # redact = form.redact.data
    # Populate agencies
    all_agencies = Agencies.query.all()
    form.agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in all_agencies]
    form.del_agency_id.choices = [(0, 'Please select an Agency')] + [(agency.id, agency.name) for agency in
                                                                     all_agencies]

    # Populate divisions based on selected agency
    if form.agency_id.data and form.agency_id.data != 0:
        divisions = Divisions.query.filter_by(agency_id=form.agency_id.data).all()
        form.division_id.choices = [(0, 'Please select a Division')] + [(division.id, division.name) for division in
                                                                        divisions]
    else:
        form.division_id.choices = [(0, 'Please select a Division')]

    # Populate personnel based on selected division
    if form.division_id.data and form.division_id.data != 0:
        personnel = Personnel.query.filter_by(division_id=form.division_id.data).all()
        form.personnel_id.choices = [(0, 'Please select Personnel')] + [(person.id, person.full_name) for person in
                                                                        personnel]
    else:
        form.personnel_id.choices = [(0, 'Please select Personnel')]
    item_type = 'Litigation Packet'
    item_name = 'Litigation Packets'
    table = LitigationPackets
    table_name = 'litigation_packets'
    name = 'id'  # This selects what property is displayed in the flash messages
    requires_approval = False  # controls whether the approval process is required. Can be set on a view level
    case_number = Cases.query.filter_by(id=item_id).first()
    print(case_number.case_number)
    # if form.is_submitted():
    #     form.case_id.data = item_id
    #     existing_packets = LitigationPackets.query.filter(
    #         LitigationPackets.packet_name.like(f"{case_number.case_number}_L%")
    #     ).all()
    #
    #     # Determine the next number in the sequence
    #     if existing_packets:
    #         max_number = max(
    #             int(packet.packet_name.split('_L')[-1]) for packet in existing_packets
    #         )
    #         next_number = max_number + 1
    #     else:
    #         next_number = 1
    #
    #     # Create the new packet name
    #     new_packet_name = f'{case_number.case_number}_L{next_number}'
    #     form.packet_status.data = 'Created'
    #     form.packet_name.data = new_packet_name
    #     form.case_id = item_id
    if form.is_submitted() and form.validate():
        # Fetch existing packets for the case number
        existing_packets = LitigationPackets.query.filter(
            LitigationPackets.packet_name.like(f"{case_number.case_number}_L%")
        ).all()

        if existing_packets:
            not_finalized_packet = None
            max_finalized_number = 0

            for packet in existing_packets:
                l_number = int(packet.packet_name.split('_L')[-1])
                if packet.packet_status == 'Finalized':
                    max_finalized_number = max(max_finalized_number, l_number)
                elif packet.packet_status != 'Canceled':
                    not_finalized_packet = packet

            if not_finalized_packet:
                session['form_data'] = request.form.to_dict(flat=False)
                return redirect(url_for('litigation_packets.confirm_packet_creation', item_id=not_finalized_packet.id))

            next_number = max_finalized_number + 1 if max_finalized_number > 0 else 1
            new_packet_name = f'{case_number.case_number}_L{next_number}'
            form.packet_name.data = new_packet_name
            form.packet_status.data = 'Created'

        else:
            new_packet_name = f'{case_number.case_number}_L1'
            form.packet_name.data = new_packet_name
            form.packet_status.data = 'Created'
        _lit_packet_form = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

        return redirect(url_for('litigation_packets.view_list'))

    _lit_packet_form = add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

    return _lit_packet_form


@blueprint.route(f'/{table_name}/<int:item_id>/update_retention_policy', methods=['GET', 'POST'])
@login_required
def update_retention_policy(item_id):
    if current_user.permissions not in ['Admin', 'Owner']:
        abort(403)

    item = table.query.get_or_404(item_id)

    kwargs = default_kwargs.copy()
    form = UpdateRetentionPolicy()
    kwargs['template'] = 'update_retention_policy.html'

    policies = [(item.id, item.name) for item in RetentionPolicies.query]
    policies.insert(0, (0, 'Please select a policy'))
    form.retention_policy.choices = policies

    form.type_id.choices = [(item.id, item.name) for item in
                            AttachmentTypes.query.filter_by(source='Retention Policies')]
    form.type_id.choices.insert(0, (0, 'Please select a type'))

    if item.retention:
        if item.retention.date_selection == 'Automatic':
            form.discard_date.render_kw = {'readonly': True}

    if request.method == 'POST':
        if form.validate_on_submit():
            if form.files.data:
                attach_items(form, item_id, table, item_name, table_name, name, source='Retention Policies')

    _update = update_item(form, item_id, table, item_type, item_name, table_name, False, name, locking=False, **kwargs)

    return _update


@blueprint.route(f'/{table_name}/get_policy_date_selection/', methods=['GET', 'POST'])
@login_required
def get_policy_date_selection():
    policy_id = request.args.get('policy_id', type=int)

    item = RetentionPolicies.query.get_or_404(policy_id)
    date_selection = item.date_selection

    return jsonify(date_selection=date_selection)


@blueprint.route(f'/{table_name}/get_age/', methods=['GET', 'POST'])
@login_required
def get_age():
    # convert dob and doi to datetime objects to pass into calculate_age function
    dob = datetime.strptime(request.args.get('dob'), '%Y-%m-%d')
    doi = datetime.strptime(request.args.get('doi'), '%Y-%m-%d')

    # Get the age string
    age = calculate_age(dob, doi)['age']

    return jsonify(age=age)


@app.route('/get_personnel/', methods=['GET'])
def get_personnel():
    agency_id = request.args.get('agency_id')
    if agency_id:
        personnel = Personnel.query.filter_by(agency_id=agency_id).all()
        data = [{'id': person.id, 'full_name': person.full_name} for person in personnel]
    else:
        data = []
    return jsonify(data)


@blueprint.route(f'/{table_name}/get_divisions/', methods=['GET', 'POST'])
@login_required
def get_divisions():
    agency_id = request.args.get('agency_id', type=int)
    case_type_id = request.args.get('case_type_id', type=int)

    divisions = Divisions.query.filter_by(agency_id=agency_id, client='Yes', db_status='Active')
    choices = []

    if agency_id:
        if divisions.count():
            choices.append({'id': 0, 'name': 'Please select a submitting division'})
            for division in divisions:
                choice = {}
                choice['id'] = division.id
                choice['name'] = division.name
                choices.append(choice)
        else:
            choices.append({'id': 0, 'name': 'This agency has no divisions'})
    else:
        choices.append({'id': 0, 'name': 'No agency selected'})

    default_client = 0
    if case_type_id:
        client = DefaultClients.query.filter_by(agency_id=agency_id, case_type_id=case_type_id).first()
        if client:
            default_client = client.division_id

    return jsonify({'divisions': choices, 'default_client': default_client})


@blueprint.route('/stock_jar', methods=['POST'])
@login_required
def print_stock_jar():
    data = request.get_json(silent=True)
    if not data or 'case_id' not in data:
        return jsonify({'error': 'Missing case_id'}), 400

    case_number = data['case_id']  # this is actually the case number string
    selected_case = Cases.query.filter_by(case_number=case_number).first()

    if not selected_case:
        return jsonify({'error': f'Case {case_number} not found'}), 404

    # Build attributes for the label
    label_attributes = fields_dict['stock_jar'].copy()
    label_attributes.update({
        'CASE_NUM': selected_case.case_number,
        'LAST': selected_case.last_name or '',
        'FIRST': selected_case.first_name or '',
        'DATE': datetime.now().strftime('%m/%d/%y'),
        'template': 'stock_jar'
    })

    printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'
    response_data = [( [label_attributes], printer, True, 1 )]

    return jsonify(response_data)




@blueprint.route(f'/autopsy_view', methods=['POST', 'GET'])
@login_required
def autopsy_view():
    # Update user.personnel_id if needed
    # for user in Users.query.all():
    #     for person in Personnel.query.all():
    #         if user.email == person.email:
    #             user.personnel_id = person.id

    # Initialize

    start = datetime.now()
    kwargs = default_kwargs.copy()
    form = get_autopsy_choices(AutopsyScan())
    items = db.session.query(table)
    alphabet = list(ascii_uppercase)

    printer = r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo'

    discipline_lookup = {v: k for k, v in discipline_codes.items()}

    start_time = datetime.now()

    # Get only PM cases
    items = items.filter(table.case_type == CaseTypes.query.filter_by(code='PM').first().id)
    item_ids = [item.id for item in items]
    unique_name = 'Autopsy View'
    kwargs['length'] = 300
    query = request.args.get('query')
    lower_disciplines = ['toxicology', 'histology', 'physical', 'biochemistry', 'drug']

    all_containers = []
    all_specimens = []

    chunk_size = 1000

    for chunk in chunks(item_ids, chunk_size):
        all_containers.extend(Containers.query.filter(and_(Containers.case_id.in_(chunk),
                                                           Containers.db_status != 'Removed')).all())
        all_specimens.extend(Specimens.query.filter(and_(Specimens.case_id.in_(chunk),
                                                         Specimens.db_status != 'Removed')).all())

    # Need to "Chunk" query
    # all_containers = Containers.query.filter(Containers.case_id.in_(item_ids[:900])).all()
    # all_containers = db.session.query(Containers).filter(Containers.case_id.in_(item_ids)).all()

    submitted_containers = defaultdict(lambda: defaultdict(lambda: {'code': [], 'type': {}}))
    open_containers = defaultdict(lambda: defaultdict(lambda: {'code': [], 'type': {}}))
    submitted_specimens = defaultdict(lambda: defaultdict(lambda: {'code': [], 'type': {}}))

    for container in all_containers:
        d = container.discipline.lower()
        if d not in lower_disciplines:
            continue

        if container.submission_time is None:
            open_containers[container.case_id][d]['code'].append(container)
            open_containers[container.case_id][d]['type'][container.id] = container.type.name
        else:
            submitted_containers[container.case_id][d]['code'].append(container)
            submitted_containers[container.case_id][d]['type'][container.id] = container.type.name

    for specimen in all_specimens:
        d = specimen.discipline.lower()
        if d not in lower_disciplines:
            continue

        else:
            submitted_specimens[specimen.case_id][d]['code'].append(specimen)
            submitted_specimens[specimen.case_id][d]['type'][specimen.id] = specimen.type.name

    # Order the table and set the page
    order_by = table.id.desc()
    page = request.args.get('page', 1, type=int)

    # Apply ordering to the query
    items = items.order_by(order_by)

    # Paginate the query
    items = items.paginate(page=page, per_page=kwargs['length'], max_per_page=None)

    # Dictionary of submit buttons and corresponding information
    submit_dict = {
        'submit_toxicology_print': ['Toxicology (N)', 'Bag', 'By Location', 'Cooled Storage', CooledStorage,
                                    '08R', 'Toxicology'],
        'submit_physical_print': ['Physical (N)', 'No Container', 'By Location', 'Benches', Benches, 'BS60',
                                  'Physical'],
        'submit_physical_sa_print': ['Physical (SA)', 'Bag', 'By Location', 'Benches', Benches, 'BS60', 'Physical'],
        'submit_bundle_print': ['Physical (Bundle)', 'Bag', 'By Location', 'Benches', Benches, 'BS60', 'Physical'],
        'submit_histology_print': ['Histology(T)', 'Jar', 'By Location', 'Benches', Benches, 'BS60', 'Histology'],
        'submit_histology_sa_print': ['Histology(S)', 'Slide Holder', 'By Location', 'Benches', Benches, 'BS60',
                                      'Histology'],
        'submit_drug_print': ['Drug', 'Bag', 'By Location', 'Benches', Benches, 'BS60', 'Drug'],
    }

    # new_submit_dict = {
    # button: [Button text, {discipline:[container, submission_route_type, location_type, location_table, equipment_id]}
    # {label_type: number of labels}]}
    new_submit_dict = {
        'submit_toxicology_print': [
            'Autopsy', {
                'Toxicology': ['Bag', 'By Location', 'Cooled Storage', CooledStorage, '08R'],
                'Physical': ['No Container', 'By Location', 'Benches', Benches, 'BS60']
            },
            {'generic': 8, 'photocard': 1, 'histo_stock_jar': 1}
        ],

        'submit_physical_print': [
            'Admin Review', {
                'Toxicology': ['Bag', 'By Location', 'Cooled Storage', CooledStorage, '08R'],
                'Physical': ['No Container', 'By Location', 'Benches', Benches, 'BS60']
            },
            {'generic': 7, 'photocard': 1, 'histo_stock_jar': 0}
        ],

        'submit_bundle_print': [
            'Homicide (Bundle)', {
                'Toxicology': ['Bag', 'By Location', 'Cooled Storage', CooledStorage, '08R'],
                'Physical': ['Bag', 'By Location', 'Benches', Benches, 'BS60']
            },
            {'generic': 12, 'photocard': 1, 'histo_stock_jar': 1}
        ],

        'submit_histology_print': [
            'Histology(T)', {
                'Histology': ['Jar', 'By Location', 'Benches', Benches, 'BS60']
            },
            {'generic': 0, 'photocard': 0, 'histo_stock_jar': 0}
        ],

        'submit_histology_sa_print': [
            'Histology(S)', {
                'Histology': ['Slide Holder', 'By Location', 'Benches', Benches, 'BS60']
            },
            {'generic': 0, 'photocard': 0, 'histo_stock_jar': 0}
        ]
    }

    # Determine button clicked, set relevant variables, add new container, print labels
    if form.is_submitted():
        # Check if barcode scanned in

        attributes_list = [] # each item is a label job

        # Check if specimens form submitted
        if 'submit_scan' in request.form:


            print(f"SUBMIT_SCAN")
            # Get selected case from form
            selected_case = Cases.query.get(form.cases_selected.data)

            # Initialize other_desc
            other_desc = None

            # Get dynamically created form data
            form_dict = request.form.to_dict()

            # Initialize list of container ids
            containers = []

            # Iterate through all form data
            for field_name, field_value in form_dict.items():
                
                is_locker = False


                # Work with each row by isolating barcode field
                if 'barcode' in field_name and field_value != '':
                    
                    print(form_dict)
                    # Get all form data
                    # Find row number, use re to account for numbers > 9
                    row_num = re.search(r'\d+$', field_name)
                    row_num = row_num.group() if row_num else None
                    discipline = form_dict[f'discipline{row_num}']
                    specimen_type_id = SpecimenTypes.query.filter_by(name=form_dict[f'barcode{row_num}']).all()
            
                    # Look for other description if it exists on submit
                    if f'specOther{row_num}' in form_dict.keys():
                        other_desc = form_dict[f'specOther{row_num}']
                    else:
                        other_desc = None

                    # Check if specimen has multiple entries in specimen_types
                    if len(specimen_type_id) > 1:
                        for specimen in specimen_type_id:
                            # Find correct specimen_type by discipline
                            if discipline in specimen.discipline:
                                specimen_type_id = specimen.id
                    else:
                        specimen_type_id = specimen_type_id[0].id

                    collection_vessel_id = form_dict[f'collectionVessel{row_num}']
                    amount = form_dict[f'amount{row_num}']
                    container_id = form_dict[f'container{row_num}']
                    containers.append(container_id)

                    # Get conditions list and join if conditions exist
                    try:
                        condition = ', '.join(request.form.getlist(f'condition{row_num}'))
                    except KeyError:
                        condition = ''
                    collection_date = datetime.strptime(form_dict[f'collectionDate{row_num}'], '%Y-%m-%d').date()
                    collection_time = form_dict[f'collectionTime{row_num}']
                    collected_by = int(form_dict[f'collectedBy{row_num}'])
                    custody_type = form_dict[f'custodyLocation{row_num}']

                    custody = form_dict[f'custody{row_num}']

                    print("Custody type for",custody_type)
                    if custody_type == 'Evidence Lockers':
                        is_locker = True
                        #TODO idk if we need this logic. Does autopsy test clicking submit amount to adding the container?? idk if custody=equipemtn id it looked like it
                        locker = EvidenceLockers.query.filter_by(equipment_id=custody).first()
                        locker.occupied = True



                    # Initialize specimen add form
                    specimen_form = get_specimen_choices(SpecimenAdd(formdata=None), int(container_id),
                                                         int(form.cases_selected.data), custody_type, discipline)
                    # Initialize evidence comments form
                    evidence_comment_form = get_evidence_comments(EvForm())
                    kwargs['evidence_comment_form'] = evidence_comment_form

                    # Fill in specimen add form data
                    specimen_form.case_id.data = selected_case.id
                    specimen_form.container_id.data = int(container_id)
                    specimen_form.discipline.data = discipline
                    specimen_form.specimen_type_id.data = specimen_type_id
                    specimen_form.collection_date.data = datetime.combine(collection_date,
                                                                          datetime.strptime('0000',
                                                                                            '%H%M').time())
                    specimen_form.collection_time.data = collection_time
                    specimen_form.submitted_sample_amount.data = amount
                    specimen_form.collection_container_id.data = int(collection_vessel_id)
                    specimen_form.collected_by.data = collected_by
                    specimen_form.condition.data = condition
                    specimen_form.custody_type.data = custody_type
                    specimen_form.custody.data = custody
                    specimen_form.submit.data = True
                    specimen_form.evidence_comments.data = ''
                    if other_desc is not None:
                        specimen_form.other_specimen.data = other_desc

                    # Initialize modifications dictionary
                    mod_dict = {}

                    # Set specimen ignor_fields
                    specimen_ignore_fields = ['custody_type', 'custody', 'start_time', 'submit', 'communications',
                                              'csrf_token', 'db_status', 'locked', 'create_date', 'revision',
                                              'pending_submitter', 'accessioned_by', 'accession_date',
                                              'evidence_comments', 'current_sample_amount', 'accession_number',
                                              'condition', 'created_by']

                    # Iterate through specimen add form and handle specific field types for modifications
                    for field in specimen_form:
                        if field.type == 'SelectField':
                            mod_dict[field.name] = [dict(field.choices).get(field.data), field.label.text]
                        else:
                            mod_dict[field.name] = [field.data, field.label.text]

                    # Get kwargs from processing specimen add form
                    kwargs.update(specimen_process(specimen_form, event='Add'))

                    # Initialize field_data dictionary
                    field_data = {}

                    # Update dictionary with relevant specimens data
                    field_data.update({
                        'db_status': 'Pending',
                        'locked': False,
                        'create_date': datetime.now(),
                        'created_by': current_user.initials,
                        'revision': 0,
                        'pending_submitter': current_user.initials,
                        'case_id': selected_case.id,
                        'container_id': container_id,
                        'discipline': discipline,
                        'specimen_type_id': specimen_type_id,
                        'collection_date': specimen_form.collection_date.data,
                        'collection_time': collection_time,
                        'submitted_sample_amount': amount,
                        'collection_container_id': collection_vessel_id,
                        'collected_by': collected_by,
                        'condition': condition,
                        'custody_type': custody_type,
                        'custody': custody,
                        'accession_number': kwargs['accession_number'],
                        'current_sample_amount': kwargs['current_sample_amount'],
                        'evidence_comments': kwargs['evidence_comments'],
                        'accession_date': kwargs['accession_date'],
                        'accessioned_by': kwargs['accessioned_by'],
                        'start_time': start_time,
                        'other_specimen': other_desc if other_desc is not None else None
                    })

                    # Get specimen record_id
                    record_id = Specimens.get_next_id()

                    # Set modifications for each specimen field
                    for k, v in field_data.items():
                        if k not in specimen_ignore_fields:
                            modification = Modifications(event='CREATED', status='Pending', table_name='Specimens',
                                                         record_id=record_id, revision=0,
                                                         field=mod_dict.get(k)[1], field_name=k, new_value=v,
                                                         new_value_text=mod_dict.get(k)[0],
                                                         submitted_by=current_user.id,
                                                         submitted_date=datetime.now(), reviewed_by=None,
                                                         review_date=None)

                            db.session.add(modification)

                    # Add specimen and modification to database
                    item = Specimens(**field_data)

                    db.session.add(item)

                    # Increment specimens submitted number for container
                    Containers.query.get(int(container_id)).n_specimens_submitted += 1

                    db.session.commit()

                    # Add specimen audit
                    process_audit(specimen_form, from_autopsy=True)

                    # Add specimen data to attributes_list
                    label_attributes = fields_dict['specimen']
                    
                    print("THE ID THERE IS",kwargs['accession_number'])


                    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                           f'specimen{record_id}.png')
                    qrcode.make(f's: {record_id}').save(qr_path)

                    with open(qr_path, "rb") as qr_file:
                        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                    label_attributes['LAST_FIRST'] = f'{selected_case.last_name}, {selected_case.first_name}'
                    label_attributes['CASE_NUM'] = selected_case.case_number
                    label_attributes['ACC_NUM'] = kwargs['accession_number']
                    label_attributes['CODE'] = f'[{SpecimenTypes.query.get(specimen_type_id).code}]'
                    if other_desc is not None:
                        label_attributes['TYPE'] = f'{SpecimenTypes.query.get(specimen_type_id).name} ({other_desc})'
                    else:
                        label_attributes['TYPE'] = SpecimenTypes.query.get(specimen_type_id).name
                    label_attributes['QR'] = qr_encoded

                    attributes_list.append(label_attributes.copy())

                    accession_num = Containers.query.get(int(container_id)).accession_number

                    container = Containers.query.filter_by(accession_number=accession_num).first()
                    container.submission_route_type = 'By Location'
                    container.location_type = custody_type
                    container.submission_route = custody
                    qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs', f'container{container.id}.png')
                    qrcode.make(f'containers: {container.id}').save(qr_path)

                    with open(qr_path, "rb") as qr_file:
                        qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                    # is_inv = True
                    print("status of the locker variable", is_locker)

                    cont_record = Modifications.query.filter_by(record_id=str(container.id), field_name='submission_route').first()
                    cont_submit_record = Modifications.query.filter_by(record_id=str(container.id), field_name='submitted_by').first()

                    cont_record.original_value = None
                    cont_record.original_value_text = None
                    cont_record.new_value = custody
                    cont_record.new_value_text = custody
                    cont_record.submitted_by = current_user.id
                    cont_record.submitted_date = datetime.now()

                    cont_submit_record.original_value = None
                    cont_submit_record.original_value_text = None
                    cont_submit_record.new_value = current_user.id
                    cont_submit_record.new_value_text = current_user.full_name
                    cont_submit_record.submitted_by = current_user.id
                    cont_submit_record.submitted_date = datetime.now()

                    # # Container modification for submission_route
                    # modification = Modifications(event='UPDATED', status='Pending', table_name='Containers',
                    #                                      record_id=str(container.id), revision=1,
                    #                                      field='Submission Location', field_name='submission_route', new_value=custody,
                    #                                      new_value_text=custody,
                    #                                      submitted_by=current_user.id,
                    #                                      submitted_date=datetime.now(), reviewed_by=None,
                    #                                      review_date=None)

                    # db.session.add(modification)
                    db.session.commit()

                    
                    if is_locker:
                        label_attributes = fields_dict['container']
                        label_attributes['CASE_NUM'] = selected_case.case_number
                        label_attributes['ACC_NUM'] = container.accession_number
                        label_attributes['CODE'] = custody
                        label_attributes['QR'] = qr_encoded
                        label_attributes['TYPE'] = ''
                        label_attributes['DISCIPLINE'] = container.discipline
                        is_locker = False
                        attributes_list.append(label_attributes.copy())


            # Set container submission time
            containers = set(containers)
            for container in containers:
                Containers.query.get(int(container)).submission_date = \
                    datetime.combine(datetime.now().date(), datetime.strptime('0000', '%H%M').time())
                Containers.query.get(int(container)).submission_time = datetime.now().strftime('%H%M')

            db.session.commit()


            # Print labels for all submitted specimens
            # print_label(printer, attributes_list, True, 1)

            print(attributes_list)
            return jsonify([(attributes_list, printer, True, 1, url_for('cases.autopsy_view', ))])

            # return redirect(url_for('cases.autopsy_view'))
        elif 'submit_histo_scan' in request.form:
            # Get relevant information from scan
            print(f"HISTO SCAN")
            discipline_letter = form.initial_label.data.split('; ')[0].split(': ')[1].strip()

            if discipline_letter != 'H':
                flash('Only histology specimens should be submitted using this workflow', 'error')

                return jsonify([(None, None, None, None, url_for('cases.autopsy_view', ))])
                # return redirect(url_for('cases.autopsy_view'))

            # case_id = int(form.initial_label.data.split(';')[0].split(': ')[1].strip())
            case_number = form.initial_label.data.split(';')[1].split(': ')[1].split('_')[0].strip()
            case_id = Cases.query.filter_by(case_number=case_number).first().id
            discipline = discipline_lookup[discipline_letter]

            accession_letter = ''
            container_id = ''

            # Initialize accession number for histology
            accession_number = None

            if discipline == 'Histology':
                accession_number = form.initial_label.data.split(';')[1].split(': ')[1].strip()
                accession_letter = accession_number[-2]

            # Get container ID
            containers = Containers.query.filter(and_(Containers.case_id == case_id,
                                                      Containers.submission_time == None,
                                                      Containers.discipline == discipline)).all()

            for container in containers:
                if accession_letter in container.accession_number:
                    container_id = container.id

            if accession_number:
                print(f"ACCESSION NUMBER IS THERE")

                return jsonify([(None, None, None, None,
                                 url_for('specimens.add', case_id=case_id, accession_number=accession_number,
                                         container_id=container_id, discipline=discipline, from_autopsy=True,
                                         histology=True, ))])
                # return redirect(url_for('specimens.add', case_id=case_id, accession_number=accession_number,
                #                         container_id=container_id, discipline=discipline, from_autopsy=True,
                #                         histology=True))
            else:
                # return redirect(url_for('specimens.add', case_id=case_id, specimen_type=specimen_type,
                #                         container_id=container_id, discipline=discipline, from_autopsy=True))

                print(f"NO ACCESSION NUMBER")
                flash('Only histology specimens should be submitted using this workflow', 'warning')
                return jsonify([(None, None, None, None, url_for('cases.autopsy_view', ))])
                # return redirect(url_for('cases.autopsy_view'))
        elif 'submit_generic_print' in request.form:
            # Generic label
            print(f"GENERIC")
            selected_case = Cases.query.get(form.cases_selected.data)
            label_attributes = fields_dict['generic']
            label_attributes['LAST'] = selected_case.last_name if selected_case.last_name is not None else ''
            label_attributes['FIRST'] = selected_case.first_name if selected_case.first_name is not None else ''
            label_attributes['CASE_NUM'] = selected_case.case_number
            label_attributes['DOC'] = f'{datetime.now().strftime("%m")}/{datetime.now().strftime("%d")}/' \
                                      f'{datetime.now().strftime("%y")}'
            label_attributes['LABEL_TYPE'] = ''
            attributes_list.append(label_attributes.copy())
            # print_label(printer, attributes_list, True, 1)

            return jsonify([(attributes_list, printer, True, 1)])
        elif 'submit_other_print' in request.form:
            
            quantities = {
                int(k.replace("specimen_quantity_", "")): int(v)
                for k, v in request.form.items()
                if k.startswith("specimen_quantity_") and v.strip().isdigit() and int(v) > 0
            }

            print(quantities)

            for specimen_type_id, quantity in quantities.items():
                
                form.specimen_type.data = specimen_type_id
                selected_case = Cases.query.get(form.cases_selected.data)
                specimen_type = SpecimenTypes.query.get(int(specimen_type_id))
                discipline_label = discipline_lookup[specimen_type.code[0]]


                # Try to get unsubmitted container that matches discipline
                try:
                    container_id = Containers.query.filter(and_(Containers.case_id == selected_case.id,
                                                                Containers.submission_time == None,
                                                                Containers.discipline == discipline_label)).first().id

                # If no container is available, create new container and print container label
                except AttributeError:

                    container_type = None
                    location_type = None
                    submission_route = None

                    if discipline_label == 'Toxicology' or discipline_label == 'Biochemistry':
                        container_type = ContainerTypes.query.filter_by(name='Bag').first().id
                        location_type = 'Cooled Storage'
                        submission_route = '08R'

                    elif discipline_label == 'Drug':
                        container_type = ContainerTypes.query.filter_by(name='Bag').first().id
                        location_type = 'Evidence Lockers'
                        submission_route = 'Initial'
                    elif discipline_label == 'Physical':
                        container_type = ContainerTypes.query.filter_by(name='Bag').first().id
                        location_type = 'Benches'
                        submission_route = 'BS60'

                    kwargs.update(add_new_container(container_type, form, 'By Location', location_type, submission_route,
                                                    discipline_label))

                    container_id = kwargs['container_id']

                # Set specimen label properties
                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                    f'autopsy_view{selected_case.id}{specimen_type.id}.png')
                qrcode.make(f'co: {container_id}; st: {specimen_type.id}').save(qr_path)
                label_attributes = fields_dict['initial_labels']
                label_attributes['CASE_NUM'] = selected_case.case_number
                label_attributes['DATE'] = f'{datetime.now().strftime("%m")}/{datetime.now().strftime("%d")}/' \
                                        f'{datetime.now().strftime("%y")}'
                label_attributes['LAST'] = selected_case.last_name if selected_case.last_name is not None else ''
                label_attributes['FIRST'] = selected_case.first_name if selected_case.first_name is not None else ''
                label_attributes['CODE'] = f'[{specimen_type.code}]'
                label_attributes['TYPE'] = specimen_type.name

                with open(qr_path, "rb") as qr_file:
                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                label_attributes['QR'] = qr_encoded

                for i in range(quantity):
                    # Append label attributes to attributes_list
                    attributes_list.append(label_attributes.copy())

            # Print specimen label
            # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
            # print_label(printer, attributes_list, True, 1)

            return jsonify([(attributes_list, printer, True, 1)])
        elif 'submit_five_generic' in request.form:
            # Generic label
            print(f"FIVE GENERIC")
            selected_case = Cases.query.get(form.cases_selected.data)
            label_attributes = fields_dict['generic']
            label_attributes['LAST'] = selected_case.last_name if selected_case.last_name is not None else ''
            label_attributes['FIRST'] = selected_case.first_name if selected_case.first_name is not None else ''
            label_attributes['CASE_NUM'] = selected_case.case_number
            label_attributes['DOC'] = f'{datetime.now().strftime("%m")}/{datetime.now().strftime("%d")}/' \
                                      f'{datetime.now().strftime("%y")}'
            label_attributes['LABEL_TYPE'] = ''

            for i in range(0, 5):
                attributes_list.append(label_attributes.copy())
            # print_label(printer, attributes_list, True, 1)
            # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
            return jsonify([(attributes_list, printer, True, 1)])
        else:
            # Search submit type in dict
            print(f"SUBMIT HISTOLOGY PRINT IS IN ELSE BLOCK")
            for submit in submit_dict.keys():
                if submit in request.form:

                    # Initialize variables
                    label_attributes = {}
                    attributes_list = []
                    attributes_list_generic = []

                    # Get relevant information based on submit type
                    button, discipline_dict, labels_dict = new_submit_dict[submit]

                    # Get labels from button template
                    labels = AutopsyViewButtons.query.filter_by(button=button).first()

                    # Make array of labels
                    if labels:
                        specimen_types = labels.specimen_types.split(', ')
                    else:
                        specimen_types = []

                    # Initialize specimen disciplines dict
                    specimen_disciplines = {}
                    dup_specimens = {}
                    # Build specimen_disciplines dict with specimen as key and discipline as value
                    if len(specimen_types) > 0:
                        for specimen in specimen_types:
                            specimen_disciplines[specimen] = SpecimenTypes.query.get(int(specimen)).discipline

                    # Get case selection and relevant case data
                    selected_case = Cases.query.get(form.cases_selected.data)
                    case_number = selected_case.case_number
                    last_name = selected_case.last_name if selected_case.last_name is not None else ''
                    first_name = selected_case.first_name if selected_case.first_name is not None else ''

                    # Set date of collection
                    doc = f'{datetime.now().strftime("%m")}/{datetime.now().strftime("%d")}/' \
                          f'{datetime.now().strftime("%y")}'

                    # Iterate through discipline_dicts from submission and set relevant data
                    for key in discipline_dict.keys():
                        container_type, submission_route_type, location_type, location_table, equipment_id = \
                            discipline_dict[key]

                        # Get container type id and set submission_route
                        container_type = ContainerTypes.query.filter_by(name=container_type).first().id
                        submission_route = equipment_id

                        # Initialize arrays
                        codes = []
                        types = []
                        qrs = []

                        # Set discipline
                        discipline = key

                        # Add container, function prints labels
                        kwargs.update(add_new_container(container_type, form, submission_route_type, location_type,
                                                        submission_route, discipline))
                        # Check if discipline is not histology
                        print(f"DISCIPLINE IS {discipline}")
                        if discipline != 'Histology':
                            # Set label attributes
                            label_attributes = fields_dict['initial_labels']

                            # Check if specimen_types have been pulled from submission
                            if specimen_types:
                                # Iterate through each specimen type
                                for specimen in specimen_types:
                                    # Make sure discipline matches specimen_discipline
                                    if discipline in specimen_disciplines[specimen]:
                                        # Get current specimen information
                                        current_specimen = SpecimenTypes.query.get(int(specimen))
                                        current_specimen_name = list(current_specimen.name)
                                        code_list = current_specimen.code

                                        if code_list in dup_specimens.keys():
                                            dup_specimens[code_list] += 1
                                            current_specimen_name = f'{current_specimen_name} ' \
                                                                    f'{str(dup_specimens[code_list])}'
                                        else:
                                            dup_specimens[code_list] = 1

                                        # Set letter counting variable
                                        y = 0

                                        # Iterate through specimen name and break line at necessary characters
                                        chars = list(current_specimen_name)

                                        if len(chars) > 48:
                                            chars.insert(48, '-\n')
                                        if len(chars) > 24:
                                            chars.insert(24, '-\n')

                                        current_specimen_name = ''.join(chars)

                                        # Set label information in relevant arrays
                                        codes += [f"[{code_list}]"]
                                        types += [current_specimen_name]
                                        qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                                               f'initial{current_specimen.id}.png')
                                        qrcode.make(f'co: {kwargs["container_id"]}; st: {current_specimen.id}').save(
                                            qr_path)

                                        with open(qr_path, "rb") as qr_file:
                                            qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')

                                        qrs += [qr_encoded]

                        # If discipline is histology, use histology labels
                        elif discipline == 'Histology':
                            # Get histology label attributes
                            label_attributes = fields_dict['histo_initial']

                            # Get parent container letter for labels
                            container_letter = \
                                Containers.query.filter(and_(Containers.case_id == form.cases_selected.data,
                                                             Containers.discipline == discipline)).order_by(
                                    Containers.accession_number.desc())[0].accession_number[-2]

                            latest_container = Containers.query.filter(
                                and_(
                                    Containers.case_id == form.cases_selected.data,
                                    Containers.discipline == discipline
                                )
                            ).order_by(Containers.accession_number.desc()).first()

                            print(f"Container.accession_number IS {latest_container.accession_number}")
                            # Initialize accesion_number array
                            acc_nums = []
                            print(f"CONTAINER LETTER {container_letter}")
                            # Limit name length to fit on labels
                            if len(last_name) > 13:
                                last_name = last_name[:13]
                            if len(first_name) > 13:
                                first_name = first_name[:13]

                            # Create 9 labels for histology specimens
                            for i in range(1, 10):
                                qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
                                                       f'histo_initial{selected_case.id}_{i}.png')
                                qrcode.make(f'di: H; an: {case_number}_{container_letter}{i}').save(qr_path)

                                with open(qr_path, "rb") as qr_file:
                                    qr_encoded = base64.b64encode(qr_file.read()).decode('utf-8')
                                qrs += [qr_encoded]

                                acc_nums += [f'{case_number}_{container_letter}{i}']

                        # Every initial label needs to be printed HERE
                        counter = 0
                        # Using qrs to iterate through each label and print all labels
                        for x in qrs:
                            if discipline == 'Histology':
                                # Set histology label attributes
                                for y in range(0, 2):
                                    label_attributes['ACC_NUM'] = acc_nums[counter]
                                    label_attributes['FIRST'] = first_name
                                    label_attributes['LAST'] = last_name
                                    label_attributes['QR'] = qrs[counter]
                                    label_attributes['DATE'] = doc

                                    attributes_list.append(label_attributes.copy())

                                # Print initial labels to autopsy printer, left roll
                                # print_label(printer, attributes_list, True, 0)

                                counter += 1
                            else:
                                # Set all other label attributes
                                label_attributes['CASE_NUM'] = case_number
                                label_attributes['DATE'] = doc
                                label_attributes['LAST'] = last_name
                                label_attributes['FIRST'] = first_name
                                label_attributes['CODE'] = codes[counter]
                                label_attributes['TYPE'] = types[counter]
                                label_attributes['QR'] = qrs[counter]

                                attributes_list.append(label_attributes.copy())

                                counter += 1

                    # Add generic labels if defined by submission type
                    label_attributes_generic = fields_dict['generic']
                    if labels_dict['generic'] > 0:
                        attributes_list_generic = []
                        label_attributes_generic['LAST'] = last_name
                        label_attributes_generic['FIRST'] = first_name
                        label_attributes_generic['CASE_NUM'] = case_number
                        label_attributes_generic['DOC'] = doc
                        label_attributes_generic['LABEL_TYPE'] = ''

                        for i in range(0, labels_dict['generic']):
                            attributes_list_generic.append(label_attributes_generic.copy())

                    # label_attributes_extra = fields_dict['bundle']
                    # attributes_list_extra = []

                    # Add photocard labels if defined by submission type
                    if labels_dict['photocard'] > 0:
                        label_attributes_generic['LAST'] = last_name
                        label_attributes_generic['FIRST'] = first_name
                        label_attributes_generic['CASE_NUM'] = case_number
                        label_attributes_generic['DOC'] = doc
                        label_attributes_generic['LABEL_TYPE'] = 'Photocard'
                        for i in range(0, labels_dict['photocard']):
                            attributes_list_generic.append(label_attributes_generic.copy())

                    # if 'Homicide' in button:
                    #     label_attributes_generic['LAST'] = ''
                    #     label_attributes_generic['FIRST'] = ''
                    #     for i in range(0, 4):
                    #         label_attributes_generic['CASE_NUM'] = 'Wet'
                    #         attributes_list_generic.append(label_attributes_generic.copy())
                    #         label_attributes_generic['CASE_NUM'] = 'Dry'
                    #         attributes_list_generic.append(label_attributes_generic.copy())

                    # Add histology stock jar labels if defined by submission type
                    attributes_list_histo = []
                    if labels_dict['histo_stock_jar'] > 0:
                        label_attributes_histo = fields_dict['stock_jar']
                        label_attributes_histo['CASE_NUM'] = case_number
                        label_attributes_histo['LAST'] = last_name
                        label_attributes_histo['FIRST'] = first_name
                        label_attributes_histo['DATE'] = doc
                        # Get relevant histology stock jar template based on submission type
                        if button == 'Autopsy':
                            label_attributes_histo['template'] = 'stock_jar'
                        elif 'Homicide' in button:
                            label_attributes_histo['template'] = 'stock_jar_h'

                        attributes_list_histo.append(label_attributes_histo.copy())

                    response_data = []

                    # Print histology labels to left side roll
                    if 'Histology' in button:
                        # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 0)
                        # print_label(printer, attributes_list, True, 0)
                        # return jsonify(attributes_list, printer, True, 0)
                        response_data.append((attributes_list, printer, True, 0))

                    # Print all other labels to right side roll
                    else:
                        # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
                        # print_label(printer, attributes_list, True, 1)
                        # return jsonify(attributes_list, printer, True, 1)
                        response_data.append((attributes_list, printer, True, 1))

                    # Print additional labels to right side roll
                    if len(attributes_list_generic) > 0:
                        # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list_generic, True, 1)
                        # print_label(printer, attributes_list_generic, True, 1)
                        # return jsonify(attributes_list_generic, printer, True, 1)
                        response_data.append((attributes_list_generic, printer, True, 1))

                    if len(attributes_list_histo) > 0:
                        # print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list_histo, True, 1)
                        # print_label(printer, attributes_list_histo, True, 1)
                        # return jsonify(attributes_list_histo, printer, True, 1)
                        response_data.append((attributes_list_histo, printer, True, 1))

                    return jsonify(response_data)

    print(f'AUTOPSY VIEW: {datetime.now() - start}')

    return render_template(f'{table_name}/autopsy_view.html',
                           items=items, item_name=unique_name, form=form, kwargs=kwargs,
                           open_containers=open_containers, submitted_containers=submitted_containers,
                           submitted_specimens=submitted_specimens, lower_disciplines=lower_disciplines)


        #             # *****EVERYTHING BELOW IS OLD*****
        #             button, container_type, submission_route_type, location_type, location_table, equipment_id, \
        #                 discipline = submit_dict[submit]
        #             print(button)
        #             print(container_type)
        #             print(discipline)
        #             # Get container type and submission route
        #             container_type = ContainerTypes.query.filter_by(name=container_type).first().id
        #             # submission_route = location_table.query.filter_by(equipment_id=equipment_id).first().id
        #             submission_route = equipment_id
        #             print(f'SUBMISSION ROUTE === {submission_route}')
        #             print(f'equipmenID ==== {equipment_id}')
        #             codes = []
        #             types = []
        #             qrs = []
        #             selected_case = Cases.query.get(form.cases_selected.data)
        #             case_number = selected_case.case_number
        #             last_name = selected_case.last_name
        #             first_name = selected_case.first_name
        #             doc = f'{datetime.now().strftime("%m")}/{datetime.now().strftime("%d")}/' \
        #                   f'{datetime.now().strftime("%y")}'

        #             # Add container, function prints labels
        #             kwargs.update(add_new_container(container_type, form, submission_route_type, location_type,
        #                                             submission_route, discipline))

        #             if discipline != 'Histology':
        #                 label_attributes = fields_dict['initial_labels']
        #                 # Break up specimen type strings into multiple lines if too long
        #                 if specimen_types:
        #                     for specimen in specimen_types:
        #                         current_specimen = SpecimenTypes.query.get(int(specimen))
        #                         current_specimen_name = list(current_specimen.name)
        #                         code_list = current_specimen.code
        #                         y = 0
        #                         for x in current_specimen_name:
        #                             y += 1
        #                             if y == 24:
        #                                 current_specimen_name.insert(y, '-\n')
        #                             if y == 48:
        #                                 current_specimen_name.insert(y, '-\n')
        #                         codes += [f"[{code_list}]"]
        #                         types += [''.join(current_specimen_name)]
        #                         qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
        #                                                f'initial{current_specimen.id}.png')
        #                         qrcode.make(f'co: {kwargs["container_id"]}; st: {current_specimen.id}').save(
        #                             qr_path)

        #                         qrs += [qr_path]

        #             # If discipline is histology, use histology labels
        #             elif discipline == 'Histology':
        #                 # CUT OFF NAMES AFTER 13th CHARACTER
        #                 label_attributes = fields_dict['histo_initial']
        #                 container_letter = Containers.query.filter(and_(Containers.case_id == form.cases_selected.data,
        #                                                                 Containers.discipline == discipline)).order_by(
        #                     Containers.accession_number.desc())[0].accession_number[-2]

        #                 acc_nums = []

        #                 if len(last_name) > 13:
        #                     last_name = last_name[:13]
        #                 if len(first_name) > 13:
        #                     first_name = first_name[:13]

        #                 for i in range(1, 10):
        #                     qr_path = os.path.join(current_app.root_path, 'static', 'label_qrs',
        #                                            f'histo_initial{selected_case.id}_{i}.png')
        #                     qrcode.make(f'di: H; an: {case_number}_{container_letter}{i}').save(qr_path)

        #                     qrs += [qr_path]

        #                     acc_nums += [f'{case_number}_{container_letter}{i}']

        #             # Every initial label needs to be printed HERE
        #             counter = 0
        #             # Using qrs to iterate through each label and print all labels
        #             for x in qrs:
        #                 if discipline == 'Histology':
        #                     for y in range(0, 2):
        #                         label_attributes['ACC_NUM'] = acc_nums[counter]
        #                         label_attributes['FIRST'] = first_name
        #                         label_attributes['LAST'] = last_name
        #                         label_attributes['QR'] = qrs[counter]

        #                         attributes_list.append(label_attributes.copy())

        #                     # Print initial labels to autopsy printer, left roll
        #                     # print_label(printer, attributes_list, True, 0)

        #                     counter += 1
        #                 else:
        #                     label_attributes['CASE_NUM'] = case_number
        #                     label_attributes['DATE'] = doc
        #                     label_attributes['LAST'] = last_name
        #                     label_attributes['FIRST'] = first_name
        #                     label_attributes['CODE'] = codes[counter]
        #                     label_attributes['TYPE'] = types[counter]
        #                     label_attributes['QR'] = qrs[counter]

        #                     attributes_list.append(label_attributes.copy())

        #                     counter += 1

        #             # Print initial labels to autopsy printer, right roll
        #             # print_label(printer, attributes_list, True, 1)
        #             if discipline == 'Histology':
        #                 print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 0)
        #                 # print_label(printer, attributes_list, True, 0)
        #             else:
        #                 print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
        #                 # print_label(printer, attributes_list, True, 1)

        #             # Clear attributes list for generic labels
        #             attributes_list = []

        #             # Print generic labels for disciplines that require
        #             if discipline in ['Histology', 'Toxicology']:
        #                 label_attributes_generic = fields_dict['generic']
        #                 label_attributes_generic['LAST'] = selected_case.last_name
        #                 label_attributes_generic['FIRST'] = selected_case.first_name
        #                 label_attributes_generic['CASE_NUM'] = case_number

        #                 attributes_list.append(label_attributes_generic.copy())

        #                 if discipline == 'Toxicology':
        #                     for i in range(0, 13):
        #                         attributes_list.append(label_attributes_generic.copy())

        #                 print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
        #                 # print_label(printer, attributes_list, True, 1)

        #             elif button == 'Physical (Bundle)':
        #                 label_attributes_extra = fields_dict['bundle']
        #                 label_attributes_extra['TEXT'] = 'Dry'
        #                 for i in range(0, 4):
        #                     attributes_list.append(label_attributes_extra.copy())
        #                 label_attributes_extra['TEXT'] = 'Wet'
        #                 for i in range(0, 4):
        #                     attributes_list.append(label_attributes_extra.copy())
        #                 label_attributes_extra['TEXT'] = 'Photocard'
        #                 attributes_list.append(label_attributes_extra.copy())

        #                 print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
        #                 # print_label(printer, attributes_list, True, 1)

        #             elif discipline == 'Physical':
        #                 label_attributes_extra = fields_dict['bundle']
        #                 label_attributes_extra['TEXT'] = 'Photocard'
        #                 attributes_list.append(label_attributes_extra.copy())

        #                 print_label(r'DYMO LabelWriter 450 Twin Turbo (Copy 1)', attributes_list, True, 1)
        #                 # print_label(printer, attributes_list, True, 1)

        #             # Four generic labels for tox and one for histo
        #             if discipline == 'Toxicology':
        #                 for i in range(0, 4):
        #                     # Print labels to left roll
        #                     print_label(r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo',
        #                                 label_attributes_generic, True, 1)
        #             else:
        #                 # Print label to left roll
        #                 print_label(r'\\OCMEG9M056.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo',
        #                             label_attributes_generic, True, 1)

        # if 'submit_toxicology_print' in request.form:
        #     labels = AutopsyViewButtons.query.filter_by(button='Toxicology (N)').first().specimen_types.split(', ')
        #     container_type = ContainerTypes.query.filter_by(name='No Container').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Cooled Storage'
        #     submission_route = CooledStorage.query.filter_by(equipment_id='08R').first().id
        #     discipline = 'Toxicology'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_physical_print' in request.form:
        #     print('PHYSICAL')
        #     print('NO CONTAINER')
        #     labels = AutopsyViewButtons.query.filter_by(button='Physical (N)')
        #     container_type = ContainerTypes.query.filter_by(name='No Container').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Bench'
        #     submission_route = Benches.query.filter_by(equipment_id='BS60').first().id
        #     discipline = 'Physical'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_physical_sa_print' in request.form:
        #     print('PHYSICAL SA')
        #     print('BAG')
        #     labels = AutopsyViewButtons.query.filter_by(button='Physical (SA)')
        #     container_type = ContainerTypes.query.filter_by(name='Bag').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Bench'
        #     submission_route = Benches.query.filter_by(equipment_id='BS60').first().id
        #     discipline = 'Physical'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_bundle_print' in request.form:
        #     print('ME BUNDLE LABELS')
        #     print('BAG')
        #     labels = AutopsyViewButtons.query.filter_by(button='Physical (Bundle)')
        #     container_type = ContainerTypes.query.filter_by(name='Bag').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Bench'
        #     submission_route = Benches.query.filter_by(equipment_id='BS60').first().id
        #     discipline = 'Physical'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_histology_print' in request.form:
        #     print('HISTOLOGY LABELS')
        #     print('JAR')
        #     labels = AutopsyViewButtons.query.filter_by(button='Histology (N)')
        #     container_type = ContainerTypes.query.filter_by(name='Jar').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Bench'
        #     submission_route = Benches.query.filter_by(equipment_id='BS60').first().id
        #     discipline = 'Histology'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_histology_sa_print' in request.form:
        #     print('HISTOLOGY SA')
        #     print('JAR')
        #     labels = AutopsyViewButtons.query.filter_by(button='Histology (SA)')
        #     container_type = ContainerTypes.query.filter_by(name='Jar').first().id
        #     submission_route_type = 'By Location'
        #     location_type = 'Bench'
        #     submission_route = Benches.query.filter_by(equipment_id='BS60').first().id
        #     discipline = 'Histology'
        #     print(f'LABELS: {labels}')
        #     return add_new_container(container_type, form, submission_route_type, location_type, submission_route,
        #                              discipline, **kwargs)
        # elif 'submit_other_print' in request.form:
        #     print(f'SPECIMEN TYPE:{form.specimen_type.data}')
        # # Specimen was scanned in, get relevant information and direct to add specimen form
        # elif 'submit_scan' in request.form:
        #     case_id = int(form.initial_label.data.split(';')[0].split(': ')[1].strip())
        #     specimen_type = int(form.initial_label.data.split('; ')[1].split(': ')[1].strip())
        #     discipline = form.initial_label.data.split('; ')[2].split(': ')[1].strip()

        #     # Get container ID
        #     container_id = Containers.query.filter(and_(Containers.case_id == case_id,
        #                                                 Containers.submitted_by == current_user.personnel_id,
        #                                                 Containers.submission_time == None,
        #                                                 Containers.discipline == discipline)).first().id
        #     return redirect(url_for('specimens.add', case_id=case_id, specimen_type=specimen_type,
        #                             container_id=container_id, from_autopsy=True))


@blueprint.route(f'/{table_name}/get_specimen_types/', methods=['GET', 'POST'])
@login_required
def get_specimen_types():
    # Get solution type from frontend
    discipline = request.args.get('discipline', type=str)

    # Get specimen types with correct discipline
    specimen_types = [specimen_type for specimen_type in SpecimenTypes.query.all() if discipline in
                      specimen_type.discipline.split(', ')]
    
    specimen_types.sort(key=lambda s: s.name.lower())
    # Initialize choices
    choices = []

    # Sort alphabetically by name
    specimen_types.sort(key=lambda st: st.name.lower())

    # Format for frontend
    choices = [{'id':st.id, 'code': st.code, 'name': st.name} for st in specimen_types]

    return jsonify({'choices': choices})




@blueprint.route(f'/{table_name}/get_specimens/', methods=['GET', 'POST'])
@login_required
def get_specimens():
    # Get solution type from frontend
    case_id = int(request.args.get('case_id'))

    # Get specimens with correct case_id
    specimens = Specimens.query.filter_by(case_id=case_id)

    # Initialize choices
    choices = [({'id': 0, 'name': f'---'})]

    # Set each choice
    for item in specimens:
        choices.append({'id': item.id, 'name': item.accession_number})

    return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/get_submission_data/', methods=['GET', 'POST'])
@login_required
def get_submission_data():
    # Discipline dictionary k=code, v=full discipline, used for getting discipline from specimen_type code first letter
    discipline_lookup = {v: k for k, v in discipline_codes.items()}

    print("STARTED")

    # Get default location type, location choices, and location based on discipline
    locations_lookup = {
        'T': ['Cooled Storage',
              [{'id': item.equipment_id, 'name': item.equipment_id} for item in CooledStorage.query.all()],
              CooledStorage.query.filter_by(equipment_id='08R').first().equipment_id],
        'D': ['Evidence Lockers', [{'id': item.equipment_id, 'name': item.equipment_id} for item in EvidenceLockers.query.all()],
              EvidenceLockers.query.filter_by(occupied=0).first().equipment_id],
        'P': ['Benches', [{'id': item.equipment_id, 'name': item.equipment_id} for item in Benches.query.all()],
              Benches.query.filter_by(equipment_id='BS60').first().equipment_id],
        'B': ['Cooled Storage',
              [{'id': item.equipment_id, 'name': item.equipment_id} for item in CooledStorage.query.all()],
              CooledStorage.query.filter_by(equipment_id='08R').first().equipment_id],
        'H': ['Cooled Storage',
              [{'id': item.equipment_id, 'name': item.equipment_id} for item in CooledStorage.query.all()],
              CooledStorage.query.filter_by(equipment_id='08R').first().equipment_id],
    }

    # Get specimen and container from qr code scan
    st = int(request.args.get('barcode').split('st: ')[1].split(';')[0])
    co = int(request.args.get('barcode').split('co: ')[1].split(';')[0])
    specimen_type = SpecimenTypes.query.get(st)
    container = Containers.query.get(co)

    # Get selected case
    selected_case = int(request.args.get('case_id'))

    # Return an error if selected_case is not the same as the container's case
    if selected_case != container.case_id:
        response = {'error': 'The Selected Case Does Not Match The Container Case ID'}
        return jsonify(response)

    # Use specimen_type code to get discipline
    discipline = discipline_lookup[specimen_type.code[0]]
    # Get discipline choices
    discipline_choices_response = [{'name': item, 'id': item} for item in disciplines]

    # Get container choices for container associated with case
    container_choices = [{'name': f'{item.accession_number}-{item.type.name}', 'id': item.id} for item in
                         Containers.query.filter_by(case_id=container.case_id).all()]

    # Get all specimen collection vessel choices
    vessel_choices = [{'name': item.display_name, 'id': item.id} for item in SpecimenCollectionContainers.query.all()]
    # Get default collection vessel from specimen_type
    collection_vessel = specimen_type.collection_container_id

    # Get all specimen condition choices
    condition_choices = [{'id': item.name, 'name': item.name} for item in
                         SpecimenConditions.query.order_by(SpecimenConditions.name.asc())]

    # Get all specimen collector choices
    collector_choices = [{'id': item.id, 'name': f"{item.last_name}, {item.first_name}",'job_title': item.job_title} for item in
                         Personnel.query
                         .join(Divisions)
                         .join(Agencies)
                         .filter(Agencies.id == 1)
                         .order_by(Personnel.last_name)
                         ]
    collector_choices.insert(0, {'id': '', 'name': '--'})

    # Set custody_location choices
    location_choices = [{'id': k, 'name': k} for k, v in location_dict.items()]
    location_choices.insert(0, {'id': '', 'name': 'Please select a custody type'})
    default_location = locations_lookup[specimen_type.code[0]][0]
    custody_choices = locations_lookup[specimen_type.code[0]][1]
    default_custody = locations_lookup[specimen_type.code[0]][2]

    # Set response dictionary
    response = {
        'specimen_type': specimen_type.name,
        'discipline_choices': discipline_choices_response,
        'discipline': discipline,
        'container_choices': container_choices,
        'container': container.id,
        'vessel_choices': vessel_choices,
        'collection_vessel': collection_vessel,
        'condition_choices': condition_choices,
        'collector_choices': collector_choices,
        'location_choices': location_choices,
        'default_location': default_location,
        'custody_choices': custody_choices,
        'default_custody': default_custody
    }

    return jsonify(response)


@blueprint.route(f'/{table_name}/get_case_evidence_disciplines/', methods=['GET', 'POST'])
@login_required
def get_disciplines():
    # Get selected case
    case_id = int(request.args.get('case_id'))

    pending_containers = Containers.query.filter_by(case_id=case_id).filter(
        Containers.pending_submitter != None)
    pending_specimens = Specimens.query.filter_by(case_id=case_id).filter(
        Specimens.pending_submitter != None)

    total_pending = pending_containers.count() + pending_specimens.count()

    choices = [({'id': "", 'name': f"All ({pending_containers.count()}/{pending_specimens.count()})"})]

    print(disciplines)

    for discipline in disciplines:
        print(discipline)
        disc_pending_containers = pending_containers.filter_by(discipline=discipline).count()
        disc_pending_specimens = pending_specimens.filter_by(discipline=discipline).count()
        discipline_pending = disc_pending_containers + disc_pending_specimens
        if disc_pending_containers or disc_pending_specimens:
            choices.append(
                {'id': discipline, 'name': f'{discipline} ({disc_pending_containers}/{disc_pending_specimens})'})

    print(choices)

    return jsonify({'choices': choices})


@blueprint.route(f'/{table_name}/drafting/', methods=['GET', 'POST'])
@login_required
def drafting():
    discipline_query = request.args.get('discipline')

    filter_query = []
    discipline_counts = {}

    # Loop through all disciplines and filter accordingly
    for discipline in disciplines:
        # Dynamically access the discipline_status column
        discipline_status_column = getattr(table, f"{discipline.lower()}_status", None)

        if discipline_status_column:
            query = discipline_status_column == 'Ready for Drafting'

            # If no specific discipline query or matches the discipline_query, add to filter
            if not discipline_query or discipline_query.lower() == discipline.lower():
                filter_query.append(query)

            # Count how many cases match the status
            n_cases = table.query.filter(query).count()
            if n_cases:
                discipline_counts[discipline] = n_cases

    # Convert filter_query to a tuple for sa.or_
    filter_query = tuple(filter_query) if filter_query else None

    items = (db.session.query(Cases)
            .join(CaseTypes, CaseTypes.id == Cases.case_type)
            .filter(sa.or_(*filter_query))
            .order_by(Cases.create_date.asc()))

    # Get the case ids from the original query
    case_ids = [item.id for item in items]  # Extract case ids from items_query

    # Perform a separate query to fetch reports for these case_ids and group by discipline
    reports = {}

    if case_ids:  # Ensure case_ids is not empty before querying

        for discipline in disciplines:
            # Query to get reports for the current discipline
            report_query = db.session.query(Reports) \
                .filter(Reports.case_id.in_(case_ids),
                        Reports.discipline == discipline,
                        Reports.report_status == "Finalized")

            reports[discipline] = report_query.all()  # Execute query and store results

    _view_list = view_items(table, 'Drafting', 'Drafting', table_name, length=-1,
                            items=items, template_file='cases/drafting.html', show_default_alerts=False,
                            add_item_button=False, import_file_button=False, disciplines=disciplines,
                            discipline_counts=discipline_counts, reports=reports)

    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>/unlock_draft', methods=['GET', 'POST'])
@login_required
def unlock_draft(item_id):
    redirect_to = url_for(f'{table_name}.drafting')

    _unlock = unlock_item(item_id, table, name, redirect_to)

    return _unlock




@blueprint.route(f"/summary_html/placeholder/placeholder", methods = ['GET', 'POST'])
def get_summary_narratives_html():


    data = request.get_json()
    case_id = data.get('caseNumber', '')

    narratives = Narratives.query.filter_by(case_id=case_id, narrative_type="Summary (AI)").all()



    return render_template('/cases/summary_ai.html', narratives=narratives)









def check_existing(case_id, narrative_type):
    summary_exists = Narratives.query.filter_by(case_id=case_id, narrative_type=narrative_type).first() is not None
    comment_exists = Cases.query.filter_by(id=case_id).first()
    comment_exists = comment_exists and comment_exists.case_comments_ai is not None
    return summary_exists, comment_exists

def split_narrative(text):
    # Search for ; or : in the first 100 characters
    import re
    match = re.search(r'[;:]', text[:100])
    if not match:
        return None, None  # Or raise an error/return the original text as you prefer

    split_index = match.start()
    part1 = text[:split_index].strip()
    part2 = text[split_index+1:].strip()  # +1 to skip the separator
    return part1, part2


def call_and_split_ai(narrative, url):
    payload = {"prompt": [narrative]}
    response = requests.post(url, json=payload)

    if response.status_code != 200 or response.json().get('Narrative 0') is None:
        return None, None, "AI endpoint failed"
    output = response.json().get('Narrative 0', '')
    # Example split: expects output like "comment: ...; summary: ..."

    comment, summary = split_narrative(output) # do not use the summary

    if not comment or not summary:
        return None, None, "AI output could not be split"
    
    return comment, output, None




# def get_case_lock(case_id):
#     if case_id not in case_locks:
#         case_locks[case_id] = Lock()
#     return case_locks[case_id]



@blueprint.route("/get_ai_combined", methods=['POST'])
@login_required
def get_ai_combined():

    url = "http://10.63.21.194:7979/inference_qwen"
    data = request.get_json()

    narrative = data.get('narrative', '').strip()
    case_id = data.get('caseNumber', '').strip()
    narrative_type = "Summary (AI)"
    
    lock_name = f"ai_narrative_{case_id}"

    with DistributedRedisLock(lock_name):

        if not narrative or not case_id:
            return jsonify({'success': False, 'error': 'Narrative or case ID missing from frontend.'}), 400

        ###
        summary_exists, comment_exists = check_existing(case_id, narrative_type)
        if summary_exists and comment_exists: # probably iwll never get triggered becasue of javascvvript frontend
            return jsonify({'success': True, 'message': 'Summary and comment already exist.'}), 200
        ###



        comment, summary, error = call_and_split_ai(narrative, url)
        if error:
            return jsonify({'success': False, 'error': error or 'AI output missing parts.'}), 500

        # Save summary
        if not summary_exists:
            form = NarrativeAddForm(meta={'csrf': False})
            form.narrative_type.data = narrative_type
            form.narrative.data = summary
            form.case_id.data = case_id
            if form.validate():
                add_item(
                    form=form,
                    table=Narratives,
                    item_type='Narrative',
                    item_name='Narratives',
                    table_name='narratives',
                    requires_approval=False,
                    name='id',
                    initials="AI System",
                    kwargs={'template': 'form.html', 'redirect': 'view'}
                )
            else:
                return jsonify({'success': False, 'error': form.errors}), 400

        # Save comment
        if not comment_exists:
            item = Cases.query.get_or_404(case_id)
            item.case_comments_ai = comment
            db.session.commit()

        return jsonify({'success': True, 'comment': comment}), 200









@blueprint.route(f'/{table_name}/set_no_report_needed/<int:item_id>/<string:discipline>')
@login_required
def set_no_report_needed(item_id, discipline):
    case = Cases.query.get_or_404(item_id)
    attr = f"{discipline.lower()}_status"

    if not hasattr(case, attr):
        flash(f"Invalid discipline: {discipline}", "danger")
        return redirect(url_for('cases.drafting', discipline=discipline.lower()))

    # Get first letter for discipline prefix matching (_T1, _B1, etc.)
    discipline_prefix = discipline[0].upper()

    # Look for a finalized report with matching _X1 suffix
    matching_report = Reports.query.filter(
        Reports.case_id == item_id,
        Reports.report_status == 'Finalized',
        Reports.report_name.ilike(f'%_{discipline_prefix}%')
    ).first()

    if matching_report:
        setattr(case, attr, 'Ready for Dissemination')
        flash(f"{discipline} status updated to 'Ready for Dissemination' based on finalized report.", "success")
    else:
        setattr(case, attr, 'No report needed')
        flash(f"{discipline} status updated to 'No report needed'.", "success")

    db.session.commit()
    return redirect(url_for('cases.drafting', discipline=discipline.lower()))

@blueprint.route(f'/{table_name}/set_no_report_needed_bulk/<int:item_id>')
@login_required
def set_no_report_needed_bulk(item_id):
    """
    Updates only the selected disciplines (from ?disciplines=CSV) that are currently 'Ready for Drafting'.
    Leaves any blank/other statuses untouched. Mirrors per-discipline logic.
    """
    case = Cases.query.get_or_404(item_id)

    # Parse selected disciplines from query string
    csv = request.args.get('disciplines', '', type=str).strip()
    selected = [d.strip() for d in csv.split(',') if d.strip()] if csv else []

    if not selected:
        flash("No disciplines were selected.", "warning")
        return redirect(url_for('cases.drafting'))

    # (Optional) constrain to known set
    allowed = {'Toxicology','Biochemistry','External','Drug','Histology','Physical'}
    # keep only allowed ones (case-sensitive to match DB columns)
    selected = [d for d in selected if d in allowed]

    if not selected:
        flash("No valid disciplines selected.", "warning")
        return redirect(url_for('cases.drafting'))

    changed = []
    for discipline in selected:
        attr = f"{discipline.lower()}_status"
        if not hasattr(case, attr):
            continue

        if getattr(case, attr) != 'Ready for Drafting':
            continue

        prefix = discipline[0].upper()
        matching_report = (
            Reports.query
                   .filter(Reports.case_id == item_id,
                           Reports.report_status == 'Finalized',
                           Reports.report_name.ilike(f'%_{prefix}%'))
                   .first()
        )

        if matching_report:
            setattr(case, attr, 'Ready for Dissemination')
        else:
            setattr(case, attr, 'No report needed')

        changed.append(discipline)

    if changed:
        db.session.commit()
        flash(f"Updated: {', '.join(changed)}.", "success")
    else:
        flash("No disciplines in 'Ready for Drafting' among your selection.", "info")

    return redirect(url_for('cases.drafting'))

# export_filtered.OKKK Export.NEXT export_all
@blueprint.route(f'/{table_name}/export_filtered', methods=['GET', 'POST'])
@login_required
def export_filtered():
    form = ExportFiltered()
    render_form(form)
    required_fields = [field.name for field in form if field.flags.required]
    errors = {}
    exit_route = url_for(f'{table_name}.view_list')

    # For exports of Mannered Cases prior to 2024, use SSMS to query FA SQL directly. 
    # C:\Users\spearring-a\Documents\SQL Server Management Studio\FASQL_deathreport_formatted

    if form.is_submitted() and form.validate():

        created_start = form.created_start.data
        created_end = form.created_end.data
        mod = form.mod.data
        cod = form.cod.data
        content_preset = form.content_preset.data

        # if current_user.permissions == 'Admin':
        items = Cases.query.filter(
                    Cases.manner_of_death.isnot(None),
                    Cases.case_type == 7
                )

        if created_start and created_end:
            start_dt = datetime.combine(created_start, datetime.min.time())
            end_dt = datetime.combine(created_end, datetime.max.time())
            items = items.filter(Cases.fa_case_entry_date.between(start_dt, end_dt))

        if mod:
            items = items.filter(Cases.manner_of_death.in_(mod))

        if cod:
            keyword = f"%{cod}%"
            items = items.filter(or_(
                Cases.cod_a.ilike(keyword),
                Cases.cod_b.ilike(keyword),
                Cases.cod_c.ilike(keyword),
                Cases.cod_d.ilike(keyword)
            ))

        query = items.all()

        # Decode maps (e.g., reverse lookup by ID)
        gender_dict = {item.id: item.name for item in Genders.query}
        race_dict = {item.id: item.name for item in Races.query}

        column_map = {
            'case_number': 'Case Number',
            'date_of_birth': 'DOB',
            'date_of_incident': 'DOD',
            'time_of_incident': 'TOD',
            'death_address': 'Address DEATH',
            'death_zip': 'Zip Code DEATH',
            'Gender': 'Gender',
            'age_years': 'Age',
            'Race': 'Race',
            'manner_of_death': 'MOD',
            'cod_a': 'COD1',
            'cod_b': 'COD2',
            'cod_c': 'COD3',
            'cod_d': 'COD4',
            'other_conditions': 'Other Significant Contributions',
            **({'ssn': 'SSN',
            'home_address': 'Address HOME',
            'home_zip': 'Zip Code HOME',} if content_preset == 'Additional' else {})
        }

        # Convert to DataFrame
        raw_df = pd.DataFrame([get_to_dict(item) for item in query])  # Assuming `to_dict` method exists
        # else:
        #     query_str = """
        #         SELECT * FROM cases
        #         WHERE manner_of_death IS NOT NULL
        #         AND case_type = 7
        #     """
        #     params = {}

        #     if created_start and created_end:
        #         query_str += " AND fa_case_entry_date BETWEEN :start_dt AND :end_dt"
        #         params["start_dt"] = datetime.combine(created_start, datetime.min.time())
        #         params["end_dt"] = datetime.combine(created_end, datetime.max.time())

        #     if mod:
        #         mod_placeholders = ",".join(f":mod_{i}" for i in range(len(mod)))
        #         query_str += f" AND manner_of_death IN ({mod_placeholders})"
        #         for i, m in enumerate(mod):
        #             params[f"mod_{i}"] = m

        #     if cod:
        #         keyword = f"%{cod}%"
        #         query_str += """
        #             AND (
        #                 cod_a ILIKE :kw OR
        #                 cod_b ILIKE :kw OR
        #                 cod_c ILIKE :kw OR
        #                 cod_d ILIKE :kw
        #             )
        #         """
        #         params["kw"] = keyword

        #     result = db.session.execute(text(query_str), params)
        #     query = result.mappings().all()

        #         # Decode maps (e.g., reverse lookup by ID)
        #     gender_dict = {item.id: item.name for item in Genders.query}
        #     race_dict = {item.id: item.name for item in Races.query}

        #     column_map = {
        #         'case_number': 'Case Number',
        #         'date_of_birth': 'DOB',
        #         'date_of_incident': 'DOD',
        #         'time_of_incident': 'TOD',
        #         'death_address': 'Address DEATH',
        #         'death_zip': 'Zip Code DEATH',
        #         'Gender': 'Gender',
        #         'age_years': 'Age',
        #         'Race': 'Race',
        #         'manner_of_death': 'MOD',
        #         'cod_a': 'COD1',
        #         'cod_b': 'COD2',
        #         'cod_c': 'COD3',
        #         'cod_d': 'COD4',
        #         'other_conditions': 'Other Significant Contributions',
        #         **({'ssn': 'SSN',
        #         'home_address': 'Address HOME',
        #         'home_zip': 'Zip Code HOME',} if content_preset == 'Additional' else {})
        #     }

        #     # Convert to DataFrame
        #     raw_df = pd.DataFrame(query)

        

        if raw_df.empty:
            flash(Markup(f'No Cases match this filtering.'), 'warning')
        else:
            # Format Name: Lastname, Firstname Middlename
            raw_df['Name'] = (
                    raw_df['last_name'].astype(str).fillna('').str.strip().str.capitalize() + ', ' +
                    raw_df['first_name'].astype(str).fillna('').str.strip() + ' ' +
                    raw_df['middle_name'].astype(str).fillna('').str.strip()
            ).str.strip().str.replace(', $', '', regex=True)  # remove dangling comma
            # Add 'Name' to column_map at the correct spot
            column_map = {'case_number': 'Case Number', 'Name': 'Name', **column_map}

            # Use column_map values as export order (preserved order + deduped)
            export_order = list(dict.fromkeys(column_map.values()))

            # Decode gender and race
            if 'gender_id' in raw_df.columns:
                raw_df['Gender'] = raw_df['gender_id'].map(gender_dict).fillna('')
            if 'race_id' in raw_df.columns:
                raw_df['Race'] = raw_df['race_id'].map(race_dict).fillna('')
            raw_df.drop(columns=['gender_id', 'race_id'], inplace=True, errors='ignore')

            # Format dates and time and zips
            for col in ['date_of_birth', 'date_of_incident']:
                if col in raw_df.columns:
                    raw_df[col] = pd.to_datetime(raw_df[col], errors='coerce').dt.strftime('%m/%d/%Y')
            if 'time_of_incident' in raw_df.columns:
                raw_df['time_of_incident'] = (
                        raw_df['time_of_incident']
                        .astype(str)
                        .str.replace(r'\D', '', regex=True)  # strip non-digit characters, just in case
                        .str.zfill(4)  # pad to 4 digits
                        .str.slice(0, 2) + ':' +
                        raw_df['time_of_incident'].str.slice(2, 4)
                )
            zip_fields = ['home_zip', 'death_zip']
            for col in zip_fields:
                if col in raw_df.columns:
                    raw_df[col] = (
                        raw_df[col]
                        .astype(str)
                        .where(raw_df[col].notna())  # keep NaNs as-is
                        .str.strip()
                        .str.zfill(5)
                    )

            # Rename + reorder
            df = raw_df.rename(columns=column_map)
            df = df[[col for col in export_order if col in df.columns]]
            df = df.dropna(how='all', subset=export_order)
            df = df[~df.apply(lambda row: all((str(val).strip() == '' or pd.isna(val)) for val in row), axis=1)]
            df = df.sort_values(by="Case Number", ascending=True)

            # Export to CSV
            timestamp = datetime.now().strftime("%Y%m%d")
            start_str = created_start.strftime("%b-%Y") if created_start else "--"
            end_str = created_end.strftime("%b-%Y") if created_end else "--"
            filename = f"Closed_PM_Cases_{content_preset}_{timestamp}_{start_str}_{end_str}.csv"
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False)
            mimetype = 'text/csv'

            # if form.format.data == 'csv':
            #     df.to_csv(buffer, index=False)
            #     mimetype = 'text/csv'
            # else:
            #     with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            #         df.to_excel(writer, index=False, sheet_name='Export', startrow=1, header=False)
            #
            #         workbook = writer.book
            #         worksheet = writer.sheets['Export']
            #
            #         # Define header format
            #         header_format = workbook.add_format({
            #             'bold': True,
            #             'bg_color': '#D9D9D9',
            #             'border': 1,
            #             'align': 'center',
            #             'valign': 'vcenter'
            #         })
            #
            #         # Write headers manually at row 0
            #         for col_num, col_name in enumerate(df.columns):
            #             worksheet.write(0, col_num, col_name, header_format)
            #     mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            buffer.seek(0)
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype=mimetype)

    return render_template(f'{table_name}/export_filtered.html',
                           form=form,
                           item=None,
                           table_name=table_name,
                           item_name=item_name,
                           function='Export Filtered',
                           alias=None,
                           pending_fields=[],
                           approved_fields=[],
                           required_fields=required_fields,
                           errors=errors,
                           errors_json=json.dumps(errors),
                           default_header=True,
                           exit_route=exit_route
                           )

  
@blueprint.route(f'/{table_name}/case_view', methods=['GET', 'POST'])
@login_required
def case_view_only():
    case_number = request.args.get('case_number')

    item = table.query.filter_by(case_number=case_number).first()

    return redirect(url_for(f'{table_name}.view', item_id=item.id, view_only=True))


@blueprint.route(f'/{table_name}/check_t1_exists/<int:case_id>')
@login_required
def check_t1_exists(case_id):
    existing = Reports.query.filter_by(case_id=case_id).first()
    return jsonify({'exists': bool(existing)})

@blueprint.route(f'/{table_name}/mark_ready_for_dissemination/<int:case_id>')
@login_required
def mark_ready_for_dissemination(case_id):
    case = Cases.query.get_or_404(case_id)
    case.toxicology_status = 'Ready for Dissemination'
    db.session.commit()
    flash('Status updated to Ready for Dissemination.', 'info')
    return redirect(url_for('cases.view', item_id=case_id))



@blueprint.route(f'/{table_name}/<int:item_id>/gen_decedent_report', methods=['GET', 'POST'])
@login_required
def gen_decedent_report(item_id):

    generate_decedent_report(item_id)
    # ids = [1938, 1937, 1936, 1935, 1934, 1933, 1932, 1931, 1930, 1928, 1928, 1927, 1926, 1925, 1924]

    # for i in range(len(ids)):
    #     generate_decedent_report(ids[i])

    return redirect(url_for('cases.view', item_id=item_id))


@blueprint.route(f'/{table_name}/<int:item_id>/gen_decedent_report_draft', methods=['GET', 'POST'])
def download_decedent_report(item_id: int):
    """
    Enqueue the decedent report build on the single-worker queue,
    wait for the result, then stream the PDF to the client and delete it.
    No DB Records are created/modified.
    """
    # submit returns a Future-like object because _in_worker=False in the callee
    fut = generate_decedent_report_draft(item_id, _in_worker=False)

    try:
        # Block for the worker result (adjust timeout if your queue supports it)
        pdf_path, inc_num = fut.result() 
    except Exception as e:
        # If your queue returns plain values (not Future), fall back:
        # pdf_path, inc_num = fut
        return jsonify({"ok": False, "error": str(e)}), 500

    if not os.path.isfile(pdf_path):
        return jsonify({"ok": False, "error": "PDF not produced"}), 500

    filename = os.path.basename(pdf_path)

    @after_this_request
    def _cleanup(response):
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        try:
            # also try removing the temp directory if empty
            tmp_dir = os.path.dirname(pdf_path)
            if not os.listdir(tmp_dir):
                os.rmdir(tmp_dir)
        except Exception:
            pass
        return response

    # Stream the PDF to the browser; triggers download
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0
    )


@blueprint.route(f'/{table_name}/last_case_used', methods=['GET', 'POST'])
@login_required
def last_case_used():

    as_of = request.form.get('as_of')

    if not as_of:
        as_of_date = datetime.today()
    else:
        as_of_date = datetime.strptime(as_of, "%Y-%m-%d").date()

    as_of_end = datetime.combine(as_of_date, datetime.max.time())

    case_types = (
        CaseTypes.query
        .order_by(CaseTypes.code.asc())
        .all()
    )

    rows = []

    for ct in case_types:
        if ct.code.upper() == "PM":
            date_col = Cases.fa_case_entry_date
            is_pm = True
        else:
            date_col = Cases.create_date
            is_pm = False

        q = (
            Cases.query
            .filter(Cases.case_type == ct.id)
            .filter(date_col.isnot(None))
            .filter(date_col <= as_of_end)
        )

        if is_pm:
            q = q.filter(~Cases.case_number.like('NC-%'))

        highest_case = (
            q.order_by(Cases.case_number.desc())
            .with_entities(Cases.id, Cases.case_number, date_col)
            .first()
        )
        
        rows.append({
            "case_type_name": ct.name,
            "highest_case_number": highest_case[1] if highest_case else None,
            "case_url": url_for('cases.view', item_id=highest_case[0]) if highest_case else None,
        })

    return render_template(f'{table_name}/last_case_used.html',
                           as_of_date=as_of_date,
                           rows=rows)


@blueprint.route(f'/{table_name}/<int:item_id>/communications', methods=['GET', 'POST'])
@login_required
def communications(item_id):

    kwargs = default_kwargs.copy()

    item = table.query.get_or_404(item_id)

    form = Communications()

    kwargs['template'] = 'communications.html'

    errors = {}

    if form.validate_on_submit():
        new_comment = form.communications.data.strip()  # Get the new comment
        if new_comment:
            timestamp = datetime.now().strftime("%m/%d/%y %H:%M")  # Format timestamp
            user_initials = current_user.initials  # Get user initials

            # Append new comment while keeping history
            if item.communications:
                item.communications += f"\n{new_comment} ({user_initials}) {timestamp}"
            else:
                item.communications = f"{new_comment} ({user_initials}) {timestamp}"

            db.session.commit()  # Save changes

        return redirect(url_for('cases.view', item_id=item_id))  # Redirect to item view page

    # On GET request, keep the field empty for new entry
    form.communications.data = ''

    return render_template('cases/communications.html', form=form, item=item, errors=errors, **kwargs)
