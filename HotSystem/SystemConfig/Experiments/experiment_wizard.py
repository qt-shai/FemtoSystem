import dearpygui.dearpygui as dpg
import xml.etree.ElementTree as ET
import importlib
import sys
import os
import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, List, Optional, Tuple

def main():
    """
    Main function to run the sequence creation wizard.
    """
    # Create a window
    dpg.create_context()

    # Variables to store data
    elements: Dict[str, Dict[str, Any]] = {}
    sequence: List[Dict[str, Any]] = []
    element_y_positions: Dict[str, int] = {}
    system_name: str = ''
    system_module: Any = None
    row_ids: List[int] = []  # To keep track of row IDs for highlighting

    # Import SystemType from SystemConfig
    try:
        from SystemConfig import SystemType
        # Create a list of system names from SystemType
        system_names = [e.value for e in SystemType]
    except Exception as e:
        print(f"Error importing SystemType: {e}")
        system_names = []

    # Special elements
    special_elements = ['align', 'wait', 'wait_for_trigger']

    # Function to load elements and waveforms from system config class
    def load_system_config(sender, app_data, user_data):
        """
        Loads the system configuration based on the selected system name.
        Populates the elements and waveforms available for sequence creation.
        """
        nonlocal system_name, system_module
        system_name = dpg.get_value('system_name_combo').strip()
        if not system_name:
            dpg.configure_item('system_status_text', default_value='Please select a system name.')
            return
        try:
            # Correctly import the system configuration class
            system_config_class_name = f"{system_name}QuaConfig"
            # Import the class from SystemConfig
            module = importlib.import_module('SystemConfig')
            system_config_class = getattr(module, system_config_class_name)
            config = system_config_class()
            elements.clear()
            # Retrieve elements and waveforms from the class
            # Assuming config.get_elements() returns a dict with element names as keys
            for elem_name, elem_value in config.get_elements().items():
                waveforms = {}
                # Assuming each element has 'operations' dict with waveform names
                if 'operations' in elem_value:
                    for op_name in elem_value['operations']:
                        # Store waveform name
                        waveforms[op_name] = {}
                elements[elem_name] = {'waveforms': waveforms}
            # Add special elements
            for special_elem in special_elements:
                elements[special_elem] = {'waveforms': {}}
            dpg.configure_item('system_status_text', default_value=f"Loaded system: {system_name}")
            dpg.hide_item('error_window')
            update_sequence_table()
        except Exception as e:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Error loading system config: {e}")

    # Function to update the sequence table
    def update_sequence_table():
        """
        Updates the sequence table with the current sequence data.
        """
        dpg.delete_item('sequence_table', children_only=True)
        row_ids.clear()  # Clear previous row IDs
        # Add columns if not already added
        if not dpg.get_item_children('sequence_table')[1]:  # Check if columns are already added
            dpg.add_table_column(label='Index', parent='sequence_table', width_fixed=True, init_width_or_weight=30)
            dpg.add_table_column(label='Element', parent='sequence_table', width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(label='Waveform/Elements', parent='sequence_table', width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(label='Duration (ns)', parent='sequence_table')
            dpg.add_table_column(label='Start Time (ns)', parent='sequence_table')
            dpg.add_table_column(label='Frequency (MHz)', parent='sequence_table')
            dpg.add_table_column(label='Amplitude', parent='sequence_table')
            dpg.add_table_column(label='Remove', parent='sequence_table')
        for idx, pulse in enumerate(sequence):
            with dpg.table_row(parent='sequence_table', tag=f'row_{idx}'):
                row_ids.append(f'row_{idx}')
                # Index
                dpg.add_text(str(idx + 1))
                # Element dropdown
                element_items = list(elements.keys())
                element_tag = f'element_combo_{idx}'
                dpg.add_combo(element_items, default_value=pulse.get('element', ''),
                              callback=element_changed, user_data=idx, tag=element_tag, width=150)
                # Waveform dropdown or elements to wait for
                element = pulse.get('element', '')
                waveform_enabled = element not in special_elements or element == 'wait_for_trigger'
                if element == 'wait_for_trigger':
                    waveform_items = ['all'] + list(elements.keys())
                    dpg.add_combo(waveform_items, default_value=pulse.get('waveform', 'all'),
                                  tag=f'waveform_combo_{idx}', callback=waveform_changed, user_data=idx,
                                  enabled=waveform_enabled, width=150)
                elif element in special_elements:
                    waveform_items = []
                    dpg.add_combo(waveform_items, default_value='',
                                  tag=f'waveform_combo_{idx}', callback=waveform_changed, user_data=idx,
                                  enabled=False, width=150)
                else:
                    waveform_items = list(elements[element]['waveforms'].keys()) if element in elements else []
                    dpg.add_combo(waveform_items, default_value=pulse.get('waveform', ''),
                                  tag=f'waveform_combo_{idx}', callback=waveform_changed, user_data=idx,
                                  enabled=waveform_enabled, width=150)
                # Duration input
                duration_enabled = element not in special_elements or element == 'wait'
                duration_tag = f'duration_input_{idx}'
                dpg.add_input_text(default_value=str(pulse.get('duration', '')), callback=duration_changed,
                                   user_data=idx, width=100, enabled=duration_enabled, tag=duration_tag)
                # Start time input
                start_time_tag = f'start_time_input_{idx}'
                dpg.add_input_text(default_value=str(pulse.get('start_time', '')), callback=start_time_changed,
                                   user_data=idx, width=100, tag=start_time_tag)
                # Frequency input
                frequency_enabled = element not in special_elements
                frequency_tag = f'frequency_input_{idx}'
                dpg.add_input_text(default_value=str(pulse.get('frequency', '')), callback=frequency_changed,
                                   user_data=idx, width=100, enabled=frequency_enabled, tag=frequency_tag)
                # Amplitude input
                amplitude_enabled = element not in special_elements
                amplitude_tag = f'amplitude_input_{idx}'
                dpg.add_input_text(default_value=str(pulse.get('amplitude', '')), callback=amplitude_changed,
                                   user_data=idx, width=100, enabled=amplitude_enabled, tag=amplitude_tag)
                # Remove button
                dpg.add_button(label='Remove', callback=remove_pulse, user_data=idx)

    def element_changed(sender, app_data, user_data):
        """
        Callback when an element is changed in the table.
        Updates the waveform dropdown accordingly.
        """
        idx = user_data
        sequence[idx]['element'] = app_data
        waveform_tag = f'waveform_combo_{idx}'
        duration_tag = f'duration_input_{idx}'
        frequency_tag = f'frequency_input_{idx}'
        amplitude_tag = f'amplitude_input_{idx}'

        if app_data == 'wait_for_trigger':
            waveform_enabled = True
            waveform_items = ['all'] + list(elements.keys())
            dpg.configure_item(waveform_tag, items=waveform_items, enabled=waveform_enabled)
            # Set default value if current is invalid
            current_value = dpg.get_value(waveform_tag)
            if current_value not in waveform_items:
                dpg.set_value(waveform_tag, 'all')
                sequence[idx]['waveform'] = 'all'
        elif app_data in special_elements:
            waveform_enabled = False
            dpg.configure_item(waveform_tag, items=[], enabled=False)
            sequence[idx]['waveform'] = ''
        else:
            waveform_enabled = True
            waveform_items = list(elements[app_data]['waveforms'].keys())
            dpg.configure_item(waveform_tag, items=waveform_items, enabled=True)
            # Update waveform value if not valid
            current_waveform = sequence[idx].get('waveform', '')
            if current_waveform not in waveform_items:
                sequence[idx]['waveform'] = waveform_items[0] if waveform_items else ''
                dpg.set_value(waveform_tag, sequence[idx]['waveform'])
        # Enable or disable other fields based on element
        duration_enabled = app_data not in special_elements or app_data == 'wait'
        frequency_enabled = app_data not in special_elements
        amplitude_enabled = app_data not in special_elements
        dpg.configure_item(duration_tag, enabled=duration_enabled)
        dpg.configure_item(frequency_tag, enabled=frequency_enabled)
        dpg.configure_item(amplitude_tag, enabled=amplitude_enabled)

    def waveform_changed(sender, app_data, user_data):
        """
        Callback when a waveform is changed in the table.
        Updates the sequence data.
        """
        idx = user_data
        sequence[idx]['waveform'] = app_data

    def duration_changed(sender, app_data, user_data):
        """
        Callback when the duration is changed.
        Validates and updates the sequence data.
        """
        idx = user_data
        try:
            value = float(app_data)
            if value <= 0:
                raise ValueError("Duration must be positive.")
            sequence[idx]['duration'] = value
        except ValueError as e:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Row {idx+1} - {str(e)}")

    def start_time_changed(sender, app_data, user_data):
        """
        Callback when the start time is changed.
        Validates and updates the sequence data.
        """
        idx = user_data
        try:
            value = float(app_data)
            if value < 0:
                raise ValueError("Start time must be non-negative.")
            sequence[idx]['start_time'] = value
        except ValueError as e:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Row {idx+1} - {str(e)}")

    def frequency_changed(sender, app_data, user_data):
        """
        Callback when the frequency is changed.
        Validates and updates the sequence data.
        """
        idx = user_data
        try:
            if app_data.strip() == '':
                sequence[idx]['frequency'] = None
                return
            value = float(app_data)
            sequence[idx]['frequency'] = value
        except ValueError as e:
            sequence[idx]['frequency'] = None
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Row {idx+1} - Invalid frequency value.")

    def amplitude_changed(sender, app_data, user_data):
        """
        Callback when the amplitude is changed.
        Validates and updates the sequence data.
        """
        idx = user_data
        try:
            if app_data.strip() == '':
                sequence[idx]['amplitude'] = None
                return
            value = float(app_data)
            sequence[idx]['amplitude'] = value
        except ValueError as e:
            sequence[idx]['amplitude'] = None
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Row {idx+1} - Invalid amplitude value.")

    def remove_pulse(sender, app_data, user_data):
        """
        Removes a pulse from the sequence.
        """
        idx = user_data
        if 0 <= idx < len(sequence):
            sequence.pop(idx)
            update_sequence_table()
        else:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value='Invalid pulse index.')

    def add_pulse(sender, app_data, user_data):
        """
        Adds a new pulse to the sequence.
        """
        if not elements:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value='Load a system configuration first.')
            return
        # Add a new empty pulse
        default_element = list(elements.keys())[0]
        default_waveform = list(elements[default_element]['waveforms'].keys())[0] if elements[default_element]['waveforms'] else ''
        new_pulse = {
            'element': default_element,
            'waveform': default_waveform,
            'duration': 100.0,
            'start_time': 0.0,
            'frequency': None,
            'amplitude': None
        }
        sequence.append(new_pulse)
        update_sequence_table()

    # Function to update the pulse visualization
    def update_pulse_visualization():
        """
        Updates the visual representation of the sequence on the plot.
        """
        # Clear the previous series
        y_axis = 'y_axis'
        # Clear any existing series on the y-axis
        dpg.delete_item(y_axis, children_only=True)
        if not sequence:
            return
        # For each element, plot the pulses
        elements_in_sequence = list(set(p['element'] for p in sequence if p['element'] not in special_elements))
        elements_in_sequence.sort()
        element_y_positions.clear()
        for idx, element in enumerate(elements_in_sequence):
            element_y_positions[element] = idx + 1
        # Set y-axis ticks
        y_ticks: List[Tuple[float, str]] = []
        for element, y in element_y_positions.items():
            y_ticks.append((float(y), str(element)))
        # dpg.set_axis_ticks('y_axis', y_ticks)
        # For each pulse, draw a line from start to end at y
        for pulse in sequence:
            element = pulse['element']
            if element in special_elements:
                continue  # Skip special elements in visualization
            y = element_y_positions[element]
            start = float(pulse['start_time'])
            duration = float(pulse['duration'])
            end = start + duration
            times = [start, end]
            ys = [y, y]
            # Add line series to the y_axis
            dpg.add_line_series(times, ys, label=element, parent='y_axis')

    # Function to generate the sequence function code
    def generate_sequence_function(sender, app_data, user_data):
        """
        Generates the code for the sequence and displays it in a window.
        """
        # Generate code similar to the example functions
        function_code = generate_sequence_code(sequence)
        # Display the generated code in a window
        with dpg.window(label='Generated Sequence Code', width=600, height=400, modal=True):
            dpg.add_input_text(default_value=function_code, multiline=True, width=580, height=360)

    # Function to generate the sequence code
    def generate_sequence_code(sequence: List[Dict[str, Any]]) -> str:
        """
        Generates the Python code for the sequence.
        """
        code_lines = []
        sequence_name = dpg.get_value('sequence_name_input')
        code_lines.append(f"def {sequence_name}(self):")
        code_lines.append("    with program() as self.quaPGM:")
        code_lines.append("        # Define variables")
        code_lines.append("        times = declare(int, size=100)")
        code_lines.append("        counts = declare(int)")
        code_lines.append("        # Sequence")
        sorted_pulses = sorted(sequence, key=lambda p: float(p.get('start_time', 0)))
        current_time = 0.0
        for pulse in sorted_pulses:
            element = pulse['element']
            if element == 'align':
                code_lines.append("        align()")
                continue
            elif element == 'wait_for_trigger':
                elements_to_wait = pulse.get('waveform', 'all')
                if elements_to_wait == 'all' or not elements_to_wait:
                    code_line = "        wait_for_trigger()"
                else:
                    code_line = f"        wait_for_trigger('{elements_to_wait}')"
                code_lines.append(code_line)
                continue
            elif element == 'wait':
                duration_ns = float(pulse['duration'])
                duration_cycles = int(duration_ns // 4)
                code_lines.append(f"        wait({duration_cycles})")
                continue
            waveform = pulse['waveform']
            duration_ns = float(pulse['duration'])
            duration_cycles = int(duration_ns // 4)
            start_time_ns = float(pulse['start_time'])
            wait_time_ns = start_time_ns - current_time
            if wait_time_ns > 0:
                wait_cycles = int(wait_time_ns // 4)
                code_line = f"        wait({wait_cycles}, '{element}')"
                code_lines.append(code_line)
                current_time += wait_time_ns
            if pulse.get('frequency') is not None:
                frequency = pulse['frequency']
                code_line = f"        update_frequency('{element}', {frequency} * self.u.MHz)"
                code_lines.append(code_line)
            if pulse.get('amplitude') is not None:
                amplitude = pulse['amplitude']
                code_line = f"        play('{waveform}' * amp({amplitude}), '{element}', duration={duration_cycles})"
            else:
                code_line = f"        play('{waveform}', '{element}', duration={duration_cycles})"
            code_lines.append(code_line)
            current_time += duration_ns
        code_lines.append("    self.qm, self.job = self.QUA_execute()")
        return '\n'.join(code_lines)

    # Function to save sequence to XML
    def save_sequence(sender, app_data, user_data):
        """
        Opens a file dialog to save the sequence to an XML file.
        """
        if not system_name:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value='Please select and load a system name before saving.')
            return
        # Use tkinter filedialog to get the save file path
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML files", "*.xml")])
        if file_path:
            save_sequence_to_file(file_path)
            dpg.set_value('xml_file_text', f"Sequence saved to: {file_path}")

    def save_sequence_to_file(file_path: str):
        """
        Saves the sequence to the specified XML file.
        """
        root = ET.Element('sequence')
        root.set('system_name', system_name)
        sequence_name = dpg.get_value('sequence_name_input')
        root.set('sequence_name', sequence_name)
        for pulse in sequence:
            pulse_elem = ET.SubElement(root, 'pulse')
            for key, value in pulse.items():
                pulse_elem.set(key, str(value))
        tree = ET.ElementTree(root)
        tree.write(file_path)

    # Function to load sequence from XML
    def load_sequence(sender, app_data, user_data):
        """
        Opens a file dialog to load a sequence from an XML file.
        """
        # Use tkinter filedialog to get the open file path
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml")])
        if file_path:
            load_sequence_from_file(file_path)

    def load_sequence_from_file(file_path: str):
        """
        Loads the sequence from the specified XML file.
        """
        nonlocal system_name, system_module, sequence
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            loaded_system_name = root.get('system_name')
            if not loaded_system_name:
                raise ValueError("System name not found in XML.")
            # Load system config
            dpg.set_value('system_name_combo', loaded_system_name)
            load_system_config(None, None, None)
            # Set sequence name
            sequence_name = root.get('sequence_name', 'generated_sequence')
            dpg.set_value('sequence_name_input', sequence_name)
            # Clear current sequence
            sequence.clear()
            # Load pulses
            for pulse_elem in root.findall('pulse'):
                pulse = {}
                for key in ['element', 'waveform', 'duration', 'start_time', 'frequency', 'amplitude']:
                    value = pulse_elem.get(key)
                    if key in ['duration', 'start_time']:
                        value = float(value) if value not in [None, 'None', ''] else 0.0
                    elif key in ['frequency', 'amplitude']:
                        value = float(value) if value not in [None, 'None', ''] else None
                    pulse[key] = value
                sequence.append(pulse)
            update_sequence_table()
            dpg.set_value('xml_file_text', f"Sequence loaded from: {file_path}")
            dpg.hide_item('error_window')
        except Exception as e:
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=f"Error loading sequence: {e}")

    # Function to close error window
    def close_error_window(sender, app_data, user_data):
        """
        Closes the error window.
        """
        dpg.hide_item('error_window')

    # Function to sort the sequence by start times and check for conflicts
    def sort_and_check_sequence(sender, app_data, user_data):
        """
        Sorts the sequence based on start times and checks for conflicts.
        Conflicting rows are highlighted in red.
        """
        # Sort the sequence
        sequence.sort(key=lambda p: p.get('start_time', 0.0))
        # Check for conflicts
        conflicts = []
        element_times = {}
        conflict_indices = set()
        for idx, pulse in enumerate(sequence):
            element = pulse['element']
            if element in special_elements:
                continue
            start = pulse['start_time']
            duration = pulse['duration']
            end = start + duration
            if element not in element_times:
                element_times[element] = []
            # Check for overlaps
            for s_idx, (s, e) in element_times[element]:
                if (start < e and start >= s) or (end > s and end <= e) or (start <= s and end >= e):
                    conflicts.append(f"Conflict on element '{element}' between pulses at times {s} and {start}")
                    conflict_indices.update([idx, s_idx])
            element_times[element].append((idx, (start, end)))
        # Reset row colors
        for row_id in row_ids:
            dpg.bind_item_theme(row_id, None)
        if conflicts:
            conflict_message = '\n'.join(conflicts)
            dpg.show_item('error_window')
            dpg.configure_item('error_text', default_value=conflict_message)
            # Highlight conflicting rows
            for idx in conflict_indices:
                row_id = f'row_{idx}'
                with dpg.theme() as red_theme:
                    with dpg.theme_component(dpg.mvAll):
                        dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (255, 102, 102), category=dpg.mvThemeCat_Core)
                    dpg.bind_item_theme(row_id, red_theme)
        else:
            dpg.configure_item('system_status_text', default_value="Sequence sorted with no conflicts.")
        update_sequence_table()

    # Create GUI elements
    with dpg.window(label='Sequence Creation Wizard', width=800, height=700, tag='main_window'):
        dpg.add_text('System Name:')
        # Create a combo box for system names
        dpg.add_combo(system_names, label='', tag='system_name_combo', width=200)
        dpg.add_button(label='Load System Config', callback=load_system_config)
        dpg.add_text('', tag='system_status_text')
        # Sequence name input
        dpg.add_input_text(label='Sequence Name', tag='sequence_name_input', width=200, default_value='generated_sequence')
        dpg.add_separator()
        dpg.add_text('', tag='xml_file_text')
        # Error window
        with dpg.window(label='Error', show=False, tag='error_window', modal=True, width=400, height=200):
            dpg.add_text('', tag='error_text')
            dpg.add_button(label='Close', callback=close_error_window)
        # Sequence table
        dpg.add_button(label='Add Pulse', callback=add_pulse)
        dpg.add_button(label='Sort and Check Sequence', callback=sort_and_check_sequence)
        with dpg.table(header_row=True, resizable=True, policy=dpg.mvTable_SizingStretchProp,
                       borders_innerV=True, borders_outerV=True, borders_innerH=True, borders_outerH=True,
                       tag='sequence_table'):
            pass  # Columns will be added in update_sequence_table()
        dpg.add_button(label='Update Graph', callback=update_pulse_visualization)
        # Generate sequence function button
        dpg.add_button(label='Generate Sequence Function', callback=generate_sequence_function)
        # Save and load sequence
        dpg.add_button(label='Save Sequence', callback=save_sequence)
        dpg.add_button(label='Load Sequence', callback=load_sequence)
        # Pulse visualization
        with dpg.plot(label='Pulse Visualization', tag='pulse_plot', height=300):
            dpg.add_plot_axis(dpg.mvXAxis, label='Time (ns)', tag='x_axis')
            dpg.add_plot_axis(dpg.mvYAxis, label='Elements', tag='y_axis')

        # Instructions (optional)
        dpg.add_separator()
        dpg.add_text('Instructions:')
        dpg.add_text('1. Select a system name from the dropdown and click "Load System Config".')
        dpg.add_text('2. Enter a sequence name.')
        dpg.add_text('3. Click "Add Pulse" to add a new pulse to your sequence.')
        dpg.add_text('4. Edit the pulse parameters directly in the table.')
        dpg.add_text('5. Use "Sort and Check Sequence" to sort pulses and check for conflicts.')
        dpg.add_text('6. Click "Update Graph" to visualize the sequence.')
        dpg.add_text('7. Use "Save Sequence" and "Load Sequence" to manage your sequences.')
        dpg.add_text('8. Click "Generate Sequence Function" to generate code for your sequence.')

    dpg.create_viewport(title='Sequence Creation Wizard', width=820, height=720)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window('main_window', True)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == '__main__':
    main()
