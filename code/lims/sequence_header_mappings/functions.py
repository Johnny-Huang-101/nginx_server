from lims.models import BatchTemplates


def get_form_choices(form, batch_template_id=None):
    if batch_template_id is not None:
        batch_template = BatchTemplates.query.get_or_404(batch_template_id)
        batch_templates = [(batch_template.id, batch_template.name)]
    else:
        batch_templates = [(item.id, item.name) for item in BatchTemplates.query]
        batch_templates.insert(0, (0, 'Please select a batch template'))

    form.batch_template_id.choices = batch_templates

    return form