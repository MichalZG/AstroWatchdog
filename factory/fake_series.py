import glob
import shutil
import itertools
import time
import os


source_path = '/home/pi/Data/astro/asystent_test/series/'
dest_path = '/home/pi/Programs/python_programs/AstroWatchdog/data_market/'

sleep_time = 5

images = sorted(glob.glob(os.path.join(source_path, '*.fits')))

for im in itertools.cycle(images):
    print(os.path.basename(im))
    shutil.copy(im, os.path.join(dest_path, 'preview.fits'))
    time.sleep(sleep_time)
