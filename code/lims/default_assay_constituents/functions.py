from lims.models import *

def get_form_choices(form):
    """
    Get choices for:
        - constituent_id: AssayConstituents
        - assay_id: Assays
    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------

    form (FlaskForm)
    """

    # Constituent
    form.constituent_id.choices = [(str(item.id), item.name) for item in AssayConstituents.query.all()]
    form.constituent_id.choices.insert(0, (0, 'Please select a constituent'))

    # Assay
    form.assay_id.choices = [(item.id, item.assay_name) for item in Assays.query.all()]
    form.assay_id.choices.insert(0, (0, 'Please select an Assay'))

    return form
