from lims.models import Instruments, SampleFormats

def get_form_choices(form):

    instruments = [(item.id, item.instrument_id) for item in Instruments.query.order_by(Instruments.name.asc())]
    instruments.insert(0, (0, 'Please select an instrument'))
    form.instrument_id.choices = instruments

    formats = [(item.id, item.name) for item in SampleFormats.query.order_by(SampleFormats.name.asc())]
    formats.insert(0, (0, 'Please select a sample format'))
    form.sample_format_id.choices = formats

    return form

