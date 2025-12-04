import os

from docxtpl import DocxTemplate
from flask import send_file, redirect, url_for
from openpyxl.workbook import Workbook

from lims.models import *


def get_form_choices(form, case_id, test_id):

    cases = [(item.id, item.case_number) for item in Cases.query.filter(Cases.create_date > datetime(2025, 1, 1)).order_by(Cases.create_date.desc())]
    cases.insert(0, (0, 'Please select a case'))
    form.case_id.choices = cases

    units = [(item.id, item.name) for item in Units.query]
    units.insert(0, (0, 'Please select a unit'))
    form.unit_id.choices = units


    tests = []
    if case_id:
        form.case_id.data = case_id
        form.test_id.data = test_id

        tests = [(item.id, item.id) for item in Tests.query.filter_by(case_id=case_id).filter(Tests.test_status != "Pending").order_by(Tests.create_date.asc())]
    form.test_id.choices = tests

    components = [(item.id, item.name) for item in Components.query.order_by(Components.name.asc())]
    components.insert(0, (0, 'Please select a component'))
    form.component_id.choices = components

    return form


def get_test_choices(case_id):

    items_lst = []

    if case_id != 0:
        items = Tests.query.filter_by(case_id=case_id).filter(Tests.test_status != "Pending").order_by(Tests.create_date.asc())
    else:
        items = []

    if items.count():
        x = 0
        for item in items:
            x += 1
            if item.batch and item.batch.extraction_date:
                extraction_date = item.batch.extraction_date.strftime('%m/%d/%Y')
            else:
                extraction_date = ""
            dict = {}
            dict['items'] = [item.id,
                             item.assay.assay_name,
                             item.test_name,
                             item.assay.assay_name,
                             item.batch.batch_id,
                             extraction_date,
                             item.specimen.accession_number,
                             item.specimen.type.code,
                             item.dilution
                             ]

            items_lst.append(dict)

    print(items_lst)
    return {'tests': items_lst}


def get_components_and_results(test_id):

    in_scope_components = None
    in_scope_choices = []
    out_of_scope_components = None
    out_of_scope_choices = []
    results = None
    result_choices = []
    assay = ""
    if test_id:
        test = Tests.query.get(test_id)
        assay = test.assay.assay_name
        assay_id = test.assay_id
        scope_component_ids = [item.component_id for item in Scope.query.filter_by(assay_id=assay_id)]
        in_scope_components = Components.query.filter(Components.id.in_(scope_component_ids))
        out_of_scope_components = Components.query.filter(Components.id.notin_(scope_component_ids + [1]))
        results = Results.query.filter_by(test_id=test_id)

    if results and results.count():
        for result in results:
            result_dict = {key: value for key, value in result.__dict__.items() if not key.startswith('_')}

            # Ensure 'unit_id' is always a string
            result_dict['unit_id'] = str(result.unit.name) if result.unit else ""

            result_choices.append(result_dict)

    if in_scope_components.count():
        in_scope_choices = [{'id': item.id, 'name': item.name} for item in in_scope_components]

    if out_of_scope_components.count():
        out_of_scope_choices = [{'id': item.id, 'name': item.name} for item in out_of_scope_components]

    return {
        'assay': assay,
        'results': result_choices,
        'in_scope_choices': in_scope_choices,
        'out_of_scope_choices': out_of_scope_choices
    }


def print_alcohol_verbal(results):
    # doc = DocxTemplate(r"lims\static\alcohol_verbal\alcohol_verbal_template.docx")
    save_directory = r"D:\lims\code\lims\static\alcohol_verbal"

    print(f' Results from function = {results}')

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"{datetime.now().strftime('%Y%m%d')} Alcohol Verbal"

    headers = ["Case Number", "Batch ID", "Client (Agency)", "Case Ref. No", "First/Last Name", "Directive", "Component Name", "Result Status", "Result Type", "Result", "Supplementary Result"]
    sheet.append(headers)

    for r in results:
        row = [
            r.case.case_number,
            r.test.batch.batch_id,
            r.case.agency.name,
            r.case.submitter_case_reference_number if r.case.submitter_case_reference_number else '',
            f'{r.case.first_name} {r.case.last_name}',
            r.test.directives,
            r.component_name,
            r.result_status,
            r.result_type,
            r.result,
            r.supplementary_result
        ]
        sheet.append(row)

    excel_file_name = f"{datetime.now().strftime('%Y%m%d')} Alcohol Verbal.xlsx"
    excel_path = os.path.join(save_directory, excel_file_name)
    workbook.save(excel_path)

    print(f'excel path = {excel_path}')

