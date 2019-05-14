import configparser
import logging
from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.wcs import WCS
import numpy as np
import matplotlib
matplotlib.use('Agg')
import aplpy
import os
import datetime as dt
import time 
import uuid


logger = logging.getLogger(__name__)
config = configparser.ConfigParser()
config.read('../configs/factory.conf')


def dump_func_name(func):
    def echo_func(*func_args, **func_kwargs):
        print('Start func: {}'.format(func.__name__))
        return func(*func_args, **func_kwargs)
    return echo_func


class Image:
    def __init__(self, image_path):
        self.image_path = image_path
        self.image_data = None
        self.wcs_image_path = None
        self.wcs_image_data = None
        self.coo_target_hdr = None
        self.coo_target_image = None
        self.coo_center = None
        self.sextractor_data = None
        self.target_measurements = None


    @dump_func_name
    def read_raw_file(self):
        logger.info('FILE: read')
        try:
            time.sleep(0.1)
            hdu = fits.open(self.image_path)
        except UnboundLocalError:
            return False

        self.image_data = hdu[0]

        hdr = self.image_data.header
        self.coo_target_hdr = self.parse_coordinates(
            hdr[config.get('FITS', 'RA_KEY')], 
            hdr[config.get('FITS', 'DEC_KEY')],
            (u.hour, u.deg))

        return True


    @dump_func_name
    def read_solve_coo(self):

        try:
            hdu = fits.open(self.wcs_image_path)
            self.wcs_image_data = hdu[0]
        except:
            return False

        w = WCS(self.wcs_image_data.header)
        wx, wy = w.wcs_pix2world(self.wcs_image_data.header['NAXIS1']/2,
                                 self.wcs_image_data.header['NAXIS2']/2, 1)
        self.coo_center = self.parse_coordinates(wx, wy, unit='deg')

        return True


    @dump_func_name
    def draw_image(self):

        if not self.wcs_image_data:
            fig = aplpy.FITSFigure(data=self.image_data)
        else:    
            fig = aplpy.FITSFigure(data=self.wcs_image_data, north=True)

            plot_points = np.array(
                [np.array([self.coo_target_hdr.ra.deg,
                           self.coo_target_hdr.dec.deg]),
                 np.array([self.coo_center.ra.deg,
                           self.coo_center.dec.deg])]).T

            fig.show_lines([plot_points], color='red', linewidth=1, alpha=1)
            fig.show_markers(
                self.coo_target_hdr.ra.deg,
                self.coo_target_hdr.dec.deg,
                layer='marker_set_1', edgecolor='red',
                facecolor='none', marker='o', s=100, alpha=1)
            if self.target_measurements:
                fig.show_markers(self.coo_target_image.ra.deg,
                                 self.coo_target_image.dec.deg,
                                 layer='marker_set_2', edgecolor='green',
                                 facecolor='none', marker='o', s=100, alpha=1)

        fig.set_theme('publication')
        fig.show_grayscale()
        fig.save(os.path.join(
            config.get('MAIN', 'DIRECTORY_TO_SAVE'), 'main_plot.png'))
        fig.close()

        return True


    @dump_func_name
    def get_target_measurements(self):
        
        self.target_measurements = {}

        all_objects_xy = [[float(x), float(y)] for x, y in zip(
            self.sextractor_data['X_IMAGE'],
            self.sextractor_data['Y_IMAGE'])]

        target_hdr_x, target_hdr_y = WCS(
            self.wcs_image_data.header).wcs_world2pix(
            self.coo_target_hdr.ra.deg, self.coo_target_hdr.dec.deg, 1)
        logger.info('target: {}, {}'.format(target_hdr_x, target_hdr_y))

        if (self.wcs_image_data.header['NAXIS1'] < target_hdr_x < 0 or
            self.wcs_image_data.header['NAXIS2'] < target_hdr_y < 0):
            return False

        counterpart_idx, dist = closest_object(
            [target_hdr_x, target_hdr_y], all_objects_xy)
        
        logger.info('closest object on {}, {}'.format(
            self.sextractor_data['X_IMAGE'][counterpart_idx],
            self.sextractor_data['Y_IMAGE'][counterpart_idx]))

        self.coo_target_image = SkyCoord(*WCS(
            self.wcs_image_data.header).wcs_pix2world(
            self.sextractor_data['X_IMAGE'][counterpart_idx],
            self.sextractor_data['Y_IMAGE'][counterpart_idx] , 1), 
            frame='icrs', unit='deg')

        if dist > config.getint('SEXTRACTOR', 'TARGET_DIST_LIMIT'):
            logger.warning('Distance to target above limit: {}'.format(dist))
            return False

        for key in self.sextractor_data.keys():
            self.target_measurements[key] = self.sextractor_data[
                                                    key][counterpart_idx]

        return True
    

    @staticmethod
    @dump_func_name
    def parse_coordinates(ra, dec, unit):
        logger.info('FILE: parse coordinates')
        coo = SkyCoord(ra=ra, dec=dec, frame='icrs', unit=unit)

        return coo


    @staticmethod
    @dump_func_name
    def read_hdr_keys(hdr, keys_list):
        hdr_keys = {}

        for key in keys_list:
            try:
                hdr_keys[key] = hdr[key]
            except KeyError:
                hdr_keys[key] = None

        return hdr_keys
        

@dump_func_name
def prepare_data_for_influx(image, last_data):

    tags = {}
    fields = {}
    image_object_name = image.image_data.header[config.get('FITS', 'OBJECT_KEY')]

    if last_data.object_name != image_object_name:
        uuid_val = int(uuid.uuid1())
        last_data.uuid = uuid_val
        last_data.object_name = image_object_name
        tags['uuid'] = uuid_val
    else:
        tags['uuid'] = last_data.uuid

    for tag in config.get('INFLUXDB', 'HDR_KEYS_TO_DB_TAGS').split(','):
        tags[tag] = image.image_data.header[tag]

    for field in config.get('INFLUXDB', 'HDR_KEYS_TO_DB_FIELDS').split(','):
        fields[field] = image.image_data.header[field]

    if image.target_measurements:
        for key, value in image.target_measurements.items():
            fields[key] = value
        fields['PHOTOMETRY_STATUS'] = 1
    else:
        fields['PHOTOMETRY_STATUS'] = 0

    fields['RA_HDR'] = round(image.coo_target_hdr.ra.deg, 6)
    fields['DEC_HDR'] = round(image.coo_target_hdr.dec.deg, 6)

    if image.coo_center:
        fields['RA_CENTER'] = round(image.coo_center.ra.deg, 6)
        fields['DEC_CENTER'] = round(image.coo_center.dec.deg, 6)


    hdr_time = image.image_data.header[
        config.get('FITS', 'TIME_KEY')]
    date_time = image.image_data.header[
        config.get('FITS', 'DATE_KEY')]    

    image_time = 'T'.join([date_time, hdr_time])
    fields['image_time'] = image_time

    time = dt.datetime.now().isoformat()

    message_body = {
            "measurement": "image",
            "tags": tags,
            "time": time,
            "fields": fields
            }

    return message_body

@dump_func_name
def prepare_data_for_modbus(image):
    pass


@dump_func_name
def closest_object(node, nodes):
    nodes = np.asarray(nodes)
    dist_2 = np.sum((nodes - node)**2, axis=1)

    return np.argmin(dist_2), dist_2[np.argmin(dist_2)]


