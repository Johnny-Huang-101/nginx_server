from lims import db
from lims.models import module_definitions


def get_form_choices(form):

    source_choices = [(key, key) for key in module_definitions.keys()]
    source_choices.insert(0, ('Global', 'Global'))
    source_choices.insert(0, (0, 'Please select a source'))
    form.source.choices = source_choices

    return form