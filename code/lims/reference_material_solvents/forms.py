from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField


class Base(FlaskForm):
    name = StringField('Solvent')
    abbreviation = StringField('Abbreviation')

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
