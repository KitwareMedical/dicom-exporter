# DICOM-exporter

The DICOM-exporter is used to export DICOM files into the VTK file format (.vti or .vtkjs).

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

Setting the `--compress-12-bits`-flag will compress the resulting VTK file using 12 bits instead of 16 bits per block. This only works if the input DICOM files are encoded in 12 bits instead of 16 bits.
