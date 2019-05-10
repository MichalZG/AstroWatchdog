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
from datetime import datetime as dt
from datetime import timedelta
import utils
import random
import pickle
import dateutil.parser as dt_parser
from pprint import pprint as pp
import base64
import time 


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
                            dcc.Graph(id='temp1'),
                        ], className='row'),
                        html.Div([
                            dcc.Graph(id='temp2'),

                        ], className='row'),
                    ], className='six columns'),
                    html.Div([
                        html.H2('Object name', className='my-class', id='obj_name'),
                        html.H2('Image time', className='my-class alert', id='im_time'),
                        html.H2('Exptime', className='my-class', id='im_exptime'),
                        html.H2('Filter', className='my-class', id='im_filter'),
                        html.H2('Object name', className='my-class', id='obj_name1'),
                        html.H2('Image time', className='my-class alert', id='im_time1'),
                        html.H2('Exptime', className='my-class', id='im_exptime1'),
                        html.H2('Filter', className='my-class', id='im_filter1')
                    ], className='six columns'),
                ], className='row')
            ], className='seven columns')
    ], className='row'),
    html.Div([
        html.Div([
            dcc.Graph(id='snr_graph'),
        ], className='six columns'),
        html.Div([
            dcc.Graph(id='peak_graph', figure=[]),
        ], className='six columns'),
    ], className='row'),

    dcc.Interval(id='updater', interval=2000, n_intervals=0),
    html.Div(id='trigger', children=0, style={'display': 'none'}),
])


@app.callback(Output('trigger', 'children'),
             [Input('updater', 'n_intervals')])
@utils.dump_func_name
def update_state(_):
    raw_state_new = redis_client.get('state_new')
    state_new = pickle.loads(raw_state_new)
    raw_state_old = redis_client.get('state_old')
    state_old = pickle.loads(redis_client.get('state_old'))
    print('state_old', state_old)
    print('state_new', state_new)
    if state_old == state_new:
        return False
    redis_client.set('state_old', raw_state_new)

    return True


@app.callback([Output('obj_name', 'children'),
               Output('im_time', 'children'),
               Output('im_exptime', 'children'),
               Output('im_filter', 'children')],
              [Input('trigger', 'children')])
@utils.dump_func_name
def update_obj_name(_):
    raw_state_new = redis_client.get('state_new')
    state_new = pickle.loads(raw_state_new)

    obj_name_text = ' '.join(['Object name: ', state_new['OBJECT']])
    im_time_text = ' '.join(['Image time: ', state_new['TIME-OBS']])
    im_exptime = ' '.join(['Exptime: ', str(state_new['EXPTIME'])])
    im_filter_text = ' '.join(['Filter: ', state_new['FILTER']])

    return obj_name_text, im_time_text, im_exptime, im_filter_text


@app.callback(Output('image', 'figure'),
              [Input('trigger', 'children')])
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
             [Input('trigger', 'children')],
             [State('snr_graph', 'figure')])
@utils.dump_func_name
def create_snr_figure(update, figure):

    if True:
        redis_data = pickle.loads(redis_client.get('state_old'))

        time_start = dt_parser.parse(
            ' '.join([redis_data['DATE-OBS'],
                      redis_data['TIME-OBS']])) - timedelta(hours=1)
        object_name = redis_data['OBJECT']

        data = utils.get_influxdb_data(object_name,
            time_start.isoformat())

        fig_data = []
        try:
            visibilities = {
                d.get('name'): d.get('visible') for d in figure['data']}
        except TypeError:
            visibilities = {}

        for name, value in data.items():
            value = value.dropna()
            trace = go.Scatter(
                x=value.index,
                y=value['SNR_WIN'],
                name=name,
                # visible='legendonly',
                mode = 'lines+markers')
            fig_data.append(trace)

        figure = {
            'data': fig_data,
            'layout': go.Layout(title='SNR',
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)'
                                )}

    return figure


@app.callback(Output('peak_graph', 'figure'),
             [Input('trigger', 'children')],
             [State('peak_graph', 'figure')])
@utils.dump_func_name
def create_peak_figure(update, figure):

    if True:
        redis_data = pickle.loads(redis_client.get('state_old'))

        time_start = dt_parser.parse(
            ' '.join([redis_data['DATE-OBS'],
                      redis_data['TIME-OBS']])) - timedelta(hours=1)
        object_name = redis_data['OBJECT']

        data = utils.get_influxdb_data(object_name,
            time_start.isoformat())

        fig_data = []
        try:
            visibilities = {
                d.get('name'): d.get('visible') for d in figure['data']}
        except TypeError:
            visibilities = {}

        for name, value in data.items():
            value = value.dropna()
            trace = go.Scatter(
                x=value.index,
                y=value['FLUX_MAX'],
                name=name,
                # visible='legendonly',
                mode = 'lines+markers')
            fig_data.append(trace)

        figure = {
            'data': fig_data,
            'layout': go.Layout(title='PEAK',
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)')}

    return figure


# @app.callback(Output('fwhm_graph', 'figure'),
#              [Input('trigger', 'children')],
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

    influxdb_client = utils.get_influxdb_client()
    redis_client = utils.get_redis_client()
    app.run_server(host="0.0.0.0", port=8050, debug=True, threaded=False)
