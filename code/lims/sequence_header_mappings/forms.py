from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField


class Base(FlaskForm):
    batch_template_id = SelectField('Batch Template', coerce=int, validate_choice=False)
    sample_name = SelectField('Sample Name', choices=[("", '---')], validate_choice=False)
    data_file = SelectField('Data/Output File', choices=[("", '---')], validate_choice=False)
    dilution = SelectField('Dilution', choices=[("", '---')], validate_choice=False)
    vial_position = SelectField('Vial Position', validate_choice=False)
    comments = SelectField('Comments', choices=[("", '---')], validate_choice=False)
    sample_type = SelectField('Sample Type', validate_choice=False)
    acq_method = SelectField('Acquisition Method', choices=[("", '---')], validate_choice=False)

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
