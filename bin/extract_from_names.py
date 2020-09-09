import os
import os.path as osp
import re


def get_proc_micro_file_location(dataset_dir: str):
    allowed_extensions = ('.tif', '.tiff')
    file_list = [fn for fn in os.listdir(dataset_dir) if fn.endswith(allowed_extensions)]
    if file_list == []:
        return None
    else:
        return osp.join(dataset_dir, file_list[0])


def get_file_locations(base_dir: str):
    proc_micro_path = osp.join(base_dir, 'processedMicroscopy')
    raw_micro_path = osp.join(base_dir, 'rawMicroscopy')

    proc_micro_dirs = os.listdir(proc_micro_path)
    raw_micro_files = os.listdir(raw_micro_path)
    # current naming patterns:
    # processedMicroscopy/VAN0003-LK-32-22-MxIF_cyc1_images/VAN0003-LK-32-22-MxIF_cyc1_registered.ome.tiff
    # rawMicroscopy/VAN0003-LK-32-22-MxIF_cyc1_unregistered.czi
    full_path_proc_micro_dirs = [osp.join(base_dir, 'processedMicroscopy', path) for path in proc_micro_dirs if
                                 'images' in path]
    full_path_proc_micro_files = [get_proc_micro_file_location(path) for path in full_path_proc_micro_dirs]
    full_path_proc_micro_files = [path for path in full_path_proc_micro_files if path is not None]

    full_path_raw_micro_files = [osp.join(base_dir, 'rawMicroscopy', path) for path in raw_micro_files if path.lower().endswith('czi')]

    return full_path_proc_micro_files, full_path_raw_micro_files


def extract_cycle_and_region_from_name(dirname: str):
    region = 1
    if 'reg' in dirname:
        match = re.search(r'reg(\d+)', dirname, re.IGNORECASE)
        if match is not None:
            region = int(match.groups()[0])
    cycle = int(re.search(r'cyc(\d+)', dirname, re.IGNORECASE).groups()[0])

    return cycle, region


def arrange_by_cycle(proc_micro_files, raw_micro_files):
    per_cycle_info = dict()
    for fn in proc_micro_files:
        cycle, region = extract_cycle_and_region_from_name(fn)
        proc_path = {'proc_path': fn}
        if cycle in per_cycle_info:
            per_cycle_info[cycle].update({region: proc_path})
        else:
            per_cycle_info[cycle] = {region: proc_path}

    for fn in raw_micro_files:
        cycle, region = extract_cycle_and_region_from_name(fn)
        raw_path = {'raw_path': fn}
        if cycle in per_cycle_info:
            if region in per_cycle_info[cycle]:
                per_cycle_info[cycle][region].update(raw_path)

    return per_cycle_info


def extract_cycle_info_from_names(path):
    proc_micro_files, raw_micro_files = get_file_locations(path)
    per_cycle_info = arrange_by_cycle(proc_micro_files, raw_micro_files)
    return per_cycle_info
