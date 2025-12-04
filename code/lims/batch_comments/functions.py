# NOT USED

from lims import db
from lims.models import Statuses, Batches, BatchCommentsReference


def get_form_choices(form):

    form.batch_id.choices = [(item.id, item.batch_id) for item in Batches.query.all()]
    form.comment_reference.choices = [(item.id, item.comment) for item in BatchCommentsReference.query.all()]
    # Include 'Other' choice
    form.comment_reference.choices.insert(len(form.comment_reference.choices) + 1,
                                          (len(form.comment_reference.choices) + 1, 'Other'))

    return form
