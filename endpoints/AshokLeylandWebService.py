import flask
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import psycopg2
from psycopg2 import Error
from io import StringIO
import csv
from datetime import datetime, date
from typing import List, Tuple
import socket
import logging

# Suppress warnings and Flask logs
import warnings

warnings.filterwarnings('ignore')
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)

# Database configuration
db_params = {
    "host": "127.0.0.1",
    "database": "auto_company_production",
    "user": "postgres",
    "password": "postgres",
    "port": "5432"
}

# SQL Queries
select_query_by_model_name = """
    SELECT 
        qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
        knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
        hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
        nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
        nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
        nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
        free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
        free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
        splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
        bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
        remarks, created_on
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    WHERE model_name ILIKE %s
    ORDER BY component_manufacturing_date ASC
"""

select_query_by_model_name_and_date_limits = """
    SELECT 
        qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
        knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
        hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
        nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
        nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
        nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
        free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
        free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
        splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
        bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
        remarks, created_on
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    WHERE model_name = %s AND component_manufacturing_date >= %s AND component_manufacturing_date <= %s
    ORDER BY component_manufacturing_date ASC
"""

select_query_from_start_date_to_end_date = """
    SELECT 
        qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
        knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
        hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
        nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
        nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
        nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
        free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
        free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
        splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
        bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
        remarks, created_on
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    WHERE component_manufacturing_date >= %s AND component_manufacturing_date <= %s
    ORDER BY component_manufacturing_date ASC
"""

select_query_unique_model_names = """
    SELECT DISTINCT model_name
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    ORDER BY model_name
"""

select_query_unique_model_names_by_date = """
    SELECT DISTINCT model_name
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    WHERE component_manufacturing_date >= %s AND component_manufacturing_date <= %s
    ORDER BY model_name
"""


# Helper functions
def generate_csv_string(records):
    output = StringIO()
    writer = csv.writer(output, lineterminator='\n')
    headers = [
        'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
        'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
        'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
        'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
        'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
        'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
        'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
        'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
        'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
        'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
        'remarks', 'created_on'
    ]
    writer.writerow(headers)
    for record in records:
        formatted_record = list(record)
        if isinstance(formatted_record[4], (datetime, date)):
            formatted_record[4] = formatted_record[4].strftime('%Y-%m-%d')
        if isinstance(formatted_record[-1], (datetime, date)):
            formatted_record[-1] = formatted_record[-1].strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow(formatted_record)
    return output.getvalue()


def generate_csv_string_for_models(model_names):
    output = StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['model_name'])
    for model in model_names:
        writer.writerow([model])
    return output.getvalue()


def records_to_json(records):
    headers = [
        'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
        'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
        'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
        'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
        'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
        'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
        'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
        'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
        'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
        'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
        'remarks', 'created_on'
    ]
    json_data = []
    for record in records:
        record_dict = dict(zip(headers, record))
        if isinstance(record_dict['component_manufacturing_date'], (datetime, date)):
            record_dict['component_manufacturing_date'] = record_dict['component_manufacturing_date'].strftime(
                '%Y-%m-%d')
        if isinstance(record_dict['created_on'], (datetime, date)):
            record_dict['created_on'] = record_dict['created_on'].strftime('%Y-%m-%d %H:%M:%S')
        json_data.append(record_dict)
    return json_data


def parse_date(date_str):
    if not date_str:
        # print(f"parse_date: Received empty date string, returning None")
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # print(f"parse_date: Successfully parsed {date_str} to {dt}")
        return dt
    except ValueError as e:
        # print(f"parse_date: Failed to parse {date_str}, error: {str(e)}")
        raise ValueError(f"Date must be in YYYY-MM-DD format, received: {date_str}")


def getUniqueModelNames(db_name: str = db_params["database"]) -> List[str]:
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(select_query_unique_model_names)
                return [row[0] for row in cursor.fetchall()]
    except Error as e:
        print(f"Database error in getUniqueModelNames: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in getUniqueModelNames: {e}")
        return []


def getDataByModelName(modelName: str, db_name: str = db_params["database"]) -> str:
    try:
        if not modelName:
            raise ValueError("Model name must be non-empty")
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                # print(f"Executing query for model_name: {modelName}")
                cursor.execute(select_query_by_model_name, (modelName,))
                records = cursor.fetchall()
                # print(f"Found {len(records)} records")
                return records
    except Exception as e:
        print(f"Error in getDataByModelName: {str(e)}")
        return f"Error: {str(e)}"


def getDataByModelNameAndDateLimits(modelName: str, startDate: str | None, endDate: str = None,
                                    db_name: str = db_params["database"]) -> str:
    try:
        if not modelName:
            raise ValueError("Model name must be non-empty")
        print(
            f"getDataByModelNameAndDateLimits: Received modelName={modelName}, startDate={startDate}, endDate={endDate}")
        start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0,
                                                                                  microsecond=0)
        end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59,
                                                                            microsecond=999999)
        # print(f"getDataByModelNameAndDateLimits: Using start_dt={start_dt}, end_dt={end_dt}")
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(select_query_by_model_name_and_date_limits, (modelName, start_dt, end_dt))
                records = cursor.fetchall()
                # print(f"Found {len(records)} records for model_name={modelName}")
                return records
    except Exception as e:
        print(f"Error in getDataByModelNameAndDateLimits: {str(e)}")
        return f"Error: {str(e)}"


def getDataOfTodayByModelNumber(modelName: str, db_name: str = db_params["database"]) -> str:
    return getDataByModelNameAndDateLimits(modelName=modelName, startDate=None, endDate=None, db_name=db_name)


def getDataByDateLimits(startDate: str | None, endDate: str = None, db_name: str = db_params["database"]) -> Tuple[
    str, List[str]]:
    try:
        # print(f"getDataByDateLimits: Received startDate={startDate}, endDate={endDate}")
        start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0,
                                                                                  microsecond=0)
        end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59,
                                                                            microsecond=999999)
        # print(f"getDataByDateLimits: Using start_dt={start_dt}, end_dt={end_dt}")
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(select_query_from_start_date_to_end_date, (start_dt, end_dt))
                records = cursor.fetchall()
                cursor.execute(select_query_unique_model_names_by_date, (start_dt, end_dt))
                model_names = [row[0] for row in cursor.fetchall()]
                # print(f"Found {len(records)} records, model_names: {model_names}")
                return records, model_names
    except Exception as e:
        print(f"Error in getDataByDateLimits: {str(e)}")
        return f"Error: {str(e)}", []


def getAllDataOfToday(db_name: str = db_params["database"]) -> Tuple[str, List[str]]:
    return getDataByDateLimits(startDate=None, endDate=None, db_name=db_name)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 0))
        s.listen(1)
        port = s.getsockname()[1]
        return port


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hub And Disc Data Query</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f4f6f9; 
        }
        h1 { 
            color: #2c3e50; 
            text-align: center; 
        }
        .query-section { 
            margin-bottom: 20px; 
            padding: 15px; 
            background-color: #ffffff; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }
        h3 { 
            color: #34495e; 
            margin-bottom: 10px; 
        }
        button { 
            padding: 10px 20px; 
            margin: 5px; 
            background-color: #3498db; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            transition: background-color 0.3s; 
        }
        button:hover { 
            background-color: #2980b9; 
        }
        button:disabled { 
            background-color: #bdc3c7; 
            cursor: not-allowed; 
        }
        textarea { 
            width: 100%; 
            height: 200px; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
            padding: 10px; 
            font-family: monospace; 
        }
        select, input[type="date"] { 
            padding: 8px; 
            margin: 5px; 
            width: 200px; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
        }
        label { 
            margin-right: 10px; 
            color: #34495e; 
        }
        .code-example { 
            margin-top: 20px; 
            padding: 15px; 
            background-color: #ffffff; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
        }
        pre { 
            background-color: #2b2b2b; 
            color: #f8f8f8; 
            padding: 15px; 
            border-radius: 5px; 
            overflow-x: auto; 
        }
        h4 { 
            margin-bottom: 10px; 
            color: #34495e; 
        }
        #recordCount { 
            margin-left: 20px; 
            display: inline-block; 
            color: #27ae60; 
            font-weight: bold; 
        }
        .icon { 
            margin-right: 8px; 
        }
        .payload { 
            background-color: #e0e0e0; 
            font-family: monospace; 
            border: 1px solid #ccc; 
            padding: 5px; 
        }
        /* New table-section styles */
        .table-section {
            margin-top: 20px;
            padding: 15px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        /* New table styles */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 10px;
            border: 1px solid #ddd;
            text-align: left;
        }
        th.json {
            background-color: #3498db;
            color: white;
        }
        th.csv {
            background-color: #27ae60;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #e6f3ff;
        }
        td.payload {
            background-color: #e0e0e0;
            font-family: monospace;
            border: 1px solid #ccc;
            padding: 5px;
        }
    </style>
</head>
<body>
    <h1><i class="fas fa-database icon"></i>Hub And Disc Data Query</h1>

    <div class="query-section">
        <h3><i class="fas fa-car icon"></i>Get Data by Model Name</h3>
        <label for="modelName1">Model Name:</label>
        <select id="modelName1">
            <option value="">Select Model</option>
            {% for model in model_names %}
            <option value="{{ model }}">{{ model }}</option>
            {% endfor %}
        </select>
        <button id="by_model_name_csv_btn" onclick="validateAndQuery('by_model_name', 'csv', 'modelName1')"><i class="fas fa-file-csv icon"></i>Retrieve Records as CSV</button>
        <button id="by_model_name_json_btn" onclick="validateAndQuery('by_model_name', 'json', 'modelName1')"><i class="fas fa-file-code icon"></i>Retrieve Records as JSON</button>
    </div>

    <div class="query-section">
        <h3><i class="fas fa-car icon"></i>Get Data by Model Name and Date Limits</h3>
        <label for="modelName2">Model Name:</label>
        <select id="modelName2">
            <option value="">Select Model</option>
            {% for model in model_names %}
            <option value="{{ model }}">{{ model }}</option>
            {% endfor %}
        </select>
        <label for="startDate">Start Date:</label>
        <input type="date" id="startDate">
        <label for="endDate">End Date:</label>
        <input type="date" id="endDate">
        <button id="by_model_name_and_date_csv_btn" onclick="validateAndQuery('by_model_name_and_date', 'csv', 'modelName2')"><i class="fas fa-file-csv icon"></i>Retrieve Records as CSV</button>
        <button id="by_model_name_and_date_json_btn" onclick="validateAndQuery('by_model_name_and_date', 'json', 'modelName2')"><i class="fas fa-file-code icon"></i>Retrieve Records as JSON</button>
    </div>

    <div class="query-section">
        <h3><i class="fas fa-car icon"></i>Get Data of Today by Model Number</h3>
        <label for="modelName3">Model Name:</label>
        <select id="modelName3">
            <option value="">Select Model</option>
            {% for model in model_names %}
            <option value="{{ model }}">{{ model }}</option>
            {% endfor %}
        </select>
        <button id="today_by_model_csv_btn" onclick="validateAndQuery('today_by_model', 'csv', 'modelName3')"><i class="fas fa-file-csv icon"></i>Retrieve Records as CSV</button>
        <button id="today_by_model_json_btn" onclick="validateAndQuery('today_by_model', 'json', 'modelName3')"><i class="fas fa-file-code icon"></i>Retrieve Records as JSON</button>
    </div>

    <div class="query-section">
        <h3><i class="fas fa-calendar-alt icon"></i>Get Data by Date Limits</h3>
        <label for="startDate2">Start Date:</label>
        <input type="date" id="startDate2">
        <label for="endDate2">End Date:</label>
        <input type="date" id="endDate2">
        <button id="by_date_limits_csv_btn" onclick="validateAndQuery('by_date_limits', 'csv')"><i class="fas fa-file-csv icon"></i>Retrieve Records as CSV</button>
        <button id="by_date_limits_json_btn" onclick="validateAndQuery('by_date_limits', 'json')"><i class="fas fa-file-code icon"></i>Retrieve Records as JSON</button>
    </div>

    <div class="query-section">
        <h3><i class="fas fa-calendar-day icon"></i>Get All Data of Today</h3>
        <button id="all_today_csv_btn" onclick="validateAndQuery('all_today', 'csv')"><i class="fas fa-file-csv icon"></i>Retrieve Records as CSV</button>
        <button id="all_today_json_btn" onclick="validateAndQuery('all_today', 'json')"><i class="fas fa-file-code icon"></i>Retrieve Records as JSON</button>
    </div>

    <h3><i class="fas fa-table icon"></i>Result <span id="recordCount"></span></h3>
    <textarea id="result" readonly></textarea>

    <div class="code-example">
        <h3><i class="fas fa-code icon"></i>API Usage Examples</h3>
        <h4>Python (using requests)</h4>
        <pre>
import requests

# Get data by model name (CSV)
response = requests.post('http://localhost:8000/api/by_model_name/csv/', json={'modelName': 'Model 1'})
if response.status_code == 200:
    print(response.text)
else:
    print(f"Error: {response.text}")

# Get data by model name and date limits (CSV)
response = requests.post('http://localhost:8000/api/by_model_name_and_date/csv/', 
                        json={'modelName': 'Model 1', 'startDate': '2025-06-01', 'endDate': '2025-06-29'})
if response.status_code == 200:
    print(response.text)
else:
    print(f"Error: {response.text}")

# Get unique model names (JSON)
response = requests.post('http://localhost:8000/api/get_unique_model_names/json/', json={})
if response.status_code == 200:
    print(response.json()['model_names'])
else:
    print(f"Error: {response.text}")

# Get data by model name (JSON)
response = requests.post('http://localhost:8000/api/by_model_name/json/', json={'modelName': 'Model 1'})
if response.status_code == 200:
    print(response.json()['data'])
else:
    print(f"Error: {response.text}")
        </pre>

        <h4>JavaScript (using fetch)</h4>
        <pre>
fetch('http://localhost:8000/api/by_model_name/csv/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modelName: 'Model 1' })
})
.then(response => response.status === 200 ? response.text() : Promise.reject(response.text()))
.then(data => console.log(data))
.catch(error => console.error('Error:', error));

fetch('http://localhost:8000/api/by_model_name_and_date/csv/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modelName: 'Model 1', startDate: '2025-06-01', endDate: '2025-06-29' })
})
.then(response => response.status === 200 ? response.text() : Promise.reject(response.text()))
.then(data => console.log(data))
.catch(error => console.error('Error:', error));

fetch('http://localhost:8000/api/get_unique_model_names/json/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
})
.then(response => response.status === 200 ? response.json() : Promise.reject(response.text()))
.then(data => console.log(data.model_names))
.catch(error => console.error('Error:', error));

fetch('http://localhost:8000/api/by_model_name/json/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modelName: 'Model 1' })
})
.then(response => response.status === 200 ? response.json() : Promise.reject(response.text()))
.then(data => console.log(data.data))
.catch(error => console.error('Error:', error));
        </pre>

        <h4>Java (using HttpClient)</h4>
        <pre>
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.nio.charset.StandardCharsets;

public class ApiClient {
    public static void main(String[] args) throws Exception {
        HttpClient client = HttpClient.newHttpClient();

        // Get data by model name (CSV)
        String json1 = "{\"modelName\": \"Model 1\"}";
        HttpRequest request1 = HttpRequest.newBuilder()
            .uri(URI.create("http://localhost:8000/api/by_model_name/csv/"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json1))
            .build();
        HttpResponse<String> response1 = client.send(request1, HttpResponse.BodyHandlers.ofString());
        if (response1.statusCode() == 200) {
            System.out.println(response1.body());
        } else {
            System.out.println("Error: " + response1.body());
        }

        // Get data by model name and date limits (CSV)
        String json2 = "{\"modelName\": \"Model 1\", \"startDate\": \"2025-06-01\", \"endDate\": \"2025-06-29\"}";
        HttpRequest request2 = HttpRequest.newBuilder()
            .uri(URI.create("http://localhost:8000/api/by_model_name_and_date/csv/"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json2))
            .build();
        HttpResponse<String> response2 = client.send(request2, HttpResponse.BodyHandlers.ofString());
        if (response2.statusCode() == 200) {
            System.out.println(response2.body());
        } else {
            System.out.println("Error: " + response2.body());
        }

        // Get unique model names (JSON)
        String json3 = "{}";
        HttpRequest request3 = HttpRequest.newBuilder()
            .uri(URI.create("http://localhost:8000/api/get_unique_model_names/json/"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json3))
            .build();
        HttpResponse<String> response3 = client.send(request3, HttpResponse.BodyHandlers.ofString());
        if (response3.statusCode() == 200) {
            System.out.println(response3.body());
        } else {
            System.out.println("Error: " + response3.body());
        }

        // Get data by model name (JSON)
        HttpRequest request4 = HttpRequest.newBuilder()
            .uri(URI.create("http://localhost:8000/api/by_model_name/json/"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json1))
            .build();
        HttpResponse<String> response4 = client.send(request4, HttpResponse.BodyHandlers.ofString());
        if (response4.statusCode() == 200) {
            System.out.println(response4.body());
        } else {
            System.out.println("Error: " + response4.body());
        }
    }
}
        </pre>

        <h4>.NET (C# using HttpClient)</h4>
        <pre>
using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class Program
{
    static async Task Main(string[] args)
    {
        using HttpClient client = new HttpClient();

        // Get data by model name (CSV)
        string json1 = "{\"modelName\": \"Model 1\"}";
        var content1 = new StringContent(json1, Encoding.UTF8, "application/json");
        HttpResponseMessage response1 = await client.PostAsync("http://localhost:8000/api/by_model_name/csv/", content1);
        if (response1.StatusCode == System.Net.HttpStatusCode.OK)
        {
            string result1 = await response1.Content.ReadAsStringAsync();
            Console.WriteLine(result1);
        }
        else
        {
            string error1 = await response1.Content.ReadAsStringAsync();
            Console.WriteLine($"Error: {error1}");
        }

        // Get data by model name and date limits (CSV)
        string json2 = "{\"modelName\": \"Model 1\", \"startDate\": \"2025-06-01\", \"endDate\": \"2025-06-29\"}";
        var content2 = new StringContent(json2, Encoding.UTF8, "application/json");
        HttpResponseMessage response2 = await client.PostAsync("http://localhost:8000/api/by_model_name_and_date/csv/", content2);
        if (response2.StatusCode == System.Net.HttpStatusCode.OK)
        {
            string result2 = await response2.Content.ReadAsStringAsync();
            Console.WriteLine(result2);
        }
        else
        {
            string error2 = await response2.Content.ReadAsStringAsync();
            Console.WriteLine($"Error: {error2}");
        }

        // Get unique model names (JSON)
        string json3 = "{}";
        var content3 = new StringContent(json3, Encoding.UTF8, "application/json");
        HttpResponseMessage response3 = await client.PostAsync("http://localhost:8000/api/get_unique_model_names/json/", content3);
        if (response3.StatusCode == System.Net.HttpStatusCode.OK)
        {
            string result3 = await response3.Content.ReadAsStringAsync();
            Console.WriteLine(result3);
        }
        else
        {
            string error3 = await response3.Content.ReadAsStringAsync();
            Console.WriteLine($"Error: {error3}");
        }

        // Get data by model name (JSON)
        var content4 = new StringContent(json1, Encoding.UTF8, "application/json");
        HttpResponseMessage response4 = await client.PostAsync("http://localhost:8000/api/by_model_name/json/", content4);
        if (response4.StatusCode == System.Net.HttpStatusCode.OK)
        {
            string result4 = await response4.Content.ReadAsStringAsync();
            Console.WriteLine(result4);
        }
        else
        {
            string error4 = await response4.Content.ReadAsStringAsync();
            Console.WriteLine($"Error: {error4}");
        }
    }
}
        </pre>

        <h4>cURL</h4>
        <pre>
curl -X POST http://localhost:8000/api/by_model_name/csv/ -H "Content-Type: application/json" -d '{"modelName": "Model 1"}'

curl -X POST http://localhost:8000/api/by_model_name_and_date/csv/ -H "Content-Type: application/json" -d '{"modelName": "Model 1", "startDate": "2025-06-01", "endDate": "2025-06-29"}'

curl -X POST http://localhost:8000/api/get_unique_model_names/json/ -H "Content-Type: application/json" -d '{}' -o model_names.json

curl -X POST http://localhost:8000/api/by_model_name/json/ -H "Content-Type: application/json" -d '{"modelName": "Model 1"}' -o data.json
        </pre>
    </div>

    <script type="text/javascript">
        console.log('Test script executed');
    </script>
    <script type="text/javascript" src="static/app.js">
    </script>

<div class="table-section">
        <h2>API Endpoints for JSON Responses</h2>
        <table>
            <tr>
                <th class="json">Method Name</th>
                <th class="json">API Endpoint</th>
                <th class="json">Expected Payload</th>
            </tr>
            <tr>
                <td>getUniqueModelNames</td>
                <td>http://192.168.1.100:8000/api/get_unique_model_names/json/</td>
                <td class="payload">{}</td>
            </tr>
            <tr>
                <td>getDataByModelName</td>
                <td>http://192.168.1.100:8000/api/get_data_by_model_name/json/</td>
                <td class="payload">{"model_name": "DOST"}</td>
            </tr>
            <tr>
                <td>getDataByModelNameAndDateLimits</td>
                <td>http://192.168.1.100:8000/api/get_data_by_model_name_and_date_limits/json/</td>
                <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
            </tr>
            <tr>
                <td>getDataOfTodayByModelNumber</td>
                <td>http://192.168.1.100:8000/api/get_data_of_today_by_model_number/json/</td>
                <td class="payload">{"model_name": "DOST"}</td>
            </tr>
            <tr>
                <td>getDataByDateLimits</td>
                <td>http://192.168.1.100:8000/api/get_data_by_date_limits/json/</td>
                <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
            </tr>
            <tr>
                <td>getAllDataOfToday</td>
                <td>http://192.168.1.100:8000/api/get_all_data_of_today/json/</td>
                <td class="payload">{}</td>
            </tr>
        </table>

        <h2>API Endpoints for CSV Responses</h2>
        <table>
            <tr>
                <th class="csv">Method Name</th>
                <th class="csv">API Endpoint</th>
                <th class="csv">Expected Payload</th>
            </tr>
            <tr>
                <td>getUniqueModelNames</td>
                <td>http://192.168.1.100:8000/api/get_unique_model_names/csv/</td>
                <td class="payload">{}</td>
            </tr>
            <tr>
                <td>getDataByModelName</td>
                <td>http://192.168.1.100:8000/api/get_data_by_model_name/csv/</td>
                <td class="payload">{"model_name": "DOST"}</td>
            </tr>
            <tr>
                <td>getDataByModelNameAndDateLimits</td>
                <td>http://192.168.1.100:8000/api/get_data_by_model_name_and_date_limits/csv/</td>
                <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
            </tr>
            <tr>
                <td>getDataOfTodayByModelNumber</td>
                <td>http://192.168.1.100:8000/api/get_data_of_today_by_model_number/csv/</td>
                <td class="payload">{"model_name": "DOST"}</td>
            </tr>
            <tr>
                <td>getDataByDateLimits</td>
                <td>http://192.168.1.100:8000/api/get_data_by_date_limits/csv/</td>
                <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
            </tr>
            <tr>
                <td>getAllDataOfToday</td>
                <td>http://192.168.1.100:8000/api/get_all_data_of_today/csv/</td>
                <td class="payload">{}</td>
            </tr>
        </table>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    model_names = getUniqueModelNames()
    _, date_limits_models = getDataByDateLimits(startDate=None, endDate=None)
    _, today_models = getAllDataOfToday()
    # print(f"model_names: {model_names}")
    # print(f"date_limits_models: {date_limits_models}")
    # print(f"today_models: {today_models}")
    rendered_html = render_template_string(HTML_TEMPLATE, model_names=model_names)
    with open('rendered.html', 'w', encoding='utf-8') as f:
        f.write(rendered_html)
    return rendered_html, 200, {'Content-Type': 'text/html'}


@app.route('/api/by_model_name/<format>/', methods=['POST'])
def api_by_model_name(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    model_name = data.get('modelName')
    try:
        records = getDataByModelName(model_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/by_model_name_and_date/<format>/', methods=['POST'])
def api_by_model_name_and_date(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    # print(f"api_by_model_name_and_date: Received data={data}")
    model_name = data.get('modelName')
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    try:
        records = getDataByModelNameAndDateLimits(model_name, start_date, end_date)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/today_by_model/<format>/', methods=['POST'])
def api_by_model(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    model_name = data.get('model_name')
    try:
        records = getDataOfTodayByModelNumber(model_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/by_date_limits/<format>/', methods=['POST'])
def api_by_date_limits(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    # print(f"api_by_date_limits: Received data={data}")
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    try:
        records, _ = getDataByDateLimits(start_date, end_date)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/all_today/<format>/', methods=['POST'])
def api_all_today(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    try:
        records, _ = getAllDataOfToday()
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_unique_model_names/<format>/', methods=['POST'])
def api_get_unique_model_names(format):
    if format not in ['json', 'csv']:
        return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
    data = request.get_json() or {}
    db_name = data.get('db_name', db_params["database"])
    try:
        model_names = getUniqueModelNames(db_name)
        if format == 'json':
            return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string_for_models(model_names)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_data_by_model_name/<format>/', methods=['POST'])
def api_get_data_by_model_name(format):
    if format not in ['json', 'csv']:
        return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
    data = request.get_json()
    model_name = data.get('model_name')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataByModelName(model_name, db_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_data_by_model_name_and_date_limits/<format>/', methods=['POST'])
def api_get_data_by_model_name_and_date_limits(format):
    if format not in ['json', 'csv']:
        return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
    data = request.get_json()
    model_name = data.get('model_name')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataByModelNameAndDateLimits(model_name, start_date, end_date, db_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_data_of_today_by_model_number/<format>/', methods=['POST'])
def api_get_data_of_today_by_model_number(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    model_name = data.get('model_name')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_data_by_date_limits/<format>/', methods=['POST'])
def api_get_data_by_date_limits(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db_name = data.get('db_name', db_params["database"])
    try:
        records, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_all_data_of_today/<format>/', methods=['POST'])
def api_get_all_data_of_today(format):
    if format not in ['csv', 'json']:
        return jsonify({'error': 'Invalid format. Use /csv/ or /json/'}), 400
    data = request.get_json() or {}
    db_name = data.get('db_name', db_params["database"])
    try:
        records, _ = getAllDataOfToday(db_name=db_name)
        if isinstance(records, str) and records.startswith("Error"):
            raise Exception(records)
        if format == 'json':
            json_data = records_to_json(records)
            return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
        else:
            csv_string = generate_csv_string(records)
            return csv_string, 200, {'Content-Type': 'text/csv'}
    except Exception as e:
        if format == 'json':
            return jsonify({'error': str(e)}), 500
        else:
            return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}


@app.route('/api/get_unique_model_names', methods=['POST'])
def api_get_unique_model_names_default():
    data = request.get_json() or {}
    db_name = data.get('db_name', db_params["database"])
    try:
        model_names = getUniqueModelNames(db_name)
        return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_data_by_model_name', methods=['POST'])
def api_get_data_by_model_name_default():
    data = request.get_json()
    model_name = data.get('model_name')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataByModelName(modelName=model_name, db_name=db_name)
        csv_string = generate_csv_string(records)
        return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_data_by_model_name_and_date_limits', methods=['POST'])
def api_get_data_by_model_name_and_date_limits_default():
    data = request.get_json()
    model_name = data.get('model_name')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataByModelNameAndDateLimits(modelName=model_name, startDate=start_date, endDate=end_date,
                                                  db_name=db_name)
        csv_string = generate_csv_string(records)
        return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_data_of_today_by_model_number', methods=['POST'])
def api_get_data_of_today_by_model_number_default():
    data = request.get_json()
    model_name = data.get('model_name')
    db_name = data.get('db_name', db_params["database"])
    try:
        records = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
        csv_string = generate_csv_string(records)
        return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_data_by_date_limits', methods=['POST'])
def api_get_data_by_date_limits_default():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db_name = data.get('db_name', db_params["database"])
    try:
        records, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
        csv_string = generate_csv_string(records)
        return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_all_data_of_today', methods=['POST'])
def api_get_all_data_of_today_default():
    data = request.get_json() or {}
    db_name = data.get('db_name', db_params["database"])
    try:
        records, _ = getAllDataOfToday(db_name=db_name)
        csv_string = generate_csv_string(records)
        return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500
def startWebService():
    try:
        desired_port = 8000
        try:
            app.run(host='0.0.0.0', port=desired_port, debug=False)
            print(f"Started server WebService on http://localhost:{desired_port}/")
        except OSError as e:
            print(f"Port {desired_port} is in use, trying a free port")
            free_port = find_free_port()
            print(f"Starting server on port {free_port}")
            app.run(host='0.0.0.0', port=free_port, debug=False)
    except Exception as e:
        print(f"Failed to start server: {e}")


# if __name__ == '__main__':
#     # print("Testing getDataByModelName...")
#     model_names = getUniqueModelNames()
#     # if model_names:
#     #     result = getDataByModelName(model_names[0])
#     #     print(f"Testing with model: {model_names[0]}")
#     #     print(generate_csv_string(result))
#     # else:
#     #     print("No model names available in the database")
#     startWebService()

# ********************************* Start of Web Services Code with ICONS and CosTheta at port 80 ***************
# import flask
# from flask import Flask, request, jsonify, render_template_string
# import psycopg2
# from psycopg2 import Error
# from io import StringIO
# import csv
# from datetime import datetime, date
# from typing import List, Tuple
# import socket
# from utils.CosThetaPrintUtils import *
# import logging
#
# import warnings
# warnings.filterwarnings('ignore')
# logging.getLogger('werkzeug').setLevel(logging.ERROR)
#
# app = Flask(__name__)
#
# # Database configuration
# db_params = {
#     "host": "127.0.0.1",
#     "database": "auto_company_production",
#     "user": "postgres",
#     "password": "postgres",
#     "port": "5432"
# }
#
# # SQL Queries
# select_query_by_model_name = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE model_name = %s
# """
#
# select_query_by_model_name_and_date_limits = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE model_name = %s AND created_on >= %s AND created_on <= %s
# """
#
# select_query_from_start_date_to_end_date = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE created_on >= %s AND created_on <= %s
# """
#
# select_query_unique_model_names = """
#     SELECT DISTINCT model_name
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     ORDER BY model_name
# """
#
# select_query_unique_model_names_by_date = """
#     SELECT DISTINCT model_name
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE created_on >= %s AND created_on <= %s
#     ORDER BY model_name
# """
#
# # Helper function to generate CSV string for data records
# def generate_csv_string(records):
#     output = StringIO()
#     writer = csv.writer(output, lineterminator='\n')
#     headers = [
#         'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
#         'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
#         'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
#         'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
#         'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
#         'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
#         'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
#         'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
#         'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
#         'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
#         'remarks', 'created_on'
#     ]
#     writer.writerow(headers)
#     writer.writerows(records)
#     return output.getvalue()
#
# # Helper function to generate CSV string for model names
# def generate_csv_string_for_models(model_names):
#     output = StringIO()
#     writer = csv.writer(output, lineterminator='\n')
#     writer.writerow(['model_name'])
#     for model in model_names:
#         writer.writerow([model])
#     return output.getvalue()
#
# # Helper function to convert records to JSON-compatible list of dictionaries
# def records_to_json(records):
#     headers = [
#         'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
#         'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
#         'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
#         'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
#         'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
#         'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
#         'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
#         'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
#         'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
#         'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
#         'remarks', 'created_on'
#     ]
#     return [dict(zip(headers, record)) for record in records]
#
# # Helper function to parse date (YYYY-MM-DD to DD-MM-YYYY)
# def parse_date(date_str):
#     if not date_str:
#         return None
#     try:
#         dt = datetime.strptime(date_str, "%Y-%m-%d")
#         return dt.strftime("%d-%m-%Y")
#     except ValueError:
#         raise ValueError("Date must be in YYYY-MM-DD format from calendar")
#
# # Method to get unique model names
# def getUniqueModelNames(db_name: str = db_params["database"]) -> List[str]:
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_unique_model_names)
#                 return [row[0] for row in cursor.fetchall()]
#     except Error as e:
#         print(f"Database error: {e}")
#         return []
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         return []
#
# # Method 1
# def getDataByModelName(modelName: str, db_name: str = db_params["database"]) -> str:
#     try:
#         if not modelName:
#             raise ValueError("Model name must be non-empty")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name, (modelName,))
#                 records = cursor.fetchall()
#                 return generate_csv_string(records)
#     except Exception as e:
#         return f"Error: {str(e)}"
#
# # Method 2
# def getDataByModelNameAndDateLimits(modelName: str, startDate: str | None, endDate: str = None, db_name: str = db_params["database"]) -> str:
#     try:
#         if not modelName:
#             raise ValueError("Model name must be non-empty")
#         start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name_and_date_limits, (modelName, start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 return generate_csv_string(records)
#     except Exception as e:
#         return f"Error: {str(e)}"
#
# # Method 3
# def getDataOfTodayByModelNumber(modelName: str, db_name: str = db_params["database"]) -> str:
#     return getDataByModelNameAndDateLimits(modelName=modelName, startDate=None, endDate=None, db_name=db_name)
#
# # Method 4
# def getDataByDateLimits(startDate: str | None, endDate: str = None, db_name: str = db_params["database"]) -> Tuple[str, List[str]]:
#     try:
#         start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 # Fetch records
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 csv_string = generate_csv_string(records)
#                 # Fetch unique model names
#                 cursor.execute(select_query_unique_model_names_by_date, (start_dt_db, end_dt_db))
#                 model_names = [row[0] for row in cursor.fetchall()]
#                 return csv_string, model_names
#     except Exception as e:
#         return f"Error: {str(e)}", []
#
# # Method 5
# def getAllDataOfToday(db_name: str = db_params["database"]) -> Tuple[str, List[str]]:
#     return getDataByDateLimits(startDate=None, endDate=None, db_name=db_name)
#
# # Function to find a free port
# def find_free_port() -> int:
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind(('0.0.0.0', 0))  # Bind to port 0 to let OS assign a free port
#         s.listen(1)
#         port = s.getsockname()[1]  # Get the assigned port
#         return port
#
# # Webpage HTML with API tables and Python example
# HTML_TEMPLATE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <title>Hub And Disc Data Query</title>
#     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" integrity="sha512-z3gLpd7yknf1YoNbCzqRKc4qyor8gaKU1qmn+CShxbuBusANI9QpRohGBreCFkKxLhei6S9CQXFEbbKuqLg0DA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
#     <style>
#         body { font-family: Arial, sans-serif; margin: 20px; position: relative; }
#         .query-section { margin-bottom: 20px; }
#         button { padding: 10px; margin: 5px; }
#         button:disabled { background-color: #ccc; cursor: not-allowed; }
#         textarea { width: 100%; height: 200px; }
#         select, input[type="date"] { padding: 5px; margin: 5px; width: 200px; }
#         label { margin-right: 10px; }
#         table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
#         th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
#         th.json { background-color: #4682B4; color: white; }
#         th.csv { background-color: #2E8B57; color: white; }
#         tr:nth-child(even) { background-color: #f2f2f2; }
#         .payload { background-color: #e0e0e0; font-family: monospace; }
#         pre { background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-family: monospace; white-space: pre-wrap; }
#         .kw { color: #0000FF; } /* Keywords */
#         .str { color: #008000; } /* Strings */
#         .com { color: #808080; } /* Comments */
#         .costheta-comment {
#             position: fixed;
#             top: 10px;
#             right: 10px;
#             background-color: #003087;
#             color: white;
#             padding: 8px 12px;
#             border-radius: 15px;
#             font-size: 0.9rem;
#             font-weight: 500;
#             box-shadow: 0 2px 4px rgba(0,0,0,0.2);
#             z-index: 1000;
#         }
#         .header-icon { margin-right: 10px; }
#     </style>
#     <script>
#         function downloadCSV(csv, filename) {
#             const blob = newwidgets Blob([csv], { type: 'text/csv' });
#             const url = window.URL.createObjectURL(blob);
#             const a = document.createElement('a');
#             a.href = url;
#             a.download = filename;
#             document.body.appendChild(a);
#             a.click();
#             window.URL.revokeObjectURL(url);
#             document.body.removeChild(a);
#         }
#
#         function query(method, params) {
#             fetch(`http://localhost:80/api/${method}`, {
#                 method: 'POST',
#                 headers: { 'Content-Type': 'application/json' },
#                 body: JSON.stringify(params)
#             })
#             .then(response => response.json())
#             .then(data => {
#                 if (data.csv) {
#                     document.getElementById('result').value = data.csv;
#                     downloadCSV(data.csv, `${method}_${newwidgets Date().toISOString().split('T')[0]}.csv`);
#                 } else {
#                     document.getElementById('result').value = data.error || 'No data';
#                 }
#             })
#             .catch(error => {
#                 document.getElementById('result').value = `Error: ${error}`;
#             });
#         }
#
#         function validateAndQuery(method, selectId = null, startDateId = null, endDateId = null) {
#             const modelSelect = selectId ? document.getElementById(selectId) : null;
#             const modelName = modelSelect ? modelSelect.value : '';
#             const startDate = startDateId ? document.getElementById(startDateId).value : '';
#             const endDate = endDateId ? document.getElementById(endDateId).value : '';
#
#             // Check for model-based queries
#             if (['by_model_name', 'by_model_name_and_date', 'today_by_model'].includes(method)) {
#                 if (modelSelect && modelSelect.options.length <= 1) {
#                     alert('No model names available in the database. Please populate the database.');
#                     document.getElementById('result').value = 'Error: No model names available';
#                     return;
#                 }
#                 if (!modelName) {
#                     alert('Please select a valid model name.');
#                     document.getElementById('result').value = 'Error: Model name not selected';
#                     return;
#                 }
#             }
#
#             // Send query
#             const params = {};
#             if (modelName) params.modelName = modelName;
#             if (startDate) params.startDate = startDate;
#             if (endDate) params.endDate = endDate;
#             query(method, params);
#         }
#
#         // Initialize button states
#         window.onload = function() {
#             const modelSelects = [
#                 { selectId: 'modelName1', buttonId: 'by_model_name_btn' },
#                 { selectId: 'modelName2', buttonId: 'by_model_name_and_date_btn' },
#                 { selectId: 'modelName3', buttonId: 'today_by_model_btn' }
#             ];
#             modelSelects.forEach(({ selectId, buttonId }) => {
#                 const select = document.getElementById(selectId);
#                 if (select && select.options.length <= 1) {
#                     document.getElementById(buttonId).disabled = true;
#                 }
#             });
#
#             // Disable date-based buttons if no models
#             const dateLimitsModels = {{ date_limits_models | tojson }};
#             const todayModels = {{ today_models | tojson }};
#             if (dateLimitsModels.length === 0) {
#                 document.getElementById('by_date_limits_btn').disabled = true;
#             }
#             if (todayModels.length === 0) {
#                 document.getElementById('all_today_btn').disabled = true;
#             }
#         };
#     </script>
# </head>
# <body>
#     <div class="costheta-comment">Made by CosTheta Technologies</div>
#     <h2>API Endpoints for JSON Responses</h2>
#     <table>
#         <tr>
#             <th class="json">Method Name</th>
#             <th class="json">API Endpoint</th>
#             <th class="json">Expected Payload</th>
#         </tr>
#         <tr>
#             <td>getUniqueModelNames</td>
#             <td>http://192.168.1.100:80/api/get_unique_model_names/json/</td>
#             <td class="payload">{}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelName</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name/json/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelNameAndDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name_and_date_limits/json/</td>
#             <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getDataOfTodayByModelNumber</td>
#             <td>http://192.168.1.100:80/api/get_data_of_today_by_model_number/json/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_date_limits/json/</td>
#             <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getAllDataOfToday</td>
#             <td>http://192.168.1.100:80/api/get_all_data_of_today/json/</td>
#             <td class="payload">{}</td>
#         </tr>
#     </table>
#
#     <h2>API Endpoints for CSV Responses</h2>
#     <table>
#         <tr>
#             <th class="csv">Method Name</th>
#             <th class="csv">API Endpoint</th>
#             <th class="csv">Expected Payload</th>
#         </tr>
#         <tr>
#             <td>getUniqueModelNames</td>
#             <td>http://192.168.1.100:80/api/get_unique_model_names/csv/</td>
#             <td class="payload">{}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelName</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name/csv/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelNameAndDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name_and_date_limits/csv/</td>
#             <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getDataOfTodayByModelNumber</td>
#             <td>http://192.168.1.100:80/api/get_data_of_today_by_model_number/csv/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_date_limits/csv/</td>
#             <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getAllDataOfToday</td>
#             <td>http://192.168.1.100:80/api/get_all_data_of_today/csv/</td>
#             <td class="payload">{}</td>
#         </tr>
#     </table>
#
#     <h2>Python Example for API Call</h2>
#     <pre>
# <span class="kw">import</span> requests
#
# <span class="kw">def</span> get_data_by_model_name(model_name=<span class="str">"DOST"</span>):
#     url = <span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>
#     payload = {<span class="str">"model_name"</span>: model_name}
#     <span class="kw">try</span>:
#         response = requests.post(url, json=payload, timeout=10)
#         response.raise_for_status()  <span class="com"># Raises exception for 4xx/5xx errors</span>
#         <span class="kw">return</span> response.json()  <span class="com"># Returns {"data": [{...}, ...]} or {"error": "..."}</span>
#     <span class="kw">except</span> requests.RequestException <span class="kw">as</span> e:
#         <span class="kw">return</span> {<span class="str">"error"</span>: <span class="str">f"Request failed: {str(e)}"</span>}
#
# <span class="com"># Example usage</span>
# result = get_data_by_model_name(<span class="str">"DOST"</span>)
# print(result)
#     </pre>
#
#     <h2>Java Example for API Call</h2>
#     <pre>
# <span class="kw">import</span> java.net.http.HttpClient;
# <span class="kw">import</span> java.net.http.HttpRequest;
# <span class="kw">import</span> java.net.http.HttpResponse;
# <span class="kw">import</span> java.net.URI;
# <span class="kw">import</span> java.time.Duration;
# <span class="kw">import</span> java.util.Map;
#
# <span class="kw">public class</span> ApiClient {
#     <span class="kw">public static</span> String getDataByModelName(String modelName) {
#         HttpClient client = HttpClient.<span class="kw">newBuilder</span>()
#             .connectTimeout(Duration.<span class="kw">ofSeconds</span>(10))
#             .build();
#         String jsonPayload = <span class="str">"{\"model_name\":\""</span> + modelName + <span class="str">"\"}"</span>;
#         HttpRequest request = HttpRequest.<span class="kw">newBuilder</span>()
#             .uri(URI.<span class="kw">create</span>(<span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>))
#             .header(<span class="str">"Content-Type"</span>, <span class="str">"application/json"</span>)
#             .POST(HttpRequest.BodyPublishers.<span class="kw">ofString</span>(jsonPayload))
#             .build();
#         <span class="kw">try</span> {
#             HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.<span class="kw">ofString</span>());
#             <span class="kw">if</span> (response.statusCode() >= 400) {
#                 <span class="kw">return</span> <span class="str">"{\"error\":\"HTTP error code: "</span> + response.statusCode() + <span class="str">"\"}"</span>;
#             }
#             <span class="kw">return</span> response.body(); <span class="com">// Returns JSON string {"data": [{...}, ...]} or {"error": "..."}</span>
#         } <span class="kw">catch</span> (Exception e) {
#             <span class="kw">return</span> <span class="str">"{\"error\":\"Request failed: "</span> + e.getMessage() + <span class="str">"\"}"</span>;
#         }
#     }
#
#     <span class="kw">public static void</span> main(String[] args) {
#         String result = getDataByModelName(<span class="str">"DOST"</span>);
#         System.<span class="kw">out</span>.println(result);
#     }
# }
#     </pre>
#
#     <h2>.NET Example for API Call</h2>
#     <pre>
# <span class="kw">using</span> System;
# <span class="kw">using</span> System.Net.Http;
# <span class="kw">using</span> System.Text;
# <span class="kw">using</span> System.Threading.Tasks;
#
# <span class="kw">public class</span> ApiClient
# {
#     <span class="kw">private static readonly</span> HttpClient client = <span class="kw">newwidgets</span> HttpClient();
#
#     <span class="kw">public static async</span> Task<string> GetDataByModelName(<span class="kw">string</span> modelName)
#     {
#         client.Timeout = TimeSpan.<span class="kw">FromSeconds</span>(10);
#         <span class="kw">var</span> payload = <span class="str">$"{\"model_name\":\"{modelName}\"}"</span>;
#         <span class="kw">var</span> content = <span class="kw">newwidgets</span> StringContent(payload, Encoding.UTF8, <span class="str">"application/json"</span>);
#         <span class="kw">try</span>
#         {
#             <span class="kw">var</span> response = <span class="kw">await</span> client.PostAsync(<span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>, content);
#             response.EnsureSuccessStatusCode();
#             <span class="kw">return await</span> response.Content.ReadAsStringAsync(); <span class="com">// Returns JSON string {"data": [{...}, ...]} or {"error": "..."}</span>
#         }
#         <span class="kw">catch</span> (HttpRequestException e)
#         {
#             <span class="kw">return</span> <span class="str">$"{\"error\":\"Request failed: {e.Message}\"}"</span>;
#         }
#     }
#
#     <span class="kw">public static async</span> Task Main(<span class="kw">string</span>[] args)
#     {
#         <span class="kw">string</span> result = <span class="kw">await</span> GetDataByModelName(<span class="str">"DOST"</span>);
#         Console.WriteLine(result);
#     }
# }
#     </pre>
#
#     <h1><i class="fas fa-database header-icon"></i>Hub And Disc Data Query</h1>
#     <div class="query-section">
#         <h3><i class="fas fa-car header-icon"></i>Get Data by Model Name</h3>
#         <label for="modelName1">Model Name:</label>
#         <select id="modelName1">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <button id="by_model_name_btn" onclick="validateAndQuery('by_model_name', 'modelName1')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3><i class="fas fa-car header-icon"></i>Get Data by Model Name and Date Limits</h3>
#         <label for="modelName2">Model Name:</label>
#         <select id="modelName2">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <label for="startDate">Start Date:</label>
#         <input type="date" id="startDate">
#         <label for="endDate">End Date:</label>
#         <input type="date" id="endDate">
#         <button id="by_model_name_and_date_btn" onclick="validateAndQuery('by_model_name_and_date', 'modelName2', 'startDate', 'endDate')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3><i class="fas fa-car header-icon"></i>Get Today's Data by Model Number</h3>
#         <label for="modelName3">Model Name:</label>
#         <select id="modelName3">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <button id="today_by_model_btn" onclick="validateAndQuery('today_by_model', 'modelName3')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3><i class="fas fa-calendar header-icon"></i>Get Data by Date Limits</h3>
#         <label for="startDate2">Start Date:</label>
#         <input type="date" id="startDate2">
#         <label for="endDate2">End Date:</label>
#         <input type="date" id="endDate2">
#         <button id="by_date_limits_btn" onclick="validateAndQuery('by_date_limits', null, 'startDate2', 'endDate2')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3><i class="fas fa-calendar header-icon"></i>Get All Data of Today</h3>
#         <button id="all_today_btn" onclick="validateAndQuery('all_today')">Run</button>
#     </div>
#     <h3>Result</h3>
#     <textarea id="result" readonly></textarea>
# </body>
# </html>
# """
#
# # Existing Routes (for webpage)
# @app.route('/')
# def index():
#     model_names = getUniqueModelNames()
#     # Check model names for date-based queries
#     _, date_limits_models = getDataByDateLimits(startDate=None, endDate=None)  # Default to today for initialization
#     _, today_models = getAllDataOfToday()
#     return render_template_string(HTML_TEMPLATE, model_names=model_names, date_limits_models=date_limits_models, today_models=today_models)
#
# @app.route('/api/by_model_name', methods=['POST'])
# def api_by_model_name():
#     data = request.get_json()
#     model_name = data.get('modelName')
#     try:
#         csv_string = getDataByModelName(model_name)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/by_model_name_and_date', methods=['POST'])
# def api_by_model_name_and_date():
#     data = request.get_json()
#     model_name = data.get('modelName')
#     start_date = data.get('startDate')
#     end_date = data.get('endDate')
#     try:
#         csv_string = getDataByModelNameAndDateLimits(model_name, start_date, end_date)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/today_by_model', methods=['POST'])
# def api_by_model():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     try:
#         csv_string = getDataOfTodayByModelNumber(model_name)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/by_date_limits', methods=['POST'])
# def api_by_date_limits():
#     data = request.get_json()
#     start_date = data.get('startDate')
#     end_date = data.get('endDate')
#     try:
#         csv_string, _ = getDataByDateLimits(start_date, end_date)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/all_today', methods=['POST'])
# def api_all_today():
#     try:
#         csv_string, _ = getAllDataOfToday()
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# # Updated Routes (for external API access with format)
# @app.route('/api/get_unique_model_names/<format>/', methods=['POST'])
# def api_get_unique_model_names(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         model_names = getUniqueModelNames(db_name)
#         if format == 'json':
#             return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
#         else:  # csv
#             csv_string = generate_csv_string_for_models(model_names)
#             return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_model_name/<format>/', methods=['POST'])
# def api_get_data_by_model_name(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name, (model_name,))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     csv_string = generate_csv_string(records)
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_model_name_and_date_limits/<format>/', methods=['POST'])
# def api_get_data_by_model_name_and_date_limits(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         start_dt = parse_date(start_date) if start_date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(end_date) if end_date else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name_and_date_limits, (model_name, start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     csv_string = generate_csv_string(records)
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_of_today_by_model_number/<format>/', methods=['POST'])
# def api_get_data_of_today_by_model_number(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#                 end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
#                 cursor.execute(select_query_by_model_name_and_date_limits, (model_name, start_dt, end_dt))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_date_limits/<format>/', methods=['POST'])
# def api_get_data_by_date_limits(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         start_dt = parse_date(start_date) if start_date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(end_date) if end_date else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_all_data_of_today/<format>/', methods=['POST'])
# def api_get_all_data_of_today(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getAllDataOfToday(db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt, end_dt))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# # Backward-compatible routes (default to previous behavior)
# @app.route('/api/get_unique_model_names', methods=['POST'])
# def api_get_unique_model_names_default():
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         model_names = getUniqueModelNames(db_name)
#         return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_model_name', methods=['POST'])
# def api_get_data_by_model_name_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataByModelName(modelName=model_name, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_model_name_and_date_limits', methods=['POST'])
# def api_get_data_by_model_name_and_date_limits_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataByModelNameAndDateLimits(modelName=model_name, startDate=start_date, endDate=end_date, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_of_today_by_model_number', methods=['POST'])
# def api_get_data_of_today_by_model_number_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_date_limits', methods=['POST'])
# def api_get_data_by_date_limits_default():
#     data = request.get_json()
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_all_data_of_today', methods=['POST'])
# def api_get_all_data_of_today_default():
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getAllDataOfToday(db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# def startWebService():
#     try:
#         desired_port = 80
#         try:
#             app.run(host='0.0.0.0', port=desired_port, debug=False)
#             printBoldBlue(f"*****************")
#             printBlue(f"Started Hub and Disc Web Service")
#             printBoldBlue(f"*****************")
#             print(f"Started server WebService on http://localhost:{desired_port}/")
#         except OSError as e:
#             print(f"Port {desired_port} is in use, trying a free port")
#             free_port = find_free_port()
#             print(f"Starting server on port {free_port}")
#             app.run(host='0.0.0.0', port=free_port, debug=False)
#     except Exception as e:
#         print(f"Failed to start server: {e}")
#
# startWebService()

# ********************************* End of Web Services Code with ICONS and CosTheta at port 80 ***************

# ********************************* Older Web Services Code without ICONS and CosTheta ***************

# from flask import Flask, request, jsonify, render_template_string
# import psycopg2
# from psycopg2 import Error
# from io import StringIO
# import csv
# from datetime import datetime, date
# from typing import List, Tuple
# import socket
# from utils.CosThetaPrintUtils import *
#
# app = Flask(__name__)
#
# # Database configuration
# db_params = {
#     "host": "127.0.0.1",
#     "database": "auto_company_production",
#     "user": "postgres",
#     "password": "postgres",
#     "port": "5432"
# }
#
# # SQL Queries
# select_query_by_model_name = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE model_name = %s
# """
#
# select_query_by_model_name_and_date_limits = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE model_name = %s AND created_on >= %s AND created_on <= %s
# """
#
# select_query_from_start_date_to_end_date = """
#     SELECT
#         qr_code, model_name, lhs_rhs, model_tonnage, component_manufacturing_date,
#         knuckle_check_imagefile, knuckle_check_result, hub_and_first_bearing_check_imagefile,
#         hub_and_first_bearing_check_result, second_bearing_check_imagefile, second_bearing_check_result,
#         nut_and_platewasher_check_imagefile, nut_and_platewasher_check_result, nut_tightening_torque_1,
#         nut_tightening_torque_1_result, free_rotation_torque_1, free_rotation_torque_1_result,
#         nut_tightening_torque_2, nut_tightening_torque_2_result, free_rotation_torque_2,
#         free_rotation_torque_2_result, nut_tightening_torque_3, nut_tightening_torque_3_result,
#         free_rotation_torque_3, free_rotation_torque_3_result, splitpin_and_washer_check_imagefile,
#         splitpin_and_washer_check_result, cap_check_imagefile, cap_check_result, bung_check_imagefile,
#         bung_check_result, cap_pressed_successfully_check_result, ok_notok_result, username,
#         remarks, created_on
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE created_on >= %s AND created_on <= %s
# """
#
# select_query_unique_model_names = """
#     SELECT DISTINCT model_name
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     ORDER BY model_name
# """
#
# select_query_unique_model_names_by_date = """
#     SELECT DISTINCT model_name
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE created_on >= %s AND created_on <= %s
#     ORDER BY model_name
# """
#
# # Helper function to generate CSV string for data records
# def generate_csv_string(records):
#     output = StringIO()
#     writer = csv.writer(output, lineterminator='\n')
#     headers = [
#         'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
#         'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
#         'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
#         'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
#         'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
#         'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
#         'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
#         'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
#         'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
#         'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
#         'remarks', 'created_on'
#     ]
#     writer.writerow(headers)
#     writer.writerows(records)
#     return output.getvalue()
#
# # Helper function to generate CSV string for model names
# def generate_csv_string_for_models(model_names):
#     output = StringIO()
#     writer = csv.writer(output, lineterminator='\n')
#     writer.writerow(['model_name'])
#     for model in model_names:
#         writer.writerow([model])
#     return output.getvalue()
#
# # Helper function to convert records to JSON-compatible list of dictionaries
# def records_to_json(records):
#     headers = [
#         'qr_code', 'model_name', 'lhs_rhs', 'model_tonnage', 'component_manufacturing_date',
#         'knuckle_check_imagefile', 'knuckle_check_result', 'hub_and_first_bearing_check_imagefile',
#         'hub_and_first_bearing_check_result', 'second_bearing_check_imagefile', 'second_bearing_check_result',
#         'nut_and_platewasher_check_imagefile', 'nut_and_platewasher_check_result', 'nut_tightening_torque_1',
#         'nut_tightening_torque_1_result', 'free_rotation_torque_1', 'free_rotation_torque_1_result',
#         'nut_tightening_torque_2', 'nut_tightening_torque_2_result', 'free_rotation_torque_2',
#         'free_rotation_torque_2_result', 'nut_tightening_torque_3', 'nut_tightening_torque_3_result',
#         'free_rotation_torque_3', 'free_rotation_torque_3_result', 'splitpin_and_washer_check_imagefile',
#         'splitpin_and_washer_check_result', 'cap_check_imagefile', 'cap_check_result', 'bung_check_imagefile',
#         'bung_check_result', 'cap_pressed_successfully_check_result', 'ok_notok_result', 'username',
#         'remarks', 'created_on'
#     ]
#     return [dict(zip(headers, record)) for record in records]
#
# # Helper function to parse date (YYYY-MM-DD to DD-MM-YYYY)
# def parse_date(date_str):
#     if not date_str:
#         return None
#     try:
#         dt = datetime.strptime(date_str, "%Y-%m-%d")
#         return dt.strftime("%d-%m-%Y")
#     except ValueError:
#         raise ValueError("Date must be in YYYY-MM-DD format from calendar")
#
# # Method to get unique model names
# def getUniqueModelNames(db_name: str = db_params["database"]) -> List[str]:
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_unique_model_names)
#                 return [row[0] for row in cursor.fetchall()]
#     except Error as e:
#         print(f"Database error: {e}")
#         return []
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         return []
#
# # Method 1
# def getDataByModelName(modelName: str, db_name: str = db_params["database"]) -> str:
#     try:
#         if not modelName:
#             raise ValueError("Model name must be non-empty")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name, (modelName,))
#                 records = cursor.fetchall()
#                 return generate_csv_string(records)
#     except Exception as e:
#         return f"Error: {str(e)}"
#
# # Method 2
# def getDataByModelNameAndDateLimits(modelName: str, startDate: str | None, endDate: str = None, db_name: str = db_params["database"]) -> str:
#     try:
#         if not modelName:
#             raise ValueError("Model name must be non-empty")
#         start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name_and_date_limits, (modelName, start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 return generate_csv_string(records)
#     except Exception as e:
#         return f"Error: {str(e)}"
#
# # Method 3
# def getDataOfTodayByModelNumber(modelName: str, db_name: str = db_params["database"]) -> str:
#     return getDataByModelNameAndDateLimits(modelName=modelName, startDate=None, endDate=None, db_name=db_name)
#
# # Method 4
# def getDataByDateLimits(startDate: str | None, endDate: str = None, db_name: str = db_params["database"]) -> Tuple[str, List[str]]:
#     try:
#         start_dt = parse_date(startDate) if startDate else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(endDate) if endDate else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 # Fetch records
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 csv_string = generate_csv_string(records)
#                 # Fetch unique model names
#                 cursor.execute(select_query_unique_model_names_by_date, (start_dt_db, end_dt_db))
#                 model_names = [row[0] for row in cursor.fetchall()]
#                 return csv_string, model_names
#     except Exception as e:
#         return f"Error: {str(e)}", []
#
# # Method 5
# def getAllDataOfToday(db_name: str = db_params["database"]) -> Tuple[str, List[str]]:
#     return getDataByDateLimits(startDate=None, endDate=None, db_name=db_name)
#
# # Function to find a free port
# def find_free_port() -> int:
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind(('0.0.0.0', 0))  # Bind to port 0 to let OS assign a free port
#         s.listen(1)
#         port = s.getsockname()[1]  # Get the assigned port
#         return port
#
# # Webpage HTML with API tables and Python example
# HTML_TEMPLATE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <title>Hub And Disc Data Query</title>
#     <style>
#         body { font-family: Arial, sans-serif; margin: 20px; }
#         .query-section { margin-bottom: 20px; }
#         button { padding: 10px; margin: 5px; }
#         button:disabled { background-color: #ccc; cursor: not-allowed; }
#         textarea { width: 100%; height: 200px; }
#         select, input[type="date"] { padding: 5px; margin: 5px; width: 200px; }
#         label { margin-right: 10px; }
#         table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
#         th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
#         th.json { background-color: #4682B4; color: white; }
#         th.csv { background-color: #2E8B57; color: white; }
#         tr:nth-child(even) { background-color: #f2f2f2; }
#         .payload { background-color: #e0e0e0; font-family: monospace; }
#         pre { background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-family: monospace; white-space: pre-wrap; }
#         .kw { color: #0000FF; } /* Keywords */
#         .str { color: #008000; } /* Strings */
#         .com { color: #808080; } /* Comments */
#     </style>
#     <script>
#         function downloadCSV(csv, filename) {
#             const blob = newwidgets Blob([csv], { type: 'text/csv' });
#             const url = window.URL.createObjectURL(blob);
#             const a = document.createElement('a');
#             a.href = url;
#             a.download = filename;
#             document.body.appendChild(a);
#             a.click();
#             window.URL.revokeObjectURL(url);
#             document.body.removeChild(a);
#         }
#
#         function query(method, params) {
#             fetch(`http://localhost:80/api/${method}`, {
#                 method: 'POST',
#                 headers: { 'Content-Type': 'application/json' },
#                 body: JSON.stringify(params)
#             })
#             .then(response => response.json())
#             .then(data => {
#                 if (data.csv) {
#                     document.getElementById('result').value = data.csv;
#                     downloadCSV(data.csv, `${method}_${newwidgets Date().toISOString().split('T')[0]}.csv`);
#                 } else {
#                     document.getElementById('result').value = data.error || 'No data';
#                 }
#             })
#             .catch(error => {
#                 document.getElementById('result').value = `Error: ${error}`;
#             });
#         }
#
#         function validateAndQuery(method, selectId = null, startDateId = null, endDateId = null) {
#             const modelSelect = selectId ? document.getElementById(selectId) : null;
#             const modelName = modelSelect ? modelSelect.value : '';
#             const startDate = start ceasartDateId ? document.getElementById(startDateId).value : '';
#             const endDate = endDateId ? document.getElementById(endDateId).value : '';
#
#             // Check for model-based queries
#             if (['by_model_name', 'by_model_name_and_date', 'today_by_model'].includes(method)) {
#                 if (modelSelect && modelSelect.options.length <= 1) {
#                     alert('No model names available in the database. Please populate the database.');
#                     document.getElementById('result').value = 'Error: No model names available';
#                     return;
#                 }
#                 if (!modelName) {
#                     alert('Please select a valid model name.');
#                     document.getElementById('result').value = 'Error: Model name not selected';
#                     return;
#                 }
#             }
#
#             // Send query
#             const params = {};
#             if (modelName) params.modelName = modelName;
#             if (startDate) params.startDate = startDate;
#             if (endDate) params.endDate = endDate;
#             query(method, params);
#         }
#
#         // Initialize button states
#         window.onload = function() {
#             const modelSelects = [
#                 { selectId: 'modelName1', buttonId: 'by_model_name_btn' },
#                 { selectId: 'modelName2', buttonId: 'by_model_name_and_date_btn' },
#                 { selectId: 'modelName3', buttonId: 'today_by_model_btn' }
#             ];
#             modelSelects.forEach(({ selectId, buttonId }) => {
#                 const select = document.getElementById(selectId);
#                 if (select && select.options.length <= 1) {
#                     document.getElementById(buttonId).disabled = true;
#                 }
#             });
#
#             // Disable date-based buttons if no models
#             const dateLimitsModels = {{ date_limits_models | tojson }};
#             const todayModels = {{ today_models | tojson }};
#             if (dateLimitsModels.length === 0) {
#                 document.getElementById('by_date_limits_btn').disabled = true;
#             }
#             if (todayModels.length === 0) {
#                 document.getElementById('all_today_btn').disabled = true;
#             }
#         };
#     </script>
# </head>
# <body>
#     <h2>API Endpoints for JSON Responses</h2>
#     <table>
#         <tr>
#             <th class="json">Method Name</th>
#             <th class="json">API Endpoint</th>
#             <th class="json">Expected Payload</th>
#         </tr>
#         <tr>
#             <td>getUniqueModelNames</td>
#             <td>http://192.168.1.100:80/api/get_unique_model_names/json/</td>
#             <td class="payload">{}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelName</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name/json/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelNameAndDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name_and_date_limits/json/</td>
#             <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getDataOfTodayByModelNumber</td>
#             <td>http://192.168.1.100:80/api/get_data_of_today_by_model_number/json/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_date_limits/json/</td>
#             <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getAllDataOfToday</td>
#             <td>http://192.168.1.100:80/api/get_all_data_of_today/json/</td>
#             <td class="payload">{}</td>
#         </tr>
#     </table>
#
#     <h2>API Endpoints for CSV Responses</h2>
#     <table>
#         <tr>
#             <th class="csv">Method Name</th>
#             <th class="csv">API Endpoint</th>
#             <th class="csv">Expected Payload</th>
#         </tr>
#         <tr>
#             <td>getUniqueModelNames</td>
#             <td>http://192.168.1.100:80/api/get_unique_model_names/csv/</td>
#             <td class="payload">{}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelName</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name/csv/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByModelNameAndDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_model_name_and_date_limits/csv/</td>
#             <td class="payload">{"model_name": "DOST", "start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getDataOfTodayByModelNumber</td>
#             <td>http://192.168.1.100:80/api/get_data_of_today_by_model_number/csv/</td>
#             <td class="payload">{"model_name": "DOST"}</td>
#         </tr>
#         <tr>
#             <td>getDataByDateLimits</td>
#             <td>http://192.168.1.100:80/api/get_data_by_date_limits/csv/</td>
#             <td class="payload">{"start_date": "2025-06-01", "end_date": "2025-06-17"}</td>
#         </tr>
#         <tr>
#             <td>getAllDataOfToday</td>
#             <td>http://192.168.1.100:80/api/get_all_data_of_today/csv/</td>
#             <td class="payload">{}</td>
#         </tr>
#     </table>
#
#     <h2>Python Example for API Call</h2>
#     <pre>
# <span class="kw">import</span> requests
#
# <span class="kw">def</span> get_data_by_model_name(model_name=<span class="str">"DOST"</span>):
#     url = <span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>
#     payload = {<span class="str">"model_name"</span>: model_name}
#     <span class="kw">try</span>:
#         response = requests.post(url, json=payload, timeout=10)
#         response.raise_for_status()  <span class="com"># Raises exception for 4xx/5xx errors</span>
#         <span class="kw">return</span> response.json()  <span class="com"># Returns {"data": [{...}, ...]} or {"error": "..."}</span>
#     <span class="kw">except</span> requests.RequestException <span class="kw">as</span> e:
#         <span class="kw">return</span> {<span class="str">"error"</span>: <span class="str">f"Request failed: {str(e)}"</span>}
#
# <span class="com"># Example usage</span>
# result = get_data_by_model_name(<span class="str">"DOST"</span>)
# print(result)
#     </pre>
#
#     <h2>Java Example for API Call</h2>
#     <pre>
# <span class="kw">import</span> java.net.http.HttpClient;
# <span class="kw">import</span> java.net.http.HttpRequest;
# <span class="kw">import</span> java.net.http.HttpResponse;
# <span class="kw">import</span> java.net.URI;
# <span class="kw">import</span> java.time.Duration;
# <span class="kw">import</span> java.util.Map;
#
# <span class="kw">public class</span> ApiClient {
#     <span class="kw">public static</span> String getDataByModelName(String modelName) {
#         HttpClient client = HttpClient.<span class="kw">newBuilder</span>()
#             .connectTimeout(Duration.<span class="kw">ofSeconds</span>(10))
#             .build();
#         String jsonPayload = <span class="str">"{\"model_name\":\""</span> + modelName + <span class="str">"\"}"</span>;
#         HttpRequest request = HttpRequest.<span class="kw">newBuilder</span>()
#             .uri(URI.<span class="kw">create</span>(<span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>))
#             .header(<span class="str">"Content-Type"</span>, <span class="str">"application/json"</span>)
#             .POST(HttpRequest.BodyPublishers.<span class="kw">ofString</span>(jsonPayload))
#             .build();
#         <span class="kw">try</span> {
#             HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.<span class="kw">ofString</span>());
#             <span class="kw">if</span> (response.statusCode() >= 400) {
#                 <span class="kw">return</span> <span class="str">"{\"error\":\"HTTP error code: "</span> + response.statusCode() + <span class="str">"\"}"</span>;
#             }
#             <span class="kw">return</span> response.body(); <span class="com">// Returns JSON string {"data": [{...}, ...]} or {"error": "..."}</span>
#         } <span class="kw">catch</span> (Exception e) {
#             <span class="kw">return</span> <span class="str">"{\"error\":\"Request failed: "</span> + e.getMessage() + <span class="str">"\"}"</span>;
#         }
#     }
#
#     <span class="kw">public static void</span> main(String[] args) {
#         String result = getDataByModelName(<span class="str">"DOST"</span>);
#         System.<span class="kw">out</span>.println(result);
#     }
# }
#     </pre>
#
#     <h2>.NET Example for API Call</h2>
#     <pre>
# <span class="kw">using</span> System;
# <span class="kw">using</span> System.Net.Http;
# <span class="kw">using</span> System.Text;
# <span class="kw">using</span> System.Threading.Tasks;
#
# <span class="kw">public class</span> ApiClient
# {
#     <span class="kw">private static readonly</span> HttpClient client = <span class="kw">newwidgets</span> HttpClient();
#
#     <span class="kw">public static async</span> Task<string> GetDataByModelName(<span class="kw">string</span> modelName)
#     {
#         client.Timeout = TimeSpan.<span class="kw">FromSeconds</span>(10);
#         <span class="kw">var</span> payload = <span class="str">$"{\"model_name\":\"{modelName}\"}"</span>;
#         <span class="kw">var</span> content = <span class="kw">newwidgets</span> StringContent(payload, Encoding.UTF8, <span class="str">"application/json"</span>);
#         <span class="kw">try</span>
#         {
#             <span class="kw">var</span> response = <span class="kw">await</span> client.PostAsync(<span class="str">"http://192.168.1.100:80/api/get_data_by_model_name/json/"</span>, content);
#             response.EnsureSuccessStatusCode();
#             <span class="kw">return await</span> response.Content.ReadAsStringAsync(); <span class="com">// Returns JSON string {"data": [{...}, ...]} or {"error": "..."}</span>
#         }
#         <span class="kw">catch</span> (HttpRequestException e)
#         {
#             <span class="kw">return</span> <span class="str">$"{\"error\":\"Request failed: {e.Message}\"}"</span>;
#         }
#     }
#
#     <span class="kw">public static async</span> Task Main(<span class="kw">string</span>[] args)
#     {
#         <span class="kw">string</span> result = <span class="kw">await</span> GetDataByModelName(<span class="str">"DOST"</span>);
#         Console.WriteLine(result);
#     }
# }
#     </pre>
#
#     <h1>Hub And Disc Data Query</h1>
#     <div class="query-section">
#         <h3>Get Data by Model Name</h3>
#         <label for="modelName1">Model Name:</label>
#         <select id="modelName1">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <button id="by_model_name_btn" onclick="validateAndQuery('by_model_name', 'modelName1')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3>Get Data by Model Name and Date Limits</h3>
#         <label for="modelName2">Model Name:</label>
#         <select id="modelName2">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <label for="startDate">Start Date:</label>
#         <input type="date" id="startDate">
#         <label for="endDate">End Date:</label>
#         <input type="date" id="endDate">
#         <button id="by_model_name_and_date_btn" onclick="validateAndQuery('by_model_name_and_date', 'modelName2', 'startDate', 'endDate')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3>Get Today's Data by Model Number</h3>
#         <label for="modelName3">Model Name:</label>
#         <select id="modelName3">
#             <option value="">Select Model</option>
#             {% for model in model_names %}
#             <option value="{{ model }}">{{ model }}</option>
#             {% endfor %}
#         </select>
#         <button id="today_by_model_btn" onclick="validateAndQuery('today_by_model', 'modelName3')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3>Get Data by Date Limits</h3>
#         <label for="startDate2">Start Date:</label>
#         <input type="date" id="startDate2">
#         <label for="endDate2">End Date:</label>
#         <input type="date" id="endDate2">
#         <button id="by_date_limits_btn" onclick="validateAndQuery('by_date_limits', null, 'startDate2', 'endDate2')">Run</button>
#     </div>
#     <div class="query-section">
#         <h3>Get All Data of Today</h3>
#         <button id="all_today_btn" onclick="validateAndQuery('all_today')">Run</button>
#     </div>
#     <h3>Result</h3>
#     <textarea id="result" readonly></textarea>
# </body>
# </html>
# """
#
# # Existing Routes (for webpage)
# @app.route('/')
# def index():
#     model_names = getUniqueModelNames()
#     # Check model names for date-based queries
#     _, date_limits_models = getDataByDateLimits(startDate=None, endDate=None)  # Default to today for initialization
#     _, today_models = getAllDataOfToday()
#     return render_template_string(HTML_TEMPLATE, model_names=model_names, date_limits_models=date_limits_models, today_models=today_models)
#
# @app.route('/api/by_model_name', methods=['POST'])
# def api_by_model_name():
#     data = request.get_json()
#     model_name = data.get('modelName')
#     try:
#         csv_string = getDataByModelName(model_name)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/by_model_name_and_date', methods=['POST'])
# def api_by_model_name_and_date():
#     data = request.get_json()
#     model_name = data.get('modelName')
#     start_date = data.get('startDate')
#     end_date = data.get('endDate')
#     try:
#         csv_string = getDataByModelNameAndDateLimits(model_name, start_date, end_date)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/today_by_model', methods=['POST'])
# def api_by_model():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     try:
#         csv_string = getDataOfTodayByModelNumber(model_name)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/by_date_limits', methods=['POST'])
# def api_by_date_limits():
#     data = request.get_json()
#     start_date = data.get('startDate')
#     end_date = data.get('endDate')
#     try:
#         csv_string, _ = getDataByDateLimits(start_date, end_date)
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# @app.route('/api/all_today', methods=['POST'])
# def api_all_today():
#     try:
#         csv_string, _ = getAllDataOfToday()
#         return jsonify({'csv': csv_string})
#     except Exception as e:
#         return jsonify({'error': str(e)})
#
# # Updated Routes (for external API access with format)
# @app.route('/api/get_unique_model_names/<format>/', methods=['POST'])
# def api_get_unique_model_names(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         model_names = getUniqueModelNames(db_name)
#         if format == 'json':
#             return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
#         else:  # csv
#             csv_string = generate_csv_string_for_models(model_names)
#             return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_model_name/<format>/', methods=['POST'])
# def api_get_data_by_model_name(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name, (model_name,))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     csv_string = generate_csv_string(records)
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_model_name_and_date_limits/<format>/', methods=['POST'])
# def api_get_data_by_model_name_and_date_limits(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         start_dt = parse_date(start_date) if start_date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(end_date) if end_date else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_by_model_name_and_date_limits, (model_name, start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     csv_string = generate_csv_string(records)
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_of_today_by_model_number/<format>/', methods=['POST'])
# def api_get_data_of_today_by_model_number(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#                 end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
#                 cursor.execute(select_query_by_model_name_and_date_limits, (model_name, start_dt, end_dt))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_data_by_date_limits/<format>/', methods=['POST'])
# def api_get_data_by_date_limits(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json()
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         start_dt = parse_date(start_date) if start_date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%d-%m-%Y")
#         end_dt = parse_date(end_date) if end_date else datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999).strftime("%d-%m-%Y")
#         start_dt_db = datetime.strptime(start_dt, "%d-%m-%Y")
#         end_dt_db = datetime.strptime(end_dt, "%d-%m-%Y")
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt_db, end_dt_db))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# @app.route('/api/get_all_data_of_today/<format>/', methods=['POST'])
# def api_get_all_data_of_today(format):
#     if format not in ['json', 'csv']:
#         return jsonify({'error': 'Invalid format. Use /json/ or /csv/'}), 400
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getAllDataOfToday(db_name=db_name)
#         if csv_string.startswith("Error"):
#             raise Exception(csv_string)
#         start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
#         end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(select_query_from_start_date_to_end_date, (start_dt, end_dt))
#                 records = cursor.fetchall()
#                 if format == 'json':
#                     json_data = records_to_json(records)
#                     return jsonify({'data': json_data}), 200, {'Content-Type': 'application/json'}
#                 else:  # csv
#                     return csv_string, 200, {'Content-Type': 'text/csv'}
#     except Exception as e:
#         if format == 'json':
#             return jsonify({'error': str(e)}), 500
#         else:
#             return f"Error: {str(e)}", 500, {'Content-Type': 'text/plain'}
#
# # Backward-compatible routes (default to previous behavior)
# @app.route('/api/get_unique_model_names', methods=['POST'])
# def api_get_unique_model_names_default():
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         model_names = getUniqueModelNames(db_name)
#         return jsonify({'model_names': model_names}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_model_name', methods=['POST'])
# def api_get_data_by_model_name_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataByModelName(modelName=model_name, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_model_name_and_date_limits', methods=['POST'])
# def api_get_data_by_model_name_and_date_limits_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataByModelNameAndDateLimits(modelName=model_name, startDate=start_date, endDate=end_date, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_of_today_by_model_number', methods=['POST'])
# def api_get_data_of_today_by_model_number_default():
#     data = request.get_json()
#     model_name = data.get('model_name')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string = getDataOfTodayByModelNumber(modelName=model_name, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_data_by_date_limits', methods=['POST'])
# def api_get_data_by_date_limits_default():
#     data = request.get_json()
#     start_date = data.get('start_date')
#     end_date = data.get('end_date')
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getDataByDateLimits(startDate=start_date, endDate=end_date, db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# @app.route('/api/get_all_data_of_today', methods=['POST'])
# def api_get_all_data_of_today_default():
#     data = request.get_json() or {}
#     db_name = data.get('db_name', db_params["database"])
#     try:
#         csv_string, _ = getAllDataOfToday(db_name=db_name)
#         return jsonify({'data': csv_string}), 200, {'Content-Type': 'application/json'}
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#
# def startWebService():
#     try:
#         desired_port = 80
#         try:
#             app.run(host='0.0.0.0', port=desired_port, debug=False)
#             printBoldBlue(f"*****************")
#             printBlue(f"Started Hub and Disc Web Service")
#             printBoldBlue(f"*****************")
#         except OSError as e:
#             print(f"Port {desired_port} is in use, trying a free port")
#             free_port = find_free_port()
#             print(f"Starting server on port {free_port}")
#             app.run(host='0.0.0.0', port=free_port, debug=False)
#     except Exception as e:
#         print(f"Failed to start server: {e}")
