import panel as pn
import pandas as pd
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
import plotly.figure_factory as ff
import socket
import numpy as np
from typing import List, Dict, Optional
import logging
import warnings

warnings.filterwarnings('ignore')
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Initialize Panel extension with Plotly
pn.extension('plotly', sizing_mode='stretch_width')


# Helper function to fetch unique model names
def fetch_unique_models() -> List[str]:
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute(unique_models_query)
                models = [row[0] for row in cursor.fetchall() if row[0]]
                logging.info(f"Fetched models: {models}")
                return ['ALL MODELS'] + models
    except Error as e:
        logging.error(f"Database error in fetch_unique_models: {e}")
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
                logging.info(f"Fetched {len(df)} records from {start_date} to {end_date}")
                return df
    except Error as e:
        logging.error(f"Database error in fetch_data: {e}")
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


# Create Panel layout
def create_layout():
    try:
        models = fetch_unique_models()
        default_model = models[0] if models else 'ALL MODELS'

        period_options = [
            ("Last 7 Days", "7_days"),
            ("Last 30 Days", "30_days"),
            ("Last 90 Days", "90_days"),
            ("Last 365 Days", "365_days"),
            ("Year-to-Date", "ytd"),
            ("Quarter-to-Date", "qtd"),
            ("Month-to-Date", "mtd")
        ]
        week_period_options = [
            ("Last 12 Weeks", "12_weeks"),
            ("Last 52 Weeks", "52_weeks"),
            ("Year-to-Date", "ytd"),
            ("Quarter-to-Date", "qtd"),
            ("Month-to-Date", "mtd")
        ]
        torque_period_options = [
            ("Last 30 Days", "30_days"),
            ("Last 90 Days", "90_days"),
            ("Last 365 Days", "365_days")
        ]

        # Widgets
        model_select = pn.widgets.Select(name="Select Model Name", options=models, value=default_model)
        day_period_select = pn.widgets.Select(name="Period", options=[opt[0] for opt in period_options],
                                              value="Last 7 Days")
        week_period_select = pn.widgets.Select(name="Period", options=[opt[0] for opt in week_period_options],
                                               value="Last 12 Weeks")
        torque1_tightening_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                      value="Last 30 Days")
        torque1_rotation_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                    value="Last 30 Days")
        torque2_tightening_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                      value="Last 30 Days")
        torque2_rotation_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                    value="Last 30 Days")
        torque3_tightening_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                      value="Last 30 Days")
        torque3_rotation_period = pn.widgets.Select(name="Period", options=[opt[0] for opt in torque_period_options],
                                                    value="Last 30 Days")
        dark_mode_toggle = pn.widgets.Checkbox(name="Dark Mode", value=False)

        # Fetch initial data
        earliest_date = datetime.now() - timedelta(days=365)
        df = fetch_data(earliest_date, datetime.now())

        # Plotly panes
        day_plot = pn.pane.Plotly(components_per_day(df, model_select.value, dict(period_options)["Last 7 Days"]),
                                  height=400)
        week_plot = pn.pane.Plotly(
            components_per_week(df, model_select.value, dict(week_period_options)["Last 12 Weeks"]), height=400)
        torque1_tightening_plot = pn.pane.Plotly(torque_distribution(df, 'nut_tightening_torque_1', model_select.value,
                                                                     dict(torque_period_options)["Last 30 Days"]),
                                                 height=400)
        torque1_rotation_plot = pn.pane.Plotly(torque_distribution(df, 'free_rotation_torque_1', model_select.value,
                                                                   dict(torque_period_options)["Last 30 Days"]),
                                               height=400)
        torque2_tightening_plot = pn.pane.Plotly(torque_distribution(df, 'nut_tightening_torque_2', model_select.value,
                                                                     dict(torque_period_options)["Last 30 Days"]),
                                                 height=400)
        torque2_rotation_plot = pn.pane.Plotly(torque_distribution(df, 'free_rotation_torque_2', model_select.value,
                                                                   dict(torque_period_options)["Last 30 Days"]),
                                               height=400)
        torque3_tightening_plot = pn.pane.Plotly(torque_distribution(df, 'nut_tightening_torque_3', model_select.value,
                                                                     dict(torque_period_options)["Last 30 Days"]),
                                                 height=400)
        torque3_rotation_plot = pn.pane.Plotly(torque_distribution(df, 'free_rotation_torque_3', model_select.value,
                                                                   dict(torque_period_options)["Last 30 Days"]),
                                               height=400)
        reworked_plot = pn.pane.Plotly(reworked_components(df, model_select.value), height=400)

        # Theme toggle
        def update_theme(event):
            if dark_mode_toggle.value:
                pn.config.theme = 'dark'
            else:
                pn.config.theme = 'default'

        dark_mode_toggle.param.watch(update_theme, 'value')

        # Update plots function
        def update_plots(model, day_period, week_period, t1_tight, t1_rot, t2_tight, t2_rot, t3_tight, t3_rot):
            df = fetch_data(earliest_date, datetime.now())
            day_period_val = dict(period_options)[day_period]
            week_period_val = dict(week_period_options)[week_period]
            t1_tight_val = dict(torque_period_options)[t1_tight]
            t1_rot_val = dict(torque_period_options)[t1_rot]
            t2_tight_val = dict(torque_period_options)[t2_tight]
            t2_rot_val = dict(torque_period_options)[t2_rot]
            t3_tight_val = dict(torque_period_options)[t3_tight]
            t3_rot_val = dict(torque_period_options)[t3_rot]
            return [
                components_per_day(df, model, day_period_val),
                components_per_week(df, model, week_period_val),
                torque_distribution(df, 'nut_tightening_torque_1', model, t1_tight_val),
                torque_distribution(df, 'free_rotation_torque_1', model, t1_rot_val),
                torque_distribution(df, 'nut_tightening_torque_2', model, t2_tight_val),
                torque_distribution(df, 'free_rotation_torque_2', model, t2_rot_val),
                torque_distribution(df, 'nut_tightening_torque_3', model, t3_tight_val),
                torque_distribution(df, 'free_rotation_torque_3', model, t3_rot_val),
                reworked_components(df, model)
            ]

        # Bind widgets to update plots
        plots = pn.bind(
            update_plots,
            model=model_select,
            day_period=day_period_select,
            week_period=week_period_select,
            t1_tight=torque1_tightening_period,
            t1_rot=torque1_rotation_period,
            t2_tight=torque2_tightening_period,
            t2_rot=torque2_rotation_period,
            t3_tight=torque3_tightening_period,
            t3_rot=torque3_rotation_period
        )

        # Update Plotly panes
        def update_panes(*figs):
            day_plot.object = figs[0]
            week_plot.object = figs[1]
            torque1_tightening_plot.object = figs[2]
            torque1_rotation_plot.object = figs[3]
            torque2_tightening_plot.object = figs[4]
            torque2_rotation_plot.object = figs[5]
            torque3_tightening_plot.object = figs[6]
            torque3_rotation_plot.object = figs[7]
            reworked_plot.object = figs[8]

        # Bind the update function to the widgets
        pn.bind(update_panes, plots)

        # Layout
        layout = pn.Column(
            pn.Row(
                pn.pane.Markdown(
                    "Made by CosTheta Technologies",
                    styles={
                        'background': '#0d6efd',
                        'color': 'white',
                        'padding': '10px',
                        'border-radius': '20px',
                        'position': 'fixed',
                        'top': '10px',
                        'right': '10px',
                        'z-index': '1000',
                        'width': '25%'
                    }
                ),
                width=150,
                align='end'
            ),
            pn.Row(
                pn.pane.Markdown(
                    "# Hub and Disc Assembly Dashboard",
                    styles={'font-weight': '700', 'font-size': '1.25rem', 'color': '#0d6efd'},
                    align='start'
                ),
                styles={'background': 'linear-gradient(to bottom, #f8f9fa, #e9ecef)', 'padding': '20px'}
            ),
            pn.Row(
                dark_mode_toggle,
                align='start'
            ),
            pn.Card(
                pn.Row(model_select, styles={'padding': '10px'}),
                title="Select Model",
                styles={'box-shadow': '0 4px 8px rgba(0,0,0,0.1)', 'border': 'none'}
            ),
            pn.Tabs(
                (
                    "Components per Day",
                    pn.Column(
                        pn.pane.Markdown("📅", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(day_period_select, align='start'),
                        day_plot,
                        pn.pane.Markdown("Components processed per day for the selected model or all models.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Components per Week",
                    pn.Column(
                        pn.pane.Markdown("📅", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(week_period_select, align='start'),
                        week_plot,
                        pn.pane.Markdown("Components processed per week for the selected model or all models.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Nut Tightening Torque 1",
                    pn.Column(
                        pn.pane.Markdown("🔩", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque1_tightening_period, align='start'),
                        torque1_tightening_plot,
                        pn.pane.Markdown("Distribution of Nut Tightening Torque 1 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Free Rotation Torque 1",
                    pn.Column(
                        pn.pane.Markdown("🔧", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque1_rotation_period, align='start'),
                        torque1_rotation_plot,
                        pn.pane.Markdown("Distribution of Free Rotation Torque 1 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Nut Tightening Torque 2",
                    pn.Column(
                        pn.pane.Markdown("🔩", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque2_tightening_period, align='start'),
                        torque2_tightening_plot,
                        pn.pane.Markdown("Distribution of Nut Tightening Torque 2 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Free Rotation Torque 2",
                    pn.Column(
                        pn.pane.Markdown("🔧", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque2_rotation_period, align='start'),
                        torque2_rotation_plot,
                        pn.pane.Markdown("Distribution of Free Rotation Torque 2 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Nut Tightening Torque 3",
                    pn.Column(
                        pn.pane.Markdown("🔩", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque3_tightening_period, align='start'),
                        torque3_tightening_plot,
                        pn.pane.Markdown("Distribution of Nut Tightening Torque 3 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Free Rotation Torque 3",
                    pn.Column(
                        pn.pane.Markdown("🔧", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        pn.Row(torque3_rotation_period, align='start'),
                        torque3_rotation_plot,
                        pn.pane.Markdown("Distribution of Free Rotation Torque 3 values.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                (
                    "Reworked Components",
                    pn.Column(
                        pn.pane.Markdown("🔄", styles={'font-size': '1.5rem', 'text-align': 'center'}),
                        reworked_plot,
                        pn.pane.Markdown("Reworked components marked as 'DUPLICATE' in remarks.",
                                         styles={'color': '#6c757d', 'font-size': '0.9rem'})
                    )
                ),
                dynamic=True
            ),
            styles={'padding': '20px'}
        )
        return layout
    except Exception as e:
        logging.error(f"Error in create_layout: {e}")
        return pn.Column(
            pn.pane.Markdown("# Error", styles={'color': 'red'}),
            pn.pane.Markdown(f"Failed to create dashboard: {e}")
        )


# Function to find a free port
def find_free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
            logging.info(f"Found free port: {port}")
            return port
    except Exception as e:
        logging.error(f"Error finding free port: {e}")
        return 8051


# Start the Panel server
def startMIServer():
    try:
        desired_port = 8050
        logging.info(f"Attempting to start server on port {desired_port}")
        print(f"Panel is running on http://127.0.0.1:{desired_port}/")
        layout = create_layout()
        layout.servable()
        pn.serve(layout, port=desired_port, address='0.0.0.0', show=False,
                 websocket_origin=['127.0.0.1:8050', 'localhost:8050'])
        logging.info(f"Started Panel Hub and Disc Dashboard on port {desired_port}")
    except OSError as e:
        logging.error(f"Port {desired_port} is in use: {e}")
        free_port = find_free_port()
        logging.info(f"Starting server on port {free_port}")
        print(f"Panel is running on http://127.0.0.1:{free_port}/")
        layout = create_layout()
        layout.servable()
        pn.serve(layout, port=free_port, address='0.0.0.0', show=False,
                 websocket_origin=['127.0.0.1:{}'.format(free_port), 'localhost:{}'.format(free_port)])
        logging.info(f"Started Panel Hub and Disc Dashboard on port {free_port}")
    except Exception as e:
        logging.error(f"Failed to start server: {e}")


# if __name__ == '__main__':
#     startMIServer()