import os
import requests

from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import dash_table
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ===========================================
# ENDPOINTS
# ===========================================

ENDPOINTS = {
    "station05": "http://192.168.25.22:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station05",
    "station06": "http://192.168.25.22:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station06",
    "station07": "http://192.168.25.22:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station07",
    "station08": "http://192.168.25.22:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station08"
}


# ===========================================
# DB CONFIG
# ===========================================

PGHOST = os.getenv("PGHOST", "192.168.25.22")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE", "mcs-onr-db")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

DB_URL = f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
ENGINE: Engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=180)


# ===========================================
# QUERIES
# ===========================================

QUERY_CARTON = """
SELECT wo.wave_id, wo.order_id, woc.id, woc.cartonid, woc.status
FROM wave_order wo
INNER JOIN wave_order_carton woc ON wo.id = woc.wave_order_id
WHERE woc.rfid_station = :station
ORDER BY woc.carton_state DESC, woc.updated_at DESC
LIMIT 1
"""

QUERY_CARTON_SKU = """
SELECT sku_code, sku_quantity, sku_quantity_found, status
FROM wave_order_carton_sku
WHERE wave_order_carton_id = :carton_id
"""


# ===========================================
# APP
# ===========================================

app = Dash(__name__)
app.title = "Manual Scanner"


# ===========================================
# LAYOUT
# ===========================================

app.layout = html.Div([

    html.H2("Manual Scanning"),

    dcc.Tabs(
        id="station-tabs",
        value="station05",
        children=[
            dcc.Tab(label="Station 5", value="station05"),
            dcc.Tab(label="Station 6", value="station06"),
            dcc.Tab(label="Station 7", value="station07"),
            dcc.Tab(label="Station 8", value="station08"),
        ]
    ),

    dcc.Interval(
        id="refresh-interval",
        interval=1000,
        n_intervals=0
    ),

    html.Br(),

    dcc.Input(
        id="scan-input",
        type="text",
        placeholder="Scan Carton or EPC",
        debounce=True,
        autoFocus=True,
        style={
            "width": "400px",
            "fontSize": "15px",
            "padding": "10px"
        }
    ),

    html.Br(),
    html.Br(),

    # INFO CARTON
    html.Div(id="carton-info"),

    html.Br(),

    # TABLA SKU
    dash_table.DataTable(
        id="sku-table",
        columns=[
            {"name": "SKU", "id": "sku_code"},
            {"name": "Qty", "id": "sku_quantity"},
            {"name": "Found", "id": "sku_quantity_found"},
            {"name": "Status", "id": "status"},
        ],
        data=[],
        style_cell={"fontSize": "16px", "padding": "6px"},
        style_header={"fontWeight": "bold"},
        style_data_conditional=[
            {
                "if": {"filter_query": '{status} = "match"'},
                "backgroundColor": "#d4edda"
            },
            {
                "if": {"filter_query": '{status} = "unmatch"'},
                "backgroundColor": "#f8d7da"
            }
        ]
    ),

    html.Br(),

    html.H3(id="counter", children="Total scanned: 0"),

    html.Br(),

    dash_table.DataTable(
        id="scan-table",
        columns=[{"name": "Code", "id": "code"}],
        data=[],
        row_deletable=True,
        style_cell={"fontSize": "18px", "padding": "8px"},
        style_header={"fontWeight": "bold"},
        page_size=20
    ),

    html.Br(),

    html.Button(
        "Send Data",
        id="send-button",
        n_clicks=0,
        style={
            "fontSize": "18px",
            "padding": "10px 20px"
        }
    ),

    html.Button(
        "Reset",
        id="reset-button",
        n_clicks=0,
        style={
            "fontSize": "18px",
            "padding": "10px 20px",
            "marginLeft": "10px",
            "backgroundColor": "#e74c3c",
            "color": "white"
        }
    ),

    html.Br(),
    html.Br(),

    html.Div(id="send-result"),

    dcc.Store(id="scan-store", data=[])

])


# ===========================================
# SCAN INPUT
# ===========================================

@app.callback(
    Output("scan-store", "data"),
    Output("scan-input", "value"),
    Output("send-result", "children"),
    Input("scan-input", "value"),
    State("scan-store", "data"),
    State("station-tabs", "value"),
    prevent_initial_call=True
)
def process_scan(value, stored, station):

    if not value:
        raise PreventUpdate

    value = value.strip()

    # For cartonid assigment
    # =========================
    if len(value) == 10:
        try:
            with ENGINE.connect() as conn:
                result =conn.execute(
                    text("SELECT scan_now_open_carton_and_set_station(:cartonid, :station)"),
                    {
                        "cartonid": value,
                        "station": station
                    }
                ).fetchone()
                conn.commit()

                message = result[0] if result else "No response"

            print(f"Carton opened: {value} at {station}")

        except Exception as e:
            print(f"Error opening carton: {str(e)}")

        # no se agrega a la tabla
        return stored, "", message
    
    # EPC scan
    # =========================
    if len(value) == 24:
        if value in stored:
            return stored, "", ""

        stored.append(value)

        return stored, "", ""
    
    #Any other scan is ignored
    # =========================
    return stored, "", ""


# ===========================================
# UPDATE TABLE
# ===========================================

@app.callback(
    Output("scan-table", "data"),
    Output("counter", "children"),
    Input("scan-store", "data")
)
def update_table(data):
    table_data = [{"code": x} for x in data]
    return table_data, f"Total scanned: {len(data)}"


# ===========================================
# RESET
# ===========================================

@app.callback(
    Output("scan-store", "data", allow_duplicate=True),
    Output("scan-input", "value", allow_duplicate=True),
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True
)
def reset_table(n):
    return [], ""

# ===========================================
# Delete rows from table
# ===========================================

@app.callback(
    Output("scan-store", "data", allow_duplicate=True),
    Input("scan-table", "data"),
    prevent_initial_call=True
)
def sync_table_to_store(table_data):

    if table_data is None:
        return []

    return [row["code"] for row in table_data]

# ===========================================
# LOAD CARTON INFO
# ===========================================

@app.callback(
    Output("carton-info", "children"),
    Input("refresh-interval", "n_intervals"),
    Input("scan-input", "value"),
    State("station-tabs", "value")
)
def load_carton(n, scan_value, station):

    try:
        with ENGINE.connect() as conn:
            result = conn.execute(
                text(QUERY_CARTON),
                {"station": station.upper()}
            ).fetchone()

        if not result:
            return "No active carton"

        wave_id, order_id, carton_id, cartonid, status = result

        color_map = {
            "CREATED": "#3498db",
            "MATCHED": "#2ecc71",
            "UNMATCHED": "#e74c3c"
        }

        status_color = color_map.get(status, "#7f8c8d")

        return html.Div([

            html.H2(f"Carton ID: {cartonid}"),

            html.H4([
                "Status: ",
                html.Span(
                    status.upper(),
                    style={
                        "color": "white",
                        "backgroundColor": status_color,
                        "padding": "5px 10px",
                        "borderRadius": "5px",
                        "marginLeft": "5px"
                    }
                )
            ]),

            html.Div(
                f"Wave: {wave_id} | Order: {order_id}",
                style={"marginTop": "5px", "color": "#555"}
            )

        ])

    except Exception as e:
        return f"Error loading carton: {str(e)}"


# ===========================================
# LOAD SKU TABLE
# ===========================================

@app.callback(
    Output("sku-table", "data"),
    Input("refresh-interval", "n_intervals"),
    Input("scan-input", "value"),
    State("station-tabs", "value")
)
def load_skus(n, scan_value, station):

    try:
        with ENGINE.connect() as conn:

            carton = conn.execute(
                text(QUERY_CARTON),
                {"station": station.upper()}
            ).fetchone()

            if not carton:
                return []

            carton_id = carton[2]

            skus = conn.execute(
                text(QUERY_CARTON_SKU),
                {"carton_id": carton_id}
            ).fetchall()

        return [dict(row._mapping) for row in skus]

    except Exception as e:
        print(e)
        return []


# ===========================================
# SEND DATA
# ===========================================

@app.callback(
    Output("send-result", "children", allow_duplicate=True),
    Output("scan-store", "data", allow_duplicate=True),
    Output("scan-input", "value", allow_duplicate=True),
    Input("send-button", "n_clicks"),
    State("scan-store", "data"),
    State("station-tabs", "value"),
    prevent_initial_call=True
)
def send_data(n_clicks, data, station):

    if not data:
        return "No data to send", [], ""

    endpoint = ENDPOINTS.get(station)

    events = []

    now = datetime.now(timezone.utc)
    str_timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+0000"

    for code in data:
        events.append({
            "data": {
                "format": "epc",
                "idHex": code
            },
            "timestamp": str_timestamp
        })

    try:
        r = requests.post(endpoint, json=events)
        return f"Sent {len(data)} items to {station} | status {r.status_code}", [], ""
    except Exception as e:
        return f"Error sending data: {str(e)}", data, ""


# ===========================================
# MAIN
# ===========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8055,
        debug=True
    )