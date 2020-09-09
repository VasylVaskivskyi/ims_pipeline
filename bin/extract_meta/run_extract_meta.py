import argparse
import subprocess
import os
import os.path as osp


def main(input_file: str, output_file: str, mapping: str = ''):
    __location__ = osp.realpath(osp.join(os.getcwd(), osp.dirname(__file__)))
    jar_path = osp.join(__location__, 'extract_meta.jar')

    command = 'java -jar {jar_path} {input_file} {output_file} {mapping}'.format(jar_path=jar_path,
                                                                                 input_file=input_file,
                                                                                 output_file=output_file,
                                                                                 mapping=mapping)
    print('extracting raw metadatafrom file' + input_file)
    res = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0:
        print('successfully extracted')
    else:
        raise Exception('There was an error while running the script: \n' + res.stderr.decode('utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=str, help='path to input file')
    parser.add_argument('-o', type=str, help='path to output file')
    parser.add_argument('-m', type=str, default='', help='path to mapping yaml')
    args = parser.parse_args()

    main(args.i, args.o, args.m)
