import os
import pathlib
from datetime import datetime, timedelta
import string

import pythoncom
from flask import render_template, current_app, jsonify
from sqlalchemy import or_
from win32com.client import Dispatch
# from app import com_lock
# com_lock= ""
from lims.models import *
from lims import db, current_user
from lims.specimens.forms import Approve, Edit
from lims.view_templates.views import approve_item, edit_item
from lims.specimen_audit.views import add_specimen_audit
from lims.evidence_comments.functions import add_comments
from lims.redis_lock import DistributedRedisLock

# fields_dict is imported into each module that uses the print function, it is passed in as label_attributes below
fields_dict = {
    'blank_matrix': {'template': 'blank_matrix', 'CASE_NUM': None, 'MATRIX': None, 'ACC_NUM': None, 'PREP_DATE': None,
                     'EXP_DATE': None, 'COUNTER': None, 'QR': None, 'amount': 0},
    'container': {'template': 'container', 'CASE_NUM': None, 'ACC_NUM': None, 'CODE': None, 'TYPE': None, 'QR': None,
                  'DISCIPLINE': None, 'amount': 0},
    'extraction': {'template': 'extraction', 'CASE_NUM': None, 'TEST_NAME': None, 'ACC_NUM': None, 'QR': None,
                   'HAMILTON_FV': None, 'HAMILTON_SC': None, 'VIAL_POS': None, 'amount': 0},
    'extraction_cohb': {'template': 'extraction_cohb', 'CASE_NUM': None, 'ACC_NUM': None, 'TEST_NAME': None,
                        'QR': None, 'amount': 0},
    'gcet_istd': {'template': 'gcet_istd', 'COUNTER': None, 'LOT_NUM': None, 'PREP_BY': None, 'PREP_DATE': None,
                  'EXP_DATE': None, 'QR': None, 'amount': 0},
    'initial_labels': {'template': 'initial_labels', 'CASE_NUM': None, 'DATE': None, 'LAST': None, 'FIRST': None,
                       'CODE': None, 'TYPE': None, 'QR': None, 'amount': 0},
    'histo_initial': {'template': 'histo_initial', 'ACC_NUM': None, 'FIRST': None, 'LAST': None, 'DATE': None,
                      'amount': 0},
    'reagent_lg': {'template': 'reagent_lg', 'REAGENT': None, 'DESCRIPTION': None, 'LOT_NUM': None, 'PREP_DATE': None,
                   'EXP_DATE': None, 'PREP_BY': None, 'QR': None, 'DATE_TEXT': 'Prep Date', 'BY_TEXT': 'Prep By',
                   'amount': 0},
    'specimen': {'template': 'specimen', 'LAST_FIRST': None, 'CASE_NUM': None, 'ACC_NUM': None, 'CODE': None,
                 'TYPE': None, 'QR': None, 'amount': 0},
    'generic': {'template': 'generic', 'LAST': None, 'FIRST': None, 'CASE_NUM': None, 'DOC': None, 'amount': 0},
    'histo_slides': {'template': 'histo_slides', 'TYPE': None, 'ACC_NUM': None, 'QR': None, 'amount': 0},
    'equipment': {'template': 'equipment', 'EQUIP_ID': None, 'TYPE': None, 'QR': None, 'amount': 0},
    'hp_specimen': {'template': 'hp_specimen', 'CASE_NUM': None, 'ACC_NUM': None, 'CODE': None, 'QR': 'None',
                    'amount': 0},
    'gcet_qc': {'template': 'gcet_qc', 'LOT': None, 'EXP': None, 'PREP_BY': None, 'QR': 'None',
                'COUNTER': 'None'},
    'bundle': {'template': 'bundle', 'TEXT': None},
    'stock_jar': {'template': None, 'CASE_NUM': None, 'LAST': None, 'FIRST': None, 'DATE': None}
}


# COUNTER should be a string in the format of the actual counter (e.g., 001/003)
# QR is the path to the generated QR code
# HAMILTON_FV is the hamilton filter vial position, HAMILTON_SC is the hamilton sample carrier position
# CODE is the sample type code, TYPE is the full string of the sample type
# REAGENT is the name of the prepared reagent (e.g., LCQ Recon)
# DESCRIPTION is the description of the prepared reagent (e.g., (80 MPA:20 MeOH))
# LAST_FIRST is LAST NAME, First Name (e.g., DOE, John)
# amount is the number of labels to be printed, optional attribute
# Every field for hp_specimen occurs twice with an "_1" for the subsequent field


def print_label(printer, label_attributes, dual_printer=False, roll=None):
    """ Prints specimen accession labels.

    Args:

        printer (str): Printer being used

        label_attributes (old) (dict): All label attributes, create from fields_dict before being passed in

        label_attributes (list): Array of dictionaries, each dictionary is the "fields_dict" for that individual label

        dual_printer (bool): Set to True if a twin turbo label writer is being used, used for initial labels and
        specimen labels.

        roll (int): Roll to be used if printer is twin turbo. 0 = Left Roll, 1 = Right Roll, 2 = Auto Switch

    Returns:

    """

    # with com_lock:
    with DistributedRedisLock("dymo_global"):
        # Uninitialize
        pythoncom.CoUninitialize()

        try:

            # printer = r"\\OCMEG9CM09.medex.sfgov.org\DYMO LabelWriter 450 Twin Turbo";

            print(f'PRINTER: {printer}')
            # Get label template name
            label_template = f'{label_attributes[0]["template"]}.label'

            # Set label template path
            label_path = os.path.join(current_app.root_path, 'static/label_templates', label_template)

            # Initialize COM library
            pythoncom.CoInitialize()

            # Get printer object
            printer_com = Dispatch('Dymo.DymoAddIn')

            # Select relevant printer
            printer_com.SelectPrinter(printer)

            # Load label template from label path
            printer_com.Open(label_path)

            # Assign the label object
            printer_label = Dispatch('Dymo.DymoLabels')

            # Set relevant fields of label
            # Iterate through list of label attributes
            for entry in label_attributes:
                for k, v in entry.items():
                    if k != 'template' and k != 'amount':
                        if k != 'QR' and k != 'QR_1':
                            printer_label.SetField(k, v)
                        else:
                            printer_label.SetImageFile(k, v)

                # Print labels
                printer_com.StartPrintJob()
                if dual_printer:
                    printer_com.Print2(1, False, roll)
                else:
                    printer_com.Print(1, False)

            # End printing
            printer_com.EndPrintJob()
        finally:
            # Uninitialize
            pythoncom.CoUninitialize()
