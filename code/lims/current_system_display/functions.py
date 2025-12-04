from lims import app
from lims.models import *
import os
import shutil

def get_form_choices(form):

    img_choices = [(item.id, item.name) for item in
                   SystemImages.query.order_by(SystemImages.name.asc()).all()]
    img_choices.insert(0, (0, '---'))

    db_names = [(item.id, item.message) for item in SystemMessages.query.filter_by(name='LIMS Name')]
    welcome_messages = [(item.id, item.message) for item in SystemMessages.query.filter_by(name='System Message')]

    form.icon_img_id.choices = img_choices
    form.logo_img_id.choices = img_choices
    form.bg_img_id.choices = img_choices
    form.overlay_img_id.choices = img_choices
    form.db_name.choices = db_names
    form.welcome_message.choices = welcome_messages

    return form


def process_form(form, path):

    app.config['SYSTEM_NAME'] = SystemMessages.query.get(form.db_name.data).message
    app.config['SYSTEM_WELCOME'] = SystemMessages.query.get(form.welcome_message.data).message

    icon_img_path = None
    logo_img_path = None
    bg_img_path = None
    overlay_img_path = None

    if form.icon_img_id.data:
        icon_img = SystemImages.query.get(form.icon_img_id.data).image_file
        current_display_handler(icon_img, path, 'icon')
        icon_img_path = '/static/filesystem/current_system_display/icon.png'

    if form.logo_img_id.data:
        logo_img = SystemImages.query.get(form.logo_img_id.data).image_file
        current_display_handler(logo_img, path, 'logo')
        logo_img_path = '/static/filesystem/current_system_display/logo.png'


    if form.bg_img_id.data:
        bg_img = SystemImages.query.get(form.bg_img_id.data).image_file
        current_display_handler(bg_img, path, 'background')
        bg_img_path = '/static/filesystem/current_system_display/background.png'


    if form.overlay_img_id.data:
        overlay_img = SystemImages.query.get(form.overlay_img_id.data).image_file
        current_display_handler(overlay_img, path, 'overlay')
        overlay_img_path = '/static/filesystem/current_system_display/overlay.png'

    app.config['ICON_IMG'] = icon_img_path
    app.config['LOGO_IMG'] = logo_img_path
    app.config['BACKGROUND_IMG'] = bg_img_path
    app.config['OVERLAY_IMG'] = overlay_img_path

def current_display_handler(image_file, path, image_name):
    original_filepath = os.path.join(app.config['FILE_SYSTEM'], 'system_images', image_file)
    new_filepath = os.path.join(path, f"{image_name}.png")
    shutil.copy(original_filepath, new_filepath)

