from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    constituents = SelectMultipleField('Constituents', coerce=str, validators=[DataRequired()])

    notes = TextAreaField('Notes', validators=[Optional()])
    expected_fields = SelectMultipleField('Fields', validators=[DataRequired()])
    requires_admin = BooleanField('Requires Admin Approval')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"},
                                   validators=[Optional()])


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
