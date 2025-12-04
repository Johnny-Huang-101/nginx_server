from sqlalchemy import and_, or_

from lims.models import SolutionTypes
import sqlalchemy as sa


def get_form_choices(form):
    form.solution_type.choices = [(item.id, item.name) for item in SolutionTypes.query.all()]
    return form
