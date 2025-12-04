from lims.models import *
from datetime import datetime, timedelta


def get_form_choices(form, case_id):
    # case_id
    if case_id:
        case = Cases.query.get(case_id)
        form.case_id.choices = [(case.id, case.case_number)]
    else:
        form.case_id.choices = [(item.id, item.case_number) for item in 
                                Cases.query
                                    .filter(Cases.create_date > datetime(2025, 1, 1))
                                    .order_by(Cases.case_number)]
        form.case_id.choices.insert(0, (0, 'Please select a case'))

    # user_id
    form.user_id.choices = [(item.id, item.initials) for item in
                            Users.query.filter(Users.status == 'Active').order_by(Users.full_name.asc())]
    form.user_id.choices.insert(0, (0, 'Please select an expert'))

    # purpose_id
    purposes = [(item.id, item.name) for item in BookingPurposes.query.order_by(BookingPurposes.id.asc())]
    purposes.insert(0, (0, 'Please select a purpose.'))
    form.purpose_id.choices = purposes
    # type_id
    types = [(item.id, item.name) for item in BookingTypes.query.order_by(BookingTypes.id.asc())]
    types.insert(0, (0, 'Please select a type.'))
    form.type_id.choices = types
    # jurisdiction_id
    jurisdictions = [(item.id, item.name) for item in BookingJurisdiction.query.order_by(BookingJurisdiction.id.asc())]
    jurisdictions.insert(0, (0, 'Please select a jurisdiction.'))
    form.jurisdiction_id.choices = jurisdictions
    # format_id
    formats = [(item.id, item.name) for item in BookingFormats.query.order_by(BookingFormats.name.asc())]
    formats.insert(0, (0, 'Please select a format.'))
    form.format_id.choices = formats
    # location
    locations = [(item.id, item.name) for item in BookingLocations.query.order_by(BookingLocations.id.asc())]
    locations.insert(0, (0, 'Please select a location.'))
    form.location.choices = locations
    # change_id
    changes = [(item.id, item.name) for item in BookingChanges.query.order_by(BookingChanges.name.asc())]
    changes.insert(0, (0, 'Please select a reason for a change.'))
    form.change_id.choices = changes

    form.information_provider.choices = [(str(item.id), item.name) for item in
                                         BookingInformationProvider.query.all()]
    # topics_discussed
    form.topics_discussed.choices = [(str(item.id), item.name) for item in BookingInformationProvided.query.all()]

    # agency_id
    form.agency_id.choices = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    form.agency_id.choices.insert(0, (0, 'Please select an agency'))

    # personnel_id
    form.personnel_id.choices = [(0, 'No agency selected')]

    # personnel_id
    form.personnelA2_id.choices = [(0, 'No agency selected')]

    # agency_id
    form.cross_examined.choices = [(item.id, item.name) for item in Agencies.query.order_by(Agencies.name.asc())]
    form.cross_examined.choices.insert(0, (0, 'Please select an agency'))

    # personnel_id
    form.personnelB1_id.choices = [(0, 'No agency selected')]

    # personnel_id
    form.personnelB2_id.choices = [(0, 'No agency selected')]

    # others_present
    others_choices = [(str(item.id), item.full_name) for item in
                      Personnel.query.filter(Personnel.status_id == '1',
                                             Personnel.agency_id == 1)
                      .order_by(Personnel.full_name)]
    form.others_present.choices = others_choices

    return form


def process_form(form):
    """

    Calculates:
        - Total work time = finish - start - excluded time
        - Total testifying time = finish - start - excluded time - waiting time - driving time

    Parameters
    ----------
    form

    Returns
    -------

    """
    kwargs = {}

    start = form.date.data
    finish = form.finish_datetime.data
    drive_time = form.drive_time.data
    waiting_time = form.waiting_time.data
    excluded_time = form.excluded_time.data

    kwargs['total_work_time'], kwargs['total_testifying_time'] = calculate_time(start, finish, drive_time,
                                                                                excluded_time, waiting_time)

    return kwargs

def calculate_time(start_dt, finish_dt, drive_duration, excluded_duration, waiting_duration):
    total_work_time_str = None
    total_testifying_time_str = None

    if (start_dt is not None) and (finish_dt is not None):
        
        #Only parse if value is a string (WTForms form submit already provides a datetime object,AJAX request sendsa string)
        if isinstance(start_dt, str):
            start = datetime.strptime(start_dt, "%Y-%m-%dT%H:%M")
        else:
            start = start_dt

        if isinstance(finish_dt, str):
            finish = datetime.strptime(finish_dt, "%Y-%m-%dT%H:%M")
        else:
            finish = finish_dt
        # Converted entered time into datetime objects
        drive_duration = datetime.strptime(drive_duration, "%H:%M")
        excluded_duration = datetime.strptime(excluded_duration, "%H:%M")
        waiting_duration = datetime.strptime(waiting_duration, "%H:%M")
        
        # Total work time = finish - start - excluded_time
        work_time = finish - start

        excluded_duration = excluded_duration.time()
        excluded_duration = timedelta(hours=excluded_duration.hour, minutes=excluded_duration.minute,
                                  seconds=excluded_duration.second)

        total_work_time = work_time - excluded_duration
        total_work_time_str = str(total_work_time)[:-3]  # [:3] removes the seconds from the dt object

        # Total testifying time = finish - start - excluded_time - waiting_time - driving_tune

        drive_duration = drive_duration.time()
        drive_duration = timedelta(hours=drive_duration.hour, minutes=drive_duration.minute, seconds=drive_duration.second)

        waiting_duration = waiting_duration.time()
        waiting_duration = timedelta(hours=waiting_duration.hour, minutes=waiting_duration.minute, seconds=waiting_duration.second)

        total_testifying_time = total_work_time - drive_duration - waiting_duration
        total_testifying_time_str = str(total_testifying_time)[:-3]  # [:3] removes the seconds from the dt object

    return total_work_time_str, total_testifying_time_str