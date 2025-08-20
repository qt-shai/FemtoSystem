import time
import os, sys
import copy
import numpy as np
import dearpygui.dearpygui as dpg
from Common import toggle_sc, show_msg_window
from Common import Experiment
from HW_wrapper import HW_devices as hw_devices, smaractMCS2
from typing import Union, Optional, Callable, List, Tuple, Any
import os, shutil, subprocess, sys, threading, time, traceback, math, copy, JobTesting_OPX
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized, create_scan_vectors, loadFromCSV, \
    open_file_dialog, create_gaussian_vector,\
    open_file_dialog, create_gaussian_vector, create_counts_vector, OptimizerMethod, find_max_signal

def StartScan3D(self, add_scan=False, isLeftScan=False):  # currently flurascence scan
    if len(self.positioner.LoggedPoints) == 3:
        with open('logged_points.txt', 'w') as f:
            for point in self.positioner.LoggedPoints:
                f.write(f"{point[0]},{point[1]},{point[2]}\n")

    cam = self.HW.camera
    if cam.constantGrabbing:
        toggle_sc(reverse=False)

    if dpg.does_item_exist("btnOPX_Stop"):
        print("Stopping previous experiment before scanning...")
        self.btnStop()
        time.sleep(0.5)
        # print('Please stop other experiment before scanning')
        # return

    print("start scan steps")
    start_time = time.time()
    print(f"start_time: {self.format_time(start_time)}")

    # init
    self.exp = Experiment.SCAN
    self.GUI_ParametersControl(isStart=False)
    self.to_xml()  # save last params to xml
    self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")  # moved near end of scan
    # GUI - convert Start Scan to Stop scan
    dpg.disable_item("btnOPX_StartScan")

    self.scan_reset_data()
    self.scan_reset_positioner()
    self.scan_get_current_pos(_isDebug=True)
    self.initial_scan_Location = list(self.positioner.AxesPositions)

    # Loop over three axes and populate scan coordinates
    scan_coordinates = []
    self.N_scan = []
    for i in range(3):
        if self.b_Scan[i]:
            if i == 0 and isLeftScan:
                axis_values = np.array(self.GenVector(min=-self.L_scan[i], max=0,
                                                      delta=self.dL_scan[i]) * 1e3 + np.array(
                    self.initial_scan_Location[i])).astype(np.int64)
            else:
                axis_values = np.array(self.GenVector(min=-self.L_scan[i] / 2, max=self.L_scan[i] / 2,
                                                      delta=self.dL_scan[i]) * 1e3 + np.array(
                    self.initial_scan_Location[i])).astype(np.int64)
        else:
            axis_values = np.array([self.initial_scan_Location[i]]).astype(np.int64)  # Ensure it's an array

        self.N_scan.append(len(axis_values))
        scan_coordinates.append(axis_values)
    self.V_scan = scan_coordinates

    self.Xv = self.V_scan[0] / 1e6  # x data of the Smaract values from the csv
    self.Yv = self.V_scan[1] / 1e6  # y data of the Smaract values from the csv
    self.Zv = self.V_scan[2] / 1e6  # z data of the Smaract values from the csv

    # goto scan start location
    for ch in range(3):
        self.positioner.MoveABSOLUTE(ch, scan_coordinates[ch][0])
        time.sleep(self.t_wait_motionStart)  # allow motion to start
    self.scan_get_current_pos(True)

    Nx = self.N_scan[0]
    Ny = self.N_scan[1]
    Nz = self.N_scan[2]

    self.scan_intensities = np.zeros((Nx, Ny, Nz))
    self.scan_data = self.scan_intensities
    # self.idx_scan = [0, 0, 0]

    self.startLoc = [self.V_scan[0][0] / 1e6, self.V_scan[1][0] / 1e6, self.V_scan[2][0] / 1e6]
    self.endLoc = [self.V_scan[0][-1] / 1e6, self.V_scan[1][-1] / 1e6, self.V_scan[2][-1] / 1e6]

    self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0], startLoc=self.startLoc,
                   endLoc=self.endLoc, current_z=self.V_scan[2][-1] * 1e-6)

    # Start Qua PGM
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                     num_measurement_per_array=Nx)
    res_handles = self.job.result_handles
    self.counts_handle = res_handles.get("counts_scanLine")
    self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

    # init measurements index
    previousMeas_idx = 0  # used as workaround to reapet line if an error occur in number of measurements
    meas_idx = 0
    self.all_hwp_angles = []
    self.all_att_percent = []
    self.all_y_scan = []
    current_hwp = 10000  # initial non-physical value

    for i in range(self.N_scan[2]):  # Z
        if self.stopScan:
            break
        if 2 in self.positioner.channels:
            self.positioner.MoveABSOLUTE(2, int(self.V_scan[2][i]))

        j = 0
        while j < self.N_scan[1]:  # Y
            if self.stopScan:
                break
            self.positioner.MoveABSOLUTE(1, int(self.V_scan[1][j]))
            # self.dir = self.dir * -1  # change direction to create S shape scan
            V = []

            Line_time_start = time.time()
            for k in range(self.N_scan[0]):
                if self.stopScan:
                    break

                if k == 0:
                    V = list(self.V_scan[0])

                # Z correction
                if self.b_Zcorrection and len(self.positioner.LoggedPoints) == 3:
                    currentP = np.array([int(V[k]), int(self.V_scan[1][j]), int(self.V_scan[2][i])])
                    refP = copy.deepcopy(self.initial_scan_Location)
                    refP[2] = int(self.V_scan[2][i])
                    p_new = int(self.Z_correction(refP, currentP))
                    self.positioner.MoveABSOLUTE(2, p_new)

                # move to next X - when trigger the OPX will measure and append the results
                self.positioner.MoveABSOLUTE(0, int(V[k]))
                self.scan_get_current_pos()

                # self.positioner.generatePulse(channel=0) # should trigger measurement by smaract trigger
                self.qm.set_io2_value(self.ScanTrigger)  # should trigger measurement by QUA io
                time.sleep(1e-3)  # wait for measurement do occur
                # time.sleep(2*self.total_integration_time * 1e-3 + 5e-3)  # wait for measurement do occur
                if not self.stopScan:
                    res = self.qm.get_io2_value()
                while (not self.stopScan) and (res.get('int_value') == self.ScanTrigger):
                    res = self.qm.get_io2_value()

            self.positioner.MoveABSOLUTE(0, int(self.V_scan[0][0]))
            self.scan_get_current_pos()

            # fetch X scanned results
            if self.counts_handle.is_processing():
                self.counts_handle.wait_for_values(1)
                self.meas_idx_handle.wait_for_values(1)
                time.sleep(0.1)
                meas_idx = self.meas_idx_handle.fetch_all()
                counts = self.counts_handle.fetch_all()
                print(f"meas_idx = {meas_idx} | counts.size = {counts.size}")

                # self.qmm.clear_all_job_results()
                self.scan_intensities[:, j, i] = counts / self.total_integration_time  # counts/ms = Kcounts/s
                self.UpdateGuiDuringScan(self.scan_intensities[:, :, i], use_fast_rgb=True)

            if (meas_idx - previousMeas_idx) % counts.size == 0:  # if no skips in measurements
                j = j + 1
                # self.prepare_scan_data(max_position_x_scan = self.V_scan[0][-1], min_position_x_scan = self.V_scan[0][0],start_pos=[int(self.V_scan[0][0]), int(self.V_scan[1][0]), int(self.V_scan[2][0])])
                # self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.scanFN)
            else:
                print(
                    "****** error: ******\nNumber of measurements is not consistent with excpected.\nthis line will be repeated.")
                pass

            previousMeas_idx = meas_idx

            # eswtimate time left
            Line_time_End = time.time()
            elapsed_time = time.time() - start_time
            delta = (Line_time_End - Line_time_start)  # line time
            estimated_time_left = delta * ((self.N_scan[2] - i - 1) * self.N_scan[1] + (self.N_scan[1] - j - 1))
            estimated_time_left = estimated_time_left if estimated_time_left > 0 else 0
            dpg.set_value("Scan_Message", f"time left: {self.format_time(estimated_time_left)}")

        # Save after each Z slice
        current_z_um = int(self.V_scan[2][i])  # already in microns (because *1e3 earlier)
        slice_filename = self.create_scan_file_name(local=True) + f"_z{current_z_um}"
        self.prepare_scan_data(max_position_x_scan=self.V_scan[0][-1],
                               min_position_x_scan=self.V_scan[0][0],
                               start_pos=[int(self.V_scan[0][0]),
                                          int(self.V_scan[1][0]),
                                          int(self.V_scan[2][i])])  # current Z
        self.save_scan_data(Nx, Ny, Nz, slice_filename)

    # back to start position
    for i in self.positioner.channels:
        self.positioner.MoveABSOLUTE(i, self.initial_scan_Location[i])
    self.scan_get_current_pos(True)

    # save data to csv
    self.prepare_scan_data(max_position_x_scan=self.V_scan[0][-1], min_position_x_scan=self.V_scan[0][0],
                           start_pos=[int(self.V_scan[0][0]), int(self.V_scan[1][0]), int(self.V_scan[2][0])])
    # self.prepare_scan_data()
    fn = self.save_scan_data(Nx, Ny, Nz, self.create_scan_file_name(local=False))  # 333
    self.writeParametersToXML(fn + ".xml")
    self.last_loaded_file = fn + ".csv"
    filename_only = os.path.basename(fn)
    show_msg_window(f"{filename_only}")
    # total experiment time
    end_time = time.time()
    # print(f"end_time: {end_time}")
    elapsed_time = end_time - start_time
    print(f"number of points ={self.N_scan[0] * self.N_scan[1] * self.N_scan[2]}")
    print(f"Elapsed time: {elapsed_time:.0f} seconds")

    if not (self.stopScan):
        self.btnStop()

    return self.scan_data

def scan3d_femto_pulses(self):  # currently flurascence scan
    if len(self.positioner.LoggedPoints) == 3:
        with open('logged_points.txt', 'w') as f:
            for point in self.positioner.LoggedPoints:
                f.write(f"{point[0]},{point[1]},{point[2]}\n")
    cam = self.HW.camera
    if cam.constantGrabbing:
        toggle_sc(reverse=False)

    if dpg.does_item_exist("btnOPX_Stop"):
        print("Stopping previous experiment before scanning...")
        self.btnStop()
        time.sleep(0.5)

    Att_percent = float(self.pharos.getBasicTargetAttenuatorPercentage())
    dpg.set_value("femto_attenuator", int(Att_percent))

    self.Shoot_Femto_Pulses = True

    parent = sys.stdout.parent

    print("start scan steps")
    start_time = time.time()
    print(f"start_time: {self.format_time(start_time)}")

    # init
    self.exp = Experiment.SCAN
    self.GUI_ParametersControl(isStart=False)
    self.to_xml()  # save last params to xml
    self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")  # moved near end of scan
    # GUI - convert Start Scan to Stop scan
    dpg.disable_item("btnOPX_StartScan")

    isDebug = True

    self.scan_reset_data()
    self.scan_reset_positioner()
    self.scan_get_current_pos(_isDebug=isDebug)
    self.initial_scan_Location = list(self.positioner.AxesPositions)

    if self.Shoot_Femto_Pulses:
        # --- Delete all files in the folder ---
        image_folder = "Q:/QT-Quantum_Optic_Lab/expData/Images/"
        if os.path.exists(image_folder):
            for filename in os.listdir(image_folder):
                file_path = os.path.join(image_folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

        p_femto = {}
        item_tags = ["femto_attenuator", "femto_increment_att", "femto_increment_hwp","femto_increment_hwp_anneal","femto_anneal_pulse_count","femto_anneal_threshold"]
        for tag in item_tags:
            p_femto[tag] = dpg.get_value(tag)
            print(f"{tag}: {p_femto[tag]}")
        initial_hwp_angle = self.kdc_101.get_current_position()
        print(f"!!!!!!!!!! Current HWP position is {initial_hwp_angle:.2f}")
        # Store original attenuator value
        original_attenuator_value = self.pharos.getBasicTargetAttenuatorPercentage()
        print(f"!!!!!!!!!! Original attenuator value is {original_attenuator_value:.2f}")
        self.pharos.setAdvancedTargetPulseCount(1) # Setting defect pulse number to 1 !!!

    # Loop over three axes and populate scan coordinates
    scan_coordinates = []
    self.N_scan = []

    # --- Check dx, dy step size ---
    dx_nm = self.dL_scan[0] * 1e3  # convert to nm
    dy_nm = self.dL_scan[1] * 1e3  # convert to nm
    if dx_nm < 500 or dy_nm < 500:
        print(f"Scan step too small: dx = {dx_nm:.1f} nm, dy = {dy_nm:.1f} nm (must be ≥ 500 nm)")
        return

    for i in range(3):
        if self.b_Scan[i]:
            axis_values = np.array(self.GenVector(min=-self.L_scan[i] / 2, max=self.L_scan[i] / 2,
                                                  delta=self.dL_scan[i]) * 1e3 + np.array(
                self.initial_scan_Location[i])).astype(np.int64)
        else:
            axis_values = np.array([self.initial_scan_Location[i]]).astype(np.int64)  # Ensure it's an array

        self.N_scan.append(len(axis_values))
        scan_coordinates.append(axis_values)
    self.V_scan = scan_coordinates

    # goto scan start location
    for ch in range(3):
        self.positioner.MoveABSOLUTE(ch, scan_coordinates[ch][0])
        time.sleep(self.t_wait_motionStart)  # allow motion to start
    self.scan_get_current_pos(True)

    Nx = self.N_scan[0]
    Ny = self.N_scan[1]
    Nz = self.N_scan[2]

    self.scan_intensities = np.zeros((Nx, Ny, Nz))
    self.scan_data = self.scan_intensities
    #self.idx_scan = [0, 0, 0]

    self.startLoc = [self.V_scan[0][0] / 1e6, self.V_scan[1][0] / 1e6, self.V_scan[2][0] / 1e6]
    self.endLoc = [self.V_scan[0][-1] / 1e6, self.V_scan[1][-1] / 1e6, self.V_scan[2][-1] / 1e6]

    self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0], startLoc=self.startLoc,
                   endLoc=self.endLoc)  # required review

    # Start Qua PGM
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                     num_measurement_per_array=1) # here i changed Nx to 1

    res_handles = self.job.result_handles
    self.counts_handle = res_handles.get("counts_scanLine")
    self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

    # init measurements index
    previousMeas_idx = 0  # used as workaround to reapet line if an error occur in number of measurements
    meas_idx = 0
    self.all_hwp_angles = []
    self.all_att_percent = []
    self.all_y_scan = []
    self.anneal_results = []  # Each entry: [timestamp_in_seconds, count_value]
    self.all_pulse_energies = []

    current_hwp = 10000  # initial non-physical value

    for i in range(self.N_scan[2]):  # Z
        if self.stopScan:
            break
        if 2 in self.positioner.channels:
            self.positioner.MoveABSOLUTE(2, int(self.V_scan[2][i]))

        j = 0
        while j < self.N_scan[1]:  # Y
            if self.stopScan:
                break
            self.positioner.MoveABSOLUTE(1, int(self.V_scan[1][j]))
            #self.dir = self.dir * -1  # change direction to create S shape scan
            V = []

            if self.Shoot_Femto_Pulses:
                if p_femto["femto_increment_att"] == 0:
                    new_hwp_angle = initial_hwp_angle + p_femto["femto_increment_hwp"] * j
                    if abs(new_hwp_angle - current_hwp) > 0.01:
                        # print(f"!!!!! set HWP to {new_hwp_angle:.2f} deg !!!!!")
                        current_hwp=self.set_hwp_angle(new_hwp_angle)
                    self.all_y_scan.append(self.V_scan[1][j])
                    self.all_hwp_angles.append(current_hwp)
                else:
                    attenuator_value = j*p_femto["femto_increment_att"]+p_femto["femto_attenuator"]
                    if attenuator_value > 100:
                        attenuator_value = 100
                    print(f"!!!!! set attenuator to {attenuator_value} !!!!!")
                    self.pharos.setBasicTargetAttenuatorPercentage(attenuator_value)
                        # Wait until the attenuator reaches the set value
                    get_attenuator_value = self.pharos.getBasicTargetAttenuatorPercentage()
                    while abs(get_attenuator_value - attenuator_value) > 0.1:
                        time.sleep(0.1)
                        get_attenuator_value = self.pharos.getBasicTargetAttenuatorPercentage()
                    self.all_y_scan.append(self.V_scan[1][j])
                    self.all_att_percent.append(attenuator_value)

            mode = dpg.get_value(parent.femto_gui.combo_tag)
            _, pulse_energy_nJ = parent.femto_gui.calculate_laser_pulse(HWP_deg=current_hwp, Att_percent=p_femto["femto_attenuator"], mode = mode)

            x_val = self.V_scan[0][-1] / 1e6 + 1
            y_val = self.V_scan[1][j] / 1e6 + 0.5

            text_tag = f"energy_text_{i}_{j}"  # Unique tag per scan coordinate
            dpg.draw_text(
                pos=(x_val, y_val),
                text=f"{pulse_energy_nJ:.1f} nJ",
                size=1,
                color=(255, 255, 255, 255),
                parent="plot_draw_layer",
                tag=text_tag
            )
            self.all_pulse_energies.append(pulse_energy_nJ)

            Line_time_start = time.time()
            for k in range(self.N_scan[0]):
                if self.stopScan:
                    break

                if k == 0:
                    V = list(self.V_scan[0])

                # Z correction
                if self.b_Zcorrection and len(self.positioner.LoggedPoints) == 3:
                    currentP = np.array([int(V[k]), int(self.V_scan[1][j]), int(self.V_scan[2][i])])
                    refP = copy.deepcopy(self.initial_scan_Location)
                    refP[2] = int(self.V_scan[2][i])
                    p_new = int(self.Z_correction(refP, currentP))
                    self.positioner.MoveABSOLUTE(2, p_new)

                # move to next X - when trigger the OPX will measure and append the results
                self.positioner.MoveABSOLUTE(0, int(V[k]))
                self.scan_get_current_pos()

                if self.Shoot_Femto_Pulses:
                    print(f"{pulse_energy_nJ:8.2f} nJ | Pulse! x={self.V_scan[0][k]} | Y = {self.V_scan[1][j]} | HWP = {current_hwp:.2f}°")
                    self.pharos.enablePp()
                    time.sleep(0.2)
                    current_state = self.pharos.getAdvancedIsPpEnabled()
                    while current_state:
                        time.sleep(0.2)
                        current_state = self.pharos.getAdvancedIsPpEnabled()
                    # Anneal !!!!!!!!!!!!!!!!!!!!!!!!!!!
                    if p_femto["femto_increment_hwp_anneal"]>0:
                        n_pulses_anneal = p_femto["femto_anneal_pulse_count"]
                        n_pulse_defect = self.pharos.getAdvancedTargetPulseCount()

                        hwp_anneal_angle = round(current_hwp-p_femto["femto_increment_hwp_anneal"],2)
                        if hwp_anneal_angle < 0:
                            dpg.set_value("Scan_Message",
                                          f"Anneal HWP angle < 0: {hwp_anneal_angle:.2f}° — Aborting anneal")
                            return
                        print(f"!!!!! set HWP to {hwp_anneal_angle:.2f} deg !!!!!")
                        current_hwp=self.set_hwp_angle(hwp_anneal_angle)

                        print(f"Anneal Pulses!")

                        # Init data storage
                        self.anneal_counts_all = []
                        self.anneal_times_all = []

                        anneal_time_start = time.time()
                        stop_anneal = False
                        above_start_time = None

                        self.pharos.setAdvancedTargetPulseCount(n_pulses_anneal)
                        self.pharos.enablePp()
                        time.sleep(0.2)

                        # Loop while annealing is ongoing
                        while self.pharos.getAdvancedIsPpEnabled() and not stop_anneal:
                            # 🟢 GET updated threshold live from GUI:
                            anneal_threshold = dpg.get_value("femto_anneal_threshold")

                            # Trigger QUA acquisition
                            self.qm.set_io2_value(self.ScanTrigger)
                            time.sleep(1e-3)

                            if not self.stopScan:
                                res = self.qm.get_io2_value()
                            while (not self.stopScan) and (res.get('int_value') == self.ScanTrigger):
                                res = self.qm.get_io2_value()

                            # Fetch results
                            if self.counts_handle.is_processing():
                                self.counts_handle.wait_for_values(1)
                                self.meas_idx_handle.wait_for_values(1)
                                time.sleep(0.1)

                                anneal_meas_idx = self.meas_idx_handle.fetch_all()
                                anneal_counts = self.counts_handle.fetch_all() / self.total_integration_time
                                current_time = time.time() - anneal_time_start
                                current_count = float(anneal_counts[-1]) if len(anneal_counts) > 0 else 0

                                self.anneal_counts_all.append(anneal_counts)
                                self.anneal_times_all.append(current_time)
                                self.anneal_results.append([
                                    current_time,
                                    current_count,
                                    self.V_scan[0][k],
                                    self.V_scan[1][j],
                                    round(current_hwp, 2)
                                ])

                                self.lock.acquire()
                                dpg.set_value("series_counts", [self.anneal_times_all, self.anneal_counts_all])
                                dpg.fit_axis_data('x_axis')
                                dpg.fit_axis_data('y_axis')
                                self.lock.release()

                                print(f"Count: {current_count:.2f}")

                                # threshold‐based stop
                                if current_count > anneal_threshold:
                                    if above_start_time is None:
                                        above_start_time = time.time()
                                    elif (time.time() - above_start_time) >= 2.0:
                                        print(f"Anneal stopped: signal > {anneal_threshold:.1f} for ≥2 s")
                                        stop_anneal = True
                                        self.pharos.disablePp()
                                        break
                                else:
                                    above_start_time = None

                        # rewind back to defect parameters
                        self.pharos.setAdvancedTargetPulseCount(n_pulse_defect)

                        new_hwp_angle = current_hwp + p_femto["femto_increment_hwp_anneal"]
                        print(f"!!!!! set HWP to {new_hwp_angle:.2f} deg !!!!!")
                        current_hwp=self.set_hwp_angle(new_hwp_angle)

                # self.positioner.generatePulse(channel=0) # should trigger measurement by smaract trigger
                if not self.stopScan:
                    self.qm.set_io2_value(self.ScanTrigger)  # should trigger measurement by QUA io
                time.sleep(1e-3)  # wait for measurement do occur
                # time.sleep(2*self.total_integration_time * 1e-3 + 5e-3)  # wait for measurement do occur
                if not self.stopScan:
                    res = self.qm.get_io2_value()
                while (not self.stopScan) and (res.get('int_value') == self.ScanTrigger):
                    res = self.qm.get_io2_value()

                # Fetch one count
                if self.counts_handle.is_processing():
                    self.counts_handle.wait_for_values(1)
                    time.sleep(0.1)
                    count_k = self.counts_handle.fetch_all()
                    if len(count_k) > 0:
                        self.scan_intensities[k, j, i] = count_k[-1] / self.total_integration_time
                        self.UpdateGuiDuringScan(self.scan_intensities[:, :, i], use_fast_rgb=True)

            self.positioner.MoveABSOLUTE(0, int(self.V_scan[0][0]))
            self.scan_get_current_pos()
            j = j + 1

            # estimate time left
            Line_time_End = time.time()
            elapsed_time = time.time() - start_time
            delta = (Line_time_End - Line_time_start)  # line time
            estimated_time_left = delta * ((self.N_scan[2] - i - 1) * self.N_scan[1] + (self.N_scan[1] - j - 1))
            estimated_time_left = estimated_time_left if estimated_time_left > 0 else 0
            dpg.set_value("Scan_Message", f"time left: {self.format_time(estimated_time_left)}")

        # Save after each Z slice
        current_z_um = int(self.V_scan[2][i])  # already in microns (because *1e3 earlier)
        slice_filename = self.create_scan_file_name(local=True) + f"_z{current_z_um}"
        self.prepare_scan_data(max_position_x_scan=self.V_scan[0][-1],
                               min_position_x_scan=self.V_scan[0][0],
                               start_pos=[int(self.V_scan[0][0]),
                                          int(self.V_scan[1][0]),
                                          int(self.V_scan[2][i])])  # current Z
        self.save_scan_data(Nx, Ny, Nz, slice_filename)

    # back to start position
    for i in self.positioner.channels:
        self.positioner.MoveABSOLUTE(i, self.initial_scan_Location[i])
    self.scan_get_current_pos(True)


    # Restore HWP or attenuator value after scan
    if self.Shoot_Femto_Pulses:
        if p_femto["femto_increment_att"] == 0:
            name_addition = "hwp"
            print(f"Restoring HWP to {initial_hwp_angle:.2f} deg")
            current_hwp=self.set_hwp_angle(initial_hwp_angle)
        else:
            name_addition = "att"
            print(f"Restoring attenuator to {original_attenuator_value:.2f}%")
            self.pharos.setBasicTargetAttenuatorPercentage(original_attenuator_value)
            get_attenuator_value = self.pharos.getBasicTargetAttenuatorPercentage()
            while abs(get_attenuator_value - original_attenuator_value) > 0.1:
                time.sleep(0.1)
                get_attenuator_value = self.pharos.getBasicTargetAttenuatorPercentage()
        file_name = self.create_scan_file_name()
        fileName = file_name + "_" + name_addition
        # RawData_to_save = {'y_data': self.all_y_scan, name_addition: self.all_hwp_angles}
        RawData_to_save = {
            'y_data': self.all_y_scan,
            name_addition: self.all_hwp_angles if name_addition == "hwp" else self.all_att_percent,
            'pulse_energy_nJ': self.all_pulse_energies
        }
        self.save_to_cvs(fileName + ".csv", RawData_to_save)
        self.GUI_ParametersControl(isStart=False)

    # save data to csv
    self.prepare_scan_data(max_position_x_scan=self.V_scan[0][-1], min_position_x_scan=self.V_scan[0][0],
                           start_pos=[int(self.V_scan[0][0]), int(self.V_scan[1][0]), int(self.V_scan[2][0])])
    #self.prepare_scan_data()
    fn = self.save_scan_data(Nx, Ny, Nz, self.create_scan_file_name(local=False))  # 333
    self.writeParametersToXML(fn + ".xml")

    # total experiment time
    end_time = time.time()
    # print(f"end_time: {end_time}")
    elapsed_time = end_time - start_time
    print(f"number of points ={self.N_scan[0] * self.N_scan[1] * self.N_scan[2]}")
    print(f"Elapsed time: {elapsed_time:.0f} seconds")

    # Always save _pulse_data with header
    file_prefix = self.create_scan_file_name(local=False)
    pulse_data_filename = file_prefix + "_pulse_data.csv"

    # Build header parts
    hwp_start = initial_hwp_angle
    hwp_step = p_femto["femto_increment_hwp"]
    hwp_end = hwp_start + hwp_step * self.N_scan[1]
    att_percent = p_femto["femto_attenuator"]

    dx_um = self.dL_scan[0]  # um
    dy_um = self.dL_scan[1]  # um
    Lx_um = self.L_scan[0] # um
    Ly_um = self.L_scan[1] # um
    hwp_ann = p_femto["femto_increment_hwp_anneal"]
    n_pulses_ann = p_femto["femto_anneal_pulse_count"]

    header_line = f"{hwp_start:.1f}:{hwp_step:.1f}:{hwp_end:.1f},{att_percent:.1f}%, dx={dx_um:.0f} dy={dy_um:.0f} Lx={Lx_um:.0f} Ly={Ly_um:.0f} HWPAnn={hwp_ann:.3f} nPlsAnn={n_pulses_ann}"

    # If there are anneal results, write them; else just header
    if self.anneal_results:
        data_to_save = {
            "Time (s)": [row[0] for row in self.anneal_results],
            "Count (kCounts/s)": [row[1] for row in self.anneal_results],
            "X (abs)": [row[2] for row in self.anneal_results],
            "Y (abs)": [row[3] for row in self.anneal_results],
            "HWP (deg)": [row[4] for row in self.anneal_results],
        }
        self.save_to_cvs(pulse_data_filename, data_to_save, header=header_line)
        print(f"Pulse data with anneal saved to: {pulse_data_filename}")
    else:
        # Just write header line
        with open(pulse_data_filename, 'w') as f:
            f.write(header_line + "\n")
        print(f"Pulse header saved to: {pulse_data_filename}")

    self.Shoot_Femto_Pulses = False
    if not (self.stopScan):
        self.btnStop()

def scan3d_with_galvo(self, use_queried_area: bool = False):
    """
    3D scan using galvos for X,Y (Keysight AWG offsets) and positioner for Z.
    X/Y mapping follows kx/ky defaults:
        volts_per_um = 0.128/15
        kx_ratio = 3.3
        ky_ratio = -0.3
    Net offsets:
        CH1 = base_x + Vx + Vy
        CH2 = base_y + Vx*kx_ratio + Vy*ky_ratio

    Notes:
      * Z-correction is DISABLED by request.
      * Prints pre-scan min/max planned voltages for CH1/CH2.
      * If use_queried_area=True, restrict X,Y to self.queried_area (plot query) on XY plane.
    """
    import sys, time
    import numpy as np
    import dearpygui.dearpygui as dpg

    # --- Stop camera & previous OPX job ---
    cam = self.HW.camera
    if getattr(cam, "constantGrabbing", False):
        toggle_sc(reverse=False)
    if dpg.does_item_exist("btnOPX_Stop"):
        print("Stopping previous experiment before scanning...")
        self.btnStop()
        time.sleep(0.5)

    # --- Keysight device (galvo driver) ---
    parent = getattr(sys.stdout, "parent", None)
    gui = getattr(parent, "keysight_gui", None)
    if not gui or not hasattr(gui, "dev"):
        print("ERROR: Keysight AWG GUI/device not available.")
        return
    dev = gui.dev

    # --- kx/ky defaults (same as your handlers) ---
    volts_per_um = gui.volts_per_um
    kx_ratio = gui.kx_ratio
    ky_ratio = gui.ky_ratio

    def pm_to_v(pm):
        """pm (nanometers) -> volts via volts_per_um calibration (uses your 1e-3 conversion)"""
        return np.round(pm * 1e-3 * volts_per_um, 6)

    # ===== NEW: helpers for queried area =====
    def _queried_bounds_rel_um() -> tuple[float, float, float, float] | None:
        """
        Use self.queried_area captured by queryXY_callback (meters) to produce
        (xmin_um, xmax_um, ymin_um, ymax_um) for X,Y scan limits in RELATIVE micrometers.

        Assumes:
          - self.queried_area = (x_min_m, y_min_m, x_max_m, y_max_m) in METERS
          - self.queried_plane == queried_plane.XY
          - Your galvo scan logic expects REL µm (around 0) for X,Y vectors.
        """
        if getattr(self, "queried_area", None) is None:
            return None
        if getattr(self, "queried_plane", None) != queried_plane.XY:
            return None

        try:
            x_min_m, y_min_m, x_max_m, y_max_m = self.queried_area
        except Exception:
            return None

        # Normalize and validate
        if (x_max_m is None) or (y_max_m is None):
            return None
        if x_max_m <= x_min_m or y_max_m <= y_min_m:
            print("WARNING: Queried area is empty/collapsed; ignoring.")
            return None

        # Convert meters -> micrometers for the grid generator
        x_min_um = float(x_min_m) * 1e6
        x_max_um = float(x_max_m) * 1e6
        y_min_um = float(y_min_m) * 1e6
        y_max_um = float(y_max_m) * 1e6

        return x_min_um, x_max_um, y_min_um, y_max_um

    # --- Experiment/GUI bookkeeping ---
    self.exp = Experiment.SCAN
    self.GUI_ParametersControl(isStart=False)
    self.to_xml()
    self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")
    dpg.disable_item("btnOPX_StartScan")

    # --- Reset scan state & read current stage pos ---
    self.scan_reset_data()
    self.scan_reset_positioner()
    try:
        print("Trying to get current position")
        self.scan_get_current_pos(_isDebug=True)
    except Exception as e:
        print(f"ERROR: Failed to get current position: {e}")
        return

    self.initial_scan_Location = list(self.positioner.AxesPositions)  # µm abs

    # --- Read baseline galvo offsets (CH1=X, CH2=Y) ---
    try:
        base_off_x = float(dev.get_current_voltage(1))
        base_off_y = float(dev.get_current_voltage(2))
    except Exception as e:
        print(f"ERROR: Failed to read initial galvo offsets: {e}")
        return

    # --- Build scan vectors: X,Y are REL µm; Z ABS µm around current Z ---
    scan_coordinates, self.N_scan = [], []
    dx_nm = self.dL_scan[0] * 1e3
    dy_nm = self.dL_scan[1] * 1e3
    if dx_nm < 500 or dy_nm < 500:
        print(f"Scan step too small: dx={dx_nm:.1f} nm, dy={dy_nm:.1f} nm (≥500 nm required)")
        return

    centers_um = [0.0, 0.0, float(self.initial_scan_Location[2])]  # X,Y rel center=0; Z abs center=current Z

    # ===== NEW: pick bounds from queried area if requested =====
    queried_bounds = _queried_bounds_rel_um() if use_queried_area else None

    for i in range(3):
        if self.b_Scan[i]:
            if i == 0:  # X axis (REL µm)
                if queried_bounds is not None:
                    x_min_um, x_max_um, _, _ = queried_bounds
                    vec_um = self.GenVector(min=x_min_um, max=x_max_um, delta=self.dL_scan[i])
                else:
                    # previous behavior: start at -Lx and end at 0
                    vec_um = self.GenVector(min=-self.L_scan[i], max=0, delta=self.dL_scan[i])

                vec = vec_um * 1e3  # -> "pm path" in your code (nm units)

            elif i == 1:  # Y axis (REL µm)
                if queried_bounds is not None:
                    _, _, y_min_um, y_max_um = queried_bounds
                    vec_um = self.GenVector(min=y_min_um, max=y_max_um, delta=self.dL_scan[i])
                else:
                    # previous behavior: centered
                    vec_um = self.GenVector(min=-self.L_scan[i] / 2, max=self.L_scan[i] / 2, delta=self.dL_scan[i])

                vec = vec_um * 1e3  # -> nm

            else:  # Z axis (ABS µm)
                zvec_um = self.GenVector(min=-self.L_scan[i] / 2, max=self.L_scan[i] / 2, delta=self.dL_scan[i])
                vec = (np.array(zvec_um) + centers_um[i]).astype(np.int64)  # µm abs

            # dtype as before
            if i == 2:
                axis = np.array(vec, dtype=np.int64)       # Z in µm abs (int)
            else:
                axis = np.array(vec, dtype=np.float64)     # X/Y in nm path (float)

        else:
            axis = np.array([centers_um[i]], dtype=np.float64 if i < 2 else np.int64)

        self.N_scan.append(len(axis))
        scan_coordinates.append(axis)

    self.V_scan = scan_coordinates  # [X_rel_um (nm path), Y_rel_um (nm path), Z_abs_um]
    Nx, Ny, Nz = self.N_scan
    # Keep your exported vectors in meters, as you already do:
    self.Xv = self.V_scan[0] / 1e6  # meters
    self.Yv = self.V_scan[1] / 1e6  # meters
    self.Zv = self.V_scan[2] / 1e6  # meters

    # --- Precompute & print planned voltage bounds (including baselines) ---
    Vx = pm_to_v(self.V_scan[0])[:, None]  # shape (Nx, 1)
    Vy = pm_to_v(self.V_scan[1])[None, :]  # shape (1, Ny)
    ch1_grid = base_off_x + (Vx + Vy)  # CH1 at each (x,y)
    ch2_grid = base_off_y + (Vx * kx_ratio) + (Vy * ky_ratio)  # CH2 at each (x,y)

    ch1_min, ch1_max = float(np.min(ch1_grid)), float(np.max(ch1_grid))
    ch2_min, ch2_max = float(np.min(ch2_grid)), float(np.max(ch2_grid))
    print(f"[Pre-scan] CH1 range: {ch1_min:.4f} V -> {ch1_max:.4f} V  (baseline {base_off_x:.4f} V)")
    print(f"[Pre-scan] CH2 range: {ch2_min:.4f} V -> {ch2_max:.4f} V  (baseline {base_off_y:.4f} V)")

    # ─── Safety check ───
    if ch1_min < -5 or ch1_max > 5 or ch2_min < -5 or ch2_max > 5:
        print("[ERROR] Voltage range exceeds ±5 V limit. Aborting scan.")
        if not self.stopScan:
            self.btnStop()
        return

    try:
        self.positioner.MoveABSOLUTE(2, int(self.V_scan[2][0]))
        time.sleep(self.t_wait_motionStart)
        dev.set_offset(base_off_x, channel=1)
        dev.set_offset(base_off_y, channel=2)
        gui.btn_get_current_parameters()
    except Exception as e:
        print(f"ERROR: Failed initial positioning: {e}")
        return

    # --- Move to initial Z, zero galvo deflection (baseline) ---
    self.scan_get_current_pos(True)

    # --- Allocate arrays & plot first slice ---
    self.scan_intensities = np.zeros((Nx, Ny, Nz))
    self.scan_data = self.scan_intensities
    self.startLoc = [self.V_scan[0][0] / 1e6, self.V_scan[1][0] / 1e6, self.V_scan[2][0] / 1e6]
    self.endLoc   = [self.V_scan[0][-1] / 1e6, self.V_scan[1][-1] / 1e6, self.V_scan[2][-1] / 1e6]
    self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0],
                   startLoc=self.startLoc, endLoc=self.endLoc)

    # --- QUA acquisition setup ---
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                     num_measurement_per_array=1)
    res_handles = self.job.result_handles
    self.counts_handle = res_handles.get("counts_scanLine")
    self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

    print("start scan steps")
    start_time = time.time()
    print(f"start_time: {self.format_time(start_time)}")

    try:
        for iz in range(Nz):  # Z slices
            if self.stopScan:
                break

            z_abs = int(self.V_scan[2][iz])
            self.positioner.MoveABSOLUTE(2, z_abs)
            time.sleep(self.t_wait_motionStart)

            row_t0 = time.time()
            j = 0
            while j < Ny:  # Y rows
                if self.stopScan:
                    break

                y_pm = float(self.V_scan[1][j])
                Vy_ = pm_to_v(y_pm)

                # X line
                for k in range(Nx):
                    if self.stopScan:
                        break
                    x_pm = float(self.V_scan[0][k])
                    Vx_ = pm_to_v(x_pm)

                    # === Apply combined X,Y galvo move with kx/ky defaults ===
                    ch1 = base_off_x + (Vx_ + Vy_)
                    ch2 = base_off_y + (Vx_ * kx_ratio) + (Vy_ * ky_ratio)
                    dev.set_offset(ch1, channel=1)
                    dev.set_offset(ch2, channel=2)

                    # Galvo settle (if needed)
                    time.sleep(getattr(self, "t_wait_galvo_settle", 0.001))

                    # Trigger QUA measurement
                    if not self.stopScan:
                        self.qm.set_io2_value(self.ScanTrigger)
                    time.sleep(1e-3)
                    if not self.stopScan:
                        res = self.qm.get_io2_value()
                    while (not self.stopScan) and (res.get('int_value') == self.ScanTrigger):
                        res = self.qm.get_io2_value()

                    # Fetch one count
                    if self.counts_handle.is_processing():
                        self.counts_handle.wait_for_values(1)
                        time.sleep(0.05)
                        counts = self.counts_handle.fetch_all()
                        if len(counts) > 0:
                            self.scan_intensities[k, j, iz] = counts[-1] / self.total_integration_time
                            self.UpdateGuiDuringScan(self.scan_intensities[:, :, iz], use_fast_rgb=True)

                # return X component to baseline at row end (keep Y at its row value until next row change)
                dev.set_offset(base_off_x + Vy_, channel=1)
                dev.set_offset(base_off_y + (Vy_ * ky_ratio), channel=2)

                j += 1

                # Time-left estimate
                dt = time.time() - row_t0
                est_left = dt * ((Nz - iz - 1) * Ny + (Ny - j))
                dpg.set_value("Scan_Message", f"time left: {self.format_time(max(est_left, 0))}")

            # --- Save after each Z slice ---
            slice_fn = self.create_scan_file_name(local=True) + f"_z{int(self.V_scan[2][iz])}"
            self.prepare_scan_data(
                max_position_x_scan=self.V_scan[0][-1] if Nx else 0.0,
                min_position_x_scan=self.V_scan[0][0] if Nx else 0.0,
                start_pos=[
                    int(self.V_scan[0][0] if Nx else 0.0),
                    int(self.V_scan[1][0] if Ny else 0.0),
                    int(self.V_scan[2][iz]),
                ],
            )
            self.save_scan_data(Nx, Ny, Nz, slice_fn)

    finally:
        # Restore galvos to baselines
        try:
            dev.set_offset(base_off_x, channel=1)
            dev.set_offset(base_off_y, channel=2)
            gui.btn_get_current_parameters()
        except Exception as e:
            print(f"WARNING: Failed to restore galvo offsets: {e}")

        # Return stage to initial XYZ
        for ch in self.positioner.channels:
            self.positioner.MoveABSOLUTE(ch, self.initial_scan_Location[ch])
        self.scan_get_current_pos(True)

    # --- Final save & params ---
    self.prepare_scan_data(
        max_position_x_scan=self.V_scan[0][-1] if Nx else 0.0,
        min_position_x_scan=self.V_scan[0][0] if Nx else 0.0,
        start_pos=[
            int(self.V_scan[0][0] if Nx else 0.0),
            int(self.V_scan[1][0] if Ny else 0.0),
            int(self.V_scan[2][0] if Nz else self.initial_scan_Location[2]),
        ],
    )
    fn = self.save_scan_data(Nx, Ny, Nz, self.create_scan_file_name(local=False))
    self.writeParametersToXML(fn + ".xml")

    # Stats
    elapsed = time.time() - start_time
    print(f"number of points = {Nx * Ny * Nz}")
    print(f"Elapsed time: {elapsed:.0f} seconds")
    if not self.stopScan:
        self.btnStop()

def start_scan_general(self, move_abs_fn, read_in_pos_fn, get_positions_fn, device_reset_fn, x_vec=None, y_vec=None,
                       z_vec=None, current_experiment=Experiment.SCAN, is_not_ple=True,
                       UseDisplayDuring=True,
                       meas_continuously=False,
                       check_srs_stability=False):
    self.refSignal = 0

    x_vec = x_vec if x_vec else []
    y_vec = y_vec if y_vec else []
    z_vec = z_vec if z_vec else []

    Nx, Ny, Nz = len(x_vec) or 1, len(y_vec) or 1, len(z_vec) or 1
    dim = sum(bool(v) for v in [x_vec, y_vec, z_vec])
    print(f"Starting {dim}D scan: Nx={Nx}, Ny={Ny}, Nz={Nz}")

    start_time = time.time()
    print(f"start_time: {self.format_time(start_time)}")

    self.exp = current_experiment
    self.GUI_ParametersControl(isStart=False)
    self.to_xml()  # Save last params to XML
    self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")

    # Copy relevant config & image files, if they exist
    try:
        file_mappings = [
            {
                "src": 'Q:/QT-Quantum_Optic_Lab/expData/Images/Zelux_Last_Image.png',
                "dest_local": self.create_scan_file_name(local=True) + "_ZELUX.png",
                "dest_remote": self.create_scan_file_name(local=False) + "_ZELUX.png"
            },
            {
                "src": 'C:/WC/HotSystem/map_config.txt',
                "dest_local": self.create_scan_file_name(local=True) + "_map_config.txt",
                "dest_remote": self.create_scan_file_name(local=False) + "_map_config.txt"
            }
        ]
        for file_map in file_mappings:
            for dest in [file_map["dest_local"], file_map["dest_remote"]]:
                if os.path.exists(file_map["src"]):
                    shutil.copy(file_map["src"], dest)
                    print(f"File moved to {dest}")
                else:
                    print(f"Source file {file_map['src']} does not exist.")
    except Exception as e:
        print(f"Error occurred: {e}")

    self.stopScan = False
    self.scan_Out = []
    self.scan_intensities = []

    if device_reset_fn:
        device_reset_fn()

    # Disable the “Start Scan” button in the GUI
    if dpg.does_item_exist("btnOPX_StartScan"):
        dpg.disable_item("btnOPX_StartScan")

    # Prepare internal references
    self.X_vec, self.Y_vec, self.Z_vec = [], [], []
    self.Y_vec_ref = []
    self.iteration = 0

    # For original code continuity, store these as internal references
    self.Xv, self.Yv, self.Zv = x_vec, y_vec, z_vec
    self.V_scan = []
    self.initial_scan_Location = []

    # Acquire initial positions (for reference)
    # This can be done via get_positions_fn() or from the device directly.
    expected_axes = 3  # X, Y, Z
    for ax in range(expected_axes):
        read_in_pos_fn(ax)  # Ensure in position
    current_positions = get_positions_fn()
    if isinstance(current_positions, float):
        current_positions = [current_positions]  # Wrap single float in a list
    initial_pos=current_positions
    initial_pos=[round(initial_pos[0] / 1e12, 0)*1e12]
    initial_pos_offset=current_positions[0]-initial_pos[0]

    # Pad with zeros if fewer than expected_axes
    if self.exp == Experiment.PLE:
        self.initial_scan_Location = [x_vec[0]] + [0] * (expected_axes - len(current_positions))
    else:
        self.initial_scan_Location = list(current_positions) + [0] * (expected_axes - len(current_positions))

    # Build scanning arrays for each axis (like original “V_scan” concept)
    self.V_scan = [
        x_vec if x_vec else [self.initial_scan_Location[0]],
        y_vec if y_vec else [self.initial_scan_Location[1]],
        z_vec if z_vec else [self.initial_scan_Location[2]],
    ]

    Nx, Ny, Nz = len(self.V_scan[0]), len(self.V_scan[1]), len(self.V_scan[2])

    # Initialize the 3D array for intensities
    self.scan_intensities = np.zeros((Nx, Ny, Nz), dtype=float)

    # For user reference
    self.scan_data = self.scan_intensities
    self.idx_scan = [0, 0, 0]

    # Start and End for Plot
    self.startLoc = [
        self.V_scan[0][0] if Nx > 1 else self.initial_scan_Location[0],
        self.V_scan[1][0] if Ny > 1 else self.initial_scan_Location[1],
        self.V_scan[2][0] if Nz > 1 else self.initial_scan_Location[2]
    ]
    self.endLoc = [
        self.V_scan[0][-1] if Nx > 1 else self.initial_scan_Location[0],
        self.V_scan[1][-1] if Ny > 1 else self.initial_scan_Location[1],
        self.V_scan[2][-1] if Nz > 1 else self.initial_scan_Location[2]
    ]

    if UseDisplayDuring and is_not_ple:
        self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0], startLoc=self.startLoc,
                       endLoc=self.endLoc)

    # QUA program init (example)
    if not self.simulation:
        if is_not_ple:
            self.initQUA_gen(
                n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                num_measurement_per_array=Nx
            )
        else:
            self.initQUA_gen(
                n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                num_measurement_per_array=1
            )

        res_handles = getattr(self.job, 'result_handles', None)
        if res_handles is None:
            print("No results")
            self.btnStop()
            return

        self.counts_handle = res_handles.get("counts_scanLine")
        self.ref_counts_handle = res_handles.get("counts_Ref")
        self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

    # Example: offset for X start
    if Nx > 1:
        x_channel = 0
        scanPx_Start = self.V_scan[x_channel][0]  # - (self.dL_scan[x_channel] if self.dL_scan[x_channel] else 0)
        move_abs_fn(x_channel, scanPx_Start)
        time.sleep(0.005)
        read_in_pos_fn(x_channel)

    self.dir = 1
    self.scanFN = self.create_scan_file_name(local=True)
    previousMeas_idx = 0
    meas_idx = 0

    # Z-calibration offset
    z_correction_previous = 0
    z_calibration_offset = 0
    if self.b_Zcorrection and (self.ZCalibrationData is not None):
        # at the origin
        z_correction_origin = calculate_z_series(
            self.ZCalibrationData,
            np.array([self.initial_scan_Location[0]]),
            self.initial_scan_Location[1]
        )[0]
        z_calibration_offset = int(z_correction_origin)

    # Initialize the 3D array for intensities
    self.scan_intensities = np.zeros((Nx, Ny, Nz), dtype=float)
    scan_counts = np.zeros_like(self.scan_intensities)
    self.scan_iterations = 0

    def perform_scan_pass(Nx, Ny, Nz, continuous=False, check_srs_stability=True, ):
        nonlocal z_correction_previous, previousMeas_idx, meas_idx
        # For time estimations
        pass_start_time = time.time()
        current_positions_array = []
        data = []

        self.x_expected=[]
        self.y_expected=[]
        self.z_expected=[]
        for iz in range(Nz):
            if self.stopScan:
                break
            # Move Z axis if scanning in Z
            if Nz > 1:
                move_abs_fn(2, self.V_scan[2][iz])
                read_in_pos_fn(2)
                self.z_expected = self.V_scan[2][iz]
            else:
                self.z_expected = -1

            iy = 0
            while iy < Ny:
                if self.stopScan:
                    break
                # Move Y axis if scanning in Y
                if Ny > 1:
                    move_abs_fn(1, self.V_scan[1][iy])
                    read_in_pos_fn(1)
                    self.y_expected = self.V_scan[1][iy]
                else:
                    self.y_expected = -1

                # Flip direction for S-shape scanning
                self.dir *= -1

                line_start_time = time.time()
                # X loop
                current_positions_array=[]
                counts=[]
                for ix in range(Nx):
                    if self.stopScan:
                        break

                    # Z correction if needed
                    new_z_pos = self.V_scan[2][iz] if Nz > 1 else self.initial_scan_Location[2]
                    if self.b_Zcorrection and (self.ZCalibrationData is not None):
                        z_correction_new = (
                                calculate_z_series(
                                    self.ZCalibrationData,
                                    np.array([int(self.V_scan[0][ix])]),
                                    int(self.V_scan[1][iy]) if Ny > 1 else self.initial_scan_Location[1],
                                )[0]
                                - z_calibration_offset
                        )

                        if abs(z_correction_new - z_correction_previous) > self.z_correction_threshold:
                            new_z_pos += int(z_correction_new)
                            z_correction_previous = z_correction_new
                            move_abs_fn(2, new_z_pos)
                            read_in_pos_fn(2)
                            self.z_expected = new_z_pos
                        else:
                            new_z_pos += z_correction_previous

                    # Move X
                    move_abs_fn(0, self.V_scan[0][ix])
                    read_in_pos_fn(0)
                    self.x_expected.append(self.V_scan[0][ix])

                    current_positions = get_positions_fn()
                    if is_not_ple:
                        current_positions_array.append(current_positions)
                    else:
                        current_positions_array.append(current_positions - initial_pos[0])
                    self.extract_vectors(current_positions_array)

                    # Ensure SRS stable
                    if self.exp == Experiment.PLE and check_srs_stability and not self.simulation:
                        while not self.HW.SRS_PID_list[0].is_stable:
                            if self.stopScan:
                                return False
                            print("Waiting for SRS to stabilize")
                            time.sleep(1)

                    if not self.simulation:
                        # Trigger measurement
                        self.qm.set_io2_value(self.ScanTrigger)
                        if self.exp == Experiment.PLE:
                            sleep_time = (self.total_integration_time * 1e-3 + self.Tpump*1e-9) * (self.n_avg+1) + self.Tpump*1e-9 + 6e-3
                        else:
                            sleep_time = (self.total_integration_time * 1e-3 + self.Tpump * 1e-9) + self.Tpump*1e-9 + 1e-3
                        time.sleep(sleep_time)

                    if not is_not_ple: # Only in PLE
                        current_measurement=0
                        if self.simulation:
                            current_measurement=[np.array(float(np.random.randint(1, 1000)))]
                        elif self.counts_handle.is_processing():  # TODO: add count_ref and enable tracking
                            # block until at least 1 data chunk is there
                            self.counts_handle.wait_for_values(1)
                            self.meas_idx_handle.wait_for_values(1)
                            time.sleep(0.1)
                            meas_idx = self.meas_idx_handle.fetch_all()
                            current_measurement=self.counts_handle.fetch_all()
                            self.tracking_ref = self.ref_counts_handle.fetch_all()/5
                            if self.refSignal == 0:
                                self.refSignal = self.tracking_ref / self.TrackingThreshold
                            self.qmm.clear_all_job_results()

                        current_measurement = current_measurement / int(self.total_integration_time*self.u.ms) *1e9 /1e3 / self.n_avg # [KCounts/s]
                        counts.append(current_measurement) # [counts/s]

                        # Correct mistmatch between wavemeter measurements (actual frequency) and mattise wavenlength
                        # measurement of the contribution of the slow piezo

                        self.Y_vec = [0] * len(self.V_scan[0]) # Initialize Y_vec with zeros

                        for i in range(ix + 1): # Override Y_vec values for i = 0 up to ix with counts
                            self.Y_vec[i] = counts[i] if i < len(counts) else 0

                        self.X_vec=list((np.array(self.V_scan[0][:])*1e6+self.mattise_frequency_offset-initial_pos)/1e6)

                        for i in range(ix + 1): # Override X_vec values for i = 0 up to ix
                            self.X_vec[i] = round(current_positions_array[i] / 1e6, 2)  # Convert to MHz

                        self.generate_x_y_vectors_for_average()
                        self.Common_updateGraph(_xLabel="Frequency[MHz]", _yLabel="I[KCounts/s]")
                        # if type(current_measurement) == int:
                        #     current_measurement=[-1]

                        self.scan_Out.append([current_positions_array[ix],  -1, -1,current_measurement,self.V_scan[0][ix],-1,-1,self.tracking_ref ])
                # End X loop
                if self.stopScan:
                    break


                self.extract_vectors(current_positions_array)
                # Fetch data from QUA
                if self.simulation:
                    counts = np.concatenate([
                        create_gaussian_vector(Nx // 2, center=1.5, width=10),
                        create_gaussian_vector(Nx - Nx // 2, center=3.5, width=10)
                    ])
                elif is_not_ple and self.counts_handle.is_processing():
                    # block until at least 1 data chunk is there
                    self.counts_handle.wait_for_values(1)
                    self.meas_idx_handle.wait_for_values(1)
                    time.sleep(0.1)

                    meas_idx = self.meas_idx_handle.fetch_all()
                    counts = self.counts_handle.fetch_all()

                    self.qmm.clear_all_job_results()


                if counts is not None:
                    self.scan_counts_aggregated.append(np.squeeze(counts))
                    self.scan_frequencies_aggregated.append(np.squeeze(current_positions_array))
                    if is_not_ple:
                        for i in range(len(self.X_vec)):
                            self.scan_Out.append([self.X_vec[i],  # X coordinate
                                self.Y_vec[i],  # Y coordinate
                                self.Z_vec[i],  # Z coordinate
                                (np.squeeze(counts)[i] / self.total_integration_time),  # Normalized counts
                                self.x_expected[i],  # Expected X
                                self.y_expected,  # Expected Y (assumes it's the same for all)
                                self.z_expected  # Expected Z (assumes it's the same for all)
                            ])

                    # Validate data
                    if type(counts)==list:
                        counts = np.array(counts)

                    if counts.size == Nx:
                        self.scan_intensities[:, iy, iz] = counts / self.total_integration_time

                        if UseDisplayDuring and is_not_ple:
                            self.UpdateGuiDuringScan(self.scan_intensities[:, :, iz], use_fast_rgb=True)
                            self.extract_vectors(current_positions_array)
                        else:
                            self.generate_x_y_vectors_for_average()
                            half_length = len(self.V_scan[0]) // 2  # Assuming symmetric up and down scan
                            self.X_vec = list((np.array(current_positions_array[:half_length]) -
                                               current_positions_array[0]) * 1e-6)
                            data = self.scan_intensities[:, :, iz]
                            if data.shape[1] == 1:
                                data = data.squeeze()
                            self.Y_vec = data.tolist()

                            # Split the data into up scan and down scan
                            up_scan_length = len(self.V_scan[0]) // 2  # Assuming symmetric up and down scan
                            self.Y_vec = data[:up_scan_length].tolist()  # Data for up scan
                            self.Y_vec_ref = data[up_scan_length:].tolist()  # Data for down scan
                            self.V_scan[1] = list(range(self.scan_iterations+1))
                            self.Common_updateGraph(_xLabel="Frequency[MHz]", _yLabel="I[counts]")
                            self.Y_vec = list(range(self.scan_iterations + 1))
                            self.Z_vec = list(range(Nz))
                    else:
                        print(
                            "Warning: counts size mismatch. Possibly partial line or measurement error."
                        )
                        return False

                    # Check if line is “complete”
                    save_partial = True
                    if not continuous:
                        if (meas_idx - previousMeas_idx) % (Nx if Nx > 1 else 1) == 0:
                            # Good line: increment
                            iy += 1
                        else:
                            print(
                                "****** Error: ******\n"
                                "Number of measurements is not consistent with expected.\n"
                                "Repeating line..."
                            )
                            # do not increment iy => repeat line
                            save_partial = False
                    else:
                        # If continuous, just move to the next line
                        iy += 1

                    # Save partial data
                    if save_partial:
                        print(f"file : {self.scanFN}.csv")
                        self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.scanFN, to_append=True)

                # End while over iy
            # End iz loop

        pass_end_time = time.time()
        if not continuous:
            print(f"Pass time: {pass_end_time - pass_start_time:.2f} s")
        previousMeas_idx = meas_idx
        return not self.stopScan  # If we got here, presumably okay

    def prepare_and_save_data(Nx, Ny, Nz):
        self.prepare_scan_data()
        self.save_scan_data(
            Nx=Nx, Ny=Ny, Nz=Nz,
            fileName=self.scanFN,
            to_append=True
        )

    # ----------------------------------------------------------------------
    # Main Scanning Loops
    # ----------------------------------------------------------------------
    self.scan_counts_aggregated = []
    self.scan_frequencies_aggregated = []
    self.scan_Out = []
    if meas_continuously:
        print("Entering infinite averaging mode...")
        while not self.stopScan:
            success = perform_scan_pass(Nx, Ny, Nz, continuous=True, check_srs_stability=check_srs_stability)
            self.scan_iterations += success
            if not success:
                print("scanning pass is not complete")
    else:
        success = perform_scan_pass(Nx, Ny, Nz, continuous=False, check_srs_stability=check_srs_stability)
        self.scan_iterations += success
        if not success:
            print("Error in scanning pass")
            return

    # ----------------------------------------------------------------------
    # Return to Original Position (Only for Scanned Axes)
    # ----------------------------------------------------------------------
    if x_vec:
        move_abs_fn(0, self.initial_scan_Location[0])  # Move X axis back to initial position
        read_in_pos_fn(0)

    if y_vec:
        move_abs_fn(1, self.initial_scan_Location[1])  # Move Y axis back to initial position
        read_in_pos_fn(1)

    if z_vec:
        move_abs_fn(2, self.initial_scan_Location[2])  # Move Z axis back to initial position
        read_in_pos_fn(2)

    # TODO: If saving doesnt work, try deleting all of the lines below
    # Final save
    # Determine the expected number of columns (length of the longest row)
    max_length = max(len(row) for row in self.scan_frequencies_aggregated)
    self.scan_frequencies_aggregated = np.array(
        [np.pad(row, (0, max_length - len(row)), constant_values=0) for row in self.scan_frequencies_aggregated])
    self.scan_counts_aggregated = np.array(
        [np.pad(row, (0, max_length - len(row)), constant_values=0) for row in self.scan_counts_aggregated])
    self.X_vec = np.array([list(positions) for positions in self.scan_frequencies_aggregated])
    self.scan_intensities = np.array([list(counts) for counts in self.scan_counts_aggregated])[:, :, np.newaxis]

    Nx = self.scan_intensities.shape[0]  # X-axis (number of points per line)
    Ny = self.scan_intensities.shape[1]  # Y-axis (number of lines in the data)
    Nz = 1  # Default Z-axis since no additional layers are specified

    if UseDisplayDuring:
        self.V_scan[1] = list(range(Ny))  # Y dimension represents line indices
        self.V_scan[2] = [0]  # Keep Z dimension as a single layer
        self.Y_vec = list(range(Ny))
        self.Z_vec = list(range(Nz))
        self.prepare_scan_data()
    else:
        self.X_vec = list(np.array(self.scan_frequencies_aggregated).flatten())
        self.Y_vec = list(range(self.scan_iterations))
        self.Z_vec = list(range(Nz))
        self.V_scan[1] = list(range(self.scan_iterations))
        self.scan_intensities = list(np.array(self.scan_counts_aggregated).flatten())
        self.prepare_scan_data()
    # end part to delete if save doesnt work
    fn = self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.create_scan_file_name(local=False))
    self.writeParametersToXML(fn + ".xml")
    self.to_xml()
    end_time = time.time()
    # print(f"end_time: {end_time}")
    print(f"number of points = {Nx * Ny * Nz}")
    print(f"Elapsed time: {end_time - start_time:.0f} seconds")

    if not self.stopScan:
        self.btnStop()

    return self.scan_intensities

def scan_reset_data(self):
    self.stopScan = False
    self.scan_Out = []
    self.scan_intensities = []
    self.X_vec = []
    self.Y_vec = []
    self.Y_vec_ref = []
    self.iteration = 0

    self.Xv = [0]
    self.Yv = [0]
    self.Zv = [0]
    self.initial_scan_Location = []
    self.V_scan = []
    self.t_wait_motionStart = 0.005
    self.N_scan = [1, 1, 1]
    self.scanFN = self.create_scan_file_name(local=True)

def scan_reset_positioner(self):
    if isinstance(self.positioner,
                  smaractMCS2):  # reset stage motion parameters (stream, motion delays, mav velocity)
        self.positioner.set_in_position_delay(0, delay=0)  # reset delays yo minimal
        self.positioner.DisablePositionTrigger(0)  # disable triggers
        self.positioner.SetVelocity(0, 0)  # set max velocity (ch 0)
        self.positioner.setIOmoduleEnable(dev=0)
        self.positioner.set_Channel_Constant_Mode_State(channel=0)

def scan_get_current_pos(self, _isDebug=False):
        time.sleep(1e-3)
        for ch in self.positioner.channels:  # verify in postion
            res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = list(self.positioner.AxesPosUnits)
        if _isDebug:
            res = list(self.positioner.AxesPositions)
            for ch in self.positioner.channels:
                print(f"ch{ch}: in position = {res}, position = {res[ch]} {self.positioner.AxesPosUnits[ch]}")

def StartScan(self, add_scan=False, isLeftScan=False):
        if self.HW.atto_scanner:

            # Move and read functions for mixed axes control
            def move_axes(channel: int, position: float):
                """
                Set offset voltage for the corresponding axis.
                """
                print(f"Moving channel {channel} to position {position}")
                if channel in [0, 1]:  # X and Y axes: atto_scanner
                    self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
                    time.sleep(10e-3)
                    # actual_voltage = self.HW.atto_scanner.get_output_voltage(self.HW.atto_scanner.channels[channel])
                    # while not np.isclose(actual_voltage, position,0.1):
                    #     self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
                    #     time.sleep(10e-3)
                    #     actual_voltage = self.HW.atto_scanner.get_output_voltage(self.HW.atto_scanner.channels[channel])
                    #     print(f"Actual voltage: {actual_voltage}. Requested voltage: {position}")
                elif channel == 2:  # Z axis: atto_positioner
                    # if self.L_scan[2] > 1e6:
                    self.HW.atto_positioner.MoveABSOLUTE(channel, position)
                    # else:
                    #     self.HW.atto_positioner.set_control_fix_output_voltage(self.HW.atto_positioner.channels[channel],
                    #                                                        int(position))

            def get_positions():
                """
                Get current positions for all three axes.
                """
                x = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[0])  # X axis
                y = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[1])  # Y axis
                # z = self.HW.atto_positioner.wait_for_axes_to_stop()  # Z axis
                # z = self.HW.atto_positioner.get_control_output_voltage(2)  # Z axis
                # print(f"control voltage: {z}, fixed_offset_voltage: {self.HW.atto_positioner.get_control_output_voltage(2)}")
                return x, y

            self.HW.atto_scanner.stop_updates()
            self.HW.atto_positioner.stop_updates()

            self.initial_scan_Location = list(get_positions())
            print(f"Initial scan location: {self.initial_scan_Location}")
            scan_lengths = [self.L_scan[ch] * int(self.b_Scan[ch]) * 1e-3 for ch in range(3)]
            scan_steps = [self.dL_scan[ch] * 1e-3 for ch in range(3)]

            # Extract bounds for axis 0 and 1 from the atto_scanner
            scanner_min = self.HW.atto_scanner.offset_voltage_min
            scanner_max = self.HW.atto_scanner.offset_voltage_max

            # Extract bounds for axis 2 from the atto_positioner
            positioner_min = self.HW.atto_positioner.fix_output_voltage_min
            positioner_max = self.HW.atto_positioner.fix_output_voltage_max

            # Create lower and upper bounds
            lower_bounds = [scanner_min, scanner_min, positioner_min]
            upper_bounds = [scanner_max, scanner_max, positioner_max]

            if len(self.initial_scan_Location) == 3:
                x_vec, y_vec, z_vec = create_scan_vectors(self.initial_scan_Location,
                                                      scan_lengths, scan_steps,
                                                      (lower_bounds, upper_bounds))
            else:
                x_vec, y_vec = create_scan_vectors(self.initial_scan_Location,
                                                          scan_lengths, scan_steps,
                                                          (lower_bounds, upper_bounds))
                z_vec = None
            print(f"x_vec: {x_vec}")
            print(f"y_vec: {y_vec}")
            print(f"z_vec: {z_vec}")
            self.start_scan_general(move_abs_fn=move_axes,
                                    read_in_pos_fn=lambda ch: (time.sleep(self.scan_default_sleep_time), True)[1],
                                    get_positions_fn=get_positions, device_reset_fn=None, x_vec=x_vec, y_vec=y_vec,
                                    z_vec=z_vec, meas_continuously=False)
            self.HW.atto_scanner.start_updates()
            self.HW.atto_positioner.start_updates()
        else:
            self.StartScan3D(add_scan=add_scan, isLeftScan=isLeftScan)

def btnFemtoPulses(self):
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Shooting femto pulses !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    self.Shoot_Femto_Pulses = True
    self.ScanTh = threading.Thread(target=self.scan3d_femto_pulses)
    self.ScanTh.start()

def btnStartScan(self, add_scan=False, isLeftScan = False):
    self.ScanTh = threading.Thread(target=self.StartScan,args=(add_scan, isLeftScan))
    self.ScanTh.start()

def btnStartGalvoScan(self, add_scan: bool = False, use_queried_area: bool = False):
    """
    Launches the galvo-based 3D scan in a background thread.
    """
    # Preserve your threading convention
    try:
        # If you keep a stop/start guarding, keep it here as needed
        self.ScanTh = threading.Thread(
            target=self.scan3d_with_galvo,
            kwargs={"use_queried_area": use_queried_area},
            daemon=True
        )
        self.ScanTh.start()
    except Exception as e:
        print(f"btnStartGalvoScan error: {e}")

def btnStartPLE(self):
    self.ScanTh = threading.Thread(target=self.StartPLE)
    self.ScanTh.start()

def btnStartExternalFrequencyScan(self, b_startFetch=True):
    self.exp = Experiment.EXTERNAL_FREQUENCY_SCAN
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.timeStamp = self.getCurrentTimeStamp()
    folder_path = 'C:/temp/' + self.exp.name + '/'
    if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
        os.makedirs(folder_path)
    self.csv_file = os.path.join(folder_path, self.timeStamp + self.exp.name + ".csv")
    # TODO: Boaz - Check for edge cases in number of measurements per array
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                     num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

    if b_startFetch and not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartAWG_FP_SCAN(self, b_startFetch=True):
    self.exp = Experiment.AWG_FP_SCAN
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.timeStamp = self.getCurrentTimeStamp()
    folder_path = 'C:/temp/' + self.exp.name + '/'
    if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
        os.makedirs(folder_path)
    self.csv_file = os.path.join(folder_path, self.timeStamp + self.exp.name + ".csv")
    # TODO: Boaz - Check for edge cases in number of measurements per array
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                     num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

    if b_startFetch and not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def StartPLE(self):
        self.exp = Experiment.PLE
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        try:
            # Get initial wavelength position in MHz
            scan_device = self.matisse.scan_device
            initial_position = self.matisse.get_wavelength_position(scan_device)
            self.mattise_frequency_offset = self.HW.wavemeter.get_frequency() - initial_position*1e6

        except Exception as e:
            print(f"Failed to retrieve initial wavelength position: {e}")
            return

        check_srs_stability=self.matisse.check_srs_stability
        if self.HW.SRS_PID_list is None and check_srs_stability:
            print('Cannot check SRS stability, device not found.')
            check_srs_stability=False

        num_points = self.matisse.num_scan_points
        half_length = self.matisse.scan_range / 2
        vec = list(
            np.concatenate((np.linspace(initial_position - half_length, initial_position + half_length, num_points),
                            np.linspace(initial_position + half_length, initial_position - half_length, num_points)[
                            1:])))

        self.start_scan_general(move_abs_fn=self.matisse.move_wavelength,
                                read_in_pos_fn=lambda ch: (time.sleep(self.matisse.ple_waiting_time), True)[1],
                                get_positions_fn=self.HW.wavemeter.get_frequency,
                                device_reset_fn=None,
                                x_vec=vec,
                                y_vec=None,
                                z_vec=None,
                                current_experiment=Experiment.PLE,
                                is_not_ple=False,
                                meas_continuously=True,
                                UseDisplayDuring=False,
                                check_srs_stability=check_srs_stability)

def btnStartG2Survey(self) -> None:
    """
    Wrapper function to prompt the user for a CSV file containing survey points, extract the points,
    select the appropriate move and position functions, and start the g2 survey.

    The CSV file is expected to have rows with at least two columns representing the x and y coordinates.
    The move function is chosen based on the existence of self.HW.atto_positioner.MoveABSOLUTE or
    self.positioner.MoveABSOLUTE. Similarly, the position function is selected from self.HW.atto_positioner.get_position
    or self.positioner.get_position, and the wait function is wrapped from either
    self.HW.atto_positioner.wait_for_axes_to_stop or self.positioner.ReadIsInPosition.

    Recommended survey parameters:
      - g2_threshold: 0.45
      - g2_counts: 200

    :return: None
    """
    try:
        # Prompt user for CSV file path
        system_name=None
        file_path = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])  # Show .csv and all file types
        points = []
        with open(file_path, 'r') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) >= 2:
                    try:
                        x = float(row[0].strip())
                        y = float(row[1].strip())
                        points.append((x, y))
                    except ValueError:
                        print(f"Skipping row with invalid coordinates: {row}")
        if not points:
            print("No valid points found in the CSV file.")
            return

        # Select move, position, and wait functions based on available hardware
        if hasattr(self, "HW") and hasattr(self.HW, "atto_positioner") and hasattr(self.HW.atto_positioner,
                                                                                   "MoveABSOLUTE"):
            move_fn = self.HW.atto_positioner.MoveABSOLUTE
            get_positions_fn = self.HW.atto_positioner.get_position
            read_in_pos_fn = lambda ax: self.HW.atto_positioner.wait_for_axes_to_stop([ax], max_wait_time=20.0)
            system_name = "Atto"
        elif hasattr(self, "positioner") and hasattr(self.positioner, "MoveABSOLUTE"):
            move_fn = self.positioner.MoveABSOLUTE
            get_positions_fn = self.positioner.GetPosition
            read_in_pos_fn = lambda ch: self.positioner.ReadIsInPosition(ch)
            system_name = "Femto"
        else:
            print("No valid move function found.")
            return

        # Determine the expected number of axes based on the current positions
        if system_name == "Femto":
            get_positions_fn()
            positions = [self.positioner.AxesPositions[x] for x in range(len(points[0]))]
        else:
            positions = [get_positions_fn(x) for x in range(len(points[0]))]
        if not positions:
            print("Unable to retrieve current positions. Aborting survey.")
            return

        def run_survey():
            self.perform_survey(
                points=points,
                move_fn=move_fn,
                read_in_pos_fn=read_in_pos_fn,
                get_positions_fn=get_positions_fn,
                g2_counts=self.survey_g2_counts,
                g2_threshold=self.survey_g2_threshold,
                g2_timeout=self.survey_g2_timeout,
                move_only=False,
                search_peak_intensity_near_positions=True
            )

        self.survey_thread = threading.Thread(target=run_survey, daemon=True)
        self.survey_thread.start()
    except Exception as e:
        print(f"An error occurred in btnStartG2Survey: {e}")

def perform_survey(
        self,
        points: List[Tuple[float, float]],
        move_fn: Callable[[int, int|float], Any],
        g2_threshold: float,
        g2_counts: int,
        g2_timeout: int,
        read_in_pos_fn: Callable[[int], Any],
        get_positions_fn: Callable[[int], Any],
        move_only: bool = False,
        search_peak_intensity_near_positions: bool = True
) -> None:
        """
        Perform a survey of g2 and PL scans of NV centers.

        For each (x, y) point in the provided list, the function performs the following:
          1. Sets the survey flag to True.
          2. Moves to the given point using the provided move function.
          3. Verifies positioning by reading each axis position via read_in_pos_fn and gets current positions using get_positions_fn.
          4. Starts a live counter by invoking self.btnStartCounterLive.
          5. Searches for peak intensity using self.MoveToPeakIntensity.
          6. Waits for the thread self.MAxSignalTh to complete.
          7. Stops the live counter via self.btnStop.
          8. Initiates a g2 measurement using self.btnStartG2.
          9. Waits until self.Y_vec[0] equals g2_counts (with a timeout safeguard).
         10. Stops the g2 measurement with self.btnStop.
         11. If the ratio (min(self.Y_vec) / self.Y_vec[0]) exceeds g2_threshold, starts a scan by invoking self.btnStartScan and waits for self.ScanTh to finish.
             Otherwise, it moves on to the next point.

        Throughout the survey, progress updates are printed, including:
          - Percentage completion.
          - Number of points processed out of the total.
          - Time elapsed for the current point and overall.
          - Estimated Time of Arrival (ETA) for survey completion.

        :param points: List of (x, y) tuples representing the coordinates to survey.
        :param move_fn: A callable function that moves the system to a specified (x, y) coordinate.
        :param g2_threshold: Threshold ratio to decide whether to perform a scan.
        :param g2_counts: Expected count value for g2 measurement to wait for.
        :param g2_timeout: timeout of the g2 measurement if counts threshold was not reached. [seconds]
        :param read_in_pos_fn: A callable that accepts an axis index (int) and ensures that axis is in position.
        :param get_positions_fn: A callable that returns the current positions after reading all axes.
        :param move_only: boolean that controls if the survey only moves to positions or performs the measurements as well.
        :param search_peak_intensity_near_positions: boolean that controls if peak search is required around each location
        """
        try:
            # Set survey flag to indicate that the survey is running
            self.survey = True
            self.survey_stop_flag = False
            total_points = len(points)

            if self.HW.atto_scanner:
                self.HW.atto_scanner.MoveABSOLUTE(1, 25)
                self.HW.atto_scanner.MoveABSOLUTE(2, 25)

            if total_points == 0:
                print("No points provided for the survey. Exiting function.")
                return

            overall_start_time = time.time()  # Record the overall start time

            # Iterate over each survey point
            for idx, point in enumerate(points, start=1):
                if self.survey_stop_flag:
                    return
                point_start_time = time.time()
                print(f"\n--- Starting point {idx}/{total_points}: {point} ---")

                if self.HW.atto_scanner:
                    self.HW.atto_scanner.MoveABSOLUTE(1, 25)
                    self.HW.atto_scanner.MoveABSOLUTE(2, 25)
                    system_name="Atto"
                else:
                    system_name="Femto"

                # Move to the specified point using the provided move function
                try:
                    for ax in range(len(point)):
                        move_fn(ax, point[ax])
                        read_in_pos_fn(ax)  # Ensure in position
                    current_positions = [get_positions_fn(x) for x in range(len(point))]
                    print(f"Current positions after move: {current_positions}")
                    print(f"Moved to point {point} successfully.")
                except Exception as move_error:
                    print(f"Error moving to point {point}: {move_error}. Skipping this point.")
                    continue

                if search_peak_intensity_near_positions:
                    # Start the live counter and search for peak intensity
                    try:
                        print("Starting live counter.")
                        self.Y_vec = []
                        self.btnStartCounterLive()
                        time.sleep(1)
                        self.wait_for_job()
                        print("Moving to peak intensity.")
                        self.MoveToPeakIntensity()
                        time.sleep(1)
                    except Exception as intensity_error:
                        print(f"Error during live counter/peak intensity at point {point}: {intensity_error}.")
                        continue
                    if self.survey_stop_flag:
                        return
                        # Wait for the MAxSignal thread to finish
                    try:
                        if hasattr(self, 'MAxSignalTh') and self.MAxSignalTh is not None:
                            print("Waiting for MAxSignal thread to complete...")
                            while self.MAxSignalTh.is_alive():
                                time.sleep(0.1)
                            print("MAxSignal thread completed.")
                            time.sleep(3)
                        else:
                            print("MAxSignal thread not found; proceeding without waiting.")
                    except Exception as thread_error:
                        print(f"Error while waiting for MAxSignal thread at point {point}: {thread_error}.")
                        continue

                    # Stop the live counter
                    try:
                        print("Stopping live counter.")
                        self.btnStop()
                        self.wait_for_job()
                    except Exception as stop_error:
                        print(f"Error stopping live counter at point {point}: {stop_error}.")
                        continue

                if move_only:
                    continue

                # Start the g2 measurement
                try:
                    print("Starting g2 measurement.")
                    self.btnStartG2()
                    g2_wait_start = time.time()
                    self.wait_for_job()
                except Exception as g2_start_error:
                    print(f"Error starting g2 measurement at point {point}: {g2_start_error}.")
                    continue

                # Wait until self.Y_vec[0] equals the expected g2_counts (with a timeout safeguard)
                try:
                    print(f"Waiting for g2 measurement to reach {g2_counts} counts...")
                    timeout = g2_timeout  # maximum wait time in seconds
                    while True:
                        if self.survey_stop_flag:
                            return
                            # Ensure self.Y_vec exists and has at least one element
                        time.sleep(0.1)
                        if hasattr(self, "Y_vec") and self.Y_vec is not None and len(self.Y_vec) > 0 and self.Y_vec[0] == g2_counts:
                            break
                        if time.time() - g2_wait_start > timeout:
                            print(f"Timeout reached while waiting for g2 counts at point {point}.")
                            break

                    print("g2 measurement condition met or timeout occurred.")
                except Exception as g2_wait_error:
                    print(f"Error during g2 measurement wait at point {point}: {g2_wait_error}.")
                    continue

                # Stop the g2 measurement
                try:
                    print("Stopping g2 measurement.")
                    self.btnStop()
                    if hasattr(self, 'fetchTh'):
                        while self.fetchTh.is_alive():
                            time.sleep(0.1)
                except Exception as g2_stop_error:
                    print(f"Error stopping g2 measurement at point {point}: {g2_stop_error}.")
                    continue

                # Evaluate g2 measurement results and decide whether to perform a scan
                try:
                    if hasattr(self, "Y_vec") and self.Y_vec is not None and self.Y_vec[0] != 0:
                        ratio = min(self.Y_vec) / self.Y_vec[0]
                        print(f"g2 ratio: {ratio:.3f} (Threshold: {g2_threshold})")
                        if ratio < g2_threshold:
                            print("g2 condition satisfied. Initiating scan.")
                            self.btnStartScan()
                            time.sleep(1)
                            self.wait_for_job()
                            if hasattr(self, 'ScanTh') and self.ScanTh is not None:
                                print("Waiting for Scan thread to complete...")
                                while self.ScanTh.is_alive():
                                    time.sleep(0.1)
                                print("Scan thread completed.")
                                time.sleep(1)
                            else:
                                print("Scan thread not found; proceeding without waiting.")
                        else:
                            print("g2 condition not met. Skipping scan at this point.")
                    else:
                        print("Invalid g2 measurement data. Skipping scan evaluation for this point.")
                except Exception as scan_error:
                    print(f"Error during scan evaluation at point {point}: {scan_error}.")

                # Calculate and display progress, elapsed time, and ETA
                elapsed_point = time.time() - point_start_time
                elapsed_total = time.time() - overall_start_time
                progress_percent = (idx / total_points) * 100
                estimated_total = (elapsed_total / idx) * total_points
                eta = estimated_total - elapsed_total

                print(
                    f"Point {idx}/{total_points} completed in {elapsed_point:.2f} sec. "
                    f"Overall progress: {progress_percent:.2f}% | Total elapsed: {elapsed_total:.2f} sec | ETA: {eta:.2f} sec."
                )

            print("\nSurvey completed successfully.")

        except Exception as general_error:
            print(f"An unexpected error occurred during the survey: {general_error}.")

        finally:
            # Reset the survey flag when done
            self.survey = False