from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired
from lims.choices import yes_no

class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    abbreviation = StringField('Abbreviation')
    vendor = SelectField('Vendor?', choices=yes_no)
    manufacturer = SelectField('Manufacturer?', choices=yes_no)

# SWEEP #
    notes = TextAreaField('Notes')
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')

# END SWEEP #

# EXAMPLE CUSTOM VALIDATOR #
    # def validate_fieldname(self, field1, field2):
    #     name = f'{first_name.lower()} {middle_name.lower()} {last_name.lower()}'
    #     if len(Personnel.query.filter_by(name=name).all()) > 1:
    #         raise ValidationError('Person already exists!')
    #
    # https://wtforms.readthedocs.io/en/2.3.x/validators/
    # if applied in all events, insert this to Base(FlaskForm)
