from lims.models import *


def get_form_choices(form):
    """

    Get the list of current sections to populate the parent_section field
    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------

    form (FlaskFrom)
    """

    sections = [(item.id, f"{item.code} - {item.name}") for item in EvidenceCommentsReference.query.filter_by(type='Section')]
    sections.insert(0, (0, 'Please select a parent section'))
    form.parent_section.choices = sections

    return form
