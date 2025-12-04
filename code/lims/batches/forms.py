from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, \
    SubmitField, DateField, SelectMultipleField, IntegerField, DateTimeField
from wtforms.validators import DataRequired, Optional, Regexp, ValidationError


class Base(FlaskForm):
    assay_id = SelectField('Assay', coerce=int, validate_choice=False,
                           validators=[DataRequired()])
    test_id_order = StringField('Test Order', render_kw={'readonly': True, 'hidden': True})
    test_id = SelectMultipleField('Tests', coerce=int, validate_choice=False,
                                  validators=[DataRequired()])
    instrument_type_id = SelectField('Instrument', coerce=int, validate_choice=False)
    batch_template_id = SelectField('Batch Template ID', coerce=int, validate_choice=False)
    constituent_id = SelectMultipleField('Available Constituents', coerce=int)
    extracted_by_id = SelectField('Extracting Analyst (EA)', coerce=int)
    extraction_date = DateField('Extraction Date', render_kw={'type': 'date'}, default=datetime.now().date())
    Notes = TextAreaField('Notes')


class Add(FlaskForm):
    assay_id = SelectField('Assay', coerce=int, validate_choice=False,
                           validators=[DataRequired()])
    test_id_order = StringField('Test Order', render_kw={'readonly': True, 'hidden': True})
    test_id = SelectMultipleField('Tests', coerce=int, validate_choice=False,
                                  validators=[DataRequired()])
    submit = SubmitField('Submit')


class Edit(Base):
    submit = SubmitField('Submit')


class Approve(Base):
    submit = SubmitField('Submit')


class Update(FlaskForm):
    assay_id = SelectField('Assay', coerce=int, validate_choice=False,
                           validators=[DataRequired()])
    test_id_order = StringField('Test Order', render_kw={'readonly': True})  # , render_kw={'hidden': True})
    test_id = SelectMultipleField('Tests', coerce=int, validate_choice=False,
                                  validators=[DataRequired()])
    instrument_type_id = SelectField('Instrument', coerce=int, validate_choice=False)
    submit = SubmitField('Submit')


class AssignResources(FlaskForm):
    constituent_id = SelectMultipleField('Available Constituents', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit')


class Duplicate(FlaskForm):
    batch_id = SelectField('Batch ID', coerce=int, validators=[DataRequired()], validate_choice=False)
    test_id = SelectMultipleField('Tests', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit')


class CollectSpecimens(FlaskForm):
    selected_specimens = SelectMultipleField('Specimens Selected', validate_choice=False, coerce=int,
                                             validators=[DataRequired()])
    submit = SubmitField('Confirm')


class ReturnSpecimens(FlaskForm):
    selected_specimens = SelectMultipleField('Specimens Selected', validate_choice=False, coerce=int,
                                             validators=[Optional()])
    custody = SelectField('Next Location', coerce=str, validate_choice=False)
    submit = SubmitField('Confirm')


class BarcodeCheck(FlaskForm):
    source_specimen = StringField('Source Specimen', validators=[Optional()])
    test_specimen = StringField('Test Specimen', validators=[Optional()])
    test_specimen_2 = StringField('Test Specimen', validators=[Optional()])
    submit = SubmitField('Skip')


class Tandem(FlaskForm):
    tandem_id = SelectField('Associated Batch', validators=[DataRequired()],
                            coerce=int, validate_choice=False)
    submit = SubmitField('Submit')


class ResourcesBarcode(FlaskForm):
    constituent_scan = StringField('Scan constituent here', render_kw={'placeholder': 'Scan constituent barcode here'},
                                   validators=[Regexp(r'(standards_and_solutions|solvents_and_reagents):\s*\d+',
                                                      message='NOT A BATCH CONSTITUENT'),
                                               DataRequired('MUST SCAN A BATCH CONSTITUENT')])
    constituent_id = IntegerField('Constituent', validators=[Optional()])
    reagent_id = IntegerField('Reagent', validators=[Optional()])
    batch_id = IntegerField('Batch', validators=[Optional()])
    specimen_check_by = IntegerField('Specimen check', validators=[Optional()])
    specimen_check_date = DateField('Check date', validators=[Optional()])
    submit = SubmitField('Submit')


class ExtractingAnalyst(FlaskForm):
    extracted_by_id = SelectField('Select Extracting Analyst', coerce=int)
    extraction_date = DateField('Extraction Date', validators=[Optional()])
    submit = SubmitField('Submit')


class ProcessingAnalyst(FlaskForm):
    processed_by_id = SelectField('Select Processing Analyst', coerce=int, validators=[Optional()])
    process_date = DateTimeField('Process Date', validators=[Optional()])
    submit_pa = SubmitField('Submit')


class BatchReviewer(FlaskForm):
    reviewed_by_id = SelectField('Select Batch Reviewer', coerce=int, validators=[Optional()])
    review_date = DateTimeField('Review Date', validators=[Optional()])
    submit_br = SubmitField('Submit')


class Instrument(FlaskForm):
    instrument_id = SelectField('Instrument', coerce=int)
    inst_submit = SubmitField('Submit')


class BatchTemplate(FlaskForm):
    batch_template_id = SelectField('Batch Template ID', coerce=int)
    submit = SubmitField('Submit')


class GenerateSequence(FlaskForm):
    batch_id = IntegerField('Batch ID', validators=[Optional()])
    file_name = StringField('File Name', validators=[Optional()])
    file_type = StringField('File Type', validators=[Optional()])
    file_path = StringField('File Path', validators=[Optional()])
    submit_seq = SubmitField('Create')


class HamiltonCheck(FlaskForm):
    fields = ['p1a1', 'p1b1', 'p1c1', 'p1d1', 'p1e1', 'p1f1',
              'p1a2', 'p1b2', 'p1c2', 'p1d2', 'p1e2', 'p1f2',
              'p1a4', 'p1b4', 'p1c4', 'p1d4', 'p1e4', 'p1f4',
              'p1a5', 'p1b5', 'p1c5', 'p1d5', 'p1e5', 'p1f5',
              'p1a7', 'p1b7', 'p1c7', 'p1d7', 'p1e7', 'p1f7',
              'p1a8', 'p1b8', 'p1c8', 'p1d8', 'p1e8', 'p1f8',
              'p2a1', 'p2b1', 'p2c1', 'p2d1', 'p2e1', 'p2f1',
              'p2a2', 'p2b2', 'p2c2', 'p2d2', 'p2e2', 'p2f2',
              'p2a4', 'p2b4', 'p2c4', 'p2d4', 'p2e4', 'p2f4',
              'p2a5', 'p2b5', 'p2c5', 'p2d5', 'p2e5', 'p2f5',
              'p2a7', 'p2b7', 'p2c7', 'p2d7', 'p2e7', 'p2f7',
              'p2a8', 'p2b8', 'p2c8', 'p2d8', 'p2e8', 'p2f8']

    for field in fields:
        locals()[field] = StringField()
        locals()[field + '_date'] = StringField(validators=[Optional()], render_kw={'hidden': 'True'})
    submit = SubmitField('Submit')


class HamiltonSampleCheck(FlaskForm):
    fields = [
        '1-1', '1-2', '1-3', '1-4', '1-5', '1-6', '1-7', '1-8', '1-9', '1-10',
        '1-11', '1-12', '1-13', '1-14', '1-15', '1-16', '1-17', '1-18', '1-19', '1-20',
        '1-21', '1-22', '1-23', '1-24',
        '2-1', '2-2', '2-3', '2-4', '2-5', '2-6', '2-7', '2-8', '2-9', '2-10',
        '2-11', '2-12', '2-13', '2-14', '2-15', '2-16', '2-17', '2-18', '2-19', '2-20',
        '2-21', '2-22', '2-23', '2-24',
        '3-1', '3-2', '3-3', '3-4', '3-5', '3-6', '3-7', '3-8', '3-9', '3-10',
        '3-11', '3-12', '3-13', '3-14', '3-15', '3-16', '3-17', '3-18', '3-19', '3-20',
        '3-21', '3-22', '3-23', '3-24',
        '4-1', '4-2', '4-3', '4-4', '4-5', '4-6', '4-7', '4-8', '4-9', '4-10',
        '4-11', '4-12', '4-13', '4-14', '4-15', '4-16', '4-17', '4-18', '4-19', '4-20',
        '4-21', '4-22', '4-23', '4-24'
    ]

    for field in fields:
        locals()[field] = StringField(validators=[Optional()])
        locals()[field + '_date'] = StringField(validators=[Optional()], render_kw={'hidden': 'True'})
    submit = SubmitField('Submit')


class SequenceCheck(FlaskForm):
    fields_int = list(range(1, 110))
    samq_fields_int = list(range(1, 11))

    fields = map(str, fields_int)
    samq_fields = map(str, samq_fields_int)

    for field in fields:
        locals()[field] = StringField(validators=[Optional()])
        locals()[field + '_date'] = StringField(validators=[Optional()], render_kw={'hidden': 'True'})

    for samq in samq_fields:
        locals()['samq_' + samq] = StringField(validators=[Optional()])
        locals()['samq_' + samq + '_date'] = StringField(validators=[Optional()], render_kw={'hidden': 'True'})
    submit = SubmitField('Submit')


class PopulateConstituents(FlaskForm):
    constituent_type = StringField('Constituent Type', validators=[DataRequired()])
    batch_id = IntegerField('Batch ID', validators=[DataRequired()])
    submit = SubmitField('Submit')


class AssignConstituents(FlaskForm):
    batch_constituent_id = IntegerField('Batch Constituent ID', validators=[DataRequired()])
    constituent_source = StringField('Constituent Source', validators=[DataRequired()])


class ManualConstituents(FlaskForm):
    batch_id = IntegerField('Batch ID', validators=[DataRequired()])
    constituent_type = SelectField('Constituent as it appears in sequence', validators=[DataRequired()], coerce=str)
    populated_from = StringField('Populated From', validators=[Optional()], render_kw={'hidden': 'True'})
    const_submit = SubmitField('Submit')


class PipetteForm(FlaskForm):
    pipettes = SelectMultipleField('Pipettes', choices=[], coerce=str, validators=[DataRequired()])
    pip_submit = SubmitField('Submit')


class DeletePipetteForm(FlaskForm):
    pipettes = SelectMultipleField('Select Pipettes to Delete', choices=[], coerce=str, validators=[DataRequired()])
    pip_submit = SubmitField('Delete')


def dynamic_form(items):
    # Creates form dynamically for SAMQ constituents
    class SAMQConstituents(FlaskForm):
        pass

    for test in items:
        field_name = f'test_{test.id}'
        field = SelectMultipleField('Constituents')
        setattr(SAMQConstituents, field_name, field)

    setattr(SAMQConstituents, 'samq_submit', SubmitField('Submit'))

    return SAMQConstituents()

# class SAMQConstituents(FlaskForm):
#
#     def __init__(self, items):
#         super(SAMQConstituents, self).__init__()
#
#         for test in items:
#             field_name = f'test_{test.id}_id'
#             field = IntegerField('TEST ID')
#
#             setattr(self, field_name, field)
#
#             self._fields[field_name] = field
#
#     batch_id = IntegerField('Batch ID', validators=[DataRequired()])
#
#     samq_submit = SubmitField('Submit')


class DilutionUpdate(FlaskForm):
    id_test = IntegerField('Test ID', validators=[DataRequired()], render_kw={'hidden': True})
    dilution = StringField('Dilution factor', validators=[DataRequired()])
    dilution_submit = SubmitField('Submit')


class DirectiveUpdate(FlaskForm):
    id_test = IntegerField('Test ID', validators=[DataRequired()], render_kw={'hidden': True})
    directives = StringField('Directives', validators=[DataRequired()])
    directive_submit = SubmitField('Submit')


class AddComment(FlaskForm):
    comment_item_type = StringField('Item Type')
    comment_item_id = IntegerField('Test ID', validators=[DataRequired()], render_kw={'hidden': True})
    comment_id = SelectField('Select from Comment Reference', validate_choice=False)
    comment_text = StringField('Enter Manual Comment')
    comment_type = StringField('Comment Type', render_kw={'hidden': True})
    comment_submit = SubmitField('Submit')


class InstrumentCheck(FlaskForm):
    instrument_check = SelectField('Instrument Check Result', coerce=str,
                                   validators=[DataRequired('Please select a choice')])
    instrument_check_by = IntegerField('Completed By', validators=[Optional()], render_kw={'hidden': True})
    instrument_check_date = DateTimeField('Date', validators=[Optional()], render_kw={'hidden': True})
    inst_check_submit = SubmitField('Submit')


class ExtractionCheck(FlaskForm):
    extraction_check = SelectField('Extraction Check Result', coerce=str,
                                   validators=[Optional('Please select a choice')])
    extraction_check_by = IntegerField('Completed By', validators=[Optional()], render_kw={'hidden': True})
    extraction_check_date = DateTimeField('Date', validators=[Optional()], render_kw={'hidden': True})
    ext_check_submit = SubmitField('Submit')


class TranscribeCheck(FlaskForm):
    transfer_check = StringField('Transcribe Check', validators=[Optional()], render_kw={'hidden': True})
    checked_by_id = IntegerField('Completed By', validators=[Optional()], render_kw={'hidden': True})
    checked_date = DateField('Date', validators=[Optional()], render_kw={'hidden': True})
    transcribe_check_submit = SubmitField('Submit')


class SetNT(FlaskForm):
    test_id = IntegerField('Test ID', validators=[DataRequired()])
    qr_id = SelectField('Comment', coerce=int, validators=[DataRequired()])
    nt_submit = SubmitField('Submit')


class SetFinalized(FlaskForm):
    test_id = IntegerField('Test ID', validators=[DataRequired()])
    fin_submit = SubmitField('Submit')


class SeqChanges(FlaskForm):
    changes_dict = StringField('Changes', render_kw={'hidden': True})
    submit = SubmitField('Confirm')


class GcdpVar(FlaskForm):
    gcdp_assay_id = SelectField('Variant', validators=[Optional()], validate_choice=False)
    submit_gcdp = SubmitField('Confirm')
