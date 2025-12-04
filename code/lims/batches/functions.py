from datetime import datetime
import os
import re
import time

from flask_login import current_user
import pythoncom
import pytz
from docx2pdf import convert
from docxtpl import DocxTemplate
from flask import jsonify, current_app, send_file, redirect, url_for, render_template
from pytz import timezone
from sqlalchemy import and_
from win32com.client import Dispatch
import pandas as pd

from lims import db
from lims.models import Tests, Assays, Batches, Instruments, \
    BatchTemplates, Cases, CaseTypes, StandardsAndSolutions, Modifications, Specimens, BatchConstituents


def get_form_choices(form, function='Add', assay_id=None, batch_id=None):
    if function == 'Add':
        assays = []
        if assay_id:
            assay = Assays.query.get(assay_id)
            tests = Tests.query.filter_by(assay_id=assay.id, test_status='Pending').count()
            assays = [(assay.id, f"{assay.assay_name} [{tests}]")]
        else:
            for assay in Assays.query.order_by(Assays.assay_order.asc()):
                tests = Tests.query.filter_by(assay_id=assay.id, test_status='Pending').count()
                if tests != 0:
                    assays.append((assay.id, f"{assay.assay_name} [{tests}]"))

            if len(assays) != 0:
                assays.insert(0, (0, 'Please select an assay'))
            else:
                assays.insert(0, (0, 'No pending tests'))

        form.assay_id.choices = assays

        form.test_id.choices = [(item.id, item.id) for item in Tests.query.filter_by(test_status='Pending')]

    # elif function == 'Update':
    #     assay = Assays.query.get(assay_id)
    #     form.assay_id.choices = [(assay.id, assay.assay_name)]
    #     form.test_id.choices = [(item.id, item.id) for item in Tests.query.filter_by(assay_id=assay.id).filter(Tests.test_status.in_(['Pending', 'Processing']))]
    #     print(len(form.test_id.choices))
    else:
        instruments = []
        batch_templates = []
        constituents = []

        if batch_id is not None:
            batch = Batches.query.get(batch_id)

            instruments = [(item.id, item.name) for item in Instruments.query.all()]
            batch_templates = [(item.id, item.name) for item in
                               BatchTemplates.query.filter_by(instrument_id=batch.assay.instrument.id)
                               .filter(BatchTemplates.max_samples >= batch.test_count)]

            constituents = [(item.id, item.lot) for item in
                            StandardsAndSolutions.query.filter(and_(StandardsAndSolutions.assay.contains(str(assay_id)),
                                                                    StandardsAndSolutions.in_use == False))]

        instruments.insert(0, (0, "Please select an instrument"))
        batch_templates.insert(0, (0, "Please select a batch template"))
        form.instrument_type_id.choices = instruments
        # form.batch_template_id.choices = batch_templates
        form.constituent_id.choices = constituents

        # form.extracted_by_id.choices =[(item.id, item.initials) for item in Users.query.filter_by(status='Active').order_by(Users.initials.asc())]

    return form


def get_tests(assay_id, batch_id):
    items_lst = []
    num_tests = ""

    if assay_id not in [0, None]:
        assay = Assays.query.get(assay_id)
        items = Tests.query.filter_by(assay_id=assay_id, test_status='Pending').order_by(Tests.create_date.asc())
        num_tests = assay.num_tests
    elif batch_id not in [0, None]:
        items = Tests.query.filter_by(batch_id=batch_id).order_by(Tests.create_date.asc())
    else:
        items = []

    if items.count() != 0:
        x = 0
        for item in items:
            x += 1
            dict = {}
            if item.dilution == '1':
                dilution = ''
            elif (item.dilution) and (item.dilution.isnumeric()):
                if float(item.dilution) > 1:
                    dilution = f"d1/{item.dilution}"
            else:
                dilution = item.dilution
            if item.case.priority == 'Normal':
                priority = ""
            else:
                priority = item.case.priority

            test_dict = {
                '#': x,
                'id': item.id,
                'assay': item.assay.assay_name,
                'case_number': item.case.case_number,
                'accession_numer': item.specimen.accession_number,
                'code': item.specimen.type.code,
                'description': item.specimen.type.name,
                'dilution': dilution,
                'directives':item.directives,
                'test_date': item.create_date.strftime('%m/%d/%Y %H%M'),
                'test_ordered_by': item.created_by,
                'current_sample_amount': item.specimen.current_sample_amount,
                'submitted_sample_amount':item.specimen.submitted_sample_amount,
                'condition': item.specimen.condition,
                'priority': priority
            }

            items_lst.append(test_dict)


    # else:
    #     items_lst.append({'id': 0, 'name': 'This assay has no pending tests.'})

    return jsonify({'tests': items_lst,
                    'num_tests': num_tests})


def get_newest(assay_id):
    assay = Assays.query.get(assay_id)
    num_tests = int(assay.num_tests)

    tests = Tests.query.filter_by(test_status='Pending', assay_id=assay_id).order_by(Tests.create_date.desc()).all()
    tests = [item.id for item in tests]
    n_tests = len(tests)
    row_lst = [x for x in range(n_tests - num_tests, n_tests)]
    if n_tests > num_tests:
        tests = tests[:num_tests]
        n_tests = num_tests

    test_lst = ",".join(map(str, tests))

    print(row_lst)
    return jsonify(tests=tests,
                   test_lst=test_lst,
                   row_lst=row_lst
                   )


def get_oldest(assay_id):

    assay = Assays.query.get(assay_id)
    num_tests = int(assay.num_tests)

    tests = Tests.query.filter_by(test_status='Pending', assay_id=assay_id).order_by(Tests.create_date.asc()).all()
    tests = [item.id for item in tests]
    n_tests = len(tests)
    if len(tests) > num_tests:
        tests = tests[:num_tests]
        n_tests = num_tests

    test_lst = ",".join(map(str, tests))

    row_lst = [x for x in range(0, n_tests)]

    return jsonify(tests=tests,
                   test_lst=test_lst,
                   row_lst=row_lst
                   )


def get_optimum(assay_id):

    assay = Assays.query.get(assay_id)
    num_tests = int(assay.num_tests)

    if 'GCET' in assay.assay_name:
        # Do not order by priority for GCET batches
        tests = Tests.query.filter_by(test_status='Pending', assay_id=assay_id)\
            .join(Cases)\
            .join(CaseTypes)\
            .order_by(
            CaseTypes.batch_level.asc(),
            Cases.case_number,
            CaseTypes.code,
            Tests.dilution,
            Tests.id
        ).all()
    else:        
        tests = Tests.query.filter_by(test_status='Pending', assay_id=assay_id)\
            .join(Cases)\
            .join(CaseTypes)\
            .order_by(
            Cases.priority,
            CaseTypes.batch_level.asc(),
            Cases.case_number,
            CaseTypes.code,
            Tests.dilution,
            Tests.id
        ).all()

    items_lst = []
    if len(tests) != 0:
        x = 0
        for item in tests:
            x += 1
            dict = {}
            if item.dilution == '1':
                dilution = ''
            elif (item.dilution) and (item.dilution.isnumeric()):
                if float(item.dilution) > 1:
                    dilution = f"d1/{item.dilution}"
            else:
                dilution = item.dilution
            if item.case.priority == 'Normal':
                priority = ""
            else:
                priority = item.case.priority

            test_dict = {
                '#': x,
                'id': item.id,
                'assay': item.assay.assay_name,
                'case_number': item.case.case_number,
                'accession_numer': item.specimen.accession_number,
                'code': item.specimen.type.code,
                'description': item.specimen.type.name,
                'dilution': dilution,
                'directives': item.directives,
                'days_since_submission': '',
                'test_date': item.create_date.strftime('%m/%d/%Y %H%M'),
                'test_ordered_by': item.created_by,
                'current_sample_amount': item.specimen.current_sample_amount,
                'submitted_sample_amount': item.specimen.submitted_sample_amount,
                'condition': item.specimen.condition,
                'priority': priority
            }

            items_lst.append(test_dict)

    tests = [item.id for item in tests]
    n_tests = len(tests)

    if n_tests > num_tests:
        tests = tests[:num_tests]
        n_tests = num_tests

    row_lst = [x for x in range(0, n_tests)]
    test_lst = ",".join(map(str, tests))

    return jsonify(items_lst=items_lst,
                   tests=tests,
                   test_lst=test_lst,
                   row_lst=row_lst
                   )


def print_tests(test):
    """
    Prints labels

    Args:
        test: ORM of the test that is part of the batch.

    Returns:

    """

    # Assign name of printer
    # Printer assigned based on task
    # my_printer = r'\\OCMEG9M026.medex.sfgov.org\DYMO LabelWriter 450'
    my_printer = r'DYMO LabelWriter 450'

    if 'COHB' in test.assay.assay_name:
        # Assign label parameters based on specimen
        table_barcode = f'tests: {test.id}'
        print(f'TABLE BARCODE: {table_barcode}')
        read_barcode = f'{test.case.case_number} {test.specimen.accession_number}'
        text = test.test_name

        # Get path to label template
        label_path = os.path.join(current_app.root_path, 'static/label_templates', 'extraction_cohb.label')

        # Initialize COM library
        pythoncom.CoInitialize()

        # Get printer object
        printer_com = Dispatch('Dymo.DymoAddIn')

        # Select relevant printer
        printer_com.SelectPrinter(my_printer)

        # Load label template from label path
        printer_com.Open(label_path)

        # Assign the label object
        printer_label = Dispatch('Dymo.DymoLabels')

        # Set relevant fields of label
        printer_label.SetField('Barcode', table_barcode)
        printer_label.SetField('Barcode_2', read_barcode)
        printer_label.SetField('Barcode_3', table_barcode)
        printer_label.SetField('Barcode_4', read_barcode)
        printer_label.SetField('Text', text)
        printer_label.SetField('Text_1', text)

        # Print one label
        printer_com.StartPrintJob()
        printer_com.Print(1, False)

        # End printing
        printer_com.EndPrintJob()

        # Uninitialize
        pythoncom.CoUninitialize()
    else:
        # Assign label parameters based on specimen
        text, text_2, text_1 = test.test_name.split(' ')
        label_barcode = f'tests: {test.id}'

        # Get path to label template
        label_path = os.path.join(current_app.root_path, 'static/label_templates', 'extraction.label')

        # Initialize COM library
        pythoncom.CoInitialize()

        # Get printer object
        printer_com = Dispatch('Dymo.DymoAddIn')

        # Select relevant printer
        printer_com.SelectPrinter(my_printer)

        # Load label template from label path
        printer_com.Open(label_path)

        # Assign the label object
        printer_label = Dispatch('Dymo.DymoLabels')

        # Set relevant fields of label
        printer_label.SetField('Barcode', label_barcode)
        printer_label.SetField('Text', text)
        printer_label.SetField('Text__1', text_1)
        printer_label.SetField('Text_2', text_2)
        printer_label.SetField('Text_1', text)
        printer_label.SetField('Text__2', text_2)
        printer_label.SetField('Text___1', text_1)
        printer_label.SetField('Barcode_1', label_barcode)

        # Print one label
        printer_com.StartPrintJob()
        printer_com.Print(1, False)

        # End printing
        printer_com.EndPrintJob()

        # Uninitialize
        pythoncom.CoUninitialize()


def modifications(event, status, record_id, revision, field, original_value, original_value_text, new_value,
                  new_value_text, submitted_by, reviewed_by, reviewed_date):
    modification = Modifications(
        event=event,  # Created, updated, etc.
        status=status,  # Approved, pending etc.
        table_name='Batches',
        record_id=record_id,  # ID in batches table
        revision=revision,
        field=field.label.text,
        field_name=field.name,
        original_value=original_value,
        original_value_text=original_value_text,
        new_value=new_value,
        new_value_text=new_value_text,
        submitted_by=submitted_by,
        submitted_date=datetime.now(),
        reviewed_by=reviewed_by,
        review_date=reviewed_date
    )
    db.session.add(modification)
    db.session.commit()


# def batches_printable_page(item_id):
#     doc = DocxTemplate(r"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Batch Print\batch_print_template.docx")
#
#     save_directory = r"C:\Users\ekarwowski\Documents\GitHub\lims\code\static\Batch Printout"
#
#     batch = Batches.query.filter_by(id=item_id).first()
#
#     contents = Tests.query.filter_by(batch_id=item_id)
#
#     data = {}
#
#     data['batch_name'] = batch.batch_id
#
#     data['contents'] = []
#     for c in contents:
#         content = {
#             "vial": c.vial_position,
#             "spec_type": c.specimen.type.code,
#             "case_num": c.case.case_number,
#             "acc_num": c.specimen.accession_number,
#             "instruction": c.directives,
#         }
#         data['contents'].append(content)
#
#     docx_file_name = f"{batch.batch_id}.docx"
#     pdf_file_name = f"{batch.batch_id}.pdf"
#
#     # Paths for DOCX and PDF files
#     docx_path = os.path.join(save_directory, docx_file_name)
#     pdf_path = os.path.join(save_directory, pdf_file_name)
#
#     # Render the DOCX file with the provided data
#     doc.render(data, autoescape=True)
#     doc.save(docx_path)
#
#     # Initialize COM for the conversion
#     pythoncom.CoInitialize()
#
#     # Convert DOCX to PDF
#     convert(docx_path, pdf_path)
#
#     # Optionally remove the DOCX file after conversion
#     os.remove(docx_path)
#
#     # Return the path to the generated PDF
#     return pdf_path
#

def delete_file_after_delay(file_path, delay=2):
    # Wait for a few seconds to ensure the file is no longer being accessed
    try:
        time.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
    except Exception as e:
        print(f"Error deleting file: {e}")


def batches_printable_page(item_id):
    """
    This is responsible for the "print" button within batches
    This creates a PDF for FLAs showing Vial - Specimen type - Case # - Acc # - Instructions of a batch
    """
    doc = DocxTemplate(r"lims\static\batch_pdf_reference\batch_print_template.docx")
    save_directory = r"lims\static\batch_pdf_reference"

    batch = Batches.query.filter_by(id=item_id).first()
    contents = Tests.query.filter_by(batch_id=item_id).join(Tests.case).join(Tests.specimen).order_by(
        Cases.case_number,
        Specimens.accession_number,
        Tests.dilution
    )

    data = {
        'batch_name': batch.batch_id,
        'contents': [
            {
                "case_num": t.case.case_number,
                "acc_num": t.specimen.accession_number,
                "sample_name": t.specimen.type.name,
                "location": t.specimen.custody,
                "dilution": t.dilution,
                "test_id": t.test_id.rsplit('_', 1)[-1],
            } for t in contents
        ]
    }

    docx_file_name = f"{batch.batch_id}.docx"
    pdf_file_name = f"{batch.batch_id}.pdf"

    # Paths for DOCX and PDF files
    docx_path = os.path.join(save_directory, docx_file_name)
    pdf_path = os.path.join(save_directory, pdf_file_name)

    # Render and save the DOCX file
    doc.render(data, autoescape=True)
    doc.save(docx_path)

    # Initialize COM for the conversion
    pythoncom.CoInitialize()
    convert(docx_path, pdf_path)

    # Clean up the DOCX file after conversion
    os.remove(docx_path)

    print(f'pdf path - {pdf_path}')

    # pdf_return_path = pdf_path.replace(r"lims\static", r"\static")
    # print(pdf_return_path)
    # return render_template(f'/static/batch_pdf_reference/{pdf_file_name}')


def get_batch_checks(item_id):
    """

    Args:
        item_id (int): The id of the batch object.

    Returns:
        dict: Dictionary of relevant batch level checks depending on the assay.

    """

    item = Batches.query.get(item_id)

    # Dictionary of all batch checks
    checks = {
        'batch_specimen_check': '',
        'batch_sequence': '',
        'batch_load_check': '',
        'batch_transfer_check': '',
    }

    # Get relevant tests and batch constituents
    tests = Tests.query.filter_by(batch_id=item_id).all()
    constituents = BatchConstituents.query.filter_by(batch_id=item_id).all()

    # Check if constituent checks are complete
    for const in constituents:
        checks['batch_specimen_check'] = 'Complete'
        checks['batch_sequence'] = 'Complete'
        if const.specimen_check_by is not None:
            pass
        elif const.specimen_check_by is None:
            checks['batch_specimen_check'] = 'Incomplete'

        if const.sequence_check is not None:
            pass
        elif const.sequence_check is None:
            checks['batch_sequence'] = 'Incomplete'

    # Check for tandem batch
    if 'LCCI' in item.assay.assay_name and item.tandem_id:
        # Get tandem tests and constituents
        tandem_tests = Tests.query.filter_by(batch_id=item.tandem_id).all()
        tandem_constituents = BatchConstituents.query.filter_by(batch_id=item.tandem_id).all()

        # Check tests check statuses
        for test in tandem_tests:

            checks['batch_load_check'] = 'Complete'
            checks['batch_transfer_check'] = 'Complete'
            checks['batch_sequence'] = 'Complete'

            if test.load_check is not None:
                pass
            elif test.load_check is None:
                checks['batch_load_check'] = 'Incomplete'

            if test.transfer_check is not None:
                pass
            elif test.transfer_check is None:
                checks['batch_transfer_check'] = 'Incomplete'

            if test.sequence_check is not None:
                pass
            elif test.sequence_check is None:
                checks['batch_sequence'] = 'Incomplete'

            # Check constituents check statuses, same logic as above
            for const in tandem_constituents:
                if const.transfer_check is not None:
                    pass
                elif const.transfer_check is None:
                    checks['batch_transfer_check'] = 'Incomplete'

                if const.sequence_check is not None:
                    pass
                elif const.sequence_check is None:
                    checks['batch_sequence'] = 'Incomplete'

    # Check for ref batch and relevant checks
    elif 'REF' in item.assay.assay_name:
        # Check tests check statuses
        for test in tests:

            checks['batch_specimen_check'] = 'Complete'
            checks['batch_transfer_check'] = 'Complete'
            # If relevant check is completed, keep status boolean, else set status to False
            if test.specimen_check != 'Skipped' and test.specimen_check is not None:
                pass
            elif test.specimen_check is None or test.specimen_check == 'Skipped':
                checks['batch_specimen_check'] = 'Incomplete'

    # Check for all other batch relevant checks
    else:

        # Check constituents check statuses, same logic as above
        for const in constituents:
            if const.transfer_check is not None:
                pass
            elif const.transfer_check is None:
                checks['batch_transfer_check'] = 'Incomplete'

        # Check tests check statuses
        for test in tests:

            checks['batch_specimen_check'] = 'Complete'
            checks['batch_load_check'] = 'Complete'
            checks['batch_transfer_check'] = 'Complete'
            checks['batch_sequence'] = 'Complete'

            # If relevant check is completed, keep status boolean, else set status to False
            if test.specimen_check != 'Skipped' and test.specimen_check is not None:
                pass
            elif test.specimen_check is None or test.specimen_check == 'Skipped':
                checks['batch_specimen_check'] = 'Incomplete'

            if test.load_check is not None:
                pass
            elif test.load_check is None:
                checks['batch_load_check'] = 'Incomplete'

            if test.transfer_check is not None:
                pass
            elif test.transfer_check is None:
                checks['batch_transfer_check'] = 'Incomplete'

            if test.sequence_check is not None:
                pass
            elif test.sequence_check is None:
                checks['batch_sequence'] = 'Incomplete'

        # Check constituents check statuses, same logic as above
        for const in constituents:
            if const.specimen_check_by is not None:
                pass
            elif const.specimen_check_by is None:
                checks['batch_specimen_check'] = 'Incomplete'

            if const.transfer_check is not None:
                pass
            elif const.transfer_check is None:
                checks['batch_transfer_check'] = 'Incomplete'

            if const.sequence_check is not None:
                pass
            elif const.sequence_check is None:
                checks['batch_sequence'] = 'Incomplete'

    return checks


def extract_suffix(sample_name):
    """
    Extracts the substring that comes after the two digits and underscore (##_)
    in the sample name. If the sample name doesn't match the pattern,
    returns None.
    """
    # This regex looks for two digits (\d{2}) followed by an underscore and then
    # captures everything till the end of the string.
    pattern = r'\d{2}_(.*)$'
    match = re.search(pattern, sample_name)
    if match:
        # Return the captured group
        return match.group(1)
    else:
        # Pattern did not match, return None to indicate no valid suffix was found.
        return None


def replace_nan(d1):
    """Return a nested dict with all pandas NaN values replaced by None.

    This makes a new *outer* dictionary and shallow-copies each inner-dict, replacing any value for which
    'pd.isna(value)' is True with Python 'None'. The original nested dicts in 'd1' are left unmodified.

    Args:
        d1: A dict mapping keys to inner dicts whose values may contain NaN.

    Returns:
        A new dict with the same keys as 'd1'. Each value is a new dict with all 'NaN' entries replaced by 'None'

    """
    o_dict = {}
    for k, v in d1.items():
        o_dict[k] = v.copy()
        for x, y in v.items():
            if pd.isna(y):
                o_dict[k][x] = None
    return o_dict


def complete_datetime(item_id, item_name, event, to_set, iteration, admin=False):
    # When complete is selected for EA, PA, BR

    # to_set = request.args.get('to_set')
    item = Batches.query.get(item_id)
    # event = 'UPDATED'

    new_value = datetime.now()
    status = 'Approved'
    test_revision = -1

    # Get the discipline of the assay
    discipline = item.assay.discipline

    # Dict with iteration as key, value = dict of 'to_set' as key and array of relevant strings as values
    change_dict = {
        1: {
            'extract': ['Extraction Finish Date', 'extraction_finish_date'],
            'process': ['Processing Finish Date', 'process_finish_date'],
            'review': ['Review Finish Date', 'review_finish_date']
        },
        2: {
            'extract': ['Extraction Finish Date 2', 'extraction_finish_date_2'],
            'process': ['Processing Finish Date 2', 'process_finish_date_2'],
            'review': ['Review Finish Date 2', 'review_finish_date_2']
        },
        3: {
            'extract': ['Extraction Finish Date 3', 'extraction_finish_date_3'],
            'process': ['Processing Finish Date 3', 'process_finish_date_3'],
            'review': ['Review Finish Date 3', 'review_finish_date_3']
        }
    }

    # Unpack change dict
    field, field_name = change_dict[iteration][to_set]

    # Get original value
    original_value = getattr(item, field_name)

    # Set field_name being changed with new_value
    setattr(item, field_name, new_value)

    # Check if br and set test statuses to finalized, update case status if ready
    if to_set == 'review':
        item.batch_status = 'Finalized'

        # Mark each test as finalized when batch is finalized
        for test in Tests.query.filter_by(batch_id=item_id).all():
            test_original_value = test.test_status
            test.test_status = 'Finalized'
            test_mod = Modifications.query.filter_by(record_id=test.id, table_name='Tests',
                                                     field_name='test_status').first()
            if test_mod:
                test_revision = int(test_mod.revision)

            test_revision += 1

            modification = Modifications(
                event=event,
                status=status,
                table_name='Tests',
                record_id=test.id,
                revision=test_revision,
                field='Test Status',
                field_name='test_status',
                original_value=test_original_value,
                original_value_text=str(test_original_value),
                new_value='Finalized',
                new_value_text='Finalized',
                submitted_by=current_user.id,
                submitted_date=datetime.now(),
                reviewed_by=current_user.id,
                review_date=datetime.now()
            )

            db.session.add(modification)

            # Get the case for the test
            case = test.case
            # Get the statuses of each test for that discipline in a case
            test_statuses = [x.test_status for x in
                             Tests.query.join(Assays).filter(
                                 and_(Tests.case_id == case.id, Tests.test_status != 'Cancelled',
                                      Assays.discipline == discipline))]
            # Check if all statuses are 'Finalized' we also need to check if the list is empty as it also returns True.
            # Set the discipline status to 'Drafting
            if test_statuses and all(x == 'Finalized' for x in test_statuses):
                if test_original_value != 'Finalized':
                    setattr(case, f"{discipline.lower()}_status", 'Ready for Drafting')

            db.session.commit()

    # Unlock batch
    item.locked = False
    item.locked_by = None
    item.lock_date = None

    # Create and add modification
    mod = Modifications.query.filter_by(record_id=str(item_id), table_name=item_name, field_name=field_name).first()

    # Initialize revision number to set to 0 if no revisions exist
    revision = -1

    if mod:
        revision = int(mod.revision)
    else:
        event = 'CREATED'

    revision += 1

    try:
        original_value = original_value.strftime("%m/%d/%Y")

    except AttributeError:
        original_value = str(original_value)

    try:
        new_value = new_value.strftime("%m/%d/%Y")
    except AttributeError:
        new_value = str(new_value)

    modification = Modifications(
        event=event,
        status=status,
        table_name=item_name,
        record_id=str(item.id),
        revision=revision,
        field=field,
        field_name=field_name,
        original_value=original_value,
        original_value_text=str(original_value),
        new_value=new_value,
        new_value_text=new_value,
        submitted_by=current_user.id,
        submitted_date=datetime.now(),
        reviewed_by=current_user.id,
        review_date=datetime.now()
    )

    db.session.add(modification)

    db.session.commit()
