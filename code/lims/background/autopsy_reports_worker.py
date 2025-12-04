import pyodbc
import os
import gzip
import threading
import time
from tqdm import tqdm
from datetime import datetime
from flask import current_app
from datetime import datetime
from app import app
import re
import traceback


def start_connections():

    conn = pyodbc.connect(
                'DRIVER={SQL Server};SERVER=OCME-SQL;DATABASE=FA_Prod_Core;Trusted_Connection=yes'
            )
    
    cursor = conn.cursor()

    connLIMS = pyodbc.connect(
                'DRIVER={SQL Server};SERVER=OCME-LIMS;DATABASE=lims;Trusted_Connection=yes' 
            )
    
    cursorLIMS = connLIMS.cursor()

    return conn, cursor, connLIMS, cursorLIMS

def reconstruct_pdfs():
    
    with app.app_context():
        while True:

            try:
                time.sleep(5)
                conn, cursor, connLIMS, cursorLIMS = start_connections()
                
                # Build stricter pattern-to-ending logic
                pattern_end_conditions = []  # tuples of (LIKE ?, AND ...)

                from datetime import timedelta
                # start_date = datetime(datetime.now().year - 1, 1, 1).strftime("%Y-%m-%d")         # first time (beginning of previous year)
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")              # most recent week; decreases risk of missing files during downtime 
                end_date = end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")     # 1/1/24 to 8/13/25 ~30s with no new files, ~60s with 1450 new files

                ############################################### TODO AFTER renaming convention is effective, remove block below.
                for y in range(2024, datetime.now().year + 1): # range is not inclusive, need +1 to capture
                    prefix_exact = f"{y}-____[_]A"
                    prefix_wild = f"{y}-____[_]A_"
                    prefix_wrong1 = f"{y}-____A"
                    prefix_wrong2 = f"{y}-____A_"
                    prefix_wrong3 = f"{y}-____"
                    prefix_wrong4 = f"{y}-____ v2"

                    # 2025-____A must end in 'A'
                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) = 'A'",
                        prefix_exact
                    ))

                    # 2025-____A_ must end in digit
                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) LIKE '[1-9]'", 
                        prefix_wild
                    ))         

                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) LIKE 'A'", 
                        prefix_wrong1
                    ))          

                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) LIKE '[1-9]'", 
                        prefix_wrong2
                    ))     

                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) LIKE '[0-9]'", 
                        prefix_wrong3
                    ))     
                    
                    pattern_end_conditions.append((
                        "UPPER(OBV.name) LIKE ?", 
                        prefix_wrong4
                    ))            
                ###############################################
                    
                #### FOR PRODUCTION ### 
                # for y in range(2025, datetime.now().year + 1): # range is not inclusive, need +1 to capture
                #     prefix_exact = f"{y}-____[_]A"
                #     prefix_wild = f"{y}-____[_]A_"

                #     # 2025-____A must end in 'A'
                #     pattern_end_conditions.append((
                #         "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) = 'A'",
                #         prefix_exact
                #     ))

                #     # 2025-____A_ must end in digit
                #     pattern_end_conditions.append((
                #         "UPPER(OBV.name) LIKE ? AND RIGHT(OBV.name, 1) LIKE '[1-9]'", 
                #         prefix_wild
                #     ))             
                ####

                # Combine all pattern/ending checks with OR
                pattern_where = " OR ".join([cond for cond, _ in pattern_end_conditions])
                pattern_params = [val for _, val in pattern_end_conditions]

                # Add this to your WHERE clause
                where_clauses = [
                    "OBV.extension = '.pdf'",
                    f"({pattern_where})",
                    "(OBV.description IS NOT NULL AND LTRIM(RTRIM(OBV.description)) NOT LIKE 'Incorrect%')",
                    "OBV.importDate >= ? AND OBV.importDate < ?"
                ]
                params = [*pattern_params, start_date, end_date]

                where_sql = " AND ".join(where_clauses)
                sql = f"""
                    WITH RankedVersions AS (
                        SELECT 
                            EM.DisplayName,
                            OBV.contentId,
                            UPPER(OBV.name) AS name,
                            OBV.version,
                            OBV.importDate,
                            OBV.description,
                            DC.CaseNumber AS case_number,
                            ROW_NUMBER() OVER (PARTITION BY DC.CaseNumber ORDER BY OBV.importDate DESC, OBV.version DESC) AS rn
                        FROM [dbo].[ExternalRepositoryObjectVersion] OBV
                        JOIN [dbo].[ExternalRepositoryObjectLink] OBL ON OBV.objectId = OBL.objectId
                        JOIN [me].[Investigation] INV ON OBL.entityId = INV.guid
                        JOIN [me].[DecedentCase] DC ON DC.DecedentCaseID = INV.DecedentCaseId
                        JOIN [dbo].[Employee] EM ON EM.EmployeeID = OBV.importedBy

                        WHERE {where_sql}
                    )
                    SELECT contentId, name, version, importDate, description, case_number, DisplayName
                    FROM RankedVersions
                    WHERE rn = 1
                """
                        
                # print("🔍 Final SQL query:")
                # print(sql)
                # print("📦 With parameters:")
                # for i, p in enumerate(params, 1):
                #     print(f"  Param {i}: {repr(p)}")

                cursor.execute(sql, params)
                pdf_entries = cursor.fetchall()

                pdf_dict = {
                    (name, version): (content_id, description, import_date, case_number, DisplayName)
                    for content_id, name, version, import_date, description, case_number, DisplayName in pdf_entries
                }                         
                # print(pdf_dict)

                cursorLIMS.execute("""
                    SELECT 
                        fa_OR_name, 
                        fa_OR_version
                    FROM
                        records
                    WHERE
                        record_type = 1;
                """)
                existing_AR = cursorLIMS.fetchall()

                existing_AR = [(os.path.splitext(name)[0], version) for name, version in existing_AR] # strips '.pdf' from fa_OR_name
                existing_versions = {}

                for record_name, version in existing_AR:
                    # Store highest version seen for each record_name
                    if record_name not in existing_versions or version > existing_versions[record_name]:
                        existing_versions[record_name] = version
                
                # print(">>>>>>>>>>>>>>>>>\n", existing_versions)
                remaining_entries = [] # NOTE if there is a new version of the same file the behavior is the newest pdf replaces the old one but both are inserted and recorded in the DB
                for (name, version), (cid, description, import_date, case_number, DisplayName) in pdf_dict.items():
                    existing_version = existing_versions.get(name)
                    if existing_version is None or version > existing_version:
                        remaining_entries.append((cid, name, version, description, import_date, case_number, DisplayName))

                # print(">>>>>>>>>>>>>>>>>\n", remaining_entries)
                # because this is a sync to fa, we are not tracking modifications, only create date and the most recent version

                if not remaining_entries or len(remaining_entries)==0:
                    print("No new Autopsy Report PDFs to process")
                    continue
                
                for content_id, file_name, version, description, importDate, case_number, DisplayName in tqdm(remaining_entries, desc="Reconstructing PDFs", unit="file"):
                    
                    cursor.execute("""
                    SELECT CH.contentData
                    FROM dbo.ExternalRepositoryObjectContentChunk CH
                    WHERE CH.contentId = ?
                    ORDER BY CH.chunkId ASC
                    """, content_id)

                    chunks = cursor.fetchall()

                    if not chunks:
                        tqdm.write(f"[{datetime.now()}] No chunks for {file_name}: contentId {content_id}")
                        continue

                    try:
                        combined_gzip_bytes = b"".join(chunk.contentData for chunk in chunks)
                        pdf_data = gzip.decompress(combined_gzip_bytes)
                    except Exception as e:
                        tqdm.write(f"[{datetime.now()}] Failed decompressing {file_name}: {e}")
                        continue

                    if not file_name.lower().endswith(".pdf"):
                        file_name += ".pdf"
                    
                    cursorLIMS.execute("""
                        SELECT id
                        FROM Cases
                        WHERE case_number = ?
                    """, case_number)

                    case_result = cursorLIMS.fetchone()
                    case_id = case_result[0] if case_result else None

                    ############################################### TODO Remove block below. 
                    lims_file_name = case_number + '_A1'
                    r_numb = 1
                    ###############################################

                    # ### FOR PRODUCTION ###     
                    # lims_file_name = file_name[:-4] if file_name.lower().endswith('.pdf') else file_name
                    #
                    # if re.search(r'^\d{4}-\d{4}_A\.pdf$', file_name): # ####-####_A.pdf
                    #     lims_file_name = case_number + '_A1' ### if starting filename is correct as 2025-0001_A.pdf, it'll become 2025-0001_A1.pdf
                    #     r_numb = 1
                    # elif re.search(r'^\d{4}-\d{4}_A\d{1}\.pdf$', file_name): # ####-####_A#.pdf
                    #     r_numb = file_name[11:12]
                    #     lims_file_name = case_number + '_A' + r_numb
                    # ############
                                             
                    static_dir = os.path.join(app.root_path, 'static', 'filesystem', 'records', case_number)  # you can adjust subfolder like 'pdfs' as needed
                    os.makedirs(static_dir, exist_ok=True)  # will add if the directory doesn't exists
                    save_path = os.path.join(static_dir, lims_file_name + '.pdf')

                    with open(save_path, "wb") as f:
                    
                        if case_id is None:
                            print(f"** NEW CASE DETECTED, {lims_file_name} found but not imported, will check again in 1 hr... THERE IS NO CASE NUMBER FOR THIS REPORT, NOT INSERTED INTO DB EXPLORER")
                        else:

                            f.write(pdf_data)                            
                            cursorLIMS.execute("""
                                INSERT INTO Records (case_id, record_name, record_type, record_number, create_date, created_by, db_status, locked, pending_submitter, revision, fa_OR_version, fa_OR_importDate, fa_OR_name, fa_OR_description, fa_OR_importedBy)
                                VALUES (?, ?, ?, ?, ?, ?,?,?,?,?,?,?,?,?,?)
                            """, (case_id, lims_file_name, 1, r_numb, datetime.now(), 'ZZZ', 'Active', 0, None, 0, version, importDate, file_name, description, DisplayName))

                            connLIMS.commit()

                            print(f"New File inserted into RECORDS LIMS DB")
                            print(f"New file {lims_file_name} detected and saved at {save_path} for case {case_number}")

            except Exception as e:
                print(f"Worker error: {e}")
                traceback.print_exc()
            finally:
                try:
                    if cursor: cursor.close()
                    if conn: conn.close()
                    if cursorLIMS: cursorLIMS.close()
                    if connLIMS: connLIMS.close()
                except Exception as cleanup_err:
                    print(f"Cleanup error: {cleanup_err}")

                print("AR Worker Sleeping for 1 hr...")
                time.sleep(3600) # checks every 1 hr to pull pdfs
                print("AR Worker Woke up, going to check autopsy report right now!")

def autopsy_worker():
    worker = threading.Thread(target=reconstruct_pdfs, daemon = True)
    worker.start()
