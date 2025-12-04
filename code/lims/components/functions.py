from lims.models import *
from lims.view_templates.views import *
def get_form_choices(form):
    """

     Get choices for:
        - compounds (Compounds)
            Only compounds with a drug class assigned are shown.

    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------
    form (FlaskForm)

    """

    # Compounds
    compounds = [(item.id, item.name) for item in Compounds.query.filter(Compounds.drug_class_id != None).order_by(Compounds.name.asc()).all()]
    compounds.insert(0, (0, '---'))
    form.compound_id.choices = compounds

    return form


def process_form(form, component_id=None):

    kwargs = {}
    component_drug_class = []

    if not component_id:
        component_id = Components.get_next_id()

    # Get the existing compound_id/component_id pairs
    component_compounds = CompoundsComponentsReference.query.filter_by(component_id=component_id)
    # If any of the existing compound_ids are not in the compound_id field of the form
    # i.e., the compounds were unselected, then delete the items

    for item in component_compounds:
        if str(item.compound_id) not in form.compound_id.data:
            db.session.delete(item)

    # Iterate through each selected compound and add their
    # compound_id/component_id combination to CompoundsComponentsReference
    if form.compound_id.data:
        for compound_id in form.compound_id.data:
            # Get the compound
            compound = Compounds.query.get(compound_id)
            # Add the drug class to the component_drug_class list
            component_drug_class.append(DrugClasses.query.get(compound.drug_class_id).name)

            # Check if the compound_id/component_id pair already exists, if not add
            # it to the CompoundsComponentsReference table
            compound_component = CompoundsComponentsReference.query.filter_by(component_id=component_id,
                                                         compound_id=compound_id).first()

            if not compound_component:
                item_dict = {
                    'component_id': component_id,
                    'compound_id': compound_id,
                    'create_date': datetime.now(),
                    'created_by': current_user.initials
                }
                kwargs['compound_component_dict'] = item_dict
                # item = CompoundsComponentsReference(**item_dict)
                # db.session.add(item)

        #db.session.commit()
        # Join the drug classes by ' / '
        component_drug_class = ' / '.join(sorted(list(set(component_drug_class))))
        # Set the component_drug_class string to be added to the database
        kwargs['component_drug_class'] = component_drug_class
        # Query the database for that drug class
        drug_class = DrugClasses.query.filter_by(name=component_drug_class).first()

        # If there is already a drug class with that name, set the drug_class_id to the
        # drug class' id. If it doesn't set the drug_class_id to
        if drug_class:
            kwargs['drug_class_id'] = drug_class.id
            kwargs['add_drug_class'] = False
        else:
            kwargs['drug_class_id'] = DrugClasses.get_next_id()
            kwargs['add_drug_class'] = True

    return kwargs


def get_drug_classes(compound_ids):
    """

    Gets existing components and their ranks based on the component drug class.

    Parameters
    ----------
    compound_ids

    Returns
    -------

    """

    print(compound_ids)
    drug_classes = []
    for compound_id in compound_ids:
        compound = Compounds.query.get(compound_id)
        if compound.drug_class:
            drug_classes.append(compound.drug_class.name)

    if drug_classes:
        drug_class = " / ".join(sorted(set(drug_classes)))

        # ranks = [item.rank for item in Components.query.filter_by(component_drug_class=drug_class) if item.rank]
        rank_dict = {item.rank: item.name for item in Components.query.filter_by(component_drug_class=drug_class) if item.rank}
        ranks = sorted([item for item in rank_dict.keys()])
        rank_str = ""
        if rank_dict:
            # Set the start of the order string with the lower order
            rank_str += f"{ranks[0]}"
            # The order variable is order - 1. It keeps track to see if orders are consecutive
            rank = ranks[0]
            # Iterate through the remainer of the orders
            for x in ranks[1:]:
                # if the current order is only 1 away from previous order (i.e. consecutive)
                if x == rank + 1:
                    # if the current order is the last in the list, add  -order to the string
                    # i.e. 1-5, 1-20. If it isn't the last order, skip this order
                    if ranks[-1] == x:
                        rank_str += f"-{x}"
                    else:
                        pass
                # if the next order is not consecutive, join consecutive numbers with hypher
                # then add the non consecutive order after a comma i.e.., 1-5, 9
                else:
                    rank_str += f"-{rank}, {x}"
                # set the new order value
                rank = x

        ranks = sorted(rank_dict.items(), key=lambda item: item[0])

    else:
        drug_class = "Compounds not assigned a drug class"
        rank_str = ""
        ranks = []
    return drug_class, ranks, rank_str
