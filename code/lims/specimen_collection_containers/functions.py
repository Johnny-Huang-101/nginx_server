from lims.models import SpecimenCollectionContainerTypes

def get_form_choices(form):

    types = [(item.id, item.name) for item in SpecimenCollectionContainerTypes.query]
    types.insert(0, (0, '---'))

    form.type_id.choices = types

    return form