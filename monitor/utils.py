import configparser 
import logging
from datetime import datetime as dt
from influxdb import InfluxDBClient, DataFrameClient
import uuid


logger = logging.getLogger(__name__)
config = configparser.ConfigParser()
config.read('../configs/monitor.conf')


def dump_func_name(func):
    def echo_func(*func_args, **func_kwargs):
        print('Start func: {}'.format(func.__name__))
        return func(*func_args, **func_kwargs)
    return echo_func



@dump_func_name
def get_influxdb_clients():
    # FIXME
    influxdb_client = InfluxDBClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    influxdb_df_client = DataFrameClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    return influxdb_client, influxdb_df_client


@dump_func_name
def get_influxdb_data(client, df_client, refresh_timestamp):

    last_element_query = 'select * from image order by desc limit 200'
    last_result = list(client.query(last_element_query).get_points())[-1]
    
    last_uuid = last_result['uuid']
    # refresh_timestamp = '2015-08-18T00:12:00Z'
    logger.info(refresh_timestamp)
    if refresh_timestamp is None: refresh_timestamp = 0
    refresh_datetime = dt.fromtimestamp(refresh_timestamp / 1000)
    refresh_datetime = refresh_datetime.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    data_query = 'select * from image where uuid = \'{}\' and time > \'{}\' group by "FILTER" \
                  order by desc'.format(last_uuid, refresh_datetime)
    
    #data_query = 'select * from image group by "FILTER" order by asc limit 100'.format(
    #                 uuid
    #                )
    result = df_client.query(data_query)
    if result:
        result = dict(
            [(k[1][0][1], v.reset_index(
                level=0).to_json()) for k, v in result.items()])
    return last_result, result


# @dump_func_name
# def get_last_influxdb_data():

#     query_body = 'select * from image order by desc limit 1'
                  
#     client = DataFrameClient(
#         config.get('INFLUXDB', 'ADDRESS'),
#         config.get('INFLUXDB', 'PORT'),
#         config.get('INFLUXDB', 'USER'),
#         config.get('INFLUXDB', 'PASSWORD'),
#         config.get('INFLUXDB', 'DB_NAME'))

#     result = client.query(query_body)
#     logger.info('result: {}'.format(result))
#     result = dict([(k[1][0][1], v) for k, v in result.items()])

#     return result
