from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SubmitField, SelectField, BooleanField, DateField, IntegerField, TextAreaField
from wtforms.fields.simple import HiddenField
from wtforms.validators import DataRequired, Optional


class Base(FlaskForm):
    case_id = SelectField('Case ID', coerce=int, validators=[DataRequired()])
    agency_id = SelectField('Requested Agency', coerce=int, validators=[Optional()],
                            choices=[(0, 'Please select an Agency')], validate_choice=False)
    division_id = SelectField('Requested Division', coerce=int, validators=[Optional()],
                              choices=[(0, 'Please Select Division')], validate_choice=False)
    personnel_id = SelectField('Requested Personnel', coerce=int, validators=[Optional()],
                               choices=[(0, 'Please select Personnel')], validate_choice=False)
    del_agency_id = SelectField('Delivered Agency', coerce=int, validators=[Optional()],
                                choices=[(0, 'Please select an Agency')], validate_choice=False)
    del_division_id = SelectField('Delivered Division', coerce=int, validators=[Optional()],
                                  choices=[(0, 'Please Select Division')], validate_choice=False)
    del_personnel_id = SelectField('Delivered Personnel', coerce=int, validators=[Optional()],
                                   choices=[(0, 'Please select Personnel')], validate_choice=False)
    packet_name = StringField('Packet Name', validators=[Optional()], render_kw={"hidden": "True"})
    redact = BooleanField('No Redaction', validators=[Optional()])
    remove_pages = BooleanField('No Page Removal', validators=[Optional()])
    requested_date = DateField('Requested Date', render_kw={'type': 'date'}, validators=[Optional()],
                               default=datetime.today)
    due_date = DateField('Due Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivery_date = DateField('Delivery Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivered_to = StringField('Delivered To', validators=[Optional()])
    n_pages = IntegerField('Number of Pages', validators=[Optional()])
    postage_and_delivery = StringField('Postage and Delivery', validators=[Optional()])
    additional_costs = StringField('Additional Costs', validators=[Optional()])
    total_costs = StringField('Total Costs', validators=[Optional()])
    paid_date = DateField('Paid Date', render_kw={'type': 'date'}, validators=[Optional()])
    # file = FileField('Subpoena', validators=[DataRequired(message='This field is required')])
    # subpoena_path = StringField('Upload Subpoena', validators=[Optional()], render_kw={"hidden": "True"})
    packet_status = StringField('Packet Status', validators=[Optional()], render_kw={"hidden": "True"})
    previous_packet_name = HiddenField('Previous Packet Name')


class Add(Base):
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    submit = SubmitField('Update')


class LitPacketUpdate(FlaskForm):
    case_id = StringField('Case ID', render_kw={'readonly': True})
    agency_id = SelectField('Requested Agency', coerce=int, validators=[Optional()],
                            choices=[(0, 'Please select an Agency')], validate_choice=False)
    division_id = SelectField('Requested Division', coerce=int, validators=[Optional()],
                              choices=[(0, 'Please Select Division')], validate_choice=False)
    personnel_id = SelectField('Requested Personnel', coerce=int, validators=[Optional()],
                               choices=[(0, 'Please select Personnel')], validate_choice=False)
    del_agency_id = SelectField('Delivered Agency', coerce=int, validators=[Optional()],
                                choices=[(0, 'Please select an Agency')], validate_choice=False)
    del_division_id = SelectField('Delivered Division', coerce=int, validators=[Optional()],
                                  choices=[(0, 'Please Select Division')], validate_choice=False)
    del_personnel_id = SelectField('Delivered Personnel', coerce=int, validators=[Optional()],
                                   choices=[(0, 'Please select Personnel')], validate_choice=False)
    packet_name = StringField('Packet Name', validators=[Optional()], render_kw={"hidden": "True"})
    redact = BooleanField('No Redaction', validators=[Optional()])
    remove_pages = BooleanField('No Page Removal', validators=[Optional()])
    requested_date = DateField('Requested Date', render_kw={'type': 'date'}, validators=[Optional()])
    due_date = DateField('Due Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivery_date = DateField('Delivery Date', render_kw={'type': 'date'}, validators=[Optional()])
    delivered_to = StringField('Delivered To', validators=[Optional()])
    n_pages = IntegerField('Number of Pages', validators=[Optional()])
    postage_and_delivery = StringField('Postage and Delivery', validators=[Optional()])
    additional_costs = StringField('Additional Costs', validators=[Optional()])
    total_costs = StringField('Total Costs', validators=[Optional()])
    paid_date = DateField('Paid Date', render_kw={'type': 'date'}, validators=[Optional()])
    submit = SubmitField('Submit')


class UploadedCompletedPacket(FlaskForm):
    file = FileField('Completed Packet', validators=[DataRequired(message='This field is required')])
    # completed_packet_path = db.Column(db.String(264))
    # litigation_preparer = db.Column(db.Integer, db.ForeignKey('users.id'))  # backref = prep_user
    # litigation_prepare_date = db.Column(db.DateTime)
    # packet_status = db.Column(db.String(128))
    submit = SubmitField('Submit')

class Communications(FlaskForm):
    communications = TextAreaField('Communications', render_kw={
            'style': "background-color: rgb(221, 204, 238); width:60%; height:120px;"
        })
    submit = SubmitField('Submit')
