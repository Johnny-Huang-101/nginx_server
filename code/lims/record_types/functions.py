from lims.models import Divisions


def get_form_choices(form):
    """

    Gets the list of divisions from the San Francisco Office of the Chief
    Medical Examiner (i.e. agency_id = 1)

    Parameters
    ----------
    form (FlaskFrom)

    Returns
    -------
    form (FlaskForm)
    """

    divisions = [(item.id, item.name) for item in Divisions.query.filter_by(agency_id=1).order_by(Divisions.name.desc())]
    divisions.insert(0, (0, '---'))
    form.division_id.choices = divisions

    return form