from lims import db
from lims.models import Statuses
from lims.locations.functions import models_iter, location_dict


def get_form_choices(form):
    statuses = [(item.id, item.name) for item in Statuses.query.order_by(Statuses.name.asc())]
    statuses.insert(0, (0, 'Please select a status'))
    form.status_id.choices = statuses

    choices = [
        (k, v['option'])
        for k, v in location_dict.items()
        if v['table'] in models_iter
           and hasattr(v['table'], 'resource_level')
           and getattr(v['table'], 'resource_level') == 'primary'
    ]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    return form
