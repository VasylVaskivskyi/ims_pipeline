import argparse
import os
import os.path as osp
import re

import yaml

import combine_mxif
from extract_from_names import extract_cycle_info_from_names


def main(pipeline_config: str, mxif_dataset_dir_path: str):
    with open(pipeline_config, 'r') as s:
        pipeline_config = yaml.safe_load(s)

    per_cycle_info = extract_cycle_info_from_names(mxif_dataset_dir_path)

    mxif_data_paths = []
    total_cycles = list(per_cycle_info.keys())
    for c in total_cycles:
        this_cycle_info = per_cycle_info[c]
        regions = list(this_cycle_info.keys())
        for r in regions:
            proc_img_path = this_cycle_info[r]['proc_path']
            mxif_data_paths.append(proc_img_path)

    mxif_combined_out_path = 'mxif_combined_multilayer.ome.tiff'

    combine_mxif.main(pipeline_config, mxif_data_paths, mxif_combined_out_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pipeline_config', type=str, help='path pipeline config')
    parser.add_argument('--mxif_dataset_dir_path', type=str,
                        help='path to directory with MxIF datasets. Contains two directories: processedMicroscopy, rawMicroscopy')
    args = parser.parse_args()

    main(args.pipeline_config, args.mxif_dataset_dir_path)
