from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SubmitField, SelectField, TextAreaField
from wtforms.fields import DateField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    name = StringField('Name')
    compound_id = SelectField('Compound', coerce=int)
    manufacturer_id = SelectField('Manufacturer', coerce=int)
    product_no = StringField('Product No.', validators=[DataRequired(message="Must include product number")])
    lot_no = StringField('Lot No.')
    salt_id = SelectField('Salt', coerce=int)
    state_id = SelectField('Preparation', coerce=int, validators=[DataRequired()])
    solvent_id = SelectField('Solvent', coerce=int)
    amount = StringField('Amount')
    unit_id = SelectField('Units', coerce=int)
    storage_temperature_id = SelectField('Storage Temperature', coerce=int)
    received_date = DateField('Received Date', render_kw={'type': 'date'},
                              validators=[DataRequired(message="Received date must be included")])
    received_by = SelectField('Received By', coerce=int)
    expire_retest = SelectField(
        'Expire/Retest',
        choices=[
            ('Expire', 'Expire'),
            ('Retest', 'Retest')
        ]
    )
    expire_retest_date = DateField('Expire/Retest Date', render_kw={'type': 'date'},
                                   validators=[DataRequired(message="An expiry or retest date must be included")])
    cert_of_analysis = FileField('Certificate of Analysis')
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
