# DICOM-exporter

The DICOM-exporter is used to export DICOM files into VTK.JS, VTI, PNG, JPEG or Nifti files.

## Install

```sh
pip install .
```

## Usage

```sh
dicom-exporter <path/to/dicom/folder> <path/to/output.vti>
```

or for faster loading in VTK.JS:

```sh
dicom-exporter <path/to/dicom/folder> <path/to/output.vtkjs>
```

Setting the `--convert-12-bits`-flag will convert the resulting VTK file using 12 bits instead of 16 bits per block. This is only applied if the input DICOM files are encoded in 12 bits instead of 16 bits (i.e. BitsStored is 12 in the DICOM metadata).

The output file is compressed using gzip for VTK.JS files and ZLib for VTI files, unless the `--no-compress` flag is set.

Use `--resample` flag to resample the volume using the closest axis aligned direction matrix. This resampling will set the direction matrix to identity (legacy behavior).

## Screenshots

You can take extract slices from a DICOM volume by exporting to PNG or JPEG.

```sh
dicom-exporter <path/to/dicom/folder> <path/to/output.png> --apply_window_level --slices 0 1 2-100 1024
```

or extract middle slice using floating numbers as slices

```sh
dicom-exporter <path/to/dicom/folder> <path/to/output.jpeg> --apply_window_level --slices 0.5
```
