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


def create_new_xml_from_combined_metadata(old_xml, mxif_data_paths):
    # set proper ome attributes tags
    combined_xml = copy.deepcopy(old_xml)
    proper_ome_attribs = {'xmlns': 'http://www.openmicroscopy.org/Schemas/OME/2016-06',
                          'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                          'xsi:schemaLocation': 'http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd'}
    combined_xml.attrib.clear()

    for attr, val in proper_ome_attribs.items():
        combined_xml.set(attr, val)
    for child in combined_xml.find('Image').find('Pixels').getchildren():
        combined_xml.find('Image').find('Pixels').remove(child)

    combined_meta = []
    prev_num_ch = 0
    for path in mxif_data_paths:
        meta = get_necessary_meta(path)
        for i in range(0, meta['nchannels']):
            new_id = str(prev_num_ch + i)
            meta['channels'][i].set('ID', 'Channel:0:' + new_id)
            # meta['tiffdata'][i].set('FisrtC', new_id)
            # meta['tiffdata'][i].set('IFD', new_id)
        combined_meta.append(meta)
        prev_num_ch += meta['nchannels']

    total_channels = str(prev_num_ch)
    combined_xml.find('Image').find('Pixels').set('SizeC', total_channels)

    for dataset in combined_meta:
        for c in dataset['channels']:
            combined_xml.find('Image').find('Pixels').append(c)
    #
    # for dataset in combined_meta:
    #     for t in dataset['tiffdata']:
    #         combined_xml.find('Image').find('Pixels').append(t)

    # μm contain symbol that is cannot be encoded with ascii. ascii encoding is required by tifffile
    pixel_attribs = combined_xml.find('Image').find('Pixels').attrib
    if pixel_attribs['PhysicalSizeXUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeXUnit']
    if pixel_attribs['PhysicalSizeYUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeYUnit']

    combined_xml_str = ET.tostring(combined_xml, method='xml', encoding='utf-8')
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    final_combined_xml_str = combined_xml_str.decode('ascii', errors='backslashreplace')
    final_combined_xml_str = xml_declaration + final_combined_xml_str

    return final_combined_xml_str, combined_meta


def get_values_from_sorted_dict(dictionary: dict):
    sorted_keys = sorted(dictionary.keys())
    values_from_sorted_dict = list()
    for k in sorted_keys:
        values_from_sorted_dict.append(dictionary[k])
    return values_from_sorted_dict


def main(pipeline_config: dict, mxif_data_paths: list, mxif_combined_out_path: str):

    first_cycle_xml = strip_namespace(read_ome_meta(mxif_data_paths[0]))
    combined_xml, combined_meta = create_new_xml_from_combined_metadata(first_cycle_xml, mxif_data_paths)

    nuclei_channel_id_per_cycle = pipeline_config['submission']['nuclei_channel_id_per_cycle']
    nuclei_channel_id_list = get_values_from_sorted_dict(nuclei_channel_id_per_cycle)
    nuclei_channel_id_list[0] = -1  # to keep nuclei channel in first cycle

    with tif.TiffWriter(mxif_combined_out_path, bigtiff=True) as TW:
        for i, dataset in enumerate(mxif_data_paths):
            npages = combined_meta[i]['nchannels']
            redundant_nuclei_channel_id = nuclei_channel_id_list[i]
            for page in range(0, npages):
                if page != redundant_nuclei_channel_id:
                    TW.save(tif.imread(dataset, key=page),
                            photometric='minisblack', description=combined_xml)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mxif_data_paths', type=str, nargs='+',
                        help='space separated list of paths to MxIF OME-TIFF')
    parser.add_argument('--mxif_combined_out_path', type=str,
                        help='path to output combined MxIF images')
    args = parser.parse_args()

    main(args.mxif_data_paths, args.mxif_combined_out_path)
