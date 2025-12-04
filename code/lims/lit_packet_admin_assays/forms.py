from flask_wtf import FlaskForm

from wtforms import StringField, SubmitField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    name = SelectField('Name', validators=[DataRequired(message="Name required.")])
    overview_sheet = HiddenField('Include Overviews sheet', validators=[Optional()], default='Yes')
    lit_admin_template_id = SelectField('Template Name', coerce=int, render_kw={'disabled': 'disabled'})

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class FilesUpdate(FlaskForm):
    use_file = SelectField('Include this file', validators=[DataRequired(message='Required')])
    redact_type = SelectField('Redact Type', validators=[DataRequired(message='Redact Type Required')])
    submit = SubmitField('Update')


class UpdateOverview(FlaskForm):
    overview_sheet = SelectField('Overview Sheet')
    submit = SubmitField('Update')


class SortOrder(FlaskForm):
    fields = [str(x) for x in range(1, 21)]
    for field in fields:
        locals()[f'sort_order_{field}'] = SelectField('Sort Order', coerce=int, validate_choice=False)
    submit = SubmitField('Confirm')
