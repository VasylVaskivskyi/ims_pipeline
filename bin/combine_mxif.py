import argparse
import xml.etree.ElementTree as ET
from io import StringIO
import copy

import tifffile as tif


def read_ome_meta(path: str):
    with tif.TiffFile(path) as TF:
        # ims_shape = TF.series[0].shape
        ims_ome_meta = TF.ome_metadata

    return ims_ome_meta


def strip_namespace(xmlstr: str):
    it = ET.iterparse(StringIO(xmlstr))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition('}')
    root = it.root
    return root


def get_all_channels_and_tiffdata(xml):
    pixels = xml.find('Image').find('Pixels')
    nchannels = int(pixels.get('SizeC'))
    channels = pixels.findall('Channel')
    tiffdata = pixels.findall('TiffData')
    return nchannels, channels, tiffdata


def get_necessary_meta(path):
    ome_meta = read_ome_meta(path)
    xml = strip_namespace(ome_meta)
    nchannels, channels, tiffdata = get_all_channels_and_tiffdata(xml)
    meta = {'nchannels': nchannels, 'channels': channels, 'tiffdata': tiffdata}
    return meta


def filter_redundant_nuclei_channels(mxif_data_paths, nuclei_channel_id_list):
    metadata_per_cycle = []
    for i, path in enumerate(mxif_data_paths):
        meta = get_necessary_meta(path)
        redundant_nuclei_channel_id = nuclei_channel_id_list[i]
        if redundant_nuclei_channel_id != -1:
            del meta['channels'][redundant_nuclei_channel_id]
            meta['nchannels'] -= 1
        metadata_per_cycle.append(meta)
    return metadata_per_cycle


def create_new_xml_from_combined_metadata(old_xml, metadata_per_cycle):
    # set proper ome attributes tags
    combined_xml = copy.deepcopy(old_xml)
    proper_ome_attribs = {'xmlns': 'http://www.openmicroscopy.org/Schemas/OME/2016-06',
                          'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                          'xsi:schemaLocation': 'http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd'}
    combined_xml.attrib.clear()

    for attr, val in proper_ome_attribs.items():
        combined_xml.set(attr, val)
    for child_node in combined_xml.find('Image').find('Pixels'):
        combined_xml.find('Image').find('Pixels').remove(child_node)

    tiff_data = ET.Element('TiffData', dict(FirstC="0", FirstT="0", FirstZ="0", IFD="0", PlaneCount="1"))

    combined_meta = []
    num_channels = 0
    for meta in metadata_per_cycle:
        meta['tiffdata'] = []
        for j in range(0, meta['nchannels']):
            new_id = str(num_channels)
            meta['channels'][j].set('ID', 'Channel:0:' + new_id)

            new_tiff_data = copy.copy(tiff_data)
            new_tiff_data.set('FisrtC', new_id)
            new_tiff_data.set('IFD', new_id)
            meta['tiffdata'].append(new_tiff_data)

            num_channels += 1
        combined_meta.append(meta)

    total_channels = str(num_channels)
    combined_xml.find('Image').find('Pixels').set('SizeC', total_channels)

    for dataset in combined_meta:
        for c in dataset['channels']:
            combined_xml.find('Image').find('Pixels').append(c)

    for dataset in combined_meta:
        for t in dataset['tiffdata']:
            combined_xml.find('Image').find('Pixels').append(t)

    # μm contain symbol that is cannot be encoded with ascii. ascii encoding is required by tifffile
    pixel_attribs = combined_xml.find('Image').find('Pixels').attrib
    if pixel_attribs['PhysicalSizeXUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeXUnit']
    if pixel_attribs['PhysicalSizeYUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeYUnit']

    combined_xml_str = ET.tostring(combined_xml, method='xml', encoding='utf-8')
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    final_combined_xml_str = combined_xml_str.decode('ascii', errors='ignore')
    final_combined_xml_str = xml_declaration + final_combined_xml_str

    return final_combined_xml_str, combined_meta


def get_values_from_sorted_dict(dictionary: dict):
    sorted_keys = sorted(dictionary.keys())
    values_from_sorted_dict = list()
    for k in sorted_keys:
        values_from_sorted_dict.append(dictionary[k])
    return values_from_sorted_dict


def get_number_of_tiff_pages(file_path):
    with tif.TiffFile(file_path) as TF:
        npages = len(TF.pages)
    return npages


def main(pipeline_config: dict, mxif_data_paths: list, mxif_combined_out_path: str):

    nuclei_channel_id_per_cycle = pipeline_config['submission']['nuclei_channel_id_per_cycle']
    nuclei_channel_id_list = get_values_from_sorted_dict(nuclei_channel_id_per_cycle)
    nuclei_channel_id_list[0] = -1  # to keep nuclei channel in first cycle

    first_cycle_xml = strip_namespace(read_ome_meta(mxif_data_paths[0]))
    metadata_per_cycle = filter_redundant_nuclei_channels(mxif_data_paths, nuclei_channel_id_list)
    combined_xml, combined_meta = create_new_xml_from_combined_metadata(first_cycle_xml, metadata_per_cycle)

    with tif.TiffWriter(mxif_combined_out_path, bigtiff=True) as TW:
        for i, data_path in enumerate(mxif_data_paths):
            npages = get_number_of_tiff_pages(data_path)
            redundant_nuclei_channel_id = nuclei_channel_id_list[i]
            for page in range(0, npages):
                if page != redundant_nuclei_channel_id:
                    TW.save(tif.imread(data_path, key=page), photometric='minisblack', description=combined_xml)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mxif_data_paths', type=str, nargs='+',
                        help='space separated list of paths to MxIF OME-TIFF')
    parser.add_argument('--mxif_combined_out_path', type=str,
                        help='path to output combined MxIF images')
    args = parser.parse_args()

    main(args.mxif_data_paths, args.mxif_combined_out_path)
