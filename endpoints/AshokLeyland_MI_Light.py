import http.server
import socketserver
import json
import socket as parentclasssocket
from socket import socket as mainsocket
from urllib.parse import urlparse, parse_qs

import pandas as pd
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
import numpy as np
from html import escape

# Custom JSON encoder to handle NumPy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super().default(obj)

# Database configuration
db_params = {
    "host": "127.0.0.1",
    "database": "auto_company_production",
    "user": "postgres",
    "password": "postgres",
    "port": "5432"
}

# SQL Queries
base_query = """
    SELECT created_on, model_name, nut_tightening_torque_1, free_rotation_torque_1,
           nut_tightening_torque_2, free_rotation_torque_2,
           nut_tightening_torque_3, free_rotation_torque_3,
           remarks
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    WHERE created_on >= %s AND created_on <= %s
"""

unique_models_query = """
    SELECT DISTINCT model_name
    FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
    ORDER BY model_name
"""

# Helper function to fetch unique model names
def fetch_unique_models():
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(unique_models_query)
                models = [row[0] for row in cursor.fetchall() if row[0]]
                if not models:
                    print("Warning: No models found in the database. Using 'ALL MODELS' only.")
                else:
                    # print(f"Fetched models: {models}")
                    pass
                return ['ALL MODELS'] + models
    except Error as e:
        print(f"Database error in fetch_unique_models: {e}")
        return ['ALL MODELS']

# Helper function to fetch data
def fetch_data(start_date, end_date):
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(base_query, (start_date, end_date))
                records = cursor.fetchall()
                df = pd.DataFrame(records, columns=[
                    'created_on', 'model_name', 'nut_tightening_torque_1', 'free_rotation_torque_1',
                    'nut_tightening_torque_2', 'free_rotation_torque_2',
                    'nut_tightening_torque_3', 'free_rotation_torque_3', 'remarks'
                ])
                # print(f"Fetched {len(df)} records from {start_date} to {end_date}")
                return df
    except Error as e:
        print(f"Database error in fetch_data: {e}")
        return pd.DataFrame()

# Helper function to calculate date ranges
def get_date_ranges():
    now = datetime.now()
    return {
        '7_days': (now - timedelta(days=7), now),
        '30_days': (now - timedelta(days=30), now),
        '90_days': (now - timedelta(days=90), now),
        '365_days': (now - timedelta(days=365), now),
        'ytd': (datetime(now.year, 1, 1), now),
        'qtd': (now - relativedelta(months=(now.month - 1) % 3), now),
        'mtd': (datetime(now.year, now.month, 1), now)
    }

# Helper function to calculate components per day
def components_per_day(df, model_name, period):
    # print(f"components_per_day: model={model_name}, period={period}, input df rows={len(df)}")
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    start, end = get_date_ranges()[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    # print(f"components_per_day: filtered df rows={len(df_period)}")
    if df_period.empty:
        fig = go.Figure().update_layout(
            title=f'Components per Day ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            xaxis_title="Date",
            yaxis_title="Component Count",
            plot_bgcolor='rgba(144, 238, 144, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12)
        )
        # print("components_per_day: returning empty figure")
        return fig.to_dict()
    df_grouped = df_period.groupby(df_period['created_on'].dt.date).size().reset_index(name='count')
    # print(f"components_per_day: grouped data points={len(df_grouped)}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['created_on'].astype(str).tolist(),
        y=df_grouped['count'].tolist(),
        mode='lines+markers',
        line=dict(color='#006400', width=2),
        marker=dict(size=8, color='#006400')
    ))
    fig.update_layout(
        title=f'Components per Day ({period.replace("_", " ").title()} - {title_suffix})',
        template='plotly_white',
        xaxis_title="Date",
        yaxis_title="Component Count",
        plot_bgcolor='rgba(144, 238, 144, 0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    # print("components_per_day: returning populated figure")
    return fig.to_dict()

# Helper function to calculate components per week
def components_per_week(df, model_name, period):
    # print(f"components_per_week: model={model_name}, period={period}, input df rows={len(df)}")
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    week_ranges = {
        '12_weeks': (datetime.now() - timedelta(weeks=12), datetime.now()),
        '52_weeks': (datetime.now() - timedelta(weeks=52), datetime.now()),
        'ytd': (datetime(datetime.now().year, 1, 1), datetime.now()),
        'qtd': (datetime.now() - relativedelta(months=(datetime.now().month - 1) % 3), datetime.now()),
        'mtd': (datetime(datetime.now().year, datetime.now().month, 1), datetime.now())
    }
    start, end = week_ranges[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    # print(f"components_per_week: filtered df rows={len(df_period)}")
    if df_period.empty:
        fig = go.Figure().update_layout(
            title=f'Components per Week ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            xaxis_title="Week Starting",
            yaxis_title="Component Count",
            plot_bgcolor='rgba(144, 238, 144, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12)
        )
        # print("components_per_week: returning empty figure")
        return fig.to_dict()
    df_grouped = df_period.groupby(pd.Grouper(key='created_on', freq='W-MON')).size().reset_index(name='count')
    # print(f"components_per_week: grouped data points={len(df_grouped)}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['created_on'].astype(str).tolist(),
        y=df_grouped['count'].tolist(),
        mode='lines+markers',
        line=dict(color='#006400', width=2),
        marker=dict(size=8, color='#006400')
    ))
    fig.update_layout(
        title=f'Components per Week ({period.replace("_", " ").title()} - {title_suffix})',
        template='plotly_white',
        xaxis_title="Week Starting",
        yaxis_title="Component Count",
        plot_bgcolor='rgba(144, 238, 144, 0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    # print("components_per_week: returning populated figure")
    return fig.to_dict()

# Helper function for torque distributions
def torque_distribution(df, column, model_name, period):
    # print(f"torque_distribution: column={column}, model={model_name}, period={period}, input df rows={len(df)}")
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    torque_ranges = {
        '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
        '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
        '365_days': (datetime.now() - timedelta(days=365), datetime.now())
    }
    start, end = torque_ranges[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df[column].notnull())]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    # print(f"torque_distribution: filtered df rows={len(df_period)}")
    if df_period.empty or df_period[column].dropna().empty:
        fig = go.Figure().update_layout(
            title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            xaxis_title="Torque Value",
            yaxis_title="Density",
            plot_bgcolor='rgba(173, 216, 230, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12)
        )
        # print("torque_distribution: returning empty figure")
        return fig.to_dict()
    data = df_period[column].dropna().tolist()
    # print(f"torque_distribution: data points={len(data)}")
    # Calculate histogram bins with 0.05 bucket size
    min_val = min(data)
    max_val = max(data)
    bin_size = 0.05
    bins = np.arange(np.floor(min_val / bin_size) * bin_size, np.ceil(max_val / bin_size) * bin_size + bin_size, bin_size)
    hist, bin_edges = np.histogram(data, bins=bins, density=True)
    # Log histogram for verification
    # print(f"torque_distribution: {column} histogram bins={bin_edges.tolist()}")
    # print(f"torque_distribution: {column} histogram counts (normalized)={hist.tolist()}")
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=data,
        xbins=dict(start=min_val, end=max_val + bin_size, size=bin_size),
        histnorm='probability density',
        marker=dict(
            color='rgba(173, 216, 230, 0.5)',
            line=dict(color='#00008B', width=2)
        )
    ))
    fig.update_layout(
        title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").title()} - {title_suffix})',
        template='plotly_white',
        xaxis_title="Torque Value",
        yaxis_title="Density",
        plot_bgcolor='rgba(173, 216, 230, 0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    # print("torque_distribution: returning populated figure")
    return fig.to_dict()

# Helper function for reworked components
def reworked_components(df, model_name, period):
    # print(f"reworked_components: model={model_name}, period={period}, input df rows={len(df)}")
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    period_ranges = {
        '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
        '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
        '365_days': (datetime.now() - timedelta(days=365), datetime.now())
    }
    start, end = period_ranges[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    df_reworked = df_period[df_period['remarks'].str.contains('DUPLICATE', case=False, na=False)]
    # print(f"reworked_components: filtered df rows={len(df_reworked)}")
    if df_reworked.empty:
        fig = go.Figure().update_layout(
            title=f'Reworked Components per Day ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            xaxis_title="Date",
            yaxis_title="Reworked Component Count",
            plot_bgcolor='rgba(144, 238, 144, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12)
        )
        # print("reworked_components: returning empty figure")
        return fig.to_dict()
    df_grouped = df_reworked.groupby(df_reworked['created_on'].dt.date).size().reset_index(name='count')
    # print(f"reworked_components: grouped data points={len(df_grouped)}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['created_on'].astype(str).tolist(),
        y=df_grouped['count'].tolist(),
        mode='lines+markers',
        line=dict(color='#006400', width=2),
        marker=dict(size=8, color='#006400')
    ))
    fig.update_layout(
        title=f'Reworked Components per Day ({period.replace("_", " ").title()} - {title_suffix})',
        template='plotly_white',
        xaxis_title="Date",
        yaxis_title="Reworked Component Count",
        plot_bgcolor='rgba(144, 238, 144, 0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    # print("reworked_components: returning populated figure")
    return fig.to_dict()

# HTML template with escaped curly braces in CSS
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hub and Disc Assembly Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ background: linear-gradient(to bottom, #f8f9fa, #e9ecef); }}
        .card {{ border: none; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .nav-tabs .nav-link {{ border-radius: 0.25rem; }}
        .nav-tabs .nav-link.active {{ background-color: #007bff; color: white; }}
        .description {{ color: #6c757d; font-size: 0.9rem; margin-top: 1rem; }}
        .dropdown-container {{ margin-bottom: 1.5rem; }}
        .chart-container {{ width: 100%; height: 400px; box-sizing: border-box; clear: both; display: block; }}
        .card-body {{ padding: 1rem; }}
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="row mb-4 align-items-center">
            <div class="col-auto">
                <h1 class="text-primary mb-0" style="font-weight: 700; font-size: 2.5rem;">
                    <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/bar-chart-line.svg" width="32" class="me-2" alt="Chart Icon">
                    Hub and Disc Assembly Dashboard
                </h1>
            </div>
            <div class="col-auto ms-auto">
                <div class="bg-primary text-white rounded-pill px-3 py-2 shadow-sm" style="font-size: 0.9rem; font-weight: 500;">
                    Made by CosTheta Technologies
                </div>
            </div>
        </div>
        <div class="card mb-4">
            <div class="card-body">
                <label class="form-label fw-semibold mb-2">
                    <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/gear-fill.svg" width="20" class="me-2" alt="Gear Icon">
                    Select Model Name
                </label>
                <select id="model-dropdown" class="form-select mb-3" style="max-width: 400px;">
                    <!-- MODEL_OPTIONS_PLACEHOLDER -->
                </select>
            </div>
        </div>
        <ul class="nav nav-tabs" id="tabs" role="tablist">
            <li class="nav-item">
                <a class="nav-link active" id="day-tab" data-bs-toggle="tab" href="#day" role="tab">Components per Day</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="week-tab" data-bs-toggle="tab" href="#week" role="tab">Components per Week</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque1-tightening-tab" data-bs-toggle="tab" href="#torque1-tightening" role="tab">Nut Tightening Torque 1</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque1-rotation-tab" data-bs-toggle="tab" href="#torque1-rotation" role="tab">Free Rotation Torque 1</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque2-tightening-tab" data-bs-toggle="tab" href="#torque2-tightening" role="tab">Nut Tightening Torque 2</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque2-rotation-tab" data-bs-toggle="tab" href="#torque2-rotation" role="tab">Free Rotation Torque 2</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque3-tightening-tab" data-bs-toggle="tab" href="#torque3-tightening" role="tab">Nut Tightening Torque 3</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="torque3-rotation-tab" data-bs-toggle="tab" href="#torque3-rotation" role="tab">Free Rotation Torque 3</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" id="reworked-tab" data-bs-toggle="tab" href="#reworked" role="tab">Reworked Components</a>
            </li>
        </ul>
        <div class="tab-content mt-3">
            <div class="tab-pane fade show active" id="day" role="tabpanel">
                <div class="card">
                    <div class="card-header bg-light">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/calendar-day.svg" width="20" class="me-2" alt="Calendar Day">
                        <span class="fw-semibold">Components per Day</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="day-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="day-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="7_days">Last 7 Days</option>
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                    <option value="ytd">Year-to-Date</option>
                                    <option value="qtd">Quarter-to-Date</option>
                                    <option value="mtd">Month-to-Date</option>
                                </select>
                            </div>
                        </div>
                        <div id="components-day" class="chart-container"></div>
                        <p class="description">Components processed per day for the selected model or all models.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="week" role="tabpanel">
                <div class="card">
                    <div class="card-header bg-light">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/calendar-week.svg" width="20" class="me-2" alt="Calendar Week">
                        <span class="fw-semibold">Components per Week</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="week-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="week-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="12_weeks">Last 12 Weeks</option>
                                    <option value="52_weeks">Last 52 Weeks</option>
                                    <option value="ytd">Year-to-Date</option>
                                    <option value="qtd">Quarter-to-Date</option>
                                    <option value="mtd">Month-to-Date</option>
                                </select>
                            </div>
                        </div>
                        <div id="components-week" class="chart-container"></div>
                        <p class="description">Components processed per week for the selected model or all models.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque1-tightening" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/wrench.svg" width="20" class="me-2" alt="Wrench">
                        <span class="fw-semibold">Nut Tightening Torque 1</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque1-tightening-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque1-tightening-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque1-tightening-chart" class="chart-container"></div>
                        <p class="description">Histogram of Nut Tightening Torque 1 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque1-rotation" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/arrow-repeat.svg" width="20" class="me-2" alt="Arrow Repeat">
                        <span class="fw-semibold">Free Rotation Torque 1</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque1-rotation-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque1-rotation-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque1-rotation-chart" class="chart-container"></div>
                        <p class="description">Histogram of Free Rotation Torque 1 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque2-tightening" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/wrench.svg" width="20" class="me-2" alt="Wrench">
                        <span class="fw-semibold">Nut Tightening Torque 2</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque2-tightening-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque2-tightening-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque2-tightening-chart" class="chart-container"></div>
                        <p class="description">Histogram of Nut Tightening Torque 2 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque2-rotation" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/arrow-repeat.svg" width="20" class="me-2" alt="Arrow Repeat">
                        <span class="fw-semibold">Free Rotation Torque 2</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque2-rotation-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque2-rotation-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque2-rotation-chart" class="chart-container"></div>
                        <p class="description">Histogram of Free Rotation Torque 2 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque3-tightening" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/wrench.svg" width="20" class="me-2" alt="Wrench">
                        <span class="fw-semibold">Nut Tightening Torque 3</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque3-tightening-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque3-tightening-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque3-tightening-chart" class="chart-container"></div>
                        <p class="description">Histogram of Nut Tightening Torque 3 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="torque3-rotation" role="tabpanel">
                <div class="card">
                    <div class="card-header" style="background-color: #ADD8E6;">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/arrow-repeat.svg" width="20" class="me-2" alt="Arrow Repeat">
                        <span class="fw-semibold">Free Rotation Torque 3</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="torque3-rotation-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="torque3-rotation-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="torque3-rotation-chart" class="chart-container"></div>
                        <p class="description">Histogram of Free Rotation Torque 3 values with 0.05 bin size.</p>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="reworked" role="tabpanel">
                <div class="card">
                    <div class="card-header bg-light">
                        <img src="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/arrow-counterclockwise.svg" width="20" class="me-2" alt="Arrow Counterclockwise">
                        <span class="fw-semibold">Reworked Components</span>
                    </div>
                    <div class="card-body">
                        <div class="row dropdown-container">
                            <div class="col-auto">
                                <label for="reworked-period-dropdown" class="form-label fw-semibold">Select Period</label>
                                <select id="reworked-period-dropdown" class="form-select" style="max-width: 300px;">
                                    <option value="30_days">Last 30 Days</option>
                                    <option value="90_days">Last 90 Days</option>
                                    <option value="365_days">Last 365 Days</option>
                                </select>
                            </div>
                        </div>
                        <div id="reworked-components" class="chart-container"></div>
                        <p class="description">Reworked components marked as 'DUPLICATE' in remarks, shown per day.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        function fetchGraphData() {
            const model = document.getElementById('model-dropdown').value || 'ALL MODELS';
            const dayPeriod = document.getElementById('day-period-dropdown').value;
            const weekPeriod = document.getElementById('week-period-dropdown').value;
            const torque1TighteningPeriod = document.getElementById('torque1-tightening-period-dropdown').value;
            const torque1RotationPeriod = document.getElementById('torque1-rotation-period-dropdown').value;
            const torque2TighteningPeriod = document.getElementById('torque2-tightening-period-dropdown').value;
            const torque2RotationPeriod = document.getElementById('torque2-rotation-period-dropdown').value;
            const torque3TighteningPeriod = document.getElementById('torque3-tightening-period-dropdown').value;
            const torque3RotationPeriod = document.getElementById('torque3-rotation-period-dropdown').value;
            const reworkedPeriod = document.getElementById('reworked-period-dropdown').value;

            fetch('/data?model=' + encodeURIComponent(model) +
                '&day_period=' + encodeURIComponent(dayPeriod) +
                '&week_period=' + encodeURIComponent(weekPeriod) +
                '&torque1_tightening_period=' + encodeURIComponent(torque1TighteningPeriod) +
                '&torque1_rotation_period=' + encodeURIComponent(torque1RotationPeriod) +
                '&torque2_tightening_period=' + encodeURIComponent(torque2TighteningPeriod) +
                '&torque2_rotation_period=' + encodeURIComponent(torque2RotationPeriod) +
                '&torque3_tightening_period=' + encodeURIComponent(torque3TighteningPeriod) +
                '&torque3_rotation_period=' + encodeURIComponent(torque3RotationPeriod) +
                '&reworked_period=' + encodeURIComponent(reworkedPeriod))
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok: ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    const config = { responsive: true, displayModeBar: true };
                    try {
                        Plotly.newPlot('components-day', data.components_day.data, data.components_day.layout, config);
                        console.log('Rendered components-day');
                    } catch (e) {
                        console.error('Error rendering components-day:', e);
                    }
                    try {
                        Plotly.newPlot('components-week', data.components_week.data, data.components_week.layout, config);
                        console.log('Rendered components-week');
                    } catch (e) {
                        console.error('Error rendering components-week:', e);
                    }
                    try {
                        Plotly.newPlot('torque1-tightening-chart', data.torque1_tightening.data, data.torque1_tightening.layout, config);
                        console.log('Rendered torque1-tightening-chart');
                    } catch (e) {
                        console.error('Error rendering torque1-tightening-chart:', e);
                    }
                    try {
                        Plotly.newPlot('torque1-rotation-chart', data.torque1_rotation.data, data.torque1_rotation.layout, config);
                        console.log('Rendered torque1-rotation-chart');
                    } catch (e) {
                        console.error('Error rendering torque1-rotation-chart:', e);
                    }
                    try {
                        Plotly.newPlot('torque2-tightening-chart', data.torque2_tightening.data, data.torque2_tightening.layout, config);
                        console.log('Rendered torque2-tightening-chart');
                    } catch (e) {
                        console.error('Error rendering torque2-tightening-chart:', e);
                    }
                    try {
                        Plotly.newPlot('torque2-rotation-chart', data.torque2_rotation.data, data.torque2_rotation.layout, config);
                        console.log('Rendered torque2-rotation-chart');
                    } catch (e) {
                        console.error('Error rendering torque2-rotation-chart:', e);
                    }
                    try {
                        Plotly.newPlot('torque3-tightening-chart', data.torque3_tightening.data, data.torque3_tightening.layout, config);
                        console.log('Rendered torque3-tightening-chart');
                    } catch (e) {
                        console.error('Error rendering torque3-tightening-chart:', e);
                    }
                    try {
                        Plotly.newPlot('torque3-rotation-chart', data.torque3_rotation.data, data.torque3_rotation.layout, config);
                        console.log('Rendered torque3-rotation-chart');
                    } catch (e) {
                        console.error('Error rendering torque3-rotation-chart:', e);
                    }
                    try {
                        Plotly.newPlot('reworked-components', data.reworked_components.data, data.reworked_components.layout, config);
                        console.log('Rendered reworked-components');
                    } catch (e) {
                        console.error('Error rendering reworked-components:', e);
                    }
                })
                .then(() => console.log('Charts rendered successfully'))
                .catch(error => console.error('Error fetching data:', error));
        }

        // Add event listeners for dropdown changes
        document.getElementById('model-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('day-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('week-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque1-tightening-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque1-rotation-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque2-tightening-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque2-rotation-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque3-tightening-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('torque3-rotation-period-dropdown').addEventListener('change', fetchGraphData);
        document.getElementById('reworked-period-dropdown').addEventListener('change', fetchGraphData);

        // Add event listeners for tab changes to simulate dropdown click
        document.getElementById('day-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('day-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on day-period-dropdown');
        });
        document.getElementById('week-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('week-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on week-period-dropdown');
        });
        document.getElementById('torque1-tightening-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque1-tightening-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque1-tightening-period-dropdown');
        });
        document.getElementById('torque1-rotation-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque1-rotation-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque1-rotation-period-dropdown');
        });
        document.getElementById('torque2-tightening-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque2-tightening-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque2-tightening-period-dropdown');
        });
        document.getElementById('torque2-rotation-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque2-rotation-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque2-rotation-period-dropdown');
        });
        document.getElementById('torque3-tightening-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque3-tightening-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque3-tightening-period-dropdown');
        });
        document.getElementById('torque3-rotation-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('torque3-rotation-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on torque3-rotation-period-dropdown');
        });
        document.getElementById('reworked-tab').addEventListener('shown.bs.tab', function () {
            document.getElementById('reworked-period-dropdown').dispatchEvent(new Event('change'));
            console.log('Simulated click on reworked-period-dropdown');
        });

        // Initial data fetch
        fetchGraphData();

        // Auto-refresh every minute
        setInterval(fetchGraphData, 60 * 1000);
    </script>
</body>
</html>
"""

# HTTP Request Handler
class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == '/':
            try:
                models = fetch_unique_models()
                # Escape model names to prevent HTML injection
                model_options = ''.join([f'<option value="{escape(model)}">{escape(model)}</option>' for model in models])
                # print(f"model_options: {model_options}")
                # Use string concatenation to avoid str.format() issues
                html_content = HTML_TEMPLATE.replace('<!-- MODEL_OPTIONS_PLACEHOLDER -->', model_options)
                # print(f"html_content first 100 chars: {html_content[:100]}")
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
            except Exception as e:
                print(f"Error generating HTML response: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Internal Server Error: {str(e)}".encode('utf-8'))
        elif path == '/data':
            try:
                model_name = query.get('model', ['ALL MODELS'])[0]
                day_period = query.get('day_period', ['7_days'])[0]
                week_period = query.get('week_period', ['12_weeks'])[0]
                torque1_tightening_period = query.get('torque1_tightening_period', ['30_days'])[0]
                torque1_rotation_period = query.get('torque1_rotation_period', ['30_days'])[0]
                torque2_tightening_period = query.get('torque2_tightening_period', ['30_days'])[0]
                torque2_rotation_period = query.get('torque2_rotation_period', ['30_days'])[0]
                torque3_tightening_period = query.get('torque3_tightening_period', ['30_days'])[0]
                torque3_rotation_period = query.get('torque3_rotation_period', ['30_days'])[0]
                reworked_period = query.get('reworked_period', ['30_days'])[0]

                # print(f"/data: model={model_name}, day_period={day_period}, week_period={week_period}, reworked_period={reworked_period}")
                earliest_date = datetime.now() - timedelta(days=365)
                df = fetch_data(earliest_date, datetime.now())
                # print(f"/data: fetched df rows={len(df)}")

                data = {
                    'components_day': components_per_day(df, model_name, day_period),
                    'components_week': components_per_week(df, model_name, week_period),
                    'torque1_tightening': torque_distribution(df, 'nut_tightening_torque_1', model_name, torque1_tightening_period),
                    'torque1_rotation': torque_distribution(df, 'free_rotation_torque_1', model_name, torque1_rotation_period),
                    'torque2_tightening': torque_distribution(df, 'nut_tightening_torque_2', model_name, torque2_tightening_period),
                    'torque2_rotation': torque_distribution(df, 'free_rotation_torque_2', model_name, torque2_rotation_period),
                    'torque3_tightening': torque_distribution(df, 'nut_tightening_torque_3', model_name, torque3_tightening_period),
                    'torque3_rotation': torque_distribution(df, 'free_rotation_torque_3', model_name, torque3_rotation_period),
                    'reworked_components': reworked_components(df, model_name, reworked_period)
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data, cls=NumpyEncoder).encode('utf-8'))
            except Exception as e:
                print(f"Error generating JSON data: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Internal Server Error: {str(e)}".encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')

# Function to find a free port
def find_free_port():
    # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    with mainsocket(parentclasssocket.AF_INET, parentclasssocket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        s.listen(1)
        port = s.getsockname()[1]
        print(f"Found free port: {port}")
        return port

# Start the server
def start_server():
    desired_port = 8050
    try:
        server = socketserver.TCPServer(('0.0.0.0', desired_port), DashboardHandler)
        print(f"Started server on http://127.0.0.1:{desired_port}/")
        server.serve_forever()
    except OSError as e:
        print(f"Port {desired_port} is in use: {e}")
        free_port = find_free_port()
        server = socketserver.TCPServer(('0.0.0.0', free_port), DashboardHandler)
        print(f"Started MI server on http://127.0.0.1:{free_port}/")
        server.serve_forever()

def startMIServer():
    start_server()