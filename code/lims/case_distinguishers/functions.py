from lims.models import CaseTypes


def get_form_choices(form):
    """

    Parameters
    ----------
    form

    Returns
    -------

    """
    case_types = [(item.id, f"{item.code} | {item.name}") for item in CaseTypes.query]
    form.case_type_id.choices = case_types
    form.case_type_id.render_kw = {'size': len(case_types)}

    return form
