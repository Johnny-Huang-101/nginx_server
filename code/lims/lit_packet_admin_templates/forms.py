from flask_wtf import FlaskForm

from wtforms import StringField, SubmitField, TextAreaField, SelectField, FieldList
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    name = StringField('Template Name', validators=[DataRequired(message="Template Name Required")])
    # case_contents = HiddenField('Include Overviews sheet', validators=[Optional()], default='None')


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class UpdateCaseContents(FlaskForm):
    case_contents = SelectField('Case Contents')
    submit = SubmitField('Update')


class SortOrder(FlaskForm):
    fields = [str(x) for x in range(1, 21)]
    for field in fields:
        locals()[f'sort_order_{field}'] = SelectField('Sort Order', coerce=int, validate_choice=False)
    submit = SubmitField('Confirm')
