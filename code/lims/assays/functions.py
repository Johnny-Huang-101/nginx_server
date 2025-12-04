from lims.models import *

def get_form_choices(form):
    """

    View the list of items in a database table

    Parameters
    ----------
    form (FlaskForm):

    Returns
    -------
    Choices for:
        - disciplines (from discipline choices variable in models.py)
        - Default Instruments
        - Default batch template
        - Statuses
    """

    # Disciplines
    form.discipline.choices = discipline_choices

    # Default instruments
    form.instrument_id.choices = [(item.id, item.instrument_id) for item in Instruments.query]
    form.instrument_id.choices.insert(0, (0, "---"))

    # Default batch templates
    form.batch_template_id.choices = [(item.id, item.name) for item in BatchTemplates.query]
    form.batch_template_id.choices.insert(0, (0, '---'))

    # Statuses
    form.status_id.choices = [(item.id, item.name) for item in Statuses.query]
    form.status_id.choices.insert(0, (0, 'Please select a status'))

    return form


def get_order():
    """

    Returns
    -------

    order_str (str):
        The list of orders used in assays. Will truncate consecutive numbers with
        a hyphen (i.e. 1-15). If an order is missing, the consecutive numbers will
        be followed by a comma (i.e. 1-15, 18-20).

    """

    # Get currently used unique orders in ascending order
    orders = [int(item.assay_order) for item in Assays.query
        .with_entities(Assays.assay_order)  # Select only the assay_order column
        .group_by(Assays.assay_order)  # Group by assay_order
        .filter(Assays.assay_order.isnot(None))  # Exclude None values
        .all()]

    order_str = ""
    if orders:
        # Set the start of the order string with the lower order
        order_str += f"{orders[0]}"
        # The order variable is order - 1. It keeps track to see if orders are consecutive
        order = orders[0]
        # Iterate through the remainer of the orders
        for x in orders[1:]:
            # if the current order is only 1 away from previous order (i.e. consecutive)
            if x == order + 1:
                # if the current order is the last in the list, add  -order to the string
                # i.e. 1-5, 1-20. If it isn't the last order, skip this order
                if orders[-1] == x:
                    order_str += f"-{x}"
                else:
                    pass
            # if the next order is not consecutive, join consecutive numbers with hypher
            # then add the non consecutive order after a comma i.e.., 1-5, 9
            else:
                order_str += f"-{order}, {x}"
            # set the new order value
            order = x

        order_str += " currently in use."

    return order_str


def update_counts(assay_id):
    """

    Updates the following values for an assay when routed to the view_list or view:
    - n_components
    - n_compounds
    - test_count
    - batch_count

    Parameters
    ----------
    assay_id

    Returns
    -------
    """

    # Get assay
    assay = Assays.query.get(assay_id)
    # Get assay scope
    scope = Scope.query.filter_by(assay_id=assay_id)
    # Updates n_components (i.e., length of scope)
    assay.n_components = scope.count()
    # Get the component_ids to query CompoundComponentReference
    component_ids = [item.component_id for item in scope]
    # Updates n_compounds
    assay.n_compounds = CompoundsComponentsReference.query.filter(
        CompoundsComponentsReference.component_id.in_(component_ids)
    ).count()
    # Updates test_count
    assay.test_count = Tests.query.filter_by(assay_id=assay_id).count()
    # update batch_count
    assay.batch_count = Batches.query.filter_by(assay_id=assay_id).count()
    db.session.commit()

