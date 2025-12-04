# NOT USED

from flask import jsonify

from lims.models import Locations, Tests
from lims.view_templates.views import *
from lims.locations.forms import *
from sqlalchemy import and_, or_


def get_form_choices(form):
    form.test_id.choices = [(test.id, test.test_name) for test in Tests.query.all()]

    return form
