#!/bin/bash

# Specify the path to your requirements.txt file
REQUIREMENTS_FILE="PackagesList.txt"

# Check if the requirements file exists
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: requirements.txt file not found!"
    exit 1
fi

# Install packages using pip
pip install -r "$REQUIREMENTS_FILE"
