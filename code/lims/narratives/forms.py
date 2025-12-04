from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, IntegerField
from wtforms.validators import DataRequired

narrative_types = [
    ('', '---'),
    ('Initial', 'Initial'),
    ('Summary', 'Summary'),
    ('Summary (AI)', 'Summary (AI)')# here
]

class Base(FlaskForm):
    narrative_type = SelectField('Narrative Type', choices=narrative_types, render_kw={'disabled':True})
    narrative = TextAreaField('Narrative', render_kw={'hidden': True})

# SWEEP #
    notes = TextAreaField('Notes')
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})

class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Submit')

# END SWEEP #

# EXAMPLE CUSTOM VALIDATOR #
    # def validate_fieldname(self, field1, field2):
    #     name = f'{first_name.lower()} {middle_name.lower()} {last_name.lower()}'
    #     if len(Personnel.query.filter_by(name=name).all()) > 1:
    #         raise ValidationError('Person already exists!')
    #
    # https://wtforms.readthedocs.io/en/2.3.x/validators/
    # if applied in all events, insert this to Base(FlaskForm)


class AISummary(Base):
    case_id = IntegerField('Case ID')
    submit = SubmitField('Submit')