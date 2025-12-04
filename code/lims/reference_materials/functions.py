import os
import string
from lims import db
from lims.models import Compounds, Divisions, Salts, RefMatSolvents, Units, \
    Users, StorageTemperatures, StatesOfMatter
from flask import url_for, current_app
from lims.locations.functions import location_dict


def get_form_choices(form):

    # Get available analytes to populate "Analyte" drop-down
    compounds = [(item.id, item.name) for item in
                db.session.query(Compounds).order_by(Compounds.name.asc())]
    compounds.insert(0, (0, "Please select a compound"))
    form.compound_id.choices = compounds

    # Get available vendors to populate "Manufacturer" drop-down
    manufacturers = [(vendor.id, vendor.name) for vendor in db.session.query(Divisions).filter_by(vendor='Yes')]
    manufacturers.insert(0, (0, 'Please select a vendor'))
    form.manufacturer_id.choices = manufacturers

    # Get available salts to populate "Salt" drop-down
    salts = [(salt.id, salt.name) for salt in db.session.query(Salts)]
    salts.insert(0, (0, '---'))
    form.salt_id.choices = salts

    # Get available preparations to populate "preparation" drop-down
    states = [(item.id, item.name) for item in StatesOfMatter.query]
    states.insert(0, (0, 'Please select a preparation'))
    form.state_id.choices = states
    
    # Get available reference material solvents to populate "solvent" drop-down
    solvents = [(solvent.id, solvent.name) for solvent in db.session.query(RefMatSolvents)]
    solvents.insert(0, (0, '---'))
    form.solvent_id.choices = solvents

    # Get available units to populate "Units" drop-down
    units = [(unit.id, unit.name) for unit in db.session.query(Units)]
    units.insert(0, (0, '---'))
    form.unit_id.choices = units

    # Get available personnel to populate "analyte" drop-down
    personnel = [(user.id, user.initials) for user in db.session.query(Users)]
    personnel.insert(0, (0, '---'))
    form.received_by.choices = personnel

    temperatures = [(item.id, item.name) for item in StorageTemperatures.query]
    temperatures.insert(0, (0, '---'))
    form.storage_temperature_id.choices = temperatures

    choices = [(k, v['option']) for k, v in location_dict.items()]
    choices.insert(0, ('', 'Please select a location type'))
    form.location_table.choices = choices

    return form


def get_set_letter(letter):
    alphabet = string.ascii_lowercase
    letter = alphabet[alphabet.index(letter)+1]
    return letter

