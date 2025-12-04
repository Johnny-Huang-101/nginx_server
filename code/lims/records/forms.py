from flask import flash
from flask_wtf import FlaskForm
from markupsafe import Markup
from wtforms import StringField, SelectField, TextAreaField, FileField, MultipleFileField\
    ,SubmitField, HiddenField, ValidationError
from wtforms.validators import DataRequired, InputRequired, Optional
from werkzeug.utils import secure_filename
from pathlib import Path
from lims.records.functions import *

class ParseFromFilename:
    def __init__(self, get_case_id_by_case_number, get_type_id_from_abbrev):
        self.get_case_id_by_case_number = get_case_id_by_case_number
        self.get_type_id_from_abbrev = get_type_id_from_abbrev

    def __call__(self, form, field):
        files = field.data if isinstance(field.data, (list, tuple)) else [field.data]
        parsed = []

        for fs in files:
            filename = secure_filename(getattr(fs, "filename", "") or "")
            if not filename:
                raise ValidationError("Invalid record filename.")

            stem = Path(filename).stem  # e.g. 2024-1234_C1
            parts = stem.split("_", 1)
            if len(parts) != 2:
                raise ValidationError("Filename must be '<case_number>_<type><number>' (e.g., 2024-1234_C1).")

            file_case_number, after = parts
            if len(after) < 2 or not after[1:].isdigit():
                raise ValidationError("Suffix must be a letter followed by digits (e.g., C1, R12).")

            abbrev = after[0].upper()
            record_number = int(after[1:])
            type_id = self.get_type_id_from_abbrev(abbrev)

            case_id = self.get_case_id_by_case_number(file_case_number)
            if not case_id:
                raise ValidationError(f"Case '{file_case_number}' not found.")

            parsed.append({
                "fs": fs,
                "filename": filename,
                "stem": stem,
                "case_id": case_id,
                "record_type": type_id,
                "record_number": record_number,
            })

        form._parsed_files = parsed  # stash for the view
        
class FilenameMatchesCase:
    def __init__(self, get_case_number_by_case_id, get_type_id_from_abbrev, message=None):
        self.get_case_number_by_case_id = get_case_number_by_case_id
        self.get_type_id_from_abbrev = get_type_id_from_abbrev
        # self.message = message or "Case number in FILENAME does not match selected Case."

    def __call__(self, form, field):
        # field is the FileField
        fs = field.data
        filename = secure_filename(getattr(fs, "filename", "") or "")
        if not filename:
            msg = "Invalid record filename."
            flash(Markup(msg),'error')
            raise ValidationError(msg)

        stem = Path(filename).stem  # e.g., '2024-1234_C1'
        parts = stem.split("_", 1)
        if len(parts) != 2:
            msg = "Record filename must be CaseNum_Suffix#."
            flash(Markup(msg),'error')
            raise ValidationError(msg)
        
        file_case_number, after = parts
        abbrev = after[0].upper()
        r_numb = after[1:]
        if not file_case_number or not after or not r_numb.isdigit() or len(after) < 2:
            msg = "Record filename must be CaseNum_Suffix#."
            flash(Markup(msg),'error')
            raise ValidationError(msg)

        expected = self.get_case_number_by_case_id(form.case_id.data)
        if file_case_number != expected:
            msg = "Case number in Record FILENAME does not match selected Case."
            flash(Markup(msg),'error')
            raise ValidationError(msg)

        mapped_type_id = self.get_type_id_from_abbrev(abbrev)
        if mapped_type_id is None:
            msg = "Record filename has invalid record type suffix."
            flash(Markup(msg),'error')
            raise ValidationError(msg)
        
        existing = (
                    Records.query
                    .filter_by(case_id=form.case_id.data, record_name=stem, db_status='Active')
                    .first()
                )
        if existing:
            flash(Markup("A record with this name already exists for this case."),'error')
            raise ValidationError("A record with this name already exists for this case.")
    
        # Side effects: set other fields based on filename
        form.record_type.data = str(mapped_type_id)
        form.record_name.data = stem
        form.record_number.data = r_numb

def UniqueRecordName(form, field):
    # scope uniqueness to case_id; make it global if you prefer
    existing = (
        Records.query
        .filter_by(case_id=form.case_id.data, record_name=field.data)
        .first()
    )
    if existing:
        flash(Markup("A record with this name already exists for this case."),'error')
        raise ValidationError("A record with this name already exists for this case.")
    
class Base(FlaskForm):
    case_id = SelectField('Case', coerce=int, validators=[Optional()])

    record_name = HiddenField() 
    record_number = HiddenField()
    record_type = HiddenField() 

    notes = TextAreaField('Notes')
    # If module requires_approval
    communications = TextAreaField('Communications', render_kw={'style': "background-color: #fff3cd"})


class Add(Base):
    file = FileField('File', validators=[
            InputRequired(),
            FilenameMatchesCase(get_case_number_by_case_id, get_type_id_from_abbrev),
        ], render_kw={'multiple': False})
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(Base):
    record_name = StringField('Name', validators=[DataRequired()])
    record_number = StringField('Name', validators=[DataRequired()])
    record_type = SelectField('Record Type', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Update')

class AddMulti(Base):
    case_id = SelectField('Case', coerce=int, validators=[Optional()], validate_choice=False, render_kw={'disabled':True})
    file = MultipleFileField('Select File(s) to attach', validators=[
                InputRequired(), 
                ParseFromFilename(get_case_id_by_case_number, get_type_id_from_abbrev)
            ], render_kw={'multiple': True}
    )
    submit = SubmitField('Submit')
