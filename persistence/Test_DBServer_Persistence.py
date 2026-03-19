"""
Comprehensive Test Script for DBServer and Persistence - FIXED VERSION

This script tests:
1. Database connection and schema creation
2. Direct insertions using Persistence.insertData()
3. Redis-based insertions using sendDataFromFEServerToDatabaseServer()
4. Data validation and retrieval
5. Error handling for duplicates
6. Image file creation and storage
7. DateTime handling

Author: Test Suite - Fixed for actual code
Date: 2024
"""

import sys
import os
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import numpy as np
import cv2
# Import the functions at the top of the file (add to existing imports around line 33):
from Persistence import insertRole, insertNewUser

# Add project root to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import redis
import psycopg2

from DBServer import DataPersistence
from Persistence import (
    insertData,
    checkIfRecordExists,
    getDatabaseName,
    setDatabaseName,
    createSchema,
    createAllTables,
    getTodaysDateAsAFolder
)
from utils.RedisUtils import (
    sendDataFromFEServerToDatabaseServer,
    readDataInDatabaseServerFromFEServer,
    clearQueues
)
from BaseUtils import getCurrentTime, getPostgresDatetimeFromString
from utils.CosThetaPrintUtils import *
from Configuration import CosThetaConfigurator


# =============================================================================
# Test Configuration
# =============================================================================

class TestConfig:
    """Configuration for test execution."""

    def __init__(self):
        self.test_db_name = "test_database"
        self.test_mode = "Test"
        self.test_username = "test_user"
        self.redis_host = "localhost"
        self.redis_port = 6379
        self.test_qr_codes = [
            "TEST_QR_001_DOST_LHS_14T",
            "TEST_QR_002_DOSTPLUS_RHS_14T",
            "TEST_QR_003_DOST_LHS_16T",
            "TEST_QR_004_GARUDA_RHS_16T",
            "TEST_QR_005_DOST_LHS_14T",  # For Redis test
            "TEST_QR_006_DOSTPLUS_RHS_16T"  # For Redis test
        ]
        self.db_server = None
        self.redis_connection = None
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0
        }


# =============================================================================
# Test Utilities
# =============================================================================

def print_test_header(test_name: str) -> None:
    """Print formatted test header."""
    printBoldBlue("=" * 80)
    printBoldBlue(f"TEST: {test_name}")
    printBoldBlue("=" * 80)


def print_test_result(test_name: str, passed: bool, message: str = "") -> None:
    """Print formatted test result."""
    if passed:
        printBoldGreen(f"✓ PASSED: {test_name}")
        if message:
            printBoldBlue(f"  {message}")
    else:
        printBoldRed(f"✗ FAILED: {test_name}")
        if message:
            printBoldRed(f"  {message}")


def create_test_image(width: int = 640, height: int = 480, color: Tuple[int, int, int] = (100, 150, 200)) -> np.ndarray:
    """
    Create a test image with timestamp text.

    Args:
        width: Image width
        height: Image height
        color: BGR color tuple

    Returns:
        numpy array representing the image
    """
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = color

    # Add timestamp text
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cv2.putText(image, f"Test Image - {timestamp}", (10, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return image


def verify_record_in_database(qr_code: str, db_name: str) -> bool:
    """
    Verify a record exists in the database.

    Args:
        qr_code: QR code to check
        db_name: Database name

    Returns:
        bool: True if record exists
    """
    try:
        # Use parameterized query to prevent SQL injection
        query = "SELECT qr_code FROM al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data WHERE qr_code = %s"

        conn = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        cur = conn.cursor()
        cur.execute(query, [qr_code])
        result = cur.fetchone()
        cur.close()
        conn.close()

        return result is not None

    except Exception as e:
        printBoldRed(f"Error verifying record: {e}")
        return False


def get_record_from_database(qr_code: str, db_name: str) -> Optional[Dict]:
    """
    Retrieve a record from the database.

    Args:
        qr_code: QR code to retrieve
        db_name: Database name

    Returns:
        Dictionary with record data, or None if not found
    """
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        cur = conn.cursor()

        query = """
            SELECT qr_code, model_name, lhs_rhs, model_tonnage,
                   check_knuckle_result, check_hub_and_bottom_bearing_result,
                   nut_tightening_torque_1, ok_notok_result, created_on,
                   component_assembly_start_datetime
            FROM al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data
            WHERE qr_code = %s
        """
        cur.execute(query, [qr_code])
        row = cur.fetchone()

        if row:
            return {
                'qr_code': row[0],
                'model_name': row[1],
                'lhs_rhs': row[2],
                'model_tonnage': row[3],
                'check_knuckle_result': row[4],
                'check_hub_and_bottom_bearing_result': row[5],
                'nut_tightening_torque_1': row[6],
                'ok_notok_result': row[7],
                'created_on': row[8],
                'component_assembly_start_datetime': row[9]
            }

        return None

    except Exception as e:
        printBoldRed(f"Error retrieving record: {e}")
        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def clean_test_data(qr_codes: List[str], db_name: str) -> None:
    """
    Delete test records from database.

    Args:
        qr_codes: List of QR codes to delete
        db_name: Database name
    """
    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
            user="postgres",
            password="postgres",
            host="127.0.0.1",
            port="5432",
            database=db_name
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        for qr_code in qr_codes:
            try:
                cur.execute(
                    "DELETE FROM al_hub_and_disc_assembly_schema.hub_and_disc_assembly_data WHERE qr_code = %s",
                    [qr_code]
                )
                printBoldBlue(f"Deleted test record: {qr_code}")
            except Exception as e:
                printBoldYellow(f"Could not delete {qr_code}: {e}")

    except Exception as e:
        printBoldRed(f"Error cleaning test data: {e}")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =============================================================================
# Test Cases
# =============================================================================

def test_01_database_connection(config: TestConfig) -> bool:
    """Test 1: Database Connection and Setup."""
    print_test_header("Database Connection and Setup")

    try:
        # Set database name to Test mode
        db_name = setDatabaseName(config.test_mode, createDB=True)
        printBoldGreen(f"✓ Database set to: {db_name}")

        # Verify database name
        retrieved_name = getDatabaseName()
        if retrieved_name != db_name:
            print_test_result("Database Name Verification", False,
                            f"Expected {db_name}, got {retrieved_name}")
            return False

        printBoldGreen(f"✓ Database name verified: {retrieved_name}")

        # Create schema and tables
        createSchema(db_name)
        printBoldGreen(f"✓ Schema created")

        createAllTables(db_name)
        # Add test role and user
        insertRole(role_name="Operator", db_name=db_name, module_access="")
        insertNewUser(
            db_name=db_name,
            username="test_user",
            password="test_password",
            first_name="Test",
            middle_name="",
            last_name="User",
            role_name="Operator",
            email="test@example.com",
            mobile="0000000000",
            remarks="Test user for automated testing"
        )
        printBoldGreen(f"✓ Test user created")
        printBoldGreen(f"✓ Tables created")

        print_test_result("Database Connection and Setup", True,
                         f"Database: {db_name}")
        config.test_results['passed'] += 1
        return True

    except Exception as e:
        print_test_result("Database Connection and Setup", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_02_direct_insertions(config: TestConfig) -> bool:
    """Test 2: Direct Insertions using Persistence.insertData()."""
    print_test_header("Direct Insertions using Persistence.insertData()")

    db_name = getDatabaseName()
    test_data = []

    # Prepare 4 test records
    for i in range(4):
        qr_code = config.test_qr_codes[i]

        # Create test images
        knuckle_img = create_test_image(color=(100, 100, 200))
        hub_img = create_test_image(color=(100, 200, 100))
        top_bearing_img = create_test_image(color=(200, 100, 100))
        nut_img = create_test_image(color=(150, 150, 100))

        # Prepare data
        data = {
            'qr_code': qr_code,
            'knuckle_result': 'OK' if i % 2 == 0 else 'NotOK',
            'knuckle_datetime': getCurrentTime(),
            'hub_result': 'OK',
            'hub_datetime': getCurrentTime(),
            'top_bearing_result': 'OK',
            'top_bearing_datetime': getCurrentTime(),
            'nut_result': 'OK',
            'nut_datetime': getCurrentTime(),
            'torque1': 45.5 + i,
            'torque1_result': 'OK',
            'torque1_datetime': getCurrentTime(),
            'torque2': 50.0 + i,
            'torque2_result': 'OK',
            'torque2_datetime': getCurrentTime(),
            'free_rotation_torque': 5.5 + i,
            'free_rotation_result': 'OK',
            'free_rotation_datetime': getCurrentTime(),
            'overall_result': 'OK' if i % 2 == 0 else 'NotOK'
        }

        test_data.append(data)

    # Insert records
    inserted_count = 0
    failed_count = 0

    for i, data in enumerate(test_data):
        printBoldBlue(f"\nInserting record {i+1}/4: {data['qr_code']}")

        try:
            # Parse QR code to get model, lhs_rhs, tonnage
            parts = data['qr_code'].split('_')
            model_name = parts[2] if len(parts) > 2 else "DOST"
            lhs_rhs = parts[3] if len(parts) > 3 else "LHS"
            tonnage = parts[4] if len(parts) > 4 else "14T"

            # FIXED: db_name is now the FIRST parameter!
            success = insertData(
                db_name=db_name,  # FIRST!
                qr_code=data['qr_code'],
                model_name=model_name,
                lhs_rhs=lhs_rhs,
                model_tonnage=tonnage,
                component_assembly_start_datetime=getCurrentTime(),
                check_knuckle_imagefile='',
                check_knuckle_result=data['knuckle_result'],
                check_knuckle_datetime=data['knuckle_datetime'],
                check_hub_and_bottom_bearing_imagefile='',
                check_hub_and_bottom_bearing_result=data['hub_result'],
                check_hub_and_bottom_bearing_datetime=data['hub_datetime'],
                check_top_bearing_imagefile='',
                check_top_bearing_result=data['top_bearing_result'],
                check_top_bearing_datetime=data['top_bearing_datetime'],
                check_nut_and_platewasher_imagefile='',
                check_nut_and_platewasher_result=data['nut_result'],
                check_nut_and_platewasher_datetime=data['nut_datetime'],
                nut_tightening_torque_1=data['torque1'],
                nut_tightening_torque_1_result=data['torque1_result'],
                nut_tightening_torque_1_datetime=data['torque1_datetime'],
                free_rotations_done='Done',
                free_rotations_datetime=getCurrentTime(),
                check_bunk_for_component_press_imagefile='',
                check_bunk_for_component_press_result='OK',
                check_bunk_for_component_press_datetime=getCurrentTime(),
                component_press_done='Done',
                component_press_datetime=getCurrentTime(),
                check_no_bunk_imagefile='',
                check_no_bunk_result='OK',
                check_no_bunk_datetime=getCurrentTime(),
                nut_tightening_torque_2=data['torque2'],
                nut_tightening_torque_2_result=data['torque2_result'],
                nut_tightening_torque_2_datetime=data['torque2_datetime'],
                check_splitpin_and_washer_imagefile='',
                check_splitpin_and_washer_result='OK',
                check_splitpin_and_washer_datetime=getCurrentTime(),
                check_cap_imagefile='',
                check_cap_result='OK',
                check_cap_datetime=getCurrentTime(),
                check_bunk_cap_press_imagefile='',
                check_bunk_cap_press_result='OK',
                check_bunk_cap_press_datetime=getCurrentTime(),
                cap_press_done='Done',
                cap_press_datetime=getCurrentTime(),
                free_rotation_torque_1=data['free_rotation_torque'],
                free_rotation_torque_1_result=data['free_rotation_result'],
                free_rotation_torque_1_datetime=data['free_rotation_datetime'],
                ok_notok_result=data['overall_result'],
                username='test_user',
                remarks=f'Test record {i+1}'
            )

            if success:
                printBoldGreen(f"✓ Inserted: {data['qr_code']}")
                inserted_count += 1

                # Verify insertion
                if verify_record_in_database(data['qr_code'], db_name):
                    printBoldGreen(f"✓ Verified in database: {data['qr_code']}")
                else:
                    printBoldYellow(f"⚠ Could not verify: {data['qr_code']}")
            else:
                printBoldRed(f"✗ Failed to insert: {data['qr_code']}")
                failed_count += 1

        except Exception as e:
            printBoldRed(f"✗ Error inserting {data['qr_code']}: {e}")
            import traceback
            traceback.print_exc()
            failed_count += 1

    # Test result
    success = (inserted_count == 4 and failed_count == 0)
    print_test_result("Direct Insertions", success,
                     f"Inserted: {inserted_count}/4, Failed: {failed_count}")

    if success:
        config.test_results['passed'] += 1
    else:
        config.test_results['failed'] += 1

    return success


def test_03_duplicate_qr_handling(config: TestConfig) -> bool:
    """Test 3: Duplicate QR Code Handling."""
    print_test_header("Duplicate QR Code Handling")

    db_name = getDatabaseName()
    duplicate_qr = config.test_qr_codes[0]  # Use first QR code again

    try:
        printBoldBlue(f"Attempting to insert duplicate QR: {duplicate_qr}")

        # FIXED: db_name is first parameter
        success = insertData(
            db_name=db_name,
            qr_code=duplicate_qr,
            model_name="DOST",
            lhs_rhs="LHS",
            model_tonnage="14T",
            component_assembly_start_datetime=getCurrentTime(),
            check_knuckle_imagefile='',
            check_knuckle_result='OK',
            check_knuckle_datetime=getCurrentTime(),
            ok_notok_result='OK',
            username='test_user',
            remarks='Duplicate test'
        )

        # Should return False for duplicate
        if not success:
            printBoldGreen(f"✓ Correctly rejected duplicate QR code")
            print_test_result("Duplicate QR Code Handling", True,
                            "Duplicate correctly rejected")
            config.test_results['passed'] += 1
            return True
        else:
            printBoldRed(f"✗ Duplicate was inserted (should have been rejected)")
            print_test_result("Duplicate QR Code Handling", False,
                            "Duplicate was incorrectly accepted")
            config.test_results['failed'] += 1
            return False

    except Exception as e:
        printBoldRed(f"Error in duplicate test: {e}")
        print_test_result("Duplicate QR Code Handling", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_04_redis_connection(config: TestConfig) -> bool:
    """Test 4: Redis Connection."""
    print_test_header("Redis Connection")

    try:
        # Clear queues
        clearQueues(config.redis_connection, reportCounts=False)
        printBoldGreen(f"✓ Redis queues cleared")

        print_test_result("Redis Connection", True,
                         f"Connected to {config.redis_host}:{config.redis_port}")
        config.test_results['passed'] += 1
        return True

    except Exception as e:
        printBoldRed(f"Redis connection failed: {e}")
        print_test_result("Redis Connection", False, str(e))
        config.test_results['failed'] += 1
        return False


def test_05_start_dbserver(config: TestConfig) -> bool:
    """Test 5: Start DBServer in Test Mode."""
    print_test_header("Start DBServer in Test Mode")

    try:
        if config.redis_connection is None:
            printBoldRed("Redis connection not available")
            print_test_result("Start DBServer", False, "No Redis connection")
            config.test_results['failed'] += 1
            return False

        # FIXED: Create DBServer with mode and username
        printBoldBlue(f"Creating DBServer with mode='{config.test_mode}', username='{config.test_username}'")
        config.db_server = DataPersistence(mode=config.test_mode, username=config.test_username)
        printBoldGreen(f"✓ DBServer instance created")

        # DBServer automatically starts threads in __init__
        printBoldGreen(f"✓ DBServer threads started automatically")

        # Give it a moment to initialize
        time.sleep(2)

        print_test_result("Start DBServer", True, "DBServer running in Test mode")
        config.test_results['passed'] += 1
        return True

    except Exception as e:
        printBoldRed(f"Failed to start DBServer: {e}")
        print_test_result("Start DBServer", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_06_redis_insertions(config: TestConfig) -> bool:
    """Test 6: Insertions via Redis using sendDataFromFEServerToDatabaseServer()."""
    print_test_header("Redis-based Insertions")

    if config.redis_connection is None or config.db_server is None:
        printBoldRed("Redis or DBServer not available")
        print_test_result("Redis Insertions", False, "Prerequisites not met")
        config.test_results['failed'] += 1
        return False

    db_name = getDatabaseName()
    inserted_count = 0
    failed_count = 0

    # Send 2 records via Redis
    for i in range(2):
        qr_code = config.test_qr_codes[4 + i]  # Use QR codes 5 and 6

        printBoldBlue(f"\nSending record {i+1}/2 via Redis: {qr_code}")

        # Create test images
        knuckle_img = create_test_image(color=(200, 100, 150))
        hub_img = create_test_image(color=(150, 200, 100))
        top_bearing_img = create_test_image(color=(100, 150, 200))
        nut_img = create_test_image(color=(200, 200, 100))
        split_pin_img = create_test_image(color=(100, 200, 200))
        cap_img = create_test_image(color=(200, 100, 100))
        bung_img = create_test_image(color=(150, 150, 150))

        try:
            # Send via Redis
            success = sendDataFromFEServerToDatabaseServer(
                redisConnection=config.redis_connection,
                qrCode=qr_code,
                knucklePicture=knuckle_img,
                knuckleResult='OK',
                knuckleDatetime=getCurrentTime(),
                hubAndBottomBearingPicture=hub_img,
                hubAndBottomBearingResult='OK',
                hubAndBottomBearingDatetime=getCurrentTime(),
                topBearingPicture=top_bearing_img,
                topBearingResult='OK',
                topBearingDatetime=getCurrentTime(),
                nutAndPlateWasherPicture=nut_img,
                nutAndPlateWasherResult='OK',
                nutAndPlateWasherDatetime=getCurrentTime(),
                tighteningTorque1=47.5 + i,
                tighteningTorque1Result='OK',
                tighteningTorque1Datetime=getCurrentTime(),
                freeRotationDone='Done',
                freeRotationDatetime=getCurrentTime(),
                componentPressBunkCheckingPicture=bung_img,
                componentPressBunkCheckingResult='OK',
                componentPressBunkCheckDatetime=getCurrentTime(),
                componentPressDone='Done',
                componentPressDoneDatetime=getCurrentTime(),
                noBunkCheckingPicture=bung_img,
                noBunkCheckingResult='OK',
                noBunkCheckDatetime=getCurrentTime(),
                tighteningTorque2=52.0 + i,
                tighteningTorque2Result='OK',
                tighteningTorque2Datetime=getCurrentTime(),
                splitPinAndWasherPicture=split_pin_img,
                splitPinAndWasherResult='OK',
                splitPinAndWasherDatetime=getCurrentTime(),
                capCheckingPicture=cap_img,
                capCheckingResult='OK',
                capCheckingDatetime=getCurrentTime(),
                bunkCheckingPicture=bung_img,
                capPressBunkCheckingResult='OK',
                capPressBunkCheckDatetime=getCurrentTime(),
                pressDone='Done',
                capPressDoneDatetime=getCurrentTime(),
                freeRotationTorque1=6.5 + i,
                freeRotationTorque1Result='OK',
                freeRotationTorque1Datetime=getCurrentTime(),
                overallResult='OK',
                aProducer='TestScript'
            )

            if success:
                printBoldGreen(f"✓ Sent to Redis: {qr_code}")

                # Wait for DBServer to process
                printBoldBlue("Waiting for DBServer to process...")
                # time.sleep(3)
                #
                # # Verify in database
                # if verify_record_in_database(qr_code, db_name):
                #     printBoldGreen(f"✓ Verified in database: {qr_code}")
                #     inserted_count += 1
                #
                #     # Retrieve and display some data
                #     record = get_record_from_database(qr_code, db_name)
                #     if record:
                #         printBoldBlue(f"  Model: {record['model_name']}")
                #         printBoldBlue(f"  LHS/RHS: {record['lhs_rhs']}")
                #         printBoldBlue(f"  Torque: {record['nut_tightening_torque_1']}")
                #         printBoldBlue(f"  Result: {record['ok_notok_result']}")
                # else:
                #     printBoldYellow(f"⚠ Not found in database yet: {qr_code}")
                #     failed_count += 1
                # Change to polling with timeout:
                max_attempts = 10
                attempt = 0
                found = False

                while attempt < max_attempts and not found:
                    time.sleep(0.5)  # Check every 500ms
                    found = verify_record_in_database(qr_code, db_name)
                    attempt += 1

                if found:
                    printBoldGreen(f"✓ Verified in database: {qr_code}")
                    inserted_count += 1

                    # Retrieve and display some data
                    record = get_record_from_database(qr_code, db_name)
                    if record:
                        printBoldBlue(f"  Model: {record['model_name']}")
                        printBoldBlue(f"  LHS/RHS: {record['lhs_rhs']}")
                        printBoldBlue(f"  Torque: {record['nut_tightening_torque_1']}")
                        printBoldBlue(f"  Result: {record['ok_notok_result']}")
                else:
                    printBoldYellow(f"⚠ Not found in database after {max_attempts * 0.5} seconds: {qr_code}")
                    failed_count += 1
            else:
                printBoldRed(f"✗ Failed to send to Redis: {qr_code}")
                failed_count += 1

        except Exception as e:
            printBoldRed(f"✗ Error in Redis insertion: {e}")
            import traceback
            traceback.print_exc()
            failed_count += 1

    # Test result
    success = (inserted_count == 2 and failed_count == 0)
    print_test_result("Redis Insertions", success,
                     f"Inserted: {inserted_count}/2, Failed: {failed_count}")

    if success:
        config.test_results['passed'] += 1
    else:
        config.test_results['failed'] += 1

    return success


def test_07_datetime_handling(config: TestConfig) -> bool:
    """Test 7: DateTime Format Handling."""
    print_test_header("DateTime Format Handling")

    db_name = getDatabaseName()

    try:
        # Get a record we inserted
        test_qr = config.test_qr_codes[0]
        record = get_record_from_database(test_qr, db_name)

        if not record:
            printBoldRed(f"Could not retrieve record: {test_qr}")
            print_test_result("DateTime Handling", False, "Record not found")
            config.test_results['failed'] += 1
            return False

        # Check both datetime fields
        created_on = record['created_on']
        assembly_start = record['component_assembly_start_datetime']

        printBoldBlue(f"Created on: {created_on}")
        printBoldBlue(f"Assembly start: {assembly_start}")

        if created_on is not None and assembly_start is not None:
            printBoldGreen(f"✓ DateTime fields stored successfully")

            # Verify they're valid datetimes
            if isinstance(created_on, datetime) and isinstance(assembly_start, datetime):
                printBoldGreen(f"✓ DateTime types are correct")
                print_test_result("DateTime Handling", True,
                                f"Created: {created_on}, Assembly: {assembly_start}")
                config.test_results['passed'] += 1
                return True
            else:
                printBoldYellow(f"⚠ DateTime types unexpected")
                print_test_result("DateTime Handling", False, "Wrong types")
                config.test_results['failed'] += 1
                return False
        else:
            printBoldRed(f"✗ One or both DateTimes are NULL")
            printBoldRed(f"  created_on: {created_on}")
            printBoldRed(f"  assembly_start: {assembly_start}")
            print_test_result("DateTime Handling", False, "DateTime is NULL")
            config.test_results['failed'] += 1
            return False

    except Exception as e:
        printBoldRed(f"Error testing datetime: {e}")
        print_test_result("DateTime Handling", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_08_data_retrieval(config: TestConfig) -> bool:
    """Test 8: Data Retrieval and Validation."""
    print_test_header("Data Retrieval and Validation")

    db_name = getDatabaseName()
    retrieved_count = 0

    try:
        printBoldBlue("Retrieving all test records...")

        for qr_code in config.test_qr_codes[:6]:  # Check first 6 QR codes
            record = get_record_from_database(qr_code, db_name)

            if record:
                printBoldGreen(f"✓ Retrieved: {qr_code}")
                printBoldBlue(f"  Model: {record['model_name']}, "
                            f"Result: {record['ok_notok_result']}, "
                            f"Created: {record['created_on']}")
                retrieved_count += 1
            else:
                printBoldYellow(f"⚠ Not found: {qr_code}")

        # We expect to find all 6 records (4 direct + 2 redis)
        success = (retrieved_count == 6)
        print_test_result("Data Retrieval", success,
                         f"Retrieved: {retrieved_count}/6 records")

        if success:
            config.test_results['passed'] += 1
        else:
            config.test_results['failed'] += 1

        return success

    except Exception as e:
        printBoldRed(f"Error in data retrieval: {e}")
        print_test_result("Data Retrieval", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_09_torque_values(config: TestConfig) -> bool:
    """Test 9: Torque Value Storage and Retrieval."""
    print_test_header("Torque Value Validation")

    db_name = getDatabaseName()

    try:
        # Check torque values for records we inserted
        test_qr = config.test_qr_codes[0]
        record = get_record_from_database(test_qr, db_name)

        if not record:
            printBoldRed(f"Could not retrieve record: {test_qr}")
            print_test_result("Torque Values", False, "Record not found")
            config.test_results['failed'] += 1
            return False

        torque = record['nut_tightening_torque_1']
        printBoldBlue(f"Torque value: {torque}")

        # Verify it's a float and in expected range
        if isinstance(torque, (int, float)):
            if 40.0 <= torque <= 60.0:
                printBoldGreen(f"✓ Torque value valid: {torque}")
                print_test_result("Torque Values", True, f"Torque: {torque}")
                config.test_results['passed'] += 1
                return True
            else:
                printBoldRed(f"✗ Torque out of range: {torque}")
                print_test_result("Torque Values", False, "Out of range")
                config.test_results['failed'] += 1
                return False
        else:
            printBoldRed(f"✗ Torque wrong type: {type(torque)}")
            print_test_result("Torque Values", False, "Wrong type")
            config.test_results['failed'] += 1
            return False

    except Exception as e:
        printBoldRed(f"Error testing torque: {e}")
        print_test_result("Torque Values", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


def test_10_cleanup(config: TestConfig) -> bool:
    """Test 10: Cleanup Test Data."""
    print_test_header("Cleanup Test Data")

    try:
        db_name = getDatabaseName()

        printBoldBlue("Cleaning up test records...")
        clean_test_data(config.test_qr_codes, db_name)

        # Verify cleanup
        remaining = 0
        for qr_code in config.test_qr_codes:
            if verify_record_in_database(qr_code, db_name):
                printBoldYellow(f"⚠ Still exists: {qr_code}")
                remaining += 1

        if remaining == 0:
            printBoldGreen(f"✓ All test records cleaned up")
            print_test_result("Cleanup", True, "All test data removed")
            config.test_results['passed'] += 1
            return True
        else:
            printBoldYellow(f"⚠ {remaining} records still in database")
            print_test_result("Cleanup", False, f"{remaining} records remain")
            config.test_results['failed'] += 1
            return False

    except Exception as e:
        printBoldRed(f"Error in cleanup: {e}")
        print_test_result("Cleanup", False, str(e))
        config.test_results['failed'] += 1
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# Main Test Runner
# =============================================================================

config = TestConfig()
try:
    config.redis_connection = redis.Redis(
        host=config.redis_host,
        port=config.redis_port,
        retry_on_timeout=True
    )

    # Test connection
    config.redis_connection.ping()
    printBoldGreen(f"✓ Connected to Redis at {config.redis_host}:{config.redis_port}")
except:
    pass


def run_all_tests() -> None:
    """Run all test cases."""
    printBoldBlue("=" * 80)
    printBoldBlue("DATABASE AND PERSISTENCE TEST SUITE")
    printBoldBlue("=" * 80)
    printBoldBlue(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    printBoldBlue("=" * 80)

    # Run tests in sequence (EXCLUDING cleanup)
    tests = [
        test_01_database_connection,
        test_02_direct_insertions,
        test_03_duplicate_qr_handling,
        test_04_redis_connection,
        test_05_start_dbserver,
        test_06_redis_insertions,
        test_07_datetime_handling,
        test_08_data_retrieval,
        test_09_torque_values,
        # NOTE: test_10_cleanup runs AFTER DBServer is stopped
    ]

    for test_func in tests:
        try:
            test_func(config)
            print()  # Blank line between tests
        except KeyboardInterrupt:
            printBoldRed("\n\nTest interrupted by user")
            break
        except Exception as e:
            printBoldRed(f"\n\nUnexpected error in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    printBoldBlue("=" * 80)
    printBoldBlue("TEST SUMMARY")
    printBoldBlue("=" * 80)
    printBoldGreen(f"✓ PASSED: {config.test_results['passed']}")
    if config.test_results['failed'] > 0:
        printBoldRed(f"✗ FAILED: {config.test_results['failed']}")
    else:
        printBoldBlue(f"✗ FAILED: {config.test_results['failed']}")

    if config.test_results['skipped'] > 0:
        printBoldYellow(f"⊘ SKIPPED: {config.test_results['skipped']}")

    total = sum(config.test_results.values())
    if total > 0:
        pass_rate = (config.test_results['passed'] / total) * 100
        printBoldBlue(f"Pass Rate: {pass_rate:.1f}%")

    # CRITICAL: Stop DBServer BEFORE cleanup
    if config.db_server:
        try:
            config.db_server.stop()
            printBoldBlue("DBServer stopped")
            time.sleep(3)  # Give threads time to actually finish
        except:
            pass

    # Clear any remaining items in Redis
    try:
        clearQueues(config.redis_connection)
        printBoldBlue("Redis queues cleared")
    except:
        pass

    # NOW run cleanup after everything has stopped
    try:
        test_10_cleanup(config)
    except Exception as e:
        printBoldRed(f"Error in cleanup: {e}")

    printBoldBlue(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    printBoldBlue("=" * 80)

if __name__ == '__main__':
    try:
        run_all_tests()
    except KeyboardInterrupt:
        printBoldRed("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        printBoldRed(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)