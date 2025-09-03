import gzip
import logging
import os
import re
import shutil
from pathlib import Path

import itk
import numpy
import vtk

from .dicom import createITKImageReader
from .itk_utils import getMetadata, getMetadataList
# To uncomment when running script manually
# from helpers.DICOM import createITKImageReader
# from helpers.itk import convertITKTypeToVTKType, getMetadata, getMetadataList
# from helpers.volume import VolumeData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VTKLogger")


class IterableEnum(type):
    def __iter__(self):
        for attr in dir(self):
            if not attr.startswith('__'):
                yield attr


class ALLOWED_EXTENSIONS(metaclass=IterableEnum):
    vti = 'vti'
    vtkjs = 'vtkjs'
    png = 'png'
    jpg = 'jpg'
    nii = 'nii'
    img = 'img' # Nifti img/hdr pair


def extractExtensionsFromFilePath(path):
    """
    Given a path, return it without extensions and a list of all its
    extensions (without a leading dot '.').
    """
    path_without_extensions = os.path.join(
        os.path.dirname(path), os.path.basename(path).split(os.extsep)[0]
    )
    extensions = os.path.basename(path).split(os.extsep)[1:]
    return path_without_extensions, extensions


def firstFloat(v):
    return float(v.split('\\')[0])


def readDICOMVolume(
        dicom_directory,
        resample=False
        ):
    """
    Converts DICOM files in a directory into a VTK file (.vti or .vtkjs)
    """
    itk.DataObject.GlobalReleaseDataFlagOn()

    itkReader = createITKImageReader(dicom_directory)
    volume = itkReader.GetOutput() if itkReader is not None else None

    if volume is None:
        print('Failed to read DICOM volume', dicom_directory)
        return None

    # Extract DICOM fields #
    bits_stored = getMetadata(itkReader, '0028|0101', int)
    position = getMetadataList(itkReader, '0020|0032', float)
    orientation = getMetadataList(itkReader, '0020|0037', float)
    # spacingXY = getMetadataList(itkReader, '0028|0030', float)

    window_center = getMetadata(itkReader, '0028|1050', firstFloat)
    window_width = getMetadata(itkReader, '0028|1051', firstFloat)
    del itkReader

    # Get original volume data #
    volumeData = itk.vtk_image_from_image(volume)
    del volume

    # Compute volume data #
    if resample:
        # Set origin to 0
        volumeData.SetOrigin((0, 0, 0))
        if orientation and position:
            # Compute transform matrix #
            # X direction #
            orientationX = orientation[0: 3]
            directionXIndex = orientationX.index(max(orientationX, key=abs))
            directionX = [0, 0, 0]

            if orientationX[directionXIndex] > 0:
                directionX[directionXIndex] = 1
            else:
                directionX[directionXIndex] = -1

            # Y direction #
            orientationY = orientation[3: 6]
            directionYIndex = orientationY.index(max(orientationY, key=abs))
            directionY = [0, 0, 0]

            if orientationY[directionYIndex] > 0:
                directionY[directionYIndex] = 1
            else:
                directionY[directionYIndex] = -1

            # Z direction #
            directionZ = tuple(numpy.cross(directionX, directionY))

            # Transformation matrix #
            transformationMatrix = [
                directionX[0], directionY[0], directionZ[0], position[0],
                directionX[1], directionY[1], directionZ[1], position[1],
                directionX[2], directionY[2], directionZ[2], position[2],
                0, 0, 0, 1,
            ]

            reSliceMatrix = vtk.vtkMatrix4x4()

            reSliceMatrix.DeepCopy(transformationMatrix)
            reSliceMatrix.Invert()

            # Slice volume data #
            reSliceFilter = vtk.vtkImageReslice()
            reSliceFilter.SetInputData(volumeData)
            reSliceFilter.SetResliceAxes(reSliceMatrix)
            reSliceFilter.Update()

            volumeData.ShallowCopy(reSliceFilter.GetOutput())
        # Set direction matrix to identity
        volumeData.SetDirectionMatrix(vtk.vtkMatrix3x3())

    # Set Field Data #
    window_level = vtk.vtkFieldData()
    window_level_array = vtk.vtkFloatArray()
    window_level_array.SetName('window_level')
    window_level_array.SetNumberOfComponents(2)
    window_level_array.InsertNextTuple((window_center, window_width))
    window_level.AddArray(window_level_array)
    volumeData.SetFieldData(window_level)
    del window_level
    del window_level_array

    return volumeData, bits_stored


def delete_with_suffix(path: str, suffix: str = None, overwrite: bool = True):
    """
    Delete a file/folder and optionally its suffixed variants in the same directory.
    
    Args:
        path (str): Absolute path to the base file/folder.
        suffix (str, optional): 
            - None: delete only the exact file/folder
            - "_": delete the exact file/folder and any with suffix starting with "_"
        overwrite (bool): If False, it does not delete the file but print a warning.
    """
    base_path = Path(path).resolve()
    directory = base_path.parent
    stem = base_path.stem
    extension = base_path.suffix

    if suffix is None:
        # Exact match only
        regex = rf"^{re.escape(stem)}{re.escape(extension)}$"
    else:
        # Match exact + suffix variants
        regex = rf"^{re.escape(stem)}(?:{re.escape(suffix)}.+)?{re.escape(extension)}$"

    pattern = re.compile(regex)

    for f in directory.iterdir():
        if pattern.match(f.name):
            if overwrite is False:
                logger.error(f" Would delete: {f}")
                return False
            else:
                try:
                    if f.is_file():
                        f.unlink()
                        logger.debug(f"Deleted file: {f}")
                    elif f.is_dir():
                        shutil.rmtree(f)
                        logger.debug(f"Deleted directory: {f}")
                except Exception as e:
                    logger.error(f"Error deleting {f}: {e}")
                    return False
    return True


def convertDICOMVolumeToVTKFile(
        dicom_directory,
        output_file_path,
        overwrite=False,
        compress=True,
        convert_12_bits=False,
        resample=False,
        blockSize=10 * 1024 * 1024,
        slices=[],
        apply_window_level=False
        ):
    """
    Converts DICOM files in a directory into a VTK file (.vti or .vtkjs)
    slices: list of slice indexes to export (only for png/jpg), empty to
    export all slices. if values are floats, then they represent a percentage
    of the volume depth. (0.5 = middle slice)
    """
    itk.DataObject.GlobalReleaseDataFlagOn()

    _, file_extensions = extractExtensionsFromFilePath(output_file_path)
    # only handling single file_extensions for now
    file_extension = file_extensions[-1] if len(file_extensions) > 0 else ''

    if file_extension not in ALLOWED_EXTENSIONS:
        logger.error('Unknown file extension \'' + file_extension + '\'')
        return False, None

    # Test output_file_path #
    may_have_suffix = ('_'
                       if file_extension in [ALLOWED_EXTENSIONS.png,
                                             ALLOWED_EXTENSIONS.jpg]
                       else None)
    suffix = may_have_suffix if len(slices) != 1 else None
    cleared = delete_with_suffix(output_file_path, may_have_suffix, overwrite)
    if not cleared:
        return False, 'Output path could not be cleared'

    # Extract DICOM fields #
    volumeData, bits_stored = readDICOMVolume(dicom_directory,
                                              resample=resample)

    # Create writer #
    if file_extension == ALLOWED_EXTENSIONS.vti:
        writer = vtk.vtkXMLImageDataWriter()
        writer.SetDataModeToBinary()
        if compress:
            writer.SetCompressorTypeToZLib()
            writer.SetBlockSize(blockSize)
        writer.SetFileName(output_file_path)
    elif file_extension == ALLOWED_EXTENSIONS.vtkjs:
        writer = vtk.vtkJSONDataSetWriter()
        writer.GetArchiver().SetArchiveName(output_file_path)
    elif file_extension in [ALLOWED_EXTENSIONS.nii, ALLOWED_EXTENSIONS.img]:
        writer = vtk.vtkNIFTIImageWriter()
        m4 = vtk.vtkMatrix4x4()
        [m4.SetElement(i, j, volumeData.GetDirectionMatrix().GetElement(i, j)) for i in range(3) for j in range(3)]

        writer.SetQFormMatrix(m4)
        writer.SetSFormMatrix(m4)
        writer.SetFileName(output_file_path)
    elif file_extension == ALLOWED_EXTENSIONS.png:
        writer = vtk.vtkPNGWriter()
    elif file_extension == ALLOWED_EXTENSIONS.jpg:
        writer = vtk.vtkJPEGWriter()

    # Write file #
    if file_extension in [ALLOWED_EXTENSIONS.png, ALLOWED_EXTENSIONS.jpg]:
        input = volumeData
        # Extract slice
        extractVOI = vtk.vtkExtractVOI()
        if apply_window_level:
            window_level_array = volumeData.GetFieldData().GetArray(
                'window_level')

            # Get the first tuple (we stored window_center, window_width)
            window_center, window_width = window_level_array.GetTuple2(0)
            shift = - (window_center - window_width / 2)
            scale = 255.0 / window_width
            logger.info(f"Apply window level "
                        f"W:{window_center}, L:{window_width}")

            rescaler = vtk.vtkImageShiftScale()
            rescaler.SetInputData(input)
            rescaler.SetOutputScalarTypeToUnsignedChar()
            rescaler.SetShift(shift)
            rescaler.SetScale(scale)
            rescaler.ClampOverflowOn()

            reslice = vtk.vtkImageReslice()
            reslice.SetInputConnection(rescaler.GetOutputPort())
            reslice.SetOutputSpacing(volumeData.GetSpacing()[0],
                                     -volumeData.GetSpacing()[1], # flip Y
                                     volumeData.GetSpacing()[2])
            # reslice.Update()
            extractVOI.SetInputConnection(reslice.GetOutputPort())
        else:
            extractVOI.SetInputData(volumeData)

        writer.SetInputConnection(extractVOI.GetOutputPort())

        base, ext = os.path.splitext(output_file_path)
        pattern = f"{base}{suffix}%04d{ext}"

        extent = volumeData.GetExtent()
        dimension = extent[5] - extent[4] + 1
        int_slices = [slice if isinstance(slice, int) else
                      int(slice * dimension) for slice in slices]

        # Write slice by slice
        for i in range(extent[4], extent[5] + 1):
            if slices and i not in int_slices:
                continue
            writer.SetFileName(pattern % i if suffix else output_file_path)

            extractVOI.SetVOI(extent[0], extent[1], extent[2], extent[3], i, i)
            extractVOI.Update()

            # Write slice
            writer.Write()

        del extractVOI
    else:
        # Set writer volume data #
        writer.SetInputData(volumeData)
        writer.Write()

    del volumeData
    del writer

    if file_extension == ALLOWED_EXTENSIONS.vtkjs and (compress or convert_12_bits):
        data_path = os.path.join(output_file_path, 'data')
        for full_path in iterFilePaths(data_path):
            if convert_12_bits and bits_stored == 12:  # we also check if the input file is in 12 bits
                convertFileTo12Bits(full_path)

            if compress:
                compressWithGzip(full_path)

    return True, None


def iterFilePaths(root_path):
    """Walks through all files in all subdirectories of the given root_path and yields their full path."""

    return (os.path.join(root_path, file) for _, _, f in os.walk(root_path) for file in f)


def convertFileTo12Bits(file_path):
    """Converts a file from 16 bit to 12 bit blocks"""

    out_path = file_path + '.as12bits'

    with open(file_path, 'rb') as f_in:
        as16bits = numpy.fromfile(f_in, numpy.dtype('uint8'))
        one_uint8, two_uint8, three_uint8, four_uint8 = numpy.reshape(
            as16bits, (as16bits.shape[0] // 4, 4)).astype(numpy.uint8).T
        fst_uint12 = (one_uint8 << 4) + (two_uint8 >> 4)
        snd_uint12 = (two_uint8 << 4) + three_uint8 # %16
        thr_uint12 = four_uint8
        as12bits = numpy.reshape(numpy.concatenate(
            (fst_uint12[:, None], snd_uint12[:, None], thr_uint12[:, None]), axis=1), 3 * fst_uint12.shape[0])
        as12bits.tofile(out_path)

    os.replace(out_path, file_path)


def compressWithGzip(file_path):
    """Compress a file using gzip"""

    with open(file_path, 'rb') as f_in, gzip.open(file_path + '.gz', 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
        f_in.close()
        f_out.close()
    os.remove(file_path)
