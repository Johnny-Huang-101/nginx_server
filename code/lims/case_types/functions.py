from lims.models import *


def get_form_choices(form):

    retention_policies = [(item.id, item.name) for item in RetentionPolicies.query]
    retention_policies.insert(0, (0, '---'))
    form.retention_policy.choices = retention_policies

    assays = [(str(item.id), item.assay_name) for item in Assays.query]
    assays.insert(0, (0, '---'))
    form.default_assays.choices = assays

    toxicology_templates = [(item.id, item.name) for item in ReportTemplates.query.filter_by(discipline='Toxicology')]
    if len(toxicology_templates):
        toxicology_templates.insert(0, (0, 'Please select a toxicology template'))
    else:
        toxicology_templates.insert(0, (0, 'No toxicology templates'))
    form.toxicology_report_template_id.choices = toxicology_templates

    biochemistry_templates = [(item.id, item.name) for item in ReportTemplates.query.filter_by(discipline='Biochemistry')]
    if len(biochemistry_templates):
        biochemistry_templates.insert(0, (0, 'Please select a biochemistry template'))
    else:
        biochemistry_templates.insert(0, (0, 'No biochemistry templates'))
    form.biochemistry_report_template_id.choices = biochemistry_templates

    histology_templates = [(item.id, item.name) for item in ReportTemplates.query.filter_by(discipline='Histology')]
    if len(histology_templates):
        histology_templates.insert(0, (0, 'Please select a histology template'))
    else:
        histology_templates.insert(0, (0, 'No histology template selected'))
    form.histology_report_template_id.choices = histology_templates

    external_templates = [(item.id, item.name) for item in ReportTemplates.query.filter_by(discipline='External')]
    if len(external_templates):
        external_templates.insert(0, (0, 'Please select a external template'))
    else:
        external_templates.insert(0, (0, 'No external templates'))
    form.external_report_template_id.choices = external_templates

    litigation_packet_templates = [(item.id, item.name) for item in LitigationPacketTemplates.query]
    litigation_packet_templates.insert(0, (0, 'Please select a litigation packet template'))
    form.litigation_packet_template_id.choices = litigation_packet_templates

    return form

def get_orders():

    accession_orders = [item.accession_level for item in CaseTypes.query.order_by(CaseTypes.accession_level).all() if item.accession_level is not None]
    accession_orders = map(str, sorted(map(int, accession_orders)))
    accession_orders = ", ".join(accession_orders)
    accession_orders += " currently in use."

    batch_orders = [item.batch_level for item in CaseTypes.query.order_by(CaseTypes.batch_level).all() if item.batch_level is not None]
    batch_orders = map(str, sorted(map(int, batch_orders)))
    batch_orders = ", ".join(batch_orders)
    batch_orders += " currently in use."

    return (accession_orders, batch_orders)