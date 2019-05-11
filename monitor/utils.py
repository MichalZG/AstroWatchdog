from influxdb import InfluxDBClient, DataFrameClient
import configparser 
import logging
import datetime as dt


logger = logging.getLogger(__name__)
config = configparser.ConfigParser()
config.read('../configs/monitor.conf')


def dump_func_name(func):
    def echo_func(*func_args, **func_kwargs):
        print('Start func: {}'.format(func.__name__))
        return func(*func_args, **func_kwargs)
    return echo_func



@dump_func_name
def get_influxdb_client():
    influxdb_client = InfluxDBClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    return influxdb_client


@dump_func_name
def get_influxdb_data(object_name, time_start):

    query_body = 'select * from image where time >= \'{}Z\' and OBJECT = \'{}\' \
                  group by "FILTER" order by desc limit {}'.format(
                    time_start, object_name, config.get(
                        'INFLUXDB', 'LIMIT')
                    )
                  
    client = DataFrameClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    result = client.query(query_body)
    logger.info('result: {}'.format(result))
    result = dict([(k[1][0][1], v) for k, v in result.items()])

    return result


@dump_func_name
def get_last_influxdb_data():

    query_body = 'select * from image order by desc limit 1'
                  
    client = DataFrameClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    result = client.query(query_body)
    logger.info('result: {}'.format(result))
    result = dict([(k[1][0][1], v) for k, v in result.items()])

    return result