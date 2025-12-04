from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField, FloatField
from wtforms.validators import ValidationError, DataRequired, AnyOf, Optional
from lims.models import Specimens, SpecimenTypes, SpecimenConditions, Assays, Cases, \
    Containers, Units, SpecimenCollectionContainers, discipline_choices
from datetime import datetime
import pytz
from pytz import timezone
from flask_wtf.file import FileField
from lims.fields import NullableDateField, NullableFloatField


class Base(FlaskForm):
    today = datetime.now().date()
    case_id = SelectField('Case', coerce=int, validators=[DataRequired()])
    container_id = SelectField('Parent Container', coerce=int, validate_choice=False)
    discipline = SelectMultipleField('Discipline', validate_choice=False,)
    specimen_type_id = SelectField('Specimen Type', coerce=int, validate_choice=False, validators=[DataRequired()])
    collection_date = NullableDateField('Collection Date')
    no_collection_date = BooleanField('No collection date')
    future_collection_date = BooleanField('Collection date is in the future')
    collection_time = StringField('Collection Time')
    no_collection_time = BooleanField('No collection time')
    submitted_sample_amount = NullableFloatField('Sample Amount')
    unknown_sample_amount = BooleanField('Unknown sample amount')
    collection_container_id = SelectField('Collection Vessel', coerce=int, validate_choice=False, validators=[DataRequired()])
    collected_by = SelectField('Collected By', coerce=int, validate_choice=False, render_kw={'disabled': True})
    no_collected_by = BooleanField('Collector unknown', render_kw={'disabled': True})
    condition = SelectMultipleField('Condition')
    sub_specimen = BooleanField('Sub-Specimen')
    parent_specimen = SelectField('Parent Specimen', coerce=int, render_kw={'disabled': True}, validate_choice=False)
    custody_type = SelectField('Custody Location Type', validators=[DataRequired()])
    custody = SelectField('Transfer custody to', validate_choice=False, validators=[DataRequired()], coerce=str)
    evidence_comments = TextAreaField('Evidence Receipt Comments', render_kw={'readonly': True},
                                      validators=[Optional()])
    start_time = DateTimeField('Start Time', validators=[Optional()], render_kw={'hidden': True})
    comments = TextAreaField('Comments', validators=[Optional()])
    communications = TextAreaField('Messages', render_kw={'style': "background-color: #fff3cd"},
                                   validators=[Optional()])
    # received_date = DateField('Date Received', default=datetime.today())
    # received_time = StringField('Time Received')

    submit_exit = SubmitField('Submit and Exit')
    submit_close = SubmitField('Confirm')
    submit_attach = SubmitField('Submit and add attachment to parent container')
    other_specimen = StringField(
        'Other Specimen',
        validators=[DataRequired()],
        filters=[lambda x: x or None]
    )

    def validate_collection_date(self, collection_date):
        now = datetime.now()
        # if "No collection date" is left unchecked
        if not self.no_collection_date.data:
            if not collection_date.data:
                raise ValidationError('A collection date must be entered')
            elif not self.collection_time.data:
                pass
            else:
                if not self.future_collection_date.data:
                    collection_time = datetime.strptime(self.collection_time.data, '%H%M').time()
                    collection_datetime = datetime.combine(collection_date.data, collection_time)
                    print(collection_datetime)
                    print(self.future_collection_date.data)
                    if collection_datetime > now:
                        raise ValidationError('Collection date/time cannot be in the future.')


    def validate_collection_time(self, collection_time):
        if not self.no_collection_time.data:
            if not collection_time.data:
                raise ValidationError('A collection time must be entered')

    def validate_collected_by(self, collected_by):
        if self.case_id.data:
            case = Cases.query.get(self.case_id.data)
            print(f'CASE DATA: {case}')
            if case.type.code == 'PM':
                # container = Containers.query.get(self.container_id.data)
                # if container.submitter:
                #     submitting_agency = container.submitter.agency.name
                #     print(submitting_agency)
                #     if submitting_agency == 'San Francisco Office of the Chief Medical Examiner':
                if not collected_by.data and not self.no_collected_by.data:
                    raise ValidationError('Collected by must be selected')

    def validate_submitted_sample_amount(self, submitted_sample_amount):
        if self.submitted_sample_amount.data == 0:
            pass
        elif not self.unknown_sample_amount.data and not submitted_sample_amount.data:
            raise ValidationError('Please either enter a sample amount or check "Unknown sample amount".')

    def validate_container_id(self, container_id):
        if not self.sub_specimen.data:
            if not container_id.data:
                raise ValidationError('A container must be selected')

    # def validate_collection_date(self, collection_date):
    #     today = datetime.date(datetime.now(tz=pytz.utc).astimezone(timezone('US/Pacific')))
    #     case = Cases.query.get(self.case_id.data)
    #     if collection_date.data is not None:
    #         if collection_date.data > today:
    #             raise ValidationError('collection date cannot be in the future.')
    #         elif collection_date.data < case.date_of_incident.date():
    #             raise ValidationError(f"Collection date cannot be before date of incident/death "
    #                                   f"({case.date_of_incident.strftime('%m/%d/%Y')})")
    #
    #
    # def validate_collection_time(self, collection_time):
    #     case = Cases.query.get(self.case_id.data)
    #     container = Containers.query.get(self.container_id.data)
    #     if len(collection_time.data) != 4:
    #         raise ValidationError("Collection time must be in the format of 'HHMM'")
    #     try:
    #         datetime.strptime(collection_time.data, '%H%M')
    #     except:
    #         raise ValidationError(f"{collection_time.data} is not a valid time")
    #
    #     if self.collection_date.data == case.date_of_incident.date():
    #         if datetime.strptime(collection_time.data, '%H%M').time() < datetime.strptime(case.time_of_incident, '%H%M').time():
    #             raise ValidationError(
    #                 f"Collection time cannot be before incident/death time ({case.time_of_incident}) on date of incident/death.")
    #     if self.collection_date.data == container.submission_date.date():
    #         if datetime.strptime(collection_time.data, '%H%M').time() > datetime.strptime(container.submission_time, '%H%M').time():
    #             raise ValidationError(
    #                 f"Collection time cannot be after container submission date  ({container.submission_date.strftime('%m/%d/%Y')}) and time ({container.submission_time})")
    #     if self.collection_date.data == datetime.today().date():
    #         if datetime.strptime(collection_time.data, '%H%M').time() > datetime.today().time():
    #             raise ValidationError("Submission time is in the future based on submission date")


class Add(Base):
    submit =  SubmitField('Submit and Next Specimen')


class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')
    submit_close = SubmitField('Confirm')


class AdminCustody(FlaskForm):
    custody_type = SelectField('Custody Type', coerce=str, validators=[DataRequired()])
    custody = SelectField('Custody', coerce=str, validators=[DataRequired()], validate_choice=False)
    reason = StringField('Explanation')
    custody_submit = SubmitField('Submit')


class EditDiscipline(FlaskForm):
    add_discipline = SelectField('Add a Discipline', choices=discipline_choices, validators=[DataRequired()])
    disc_submit = SubmitField('Submit')


class AdminOnlyCustody(FlaskForm):
    custody_type = SelectField('Custody Type', coerce=str, validators=[DataRequired()])
    custody = SelectField('Custody', coerce=str, validators=[DataRequired()], validate_choice=False)
    admin_custody_submit = SubmitField('Submit')
