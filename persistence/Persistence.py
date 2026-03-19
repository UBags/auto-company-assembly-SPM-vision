import csv
import base64
from io import StringIO
from datetime import datetime, date
from typing import Union, List, Any

import psycopg2
from psycopg2 import Error
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dateutil.parser import parse

from logutils import LogLevel
# From utils package
from utils.CosThetaFileUtils import createDirectory

# From BaseUtils
from BaseUtils import (
    getFullyQualifiedName
)

from utils.CosThetaPrintUtils import (printBoldRed,
                                      printBoldGreen,
                                      printBoldYellow,
                                      printBoldBlue,
                                      printLight
                                      )

# From Configuration
from Configuration import CosThetaConfigurator
from utils.RedisUtils import notok, ok, logMessageToConsoleAndFile

# NOTE: The following import appears to be UNUSED and can be removed:
# from utils.RedisUtils import *

CosThetaConfigurator.getInstance()  # needs to be called to ensure that configurations are properly loaded

reportMajorDatabaseActions = True
reportMinorDatabaseActions = True
# mode: str = CosThetaConfigurator.getInstance().getApplicationMode()

# To check if Persistence is getting loaded multiple times
# printBoldYellow(f"Initializing Persistence module: {id(__name__)}")

# *********************************Database and Schema Names******************************

# THREAD-SAFETY WARNING: These global variables are NOT thread-safe.
# For multi-threaded/web applications, consider using a class-based approach
# (e.g., PersistenceManager) to encapsulate state or pass configs as parameters.

currentMode: str = "Production"
database_name: str = "auto_company_production"
data_subfolder: str = "Production/"
schema_name: str = "al_hub_and_disc_assembly_schema"


def getCurrentMode() -> str:
    return currentMode


def getDatabaseName() -> str:
    return database_name


def getDataSubFolder() -> str:
    return data_subfolder


def getSchemaName() -> str:
    return schema_name


# *********************************Folders For Images******************************

folderForKnuckleImages: str = ""
folderForHubAndBottomBearingImages: str = ""
folderForTopBearingImages: str = ""
folderForNutAndPlateWasherImages: str = ""
folderForBunkAndNoBunkImages: str = ""
folderForSplitPinAndWasherImages: str = ""
folderForCapImages: str = ""


def getFolderForKnuckleImages() -> str:
    return folderForKnuckleImages


def getFolderForHubAndBottomBearingImages() -> str:
    return folderForHubAndBottomBearingImages


def getFolderForTopBearingImages() -> str:
    return folderForTopBearingImages


def getFolderForNutAndPlateWasherImages() -> str:
    return folderForNutAndPlateWasherImages


def getFolderForBunkAndNoBunkImages() -> str:
    return folderForBunkAndNoBunkImages


def getFolderForSplitPinAndWasherImages() -> str:
    return folderForSplitPinAndWasherImages


def getFolderForCapImages() -> str:
    return folderForCapImages


allowed_roles = ["Administrator", "Supervisor", "Operator"]
logSource = getFullyQualifiedName(__file__)

# *********************************Database Statements******************************
create_database = "CREATE DATABASE {};"
query_get_database_names = '''SELECT datname,
    owner as Owner,
    encoding as Encoding,
    collate as Collate,
    ctype as Ctype,
    privileges as "Access Privileges"
    FROM pg_database;
    '''


def printAllVariables() -> None:
    printLight(f"{getCurrentMode() = }")
    printLight(f"{getDatabaseName() = }")
    printLight(f"{getDataSubFolder() = }")
    printLight(f"{getSchemaName() = }")
    printLight(f"{getFolderForKnuckleImages() = }")
    printLight(f"{getFolderForHubAndBottomBearingImages() = }")
    printLight(f"{getFolderForTopBearingImages() = }")
    printLight(f"{getFolderForNutAndPlateWasherImages() = }")
    printLight(f"{getFolderForBunkAndNoBunkImages() = }")
    printLight(f"{getFolderForSplitPinAndWasherImages() = }")
    printLight(f"{getFolderForCapImages() = }")


def setDatabaseName(mode: str, createDB: bool = True) -> str:
    """
    Set database name based on mode and optionally create/initialize database.

    THREAD-SAFETY WARNING: Modifies global variables. Not thread-safe.
    Consider using a class-based approach for multi-threaded applications.

    Args:
        mode: "test" or "production"
        createDB: Whether to create database and initialize tables

    Returns:
        str: Database name
    """
    global database_name, data_subfolder, currentMode
    global folderForKnuckleImages, folderForHubAndBottomBearingImages, folderForTopBearingImages, folderForNutAndPlateWasherImages
    global folderForBunkAndNoBunkImages, folderForSplitPinAndWasherImages, folderForCapImages
    if mode.lower() == "test":
        database_name = "auto_company_test"
        data_subfolder = "Test/"
        currentMode = "Test"
    else:
        database_name = "auto_company_production"
        data_subfolder = "Production/"
        currentMode = "Production"
    # printBoldBlue(f"In Persistence, {currentMode = }, {database_name = }, {data_subfolder = }")
    if createDB:
        createDatabase(db_name=getDatabaseName())
        createSchema(db_name=getDatabaseName())
        createAllTables(db_name=getDatabaseName())
        ensureIndexesExist(db_name=getDatabaseName(), verbose=reportMajorDatabaseActions)
        insertDefaultMachineSettings(db_name=getDatabaseName())
        insertRole(role_name=allowed_roles[0], db_name=getDatabaseName())
        insertRole(role_name=allowed_roles[1], db_name=getDatabaseName())
        insertRole(role_name=allowed_roles[2], db_name=getDatabaseName())
        insertNewUser(username="admin", password="admin123", first_name="Administrator", middle_name="", last_name="",
                      email="", role_name="Administrator", mobile="", db_name=getDatabaseName())
        insertNewUser(username="costheta", password="costheta123", first_name="Costheta", middle_name="",
                      last_name="User", email="", role_name="Administrator", mobile="", db_name=getDatabaseName())
        insertNewUser(getDatabaseName(), "superuser", "al_costheta@123", "auto_company", "", "Superuser",
                      "Administrator", "", "",
                      remarks="")

    return database_name


def checkIfDatabaseExists(dbname: str) -> bool:
    exists = False
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        aCursor.execute(f"SELECT datname FROM pg_database WHERE datname='{dbname}'")
        rows = aCursor.fetchall()
        exists = bool(rows)
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while checking if database exists: {error}"}, logSource, level=LogLevel.WARNING)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error checking if database exists: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        # raise error
    return exists


def createDatabase(db_name: str) -> None:
    aConnection = None
    try:
        exists = checkIfDatabaseExists(dbname=db_name)
    except:
        exists = False
    if exists:
        return
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        createDBStatement = sql.SQL(create_database).format(sql.Identifier(db_name))
        aCursor.execute(createDBStatement)
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except psycopg2.errors.DuplicateDatabase:
        # Database already exists, this is fine
        pass
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while creating database {db_name}: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error creating database {db_name}: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        # raise error


def showAllDatabases() -> None:
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        aCursor.execute("""SELECT datname from pg_database""")
        rows = aCursor.fetchall()
        # for row in rows:
        #     print("   ", row)
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Message : {error}, {type(error)} while showing all databases"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass


# *********************************Check Connection Statements******************************

enable_pgcrypto = "CREATE EXTENSION IF NOT EXISTS pgcrypto;"


def checkConnection(db_name: str) -> bool:
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # aCursor.execute(enable_pgcrypto)
        aCursor.execute("SELECT version();")
        # Fetch result
        record = aCursor.fetchone()
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        return True
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection check failed: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False


# *********************************Schema Statements******************************

create_schema = "CREATE SCHEMA IF NOT EXISTS {};".format(schema_name)
query_get_schema_names = '''SELECT * FROM pg_catalog.pg_namespace ORDER BY nspname;'''


def createSchema(db_name: str) -> None:
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        createSchemaStatement = sql.SQL(create_schema)
        aCursor.execute(createSchemaStatement)
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except psycopg2.errors.DuplicateSchema:
        # Schema already exists, this is fine
        pass
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while creating schema {schema_name}: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error creating schema {schema_name}: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        # raise error


# *********************************Folders for storing images******************************
def getTodaysDateAsAFolder() -> str:
    return f'{datetime.now().strftime("%Y-%m-%d")}/'


def makeFoldersForImages(mode_data_subfolder):
    global folderForKnuckleImages, folderForHubAndBottomBearingImages, folderForTopBearingImages, folderForNutAndPlateWasherImages
    global folderForBunkAndNoBunkImages, folderForSplitPinAndWasherImages, folderForCapImages
    folderForKnuckleImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForKnuckleImages()}{getTodaysDateAsAFolder()}"
    folderForHubAndBottomBearingImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForHubAndBottomBearingImages()}{getTodaysDateAsAFolder()}"
    folderForTopBearingImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForTopBearingImages()}{getTodaysDateAsAFolder()}"
    folderForNutAndPlateWasherImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForNutAndPlateWasherImages()}{getTodaysDateAsAFolder()}"
    folderForBunkAndNoBunkImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForBunkAndNoBunkImages()}{getTodaysDateAsAFolder()}"
    folderForSplitPinAndWasherImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForSplitPinAndWasherImages()}{getTodaysDateAsAFolder()}"
    folderForCapImages = f"{CosThetaConfigurator.getInstance().getBaseFolderForImages()}{getDataSubFolder()}{CosThetaConfigurator.getInstance().getFolderForCapImages()}{getTodaysDateAsAFolder()}"
    # print(f"{folderForKnuckleImages = }")
    createDirectory(folderForKnuckleImages)
    createDirectory(folderForHubAndBottomBearingImages)
    createDirectory(folderForTopBearingImages)
    createDirectory(folderForNutAndPlateWasherImages)
    createDirectory(folderForBunkAndNoBunkImages)
    createDirectory(folderForSplitPinAndWasherImages)
    createDirectory(folderForCapImages)


# *********************************Some constants******************************

okResult = CosThetaConfigurator.getInstance().getOkCommand()
notokResult = CosThetaConfigurator.getInstance().getNotOKCommand()
notChecked: str = "Not Checked"
notPopulated: str = "Not Populated"
defaultTorqueValue: float = -0.1

# *********************************Table creation statements******************************

create_tables_string: str = '''
-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS al_hub_and_disc_assembly_schema.roles_role_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS al_hub_and_disc_assembly_schema.roles
(
    role_id integer NOT NULL DEFAULT nextval('al_hub_and_disc_assembly_schema.roles_role_id_seq'::regclass),
    role_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    modules_access character varying(255) COLLATE pg_catalog."default",
    CONSTRAINT roles_pkey PRIMARY KEY (role_id),
	CONSTRAINT roles_rolename_key UNIQUE (role_name)
);

-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS al_hub_and_disc_assembly_schema.users_user_id_seq
    INCREMENT BY 1
    START WITH 100
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS al_hub_and_disc_assembly_schema.users
(
    user_id integer NOT NULL DEFAULT nextval('al_hub_and_disc_assembly_schema.users_user_id_seq'::regclass),
    username character varying(100) COLLATE pg_catalog."default" NOT NULL,
    password character varying(1024) COLLATE pg_catalog."default" NOT NULL,
    first_name character varying(100) COLLATE pg_catalog."default" NOT NULL,
    middle_name character varying(100) COLLATE pg_catalog."default",
    last_name character varying(100) COLLATE pg_catalog."default",
    role_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    email character varying(255) COLLATE pg_catalog."default",
    mobile character varying(255) COLLATE pg_catalog."default",
    active_status character varying(20) COLLATE pg_catalog."default" NOT NULL DEFAULT 'YES'::character varying,
    remarks character varying(255) COLLATE pg_catalog."default",
    created_on timestamp without time zone NOT NULL,
    last_login timestamp without time zone,
    CONSTRAINT users_pkey PRIMARY KEY (user_id),
    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_role_name_fkey FOREIGN KEY (role_name)
        REFERENCES al_hub_and_disc_assembly_schema.roles (role_name) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data_record_id_seq
    INCREMENT BY 1
    START WITH 1000
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data
(
    record_id integer NOT NULL DEFAULT nextval('al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data_record_id_seq'::regclass),
    qr_code character varying(255) COLLATE pg_catalog."default" NOT NULL,
    model_name character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    lhs_rhs character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    model_tonnage character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    component_assembly_start_datetime timestamp without time zone,
    check_knuckle_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_knuckle_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_knuckle_datetime timestamp without time zone,
    check_hub_and_bottom_bearing_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_hub_and_bottom_bearing_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_hub_and_bottom_bearing_datetime timestamp without time zone,
    check_top_bearing_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_top_bearing_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_top_bearing_datetime timestamp without time zone,
    check_nut_and_platewasher_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_nut_and_platewasher_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_nut_and_platewasher_datetime timestamp without time zone,
    nut_tightening_torque_1 float DEFAULT -1.0 NOT NULL,
    nut_tightening_torque_1_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    nut_tightening_torque_1_datetime timestamp without time zone,
    free_rotations_done character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    free_rotations_datetime timestamp without time zone,
    check_bunk_for_component_press_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_bunk_for_component_press_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_bunk_for_component_press_datetime timestamp without time zone,
    component_press_done character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    component_press_datetime timestamp without time zone,
    check_no_bunk_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_no_bunk_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_no_bunk_datetime timestamp without time zone,
    nut_tightening_torque_2 float DEFAULT -1.0 NOT NULL,
    nut_tightening_torque_2_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    nut_tightening_torque_2_datetime timestamp without time zone,
    check_splitpin_and_washer_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_splitpin_and_washer_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_splitpin_and_washer_datetime timestamp without time zone,
    check_cap_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_cap_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_cap_datetime timestamp without time zone,
    check_bunk_cap_press_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    check_bunk_cap_press_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    check_bunk_cap_press_datetime timestamp without time zone,
    cap_press_done character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    cap_press_datetime timestamp without time zone,
    free_rotation_torque_1 float DEFAULT -1.0 NOT NULL,
    free_rotation_torque_1_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    free_rotation_torque_1_datetime timestamp without time zone,
    ok_notok_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not OK',
    username character varying(100) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Default User',
    remarks character varying(255) COLLATE pg_catalog."default",
    created_on timestamp without time zone NOT NULL,
    CONSTRAINT hub_and_disc_assembly_data_pkey PRIMARY KEY (record_id),
    CONSTRAINT hub_and_disc_assembly_data_username_fkey FOREIGN KEY (username)
        REFERENCES al_hub_and_disc_assembly_schema.users (username) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

CREATE INDEX IF NOT EXISTS idx_model_name ON al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data(model_name);

CREATE INDEX IF NOT EXISTS idx_qr_code ON al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data (qr_code);

CREATE INDEX IF NOT EXISTS idx_created_on ON al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data(created_on);

-- Create the machine_settings table
CREATE TABLE IF NOT EXISTS al_hub_and_disc_assembly_schema.machine_settings
(
    setting_id integer NOT NULL GENERATED ALWAYS AS IDENTITY,
    NoOfRotation1CCW integer NOT NULL DEFAULT 1 CHECK (NoOfRotation1CCW BETWEEN 0 AND 10),
    NoOfRotation1CW integer NOT NULL DEFAULT 1 CHECK (NoOfRotation1CW BETWEEN 0 AND 10),
    NoOfRotation2CCW integer NOT NULL DEFAULT 1 CHECK (NoOfRotation2CCW BETWEEN 0 AND 10),
    NoOfRotation2CW integer NOT NULL DEFAULT 1 CHECK (NoOfRotation2CW BETWEEN 0 AND 10),
    RotationUnitRPM integer NOT NULL DEFAULT 60 CHECK (RotationUnitRPM BETWEEN 1 AND 200),
    updated_on_date timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT machine_settings_pkey PRIMARY KEY (setting_id)
);
'''


def createAllTables(db_name: str) -> None:
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        createAllTablesStatement = sql.SQL(create_tables_string)
        aCursor.execute(createAllTablesStatement)
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while creating tables in schema {schema_name}: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error creating tables in schema {schema_name}: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass


# *********************************Constants defining user actions******************************

CHANGED_OWN_PASSWORD = "Changed_Own_Password"
ADDED_NEW_USER = "Added_New_User"
CHANGED_OTHERS_PASSWORD = "Changed_Others_Password"
CHANGED_USER_ROLE = "Changed_User_Role"
INACTIVATED_USER = "Inactivated_User"
ACTIVATED_USER = "Activated_User"
SENT_FROM_TO_REPORT = "Sent_From_To_Report"
SENT_AUDIT_REPORT = "Sent_Audit_Report"
SAVED_FROM_TO_REPORT = "Saved_From_To_Report"
SAVED_AUDIT_REPORT = "Saved_Audit_Report"
LOGGED_IN = "Logged_In"
LOGGED_OUT = "Logged_Out"

# ************************* BEGIN - ROLES TABLE ******************************************

insert_table_roles = '''INSERT INTO {}.roles
    (role_id, role_name, modules_access)
    VALUES (
        DEFAULT,
        '{}',
        '{}'
    );
    '''


def insertRole(db_name: str, role_name: str, module_access="") -> bool:
    global schema_name
    done = False
    aConnection = None
    insertStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in insertRole()")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use INSERT ... ON CONFLICT for idempotency and parameterized query
        insertStatement = sql.SQL("""
            INSERT INTO {schema}.roles (role_id, role_name, modules_access)
            VALUES (DEFAULT, %s, %s)
            ON CONFLICT (role_name) DO NOTHING
        """).format(schema=sql.Identifier(schema_name))

        aCursor.execute(insertStatement, (role_name, module_access))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        done = True
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while inserting role {role_name}: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error inserting role {role_name}: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        # raise error
    return done


# ************************* END - ROLES TABLE ******************************************

def checkIfRecordExists(selectStatement: str, db_name: str) -> tuple[bool, int]:
    aConnection = None
    resultRecords = []
    fetchStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        fetchStatement = sql.SQL(selectStatement)
        aCursor.execute(fetchStatement)
        resultRecords = aCursor.fetchall()
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        nRecords = len(resultRecords)
        return True, nRecords
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {fetchStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    return False, 0


# ************************* BEGIN - USERS TABLE ******************************************

insert_table_users = '''INSERT INTO
    {}.users (user_id, username, password, first_name, middle_name, last_name, role_name, email, mobile, active_status, remarks, created_on, last_login)
    VALUES (
        DEFAULT,
        '{}',
        '{}',
        '{}',
        '{}',
        '{}',
        '{}',
        '{}',
        '{}',
        DEFAULT,
        '{}',
        to_timestamp('{}', 'dd-mm-yyyy hh24:mi:ss'),
        to_timestamp('{}', 'dd-mm-yyyy hh24:mi:ss')
    );
    '''

query_table_users_for_specific_username_password_and_role = '''SELECT user_id, username, password, role_name
        FROM {}.users
        WHERE username = '{}';
        '''

query_table_users_for_active_users_passwords_roles = '''SELECT user_id, username, password, role_name
        FROM {}.users
        WHERE active_status = 'YES';
        '''

query_table_users_for_inactive_users_passwords = '''SELECT user_id, username, password, role_name
        FROM {}.users
        WHERE active_status = 'NO';
        '''

query_table_users_for_all_users_passwords_roles = '''SELECT user_id, username, password, role_name
        FROM {}.users;
        '''

update_table_users_with_password_for_specific_username = '''UPDATE {}.users
    SET password = '{}'
    WHERE username = '{}';
    '''

update_table_users_with_rolename_for_specific_username = '''UPDATE {}.users
    SET role_name = '{}'
    WHERE username = '{}';
    '''

inactivate_username_in_table_users = '''UPDATE {}.users
    SET active_status = 'NO'
    WHERE username = '{}';
    '''

activate_username_in_table_users = '''UPDATE {}.users
    SET active_status = 'YES'
    WHERE username = '{}';
    '''


# returns if the insert was executed, and the number of existing records it found with the username
def insertNewUser(db_name: str, username: str, password: str, first_name: str, middle_name: str,
                  last_name: str, role_name: str, email: str, mobile: str, remarks: str = ""):
    global schema_name
    checkUserExistsStatement = query_table_users_for_specific_username_password_and_role.format(schema_name, username)
    executed, nUsers = checkIfRecordExists(db_name=db_name, selectStatement=checkUserExistsStatement)
    # False == not executed; 0 == no existing record found
    if not executed:
        return False, 0
    # True == executed; 1 == at least one record found
    if nUsers > 0:
        return False, 1
    done = False
    aConnection = None
    insertStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use parameterized query to prevent SQL injection
        insertStatement = sql.SQL("""
            INSERT INTO {schema}.users 
                (user_id, username, password, first_name, middle_name, last_name, role_name, 
                 email, mobile, active_status, remarks, created_on, last_login)
            VALUES (DEFAULT, %s, %s, %s, %s, %s, %s, %s, %s, DEFAULT, %s, 
                    to_timestamp(%s, 'DD-MM-YYYY HH24:MI:SS'), 
                    to_timestamp(%s, 'DD-MM-YYYY HH24:MI:SS'))
        """).format(schema=sql.Identifier(schema_name))

        current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        aCursor.execute(insertStatement, (
            username, encodeString(password), first_name, middle_name,
            last_name, role_name, email, mobile, remarks,
            current_time, current_time
        ))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        done = True
    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while inserting role {role_name}: {error}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error inserting role {role_name}: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        # False == not executed; 0 == no existing record found
        return False, 0
    # True == executed; 0 == no record found
    return True, 0


def getIdAndUsernamesAndPasswordsAndRolesForActiveUsers(db_name: str):
    global schema_name
    aConnection = None
    fetchStatement = ''
    resultRecords = []
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        fetchStatement = query_table_users_for_active_users_passwords_roles.format(schema_name)
        fetchStatement = sql.SQL(fetchStatement)
        aCursor.execute(fetchStatement)
        interimResultRecords = aCursor.fetchall()
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        for aRecord in interimResultRecords:
            recordAsList = []
            for i in range(len(aRecord)):
                if i != 2:
                    recordAsList.append(aRecord[i])
                else:
                    recordAsList.append(decodeString(aRecord[i]))
            resultRecords.append(recordAsList)
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {fetchStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    return resultRecords


def getIdAndUsernamesAndPasswordsForInactiveUsers(db_name: str) -> List[List]:
    global schema_name
    aConnection = None
    fetchStatement = ''
    resultRecords = []
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        fetchStatement = query_table_users_for_inactive_users_passwords.format(schema_name)
        fetchStatement = sql.SQL(fetchStatement)
        aCursor.execute(fetchStatement)
        interimResultRecords = aCursor.fetchall()
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        for aRecord in interimResultRecords:
            recordAsList = []
            for i in range(len(aRecord)):
                if i != 2:
                    recordAsList.append(aRecord[i])
                else:
                    recordAsList.append(decodeString(aRecord[i]))
            resultRecords.append(recordAsList)
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {fetchStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    return resultRecords


def getIdAndUsernamesAndPasswordsForAllUsers(db_name: str) -> List[List]:
    global schema_name
    aConnection = None
    fetchStatement = ''
    resultRecords = []
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        fetchStatement = query_table_users_for_all_users_passwords_roles.format(schema_name)
        fetchStatement = sql.SQL(fetchStatement)
        aCursor.execute(fetchStatement)
        interimResultRecords = aCursor.fetchall()
        aConnection.commit()
        aCursor.close()
        aConnection.close()
        for aRecord in interimResultRecords:
            recordAsList = []
            for i in range(len(aRecord)):
                if i != 2:
                    recordAsList.append(aRecord[i])
                else:
                    recordAsList.append(decodeString(aRecord[i]))
            resultRecords.append(recordAsList)
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {fetchStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
    return resultRecords


def updatePassword(username: str, password: str, db_name: str) -> bool:
    global schema_name
    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use parameterized query to prevent SQL injection
        updateStatement = sql.SQL("UPDATE {schema}.users SET password = %s WHERE username = %s").format(
            schema=sql.Identifier(schema_name)
        )
        aCursor.execute(updateStatement, (encodeString(password), username))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False
    return True


def updateRole(username: str, role_name: str, db_name: str) -> bool:
    global schema_name
    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use parameterized query to prevent SQL injection
        updateStatement = sql.SQL("UPDATE {schema}.users SET role_name = %s WHERE username = %s").format(
            schema=sql.Identifier(schema_name)
        )
        aCursor.execute(updateStatement, (role_name, username))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False
    return True


def inactivateUserInDatabase(username: str, db_name: str) -> bool:
    global schema_name
    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use parameterized query to prevent SQL injection
        updateStatement = sql.SQL("UPDATE {schema}.users SET active_status = 'NO' WHERE username = %s").format(
            schema=sql.Identifier(schema_name)
        )
        aCursor.execute(updateStatement, (username,))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False
    return True


def activateInactiveUserInDatabase(username: str, db_name: str):
    global schema_name
    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres",
                                       password="postgres",
                                       host="127.0.0.1",
                                       port="5432",
                                       database=db_name)
        # printBoldYellow(f"Established database connection with {db_name} in Persistence")
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        # Use parameterized query to prevent SQL injection
        updateStatement = sql.SQL("UPDATE {schema}.users SET active_status = 'YES' WHERE username = %s").format(
            schema=sql.Identifier(schema_name)
        )
        aCursor.execute(updateStatement, (username,))
        aConnection.commit()
        aCursor.close()
        aConnection.close()
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource, level=LogLevel.CRITICAL)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False
    return True


# ************************* END - USERS TABLE ******************************************

# ************************* BEGIN - DATA TABLE ******************************************

insert_table_data = '''INSERT INTO {}.hub_and_disc_assembly_data (
    qr_code, model_name, lhs_rhs, model_tonnage, component_assembly_start_datetime,
    check_knuckle_imagefile,     check_knuckle_result,     check_knuckle_datetime,
    check_hub_and_bottom_bearing_imagefile, check_hub_and_bottom_bearing_result, check_hub_and_bottom_bearing_datetime,
    check_top_bearing_imagefile, check_top_bearing_result, check_top_bearing_datetime,
    check_nut_and_platewasher_imagefile, check_nut_and_platewasher_result, check_nut_and_platewasher_datetime,
    nut_tightening_torque_1, nut_tightening_torque_1_result, nut_tightening_torque_1_datetime,
    free_rotations_done, free_rotations_datetime,
    check_bunk_for_component_press_imagefile, check_bunk_for_component_press_result, check_bunk_for_component_press_datetime,
    component_press_done, component_press_datetime,
    check_no_bunk_imagefile, check_no_bunk_result, check_no_bunk_datetime,
    nut_tightening_torque_2, nut_tightening_torque_2_result, nut_tightening_torque_2_datetime,
    check_splitpin_and_washer_imagefile, check_splitpin_and_washer_result, check_splitpin_and_washer_datetime,
    check_cap_imagefile, check_cap_result, check_cap_datetime,
    check_bunk_cap_press_imagefile, check_bunk_cap_press_result, check_bunk_cap_press_datetime,
    cap_press_done, cap_press_datetime,
    free_rotation_torque_1, free_rotation_torque_1_result, free_rotation_torque_1_datetime,
    ok_notok_result, username, remarks, created_on
)
VALUES (
    '{}', '{}', '{}', '{}',          to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    {},   '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    {},   '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    {},   '{}', to_timestamp('{}', 'DD-MM-YYYY HH24:MI:SS'),
    '{}', '{}', '{}',
    NOW()
);'''


def rationaliseOK_NotOK(input: Union[str, bool], includeNotCheckedAsReturnValue: bool = False):
    if not includeNotCheckedAsReturnValue:
        if input is None:
            return notok.upper()
        if isinstance(input, str):
            if input.strip().lower() == "ok":
                return ok.upper()
            if (input.strip().lower() == "notok") or (input.strip().lower() == "not ok"):
                return notok.upper()
            return notok.upper()
        if isinstance(input, bool):
            if input:
                return ok.upper()
            else:
                return notok.upper()
        return notok.upper()
    else:
        if input is None:
            return notChecked
        if isinstance(input, str):
            if input.strip().lower() == "ok":
                return ok.upper()
            if (input.strip().lower() == "notok") or (input.strip().lower() == "not ok"):
                return notok.upper()
            return notChecked
        if isinstance(input, bool):
            if input:
                return ok.upper()
            else:
                return notok.upper()
        return notChecked


def getUniqueModelNames(db_name: str) -> List[str]:
    """
    Retrieve unique model names from the hub_and_disc_assembly_data table.

    Args:
        db_name (str): Database name

    Returns:
        List[str]: List of unique model names.

    Raises:
        Exception: No exceptions are raised. Consider raising if database connection or query fails.
    """
    model_names = []
    try:
        # Establish connection to PostgreSQL database
        with psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                              port="5432", database=db_name) as conn:
            with conn.cursor() as cursor:
                # Execute query to get distinct model names
                query = "SELECT DISTINCT model_name FROM al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data;"
                cursor.execute(query)

                # Fetch all results
                results = cursor.fetchall()

                # Extract model names from results (single column)
                model_names = [row[0] for row in results if row[0] != 'Not Populated']

    except Error as e:
        # print(f"Database error: {e}")
        # raise Exception(f"Failed to fetch model names: {e}")
        return []
    except Exception as e:
        # print(f"Unexpected error: {e}")
        # raise Exception(f"Unexpected error: {e}")
        return []

    return model_names


def checkIfQRCodeExists(qr_code: str, db_name: str) -> bool:
    """
    Check if a given QR code exists in the hub_and_disc_assembly_data table.

    Args:
        db_name (str): Database name
        qr_code (str): QR code to check.

    Returns:
        bool: True if QR code exists, False otherwise.

    Raises:
        Exception: No exceptions are raised. Consider raising if database connection or query fails.
    """
    try:
        # Validate input
        if not qr_code or not isinstance(qr_code, str):
            return False

        # Establish connection to PostgreSQL database
        with psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                              port="5432", database=db_name) as conn:
            with conn.cursor() as cursor:
                # Execute query to check QR code existence
                query = """
                    SELECT EXISTS (
                        SELECT 1 
                        FROM al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data 
                        WHERE qr_code = %s
                    );
                """
                cursor.execute(query, (qr_code,))

                # Fetch result (returns True/False)
                exists = cursor.fetchone()[0]

                return exists

    except Error as e:
        # print(f"Database error: {e}")
        return False
    except ValueError as e:
        # print(f"Input error: {e}")
        return False
    except Exception as e:
        # print(f"Unexpected error: {e}")
        # raise Exception(f"Unexpected error: {e}")
        return False


def reindexIndices(db_name: str) -> bool:
    """
    Reindex both idx_model_name and idx_qr_code for hub_and_disc_assembly_data table.

    Args:
        db_name (str): Database name.

    Returns:
        bool: True if reindexing succeeds, False otherwise.

    Raises:
        Exception: No exceptions are raised. Consider raising if database connection or query fails.
    """
    try:
        # Establish connection to PostgreSQL database
        with psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                              port="5432", database=db_name) as conn:
            # Set autocommit to handle REINDEX
            conn.autocommit = True
            with conn.cursor() as cursor:
                # Reindex both indices
                query = """
                    REINDEX INDEX al_hub_and_disc_assembly_schema.idx_model_name;
                    REINDEX INDEX al_hub_and_disc_assembly_schema.idx_qr_code;
                    REINDEX INDEX al_hub_and_disc_assembly_schema.idx_created_on;
                """
                cursor.execute(query)
                # print("Successfully reindexed idx_model_name, idx_qr_code, and idx_created_on")
                return True

    except Error as e:
        # print(f"Database error during reindexing: {e}")
        # raise Exception(f"Failed to reindex indices: {e}")
        return False
    except Exception as e:
        # print(f"Unexpected error: {e}")
        # raise Exception(f"Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.autocommit = False  # Restore default autocommit state


def reindexQRCodeIndex(db_name: str) -> bool:
    """
    Reindex idx_qr_code for hub_and_disc_assembly_data table.

    Args:
        db_name (str): Database name.

    Returns:
        bool: True if reindexing succeeds, False otherwise.

    Raises:
        Exception: No exceptions are raised. Consider raising if database connection or query fails.
    """
    try:
        # Establish connection to PostgreSQL database
        with psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                              port="5432", database=db_name) as conn:
            # Set autocommit to handle REINDEX
            conn.autocommit = True
            with conn.cursor() as cursor:
                # Reindex both indices
                query = """
                    REINDEX INDEX al_hub_and_disc_assembly_schema.idx_qr_code;
                """
                cursor.execute(query)
                # print("Successfully reindexed idx_model_name, idx_qr_code, and idx_created_on")
                return True

    except Error as e:
        # print(f"Database error during reindexing: {e}")
        # raise Exception(f"Failed to reindex indices: {e}")
        return False
    except Exception as e:
        # print(f"Unexpected error: {e}")
        # raise Exception(f"Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.autocommit = False  # Restore default autocommit state


def insertData(
        db_name: str,
        qr_code: str,
        model_name: str = "Not Populated",
        lhs_rhs: str = "Not Populated",
        model_tonnage: str = "Not Populated",

        component_assembly_start_datetime: str = "",

        check_knuckle_imagefile: str = "Not Populated",
        check_knuckle_result: str = "Not Checked",
        check_knuckle_datetime: str = "",

        check_hub_and_bottom_bearing_imagefile: str = "Not Populated",
        check_hub_and_bottom_bearing_result: str = "Not Checked",
        check_hub_and_bottom_bearing_datetime: str = "",

        check_top_bearing_imagefile: str = "Not Populated",
        check_top_bearing_result: str = "Not Checked",
        check_top_bearing_datetime: str = "",

        check_nut_and_platewasher_imagefile: str = "Not Populated",
        check_nut_and_platewasher_result: str = "Not Checked",
        check_nut_and_platewasher_datetime: str = "",

        nut_tightening_torque_1: float = -1.0,
        nut_tightening_torque_1_result: str = "Not Checked",
        nut_tightening_torque_1_datetime: str = "",

        free_rotations_done: str = "Not Checked",
        free_rotations_datetime: str = "",

        check_bunk_for_component_press_imagefile: str = "Not Populated",
        check_bunk_for_component_press_result: str = "Not Checked",
        check_bunk_for_component_press_datetime: str = "",

        component_press_done: str = "Not Checked",
        component_press_datetime: str = "",

        check_no_bunk_imagefile: str = "Not Populated",
        check_no_bunk_result: str = "Not Checked",
        check_no_bunk_datetime: str = "",

        nut_tightening_torque_2: float = -1.0,
        nut_tightening_torque_2_result: str = "Not Checked",
        nut_tightening_torque_2_datetime: str = "",

        check_splitpin_and_washer_imagefile: str = "Not Populated",
        check_splitpin_and_washer_result: str = "Not Checked",
        check_splitpin_and_washer_datetime: str = "",

        check_cap_imagefile: str = "Not Populated",
        check_cap_result: str = "Not Checked",
        check_cap_datetime: str = "",

        check_bunk_cap_press_imagefile: str = "Not Populated",
        check_bunk_cap_press_result: str = "Not Checked",
        check_bunk_cap_press_datetime: str = "",

        cap_press_done: str = "Not Checked",
        cap_press_datetime: str = "",

        free_rotation_torque_1: float = -1.0,
        free_rotation_torque_1_result: str = "Not Checked",
        free_rotation_torque_1_datetime: str = "",

        ok_notok_result: str = "Not OK",
        username: str = "Default User",
        remarks: str = ""
) -> bool:
    """
    Insert one complete or partial record into hub_and_disc_assembly_data.
    All *_datetime fields are optional — passed as empty string = NULL in DB.
    Uses safe parameterized query.
    """
    global schema_name

    if not qr_code or qr_code.strip() == "":
        return False

    # Normalize result fields (OK / Not OK / Not Checked)
    ok_notok_result = rationaliseOK_NotOK(ok_notok_result)

    result_fields = [
        check_knuckle_result,
        check_hub_and_bottom_bearing_result,
        check_top_bearing_result,
        check_nut_and_platewasher_result,
        nut_tightening_torque_1_result,
        free_rotations_done,
        check_bunk_for_component_press_result,
        component_press_done,
        check_no_bunk_result,
        nut_tightening_torque_2_result,
        check_splitpin_and_washer_result,
        check_cap_result,
        check_bunk_cap_press_result,
        cap_press_done,
        free_rotation_torque_1_result,
    ]

    normalized_results = [
        rationaliseOK_NotOK(val, includeNotCheckedAsReturnValue=True)
        for val in result_fields
    ]

    (
        check_knuckle_result,
        check_hub_and_bottom_bearing_result,
        check_top_bearing_result,
        check_nut_and_platewasher_result,
        nut_tightening_torque_1_result,
        free_rotations_done,
        check_bunk_for_component_press_result,
        component_press_done,
        check_no_bunk_result,
        nut_tightening_torque_2_result,
        check_splitpin_and_washer_result,
        check_cap_result,
        check_bunk_cap_press_result,
        cap_press_done,
        free_rotation_torque_1_result,
    ) = normalized_results

    # Coerce torque values to float, fallback to -1.0
    try:
        nut_tightening_torque_1 = float(nut_tightening_torque_1)
    except (TypeError, ValueError):
        nut_tightening_torque_1 = -1.0

    try:
        nut_tightening_torque_2 = float(nut_tightening_torque_2)
    except (TypeError, ValueError):
        nut_tightening_torque_2 = -1.0

    try:
        free_rotation_torque_1 = float(free_rotation_torque_1)
    except (TypeError, ValueError):
        free_rotation_torque_1 = -1.0

    conn = None
    try:
        conn = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # ─────────────────────────────────────────────────────
        #  Helper to prepare timestamp SQL + parameter
        # ─────────────────────────────────────────────────────
        # def ts_placeholder(dt_str: str) -> tuple[str, list[str]]:
        #     if not dt_str or not dt_str.strip():
        #         return "NULL", []
        #     try:
        #         pg_fmt = getPostgresDatetimeFromString(dt_str.strip())
        #         return "to_timestamp(%s, 'DD-MM-YYYY HH24:MI:SS')", [pg_fmt]
        #     except ValueError:
        #         return "NULL", []

        def ts_placeholder(dt_str: str) -> tuple[str, list[str]]:
            if not dt_str or not dt_str.strip():
                return "NULL", []
            try:
                from BaseUtils import convertToPostgresTimestamp
                pg_fmt = convertToPostgresTimestamp(dt_str.strip())
                return "%s::timestamp", [pg_fmt]
            except ValueError:
                return "NULL", []

        params: list[Any] = []
        placeholders: list[str] = []

        # Core fields
        params.extend([qr_code, model_name, lhs_rhs, model_tonnage])
        placeholders.extend(["%s"] * 4)

        # component_assembly_start_datetime
        sql_part, p = ts_placeholder(component_assembly_start_datetime)
        placeholders.append(sql_part)
        params.extend(p)

        # ── All checking / pressing / torque steps ───────────
        step_data = [
            # image/result/datetime triples
            (check_knuckle_imagefile, check_knuckle_result, check_knuckle_datetime),
            (check_hub_and_bottom_bearing_imagefile, check_hub_and_bottom_bearing_result,
             check_hub_and_bottom_bearing_datetime),
            (check_top_bearing_imagefile, check_top_bearing_result, check_top_bearing_datetime),
            (check_nut_and_platewasher_imagefile, check_nut_and_platewasher_result, check_nut_and_platewasher_datetime),
            (nut_tightening_torque_1, nut_tightening_torque_1_result, nut_tightening_torque_1_datetime),
            # result + datetime pairs (must match INSERT order)
            (free_rotations_done, free_rotations_datetime),
            # back to image/result/datetime triples
            (check_bunk_for_component_press_imagefile, check_bunk_for_component_press_result,
             check_bunk_for_component_press_datetime),
            # result + datetime pair
            (component_press_done, component_press_datetime),
            # back to image/result/datetime triples
            (check_no_bunk_imagefile, check_no_bunk_result, check_no_bunk_datetime),
            (nut_tightening_torque_2, nut_tightening_torque_2_result, nut_tightening_torque_2_datetime),
            (check_splitpin_and_washer_imagefile, check_splitpin_and_washer_result, check_splitpin_and_washer_datetime),
            (check_cap_imagefile, check_cap_result, check_cap_datetime),
            (check_bunk_cap_press_imagefile, check_bunk_cap_press_result, check_bunk_cap_press_datetime),
            # result + datetime pair
            (cap_press_done, cap_press_datetime),
            # back to value/result/datetime triple
            (free_rotation_torque_1, free_rotation_torque_1_result, free_rotation_torque_1_datetime),
        ]

        for item in step_data:
            if len(item) == 3:  # value/result + datetime
                val, res, dt = item
                params.extend([val, res])
                placeholders.extend(["%s", "%s"])

                sql_part, p = ts_placeholder(dt)
                placeholders.append(sql_part)
                params.extend(p)

            else:  # only result + datetime
                res, dt = item
                params.append(res)
                placeholders.append("%s")

                sql_part, p = ts_placeholder(dt)
                placeholders.append(sql_part)
                params.extend(p)

        # Final fields
        params.extend([ok_notok_result, username, remarks])
        placeholders.extend(["%s"] * 3)

        # created_on ← server time
        placeholders.append("NOW()")

        # ── Build & execute ──────────────────────────────────
        query = sql.SQL("""
            INSERT INTO {schema}.hub_and_disc_assembly_data (
                qr_code, model_name, lhs_rhs, model_tonnage, component_assembly_start_datetime,
                check_knuckle_imagefile,     check_knuckle_result,     check_knuckle_datetime,
                check_hub_and_bottom_bearing_imagefile, check_hub_and_bottom_bearing_result, check_hub_and_bottom_bearing_datetime,
                check_top_bearing_imagefile, check_top_bearing_result, check_top_bearing_datetime,
                check_nut_and_platewasher_imagefile, check_nut_and_platewasher_result, check_nut_and_platewasher_datetime,
                nut_tightening_torque_1, nut_tightening_torque_1_result, nut_tightening_torque_1_datetime,
                free_rotations_done, free_rotations_datetime,
                check_bunk_for_component_press_imagefile, check_bunk_for_component_press_result, check_bunk_for_component_press_datetime,
                component_press_done, component_press_datetime,
                check_no_bunk_imagefile, check_no_bunk_result, check_no_bunk_datetime,
                nut_tightening_torque_2, nut_tightening_torque_2_result, nut_tightening_torque_2_datetime,
                check_splitpin_and_washer_imagefile, check_splitpin_and_washer_result, check_splitpin_and_washer_datetime,
                check_cap_imagefile, check_cap_result, check_cap_datetime,
                check_bunk_cap_press_imagefile, check_bunk_cap_press_result, check_bunk_cap_press_datetime,
                cap_press_done, cap_press_datetime,
                free_rotation_torque_1, free_rotation_torque_1_result, free_rotation_torque_1_datetime,
                ok_notok_result, username, remarks, created_on
            ) VALUES ({ph})
        """).format(
            schema=sql.Identifier(schema_name),
            ph=sql.SQL(", ").join(sql.SQL(p) for p in placeholders)
        )

        cur.execute(query, params)
        conn.commit()
        reindexIndices(db_name=db_name)
        return True

    except psycopg2.errors.UniqueViolation:
        # QR code already exists
        return False
    except Exception as e:
        logMessageToConsoleAndFile(None, {"text": f"Insert failed: {type(e).__name__}: {e}"}, logSource, level=LogLevel.CRITICAL)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


all_columns_record_header = [
    "qr_code",
    "model_name",
    "lhs_rhs",
    "model_tonnage",
    "component_assembly_start_datetime",
    "check_knuckle_imagefile",
    "check_knuckle_result",
    "check_knuckle_datetime",
    "check_hub_and_bottom_bearing_imagefile",
    "check_hub_and_bottom_bearing_result",
    "check_hub_and_bottom_bearing_datetime",
    "check_top_bearing_imagefile",
    "check_top_bearing_result",
    "check_top_bearing_datetime",
    "check_nut_and_platewasher_imagefile",
    "check_nut_and_platewasher_result",
    "check_nut_and_platewasher_datetime",
    "nut_tightening_torque_1",
    "nut_tightening_torque_1_result",
    "nut_tightening_torque_1_datetime",
    "free_rotations_done",
    "free_rotations_datetime",
    "check_bunk_for_component_press_imagefile",
    "check_bunk_for_component_press_result",
    "check_bunk_for_component_press_datetime",
    "component_press_done",
    "component_press_datetime",
    "check_no_bunk_imagefile",
    "check_no_bunk_result",
    "check_no_bunk_datetime",
    "nut_tightening_torque_2",
    "nut_tightening_torque_2_result",
    "nut_tightening_torque_2_datetime",
    "check_splitpin_and_washer_imagefile",
    "check_splitpin_and_washer_result",
    "check_splitpin_and_washer_datetime",
    "check_cap_imagefile",
    "check_cap_result",
    "check_cap_datetime",
    "check_bunk_cap_press_imagefile",
    "check_bunk_cap_press_result",
    "check_bunk_cap_press_datetime",
    "cap_press_done",
    "cap_press_datetime",
    "free_rotation_torque_1",
    "free_rotation_torque_1_result",
    "free_rotation_torque_1_datetime",
    "ok_notok_result",
    "username",
    "remarks",
    "created_on"
]

# SQL query with parameterized model_name
select_query_by_model_name = """
SELECT 
    qr_code,
    model_name,
    lhs_rhs,
    model_tonnage,
    component_assembly_start_datetime,
    check_knuckle_imagefile,
    check_knuckle_result,
    check_knuckle_datetime,
    check_hub_and_bottom_bearing_imagefile,
    check_hub_and_bottom_bearing_result,
    check_hub_and_bottom_bearing_datetime,
    check_top_bearing_imagefile,
    check_top_bearing_result,
    check_top_bearing_datetime,
    check_nut_and_platewasher_imagefile,
    check_nut_and_platewasher_result,
    check_nut_and_platewasher_datetime,
    nut_tightening_torque_1,
    nut_tightening_torque_1_result,
    nut_tightening_torque_1_datetime,
    free_rotations_done,
    free_rotations_datetime,
    check_bunk_for_component_press_imagefile,
    check_bunk_for_component_press_result,
    check_bunk_for_component_press_datetime,
    component_press_done,
    component_press_datetime,
    check_no_bunk_imagefile,
    check_no_bunk_result,
    check_no_bunk_datetime,
    nut_tightening_torque_2,
    nut_tightening_torque_2_result,
    nut_tightening_torque_2_datetime,
    check_splitpin_and_washer_imagefile,
    check_splitpin_and_washer_result,
    check_splitpin_and_washer_datetime,
    check_cap_imagefile,
    check_cap_result,
    check_cap_datetime,
    check_bunk_cap_press_imagefile,
    check_bunk_cap_press_result,
    check_bunk_cap_press_datetime,
    cap_press_done,
    cap_press_datetime,
    free_rotation_torque_1,
    free_rotation_torque_1_result,
    free_rotation_torque_1_datetime,
    ok_notok_result,
    username,
    remarks,
    created_on
FROM {schema}.hub_and_disc_assembly_data
WHERE model_name = %s;
"""


# ************************************ REPORTS ****************************************

def getDataByModelName(modelName: str, db_name: str, debug: bool = False) -> str:
    global schema_name
    """
        Fetch records from hub_and_disc_assembly_schema.hub_and_disc_assembly_data for a given model_name
        and return them as a CSV string with column names as the header.

        Args:
            modelName (str): The model name to filter records (required)
            db_name (str): Database name

        Returns:
            str: CSV string with column names as header and records as rows, or empty string on error
        """

    csv_output = StringIO()
    # Create CSV writer
    writer = csv.writer(csv_output, quoting=csv.QUOTE_MINIMAL)

    if not modelName or not isinstance(modelName, str) or not modelName.strip():
        logMessageToConsoleAndFile(None, {"text": "Error: model_name must be a non-empty string"}, logSource, level=LogLevel.CRITICAL)
        writer.writerow(all_columns_record_header)
        return csv_output.getvalue()

    aConnection = None
    aCursor = None
    csv_string = ",".join(all_columns_record_header)

    try:
        # Establish database connection
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Execute query

        # FIXED: Use parameterized query to prevent SQL injection
        current_select_query = sql.SQL(select_query_by_model_name).format(
            schema=sql.Identifier(schema_name)
        )
        if debug:
            logMessageToConsoleAndFile(None, {"text": f"Executing query for model {modelName}"}, logSource, level=LogLevel.DEBUG)
        aCursor.execute(current_select_query, (modelName,))
        records = aCursor.fetchall()

        # Get column names from cursor description
        columns = [desc[0] for desc in aCursor.description]

        # Write header
        writer.writerow(columns)

        # Write records
        for record in records:
            # Format each field to handle types (e.g., timestamps, NULLs)
            formatted_record = []
            for value in record:
                if value is None:
                    formatted_record.append("")
                elif isinstance(value, datetime):
                    formatted_record.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    formatted_record.append(str(value))
            writer.writerow(formatted_record)

        # Get CSV string
        csv_string = csv_output.getvalue()

    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        writer.writerow(all_columns_record_header)
        return csv_output.getvalue()
    finally:
        if aCursor:
            try:
                aCursor.close()
            except:
                pass
        if aConnection:
            try:
                aConnection.close()
            except:
                pass
        csv_output.close()
    if debug:
        logMessageToConsoleAndFile(None, {"text": csv_string}, logSource, level=LogLevel.DEBUG)
    return csv_string


# SQL query with parameterized model_name and date range
select_query_by_model_name_and_date_limits = """
SELECT 
    qr_code,
    model_name,
    lhs_rhs,
    model_tonnage,
    component_assembly_start_datetime,
    check_knuckle_imagefile,
    check_knuckle_result,
    check_knuckle_datetime,
    check_hub_and_bottom_bearing_imagefile,
    check_hub_and_bottom_bearing_result,
    check_hub_and_bottom_bearing_datetime,
    check_top_bearing_imagefile,
    check_top_bearing_result,
    check_top_bearing_datetime,
    check_nut_and_platewasher_imagefile,
    check_nut_and_platewasher_result,
    check_nut_and_platewasher_datetime,
    nut_tightening_torque_1,
    nut_tightening_torque_1_result,
    nut_tightening_torque_1_datetime,
    free_rotations_done,
    free_rotations_datetime,
    check_bunk_for_component_press_imagefile,
    check_bunk_for_component_press_result,
    check_bunk_for_component_press_datetime,
    component_press_done,
    component_press_datetime,
    check_no_bunk_imagefile,
    check_no_bunk_result,
    check_no_bunk_datetime,
    nut_tightening_torque_2,
    nut_tightening_torque_2_result,
    nut_tightening_torque_2_datetime,
    check_splitpin_and_washer_imagefile,
    check_splitpin_and_washer_result,
    check_splitpin_and_washer_datetime,
    check_cap_imagefile,
    check_cap_result,
    check_cap_datetime,
    check_bunk_cap_press_imagefile,
    check_bunk_cap_press_result,
    check_bunk_cap_press_datetime,
    cap_press_done,
    cap_press_datetime,
    free_rotation_torque_1,
    free_rotation_torque_1_result,
    free_rotation_torque_1_datetime,
    ok_notok_result,
    username,
    remarks,
    created_on
FROM {}.hub_and_disc_assembly_data
WHERE model_name = '{}'
  AND created_on >= to_timestamp('{} 00:00:00', 'YYYY-MM-DD HH24:MI:SS')
  AND created_on <  to_timestamp('{} 23:59:59', 'YYYY-MM-DD HH24:MI:SS')
  -- or use: AND created_on::date BETWEEN '{}' AND '{}'
ORDER BY created_on ASC;
"""


def getDataByModelNameAndDateLimits(
        db_name: str,
        modelName: str,
        startDate: str | None,
        endDate: str | None = None,
        debug: bool = False
) -> str:
    """
    Fetch records from hub_and_disc_assembly_schema.hub_and_disc_assembly_data for a given model_name
    and date range, returning them as a CSV string with column names as the header.

    FIXED: Uses parameterized queries and proper date handling to prevent SQL injection and date parsing errors.

    Args:
        db_name: Database name
        modelName: The model name to filter records (required)
        startDate: Start date for created_on (format: YYYY-MM-DD), None for today
        endDate: End date for created_on (format: YYYY-MM-DD), None for today
        debug: Whether to print debug statements

    Returns:
        str: CSV string with column names as header and records as rows, or empty string on error
    """
    global schema_name
    csv_output = StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_MINIMAL)

    # Validate model_name
    if not modelName or not isinstance(modelName, str) or not modelName.strip():
        logMessageToConsoleAndFile(None, {"text": "Error: model_name must be a non-empty string"}, logSource, level=LogLevel.CRITICAL)
        writer.writerow(all_columns_record_header)
        return csv_output.getvalue()

    # Parse and validate dates
    # FIXED: Proper handling of None dates - use today's date instead of 23:59:59
    try:
        if startDate:
            start_dt = parse(startDate).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to today at 00:00:00
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if endDate:
            end_dt = parse(endDate).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Default to today at 23:59:59
            end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    except (ValueError, TypeError) as e:
        logMessageToConsoleAndFile(None, {"text": f"Error parsing dates: {e}"}, logSource, level=LogLevel.CRITICAL)
        writer.writerow(all_columns_record_header)
        return csv_output.getvalue()

    # Swap if start_date > end_date
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    aConnection = None
    aCursor = None
    csv_string = ",".join(all_columns_record_header)

    try:
        # Establish database connection
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # FIXED: Use parameterized query with proper date handling
        # Use created_on::date for date-only comparison
        currentQuery = sql.SQL("""
            SELECT 
                qr_code, model_name, lhs_rhs, model_tonnage, component_assembly_start_datetime,
                check_knuckle_imagefile, check_knuckle_result, check_knuckle_datetime,
                check_hub_and_bottom_bearing_imagefile, check_hub_and_bottom_bearing_result, check_hub_and_bottom_bearing_datetime,
                check_top_bearing_imagefile, check_top_bearing_result, check_top_bearing_datetime,
                check_nut_and_platewasher_imagefile, check_nut_and_platewasher_result, check_nut_and_platewasher_datetime,
                nut_tightening_torque_1, nut_tightening_torque_1_result, nut_tightening_torque_1_datetime,
                free_rotations_done, free_rotations_datetime,
                check_bunk_for_component_press_imagefile, check_bunk_for_component_press_result, check_bunk_for_component_press_datetime,
                component_press_done, component_press_datetime,
                check_no_bunk_imagefile, check_no_bunk_result, check_no_bunk_datetime,
                nut_tightening_torque_2, nut_tightening_torque_2_result, nut_tightening_torque_2_datetime,
                check_splitpin_and_washer_imagefile, check_splitpin_and_washer_result, check_splitpin_and_washer_datetime,
                check_cap_imagefile, check_cap_result, check_cap_datetime,
                check_bunk_cap_press_imagefile, check_bunk_cap_press_result, check_bunk_cap_press_datetime,
                cap_press_done, cap_press_datetime,
                free_rotation_torque_1, free_rotation_torque_1_result, free_rotation_torque_1_datetime,
                ok_notok_result, username, remarks, created_on
            FROM {schema}.hub_and_disc_assembly_data
            WHERE model_name = %s
              AND created_on::date BETWEEN %s AND %s
            ORDER BY created_on ASC
        """).format(schema=sql.Identifier(schema_name))

        if debug:
            logMessageToConsoleAndFile(None, {"text": f"Executing query for model {modelName} between {start_dt.date()} and {end_dt.date()}"}, logSource, level=LogLevel.DEBUG)

        # Execute with parameterized values
        aCursor.execute(currentQuery, (modelName, start_dt.date(), end_dt.date()))
        records = aCursor.fetchall()

        # Get column names from cursor description
        columns = [desc[0] for desc in aCursor.description]

        # Write header
        writer.writerow(columns)

        # Write records
        for record in records:
            formatted_record = []
            for value in record:
                if value is None:
                    formatted_record.append("")
                elif isinstance(value, datetime):
                    formatted_record.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    formatted_record.append(str(value))
            writer.writerow(formatted_record)

        # Get CSV string
        csv_string = csv_output.getvalue()
        if debug:
            logMessageToConsoleAndFile(None, {"text": csv_string}, logSource, level=LogLevel.DEBUG)
        return csv_string

    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        return csv_string
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Query error: {error}, {type(error)}"}, logSource, level=LogLevel.CRITICAL)
        return csv_string
    finally:
        if aCursor:
            try:
                aCursor.close()
            except:
                pass
        if aConnection:
            try:
                aConnection.close()
            except:
                pass
        csv_output.close()


def getDataOfTodayByModelNumber(modelName: str, db_name: str, debug: bool = False) -> str:
    return getDataByModelNameAndDateLimits(modelName=modelName, startDate=None, endDate=None, db_name=db_name,
                                           debug=debug)


# ************************************ PRODUCTION COUNT QUERIES ****************************************

def getComponentsProducedToday(db_name: str, debug: bool = False) -> int:
    """
    Return the count of components (records) whose created_on date is today.

    Uses a simple DATE cast comparison so the query is index-friendly.

    Args:
        db_name: Database name to query.
        debug:   If True, print the count result.

    Returns:
        int: Number of records created today, or 0 on any error.
    """
    global schema_name
    aConnection = None
    aCursor = None
    count: int = 0
    try:
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        query = sql.SQL(
            "SELECT COUNT(*) FROM {schema}.hub_and_disc_assembly_data "
            "WHERE created_on::date = CURRENT_DATE "
            "AND ok_notok_result = 'OK';"
        ).format(schema=sql.Identifier(schema_name))
        aCursor.execute(query)
        row = aCursor.fetchone()
        count = int(row[0]) if row else 0
        if debug:
            logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedToday() = {count}"}, logSource)
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedToday() error: {error}, {type(error)}"}, logSource)
        count = 0
    finally:
        if aCursor:
            try:
                aCursor.close()
            except Exception:
                pass
        if aConnection:
            try:
                aConnection.close()
            except Exception:
                pass
    return count


def getComponentsProducedThisWeek(db_name: str, debug: bool = False) -> int:
    """
    Return the count of components (records) created during the current ISO calendar week
    (Monday 00:00:00 through the current moment).

    Uses date_trunc('week', CURRENT_DATE) which PostgreSQL aligns to Monday.

    Args:
        db_name: Database name to query.
        debug:   If True, print the count result.

    Returns:
        int: Number of records created this week, or 0 on any error.
    """
    global schema_name
    aConnection = None
    aCursor = None
    count: int = 0
    try:
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        query = sql.SQL(
            "SELECT COUNT(*) FROM {schema}.hub_and_disc_assembly_data "
            "WHERE created_on >= date_trunc('week', CURRENT_DATE) "
            "AND ok_notok_result = 'OK';"
        ).format(schema=sql.Identifier(schema_name))
        aCursor.execute(query)
        row = aCursor.fetchone()
        count = int(row[0]) if row else 0
        if debug:
            logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedThisWeek() = {count}"}, logSource)
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedThisWeek() error: {error}, {type(error)}"}, logSource)
        count = 0
    finally:
        if aCursor:
            try:
                aCursor.close()
            except Exception:
                pass
        if aConnection:
            try:
                aConnection.close()
            except Exception:
                pass
    return count


def getComponentsProducedThisMonth(db_name: str, debug: bool = False) -> int:
    """
    Return the count of components (records) created during the current calendar month
    (first day of month 00:00:00 through the current moment).

    Uses date_trunc('month', CURRENT_DATE) for a clean month boundary.

    Args:
        db_name: Database name to query.
        debug:   If True, print the count result.

    Returns:
        int: Number of records created this month, or 0 on any error.
    """
    global schema_name
    aConnection = None
    aCursor = None
    count: int = 0
    try:
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()
        query = sql.SQL(
            "SELECT COUNT(*) FROM {schema}.hub_and_disc_assembly_data "
            "WHERE created_on >= date_trunc('month', CURRENT_DATE) "
            "AND ok_notok_result = 'OK';"
        ).format(schema=sql.Identifier(schema_name))
        aCursor.execute(query)
        row = aCursor.fetchone()
        count = int(row[0]) if row else 0
        if debug:
            logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedThisMonth() = {count}"}, logSource)
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"getComponentsProducedThisMonth() error: {error}, {type(error)}"}, logSource)
        count = 0
    finally:
        if aCursor:
            try:
                aCursor.close()
            except Exception:
                pass
        if aConnection:
            try:
                aConnection.close()
            except Exception:
                pass
    return count


# ******************************* END PRODUCTION COUNT QUERIES *********************************

select_query_from_start_date_to_end_date = """
SELECT 
    qr_code,
    model_name,
    lhs_rhs,
    model_tonnage,
    component_assembly_start_datetime,
    check_knuckle_imagefile,
    check_knuckle_result,
    check_knuckle_datetime,
    check_hub_and_bottom_bearing_imagefile,
    check_hub_and_bottom_bearing_result,
    check_hub_and_bottom_bearing_datetime,
    check_top_bearing_imagefile,
    check_top_bearing_result,
    check_top_bearing_datetime,
    check_nut_and_platewasher_imagefile,
    check_nut_and_platewasher_result,
    check_nut_and_platewasher_datetime,
    nut_tightening_torque_1,
    nut_tightening_torque_1_result,
    nut_tightening_torque_1_datetime,
    free_rotations_done,
    free_rotations_datetime,
    check_bunk_for_component_press_imagefile,
    check_bunk_for_component_press_result,
    check_bunk_for_component_press_datetime,
    component_press_done,
    component_press_datetime,
    check_no_bunk_imagefile,
    check_no_bunk_result,
    check_no_bunk_datetime,
    nut_tightening_torque_2,
    nut_tightening_torque_2_result,
    nut_tightening_torque_2_datetime,
    check_splitpin_and_washer_imagefile,
    check_splitpin_and_washer_result,
    check_splitpin_and_washer_datetime,
    check_cap_imagefile,
    check_cap_result,
    check_cap_datetime,
    check_bunk_cap_press_imagefile,
    check_bunk_cap_press_result,
    check_bunk_cap_press_datetime,
    cap_press_done,
    cap_press_datetime,
    free_rotation_torque_1,
    free_rotation_torque_1_result,
    free_rotation_torque_1_datetime,
    ok_notok_result,
    username,
    remarks,
    created_on
FROM {}.hub_and_disc_assembly_data
WHERE created_on >= to_timestamp('{} 00:00:00', 'YYYY-MM-DD HH24:MI:SS')
  AND created_on <  to_timestamp('{} 23:59:59.999', 'YYYY-MM-DD HH24:MI:SS')
  -- Alternative (simpler & usually preferred):
  -- AND created_on::date BETWEEN '{}' AND '{}'
ORDER BY model_name ASC, created_on ASC;
"""


def getDataByDateLimits(
        db_name: str,
        startDate: str | None,
        endDate: str | None = None,
        debug: bool = False
) -> str:
    """
    Fetch records from hub_and_disc_assembly_schema.hub_and_disc_assembly_data for a given date range,
    returning them as a CSV string with column names as the header.

    FIXED: Uses parameterized queries and proper date handling to prevent SQL injection and date parsing errors.

    Args:
        db_name: Database name
        startDate: Start date for created_on (format: YYYY-MM-DD), None for today
        endDate: End date for created_on (format: YYYY-MM-DD), None for today

    Returns:
        str: CSV string with column names as header and records as rows, or empty string on error
    """
    global schema_name
    csv_output = StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_MINIMAL)

    # Parse and validate dates
    # FIXED: Proper handling of None dates - use today's date instead of 23:59:59
    try:
        if startDate:
            start_dt = parse(startDate).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to today at 00:00:00
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if endDate:
            end_dt = parse(endDate).replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Default to today at 23:59:59
            end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    except (ValueError, TypeError) as e:
        logMessageToConsoleAndFile(None, {"text": f"Error parsing dates: {e}"}, logSource)
        writer.writerow(all_columns_record_header)
        return csv_output.getvalue()

    # Swap if start_date > end_date
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    aConnection = None
    aCursor = None
    csv_string = ",".join(all_columns_record_header)

    try:
        # Establish database connection
        aConnection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # FIXED: Use parameterized query with proper date handling
        currentQuery = sql.SQL("""
            SELECT 
                qr_code, model_name, lhs_rhs, model_tonnage, component_assembly_start_datetime,
                check_knuckle_imagefile, check_knuckle_result, check_knuckle_datetime,
                check_hub_and_bottom_bearing_imagefile, check_hub_and_bottom_bearing_result, check_hub_and_bottom_bearing_datetime,
                check_top_bearing_imagefile, check_top_bearing_result, check_top_bearing_datetime,
                check_nut_and_platewasher_imagefile, check_nut_and_platewasher_result, check_nut_and_platewasher_datetime,
                nut_tightening_torque_1, nut_tightening_torque_1_result, nut_tightening_torque_1_datetime,
                free_rotations_done, free_rotations_datetime,
                check_bunk_for_component_press_imagefile, check_bunk_for_component_press_result, check_bunk_for_component_press_datetime,
                component_press_done, component_press_datetime,
                check_no_bunk_imagefile, check_no_bunk_result, check_no_bunk_datetime,
                nut_tightening_torque_2, nut_tightening_torque_2_result, nut_tightening_torque_2_datetime,
                check_splitpin_and_washer_imagefile, check_splitpin_and_washer_result, check_splitpin_and_washer_datetime,
                check_cap_imagefile, check_cap_result, check_cap_datetime,
                check_bunk_cap_press_imagefile, check_bunk_cap_press_result, check_bunk_cap_press_datetime,
                cap_press_done, cap_press_datetime,
                free_rotation_torque_1, free_rotation_torque_1_result, free_rotation_torque_1_datetime,
                ok_notok_result, username, remarks, created_on
            FROM {schema}.hub_and_disc_assembly_data
            WHERE created_on::date BETWEEN %s AND %s
            ORDER BY model_name ASC, created_on ASC
        """).format(schema=sql.Identifier(schema_name))

        if debug:
            logMessageToConsoleAndFile(None, {"text": f"Executing query between {start_dt.date()} and {end_dt.date()}"}, logSource)

        # Execute with parameterized values
        aCursor.execute(currentQuery, (start_dt.date(), end_dt.date()))
        records = aCursor.fetchall()

        # Get column names from cursor description
        columns = [desc[0] for desc in aCursor.description]

        # Write header
        writer.writerow(columns)

        # Write records
        for record in records:
            formatted_record = []
            for value in record:
                if value is None:
                    formatted_record.append("")
                elif isinstance(value, datetime):
                    formatted_record.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    formatted_record.append(str(value))
            writer.writerow(formatted_record)

        # Get CSV string
        csv_string = csv_output.getvalue()
        if debug:
            logMessageToConsoleAndFile(None, {"text": csv_string}, logSource)
        return csv_string

    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error: {error}, {type(error)}"}, logSource)
        return csv_string
    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Query error: {error}, {type(error)}"}, logSource)
        return csv_string
    finally:
        if aCursor:
            try:
                aCursor.close()
            except:
                pass
        if aConnection:
            try:
                aConnection.close()
            except:
                pass
        csv_output.close()


def getAllDataOfToday(db_name: str, debug: bool = False) -> str:
    return getDataByDateLimits(startDate=None, endDate=None, db_name=db_name, debug=debug)


# ************************* END - DATA TABLE ******************************************

# *********************************Database Statements******************************

def setReportMajorDatabaseActions(value=False):
    global reportMajorDatabaseActions
    reportMajorDatabaseActions = value


def setReportMinorDatabaseActions(value=False):
    global reportMinorDatabaseActions
    reportMinorDatabaseActions = value


def encodeString(inputString: str):
    input_string_bytes = inputString.encode("utf-8")
    base64_bytes = base64.b64encode(input_string_bytes)
    base64_string = base64_bytes.decode("utf-8")
    return base64_string


def decodeString(inputString: str):
    base64_bytes = inputString.encode("utf-8")
    input_string_bytes = base64.b64decode(base64_bytes)
    requiredString = input_string_bytes.decode("utf-8")
    return requiredString


# =============================================================================
# Index Rebuilding Utilities
# =============================================================================
# Purpose: Rebuild indexes on frequently queried tables after bulk operations
#          (e.g., large data imports) to maintain query performance.
# =============================================================================

def reindexHubAndDiscAssemblyData(db_name: str, verbose: bool = True) -> bool:
    """
    Rebuilds indexes on the hub_and_disc_assembly_data table.

    This should be called after bulk inserts or when performance degrades.

    Args:
        db_name: Name of the database to operate on
        verbose: Whether to print success/failure messages

    Returns:
        bool: True if successful, False otherwise
    """
    connection = None
    cursor = None
    success = False

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()

        schema = getSchemaName()

        # List of indexes to rebuild (add more if you create additional indexes)
        indexes = [
            f"{schema}_hub_and_disc_assembly_data_qr_code_idx",
            f"{schema}_hub_and_disc_assembly_data_model_name_idx",
            f"{schema}_hub_and_disc_assembly_data_created_on_idx",
            # Add any composite indexes if they exist, e.g.:
            # f"{schema}_hub_and_disc_assembly_data_model_created_idx",
        ]

        # Rebuild the table itself (includes all indexes)
        cursor.execute(f"REINDEX TABLE {schema}.hub_and_disc_assembly_data;")

        # Optionally rebuild individual indexes (useful if only some are degraded)
        # for idx_name in indexes:
        #     cursor.execute(f"REINDEX INDEX {idx_name};")

        connection.commit()
        success = True

        if verbose and reportMajorDatabaseActions:
            logMessageToConsoleAndFile(None, {"text": f"Successfully reindexed hub_and_disc_assembly_data in database {db_name}"}, logSource)

    except psycopg2.errors.UndefinedObject as e:
        logMessageToConsoleAndFile(None, {"text": f"Some index does not exist - skipping: {e}"}, logSource)
        success = True  # still consider operation successful if table was reindexed
    except psycopg2.OperationalError as e:
        logMessageToConsoleAndFile(None, {"text": f"Connection error during reindex: {e}"}, logSource)
    except Exception as e:
        logMessageToConsoleAndFile(None, {"text": f"Error during reindex of hub_and_disc_assembly_data: {e}"}, logSource)
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

    return success


def ensureIndexesExist(db_name: str, verbose: bool = True) -> bool:
    """
    Creates commonly used indexes if they do not already exist.
    Call this once during database initialization (e.g. in createAllTables or setDatabaseName).
    """
    connection = None
    cursor = None
    success = False

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()

        schema = getSchemaName()
        table = f"{schema}.hub_and_disc_assembly_data"

        index_definitions = [
            # Fast lookups by QR code (should be unique or near-unique)
            (f"{schema}_hub_and_disc_assembly_data_qr_code_idx",
             f"CREATE INDEX IF NOT EXISTS {schema}_hub_and_disc_assembly_data_qr_code_idx "
             f"ON {table} (qr_code);"),

            # Filter by model (very common in reports)
            (f"{schema}_hub_and_disc_assembly_data_model_name_idx",
             f"CREATE INDEX IF NOT EXISTS {schema}_hub_and_disc_assembly_data_model_name_idx "
             f"ON {table} (model_name);"),

            # Time-based queries & sorting
            (f"{schema}_hub_and_disc_assembly_data_created_on_idx",
             f"CREATE INDEX IF NOT EXISTS {schema}_hub_and_disc_assembly_data_created_on_idx "
             f"ON {table} (created_on);"),

            # Optional composite index for frequent model + date queries
            # (f"{schema}_hub_and_disc_assembly_data_model_created_idx",
            #  f"CREATE INDEX IF NOT EXISTS {schema}_hub_and_disc_assembly_data_model_created_idx "
            #  f"ON {table} (model_name, created_on);"),
        ]

        for idx_name, create_stmt in index_definitions:
            cursor.execute(create_stmt)

        connection.commit()
        success = True

        if verbose and reportMajorDatabaseActions:
            logMessageToConsoleAndFile(None, {"text": f"Ensured existence of performance indexes on {table}"}, logSource)

    except Exception as e:
        logMessageToConsoleAndFile(None, {"text": f"Error creating/ensuring indexes: {e}"}, logSource)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return success


# ************************* BEGIN - MACHINE_SETTINGS TABLE ******************************************


def insertDefaultMachineSettings(db_name: str) -> bool:
    """
    Insert default machine settings if table is empty.
    Should be called during initial setup in setDatabaseName().

    Args:
        db_name (str): Database name

    Returns:
        bool: True if successful, False otherwise
    """
    global schema_name
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Check if settings exist
        check_query = f"SELECT COUNT(*) FROM {schema_name}.machine_settings;"
        aCursor.execute(check_query)
        count = aCursor.fetchone()[0]

        if count == 0:
            # Use parameterized query with ON CONFLICT for idempotency
            insert_query = f"""
                INSERT INTO {schema_name}.machine_settings 
                    (NoOfRotation1CCW, NoOfRotation1CW, NoOfRotation2CCW, NoOfRotation2CW,
                     RotationUnitRPM, updated_on_date)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING;
            """
            aCursor.execute(insert_query, (5, 5, 5, 5, 60))
            aConnection.commit()
            if reportMajorDatabaseActions:
                logMessageToConsoleAndFile(None, {"text": f"Inserted default machine settings in {schema_name}"}, logSource)

        aCursor.close()
        aConnection.close()
        return True

    except psycopg2.OperationalError as error:
        logMessageToConsoleAndFile(None, {"text": f"Connection error while inserting default machine settings: {error}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False
    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Error inserting default machine settings: {error}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False


def getMachineSettings(db_name: str) -> dict:
    """
    Fetch the latest machine settings as a dictionary.
    Returns the most recent record based on updated_on_date (audit trail support).

    Args:
        db_name (str): Database name

    Returns:
        dict: Dictionary containing all machine settings, or empty dict on error
    """
    global schema_name
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Get the latest record by updated_on_date descending (for audit trail support)
        query = f"""SELECT noofrotation1ccw, noofrotation1cw, noofrotation2ccw, noofrotation2cw,
                           rotationunitrpm, updated_on_date
                    FROM {schema_name}.machine_settings 
                    ORDER BY updated_on_date DESC
                    LIMIT 1;"""
        aCursor.execute(query)
        result = aCursor.fetchone()

        aCursor.close()
        aConnection.close()

        if result:
            return {
                "NoOfRotation1CCW": result[0],
                "NoOfRotation1CW": result[1],
                "NoOfRotation2CCW": result[2],
                "NoOfRotation2CW": result[3],
                "RotationUnitRPM": result[4],
                "updated_on_date": result[5]
            }
        return {}

    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Error fetching machine settings: {error}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return {}


def updateNoOfRotation1CCW(db_name: str, value: int) -> bool:
    """Update NoOfRotation1CCW setting (0-10)"""
    if not isinstance(value, int) or value < 0 or value > 10:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for NoOfRotation1CCW: {value} (must be 0-10)"}, logSource)
        return False
    return updateMachineSetting(db_name, 'noofrotation1ccw', value)


def updateNoOfRotation1CW(db_name: str, value: int) -> bool:
    """Update NoOfRotation1CW setting (0-10)"""
    if not isinstance(value, int) or value < 0 or value > 10:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for NoOfRotation1CW: {value} (must be 0-10)"}, logSource)
        return False
    return updateMachineSetting(db_name, 'noofrotation1cw', value)


def updateNoOfRotation2CCW(db_name: str, value: int) -> bool:
    """Update NoOfRotation2CCW setting (0-10)"""
    if not isinstance(value, int) or value < 0 or value > 10:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for NoOfRotation2CCW: {value} (must be 0-10)"}, logSource)
        return False
    return updateMachineSetting(db_name, 'noofrotation2ccw', value)


def updateNoOfRotation2CW(db_name: str, value: int) -> bool:
    """Update NoOfRotation2CW setting (0-10)"""
    if not isinstance(value, int) or value < 0 or value > 10:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for NoOfRotation2CW: {value} (must be 0-10)"}, logSource)
        return False
    return updateMachineSetting(db_name, 'noofrotation2cw', value)


def updateRotationUnitRPM(db_name: str, value: int) -> bool:
    """Update RotationUnitRPM setting (1-120)"""
    if not isinstance(value, int) or value < 1 or value > 120:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for RotationUnitRPM: {value} (must be 1-120)"}, logSource)
        return False
    return updateMachineSetting(db_name, 'rotationunitrpm', value)


def updateMachineSetting(db_name: str, setting_name: str, value) -> bool:
    """
    Update a specific machine setting.

    Args:
        db_name (str): Database name
        setting_name (str): Name of the setting column (lowercase)
        value: New value (int)

    Returns:
        bool: True if successful, False otherwise
    """
    global schema_name

    # PostgreSQL stores unquoted column names as lowercase
    valid_settings = {
        'noofrotation1ccw', 'noofrotation1cw', 'noofrotation2ccw', 'noofrotation2cw',
        'rotationunitrpm'
    }

    setting_name_lower = setting_name.lower()
    if setting_name_lower not in valid_settings:
        logMessageToConsoleAndFile(None, {"text": f"Invalid setting name: {setting_name}"}, logSource)
        return False

    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Use SQL string directly (not Identifier) since PostgreSQL stores columns as lowercase
        updateStatement = sql.SQL(
            "UPDATE {schema}.machine_settings SET {field} = %s, updated_on_date = CURRENT_TIMESTAMP").format(
            schema=sql.Identifier(schema_name),
            field=sql.SQL(setting_name_lower)
        )
        aCursor.execute(updateStatement, (value,))
        aConnection.commit()
        aCursor.close()
        aConnection.close()

        if reportMinorDatabaseActions:
            logMessageToConsoleAndFile(None, {"text": f"Updated {setting_name} to {value}"}, logSource)
        return True

    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False


def updateAllMachineSettings(db_name: str, no_of_rotation1_ccw: int, no_of_rotation1_cw: int,
                             no_of_rotation2_ccw: int, no_of_rotation2_cw: int,
                             rotation_unit_rpm: int) -> bool:
    """
    Update all machine settings at once (updates existing record).

    Args:
        db_name (str): Database name
        no_of_rotation1_ccw (int): Number of rotations 1 CCW (0-10)
        no_of_rotation1_cw (int): Number of rotations 1 CW (0-10)
        no_of_rotation2_ccw (int): Number of rotations 2 CCW (0-10)
        no_of_rotation2_cw (int): Number of rotations 2 CW (0-10)
        rotation_unit_rpm (int): Rotation speed in RPM (1-120)

    Returns:
        bool: True if successful, False otherwise
    """
    global schema_name

    # Validate rotation counts (0-10)
    rotation_params = [
        ('no_of_rotation1_ccw', no_of_rotation1_ccw),
        ('no_of_rotation1_cw', no_of_rotation1_cw),
        ('no_of_rotation2_ccw', no_of_rotation2_ccw),
        ('no_of_rotation2_cw', no_of_rotation2_cw),
    ]
    for param_name, param_value in rotation_params:
        if not isinstance(param_value, int) or param_value < 0 or param_value > 10:
            logMessageToConsoleAndFile(None, {"text": f"Invalid value for {param_name}: {param_value} (must be 0-10)"}, logSource)
            return False

    # Validate RPM (1-120)
    if not isinstance(rotation_unit_rpm, int) or rotation_unit_rpm < 1 or rotation_unit_rpm > 120:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for rotation_unit_rpm: {rotation_unit_rpm} (must be 1-120)"}, logSource)
        return False

    aConnection = None
    updateStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Use parameterized query to prevent SQL injection
        updateStatement = sql.SQL("""
            UPDATE {schema}.machine_settings 
            SET noofrotation1ccw = %s, 
                noofrotation1cw = %s, 
                noofrotation2ccw = %s, 
                noofrotation2cw = %s, 
                rotationunitrpm = %s,
                updated_on_date = CURRENT_TIMESTAMP
        """).format(schema=sql.Identifier(schema_name))

        aCursor.execute(updateStatement, (no_of_rotation1_ccw, no_of_rotation1_cw,
                                          no_of_rotation2_ccw, no_of_rotation2_cw,
                                          rotation_unit_rpm))
        aConnection.commit()
        aCursor.close()
        aConnection.close()

        if reportMinorDatabaseActions:
            logMessageToConsoleAndFile(None, {"text": "Updated all machine settings"}, logSource)
        return True

    except Exception as error:
        if not isinstance(error, psycopg2.errors.UniqueViolation):
            logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {updateStatement}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False


def insertNewMachineSettings(db_name: str, no_of_rotation1_ccw: int, no_of_rotation1_cw: int,
                             no_of_rotation2_ccw: int, no_of_rotation2_cw: int,
                             rotation_unit_rpm: int) -> bool:
    """
    Insert a new machine settings record (for audit trail).
    Each update creates a new record, preserving history.

    Args:
        db_name (str): Database name
        no_of_rotation1_ccw (int): Number of rotations 1 CCW (0-10)
        no_of_rotation1_cw (int): Number of rotations 1 CW (0-10)
        no_of_rotation2_ccw (int): Number of rotations 2 CCW (0-10)
        no_of_rotation2_cw (int): Number of rotations 2 CW (0-10)
        rotation_unit_rpm (int): Rotation speed in RPM (1-120)

    Returns:
        bool: True if successful, False otherwise
    """
    global schema_name

    # Validate rotation counts (0-10)
    rotation_params = [
        ('no_of_rotation1_ccw', no_of_rotation1_ccw),
        ('no_of_rotation1_cw', no_of_rotation1_cw),
        ('no_of_rotation2_ccw', no_of_rotation2_ccw),
        ('no_of_rotation2_cw', no_of_rotation2_cw),
    ]
    for param_name, param_value in rotation_params:
        if not isinstance(param_value, int) or param_value < 0 or param_value > 10:
            logMessageToConsoleAndFile(None, {"text": f"Invalid value for {param_name}: {param_value} (must be 0-10)"}, logSource)
            return False

    # Validate RPM (1-120)
    if not isinstance(rotation_unit_rpm, int) or rotation_unit_rpm < 1 or rotation_unit_rpm > 120:
        logMessageToConsoleAndFile(None, {"text": f"Invalid value for rotation_unit_rpm: {rotation_unit_rpm} (must be 1-120)"}, logSource)
        return False

    aConnection = None
    insertStatement = ''
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Insert a new record (for audit trail)
        insertStatement = sql.SQL("""
            INSERT INTO {schema}.machine_settings 
                (noofrotation1ccw, noofrotation1cw, noofrotation2ccw, noofrotation2cw,
                 rotationunitrpm, updated_on_date)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """).format(schema=sql.Identifier(schema_name))

        aCursor.execute(insertStatement, (no_of_rotation1_ccw, no_of_rotation1_cw,
                                          no_of_rotation2_ccw, no_of_rotation2_cw,
                                          rotation_unit_rpm))
        aConnection.commit()
        aCursor.close()
        aConnection.close()

        if reportMajorDatabaseActions:
            logMessageToConsoleAndFile(None, {"text": "Inserted new machine settings record"}, logSource)
        return True

    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Encountered {error}, {type(error)} for statement {insertStatement}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return False


def getMachineSettingsHistory(db_name: str, limit: int = 10) -> list:
    """
    Fetch machine settings history (multiple records for audit trail).

    Args:
        db_name (str): Database name
        limit (int): Maximum number of records to return (default 10)

    Returns:
        list: List of dictionaries containing machine settings history, or empty list on error
    """
    global schema_name
    aConnection = None
    try:
        aConnection = psycopg2.connect(user="postgres", password="postgres", host="127.0.0.1",
                                       port="5432", database=db_name)
        aConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        aCursor = aConnection.cursor()

        # Get records ordered by updated_on_date descending
        query = f"""SELECT setting_id, noofrotation1ccw, noofrotation1cw, noofrotation2ccw, noofrotation2cw,
                           rotationunitrpm, updated_on_date
                    FROM {schema_name}.machine_settings 
                    ORDER BY updated_on_date DESC
                    LIMIT %s;"""
        aCursor.execute(query, (limit,))
        results = aCursor.fetchall()

        aCursor.close()
        aConnection.close()

        history = []
        for result in results:
            history.append({
                "setting_id": result[0],
                "NoOfRotation1CCW": result[1],
                "NoOfRotation1CW": result[2],
                "NoOfRotation2CCW": result[3],
                "NoOfRotation2CW": result[4],
                "RotationUnitRPM": result[5],
                "updated_on_date": result[6]
            })
        return history

    except Exception as error:
        logMessageToConsoleAndFile(None, {"text": f"Error fetching machine settings history: {error}"}, logSource)
        if aConnection is not None:
            try:
                aConnection.close()
            except:
                pass
        return []


# ************************* END - MACHINE_SETTINGS TABLE ******************************************


# ************************* TEST ROUTINE FOR MACHINE_SETTINGS ******************************************

def testMachineSettings(db_name: str = None, verbose: bool = True) -> bool:
    """
    Test routine for machine_settings table operations.
    Tests all CRUD operations for machine_settings.

    Args:
        db_name (str): Database name. If None, uses current database from getDatabaseName()
        verbose (bool): If True, prints detailed test results

    Returns:
        bool: True if all tests pass, False otherwise
    """
    if db_name is None:
        db_name = getDatabaseName()

    all_passed = True
    test_results = []

    def log(message: str, success: bool = True):
        nonlocal all_passed
        status = "✓ PASS" if success else "✗ FAIL"
        if not success:
            all_passed = False
        test_results.append(f"{status}: {message}")
        if verbose:
            if success:
                printBoldGreen(f"{status}: {message}")
            else:
                printBoldRed(f"{status}: {message}")

    if verbose:
        printBoldBlue("=" * 60)
        printBoldBlue("MACHINE SETTINGS TEST ROUTINE")
        printBoldBlue(f"Database: {db_name}")
        printBoldBlue("=" * 60)

    # Test 1: Insert default machine settings
    if verbose:
        printBoldYellow("\n[Test 1] Insert Default Machine Settings")
    try:
        result = insertDefaultMachineSettings(db_name)
        log("insertDefaultMachineSettings() executed", result)
    except Exception as e:
        log(f"insertDefaultMachineSettings() raised exception: {e}", False)

    # Test 2: Get machine settings
    if verbose:
        printBoldYellow("\n[Test 2] Get Machine Settings")
    try:
        settings = getMachineSettings(db_name)
        if settings:
            log(f"getMachineSettings() returned: {settings}", True)
            # Verify all expected keys exist
            expected_keys = ['NoOfRotation1CCW', 'NoOfRotation1CW', 'NoOfRotation2CCW',
                             'NoOfRotation2CW', 'RotationUnitRPM', 'updated_on_date']
            missing_keys = [k for k in expected_keys if k not in settings]
            if missing_keys:
                log(f"Missing keys in settings: {missing_keys}", False)
            else:
                log("All expected keys present in settings", True)
        else:
            log("getMachineSettings() returned empty dict", False)
    except Exception as e:
        log(f"getMachineSettings() raised exception: {e}", False)

    # Test 3: Update individual settings
    if verbose:
        printBoldYellow("\n[Test 3] Update Individual Settings")

    # Test updateNoOfRotation1CCW
    try:
        result = updateNoOfRotation1CCW(db_name, 5)
        log(f"updateNoOfRotation1CCW(5) = {result}", result)
    except Exception as e:
        log(f"updateNoOfRotation1CCW() raised exception: {e}", False)

    # Test updateNoOfRotation1CW
    try:
        result = updateNoOfRotation1CW(db_name, 7)
        log(f"updateNoOfRotation1CW(7) = {result}", result)
    except Exception as e:
        log(f"updateNoOfRotation1CW() raised exception: {e}", False)

    # Test updateNoOfRotation2CCW
    try:
        result = updateNoOfRotation2CCW(db_name, 3)
        log(f"updateNoOfRotation2CCW(3) = {result}", result)
    except Exception as e:
        log(f"updateNoOfRotation2CCW() raised exception: {e}", False)

    # Test updateNoOfRotation2CW
    try:
        result = updateNoOfRotation2CW(db_name, 9)
        log(f"updateNoOfRotation2CW(9) = {result}", result)
    except Exception as e:
        log(f"updateNoOfRotation2CW() raised exception: {e}", False)

    # Test updateRotationUnitRPM
    try:
        result = updateRotationUnitRPM(db_name, 100)
        log(f"updateRotationUnitRPM(100) = {result}", result)
    except Exception as e:
        log(f"updateRotationUnitRPM() raised exception: {e}", False)

    # Test 4: Verify updates were applied
    if verbose:
        printBoldYellow("\n[Test 4] Verify Individual Updates")
    try:
        settings = getMachineSettings(db_name)
        if settings:
            checks = [
                (settings.get('NoOfRotation1CCW') == 5,
                 f"NoOfRotation1CCW = {settings.get('NoOfRotation1CCW')} (expected 5)"),
                (settings.get('NoOfRotation1CW') == 7,
                 f"NoOfRotation1CW = {settings.get('NoOfRotation1CW')} (expected 7)"),
                (settings.get('NoOfRotation2CCW') == 3,
                 f"NoOfRotation2CCW = {settings.get('NoOfRotation2CCW')} (expected 3)"),
                (settings.get('NoOfRotation2CW') == 9,
                 f"NoOfRotation2CW = {settings.get('NoOfRotation2CW')} (expected 9)"),
                (settings.get('RotationUnitRPM') == 100,
                 f"RotationUnitRPM = {settings.get('RotationUnitRPM')} (expected 100)"),
            ]
            for passed, msg in checks:
                log(msg, passed)
        else:
            log("Could not verify updates - getMachineSettings returned empty", False)
    except Exception as e:
        log(f"Verification raised exception: {e}", False)

    # Test 5: Update all settings at once
    if verbose:
        printBoldYellow("\n[Test 5] Update All Settings At Once")
    try:
        result = updateAllMachineSettings(db_name,
                                          no_of_rotation1_ccw=2,
                                          no_of_rotation1_cw=4,
                                          no_of_rotation2_ccw=6,
                                          no_of_rotation2_cw=8,
                                          rotation_unit_rpm=80)
        log(f"updateAllMachineSettings(2, 4, 6, 8, 80) = {result}", result)
    except Exception as e:
        log(f"updateAllMachineSettings() raised exception: {e}", False)

    # Test 6: Verify bulk update
    if verbose:
        printBoldYellow("\n[Test 6] Verify Bulk Update")
    try:
        settings = getMachineSettings(db_name)
        if settings:
            checks = [
                (settings.get('NoOfRotation1CCW') == 2,
                 f"NoOfRotation1CCW = {settings.get('NoOfRotation1CCW')} (expected 2)"),
                (settings.get('NoOfRotation1CW') == 4,
                 f"NoOfRotation1CW = {settings.get('NoOfRotation1CW')} (expected 4)"),
                (settings.get('NoOfRotation2CCW') == 6,
                 f"NoOfRotation2CCW = {settings.get('NoOfRotation2CCW')} (expected 6)"),
                (settings.get('NoOfRotation2CW') == 8,
                 f"NoOfRotation2CW = {settings.get('NoOfRotation2CW')} (expected 8)"),
                (settings.get('RotationUnitRPM') == 80,
                 f"RotationUnitRPM = {settings.get('RotationUnitRPM')} (expected 80)"),
            ]
            for passed, msg in checks:
                log(msg, passed)

            # Verify updated_on_date is recent
            if settings.get('updated_on_date'):
                log(f"updated_on_date = {settings.get('updated_on_date')}", True)
            else:
                log("updated_on_date is None", False)
        else:
            log("Could not verify bulk update - getMachineSettings returned empty", False)
    except Exception as e:
        log(f"Verification raised exception: {e}", False)

    # Test 7: Test Invalid Setting Name (should fail gracefully)
    if verbose:
        printBoldYellow("\n[Test 7] Test Invalid Setting Name (should fail gracefully)")
    try:
        result = updateMachineSetting(db_name, 'InvalidSettingName', 999)
        log(f"updateMachineSetting('InvalidSettingName', 999) correctly returned False", not result)
    except Exception as e:
        log(f"updateMachineSetting() raised exception for invalid name: {e}", False)

    # Test 7a: Test Boundary Validation (values outside valid range should fail)
    if verbose:
        printBoldYellow("\n[Test 7a] Test Boundary Validation")

    # Test rotation > 10 should fail
    try:
        result = updateNoOfRotation1CCW(db_name, 15)
        log(f"updateNoOfRotation1CCW(15) correctly returned False (>10)", not result)
    except Exception as e:
        log(f"updateNoOfRotation1CCW(15) raised exception: {e}", False)

    # Test rotation < 0 should fail
    try:
        result = updateNoOfRotation1CW(db_name, -1)
        log(f"updateNoOfRotation1CW(-1) correctly returned False (<0)", not result)
    except Exception as e:
        log(f"updateNoOfRotation1CW(-1) raised exception: {e}", False)

    # Test RPM > 120 should fail
    try:
        result = updateRotationUnitRPM(db_name, 150)
        log(f"updateRotationUnitRPM(150) correctly returned False (>120)", not result)
    except Exception as e:
        log(f"updateRotationUnitRPM(150) raised exception: {e}", False)

    # Test RPM < 1 should fail
    try:
        result = updateRotationUnitRPM(db_name, 0)
        log(f"updateRotationUnitRPM(0) correctly returned False (<1)", not result)
    except Exception as e:
        log(f"updateRotationUnitRPM(0) raised exception: {e}", False)

    # Test bulk update with invalid values should fail
    try:
        result = updateAllMachineSettings(db_name,
                                          no_of_rotation1_ccw=20,  # Invalid: > 10
                                          no_of_rotation1_cw=1,
                                          no_of_rotation2_ccw=1,
                                          no_of_rotation2_cw=1,
                                          rotation_unit_rpm=60)
        log(f"updateAllMachineSettings with rotation=20 correctly returned False", not result)
    except Exception as e:
        log(f"updateAllMachineSettings() raised exception: {e}", False)

    # Test 8: Reset to defaults
    if verbose:
        printBoldYellow("\n[Test 8] Reset to Default Values")
    try:
        result = updateAllMachineSettings(db_name,
                                          no_of_rotation1_ccw=1,
                                          no_of_rotation1_cw=1,
                                          no_of_rotation2_ccw=1,
                                          no_of_rotation2_cw=1,
                                          rotation_unit_rpm=60)
        log(f"Reset to defaults (1, 1, 1, 1, 60) = {result}", result)
    except Exception as e:
        log(f"Reset raised exception: {e}", False)

    # Summary
    if verbose:
        printBoldBlue("\n" + "=" * 60)
        printBoldBlue("TEST SUMMARY")
        printBoldBlue("=" * 60)
        passed_count = sum(1 for r in test_results if r.startswith("✓"))
        failed_count = sum(1 for r in test_results if r.startswith("✗"))
        printBoldYellow(f"Total Tests: {len(test_results)}")
        printBoldGreen(f"Passed: {passed_count}")
        if failed_count > 0:
            printBoldRed(f"Failed: {failed_count}")
        else:
            printLight(f"Failed: {failed_count}")

        if all_passed:
            printBoldGreen("\n*** ALL TESTS PASSED ***")
        else:
            printBoldRed("\n*** SOME TESTS FAILED ***")

    return all_passed

# To run the test, uncomment the following lines:
# if __name__ == "__main__":
#     setDatabaseName(mode="Test", createDB=True)
#     testMachineSettings(verbose=True)

# ************************* END - TEST ROUTINE ******************************************