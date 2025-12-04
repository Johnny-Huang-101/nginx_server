from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateTimeField, DateField, BooleanField, SelectMultipleField

class Base(FlaskForm):
    db_name = SelectField('Database Name', coerce=int)
    welcome_message = SelectField('Welcome Message', coerce=int)
    icon_img_id = SelectField('Icon', coerce=int)
    logo_img_id = SelectField('Logo', coerce=int)
    bg_img_id = SelectField('Background Image', coerce=int)
    overlay_img_id = SelectField('Overlay Image', coerce=int)
    accession_letter = StringField('Accession Letter')
    accession_counter = StringField('Accession Number')


class Add(Base):
    submit = SubmitField('Submit')

class Edit(Base):
    submit = SubmitField('Submit')

class Approve(Base):
    submit = SubmitField('Submit')

class Update(Base):
    submit = SubmitField('Submit')

