import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import logging
import plotly.graph_objs as go
import numpy as np
import os
import configparser 
import datetime as dt
from datetime import timedelta
import utils
import random
import pickle
import dateutil.parser as dt_parser
from pprint import pprint as pp
import base64
import time 
import uuid
import pandas as pd

logging.basicConfig(
    filename='monitor.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('../configs/monitor.conf')

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.title = 'AstroWatchdog'

RANGE = [0, 1]

img_width = 1400
img_height = 1200
scale_factor = 0.5
"""
html.H2('Object name', className='my-class', id='obj_name'),
                html.H2('Image time', className='my-class alert', id='im_time'),
                html.H2('Exptime', className='my-class', id='im_exptime'),
                html.H2('Filter', className='my-class', id='im_filter')
"""

app.layout = html.Div([
    html.Div([
        html.Div([
            dcc.Graph(id='image', figure=[]),
        ], className='figure'),
            html.Div([
                html.Div([
                    html.H3('Object name'),
                    html.H3('---', id='object_name_val'),
                ],),
                html.Div([
                    html.H3('Image time '),
                    html.H3('---', id='image_time_val'),
                ], className='it'),
                html.Div([
                    html.H3('Exptime '),                        
                    html.H3('---', id='image_exptime_val'),
                ], className='et'),
                html.Div([
                    html.H3('Filter'),                        
                    html.H3('---', id='image_filter_val', 
                        ),
                ],),
                html.Div([
                    html.H3('Last data [min]',),                        
                    html.H3('---', id='time_from_last_val'),
                ]),
            ], className='data')
    ]),
    html.Div([
        dcc.Graph(id='snr_graph', className='snr_graph'),
        html.Div([
                html.H6('No', className='npf_label'),
                dcc.Input(id='data_len_input', type='number',
                    value=20, className='npf_val'),
        ]),
        html.Div([
                html.H6('Filter', className='fts_label'),
                dcc.Input(id='data_filter', type='text',
                    value='', className='fts_val'),
        ]),
        html.Button('Refresh', id='refresh_button',
                            className='refresh_button'),
    ], className='graph_1_box'),
    dcc.Interval(
            id='interval',
            interval=5*1000),
    html.Div(id='data_div', children=0, style={'display': 'none'}),
    html.Div(id='test_data_div', children=0, style={'display': 'none'}),
], style={'backgroundColor': 'black'}, className='main')


@app.callback([Output('data_div', 'children'),
               Output('data_div', 'data-last'),
               Output('data_div', 'data-main')],
              [Input('refresh_button', 'n_clicks_timestamp'),
               Input('interval', 'n_intervals')])
@utils.dump_func_name
def update_data(_, __):
    last_point, data = utils.get_influxdb_data(influxdb_client,
                                               influxdb_df_client)

    return time.time(), last_point, data


@app.callback([Output('object_name_val', 'children'),
               Output('image_time_val', 'children'),
               Output('image_exptime_val', 'children'),
               Output('image_filter_val', 'children'),
               Output('time_from_last_val', 'children'),
               Output('time_from_last_val', 'style')],
              [Input('data_div', 'data-last')])
@utils.dump_func_name
def update_image_info(data):
    image_datetime = dt_parser.parse(data['image_time'])
    image_time_str = image_datetime.time().strftime("%H:%M:%S")
    minutes_from_last = (
        image_datetime - dt.datetime.utcnow()).total_seconds() / 60.

    if minutes_from_last < -5:
        time_from_last_val_style = {'color': 'red'}
    else:
        time_from_last_val_style = {}

    return (data['OBJECT'], image_time_str, data['EXPTIME'], data['FILTER'],
            int(minutes_from_last), time_from_last_val_style)


@app.callback(Output('image', 'figure'),
             [Input('data_div', 'children')])
@utils.dump_func_name
def update_image(_):

    encoded_image = base64.b64encode(
        open('./assets/main_plot.png', 'rb').read())

    layout = go.Layout(
        xaxis = go.layout.XAxis(
            visible = False,
            range = [10, img_width*scale_factor]),
        yaxis = go.layout.YAxis(
            visible=False,
            range = [10, img_height*scale_factor],
            scaleanchor = 'x'),
        width = img_width*scale_factor,
        height = img_height*scale_factor,
        margin = {'l': 0, 'r': 0, 't': 0, 'b': 0},
        images = [go.layout.Image(
            x=0,
            sizex=img_width*scale_factor,
            y=img_height*scale_factor,
            sizey=img_height*scale_factor,
            xref="x",
            yref="y",
            opacity=1.0,
            layer="below",
            sizing="stretch",
            source='data:image/png;base64,{}'.format(encoded_image.decode()))
        ],
        paper_bgcolor='rgba(0,20,20,20)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    figure={'data': [],
            'layout': layout}

    return figure


@app.callback(Output('snr_graph', 'figure'),
             [Input('data_div', 'data-main')],
             [State('snr_graph', 'figure')])
@utils.dump_func_name
def create_snr_figure(data, figure):

    fig_data = []
    # try:
    #     visibilities = {
    #         d.get('name'): d.get('visible') for d in figure['data']}
    # except TypeError:
    #     visibilities = {}

    for name, value in data.items():
        # index is first column not dt index
        # FIXME
        value = pd.read_json(value)
        value = value.sort_values(by='image_time')
        value = value.tail(50)
        logger.info(value)
        logger.info('snr_graph value: {}'.format(value['SNR_WIN']))
        x = value.image_time
        y = value.SNR_WIN
        trace = go.Scatter(
            x=x,
            y=y,
            name=name,
            # visible='legendonly',
            mode = 'lines+markers')
        fig_data.append(trace)

    figure = {
        'data': fig_data,
        'layout': go.Layout(title='SNR',
                            paper_bgcolor='rgba(120,120,120,120)',
                            plot_bgcolor='rgba(80,80,80,80)'
                            )}

    return figure

# @app.callback([Output('data_div', 'data-tmp')],
#               [Input('object_name', 'value'),
#                Input('image_time', 'value'),
#                Input('image_exptime', 'value'),
#                Input('image_filter', 'value')])
# def test(a, b, c, d):
#     pass
# @app.callback(Output('peak_graph', 'figure'),
#              [Input('data_div', 'children')],
#              [State('peak_graph', 'figure')])
# @utils.dump_func_name
# def create_peak_figure(update, figure):

#     if True:
#         redis_data = pickle.loads(redis_client.get('state_old'))

#         time_start = dt_parser.parse(
#             ' '.join([redis_data['DATE-OBS'],
#                       redis_data['TIME-OBS']])) - timedelta(hours=1)
#         object_name = redis_data['OBJECT']

#         data = utils.get_influxdb_data(object_name,
#             time_start.isoformat())

#         fig_data = []
#         try:
#             visibilities = {
#                 d.get('name'): d.get('visible') for d in figure['data']}
#         except TypeError:
#             visibilities = {}

#         for name, value in data.items():
#             value = value.dropna()
#             trace = go.Scatter(
#                 x=value.index,
#                 y=value['FLUX_MAX'],
#                 name=name,
#                 # visible='legendonly',
#                 mode = 'lines+markers')
#             fig_data.append(trace)

#         figure = {
#             'data': fig_data,
#             'layout': go.Layout(title='PEAK',
#                                 paper_bgcolor='rgba(0,0,0,0)',
#                                 plot_bgcolor='rgba(0,0,0,0)')}

#     return figure


# @app.callback(Output('fwhm_graph', 'figure'),
#              [Input('data', 'children')],
#              [State('fwhm_graph', 'figure')])
# @utils.dump_func_name
# def create_fwhm_figure(update, figure):
#     if update:
#         redis_data = pickle.loads(redis_client.get('state_old'))
#         print(redis_data)
#         time_start = dt_parser.parse(
#             ' '.join([redis_data['DATE-OBS'],
#                       redis_data['TIME-OBS']])) - timedelta(hours=12)
#         object_name = redis_data['OBJECT']

#         data = utils.get_influxdb_data(object_name,
#             time_start.isoformat())

#         fig_data = []
#         try:
#             visibilities = {d.get('name'): d.get(
#                 'visible') for d in figure['data']}
#         except TypeError:
#             visibilities = {}

#         for name, value in data.items():
#             trace = go.Scatter(
#                 x=value.index,
#                 y=value['FWHM_IMAGE'],
#                 name=name,
#                 visible=visibilities.get(name) or 'legendonly',
#                 mode = 'lines+markers')
#             fig_data.append(trace)

#         figure = {
#             'data': fig_data}

#     return figure
    
app.css.append_css({
        "external_url": "/static/main.css"})

if __name__ == '__main__':

    influxdb_client, influxdb_df_client = utils.get_influxdb_clients()
    app.run_server(host="0.0.0.0", port=8050, debug=False, threaded=False)
