import os
from datetime import timedelta, time 
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import pandas as pd
from lims.models import Tests, Batches, Results
from flask import session, current_app, Blueprint, jsonify, send_file, abort
import requests
from lims import *
import base64
from io import BytesIO
import zipfile

# # Connection string
# conn_str = (
#     "DRIVER={ODBC Driver 17 for SQL Server};"
#     "SERVER=OCME-LIMSDEV.medex.sfgov.org;"
#     "DATABASE=lims_JXH;"
#     "Trusted_Connection=yes;"
# )

# params = quote_plus(conn_str)
# engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# each batch name has 1 ID. each batch id corresponds to n tests and each tests has x results.
blueprint = Blueprint('results_api', __name__)

@blueprint.route('/get_results/<string:batch_id_str>', methods=['GET'])
def get_results_for_batch_str(batch_id_str):
    all_results = []  # Store all result rows
    record_return = {}  # batch_id -> test_id -> list of result_ids

    print("Getting info for the batch name: ", batch_id_str)

    # Step 1: Fetch batch by external batch_id
    batches = Batches.query.filter_by(batch_id=batch_id_str).all()
    total_batches = len(batches)

    if not batches:
        print(f"No batch found at all for the name {batch_id_str}.")
        return jsonify({
            "message": "No batch found for this batch string.",
            "batch_id_str": batch_id_str,
            "batch_count": 0,
            "test_count": 0,
            "result_count": 0,
            "record_return": {},
            "csv_base64": None
        }), 404

    total_tests = 0

    for batch in batches:
        batch_id = batch.id
        # print(f"\nBatch ID (DB): {batch_id}")
        record_return[batch_id] = {}

        # Step 2: Get tests linked to this batch
        tests = Tests.query.filter_by(batch_id=batch_id).all()
        total_tests += len(tests)

        if not tests:
            print(f"  No tests found for this batch {batch_id}.")
            continue

        print("To double check we are loading results for this case number: ", tests[0].case_id)

        for test in tests:
            # print(f"\n  Test ID: {test.id}")
            record_return[batch_id][test.id] = []

            # Step 3: Get results linked to this test
            results = Results.query.filter_by(test_id=test.id, case_id=test.case_id).all()

            if not results:
                print(f"    No results found for test {test.id} in this batch")
                continue

            for row in results:
                row_dict = {col.name: getattr(row, col.name) for col in row.__table__.columns}
                # print(f"    Result: {row_dict}")
                record_return[batch_id][test.id].append(row.id)
                row_dict["batch_id_str"] = batch_id_str
                all_results.append(row_dict)

    if not all_results and total_tests!=0:
        print("\nNo results found to save.")
        return jsonify({
            "message": "Found batch but there are no results for any of the tests",
            "batch_id_str": batch_id_str,
            "batch_count": total_batches,
            "test_count": total_tests,
            "result_count": 0,
            "record_return": record_return,
            "csv_base64": None
        }), 404
    elif not all_results and total_tests==0:
        print("\nNo results found to save.")
        return jsonify({
            "message": "Found batch but there are no tests for this batch",
            "batch_id_str": batch_id_str,
            "batch_count": total_batches,
            "test_count": 0,
            "result_count": 0,
            "record_return": record_return,
            "csv_base64": None
        }), 404

    # Create Excel
    df = pd.DataFrame(all_results)
    
    tests = db.session.query(
        Tests.id,
        Tests.case_id,
        Tests.test_name
    ).all()
    
    tests_df = pd.DataFrame(tests, columns=['id', 'case_id', 'test_name'])
    tests_df = tests_df.rename(columns={'id': 'test_id'})

    df = pd.merge(
        df,
        tests_df,
        how='left',
        on=['test_id', 'case_id']
    )

    columns_to_drop = [
        'db_status', 'locked', 'revision', 'notes', 'communications', 'remove_reason',
        'create_date', 'created_by', 'modify_date', 'modified_by', 'locked_by', 'lock_date', 
        'pending_submitter'#, 'idy'
    ]

    # Only drop columns that actually exist (some may not be present)
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])


    if 'id' in df.columns:
        df = df.rename(columns={'id': 'result_id'})

    cols = df.columns.tolist()
    for col_name in ["test_name","result_id", "test_id", "batch_id_str"]:
        if col_name in cols:
            cols.insert(0, cols.pop(cols.index(col_name)))

    df = df[cols]

    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    # Encode Excel to base64
    encoded = base64.b64encode(output.read()).decode('utf-8')

    print(f"\nPrepared {len(df)} result(s) to return as CSV")

    return jsonify({
        "message": "Results fetched successfully. Dictionary structure is Batch ID --> Tests per batch --> results per test",
        "batch_id_str": batch_id_str,
        "batch_count": total_batches,
        "test_count": total_tests,
        "result_count": len(df),
        "record_return": record_return,
        "csv_base64": encoded
    }), 200




@blueprint.route('/get_the_wiffs/<string:batch_id_str>', methods=['GET'])
def get_the_wiffs(batch_id_str):
    base_dir = os.path.join(os.getcwd(), "lims", "static", "filesystem", "batch_records")
    batch_dir = os.path.join(base_dir, batch_id_str) # trying to find the batch_record that matches

    # print(batch_dir)
    # print("Exists?", os.path.exists(batch_dir))
    # print("Is dir?", os.path.isdir(batch_dir))
    # print("Directory listing:", os.listdir(os.path.dirname(batch_dir)))

    # Check if batch directory exists

    if batch_id_str[:4]!='QTON':
        return jsonify({
            "message": f"Are you putting the right batch name? It should only be QTON cases"
        }), 404
    
    if not os.path.isdir(batch_dir):
        return jsonify({
            "message": f"The batch {batch_id_str} doesnt exist in the lims backend"
        }), 404

    # wiff_files = [os.path.join(batch_dir, f) for f in os.listdir(batch_dir) if f.lower().endswith('.wiff')]
    # Find all .wiff files

    wiff_files = [
        os.path.join(batch_dir, f)
        for f in os.listdir(batch_dir)
        if (
            ('(P)' in f)
            and (
                '.wiff' in f.lower()
                or '.wiff.scan' in f.lower()
                or '.wiff2' in f.lower()
                or 'timeseries.data' in f.lower()
            )
        )
    ]


    if not wiff_files:
        return jsonify({
            "message": f"The batch {batch_id_str} exists but there are no positive wiff files inside it"
        }), 404

    # Create in-memory ZIP file
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in wiff_files:
            arcname = os.path.basename(file_path)  # name inside zip
            zipf.write(file_path, arcname)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{batch_id_str}_wiffs.zip'
    ), 200