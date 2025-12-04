from flask_wtf import FlaskForm
from wtforms import ValidationError, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description')

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
