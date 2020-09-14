#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: CommandLineTool
requirements:
  DockerRequirement:
    dockerPull: hubmap/ims-mxif-pipeline:latest
baseCommand: ["python", "/opt/ims_pipeline/bin/run_combine_mxif.py"]

inputs:
  pipeline_config:
    type: File
    inputBinding:
      prefix: "--pipeline_config"

  mxif_dataset_dir_path:
    type: Directory
    inputBinding:
      prefix: "--mxif_dataset_dir_path"

outputs:
  combined_mxif:
    type: File
    outputBinding:
      glob: "mxif_combined_multilayer.ome.tiff"