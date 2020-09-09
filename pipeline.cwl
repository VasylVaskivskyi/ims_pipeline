#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: Workflow


inputs:
  - id: experiment_name
    type: string
  - id: mxif_dataset_dir_path
    type: Directory
  - id: multichannel_ims_ometiff_positive_path
    type: File
  - id: multichannel_ims_ometiff_negative_path
    type: File

  - id: ngpus
    type: int
  - id: nuclei_channel
    type: string
  - id: block_size
    type: int
  - id: overlap
    type: int

steps:
  - id: initiate_pipeline
    in:
      - id: experiment_name
        source: experiment_name
      - id: mxif_dataset_dir_path
        source: mxif_dataset_dir_path
      - id: multichannel_ims_ometiff_positive_path
        source: multichannel_ims_ometiff_positive_path
      - id: multichannel_ims_ometiff_negative_path
        source: multichannel_ims_ometiff_negative_path

      - id: ngpus
        source: ngpus
      - id: nuclei_channel
        source: nuclei_channel
      - id: block_size
        source: block_size
      - id: overlap
        source: overlap
    run: steps/initiate_pipeline.cwl
    out:
      - id: cytokit_config
      - id: pipeline_config

  - id: run_slicer
    in:
      - id: pipeline_config
        source: initiate_pipeline/pipeline_config
      - id: mxif_dataset_dir_path
        source: mxif_dataset_dir_path
      - id: block_size
        source: block_size
      - id: overlap
        source: overlap
    run: steps/run_slicer.cwl
    out:
      - id: slicer_out_dir

  - id: run_cytokit
    in:
      - id: pipeline_config
        source: initiate_pipeline/pipeline_config
      - id: cytokit_config
        source: initiate_pipeline/cytokit_config
      - id: slicer_out_dir
        source: run_slicer/slicer_out_dir
    run: steps/run_cytokit.cwl
    out:
      - id: cytokit_out_dir

  - id: run_stitcher
    in:
      - id: pipeline_config
        source: initiate_pipeline/pipeline_config
      - id: cytokit_out_dir
        source: run_cytokit/cytokit_out_dir
    run: steps/run_stitcher.cwl
    out:
      - id: stitched_mask

  - id: run_combine_ims
    in:
      - id: multichannel_ims_ometiff_positive_path
        source: multichannel_ims_ometiff_positive_path
      - id: multichannel_ims_ometiff_negative_path
        source: multichannel_ims_ometiff_negative_path
    run: steps/run_combine_ims.cwl
    out:
      - id: combined_ims

  - id: run_combine_mxif
    in:
      - id: mxif_dataset_dir_path
        source: mxif_dataset_dir_path
      - id: pipeline_config
        source: initiate_pipeline/pipeline_config
    run: steps/run_combine_mxif.cwl
    out:
      - id: combined_mxif


outputs:
  pipeline_config:
    outputSource: initiate_pipeline/pipeline_config
    type: File
    label: "Pipeline config"

  cytokit_config:
    outputSource: initiate_pipeline/cytokit_config
    type: File
    label: "Cytokit config"

  stitched_mask:
    outputSource: run_stitcher/stitched_mask
    type: File
    label: "Stitched segmentation mask"

  combined_ims:
    outputSource: run_combine_ims/combined_ims
    type: File
    label: "Combined positive and negative IMS"

  combined_mxif:
    outputSource: run_combine_mxif/combined_mxif
    type: File
    label: "Combined positive and negative MxIF"

