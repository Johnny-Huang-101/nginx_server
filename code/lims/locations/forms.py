from flask_wtf import FlaskForm

from wtforms import StringField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    item_table = StringField('Item Table', validators=[DataRequired()])
    item_id = IntegerField('Item ID', validators=[DataRequired()])
    location_table = StringField('Location Table', validators=[DataRequired()])
    location_id = StringField('Location ID', validators=[Optional()])


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')


# EXAMPLE CUSTOM VALIDATOR #
    # def validate_fieldname(self, field1, field2):
    #     name = f'{first_name.lower()} {middle_name.lower()} {last_name.lower()}'
    #     if len(Personnel.query.filter_by(name=name).all()) > 1:
    #         raise ValidationError('Person already exists!')
    #
    # https://wtforms.readthedocs.io/en/2.3.x/validators/
    # if applied in all events, insert this to Base(FlaskForm)
