from datetime import datetime
from lims.models import Cases, Assays, disciplines, Specimens, SpecimenTypes
import sqlalchemy as sa


def get_form_choices(form, case_id, discipline=None):

    discipline_choices = []
    if case_id:
        case = Cases.query.get(case_id)


        for d in disciplines:
            if hasattr(case, f"{d.lower()}_requested"):
                if getattr(case, f"{d.lower()}_requested") == 'Yes':
                    form[f'{d.lower()}_requested'].data = True

            if hasattr(case, f"{d.lower()}_performed"):
                if getattr(case, f"{d.lower()}_performed") == 'Yes':
                    form[f'{d.lower()}'].data = True
                    form[f'{d.lower()}'].render_kw = {'disabled': True}
                    discipline_choices.append((d, d))


        if len(discipline_choices):
            discipline_choices.insert(0, (0, 'Please select a discipline'))
        else:
            discipline_choices.insert(0, (0, 'No disciplines selected to be performed'))

        form.discipline.choices = discipline_choices
        form.case_id.choices = [(case.id, case.case_number)]

    else:
        cases = [(item.id, item.case_number) for item in Cases.query.filter(Cases.create_date > datetime(2025, 1, 1)).order_by(Cases.create_date.desc())]
        cases.insert(0, (0, 'Please select a case'))
        form.case_id.choices = cases[:100]
        form.discipline.choices = [(0, 'No case selected')]

    if case_id and discipline:
        specimens = [
            (item.id, item.accession_number) for item in Specimens.query
                .join(SpecimenTypes)
                .filter(sa.and_(
                    Specimens.db_status.in_(['Active', 'Active With Pending Changes']),
                    Specimens.case_id == case_id,
                    SpecimenTypes.discipline.contains(discipline))
                )
        ]
        form.specimen_id.choices = specimens
    else:
        form.specimen_id.choices = [(0, 'No case selected')]

    form.assay_id.choices = [(item.id, item.assay_name) for item in Assays.query]

    return form
