import re
import time
import shutil
import tempfile
import zipfile
import logging
from collections import defaultdict
from datetime import datetime
import os
import pythoncom
import docx2pdf
from docxtpl import DocxTemplate, RichText
from docx.enum.text import WD_BREAK
from docx.shared import Pt
import fitz
from flask import jsonify, send_file, current_app
from flask_login import current_user
from sqlalchemy import and_, or_

from lims import db
from lims.models import *
from lims.batches.functions import get_batch_checks
from lims import app
from datetime import datetime
from io import BytesIO
# from lims.pdf_redacting.functions import Redactor
import win32com.client
from win32com.client import gencache
import pikepdf


class Redactor:
    @staticmethod
    def get_sensitive_data(text, ignore_case_number=None, ignore_accession_numbers=None):
        """Get all strings matching sensitive data patterns."""
        patterns = [
            r"\b\d{4}-\d{4}\b",  # 0000-0000
            r"\bD-\d{5}\b",  # D-00000
            r"\bD[\-\u2010\u2011\u2012\u2013\u2014]\d{5}\b",
            r"\bM-\d{5}\b",  # M-00000
            r"\bX-\d{5}\b",  # X-00000
            r"\bN-\d{4}\b",  # N-0000
            r"\b[A-Z]\d{5}\b",  # A00000
            r"\bP-\d{5}\b",  # P-00000
            r"\bQ-\d{5}\b",  # Q-00000
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found_text = match.group(0)
                if ignore_case_number and ignore_case_number.upper() != "NA" and found_text == ignore_case_number:
                    continue
                elif ignore_accession_numbers and found_text in ignore_accession_numbers:
                    continue
                yield found_text

    def __init__(self, path, ignore_case_number=None, ignore_accession_numbers=None):
        self.path = path
        self.ignore_case_number = ignore_case_number
        self.ignore_accession_numbers = ignore_accession_numbers

    def redaction(self):
        # Normalize the PDF first (rewrites the structure)
        input_pdf = self.path
        # Save the normalized version to the same location (or you can choose a new filename)
        normalized_pdf = self.path

        with pikepdf.open(input_pdf, allow_overwriting_input=True) as pdf:
            pdf.save(normalized_pdf)

        doc = fitz.open(normalized_pdf)
        for page_num, page in enumerate(doc, start=1):
            text_blocks = page.get_text("blocks")
            if not text_blocks:
                print(f"No text found on page {page_num}")
                continue

            full_text = "\n".join(block[4] for block in text_blocks)

            # Identify sensitive data
            sensitive_data = list(
                self.get_sensitive_data(full_text, self.ignore_case_number, self.ignore_accession_numbers))
            for data in sensitive_data:
                areas = page.search_for(data)
                for area in areas:
                    redaction_rect = fitz.Rect(area)
                    page.add_redact_annot(redaction_rect, fill=(0, 0, 0))
            page.apply_redactions()

        # Save the redacted file (this returns a new file path)
        save_path = os.path.join(os.path.dirname(self.path), f"redacted_{os.path.basename(self.path)}")
        doc.save(save_path, deflate=True, clean=True, incremental=False)
        return save_path

# class Redactor:
#     @staticmethod
#     def get_sensitive_data(text, ignore_case_number=None):
#         """ Function to get all the lines with the sensitive data patterns """
#         patterns = [
#             r"\b\d{4}-\d{4}\b",            # 0000-0000
#             r"\bD-\d{5}\b",                # D-0000
#             r"\bM-\d{5}\b",                # M-00000
#             r"\bX-\d{4}\b",                # X-0000
#             r"\bN-\d{4}\b",                # N-0000
#             r"\bB-\d{4}\b",                # B-0000
#             r"\bB-\d{5}\b",                # B-00000
#             r"\bQ-\d{4}\b",                # Q-0000
#             r"\b\d{4}-\d{4}_[A-Z]\d\b",    # 0000-0000_L1
#             r"\bD-\d{4}_[A-Z]\d\b",        # D-0000_L1
#             r"\bM-\d{5}_[A-Z]\d\b",        # M-00000_L1
#             r"\bX-\d{4}_[A-Z]\d\b",        # X-0000_L1
#             r"\bN-\d{4}_[A-Z]\d\b",        # N-0000_L1
#             r"\bB-\d{4}_[A-Z]\d\b",        # B-0000_L1
#         ]
#         for pattern in patterns:
#             for match in re.finditer(pattern, text, re.IGNORECASE):
#                 found_text = match.group(0)
#                 if ignore_case_number and ignore_case_number.upper() != "NA" and found_text == ignore_case_number:
#                     continue
#                 yield found_text
#
#     def __init__(self, path, ignore_case_number=None):
#         self.path = path
#         self.ignore_case_number = ignore_case_number
#
#     def redaction(self):
#         """ Main redactor code """
#         doc = fitz.open(self.path)
#         print('IN REDACTION')
#
#         for page_num, page in enumerate(doc, start=1):
#             # print(f"Processing page {page_num} of {len(doc)}")
#             text_blocks = page.get_text("blocks")
#             if not text_blocks:
#                 print(f"No text found on page {page_num}")
#                 continue
#
#             full_text = ""
#             for block in text_blocks:
#                 full_text += block[4] + "\n"
#
#             # Identify sensitive data
#             sensitive = self.get_sensitive_data(full_text, self.ignore_case_number)
#             sensitive_data = list(sensitive)
#             # print(f"Sensitive data found on page {page_num}: {sensitive_data}")
#
#             for data in sensitive_data:
#                 areas = page.search_for(data)
#                 # print(f"Redacting data '{data}' found in areas: {areas}")
#
#                 for area in areas:
#                     # Add redaction annotation
#                     page.add_redact_annot(area, fill=(0, 0, 0))
#                     # print(f"Redaction added at {area}")
#
#             page.apply_redactions()
#             # print(f"Redactions applied on page {page_num}")
#
#         save_path = os.path.join(os.path.dirname(self.path), f"redacted_{os.path.basename(self.path)}")
#         doc.save(save_path)
#         # print(f"Successfully redacted and saved to {save_path}")
#         return save_path


def generate_pdf(item_id, case, docpath):
    doc = DocxTemplate(r"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Litigation Packet Templates\Litigation Packet Template.docx")

    file_name = f"{case.case_number}_case_contents"
    data = {}

    data['case_number'] = case.case_number
    data['name'] = f'{case.last_name}, {case.first_name} {case.middle_name}'
    data['case_status'] = case.case_status
    data['case_type_name'] = f'{case.type.name} ({case.type.code})'
    data['priority'] = case.priority
    data['sensitivity'] = case.sensitivity
    data['n_containers'] = case.n_containers
    data['ret_policy'] = case.retention.name
    data['discard_eligible'] = case.discard_eligible
    data['discard_date'] = case.discard_date
    if case.gender is not None:
        data['gender'] = case.gender.name
    else:
        data['gender'] = ""
    data['birth_sex'] = case.birth_sex
    if case.race is not None:
        data['race'] = case.race.name
    else:
        data['race'] = ""
    # data['race'] = case.race.name
    data['hispanic_ethnicity'] = case.hispanic_ethnicity
    data['date_of_birth'] = case.date_of_birth
    data['age'] = case.age
    data['age_status'] = case.age_status
    if case.date_of_incident is not None:
        data['date_time_of_inc'] = f'{case.date_of_incident} at {case.time_of_incident}'
    else:
        data['date_time_of_inc'] = "None"
    data['agency'] = case.agency.name
    data['submitter_case_reference_number_1'] = case.submitter_case_reference_number
    data['alternate_case_reference_number_1'] = case.alternate_case_reference_number_1
    data['alternate_case_reference_number_2'] = case.alternate_case_reference_number_2
    data['notes'] = case.notes
    data['tox_requested'] = case.toxicology_requested
    data['tox_performed'] = case.toxicology_performed
    data['tox_status'] = case.toxicology_status
    data['t_s_d'] = case.toxicology_start_date
    data['diss_d'] = ""
    data['dss_tat_tox'] = ""
    data['bio_requested'] = case.biochemistry_requested
    data['bio_performed'] = case.biochemistry_performed
    data['bio_status'] = case.biochemistry_status
    data['hist_requested'] = case.histology_requested
    data['hist_performed'] = case.histology_performed
    data['hist_status'] = case.histology_status
    data['ext_requested'] = case.external_requested
    data['ext_performed'] = case.external_performed
    data['ext_status'] = case.external_status
    if hasattr(case, 'testing_notes') and case.testing_notes is not None:
        data['testing_notes'] = case.testing_notes
    else:
        data['testing_notes'] = ""
    data['item_medical_record'] = case.medical_record
    if case.home_address is None:
        data['item_home_address'] = ""
    else:
        data['item_home_address'] = case.home_address
    data['item_home_zip'] = case.home_zip
    data['item_death_address'] = f'{case.death_address} {case.death_zip} ({case.latitude}, {case.longitude})'
    data['item_death_premise'] = case.death_premises
    data['item_fa_case_comments'] = case.fa_case_comments
    data['item_fa_case_stage'] = case.fa_case_stage
    if case.fa_case_entry_date is not None:
        data['fa_case_entry_date'] = case.fa_case_entry_date
    else:
        data['fa_case_entry_date'] = ""
    data['item_exam_status'] = case.exam_status

    data['autopsy_date'] = f'{case.autopsy_type} - {case.autopsy_date}'
    data['item_manner_of_death'] = case.manner_of_death
    data['item_cod_a'] = case.cod_a
    data['item_cod_b'] = case.cod_b
    data['item_cod_c'] = case.cod_c
    data['item_other_conditions'] = case.other_conditions
    data['item_method_of_death'] = case.method_of_death
    if case.pathologist is not None:
        data['item_pathologist_full_name'] = case.pathologist.full_name
    else:
        data['item_pathologist_full_name'] = ""
    if case.primary_investigator:
        data['item_investigator_full_name'] = case.investigator.full_name
    else:
        data['item_investigator_full_name'] = ""
    data['item_cert_status'] = case.cert_status
    data['item_short_narrative'] = case.short_narrative
    if case.investigators_report is not None:
        data['item_investigators_report'] = case.investigators_report
    else:
        data['item_investigators_report'] = ""

    containers = Containers.query.filter_by(case_id=case.id).order_by(Containers.create_date.asc())
    data['containers'] = []

    for cont in containers:
        container = {}
        container['cont_accession_num'] = cont.accession_number
        container['type_code_cont'] = f'[#{cont.type.code}#]'
        container['spec_acc_rec'] = f'{cont.n_specimens} / {cont.n_specimens_submitted}'
        container_number = 0
        container['container_num'] = container_number + 1
        if cont.submitter is not None:
            container['submitted_by'] = cont.submitter.full_name
        else:
            container['submitted_by'] = ''
        container['evidence_receipt_comments'] = cont.evidence_comments
        container['submission_date_time'] = f'{cont.submission_date} {cont.submission_time}'
        container['submission_route_type'] = cont.submission_route_type
        if cont.storage is not None:
            container['submission_route'] = cont.storage.name
        else:
            container['submission_route'] = ''
        container['container_spec_notes'] = cont.notes

        container['specimens'] = []
        num_specimen = 0
        for spec in Specimens.query.filter_by(case_id=case.id, container_id=cont.id):
            num_specimen = num_specimen + 1
            specimen = {}
            specimen['spec_accession_num'] = spec.accession_number
            specimen['spec_type_code'] = f'[{spec.type.code}]'
            specimen['custody'] = spec.custody
            specimen['evidence_receipt_comments_spec’'] = spec.evidence_comments
            specimen['submission_date_time_spec'] = f'{spec.collection_date} {spec.collection_time}'
            specimen['collection_site'] = spec.specimen_site
            specimen['collection_container'] = spec.collection_container
            specimen['current_submitted_amount'] = f'{spec.current_sample_amount} / {spec.submitted_sample_amount}'
            specimen['condition'] = spec.condition
            specimen['spec_notes'] = spec.notes
            specimen['specimen_num'] = num_specimen

            container['specimens'].append(specimen) # appending specimen dictionary to container ['specimens'] array
        data['containers'].append(container)
    results_ = Results.query.filter_by(case_id=case.id)
    data['tests'] = []
    item = Cases.query.get_or_404(item_id)
    # results = db.session.query(Results).filter(Results.case_id == item.id)
    tests = (
        db.session.query(Tests)
        .filter(Tests.case_id == case.id)
        .join(Assays, Assays.id == Tests.assay_id)         # assumes Assays model/table exists
        .options(
            joinedload(Tests.assay),                        # so t.assay.assay_name is loaded
            joinedload(Tests.batch),
            joinedload(Tests.specimen).joinedload(Specimens.type),
        )
        .order_by(asc(Assays.assay_name), asc(Tests.test_name))   # key line
        .all()
)
    for t in tests:
        test = {}
        test['tests_assay'] = t.assay.assay_name
        test['tests_batch_id'] = t.batch_id
        if t.batch is not None:
            test['tests_batch_date'] = t.batch.extraction_date
        else:
            test['tests_batch_date'] = ''
        test['tests_name'] = t.test_name
        test['tests_status'] = t.test_status
        test['tests_specimen_accession_number'] = t.specimen.accession_number
        test['tests_specimen_type'] = f'[{t.specimen.type.code}]'
        test['tests_dilution'] = t.dilution
        test['testresults'] = []
        for r in Results.query.filter_by(case_id=case.id, test_id=t.id):
            result = {}
            result['result_status'] = r.result_status
            result['result_component_name'] = r.component.name
            result['result_name'] = r.result
            result['supp_result'] = r.supplementary_result
            result['result_concentration'] = r.concentration
            result['result_qualitative'] = r.qualitative
            result['result_type'] = r.result_type
            result['result_notes_tests'] = r.notes
            result['outlier_reason'] = r.report_reason
            result['qualitative_reason'] = r.qualitative_reason
            test['testresults'].append(result)
        data['tests'].append(test)

    data['results'] = []
    for r in results_:
        result = {}
        result['results_assay'] = r.test.assay.assay_name
        if r.test.batch is not None:
            result['results_batch'] = r.test.batch.batch_id
        else:
            result['results_batch'] = ''
        if r.test.batch is not None:
            result['results_batch_date'] = r.test.batch.extraction_date
        else:
            result['results_batch_date'] = ''
        result['results_test'] = r.test.test_name
        result['results_component_name'] = r.component.name
        result['result'] = r.result
        result['results_supplementary_result'] = r.supplementary_result
        result['results_concentration'] = r.concentration
        result['results_comments'] = r.notes


        data['results'].append(result)
    records = Records.query.filter_by(case_id=case.id)
    data['records'] = []
    for rec in records:
        record = {}
        record['record_name'] = rec.record_name
        record['record_status'] = rec.record_status
        record['record_type'] = rec.record_type
        record['record_number'] = rec.record_number
        record['dissemination_date'] = rec.dissemination_date
        record['disseminated_by'] = rec.disseminated_by
        record['disseminated_to'] = rec.disseminated_to
        record['record_comments'] = rec.general_comments
        record['date_record_created'] = rec.create_date
        record['record_created_by'] = rec.created_by
        record['record_date_modified'] = rec.modify_date
        record['record_modified_by'] = rec.modified_by

        data['records'].append(record)

    def get_unique_file_name(directory, file_name, extension):
        counter = 1
        unique_file_name = f"{file_name}.{extension}"
        while os.path.exists(os.path.join(directory, unique_file_name)):
            unique_file_name = f"{file_name} ({counter}).{extension}"
            counter += 1
        return unique_file_name

    save_directory = r"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Litigation Packet Templates"
    base_file_name = f"{case.case_number}_case_contents"
    docx_file_name = get_unique_file_name(save_directory, base_file_name, "docx")
    pdf_file_name = get_unique_file_name(save_directory, base_file_name, "pdf")

    docx_path = os.path.join(save_directory, docx_file_name)
    pdf_path = os.path.join(save_directory, pdf_file_name)

    doc.render(data, autoescape=True)
    doc.save(docx_path)

    pythoncom.CoInitialize()
    docx2pdf.convert(docx_path, pdf_path)


def generate_pdf_lit(item_id, docpath, temp_dir):
    doc = DocxTemplate(docpath)
    case = Cases.query.get_or_404(item_id)

    file_name = f"{case.case_number}_case_contents"
    data = {}

    data['case_number'] = case.case_number
    data['name'] = f'{case.last_name}, {case.first_name} {case.middle_name}'
    data['case_status'] = case.case_status
    data['case_type_name'] = f'{case.type.name} ({case.type.code})'
    data['priority'] = case.priority
    data['sensitivity'] = case.sensitivity
    data['n_containers'] = case.n_containers
    data['ret_policy'] = case.retention.name
    data['discard_eligible'] = case.discard_eligible
    data['discard_date'] = case.discard_date
    if case.gender is not None:
        data['gender'] = case.gender.name
    else:
        data['gender'] = ""
    data['birth_sex'] = case.birth_sex
    if case.race is not None:
        data['race'] = case.race.name
    else:
        data['race'] = ""
    # data['race'] = case.race.name
    data['hispanic_ethnicity'] = case.hispanic_ethnicity
    data['date_of_birth'] = case.date_of_birth
    data['age'] = case.age
    data['age_status'] = case.age_status
    if case.date_of_incident is not None:
        data['date_time_of_inc'] = f'{case.date_of_incident} at {case.time_of_incident}'
    else:
        data['date_time_of_inc'] = "None"
    data['agency'] = case.agency.name
    data['submitter_case_reference_number_1'] = case.submitter_case_reference_number
    data['alternate_case_reference_number_1'] = case.alternate_case_reference_number_1
    data['alternate_case_reference_number_2'] = case.alternate_case_reference_number_2
    data['notes'] = case.notes
    data['tox_requested'] = case.toxicology_requested
    data['tox_performed'] = case.toxicology_performed
    data['tox_status'] = case.toxicology_status
    data['t_s_d'] = case.toxicology_start_date
    data['diss_d'] = ""
    data['dss_tat_tox'] = ""
    data['bio_requested'] = case.biochemistry_requested
    data['bio_performed'] = case.biochemistry_performed
    data['bio_status'] = case.biochemistry_status
    data['hist_requested'] = case.histology_requested
    data['hist_performed'] = case.histology_performed
    data['hist_status'] = case.histology_status
    data['ext_requested'] = case.external_requested
    data['ext_performed'] = case.external_performed
    data['ext_status'] = case.external_status
    if hasattr(case, 'testing_notes') and case.testing_notes is not None:
        data['testing_notes'] = case.testing_notes
    else:
        data['testing_notes'] = ""
    data['item_medical_record'] = case.medical_record
    if case.home_address is None:
        data['item_home_address'] = ""
    else:
        data['item_home_address'] = case.home_address
    data['item_home_zip'] = case.home_zip
    data['item_death_address'] = f'{case.death_address} {case.death_zip} ({case.latitude}, {case.longitude})'
    data['item_death_premise'] = case.death_premises
    data['item_fa_case_comments'] = case.fa_case_comments
    data['item_fa_case_stage'] = case.fa_case_stage
    if case.fa_case_entry_date is not None:
        data['fa_case_entry_date'] = case.fa_case_entry_date
    else:
        data['fa_case_entry_date'] = ""
    data['item_exam_status'] = case.exam_status

    data['autopsy_date'] = f'{case.autopsy_type} - {case.autopsy_date}'
    data['item_manner_of_death'] = case.manner_of_death
    data['item_cod_a'] = case.cod_a
    data['item_cod_b'] = case.cod_b
    data['item_cod_c'] = case.cod_c
    data['item_other_conditions'] = case.other_conditions
    data['item_method_of_death'] = case.method_of_death
    if case.pathologist is not None:
        data['item_pathologist_full_name'] = case.pathologist.full_name
    else:
        data['item_pathologist_full_name'] = ""
    if case.primary_investigator:
        data['item_investigator_full_name'] = case.investigator.full_name
    else:
        data['item_investigator_full_name'] = ""
    data['item_cert_status'] = case.cert_status
    data['item_short_narrative'] = case.short_narrative
    if case.investigators_report is not None:
        data['item_investigators_report'] = case.investigators_report
    else:
        data['item_investigators_report'] = ""

    containers = Containers.query.filter_by(case_id=case.id).order_by(Containers.create_date.asc())
    data['containers'] = []
    # Looping to grab each container, then looping to grab each specimen within that container, then looping once more to obtain the chain of custody per specimen
    for cont in containers:
        container = {}
        container['cont_accession_num'] = cont.accession_number
        container['type_code_cont'] = f'[#{cont.type.code}#]'
        container['spec_acc_rec'] = f'{cont.n_specimens} / {cont.n_specimens_submitted}'
        container_number = 0
        container['container_num'] = container_number + 1
        if cont.submitter is not None:
            container['submitted_by'] = cont.submitter.full_name
        else:
            container['submitted_by'] = ''
        container['evidence_receipt_comments'] = cont.evidence_comments
        container['submission_date_time'] = f'{cont.submission_date} {cont.submission_time}'
        container['submission_route_type'] = cont.submission_route_type
        if cont.storage is not None:
            container['submission_route'] = cont.storage.name
        else:
            container['submission_route'] = ''
        container['container_spec_notes'] = cont.notes

        container['specimens'] = []
        num_specimen = 0
        for spec in Specimens.query.filter_by(case_id=case.id, container_id=cont.id):
            num_specimen = num_specimen + 1
            specimen = {}
            specimen['spec_accession_num'] = spec.accession_number
            specimen['spec_type_code'] = f'[{spec.type.code}]'
            specimen['custody'] = spec.custody
            specimen['evidence_receipt_comments_spec’'] = spec.evidence_comments
            specimen['submission_date_time_spec'] = f'{spec.collection_date} {spec.collection_time}'
            specimen['collection_site'] = spec.specimen_site
            specimen['collection_container'] = spec.collection_container
            specimen['current_submitted_amount'] = f'{spec.current_sample_amount} / {spec.submitted_sample_amount}'
            specimen['condition'] = spec.condition
            specimen['spec_notes'] = spec.notes
            specimen['specimen_num'] = num_specimen
            specimen['specimen_audit'] = []
            container['specimens'].append(specimen) # appending specimen dictionary to container ['specimens'] array
            custody_order = 0
            for c in SpecimenAudit.query.filter_by(specimen_id=spec.id):
                custodychain = {}
                custody_order = custody_order + 1
                # custody['cust-id'] = c.id - something like this
                custodychain['cust-id'] = custody_order
                custodychain['custody_audit'] = c.destination
                custodychain['reason'] = c.reason
                custodychain['cust-date-time'] = c.o_time.strftime('%Y-%m-%d %H:%M') if c.o_time else 'N/A'

                specimen['specimen_audit'].append(custodychain)
        data['containers'].append(container)
    results_ = Results.query.filter_by(case_id=case.id)
    data['tests'] = []
    item = Cases.query.get_or_404(item_id)
    # results = db.session.query(Results).filter(Results.case_id == item.id)
    tests = Tests.query.filter_by(case_id=case.id)
    for t in tests:
        test = {}
        test['tests_assay'] = t.assay.assay_name
        test['tests_batch_id'] = t.batch_id
        if t.batch is not None:
            test['tests_batch_date'] = t.batch.extraction_date
        else:
            test['tests_batch_date'] = ''
        test['tests_name'] = t.test_name
        test['tests_status'] = t.test_status
        test['tests_specimen_accession_number'] = t.specimen.accession_number
        test['tests_specimen_type'] = f'[{t.specimen.type.code}]'
        test['tests_dilution'] = t.dilution
        test['testresults'] = []
        for r in Results.query.filter_by(case_id=case.id, test_id=t.id):
            result = {}
            result['result_status'] = r.result_status
            result['result_component_name'] = r.component.name
            result['result_name'] = r.result
            result['supp_result'] = r.supplementary_result
            result['result_concentration'] = r.concentration
            result['result_qualitative'] = r.qualitative
            result['result_type'] = r.result_type
            result['result_notes_tests'] = r.notes
            result['outlier_reason'] = r.report_reason
            result['qualitative_reason'] = r.qualitative_reason
            test['testresults'].append(result)
            # for c in db.session.query(SpecimenAudit).filter_by(specimen_id=item_id).order_by(SpecimenAudit.o_time.desc()):
        data['tests'].append(test)

    data['results'] = []
    for r in results_:
        result = {}
        result['results_assay'] = r.test.assay.assay_name
        if r.test.batch is not None:
            result['results_batch'] = r.test.batch.batch_id
        else:
            result['results_batch'] = ''
        if r.test.batch is not None:
            result['results_batch_date'] = r.test.batch.extraction_date
        else:
            result['results_batch_date'] = ''
        result['results_test'] = r.test.test_name
        result['results_component_name'] = r.component.name
        result['result'] = r.result
        result['results_supplementary_result'] = r.supplementary_result
        result['results_concentration'] = r.concentration
        result['results_comments'] = r.notes


        data['results'].append(result)
    records = Records.query.filter_by(case_id=case.id)
    data['records'] = []
    for rec in records:
        record = {}
        record['record_name'] = rec.record_name
        record['record_status'] = rec.record_status
        record['record_type'] = rec.record_type
        record['record_number'] = rec.record_number
        record['dissemination_date'] = rec.dissemination_date
        record['disseminated_by'] = rec.disseminated_by
        record['disseminated_to'] = rec.disseminated_to
        record['record_comments'] = rec.general_comments
        record['date_record_created'] = rec.create_date
        record['record_created_by'] = rec.created_by
        record['record_date_modified'] = rec.modify_date
        record['record_modified_by'] = rec.modified_by

        data['records'].append(record)
    reports = Reports.query.filter_by(case_id=case.id)
    data['reports'] = []
    for r in reports:
        report = {}
        report['report_name'] = r.report_name
        report['report_case_number'] = r.case.case_number
        report['report_discipline'] = r.discipline
        report['report_number'] = r.report_number
        report['draft_number'] = r.draft_number
        # verify this is correct - backend shows report_status front end shows draft_status
        report['report_draft_status'] = r.report_status
        report['report_cr'] = r.case_review
        report['report_cr_date'] = r.case_review_date
        report['report_dr'] = r.divisional_review
        report['report_dr_date'] = r.divisional_review_date
        report['record'] = r.record_id
        report['report_date_created'] = r.create_date.strftime('%H:%M:%S')
        report['report_created_by'] = r.created_by
        report['report_date_modified'] = r.modify_date
        data['reports'].append(report)

    docx_path = os.path.join(temp_dir, f"{file_name}.docx")
    pdf_path = os.path.join(temp_dir, f"{file_name}.pdf")

    doc.render(data, autoescape=True)
    doc.save(docx_path)

    pythoncom.CoInitialize()
    docx2pdf.convert(docx_path, pdf_path)

    return docx_path, pdf_path
#
# def generate_batches(item_id, temp_dir):
#     doc_template_path = r"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Litigation Packet Templates\batch pdf template V4.docx"
#
#     batch_ids = set()  # This will filter for batch ids that are duplicated when looping
#     batch_data = []  # a list to store all the batch data
#     tests = Tests.query.filter_by(case_id=item_id)
#
#     for test in tests:
#         if test.batch_id:
#             batch_ids.add(test.batch_id)
#
#     for batch_id in batch_ids:
#         batch = Batches.query.filter_by(id=batch_id).first()
#         if batch:
#             batch_info = {
#                 "name": batch.batch_id,
#                 "status": batch.batch_status,
#                 "assay": batch.assay.assay_name,
#                 "test_count": batch.test_count,
#                 "batch_template": batch.batch_template.name if batch.batch_template is not None else "",
#                 "instrument": batch.instrument.instrument_id if batch.instrument is not None else "",
#                 "instrument_two": batch.instrument_2.instrument_id if batch.instrument_2 is not None else "",
#                 "technique": batch.technique,
#                 "tandem_batch": [tandem.tandem_id for tandem in batch.tandem_id] if batch.tandem_id is not None else "",
#                 "extracting_analyst": batch.extractor.initials if batch.extractor is not None else "",
#                 "extraction_date": batch.extraction_date,
#                 "check_date": batch.checked_date,
#                 "process_date": batch.process_date,
#                 "tests": [],
#                 "checks": [],
#                 "constituents": [],
#                 "reagents": []
#             }
#             batch_data.append(batch_info)
#
#             batches = BatchConstituents.query.filter_by(batch_id=batch_id)
#             for constituent in batches:
#                 constituent_info = {}
#                 if constituent.constituent is not None:
#                     constituent_info['prepared_s_r_name'] = constituent.constituent.lot
#                     constituent_info['stand_and_solution'] = constituent.constituent.constituent.name
#                     constituent_info['in_use'] = constituent.constituent.in_use
#                     if constituent.constituent.retest_date is not None:
#                         constituent_info['s_r_expiration_date'] = constituent.constituent.retest_date.strftime('%H:%M') if constituent.constituent.retest_date else ''
#                     else:
#                         constituent_info['s_r_expiration_date'] = ""
#                     if constituent.specimen_checker is not None:
#                         constituent_info['spec_check_by'] = constituent.specimen_checker.initials
#                     else:
#                         constituent_info['spec_check_by'] = ""
#                     if constituent.sequence_checker is not None:
#                         constituent_info['seq_check_by'] = constituent.sequence_checker.initials
#                     else:
#                         constituent_info['seq_check_by'] = ""
#                     constituent_info['spec_check_date'] = constituent.specimen_check_date.strftime('%H:%M') if constituent.specimen_check_date else ''
#                     if constituent.transfer_check is not None:
#                         constituent_info['transfer_check'] = constituent.transfer_check
#                     else:
#                         constituent_info['transfer_check'] = ""
#                     if constituent.transfer_checker is not None:
#                         constituent_info['transfer_check_by'] = constituent.transfer_checker.initials
#                     else:
#                         constituent_info['transfer_check_by'] = ""
#                     constituent_info['transfer_check_date'] = constituent.transfer_check_date.strftime('%H:%M') if constituent.transfer_check_date else ''
#                     if constituent.sequence_check:
#                         constituent_info['seq_check_status'] = constituent.sequence_check
#                     else:
#                         constituent_info['seq_check_status'] = ""
#                     if constituent.sequence_checker is not None:
#                         constituent_info['seq_check_by'] = constituent.sequence_checker.initials
#                     else:
#                         constituent_info['seq_check_by'] = ""
#                     constituent_info['seq_check_date_time'] = constituent.sequence_check_date.strftime('%H:%M') if constituent.sequence_check_date else ''
#                 batch_info['constituents'].append(constituent_info)
#
#             for reagent in batches:
#                 reagent_info = {}
#                 if reagent.reagent is not None:
#                     reagent_info['purchased_s_r_name'] = reagent.reagent.name
#                     reagent_info['s_r_lot'] = reagent.reagent.lot
#                     reagent_info['s_r_manufacturer'] = reagent.reagent.manufacturer
#                     reagent_info['s_r_expiration_date'] = reagent.reagent.exp_date.strftime('%H:%M') if reagent.reagent.exp_date else ''
#                     if reagent.specimen_checker is not None:
#                         reagent_info['purchased_spec_check_by'] = reagent.specimen_checker.initials
#                     else:
#                         reagent_info['purchased_spec_check_by'] = ""
#                     reagent_info['purchased_spec_check_date'] = reagent.specimen_check_date.strftime('%H:%M') if reagent.specimen_check_date else ''
#
#                 batch_info['reagents'].append(reagent_info)
#
#             test_loop_num = 0
#             for t in Tests.query.filter_by(batch_id=batch_id):
#                 test_loop_num += 1
#                 test_info = {
#                     "test_num": test_loop_num,
#                     "test_status": t.test_status,
#                     "test_name": t.test_name,
#                     "test_id": t.test_id,
#                     "dilution": t.dilution,
#                     "case_dist": t.case.case_distinguisher,
#                     "case_id": t.case_id
#                 }
#                 batch_info['tests'].append(test_info)
#
#             checks = Tests.query.filter_by(batch_id=batch_id)
#             check_loop_num = 0
#             for check in checks:
#                 check_loop_num += 1
#                 check_info = {
#                     "check_num": check_loop_num,
#                     "check_test_id": check.test_name,
#                     "spec_checked_by": check.specimen_checker.initials if check.specimen_checker else '',
#                     "spec_check_date_time": check.checked_date.strftime('%Y-%m-%d %H:%M') if check.checked_date else '',
#                     "hamilton_load_check": check.load_check if check.load_check is not None else '',
#                     "hamilton_load_checked_by": check.load_checker.initials if check.load_checker else '',
#                     "hamilton_load_check_date_time": check.load_checked_date.strftime('%Y-%m-%d %H:%M') if check.load_checked_date else '',
#                     "transfer_check_status": check.transfer_check if check.transfer_check is not None else '',
#                     "transfer_checked_by": check.transfer_checker.initials if check.transfer_checker else '',
#                     "transfer_checked_date_time": check.transfer_checked_date.strftime('%Y-%m-%d %H:%M') if check.transfer_checked_date else '',
#                     "seq_check_status": check.sequence_check if check.sequence_check is not None else '',
#                     "seq_checked_by": check.sequence_checker.initials if check.sequence_checker else '',
#                     "seq_check_date_time": check.sequence_check_date.strftime('%Y-%m-%d %H:%M') if check.sequence_check_date else '',
#                 }
#                 batch_info['checks'].append(check_info)
#
#     data = {
#         "batches": batch_data,
#         "case_id": item_id
#     }
#
#     def get_unique_file_name(directory, file_name, extension):
#         counter = 1
#         unique_file_name = f"{file_name}.{extension}"
#         while os.path.exists(os.path.join(directory, unique_file_name)):
#             unique_file_name = f"{file_name} ({counter}).{extension}"
#             counter += 1
#         return unique_file_name
#
#     case = Cases.query.get_or_404(item_id)
#     save_directory = r"F:\ForensicLab\LIMS\LIMS Modules\1. Case Management\Litigation Packet Templates"
#     base_file_name = f"{case.case_number}_Batches"
#     docx_file_name = get_unique_file_name(save_directory, base_file_name, "docx")
#     pdf_file_name = get_unique_file_name(save_directory, base_file_name, "pdf")
#
#     docx_path = os.path.join(save_directory, docx_file_name)
#     pdf_path = os.path.join(save_directory, pdf_file_name)
#
#     # Create a temporary directory
#     docx_path = os.path.join(temp_dir, f"{case.case_number}_Batches.docx")
#     pdf_path = os.path.join(temp_dir, f"{case.case_number}_Batches.pdf")
#
#     doc = DocxTemplate(doc_template_path)
#     doc.render(data, autoescape=True)
#     doc.save(docx_path)
#
#     pythoncom.CoInitialize()
#     docx2pdf.convert(docx_path, pdf_path)
#
#     return docx_path, pdf_path
#

# def create_combined_zip(item_id, docpath, case, static_folder, redact):
#     batch_ids = set()  # This will filter for batch ids that are duplicated when looping
#     tests = Tests.query.filter_by(case_id=item_id)
#     batch_record_path = None
#     attachment_path = None
#     for test in tests:
#         if test.batch_id:
#             batch_ids.add(test.batch_id)
#
#     for batch_id in batch_ids:
#         for b in BatchRecords.query.filter_by(batch_id=batch_id):
#             if b.file_path.endswith('.pdf'):
#                 batch_record_path = b.file_path
#
#     for attachment in Attachments.query.filter_by(table_name='Cases', record_id=item_id):
#         if attachment.path.endswith('.pdf'):
#             attachment_path = attachment.path
#
#     # for record in Records.query.filter_by(case_id=item_id):
#
#     with tempfile.TemporaryDirectory() as tmpdirname:
#         # Generate both PDF and DOCX files
#         logging.debug(f"Generating litigation packet for case {item_id}")
#         lit_docx_path, lit_pdf_path = generate_pdf_lit(item_id, docpath, tmpdirname)
#
#         logging.debug(f"Generating batch documents for case {item_id}")
#         batch_docx_path, batch_pdf_path = generate_batches(item_id, tmpdirname)
#
#         # Create the ZIP file
#         zip_filename = f"{case.case_number}_Documents.zip"
#         zip_filepath = os.path.join(static_folder, zip_filename)  # Save to static folder
#
#         logging.debug(f"Creating ZIP file at {zip_filepath}")
#         with zipfile.ZipFile(zip_filepath, 'w') as zipf:
#             zipf.write(lit_docx_path, os.path.basename(lit_docx_path))
#             zipf.write(lit_pdf_path, os.path.basename(lit_pdf_path))
#             zipf.write(batch_docx_path, os.path.basename(batch_docx_path))
#             zipf.write(batch_pdf_path, os.path.basename(batch_pdf_path))
#             if batch_record_path is not None:
#                 zipf.write(batch_record_path, os.path.basename(batch_record_path))
#             if attachment_path is not None:
#                 zipf.write(attachment_path, os.path.basename(attachment_path))
#
#     if redact is True:
#         # logic for making the zip file be redacted
#         print()
#     else:
#         print()
#         # return what is already being returned(zip_filepath)
#     logging.debug(f"ZIP file created at {zip_filepath}")
#     return zip_filepath  # Return path to ZIP file


def create_combined_zip(item_id, docpath, case, static_folder, redact):
    batch_ids = set()  # This will filter for batch ids that are duplicated when looping
    tests = Tests.query.filter_by(case_id=item_id)
    batch_record_path = None
    attachment_path = None
    for test in tests:
        if test.batch_id:
            batch_ids.add(test.batch_id)

    for batch_id in batch_ids:
        for b in BatchRecords.query.filter_by(batch_id=batch_id):
            if b.file_path.endswith('.pdf'):
                batch_record_path = b.file_path

    for attachment in Attachments.query.filter_by(table_name='Cases', record_id=str(item_id)):
        if attachment.path.endswith('.pdf'):
            attachment_path = attachment.path

    # for record in Records.query.filter_by(case_id=item_id):

    with tempfile.TemporaryDirectory() as tmpdirname:
        # Generate both PDF and DOCX files
        logging.debug(f"Generating litigation packet for case {item_id}")
        lit_docx_path, lit_pdf_path = generate_pdf_lit(item_id, docpath, tmpdirname)

        logging.debug(f"Generating batch documents for case {item_id}")
        batch_docx_path, batch_pdf_path = generate_batches(item_id, tmpdirname)

        # Create the ZIP file
        zip_filename = f"{case.case_number}_Documents.zip"
        zip_filepath = os.path.join(static_folder, zip_filename)  # Save to static folder

        logging.debug(f"Creating ZIP file at {zip_filepath}")
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            zipf.write(lit_docx_path, os.path.basename(lit_docx_path))
            zipf.write(lit_pdf_path, os.path.basename(lit_pdf_path))
            zipf.write(batch_docx_path, os.path.basename(batch_docx_path))
            zipf.write(batch_pdf_path, os.path.basename(batch_pdf_path))
            if batch_record_path is not None:
                zipf.write(batch_record_path, os.path.basename(batch_record_path))
            if attachment_path is not None:
                zipf.write(attachment_path, os.path.basename(attachment_path))

    if redact:
        with tempfile.TemporaryDirectory() as redacted_tmpdirname:
            # Extract the original zip file
            with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                zip_ref.extractall(redacted_tmpdirname)

            # Find all PDFs in the extracted folder
            pdf_files = [os.path.join(redacted_tmpdirname, f) for f in os.listdir(redacted_tmpdirname) if
                         f.endswith('.pdf')]

            # Redact all PDFs
            # redacted_paths = redact_multiple_pdfs(pdf_files, ignore_case_number=case.case_number)

            # Create a new ZIP file with redacted PDFspython
            redacted_zip_filename = f"{case.case_number}_Redacted_Documents.zip"
            redacted_zip_filepath = os.path.join(static_folder, redacted_zip_filename)

            with zipfile.ZipFile(redacted_zip_filepath, 'w') as zipf:
                # for redacted_path in redacted_paths:
                #     zipf.write(redacted_path, os.path.basename(redacted_path))
                for file_path in os.listdir(redacted_tmpdirname):
                    if not file_path.endswith('.pdf'):
                        zipf.write(os.path.join(redacted_tmpdirname, file_path), file_path)

        logging.debug(f"Redacted ZIP file created at {redacted_zip_filepath}")
        return redacted_zip_filepath
    else:
        logging.debug(f"ZIP file created at {zip_filepath}")
        return zip_filepath  # Return path to ZIP file


def generate_pdf_lit_two(case_id, redact, packet_name):
    """
    Generates desired packet. Results in a popup with download option and saves a packet in
    static/filesystem/litigation_packets

    Args:
        case_id (int): The id of the case having a lit packet generated
        redact (bool): Whether the packet should be redacted or not
        packet_name (str): Name of the packet

    Returns:

    """
    # THIS IS ACTUALLY USED
    case = Cases.query.get_or_404(case_id)
    pm_case = CaseTypes.query.filter_by(code='PM').first().id
    is_pm = False

    if case.case_type == pm_case:
        template_path = os.path.join(current_app.root_path, 'static/litigation_packet_templates', 
                                     'Litigation Packet Template_pm.docx')
        is_pm = True
    else:
        template_path = os.path.join(current_app.root_path, 'static/litigation_packet_templates', 
                                     'Litigation Packet Template_hp.docx')

    # template_path = os.path.join(current_app.root_path, 'static/litigation_packet_templates', 
    #                              'Litigation Packet Template.docx')
    doc = DocxTemplate(template_path)
    # doc = doc_path
    file_name = f"{case.case_number}_case_contents"
    narratives = {narrative.narrative_type: f'{narrative.narrative} \n{f"- Reviewed by {narrative.modified_by}" if narrative.modified_by is not None else ""} '
                  f'{narrative.modify_date.strftime("%m/%d/%Y") if narrative.modify_date is not None else ""}' for narrative in
                  Narratives.query.filter_by(case_id=case_id).all() if narrative is not None}

    data = {}

    accession_numbers = []
    packet = LitigationPackets.query.filter_by(packet_name=packet_name).first()

    # Get case type
    if case.type.name == 'Postmortem':
        data['case_type'] = 'PM'
    else:
        data['case_type'] = 'HP'

    # Set case data
    data['case_number'] = case.case_number
    data['name'] = f'{case.last_name}, {case.first_name} {case.middle_name if case.middle_name is not None else ""}'
    data['create_date'] = packet.create_date.strftime("%m/%d/%Y")
    data['packet_name'] = packet_name
    data['case_status'] = case.case_status
    data['case_type_name'] = f'{case.type.name} ({case.type.code})'
    data['priority'] = case.priority
    data['sensitivity'] = case.sensitivity
    data['n_containers'] = case.n_containers
    data['ret_policy'] = case.retention.name
    data['discard_eligible'] = case.discard_eligible
    if case.discard_date:
        data['discard_date'] = case.discard_date.strftime('%Y-%m-%d')
    else:
        data['discard_date'] = '-'
    data['gender'] = case.gender.name if case.gender else "-"
    data['birth_sex'] = case.birth_sex if case.birth_sex is not None else '-'
    data['race'] = case.race.name if case.race else "-"
    data['hispanic_ethnicity'] = case.hispanic_ethnicity if case.hispanic_ethnicity is not None else '-'
    if case.date_of_birth:
        data['date_of_birth'] = case.date_of_birth.strftime('%Y-%m-%d')
    else:
        data['date_of_birth']='-'
    data['age'] = case.age if case.age is not None else '-'
    data['age_status'] = case.age_status if case.age_status is not None else '-'
    if case.date_of_incident:
        data['date_time_of_inc'] = f'{case.date_of_incident.strftime("%Y-%m-%d")}'
    else:
        data['date_time_of_inc'] = '-'
    if case.time_of_incident is not None:
        data['date_time_of_inc'] += f' {datetime.strptime(case.time_of_incident, "%H%M").strftime("%H:%M")}'
    data['agency'] = f'{case.agency.name} - {case.division.name}' if case.agency is not None else '-'
    data['submitter_case_reference_number_1'] = case.submitter_case_reference_number if (
            case.submitter_case_reference_number is not None) else '-'
    data['alternate_case_reference_number_1'] = case.alternate_case_reference_number_1 if (
            case.alternate_case_reference_number_1 is not None) else '-'
    data['alternate_case_reference_number_2'] = case.alternate_case_reference_number_2 if (
            case.alternate_case_reference_number_2 is not None) else '-'
    data['tox_requested'] = case.toxicology_requested if case.toxicology_requested is not None else '-'
    data['tox_performed'] = case.toxicology_performed if case.toxicology_performed is not None else '-'
    data['tox_status'] = case.toxicology_status if case.toxicology_status is not None else '-'
    data['diss_d'] = ""
    data['dss_tat_tox'] = ""
    data['bio_requested'] = case.biochemistry_requested if case.biochemistry_requested is not None else '-'
    data['bio_performed'] = case.biochemistry_performed if case.biochemistry_performed is not None else '-'
    data['bio_status'] = case.biochemistry_status if case.biochemistry_status is not None else '-'
    data['hist_requested'] = case.histology_requested if case.histology_requested is not None else '-'
    data['hist_performed'] = case.histology_performed if case.histology_performed is not None else '-'
    data['hist_status'] = case.histology_status if case.histology_status is not None else '-'
    data['ext_requested'] = case.external_requested if case.external_requested is not None else '-'
    data['ext_performed'] = case.external_performed if case.external_performed is not None else '-'
    data['ext_status'] = case.external_status if case.external_status is not None else '-'
    data['phys_requested'] = case.physical_requested if case.physical_requested is not None else '-'
    data['phys_performed'] = case.physical_performed if case.physical_performed is not None else '-'
    data['phys_status'] = case.physical_status if case.physical_status is not None else '-'
    data['drug_requested'] = case.drug_requested if case.drug_requested is not None else '-'
    data['drug_performed'] = case.drug_performed if case.drug_performed is not None else '-'
    data['drug_status'] = case.drug_status if case.drug_status is not None else '-'
    data['item_medical_record'] = case.medical_record if case.medical_record is not None else '-'
    data['item_home_address'] = case.home_address if case.home_address is not None else "-"
    data['item_home_zip'] = case.home_zip if case.home_zip is not None else '-'
    data['item_death_address'] = f'{case.death_address} {case.death_zip} ({case.latitude}, {case.longitude})' if (
            case.death_address is not None) else '-'
    data['item_death_premise'] = case.death_premises if case.death_premises is not None else '-'
    data['item_fa_case_comments'] = case.fa_case_comments if case.fa_case_comments is not None else '-'
    data['item_fa_case_stage'] = case.fa_case_stage if case.fa_case_stage is not None else '-'
    data['fa_case_entry_date'] = case.fa_case_entry_date if case.fa_case_entry_date is not None else "-"
    data['item_exam_status'] = case.exam_status if case.exam_status is not None else '-'
    data['autopsy_date'] = f'{case.autopsy_type}: {case.autopsy_start_date} - {case.autopsy_end_date}' if (
            case.autopsy_type is not None) else '-'
    data['item_manner_of_death'] = case.manner_of_death if case.manner_of_death is not None else '-'
    data['item_cod_a'] = case.cod_a if case.cod_a is not None else '-'
    data['item_cod_b'] = case.cod_b if case.cod_b is not None else '-'
    data['item_cod_c'] = case.cod_c if case.cod_c is not None else '-'
    data['item_other_conditions'] = case.other_conditions if case.other_conditions is not None else '-'
    data['item_method_of_death'] = case.method_of_death if case.method_of_death is not None else '-'
    data['item_pathologist_full_name'] = case.pathologist.full_name if case.pathologist is not None else "-"
    data['item_investigator_full_name'] = case.investigator.full_name if case.primary_investigator else "-"
    data['item_cert_status'] = case.certificate_status if case.certificate_status is not None else '-'
    if is_pm:
        data['item_short_narrative'] = html_to_richtext(narratives['Summary'])
        data['item_investigators_report'] = html_to_richtext(narratives['Initial'])
    else:
        data['item_short_narrative'] = '-'
        data['item_investigators_report'] = '-'

    if case.toxicology_alternate_start_date is not None:
        data['t_s_d'] = f'{case.toxiocolgy_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.toxicology_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.toxicology_start_date is not None:
        data['t_s_d'] = f'{case.toxicology_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['t_s_d'] = '-'

    if case.biochemistry_alternate_start_date is not None:
        data['bio_start_date'] = f'{case.biochemistry_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.biochemistry_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.biochemistry_start_date is not None:
        data['bio_start_date'] = f'{case.biochemistry_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['bio_start_date'] = '-'

    if case.histology_alternate_start_date is not None:
        data['hist_start_date'] = f'{case.histology_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.histology_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.histology_start_date is not None:
        data['hist_start_date'] = f'{case.histology_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['hist_start_date'] = '-'

    if case.physical_alternate_start_date is not None:
        data['phys_start_date'] = f'{case.physical_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.physical_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.physical_start_date is not None:
        data['phys_start_date'] = f'{case.physical_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['phys_start_date' ] = '-'

    if case.external_alternate_start_date is not None:
        data['ext_start_date'] = f'{case.external_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.external_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.external_start_date is not None:
        data['ext_start_date'] = f'{case.external_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['ext_start_date'] = '-'
    
    if case.drug_alternate_start_date is not None:
        data['drug_start_date'] = f'{case.drug_start_date.strftime("%Y-%m-%d %H:%M")} (alt. {case.drug_alternate_start_date.strftime("%Y-%m-%d %H:%M")})'
    elif case.drug_start_date is not None:
        data['drug_start_date'] = f'{case.drug_start_date.strftime("%Y-%m-%d %H:%M")}'
    else:
        data['drug_start_date'] = '-'

    data['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                        if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                        for comment in CommentInstances.query.filter_by(comment_item_type='Cases', comment_item_id=case.id, db_status='Active')]
    
    if len(data['comments']) == 0:
        data['comments'] = None

    # Get container data
    containers = Containers.query.filter_by(case_id=case.id).order_by(Containers.create_date.asc())
    data['containers'] = []
    data['modifications'] = []
    for cont in containers:
        container = {}
        container['container_mod'] = []
        container['cont_accession_num'] = cont.accession_number
        container['type_code_cont'] = f'[#{cont.type.code}#] {cont.type.name}'
        container['spec_acc_rec'] = f'{cont.n_specimens} / {cont.n_specimens_submitted}'
        container_number = 0
        container['container_num'] = container_number + 1
        container['submitted_by'] = f'{cont.submitter.full_name} - {cont.submitter.division.name} - ' \
                                    f'{cont.submitter.division.agency.name}' if cont.submitter else '-'
        container['evidence_receipt_comments'] = cont.evidence_comments if cont.evidence_comments is not None else '-'
        if container['evidence_receipt_comments'] == '':
            container['evidence_receipt_comments'] = '-'
        if cont.submission_date:
            container['submission_date_time'] = f'{cont.submission_date.strftime("%Y-%m-%d")} '\
                f'{datetime.strptime(cont.submission_time, "%H%M").strftime("%H:%M") if cont.submission_time is not None else ""}'
        else:
            container['submission_date_time'] = '-'
        container['submission_route_type'] = cont.submission_route_type if (cont.submission_route_type
                                                                            is not None) else '-'
        container['submission_route'] = cont.submission_route if cont.submission_route is not None else '-'
        container['container_spec_notes'] = cont.notes if cont.notes is not None else '-'
        container['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                 if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                 for comment in CommentInstances.query.filter_by(comment_item_type='Containers', comment_item_id=cont.id, db_status='Active')]
        
        if len(container['comments']) == 0:
                container['comments'] = None

        container['specimens'] = []
        num_specimen = 0
        # Set container accession_numbers to make sure they are not redacted
        accession_numbers.append(cont.accession_number)

        # Add container modifications
        for m in Modifications.query.filter_by(table_name='containers', record_id=str(cont.id)):
            modification = {
                'event': m.event,
                'status': m.status,
                'revision': m.revision,
                'field': m.field,
                'original_value': m.original_value_text if m.original_value is not None else '-',
                'new_value': m.new_value_text if m.new_value is not None else '-',
                'submitter': f'{m.submitter.initials} {m.submitted_date.strftime("%Y-%m-%d %H:%M")}'
                if m.submitted_by is not None else '-',
                'reviewer': f'{m.reviewer.initials} {m.review_date.strftime("%Y-%m-%d %H:%M")}'
                if m.reviewed_by is not None else '-',
                'table_name': m.table_name
            }

            container['container_mod'].append(modification)

        # Get all specimen data
        for spec in Specimens.query.filter_by(case_id=case.id, container_id=cont.id):
            num_specimen = num_specimen + 1
            specimen = {}
            specimen['specimen_mod'] = []
            specimen['spec_accession_num'] = spec.accession_number
            specimen['spec_type_code'] = f'[{spec.type.code}] {spec.type.name}'
            if spec.other_specimen is not None:
                specimen['spec_type_code'] += f' - {spec.other_specimen}'
            specimen['custody'] = spec.custody
            specimen['evidence_receipt_comments_spec'] = spec.evidence_comments if (spec.evidence_comments
                                                                                    is not None) else '-'
            if specimen['evidence_receipt_comments_spec'] == '':
                specimen['evidence_receipt_comments_spec'] = '-'
            if spec.collection_date:
                specimen['submission_date_time_spec'] = (f'{spec.collection_date.strftime("%Y-%m-%d")} '
                                                         f'{datetime.strptime(spec.collection_time, "%H%M").strftime("%H:%M") if spec.collection_time is not None else ""}')
            else:
                specimen['submission_date_time_spec'] = '-'
            specimen['collection_site'] = spec.specimen_site if spec.specimen_site is not None else '-'
            specimen['collection_container'] = spec.collection_container.display_name
            specimen['current_submitted_amount'] = f'{spec.current_sample_amount} / {spec.submitted_sample_amount}'
            specimen['condition'] = spec.condition if spec.condition is not None else '-'
            specimen['spec_notes'] =  f'{spec.notes if spec.notes is not None else None}'
            specimen['specimen_num'] = num_specimen if num_specimen is not None else '-'
            specimen['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                    if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                    for comment in CommentInstances.query.filter_by(comment_item_type='Specimens', comment_item_id=spec.id, db_status='Active')]
            
            if len(specimen['comments']) == 0:
                specimen['comments'] = None

            specimen['specimen_audit'] = []
            container['specimens'].append(specimen)
            custody_order = 0

            if specimen['spec_notes'] is None:
                specimen['spec_notes'] = '-'

            # Set specimen accession_numbers to ignore in redaction
            accession_numbers.append(spec.accession_number)

            # Add specimen modifications
            for m in Modifications.query.filter_by(table_name='specimens', record_id=str(spec.id)):
                modification = {
                    'event': m.event,
                    'status': m.status,
                    'revision': m.revision,
                    'field': m.field,
                    'original_value': m.original_value_text if m.original_value is not None else '-',
                    'new_value': m.new_value_text if m.new_value is not None else '-',
                    'submitter': f'{m.submitter.initials} {m.submitted_date.strftime("%m/%d/%Y %H:%M")}'
                    if m.submitted_by is not None else '-',
                    'reviewer': f'{m.reviewer.initials} {m.review_date.strftime("%m/%d/%Y %H:%M")}'
                    if m.reviewed_by is not None else '-',
                    'table_name': m.table_name
                }

                specimen['specimen_mod'].append(modification)

            # Get all chain of custody data
            for c in SpecimenAudit.query.filter_by(specimen_id=spec.id, db_status='Active'):
                custodychain = {}
                custody_order = custody_order + 1
                custodychain['cust-id'] = custody_order
                custodychain['custody_audit'] = c.destination
                custodychain['reason'] = c.reason
                custodychain['cust-date-time'] = c.o_time.strftime('%Y-%m-%d %H:%M') if c.o_time else '-'
                specimen['specimen_audit'].append(custodychain)
        data['containers'].append(container)
    results_ = Results.query.filter_by(case_id=case.id)
    data['tests'] = []

    # Get all test data
    tests = Tests.query.filter_by(case_id=case.id)
    for t in tests:
        test = {}
        if t.assay:
            test['tests_assay'] = t.assay.assay_name
        test['tests_batch_id'] = t.batch.batch_id if t.batch is not None else '-'
        if t.batch:
            test['tests_batch_date'] = t.batch.extraction_date.strftime("%Y-%m-%d %H:%M")
        else:
            test['tests_batch_date'] = '-'
        test['tests_name'] = t.test_name if t.test_name is not None else '-'
        if t.test_status == 'Finalized':
            test['tests_status'] = f'{t.test_status} {t.batch.review_finish_date.strftime("%Y-%m-%d %H:%M")}'
        else:
            test['tests_status'] = t.test_status if t.test_status is not None else '-'
        test['tests_specimen_accession_number'] = t.specimen.accession_number
        test['tests_specimen_type'] = f'[{t.specimen.type.code}] {t.specimen.type.name}'
        test['tests_dilution'] = t.dilution
        test['testresults'] = []
        for r in Results.query.filter_by(case_id=case.id, test_id=t.id):
            result = {}
            result['result_status'] = f'{r.result_status} (Updated)' if r.result_status_updated == 'Yes' else r.result_status
            result['result_component_name'] = r.component.name
            result['result_name'] = r.result if r.result is not None else '-'
            result['supp_result'] = r.supplementary_result if r.supplementary_result is not None else '-'
            result['result_concentration'] = r.concentration if r.concentration is not None else '-'
            result['result_qualitative'] = r.qualitative if r.qualitative is not None else '-'
            result['result_type'] = f"{r.result_type} (Updated)" if r.result_type_updated == 'Y' else (r.result_type if r.result_type is not None else '')
            result['result_notes'] = r.notes if r.notes is not None else '-'
            result['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                          if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                          for comment in CommentInstances.query.filter_by(comment_item_type='Results', comment_item_id=r.id, db_status='Active')]
            result['outlier_reason'] = r.report_reason if r.report_reason is not None else '-'
            result['qualitative_reason'] = r.qualitative_reason if r.qualitative_reason is not None else '-'
            result['status_update'] = r.result_status_updated
            result['type_update'] = r.result_type_updated
            result['result_status_update_reason'] = r.result_status_update_reason
            result['result_type_update_reason'] = r.result_type_update_reason
            result['unit'] = r.unit.name if r.unit_id is not None else '-'
            if len(result['comments']) == 0:
                result['comments'] = None
            test['testresults'].append(result)            
        data['tests'].append(test)

    data['results'] = []

    # Get all results data
    # for r in results_:
    #     result = {}
    #     if r.test.assay:
    #         result['results_assay'] = r.test.assay.assay_name
    #     result['results_batch'] = r.test.batch.batch_id if r.test.batch else '-'
    #     if r.test.batch.extraction_date:
    #         result['results_batch_date'] = r.test.batch.extraction_date.strftime("%Y-%m-%d")
    #     else:
    #         result['results_batch_date'] = 'N/A'
    #     result['results_test'] = r.test.test_name
    #     result['results_component_name'] = r.component.name
    #     result['result'] = r.result
    #     result['results_supplementary_result'] = r.supplementary_result
    #     result['results_concentration'] = r.concentration
    #     result['results_comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
    #                                   if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
    #                                   for comment in CommentInstances.query.filter_by(comment_item_type='Results', comment_item_id=r.id)]
    #     data['results'].append(result)

    # Get all records data
    records = Records.query.filter_by(case_id=case.id, db_status='Active').all()
    data['records'] = []
    for rec in records:
        record = {}
        record['record_name'] = rec.record_name
        record['record_type'] = rec.type.name if rec.record_type is not None else '-'
        if rec.dissemination_date:
            record['dissemination_date'] = f'{rec.dissemination_date.strftime("%Y-%m-%d %H:%M")} - {rec.disseminated_by}'
        else:
            record['dissemination_date'] = '-'
        record['disseminated_by'] = rec.disseminated_by if rec.disseminated_by is not None else '-'
        record['disseminated_to'] = rec.disseminated_to if rec.disseminated_to is not None else '-'
        if rec.create_date:
            record['date_record_created'] = rec.create_date.strftime("%Y-%m-%d %H:%M")
        else:
            record['date_record_created'] = '-'
        record['record_created_by'] = rec.created_by
        if rec.modify_date:
            record['record_date_modified'] = rec.modify_date.strftime("%Y-%m-%d %H:%M")
        else:
            record['record_date_modified '] = '-'
        record['record_modified_by'] = rec.modified_by
        data['records'].append(record)

    # Get all reports data
    reports = Reports.query.filter_by(case_id=case.id)
    data['reports'] = []
    for r in reports:
        report = {}
        report['report_name'] = r.report_name
        report['report_case_number'] = r.case.case_number
        report['report_discipline'] = r.discipline
        report['report_number'] = r.report_number
        report['draft_number'] = r.draft_number
        report['report_draft_status'] = r.report_status
        report['report_cr'] = r.case_review
        if r.case_review_date:
            report['report_cr_date'] = r.case_review_date.strftime("%Y-%m-%d %H:%M")
        else:
            report['report_cr_date'] = '-'
        report['report_dr'] = r.divisional_review
        if r.divisional_review_date:
            report['report_dr_date'] = r.divisional_review_date.strftime("%Y-%m-%d %H:%M")
        else:
            report['report_dr_date'] = '-'
        report['record'] = r.record_id
        if r.create_date:
            report['report_date_created'] = r.create_date.strftime('%Y-%m-%d %H:%M')
        else:
            report['report_date_created'] = '-'
        report['report_created_by'] = r.created_by
        if r.modify_date:
            report['report_date_modified'] = r.modify_date.strftime("%Y-%m-%d %H:%M")
        else:
            report['report_date_modified'] = '-'
        data['reports'].append(report)

    # Get all requests that include the relevant case_id
    requests = Requests.query.filter(
        or_(
            Requests.case_id == case_id,                        # exactly "123"
            Requests.case_id.like(f"{case_id},%"),              # starts "123,"
            Requests.case_id.like(f"%,{case_id},%"),            # contains ",123,"
            Requests.case_id.like(f"%,{case_id}")               # ends ",123"
        )
    ).all()
    
    data['requests'] = []
    
    # Iterate through requests and set relevant variables
    for req in requests:
        request = {}
        request['type'] = req.request_type.name

        # Use try/except statements to handle potential strftime fatal errors
        try:
            request['intake_user'] = f'{Users.query.get(int(req.intake_user)).initials} {req.intake_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['intake_user'] = f'{Users.query.get(int(req.intake_user)).initials}'
        request['items_requested'] = req.requested_items
        request['requestor'] = f'{req.agency_req.name} - {req.division_req.name} '\
            f'- {req.personnel_req.full_name}'
        request['destination'] = f'{req.dest_agency.name}' if req.dest_agency else 'N/A'
        request['destination'] += f' - {req.dest_division.name} - {req.dest_division.full_address}'\
              if req.dest_division is not None else ' - N/A'
        try:
            request['nok'] = f'{req.next_of_kin_confirmation} {req.next_of_kin_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['nok'] = f'{req.next_of_kin_confirmation}'
        request['payment'] = req.payment_confirmation
        try:
            request['submission_auth'] = f'{req.me_confirmation} {req.me_confirmation_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['submission_auth'] = req.me_confirmation if req.me_confirmation is not None else 'N/A'
        try:
            request['cft_auth'] = f'{req.approver.initials} {req.approve_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['cft_auth'] = f'{req.approver.initials}'
        try:
            request['preparer'] = f'{req.prepare_status} {req.preparing_user.initials} {req.prepare_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['preparer'] = f'{req.prepare_status}'
        try:
            request['checker'] = f'{req.check_status} {req.checking_user.initials} {req.check_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['checker'] = f'{req.check_status}'
        try:
            request['releaser'] = f'{req.release_status} {req.releasing_user.initials} {req.release_date.strftime("%Y-%m-%d %H:%M")}'
        except AttributeError:
            request['releaser'] = f'{req.release_status}'
        request['received_by'] = f'{req.agency_rec.name} - {req.division_rec.name} - {req.personnel_rec.full_name}'
        request['notes'] = req.notes

        # Get request comments
        request['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                               if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                               for comment in CommentInstances.query.filter_by(comment_item_type='Requests', comment_item_id=req.id, db_status='Active')]
        
        # Set comments to None if query returns empty array
        if len(request['comments']) == 0:
            request['comments'] = None

        # Set all missing variables to N/A
        for k, v in request.items():
            if v is None and k != 'comments':
                request[k] = 'N/A'

        # Add specimen information
        # Use try/except to handle .split() fatal errors
        try:
            approved_specimens = req.approved_specimens.split(',')
        except AttributeError:
            approved_specimens = [req.approved_specimens]
        try:
            requested_specimens = req.specimens.split(',')
        except AttributeError:
            requested_specimens = [req.specimens]
        try:
            denied_specimens = req.denied_specimens.split(',')
        except AttributeError:
            denied_specimens = [req.denied_specimens]
        request['specimens'] = []
        
        # Iterate through specimen and set relevant variables
        if approved_specimens[0] is not None:
            for spec in approved_specimens:
                # Get specimen item
                specimen = Specimens.query.get(int(spec))
                request_spec = {
                    'case_num': specimen.case.case_number,
                    'acc_num': specimen.accession_number,
                    'type': f'[{specimen.type.code}] {specimen.type.name}',
                    'custody': specimen.custody,
                    'status': 'Approved'
                }
                request['specimens'].append(request_spec)
            
        # See above comments
        if requested_specimens[0] is not None:
            for spec in requested_specimens:
                specimen = Specimens.query.get(int(spec))
                request_spec = {
                    'case_num': specimen.case.case_number,
                    'acc_num': specimen.accession_number,
                    'type': f'[{specimen.type.code}] {specimen.type.name}',
                    'custody': specimen.custody,
                    'status': 'Requested'
                }
                request['specimens'].append(request_spec)

        # See above comments
        if denied_specimens[0] is not None:
            for spec in denied_specimens:
                specimen = Specimens.query.get(int(spec))
                request_spec = {
                    'case_num': specimen.case.case_number,
                    'acc_num': specimen.accession_number,
                    'type': f'[{specimen.type.code}] {specimen.type.name}',
                    'custody': specimen.custody,
                    'status': 'Denied'
                }
                request['specimens'].append(request_spec)
        
        data['requests'].append(request)

    # Get all returns relevant to case
    returns = Returns.query.filter(
        or_(
            Returns.case_id == str(case_id),                   # exactly "123"
            Returns.case_id.like(f"{case_id},%"),              # starts "123,"
            Returns.case_id.like(f"%,{case_id},%"),            # contains ",123,"
            Returns.case_id.like(f"%,{case_id}")               # ends ",123"
        )
    ).all()

    data['returns'] = []

    # Iterate through all returns and set relevant variables
    for ret in returns:
        rtrn = {}
        rtrn['returned_by'] = f'{ret.agency.name} - {ret.division.name} - {ret.personnel.full_name}'
        rtrn['checker'] = ret.checker_user.initials
        rtrn['notes'] = ret.notes
        rtrn['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                            if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                            for comment in CommentInstances.query.filter_by(comment_item_type='Returns', comment_item_id=ret.id, db_status='Active')]
        
        # If comments query returns empty array, set comments to None
        if len(rtrn['comments']) == 0:
            rtrn['comments'] = None
        
        # Set all relevant variable
        for k, v in rtrn.items():
            if v is None and k != 'comments':
                rtrn[k] = 'N/A'

        # Get relevant returned and stored specimens and handle potentifal fatal .split errors
        try:
            returned_specimens = ret.returned_specimens.split(',')
        except AttributeError:
            returned_specimens = [ret.returned_speicmens]
        try:
            stored_specimens = ret.stored_specimens.split(',')
        except AttributeError:
            stored_specimens = [ret.stored_specimens]
        
        # Iterate through specimens and set relevant data
        rtrn['specimens'] = []
        if returned_specimens[0] is not None:
            for spec in returned_specimens:
                specimen = Specimens.query.get(int(spec))
                rtrn_spec = {
                    'case_num': specimen.case.case_number,
                    'acc_num': specimen.accession_number,
                    'type': f'[{specimen.type.code}] {specimen.type.name}',
                    'custody': specimen.custody,
                    'status': 'Returned'
                }
                rtrn['specimens'].append(rtrn_spec)
        
        if stored_specimens[0] is not None:
            for spec in stored_specimens:
                specimen = Specimens.query.get(int(spec))
                rtrn_spec = {
                    'case_num': specimen.case.case_number,
                    'acc_num': specimen.accession_number,
                    'type': f'[{specimen.type.code}] {specimen.type.name}',
                    'custody': specimen.custody,
                    'status': 'Stored'
                }
                rtrn['specimens'].append(rtrn_spec)

        data['returns'].append(rtrn)


    # # Create the document and PDF in memory
    # doc_stream = BytesIO()
    # doc.render(data, autoescape=True)
    # doc.save(doc_stream)
    # doc_stream.seek(0)
    #
    # pdf_stream = BytesIO()
    # pythoncom.CoInitialize()
    # docx2pdf.convert(doc_stream, pdf_stream)
    # pdf_stream.seek(0)
    # return pdf_stream

    def get_unique_file_name(directory, file_name, extension):
        """

        Args:
            directory (str): Usually created with os.path.join to get the directory you want to save to
            file_name (str): The file name that the unique_file_name will be based off of
            extension (str): The extension of the file (e.g., pdf, docx, etc.)

        Returns:
            str: Unique file name created by joining the directory with a uniquely generated file
            name

        """
        counter = 1
        unique_file_name = f"{file_name}.{extension}"
        while os.path.exists(os.path.join(directory, unique_file_name)):
            unique_file_name = f"{file_name} ({counter}).{extension}"
            counter += 1
        return unique_file_name

    # Use the packet-specific folder
    packet_folder = os.path.join(current_app.root_path, 'static/filesystem/litigation_packets', packet_name)
    if not os.path.exists(packet_folder):
        os.makedirs(packet_folder)

    # Save the DOCX and PDF files in the packet-specific folder
    # base_file_name = f"00 Case Contents {case.case_number}"
    # docx_file_name = get_unique_file_name(packet_folder, base_file_name, "docx")
    docx_file_name = f"0A Case Contents {case.case_number}.docx"
    # pdf_file_name = get_unique_file_name(packet_folder, base_file_name, "pdf")
    pdf_file_name = f"0A Case Contents {case.case_number}.pdf"

    # Generate requests/returns warning pdf
    if len(data['requests']) > 0 or len(data['returns']) > 0:
        warning_docx = '000A WARNING.docx'
        warning_pdf = '000A WARNING.pdf'
        warning_docx_path = os.path.join(packet_folder, warning_docx)
        warning_pdf_path = os.path.join(packet_folder, warning_pdf)

        warning_doc = DocxTemplate(os.path.join(current_app.root_path, 'static/litigation_packet_templates', 
                                                'warning_template.docx'))
        warning_doc.render(data, autoescape=True)
        warning_doc.save(warning_docx_path)
        need_warning = True
    else:
        warning_pdf = None
        need_warning = False

    # Get word upfront
    word = gencache.EnsureDispatch('Word.Application')

    docx_path = os.path.join(packet_folder, docx_file_name)
    pdf_path = os.path.join(packet_folder, pdf_file_name)

    doc.render(data, autoescape=True)
    doc.save(docx_path)

    pythoncom.CoInitialize()
    docx2pdf.convert(docx_path, pdf_path, keep_active=True)
    if need_warning:
        docx2pdf.convert(warning_docx_path, warning_pdf_path)

    # When using 'keep_active' need to quit word
    word.Quit()

    # Remove the DOCX file - only keep the PDF
    try:
        os.remove(docx_path)
    except Exception as e:
        print(f"Failed to delete temporary Word document: {e}")

    return pdf_file_name, warning_pdf

    # Redact the file
    # *****(No redaction necessary for case contents per LNR 03/20/2025)*****
    # if redact is False:
    #     redactor = Redactor(pdf_path, ignore_case_number=Cases.query.get_or_404(case_id).case_number,
    #                         ignore_accession_numbers=accession_numbers)
    #     redacted_path = redactor.redaction()
    #     shutil.move(redacted_path, pdf_path)
    #     print(f"Redacted file saved at {pdf_path}")


def generate_batches(item_id, assay_ids, redact, packet_name):
    template_path = os.path.join(current_app.root_path, 'static/litigation_packet_templates', 'Batch pdf Template.docx')
    doc = DocxTemplate(template_path)
    batch_ids = set()  # This will filter for batch ids that are duplicated when looping
    batch_data = []  # a list to store all the batch data
    batch = Batches.query.filter_by(batch_id=assay_ids).first().id
    assay_name = Batches.query.filter_by(batch_id=assay_ids).first().assay.assay_name
    # tests = Tests.query.filter_by(case_id=item_id)
    tests = Tests.query.filter_by(batch_id=batch)
    assay_ids_case = set()
    accession_numbers = []
    sort_order = LitPacketAdminAssays.query.filter_by(name=assay_name).first().lit_admin_sort_order

    tests_by_assay = defaultdict(list)

    for test in tests:
        if test.batch_id:
            batch_ids.add(test.batch_id)
            assay_ids_case.add(test.assay_id)

            tests_by_assay[test.assay.assay_name].append({
                "name": test.test_name,
                "id": test.test_id,
                "case_num": test.case.case_number,
                "accession_num": test.specimen.accession_number,
                "specimen_type": test.specimen.type.code,
            })

    combined_assay_ids = list(assay_ids_case.intersection(assay_ids))

    # Iterate through each batch and get related data
    for batch_id in batch_ids:
        batch = Batches.query.get(batch_id)
        checks = get_batch_checks(batch_id)
        sequence_name = ''
        counter = 0

        # Initialize required verification columns for specific batch
        required_columns = ['specimen_check']

        # Get the sequence for the batch
        for sequence in BatchRecords.query.filter_by(batch_id=batch.id, file_type='Sequence'):
            counter += 1
            if counter == 1:
                sequence_name += f'{sequence.file_name}'
            else:
                sequence_name += f', {sequence.file_name}'

        if batch and batch.assay_id in combined_assay_ids:

            # Check if batch is tandem and handle accordingly
            if batch.tandem_id:
                tandem_batch = Batches.query.get(batch.tandem_id).batch_id
            else:
                tandem_batch = '-'

            # Initialize and set batch_info
            batch_info = {
                "constituents": [],
                'tests': [],
                'checks': [],
                'required_columns': [],
                "name": batch.batch_id,
                "status": batch.batch_status,
                "assay": batch.assay.assay_name if batch.assay is not None else "-",
                "test_count": batch.test_count,
                "instrument": batch.instrument.instrument_id if batch.instrument is not None else "-",
                "instrument_two": batch.instrument_2.instrument_id if batch.instrument_2 is not None else "-",
                "batch_template": batch.batch_template.name if batch.batch_template is not None else "-",
                "sequence_file": sequence_name,
                "technique": batch.technique,
                "tandem_batch": tandem_batch,
                'transfer_check': checks['batch_transfer_check'],
                'sequence_check': checks['batch_sequence'],
                'source_check': checks['batch_specimen_check'],
                'comments': [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                             if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                             for comment in CommentInstances.query.filter_by(comment_item_type='Batches', 
                                                                             comment_item_id=batch.id,
                                                                             db_status='Active')],
                'pipettes': [f'{CalibratedLabware.query.get(int(pipette)).equipment_id}' 
                             for pipette in batch.pipettes.split(',')] if batch.pipettes is not None else []
            }

            # If no batch comments exist, set to "-"
            if len(batch_info['comments']) == 0:
                batch_info['comments'] = ['-']
            batch_data.append(batch_info)

            if batch.extracted_by_id is not None and batch.extraction_finish_date is not None:
                batch_info['extracting_analyst'] = f'{batch.extractor.initials} | Start: {batch.extraction_date.strftime("%Y-%m-%d %H:%M")} |'
                f' Finish: {batch.extraction_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.extracted_by_id:
                batch_info['extracting_analyst'] = f'{batch.extractor.initials} | Start: {batch.extraction_date.strftime("%Y-%m-%d %H:%M")}'
            else:
                batch_info['extracting_analyst'] = '-'

            if batch.processed_by_id is not None and batch.process_finish_date is not None:
                batch_info['processing_analyst'] = f'{batch.processor.initials} | Start: {batch.process_date.strftime("%Y-%m-%d %H:%M")} |'
                f' finish: {batch.process_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.processed_by_id is not None:
                batch_info['processing_analyst'] = f'{batch.processor.initials} | Start: {batch.process_date.strftime("%Y-%m-%d %H:%M")} |' 
            else:
                batch_info['processing_analyst'] = '-'

            if batch.reviewed_by_id is not None and batch.review_finish_date is not None:
                batch_info['batch_reviewer'] = f'{batch.batch_reviewer.initials} | Start: {batch.review_date.strftime("%Y-%m-%d %H:%M")} |'
                f' finish: {batch.review_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.reviewed_by_id is not None:
                batch_info['batch_reviewer'] = f'{batch.batch_reviewer.initials} | Start: {batch.review_date.strftime("%Y-%m-%d %H:%M")} |'
            else:
                batch_info['batch_reviewer'] = '-'

            # Set required verification columns based on assay
            if 'LCQD' in batch.assay.assay_name or 'QTON' in batch.assay.assay_name:
                required_columns.extend(['specimen_check', 'transfer_check', 'sequence_check'])

                if batch.technique == 'Automated':
                    required_columns.append('load_check')
            elif 'GCET' in batch.assay.assay_name:
                required_columns.append('sequence_check')

            elif 'LCCI' in batch.assay.assay_name:
                required_columns.append('sequence_check')
                required_columns.append('transfer_check')

            batch_info['required_columns'].extend(required_columns.copy())

            # Get batch_constituents and set relevant data and set verification column values
            batch_constituents = BatchConstituents.query.filter_by(batch_id=batch.id).all()

            # Create dictionary of constituent_type key and vial_position value to display vial position for manually added constituents
            constituent_vials = {const.constituent_type: const.vial_position for const in batch_constituents if const.vial_position is not None}

            for constituent in batch_constituents:

                if batch.technique == 'Hamilton' and constituent.load_check is not None and \
                        constituent.load_check != 'N/A':
                    const_load_check = (f'{constituent.load_check}\n'
                                        f'{constituent.loader.initials} '
                                        f'{constituent.load_checked_date.strftime("%Y-%m-%d %H:%M")}')
                elif batch.technique == 'Non-Hamilton':
                    const_load_check = 'N/A'
                else:
                    const_load_check = '-'

                if constituent.transfer_check is not None and constituent.transfer_check != 'N/A' and \
                        constituent.transfer_check != 'Skipped':
                    const_transfer_check = (f'{constituent.transfer_check}\n'
                                            f'{constituent.transfer_checker.initials} '
                                            f'{constituent.transfer_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif constituent.transfer_check == 'N/A':
                    const_transfer_check = 'N/A'
                elif constituent.transfer_check == 'Skipped':
                    const_transfer_check = 'Skipped'
                else:
                    const_transfer_check = '-'

                if constituent.sequence_check is not None and constituent.sequence_check != 'N/A':
                    const_sequence_check = (f'{constituent.sequence_check}\n'
                                            f'{constituent.sequence_checker.initials} '
                                            f'{constituent.sequence_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif constituent.sequence_check == 'N/A':
                    const_sequence_check = 'N/A'
                else:
                    const_sequence_check = '-'

                # Assign vial_position for packet generation
                if constituent.vial_position is not None:
                    vial_position = constituent.vial_position
                elif constituent.constituent_type in constituent_vials.keys():
                    vial_position = constituent_vials[constituent.constituent_type]
                else:
                    vial_position = '-'

                # Initialze const_comment_text array
                const_comment_text = []

                if constituent.constituent_id is not None:
                    # Query for standards_and_solutions comments
                    constituent_comments = CommentInstances.query.filter_by(comment_item_type='Prepared Standards and Reagents', comment_item_id=constituent.id).all()
                elif constituent.reagent_id is not None:
                    # Query for solvents_and_reagents comments
                    constituent_comments = CommentInstances.query.filter_by(comment_item_type='Purchased Reagents', comment_item_id=constituent.id).all()
                else:
                    # Set const_comment_text to None if no reagent_id or constituent_id
                    const_comment_text = ['-']

                if len(constituent_comments) > 0:
                    for comment in constituent_comments:
                        # Add all comment text to const_comment_text
                        const_comment_text.append(f'{comment.text} - {comment.created_by} {comment.create_date.strftime("%m/%d/%Y")}')
                else:
                    const_comment_text = ['-']

                constituent_info = {
                    "vial_position": vial_position,
                    "name": constituent.constituent_type if constituent.constituent_type is not None else "-",
                    "populated_from": constituent.populated_from if constituent.populated_from is not None else "-",
                    "transfer_check": const_transfer_check,
                    "sequence_check": const_sequence_check,
                    "hamilton_load_check": const_load_check,
                    "comments": const_comment_text
                }

                if constituent.specimen_check != 'N/A' and constituent.specimen_check is not None:
                    constituent_info['source_check'] = f'{constituent.specimen_check}\n {constituent.specimen_checker.initials} {constituent.specimen_check_date.strftime("%Y-%m-%d %H:%M")}'
                elif constituent.specimen_check == 'N/A':
                    constituent_info['source_check'] = 'N/A'
                elif constituent.specimen_check is None:
                    constituent_info['source_check'] = '-'
                else:
                    constituent_info['source_check'] = constituent.specimen_check

                if constituent.include_checks:
                    constituent_info['checks'] = 'Yes'
                else:
                    constituent_info['checks'] = 'No'
                if constituent.constituent is not None:
                    constituent_info["lot"] =  constituent.constituent.lot if (constituent.constituent is
                                                                               not None) else "-"
                    constituent_info['in_use'] = constituent.constituent.in_use

                    if constituent.constituent.retest_date is not None:
                        constituent_info['expiration_date'] = constituent.constituent.retest_date.strftime('%Y-%m-%d')
                    if constituent.constituent is not None:
                        pass
                    if constituent.include_checks:
                        constituent_info['checks'] = 'Yes'
                    else:
                        constituent_info['checks'] = 'No'
                elif constituent.reagent is not None:
                    constituent_info['lot'] = constituent.reagent.lot if constituent.reagent is not None else "-"
                    constituent_info['in_use'] = constituent.reagent.in_use

                    if constituent.reagent.exp_date is not None:
                        constituent_info['expiration_date'] = constituent.reagent.exp_date.strftime('%Y-%m-%d')
                    else:
                        constituent_info['expiration_date'] = 'N/A'

                batch_info['constituents'].append(constituent_info.copy())

            # Iterate through tests, set relevant data and set verification column values
            for t in Tests.query.filter_by(batch_id=batch.id, test_status='Finalized').all():
                if t.case_id == Cases.query.get(item_id).id:
                    accession_numbers.append(t.specimen.accession_number)

                if batch.technique == 'Automated' and t.load_check != 'N/A' and t.load_check is not None:
                    t_load_check = (f'{t.load_check}\n'
                                    f'{t.load_checker.initials} '
                                    f'{t.load_checked_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.load_check == 'N/A':
                    t_load_check = 'N/A'
                else:
                    t_load_check = '-'

                if t.transfer_check is not None and t.transfer_check != 'N/A':
                    t_transfer_check = (f'{t.transfer_check}\n'
                                        f'{t.transfer_checker.initials} '
                                        f'{t.transfer_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.transfer_check == 'N/A':
                    t_transfer_check = 'N/A'
                else:
                    t_transfer_check = '-'

                if t.sequence_check is not None and t.sequence_check != 'N/A':
                    t_sequence_check = (f'{t.sequence_check}\n'
                                        f'{t.sequence_checker.initials} '
                                        f'{t.sequence_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.sequence_check == 'N/A':
                    t_sequence_check = 'N/A'
                else:
                    t_sequence_check = '-'

                test_info = {
                    "status": t.test_status,
                    "name": t.test_name,
                    "id": t.test_id,
                    "dilution": t.dilution,

                    "assay": t.assay.assay_name if t.assay is not None else "-",

                    "case_num": t.case.case_number,
                    "accession_num": t.specimen.accession_number,
                    "specimen_type": t.specimen.type.code,
                    "test_order_date": t.create_date.strftime('%Y-%m-%d %H:%M') if t.create_date else '-',
                    "current_amount": t.specimen.current_sample_amount,
                    "original_amount": t.specimen.submitted_sample_amount,
                    "conditions": t.specimen.condition,
                    "priority": t.case.priority,
                    "current_location": t.specimen.custody,
                    'notes': t.notes if t.notes is not None else '-'
                }
                # Get test comments only for relevant case
                if t.case_id == item_id:
                    test_info['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                             if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                                             for comment in CommentInstances.query.filter_by(comment_item_type='Tests', 
                                                                                             comment_item_id=t.id,
                                                                                             db_status='Active')]
                    # Check if any comments exist, set to N/A if not
                    if len(test_info['comments']) == 0:
                        test_info['comments'] = '-'
                
                # Set all other cases test comments to N/A
                else:
                    test_info['comments'] = '-'

                check_info = {
                    "check_test_id": t.test_name,
                    "spec_check": f'{t.specimen_check}\n'
                                  f'{t.specimen_checker.initials} '
                                  f'{t.checked_date.strftime("%Y-%m-%d %H:%M")}' if
                    t.specimen_check is not None else '-',
                    "hamilton_load_check": t_load_check,
                    "transfer_check": t_transfer_check,
                    "seq_check": t_sequence_check,
                }
                batch_info['tests'].append(test_info.copy())
                batch_info['checks'].append(check_info.copy())

            # checks = Tests.query.filter_by(batch_id=batch_id)
            # for check in checks:
            #     check_info = {
            #         "check_test_id": check.test_name,
            #         "spec_checked_by": "N/A",
            #         "hamilton_load_check": "N/A",
            #         "hamilton_load_checked_by": "N/A",
            #         "transfer_check_status": "N/A",
            #         "transfer_checked_by": "N/A",
            #         "seq_check_status": "N/A",
            #         "seq_checked_by": "N/A"
            #     }
            #     batch_info['checks'] = check_info
        else:  # Added check for combined_assay_ids

            # Check if batch is tandem and handle accordingly
            if batch.tandem_id:
                tandem_batch = Batches.query.get(batch.tandem_id).batch_id
            else:
                tandem_batch = '-'

            batch_info = {
                "tests": [],
                "checks": [],
                "constituents": [],
                'required_columns': [],
                # "reagents": []
                "name": batch.batch_id,
                "status": batch.batch_status,
                "assay": batch.assay.assay_name if batch.assay is not None else "-",
                "test_count": batch.test_count,
                "instrument": batch.instrument.instrument_id if batch.instrument is not None else "-",
                "instrument_two": batch.instrument_2.instrument_id if batch.instrument_2 is not None else "-",
                "batch_template": batch.batch_template.name if batch.batch_template is not None else "-",
                "sequence_file": sequence_name,
                "technique": batch.technique,
                "tandem_batch": tandem_batch,
                'transfer_check': checks['batch_transfer_check'] if batch.assay.assay_name != 'GCET-FL' else "N/A",
                'sequence_check': checks['batch_sequence'],
                'source_check': checks['batch_specimen_check'],
                'comments': [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                             if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                             for comment in CommentInstances.query.filter_by(comment_item_type='Batches', 
                                                                             comment_item_id=batch.id,
                                                                             db_status='Active')],
                'pipettes': [f'{CalibratedLabware.query.get(int(pipette)).equipment_id}' 
                             for pipette in batch.pipettes.split(',')] if batch.pipettes is not None else []
            }
            if len(batch_info['comments']) == 0:
                batch_info['comments'] = None
            if len(batch_info['pipettes']) > 0 and len(batch_info['pipettes']) > 1:
                batch_info['pipettes'] = ', '.join(batch_info['pipettes'])

            if batch.extracted_by_id is not None and batch.extraction_finish_date is not None:
                batch_info['extracting_analyst'] = f'{batch.extractor.initials} | Start: {batch.extraction_date.strftime("%Y-%m-%d %H:%M")} |'
                f' Finish: {batch.extraction_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.extracted_by_id:
                batch_info['extracting_analyst'] = f'{batch.extractor.initials} | Start: {batch.extraction_date.strftime("%Y-%m-%d %H:%M")}'
            else:
                batch_info['extracting_analyst'] = '-'

            if batch.processed_by_id is not None and batch.process_finish_date is not None:
                batch_info['processing_analyst'] = f'{batch.processor.initials} | Start: {batch.process_date.strftime("%Y-%m-%d %H:%M")} |'
                f' finish: {batch.process_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.processed_by_id is not None:
                batch_info['processing_analyst'] = f'{batch.processor.initials} | Start: {batch.process_date.strftime("%Y-%m-%d %H:%M")} |' 
            else:
                batch_info['processing_analyst'] = '-'

            if batch.reviewed_by_id is not None and batch.review_finish_date is not None:
                batch_info['batch_reviewer'] = f'{batch.batch_reviewer.initials} | Start: {batch.review_date.strftime("%Y-%m-%d %H:%M")} |'
                f' finish: {batch.review_finish_date.strftime("%Y-%m-%d %H:%M")}'
            elif batch.reviewed_by_id is not None:
                batch_info['batch_reviewer'] = f'{batch.batch_reviewer.initials} | Start: {batch.review_date.strftime("%Y-%m-%d %H:%M")} |'
            else:
                batch_info['batch_reviewer'] = '-'
            
            batch_data.append(batch_info)

            if 'LCQD' in batch.assay.assay_name or 'QTON' in batch.assay.assay_name:
                required_columns.extend(['specimen_check', 'transfer_check', 'sequence_check'])

                if batch.technique == 'Automated':
                    required_columns.append('load_check')

            elif 'GCET' in batch.assay.assay_name:
                required_columns.append('sequence_check')

            elif 'LCCI' in batch.assay.assay_name:
                required_columns.append('sequence_check')
                required_columns.append('transfer_check')

            batch_info['required_columns'].extend(required_columns.copy())

            batch_constituents = BatchConstituents.query.filter_by(batch_id=batch.id).all()

            # Create dictionary of constituent_type key and vial_position value to display vial position for manually added constituents
            constituent_vials = {const.constituent_type: const.vial_position for const in batch_constituents if const.vial_position is not None}

            for constituent in batch_constituents:
                if batch.technique == 'Hamilton' and constituent.load_check is not None and \
                        constituent.load_check != 'N/A':
                    const_load_check = (f'{constituent.load_check}\n'
                                        f'{constituent.loader.initials} '
                                        f'{constituent.load_checked_date.strftime("%Y-%m-%d %H:%M")}')
                elif batch.technique == 'Non-Hamilton':
                    const_load_check = 'N/A'
                elif constituent.load_check == 'N/A':
                    const_load_check = 'N/A'
                else:
                    const_load_check = '-'

                if constituent.transfer_check is not None and constituent.transfer_check != 'N/A' and \
                        constituent.transfer_check != 'Skipped':
                    const_transfer_check = (f'{constituent.transfer_check}\n'
                                            f'{constituent.transfer_checker.initials} '
                                            f'{constituent.transfer_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif constituent.transfer_check == 'N/A':
                    const_transfer_check = 'N/A'
                elif constituent.transfer_check == 'Skipped':
                    const_transfer_check = 'Skipped'
                else:
                    const_transfer_check = '-'

                if constituent.sequence_check is not None and constituent.sequence_check != 'N/A':
                    const_sequence_check = (f'{constituent.sequence_check}\n'
                                            f'{constituent.sequence_checker.initials} '
                                            f'{constituent.sequence_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif constituent.sequence_check == 'N/A':
                    const_sequence_check = 'N/A'
                else:
                    const_sequence_check = '-'

                # Assign vial_position for packet generation
                if constituent.vial_position is not None:
                    vial_position = constituent.vial_position
                elif constituent.constituent_type in constituent_vials.keys():
                    vial_position = constituent_vials[constituent.constituent_type]
                else:
                    vial_position = 'N/A'

                # Initialze const_comment_text array
                const_comment_text = []
                constituent_comments = []

                if constituent.constituent_id is not None:
                    # Query for standards_and_solutions comments
                    constituent_comments = CommentInstances.query.filter_by(comment_item_type='Prepared Standards and Reagents', comment_item_id=constituent.constituent_id).all()
                elif constituent.reagent_id is not None:
                    # Query for solvents_and_reagents comments
                    constituent_comments = CommentInstances.query.filter_by(comment_item_type='Purchased Reagents', comment_item_id=constituent.reagent_id).all()
                else:
                    # Set const_comment_text to None if no reagent_id or constituent_id
                    const_comment_text = ['-']
                
                if len(constituent_comments) > 0:
                    for comment in constituent_comments:
                        # Add all comment text to const_comment_text
                        const_comment_text.append(f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%m/%d/%Y")}')
                else:
                    const_comment_text = ['-']

                constituent_info = {
                    "vial_position": vial_position,
                    "name": constituent.constituent_type if constituent.constituent_type is not None else "-",
                    "populated_from": constituent.populated_from if constituent.populated_from is not None else "-",
                    "transfer_check": const_transfer_check,
                    "sequence_check": const_sequence_check,
                    "hamilton_load_check": const_load_check,
                    "comments": const_comment_text
                }

                if constituent.specimen_check != 'N/A' and constituent.specimen_check is not None:
                    constituent_info['source_check'] = f'{constituent.specimen_check}\n {constituent.specimen_checker.initials} {constituent.specimen_check_date.strftime("%Y-%m-%d %H:%M")}'
                elif constituent.specimen_check == 'N/A':
                    constituent_info['source_check'] = 'N/A'
                elif constituent.specimen_check is None:
                    constituent_info['source_check'] = '-'
                else:
                    constituent_info['source_check'] = constituent.specimen_check

                if constituent.include_checks:
                    constituent_info['checks'] = 'Yes'
                else:
                    constituent_info['checks'] = 'No'
                if constituent.constituent is not None:
                    constituent_info['lot'] = constituent.constituent.lot if (constituent.constituent is
                                                                              not None) else "N/A"
                    constituent_info['in_use'] = ''

                    if constituent.constituent.authorized_date:
                        constituent_info['in_use'] += str(constituent.constituent.authorized_date.strftime('%Y-%m-%d'))
                    if constituent.constituent.retest_date is not None:
                        constituent_info['expiration_date'] = constituent.constituent.retest_date.strftime('%Y-%m-%d')
                    if constituent.constituent is not None:
                        pass
                    if constituent.include_checks:
                        constituent_info['checks'] = 'Yes'
                    else:
                        constituent_info['checks'] = 'No'
                elif constituent.reagent is not None:
                    constituent_info['lot'] = constituent.reagent.lot if constituent.reagent is not None else "-"
                    # constituent['in_use'] = constituent.constituent.in_use
                    constituent_info['in_use'] = constituent.reagent.in_use

                    if constituent.reagent.exp_date is not None:
                        constituent_info['expiration_date'] = constituent.reagent.exp_date.strftime('%Y-%m-%d')
                    else:
                        constituent_info['expiration_date'] = 'N/A'

                batch_info['constituents'].append(constituent_info.copy())

            for t in Tests.query.filter_by(batch_id=batch.id, test_status='Finalized').all():
                if t.case_id == Cases.query.get(item_id).id:
                    accession_numbers.append(t.specimen.accession_number)

                if batch.technique == 'Automated' and t.load_check != 'N/A' and t.load_check is not None:
                    t_load_check = (f'{t.load_check}\n'
                                    f'{t.load_checker.initials} '
                                    f'{t.load_checked_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.load_check == 'N/A':
                    t_load_check = 'N/A'
                else:
                    t_load_check = '-'

                # Set checks with relevant data
                if t.transfer_check is not None and t.transfer_check != 'N/A':
                    t_transfer_check = (f'{t.transfer_check}\n'
                                        f'{t.transfer_checker.initials} '
                                        f'{t.transfer_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.transfer_check == 'N/A':
                    t_transfer_check = 'N/A'
                else:
                    t_transfer_check = '-'

                if t.sequence_check is not None and t.sequence_check != 'N/A':
                    t_sequence_check = (f'{t.sequence_check}\n'
                                        f'{t.sequence_checker.initials} '
                                        f'{t.sequence_check_date.strftime("%Y-%m-%d %H:%M")}')
                elif t.sequence_check == 'N/A':
                    t_sequence_check = 'N/A'
                else:
                    t_sequence_check = '-'

                test_info = {
                    "status": t.test_status,
                    "name": t.test_name,
                    "id": t.test_id,
                    "dilution": t.dilution,
                    "assay": t.assay.assay_name if t.assay is not None else "N/A",
                    "case_num": t.case.case_number,
                    "accession_num": t.specimen.accession_number,
                    "specimen_type": t.specimen.type.code,
                    "test_order_date": t.create_date.strftime('%Y-%m-%d %H:%M') if t.create_date else '-',
                    "current_amount": t.specimen.current_sample_amount,
                    "original_amount": t.specimen.submitted_sample_amount,
                    "conditions": t.specimen.condition,
                    "priority": t.case.priority,
                    "current_location": t.specimen.custody,
                    "comments": ""
                }
                
                if t.case_id == item_id:
                    test_info['comments'] = [f'{comment.comment_text} - {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}' 
                                             if comment.comment_text is not None else f'{comment.comment.comment} {comment.created_by} {comment.create_date.strftime("%Y-%m-%d")}'
                                             for comment in CommentInstances.query.filter_by(comment_item_type='Tests', 
                                                                                             comment_item_id=t.id,
                                                                                             db_status='Active')]
                    if len(test_info['comments']) == 0:
                        test_info['comments'] = '-'
                else:
                    test_info['comments'] = '-'

                check_info = {
                    "check_test_id": t.test_name,
                    "spec_check": (
                            f"{t.specimen_check}\n"
                            f"{t.specimen_checker.initials if t.specimen_checker else ''} "
                            f"{t.checked_date.strftime('%Y-%m-%d %H:%M') if t.checked_date else ''}"
                        ).strip() if t.specimen_check else "-",
                    "hamilton_load_check": t_load_check,
                    "transfer_check": t_transfer_check,
                    "seq_check": t_sequence_check,
                }
                batch_info['tests'].append(test_info.copy())
                batch_info['checks'].append(check_info.copy())

            # checks = Tests.query.filter_by(batch_id=batch_id)
            # for check in checks:
            #     check_info = {
            #         "check_test_id": check.test_name,
            #         "spec_checked_by": "N/A",
            #         "hamilton_load_check": "N/A",
            #         "hamilton_load_checked_by": "N/A",
            #         "transfer_check_status": "N/A",
            #         "transfer_checked_by": "N/A",
            #         "seq_check_status": "N/A",
            #         "seq_checked_by": "N/A"
            #     }
            #     batch_info['checks'] = check_info

    data = {
        "batches": batch_data,
        "case_id": item_id
    }

    def get_unique_file_name(directory, file_name, extension):
        counter = 1
        unique_file_name = f"{file_name}.{extension}"
        while os.path.exists(os.path.join(directory, unique_file_name)):
            unique_file_name = f"{file_name} ({counter}).{extension}"
            counter += 1
        return unique_file_name

    # Step 1: Create or use the packet-specific folder
    packet_folder = os.path.join(current_app.root_path, 'static/filesystem/litigation_packets', packet_name)
    if not os.path.exists(packet_folder):
        os.makedirs(packet_folder)

    # Step 2: Save the DOCX and PDF files in the packet-specific folder
    case = Cases.query.get_or_404(item_id)
    # base_file_name = f"01 {case.case_number}_batch_details"
    # docx_file_name = get_unique_file_name(packet_folder, base_file_name, "docx")
    docx_file_name = f'{sort_order:02d}_{assay_ids}_00 Overview.docx'
    # pdf_file_name = get_unique_file_name(packet_folder, base_file_name, "pdf")
    pdf_file_name = f'{sort_order:02d}_{assay_ids}_00 Overview.pdf'

    docx_path = os.path.join(packet_folder, docx_file_name)
    pdf_path = os.path.join(packet_folder, pdf_file_name)

    doc.render(data, autoescape=True)
    doc.save(docx_path)

    pythoncom.CoInitialize()
    print(f'START CONVERT TO PDF')
    docx2pdf.convert(docx_path, pdf_path)
    print(f'END CONVERT TO PDF')

    # Remove the DOCX file - only keep the PDF
    try:
        os.remove(docx_path)
    except Exception as e:
        print(f"Failed to delete temporary Word document: {e}")

    if redact is False:
        redactor = Redactor(pdf_path, ignore_case_number=Cases.query.get_or_404(item_id).case_number,
                            ignore_accession_numbers=accession_numbers)
        redacted_path = redactor.redaction()
        shutil.move(redacted_path, pdf_path)
        print(f"Redacted file saved at {pdf_path}")


models = {
    'litigation_packets': LitigationPackets,
}


def ready_for_lp():
    return models['litigation_packets'].query.filter_by(packet_status='Ready for LP').all()


def ready_for_lr():
    return models['litigation_packets'].query.filter_by(packet_status='Ready for LR').all()


def html_to_richtext(html: str) -> RichText:
    """
    A simple HTML→RichText converter that handles:
      - <br>         → line break
      - <pagebreak>  → page break
      - <mark>...</mark> → yellow highlight
    """

    rt = RichText()

    # Split out the tags we care about (keep the tags in the result)
    parts = re.split(
        r'(<br>|<pagebreak>|<mark>.*?</mark>)',
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    for part in parts:
        if not part:
            continue
        low = part.lower()
        if low == '<br>':
            rt.add('\n', font='Arial', size=18) # line break
        elif low == '<pagebreak>':
            rt.add('\f', font='Arial', size=18)  # page break
        elif low.startswith('<mark>') and low.endswith('</mark>'):
            # strip the <mark> tags and highlight the inner text
            inner = re.sub(r'^<mark>(.*)</mark>$', r'\1', part, flags=re.IGNORECASE|re.DOTALL)
            rt.add(inner, highlight='#ffff00', font='Arial', size=18)
        else:
            # plain text
            rt.add(part, font='Arial', size=18)

    return rt
