# %%
import pandas as pd
import numpy as np
import os
import xml.etree.ElementTree as ET
import bs4
import USPTOSanitizer
import typing
import warnings
import re
import USPTOLogger
import USPTOSanitizer
import USPTOCSVHandler
import USPTOProcessLinks
import USPTOStoreGrantData
import USPTOProcessZipFile
import zipfile
import sqlalchemy
import psycopg2
import pathos
import signal
import logging
import tqdm

# Create and configure logger
logging.basicConfig(filename="AddOn_grant_application_fulltexture_extraction_errors.log",
                    format='%(asctime)s,%(message)s',
                    filemode='a')

# Creating an object
logger = logging.getLogger()
 
# Setting the threshold of logger to DEBUG
logger.setLevel(logging.DEBUG)

def processes_interrupt_initiator():
    """
    Function for multiprocessing.Pool(initializer=threads_interrupt_initiator())
    Each pool process will execute this as part of its initialization.
    Use this to keep safe for multiprocessing...and gracefully interrupt by keyboard
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)



def extract_xml_file_from_zip(zip_file_path):

    # Extract the zipfile to read it
    try:
        zip_file = zipfile.ZipFile(zip_file_path, 'r')
        # Find the xml file from the extracted filenames
        for filename in zip_file.namelist():
            # if '.xml' in filename or '.sgml' in filename:
            if filename.lower().endswith('.xml') or filename.lower().endswith('.sgml'):
                xml_file_name = filename
        # Print stdout message that xml file was found
        print('[xml file found. Filename: {0}]'.format(xml_file_name))
        # Open the file to read lines out of
        xml_file = zip_file.open(xml_file_name, 'r')
        # Extract the contents from the file
        xml_file_contents = xml_file.readlines()
        # Close the file being read from
        zip_file.close()
        
        return xml_file_contents
        
    except Exception as e:
        print(e)
        return None
    
def _extract_grant_gxml4(xml_string, filename):

    # Pass the raw_data data into Element Tree
    document_root = ET.fromstring(xml_string)

    # Start the extraction of XML data
    r = document_root.find('us-bibliographic-data-grant')
    if r is not None:
        # Find the main patent grant data
        for pr in r.findall('publication-reference'):
            for di in pr.findall('document-id'):
                try:
                    document_id = di.findtext('doc-number').strip()
                    document_id = USPTOSanitizer.fix_patent_number(document_id)[:20]
                except:
                    document_id = None

        # Find the main application data
        for ar in r.findall('application-reference'):
            for di in ar.findall('document-id'):
                try: app_no = di.findtext('doc-number')[:20].strip()
                except: app_no = None
                
        try:
            extract_text = ' '.join(
                [t.strip() for t in document_root.itertext()]
            ).strip()
        except:
            extract_text = None
    else:
        return {
            "GrantID" : None,
            "ApplicationID" : None,
            "OrginalRawText": None,
            "FileName": filename
        }
        
    return {
            "GrantID" : document_id,
            "ApplicationID" : app_no,
            "OrginalRawText": extract_text,
            "FileName": filename
        }
    
def _extract_grant_gxml2(xml_string, filename):
    
    document_root = ET.fromstring(xml_string)
    
    # SDOBI is the bibliographic data
    r = document_root.find('SDOBI')
    if r is not None:
        # B100 Document Identification
        for B100 in r.findall('B100'):
            try:
                document_id = USPTOSanitizer.return_element_text(B100.find('B110')).strip()
                document_id = USPTOSanitizer.fix_patent_number(document_id)[:20]
            except:
                document_id = None

        # B200 is Domestic Filing Data
        for B200 in r.findall('B200'):
            # TODO: find this in XML2 applications
            app_country = None
            # Application number
            try: app_no = USPTOSanitizer.return_element_text(B200.find('B210')).strip()[:20]
            except: app_no = None
            
        # if ID could not be find, then we do not need to find the text
        try:
            extract_text = ' '.join(
                [t.strip() for t in document_root.itertext()]
            ).strip()
        except:
            extract_text = None
            
    else:
        return {
            "GrantID" : None,
            "ApplicationID" : None,
            "OrginalRawText": None,
            "FileName": filename
        }

    return {
            "GrantID" : document_id,
            "ApplicationID" : app_no,
            "OrginalRawText": extract_text,
            "FileName": filename
        }

def _extract_application_axml1(xml_string, filename):
    
    document_root = ET.fromstring(xml_string)
    
    r = document_root.find('subdoc-bibliographic-information')

    # Get and fix the document_id data
    di = r.find('document-id')
    if di is not None:
        # This document ID is NOT application number
        try: document_id = di.findtext('doc-number').strip()
        except:
            document_id = None
    else:
        document_id = None

    # Get application filing data
    ar = r.find('domestic-filing-data')
    if ar is not None:
        try: app_no = ar.find('application-number').findtext('doc-number').strip()[:20]
        except: app_no = None
    else:
        document_id = None
    
    try:
        extract_text = ' '.join(
            [t.strip() for t in document_root.itertext()]
        ).strip()
    except:
        extract_text = None

    return {
            "ApplicationID" : app_no,
            "PublicationID" : document_id,
            "OrginalRawText": extract_text,
            "FileName": filename
        }

def _extract_application_axml4(xml_string, filename):
    
    # Pass the raw data into Element tree xml object
    document_root = ET.fromstring(xml_string)

    # Start extract XML data
    for r in document_root.findall('us-bibliographic-data-application'):

        # Get basic document ID information
        pr = r.find('publication-reference')
        pub_doc = pr.find('document-id')

        try:
            document_id = pub_doc.findtext('doc-number').strip()
            document_id = USPTOSanitizer.fix_patent_number(document_id)
        except:
            document_id = None

        # Get application reference data
        ar = r.find('application-reference')
        if ar is not None:
            app_doc = ar.find('document-id')
            try: app_no = app_doc.findtext('doc-number').strip()[:20]
            except: app_no = None
        else:
            app_no = None

    try:
        extract_text = ' '.join(
            [t.strip() for t in document_root.itertext()]
        ).strip()
    except:
        extract_text = None
        
    return {
            "ApplicationID" : app_no,
            "PublicationID" : document_id,
            "OrginalRawText": extract_text,
            "FileName": filename
        }

def extract_grant_application(grant_app_zip_path, uspto_xml_format, filename):
    
    xml_file_contents = extract_xml_file_from_zip(grant_app_zip_path)
    
    # If xml_file_contents is None or False, then return immediately
    if xml_file_contents == None or xml_file_contents == False:
        return []
    
    final_list = []
    
    # Create variables needed to parse the file
    xml_string = ''
    patent_xml_started = False
    # read through the file and append into groups of string.
    # Send the finished strings to be parsed
    # Use uspto_xml_format to determine file contents and parse accordingly
    #print "The xml format is: " + uspto_xml_format
    if uspto_xml_format == "gXML4":

        # Loop through all lines in the xml file
        for line in xml_file_contents:

            # Decode the line from byte-object
            line = USPTOSanitizer.decode_line(line)

            # This identifies the start of well formed XML segment for patent
            # Grant bibliographic information
            if "<us-patent-grant" in line:
                patent_xml_started = True
                xml_string += "<us-patent-grant>"

            # This identifies end of well-formed XML segement for single patent
            # Grant bibliographic information
            elif "</us-patent-grant" in line:
                patent_xml_started = False
                xml_string += "</us-patent-grant>"
                # Call the function extract data
                processed_data_array_dict = _extract_grant_gxml4(xml_string, filename)
                final_list.append(processed_data_array_dict)
                # Reset the xml string
                xml_string = ''

            # This is used to append lines of file when inside single patent grant
            elif patent_xml_started == True:
                # Check which type of encoding should be used to fix the line string
                xml_string += USPTOSanitizer.replace_new_html_characters(line)

    # Used for gXML2 files
    elif uspto_xml_format == "gXML2":

        # Loop through all lines in the xml file
        for line in xml_file_contents:

            # Decode the line from byte-object
            line = USPTOSanitizer.decode_line(line)

            # This identifies the start of well formed XML segment for patent
            # Grant bibliographic information
            if "<PATDOC" in line:
                patent_xml_started = True
                xml_string += "<PATDOC>"

            # This identifies end of well-formed XML segement for single patent
            # Grant bibliographic information
            elif "</PATDOC" in line:
                patent_xml_started = False
                xml_string += "</PATDOC>"

                # Call the function extract data
                processed_data_array_dict = _extract_grant_gxml2(xml_string, filename)
                final_list.append(processed_data_array_dict)
                # Reset the xml string
                xml_string = ''

            # This is used to append lines of file when inside single patent grant
            elif patent_xml_started == True:
                # Check which type of encoding should be used to fix the line string
                xml_string += USPTOSanitizer.replace_old_html_characters(line)

    # read through the file and append into groups of string.
    # Send the finished strings to be parsed
    # Use uspto_xml_format to determine file contents and parse accordingly
    elif uspto_xml_format == "aXML4":

        # Loop through all lines in the xml file
        for line in xml_file_contents:
            # Decode the line from byte-object
            line = USPTOSanitizer.decode_line(line)

            # This identifies the start of well formed XML segment for patent
            # application bibliographic information
            if "<us-patent-application" in line:
                patent_xml_started = True
                xml_string += "<us-patent-application>"

            # This identifies end of well-formed XML segement for single patent
            # application bibliographic information
            elif "</us-patent-application" in line:
                patent_xml_started = False
                xml_string += "</us-patent-application>"

                # Call the function extract data
                processed_data_array_dict = _extract_application_axml4(xml_string, filename)
                final_list.append(processed_data_array_dict)
                # Reset the xml string
                xml_string = ''

            # This is used to append lines of file when inside single patent grant
            elif patent_xml_started == True:
                xml_string += USPTOSanitizer.replace_new_html_characters(line)

    elif uspto_xml_format == "aXML1":

        line_count = 1

        # Loop through all lines in the xml file
        for line in xml_file_contents:

            # Decode the line from byte-object
            line = USPTOSanitizer.decode_line(line)

            # This identifies the start of well formed XML segment for patent
            # application bibliographic information
            if "<patent-application-publication" in line:
                patent_xml_started = True
                xml_string += "<patent-application-publication>"

            # This identifies end of well-formed XML segement for single patent
            # application bibliographic information
            elif "</patent-application-publication" in line:
                patent_xml_started = False
                xml_string += "</patent-application-publication>"

                # Call the function extract data
                processed_data_array_dict = _extract_application_axml1(xml_string, filename)
                final_list.append(processed_data_array_dict)
                # reset the xml string
                xml_string = ''

            # This is used to append lines of file when inside single patent grant
            elif patent_xml_started == True:
                xml_string += USPTOSanitizer.replace_old_html_characters(line)
                
    else:
        print(f'{uspto_xml_format} not in list, return []')
        return []
                
    return final_list
    

def run_pgsql_command(sqlcommand, db_url):
    # Connect to the PostgreSQL database
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    cursor.execute(sqlcommand)

    # Commit changes and close connection
    conn.commit()
    conn.close()

"""TODO: the lowercase here is to solve the conflict between psycopg2 and pd.to_sql + sqlalchemy(case insensitive ~ case sensitive)"""
def update_pgsql_db(df:pd.DataFrame, db_url, table_name, primary_key_column, schema_name=None):
    # Step 1: Get list of primary key IDs from the DataFrame
    df_ids = tuple(df[primary_key_column].drop_duplicates().dropna().tolist())

    # Step 2: Remove rows in the PostgreSQL table with conflicting primary keys
    # Using a tuple for the query placeholders
    
    if not schema_name:
        query_table_name = table_name
    else:
        query_table_name = f'{schema_name}.{table_name}'
    
    if len(df_ids) == 1:
        query = f"DELETE FROM {query_table_name} WHERE {primary_key_column} IN ('{df_ids[0]}')"
    elif len(df_ids) > 1:
        query = f"DELETE FROM {query_table_name} WHERE {primary_key_column} IN {df_ids}"
        
    run_pgsql_command(query, db_url)

    # Step 3: Append DataFrame to the table
    lowercase_df = df.copy()
    lowercase_df.columns = [s.lower() for s in lowercase_df.columns]
    # execute_many(db_url, df, query_table_name)
    # execute_many(db_url=db_url, df=df, table=query_table_name) 
    lowercase_df.to_sql(con=sqlalchemy.create_engine(db_url), 
              name=table_name.lower(), 
              schema=schema_name, 
              if_exists='append',
              index=False
              )

def mp_extract_grant_application_to_pgsql(
    grant_app_zip_path_list, uspto_xml_format_list, filename_list, 
    db_url, table_name, primary_key_column, schema_name=None,
                                 processes=30):
    def _worker_tuple(task_tuple):
        grant_app_zip_path, uspto_xml_format, filename = task_tuple
        
        try:
            rst_list = extract_grant_application(
                grant_app_zip_path, uspto_xml_format, filename
            )
            
            tmp_df = pd.DataFrame(rst_list)
            
            # remove the na in PK
            if uspto_xml_format in ('aXML1', 'aXML4'):
                tmp_df = tmp_df.dropna(
                subset=['ApplicationID', 'FileName']
                )
            elif uspto_xml_format in ('gXML2', 'gXML4'):
                tmp_df = tmp_df.dropna(
                subset=['GrantID', 'FileName']
                )
            else:
                print(f'unsupport uspto_xml_format {uspto_xml_format}')
                raise ValueError('Wrong in uspto_xml_format_list')
            
            
            # send the data to sql
            update_pgsql_db(
                tmp_df,
                db_url, 
                table_name, 
                primary_key_column, 
                schema_name
            )
        except Exception as e:
            print(e)
            logger.error(filename)
            
        return 1
        
    task_chunk_list = [tp for tp in zip(grant_app_zip_path_list, uspto_xml_format_list, filename_list)]
    
    with pathos.multiprocessing.Pool(
        processes=processes,
        initializer=processes_interrupt_initiator
    ) as pool:
        for rst in tqdm.tqdm(pool.imap_unordered(
            _worker_tuple,
            task_chunk_list,
        ), total=len(task_chunk_list)):
            pass
    
# %%
if __name__ == "__main__":
    
    SQL_URL_USPTO = f"postgresql://uspto:Ld58KimTi06v2PnlXTFuLG4@localhost/uspto"
    
    SQL_URL_ADMIN = f"postgresql://postgres:{input('type in admin password of pgsql')}@localhost/uspto"
    
    NEW_SCHEMA_NAME = 'uspto_addon'
    
    run_pgsql_command(
        f"""
        CREATE SCHEMA IF NOT EXISTS {NEW_SCHEMA_NAME};
        """,
        SQL_URL_USPTO
    )
    
    run_pgsql_command(
        f"""
        CREATE TABLE IF NOT EXISTS {NEW_SCHEMA_NAME}.ORGINIALRAWTEXT_a (
        ApplicationID VARCHAR(20) NOT NULL,
        PublicationID VARCHAR(20) DEFAULT NULL,
        OrginalRawText TEXT DEFAULT NULL,
        FileName VARCHAR(45),
        PRIMARY KEY (ApplicationID, FileName)
        );
    """,
    SQL_URL_USPTO
    )
    
    # give the owner to uspto
    
    run_pgsql_command(
    f"""
        CREATE TABLE IF NOT EXISTS {NEW_SCHEMA_NAME}.ORGINIALRAWTEXT_g (
        GrantID VARCHAR(20) NOT NULL,
        ApplicationID VARCHAR(20) DEFAULT NULL,
        OrginalRawText TEXT DEFAULT NULL,
        FileName VARCHAR(45),
        PRIMARY KEY (GrantID, FileName))
    """,
    SQL_URL_USPTO
    )
    
    
    run_pgsql_command(
        f"""
        ALTER SCHEMA {NEW_SCHEMA_NAME} OWNER to uspto;

        GRANT USAGE ON SCHEMA {NEW_SCHEMA_NAME} TO uspto;
        GRANT ALL ON ALL TABLES IN SCHEMA {NEW_SCHEMA_NAME} TO uspto;
        """,    
        SQL_URL_ADMIN
    )
    
    # However, when update, we only use FileName as PK(remove all existed PK, if)

    typ_df_dict = {}
    for typ in ['grant', 'application']:
        typ_df_dict[typ] = pd.read_csv(f'LOG/{typ}_links.log',
                                        names=['url', 'type', 'status']
                                        )
        
        typ_df_dict[typ]['filepath'] = typ_df_dict[typ]['url'].apply(
        lambda x:  os.path.join(
                        './TMP/downloads',
                        os.path.basename(x))
        )
        
        typ_df_dict[typ]['filefolder_base'] = typ_df_dict[typ]['url'].apply(
        lambda x:  os.path.basename(x).split('.')[0]
        )
        
        # ----------------------------------------------------------------------
        """TODO: gAPS has not been dealed in this version"""
        # ----------------------------------------------------------------------
        typ_df_dict[typ] = typ_df_dict[typ][
            (typ_df_dict[typ]['type'] != 'gAPS') &
            (typ_df_dict[typ]['status'] == 'Processed')
        ].copy()
        
        # start to run
        # may cost times...
        
        mp_extract_grant_application_to_pgsql(
            grant_app_zip_path_list=typ_df_dict[typ]['filepath'].to_list(),
            uspto_xml_format_list=typ_df_dict[typ]['type'].to_list(),
            filename_list=typ_df_dict[typ]['filefolder_base'].to_list(),
            db_url=SQL_URL_USPTO,
            table_name=f'ORGINIALRAWTEXT_{typ[0]}',
            primary_key_column='FileName',
            schema_name=NEW_SCHEMA_NAME,
            processes=40
        )
    
    
# %%
