# from datetime import datetime
# import subprocess
# import os
# import tempfile
# from tempfile import mkstemp
#
# import gzip
# import boto3
# import psycopg2
# from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
#
# from Configuration import CosThetaConfigurator
# from utils.CosThetaPrintUtils import *
# from utils.CosThetaFileUtils import *
#
# # Amazon S3 settings.
# # AWS_ACCESS_KEY_ID  in ~/.aws/credentials
# # AWS_SECRET_ACCESS_KEY in ~/.aws/credentials
#
#
# def upload_to_s3(file_full_path, dest_file, manager_config):
#     """
#     Upload a file to an AWS S3 bucket.
#     """
#     s3_client = boto3.client('s3')
#     try:
#         s3_client.upload_file(file_full_path,
#                               manager_config.get('AWS_BUCKET_NAME'),
#                               manager_config.get('AWS_BUCKET_PATH') + dest_file)
#         os.remove(file_full_path)
#     except Exception as exc:
#         print(exc)
#         # exit(1)
#
#
# def download_from_s3(backup_s3_key, dest_file, manager_config):
#     """
#     Upload a file to an AWS S3 bucket.
#     """
#     s3_client = boto3.resource('s3')
#     try:
#         s3_client.meta.clientForReads.download_file(manager_config.get('AWS_BUCKET_NAME'), backup_s3_key, dest_file)
#     except Exception as e:
#         print(e)
#         # exit(1)
#
#
# def list_available_backups(storage_engine, manager_config):
#     key_list = []
#     backup_folder = ''
#     backup_list = []
#     if storage_engine == 'LOCAL':
#         try:
#             backup_folder = manager_config.get('LOCAL_BACKUP_PATH')
#             backup_list = os.listdir(backup_folder)
#         except FileNotFoundError:
#             print(f'Could not find {backup_folder} when searching for backups.'
#                   f'Check your .config file settings')
#             # exit(1)
#     elif storage_engine == 'S3':
#         # logger.info('Listing S3 bucket s3://{}/{} content :'.format(aws_bucket_name, aws_bucket_path))
#         s3_client = boto3.client('s3')
#         s3_objects = s3_client.list_objects_v2(Bucket=manager_config.get('AWS_BUCKET_NAME'),
#                                                Prefix=manager_config.get('AWS_BUCKET_PATH'))
#         backup_list = [s3_content['Key'] for s3_content in s3_objects['Contents']]
#
#     for bckp in backup_list:
#         key_list.append(bckp)
#     return key_list
#
#
# def list_postgres_databases(host, database_name, port, user, password):
#     try:
#         process = subprocess.Popen(
#             ['psql',
#              '--dbname=postgresql://{}:{}@{}:{}/{}'.format(user, password, host, port, database_name),
#              '--list'],
#             stdout=subprocess.PIPE
#         )
#         output = process.communicate()[0]
#         if int(process.returncode) != 0:
#             print('Command failed. Return code : {}'.format(process.returncode))
#             # exit(1)
#         return output
#     except Exception as e:
#         print(e)
#         # exit(1)
#
#
# def backup_postgres_db(host, database_name, port, user, password, dest_file, verbose : bool = False):
#     """
#     Backup postgres db to a file.
#     """
#     if verbose:
#         try:
#             # process = subprocess.Popen(
#             #     ['pg_dump',
#             #      '--dbname=postgresql://{}:{}@{}:{}/{}'.format(user, password, host, port, database_name),
#             #      '-Fc',
#             #      '-f', dest_file,
#             #      '-v'],
#             #     stdout=subprocess.PIPE
#             # )
#             process = subprocess.Popen(
#                 ['pg_dump.exe',
#                  f'--file={dest_file}',
#                  f'--dbname=postgresql://{user}:{password}@{host}:{port}/{database_name}',
#                  '--role=postgres',
#                  '--format=t',
#                  '--blobs',
#                  '--verbose',
#                  '--create'],
#                 stdout=subprocess.PIPE
#             )
#             # print("the commandline is {}".format(process.args))
#             output = process.communicate()[0]
#             if int(process.returncode) != 0:
#                 print('Command failed. Return code : {}'.format(process.returncode))
#                 # exit(1)
#             return output
#         except Exception as e:
#             print(e)
#             # exit(1)
#     else:
#
#         try:
#             # process = subprocess.Popen(
#             #     ['pg_dump',
#             #      '--dbname=postgresql://{}:{}@{}:{}/{}'.format(user, password, host, port, database_name),
#             #      '-f', dest_file],
#             #     stdout=subprocess.PIPE
#             # )
#             process = subprocess.Popen(
#                 ['pg_dump.exe',
#                  f'--file={dest_file}',
#                  f'--dbname=postgresql://{user}:{password}@{host}:{port}/{database_name}',
#                  '--role=postgres',
#                  '--format=t',
#                  '--blobs',
#                  '--create'],
#                 stdout=subprocess.PIPE
#             )
#             # print("the commandline is {}".format(process.args))
#             output = process.communicate()[0]
#             if process.returncode != 0:
#                 print('Command failed. Return code : {}'.format(process.returncode))
#                 # exit(1)
#             return output
#         except Exception as e:
#             print(e)
#             # exit(1)
#
#
# def compress_file(src_file):
#     compressed_file = "{}.gz".format(str(src_file))
#     with open(src_file, 'rb') as f_in:
#         with gzip.open(compressed_file, 'wb') as f_out:
#             for line in f_in:
#                 f_out.write(line)
#     return compressed_file
#
#
# def extract_file(src_file):
#     extracted_file, extension = os.path.splitext(src_file)
#
#     with gzip.open(src_file, 'rb') as f_in:
#         with open(extracted_file, 'wb') as f_out:
#             for line in f_in:
#                 f_out.write(line)
#     return extracted_file
#
#
# def remove_faulty_statement_from_dump(src_file):
#     temp_file, _ = tempfile.mkstemp()
#
#     try:
#         with open(temp_file, 'w+'):
#             process = subprocess.Popen(
#                 ['pg_restore',
#                  '-l'
#                  '-v',
#                  src_file],
#                 stdout=subprocess.PIPE
#             )
#             output = subprocess.check_output(('grep', '-v', '"EXTENSION - plpgsql"'), stdin=process.stdout)
#             process.wait()
#             if int(process.returncode) != 0:
#                 print('Command failed. Return code : {}'.format(process.returncode))
#                 # exit(1)
#
#             os.remove(src_file)
#             with open(src_file, 'w+') as cleaned_dump:
#                 subprocess.call(
#                     ['pg_restore',
#                      '-L'],
#                     stdin=output,
#                     stdout=cleaned_dump
#                 )
#
#     except Exception as e:
#         print("Issue when modifying dump : {}".format(e))
#
#
# def change_user_from_dump(source_dump_path, old_user, new_user):
#     fh, abs_path = mkstemp()
#     with os.fdopen(fh, 'w') as new_file:
#         with open(source_dump_path) as old_file:
#             for line in old_file:
#                 new_file.write(line.replace(old_user, new_user))
#     # Remove original file
#     os.remove(source_dump_path)
#     # Move newwidgets file
#     shutil.move(abs_path, source_dump_path)
#
#
# def restore_postgres_db(db_host, db, port, user, password, backup_file, verbose):
#     """Restore postgres db from a file."""
#     try:
#         subprocess_params = [
#             'pg_restore',
#             '--no-owner',
#             '--dbname=postgresql://{}:{}@{}:{}/{}'.format(user,
#                                                           password,
#                                                           db_host,
#                                                           port,
#                                                           db)
#         ]
#
#         if verbose:
#             subprocess_params.append('-v')
#
#         subprocess_params.append(backup_file)
#         process = subprocess.Popen(subprocess_params, stdout=subprocess.PIPE)
#         output = process.communicate()[0]
#
#         if int(process.returncode) != 0:
#             print('Command failed. Return code : {}'.format(process.returncode))
#
#         return output
#     except Exception as e:
#         print("Issue with the db restore : {}".format(e))
#
#
# def create_db(db_host, database, db_port, user_name, user_password):
#     try:
#         con = psycopg2.connect(dbname='postgres', port=db_port,
#                                user=user_name, host=db_host,
#                                password=user_password)
#
#     except Exception as e:
#         print(e)
#         # exit(1)
#
#     con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
#     cur = con.cursor()
#     try:
#         cur.execute("SELECT pg_terminate_backend( pid ) "
#                     "FROM pg_stat_activity "
#                     "WHERE pid <> pg_backend_pid( ) "
#                     "AND datname = '{}'".format(database))
#         cur.execute("DROP DATABASE IF EXISTS {} ;".format(database))
#     except Exception as e:
#         print(e)
#         # exit(1)
#     cur.execute("CREATE DATABASE {} ;".format(database))
#     cur.execute("GRANT ALL PRIVILEGES ON DATABASE {} TO {} ;".format(database, user_name))
#     return database
#
#
# def swap_after_restore(db_host, restore_database, new_active_database, db_port, user_name, user_password):
#     try:
#         con = psycopg2.connect(dbname='postgres', port=db_port,
#                                user=user_name, host=db_host,
#                                password=user_password)
#         con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
#         cur = con.cursor()
#         cur.execute("SELECT pg_terminate_backend( pid ) "
#                     "FROM pg_stat_activity "
#                     "WHERE pid <> pg_backend_pid( ) "
#                     "AND datname = '{}'".format(new_active_database))
#         cur.execute("DROP DATABASE IF EXISTS {}".format(new_active_database))
#         cur.execute('ALTER DATABASE "{}" RENAME TO "{}";'.format(restore_database, new_active_database))
#     except Exception as e:
#         print(e)
#         # exit(1)
#
#
# def move_to_local_storage(comp_file, filename_compressed, manager_config):
#     """ Move compressed backup into {LOCAL_BACKUP_PATH}. """
#     backup_folder = manager_config.get('LOCAL_BACKUP_PATH')
#     try:
#         check_folder = os.listdir(backup_folder)
#     except FileNotFoundError:
#         os.mkdir(backup_folder)
#     shutil.move(comp_file, '{}{}'.format(manager_config.get('LOCAL_BACKUP_PATH'), filename_compressed))
#
#
#
# # def main():
# #     logger = logging.getLogger(__name__)
# #     logger.setLevel(logging.INFO)
# #     handler = logging.StreamHandler()
# #     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# #     handler.setFormatter(formatter)
# #     logger.addHandler(handler)
# #     args_parser = argparse.ArgumentParser(description='Postgres database management')
# #     args_parser.add_argument("--action",
# #                              metavar="action",
# #                              choices=['list', 'list_dbs', 'restore', 'backup'],
# #                              required=True)
# #     args_parser.add_argument("--date",
# #                              metavar="YYYY-MM-dd",
# #                              help="Date to use for restore (show with --action list)")
# #     args_parser.add_argument("--dest-db",
# #                              metavar="dest_db",
# #                              default=None,
# #                              help="Name of the new restored database")
# #     args_parser.add_argument("--verbose",
# #                              default=False,
# #                              help="Verbose output")
# #     args_parser.add_argument("--configfile",
# #                              required=True,
# #                              help="Database configuration file")
# #     args = args_parser.parse_args()
# #
# #     config = configparser.ConfigParser()
# #     config.read(args.configfile)
# #
# #     postgres_host = config.get('postgresql', 'host')
# #     postgres_port = config.get('postgresql', 'port')
# #     postgres_db = config.get('postgresql', 'db')
# #     postgres_restore = "{}_restore".format(postgres_db)
# #     postgres_user = config.get('postgresql', 'user')
# #     postgres_password = config.get('postgresql', 'password')
# #     aws_bucket_name = config.get('S3', 'bucket_name')
# #     aws_bucket_path = config.get('S3', 'bucket_backup_path')
# #     storage_engine = config.get('setup', 'storage_engine')
# #     timestr = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
# #     filename = 'backup-{}-{}.dump'.format(timestr, postgres_db)
# #     filename_compressed = '{}.gz'.format(filename)
# #     restore_filename = '/tmp/restore.dump.gz'
# #     restore_uncompressed = '/tmp/restore.dump'
# #     local_storage_path = config.get('local_storage', 'path', fallback='./backups/')
# #
# #     manager_config = {
# #         'AWS_BUCKET_NAME': aws_bucket_name,
# #         'AWS_BUCKET_PATH': aws_bucket_path,
# #         'BACKUP_PATH': '/tmp/',
# #         'LOCAL_BACKUP_PATH': local_storage_path
# #     }
# #
# #     local_file_path = '{}{}'.format(manager_config.get('BACKUP_PATH'), filename)
# #
# #     # list task
# #     if args.action == "list":
# #         backup_objects = sorted(list_available_backups(storage_engine, manager_config), reverse=True)
# #         for key in backup_objects:
# #             logger.info("Key : {}".format(key))
# #     # list databases task
# #     elif args.action == "list_dbs":
# #         result = list_postgres_databases(postgres_host,
# #                                          postgres_db,
# #                                          postgres_port,
# #                                          postgres_user,
# #                                          postgres_password)
# #         for line in result.splitlines():
# #             logger.info(line)
# #     # backup task
# #     elif args.action == "backup":
# #         logger.info('Backing up {} database to {}'.format(postgres_db, local_file_path))
# #         result = backup_postgres_db(postgres_host,
# #                                     postgres_db,
# #                                     postgres_port,
# #                                     postgres_user,
# #                                     postgres_password,
# #                                     local_file_path, args.verbose)
# #         if args.verbose:
# #             for line in result.splitlines():
# #                 logger.info(line)
# #
# #         logger.info("Backup complete")
# #         logger.info("Compressing {}".format(local_file_path))
# #         comp_file = compress_file(local_file_path)
# #         if storage_engine == 'LOCAL':
# #             logger.info('Moving {} to local storage...'.format(comp_file))
# #             move_to_local_storage(comp_file, filename_compressed, manager_config)
# #             logger.info("Moved to {}{}".format(manager_config.get('LOCAL_BACKUP_PATH'), filename_compressed))
# #         elif storage_engine == 'S3':
# #             logger.info('Uploading {} to Amazon S3...'.format(comp_file))
# #             upload_to_s3(comp_file, filename_compressed, manager_config)
# #             logger.info("Uploaded to {}".format(filename_compressed))
# #     # restore task
# #     elif args.action == "restore":
# #         if not args.date:
# #             logger.warn('No date was chosen for restore. Run again with the "list" '
# #                         'action to see available restore dates')
# #         else:
# #             try:
# #                 os.remove(restore_filename)
# #             except Exception as e:
# #                 logger.info(e)
# #             all_backup_keys = list_available_backups(storage_engine, manager_config)
# #             backup_match = [s for s in all_backup_keys if args.date in s]
# #             if backup_match:
# #                 logger.info("Found the following backup : {}".format(backup_match))
# #             else:
# #                 logger.error("No match found for backups with date : {}".format(args.date))
# #                 logger.info("Available keys : {}".format([s for s in all_backup_keys]))
# #                 exit(1)
# #
# #             if storage_engine == 'LOCAL':
# #                 logger.info("Choosing {} from local storage".format(backup_match[0]))
# #                 shutil.copy('{}/{}'.format(manager_config.get('LOCAL_BACKUP_PATH'), backup_match[0]),
# #                             restore_filename)
# #                 logger.info("Fetch complete")
# #             elif storage_engine == 'S3':
# #                 logger.info("Downloading {} from S3 into : {}".format(backup_match[0], restore_filename))
# #                 download_from_s3(backup_match[0], restore_filename, manager_config)
# #                 logger.info("Download complete")
# #
# #             logger.info("Extracting {}".format(restore_filename))
# #             ext_file = extract_file(restore_filename)
# #             # cleaned_ext_file = remove_faulty_statement_from_dump(ext_file)
# #             logger.info("Extracted to : {}".format(ext_file))
# #             logger.info("Creating temp database for restore : {}".format(postgres_restore))
# #             tmp_database = create_db(postgres_host,
# #                                      postgres_restore,
# #                                      postgres_port,
# #                                      postgres_user,
# #                                      postgres_password)
# #             logger.info("Created temp database for restore : {}".format(tmp_database))
# #             logger.info("Restore starting")
# #             result = restore_postgres_db(postgres_host,
# #                                          postgres_restore,
# #                                          postgres_port,
# #                                          postgres_user,
# #                                          postgres_password,
# #                                          restore_uncompressed,
# #                                          args.verbose)
# #             if args.verbose:
# #                 for line in result.splitlines():
# #                     logger.info(line)
# #             logger.info("Restore complete")
# #             if args.dest_db is not None:
# #                 restored_db_name = args.dest_db
# #                 logger.info("Switching restored database with newwidgets one : {} > {}".format(
# #                     postgres_restore, restored_db_name
# #                 ))
# #             else:
# #                 restored_db_name = postgres_db
# #                 logger.info("Switching restored database with active one : {} > {}".format(
# #                     postgres_restore, restored_db_name
# #                 ))
# #
# #             swap_after_restore(postgres_host,
# #                                postgres_restore,
# #                                restored_db_name,
# #                                postgres_port,
# #                                postgres_user,
# #                                postgres_password)
# #             logger.info("Database restored and active.")
# #     else:
# #         logger.warn("No valid argument was given.")
# #         logger.warn(args)
#
# def doBackup():
#     postgres_host = "127.0.0.1"
#     postgres_port = "5432"
#     postgres_db = "auto_company_production"
#     postgres_user = "postgres"
#     postgres_password = "postgres"
#
#     try:
#         timestr = datetime.now().strftime('%Y%m%d-%H%M%S')
#         filename = f'backup-{postgres_db}-{timestr}.sql'
#         createDirectory(CosThetaConfigurator.getInstance().getDatabaseBackupDirectory())
#         # filename_compressed = '{}.gz'.format(filename)
#
#         local_file_path = f'{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{filename}'
#
#         result = backup_postgres_db(postgres_host,
#                                     postgres_db,
#                                     postgres_port,
#                                     postgres_user,
#                                     postgres_password,
#                                     local_file_path)
#         # print(result)
#         _log(f"Database {postgres_db} backup complete", LogLevel.INFO, MessageType.GENERAL)
#         comp_file = compress_file(local_file_path)
#         _log(f"Compressed {local_file_path}", LogLevel.INFO, MessageType.GENERAL)
#         filesInDirectory = listFilesInDirectory(CosThetaConfigurator.getInstance().getDatabaseBackupDirectory())
#         filesInDirectory.sort()
#         nFiles = len(filesInDirectory)
#         if nFiles > 5:
#             numberOfFilesToBeRemoved = nFiles - 5
#             # for file in filesInDirectory:
#             #     if file in comp_file :
#             #         pass
#             #     else:
#             #         try:
#             #             # print(f'{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{file}')
#             #             os.remove(f'{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{file}')
#             #             # print(f"File '{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{file}' sent to trash successfully.")
#             #         except FileNotFoundError:
#             #             pass
#             for i in range(numberOfFilesToBeRemoved):
#                 try:
#                     # print(f'{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{file}')
#                     os.remove(f'{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{filesInDirectory[i]}')
#                     # print(f"File '{CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()}{file}' sent to trash successfully.")
#                 except FileNotFoundError:
#                     pass
#
#         try:
#             os.remove(f'{local_file_path}')
#         except:
#             pass
#     except Exception as e:
#         _log(f"Database {postgres_db} backup could not be taken because of {e}", LogLevel.ERROR, MessageType.ISSUE)
#         pass
#
# def doRestore(filePath : str, schema_name : str = "capsule_inspection_schema"):
#     postgres_host = "127.0.0.1"
#     postgres_port = "5432"
#     postgres_db = "auto_company_production"
#     postgres_user = "postgres"
#     postgres_password = "postgres"
#
#     cur = None
#     conn = None
#     try:
#         # Connect to the PostgreSQL database
#         conn = psycopg2.connect(
#             dbname=postgres_db,
#             user=postgres_user,
#             password=postgres_password,
#             host=postgres_host,
#             port=postgres_port
#         )
#
#         # Create a cursor object
#         cur = conn.cursor()
#
#         # Execute the DROP SCHEMA command
#         cur.execute(f'DROP SCHEMA {schema_name} CASCADE;')
#
#         # Commit the changes
#         conn.commit()
#
#         print(f'Schema "{schema_name}" dropped successfully.')
#
#     except Exception as e:
#         print(f'An error occurred: {e}')
#
#     finally:
#         # Close the cursor and connection
#         if cur:
#             cur.close()
#         if conn:
#             conn.close()
#
#     try:
#         unzippedFile = extract_file(src_file=filePath)
#         result = restore_postgres_db(db_host=postgres_host, db=postgres_db, port=postgres_port, user=postgres_user, password=postgres_password, backup_file=unzippedFile, verbose=True)
#         # print(result)
#         _log(f"Database {postgres_db} restore complete", LogLevel.INFO, MessageType.GENERAL)
#     except Exception as e:
#         _log(f"Database {postgres_db} restore incomplete because of {e}", LogLevel.ERROR, MessageType.ISSUE)
#         pass
#
#
# # if __name__ == '__main__':
# #   doBackup()
# #     doRestore("C:/Users/bagch/Downloads/backup-xyz_production-20241116-165100.sql.gz")
#

"""
PostgreSQL Backup and Restore Utility - Production Version

This module provides secure backup and restore functionality for PostgreSQL databases.

Security Features:
- SQL injection protection using parameterized queries
- Password protection via environment variables
- Validation before destructive operations
- Comprehensive error handling and logging

Safety Features:
- Backup validation before restore
- Schema verification before dropping
- Automatic cleanup of old backups
- User confirmation for destructive operations

Author: Production Ready Version
Date: 2024
"""

from datetime import datetime
import subprocess
import os
import platform
import shutil
from typing import Optional, List, Dict
import traceback

import gzip
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from Configuration import CosThetaConfigurator
from utils.CosThetaPrintUtils import printWithTime
from utils.CosThetaFileUtils import *
from utils.RedisUtils import logMessageToConsoleAndFile, borrowRedisConnection, returnRedisConnection
from logutils.Logger import LogLevel, MessageType


_SRC: str = "PostgresBackupUtility"


def _log(message: str,
         level: int   = LogLevel.INFO,
         mtype: int   = MessageType.GENERAL) -> None:
    """
    Route to Redis logging pipeline when available; fall back to
    printWithTime when the logging server is not yet running.
    """
    rc = None
    try:
        rc = borrowRedisConnection()
        if rc is not None:
            logMessageToConsoleAndFile(
                redisConnection=rc,
                data={"text": message, "message_type": mtype},
                aProducer=_SRC,
                level=level,
            )
            return
    except Exception:
        pass
    finally:
        if rc is not None:
            try:
                returnRedisConnection(rc)
            except Exception:
                pass
    # Fallback — logging server not yet up or pool exhausted
    printWithTime(message + "\n")


# ============================================================================
# Configuration and Helper Functions
# ============================================================================

def get_pg_executable(command: str) -> str:
    """
    Get platform-specific PostgreSQL executable name.

    Args:
        command: Base command name ('pg_dump', 'pg_restore', 'psql')

    Returns:
        str: Platform-specific executable name
    """
    if platform.system() == 'Windows':
        return f'{command}.exe'
    return command


def get_database_config() -> Dict[str, str]:
    """
    Get database configuration from environment variables.

    Returns:
        Dict with keys: host, port, database, user, password
    """
    config = {
        'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'auto_company_production'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
    }

    # Warn if using default password
    if config['password'] == 'postgres':
        _log("WARNING: Using default password. Set POSTGRES_PASSWORD environment variable.", LogLevel.WARNING, MessageType.RISK)

    return config


def check_database_exists(config: Dict[str, str]) -> bool:
    """
    Check if the target database exists.

    Args:
        config: Database configuration dictionary

    Returns:
        bool: True if database exists, False otherwise
    """
    conn = None
    cur = None
    try:
        # Connect to the 'postgres' database (always exists) to check if target DB exists
        conn = psycopg2.connect(
            dbname='postgres',
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port'],
            connect_timeout=5
        )
        cur = conn.cursor()

        # Check if database exists
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            [config['database']]
        )

        exists = cur.fetchone() is not None
        return exists

    except psycopg2.OperationalError as e:
        # Connection failed - server might be down
        error_msg = str(e).lower()
        if 'connection refused' in error_msg:
            _log(f"WARNING: PostgreSQL server not reachable at {config['host']}:{config['port']}", LogLevel.WARNING, MessageType.RISK)
        elif 'authentication failed' in error_msg:
            _log(f"WARNING: Authentication failed for user '{config['user']}'", LogLevel.WARNING, MessageType.RISK)
        elif 'timeout' in error_msg:
            _log(f"WARNING: Connection to PostgreSQL timed out", LogLevel.WARNING, MessageType.RISK)
        else:
            _log(f"WARNING: Cannot connect to PostgreSQL: {e}", LogLevel.WARNING, MessageType.RISK)
        return False

    except Exception as e:
        _log(f"WARNING: Database check failed: {e}", LogLevel.WARNING, MessageType.RISK)
        return False

    finally:
        if cur:
            try:
                cur.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

# ============================================================================
# File Compression Functions
# ============================================================================

def compress_file(src_file: str) -> Optional[str]:
    """
    Compress a file using gzip.

    Args:
        src_file: Source file path

    Returns:
        Path to compressed file, or None if failed
    """
    try:
        compressed_file = f"{src_file}.gz"
        _log(f"Compressing {os.path.basename(src_file)}...", LogLevel.INFO, MessageType.GENERAL)

        with open(src_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        if not os.path.exists(compressed_file):
            _log("ERROR: Compressed file was not created", LogLevel.ERROR, MessageType.ISSUE)
            return None

        original_size = os.path.getsize(src_file)
        compressed_size = os.path.getsize(compressed_file)
        ratio = (1 - compressed_size / original_size) * 100

        _log(f"✓ Compressed to {compressed_size:,} bytes ({ratio:.1f}% reduction)", LogLevel.INFO, MessageType.SUCCESS)
        return compressed_file

    except Exception as e:
        _log(f"ERROR: Compression failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        return None


def extract_file(src_file: str) -> Optional[str]:
    """
    Extract a gzipped file.

    Args:
        src_file: Compressed source file path

    Returns:
        Path to extracted file, or None if failed
    """
    try:
        if not os.path.exists(src_file):
            _log(f"ERROR: File not found: {src_file}", LogLevel.ERROR, MessageType.ISSUE)
            return None

        extracted_file = src_file[:-3] if src_file.endswith('.gz') else f"{src_file}.extracted"
        _log(f"Extracting {os.path.basename(src_file)}...", LogLevel.INFO, MessageType.GENERAL)

        with gzip.open(src_file, 'rb') as f_in:
            with open(extracted_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        if not os.path.exists(extracted_file):
            _log("ERROR: Extraction failed", LogLevel.ERROR, MessageType.ISSUE)
            return None

        size = os.path.getsize(extracted_file)
        _log(f"✓ Extracted to {extracted_file} ({size:,} bytes)", LogLevel.INFO, MessageType.SUCCESS)
        return extracted_file

    except Exception as e:
        _log(f"ERROR: Extraction failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        return None


# ============================================================================
# Backup Validation
# ============================================================================

def validate_backup_file(backup_file: str) -> bool:
    """
    Validate that a backup file is readable by pg_restore.

    Args:
        backup_file: Path to backup file

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        if not os.path.exists(backup_file):
            _log(f"ERROR: Backup file not found: {backup_file}", LogLevel.ERROR, MessageType.ISSUE)
            return False

        file_size = os.path.getsize(backup_file)
        if file_size == 0:
            _log("ERROR: Backup file is empty", LogLevel.ERROR, MessageType.ISSUE)
            return False

        # Test if pg_restore can read the file
        process = subprocess.Popen(
            [get_pg_executable('pg_restore'), '-l', backup_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            _log("ERROR: Backup validation failed", LogLevel.ERROR, MessageType.ISSUE)
            _log(f"Details: {stderr.decode()}", LogLevel.ERROR, MessageType.ISSUE)
            return False

        _log(f"✓ Backup validated ({file_size:,} bytes)", LogLevel.INFO, MessageType.SUCCESS)
        return True

    except Exception as e:
        _log(f"ERROR: Validation failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        return False


# ============================================================================
# Backup Functions
# ============================================================================

def backup_postgres_db(config: Dict[str, str], dest_file: str) -> bool:
    """
    Backup PostgreSQL database to a file.

    Args:
        config: Database configuration dictionary
        dest_file: Destination file path for backup

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Set password via environment variable (secure)
        env = os.environ.copy()
        env['PGPASSWORD'] = config['password']

        connection_string = (
            f"postgresql://{config['user']}@{config['host']}:{config['port']}/{config['database']}"
        )

        args = [
            get_pg_executable('pg_dump'),
            f'--file={dest_file}',
            f'--dbname={connection_string}',
            '--format=t',
            '--blobs',
            '--create'
        ]

        _log(f"Backing up {config['database']}...", LogLevel.INFO, MessageType.GENERAL)

        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            error_text = stderr.decode().strip()

            # Parse common errors and provide friendly messages
            if 'does not exist' in error_text:
                _log(f"Database '{config['database']}' does not exist - backup skipped", LogLevel.WARNING, MessageType.RISK)
            elif 'connection refused' in error_text.lower():
                _log(f"PostgreSQL server not running at {config['host']}:{config['port']} - backup skipped", LogLevel.WARNING, MessageType.RISK)
            elif 'authentication failed' in error_text.lower():
                _log(f"Authentication failed for user '{config['user']}' - backup skipped", LogLevel.WARNING, MessageType.RISK)
            elif 'permission denied' in error_text.lower():
                _log(f"Permission denied - backup skipped", LogLevel.WARNING, MessageType.RISK)
            elif 'could not connect' in error_text.lower():
                _log(f"Could not connect to database - backup skipped", LogLevel.WARNING, MessageType.RISK)
            else:
                _log(f"ERROR: Backup failed (code {process.returncode})", LogLevel.ERROR, MessageType.ISSUE)
                _log(f"Details: {error_text}", LogLevel.ERROR, MessageType.ISSUE)

            return False

        if not os.path.exists(dest_file):
            _log("ERROR: Backup file not created", LogLevel.ERROR, MessageType.ISSUE)
            return False

        size = os.path.getsize(dest_file)
        _log(f"✓ Backup created ({size:,} bytes)", LogLevel.INFO, MessageType.SUCCESS)

        # Validate the backup
        if not validate_backup_file(dest_file):
            return False

        return True

    except FileNotFoundError:
        _log(f"pg_dump not found - ensure PostgreSQL client tools are installed", LogLevel.WARNING, MessageType.RISK)
        return False

    except Exception as e:
        _log(f"ERROR: Backup failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        traceback.print_exc()
        return False

# ============================================================================
# Restore Functions
# ============================================================================

def restore_postgres_db(config: Dict[str, str], backup_file: str) -> bool:
    """
    Restore PostgreSQL database from a backup file.

    Args:
        config: Database configuration dictionary
        backup_file: Path to backup file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(backup_file):
            _log(f"ERROR: Backup file not found: {backup_file}", LogLevel.ERROR, MessageType.ISSUE)
            return False

        # Validate before restore
        if not validate_backup_file(backup_file):
            return False

        env = os.environ.copy()
        env['PGPASSWORD'] = config['password']

        connection_string = (
            f"postgresql://{config['user']}@{config['host']}:{config['port']}/{config['database']}"
        )

        args = [
            get_pg_executable('pg_restore'),
            '--no-owner',
            f'--dbname={connection_string}',
            '-v',
            backup_file
        ]

        _log(f"Restoring from {os.path.basename(backup_file)}...", LogLevel.INFO, MessageType.GENERAL)

        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            _log(f"ERROR: Restore failed (code {process.returncode})", LogLevel.ERROR, MessageType.ISSUE)
            _log(f"Details: {stderr.decode()}", LogLevel.ERROR, MessageType.ISSUE)
            return False

        _log("✓ Database restored", LogLevel.INFO, MessageType.SUCCESS)
        return True

    except Exception as e:
        _log(f"ERROR: Restore failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        traceback.print_exc()
        return False


def drop_schema_safe(config: Dict[str, str], schema_name: str) -> bool:
    """
    Safely drop a database schema using parameterized queries.

    Args:
        config: Database configuration dictionary
        schema_name: Name of schema to drop

    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
            dbname=config['database'],
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=config['port']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Check if schema exists
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
            [schema_name]
        )

        if not cur.fetchone():
            _log(f"Schema '{schema_name}' does not exist", LogLevel.WARNING, MessageType.RISK)
            return True

        _log(f"Dropping schema '{schema_name}'...", LogLevel.WARNING, MessageType.RISK)

        # Use SQL identifier to prevent SQL injection
        cur.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
        )

        _log(f"✓ Schema '{schema_name}' dropped", LogLevel.INFO, MessageType.SUCCESS)
        return True

    except Exception as e:
        _log(f"ERROR: Failed to drop schema: {e}", LogLevel.ERROR, MessageType.ISSUE)
        traceback.print_exc()
        return False

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ============================================================================
# High-Level Functions
# ============================================================================

def doBackup(keep_last_n: int = 5) -> bool:
    """
    Create a backup with automatic cleanup of old backups.

    Handles failures gracefully:
    - Database doesn't exist: logs warning, returns False
    - Server unreachable: logs warning, returns False
    - Permission denied: logs warning, returns False

    Args:
        keep_last_n: Number of most recent backups to keep

    Returns:
        bool: True if successful, False otherwise
    """
    config = None
    local_file_path = None

    try:
        config = get_database_config()
        backup_dir = CosThetaConfigurator.getInstance().getDatabaseBackupDirectory()

        # Pre-check: Verify database exists before attempting backup
        if not check_database_exists(config):
            _log(f"BACKUP SKIPPED: Database '{config['database']}' does not exist or is unreachable", LogLevel.WARNING, MessageType.RISK)
            return False

        # Create backup directory
        try:
            createDirectory(backup_dir)
        except Exception as e:
            _log(f"BACKUP SKIPPED: Cannot create backup directory '{backup_dir}': {e}", LogLevel.WARNING, MessageType.RISK)
            return False

        timestr = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f"backup-{config['database']}-{timestr}.sql"
        local_file_path = os.path.join(backup_dir, filename)

        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)
        _log("DATABASE BACKUP", LogLevel.INFO, MessageType.GENERAL)
        _log(f"Database: {config['database']}", LogLevel.INFO, MessageType.GENERAL)
        _log(f"Time: {timestr}", LogLevel.INFO, MessageType.GENERAL)
        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)

        # Create backup
        if not backup_postgres_db(config, local_file_path):
            # Cleanup any partial file
            if local_file_path and os.path.exists(local_file_path):
                try:
                    os.remove(local_file_path)
                except:
                    pass
            return False

        # Compress
        compressed = compress_file(local_file_path)
        if compressed:
            try:
                os.remove(local_file_path)
            except:
                pass
            final_file = compressed
        else:
            final_file = local_file_path

        # Cleanup old backups
        _log(f"Managing backups (keeping {keep_last_n} most recent)...", LogLevel.INFO, MessageType.GENERAL)
        try:
            all_backups = sorted([f for f in os.listdir(backup_dir)
                                  if f.startswith('backup-') and config['database'] in f],
                                 reverse=True)

            if len(all_backups) > keep_last_n:
                for old_file in all_backups[keep_last_n:]:
                    try:
                        os.remove(os.path.join(backup_dir, old_file))
                        _log(f"  Removed: {old_file}", LogLevel.INFO, MessageType.GENERAL)
                    except:
                        pass
        except Exception as e:
            _log(f"Warning: Cleanup failed: {e}", LogLevel.WARNING, MessageType.RISK)

        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)
        _log("✓ BACKUP COMPLETE", LogLevel.INFO, MessageType.SUCCESS)
        _log(f"File: {os.path.basename(final_file)}", LogLevel.INFO, MessageType.SUCCESS)
        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)

        return True

    except KeyboardInterrupt:
        _log("\nBackup cancelled by user", LogLevel.WARNING, MessageType.RISK)
        # Cleanup partial file
        if local_file_path and os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except:
                pass
        return False

    except Exception as e:
        _log(f"✗ BACKUP FAILED: {e}", LogLevel.ERROR, MessageType.ISSUE)
        # Don't print traceback for known error types
        if not isinstance(e,
                          (psycopg2.OperationalError, psycopg2.ProgrammingError, FileNotFoundError, PermissionError)):
            traceback.print_exc()
        # Cleanup partial file
        if local_file_path and os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except:
                pass
        return False


def doRestore(backup_file_path: str,
              schema_name: str = "al_hub_and_disc_assembly_schema",
              confirm: bool = True) -> bool:
    """
    Restore database schema from backup (SAFE - validates before dropping).

    Args:
        backup_file_path: Path to backup file (.sql.gz or .sql)
        schema_name: Schema to restore
        confirm: Ask for confirmation before proceeding

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        config = get_database_config()

        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)
        _log("DATABASE RESTORE", LogLevel.WARNING, MessageType.RISK)
        _log(f"Database: {config['database']}", LogLevel.WARNING, MessageType.RISK)
        _log(f"Schema: {schema_name}", LogLevel.WARNING, MessageType.RISK)
        _log(f"Backup: {os.path.basename(backup_file_path)}", LogLevel.WARNING, MessageType.RISK)
        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)

        # Confirmation
        if confirm:
            _log("WARNING: This will DROP the existing schema!", LogLevel.ERROR, MessageType.ISSUE)
            response = input("Type 'YES' to continue: ")
            if response != 'YES':
                _log("Cancelled", LogLevel.WARNING, MessageType.RISK)
                return False

        # Validate file exists
        if not os.path.exists(backup_file_path):
            _log(f"ERROR: File not found: {backup_file_path}", LogLevel.ERROR, MessageType.ISSUE)
            return False

        _log(f"✓ Found: {backup_file_path}", LogLevel.INFO, MessageType.SUCCESS)

        # Extract if compressed
        working_file = backup_file_path
        if backup_file_path.endswith('.gz'):
            working_file = extract_file(backup_file_path)
            if not working_file:
                return False

        # Validate backup BEFORE dropping schema
        if not validate_backup_file(working_file):
            if working_file != backup_file_path:
                try:
                    os.remove(working_file)
                except:
                    pass
            return False

        # Drop schema (now safe - backup validated)
        if not drop_schema_safe(config, schema_name):
            if working_file != backup_file_path:
                try:
                    os.remove(working_file)
                except:
                    pass
            return False

        # Restore
        if not restore_postgres_db(config, working_file):
            _log("✗ RESTORE FAILED - Schema dropped but restore failed!", LogLevel.ERROR, MessageType.ISSUE)
            if working_file != backup_file_path:
                try:
                    os.remove(working_file)
                except:
                    pass
            return False

        # Cleanup temp file
        if working_file != backup_file_path:
            try:
                os.remove(working_file)
            except:
                pass

        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)
        _log("✓ RESTORE COMPLETE", LogLevel.INFO, MessageType.SUCCESS)
        _log("=" * 70, LogLevel.INFO, MessageType.GENERAL)

        return True

    except KeyboardInterrupt:
        _log("\nCancelled by user", LogLevel.WARNING, MessageType.RISK)
        return False
    except Exception as e:
        _log(f"✗ RESTORE FAILED: {e}", LogLevel.ERROR, MessageType.ISSUE)
        traceback.print_exc()
        return False


# ============================================================================
# AWS S3 Functions (Optional)
# ============================================================================

def upload_to_s3(file_full_path: str, dest_file: str, manager_config: Dict[str, str]) -> bool:
    """Upload file to S3 bucket."""
    if not BOTO3_AVAILABLE:
        _log("ERROR: boto3 not available", LogLevel.ERROR, MessageType.ISSUE)
        return False

    try:
        s3_client = boto3.client('s3')
        bucket = manager_config.get('AWS_BUCKET_NAME')
        key = manager_config.get('AWS_BUCKET_PATH', '') + dest_file

        s3_client.upload_file(file_full_path, bucket, key)
        os.remove(file_full_path)
        _log(f"✓ Uploaded to S3: {key}", LogLevel.INFO, MessageType.SUCCESS)
        return True
    except Exception as e:
        _log(f"ERROR: S3 upload failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        return False


def download_from_s3(backup_s3_key: str, dest_file: str, manager_config: Dict[str, str]) -> bool:
    """Download file from S3 bucket."""
    if not BOTO3_AVAILABLE:
        _log("ERROR: boto3 not available", LogLevel.ERROR, MessageType.ISSUE)
        return False

    try:
        s3_client = boto3.resource('s3')
        bucket = manager_config.get('AWS_BUCKET_NAME')

        s3_client.meta.client.download_file(bucket, backup_s3_key, dest_file)
        _log(f"✓ Downloaded from S3: {backup_s3_key}", LogLevel.INFO, MessageType.SUCCESS)
        return True
    except Exception as e:
        _log(f"ERROR: S3 download failed: {e}", LogLevel.ERROR, MessageType.ISSUE)
        return False


def list_available_backups(storage_engine: str, manager_config: Dict[str, str]) -> List[str]:
    """List backups from local or S3 storage."""
    if storage_engine == 'LOCAL':
        try:
            folder = manager_config.get('LOCAL_BACKUP_PATH')
            if not folder or not os.path.exists(folder):
                return []
            return sorted(os.listdir(folder), reverse=True)
        except:
            return []

    elif storage_engine == 'S3' and BOTO3_AVAILABLE:
        try:
            s3 = boto3.client('s3')
            bucket = manager_config.get('AWS_BUCKET_NAME')
            prefix = manager_config.get('AWS_BUCKET_PATH', '')

            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if 'Contents' in response:
                return sorted([obj['Key'] for obj in response['Contents']], reverse=True)
        except:
            return []

    return []


# ============================================================================
# Main Entry Point
# ============================================================================

# if __name__ == '__main__':
#     import sys
#
#     if len(sys.argv) < 2:
#         print("Usage:")
#         print("  Backup:  python PostgresBackupUtility.py backup")
#         print("  Restore: python PostgresBackupUtility.py restore <backup-file>")
#         sys.exit(1)
#
#     command = sys.argv[1].lower()
#
#     if command == 'backup':
#         success = doBackup()
#         sys.exit(0 if success else 1)
#
#     elif command == 'restore':
#         if len(sys.argv) < 3:
#             _log("ERROR: Backup file required", LogLevel.ERROR, MessageType.ISSUE)
#             sys.exit(1)
#
#         success = doRestore(sys.argv[2], confirm=True)
#         sys.exit(0 if success else 1)
#
#     else:
#         _log(f"ERROR: Unknown command: {command}", LogLevel.ERROR, MessageType.ISSUE)
#         sys.exit(1)