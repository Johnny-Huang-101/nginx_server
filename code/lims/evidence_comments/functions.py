from datetime import datetime
from flask_login import current_user
from lims import db
from lims.models import *
import sqlalchemy as sa

import re

def get_form_choices(form):

    sections = [(item.id, f"{item.code} - {item.name}") for item in EvidenceCommentsReference.query.filter_by(type='Section').order_by(sa.cast(EvidenceCommentsReference.code, sa.Integer))]
    sections.insert(0, (0, 'Please select a section'))
    form.section.choices = sections

    form.field.choices = [(0, 'No section selected')]
    issues = [(item.id, f"{item.code} - {item.name}") for item in EvidenceCommentsReference.query.filter_by(type='Issue').order_by(EvidenceCommentsReference.code.asc())]
    issues.insert(0, (0, 'Please select an issue'))
    form.issue.choices = issues

    return form


def add_comments(form, accession_number, route):

    comments = form.evidence_comments.data

    case = Cases.query.get(form.case_id.data)
    print(case.submitting_agency)

    if route == 'Container':
        submitter = Personnel.query.get(form.submitted_by.data)
    else:
        container = Containers.query.get(form.container_id.data)
        submitter = container.submitter

    accession_codes = []
    if accession_number:
        accession_comments = EvidenceComments.query.filter_by(accession_number=accession_number)
        accession_codes = [item.code for item in accession_comments]
    print(accession_codes)

    comments_lst = []
    print(comments)

    if comments is not None:
        comments = sort_comments(comments)
        comments_lst = comments.split("\n")

    new_codes = []
    for comment in comments_lst:
        code, statement = comment.split(": ")
        new_codes.append(code)
        if code not in accession_codes:
            item = EvidenceComments(
                accession_number=accession_number,
                case_number=form.case_id.data,
                code=code,
                statement=statement,
                submitter_id=submitter.id,
                submitter_name=submitter.full_name,
                submitter_division=submitter.division.name,
                submitter_agency=submitter.agency.name,
                create_date=datetime.now(),
                created_by=current_user.initials,
            )
            db.session.add(item)
    print(new_codes)

    if accession_number:
        for code in accession_codes:
            if code not in new_codes:
                comment = EvidenceComments.query.filter_by(accession_number=accession_number, code=code).first()
                print(comment)
                db.session.delete(comment)

    db.session.commit()


def delete_comments(item_id, item_type):

    if item_type == 'Containers':
        item = Containers.query.get(item_id)
    else:
        item = Specimens.query.get(item_id)

    # Handle if item has no evidence comments
    try:
        accession_number = item.accession_number

        comments = EvidenceComments.query.filter_by(accession_number=accession_number).all()
        print(comments)

        for comment in comments:
            db.session.delete(comment)

        db.session.commit()

    except AttributeError:
        pass



def sort_comments(comments):

    # Convert comments to list by splitting on the new-line character (\n)
    # The list is also sorted, this will ensure that comments within the same section
    # are sorted properly i.e. 13A-6 comes before 13B-2.
    if comments:
        comments = sorted(comments.split("\n"))
        # Add each comment to the comment_dict. The keys will be the full comment and the values will be the
        # numerical sections e.g.
        # {'8B-4: An inconsistent entry was observed in Blood Collection Date & Time (24h): 8}
        comment_dict = {}
        for comment in comments:
            code = comment.split(": ")[0]
            code_number = int(re.findall('\d{1,2}', code)[0])
            comment_dict[comment] = code_number

        # Sort the comments (dictionary) and case them to a list
        comment_text = list(dict(sorted(comment_dict.items(), key=lambda item: item[1])).keys())

        # Join each comment with a new-line character
        comments = "\n".join(comment_text)

    return comments