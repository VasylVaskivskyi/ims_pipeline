""" Pull all metadata together in one file """

import os
import os.path as osp
import argparse
import re
import xml.etree.ElementTree as ET
from io import StringIO

import yaml
import tifffile as tif

from extract_meta import run_extract_meta
from extract_from_names import extract_cycle_info_from_names


def strip_namespace(xmlstr: str):
    it = ET.iterparse(StringIO(xmlstr))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition('}')
    root = it.root
    return root


def get_img_info(img_path, block_size):
    if img_path.endswith(('tif', 'tiff')):
        with tif.TiffFile(img_path) as TF:
            npages = len(TF.pages)
            plane_shape = TF.series[0].shape
            try:
                meta = TF.ome_metadata
            except AttributeError:
                meta = None
    else:
        raise ValueError(img_path + 'is not a TIFF file')
    img_name = osp.basename(img_path)

    if plane_shape[-1] % block_size == 0:
        x_nblocks = plane_shape[-1] // block_size
    else:
        x_nblocks = (plane_shape[-1] // block_size) + 1

    if plane_shape[-2] % block_size == 0:
        y_nblocks = plane_shape[-2] // block_size
    else:
        y_nblocks = (plane_shape[-2] // block_size) + 1

    return img_name, plane_shape, x_nblocks, y_nblocks


def generate_slicer_meta(img_name: str, plane_shape: tuple, block_size: int, overlap: int,
                         x_nblocks: int, y_nblocks: int, cycle: int, region: int):
    block_shape = (block_size + overlap * 2, block_size + overlap * 2)
    block_shape_no_overlap = (block_shape[-2] - overlap * 2, block_shape[-1] - overlap * 2)

    nblocks_info = dict(x=x_nblocks, y=y_nblocks)
    block_shape_info = dict(x=block_shape[-1], y=block_shape[-2])
    block_shape_no_overlap_info = dict(x=block_shape_no_overlap[-1], y=block_shape_no_overlap[-2])
    original_img_shape_info = dict(x=plane_shape[-1], y=plane_shape[-2])
    new_image_shape_info = dict(x=block_shape[-1] * x_nblocks, y=block_shape[-2] * y_nblocks)
    overlap_info = dict(x=overlap * 2, y=overlap * 2)

    padding = dict(left=0, right=0, top=0, bottom=0)
    padding["right"] = block_shape_no_overlap[-1] - (plane_shape[-1] % block_shape_no_overlap[-1])
    padding["bottom"] = block_shape_no_overlap[-2] - (plane_shape[-2] % block_shape_no_overlap[-2])

    slicer_meta = {'image_name': img_name,
                   'original_image_shape': original_img_shape_info,
                   'new_image_shape': new_image_shape_info,
                   'block_shape': block_shape_info,
                   'block_shape_no_overlap': block_shape_no_overlap_info,
                   'nblocks': nblocks_info,
                   'overlap': overlap_info,
                   'padding': padding,
                   'tiling_mode': 'grid',
                   'cycle': cycle,
                   'region': region
                   }

    return slicer_meta


def extract_from_raw_meta(path: str):  #  ncycles: int, nregions: int
    with open(path, 'r', encoding='utf-8') as f:
        ome_meta = f.read()

    xml = strip_namespace(ome_meta)

    tag_pixels = xml.find('Image').find('Pixels')
    lateral_resolution = float(tag_pixels.get('PhysicalSizeX'))
    # TODO calculate axial resolution
    axial_resolution = 1

    dims = ['SizeT', 'SizeZ', 'SizeC', 'SizeY', 'SizeX']
    axes = 'TZCYX'
    shape = [int(tag_pixels.get(attr)) for attr in dims if attr in tag_pixels.attrib]

    num_z_planes = shape[-4] if len(shape) > 3 else 1
    channel_list = tag_pixels.findall('Channel')
    channel_names = [ch.get('Name') for ch in channel_list]
    per_cycle_channel_names = ['CH' + str(i) for i in range(1, len(channel_names) + 1)]
    fluors = [ch.get('Fluor') for ch in channel_list]
    emission_wavelengths = [int(float(ch.get('EmissionWavelength'))) for ch in channel_list]

    this_instrument_id = xml.find('Image').find('InstrumentRef').get('ID')
    this_objective_id = xml.find('Image').find('ObjectiveSettings').get('ID')

    this_instrument = [ins for ins in xml.findall('Instrument') if ins.get('ID') == this_instrument_id][0]
    this_objective = [obj for obj in this_instrument.findall('Objective') if obj.get('ID') == this_objective_id][0]
    magnification = int(float(this_objective.get('NominalMagnification')))
    objective_type = this_objective.get('Immersion').lower()
    numerical_aperture = float(this_objective.get('LensNA'))

    extracted_ome_meta = {"per_cycle_channel_names": per_cycle_channel_names,
                          "channel_names": fluors,
                          "axial_resolution": axial_resolution,
                          "lateral_resolution": lateral_resolution,
                          "emission_wavelengths": emission_wavelengths,
                          "magnification": magnification,
                          "num_z_planes": num_z_planes,
                          "numerical_aperture": numerical_aperture,
                          "objective_type": objective_type,
                          }
    return extracted_ome_meta


def get_raw_meta(raw_img_path, meta_output_dir):
    raw_meta_path = osp.join(meta_output_dir, 'raw_meta.xml')
    run_extract_meta.main(raw_img_path, raw_meta_path)
    extracted_raw_meta = extract_from_raw_meta(raw_meta_path)
    return extracted_raw_meta


def get_slicer_meta(proc_img_path, cycle, region, block_size, overlap):
    img_name, plane_shape, x_nblocks, y_nblocks = get_img_info(proc_img_path, block_size)
    slicer_meta = generate_slicer_meta(img_name, plane_shape, block_size,
                                       overlap, x_nblocks, y_nblocks, cycle, region)
    return slicer_meta


def get_meta_for_each_cycle(per_cycle_info, base_pipeline_dir, block_size, overlap):
    cycles = per_cycle_info.keys()
    region = 1

    raw_meta_per_cycle = dict()
    slicer_meta_per_cycle = dict()

    for cycle in cycles:
        this_cycle_info = per_cycle_info[cycle]
        proc_img_path = this_cycle_info[region]['proc_path']
        raw_img_path = this_cycle_info[region]['raw_path']

        meta_output_dir = osp.join(base_pipeline_dir, 'meta', 'Cyc' + str(cycle) + '_reg' + str(region))
        if not osp.exists(meta_output_dir):
            os.makedirs(meta_output_dir)

        slicer_meta = get_slicer_meta(proc_img_path, cycle, region, block_size, overlap)
        extracted_raw_meta = get_raw_meta(raw_img_path, meta_output_dir)

        slicer_meta_per_cycle[cycle] = slicer_meta
        raw_meta_per_cycle[cycle] = extracted_raw_meta

    return raw_meta_per_cycle, slicer_meta_per_cycle


def main(submission: dict, base_pipeline_dir: str,  pipeline_config_path: str):

    block_size = submission['block_size']
    overlap = submission['overlap']
    mxif_dir = submission['mxif_dataset_dir_path']

    per_cycle_info = extract_cycle_info_from_names(mxif_dir)

    raw_meta_per_cycle, slicer_meta_per_cycle = get_meta_for_each_cycle(per_cycle_info, base_pipeline_dir, block_size, overlap)
    num_regions_for_segmentation = 1  # all data so far had only one region
    num_cycles_for_segmentation = 1
    cycles = per_cycle_info.keys()
    first_cycle = min(list(cycles))
    first_cycle_raw_meta = raw_meta_per_cycle[first_cycle]
    first_cycle_slicer_meta = slicer_meta_per_cycle[first_cycle]

    # find id of nuclei channel
    nuclei_channel_id_per_cycle = dict()
    for cycle in raw_meta_per_cycle:
        nuclei_channel_id = 0
        for i, ch_name in enumerate(raw_meta_per_cycle[cycle]['channel_names']):
            if ch_name.lower() == submission['nuclei_channel'].lower():
                nuclei_channel_id = i
                break
        nuclei_channel_id_per_cycle[cycle] = nuclei_channel_id

    first_cycle_nuclei_channel_id = nuclei_channel_id_per_cycle[first_cycle]
    nuclei_channel_name = 'CH' + str(first_cycle_nuclei_channel_id + 1)

    # collect paths of all mxif datasets
    mxif_data_paths = []
    total_cycles = list(per_cycle_info.keys())
    for c in total_cycles:
        this_cycle_info = per_cycle_info[c]
        regions = list(this_cycle_info.keys())
        for r in regions:
            proc_img_path = this_cycle_info[r]['proc_path']
            mxif_data_paths.append(proc_img_path)

    # create general slicer meta
    remove_keys = ['image_name', 'cycle', 'region']
    general_slicer_meta = {key: val for key, val in first_cycle_slicer_meta.items() if key not in remove_keys}

    # create general ome meta
    general_ome_meta = first_cycle_raw_meta
    general_ome_meta['channel_names'] = [submission['nuclei_channel']]
    general_ome_meta['per_cycle_channel_names'] = [nuclei_channel_name]
    general_ome_meta['emission_wavelengths'] = [first_cycle_raw_meta['emission_wavelengths'][first_cycle_nuclei_channel_id]]
    general_ome_meta['region_names'] = ['reg' + str(i) for i in range(1, num_regions_for_segmentation + 1)]
    general_ome_meta['num_cycles'] = num_cycles_for_segmentation

    submission['nuclei_channel_id_per_cycle'] = nuclei_channel_id_per_cycle

    # combine all metadata into pipeline config
    pipeline_config = dict()
    pipeline_config['submission'] = submission
    pipeline_config['ome_meta'] = general_ome_meta
    pipeline_config['slicer_meta'] = general_slicer_meta

    with open(pipeline_config_path, 'w') as s:
        yaml.safe_dump(pipeline_config, stream=s, default_flow_style=False, indent=4, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--submission', type=yaml.safe_load, help='data from submission file')
    parser.add_argument('--base_pipeline_dir', type=str, help='base pipeline directory')
    parser.add_argument('--pipeline_config_path', type=str, help='path to output collected pipeline metadata')

    args = parser.parse_args()

    main(args.submission, args.base_pipeline_dir,  args.pipeline_config_path)
