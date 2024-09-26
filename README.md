
# Lab Instrument Control and Automation Software

This software is designed to control and manage various lab instruments used in quantum optics and related experiments. It provides a user-friendly graphical interface to interact with multiple instruments, manage experiment configurations, and perform data acquisition in real-time.

## Table of Contents

- [Features](#features)
- [Instruments Supported](#instruments-supported)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [License](#license)

## Features

- **Instrument Control**: Easily connect and control multiple instruments from a single interface.
- **Configurable UI**: The UI adjusts based on the screen resolution and available instruments.
- **Dynamic Instrument Loading**: Automatically detects and loads instruments based on system configuration.
- **Customizable Scanning and Experiment Tools**: Easily set up and manage various scanning routines and experiments.
- **Real-time Feedback**: Provides real-time control and data monitoring for precision experiments.
- **Configuration Management**: Save and load experiment configurations for future use.

## Instruments Supported

The software currently supports the following instruments:
- Rohde & Schwarz Signal Generators
- SmarAct Positioners and Scanners
- Cobolt Lasers
- Picomotor Controllers
- Zelux Cameras
- OPX Quantum Controllers
- AttoCube Positioners

New instruments can be added via the configuration files and corresponding GUI modules.

## Installation

### Prerequisites

- **Python 3.11.9**: Make sure you have Python installed. You can download it from [here](https://www.python.org/downloads/release/python-3119/).
- **pip**: Ensure `pip` is installed for package management.

### Clone the Repository

To get started, clone the repository using the following command:

```bash
git clone https://github.com/Quantum-Transistors-Ltd/QuTi.git
```

### Install Dependencies
Run the following command to install the required Python packages:

```bash
pip install -r PackagesList.txt
```

Usage
Launch the program using the command python main.py.
The main interface will open, displaying a sidebar with instrument icons.
Click on the instrument icons to configure and control each instrument.
Use the "Scanning", "Experiments", and "Configurations" icons to manage different operations.
For detailed instructions on how to configure each instrument, refer to the user manual or the instrument’s help page within the software.

### Configuration
System Configuration
The system configuration is stored in the HotSystem/SystemConfig folder. Before running the software, ensure that your configuration file is correctly set up, defining the instruments and their respective parameters. You can edit these configurations by running the configuration GUI:

### To add support for a new instrument:

Define the instrument in the configuration file (SystemConfig.json).
Create a corresponding GUI module that inherits from the base instrument control class.
Add the instrument image to the HotSystem/SystemConfig/Images/ directory.
Dependencies
The software requires the following Python packages:

dearpygui: For the graphical interface.
numpy: For numerical operations.
SerialDevice: For serial communication with certain instruments.
threading: For managing background tasks.

### Fork the repository.
Create a feature branch (git checkout -b feature-branch).

Commit your changes (git commit -m 'Add new feature').

Push to the branch (git push origin feature-branch).

Create a Pull Request (PR) and describe your changes in detail.

### License
This project is licensed under the MIT License. See the LICENSE file for more details.
