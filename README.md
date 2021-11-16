# DICOM-exporter

The DICOM-exporter is used to export DICOM files into file formats including .vtk and .vti.

## Install

```sh
pip install -r requirements.txt
```

## Usage

```sh
python dicom-exporter.py <path/to/dicom/folder> <path/to/output.vti>
```

or for faster loading in vtkjs:

```sh
python dicom-exporter.py <path/to/dicom/folder> <path/to/output.vtkjs>
```
