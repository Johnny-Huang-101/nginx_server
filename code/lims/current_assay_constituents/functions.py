### NOT USED ###

from lims.models import Assays, AssayConstituents, StandardsAndSolutions


def get_form_choices(form):

    assay_choices = [(item.id, item.assay_name) for item in Assays.query]
    assay_choices = assay_choices[::-1]
    assay_choices.insert(0, (0, '--'))
    form.assay_id.choices = assay_choices

    constituent_name_choices = [(item.id, item.constituent) for item in AssayConstituents.query]
    constituent_name_choices = constituent_name_choices[::-1]
    constituent_name_choices.insert(0, (0, '--'))
    form.constituent_name.choices = constituent_name_choices

    constituent_lot_choices = [(item.id, item.lot) for item in StandardsAndSolutions.query]
    constituent_lot_choices = constituent_lot_choices[::-1]
    constituent_lot_choices.insert(0, (0, '--'))
    form.constituent_lot.choices = constituent_lot_choices

    return form
