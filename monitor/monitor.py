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
        ], className='five columns'),
            html.Div([
                html.Div([
                    html.Div([
                        html.Div([
                            html.Button('Refresh', id='refresh_button',
                                        className='six columns'),
                            dcc.Input(id='refresh_interval_input', type='number',
                                      value=2, className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Object name', className='six columns'),
                            html.H2('---', id='object_name_val',
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Image time', className='six columns'),
                            html.H2('---', id='image_time_val',
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Exptime', className='six columns'),                        
                            html.H2('---', id='image_exptime_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Filter', className='six columns'),                        
                            html.H2('---', id='image_filter_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Peak', className='six columns'),                        
                            html.H2('---', id='object_peak_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('SNR', className='six columns'),                        
                            html.H2('---', id='object_snr_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('FWHM', className='six columns'),                        
                            html.H2('---', id='object_fwhm_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Dist to center', className='six columns'),                        
                            html.H2('---', id='object_center_dist_val', 
                                className='six columns'),
                        ], className='row'),
                        html.Div([
                            html.H2('Last [min]', className='six columns'),                        
                            html.H2('---', id='time_from_last_val', 
                                className='six columns'),
                        ], className='row'),
                    ], className='six columns'),
                ], className='row')
            ], className='seven columns')
    ], className='row'),
    html.Div([
        html.Div([
            html.Div([
                html.H2('Number of points by filter', className='six columns'),
                html.H2('Filter to show', className='six columns'),
            ], className='row'),
            html.Div([
                dcc.Input(id='data_len_input', type='number',
                    value=20, className='six columns'),
                dcc.Input(id='data_filter', type='text',
                    value='', className='six columns'),
            ], className='row'),
        ], className='row'),
        html.Div([
            html.Div([
                dcc.Graph(id='snr_graph'),
            ], className='six columns'),
            html.Div([
                dcc.Graph(id='peak_graph', figure=[]),
            ], className='six columns'),
        ], className='row'),
    
        html.Div([
                dcc.Graph(id='xy_graph'),
            ], className='six columns'),

    ], className='row'),

    dcc.Interval(
            id='interval',
            interval=10*1000),
    html.Div(id='data_div', children=0, style={'display': 'none'}),
    html.Div(id='test_data_div', children=0, style={'display': 'none'}),
])

@app.callback([Output('interval', 'interval')],
              [Input('refresh_button', 'n_clicks_timestamp'),
               Input('refresh_interval_input', 'value')])
@utils.dump_func_name
def set_interval(_, interval_value):
    print(interval_value)
    return int(interval_value)


@app.callback([Output('data_div', 'data-last'),
               Output('data_div', 'data-main')],
              [Input('refresh_button', 'n_clicks_timestamp'),
               Input('interval', 'n_intervals')])
@utils.dump_func_name
def update_data(_, __):
    last_point, data = utils.get_influxdb_data(influxdb_client,
                                               influxdb_df_client)

    return last_point, data


@app.callback([Output('object_name_val', 'children'),
               Output('image_time_val', 'children'),
               Output('image_exptime_val', 'children'),
               Output('image_filter_val', 'children'),
               Output('time_from_last_val', 'children'),
               Output('object_peak_val', 'children'),
               Output('object_snr_val', 'children'),
               Output('object_fwhm_val', 'children'),
               Output('object_center_dist_val', 'children'),
               ],
              [Input('data_div', 'data-last')])
@utils.dump_func_name
def update_image_info(data):
    image_datetime = dt_parser.parse(data['image_time'])
    image_time_str = image_datetime.time().strftime("%H:%M:%S")
    minutes_from_last = (
        image_datetime - dt.datetime.utcnow()).total_seconds() / 60.
    object_peak = data.get('FLUX_MAX', '?')
    object_snr = data.get('SNR_WIN', '?')
    object_fwhm = data.get('FWHM_IMAGE', '?')

    object_center_dist = utils.calculate_distance_from_center(data)

    return (data['OBJECT'], image_time_str, data['EXPTIME'], data['FILTER'],
            int(minutes_from_last), int(object_peak), object_snr, object_fwhm,
            int(object_center_dist))


@app.callback(Output('image', 'figure'),
             [Input('data_div', 'data-main')])
@utils.dump_func_name
def update_image(_):

    encoded_image = base64.b64encode(
        open('./assets/main_plot.png', 'rb').read())

    layout = go.Layout(
        xaxis = go.layout.XAxis(visible = False,
            range = [0, img_width*scale_factor]),
        yaxis = go.layout.YAxis(
            visible=False,
            range = [0, img_height*scale_factor],
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
        paper_bgcolor='rgba(0,0,0,0)',
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

    for name, value in data.items():
        value = pd.read_json(value)
        if 'SNR_WIN' in value:
            x = value.image_time
            y = value['SNR_WIN']
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
                            # paper_bgcolor='rgba(0,0,0,0)',
                            # plot_bgcolor='rgba(0,0,0,0)'
                            )}

    return figure


@app.callback(Output('peak_graph', 'figure'),
             [Input('data_div', 'data-main')],
             [State('peak_graph', 'figure')])
@utils.dump_func_name
def create_peak_figure(data, figure):

    fig_data = []

    for name, value in data.items():
        value = pd.read_json(value)
        if 'FLUX_MAX' in value:
            x = value.image_time
            y = value['FLUX_MAX']
            trace = go.Scatter(
                x=x,
                y=y,
                name=name,
                # visible='legendonly',
                mode = 'lines+markers')
            fig_data.append(trace)

    figure = {
        'data': fig_data,
        'layout': go.Layout(title='PEAK',
                            # paper_bgcolor='rgba(0,0,0,0)',
                            # plot_bgcolor='rgba(0,0,0,0)'
                            )}

    return figure


@app.callback(Output('xy_graph', 'figure'),
             [Input('data_div', 'data-main')],
             [State('xy_graph', 'figure')])
@utils.dump_func_name
def create_peak_figure(data, figure):

    fig_data = []

    for name, value in data.items():
        value = pd.read_json(value)
        if 'X_IMAGE' in value and 'Y_IMAGE' in value:
            x = value['X_IMAGE']
            y = value['Y_IMAGE']
            trace = go.Scatter(
                x=x,
                y=y,
                name=name,
                # visible='legendonly',
                mode = 'lines+markers')
            fig_data.append(trace)

    figure = {
        'data': fig_data,
        'layout': go.Layout(title='PEAK',
                            width=400,
                            height=400,
                            # paper_bgcolor='rgba(0,0,0,0)',
                            # plot_bgcolor='rgba(0,0,0,0)'
                            )}

    return figure

    
app.css.append_css({
        "external_url": "/static/main.css"})

if __name__ == '__main__':

    influxdb_client, influxdb_df_client = utils.get_influxdb_clients()
    app.run_server(host="0.0.0.0", port=8050, debug=False, threaded=False)
