from sqlalchemy import and_, or_

from lims.models import AssayConstituents
from lims.standards_and_solutions.views import optional_fields
import sqlalchemy as sa


def get_form_choices(form):
    form.constituents.choices = [(str(item.id), item.name) for item in AssayConstituents.query.all()]
    form.expected_fields.choices = [(v, k) for k, v in optional_fields.items()]
    return form
