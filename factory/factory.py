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
    logger.info('sex image: {}'.format(image_path))
    solve_field_command = ['docker', 'run',
                           '-v', config.get(
                                'MAIN', 'DIRECTORY_TO_WATCH') + ':/data',
                           '-v', config.get(
                                'MAIN', 'SEXTRACTOR_CONFIGS_PATH') + ':/configs',
                            'sextractor', 'sex',
                            '/data/' + image_base_name,
                            '-c', '/configs/sex.conf',
                            '-CATALOG_NAME', '/data/' + image_base_name + '.cat',
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

    from astropy.io import fits as afits
    with afits.open(data_path) as hdul:
        data = hdul[2].data  # LDAC_OBJECTS extension
        for column_name in sextractor_columns:
            col_data = data[column_name]
            output[column_name] = list(col_data)

    return output


@utils.dump_func_name
def run_astrometry(image, image_path):
    logger.info('ASTROMETRY: start')
    image_base_name = os.path.basename(image_path)

    # Build a simple FITS xylist from the SExtractor FITS_LDAC catalog
    cat_path = image_path + '.cat'
    xyls_path = image_path + '.xyls'
    try:
        from astropy.io import fits as afits
        import numpy as np
        with afits.open(cat_path) as hdul:
            cat_data = hdul[2].data  # LDAC_OBJECTS extension
            x = np.array(cat_data[config.get('SOLVE', 'X_COLUMN')], dtype=np.float64)
            y = np.array(cat_data[config.get('SOLVE', 'Y_COLUMN')], dtype=np.float64)
            mag = np.array(cat_data[config.get('SOLVE', 'SORT_COLUMN')], dtype=np.float64)
        col_x = afits.Column(name='X', array=x, format='D')
        col_y = afits.Column(name='Y', array=y, format='D')
        col_mag = afits.Column(name=config.get('SOLVE', 'SORT_COLUMN'), array=mag, format='D')
        hdu = afits.BinTableHDU.from_columns([col_x, col_y, col_mag])
        hdu.writeto(xyls_path, overwrite=True)
        logger.info('ASTROMETRY: wrote xylist with {} sources'.format(len(x)))
    except Exception as e:
        logger.error('ASTROMETRY: failed to build xylist: {}'.format(e))
        return None, False

    # Get image dimensions for solve-field
    with afits.open(image_path) as hdul:
        width = hdul[0].header.get('NAXIS1', 0)
        height = hdul[0].header.get('NAXIS2', 0)

    xyls_container_path = '/data_market/' + image_base_name + '.xyls'
    new_fits_path = '/data_market/' + image_base_name + '.new'
    solve_field_command = [
        'docker', 'exec', 'nova', 'solve-field',
        '--ra', '%s' % image.coo_target_hdr.ra.deg,
        '--dec', '%s' % image.coo_target_hdr.dec.deg,
        '--radius', '%1.1f' % config.getfloat('SOLVE', 'SOLVE_RADIUS'),
        '--cpulimit', '%f' % config.getfloat('SOLVE', 'CPU_LIMIT'),
        '--scale-units', config.get('SOLVE', 'SCALE_UNITS'),
        '--scale-low', '%.5f' % config.getfloat('SOLVE', 'SCALE_LOW'),
        '--scale-high', '%.5f' % config.getfloat('SOLVE', 'SCALE_HIGH'),
        '--width', '%d' % width,
        '--height', '%d' % height,
        '--x-column', 'X',
        '--y-column', 'Y',
        '--sort-column', config.get('SOLVE', 'SORT_COLUMN'),
        '--sort-ascending',
        '--new-fits', new_fits_path,
        '--overwrite', '--no-plots',
        xyls_container_path]

    sub.Popen(solve_field_command, stdout=sub.PIPE,
              stderr=sub.PIPE).communicate()

    # For xylist input, solve-field creates .wcs (header only, no image data).
    # Build .new by copying the original FITS and appending WCS header cards.
    wcs_file_path = image_path + '.wcs'
    new_file_path = image_path + '.new'

    if os.path.exists(wcs_file_path):
        try:
            from astropy.io import fits as afits
            # Read WCS header from .wcs
            with afits.open(wcs_file_path) as wcs_hdul:
                wcs_hdr = wcs_hdul[0].header
            # Copy original image and update its header with WCS
            with afits.open(image_path) as img_hdul:
                hdr = img_hdul[0].header
                # Remove existing WCS keys
                for key in list(hdr.keys()):
                    if key.startswith(('CTYPE', 'CRVAL', 'CRPIX', 'CUNIT',
                                       'CD', 'CDELT', 'PC', 'WCSAXES',
                                       'EQUINOX', 'LONPOLE', 'LATPOLE')):
                        del hdr[key]
                # Add WCS keys from solved header
                for key, val in wcs_hdr.items():
                    if key not in ('SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND'):
                        hdr[key] = val
                img_hdul[0].header = hdr
                img_hdul.writeto(new_file_path, overwrite=True)
            logger.info('ASTROMETRY: success, wrote {}'.format(new_file_path))
            return new_file_path, True
        except Exception as e:
            logger.error('ASTROMETRY: failed to build .new: {}'.format(e))

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
