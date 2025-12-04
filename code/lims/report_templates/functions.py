import os
import docx2pdf
import pythoncom
import glob

from lims.models import ReportTemplates

def process_form(path, form, item_id=None):
    """

    Saves.docx and .pdf of the submitted file in the provided path.
    If item_id is provided with no file, rename existing files.

    Parameters
    ----------
    path: str
        String representation of the destination path
    form: FlaskForm
        instance of the submitted FlaskForm
    item_id: int
        id of the report_template to be updated

    Returns
    -------
    None

    """

    file = form.template_file.data
    name = form.name.data
    if form.template_file.data:
        os.makedirs(path, exist_ok=True)
        doc_path = os.path.join(path, f"{name}.docx")
        file.save(doc_path)
        file.close()
        pdf_path = str(os.path.join(path, name).split(".")[0] + ".pdf")
        pythoncom.CoInitialize()
        docx2pdf.convert(doc_path, pdf_path)

    if item_id:
        item = ReportTemplates.query.get(item_id)
        files = glob.glob(f"{path}\{item.name}*")
        if item.name != form.name.data:
            for f in files:
                os.rename(f, f.replace(item.name, form.name.data))
        # else:
        #     for f in files:
        #         os.remove(f)





