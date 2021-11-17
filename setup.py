from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='dicom_exporter',
    version='1.0.0',
    description='Program to export dicom files to .vti or .vtkjs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/KitwareMedical/dicom-exporter',
    author='Julien Finet',
    author_email='julien.finet@kitware.com',
    classifiers=[ 
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python'
    ],
    keywords='dicom exporter medical',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'dicom-exporter = dicomexporter.cli:main'
        ]
    },
    install_requires=['itk', 'vtk', 'numpy'],
)
