from os import path
import sys
import itk
import numpy
import vtk

from dicom import createITKImageReader
from itk_utils import convertITKTypeToVTKType, getMetadata, getMetadataList
# To uncomment when running script manually
# from helpers.DICOM import createITKImageReader
# from helpers.itk import convertITKTypeToVTKType, getMetadata, getMetadataList
# from helpers.volume import VolumeData


def convertDICOMVolumeToVTKFile(dicom_directory, output_file_path, blockSize=50 * 1024 * 1024,
                                windowing=None):
    """
    Converts DICOM files in a directory into a VTK file (.vti or .vtkjs)
    """
    # Test output_file_path #
    if path.exists(output_file_path):
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
        writer.SetCompressorTypeToZLib()
        writer.SetBlockSize(blockSize)
    else:
        writer = vtk.vtkJSONDataSetWriter()

    writer.SetFileName(output_file_path)

    # Set writer volume data #
    writer.SetInputData(processedVolumeData)

    # Write file #
    writer.Write()

    # retrieve coordinate of first non empty slices
    scalarRange = None
    if windowing is not None:
        halfWindow = windowing["window"] / 2.0
        scalarRange = (windowing["level"] - halfWindow, windowing["level"] + halfWindow)

    return True



if __name__ == '__main__':
    """
    Script entry point
    """

    if len(sys.argv) != 3:
        print('Usage:', sys.argv[0], '<DICOM file path> <output VTI file path>')
        exitCode = 1
    else:
        convertDICOMVolumeToVTKFile(*sys.argv[1:])
        exitCode = 0

    exit(exitCode)
