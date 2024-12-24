import subprocess

def uninstall_all():
    result = subprocess.run(['pip', 'freeze'], capture_output=True, text=True)

    # Check if the command was successful
    if result.returncode == 0:
        # Get the list of installed packages
        installed_packages = result.stdout.splitlines()
        
        # Uninstall all packages
        for package in installed_packages:
            subprocess.run(['pip', 'uninstall', '-y', package])

        print("All packages have been uninstalled.")
    else:
        print(f"Error: {result.stderr}")                                                    
def install_packages():
    # Install each package in the specified order
    for package in packages:
        subprocess.run(["pip", "install", package])

# List of packages in the desired order
packages = [
    "pip",
    "setuptools",
    "wheel",
    "setuptools==65",
    "NumPy",
    "glfw",
    "imgui[full]",
    "dearpygui",
    "pino",
    "pandas",
    "matplotlib",
    "pylablib",
    "PyOpenGL",
    "PyQt5",
    "pythonnet",
    "pyserial",
    "pyvisa-py",
    "pyvisa",
    "pulsestreamer",
    "rohdeschwarz",
    "qm-qua",
    "qualang-tools",
    "C:\\SmarAct\\MCS2\\SDK\\Python\packages\\smaract.ctl-1.4.3.zip",
    "C:\\SmarAct\\MCS2\\SDK\\Python\packages\\smaract.hsdr-1.0.0.zip",
    "C:\\SmarAct\\MCS2\\SDK\\Python\packages\\smaract.si-2.1.6.zip",
    "C:\\WC\\QuTi\\HotSystem\\ExampleZeluxCam\\Scientific Camera Interfaces\\SDK\\Python Toolkit\\thorlabs_tsi_camera_python_sdk_package.zip",
]

b_install = True

print("before:\n=======\n")
subprocess.run(['pip', 'list'])

if b_install:
    install_packages()
else:
    uninstall_all()

print("after:\n======\n")
subprocess.run(['pip', 'list'])