import os
import re
import argparse
import numpy as np
import tifffile as tif
import pandas as pd
from typing import List, Tuple, Union
import dask
Image = np.ndarray


def alpha_num_order(string: str) -> str:
    """ Returns all numbers on 5 digits to let sort the string with numeric order.
    Ex: alphaNumOrder("a6b12.125")  ==> "a00006b00012.00125"
    """
    return ''.join([format(int(x), '05d') if x.isdigit()
                    else x for x in re.split(r'(\d+)', string)])


def parse_str_to_dict(string):
    value_list = re.split(r'(\d+)(?:_?)', string)[:-1]
    d = dict(zip(*[iter(value_list)]*2))
    d = {k: int(v) for k, v in d.items()}
    d.update({"path": string})
    return d


def stitch_plane(path_list: List[str], page: int,
                 x_nblocks: int, y_nblocks: int,
                 block_shape: list, dtype: np.dtype,
                 overlap: int, padding: dict, remap_dict: dict = None) -> Tuple[Image, Union[np.ndarray, None]]:

    x_axis = -1
    y_axis = -2

    block_x_size = block_shape[x_axis] - overlap * 2
    block_y_size = block_shape[y_axis] - overlap * 2

    big_image_x_size = (x_nblocks * block_x_size) - padding["left"] - padding["right"]
    big_image_y_size = (y_nblocks * block_y_size) - padding["top"] - padding["bottom"]

    big_image_shape = (big_image_y_size, big_image_x_size)
    big_image = np.zeros(big_image_shape, dtype=dtype)
    big_image_slice = [slice(None), slice(None)]
    block_slice = [slice(None), slice(None)]
    previous_tile_max = 0
    tile_additions = np.zeros((y_nblocks, x_nblocks), dtype=dtype)
    print('n blocks x,y:', (x_nblocks, y_nblocks))
    print('plane shape x,y:', big_image_shape[::-1])
    n = 0
    for i in range(0, y_nblocks):
        yf = i * block_y_size
        yt = yf + block_y_size

        if i == 0:
            block_slice[y_axis] = slice(0 + overlap + padding["top"], block_y_size + overlap)
            big_image_slice[y_axis] = slice(padding["top"], yt)
        elif i == y_nblocks - 1:
            block_slice[y_axis] = slice(0 + overlap, block_y_size + overlap - padding["bottom"])
            big_image_slice[y_axis] = slice(yf, yt - padding["bottom"])
        else:
            block_slice[y_axis] = slice(0 + overlap, block_y_size + overlap)
            big_image_slice[y_axis] = slice(yf, yt)

        for j in range(0, x_nblocks):
            xf = j * block_x_size
            xt = xf + block_x_size

            if j == 0:
                block_slice[x_axis] = slice(0 + overlap + padding["left"], block_x_size + overlap)
                big_image_slice[x_axis] = slice(padding["left"], xt)
            elif j == x_nblocks - 1:
                block_slice[x_axis] = slice(0 + overlap, block_x_size + overlap - padding["right"])
                big_image_slice[x_axis] = slice(xf, xt - padding["right"])
            else:
                block_slice[x_axis] = slice(0 + overlap, block_x_size + overlap)
                big_image_slice[x_axis] = slice(xf, xt)

            block = tif.imread(path_list[n], key=page).astype(dtype)

            if remap_dict is not None:
                block[np.nonzero(block)] += previous_tile_max

            big_image[tuple(big_image_slice)] = block[tuple(block_slice)]

            if remap_dict is not None:
                tile_additions[i, j] = previous_tile_max

                # update previous tile max
                non_zero_selection = block[np.nonzero(block)]
                if len(non_zero_selection) > 0:
                    previous_tile_max = non_zero_selection.max()

            n += 1
    if remap_dict is None:
        tile_additions = None
    return big_image, tile_additions


def get_remapping(img1: Image, img2: Image, overlap: int, mode: str) -> dict:
    if mode == 'horizontal':
        img1_ov = img1[:, -overlap:]
        img2_ov = img2[:, :overlap]
    elif mode == 'vertical':
        img1_ov = img1[-overlap:, :]
        img2_ov = img2[:overlap, :]

    nrows, ncols = img2_ov.shape

    remap_dict = dict()

    for i in range(0, nrows):
        for j in range(0, ncols):
            old_value = img2_ov[i, j]
            if old_value in remap_dict:
                continue
            else:
                new_value = img1_ov[i, j]
                if old_value > 0 and new_value > 0:
                    remap_dict[old_value] = img1_ov[i, j]

    return remap_dict


def remap(path_list: List[str], img1_id: int, img2_id: int, overlap: int, mode: str):
    # take only first channel
    img1 = tif.imread(path_list[img1_id], key=0)
    img2 = tif.imread(path_list[img2_id], key=0)
    remapping = get_remapping(img1, img2, overlap, mode=mode)
    if mode == 'horizontal':
        return {img2_id: {'horizontal': remapping, 'vertical': {}}} # add empty vertical mapping if it is not present
    elif mode == 'vertical':
        return {img2_id: {'vertical': remapping}}


def get_remapping_for_border_values(path_list: List[str],
                                    x_nblocks: int, y_nblocks: int,
                                    overlap: int) -> dict:
    remap_dict = dict()
    htask = []
    for i in range(0, y_nblocks):
        for j in range(0, x_nblocks - 1):
            img1_id = i * x_nblocks + j
            img2h_id = i * x_nblocks + (j + 1)
            htask.append(dask.delayed(remap)(path_list, img1_id, img2h_id, overlap, 'horizontal'))

    hor_values = dask.compute(*htask, scheduler='processes')
    hor_values = list(hor_values)
    for d in hor_values:
        remap_dict.update(d)

    vtask = []
    for i in range(0, y_nblocks - 1):
        for j in range(0, x_nblocks):
            img1_id = i * x_nblocks + j
            img2v_id = (i + 1) * x_nblocks + j
            vtask.append(dask.delayed(remap)(path_list, img1_id, img2v_id, overlap, 'vertical'))

    ver_values = dask.compute(*vtask, scheduler='processes')
    ver_values = list(ver_values)
    for d in ver_values:
        k, v = list(*d.items())
        if k in remap_dict:
            remap_dict[k].update(v)
        else:
            v.update({'horizontal': {}})  # add empty horizontal mapping if it is not present
            remap_dict[k] = {k: v}

    return remap_dict


def remap_values(big_image: Image, remap_dict: dict,
                 tile_additions: np.ndarray, block_shape: list,
                 overlap: int, x_nblocks: int, y_nblocks: int) -> Image:
    print('remapping values')
    x_axis = -1
    y_axis = -2
    x_block_size = block_shape[x_axis] - overlap * 2
    y_block_size = block_shape[y_axis] - overlap * 2

    this_block_slice = [slice(None), slice(None)]
    #top_block_slice = [slice(None), slice(None)]
    #left_block_slice = [slice(None), slice(None)]
    n = 0
    for i in range(0, y_nblocks):
        yf = i * y_block_size
        yt = yf + y_block_size

        this_block_slice[y_axis] = slice(yf, yt)
        #top_block_slice[y_axis] = slice(yf - y_block_size, yt - y_block_size)
        #left_block_slice[y_axis] = slice(yf, yt)

        for j in range(0, x_nblocks):
            xf = j * x_block_size
            xt = xf + x_block_size

            this_block_slice[x_axis] = slice(xf, xt)
            #top_block_slice[x_axis] = slice(xf, xt)
            #left_block_slice[x_axis] = slice(xf - x_block_size, xt - x_block_size)

            this_block = big_image[tuple(this_block_slice)]
            try:
                hor_remap = remap_dict[n]['horizontal']
            except KeyError:
                hor_remap = {}
            try:
                ver_remap = remap_dict[n]['vertical']
            except KeyError:
                ver_remap = {}

            modified_x = False
            modified_y = False

            if hor_remap != {}:
                left_tile_addition = tile_additions[i, j - 1]
                this_tile_addition = tile_additions[i, j]
                for old_value, new_value in hor_remap.items():
                    this_block[this_block == old_value + this_tile_addition] = new_value + left_tile_addition
                modified_x = True
            if ver_remap != {}:
                top_tile_addition = tile_additions[i - 1, j]
                this_tile_addition = tile_additions[i, j]
                for old_value, new_value in ver_remap.items():
                    this_block[this_block == old_value + this_tile_addition] = new_value + top_tile_addition
                modified_y = True

            if modified_x or modified_y:
                big_image[tuple(this_block_slice)] = this_block

            n += 1
    return big_image


def main(img_dir: str, out_path: str, overlap: int, padding_str: str):

    padding_int = [int(i) for i in padding_str.split(',')]
    padding = {"left": padding_int[0], "right": padding_int[1], "top": padding_int[2], "bottom": padding_int[3]}

    allowed_extensions = ('.tif', '.tiff')
    file_list = [fn for fn in os.listdir(img_dir) if fn.endswith(allowed_extensions)]
    dict_list = [parse_str_to_dict(f) for f in file_list]
    df = pd.DataFrame(dict_list)
    df.sort_values(["R", "Y", "X"], inplace=True)

    x_nblocks = df["X"].max()
    y_nblocks = df["Y"].max()
    path_list = [os.path.join(img_dir, p) for p in df["path"].to_list()]
    print('getting values for remapping')
    remap_dict = get_remapping_for_border_values(path_list, x_nblocks, y_nblocks, overlap)

    with tif.TiffFile(path_list[0]) as TF:
        block_shape = list(TF.series[0].shape)
        dtype = TF.series[0].dtype
        npages = len(TF.pages)
        try:
            ome_meta = TF.ome_metadata
        except AttributeError:
            ome_meta = None

    if remap_dict is not None:
        dtype = np.uint32

    if ome_meta is not None:
        big_image_x_size = (x_nblocks * (block_shape[-1] - overlap * 2)) - padding["left"] - padding["right"]
        big_image_y_size = (y_nblocks * (block_shape[-2] - overlap * 2)) - padding["top"] - padding["bottom"]
        ome_meta = re.sub(r'SizeX="\d+"', 'SizeX="' + str(big_image_x_size) + '"', ome_meta)
        ome_meta = re.sub(r'SizeY="\d+"', 'SizeY="' + str(big_image_y_size) + '"', ome_meta)

    with tif.TiffWriter(out_path, bigtiff=True) as TW:
        for p in range(0, npages):
            print('\npage', p)
            print('stitching')
            plane, tile_additions = stitch_plane(path_list, p, x_nblocks, y_nblocks, block_shape, dtype, overlap, padding, remap_dict)
            if remap_dict is not None:
                plane = remap_values(plane, remap_dict, tile_additions, block_shape, overlap, x_nblocks, y_nblocks)
            TW.save(plane, photometric="minisblack", description=ome_meta)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=str, required=True, help='path to directory with images')
    parser.add_argument('-o', type=str, required=True, help='path to output file')
    parser.add_argument('-v', type=int, required=True, default=0, help='overlap size in pixels, default 0')
    parser.add_argument('-p', type=str, default='0,0,0,0',
                        help='image padding that should be removed, 4 comma separated numbers: left, right, top, bottom.' +
                             'Default: 0,0,0,0')

    args = parser.parse_args()

    main(args.i, args.o, args.v, args.p)
