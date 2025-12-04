from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    suffix = StringField('Suffix', validators=[DataRequired()])
    division_id = SelectField('Division', coerce=int)
    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

    unique_fields = ['suffix']

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
