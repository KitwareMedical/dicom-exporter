import argparse
from .exporter import convertDICOMVolumeToVTKFile


def parse_number_or_range(s):
    """Parse a single number or range 'start-end' into a list of integers."""
    if "-" in s:
        # only allow integer ranges
        parts = s.split("-", 1)
        if not parts[0].isdigit() or not parts[1].isdigit():
            raise argparse.ArgumentTypeError(f"Invalid range (only integers allowed): {s}")
        start, end = map(int, parts)
        if end < start:
            raise argparse.ArgumentTypeError(f"Invalid range: {s}")
        return list(range(start, end + 1))
    else:
        # single number: preserve int or float
        if "." in s:
            return [float(s)]
        else:
            return [int(s)]


def parse_numbers_or_ranges(values):
    """Flatten a list of number/range strings into a single list of integers."""
    result = []
    for val in values:
        result.extend(parse_number_or_range(val))
    return result


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("DICOM", help="a directory containing DICOM files")
    parser.add_argument("output", help="output VTI, VTK.JS, PNG, JPG or NII file")
    parser.add_argument("--no-compress", action="store_true", help="Do not compress output with ZLib (VTI) or gzip (VTK.JS)")
    parser.add_argument("--convert-12-bits", action="store_true", help="Converts from 16 to 12 bits")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output")
    parser.add_argument("--resample", action="store_true", help="Resample using the closest axis aligned orientation, discard volume orientation")
    parser.add_argument("--slices", nargs="*", default=[], help="Slice indexes or ranges (e.g. 1 5-10 12), empty to export all slices")
    parser.add_argument("--apply_window_level", action="store_true", help="Rescale to 8 bits using DICOM window center/width (only for PNG/JPG output)")

    args = parser.parse_args()

    convertDICOMVolumeToVTKFile(
        args.DICOM,
        args.output,
        overwrite=args.overwrite,
        compress=not args.no_compress,
        convert_12_bits=args.convert_12_bits,
        resample=args.resample,
        slices=parse_numbers_or_ranges(args.slices),
        apply_window_level=args.apply_window_level
    )
