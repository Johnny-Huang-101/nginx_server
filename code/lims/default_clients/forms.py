from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, ValidationError
from flask import Markup
from lims.models import DefaultClients, CaseTypes, Agencies


class Base(FlaskForm):
    case_type_id = SelectField('Case Type', coerce=int, validators=[DataRequired()])
    agency_id = SelectField('Submitting Agency', coerce=int, validators=[DataRequired()])
    division_id = SelectField('Default Client', coerce=int, validate_choice=False, validators=[DataRequired()])

# SWEEP #
    notes = TextAreaField('Notes')
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})


class Add(Base):
    submit = SubmitField('Submit')

    def validate_agency_id(self, agency_id):
        default_client = DefaultClients.query.filter_by(case_type_id=self.case_type_id.data, agency_id=agency_id.data).first()
        if default_client:
            case_type = CaseTypes.query.get(self.case_type_id.data).name
            agency = Agencies.query.get(agency_id.data).name
            raise ValidationError(Markup(f'<b>{agency}</b> already has a default client (<b>{default_client.division.name}</b>) for <b>{case_type}</b>'))



class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')

# END SWEEP #

# EXAMPLE CUSTOM VALIDATOR #
    # def validate_fieldname(self, field1, field2):
    #     name = f'{first_name.lower()} {middle_name.lower()} {last_name.lower()}'
    #     if len(Personnel.query.filter_by(name=name).all()) > 1:
    #         raise ValidationError('Person already exists!')
    #
    # https://wtforms.readthedocs.io/en/2.3.x/validators/
    # if applied in all events, insert this to Base(FlaskForm)
