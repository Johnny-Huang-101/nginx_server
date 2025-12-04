from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional, ValidationError, NumberRange


class Base(FlaskForm):
    case_id = SelectField('Case', coerce=int, validate_choice=False, validators=[DataRequired()])
    container_type_id = SelectField('Container Type', coerce=int, validators=[DataRequired()])
    #accession_number = StringField('Accession Number')
    division_id = SelectField('Submitting Division', coerce=int, validate_choice=False, validators=[DataRequired()])
    submitted_by = SelectField('Submitted By', coerce=int, validate_choice=False, validators=[DataRequired()])
    submission_date = DateField('Submission Date', default=datetime.now().date(), validators=[DataRequired()])
    future_submission_date = BooleanField('Submission date is in the future')
    submission_time = StringField('Submission Time', validators=[DataRequired()])
    n_specimens_submitted = IntegerField('Number of specimens submitted', validators=[Optional(), NumberRange(min=0, message = "Please enter a positive value.")],
                                         render_kw={'placeholder': 'Leave blank for automatic calculation'})
    submission_route_type = SelectField('Submission Route Type', choices=[('By Hand', 'By Hand'),
                                                                          ('By Location', 'By Location'),
                                                                          ('By Transfer', 'By Transfer')])
    submission_route = SelectField('Submission Location', coerce=str, render_kw={'disabled': True},
                                    validate_choice=False)
    location_type = SelectField('Location Type', coerce=str, render_kw={'disabled': True}, validate_choice=False)
    evidence_comments = TextAreaField('Evidence Receipt Comments', render_kw={'readonly': True})
    discipline = SelectField('Discipline', coerce=str, validators=[DataRequired()])
    transfer_by = SelectField('Transferred By', coerce=int, validators=[Optional()], render_kw={'disabled': True})
    comments = TextAreaField('Comments')
    communications = TextAreaField('Messages', render_kw={'style': "background-color: #fff3cd"})
    observed_by = SelectField('Observed By' ,coerce=int, validate_choice=False, validators=[Optional()],render_kw={'disabled': True})
    def validate_submission_date(self, submission_date):
        now = datetime.now()
        if self.submission_time.data:
            submission_time = datetime.strptime(self.submission_time.data, '%H%M').time()
            submission_datetime = datetime.combine(submission_date.data, submission_time)
            if not self.future_submission_date.data:
                if submission_datetime > now:
                    raise ValidationError('Submission date cannot be in the future.')

    def validate_location_type(self, location_type):
        if self.submission_route_type.data == 'By Location':
            print(location_type.data)
            if not location_type.data:
                raise ValidationError('Location type must be selected if submission route type is by hand')

    def validate_submission_route(self, submission_route):
        if not submission_route.data:
            if self.location_type.data:
                raise ValidationError('Submission location must be entered')
            elif self.submission_route_type.data == 'By Location':
                raise ValidationError('No location type selected')


    # def validate_submission_time(self, submission_time):
    #     if len(submission_time.data) != 4:
    #         raise ValidationError("Submission Time must be in the format of 'HHMM'.")
    #
    #     try:
    #         datetime.strptime(submission_time.data, '%H%M')
    #     except:
    #         raise ValidationError(f"{submission_time.data} in not a valid time.")

    # def validate_submission_time(self, submission_time):
    #     case = Cases.query.get(self.case_id.data)
    #     if len(submission_time.data) != 4:
    #         raise ValidationError("Submission time must be in the format of 'HHMM'")
    #     try:
    #         datetime.strptime(submission_time.data, '%H%M')
    #     except:
    #         raise ValidationError(f"{submission_time.data} in not a valid time")
    #
    #     if self.submission_date.data == case.date_of_incident.date():
    #         if datetime.strptime(submission_time.data, '%H%M').time() < datetime.strptime(case.time_of_incident,
    #                                                                                       '%H%M').time():
    #             raise ValidationError(
    #                 f"Submission time cannot be before incident/death time ({case.time_of_incident}) on date of incident/death.")
    #     elif self.submission_date.data == datetime.today().date():
    #         if datetime.strptime(submission_time.data, '%H%M').time() > datetime.today().time():
    #             raise ValidationError("Submission time is in the future based on submission date")

        # if self.submission_date.data == datetime.today().date():
        #     if datetime.strptime(submission_time.data, '%H%M').time() > datetime.today().time():
        #         raise ValidationError("Submission time is in the future based on submission date")
        # elif self.submission_date.data == case.date_of_incident.date():
        #     if datetime.strptime(submission_time.data, '%H%M').time() < datetime.strptime(case.time_of_incident, '%H%M').time():
        #         raise ValidationError(
        #             f"Submission time cannot be before incident/death time ({case.time_of_incident}) on date of incident/death.")

        # try:
        #     datetime.strptime(submission_time.data, '%H%M')
        # except:
        #     raise ValidationError(f"{submission_time.data} in not a valid time")


class Add(Base):
    submit = SubmitField('Submit and Proceed to Specimens')
    submit_exit = SubmitField('Submit and Exit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')
