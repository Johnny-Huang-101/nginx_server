from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    text = StringField('QR Code Explanation', validators=[DataRequired()])
    qr_path = StringField('Path', validators=[Optional()], render_kw={'hidden': True})


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')
