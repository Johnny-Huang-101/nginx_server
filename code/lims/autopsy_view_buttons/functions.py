from lims import db
from lims.models import discipline_choices, SpecimenTypes


def get_form_choices(form):

    form.discipline.choices = discipline_choices
    form.specimen_types.choices = [(str(item.id), item.name) for item in SpecimenTypes.query.all()]

    # Hardcoded button choices to match options in autopsy view
    form.button.choices = [
        ('Histology (T)', 'Histology (T)'),
        ('Histology (S)', 'Histology (S)'),
        ('Admin Review', 'Admin Review'),
        ('Autopsy', 'Autopsy'),
        ('Homicide (Bundle)', 'Homicide (Bundle)')
    ]

    return form
