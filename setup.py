#!/usr/bin/env python3

from pathlib import Path
from setuptools import setup

directory = Path(__file__).resolve().parent
with open(directory / 'readme.txt', encoding='utf-8') as f:
  long_description = f.read()

setup(name='tinygrad',
      version='0.8.0',
      description='You like pytorch? You like micrograd? You love tinygrad! <3',
      author='George Hotz',
      license='MIT',
      long_description=long_description,
      long_description_content_type='text/plain',
      packages = ['tinygrad', 'tinygrad.codegen', 'tinygrad.nn', 'tinygrad.renderer',
                  'tinygrad.runtime', 'tinygrad.runtime.graph', 'tinygrad.shape', 'tinygrad.features'],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
      ],
      install_requires=["numpy", "tqdm", "gpuctypes",
                        "pyobjc-framework-Metal; platform_system=='Darwin'",
                        "pyobjc-framework-libdispatch; platform_system=='Darwin'"],
      python_requires='>=3.8',
      extras_require={
        'llvm': ["llvmlite"],
        'arm': ["unicorn"],
        'triton': ["triton-nightly>=2.1.0.dev20231014192330"],
        'webgpu': ["wgpu>=v0.12.0"],
        'linting': [
            "pylint",
            "mypy",
            "typing-extensions",
            "pre-commit",
            "ruff",
            "types-tqdm",
        ],
        'testing': [
            "torch",
            "pillow",
            "pytest",
            "pytest-xdist",
            "onnx==1.15.0",
            "onnx2torch",
            "opencv-python",
            "tabulate",
            "safetensors",
            "transformers",
            "sentencepiece",
            "tiktoken",
            "librosa",
            "networkx",
            "hypothesis",
        ]
      },
      include_package_data=True)
