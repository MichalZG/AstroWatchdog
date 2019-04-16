from influxdb import InfluxDBClient
import configparser 
config = configparser.ConfigParser()
config.read('../configs/factory.conf')
import time
import itertools
from datetime import datetime as dt
import random
import redis
import pickle


def send_data_to_influxdb(object_name, filter_name):

    tags = {}
    fields = {}

    tags['FILTER'] = filter_name
    tags['OBJECT'] = object_name
    tags['OBSERVER'] = 'NOBODY'

    fields['EXPTIME'] = 5.
    fields['FWHM'] = random.randrange(3, 6)
    fields['RA_HDR'] = 11.11
    fields['DEC_HDR'] = 12.12
    fields['FLUX_BEST'] = random.randrange(100, 200)
    fields['X_IMAGE'] = random.randrange(100, 200)
    fields['Y_IMAGE'] = random.randrange(100, 200)

    time = dt.now().time().isoformat()


    message_body = {
            "measurement": "image",
            "tags": tags,
            "time": time,
            "fields": fields
            }

    if influxdb_client.write_points([message_body]):
        print('influx success')


    return True


def send_data_to_redis(object_name):
    message_body = {}

    message_body['OBJECT'] = object_name
    message_body['TIME-OBS'] = dt.now().time().isoformat()
    message_body['DATE-OBS'] = dt.now().date().isoformat()

    print(message_body)
    if redis_client.set('state_new', pickle.dumps(message_body)):
        print('redis OK')

    return True


def get_influxdb_client():
    influxdb_client = InfluxDBClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    return influxdb_client


def get_redis_client():
    redis_client = redis.Redis(host=config.get('REDIS', 'ADDRESS'),
                               port=config.get('REDIS', 'PORT'),
                               db=config.get('REDIS', 'DB_NAME'))
    redis_client.set('state_new', pickle.dumps({'temp': None}))
    redis_client.set('state_old', pickle.dumps({'temp': None}))

    return redis_client


if __name__ == '__main__':
    influxdb_client = get_influxdb_client()
    redis_client = get_redis_client()

    c = 0
    object_names = ['EX_DRA'] * 20
    object_names.extend(['HU_AQR'] * 20)
    filter_names = ['B', 'V', 'R', 'I'] * 10

    for object_name, filter_name in itertools.cycle(
        zip(object_names, filter_names)):

        send_data_to_influxdb(object_name, filter_name)
        send_data_to_redis(object_name)
        time.sleep(2)
