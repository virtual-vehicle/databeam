import os
import urllib.request
from zipfile import ZipFile
import shutil
import json
import logging


if __name__ == '__main__':
    # download external libs for development
    # in docker, all libs should be already in place
    static_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    js_dir_path = os.path.join(static_dir_path, 'js')
    css_dir_path = os.path.join(static_dir_path, 'css')
    images_dir_path = os.path.join(css_dir_path, 'images')

    # leaflet
    logging.warning('downloading leaflet library')
    zip_file, _ = urllib.request.urlretrieve(
        "https://github.com/Leaflet/Leaflet/releases/latest/download/leaflet.zip", 'temp_leaflet.zip')
    zf = ZipFile(zip_file)
    zf.extractall('temp_leaflet')
    os.rename(os.path.join('temp_leaflet', 'dist', 'leaflet.js'), os.path.join(js_dir_path, 'leaflet.js'))
    os.rename(os.path.join('temp_leaflet', 'dist', 'leaflet.css'), os.path.join(css_dir_path, 'leaflet.css'))
    if not os.path.exists(images_dir_path):
        os.mkdir(images_dir_path)
    for image in [i for i in zf.namelist() if i.startswith('dist/images/') and not i.endswith('/')]:
        os.rename(os.path.join('temp_leaflet', image), os.path.join(images_dir_path, image.split('/')[-1]))
    zf.close()
    shutil.rmtree('temp_leaflet')  # remove extracted archive
    os.remove(zip_file)  # remove archive

    # uPlot
    logging.warning('downloading uPlot library')
    _json = json.loads(urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/leeoniya/uPlot/releases/latest',
        headers={'Accept': 'application/vnd.github.v3+json'},
    )).read())
    zip_file, _ = urllib.request.urlretrieve(_json['zipball_url'], 'temp_uPlot.zip')
    zf = ZipFile(zip_file)
    zf.extractall('temp_uPlot')
    for file in [f for f in zf.namelist() if f.endswith('uPlot.iife.min.js')]:
        os.rename(os.path.join('temp_uPlot', file), os.path.join(js_dir_path, file.split('/')[-1]))
    for file in [f for f in zf.namelist() if f.endswith('uPlot.min.css')]:
        os.rename(os.path.join('temp_uPlot', file), os.path.join(css_dir_path, file.split('/')[-1]))
    zf.close()
    shutil.rmtree('temp_uPlot')  # remove extracted archive
    os.remove(zip_file)  # remove archive
