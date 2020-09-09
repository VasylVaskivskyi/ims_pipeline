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


def create_new_xml_from_combined_metadata(positive_xml, negative_xml):
    num_pos_ch, pos_ch, pos_tiff = get_all_channels_and_tiffdata(positive_xml)
    num_neg_ch, neg_ch, neg_tiff = get_all_channels_and_tiffdata(negative_xml)
    combined_xml = copy.copy(positive_xml)

    for child in combined_xml.find('Image').find('Pixels').getchildren():
        combined_xml.find('Image').find('Pixels').remove(child)

    total_channels = str(num_pos_ch + num_neg_ch)
    combined_xml.find('Image').find('Pixels').set('SizeC', total_channels)

    for i in range(0, len(neg_ch)):
        new_id = str(num_pos_ch + i)
        neg_ch[i].set('ID', 'Channel:0:' + new_id)
        neg_tiff[i].set('FisrtC', new_id)
        neg_tiff[i].set('IFD', new_id)

    # combine positive and negative channels and tiffdata
    pos_ch.extend(neg_ch)
    pos_tiff.extend(neg_tiff)

    for c in pos_ch:
        combined_xml.find('Image').find('Pixels').append(c)
    for t in pos_tiff:
        combined_xml.find('Image').find('Pixels').append(t)

    # these attributes contain symbol that is cannot be encoded with ascii. ascii encoding required by tifffile
    pixel_attribs = combined_xml.find('Image').find('Pixels').attrib
    if pixel_attribs['PhysicalSizeXUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeXUnit']
    if pixel_attribs['PhysicalSizeYUnit'] == 'μm':
        del combined_xml.find('Image').find('Pixels').attrib['PhysicalSizeYUnit']

    combined_xml_str = ET.tostring(combined_xml, method='xml', encoding='utf-8')
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    final_combined_xml_str = combined_xml_str.decode('ascii', errors='backslashreplace')
    final_combined_xml_str = xml_declaration + final_combined_xml_str

    return final_combined_xml_str, num_pos_ch, num_neg_ch


def main(ims_pos_path: str, ims_neg_path: str, ims_combined_out_path: str):
    pos_xml_str = read_ome_meta(ims_pos_path)
    neg_xml_str = read_ome_meta(ims_neg_path)

    pos_xml = strip_namespace(pos_xml_str)
    neg_xml = strip_namespace(neg_xml_str)

    combined_xml, num_pos_ch, num_neg_ch = create_new_xml_from_combined_metadata(pos_xml, neg_xml)

    with tif.TiffWriter(ims_combined_out_path, bigtiff=True) as TW:
        for i in range(0, num_pos_ch):
            TW.save(tif.imread(ims_pos_path, key=i), photometric='minisblack', description=combined_xml)
        for i in range(0, num_neg_ch):
            TW.save(tif.imread(ims_neg_path, key=i), photometric='minisblack', description=combined_xml)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ims_pos_path', type=str, help='path to positive IMS OME-TIFF')
    parser.add_argument('--ims_neg_path', type=str, help='path to negative IMS OME-TIFF')
    parser.add_argument('--ims_combined_out_path', type=str,
                        help='path to output combined positive and negative OME-TIFF')
    args = parser.parse_args()

    main(args.ims_pos_path, args.ims_neg_path, args.ims_combined_out_path)
