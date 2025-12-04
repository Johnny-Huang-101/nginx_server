from lims.models import Cases, Users, BookingPurposes, BookingFormats, BookingChanges


def get_form_choices(form):

    # form.agency_id.choices = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    # form.agency_id.choices.insert(0, (0, 'Please select an Agency'))
    #
    # form.personnel_id.choices = [(item.id, item.full_name) for item in Personnel.query.order_by(Personnel.full_name.asc())]
    # form.personnel_id.choices.insert(0, (0, 'Please select who was met with'))

    return form
