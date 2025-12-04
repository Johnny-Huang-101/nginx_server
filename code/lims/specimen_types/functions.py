from lims.models import (Assays, SpecimenCollectionContainers,
                         Units, StatesOfMatter)


def get_form_choices(form):

    states = [(item.id, item.name) for item in StatesOfMatter.query.all()]
    form.state_id.choices = states

    assays = [(str(item.id), item.assay_name) for item in Assays.query]
    assays.insert(0, (0, '---'))
    form.default_assays.choices = assays

    units = [(item.id, item.name) for item in Units.query]
    units.insert(0, (0, "---"))
    form.unit_id.choices = units

    collection_containers = [(item.id, item.display_name) for item in SpecimenCollectionContainers.select_field_query()]
    collection_containers.insert(0, (0, '---'))
    form.collection_container_id.choices = collection_containers
    #
    # types = [(item.id, item.name) for item in ReferenceMaterialPreparations.query]
    # types.insert(0, (0, 'Please select a type'))
    # form.preparation_id.choices = types
    #
    return form
