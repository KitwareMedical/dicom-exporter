import gzip
import os
import shutil

import itk
import numpy
import vtk

from .dicom import createITKImageReader
from .itk_utils import convertITKTypeToVTKType, getMetadata, getMetadataList
# To uncomment when running script manually
# from helpers.DICOM import createITKImageReader
# from helpers.itk import convertITKTypeToVTKType, getMetadata, getMetadataList
# from helpers.volume import VolumeData

class IterableEnum(type):
    def __iter__(self):
        for attr in dir(self):
            if not attr.startswith('__'):
                yield attr


class ALLOWED_EXTENSIONS(metaclass=IterableEnum):
    vti = 'vti'
    vtkjs = 'vtkjs'


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


def convertDICOMVolumeToVTKFile(
        dicom_directory,
        output_file_path,
        overwrite=False,
        compress=True,
        convert_12_bits=False,
        blockSize=10 * 1024 * 1024
    ):
    """
    Converts DICOM files in a directory into a VTK file (.vti or .vtkjs)
    """
    itk.DataObject.GlobalReleaseDataFlagOn()

    _, file_extensions = extractExtensionsFromFilePath(output_file_path)
    # only handling single file_extensions for now
    file_extension = file_extensions[-1] if len(file_extensions) > 0 else ''

    if not file_extension in ALLOWED_EXTENSIONS:
        print('Unknown file extension \'' + file_extension + '\'')
        return False, None

    # Test output_file_path #
    if os.path.exists(output_file_path):
        if not overwrite:
            print(
                'Output file already exist',
                output_file_path,
                '\nIf you want to overwrite the file add the \'--overwrite\' flag',
            )
            return False, None

        if file_extension == ALLOWED_EXTENSIONS.vti:
            os.unlink(output_file_path)
        elif file_extension == ALLOWED_EXTENSIONS.vtkjs:
            shutil.rmtree(output_file_path)


    itkReader = createITKImageReader(dicom_directory)
    volume = itkReader.GetOutput() if itkReader is not None else None

    if volume is None:
        print('Failed to read DICOM volume', dicom_directory, output_file_path)
        return False, None

    # Extract DICOM fields #
    bits_stored = getMetadata(itkReader, '0028|0101', int)
    position = getMetadataList(itkReader, '0020|0032', float)
    orientation = getMetadataList(itkReader, '0020|0037', float)
    spacingXY = getMetadataList(itkReader, '0028|0030', float)

    window_center = getMetadata(itkReader, '0028|1050', firstFloat)
    window_width = getMetadata(itkReader, '0028|1051', firstFloat)
    del itkReader

    # Get original volume data #
    volumeData = itk.vtk_image_from_image(volume)
    del volume

    volumeData.SetOrigin((0, 0, 0))

    # Compute volume data #
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

    # Create writer #
    if file_extension == ALLOWED_EXTENSIONS.vti:
        writer = vtk.vtkXMLImageDataWriter()
        writer.SetDataModeToBinary()
        if compress:
            writer.SetCompressorTypeToZLib()
            writer.SetBlockSize(blockSize)
        writer.SetFileName(output_file_path)
    else: # vtkjs
        writer = vtk.vtkJSONDataSetWriter()
        writer.GetArchiver().SetArchiveName(output_file_path)

    # Set writer volume data #
    writer.SetInputData(volumeData)

    # Write file #
    writer.Write()
    del volumeData
    del writer

    if file_extension == ALLOWED_EXTENSIONS.vtkjs and (compress or convert_12_bits):
        data_path = os.path.join(output_file_path, 'data')
        for full_path in iterFilePaths(data_path):
            if convert_12_bits and bits_stored == 12: # we also check if the input file is in 12 bits
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
