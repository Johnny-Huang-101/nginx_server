from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DateField
from wtforms.validators import Optional, DataRequired


class Base(FlaskForm):

    instrument_id = StringField('Instrument ID', validators=[DataRequired()])
    instrument_type_id = SelectField('Type', coerce=int, validators=[DataRequired()])
    acquired_date = DateField("Acquired Date", validators=[Optional()])
    status_id = SelectField('Status', coerce=int, validators=[DataRequired()])
    last_service_date = DateField('Last Service Date', validators=[Optional()])
    due_service_date = DateField("Service Due Date", validators=[Optional()])
    vendor_id = SelectField('Service Provider', coerce=int, validators=[DataRequired()])
    manufacturer_id = SelectField('Manufacturer', coerce=int, validators=[DataRequired()])

    module_model_1 = StringField('Module 1 Model No.')
    module_serial_1 = StringField('Module 1 Serial No.')
    module_model_2 = StringField('Module 2 Model No.')
    module_serial_2 = StringField('Module 2 Serial No.')
    module_model_3 = StringField('Module 3 Model No.')
    module_serial_3 = StringField('Module 3 Serial No.')
    module_model_4 = StringField('Module 4 Model No.')
    module_serial_4 = StringField('Module 4 Serial No.')
    module_model_5 = StringField('Module 5 Model No.')
    module_serial_5 = StringField('Module 5 Serial No.')
    module_model_6 = StringField('Module 6 Model No.')
    module_serial_6 = StringField('Module 6 Serial No.')
    module_model_7 = StringField('Module 7 Model No.')
    module_serial_7 = StringField('Module 7 Serial No.')
    module_model_8 = StringField('Module 8 Model No,')
    module_serial_8 = StringField('Module 8 Serial No.')
    module_model_9 = StringField('Module 9 Model No.')
    module_serial_9 = StringField('Module 9 Serial No.')
    module_model_10 = StringField('Module 10 Model No.')
    module_serial_10 = StringField('Module 10 Serial No.')
    pc_os = StringField('PC Operating System')
    pc_model = StringField('PC Model')
    software = StringField('Instrument Software')
    software_version = StringField('Instrument Software Version')
    hostname = StringField('Hostname')
    ip_address = StringField('IP Address')
    location_id = SelectField('Location', coerce=int, validators=[DataRequired()], validate_choice=False,
                              choices=[(0, 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[DataRequired()],
                                 choices=[('', 'Please Select')])

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
