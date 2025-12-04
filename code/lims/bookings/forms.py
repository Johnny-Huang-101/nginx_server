from datetime import datetime
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Optional
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, SelectMultipleField, validators

class Base(FlaskForm):

    case_id = SelectField('Case', coerce=int, validators=[DataRequired()], validate_choice=False)
    user_id = SelectField('Expert', coerce=int, validators=[DataRequired()], validate_choice=False)
    date  = DateTimeField(
        "Start Date/Time",
        format="%Y-%m-%dT%H:%M",                   
        validators=[DataRequired()],
        render_kw={"type": "datetime-local", "step": "60"}   #makes browser show date+time picker
    )
    finish_datetime = DateTimeField(
        "Finish Date/Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
        render_kw={"type": "datetime-local", "step": "60"}
    )
    jurisdiction_id = SelectField('Jurisdiction', coerce=int, validators=[DataRequired()], validate_choice=False, default=1)
    purpose_id = SelectField('Purpose', coerce=int, validators=[DataRequired()], validate_choice=False)
    type_id = SelectField('Type', coerce=int, validators=[DataRequired()], validate_choice=False, default=1)
    agency_id = SelectField("Agency, Met or Subpoena'd By", coerce=int, validators=[DataRequired()], validate_choice=False)
    personnel_id = SelectField("Person", coerce=int, validators=[Optional()], validate_choice=False)
    personnelA2_id = SelectField("Person, additional", coerce=int, validate_choice=False)
    change_id = SelectField("Change (e.g., cancelled)", coerce=int)
    format_id = SelectField("Format", coerce=int, validators=[DataRequired()])
    location = SelectField("Location", coerce=int, validators=[Optional()], validate_choice=False)
    others_present = SelectMultipleField("Other OCME Personnel Present", coerce=str, validate_choice=False)
    personnelB1_id = SelectField("Person", coerce=int, validate_choice=False)
    personnelB2_id = SelectField("Person, additional", coerce=int, validate_choice=False)
    cross_examined = SelectField("Agency, Opposing or Other", coerce=int, validate_choice=False)
    start = StringField('Start', render_kw={'class': 'duration'})
    finish = StringField('Finish', render_kw={'class': 'duration'})
    drive_time = StringField("Drive Duration", default="00:00", render_kw={'class': 'duration'})
    excluded_time = StringField("Excluded Duration", default="00:00", render_kw={'class': 'duration'})
    waiting_time = StringField("Waiting Duration", default="00:00", render_kw={'class': 'duration'})
    total_testifying_time = StringField("Total Active Duration", render_kw={'disabled': True})
    total_work_time = StringField("Total Work Duration", render_kw={'disabled': True})
    information_provider = SelectMultipleField('Information provided by', coerce=str, validate_choice=False,
                                               choices=[('', '---')])
    topics_discussed = SelectMultipleField('Topics discussed', coerce=str, validate_choice=False, choices=[('', '---')])
    narrative = TextAreaField('Information, Comment')
    booking_comment = TextAreaField('Topics, Comment')

    # for the Select User modal
    users = SelectField('User', coerce=str, validate_choice=False)

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})



class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
