from sqlalchemy import and_, or_

from lims import db
from lims.models import Users, SolutionTypes, Agencies
import sqlalchemy as sa
from lims.locations.functions import location_dict


def get_form_choices(form):
    by_choices = [(item.id, item.initials) for item in Users.query.filter(sa.and_(Users.job_class.in_(['2403', '2456',
                                                                                                       '2457', '2458']),
                                                                                  Users.status.in_(['Active'])))]
    form.recd_by.choices = by_choices

    manufacturers = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    manufacturers.insert(0, (0, 'Please select a manufacturer'))
    form.manufacturer_id.choices = manufacturers

    # Filters for relevant solution types
    solution_types = [(item.id, item.name) for item in SolutionTypes.query.filter(or_(SolutionTypes.id == 3,
                                                                                      SolutionTypes.id == 14,
                                                                                      SolutionTypes.id == 15,
                                                                                      SolutionTypes.id == 16,
                                                                                      SolutionTypes.id == 17,
                                                                                      SolutionTypes.id == 18,
                                                                                      SolutionTypes.id == 19,
                                                                                      SolutionTypes.id == 20))]
    solution_types.insert(0, (0, '--'))
    form.solution_type_id.choices = solution_types

    choices = [(k, v['option']) for k, v in location_dict.items()]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices
    return form
