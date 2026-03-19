import dash
from dash import dcc, Input, Output, State, callback, html, clientside_callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import socket
import numpy as np
from typing import List, Dict, Optional
import logging
import sys
from utils.CosThetaPrintUtils import *

import warnings
warnings.filterwarnings('ignore')
logging.getLogger('werkzeug').setLevel(logging.ERROR)


# Setup logging
# logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s', force=False)
# logger = logging.getLogger(__name__)

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

import os
assets_path = os.path.join(os.path.dirname(__file__), "assets")
if not os.path.exists(assets_path):
    printBoldRed(f"Assets directory not found: {assets_path}")
    app = dash.Dash(__name__)
    printBoldYellow("Dash app initialized without local assets")
else:
    app = dash.Dash(__name__, assets_folder=assets_path)
    printBoldGreen("Dash app initialized with local assets")

# Initialize Dash app with local assets
# try:
#     app = dash.Dash(__name__, assets_folder='assets')
#     logger.info("Dash app initialized with local assets")
# except Exception as e:
#     logger.error(f"Failed to initialize Dash app: {e}")
#     sys.exit(1)

# Client-side callback for theme toggle
clientside_callback(
    """
    function(checked) {
        document.documentElement.setAttribute('data-bs-theme', checked ? 'dark' : 'light');
        return null;
    }
    """,
    Output('theme-dummy', 'children'),
    Input('theme-switch', 'value')
)

# Client-side callback for copying chart to clipboard
# clientside_callback(
#     """
#     function(...args) {
#         const n_clicks_list = args.slice(0, -1);
#         const graph_id = args[args.length - 1];
#         const n_clicks = n_clicks_list.reduce((a, b) => a + (b || 0), 0);
#         console.log('Snapshot triggered:', {n_clicks, graph_id, n_clicks_list});
#         if (n_clicks > 0) {
#             try {
#                 const graphDiv = document.getElementById(graph_id);
#                 if (!graphDiv) {
#                     console.error('Graph element not found for ID:', graph_id);
#                     return 'Error: Graph not found.';
#                 }
#                 return Plotly.toImage(graphDiv, {format: 'png', width: 800, height: 400}).then(function(dataUrl) {
#                     const img = newwidgets Image();
#                     img.src = dataUrl;
#                     return newwidgets Promise((resolve) => {
#                         img.onload = function() {
#                             const canvas = document.createElement('canvas');
#                             canvas.width = img.width;
#                             canvas.height = img.height;
#                             const ctx = canvas.getContext('2d');
#                             ctx.drawImage(img, 0, 0);
#                             canvas.toBlob(function(blob) {
#                                 navigator.clipboard.write([
#                                     newwidgets ClipboardItem({'image/png': blob})
#                                 ]).then(function() {
#                                     console.log('Image copied to clipboard successfully');
#                                     resolve('Copied to clipboard!');
#                                 }).catch(function(error) {
#                                     console.error('Clipboard write error:', error);
#                                     resolve('Error: Failed to copy to clipboard.');
#                                 });
#                             }, 'image/png');
#                         };
#                         img.onerror = function() {
#                             console.error('Image load error for data URL');
#                             resolve('Error: Failed to load image.');
#                         };
#                     });
#                 }).catch(function(error) {
#                     console.error('Plotly toImage error:', error);
#                     return 'Error: Failed to generate image.';
#                 });
#             } catch (error) {
#                 console.error('Snapshot error:', error);
#                 return 'Error: Snapshot failed.';
#             }
#         }
#         return null;
#     }
#     """,
#     Output('toast-message', 'children'),
#     [Input(f'snapshot-btn-{tab}', 'n_clicks') for tab in [
#         'day', 'week', 'torque1-tightening', 'torque1-rotation',
#         'torque2-tightening', 'torque2-rotation', 'torque3-tightening',
#         'torque3-rotation', 'reworked'
#     ]] + [State('snapshot-graph-id', 'data')],
#     prevent_initial_call=True
# )

clientside_callback(
    """
    function(...args) {
        const n_clicks_list = args.slice(0, -1);
        const graph_id = args[args.length - 1];
        const n_clicks = n_clicks_list.reduce((a, b) => a + (b || 0), 0);
        console.log('Snapshot triggered:', {n_clicks, graph_id, n_clicks_list});
        if (n_clicks > 0) {
            try {
                const graphDiv = document.getElementById(graph_id);
                if (!graphDiv) {
                    console.error('Graph element not found for ID:', graph_id);
                    return 'Error: Graph not found.';
                }
                if (!navigator.clipboard) {
                    console.error('Clipboard API not available');
                    return 'Error: Clipboard API not supported.';
                }
                return Plotly.toImage(graphDiv, {format: 'png', width: 800, height: 400}).then(function(dataUrl) {
                    const img = newwidgets Image();
                    img.src = dataUrl;
                    return newwidgets Promise((resolve) => {
                        img.onload = function() {
                            const canvas = document.createElement('canvas');
                            canvas.width = img.width;
                            canvas.height = img.height;
                            const ctx = canvas.getContext('2d');
                            if (!ctx) {
                                console.error('Canvas context not available');
                                resolve('Error: Canvas context unavailable.');
                                return;
                            }
                            ctx.drawImage(img, 0, 0);
                            canvas.toBlob(function(blob) {
                                if (!blob) {
                                    console.error('Blob creation failed');
                                    resolve('Error: Failed to create image blob.');
                                    return;
                                }
                                navigator.clipboard.write([
                                    newwidgets ClipboardItem({'image/png': blob})
                                ]).then(function() {
                                    console.log('Image copied to clipboard successfully');
                                    resolve('Copied to clipboard!');
                                }).catch(function(error) {
                                    console.error('Clipboard write error:', error);
                                    resolve('Error: Failed to copy to clipboard.');
                                });
                            }, 'image/png');
                        };
                        img.onerror = function() {
                            console.error('Image load error for data URL');
                            resolve('Error: Failed to load image.');
                        };
                    });
                }).catch(function(error) {
                    console.error('Plotly toImage error:', error);
                    return 'Error: Failed to generate image.';
                });
            } catch (error) {
                console.error('Snapshot error:', error);
                return 'Error: Snapshot failed.';
            }
        }
        return null;
    }
    """,
    Output('toast-message', 'children'),
    [Input(f'snapshot-btn-{tab}', 'n_clicks') for tab in [
        'day', 'week', 'torque1-tightening', 'torque1-rotation',
        'torque2-tightening', 'torque2-rotation', 'torque3-tightening',
        'torque3-rotation', 'reworked'
    ]] + [State('snapshot-graph-id', 'data')],
    prevent_initial_call=True
)

# Helper function to fetch unique model names
def fetch_unique_models() -> List[str]:
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(unique_models_query)
                models = [row[0] for row in cursor.fetchall() if row[0]]
                printBlue(f"Fetched models for MI : {models}")
                return ['ALL MODELS'] + models
    except Error as e:
        printBoldRed(f"Database error in fetch_unique_models in AutoCompany_MI: {e}")
        return ['ALL MODELS']

# Helper function to connect to database and fetch data
def fetch_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
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
                printBlue(f"Fetched {len(df)} records from {start_date} to {end_date}")
                return df
    except Error as e:
        printBoldRed(f"Database error in fetch_data: {e}")
        return pd.DataFrame()

# Helper function to calculate date ranges
def get_date_ranges() -> Dict[str, tuple]:
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

# Helper function to calculate components per day by model
def components_per_day(df: pd.DataFrame, model_name: str, period: str) -> go.Figure:
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    start, end = get_date_ranges()[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    if df_period.empty:
        return go.Figure().update_layout(
            title=f'Components per Day ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            plot_bgcolor='rgba(144, 238, 144, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
    df_grouped = df_period.groupby(df_period['created_on'].dt.date).size().reset_index(name='count')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['created_on'], y=df_grouped['count'],
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
    return fig

# Helper function to calculate components per week by model
def components_per_week(df: pd.DataFrame, model_name: str, period: str) -> go.Figure:
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
    if df_period.empty:
        return go.Figure().update_layout(
            title=f'Components per Week ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            plot_bgcolor='rgba(144, 238, 144, 0.1)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
    df_grouped = df_period.groupby(pd.Grouper(key='created_on', freq='W-MON')).size().reset_index(name='count')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_grouped['created_on'], y=df_grouped['count'],
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
    return fig

# Helper function to calculate torque distributions
def torque_distribution(df: pd.DataFrame, column: str, model_name: str, period: str) -> go.Figure:
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    torque_ranges = {
        '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
        '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
        '365_days': (datetime.now() - timedelta(days=365), datetime.now())
    }
    start, end = torque_ranges[period]
    df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df[column] >= 0)]
    if model_name != 'ALL MODELS':
        df_period = df_period[df_period['model_name'] == model_name]
    if df_period.empty or df_period[column].dropna().empty:
        return go.Figure().update_layout(
            title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").title()} - {title_suffix}) - No Data',
            template='plotly_white',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
    data = [df_period[column].dropna()]
    fig = ff.create_distplot(
        data,
        group_labels=[column],
        show_hist=False,
        show_rug=False,
        colors=['#00008B']
    )
    fig.update_traces(
        fill='tozeroy',
        fillcolor='rgba(173, 216, 230, 0.5)',
        line=dict(color='#00008B', width=2)
    )
    fig.update_layout(
        title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").title()} - {title_suffix})',
        template='plotly_white',
        xaxis_title="Torque Value",
        yaxis_title="Density",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    return fig

# Helper function to calculate reworked components by model
def reworked_components(df: pd.DataFrame, model_name: str) -> go.Figure:
    title_suffix = 'All Models' if model_name == 'ALL MODELS' else model_name
    torque_ranges = {
        '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
        '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
        '365_days': (datetime.now() - timedelta(days=365), datetime.now())
    }
    data = {}
    for period, (start, end) in torque_ranges.items():
        df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
        if model_name != 'ALL MODELS':
            df_period = df_period[df_period['model_name'] == model_name]
        count = len(df_period[df_period['remarks'].str.contains('DUPLICATE', case=False, na=False)])
        data[period] = count
    df_reworked = pd.DataFrame(list(data.items()), columns=['Period', 'Reworked Components'])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_reworked['Period'],
        y=df_reworked['Reworked Components'],
        mode='lines+markers',
        line=dict(color='#006400', width=2),
        marker=dict(size=8, color='#006400')
    ))
    fig.update_layout(
        title=f'Reworked Components (Duplicate in Remarks - {title_suffix})',
        template='plotly_white',
        xaxis_title="Period",
        yaxis_title="Reworked Component Count",
        plot_bgcolor='rgba(144, 238, 144, 0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=12)
    )
    return fig

# Minimal layout for testing
def create_minimal_layout() -> html.Div:
    return html.Div([
        html.Link(rel='stylesheet', href='assets/bootstrap.min.css'),
        html.Script(src='assets/bootstrap.bundle.min.js'),
        html.H1("Minimal Dashboard Test", className="text-primary"),
        html.P("Testing DBC with local assets", className="text-muted"),
        html.Div(id="theme-dummy")
    ])

# Full Dash layout with local assets
def create_layout() -> html.Div:
    try:
        models = fetch_unique_models()
        select_data: List[Dict[str, str]] = [{"label": model, "value": model} for model in models]
        default_value: Optional[str] = models[0] if models else None
        printBlue(f"Select data for model-dropdown: {select_data}, default_value: {default_value}")

        period_data: List[Dict[str, str]] = [
            {"label": "Last 7 Days", "value": "7_days"},
            {"label": "Last 30 Days", "value": "30_days"},
            {"label": "Last 90 Days", "value": "90_days"},
            {"label": "Last 365 Days", "value": "365_days"},
            {"label": "Year-to-Date", "value": "ytd"},
            {"label": "Quarter-to-Date", "value": "qtd"},
            {"label": "Month-to-Date", "value": "mtd"}
        ]
        week_period_data: List[Dict[str, str]] = [
            {"label": "Last 12 Weeks", "value": "12_weeks"},
            {"label": "Last 52 Weeks", "value": "52_weeks"},
            {"label": "Year-to-Date", "value": "ytd"},
            {"label": "Quarter-to-Date", "value": "qtd"},
            {"label": "Month-to-Date", "value": "mtd"}
        ]
        torque_period_data: List[Dict[str, str]] = [
            {"label": "Last 30 Days", "value": "30_days"},
            {"label": "Last 90 Days", "value": "90_days"},
            {"label": "Last 365 Days", "value": "365_days"}
        ]

        toast = dbc.Toast(
            id="snapshot-toast",
            header="Snapshot Status",
            is_open=False,
            dismissable=True,
            duration=4000,
            children=html.Div(id="toast-message"),
            style={"position": "fixed", "top": 10, "right": 10, "width": 250}
        )

        return html.Div([
            html.Link(rel='stylesheet', href='assets/bootstrap.min.css'),
            html.Script(src='assets/bootstrap.bundle.min.js'),
            toast,
            dcc.Store(id='snapshot-graph-id', data='components-day'),
            dbc.Container(
                fluid=True,
                className="py-4 bg-gradient",
                style={"background": "linear-gradient(to bottom, #f8f9fa, #e9ecef)"},
                children=[
                    dbc.Row(
                        [
                            dbc.Col(
                                html.H1(
                                    [
                                        html.Img(src='assets/bootstrap-icons/bar-chart-line.svg', width=32, className="me-2", alt="Chart Icon"),
                                        "Hub and Disc Assembly Dashboard"
                                    ],
                                    className="text-primary mb-0",
                                    style={"fontWeight": "700", "fontSize": "2.5rem"}
                                ),
                                width="auto"
                            ),
                            dbc.Col(
                                [
                                    html.Div(
                                        "Made by CosTheta Technologies",
                                        className="bg-primary text-white rounded-pill px-3 py-2 shadow-sm",
                                        style={"fontSize": "0.9rem", "fontWeight": "500"}
                                    ),
                                    dbc.Switch(
                                        id="theme-switch",
                                        label=[
                                            html.Img(
                                                src='assets/bootstrap-icons/moon-stars-fill.svg' if False else 'assets/bootstrap-icons/sun-fill.svg',
                                                width=20,
                                                className="me-2",
                                                alt="Theme Icon"
                                            ),
                                            "Dark Mode"
                                        ],
                                        value=False,
                                        className="mt-2"
                                    )
                                ],
                                width="auto",
                                className="d-flex flex-column align-items-end"
                            )
                        ],
                        className="mb-4",
                        justify="between",
                        align="center"
                    ),
                    dbc.Card(
                        [
                            dbc.CardBody([
                                html.Label(
                                    [
                                        html.Img(src='assets/bootstrap-icons/gear-fill.svg', width=20, className="me-2", alt="Gear Icon"),
                                        "Select Model Name"
                                    ],
                                    className="form-label fw-semibold mb-2"
                                ),
                                dbc.Select(
                                    id="model-dropdown",
                                    options=select_data,
                                    value=default_value,
                                    placeholder="Select a model",
                                    className="mb-3 shadow-sm",
                                    style={"maxWidth": "400px"}
                                )
                            ])
                        ],
                        className="shadow mb-4 border-0"
                    ),
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                label="Components per Day",
                                tab_id="day",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/calendar-day.svg', width=20, className="me-2", alt="Calendar Day"),
                                                html.Span("Components per Day", className="fw-semibold")
                                            ], className="bg-light"),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="day-period-dropdown",
                                                            options=period_data,
                                                            value="7_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-day",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="components-day", style={"height": "400px"}),
                                                html.P(
                                                    "Components processed per day for the selected model or all models.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Components per Week",
                                tab_id="week",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/calendar-week.svg', width=20, className="me-2", alt="Calendar Week"),
                                                html.Span("Components per Week", className="fw-semibold")
                                            ], className="bg-light"),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="week-period-dropdown",
                                                            options=week_period_data,
                                                            value="12_weeks",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-week",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="components-week", style={"height": "400px"}),
                                                html.P(
                                                    "Components processed per week for the selected model or all models.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Nut Tightening Torque 1",
                                tab_id="torque1-tightening",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/wrench.svg', width=20, className="me-2", alt="Wrench"),
                                                html.Span("Nut Tightening Torque 1", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque1-tightening-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque1-tightening",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque1-tightening", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Nut Tightening Torque 1 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Free Rotation Torque 1",
                                tab_id="torque1-rotation",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/arrow-repeat.svg', width=20, className="me-2", alt="Arrow Repeat"),
                                                html.Span("Free Rotation Torque 1", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque1-rotation-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque1-rotation",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque1-rotation", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Free Rotation Torque 1 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Nut Tightening Torque 2",
                                tab_id="torque2-tightening",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/wrench.svg', width=20, className="me-2", alt="Wrench"),
                                                html.Span("Nut Tightening Torque 2", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque2-tightening-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque2-tightening",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque2-tightening", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Nut Tightening Torque 2 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Free Rotation Torque 2",
                                tab_id="torque2-rotation",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/arrow-repeat.svg', width=20, className="me-2", alt="Arrow Repeat"),
                                                html.Span("Free Rotation Torque 2", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque2-rotation-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque2-rotation",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque2-rotation", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Free Rotation Torque 2 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Nut Tightening Torque 3",
                                tab_id="torque3-tightening",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/wrench.svg', width=20, className="me-2", alt="Wrench"),
                                                html.Span("Nut Tightening Torque 3", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque3-tightening-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque3-tightening",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque3-tightening", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Nut Tightening Torque 3 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Free Rotation Torque 3",
                                tab_id="torque3-rotation",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/arrow-repeat.svg', width=20, className="me-2", alt="Arrow Repeat"),
                                                html.Span("Free Rotation Torque 3", className="fw-semibold")
                                            ], style={"backgroundColor": "#ADD8E6"}),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(
                                                        dbc.Select(
                                                            id="torque3-rotation-period-dropdown",
                                                            options=torque_period_data,
                                                            value="30_days",
                                                            className="mb-3 shadow-sm",
                                                            style={"maxWidth": "300px"}
                                                        ),
                                                        width="auto"
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-torque3-rotation",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="torque3-rotation", style={"height": "400px"}),
                                                html.P(
                                                    "Distribution of Free Rotation Torque 3 values.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            ),
                            dbc.Tab(
                                label="Reworked Components",
                                tab_id="reworked",
                                children=[
                                    dbc.Card(
                                        [
                                            dbc.CardHeader([
                                                html.Img(src='assets/bootstrap-icons/arrow-counterclockwise.svg', width=20, className="me-2", alt="Arrow Counterclockwise"),
                                                html.Span("Reworked Components", className="fw-semibold")
                                            ], className="bg-light"),
                                            dbc.CardBody([
                                                dbc.Row([
                                                    dbc.Col(width="auto"),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            [
                                                                html.Img(src='assets/bootstrap-icons/camera.svg', width=20, className="me-2", alt="Camera"),
                                                                "Take Picture"
                                                            ],
                                                            id="snapshot-btn-reworked",
                                                            color="primary",
                                                            outline=True,
                                                            className="mb-3",
                                                            n_clicks=0
                                                        ),
                                                        width="auto",
                                                        className="ms-auto"
                                                    )
                                                ]),
                                                dcc.Graph(id="reworked-components", style={"height": "400px"}),
                                                html.P(
                                                    "Reworked components marked as 'DUPLICATE' in remarks.",
                                                    className="text-muted small mt-2"
                                                )
                                            ])
                                        ],
                                        className="shadow mt-3 border-0"
                                    )
                                ]
                            )
                        ],
                        id="tabs",
                        active_tab="day",
                        className="nav-pills"
                    ),
                    dcc.Interval(id="interval-component", interval=60*1000, n_intervals=0),
                    html.Div(id="theme-dummy")
                ]
            )
        ])
    except Exception as e:
        printBoldRed(f"Error in create_layout: {e}. Defaulting to minimal layout")
        return create_minimal_layout()

# Assign layout
try:
    app.layout = create_layout()
except Exception as e:
    printBoldRed(f"Error assigning layout: {e}. Defaulting to minimal layout")
    app.layout = create_minimal_layout()

# Callback to store the graph ID when a snapshot button is clicked
@app.callback(
    Output('snapshot-graph-id', 'data'),
    [Input(f'snapshot-btn-{tab}', 'n_clicks') for tab in [
        'day', 'week', 'torque1-tightening', 'torque1-rotation',
        'torque2-tightening', 'torque2-rotation', 'torque3-tightening',
        'torque3-rotation', 'reworked'
    ]],
    prevent_initial_call=True
)
def update_snapshot_graph_id(*n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return 'components-day'
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    tab = button_id.replace('snapshot-btn-', '')
    graph_id = {
        'day': 'components-day',
        'week': 'components-week',
        'torque1-tightening': 'torque1-tightening',
        'torque1-rotation': 'torque1-rotation',
        'torque2-tightening': 'torque2-tightening',
        'torque2-rotation': 'torque2-rotation',
        'torque3-tightening': 'torque3-tightening',
        'torque3-rotation': 'torque3-rotation',
        'reworked': 'reworked-components'
    }.get(tab, 'components-day')
    return graph_id

# Callback to show toast
@app.callback(
    Output("snapshot-toast", "is_open"),
    [Input(f'snapshot-btn-{tab}', 'n_clicks') for tab in [
        'day', 'week', 'torque1-tightening', 'torque1-rotation',
        'torque2-tightening', 'torque2-rotation', 'torque3-tightening',
        'torque3-rotation', 'reworked'
    ]],
    prevent_initial_call=True
)
def show_toast(*n_clicks):
    try:
        printBlue(f"show_toast inputs: {n_clicks}")
        if any((n or 0) > 0 for n in n_clicks):
            return True
        return False
    except Exception as e:
        printBoldRed(f"Error in show_toast callback: {e}")
        return False

# Callback to update all graphs
@app.callback(
    [
        Output('components-day', 'figure'),
        Output('components-week', 'figure'),
        Output('torque1-tightening', 'figure'),
        Output('torque1-rotation', 'figure'),
        Output('torque2-tightening', 'figure'),
        Output('torque2-rotation', 'figure'),
        Output('torque3-tightening', 'figure'),
        Output('torque3-rotation', 'figure'),
        Output('reworked-components', 'figure')
    ],
    [
        Input('interval-component', 'n_intervals'),
        Input('model-dropdown', 'value'),
        Input('day-period-dropdown', 'value'),
        Input('week-period-dropdown', 'value'),
        Input('torque1-tightening-period-dropdown', 'value'),
        Input('torque1-rotation-period-dropdown', 'value'),
        Input('torque2-tightening-period-dropdown', 'value'),
        Input('torque2-rotation-period-dropdown', 'value'),
        Input('torque3-tightening-period-dropdown', 'value'),
        Input('torque3-rotation-period-dropdown', 'value')
    ]
)
def update_graphs(n_intervals: int, model_name: Optional[str], day_period: str, week_period: str,
                  torque1_tightening_period: str, torque1_rotation_period: str,
                  torque2_tightening_period: str, torque2_rotation_period: str,
                  torque3_tightening_period: str, torque3_rotation_period: str) -> List[go.Figure]:
    try:
        if not model_name:
            empty_fig = go.Figure().update_layout(
                title='No Model Selected',
                template='plotly_white',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            return [empty_fig] * 9

        earliest_date = datetime.now() - timedelta(days=365)
        df = fetch_data(earliest_date, datetime.now())

        day_fig = components_per_day(df, model_name, day_period)
        week_fig = components_per_week(df, model_name, week_period)
        torque1_tightening_fig = torque_distribution(df, 'nut_tightening_torque_1', model_name, torque1_tightening_period)
        torque1_rotation_fig = torque_distribution(df, 'free_rotation_torque_1', model_name, torque1_rotation_period)
        torque2_tightening_fig = torque_distribution(df, 'nut_tightening_torque_2', model_name, torque2_tightening_period)
        torque2_rotation_fig = torque_distribution(df, 'free_rotation_torque_2', model_name, torque2_rotation_period)
        torque3_tightening_fig = torque_distribution(df, 'nut_tightening_torque_3', model_name, torque3_tightening_period)
        torque3_rotation_fig = torque_distribution(df, 'free_rotation_torque_3', model_name, torque3_rotation_period)
        reworked_fig = reworked_components(df, model_name)

        return [
            day_fig, week_fig,
            torque1_tightening_fig, torque1_rotation_fig,
            torque2_tightening_fig, torque2_rotation_fig,
            torque3_tightening_fig, torque3_rotation_fig,
            reworked_fig
        ]
    except Exception as e:
        printBoldRed(f"Error in update_graphs: {e}")
        empty_fig = go.Figure().update_layout(
            title=f'Error: {str(e)}',
            template='plotly_white',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        return [empty_fig] * 9

# Function to find a free port
def find_free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
            printBoldRed(f"Found free port: {port}")
            return port
    except Exception as e:
        printBoldRed(f"Error finding free port: {e}")
        return 8051

# Start the Dash server
def startMIServer():
    try:
        desired_port = 8050
        printLight(f"Attempting to start server on port {desired_port}")
        print(f"Dash is running on http://127.0.0.1:{desired_port}/", flush=True)
        app.run(host='0.0.0.0', port=desired_port, debug=False)
        printLight(f"Started Dash Hub and Disc Dashboard on port {desired_port}")
        printBoldBlue(f"*****************")
        printBoldBlue(f"Started Hub and Disc Dashboard")
        printBoldBlue(f"*****************")
    except OSError as e:
        printBoldRed(f"Port {desired_port} is in use: {e}")
        free_port = find_free_port()
        printLight(f"Starting server on port {free_port}")
        print(f"Dash is running on http://127.0.0.1:{free_port}/", flush=True)
        try:
            app.run(host='0.0.0.0', port=free_port, debug=False)
            printBoldBlue(f"Started Dash Hub and Disc Dashboard on port {free_port}")
        except Exception as e:
            printBoldRed(f"Failed to start server on port {free_port}: {e}")
    except Exception as e:
        printBoldRed(f"Failed to start server: {e}")

startMIServer()

#  ************************* ALTERNATE CODE WITHOUT DBC *************************

# import dash
# from dash import dcc, html
# from dash.dependencies import Input, Output
# import plotly.express as px
# import plotly.graph_objects as go
# import plotly.figure_factory as ff
# import pandas as pd
# import psycopg2
# from psycopg2 import Error
# from datetime import datetime, timedelta
# from dateutil.relativedelta import relativedelta
# import socket
# import numpy as np
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
# base_query = """
#     SELECT created_on, model_name, nut_tightening_torque_1, free_rotation_torque_1,
#            nut_tightening_torque_2, free_rotation_torque_2,
#            nut_tightening_torque_3, free_rotation_torque_3,
#            remarks
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     WHERE created_on >= %s AND created_on <= %s
# """
#
# unique_models_query = """
#     SELECT DISTINCT model_name
#     FROM hub_and_disc_assembly_schema.hub_and_disc_assembly_data
#     ORDER BY model_name
# """
#
# # Initialize Dash app
# app = dash.Dash(__name__)
#
# # Helper function to fetch unique model names
# def fetch_unique_models():
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(unique_models_query)
#                 models = [row[0] for row in cursor.fetchall()]
#                 return ['ALL MODELS'] + models
#     except Error as e:
#         print(f"Database error: {e}")
#         return ['ALL MODELS']
#
# # Helper function to connect to database and fetch data
# def fetch_data(start_date, end_date):
#     try:
#         with psycopg2.connect(**db_params) as conn:
#             with conn.cursor() as cursor:
#                 cursor.execute(base_query, (start_date, end_date))
#                 records = cursor.fetchall()
#                 df = pd.DataFrame(records, columns=[
#                     'created_on', 'model_name', 'nut_tightening_torque_1', 'free_rotation_torque_1',
#                     'nut_tightening_torque_2', 'free_rotation_torque_2',
#                     'nut_tightening_torque_3', 'free_rotation_torque_3', 'remarks'
#                 ])
#                 return df
#     except Error as e:
#         print(f"Database error: {e}")
#         return pd.DataFrame()
#
# # Helper function to calculate date ranges
# def get_date_ranges():
#     now = datetime.now()
#     return {
#         '7_days': (now - timedelta(days=7), now),
#         '30_days': (now - timedelta(days=30), now),
#         '90_days': (now - timedelta(days=90), now),
#         '365_days': (now - timedelta(days=365), now),
#         'ytd': (datetime(now.year, 1, 1), now),
#         'qtd': (now - relativedelta(months=(now.month - 1) % 3), now),
#         'mtd': (datetime(now.year, now.month, 1), now)
#     }
#
# # Helper function to calculate components per day by model
# def components_per_day(df, model_name, period):
#     start, end = get_date_ranges()[period]
#     if model_name == 'ALL MODELS':
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
#         title_suffix = 'All Models'
#     else:
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df['model_name'] == model_name)]
#         title_suffix = model_name
#     if df_period.empty:
#         return go.Figure().update_layout(
#             title=f'Components per Day ({period.replace("_", " ").upper()} - {title_suffix}) - No Data',
#             template='plotly_white',
#             plot_bgcolor='#F5F0FF'
#         )
#     df_grouped = df_period.groupby(df_period['created_on'].dt.date).size().reset_index(name='count')
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(
#         x=df_grouped['created_on'], y=df_grouped['count'],
#         mode='lines+markers', line=dict(color='#4B0082')
#     ))
#     fig.update_layout(
#         title=f'Components per Day ({period.replace("_", " ").upper()} - {title_suffix})',
#         template='plotly_white',
#         xaxis_title="Date", yaxis_title="Component Count",
#         plot_bgcolor='#F5F0FF'
#     )
#     return fig
#
# # Helper function to calculate components per week by model
# def components_per_week(df, model_name, period):
#     week_ranges = {
#         '12_weeks': (datetime.now() - timedelta(weeks=12), datetime.now()),
#         '52_weeks': (datetime.now() - timedelta(weeks=52), datetime.now()),
#         'ytd': (datetime(datetime.now().year, 1, 1), datetime.now()),
#         'qtd': (datetime.now() - relativedelta(months=(datetime.now().month - 1) % 3), datetime.now()),
#         'mtd': (datetime(datetime.now().year, datetime.now().month, 1), datetime.now())
#     }
#     start, end = week_ranges[period]
#     if model_name == 'ALL MODELS':
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
#         title_suffix = 'All Models'
#     else:
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df['model_name'] == model_name)]
#         title_suffix = model_name
#     if df_period.empty:
#         return go.Figure().update_layout(
#             title=f'Components per Week ({period.replace("_", " ").upper()} - {title_suffix}) - No Data',
#             template='plotly_white',
#             plot_bgcolor='#F5F0FF'
#         )
#     df_grouped = df_period.groupby(pd.Grouper(key='created_on', freq='W-MON')).size().reset_index(name='count')
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(
#         x=df_grouped['created_on'], y=df_grouped['count'],
#         mode='lines+markers', line=dict(color='#4B0082')
#     ))
#     fig.update_layout(
#         title=f'Components per Week ({period.replace("_", " ").upper()} - {title_suffix})',
#         template='plotly_white',
#         xaxis_title="Week Starting", yaxis_title="Component Count",
#         plot_bgcolor='#F5F0FF'
#     )
#     return fig
#
# # Helper function to calculate torque distributions
# def torque_distribution(df, column, model_name, period):
#     torque_ranges = {
#         '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
#         '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
#         '365_days': (datetime.now() - timedelta(days=365), datetime.now())
#     }
#     start, end = torque_ranges[period]
#     if model_name == 'ALL MODELS':
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df[column] >= 0)]
#         title_suffix = 'All Models'
#     else:
#         df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df[column] >= 0) & (df['model_name'] == model_name)]
#         title_suffix = model_name
#     if df_period.empty or df_period[column].dropna().empty:
#         return go.Figure().update_layout(
#             title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").upper()} - {title_suffix}) - No Data',
#             template='plotly_white',
#             plot_bgcolor='#F0F8FF'
#         )
#     data = [df_period[column].dropna()]
#     fig = ff.create_distplot(
#         data, group_labels=[column], show_hist=False, show_rug=False,
#         colors=['#00008B']
#     )
#     fig.update_layout(
#         title=f'{column.replace("_", " ").title()} ({period.replace("_", " ").upper()} - {title_suffix})',
#         template='plotly_white',
#         xaxis_title="Torque Value", yaxis_title="Density",
#         plot_bgcolor='#F0F8FF'
#     )
#     return fig
#
# # Helper function to calculate reworked components by model
# def reworked_components(df, model_name):
#     torque_ranges = {
#         '30_days': (datetime.now() - timedelta(days=30), datetime.now()),
#         '90_days': (datetime.now() - timedelta(days=90), datetime.now()),
#         '365_days': (datetime.now() - timedelta(days=365), datetime.now())
#     }
#     data = {}
#     for period, (start, end) in torque_ranges.items():
#         if model_name == 'ALL MODELS':
#             df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end)]
#             title_suffix = 'All Models'
#         else:
#             df_period = df[(df['created_on'] >= start) & (df['created_on'] <= end) & (df['model_name'] == model_name)]
#             title_suffix = model_name
#         count = len(df_period[df_period['remarks'].str.contains('DUPLICATE', case=False, na=False)])
#         data[period] = count
#     df_reworked = pd.DataFrame(list(data.items()), columns=['Period', 'Reworked Components'])
#     fig = px.bar(
#         df_reworked, x='Period', y='Reworked Components',
#         title=f'Reworked Components (DUPLICATE in Remarks - {title_suffix})',
#         template='plotly_white',
#         color_discrete_sequence=['#4B0082']
#     )
#     fig.update_layout(
#         xaxis_title="Period", yaxis_title="Reworked Component Count",
#         plot_bgcolor='#F5F0FF'
#     )
#     return fig
#
# # Dash layout
# app.layout = html.Div([
#     html.Div(className='container', children=[
#         html.H1("Hub and Disc Assembly Dashboard"),
#         html.Label("Select Model Name:", style={'fontWeight': 'bold', 'color': '#1f77b4'}),
#         dcc.Dropdown(
#             id='model-dropdown',
#             options=[{'label': model, 'value': model} for model in fetch_unique_models()],
#             value=fetch_unique_models()[0] if fetch_unique_models() else None,
#             placeholder="Select a model",
#             className='dash-dropdown'
#         ),
#         dcc.Tabs([
#             dcc.Tab(label='Components per Day', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='day-period-dropdown',
#                     options=[
#                         {'label': 'Last 7 Days', 'value': '7_days'},
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'},
#                         {'label': 'Year-to-Date', 'value': 'ytd'},
#                         {'label': 'Quarter-to-Date', 'value': 'qtd'},
#                         {'label': 'Month-to-Date', 'value': 'mtd'}
#                     ],
#                     value='7_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='components-day'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab displays the number of components processed per day for the selected model
#                         or all models. Use the dropdown to view data for the last 7 days, 30 days, 90 days,
#                         365 days, Year-to-Date (YTD), Quarter-to-Date (QTD), or Month-to-Date (MTD). The
#                         line plot shows the count of components completed on each day.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Components per Week', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='week-period-dropdown',
#                     options=[
#                         {'label': 'Last 12 Weeks', 'value': '12_weeks'},
#                         {'label': 'Last 52 Weeks', 'value': '52_weeks'},
#                         {'label': 'Year-to-Date', 'value': 'ytd'},
#                         {'label': 'Quarter-to-Date', 'value': 'qtd'},
#                         {'label': 'Month-to-Date', 'value': 'mtd'}
#                     ],
#                     value='12_weeks',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='components-week'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab shows the number of components processed per week for the selected model
#                         or all models. Use the dropdown to view data for the last 12 weeks, 52 weeks,
#                         Year-to-Date (YTD), Quarter-to-Date (QTD), or Month-to-Date (MTD). The line plot
#                         shows the count of components completed in each week, starting on Monday.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Nut Tightening Torque 1', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque1-tightening-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque1-tightening'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab presents a distribution curve of Nut Tightening Torque 1 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve shows the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Free Rotation Torque 1', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque1-rotation-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque1-rotation'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab displays a distribution curve of Free Rotation Torque 1 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve illustrates the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Nut Tightening Torque 2', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque2-tightening-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque2-tightening'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab shows a distribution curve of Nut Tightening Torque 2 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve depicts the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Free Rotation Torque 2', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque2-rotation-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque2-rotation'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab presents a distribution curve of Free Rotation Torque 2 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve shows the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Nut Tightening Torque 3', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque3-tightening-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque3-tightening'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab displays a distribution curve of Nut Tightening Torque 3 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve illustrates the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Free Rotation Torque 3', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Dropdown(
#                     id='torque3-rotation-period-dropdown',
#                     options=[
#                         {'label': 'Last 30 Days', 'value': '30_days'},
#                         {'label': 'Last 90 Days', 'value': '90_days'},
#                         {'label': 'Last 365 Days', 'value': '365_days'}
#                     ],
#                     value='30_days',
#                     className='period-dropdown'
#                 ),
#                 dcc.Graph(id='torque3-rotation'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab shows a distribution curve of Free Rotation Torque 3 values for the
#                         selected model or all models. Use the dropdown to view data for the last 30 days,
#                         90 days, or 365 days. The curve represents the density of torque values.
#                     """)
#                 ])
#             ]),
#             dcc.Tab(label='Reworked Components', className='dash-tab', selected_className='dash-tab--selected', children=[
#                 dcc.Graph(id='reworked-components'),
#                 html.Div(className='description', children=[
#                     html.P("""
#                         This tab displays the number of reworked components (records marked as 'DUPLICATE'
#                         in the remarks) for the selected model or all models over the last 30 days,
#                         90 days, and 365 days. Each bar represents the count of reworked components
#                         for the specified period.
#                     """)
#                 ])
#             ])
#         ]),
#         dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0)  # Update every minute
#     ])
# ])
#
# # Callback to update all graphs
# @app.callback(
#     [
#         Output('components-day', 'figure'),
#         Output('components-week', 'figure'),
#         Output('torque1-tightening', 'figure'),
#         Output('torque1-rotation', 'figure'),
#         Output('torque2-tightening', 'figure'),
#         Output('torque2-rotation', 'figure'),
#         Output('torque3-tightening', 'figure'),
#         Output('torque3-rotation', 'figure'),
#         Output('reworked-components', 'figure')
#     ],
#     [
#         Input('interval-component', 'n_intervals'),
#         Input('model-dropdown', 'value'),
#         Input('day-period-dropdown', 'value'),
#         Input('week-period-dropdown', 'value'),
#         Input('torque1-tightening-period-dropdown', 'value'),
#         Input('torque1-rotation-period-dropdown', 'value'),
#         Input('torque2-tightening-period-dropdown', 'value'),
#         Input('torque2-rotation-period-dropdown', 'value'),
#         Input('torque3-tightening-period-dropdown', 'value'),
#         Input('torque3-rotation-period-dropdown', 'value')
#     ]
# )
# def update_graphs(n_intervals, model_name, day_period, week_period, torque1_tightening_period, torque1_rotation_period,
#                   torque2_tightening_period, torque2_rotation_period, torque3_tightening_period, torque3_rotation_period):
#     if not model_name:
#         # Return empty figures if no model is selected
#         empty_fig = go.Figure().update_layout(title='No Model Selected', template='plotly_white')
#         return [empty_fig] * 9
#
#     # Fetch data for the maximum range needed
#     earliest_date = datetime.now() - timedelta(days=365)
#     df = fetch_data(earliest_date, datetime.now())
#
#     # Generate figures
#     day_fig = components_per_day(df, model_name, day_period)
#     week_fig = components_per_week(df, model_name, week_period)
#     torque1_tightening_fig = torque_distribution(df, 'nut_tightening_torque_1', model_name, torque1_tightening_period)
#     torque1_rotation_fig = torque_distribution(df, 'free_rotation_torque_1', model_name, torque1_rotation_period)
#     torque2_tightening_fig = torque_distribution(df, 'nut_tightening_torque_2', model_name, torque2_tightening_period)
#     torque2_rotation_fig = torque_distribution(df, 'free_rotation_torque_2', model_name, torque2_rotation_period)
#     torque3_tightening_fig = torque_distribution(df, 'nut_tightening_torque_3', model_name, torque3_tightening_period)
#     torque3_rotation_fig = torque_distribution(df, 'free_rotation_torque_3', model_name, torque3_rotation_period)
#     reworked_fig = reworked_components(df, model_name)
#
#     return [
#         day_fig, week_fig,
#         torque1_tightening_fig, torque1_rotation_fig,
#         torque2_tightening_fig, torque2_rotation_fig,
#         torque3_tightening_fig, torque3_rotation_fig,
#         reworked_fig
#     ]
#
# # Function to find a free port
# def find_free_port():
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind(('0.0.0.0', 0))
#         s.listen(1)
#         port = s.getsockname()[1]
#         return port
#
# # Start the Dash server
# def startMIServer():
#     try:
#         desired_port = 8050
#         try:
#             app.run(host='0.0.0.0', port=desired_port, debug=False)
#             print(f"Started Dash Hub and Disc Dashboard on port {desired_port}")
#         except OSError:
#             print(f"Port {desired_port} is in use, trying a free port")
#             free_port = find_free_port()
#             print(f"Starting server on port {free_port}")
#             app.run(host='0.0.0.0', port=free_port, debug=False)
#     except Exception as e:
#         print(f"Failed to start server: {e}")