import requests

from dash import Dash, html, dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import dash_table
from datetime import datetime, timezone


# Endpoints dictionary
# ===========================================

ENDPOINTS = {

    "station1": "http://192.168.25.48:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station01",
    "station2": "http://192.168.25.48:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station02",
    "station3": "http://192.168.25.48:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station03",
    "station4": "http://192.168.25.48:9087/v1/fbm/mcs/rfid/lam/brazil/onr/epcdata/station04"

}

# App
# ================================================

app = Dash(__name__)

app.title = "Manual Scanner"

# Layout
# ==================================================

app.layout = html.Div([

    html.H2("Manual Scanning"),

    dcc.Tabs(
        id="station-tabs",
        value="station1",
        children=[

            dcc.Tab(label="Station 1", value="station1"),
            dcc.Tab(label="Station 2", value="station2"),
            dcc.Tab(label="Station 3", value="station3"),
            dcc.Tab(label="Station 4", value="station4"),

        ]
    ),

    html.Br(),

    dcc.Input(
        id="scan-input",
        type="text",
        placeholder="Scan code and press ENTER",
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

    html.H3(id="counter", children="Total scanned: 0"),

    html.Br(),

    dash_table.DataTable(

        id="scan-table",

        columns=[
            {"name": "Code", "id": "code"}
        ],

        data=[],

        style_cell={
            "fontSize": "18px",
            "padding": "8px"
        },

        style_header={
            "fontWeight": "bold"
        },

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

    html.Br(),
    html.Br(),

    html.Div(id="send-result"),

    # memoria local
    dcc.Store(id="scan-store", data=[])

])

# Scan
# =====================================================

@app.callback(

    Output("scan-store", "data"),
    Output("scan-input", "value"),

    Input("scan-input", "value"),

    State("scan-store", "data"),

    prevent_initial_call=True

)
def process_scan(value, stored):

    if not value:
        raise PreventUpdate

    value = value.strip()

    if value in stored:
        return stored, ""

    stored.append(value)

    return stored, ""


# =====================================================
# ACTUALIZAR TABLA
# =====================================================

@app.callback(

    Output("scan-table", "data"),
    Output("counter", "children"),

    Input("scan-store", "data")

)
def update_table(data):

    table_data = [{"code": x} for x in data]

    return table_data, f"Total scanned: {len(data)}"


# =====================================================
# ENVIO A ENDPOINT
# =====================================================

@app.callback(

    Output("send-result", "children"),
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

    payload = {
        "events": events
    }

    try:

        r = requests.post(endpoint, json=payload)

        return f"Sent {len(data)} items to {station} | status {r.status_code}", [], ""
    except Exception as e:

        return f"Error sending data: {str(e)}", data, ""


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8055,
        debug=True
    )