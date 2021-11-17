import argparse
from .exporter import convertDICOMVolumeToVTKFile

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("DICOM", help="a directory containing DICOM files")
    parser.add_argument("output", help="output VTI or VTK.JS")
    parser.add_argument("--no-compress", action="store_true", help="Compression with gzip/ZLib")
    parser.add_argument("--compress-12-bits", action="store_true", help="Compress to 12 bits")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output")

    args = parser.parse_args()

    convertDICOMVolumeToVTKFile(args.DICOM, args.output, overwrite=args.overwrite, compress_gzip=not args.no_compress, compress_12_bits=args.compress_12_bits)
