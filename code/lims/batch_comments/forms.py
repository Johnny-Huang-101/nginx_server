# NOT USED

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, TextAreaField, IntegerField, BooleanField, \
    SelectMultipleField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    batch_id = SelectField('Batch ID', validators=[DataRequired()], coerce=int)
    reference = BooleanField('From reference table?', validators=[Optional()], render_kw={'hidden': True})
    comment_reference = SelectField('Comment', validators=[Optional()], coerce=int)
    comment_text = TextAreaField('Comment', validators=[Optional()])
    report = BooleanField('Recommend including on tox report')

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
