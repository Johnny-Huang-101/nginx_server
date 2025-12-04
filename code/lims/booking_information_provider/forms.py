from datetime import datetime
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateField


class Base(FlaskForm):

    name = StringField('Booking information provided by option', validators=[DataRequired()])

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
