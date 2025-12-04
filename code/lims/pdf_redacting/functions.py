import os
import shutil
import tempfile
from zipfile import ZipFile
from flask import send_file, current_app, flash, Markup
import fitz  # PyMuPDF
import re

from lims.litigation_packets.functions import generate_pdf_lit_two, generate_batches, Redactor
from lims.models import *
from lims.pdf_redacting.delete_pdf_page import extract_pages_without_patterns
# from pdf2image import convert_from_path
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import letter, landscape
from pypdf import PdfReader
import stat
# from app import com_lock

# class Redactor:
#     @staticmethod
#     def get_sensitive_data(text, ignore_case_number=None):
#         """ Function to get all the lines with the sensitive data patterns """
#         patterns = [
#             r"\b\d{4}-\d{4}\b",  # 0000-0000
#             r"\bD-\d{5}\b",  # D-00000
#             r"\bD[\-\u2010\u2011\u2012\u2013\u2014]\d{5}\b",
#             r"\bM-\d{5}\b",  # M-00000
#             r"\bX-\d{5}\b",  # X-00000
#             r"\bN-\d{4}\b",  # N-0000
#             r"\bB-\d{4}\b",  # B-0000
#             r"\bB-\d{5}\b",  # B-00000
#             r"\bQ-\d{4}\b",  # Q-0000
#             r"\b[A-Z]\d{5}\b",  # A00000
#             r"\b\d{4}-\d{4}_[A-Z]\d\b",  # 0000-0000_L1
#             r"\bD-\d{5}_[A-Z]\d\b",  # D-0000_L1
#             r"\bM-\d{5}_[A-Z]\d\b",  # M-00000_L1
#             r"\bX-\d{5}_[A-Z]\d\b",  # X-00000_L1
#             r"\bN-\d{5}_[A-Z]\d\b",  # N-0000_L1
#             r"\bB-\d{4}_[A-Z]\d\b",  # B-0000_L1
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
#         doc = fitz.open(self.path)
#
#         for page_num, page in enumerate(doc, start=1):
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
#
#             for data in sensitive_data:
#                 areas = page.search_for(data)
#
#                 for area in areas:
#                     # Add redaction annotation
#                     page.add_redact_annot(area, fill=(0, 0, 0))
#
#             page.apply_redactions()
#         save_path = os.path.join(os.path.dirname(self.path), f"redacted_{os.path.basename(self.path)}")
#         doc.save(save_path)
#         return save_path


def redact_multiple_pdfs(paths, ignore_case_number=None):
    redacted_paths = []
    for path in paths:
        redactor = Redactor(path, ignore_case_number)
        redacted_path = redactor.redaction()
        redacted_paths.append(redacted_path)
    return redacted_paths


def lit_packet_generation_templates(case_id, template_id, redact, packet_name, remove_pages, worker=False):
    from pdf2image import convert_from_path
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, landscape
    from pypdf import PdfReader

    case = Cases.query.get(case_id)
    case_name = case.case_number
    accession_numbers = [spec.accession_number for spec in Specimens.query.filter_by(case_id=case_id)]
    missing_files = []
    batch_ids = set()
    batch_names = set()
    full_batch_names = set()
    assays = set()
    found_files = []
    batch_records = {}
    admin_assays = [item.name for item in LitPacketAdminAssays.query.filter_by(lit_admin_template_id=template_id,
                                                                            overview_sheet='Yes')]

    assay_sort_orders = {
        assay.name: assay.lit_admin_sort_order for assay in LitPacketAdminAssays.query
    }

    file_sort_orders = {
        file.id: file.batch_record_sort_order for file in LitPacketAdminFiles.query
    }

    batch_files = {
        assay.name: [file.file_name for file in LitPacketAdminFiles.query.filter_by(lit_packet_admin_id=assay.id).all()]
        for assay in LitPacketAdminAssays.query
    }

    # Define your packet folder (final destination)
    packet_folder = os.path.join(current_app.root_path, r'static\filesystem\litigation_packets', packet_name)

    def force_remove_readonly(func, path,exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

    if os.path.exists(packet_folder):
        for filename in os.listdir(packet_folder):
            file_path = os.path.join(packet_folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path, onerror=force_remove_readonly)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

    if not os.path.exists(packet_folder):
        os.makedirs(packet_folder)

    # Collect batch IDs and assay names for the given case
    for test in Tests.query.filter_by(case_id=case_id):
        assays.add(test.assay.assay_name)
        if test.batch_id:
            batch_ids.add(test.batch_id)
        for batch in Batches.query.filter_by(id=test.batch_id):
            if batch.assay:
                batch_names.add(batch.assay.assay_name)
                if batch.assay.assay_name in admin_assays:
                    full_batch_names.add(batch.batch_id)

    print(full_batch_names)
    # Copy all batch record PDFs directly into the packet folder
    for batch_id in batch_ids:
        batch_records[batch_id] = []
        for batch_record in BatchRecords.query.filter_by(batch_id=batch_id, db_status='Active').all():
            if batch_record.file_path.endswith('.pdf'):
                save_file_path = os.path.join(packet_folder, os.path.basename(batch_record.file_path))
                try:
                    shutil.copy(batch_record.file_path, save_file_path)
                except Exception as e:
                    print(f"Failed to copy {batch_record.file_path}: {e}")

    # Process template files for redaction or page removal
    matched_file_names = set()  # to track matched files
    memo_count = 0
    for template in LitPacketAdminTemplates.query.filter_by(id=template_id):
        if template.case_contents is not None:
            # Generate case contents (case overview) page
            case_contents, warning_pdf = generate_pdf_lit_two(case_id, redact, packet_name)
            matched_file_names.add(case_contents.lower())
            if warning_pdf is not None:
                matched_file_names.add(warning_pdf.lower())
        for assay in LitPacketAdminAssays.query.filter_by(lit_admin_template_id=template.id):
            for file in LitPacketAdminFiles.query.filter_by(lit_packet_admin_id=assay.id):
                # Look for a matching file in the packet folder
                for file_name in os.listdir(packet_folder):
                    match_found = False
                    # Check if the file name from the database appears in the packet folder filename
                    if file.file_name.lower() in file_name.lower():
                        file_path = os.path.join(packet_folder, file_name)
                        # Verify that the assay name also matches
                        for batch_id in batch_ids:
                            batch = Batches.query.filter_by(id=batch_id).first()
                            memo_batch_records = [item.file_name.lower() for item in
                                                BatchRecords.query.filter_by(batch_id=batch_id).all()]
                            if batch and batch.assay.assay_name == assay.name and assay.name.lower() in \
                                    file_name.lower():
                                match_found = True
                                break
                            elif 'memo' in file_name.lower() and any('memo' in rec.lower() for rec
                                                                    in memo_batch_records) and \
                                    batch.assay.assay_name == assay.name and file_name.lower() in memo_batch_records:
                                match_found = True
                                break
                        if match_found:
                            if 'memo' in file_name.lower():
                                memo_count += 1
                                try:
                                    new_file_name = f'{assay_sort_orders[assay.name]:02d}_{batch.batch_id}_' \
                                                    f'{file_sort_orders[file.id]:02d}_{memo_count} Memo.pdf'
                                except TypeError:
                                    new_file_name = file_name
                            else:
                                split_file_name = file_name.split(' ')
                                new_file_name = f'{assay_sort_orders[assay.name]:02d}_{split_file_name[0]}_' \
                                                f'{file_sort_orders[file.id]:02d} {" ".join(split_file_name[1:])}'
                            batch_records[batch_id].append(file_name)
                            new_file_path = os.path.join(packet_folder, new_file_name)
                            matched_file_names.add(new_file_name.lower())
                            found_files.append(new_file_name.lower())
                            found_files.append(file_name.lower())
                            if redact is False and file.redact_type == 'Redact':
                                redactor = Redactor(file_path, ignore_case_number=case_name, ignore_accession_numbers=accession_numbers)
                                redacted_path = redactor.redaction()
                                # Move the redacted file back into the packet folder (overwriting the copy)
                                shutil.move(redacted_path, new_file_path)
                            elif remove_pages is False and file.redact_type == 'Delete Pages':
                                output_pdf = new_file_path
                                extract_pages_without_patterns(file_path, output_pdf, case_name)
                            else:
                                # If no redaction is needed, leave the file as-is.
                                pass
                        else:
                            if assay.name in assays:
                                missing_files.append(file_name)

    missing_files = [f for f in missing_files if f.lower() not in found_files]
    removed_files = []

    # After processing, remove any file in the packet folder that wasn't matched.
    for file_name in os.listdir(packet_folder):
        if file_name.lower() not in matched_file_names:
            try:
                removed_files.append(file_name)
                os.remove(os.path.join(packet_folder, file_name))
                # print(f"Removed unmatched file: {file_name}")
            except Exception as e:
                print(f"Failed to remove {file_name}: {e}")

        # Process attachments (if applicable)
        for attachment in LitPacketAdminAttachments.query.filter_by(lit_admin_template_id=template.id).all():
            attachment_type = AttachmentTypes.query.filter_by(name=attachment.attachment_type).first().id
            for a in Attachments.query.filter_by(table_name=attachment.route, type_id=attachment_type).all():
                if case_name in a.name:
                    if a.path.endswith('.pdf'):
                        if 'Evidence Envelope' in a.type.name:
                            save_file_path = os.path.join(packet_folder, f'0B_{a.name}')
                        elif 'Test Tube' in a.type.name:
                            save_file_path = os.path.join(packet_folder, f'0C_{a.name}')
                        else:
                            save_file_path = os.path.join(packet_folder, f'0Z_{a.name}')
                        try:
                            shutil.copy(a.path, save_file_path)
                            # print(f"Copied {a.path} to {save_file_path}")
                        except Exception as e:
                            print(f"Failed to copy {a.path}: {e}")

    # Call generate_batches and other functions as needed
    for batch in full_batch_names:
        generate_batches(case_id, batch, redact, packet_name)

    for attachment in Attachments.query.filter_by(table_name='Cases', record_id=case_id):
        redactor = Redactor(attachment.path, ignore_case_number=case_name)
        redacted_path = redactor.redaction()
        # Update name of redacted memo/attachment
        new_attachment_path = os.path.join(packet_folder, f"0Z_{attachment.name}")
        shutil.copy(redacted_path, new_attachment_path)

    # Process records folder files
    records_folder = os.path.join(current_app.root_path, r'static\filesystem\records', case_name)
    try:
        os.listdir(records_folder)
    except FileNotFoundError:
        os.makedirs(records_folder)
    for file_name in os.listdir(records_folder):
        new_file_name = f'00_{file_name}.pdf'
        source_path = os.path.join(records_folder, file_name)
        dest_path = os.path.join(packet_folder, new_file_name)
        if os.path.isfile(source_path):
            try:
                shutil.copy(source_path, dest_path)
            except Exception as e:
                print(f'Failed to copy {source_path}: {e}')


    def flatten_pdf_with_images(input_pdf, output_pdf):
        # Convert PDF pages to images
        images = convert_from_path(input_pdf, dpi=250)
        reader = PdfReader(input_pdf)

        # Use a temp file to write the output safely
        c = canvas.Canvas(output_pdf)

        for i, img in enumerate(images):
            # Get original page size and rotation
            page = reader.pages[i]
            media_box = page.mediabox
            width = float(media_box.width)
            height = float(media_box.height)
            rotation = page.get("/Rotate", 0)

            # Adjust for rotation (if 90 or 270, swap width/height)
            if rotation in [90, 270]:
                width, height = height, width

            # Determine correct page size
            if width > height:
                page_size = landscape(letter)
            else:
                page_size = letter

            # Set page size for canvas
            c.setPageSize(page_size)
            page_width, page_height = page_size

            # Draw the image stretched to page size
            c.drawInlineImage(img, 0, 0, width=page_width, height=page_height)
            c.showPage()

        c.save()

    zip_file_path = os.path.join(packet_folder, f'{packet_name}.zip')
    with ZipFile(zip_file_path, 'w') as zipf:
        for root, dirs, files in os.walk(packet_folder):
            for file in files:
                if file.endswith('.pdf') and file != os.path.basename(zip_file_path):

                    full_path = os.path.join(root, file) # overview

                    # Flatten PDF with images
                    flattened_path = os.path.join(root, f"flattened_{file}") # flatten_overview

                    if "Overview" not in file and "Case Contents" not in file:
                        flatten_pdf_with_images(full_path, flattened_path)
                        # Add flattened PDF to ZIP
                        zipf.write(flattened_path, arcname=file)
                        # os.remove(flattened_path)
                    else:
                        zipf.write(full_path, arcname=file)
                        # os.remove(full_path)

                   


    # Optional: Cleanup files (except the ZIP)
    for root, _, files in os.walk(packet_folder):
        for file in files:
            if file != os.path.basename(zip_file_path):
                os.remove(os.path.join(root, file))

    # MISSING FILES FLASH. TO BE UPDATED FOR DYNAMIC FILE NAME CHANGES
    # for file in removed_files:
    #     if file.lower() in found_files:
    #         missing_files.append(file)
    #
    # if missing_files:
    #     list_items = ''.join(f'<li>{file}</li>' for file in missing_files)
    #     if len(missing_files) == 1:
    #         flash(Markup(f'The following file is missing:<ul>{list_items}</ul>'), 'error')
    #     else:
    #         flash(Markup(f'The following files are missing:<ul>{list_items}</ul>'), 'error')

    if worker:
        
        return zip_file_path
    
    return send_file(zip_file_path, as_attachment=True, download_name=f"{case_name}_L1 (Draft).zip")
