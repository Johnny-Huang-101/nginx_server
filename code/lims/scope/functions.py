from lims.models import *

def get_form_choices(form):
    """

    Get form choices for:
    - component_id (Components)
    - assay_id (Assays)
    - unit_id (Units)


    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------

    form (FlaskForm)

    """

    # Components
    components = [(item.id, item.name) for item in Components.query.order_by(Components.name.asc())]
    # components.insert(0, (0, 'Please select a component'))
    form.component_id.choices = components

    # Assays
    assays = [(item.id, item.assay_name) for item in
                             Assays.query.order_by(Assays.assay_order)]
    form.assay_id.choices = assays

    # Units
    units = [(item.id, item.name) for item in Units.query]
    units.insert(0, (0, 'Please select a unit'))
    form.unit_id.choices = units



    return form
