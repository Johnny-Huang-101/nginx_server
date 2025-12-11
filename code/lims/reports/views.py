from lims.forms import Attach, Import
from lims.view_templates.views import *
from lims.reports.forms import *
from lims.reports.functions import *
from flask_login import current_user
import time
import glob
from sqlalchemy import func, case
from lims.queue import get_status as queue_get_status

# Set item global variables
item_type = 'Report'
item_name = 'Reports'
table = Reports
table_name = 'reports'
name = 'report_name'  # This selects what property is displayed in the flash messages
requires_approval = False  # controls whether the approval process is required. Can be set on a view level
ignore_fields = ['result_id', 'primary_result', 'observed_result', 'qualitative_result', 'approximate_result']  # fields not added to the modification table
disable_fields = []  # fields to disable
template = 'form.html'  # template to use for add, edit, approve and update
redirect_to = 'view'
default_kwargs = {
    'template': template,
    'redirect': redirect_to,
    'disable_fields': disable_fields
}

# Create blueprint
blueprint = Blueprint(table_name, __name__)
# Filesystem path
path = os.path.join(app.config['FILE_SYSTEM'], table_name)
os.makedirs(path, exist_ok=True)


@blueprint.route(f'/{table_name}/add', methods=['GET', 'POST'])
@login_required
def add():
    kwargs = default_kwargs.copy()
    case_id = request.args.get('item_id', type=int)
    discipline = request.args.get('discipline')
    # result_statuses = request.args.get('result_statuses')
    result_statuses = ["Confirmed", "Saturated", 'Not Tested']
    exit_route = url_for('cases.unlock_draft', item_id=case_id)
    # if result_statuses:
    #     # If it's a string (like "Confirmed,Saturated"), split it into a list.
    #     if isinstance(result_statuses, str):
    #         result_statuses = [status.strip() for status in result_statuses.split(",")]
    #     # Otherwise, if it’s already a list, leave it as is.
    # else:
    #     # If no value is provided, use the default
    #     result_statuses = ['Confirmed', 'Saturated']
    if case_id:
        case_obj = Cases.query.filter_by(id=case_id).first()
        kwargs['case_notes'] = case_obj.notes if case_obj else ""
    
        kwargs['pathologist'] = case_obj.primary_pathologist if case_obj else None
        kwargs['case_type'] = case_obj.case_type

        if kwargs['case_notes']:
            print(kwargs['case_notes'])
        if result_statuses:
            kwargs['result_status_filter'] = result_statuses

        case_obj.locked = True
        case_obj.locked_by = current_user.initials
        case_obj.lock_date = datetime.now()
        db.session.commit()

    report_type = request.args.get('report_type')
    if report_type == "manual":
        report_type = "Manual Upload"

    # Create the form and update kwargs.
    form, new_kwargs = get_form_choices(Add(), case_id, discipline, result_statuses)
    kwargs.update(new_kwargs)
    kwargs['report_type'] = report_type

    # Build items for display.
    items = {}
    if case_id and discipline and 'specimens' in kwargs:
        kwargs['case_id'] = case_id
        kwargs['discipline'] = discipline
        for specimen in kwargs['specimens']:
            specimen_name = f"{specimen.type.code} {specimen.type.name} | {specimen.accession_number}"
            items[specimen_name] = get_results(specimen.id, discipline=discipline, result_statuses=result_statuses)
    kwargs['items'] = items

    # Process POST request
    if request.method == 'POST':
        if form.is_submitted() and form.validate():

            if case_obj and case_obj.locked:
                case_obj.locked = False
                case_obj.locked_by = None
                case_obj.lock_date = None
                db.session.commit()

            os.makedirs(path, exist_ok=True)
            case = Cases.query.get(form.case_id.data)
            discipline = form.discipline.data
            kwargs['discipline'] = discipline
            code = discipline_codes[discipline]
            template_id = form.report_template_id.data
            result_id_orders = list(map(int, form.result_id_order.data.split(", ")))
            template = ReportTemplates.query.get(template_id)
            template_path = os.path.join(app.config['FILE_SYSTEM'], 'report_templates', f"{template.name}.docx")
            discipline_reports = table.query.filter(and_(table.case_id == case_id, table.discipline == discipline,
                                                          table.db_status !='Removed'))
            report_number = discipline_reports.count() + 1
            current_date = datetime.now().strftime("%m/%d/%y %H:%M") 
            if form.communications.data:
                form.communications.data = f"{form.communications.data} ({current_user.initials}) {current_date}"

            # Set discard date for non-PMs if needed
            if discipline == 'Toxicology' and case.type.code != 'PM':
                if discipline_reports.count() == 0 and case.retention:
                    retention_policy_length = case.retention.retention_length
                    case.discard_date = datetime.now() + timedelta(days=retention_policy_length)

            setattr(case, f"{discipline.lower()}_status", 'Drafting')
            report_name = f"{case.case_number}_{code}{report_number}"
            file_name = f"{report_name} (DRAFT 1)"
            kwargs.update({
                'report_name': report_name,
                'report_number': report_number,
                'draft_number': 1,
                'file_name': file_name,
                'report_status': 'Created',
                'report_template_id': form.report_template_id.data
            })

            # Create the new report record.
            add_item(form, table, item_type, item_name, table_name, requires_approval, name, **kwargs)

            # Get the actual report id (assuming add_item commits the record)
            latest_report = table.query.order_by(table.id.desc()).first()
            report_id = latest_report.id if latest_report and latest_report.id else 1

            # Process the auto-generated branch.
            if form.report_type.data == 'Auto-generated':

                result_ids = form.result_id.data
                kwargs['redirect'] = url_for(f"{table_name}.add_comment", item_id=report_id)
                for result_id in result_ids:
                    result_id = int(result_id)
                    result = {
                        'report_id': report_id,
                        'result_id': result_id,
                        'primary_result': "Y" if result_id in form.primary_result_id.data else None,
                        'supplementary_result': "Y" if result_id in form.supplementary_result_id.data else None,
                        'observed_result': "Y" if result_id in form.observed_result_id.data else None,
                        'qualitative_result': "Y" if result_id in form.qualitative_result_id.data else None,
                        'approximate_result': "Y" if result_id in form.approximate_result_id.data else None,
                        'order': result_id_orders.index(result_id) + 1
                    }
                    add_report_results(**result)
                # After processing, redirect to add_comment.
                return redirect(url_for(f"{table_name}.add_comment", item_id=report_id, discipline=discipline))
            else:
                # Handle manual upload branch.
                file = form.report_file.data
                save_path = os.path.join(path, report_name)
                file.save(f"{save_path}.docx")
                pythoncom.CoInitialize()
                docx2pdf.convert(f"{save_path}.docx", f"{save_path}.pdf")
                # Check for any PDF attachments linked to results for this case
                results_all = Results.query.filter_by(case_id=case_id).all()
                pdf_attachments = []

                for result in results_all:
                    attachments = Attachments.query.filter_by(table_name="results", record_id=result.id).all()
                    for attachment in attachments:
                        if attachment.path and attachment.path.lower().endswith('.pdf'):
                            full_attachment_path = os.path.join(app.config['FILE_SYSTEM'], attachment.path)
                            if os.path.exists(full_attachment_path):
                                print(f"Appending result attachment: {full_attachment_path}")
                                pdf_attachments.append(full_attachment_path)

                # If there are any valid attachments, merge them to the end of the main PDF
                if pdf_attachments:
                    from PyPDF2 import PdfMerger
                    merged_pdf_path = f"{save_path}.pdf"

                    try:
                        pdf_merger = PdfMerger()
                        with open(merged_pdf_path, "rb") as base_pdf:
                            pdf_merger.append(base_pdf)

                        for attachment in pdf_attachments:
                            with open(attachment, "rb") as attach_pdf:
                                pdf_merger.append(attach_pdf)

                        temp_pdf_path = f"{save_path}_temp.pdf"
                        with open(temp_pdf_path, "wb") as merged_file:
                            pdf_merger.write(merged_file)

                        os.remove(merged_pdf_path)
                        os.rename(temp_pdf_path, merged_pdf_path)
                        print("PDF merge successful.")

                    except Exception as e:
                        print(f"Error merging attachments: {e}")
                # Redirect to the view page (or another appropriate page)
                return redirect(url_for(f"{table_name}.view", item_id=report_id))
        # If the form is submitted but fails validation, execution will fall through to render the form.

    # For GET requests (or if POST fails validation), render the form.
    return add_item(form, table, item_type, item_name, table_name, requires_approval, name, exit_route=exit_route,
                    **kwargs)


@blueprint.route(f'/{table_name}/<int:item_id>/add_comment', methods=['GET', 'POST'])
@login_required
def add_comment(item_id):
    kwargs = {}
    discipline = request.args.get('discipline')
    kwargs['discipline'] = discipline

    item = table.query.get(item_id)

    case = Cases.query.filter_by(id=item.case_id).first()

    case_comments = list(
        CommentInstances.query.filter(
            CommentInstances.comment_item_type == 'Cases',
            CommentInstances.comment_item_id == case.id,
            CommentInstances.db_status != 'Removed'
        ).all())
    specimens = list(
        Specimens.query.filter(
            Specimens.case_id == case.id,
            Specimens.discipline == discipline,
            Specimens.db_status != 'Removed'
         ).all())
    containers = list(
        Containers.query.filter(
            Containers.case_id == case.id,
            Containers.discipline == discipline,
            Containers.db_status != 'Removed'
        ).all())
    tests = list(
        Tests.query
        .join(Assays, Tests.assay_id == Assays.id)
        .filter(
            Tests.case_id == case.id,
            Assays.discipline == discipline,
            Tests.db_status != 'Removed'
        ).all())

    specimens_with_comments = []
    for specimen in specimens:
        comments = list(
            CommentInstances.query.filter_by(comment_item_type='Specimens', comment_item_id=specimen.id).all())
        specimens_with_comments.append({
            'specimen': specimen,
            'comments': comments
        })

    containers_with_comments = []
    for container in containers:
        comments = list(
            CommentInstances.query.filter_by(comment_item_type='Containers', comment_item_id=container.id).all()
        )
        containers_with_comments.append(({
            'container': container,
            'comments': comments
        }))

    tests_with_comments = []
    for test in tests:
        comments = list(
            CommentInstances.query.filter_by(comment_item_type='Tests', comment_item_id=test.id).all()
        )
        for comment in comments:
            print(f'comments == {comment.comment_text}')
            if comment.comment_id:
                print(comment.comment.comment)
        tests_with_comments.append({
            'test': test,
            'comments': comments
        })
        print(f'tests_with_comments == {tests_with_comments}')

    unique_batches = {test.batch for test in tests if test.batch}  # Ensure no duplicates
    batches_with_comments = []
    for batch in unique_batches:
        comments = list(
            CommentInstances.query.filter(
                CommentInstances.comment_item_type == 'Batches',
                CommentInstances.comment_item_id == batch.id,
                CommentInstances.db_status != 'Removed'
            ).all())
        batches_with_comments.append({
            'batch': batch,
            'comments': comments
        })

    assays = list(Assays.query.join(Tests).filter(
                                Tests.db_status != 'Removed',
                                Tests.case_id == case.id,
                                Assays.discipline == discipline)
                            .all())
    assay_comments = []
    for a in assays:
        comments = list(
            CommentInstances.query.filter(
                CommentInstances.comment_item_type == 'Assays',
                CommentInstances.comment_item_id == a.id,
                CommentInstances.db_status != 'Removed'
            ).all())
        assay_comments.append({
            'assay': a,
            'comments':comments
        })

    return render_template('/reports/add_comments.html',
                           item=item,
                           item_id=item_id,
                           case_comments=case_comments,
                           specimens_with_comments=specimens_with_comments,
                           containers_with_comments=containers_with_comments,
                           tests_with_comments=tests_with_comments,
                           batches_with_comments=batches_with_comments,
                           assays=assays,
                           assay_comments=assay_comments,
                           discipline=discipline,
                           )


@blueprint.route(f'/{table_name}/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(item_id):
    kwargs = default_kwargs.copy()
    form = Edit()
    _edit = edit_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _edit


@blueprint.route(f'/{table_name}/<int:item_id>/approve>', methods=['GET', 'POST'])
@login_required
def approve(item_id):
    kwargs = default_kwargs.copy()
    form = Approve()
    _approve = approve_item(form, item_id, table, item_type, item_name, table_name, name, **kwargs)

    return _approve

@blueprint.route(f'/{table_name}/<int:item_id>/update', methods=['GET', 'POST'])
@login_required
def update(item_id):
    item = table.query.get(item_id)
    case_id = item.case_id
    kwargs = default_kwargs.copy()
    discipline = request.args.get('discipline')
    kwargs['discipline'] = discipline
    kwargs['disable_fields'] = ['case_id', 'discipline']
    result_statuses = ["Confirmed", "Saturated", 'Not Tested']
    saved_results = ReportResults.query.filter_by(report_id=item.id).all()
    is_backfill = (request.args.get('backfill') == '1') or (request.form.get('backfill') == '1')
    revise = request.args.get('revise')

    report_type = request.args.get('report_type')
    if report_type == "manual":
        report_type = "Manual Upload"

    form, new_kwargs = get_form_choices(Add(), case_id=case_id, discipline=item.discipline)
    kwargs.update(new_kwargs)
    kwargs['report_type'] = 'Auto-Generated'
    kwargs['report_template_id'] = item.report_template_id
    items = {}

    # Load all specimens and their results (same as 'add')
    if case_id:
        kwargs['result_status_filter'] = result_statuses
        kwargs['case_id'] = case_id
        if kwargs.get('specimens'):
            for specimen in kwargs['specimens']:
                specimen_name = f"{specimen.type.code} | {specimen.accession_number}"
                items[specimen_name] = get_results(specimen.id, item.discipline, result_statuses=result_statuses, report_id=item.id)

    kwargs['items'] = items

    if request.method == 'POST':
        if form.is_submitted() and form.validate():

            # Increment draft number but keep the same report row
            if not is_backfill:
                item.draft_number += 1
                file_name = f"{item.report_name} (DRAFT {item.draft_number})"
                item.file_name = file_name
                item.case_review = None
                item.case_review_date = None
                item.divisional_review = None
                item.divisional_review_date = None

            # Get the selected template
            template = ReportTemplates.query.get(form.report_template_id.data)
            template_path = os.path.join(app.config['FILE_SYSTEM'], 'report_templates', f"{template.name}.docx")

            item.report_template_id = form.report_template_id.data

            if form.report_type.data == 'Auto-generated':
                ReportResults.query.filter_by(report_id=item.id).delete()
                db.session.commit()
                result_ids = form.result_id.data
                result_id_orders = list(map(int, form.result_id_order.data.split(", ")))

                new_results = []
                for result_id in form.result_id.data:
                    print(f'form approximate result id =-=-=-=- {form.approximate_result_id.data}')
                    result_id = int(result_id)
                    primary_results = request.form.getlist("primary_result_id")
                    result = {
                        'report_id': item.id,
                        'result_id': result_id,
                        'primary_result': "Y" if str(result_id) in primary_results else None,
                        'supplementary_result': "Y" if result_id in form.supplementary_result_id.data else None,
                        'observed_result': "Y" if result_id in form.observed_result_id.data else None,
                        'qualitative_result': "Y" if result_id in form.qualitative_result_id.data else None,
                        'approximate_result': "Y" if result_id in form.approximate_result_id.data else None,
                        'order': result_id_orders.index(result_id) + 1
                    }
                    commit_result = ReportResults(**result)
                    new_results.append(commit_result)

                try:
                    db.session.bulk_save_objects(new_results)
                    db.session.flush()  # Ensures issues appear before commit
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()  # Rollback to avoid partial commits

                # generate_report(case_id=form.case_id.data,
                #                 discipline=item.discipline,
                #                 report_id=item.id,  # Keep the same report
                #                 template_path=template_path,
                #                 report_name=item.report_name,
                #                 file_name=file_name)


                old_files = glob.glob(os.path.join(path, f"{item.report_name}*.pdf")) + glob.glob(os.path.join(path, f"{item.report_name}.docx"))

                return redirect(url_for(f"{table_name}.add_comment", item_id=item.id, discipline=discipline))

            else:
                file = form.report_file.data
                original_filename = secure_filename(file.filename)
                filename_base = os.path.splitext(original_filename)[0]
                prefix = filename_base.split("_")[0]

                if prefix != item.case.case_number:
                    print('FAILED UPLOAD ON REVISION')
                    flash(f"Uploaded file name does not match case number '{item.case.case_number}'", "danger")
                    return redirect(request.url)

                save_path = os.path.join(path, file_name)
                file.save(f"{save_path}.docx")

                pythoncom.CoInitialize()
                docx2pdf.convert(f"{save_path}.docx", f"{save_path}.pdf")
                # Check for any PDF attachments linked to results for this case
                results_all = Results.query.filter_by(case_id=case_id).all()
                pdf_attachments = []

                for result in results_all:
                    attachments = Attachments.query.filter_by(table_name="results", record_id=result.id).all()
                    for attachment in attachments:
                        if attachment.path and attachment.path.lower().endswith('.pdf'):
                            full_attachment_path = os.path.join(app.config['FILE_SYSTEM'], attachment.path)
                            if os.path.exists(full_attachment_path):
                                print(f"Appending result attachment: {full_attachment_path}")
                                pdf_attachments.append(full_attachment_path)

                # If there are any valid attachments, merge them to the end of the main PDF
                if pdf_attachments:
                    from PyPDF2 import PdfMerger
                    merged_pdf_path = f"{save_path}.pdf"

                    try:
                        pdf_merger = PdfMerger()
                        with open(merged_pdf_path, "rb") as base_pdf:
                            pdf_merger.append(base_pdf)

                        for attachment in pdf_attachments:
                            with open(attachment, "rb") as attach_pdf:
                                pdf_merger.append(attach_pdf)

                        temp_pdf_path = f"{save_path}_temp.pdf"
                        with open(temp_pdf_path, "wb") as merged_file:
                            pdf_merger.write(merged_file)

                        os.remove(merged_pdf_path)
                        os.rename(temp_pdf_path, merged_pdf_path)
                        print("PDF merge successful.")

                    except Exception as e:
                        print(f"Error merging attachments: {e}")
                # Redirect to the view page (or another appropriate page)

                return redirect(url_for(f"{table_name}.view", item_id=item.id))

    kwargs['delay'] = 25

    _update = update_item(form, item_id, table, item_type, item_name, table_name, requires_approval, name, locking=False, **kwargs)

    return _update

@blueprint.route(f'/{table_name}/<int:item_id>/lock', methods=['GET', 'POST'])
@login_required
def lock(item_id):
    _lock = lock_item(item_id, table, name)

    return _lock


@blueprint.route(f'/{table_name}/<int:item_id>/unlock', methods=['GET', 'POST'])
@login_required
def unlock(item_id):

    redirect_to = url_for(f'{table_name}.view_list')

    _unlock = unlock_item(item_id, table, name, redirect_to)

    return _unlock


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
    item = table.query.get_or_404(item_id)
    if current_user.permissions in ['Admin', 'Owner']:
        item.report_status = 'Removed'
        db.session.commit()
        ReportResults.query.filter_by(report_id=item_id).delete()
        ReportComments.query.filter_by(report_id=item_id).delete()
    _remove = remove_item(item_id, table, table_name, item_name, name)

    return _remove


@blueprint.route(f'/{table_name}/<int:item_id>/approve_remove', methods=['GET', 'POST'])
@login_required
def approve_remove(item_id):
    item = table.query.get(item_id)

    _approve_remove = approve_remove_item(item_id, table, table_name, item_name, name)
    item.report_status = 'Removed'
    db.session.commit()
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

    item = table.query.get_or_404(item_id)

    item.report_status = 'Ready for CR'
    db.session.commit()

    return _restore_item


@blueprint.route(f'/{table_name}/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def delete(item_id):
    form = Add()

    ReportResults.query.filter_by(report_id=item_id).delete()
    ReportComments.query.filter_by(report_id=item_id).delete()

    item = table.query.get(item_id)
    if item:
        files = glob.glob(f"{path}\{item.report_name}*")

        for file in files:
            os.remove(file)

    _delete_item = delete_item(form, item_id, table, table_name, item_name, name)

    return _delete_item


@blueprint.route(f'/{table_name}/delete_all', methods=['GET', 'POST'])
@login_required
def delete_all():
    # files = glob.glob(f"{path}\*")
    # for file in files:
    #     os.remove(file)

    _delete_items = delete_items(table, table_name, item_name)

    return _delete_items

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


@blueprint.route(f'/{table_name}/<int:item_id>/export_attachments', methods=['GET', 'POST'])
@login_required
def export_attachments(item_id):

    _export_attachments = export_item_attachments(table, item_name, item_id, name)

    return _export_attachments


@blueprint.route(f'/{table_name}', methods=['GET', 'POST'])
@login_required
def view_list():

    kwargs = default_kwargs.copy()

    query = request.args.get('query')
# Prioritize anything ending with '_B' by assigning it a lower sort value
    bio_first = case(
        (table.discipline == 'Biochemistry', 0),
        else_=1
    )
# Join with Cases
    tox_start_date = func.coalesce(Cases.toxicology_alternate_start_date, Cases.toxicology_start_date)

    # Join with Cases
    items_query = table.query.join(Cases).filter(table.db_status == 'Active')

    if query == 'ready_for_cr':
        items_query = items_query.filter(table.report_status == 'Ready for CR')
    elif query == 'ready_for_dr':
        items_query = items_query.filter(table.report_status == 'Ready for DR')
    elif query == 'all':
        items_query = table.query.join(Cases).filter(table.db_status == 'Active', table.report_status == 'Finalized')
        items_query = items_query.order_by(table.divisional_review_date.desc())
    elif query == 'removed':
        items_query = table.query.join(Cases).filter(table.db_status == 'Removed')
    elif query == 'removal-pending':
        items_query = table.query.join(Cases).filter(table.db_status == 'Removal Pending')
    elif query == 'locked':
        items_query = items_query.filter(table.locked == True)
    else:
        items_query = items_query.filter(table.report_status.in_(['Ready for CR', 'Ready for DR', 'Created']))

    items_query = items_query.order_by(bio_first, tox_start_date.asc())

    ready_for_cr = table.query.filter_by(report_status='Ready for CR', db_status='Active').count()
    ready_for_dr = table.query.filter_by(report_status='Ready for DR', db_status='Active').count()

    kwargs['query'] = query

    generic_comments = [
        "Protocol not performed due to specimen condition and/or volume; consequently, the effective scope should be considered.",
        "Subsequent testing not performed due to specimen condition and/or volume; consequently, the ability to report components and the effective scope should be considered.",
        "Analysis performed at half volume due to specimen condition and/or volume; consequently, effective reporting limits should be considered.",
        "Analytical challenges due to interference and/or specimen condition; consequently, detection of cannabinoids may be reduced.",
        "Analytical challenges due to interference and/or specimen condition; consequently, detection of some compounds may be reduced."
    ]


    _view_list = view_items(table, item_name, item_type, table_name,
                            items=items_query,
                            ready_for_cr=ready_for_cr,
                            ready_for_dr=ready_for_dr,
                            **kwargs
                            )
 
    return _view_list


@blueprint.route(f'/{table_name}/<int:item_id>', methods=['GET','POST'])
@login_required
def view(item_id):
    item = table.query.get_or_404(item_id)

    view_only = request.args.get('view_only')

    if view_only == 'true' or view_only =='True':
        view_only = True
    elif current_user.permissions == 'MED':
        view_only = True
    elif item.locked and item.locked_by != current_user.initials:
        view_only = True
    else:
        view_only = False
        item.locked = True
        item.locked_by = current_user.initials
        item.lock_date = datetime.now()
        db.session.commit()

    kwargs = default_kwargs.copy()

    file_path = os.path.join(app.config['FILE_SYSTEM'], table_name, f"{item.file_name}.pdf")
    file_exists = os.path.exists(file_path)
    kwargs['file_exists'] = file_exists
    kwargs['redirect_url'] = url_for(f"{table_name}.view", item_id=item.id)

    print(f'file_name == {item.file_name}')

    print(f'template id == {item.report_template}')

    assigned_dr_choice = AssignDRForm()
    assigned_cr_choice = AssignCRForm()

    # Get all users where job_title is 'Forensic Toxicologist', 'Admin', or 'Owner'
    drlist = Users.query.filter(
        db.or_(
            Users.job_title == 'Forensic Toxicologist',
            Users.job_title == 'Lead Forensic Toxicologist',
            Users.job_title == 'Chief Forensic Toxicologist and Director',
            Users.job_title == 'Forensic Toxicologist Supervisor and Manager'
        )
    ).all()

    # Populate choices with (id, initials)
    excluded_initials = ['MVS', 'DJP', 'TLD', 'MCF', 'SRT']  # Replace with the initials you want to hide

    filtered_drlist = [user for user in drlist if user.initials not in excluded_initials]

    assigned_dr_choice.assigned_dr.choices = [(user.id, user.initials) for user in filtered_drlist]
    assigned_cr_choice.assigned_cr.choices = [(user.id, user.initials) for user in filtered_drlist]

    # Pass form to template
    kwargs['assigned_dr'] = assigned_dr_choice
    kwargs['assigned_cr'] = assigned_cr_choice

    # assigns form value to database column
    if assigned_dr_choice.validate() and assigned_dr_choice.is_submitted():
        item.assigned_dr = assigned_dr_choice.assigned_dr.data
        item.locked = False
        item.locked_by = None
        item.lock_date = None
        db.session.commit()
        return redirect(url_for('reports.view', item_id=item.id, view_only='true'))

    if assigned_cr_choice.validate() and assigned_cr_choice.is_submitted():
        item.assigned_cr = assigned_cr_choice.assigned_cr.data
        item.locked = False
        item.locked_by = None
        item.lock_date = None
        db.session.commit()
        return redirect(url_for('reports.view', item_id=item.id, view_only='true'))

    alias = f"{getattr(item, name)} | {item.report_status}"

    _view = view_item(item, alias, item_name, table_name, default_buttons=False, view_only=view_only, **kwargs)
    return _view


@blueprint.route(f'/{table_name}/<int:item_id>/ready_for_cr', methods=['GET', 'POST'])
@login_required
def ready_for_cr(item_id):

    item = table.query.get(item_id)
    case = Cases.query.get(item.case.id)
    item.report_status = 'Ready for CR'

    setattr(case, f"{item.discipline.lower()}_status", "CR")

    db.session.commit()

    return redirect(request.referrer)


@app.route("/check_report_status")
def check_report_status():
    job_id = request.args.get("report_id")
    return jsonify({"status": queue_get_status(job_id)})

@blueprint.route(f'/{table_name}/<int:item_id>/cr', methods=['GET', 'POST'])
@login_required
def cr(item_id):
    item = table.query.get(item_id)
    case = Cases.query.get(item.case.id)

    template_path = os.path.join(path, f"{item.file_name}.docx")
    if not os.path.exists(template_path):
        tpl = ReportTemplates.query.get(item.report_template_id)
        template_path = os.path.join(app.config['FILE_SYSTEM'], 'report_templates', f"{tpl.name}.docx")

    item.report_status = 'Ready for DR'
    item.case_review = current_user.id
    item.case_review_date = datetime.now()
    item.file_name = f"{item.file_name}_Ready for CR"
    setattr(case, f"{item.discipline.lower()}_status", "DR")

    if current_user.has_signature:
        future = generate_report(
            case_id=case.id,
            discipline=item.discipline,
            report_id=item.id,
            template_path=template_path,
            report_name=item.report_name,
            file_name=item.file_name,
            cr=current_user.id
        )
        job_id = getattr(future, "job_id", None)   # <-- real queue id
        item.locked = False
        item.locked_by = None
        item.lock_date = None
    else:
        flash(f'{current_user.initials} does not have initials uploaded', 'error')
        job_id = None

    db.session.commit()
    return jsonify({
        "report_id": job_id,
        "redirect": url_for(f"{table_name}.view", item_id=item.id, view_only=True)
    })




@blueprint.route(f'/{table_name}/<int:item_id>/dr', methods=['GET', 'POST'])
@login_required
def dr(item_id):
    item = table.query.get(item_id)
    case = Cases.query.get(item.case.id)

    template_path = os.path.join(path, f"{item.file_name}.docx")
    if not os.path.exists(template_path):
        tpl = ReportTemplates.query.get(item.report_template_id)
        template_path = os.path.join(app.config['FILE_SYSTEM'], 'report_templates', f"{tpl.name}.docx")

    # finalize state
    specimens = Specimens.query.filter_by(case_id=item.case_id, discipline=item.discipline).all()
    item.file_name = item.report_name
    item.report_status = 'Finalized'
    item.divisional_review = current_user.id
    item.divisional_review_date = datetime.now()
    setattr(case, f"{item.discipline.lower()}_status", "Ready for Dissemination")
    item.communications = None
    for s in specimens:
        s.communications = None

    if current_user.has_signature:
        future = generate_report(
            case_id=case.id,
            discipline=item.discipline,
            report_id=item.id,
            template_path=template_path,
            report_name=item.report_name,
            file_name=item.report_name,
            cr=item.case_reviewer.id,
            dr=current_user.id,
        )
        job_id = getattr(future, "job_id", None)
    else:
        flash(f'{current_user.initials} does not have initials uploaded', 'error')
        job_id = None

    item.locked = False
    item.locked_by = None
    item.lock_date = None
    db.session.commit()

    # DO NOT return a report_id → no polling for DR
    return jsonify({
        "report_id": job_id,
        "redirect": url_for(f"{table_name}.view", item_id=item.id)
    })


@blueprint.route(f'/{table_name}/get_disciplines/', methods=['GET', 'POST'])
@login_required
def get_disciplines_json():
    case_id = request.args.get('case_id', type=int)
    response = get_disciplines(case_id)

    return response


@blueprint.route('/reports/create', methods=['POST'])
@login_required
def create_report():
    selected_comments = request.form.get('selected_comments')
    comment_ids = json.loads(selected_comments)

    # Validate the report ID (assumes it's passed in the form)
    report_id = request.form.get('report_id')  # Ensure this field exists in the form
    if not report_id:
        return jsonify({"error": "Report ID is required"}), 400
    
    report_id = int(report_id)

    free_comment = (request.form.get('free_comment') or "").strip()
    if free_comment:
        ci = CommentInstances(
            comment_item_type='Reports',
            comment_item_id=report_id,
            comment_type='Manual',
            comment_text=free_comment,
            db_status='Active',
            create_date=datetime.now()
        )
        db.session.add(ci)

    current_comments = db.session.query(ReportComments).filter(ReportComments.report_id == report_id)
    if current_comments:
        current_comments.delete(synchronize_session=False)

    # Process and save each selected comment to the ReportComments table
    for index, comment_id in enumerate(comment_ids, start=1):
        report_comment = ReportComments(
            report_id=report_id,
            comment_id=comment_id,
            order=index
        )
        db.session.add(report_comment)

    # Commit to the database
    db.session.commit()

    # Provide a success message and redirect
    flash("Comments successfully saved to the report.", "success")
    return redirect(url_for('reports.view', item_id=report_id))  # Adjust view route as needed


@blueprint.route(f'/{table_name}/<int:item_id>/generate_report_route', methods=['POST'])
@login_required
def generate_report_route(item_id):
    item = table.query.get_or_404(item_id)
    template = ReportTemplates.query.get(item.report_template_id)
    if not template:
        flash('Invalid template selected.', 'danger')
        return redirect(request.referrer)

    template_path = os.path.join(app.config['FILE_SYSTEM'], 'report_templates', f"{template.name}.docx")
    item.report_status = 'Ready for CR'
    db.session.commit()

    fut = generate_report(
        case_id=item.case_id,
        discipline=item.discipline,
        report_id=item.id,
        template_path=template_path,
        report_name=item.report_name,
        file_name=item.file_name
    )

    return jsonify({
        "report_id": getattr(fut, "job_id", None),
        "redirect": url_for(f"{table_name}.view", item_id=item.id)
    })



@blueprint.route(f'/{table_name}/<int:item_id>/revert', methods=['GET', 'POST'])
@login_required
def revert(item_id):

    item = table.query.get_or_404(item_id)

    cr_user = Users.query.filter(Users.id == item.case_review).first()

    old_file_path = os.path.join(app.config['FILE_SYSTEM'], table_name, f"{item.file_name}.pdf")
    new_file_name = f"{item.report_name} (DRAFT {item.draft_number})"

    item.report_status = 'Ready for CR'
    item.locked_by = cr_user.initials
    item.lock_date = datetime.now()
    item.case_review = None
    item.case_review_date = None
    item.file_name = new_file_name
    item.reverted_by = current_user.initials
    item.revert_date = datetime.now()
    db.session.commit()
    os.remove(old_file_path)


    flash("Report has been reverted successfully.", "success")

    return redirect(url_for(f"{table_name}.view", item_id=item.id))


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


        return redirect(url_for('reports.view', item_id=item_id))  # Redirect to item view page

    # On GET request, keep the field empty for new entry
    form.communications.data = ''

    return render_template('reports/communications.html', form=form, item=item, errors=errors, **kwargs)

    return _update


@blueprint.route(f'/{table_name}/<int:item_id>/backfill', methods=['GET'])
@login_required
def backfill(item_id):
    item = table.query.get_or_404(item_id)

    if item.report_status != 'Finalized':
        flash("Backfill is only available for Finalized reports.", "warning")
        return redirect(url_for(f"{table_name}.view", item_id=item.id))

    return redirect(url_for(f"{table_name}.update",
                            item_id=item.id,
                            discipline=item.discipline,
                            backfill=1))


@blueprint.route(f'/{table_name}/<int:item_id>/check_results', methods=['GET'])
@login_required
def check_results(item_id):
    item = table.query.get_or_404(item_id)

    q = (
        db.session.query(ReportResults, Results, Tests, Specimens, Components)
        .join(Results, ReportResults.result_id == Results.id)
        .join(Tests, Results.test_id == Tests.id)
        .join(Specimens, Tests.specimen_id == Specimens.id)
        .join(Components, Results.component_id == Components.id)
        .filter(ReportResults.report_id == item.id)
    )

    rows = q.all()

    def group_rank(rr):
        # Official (primary) -> 0, Official (qual) -> 1, Observed -> 2, Other -> 3
        if rr.primary_result == 'Y': return 0
        if rr.qualitative_result == 'Y': return 1
        if rr.observed_result == 'Y': return 2
        return 3

    # Stable, deterministic sort: by group, then rr.order, then Results.id
    rows.sort(key=lambda t: (group_rank(t[0]), (t[0].order or 0), t[1].id))

    def bucket_name(rr):
        if rr.primary_result == 'Y': return "official", "Official"
        if rr.qualitative_result == 'Y': return "official", "Official (Qualitative)"
        if rr.observed_result == 'Y': return "observed", "Observed"
        return "other", "Other"

    def _get(obj, attr, default=""):
        return getattr(obj, attr, default) if obj is not None else default

    def _fmt_date(dt):
        try:
            return dt.strftime("%m/%d/%Y") if dt else ""
        except Exception:
            return ""

    grouped = {"official": [], "observed": [], "other": []}

    for rr, r, t, s, c in rows:
        bucket, report_as = bucket_name(rr)
        acc = f" ({_get(s, 'accession_number')})" if _get(s, 'accession_number') else ""
        specimen = f"[{_get(_get(s, 'type'), 'code')}] {_get(_get(s, 'type'), 'name')}{acc}"

        grouped[bucket].append({
            "order": rr.order,
            "report_as": report_as,
            "supplementary": "Yes" if rr.supplementary_result == 'Y' else "",
            "status": _get(r, "result_status"),
            "specimen": specimen,
            "component": _get(r, "component_name") or _get(c, "component_name"),
            "result": _get(r, "result"),
            "supp_result": _get(r, "supplementary_result"),
            "unit": _get(_get(r, "unit"), "name"),
            "assay": _get(_get(t, "assay"), "assay_name"),
            "batch_date": _fmt_date(_get(_get(t, "batch"), "extraction_date")),
            "test_id": _get(t, "test_id"),
            "result_id": _get(r, "id"),
        })

    counts = {k: len(v) for k, v in grouped.items()}

    return render_template(
        "/reports/check_results.html",
        item=item,
        official=grouped["official"],
        observed=grouped["observed"],
        other=grouped["other"],
        counts=counts,
    )