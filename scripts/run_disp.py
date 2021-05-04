# #########################################################################
# Copyright (c) , UChicago Argonne, LLC. All rights reserved.             #
#                                                                         #
# See LICENSE file.                                                       #
# #########################################################################

"""
This user script processes reconstructed image for visualization.

After the script is executed the experiment directory will contain image.vts file for each reconstructed image in the given directory tree.
"""

__author__ = "Ross Harder"
__copyright__ = "Copyright (c), UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['save_CX',
           'process_dir',
           'save_vtk_file',
           'get_conf_dict',
           'handle_visualization',
           'main']

import pycohere.utilities.viz_util as vu
import pycohere.utilities.utils as ut
from pycohere.beamlines.viz import CXDViz
import config_verifier as ver
import argparse
import sys
import os
import numpy as np
from multiprocessing import Pool, cpu_count
import importlib


def save_CX(conf_dict, image, support, coh, save_dir):
    """
    Saves the image and support, and optionally coh vts files.

    Parameters
    ----------
    conf_dict : dict
        dictionary containing configured parameters needed for visualization
    image : array
        image file in npy format
    support : array
        support file in npy format
    coh : array
        coherence file in npy format or None
    save_dir : str
        a directory where to save the processed vts file

    Returns
    -------
    nothing
    """
    try:
        disp = importlib.import_module('beamlines.' + conf_dict['beamline'] + '.disp')
    except:
        print ('cannot import beamlines.' + conf_dict['beamline'] + '.disp module.')
        return

    try:
        params = disp.DispalyParams(conf_dict)
    except Exception as e:
        print ('exception', e)
        return

    det_obj = None
    diff_obj = None
    try:
        detector_name = params.detector
        try:
            det = importlib.import_module('beamlines.aps_34idc.detectors')
            try:
                det_obj = det.create_detector(detector_name)
            except:
                print('detector', detector_name, 'is not defined in beamlines detectors')
        except:
            print('problem importing detectors file from beamline module')
    except:
        pass
    try:
        diffractometer_name = params.diffractometer
        try:
            diff = importlib.import_module('beamlines.aps_34idc.diffractometers')
            try:
                diff_obj = diff.create_diffractometer(diffractometer_name)
            except:
                print ('diffractometer', diffractometer_name, 'is not defined in beamlines detectors')
        except:
             print('problem importing diffractometers file from beamline module')
    except:
        pass

    if not params.set_instruments(det_obj, diff_obj):
        return

    if support is not None:
        image, support = vu.center(image, support)

    try:
        rampups = params.rampsup
        if rampups > 1:
            image = vu.remove_ramp(image, ups=rampups)
    except:
        pass

    geometry = disp.set_geometry(image.shape, params)
    viz = CXDViz(params.crop, geometry)
    viz.visualize(image, support, coh, save_dir)


def process_dir(res_dir_conf):
    """
    Loads arrays from files in results directory. If reciprocal array exists, it will save reciprocal info in tif format. It calls the save_CX function with the relevant parameters.

    Parameters
    ----------
    res_dir_conf : tuple
        tuple of two elements:
        res_dir - directory where the results of reconstruction are saved
        conf_dict - dictionary containing configuration parameters

    Returns
    -------
    nothing
    """
    (res_dir, conf_dict) = res_dir_conf

    # image file was checked in calling function
    imagefile = os.path.join(res_dir, 'image.npy')
    try:
        image = np.load(imagefile)
    except:
        print('cannot load file', imagefile)
        return

    support = None
    coh = None

    supportfile = os.path.join(res_dir, 'support.npy')
    if os.path.isfile(supportfile):
        try:
            support = np.load(supportfile)
        except:
            print('cannot load file', supportfile)
    else:
        print('support file is missing in ' + res_dir + ' directory')

    cohfile = os.path.join(res_dir, 'coherence.npy')
    if os.path.isfile(cohfile):
        try:
            coh = np.load(cohfile)
        except:
            print('cannot load file', cohfile)

    save_CX(conf_dict, image, support, coh, res_dir)



def process_file(image_file, conf_dir):
    """
    Loads array from given image file. Determines the vts file name and calls savw_CX function to process this  file. The vts file will have the same name as image file, with different extension and will be saved in the same directory.

    Parameters
    ----------
    image_file : str
        name of file in npy format containing reconstructrd image
    conf_dir : str
        dictionary containing configuration parameters

    Returns
    -------
    nothing
    """
    if os.path.isfile(image_file):
        try:
            image = np.load(image_file)
        except:
            print('cannot load file', image_file)
    else:
        print(image_file, 'file is missing')
        return

    save_CX(conf_dir, image, None, None, os.path.dirname(image_file))


def get_conf_dict(experiment_dir):
    """
    Reads configuration files and creates dictionary with parameters that are needed for visualization.

    Parameters
    ----------
    experiment_dir : str
        directory where the experiment files are located

    Returns
    -------
    conf_dict : dict
        a dictionary containing configuration parameters
    """
    if not os.path.isdir(experiment_dir):
        print("Please provide a valid experiment directory")
        return None
    conf_dir = os.path.join(experiment_dir, 'conf')
    conf = os.path.join(conf_dir, 'config_disp')
    # verify configuration file
    if not ver.ver_config_disp(conf):
        print ('incorrect configuration file ' + conf +', cannot parse')
        return None

    # parse the conf once here and save it in dictionary, it will apply to all images in the directory tree
    conf_dict = {}
    try:
        conf_map = ut.read_config(conf)
        items = conf_map.items()
        for item in items:
            key = item[0]
            val = item[1]
            conf_dict[key] = val
    except:
        return None

    # get specfile and last_scan from the config file and add it to conf_dict
    main_conf = os.path.join(conf_dir, 'config')
    if os.path.isfile(main_conf):
        try:
            config_map = ut.read_config(main_conf)
        except:
            print ("info: can't read " + conf + " configuration file")
            return None

    try:
        conf_dict['beamline'] = config_map.beamline
    except Exception as e:
        print(e)
        print('beamline must be defined in the configuration file', main_conf)
        return None

    try:
        conf_dict['specfile'] = config_map.specfile
        scan = config_map.scan
        last_scan = scan.split('-')[-1]
        conf_dict['last_scan'] = int(last_scan)
    except:
        print("specfile or scan range not in main config")

    # get binning from the config_data file and add it to conf_dict
    data_conf = os.path.join(conf_dir, 'config_data')
    if os.path.isfile(data_conf):
        try:
            conf_map = ut.read_config(data_conf)
            conf_dict['binning'] = conf_map.binning
        except AttributeError:
            pass
        except Exception as e:
            print(e)
            print("info: can't load " + data_conf + " configuration file")
    return conf_dict


def handle_visualization(experiment_dir, image_file=None):
    """
    If the image_file parameter is defined, the file is processed and vts file saved. Otherwise this function determines root directory with results that should be processed for visualization. Multiple images will be processed concurrently.

    Parameters
    ----------
    conf_dir : str
        directory where the file will be saved

    Returns
    -------
    nothing
    """
    print ('starting visualization process')
    conf_dict = get_conf_dict(experiment_dir)
    if conf_dict is None:
        return

    if image_file is not None:
        process_file(image_file, conf_dict)
    else:
        try:
            results_dir = conf_dict['results_dir']
        except  Exception as ex:
            print(str(ex))
            results_dir = experiment_dir
        # find directories with image.npy file in the root of results_dir
        dirs = []
        for (dirpath, dirnames, filenames) in os.walk(results_dir):
            for file in filenames:
                if file.endswith('image.npy'):
                    dirs.append((dirpath, conf_dict))
        if len(dirs) == 0:
            print ('no image.npy files found in the directory tree', results_dir)
            return
        elif len(dirs) == 1:
            process_dir(dirs[0])
        elif len(dirs) >1:
            no_proc = min(cpu_count(), len(dirs))
            with Pool(processes = no_proc) as pool:
               pool.map_async(process_dir, dirs)
               pool.close()
               pool.join()
        print ('done with processing display')


def main(arg):
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_dir", help="experiment directory")
    parser.add_argument("--image_file", help="a file in .npy format to be processed for visualization")
    args = parser.parse_args()
    experiment_dir = args.experiment_dir
    if args.image_file:
        handle_visualization(experiment_dir, args.image_file)
    else:
        handle_visualization(experiment_dir)


if __name__ == "__main__":
    main(sys.argv[1:])

# python run_disp.py experiment_dir
