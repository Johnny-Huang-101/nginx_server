from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectMultipleField, IntegerField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    name = StringField('Component Name', validators=[DataRequired()])
    compound_id = SelectMultipleField('Compounds', coerce=int)
    rank = IntegerField('Rank', validators=[Optional()])

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
    submit = SubmitField('Submit')
