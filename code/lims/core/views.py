from flask import render_template, url_for, request, Blueprint, current_app, send_file, redirect
from flask_login import login_required, current_user
from lims.models import Users, Agencies
from lims import app, db
from sqlalchemy import inspect, DateTime, String, Boolean, Float, Integer

import glob
from pathlib import Path
from datetime import datetime
import os
import pandas as pd
import zipfile
from sqlalchemy.sql import text

core = Blueprint('core', __name__)

@core.route('/')
@login_required
def index():
    user = Users.query.get_or_404(current_user.id)
    
    if current_user.permissions in ['FLD', 'FLD-MethodDevelopment', 'Admin', 'Owner']:
        return redirect(url_for('dashboard.get_dashboard'))
    else:
        return render_template('index.html', user=user)


@core.route('/home')
@login_required
def home():
    user = Users.query.get_or_404(current_user.id)
    if current_user.permissions in ['FLD', 'FLD-MethodDevelopment', 'Admin', 'Owner']:
        return redirect(url_for('dashboard.get_dashboard'))
    else:
        return render_template('index.html', user=user)


@core.route('/import_all')
@login_required
def import_all():
    """
    NOT DEVELOPED FULLY!

    Returns
    -------

    """

    # files = glob.glob(r"")
    # names = [Path(file).name.split(".")[0] for file in files]
    # # names = ['users', 'agencies', 'divisions', 'personnel']
    # # files = [fr"C:\Users\dpasin\Desktop\FLDB Export\{name}.csv" for name in names]
    # models = app.extensions['sqlalchemy'].db
    # table_dict = {}
    # for cls in models.Model.registry.mappers:
    #     table = cls.class_
    #     table.query.delete()
    #     # db.session.commit()
    #     table_name = table.__tablename__
    #     table_dict[table_name] = table
    #
    # print(table_dict)
    # print(names)
    # for table_name in names:
    #     # Get column (name and types) data for table
    #     table = table_dict[table_name]
    #     inst = inspect(table)
    #     print(table_name)
    #     idx = names.index(table_name)
    #     file_path = files[idx]
    #     print(file_path)
    #     df = pd.read_csv(file_path)
    #     print(df)
    #     if '_sa_instance_state' in df.columns:
    #         df.drop('_sa_instance_state', axis=1, inplace=True)
    #
    #     date_cols = []
    #     columns = [x for x in inst.mapper.columns]
    #     for column in columns:
    #         if column.name in df.columns:
    #             if isinstance(column.type, DateTime):
    #                 df[column.name] = pd.to_datetime(df[column.name], errors='ignore')
    #                 date_cols.append(column.name)
    #             if isinstance(column.type, Boolean):
    #                 df[column.name].fillna(False, inplace=True)
    #             if isinstance(column.type, String):
    #                 df[column.name].fillna("", inplace=True)
    #             # if isinstance(column.type, Float):
    #             #     df[column.name].fillna(None, inplace=True)
    #             if isinstance(column.type, Integer):
    #                 df[column.name].fillna(0, inplace=True)
    #
    #     for idx, row in df.iterrows():
    #         item_dict = {}
    #         for name, val in row.iteritems():
    #             # if name in date_cols:
    #             if pd.isnull(val):
    #                 val = None
    #
    #             item_dict[name] = val
    #         print(item_dict)
    #         item = table(**item_dict)
    #         db.session.add(item)
    #         db.session.commit()

    return redirect(url_for('cases.view_list'))

@core.route('/export_all')
def export_all():

    models = app.extensions['sqlalchemy'].db
    path = os.path.join(current_app.config['FILE_SYSTEM'], 'exports', f'FLDB Export_{datetime.now().strftime("%Y%m%d%H%M")}.zip')
    with zipfile.ZipFile(path, "w") as zf:
        for cls in models.Model.registry.mappers:
            table = cls.class_
            if table.query.count():
                name = table.__tablename__

                if name == 'cases' and (not current_user or current_user.permissions != 'Admin'):
                    sql = text("SELECT * FROM cases")
                    result = db.session.execute(sql)
                    query = result.mappings().all()
                    df = pd.DataFrame(query)
                else: 
                    df = pd.DataFrame([item.__dict__ for item in table.query])

                with zf.open(f"{name}.csv", "w") as buffer:
                    df.to_csv(buffer, index=False)

    return send_file(path,
             as_attachment=True,
             download_name=f'FLDB_Export_{datetime.now().strftime("%Y%m%d%H%M")}.zip')

