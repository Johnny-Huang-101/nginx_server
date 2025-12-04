from lims.models import *
from unidecode import unidecode
from PIL import Image
from urllib.request import urlopen

def get_form_choices(form):
    """
    Get choices for:
        - drug_class_id - DrugClasses
        - drug_monograph_id - Drugmonographs

    Parameters
    ----------
    form (FlaskForm)

    Returns
    -------
    form (FLaskForm)

    """

    # Drug classes
    drug_class_choices = [(item.id, item.name) for item in DrugClasses.query.order_by(DrugClasses.name)]
    drug_class_choices.insert(0, (0, 'Please select a drug class'))
    form.drug_class_id.choices = drug_class_choices

    # Drug monographs
    drug_monographs = [(item.id, item.name) for item in DrugMonographs.query.order_by(DrugMonographs.name)]
    drug_monographs.insert(0, (0, '---'))
    form.drug_monograph_id.choices = drug_monographs

    return form


def process_form(form, path, item_id):
    """

    Save a .png file of the chemical structure in the specified path. Structures are
    obtained using an OPSIN request:

    https://opsin.ch.cam.ac.uk/opsin/<iupac>.png.

    Parameters
    ----------
    form (FlaskForm):
        instance of the submitted flask form
    path (str):
        path to save the structure png file
    item_id (int):
        id of the item. Files are saved as <item_id>.png in the specified path

    Returns
    -------

    """
    url = "https://opsin.ch.cam.ac.uk/opsin/"
    replace_dict = {
        " ": "%20", # spaces forbidden in URL, %20 is the character for a space
        "\u00B2": "2", # change superscript 2 to normal 2
        #"\u03b1": "alpha"

    }
    if form.iupac:
        iupac = form.iupac.data
        # Replace characters based on replace_dict
        for old, new in replace_dict.items():
            iupac = iupac.replace(old, new)

        print(iupac)
        # Get image from OPSIN and save
        structure = f'{url}{iupac}.png'
        img = Image.open(urlopen(structure))
        print(img)
        img.save(f"{path}\{item_id}.png")