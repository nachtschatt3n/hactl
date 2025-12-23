#!/usr/bin/env python3
"""
hactl - Home Assistant Control CLI
Setup configuration
"""

from setuptools import setup, find_packages
import os

# Read README if it exists
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = 'kubectl-style CLI for Home Assistant API'

setup(
    name='hactl',
    version='1.0.0',
    description='kubectl-style CLI for Home Assistant API',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/cberg-home-assistant',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'python-dotenv>=1.0.0',
        'pyyaml>=6.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-mock>=3.11.1',
        ]
    },
    entry_points={
        'console_scripts': [
            'hactl=hactl.cli:cli',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Topic :: Home Automation',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
)
