from lims.models import UnitTypes


def get_form_choices(form):

    types = [(item.id, item.name) for item in UnitTypes.query]
    types.insert(0, (0, 'Please select a unit type.'))

    form.unit_type_id.choices = types

    return form