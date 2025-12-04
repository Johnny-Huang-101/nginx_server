from lims.models import LitPacketAdminTemplates
from sqlalchemy import inspect


def get_form_choices(form):
    form.lit_admin_template_id.choices = [(t.id, t.name) for t in LitPacketAdminTemplates.query.all()]

    return form

