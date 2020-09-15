import argparse
import os
import os.path as osp

import yaml

import stitcher


def main(pipeline_config: str, cytokit_out_dir: str):
    with open(pipeline_config, 'r') as s:
        config = yaml.safe_load(s)
    slicer_meta = config['slicer_meta']

    tiles = osp.join(cytokit_out_dir, 'cytometry', 'tile')
    overlap = int(slicer_meta['overlap']['x'] // 2)
    padding_vals = [str(val) for val in list(slicer_meta['padding'].values())]
    padding = ','.join(padding_vals)

    stitcher_out_path = 'segmentation_mask_stitched.ome.tiff'

    stitcher.main(tiles, stitcher_out_path, overlap, padding)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pipeline_config', type=str, help='path to pipeline config')
    parser.add_argument('--cytokit_out_dir', type=str, help='path to cytokit output directory')
    args = parser.parse_args()

    main(args.pipeline_config, args.cytokit_out_dir)
