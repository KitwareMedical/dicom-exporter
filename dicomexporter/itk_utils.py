import itk
import vtk

def convertITKTypeToVTKType(ITKType):
    """Converts ITK scalar type to VTK scalar type"""

    # Define conversion dictionary #
    ITKTypesToVTKTypes = {
        itk.UC: vtk.VTK_UNSIGNED_CHAR,
        itk.RGBPixel[itk.UC]: vtk.VTK_UNSIGNED_CHAR,
        itk.SC: vtk.VTK_CHAR,
        itk.RGBPixel[itk.UC]: vtk.VTK_UNSIGNED_CHAR,
        itk.US: vtk.VTK_UNSIGNED_SHORT,
        itk.RGBPixel[itk.US]: vtk.VTK_UNSIGNED_SHORT,
        itk.SS: vtk.VTK_SHORT,
        itk.UI: vtk.VTK_UNSIGNED_INT,
        itk.SI: vtk.VTK_INT,
        itk.UL: vtk.VTK_UNSIGNED_LONG,
        itk.SL: vtk.VTK_LONG,
        itk.F: vtk.VTK_FLOAT,
        itk.RGBPixel[itk.F]: vtk.VTK_FLOAT,
        itk.D: vtk.VTK_DOUBLE,
        itk.RGBPixel[itk.D]: vtk.VTK_DOUBLE,
    }

    return ITKTypesToVTKTypes.get(ITKType, False)


def getMetadata(reader, metadataKey, format=None, searchInvertedCaseKey=True):
    """Extract DICOM tags from itkDICOMReader"""

    dictionary = reader.GetMetaDataDictionaryArray()[0]

    if dictionary.HasKey(metadataKey):
        value = dictionary[metadataKey]
        return format(value) if format else value
    elif searchInvertedCaseKey:
        # Keys correspond to DICOM tags which represent hexadecimal numbers
        # 7FD1|1010 will be equivalent to 7fd1|1010. Since itk.MetaDataDictionary is case sensitive,
        # if key wasn't found we will look for the inverted case here.
        invertedCaseKey = metadataKey.lower() if metadataKey.isupper() else metadataKey.upper()
        return getMetadata(reader, invertedCaseKey, format, searchInvertedCaseKey=False)
    else:
        return None


def getMetadataList(reader, metadataKey, format=None):
    """Extract DICOM tags as list from itkDICOMReader"""

    metadata = getMetadata(reader, metadataKey)

    if metadata:
        values = metadata.split('\\')
        return [format(value) for value in values] if format else values
    else:
        return None
