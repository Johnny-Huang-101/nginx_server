from flask_wtf import FlaskForm
from wtforms import (StringField, SelectField, TextAreaField,
                     SubmitField, DateField, BooleanField, IntegerField)
from wtforms.validators import DataRequired, Optional, ValidationError
from lims.fields import NullableDateField


class Base(FlaskForm):
    name = StringField('Name of the solvent / reagent', validators=[Optional()])  # Used for display purposes
    recd_date = DateField('Date received', render_kw={'type': 'date'}, validators=[Optional()])
    # validators=[DataRequired('Must enter a received date.')])
    recd_by = SelectField('Received by', coerce=int)
    lot = StringField('Solvent / reagent lot', validators=[DataRequired()])
    exp_date = NullableDateField('Solvent / reagent expiration date', render_kw={'type': 'date'})
    no_exp_date = BooleanField('No expiry date')
    # validators=[DataRequired('Must have an expiration date.')])
    # location = SelectField('Solvent / reagent storage location', choices=storage_locations,
    #                        validators=[DataRequired('Must have a storage location.')])  # Implement when locations
    #                                                                                       are added
    # opened_date = DateField('Date opened')  # do we need to record this in LIMS?
    # opened_by = SelectField('Opened by')  # see above
    manufacturer_id = SelectField('Manufacturer', coerce=int, validators=[DataRequired()])
    solution_type_id = SelectField('Standard/Solution type (i.e., QC, Reagent, etc.)', coerce=int,
                                   validators=[DataRequired()])

    constituent = SelectField('Constituent Type', coerce=int, choices=[(0, 'Please select a standard/solution type')],
                              validate_choice=False, validators=[DataRequired()])
    location_id = SelectField('Location', coerce=str, validators=[DataRequired()], validate_choice=False,
                              choices=[(0, 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[DataRequired()],
                                 choices=[('', 'Please Select')])
    description = StringField('Description', validators=[Optional()])

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    def validate_exp_date(self, exp_date):
        if not self.no_exp_date.data:
            if not exp_date.data:
                raise ValidationError('An expiry date must be entered')


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class PrintLabel(FlaskForm):
    amount = IntegerField('Amount of labels', validators=[DataRequired()])
    submit = SubmitField('Submit')