from lims.models import Batches


def get_form_choices(form):

    form.batch_id.choices = [(item.id, item.batch_id) for item in Batches.query.order_by(Batches.create_date.desc())]
    form.batch_id.choices.insert(0, (0, 'Please select a batch'))

    return form