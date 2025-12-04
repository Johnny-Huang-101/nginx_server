from flask import jsonify 
from sqlalchemy import and_, or_

from lims.models import *
from lims import app
from datetime import datetime
import os
import pythoncom
import docx2pdf
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import unicodeit
import sqlalchemy as sa
from sqlalchemy import case as sa_case
import pypdf
import glob
import shutil
from lims.queue import submit  

import re

from collections import defaultdict


# # Multi threading/processing
# try:
#     # from app import process_lock
#     process_lock = ""
# except (ImportError, RuntimeError):
#     # Fallback dummy lock so alembic migrations don't crash
#     class _NoopLock:
#         def __enter__(self): return self
#         def __exit__(self, *a): return False
#         def acquire(self, *a, **k): return True
#         def release(self): pass

#     process_lock = _NoopLock()


def get_form_choices(form, case_id=None, discipline=None, result_statuses=None):
    kwargs = {}

    if case_id:
        case = Cases.query.get(case_id)
        case_type = case.type.code

        # Discipline choices for the form
        discipline_choices = [(0, 'Please select a discipline')]
        for disc in disciplines:
            if hasattr(case, f"{disc.lower()}_performed") and getattr(case, f"{disc.lower()}_performed") == 'Yes':
                discipline_choices.append((disc, disc))
        form.discipline.choices = discipline_choices
        print(f'discpline == {discipline}')

        if discipline:
            # Report templates
            templates = [(t.id, t.name) for t in ReportTemplates.query.filter_by(discipline=discipline, db_status='Active', status_id=1)]
            templates.insert(0, (0, 'Please select a template'))
            attr = f"{discipline.lower()}_report_template_id"
            discipline_template = getattr(case.type, attr, 1)

            # Results for this case/discipline
            results = (
                Results.query.filter(Results.case_id == case_id)
                .join(Results.component)
                .outerjoin(Components.drug_class)
                .join(Results.test)
                .join(Tests.specimen)
                .join(Specimens.type)
                .join(Tests.batch)
                .join(Batches.assay)
                .outerjoin(ReportResults, ReportResults.result_id == Results.id)
                .filter(
                    or_(Specimens.discipline.contains(discipline),
                        SpecimenTypes.discipline.contains(discipline)),
                    Assays.discipline == discipline,
                    Results.db_status != 'Removed'
                )
                .order_by(ReportResults.order)
            )

            # Status filter (default)
            if result_statuses:
                results = results.filter(Results.result_status.in_(result_statuses))
            else:
                results = results.filter(Results.result_status.in_(['Confirmed', 'Saturated', 'Not Tested']))

            # UI ordering ONLY (doesn't affect official selection)
            if case_type == 'PM':
                results = results.order_by(Specimens.id, DrugClasses.pm_rank, Components.rank,
                                           Results.result_type.desc(), Batches.extraction_date.asc())
            elif case_type == 'X':
                results = results.order_by(Specimens.id, DrugClasses.x_rank, Components.rank,
                                           Results.result_type.desc(), Batches.extraction_date.asc())
            else:
                results = results.order_by(Specimens.id, DrugClasses.m_d_rank, Components.rank,
                                           Results.result_type.desc(), Batches.extraction_date.asc())

            results_list = list(results)

            # Build choices + collect for grouping
            result_choices = []
            supplementary_result_choices = []
            result_ids = []
            primary_result_ids = []
            supplementary_result_ids = []
            specimen_ids = []

            for r in results_list:
                result_choices.append((r.id, r.id))
                specimen_ids.append(r.test.specimen_id)
                if r.supplementary_result:
                    supplementary_result_choices.append((r.id, r.id))
                if r.result_status in ['Confirmed', 'Saturated', 'Not Tested']:
                    result_ids.append(r.id)

            # ---------- OFFICIAL PICK: use result.test.assay.assay_name ----------
            # Priority: SAMQ > LCQD > LCCI > LCFS > QTON
            FAMILY_RANK = {"SAMQ": 0, "LCQD": 1, "LCCI": 2, "LCFS": 3, "QTON": 4}

            def assay_name_from_result(row):
                try:
                    return (row.test.assay.assay_name or "").strip()
                except Exception:
                    return ""

            def assay_rank(row):
                name = assay_name_from_result(row).upper()
                # classify by prefix family; exact full name (e.g., 'LCQD-BL') is preserved for tie-breaks
                if name.startswith("SAMQ"):
                    fam = 0
                elif name.startswith("LCQD"):
                    fam = 1
                elif name.startswith("LCCI"):
                    fam = 2
                elif name.startswith("LCFS"):
                    fam = 3
                elif name.startswith("QTON"):
                    fam = 4
                else:
                    fam = 99
                # tie-break within same family by full assay string (stable but deterministic)
                return (fam, name)

            # group by (specimen, component)
            groups = {}
            for r in results_list:
                if r.result_status in ['Confirmed', 'Saturated', 'Not Tested']:
                    key = (r.test.specimen_id, r.component_name)
                    groups.setdefault(key, []).append(r)

            # choose best by assay_rank; ensures LCQD-* beats QTON-*
            for rows in groups.values():
                chosen = min(rows, key=assay_rank)
                primary_result_ids.append(chosen.id)
                if chosen.supplementary_result:
                    supplementary_result_ids.append(chosen.id)

            # Specimen ordering for the sidebar/table
            specimen_type_order = [195, 165, 196, 197, 181, 182, 180, 179, 178, 177, 198, 190, 200, 188, 184, 186, 187,
                                   189, 185, 203, 201, 202, 191, 199, 183, 166, 174, 176, 175, 173, 167, 172, 171, 170,
                                   169, 168, 194, 192, 193]
            case_ordering = sa_case(
                *[(Specimens.specimen_type_id == type_id, index) for index, type_id in enumerate(specimen_type_order)]
            )
            kwargs['specimens'] = (
                Specimens.query
                .filter(Specimens.id.in_(specimen_ids))
                .order_by(case_ordering)
            )

            # Pre-populate form values
            kwargs['result_id_order'] = ", ".join(map(str, result_ids))
            kwargs['result_id'] = result_ids
            kwargs['primary_result_id'] = primary_result_ids
            kwargs['supplementary_result_id'] = supplementary_result_ids
            kwargs['report_template_id'] = discipline_template

            # Form choices
            form.report_template_id.choices = templates
            form.result_id.choices = result_choices
            form.supplementary_result_id.choices = supplementary_result_choices
            form.primary_result_id.choices = result_choices
            form.observed_result_id.choices = result_choices
            form.qualitative_result_id.choices = result_choices
            form.approximate_result_id.choices = result_choices

        else:
            form.report_template_id.choices = [(0, 'No discipline selected')]
            form.result_id.choices = [(0, 'No discipline selected')]
            form.supplementary_result_id.choices = [(0, 'No discipline selected')]
            form.primary_result_id.choices = [(0, 'No discipline selected')]
            form.observed_result_id.choices = [(0, 'No discipline selected')]
            form.qualitative_result_id.choices = [(0, 'No discipline selected')]
            form.approximate_result_id.choices = [(0, 'No discipline selected')]

    else:
        form.report_template_id.choices = [(0, 'No case selected')]
        form.discipline.choices = [(0, 'No case selected')]
        form.result_id.choices = [(0, 'No case selected')]
        form.supplementary_result_id.choices = [(0, 'No case selected')]
        form.primary_result_id.choices = [(0, 'No case selected')]
        form.observed_result_id.choices = [(0, 'No case selected')]
        form.qualitative_result_id.choices = [(0, 'No case selected')]
        form.approximate_result_id.choices = [(0, 'No case selected')]

    cases = [(c.id, c.case_number) for c in Cases.query.order_by(Cases.id.desc())]
    cases.insert(0, (0, 'Please select a case'))
    form.case_id.choices = cases

    return form, kwargs



def get_disciplines(case_id):
    """
    Get the disciplines that were performed on the selected case

    """
    case = Cases.query.get(case_id)

    choices = []
    if case_id:
        for discipline in disciplines:
            if hasattr(case, f"{discipline.lower()}_performed") and getattr(case, f"{discipline.lower()}_performed") == 'Yes':
                choices.append({'id': discipline, 'name': discipline})

        if len(choices):
            choices.insert(0, {'id': 0, 'name': 'Please select a discipline'})
        else:
            choices.append({'id': 0, 'name': 'No disciplines performed for this case'})

    else:
        choices.append({'id': 0, 'name': 'No case selected'})

    return jsonify({'choices': choices})


def get_results(specimen_id, discipline=None, result_statuses=None, revise=None, report_id=None):
    """
    Build the rows for the specimen table. "Official" (default) is chosen by
    assay priority among selectable statuses, using result.test.assay.assay_name.
    Priority: SAMQ > LCQD > LCCI > LCFS > QTON.

    Additionally: LCCI rows NEVER show the supplementary checkbox as checked.
    """
    results_lst = []
    result_ids = []
    specimen = None
    other = None

    if not specimen_id:
        return {'results': results_lst, 'result_ids': result_ids, 'specimen': specimen, 'other': other}

    specimen = Specimens.query.get(specimen_id)
    if specimen.other_specimen is not None:
        other = specimen.other_specimen

    # Tests for this specimen/discipline
    tests = Tests.query.join(Assays).filter(Tests.specimen_id == specimen_id, Assays.discipline == discipline)
    if discipline:
        tests.filter(Assays.discipline == discipline)
    test_ids = [test.id for test in tests]

    # Results base query
    results_q = (Results.query.filter(Results.test_id.in_(test_ids))
        .join(Components)
        .outerjoin(DrugClasses)
        .join(Tests)
        .join(Batches)
        .filter(Results.db_status != 'Removed'))

    # Status filter (default)
    if result_statuses:
        results_q = results_q.filter(Results.result_status.in_(result_statuses))
    else:
        results_q = results_q.filter(Results.result_status.in_(['Confirmed', 'Saturated', 'Not Tested']))

    # Ordering for display
    case_type = Specimens.query.get(specimen_id).case.type.code
    if case_type == 'PM':
        results_q = results_q.order_by(DrugClasses.pm_rank, Components.rank, Batches.extraction_date.asc())
    elif case_type == 'X':
        results_q = results_q.order_by(DrugClasses.x_rank, Components.rank, Batches.extraction_date.asc())
    else:
        results_q = results_q.order_by(DrugClasses.m_d_rank, Components.rank, Batches.extraction_date.asc())

    # Group Biochemistry visually
    if discipline == 'Biochemistry':
        print('biochem === true')
        results_q = results_q.order_by(Results.component_name, Tests.test_id.asc())

    # Materialize once
    rows = list(results_q)

    # ---------------- OFFICIAL SELECTION BY ASSAY FAMILY ----------------
    def assay_name(row):
        try:
            return (row.test.assay.assay_name or "").strip()
        except Exception:
            return ""

    def assay_rank(row):
        name = assay_name(row).upper()
        if   name.startswith("SAMQ"): fam = 0
        elif name.startswith("LCQD"): fam = 1
        elif name.startswith("LCCI"): fam = 2
        elif name.startswith("LCFS"): fam = 3
        elif name.startswith("QTON"): fam = 4
        else:                         fam = 99
        return (fam, name)  # tie-break on full name deterministically

    selectable_statuses = {'Confirmed', 'Saturated', 'Not Tested'}
    chosen_official_by_component = {}
    for r in rows:
        if r.result_status not in selectable_statuses:
            continue
        comp = r.component_name
        if comp not in chosen_official_by_component:
            chosen_official_by_component[comp] = r
        else:
            if assay_rank(r) < assay_rank(chosen_official_by_component[comp]):
                chosen_official_by_component[comp] = r
    chosen_ids = {r.id for r in chosen_official_by_component.values()}
    # --------------------------------------------------------------------

    if rows:
        x = 0
        for item in rows:
            result_ids.append(item.id)
            x += 1
            report_as = ""
            supplementary = None

            # Respect explicit ReportResults first
            report_res = ReportResults.query.filter_by(result_id=item.id).first()
            if report_res:
                if report_res.primary_result == 'Y':
                    report_as = "Official"
                elif report_res.qualitative_result == 'Y':
                    report_as = 'Official (Qualitative)'
                elif report_res.observed_result == 'Y':
                    report_as = 'Observed'
                elif report_res.approximate_result == 'Y':
                    report_as = 'Approximate'
                if report_res.supplementary_result == 'Y' and item.component_name != 'Ethanol':
                    supplementary = 'checked'
            else:
                # Default: Official by assay priority pick
                if item.id in chosen_ids:
                    report_as = "Official"
                    # default supplementary for non-solvents only if there IS a supplementary value
                    if item.component_name not in ['Ethanol', 'Acetone', 'IPA', 'Methanol'] and item.supplementary_result:
                        supplementary = "checked"

            # >>> LCCI OVERRIDE: never show supplementary checked for LCCI assays
            try:
                if (item.test.assay.assay_name or "").upper().startswith("LCCI"):
                    supplementary = None
            except Exception:
                pass
            # <<< end override

            # Dilution display
            dilution = ""
            if item.test.dilution:
                if item.test.dilution.isnumeric():
                    if int(item.test.dilution) > 1:
                        dilution = f"d1/{item.test.dilution}"
                else:
                    dilution = item.test.dilution

            # Units
            unit = item.unit.name if item.unit else ""

            # Debug drug class string (unchanged)
            drug_class = ""
            if item.component.drug_class:
                if case_type == 'PM':
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.pm_rank})"
                elif case_type == 'X':
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.x_rank})"
                else:
                    drug_class = f"{item.component.drug_class.name} ({item.component.drug_class.m_d_rank})"

            results_lst.append({
                'n': x,
                'report_as': report_as,
                'supplementary': supplementary,
                'result_status': item.result_status,
                'component_name': item.component_name,
                'result': item.result,
                'supp_result': item.supplementary_result,
                'unit': unit,
                'assay': f'{item.test.assay.assay_name}',
                'test': item.test.test_id,
                'batch': item.test.batch.batch_id,
                'batch_date': item.test.batch.extraction_date.strftime('%m/%d/%Y'),
                'dilution': dilution,
                'component_rank': item.component.rank,
                'drug_class': drug_class,
                'id': item.id,
            })

    return {'results': results_lst, 'result_ids': result_ids, 'specimen': specimen, 'other': other}



def add_report_results(**kwargs):

    item = ReportResults(**kwargs)
    db.session.add(item)
    db.session.commit()

    return None


def add_report_comments(**kwargs):

    item = ReportComments(**kwargs)
    db.session.add(item)

    return None

# ****************************************************************************
# *********************** MULTI-PROCESSING STARTS HERE ***********************
# ****************************************************************************

#NO QUEUE YET

def gen_rep(case_id, discipline, report_id, template_path, report_name, file_name, report_status=None, cr=None, dr=None):

    print(f"Generating report....")
    doc = DocxTemplate(template_path)
    data = {}

    show_observed_findings = False
    report = Reports.query.filter_by(id=report_id).first()
    if not cr and not dr:
        case = Cases.query.get(case_id)
        if discipline == "External":
            containers = (
                Containers.query
                .join(Specimens, Specimens.container_id == Containers.id)
                .filter(
                    Containers.case_id == case.id,
                    Containers.db_status != 'Removed',
                    Specimens.discipline.contains("External")
                )
                .distinct()
                .order_by(Containers.create_date.asc())
                .all()
            )
        else:
            containers = (
                Containers.query
                .filter(
                    and_(
                        Containers.case_id == case.id,
                        Containers.discipline == discipline,
                        Containers.db_status != 'Removed'
                    )
                )
                .order_by(Containers.create_date.asc())
                .all()
            )


        if not containers:
            print('success')
            containers = (
                Containers.query
                .join(Specimens, Specimens.container_id == Containers.id)
                .filter(
                    and_(
                        Containers.case_id == case.id,
                        Containers.db_status != 'Removed',
                        Specimens.specimen_type_id.in_([201, 202, 203, 213])  # Check if any specimen in this container matches
                    )
                )
                .order_by(Containers.create_date.asc())
                .distinct()
                .all()
            )

        data['file_name'] = report_name
        data['report_name'] = report_name

        report_comments = CommentInstances.query.filter_by(
            comment_item_type='Reports',
            comment_item_id=report_id,
            db_status='Active'
        ).all()

        # this sets the specimen order by type. This is a list of IDs in order created by Anson
        specimen_type_order = [195, 165, 196, 197, 181, 182, 180, 179, 178, 177, 198, 190, 200, 188, 184, 186, 187,
                               189,
                               185, 203, 201, 202, 191, 199, 183, 166, 174, 176, 175, 173, 167, 172, 171, 170, 169,
                               168,
                               194, 192, 193]
        case_ordering = sa_case(
            *[(Specimens.specimen_type_id == type_id, index) for index, type_id in enumerate(specimen_type_order)]
            # Default order if specimen type is not in the list
        )

        module_comments = {}
        selected_specimen_comments = defaultdict(list)

        report_assay_comments = (
            db.session.query(ReportComments, CommentInstances)
            .join(CommentInstances, ReportComments.comment_id == CommentInstances.id)
            .filter(ReportComments.report_id == report_id)
            .all()
        )

        for report_comment, comment_instance in report_assay_comments:
            comment_text = (
                comment_instance.comment.comment
                if (comment_instance.comment and comment_instance.comment.comment)
                else comment_instance.comment_text
            )

            assay_name = None  # <- important: don't default to "Unknown Assay"

            if comment_instance.comment_item_type == "Tests":
                test = Tests.query.get(comment_instance.comment_item_id)
                if test and test.assay:
                    assay_name = test.assay.assay_name

            elif comment_instance.comment_item_type == "Specimens":
                # keep these ONLY at the specimen level
                specimen = Specimens.query.get(comment_instance.comment_item_id)
                if specimen:
                    selected_specimen_comments[specimen.id].append(comment_text)
                # do NOT add to module_comments here
                continue

            elif comment_instance.comment_item_type == "Containers":
                container = Containers.query.get(comment_instance.comment_item_id)
                if container:
                    # pick any specimen in that container to infer an assay (if any)
                    specimen = Specimens.query.filter_by(container_id=container.id).first()
                    if specimen:
                        test = Tests.query.filter_by(specimen_id=specimen.id).first()
                        if test and test.assay:
                            assay_name = test.assay.assay_name

            elif comment_instance.comment_item_type == "Batches":
                batch = Batches.query.get(comment_instance.comment_item_id)
                if batch:
                    test = Tests.query.filter_by(batch_id=batch.id).first()
                    if test and test.assay:
                        assay_name = test.assay.assay_name

            elif comment_instance.comment_item_type == "Assays":
                assay = Assays.query.get(comment_instance.comment_item_id)
                if assay:
                    assay_name = assay.assay_name

            # Only add to module_comments if we actually resolved an assay
            if assay_name:
                module_comments.setdefault(assay_name, []).append(comment_text)

        data['module_comments'] = [
            {"assay_name": a, "comments": cs} for a, cs in module_comments.items()
        ]

        am_specimen_ids = [195, 196, 197]

        # Format the comments into a list
        formatted_comments = [comment.comment_text for comment in report_comments if comment.comment_text]

        for container in containers:
            comment_added = False
            for specimen in Specimens.query.filter(Specimens.container_id == container.id).all():
                if specimen.type.id in am_specimen_ids:
                    # Check if n_specimens / n_specimens_submitted is not equal to 1
                    if container.n_specimens_submitted != 0:  # Prevent division by zero
                        ratio = container.n_specimens / container.n_specimens_submitted
                        if ratio != 1 and not comment_added:
                            formatted_comments.append("Most relevant antemortem case specimen(s) accessioned.")
                            comment_added = True
        for narrative in Narratives.query.filter_by(case_id=case_id).all():
            if "embalmed" in narrative.narrative.lower():  # Case-insensitive check for "test"
                formatted_comments.append("Decedent has been embalmed prior to case submission.")

        if discipline == 'External':
            formatted_comments.append("Protocol is outside the scope of accreditation.")
        elif discipline == 'Drug':
            formatted_comments.append("Validation of this protocol is not complete. Protocol is outside the scope of accreditation.")

        # Add formatted comments to data
        data['report_comments'] = formatted_comments


        # Case Details
        data['name'] = f"{case.last_name}, {case.first_name}"
        if case.middle_name:
            data['name'] += f" {case.middle_name}"
        data['case_number'] = case.case_number
        print(f'CONTAINERS == {containers}')
        if case.type.code == 'PM':
            name_parts = [
                case.pathologist.last_name,  # Last name
                ", ",  # Comma after last name
                case.pathologist.first_name  # First name
            ]

            # Add middle name only if it exists (no comma before middle name)
            if case.pathologist.middle_name:
                name_parts.append(f" {case.pathologist.middle_name}")

            # Convert list to string
            full_name = "".join(name_parts)

            # Add titles only if they exist
            if case.pathologist.titles:
                data['submitter'] = f"{full_name}, {case.pathologist.titles}"
            else:
                data['submitter'] = full_name  # No trailing comma if no titles
        elif containers[0].submitter:
            # data['submitter'] = f"{containers[0].submitter.last_name}, {containers[0].submitter.first_name}"
            data['submitter'] = containers[0].submitter.agency.abbreviation  # Only for HP cases. Need to update
        data['submission_datetime'] = f"{containers[0].submission_date.strftime('%m/%d/%Y')} {containers[0].submission_time} hrs"
        if case.submitter_case_reference_number:
            data['submitter_ref'] = case.submitter_case_reference_number
        else:
            data['submitter_ref'] = "N/A"

        data['report_date'] = datetime.now().strftime("%m/%d/%Y")

        # Build a single list across all containers
        data['specimens'] = []

        for container in containers:
            specimen_rows = (
                Specimens.query
                .filter_by(container_id=container.id)
                .order_by(Specimens.accession_number.asc())
            )

            for spec in specimen_rows:
                specimen = {}
                specimen['specimen'] = f"[{spec.type.code}] {spec.type.name} ({spec.accession_number})"

                lines_out = []
                seen = set()

                def clean_display(s: str) -> str:
                    """Remove leading code like '51C-5:' and bullets; trim spaces."""
                    s = s.strip()
                    # drop starting bullet or dash
                    s = re.sub(r'^[\-\u2022]\s*', '', s)
                    # strip a leading label like '51C-5:' or 'ABC_12:' etc.
                    s = re.sub(r'^\s*[\w\-\/]+:\s*', '', s)
                    return s.strip()

                def norm_key(s: str) -> str:
                    """Normalization used only for de-dup keys."""
                    s = clean_display(s)
                    s = re.sub(r'\s+', ' ', s).strip().lower()
                    return s

                def add_line(s: str):
                    if not s:
                        return
                    disp = clean_display(str(s))
                    if not disp:
                        return
                    key = norm_key(disp)
                    if key not in seen:
                        seen.add(key)
                        lines_out.append(disp)

                # 1) Specimens.evidence_comments (may be multi-line)
                if spec.evidence_comments:
                    for piece in str(spec.evidence_comments).splitlines():
                        add_line(piece)

                # 2) EvidenceComments rows for this accession
                for ev in EvidenceComments.query.filter(
                    EvidenceComments.accession_number == spec.accession_number
                ):
                    add_line(ev.statement)

                # 3) Selected specimen-level ReportComments for THIS report
                for txt in selected_specimen_comments.get(spec.id, []):
                    add_line(txt)

                specimen['evidence_comments'] = " ".join(lines_out) if lines_out else ""
                specimen['evidences'] = [{'comment': t} for t in lines_out]

                data['specimens'].append(specimen)


        # Containers and Specimens
        data['containers'] = []

        for cont in containers:
            container = {}
            container['type'] = f"[{cont.type.code.strip('#')}] {cont.type.name}"
            if cont.evidence_comments and ":" in cont.evidence_comments:
                container['evidence_comments'] = cont.evidence_comments.split(":", 1)[1].strip()
            else:
                container['evidence_comments'] = ""
            container['evidences'] = []
            if cont.accession_number:
                container['accession_number'] = cont.accession_number
                evidence_comments = EvidenceComments.query.filter(EvidenceComments.accession_number == cont.accession_number)
                for evidence_comment in evidence_comments:
                    evidence = {}
                    evidence['comment'] = evidence_comment.statement
                    container['evidences'].append(evidence)
            else:
                container['accession_number'] = ""

            container['submission_datetime'] = f"{cont.submission_date.strftime('%m/%d/%Y')} {cont.submission_time} hrs"
            container['specimens'] = []

            for spec in Specimens.query.join(SpecimenTypes).filter(
                            Specimens.container_id == cont.id,
                            or_(
                                Specimens.discipline.contains(discipline),
                                SpecimenTypes.discipline.contains(discipline)
                            ),
                            Specimens.db_status != 'Removed'
                        ).order_by(Specimens.accession_number.asc()):
                specimen = {}
                specimen['evidence_comments'] = spec.evidence_comments
                if spec.other_specimen:
                    specimen['type'] = f'{spec.type.name} ({spec.other_specimen})'
                else:
                    specimen['type'] = spec.type.name
                specimen['code'] = spec.type.code
                liquid_specimens = [195, 165, 196, 197, 181, 182, 180, 179, 178, 177, 198, 190, 200, 188, 184, 186, 187,
                                    189, 185, 203, 201, 202, 191, 199, 183, 166, 174, 176, 175, 173]
                if spec.type.id in liquid_specimens and 'Gastrointestinal' not in spec.type.name:
                    if spec.submitted_sample_amount > 1:
                        specimen['amount'] = int(spec.submitted_sample_amount)
                    else:
                        specimen['amount'] = "< 1.0"
                else:
                    specimen['amount'] = ''
                specimen['accession_number'] = spec.accession_number
                if spec.type.id in [195, 196, 197]:
                    if spec.collection_date is None and spec.collection_time is None:
                        specimen['collection_datetime'] = 'No date. No time.'
                    elif spec.collection_date is None:
                        specimen['collection_datetime'] = f"No date. {spec.collection_time} hrs"
                    elif spec.collection_time is None:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} No time."
                    else:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} {spec.collection_time} hrs"
                elif spec.case.type.code == 'Q':
                    if spec.collection_date is None and spec.collection_time is None:
                        specimen['collection_datetime'] = 'No date. No time.'
                    elif spec.collection_date is None:
                        specimen['collection_datetime'] = f"No date. {spec.collection_time} hrs"
                    elif spec.collection_time is None:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} No time."
                    else:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} {spec.collection_time} hrs"
                else:
                    if spec.collection_date is None and spec.collection_time is None:
                        specimen['collection_datetime'] = 'No date. No time.'
                    elif spec.collection_date is None:
                        specimen['collection_datetime'] = f"No date. {spec.collection_time} hrs"
                    elif spec.collection_time is None:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} No time."
                    else:
                        specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} {spec.collection_time} hrs"
                if spec.collection_container.name != 'gray top' and spec.collection_container.name != 'red top':
                    if spec.condition:
                        specimen['condition'] = \
                            f'{spec.condition}, ' \
                            f'{spec.collection_container.display_name if spec.collection_container and spec.collection_container.display_name != "Other" else ""}'.strip()
                    else:
                        specimen['condition'] = \
                            f'{spec.collection_container.display_name if spec.collection_container and spec.collection_container.display_name != "Other" else ""}'.strip()
                else:
                    if spec.condition:
                        specimen['condition'] = spec.condition
                specimen['descriptors'] = f'{spec.condition} {spec.other_specimen}' if spec.other_specimen is not None \
                    else spec.condition
                protocols = []
                tests = (
                    Tests.query.join(Assays).
                    filter(Tests.specimen_id == spec.id,
                    Tests.test_status == 'Finalized',
                    Assays.discipline == discipline)
                    # .join(Results)
                    # .join(ReportResults)
                )
                for item in tests:
                    assay = item.assay.assay_name
                    protocols.append(assay)

                sorted_protocols = sorted(set(protocols))

                # checks if LCCI-BL and LCQD-BL are present and places LCCI-BL after LCQD-BL
                if "LCQD-BL" in sorted_protocols and "LCCI-BL" in sorted_protocols:
                    sorted_protocols.remove("LCCI-BL")
                    index = sorted_protocols.index("LCQD-BL")
                    sorted_protocols.insert(index + 1, "LCCI-BL")

                specimen['protocols'] = ", ".join(sorted_protocols)



                container['specimens'].append(specimen)
            data['containers'].append(container)

        # Results
        specimens = Specimens.query.filter_by(case_id=case.id).order_by(case_ordering)
        results = ReportResults.query.filter_by(report_id=report_id). \
            join(Results). \
            join(Tests). \
            join(Specimens).order_by(case_ordering, ReportResults.order)

        # results = ReportResults.query.filter_by(report_id=report_id).order_by(ReportResults.order)
        #data['results'] = []
        data['confirmed_results'] = []
        data['confirmed_comments'] = []
        data['observed_findings'] = []
        data['observed_comments'] = []

        for specimen in specimens:
            confirmed_result_dict = {}
            observed_result_dict = {}

            confirmed_result_dict['specimen_results'] = []
            observed_result_dict['specimen_results'] = []

            # Get confirmed comments
            confirmed_comments = {}
            confirmed_comments['specimen'] = f"[{specimen.type.code}] {specimen.type.name} ({specimen.accession_number})"
            confirmed_comments['comments'] = []

            confirmed_results = results.filter(Specimens.id == specimen.id, ReportResults.observed_result == None).order_by(ReportResults.primary_result.desc())
            if confirmed_results.count():
                for res in confirmed_results:
                    if res.primary_result or res.qualitative_result:
                        result = {}
                        if res.result.test.specimen.other_specimen:
                            result['type'] = f'{res.result.test.specimen.type.name} ({res.result.test.specimen.other_specimen})'
                        else:
                            result['type'] = res.result.test.specimen.type.name
                        result['code'] = res.result.test.specimen.type.code
                        result['accession_number'] = res.result.test.specimen.accession_number
                        result['component'] = res.result.component_name

                        # if the result is the official result, the printed result is simply the result. Else the result
                        # is forced qualitative (i.e. Official (Qualitative)), the printed result is the LOD of the scope
                        # component multiplied by the dilution factor
                        result['result'] = ""
                        if res.primary_result:
                            if res.result.result_status == 'Not Tested' and res.result.component_name != "None Tested":
                                result['result'] = res.result.result_status
                            elif res.result.result:
                                result['result'] = res.result.result
                        else:
                            lod = float(res.result.scope.limit_of_detection)
                            dilution = res.result.test.dilution
                            if dilution:
                                try:
                                    lod = float(dilution)*lod
                                except:
                                    pass

                            result['result'] = f"\u2265 {lod}"

                        result['unit'] = ""
                        if res.result.unit:
                            result['unit'] = res.result.unit.name
                        comp_res = confirmed_results.filter(Results.component_name == res.result.component_name)
                        protocols = [item.result.test.assay.assay_name for item in comp_res]
                        sorted_protocols = sorted(protocols)
                        # this checks if the result is from a PM case - then it puts all LCQD-BL protocols first
                        if res.result.case.type.code == 'PM':
                            lcqd_bl_items = [p for p in sorted_protocols if p == "LCQD-BL" or p == "LCQD-UR"]
                            lcfs_bl_items = [p for p in sorted_protocols if p == "LCFS-BL" or p == "LCFS-UR"]
                            other_items = [p for p in sorted_protocols if
                                           p != "LCQD-BL" and p != "LCQD-UR" and p != "LCFS-UR" and p != "LCFS-BL"]

                            sorted_protocols = lcqd_bl_items + lcfs_bl_items + other_items
                        result['protocols'] = ", ".join(sorted_protocols)
                        confirmed_result_dict['specimen_results'].append(result)

                data['confirmed_results'].append(confirmed_result_dict)

            supplementary_results = confirmed_results.filter(ReportResults.supplementary_result != None)
            component_results = {}
            if supplementary_results.count():
                approximate_results_str = "Approximate result(s): "

                for res in supplementary_results:
                    component_name = res.result.component_name
                    supplementary_result = res.result.supplementary_result

                    unit_name = ''
                    if res.result.unit:
                        unit_name = res.result.unit.name
                    elif res.result.scope:
                        unit_name = res.result.scope.unit.name

                    if component_name in component_results:
                        component_results[component_name].append(f"{supplementary_result} {unit_name}")
                    else:
                        component_results[component_name] = [f"{supplementary_result} {unit_name}"]

                # formatted_results = [f"{component} {', '.join(results)}" for component, results in component_results.items()]
                # approximate_results_str += ", ".join(formatted_results)

                # confirmed_comments['comments'].append(approximate_results_str)

                # approximate_results = [f"{res.result.component.name} {res.result.supplementary_result} {res.result.scope.unit.name}" for res in approximate_results]
                # approximate_results_str += ", ".join(approximate_results)
                # confirmed_comments['comments'].append(approximate_results_str)

            qualitative_results = confirmed_results.filter(ReportResults.qualitative_result != None)

            if qualitative_results.count():

                qualitative_results_list = {}

                for q in qualitative_results:

                    q_component_name = q.result.component_name
                    q_result = q.result.result.split(" ")[0]
                    q_unit_name = q.result.scope.unit.name

                    if q_component_name in component_results:
                        component_results[q_component_name].append(f"{q_result} {q_unit_name}")
                    else:
                        component_results[q_component_name] = [f"{q_result} {q_unit_name}"]

                    # q_formatted_results = [f"{component} {', '.join(results)}" for component, results in qualitative_results_list.items()]
                    # confirmed_comments['comments'].append(", ".join(q_formatted_results))

            approximate_results = confirmed_results.filter(ReportResults.approximate_result != None)

            if approximate_results:

                approximate_result_list = {}

                for a in approximate_results:

                    a_component_name = a.result.component_name
                    a_result = a.result.result.split(" ")[0]
                    a_unit_name = a.result.scope.unit.name

                    if a_component_name in component_results:
                        component_results[a_component_name].append(f"{a_result} {a_unit_name}")
                    else:
                        component_results[a_component_name] = [f"{a_result} {a_unit_name}"]

            if component_results:
                formatted_results = [f"{component} {', '.join(results)}" for component, results in component_results.items()]
                approximate_results_str = "Approximate result(s): " + ", ".join(formatted_results)

                # Update confirmed_comments['comments'] as a single entry
                confirmed_comments['comments'] = [approximate_results_str]

            # Only add specimen comments if there have been comments added
            if confirmed_comments['comments']:
                data['confirmed_comments'].append(confirmed_comments)

            # Observed findings
            observed_findings = results.filter(Specimens.id == specimen.id,  sa.or_(ReportResults.observed_result == 'Y', ReportResults.primary_result == None))

            # Observed comments
            observed_comments = {}
            observed_comments['specimen'] = f"[{specimen.type.code}] {specimen.type.name} ({specimen.accession_number})"
            observed_comments['comments'] = []

            if observed_findings.filter(ReportResults.observed_result == 'Y').count():
                show_observed_findings = True
                for res in observed_findings:
                    if res.observed_result or res.qualitative_result:
                        result = {}
                        if res.result.test.specimen.other_specimen:
                            result['type'] = f'{res.result.test.specimen.type.name} ({res.result.test.specimen.other_specimen})'
                        else:
                            result['type'] = res.result.test.specimen.type.name
                        result['code'] = res.result.test.specimen.type.code
                        result['accession_number'] = res.result.test.specimen.accession_number
                        result['component'] = res.result.component_name

                        # if the result is the official result, the printed result is simply the result. Else the result
                        # is forced qualitative (i.e. Official (Qualitative)), the printed result is the LOD of the scope
                        # component multiplied by the dilution factor
                        if res.observed_result:
                            result['result'] = res.result.result
                        else:
                            lod = float(res.result.scope.limit_of_detection)
                            dilution = res.result.test.dilution
                            if dilution:
                                try:
                                    lod = float(dilution)*lod
                                except:
                                    pass

                            result['result'] = f"\u2265 {lod}"

                        result['unit'] = ""
                        if res.result.unit:
                            result['unit'] = res.result.unit.name
                        comp_res = observed_findings.filter(Results.component_name == res.result.component_name)
                        protocols = ", ".join(sorted([item.result.test.assay.assay_name for item in comp_res]))
                        result['protocols'] = protocols
                        observed_result_dict['specimen_results'].append(result)

                data['observed_findings'].append(observed_result_dict)

            approximate_results = observed_findings.filter(ReportResults.observed_result == 'Y',
                                                           ReportResults.supplementary_result != None)

            if approximate_results.count():
                approximate_results_str = "Approximate result(s): "
                approximate_results = [
                    f"{res.result.component.name} {res.result.supplementary_result} {res.result.scope.unit.name}" for
                    res in approximate_results]
                approximate_results_str += ", ".join(approximate_results)
                observed_comments['comments'].append(approximate_results_str)

            # Only add specimen comments if there have been comments added
            if observed_comments['comments']:
                data['observed_comments'].append(observed_comments)

        data['show_observed_findings'] = show_observed_findings

    if report_status == 'Finalized':
        data['report_status'] = 'Finalized'
    if cr:
        cr_user = Users.query.get(cr)
        data['cr_sig'] = InlineImage(doc, image_descriptor=os.path.join(app.config['FILE_SYSTEM'], "signatures",
                                                                        f"{cr_user.initials}.png"),
                                     width=Mm(20), height=Mm(10))
        data['cr'] = ", ".join(filter(lambda x: x != None, [cr_user.full_name, cr_user.title]))
        data['cr_job_title'] = cr_user.job_title
        data['cr_date'] = datetime.now().strftime("%m/%d/%Y %H:%M")
        data['footer'] = file_name
    else:
        data['cr_sig'] = "{{cr_sig}}"
        data['cr'] = "{{cr}}"
        data['cr_job_title'] = "{{cr_job_title}}"
        data['cr_date'] = "{{cr_date}}"
    if dr:
        dr_user = Users.query.get(dr)
        data['dr_sig'] = InlineImage(doc, image_descriptor=os.path.join(app.config['FILE_SYSTEM'], "signatures",
                                                                        f"{dr_user.initials}.png"),
                                     width=Mm(20), height=Mm(10))

        data['dr'] = ", ".join(filter(lambda x: x != None, [dr_user.full_name, dr_user.title]))
        data['dr_job_title'] = dr_user.job_title
        data['dr_date'] = datetime.now().strftime("%m/%d/%Y %H:%M")
        data['file_name'] = file_name
        data['report_status'] = report.report_status
        # for section in doc.sections:
        #     footer = section.footer
        #
        #     for paragraph in footer.parahraphs:
        #         if "(DRAFT)" in paragraph.text:
        #             paragraph.text = paragraph.text.replace(" (DRAFT)", "")

    else:
        data['dr_sig'] = "{{dr_sig}}"
        data['dr'] = "{{dr}}"
        data['dr_job_title'] = "{{dr_job_title}}"
        data['dr_date'] = "{{dr_date}}"

    path = os.path.join(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}.docx"))
    # print('Results: ', data['confirmed_results'])
    doc.render(data, autoescape=True)
    doc.save(path)
    pdf_path = os.path.join(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}.pdf"))

    #doc.save(os.path.join(app.config['FILE_SYSTEM_PRIVATE'], f'Reports\{case.case_number_full}_T1.docx'))
    # pythoncom.CoUninitialize()
    # pythoncom.CoInitialize()
    docx2pdf.convert(path, pdf_path)

    if dr:
        case = Cases.query.get(case_id)
        report = Reports.query.get(report_id)
        created_by = Users.query.get(int(dr)).initials

        # copy the finalized PDF to records
        pdf_path = os.path.join(app.config['FILE_SYSTEM'], 'reports', f'{file_name}.pdf')
        case_folder = os.path.join(app.config['FILE_SYSTEM'], 'records', case.case_number)
        os.makedirs(case_folder, exist_ok=True)
        record_path = os.path.join(case_folder, f'{file_name}.pdf')

        shutil.copy(pdf_path, record_path)

        docx = glob.glob(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}*.docx"))
        for doc in docx:
            os.remove(doc)

        pdfs = glob.glob(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name} (DRAFT*.pdf"))
        for pdf in pdfs:
            os.remove(pdf)

        record_type_id = RecordTypes.query.filter_by(name=f'{discipline} Report').first().id
        record = Records(
            case_id=case.id,
            record_name=report_name,
            record_type=record_type_id,
            create_date=datetime.now(),
            created_by=created_by,
            db_status='Active',
            locked=False,
            pending_submitter=None,
            revision=0,
            record_number=report.report_number
        )
        db.session.add(record)
        db.session.flush()
        reports = Reports.query.filter_by(report_name=report_name)
        for r in reports:
            r.record_id = record.id
        db.session.commit()

    results_all = Results.query.filter_by(case_id=case_id).all()
    pdf_attachments = []

    for result in results_all:
        attachments = Attachments.query.filter_by(table_name="results", record_id=result.id).all()
        for attachment in attachments:
            if attachment.path and attachment.path.lower().endswith('.pdf'):
                full_path = os.path.join(app.config['FILE_SYSTEM'], attachment.path)
                if os.path.exists(full_path):
                    pdf_attachments.append(full_path)


    if pdf_attachments:
        merged_pdf_path = pdf_path

        with open(pdf_path, "rb") as base_pdf:
            pdf_merger = pypdf.PdfMerger()
            pdf_merger.append(base_pdf)

            for attachment in pdf_attachments:
                with open(attachment, "rb") as attach_pdf:
                    pdf_merger.append(attach_pdf)

            temp_pdf_path = os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}_temp.pdf")
            with open(temp_pdf_path, "wb") as merged_file:
                pdf_merger.write(merged_file)

        os.remove(pdf_path)

        os.rename(temp_pdf_path, pdf_path)

    # pythoncom.CoUninitialize()

    return None

def generate_report(case_id, discipline, report_id, template_path, report_name, file_name, cr=None, dr=None):
    """
    Enqueue report generation with HIGH priority (reports first).
    Returns a concurrent.futures.Future compatible with your /check_report_status.
    """
    return submit(
        "lims.reports.functions:gen_rep_worker",  # wrapper below
        priority=0,                               # <-- highest priority
        case_id=case_id,
        discipline=discipline,
        report_id=report_id,
        template_path=template_path,
        report_name=report_name,
        file_name=file_name,
        cr=cr,
        dr=dr,
    )

def gen_rep_worker(case_id, discipline, report_id, template_path, report_name, file_name, cr=None, dr=None):
    """
    Runs inside the queue worker process. Gives DB/app context to gen_rep.
    """
    with app.app_context():
        # gen_rep is your existing function that actually builds the docx/pdf
        return gen_rep(case_id, discipline, report_id, template_path, report_name, file_name,
                       report_status=None, cr=cr, dr=dr)



















# -=-=-=-=- ORIGINAL FUNCTION -=-=-=-=-

# def generate_report(case_id, discipline, report_id, template_path, report_name, file_name, report_status=None, cr=None, dr=None):

#     doc = DocxTemplate(template_path)
#     data = {}

#     show_observed_findings = False
#     report = Reports.query.filter_by(id=report_id).first()
#     if not cr and not dr:
#         case = Cases.query.get(case_id)
#         containers = (
#             Containers.query
#             .filter(
#                 and_(
#                     Containers.case_id == case.id,
#                     Containers.discipline == discipline,
#                     Containers.db_status != 'Removed'
#                 )
#             )
#             .order_by(Containers.create_date.asc())
#             .all()
#         )

#         if not containers:
#             print('success')
#             containers = (
#                 Containers.query
#                 .join(Specimens, Specimens.container_id == Containers.id)
#                 .filter(
#                     and_(
#                         Containers.case_id == case.id,
#                         Containers.db_status != 'Removed',
#                         Specimens.specimen_type_id.in_([201, 202, 203, 213])  # Check if any specimen in this container matches
#                     )
#                 )
#                 .order_by(Containers.create_date.asc())
#                 .distinct()
#                 .all()
#             )



#         data['file_name'] = report_name
#         data['report_name'] = report_name

#         report_comments = CommentInstances.query.filter_by(
#             comment_item_type='Reports',
#             comment_item_id=report_id
#         ).all()

#         # this sets the specimen order by type. This is a list of IDs in order created by Anson
#         specimen_type_order = [195, 165, 196, 197, 181, 182, 180, 179, 178, 177, 198, 190, 200, 188, 184, 186, 187,
#                                189,
#                                185, 203, 201, 202, 191, 199, 183, 166, 174, 176, 175, 173, 167, 172, 171, 170, 169,
#                                168,
#                                194, 192, 193]
#         case_ordering = sa_case(
#             *[(Specimens.specimen_type_id == type_id, index) for index, type_id in enumerate(specimen_type_order)]
#             # Default order if specimen type is not in the list
#         )

#         # Dictionary to store comments grouped by Assay
#         module_comments = {}

#         # Fetch all ReportComments specifically for assay-related comments
#         report_assay_comments = db.session.query(ReportComments, CommentInstances).join(
#             CommentInstances, ReportComments.comment_id == CommentInstances.id
#         ).filter(
#             ReportComments.report_id == report_id
#         ).all()

#         # Loop through each comment instance and determine its related assay
#         for report_comment, comment_instance in report_assay_comments:
#             assay_name = "Unknown Assay"  # Default if no assay is found
#             comment_text = comment_instance.comment.comment if comment_instance.comment and comment_instance.comment.comment else comment_instance.comment_text
#             # Identify the table where the comment originated and fetch related assay
#             if comment_instance.comment_item_type == "Tests":
#                 test = Tests.query.get(comment_instance.comment_item_id)
#                 if test and test.assay:
#                     assay_name = test.assay.assay_name

#             elif comment_instance.comment_item_type == "Specimens":
#                 specimen = Specimens.query.get(comment_instance.comment_item_id)
#                 if specimen:
#                     test = Tests.query.filter_by(specimen_id=specimen.id).first()
#                     if test and test.assay:
#                         assay_name = test.assay.assay_name

#             elif comment_instance.comment_item_type == "Containers":
#                 container = Containers.query.get(comment_instance.comment_item_id)
#                 if container:
#                     specimen = Specimens.query.filter_by(container_id=container.id).first()
#                     if specimen:
#                         test = Tests.query.filter_by(specimen_id=specimen.id).first()
#                         if test and test.assay:
#                             assay_name = test.assay.assay_name

#             elif comment_instance.comment_item_type == "Batches":
#                 batch = Batches.query.get(comment_instance.comment_item_id)
#                 if batch:
#                     test = Tests.query.filter_by(batch_id=batch.id).first()
#                     if test and test.assay:
#                         assay_name = test.assay.assay_name

#             elif comment_instance.comment_item_type == "Assays":
#                 assay = Assays.query.get(comment_instance.comment_item_id)
#                 if assay:
#                     assay_name = assay.assay_name

#             # Store comment in the dictionary under the appropriate assay
#             if assay_name not in module_comments:
#                 module_comments[assay_name] = []
#             module_comments[assay_name].append(comment_text)

#         # Format data for the template
#         data['module_comments'] = [
#             {"assay_name": assay_name, "comments": comments}
#             for assay_name, comments in module_comments.items()
#         ]

#         am_specimen_ids = [195, 196, 197]

#         # Format the comments into a list
#         formatted_comments = [comment.comment_text for comment in report_comments if comment.comment_text]

#         for container in containers:
#             comment_added = False
#             for specimen in Specimens.query.filter(Specimens.container_id == container.id).all():
#                 if specimen.type.id in am_specimen_ids:
#                     # Check if n_specimens / n_specimens_submitted is not equal to 1
#                     if container.n_specimens_submitted != 0:  # Prevent division by zero
#                         ratio = container.n_specimens / container.n_specimens_submitted
#                         if ratio != 1 and not comment_added:
#                             formatted_comments.append("Most relevant antemortem case specimen(s) accessioned.")
#                             comment_added = True
#         for narrative in Narratives.query.filter_by(case_id=case_id).all():
#             if "embalmed" in narrative.narrative.lower():  # Case-insensitive check for "test"
#                 formatted_comments.append("Decedent has been embalmed prior to case submission.")

#         # Add formatted comments to data
#         data['report_comments'] = formatted_comments

#         # Case Details
#         data['name'] = f"{case.last_name}, {case.first_name}"
#         if case.middle_name:
#             data['name'] += f" {case.middle_name}"
#         data['case_number'] = case.case_number
#         print(f'CONTAINERS == {containers}')
#         if case.type.code == 'PM':
#             name_parts = [
#                 case.pathologist.last_name,  # Last name
#                 ", ",  # Comma after last name
#                 case.pathologist.first_name  # First name
#             ]

#             # Add middle name only if it exists (no comma before middle name)
#             if case.pathologist.middle_name:
#                 name_parts.append(f" {case.pathologist.middle_name}")

#             # Convert list to string
#             full_name = "".join(name_parts)

#             # Add titles only if they exist
#             if case.pathologist.titles:
#                 data['submitter'] = f"{full_name}, {case.pathologist.titles}"
#             else:
#                 data['submitter'] = full_name  # No trailing comma if no titles
#         elif containers[0].submitter:
#             # data['submitter'] = f"{containers[0].submitter.last_name}, {containers[0].submitter.first_name}"
#             data['submitter'] = containers[0].submitter.agency.abbreviation  # Only for HP cases. Need to update
#         data['submission_datetime'] = f"{containers[0].submission_date.strftime('%m/%d/%Y')} {containers[0].submission_time} hrs"
#         if case.submitter_case_reference_number:
#             data['submitter_ref'] = case.submitter_case_reference_number
#         else:
#             data['submitter_ref'] = "N/A"

#         data['report_date'] = datetime.now().strftime("%m/%d/%Y")

#         for container in containers:
#             specimen_evidence_comments = Specimens.query.filter_by(container_id=container.id).order_by(Specimens.accession_number.asc())
#             data['specimens'] = []

#             for spec in specimen_evidence_comments:
#                 specimen = {}
#                 evidence_comments = EvidenceComments.query.filter(
#                     EvidenceComments.accession_number == spec.accession_number)
#                 specimen['evidences'] = []
#                 if spec.evidence_comments:
#                     specimen['specimen'] = f"[{spec.type.code}] {spec.type.name} ({spec.accession_number})"
#                     specimen['evidence_comments'] = spec.evidence_comments.split(":", 1)[1].strip()
#                     for evidence_comment in evidence_comments:
#                         evidence = {}
#                         evidence['comment'] = evidence_comment.statement
#                         specimen['evidences'].append(evidence)
#                 else:
#                     specimen['evidence_comments'] = ""
#                 data['specimens'].append(specimen)

#         # Containers and Specimens
#         data['containers'] = []

#         for cont in containers:
#             container = {}
#             container['type'] = f"[{cont.type.code.strip('#')}] {cont.type.name}"
#             if cont.evidence_comments and ":" in cont.evidence_comments:
#                 container['evidence_comments'] = cont.evidence_comments.split(":", 1)[1].strip()
#             else:
#                 container['evidence_comments'] = ""
#             container['evidences'] = []
#             if cont.accession_number:
#                 container['accession_number'] = cont.accession_number
#                 evidence_comments = EvidenceComments.query.filter(EvidenceComments.accession_number == cont.accession_number)
#                 for evidence_comment in evidence_comments:
#                     evidence = {}
#                     evidence['comment'] = evidence_comment.statement
#                     container['evidences'].append(evidence)
#             else:
#                 container['accession_number'] = ""

#             container['submission_datetime'] = f"{cont.submission_date.strftime('%m/%d/%Y')} {cont.submission_time} hrs"
#             container['specimens'] = []


#             for spec in Specimens.query.join(SpecimenTypes).\
#                     filter(Specimens.container_id == cont.id, SpecimenTypes.discipline.contains(discipline), Specimens.db_status != 'Removed').\
#                     order_by(Specimens.accession_number.asc()):
#                 specimen = {}
#                 specimen['evidence_comments'] = spec.evidence_comments
#                 specimen['type'] = spec.type.name
#                 specimen['code'] = spec.type.code
#                 liquid_specimens = [195, 165, 196, 197, 181, 182, 180, 179, 178, 177, 198, 190, 200, 188, 184, 186, 187,
#                                     189, 185, 203, 201, 202, 191, 199, 183, 166, 174, 176, 175, 173]
#                 if spec.type.id in liquid_specimens and 'Gastrointestinal' not in spec.type.name:
#                     if spec.submitted_sample_amount > 1:
#                         specimen['amount'] = int(spec.submitted_sample_amount)
#                     else:
#                         specimen['amount'] = "< 1.0"
#                 else:
#                     specimen['amount'] = ''
#                 specimen['accession_number'] = spec.accession_number
#                 if spec.collection_date is None and spec.type.id in [195, 196, 197]:
#                     specimen['collection_datetime'] = 'No date. No time.'
#                 elif spec.collection_date is None and spec.case.type.code == 'Q':
#                     specimen['collection_datetime'] = 'No date. No time.'
#                 else:
#                     specimen['collection_datetime'] = f"{spec.collection_date.strftime('%m/%d/%Y')} {spec.collection_time} hrs"
#                 if spec.collection_container.name != 'gray top' and spec.collection_container.name != 'red top':
#                     if spec.condition:
#                         specimen['condition'] = f'{spec.condition}, {spec.collection_container.display_name if spec.collection_container else ""}'.strip()
#                     else:
#                         specimen['condition'] = f'{spec.collection_container.display_name if spec.collection_container else ""}'.strip()
#                 else:
#                     if spec.condition:
#                         specimen['condition'] = spec.condition
#                 specimen['descriptors'] = spec.condition
#                 protocols = []
#                 tests = (
#                     Tests.query.join(Assays).
#                     filter(Tests.specimen_id == spec.id,
#                     Tests.test_status == 'Finalized',
#                     Assays.discipline == discipline)
#                     # .join(Results)
#                     # .join(ReportResults)
#                 )
#                 for item in tests:
#                     assay = item.assay.assay_name
#                     protocols.append(assay)

#                 sorted_protocols = sorted(set(protocols))

#                 # checks if LCCI-BL and LCQD-BL are present and places LCCI-BL after LCQD-BL
#                 if "LCQD-BL" in sorted_protocols and "LCCI-BL" in sorted_protocols:
#                     sorted_protocols.remove("LCCI-BL")
#                     index = sorted_protocols.index("LCQD-BL")
#                     sorted_protocols.insert(index + 1, "LCCI-BL")

#                 specimen['protocols'] = ", ".join(sorted_protocols)



#                 container['specimens'].append(specimen)
#             data['containers'].append(container)

#         # Results
#         specimens = Specimens.query.filter_by(case_id=case.id).order_by(case_ordering)
#         results = ReportResults.query.filter_by(report_id=report_id). \
#             join(Results). \
#             join(Tests). \
#             join(Specimens).order_by(case_ordering, ReportResults.order)

#         # results = ReportResults.query.filter_by(report_id=report_id).order_by(ReportResults.order)
#         #data['results'] = []
#         data['confirmed_results'] = []
#         data['confirmed_comments'] = []
#         data['observed_findings'] = []
#         data['observed_comments'] = []

#         for specimen in specimens:
#             confirmed_result_dict = {}
#             observed_result_dict = {}

#             confirmed_result_dict['specimen_results'] = []
#             observed_result_dict['specimen_results'] = []

#             # Get confirmed comments
#             confirmed_comments = {}
#             confirmed_comments['specimen'] = f"[{specimen.type.code}] {specimen.type.name} ({specimen.accession_number})"
#             confirmed_comments['comments'] = []

#             confirmed_results = results.filter(Specimens.id == specimen.id, ReportResults.observed_result == None).order_by(ReportResults.primary_result.desc())
#             if confirmed_results.count():
#                 for res in confirmed_results:
#                     if res.primary_result or res.qualitative_result:
#                         result = {}
#                         result['type'] = res.result.test.specimen.type.name
#                         result['code'] = res.result.test.specimen.type.code
#                         result['accession_number'] = res.result.test.specimen.accession_number
#                         result['component'] = res.result.component_name

#                         # if the result is the official result, the printed result is simply the result. Else the result
#                         # is forced qualitative (i.e. Official (Qualitative)), the printed result is the LOD of the scope
#                         # component multiplied by the dilution factor
#                         result['result'] = ""
#                         if res.primary_result:
#                             if res.result.result:
#                                 result['result'] = res.result.result
#                         else:
#                             lod = float(res.result.scope.limit_of_detection)
#                             dilution = res.result.test.dilution
#                             if dilution:
#                                 try:
#                                     lod = float(dilution)*lod
#                                 except:
#                                     pass

#                             result['result'] = f"\u2265 {lod}"

#                         result['unit'] = ""
#                         if res.result.unit:
#                             result['unit'] = res.result.unit.name
#                         comp_res = confirmed_results.filter(Results.component_name == res.result.component_name)
#                         protocols = [item.result.test.assay.assay_name for item in comp_res]
#                         sorted_protocols = sorted(protocols)
#                         # this checks if the result is from a PM case - then it puts all LCQD-BL protocols first
#                         if res.result.case.type.code == 'PM':
#                             lcqd_bl_items = [p for p in sorted_protocols if p == "LCQD-BL" or p == "LCQD-UR"]
#                             lcfs_bl_items = [p for p in sorted_protocols if p == "LCFS-BL" or p == "LCFS-UR"]
#                             other_items = [p for p in sorted_protocols if
#                                            p != "LCQD-BL" and p != "LCQD-UR" and p != "LCFS-UR" and p != "LCFS-BL"]

#                             sorted_protocols = lcqd_bl_items + lcfs_bl_items + other_items
#                         result['protocols'] = ", ".join(sorted_protocols)
#                         confirmed_result_dict['specimen_results'].append(result)

#                 data['confirmed_results'].append(confirmed_result_dict)

#             supplementary_results = confirmed_results.filter(ReportResults.supplementary_result != None)
#             component_results = {}
#             if supplementary_results.count():
#                 approximate_results_str = "Approximate result(s): "

#                 for res in supplementary_results:
#                     component_name = res.result.component_name
#                     supplementary_result = res.result.supplementary_result
#                     unit_name = res.result.scope.unit.name

#                     if component_name in component_results:
#                         component_results[component_name].append(f"{supplementary_result} {unit_name}")
#                     else:
#                         component_results[component_name] = [f"{supplementary_result} {unit_name}"]

#                 # formatted_results = [f"{component} {', '.join(results)}" for component, results in component_results.items()]
#                 # approximate_results_str += ", ".join(formatted_results)

#                 # confirmed_comments['comments'].append(approximate_results_str)

#                 # approximate_results = [f"{res.result.component.name} {res.result.supplementary_result} {res.result.scope.unit.name}" for res in approximate_results]
#                 # approximate_results_str += ", ".join(approximate_results)
#                 # confirmed_comments['comments'].append(approximate_results_str)

#             qualitative_results = confirmed_results.filter(ReportResults.qualitative_result != None)

#             if qualitative_results.count():

#                 qualitative_results_list = {}

#                 for q in qualitative_results:

#                     q_component_name = q.result.component_name
#                     q_result = q.result.result.split(" ")[0]
#                     q_unit_name = q.result.scope.unit.name

#                     if q_component_name in component_results:
#                         component_results[q_component_name].append(f"{q_result} {q_unit_name}")
#                     else:
#                         component_results[q_component_name] = [f"{q_result} {q_unit_name}"]

#                     # q_formatted_results = [f"{component} {', '.join(results)}" for component, results in qualitative_results_list.items()]
#                     # confirmed_comments['comments'].append(", ".join(q_formatted_results))

#             approximate_results = confirmed_results.filter(ReportResults.approximate_result != None)

#             if approximate_results:

#                 approximate_result_list = {}

#                 for a in approximate_results:

#                     a_component_name = a.result.component_name
#                     a_result = a.result.result.split(" ")[0]
#                     a_unit_name = a.result.scope.unit.name

#                     if a_component_name in component_results:
#                         component_results[a_component_name].append(f"{a_result} {a_unit_name}")
#                     else:
#                         component_results[a_component_name] = [f"{a_result} {a_unit_name}"]

#             if component_results:
#                 formatted_results = [f"{component} {', '.join(results)}" for component, results in component_results.items()]
#                 approximate_results_str = "Approximate result(s): " + ", ".join(formatted_results)

#                 # Update confirmed_comments['comments'] as a single entry
#                 confirmed_comments['comments'] = [approximate_results_str]

#             # Only add specimen comments if there have been comments added
#             if confirmed_comments['comments']:
#                 data['confirmed_comments'].append(confirmed_comments)

#             # Observed findings
#             observed_findings = results.filter(Specimens.id == specimen.id,  sa.or_(ReportResults.observed_result == 'Y', ReportResults.primary_result == None))

#             # Observed comments
#             observed_comments = {}
#             observed_comments['specimen'] = f"[{specimen.type.code}] {specimen.type.name} ({specimen.accession_number})"
#             observed_comments['comments'] = []

#             if observed_findings.filter(ReportResults.observed_result == 'Y').count():
#                 show_observed_findings = True
#                 for res in observed_findings:
#                     if res.observed_result or res.qualitative_result:
#                         result = {}
#                         result['type'] = res.result.test.specimen.type.name
#                         result['code'] = res.result.test.specimen.type.code
#                         result['accession_number'] = res.result.test.specimen.accession_number
#                         result['component'] = res.result.component_name

#                         # if the result is the official result, the printed result is simply the result. Else the result
#                         # is forced qualitative (i.e. Official (Qualitative)), the printed result is the LOD of the scope
#                         # component multiplied by the dilution factor
#                         if res.observed_result:
#                             result['result'] = res.result.result
#                         else:
#                             lod = float(res.result.scope.limit_of_detection)
#                             dilution = res.result.test.dilution
#                             if dilution:
#                                 try:
#                                     lod = float(dilution)*lod
#                                 except:
#                                     pass

#                             result['result'] = f"\u2265 {lod}"

#                         result['unit'] = ""
#                         if res.result.unit:
#                             result['unit'] = res.result.unit.name
#                         comp_res = observed_findings.filter(Results.component_name == res.result.component_name)
#                         protocols = ", ".join(sorted([item.result.test.assay.assay_name for item in comp_res]))
#                         result['protocols'] = protocols
#                         observed_result_dict['specimen_results'].append(result)

#                 data['observed_findings'].append(observed_result_dict)

#             approximate_results = observed_findings.filter(ReportResults.observed_result == 'Y',
#                                                            ReportResults.supplementary_result != None)

#             if approximate_results.count():
#                 approximate_results_str = "Approximate result(s): "
#                 approximate_results = [
#                     f"{res.result.component.name} {res.result.supplementary_result} {res.result.scope.unit.name}" for
#                     res in approximate_results]
#                 approximate_results_str += ", ".join(approximate_results)
#                 observed_comments['comments'].append(approximate_results_str)

#             # Only add specimen comments if there have been comments added
#             if observed_comments['comments']:
#                 data['observed_comments'].append(observed_comments)

#         data['show_observed_findings'] = show_observed_findings

#     if report_status == 'Finalized':
#         data['report_status'] = 'Finalized'
#     if cr:
#         cr_user = Users.query.get(cr)
#         data['cr_sig'] = InlineImage(doc, image_descriptor=os.path.join(app.config['FILE_SYSTEM'], "signatures",
#                                                                         f"{cr_user.initials}.png"),
#                                      width=Mm(20), height=Mm(10))
#         data['cr'] = ", ".join(filter(lambda x: x != None, [cr_user.full_name, cr_user.title]))
#         data['cr_job_title'] = cr_user.job_title
#         data['cr_date'] = datetime.now().strftime("%m/%d/%Y %H:%M")
#         data['footer'] = file_name
#     else:
#         data['cr_sig'] = "{{cr_sig}}"
#         data['cr'] = "{{cr}}"
#         data['cr_job_title'] = "{{cr_job_title}}"
#         data['cr_date'] = "{{cr_date}}"
#     if dr:
#         dr_user = Users.query.get(dr)
#         data['dr_sig'] = InlineImage(doc, image_descriptor=os.path.join(app.config['FILE_SYSTEM'], "signatures",
#                                                                         f"{dr_user.initials}.png"),
#                                      width=Mm(20), height=Mm(10))

#         data['dr'] = ", ".join(filter(lambda x: x != None, [dr_user.full_name, dr_user.title]))
#         data['dr_job_title'] = dr_user.job_title
#         data['dr_date'] = datetime.now().strftime("%m/%d/%Y %H:%M")
#         data['file_name'] = file_name
#         data['report_status'] = report.report_status
#         # for section in doc.sections:
#         #     footer = section.footer
#         #
#         #     for paragraph in footer.parahraphs:
#         #         if "(DRAFT)" in paragraph.text:
#         #             paragraph.text = paragraph.text.replace(" (DRAFT)", "")

#     else:
#         data['dr_sig'] = "{{dr_sig}}"
#         data['dr'] = "{{dr}}"
#         data['dr_job_title'] = "{{dr_job_title}}"
#         data['dr_date'] = "{{dr_date}}"

#     path = os.path.join(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}.docx"))
#     # print('Results: ', data['confirmed_results'])
#     doc.render(data, autoescape=True)
#     doc.save(path)
#     pdf_path = os.path.join(os.path.join(app.config['FILE_SYSTEM'], "reports", f"{file_name}.pdf"))

#     #doc.save(os.path.join(app.config['FILE_SYSTEM_PRIVATE'], f'Reports\{case.case_number_full}_T1.docx'))
#     pythoncom.CoUninitialize()
#     pythoncom.CoInitialize()
#     docx2pdf.convert(path, pdf_path)
#     pythoncom.CoUninitialize()

#     return None

# -=-=-=-=- END OF ORIGINAL FUNCTION -=-=-=-=-s

