from os import path
import gzip
import sys
import itk
import shutil
import numpy
import vtk

from dicom import createITKImageReader
from itk_utils import convertITKTypeToVTKType, getMetadata, getMetadataList
# To uncomment when running script manually
# from helpers.DICOM import createITKImageReader
# from helpers.itk import convertITKTypeToVTKType, getMetadata, getMetadataList
# from helpers.volume import VolumeData


def convertDICOMVolumeToVTKFile(dicom_directory, output_file_path,
                                overwrite=False,
                                compress=True, blockSize=10 * 1024 * 1024):
    """
    Converts DICOM files in a directory into a VTK file (.vti or .vtkjs)
    """
    # Test output_file_path #
    if not overwrite and path.exists(output_file_path):
        print('Output file already exist', output_file_path)
        return False, None

    itkReader = createITKImageReader(dicom_directory)
    volume = itkReader.GetOutput() if itkReader is not None else None

    if volume is None:
        print('Failed to read DICOM volume', dicom_directory, output_file_path)
        return False, None

    # Test volume data type #
    ITKType = itk.template(volume)[1][0]
    volumeDataType = convertITKTypeToVTKType(ITKType)

    if not volumeDataType:
        print('Data type not handled', ITKType)
        return False

    # Extract volume parameters #
    volumeSize = list(volume.GetLargestPossibleRegion().GetSize())
    volumeOrigin = list(volume.GetOrigin())
    volumeSpacing = list(volume.GetSpacing())
    volumeComponents = volume.GetNumberOfComponentsPerPixel()
    volumeExtent = [
        0, volumeSize[0] - 1,
        0, volumeSize[1] - 1,
        0, volumeSize[2] - 1,
    ]

    # Extract DICOM fields #
    spacingBetweenSlices = getMetadata(itkReader, '0018|0088', float)
    spacingXY = getMetadataList(itkReader, '0028|0030', float)
    orientation = getMetadataList(itkReader, '0020|0037', float)
    position = getMetadataList(itkReader, '0020|0032', float)
    window_width = getMetadata(itkReader, '0028|1051', float)
    window_center = getMetadata(itkReader, '0028|1050', float)
    print("w: {}, c: {}".format(window_width, window_center))

    # Compute spacing #
    if spacingBetweenSlices and spacingXY:
        spacing = spacingXY + [spacingBetweenSlices]
    else:
        spacing = volumeSpacing

    # Get original volume data #
    data = itk.GetArrayViewFromImage(volume).tostring()

    dataImporter = vtk.vtkImageImport()
    dataImporter.CopyImportVoidPointer(data, len(data))

    dataImporter.SetDataExtent(volumeExtent)
    dataImporter.SetWholeExtent(volumeExtent)
    dataImporter.SetDataOrigin(volumeOrigin)
    dataImporter.SetDataScalarType(volumeDataType)
    dataImporter.SetDataSpacing(spacing)
    dataImporter.SetNumberOfScalarComponents(volumeComponents)

    dataImporter.Update()

    originalVolumeData = dataImporter.GetOutput()
    originalVolumeData.SetOrigin((0, 0, 0))

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

        reSliceFilter.SetInputData(originalVolumeData)
        reSliceFilter.SetResliceAxes(reSliceMatrix)
        reSliceFilter.Update()

        processedVolumeData = reSliceFilter.GetOutput()

    else:
        # Generate processed volume data #
        processedVolumeData = originalVolumeData

    # Create writer #
    filename, file_extension = path.splitext(output_file_path)
    if file_extension == '.vti':
        writer = vtk.vtkXMLImageDataWriter()
        writer.SetDataModeToBinary()
        if compress:
            writer.SetCompressorTypeToZLib()
            writer.SetBlockSize(blockSize)
    else:
        writer = vtk.vtkJSONDataSetWriter()

    writer.SetFileName(output_file_path)

    # Set writer volume data #
    writer.SetInputData(processedVolumeData)

    # Write file #
    writer.Write()

    if compress and file_extension != '.vti':
        data_path = os.path.join(output_file_path, 'data')
        for _, _, f in os.walk(data_path):
            for file in f:
                full_path = os.path.join(data_path, file)
                with open(full_path, 'rb') as f_in:
                    as16bits = numpy.fromfile(f_in, numpy.dtype('uint8'))
                    one_uint8, two_uint8, three_uint8, four_uint8 = numpy.reshape(
                        as16bits, (as16bits.shape[0] // 4, 4)).astype(numpy.uint8).T
                    fst_uint12 = (one_uint8 << 4) + (two_uint8 >> 4)
                    snd_uint12 = (two_uint8 << 4) + three_uint8 # %16
                    thr_uint12 = four_uint8
                    as12bits = numpy.reshape(numpy.concatenate(
                        (fst_uint12[:, None], snd_uint12[:, None], thr_uint12[:, None]), axis=1), 3 * fst_uint12.shape[0])
                    as12bits.tofile(full_path + '.as12bits')
                with open(full_path  + '.as12bits', 'rb') as f_in, gzip.open(full_path + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    f_in.close()
                    f_out.close()
                    # os.replace(full_path + '.gz', full_path):

    return True



if __name__ == '__main__':
    """
    Script entry point
    """
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("DICOM", help="a directory containing DICOM files")
    parser.add_argument("output", help="output VTI or VTK.JS")
    parser.add_argument("--no_compress", action="store_true", help="Do not compress")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output")

    args = parser.parse_args()

    convertDICOMVolumeToVTKFile(args.DICOM, args.output, overwrite=args.overwrite, compress=not args.no_compress)
