import datetime
import argparse

import yaml


def read_slicer_meta(slicer_meta: dict):

    acq_meta = {"region_width": slicer_meta['nblocks']['x'],
                "region_height": slicer_meta['nblocks']['y'],
                "tile_width": slicer_meta['block_shape_no_overlap']['x'],
                "tile_height": slicer_meta['block_shape_no_overlap']['y'],
                "tile_overlap_x": slicer_meta['overlap']['x'],
                "tile_overlap_y": slicer_meta['overlap']['y'],
                "tiling_mode": slicer_meta['tiling_mode']
                }
    return acq_meta


def generate_processor_meta(acquisition_meta: dict, submission: dict):

    num_z_planes = acquisition_meta['num_z_planes']
    ngpus = submission['ngpus']
    best_focus_channel = submission['nuclei_channel']
    nuclei_channel = submission['nuclei_channel']
    run_drift_comp = False
    drift_compensation = {}

    # drift_compensation_channel = submission['drift_compensation_channel']
    # if drift_compensation_channel is not None:
    #     run_drift_comp = True
    #     drift_compensation = {'drift_compensation': {'channel': drift_compensation_channel}}

    if num_z_planes > 1:
        run_best_focus = True
        best_focus = {'best_focus': {'channel':  best_focus_channel}}
        z_plane = 'best'
    else:
        run_best_focus = False
        best_focus = {}
        z_plane = 'all'

    gpus = list(range(0, ngpus))

    processor_meta = {
        "processor": {
            "args": {
                "gpus": gpus,
                "run_crop": False,
                "run_tile_generator": True,
                "run_drift_comp": run_drift_comp,
                "run_cytometry": True,
                "run_best_focus": run_best_focus
            },
            "deconvolution": {"n_inter": 25, "scale_factor": 0.5},
            "tile_generator": {"raw_file_type": "keyence_mixed"}
        }
    }
    processor_meta['processor'].update(best_focus)
    processor_meta['processor'].update(drift_compensation)

    cytometry = {
        "cytometry": {
                "z_plane": z_plane,
                "target_shape": [acquisition_meta["tile_width"] + acquisition_meta["tile_overlap_x"],
                                 acquisition_meta["tile_height"] + acquisition_meta["tile_overlap_y"]],
                "nuclei_channel_name": nuclei_channel,
                "segmentation_params": {"memb_min_dist": 8, "memb_sigma": 5, "memb_gamma": 0.25, "marker_min_size": 5, "marker_dilation": 3},
                "quantification_params": {"nucleus_intensity": True, "cell_graph": True}
            }
        }
    processor_meta['processor'].update(cytometry)
    return processor_meta


def main(pipeline_config_path: str, cytokit_config_path: str):
    with open(pipeline_config_path, 'r') as s:
        pipeline_config = yaml.safe_load(s)

    slicer_meta = read_slicer_meta(pipeline_config['slicer_meta'])
    ome_meta = pipeline_config['ome_meta']

    # same as acquisition_meta but without key - acquisition
    acq_meta = dict()
    acq_meta.update(slicer_meta)
    acq_meta.update(ome_meta)

    submission = pipeline_config['submission']

    head_meta = {"name": submission['experiment_name'],
                 "date": str(datetime.datetime.now()),
                 "environemnt": {"path_formats": "keyence_multi_cycle_v01"}}

    processor_meta = generate_processor_meta(acq_meta, submission)
    acquisition_meta = {'acquisition': acq_meta}

    cytokit_config = dict()
    cytokit_config.update(head_meta)
    cytokit_config.update(acquisition_meta)
    cytokit_config.update(processor_meta)

    with open(cytokit_config_path, 'w') as s:
        yaml.safe_dump(cytokit_config, stream=s, default_flow_style=False, indent=4, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pipeline_config_path', type=str, help='path to collected metadata')
    parser.add_argument('--cytokit_config_path', type=str, help='path to output cytokit config file')

    args = parser.parse_args()

    main(args.pipeline_config_path, args.cytokit_config_path)
