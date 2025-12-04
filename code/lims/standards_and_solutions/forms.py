from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import FloatField, StringField, SelectField, SubmitField, DateField, BooleanField, SelectMultipleField, IntegerField, ValidationError, TextAreaField
from wtforms.validators import DataRequired, Optional


class InitialBase(FlaskForm):
    solution_type_id = SelectField('Standard/Solution type (i.e., IS, Reagent, etc.)', coerce=int,
                                   validators=[DataRequired()])
    name = SelectField('Constituent Type', coerce=int, choices=[(0, 'Please select a standard/solution type')],
                       validate_choice=False)
    lot = StringField('Standard/Solution Lot', validators=[DataRequired()],
                      render_kw={'placeholder': 'ASSY-MMAATT-STD#-YYYYMMDD'})
    prepared_by = SelectField('Prepared by', coerce=int, validators=[Optional()])
    prepared_date = DateField('Date of preparation', render_kw={'type': 'date'},
                              validators=[DataRequired()])
    retest_date = DateField('Retest Date', render_kw={'type': 'date'},
                            validators=[DataRequired()])
    location_id = SelectField('Location', coerce=str, validate_choice=False,
                              choices=[('0', 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[Optional()],
                                 choices=[('', 'Please Select')])
    description = StringField('Description', validators=[Optional()])
    assay = SelectMultipleField('Select relevant assays', validators=[Optional()])
    no_location = BooleanField('No Current Location')

    def validate_location_id(self, location_id):
        if not self.no_location.data:
            if not location_id.data or location_id.data == '0':
                raise ValidationError('Please select a location')




class InitialAdd(InitialBase):
    submit = SubmitField('Save')
    submit_additional = SubmitField('Save and Add Additional Information')


class Edit(InitialBase):
    submit = SubmitField('Submit')


# class Approve(Base):
#     submit = SubmitField('Submit')
#
#
class Update(InitialBase):
    submit = SubmitField('Save')
    submit_additional = SubmitField('Save and Add Additional Information')


class ImportPrepLog(FlaskForm):
    file = FileField('Select File', render_kw={'accept': '.csv'})
    submit = SubmitField('Submit')


class UpdateRetest(FlaskForm):
    retest_date = DateField('Retest Date', render_kw={'type': 'date'}, validators=[DataRequired()])
    submit = SubmitField('Update')


class AdditionalInformation(FlaskForm):
    concentrator_multiplier = StringField('Concentrator multiplier (If "NA", default 1)',
                                          validators=[Optional()])
    parent_standard_lot = SelectField('Parent standard lot', validators=[Optional()], coerce=int)
    part_a = StringField('Part A name', validators=[Optional()])
    part_a_lot = StringField('Part A lot', validators=[Optional()])
    part_a_exp = DateField('Part A expiration date', render_kw={'type': 'date'}, validators=[Optional()])
    part_b = StringField('Part B name', validators=[Optional()])
    part_b_lot = StringField('Part B lot', validators=[Optional()])
    part_b_exp = DateField('Part B expiration date', render_kw={'type': 'date'}, validators=[Optional()])
    part_c = StringField('Part C name', validators=[Optional()])
    part_c_lot = StringField('Part C lot', validators=[Optional()])
    part_c_exp = DateField('Part C expiration date', render_kw={'type': 'date'}, validators=[Optional()])
    equipment_used = SelectMultipleField('Equipment used', validate_choice=False, coerce=str,
                                         validators=[Optional()])  # Choices from CalibratedLabware
    volume_prepared = FloatField('Volume prepared (in mL)',
                                   validators=[Optional()])
    solvent_used = SelectField('Solvent used', validators=[Optional()], coerce=int)  # Choices from SolventsAndReagents
    aliquot_volume = IntegerField('Aliquot volume (in µL)', validators=[Optional()])
    total_aliquots = IntegerField('Total aliquots', validators=[Optional()])
    pipette_check = BooleanField('Pipette check performed?')
    verification_batches = SelectMultipleField('Verification Batches', validators=[Optional()],
                                               coerce=str)  # Choices from Batches
    previous_lot = SelectMultipleField('Previous lots', validators=[Optional()], coerce=str)  # Same choices as parent_standard_lot
    previous_lot_comments = TextAreaField('Previous lot Details', validators=[Optional()])
    qualitative_comments = TextAreaField('Qualitative Details')
    authorized_date = DateField('Date Authorized for use', validators=[Optional()])
    additional_comments = TextAreaField('Additional Details', validators=[Optional()])
    approved_by = SelectField('Approved by', validators=[Optional()], coerce=int)
    quantitative_comments = TextAreaField('Quantitative Assessment Details', validators=[Optional()])
    calibration_comments = TextAreaField('Calibration Assessment Details', validators=[Optional()])
    verification_comments = TextAreaField('Verification Batches Details', validators=[Optional()])
    preservatives = SelectField('Preservatives added?', validators=[Optional()], coerce=int)
    no_previous_lot = BooleanField('No Previous Lot Available')
    no_part_a = BooleanField('N/A')
    no_part_b = BooleanField('N/A')
    no_part_c = BooleanField('N/A')
    part_a_table = SelectField('Part A Table', choices=[
        ('', '--'), ('standards_and_solutions', 'Prepared Standards and Reagents'), ('solvents_and_reagents', 'Purchased Reagents')
        ])
    part_a_id = SelectField('Part A', coerce=int, validate_choice=False, choices=[(0, 'Please select a table')])
    part_b_table = SelectField('Part B Table', choices=[
        ('', '--'), ('standards_and_solutions', 'Prepared Standards and Reagents'), ('solvents_and_reagents', 'Purchased Reagents')
        ])
    part_b_id = SelectField('Part B', coerce=int, validate_choice=False, choices=[(0, 'Please select a table')])
    part_c_table = SelectField('Part C Table', choices=[
        ('', '--'), ('standards_and_solutions', 'Prepared Standards and Reagents'), ('solvents_and_reagents', 'Purchased Reagents')
        ])
    part_c_id = SelectField('Part C', coerce=int, validate_choice=False, choices=[(0, 'Please select a table')])
    component = SelectMultipleField('Component(s)', validators=[Optional()], coerce=str)
    submit = SubmitField('Save')


class Approve(AdditionalInformation):
    submit = SubmitField('Submit')


class UpdateLocation(FlaskForm):
    location_id = SelectField('Location', coerce=str, validate_choice=False,
                              choices=[('0', 'Please select a location table')])
    location_table = SelectField('Location Type', coerce=str, validators=[Optional()],
                                 choices=[('', 'Please Select')])
    no_location = BooleanField('N/A')
    submit = SubmitField('Submit')


class Series(InitialBase):
    parent_standard_lot = SelectField('Parent standard lot', validators=[Optional()], coerce=int, render_kw={'hidden': True})
    series_submit = SubmitField('Save')
