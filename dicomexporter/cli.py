import argparse
from .exporter import convertDICOMVolumeToVTKFile


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("DICOM", help="a directory containing DICOM files")
    parser.add_argument("output", help="output VTI or VTK.JS")
    parser.add_argument("--no-compress", action="store_true", help="Do not compress output with ZLib (VTI) or gzip (VTK.JS)")
    parser.add_argument("--convert-12-bits", action="store_true", help="Converts from 16 to 12 bits")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output")
    parser.add_argument("--resample", action="store_true", help="Resample using the closest axis aligned orientation, discard volume orientation")

    args = parser.parse_args()

    convertDICOMVolumeToVTKFile(
        args.DICOM,
        args.output,
        overwrite=args.overwrite,
        compress=not args.no_compress,
        convert_12_bits=args.convert_12_bits,
        resample=args.resample,
    )
