import os

import itk


def getGDCMDICOMFileNames(folderPath):
    """Get correctly sorted DICOM file paths of a given folder using GDCM"""
    dicom_filename_identifier = itk.GDCMSeriesFileNames.New()

    # Find all dicom files
    dicom_filename_identifier.SetDirectory(folderPath)
    seriesUID = dicom_filename_identifier.GetSeriesUIDs()

    filenames = []
    if len(seriesUID) == 0:
        files = [name for name in os.listdir(folderPath)
                 if os.path.isfile(os.path.join(folderPath, name))]
        print('No series found in ', files)
        return None
    elif len(seriesUID) > 1:
        print('Series volume count should be 1, got ', len(seriesUID), 'instead.\
            Only the first serie is processed.')

    filenames = dicom_filename_identifier.GetFileNames(seriesUID[0])
    return filenames


def createITKImageReader(directory):
    """
    Returns the original DICOM volume as an ITK pipeline.
    The pipeline is made of:
        - 1 ImageSeriesReader
        - 1 CastImageFilter if the values are signed and need to be casted
    The pipeline behaves as an ITK filter (has SetInput()/GetOutput())
    """

    # Get the DICOM files paths in a SORTED list. The list of files is ordered by
    # itk.GDCMSeriesFileNames using their 3D position or Instance Number as a fallback
    # Do not alter the order of the serie.
    filePaths = getGDCMDICOMFileNames(directory)

    if not filePaths:
        return None

    # Configure reader #
    ImageType = itk.Image[itk.US, 3]

    dicom_reader = itk.ImageSeriesReader[ImageType].New()
    io = itk.GDCMImageIO.New()
    io.LoadPrivateTagsOn()
    dicom_reader.SetImageIO(io)

    pipeline = itk.pipeline()
    pipeline.connect(dicom_reader)
    pipeline.expose("MetaDataDictionaryArray")

    dicom_reader.SetFileNames(filePaths)

    # Populate metadata
    try:
        dicom_reader.Update()
    except BaseException as e:
        print('Failed to read DICOM volume', e)
        return None

    if (io.GetComponentType() == itk.CommonEnums.IOComponent_SHORT or
        io.GetComponentType() == itk.CommonEnums.IOComponent_INT):
        # Cast images to signed short
        SignedImageType = itk.Image[itk.SS, 3]
        castFilter = itk.CastImageFilter[ImageType, SignedImageType].New()
        castFilter.SetInput(dicom_reader.GetOutput())
        pipeline.append(castFilter)
        castFilter.Update()

    return pipeline
