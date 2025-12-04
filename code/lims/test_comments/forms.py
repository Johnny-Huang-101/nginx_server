# NOT USED

from flask_wtf import FlaskForm

from wtforms import SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    test_id = SelectField('Test ID', validate_choice=False)
    test_comment = TextAreaField('Test comment', validators=[DataRequired()])


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


# EXAMPLE CUSTOM VALIDATOR #
    # def validate_fieldname(self, field1, field2):
    #     name = f'{first_name.lower()} {middle_name.lower()} {last_name.lower()}'
    #     if len(Personnel.query.filter_by(name=name).all()) > 1:
    #         raise ValidationError('Person already exists!')
    #
    # https://wtforms.readthedocs.io/en/2.3.x/validators/
    # if applied in all events, insert this to Base(FlaskForm)
