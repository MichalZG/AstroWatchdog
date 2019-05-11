import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import logging
import logging.config
import sys
import configparser 
import subprocess as sub
import os
from datetime import datetime as dt
import filecmp
import utils
from utils import Image
from influxdb import InfluxDBClient
import redis
import pickle 
import uuid 


logging.basicConfig(
    filename='factory.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)
config = configparser.ConfigParser()
config.read('../configs/factory.conf')

files_to_rm = ['*.axy', '*.corr', '*.xyls', '*.match',
               '*.new', '*.rdls', '*.solved', '*.wcs']


class LastData:
    def __init__(self):
        self.object_name = None
        self.uuid = int(uuid.uuid1())


class MyObserver(Observer):

    def run(self):
        while self.should_keep_running():
            try:
                super().run()
            except Exception as e:
                time.sleep(2)


class Handler(PatternMatchingEventHandler):
    file_fingerprint = 0

    @utils.dump_func_name
    def process(self, event):
        
        raw_image_path = event.src_path
        if os.stat(event.src_path).st_mtime == self.file_fingerprint:
            logger.info('No new file')
            return None
        logger.info('Handler: got file!')

        self.file_fingerprint = os.stat(raw_image_path).st_mtime

        image = Image(raw_image_path)
        if not image.read_raw_file():
            return None

        sextractor_output = run_sextractor(raw_image_path)

        if not sextractor_output:
            return None
        image.sextractor_data = sextractor_output

        wcs_image_path, astrometry_flag = run_astrometry(image, raw_image_path)

        if wcs_image_path:
            image.wcs_image_path = wcs_image_path
            image.read_solve_coo()
            target_measurements_flag = image.get_target_measurements()

        image.draw_image()
        send_data(image)


    @utils.dump_func_name
    def on_created(self, event):
        logger.info('on created')
        self.process(event)


    @utils.dump_func_name
    def on_modified(self, event):
        logger.info('on modified')
        self.process(event)


@utils.dump_func_name
def run_sextractor(image_path):
    logger.info('SEXTRACTOR: start')
    image_base_name = os.path.basename(image_path)
    solve_field_command = ['docker', 'run',
                           '-v', config.get(
                                'MAIN', 'DIRECTORY_TO_WATCH') + ':/data',
                           '-v', config.get(
                                'MAIN', 'SEXTRACTOR_CONFIGS_PATH') + ':/configs',
                            'sextractor', 'sex',
                            '/data/' + image_base_name,
                            '-c', '/configs/sex.conf',
                            '-CATALOG_NAME', '/data/' + image_base_name + '.cat'
                           ]

    res = sub.Popen(solve_field_command, stdout=sub.PIPE,
              stderr=sub.PIPE).communicate()
    
    sextractor_output = read_sex_cat(image_path+'.cat')
    logger.info(
        'SEXTRACTOR: {} sextracted starts'.format(len(sextractor_output)))

    return sextractor_output


@utils.dump_func_name
def read_sex_cat(data_path):
    sextractor_columns = ['NUMBER', 'SNR_WIN', 'BACKGROUND', 'FLUX_MAX',
                          'X_IMAGE', 'Y_IMAGE','FWHM_IMAGE']
    output = dict([(column, []) for column in sextractor_columns])

    with open(data_path) as f:
        for line in f:
            line = line.rstrip("\n").split()
            if line[0] == '#':
                continue
            for column_name, column_value in zip(sextractor_columns, line):
                output[column_name].append(float(column_value))

    return output


@utils.dump_func_name
def run_astrometry(image, image_path):
    logger.info('ASTROMETRY: start')
    image_base_name = os.path.basename(image_path)
    solve_field_command = [
        'docker', 'exec', 'nova', 'solve-field',
        '--ra', '%s' % image.coo_target_hdr.ra.deg,
        '--dec', '%s' % image.coo_target_hdr.dec.deg,
        '--radius', '%1.1f' % config.getfloat('SOLVE', 'SOLVE_RADIUS'),
        '--depth', config.get('SOLVE', 'SOLVE_DEPTH'),
        '--cpulimit', '%f' % config.getfloat('SOLVE', 'CPU_LIMIT'),
        '--scale-units', config.get('SOLVE', 'SCALE_UNITS'),
        '--scale-low', '%.5f' % config.getfloat('SOLVE', 'SCALE_LOW'),
        '--scale-high', '%.5f' % config.getfloat('SOLVE', 'SCALE_HIGH'),
        '--overwrite', '--no-verify', '--no-plots',
        '/data_market/' + image_base_name]

    sub.Popen(solve_field_command, stdout=sub.PIPE,
              stderr=sub.PIPE).communicate()

    wcs_file_path = str(image_path).replace('.fits', '.new')

    if os.path.exists(wcs_file_path):
        logger.info('ASTROMETRY: success')
        return wcs_file_path, True

    logger.info('ASTROMETRY: FAILED')
    return None, False


@utils.dump_func_name
def send_data(image):
    data_for_influx = utils.prepare_data_for_influx(image, last_data)
    data_for_modbus = utils.prepare_data_for_modbus(image)

    if influxdb_client.write_points([data_for_influx]):
        print('influx success') 
        signal_status = send_signal_to_monitor()       
        
    return True


@utils.dump_func_name
def send_signal_to_monitor():
    print('signal')
    pass


@utils.dump_func_name
def get_influxdb_client():

    influxdb_client = InfluxDBClient(
        config.get('INFLUXDB', 'ADDRESS'),
        config.get('INFLUXDB', 'PORT'),
        config.get('INFLUXDB', 'USER'),
        config.get('INFLUXDB', 'PASSWORD'),
        config.get('INFLUXDB', 'DB_NAME'))

    return influxdb_client


if __name__ == '__main__':

    influxdb_client = get_influxdb_client()
    last_data = LastData()

    observer = MyObserver()
    event_handler = Handler(
        patterns=config.get(
            'MAIN', 'FILE_TO_WATCH').split(','), ignore_directories=True)
    observer.schedule(event_handler,
        config.get('MAIN', 'DIRECTORY_TO_WATCH'), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
