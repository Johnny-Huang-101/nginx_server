from lims.models import Batches, CurrentAssayConstituents, Instruments, BatchTemplates


def get_form_choices(form, batch_id=None):
    form.batch_id.choices = [(item.id, f"{item.id} | {item.batch_id}") for
                             item in Batches.query.filter_by(batch_status='Processing')]

    form.batch_id.choices.insert(0, (0, 'Please select a batch'))

    if batch_id is not None:
        form.batch_id.data = batch_id
        batch = Batches.query.get_or_404(batch_id)
        constituents = CurrentAssayConstituents.query.filter_by(assay_id=batch.assay.id, constituent_status=True)
        # CurrentAssayConstituents NOT USED but references/imports left in this file for now
        form.constituent_id.choices = [(item.id, item.assay_constituents.constituent) for item in constituents]

        instruments = Instruments.query.filter_by(instrument_type=batch.assay.instrument.instrument_type)
        form.instrument_id.choices = [(item.id, item.name) for item in instruments]
        form.instrument_id.data = batch.assay.instrument.id

        batch_templates = [(item.id, item.name) for item in BatchTemplates.query.filter(BatchTemplates.max_samples >= batch.test_count)]
        form.batch_template_id.choices = batch_templates

    else:
        constituents = [(item.id, item.assay_constituents.constituent) for item in CurrentAssayConstituents.query]
        instruments = [(item.id, item.name) for item in Instruments.query]

        form.constituent_id.choices = constituents
        form.instrument_id.choices = instruments
        form.batch_template_id.choices = [(0, 'No instrument selected')]

    form.constituent_id.choices.insert(0, (0, "Please select a batch"))
    form.instrument_id.choices.insert(0, (0, "Please select an instrument"))

    return form
