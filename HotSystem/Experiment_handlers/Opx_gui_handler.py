import time
import dearpygui.dearpygui as dpg
import glfw
import numpy as np

def Update_bX_Scan(sender, app_data, user_data):
    sender.b_Scan[0] = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_bX_Scan", value=sender.b_Scan[0])
    print("Set b_Scan[0] to: " + str(sender.b_Scan[0]))

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    sender.to_xml()

def Update_bY_Scan(sender, app_data, user_data):
    sender.b_Scan[1] = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_bY_Scan", value=sender.b_Scan[1])
    print("Set bY_Scan to: " + str(sender.b_Scan[1]))

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_bZ_Scan(sender, app_data, user_data):
    sender.b_Scan[2] = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_bZ_Scan", value=sender.b_Scan[2])
    print("Set bZ_Scan to: " + str(sender.b_Scan[2]))

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_dX_Scan(sender, app_data=None, user_data=None):
    sender.dL_scan[0] = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_dx_scan", value=sender.dL_scan[0])
    print("Set dx_scan to: " + str(sender.dL_scan[0]))
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_Lx_Scan(sender, app_data=None, user_data=None):
    sender.L_scan[0] = (int(user_data * 1000))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Lx_scan", value=user_data)
    print("Set Lx_scan to: " + str(sender.L_scan[0]) + "nm")
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_dY_Scan(sender, app_data=None, user_data=None):
    sender.dL_scan[1] = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_dy_scan", value=sender.dL_scan[1])
    print("Set dy_scan to: " + str(sender.dL_scan[1]))
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_Ly_Scan(sender, app_data=None, user_data=None):
    sender.L_scan[1] = (int(user_data * 1000))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Ly_scan", value=user_data)
    print("Set Ly_scan to: " + str(sender.L_scan[1]) + "nm")
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_dZ_Scan(sender, app_data=None, user_data=True):
    sender.dL_scan[2] = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_dz_scan", value=sender.dL_scan[2])
    print("Set dz_scan to: " + str(sender.dL_scan[2]))
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_Lz_Scan(sender, app_data=None, user_data=None):
    sender.L_scan[2] = (int(user_data * 1000))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Lz_scan", value=user_data)
    print("Set Lz_scan to: " + str(sender.L_scan[2]) + "nm")
    sender.save_scan_parameters()

    sender.Calc_estimatedScanTime()
    dpg.set_value(item="text_expectedScanTime",
                  value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

def Update_bZcorrection(sender, app_data=None, user_data=None):
    sender.b_Zcorrection = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_Zcorrection", value=sender.b_Zcorrection)
    print("Set b_Zcorrection to: " + str(sender.b_Zcorrection))
    print(sender.ZCalibrationData)

    # gets values from gui using items tag

def GetItemsVal(self, items_tag=[]):
    items_val = {}
    # Using a for loop to get each value and assign it to the auto_focus dictionary
    for tag in items_tag:
        items_val[tag] = dpg.get_value(tag)
        print(f"{tag}: {items_val[tag]}")

    return items_val

def set_moveabs_to_max_intensity(self):
    try:
        # Find the (row, col) index of the maximum intensity in the first Z slice
        max_idx = np.unravel_index(np.argmax(self.scan_intensities[:, :, 0]), self.scan_intensities[:, :, 0].shape)
        row = max_idx[0]
        col = max_idx[1]

        # Get corresponding X and Y positions
        x_pos = self.V_scan[0][row] * 1e-6  # convert from micron to meter if needed
        y_pos = self.V_scan[1][col] * 1e-6

        # Set the values to MoveABS input fields
        dpg.set_value("mcs_ch0_ABS", x_pos)
        dpg.set_value("mcs_ch1_ABS", y_pos)

        print(f"Set MoveAbsX = {x_pos:.6f} m, MoveAbsY = {y_pos:.6f} m (Max Intensity)")
    except Exception as e:
        print(f"Failed to set MoveABS from max intensity: {e}")

def fill_moveabs_with_picture_center(self):
    try:
        # === CASE 1: If V_scan exists ===
        if hasattr(self, "V_scan") and self.V_scan is not None:
            Xmin = self.V_scan[0].min()*1e-6
            Xmax = self.V_scan[0].max()*1e-6
            Ymin = self.V_scan[1].min()*1e-6
            Ymax = self.V_scan[1].max()*1e-6

        # === CASE 2: Otherwise, use startLoc & endLoc ===
        else:
            Xmin = float(self.startLoc[0])*1e-6
            Xmax = float(self.endLoc[0])*1e-6
            Ymin = float(self.startLoc[1])*1e-6
            Ymax = float(self.endLoc[1])*1e-6

        x_center = (Xmin + Xmax) / 2
        y_center = (Ymin + Ymax) / 2

        dpg.set_value("mcs_ch0_ABS", x_center)
        dpg.set_value("mcs_ch1_ABS", y_center)

        # === Z center only if available ===
        if hasattr(self, "idx_scan") and self.idx_scan is not None and hasattr(self, "Zv"):
            z_value = float(self.Zv[self.idx_scan[Axis.Z.value]])
            dpg.set_value("mcs_ch2_ABS", z_value)
            print(f"Set MoveAbsZ = {z_value:.6f} m (from current Z slice)")
        else:
            print("No idx_scan or Zv available — Z not updated.")

        print(f"Set MoveAbsX = {x_center:.6f} m, MoveAbsY = {y_center:.6f} m (Picture Center)")

    except Exception as e:
        print(f"Failed to fill MoveABS with picture center: {e}")

def fill_moveabs_from_query(self):
    try:
        if self.queried_area is None:
            print("No queried area available.")
            return
        x_pos = self.queried_area[0]
        y_pos = self.queried_area[2]
        dpg.set_value("mcs_ch0_ABS", x_pos)
        dpg.set_value("mcs_ch1_ABS", y_pos)
    except Exception as e:
        print(f"Failed to fill MoveABS from queried area: {e}")

def fill_z(self):
        # Calculate Z value (if needed, otherwise set to 0)
        x = dpg.get_value("mcs_ch0_ABS")
        y = dpg.get_value("mcs_ch1_ABS")
        requested_p = np.array([int(x*1e6), int(y*1e6)])
        refP = self.get_device_position(self.positioner)
        p_new = int(self.Z_correction(refP, requested_p))
        dpg.set_value("mcs_ch2_ABS", p_new*1e-6)

def toggle_limit(self, app_data=None, user_data=True):
        self.limit = user_data
        time.sleep(0.001)
        dpg.set_value(item="checkbox_limit", value=self.limit)
        print("Limit is " + str(self.limit))

def queryXY_callback(self, app_data):
    # print("queryXY_callback")
    a = dpg.get_plot_query_area(app_data)
    if np.any(a):
        # Find the closest index in Yv for a[3]
        y_index = np.argmin(np.abs(self.Yv - a[3]))
        # Find the closest index in Xv for a[1]
        x_index = np.argmin(np.abs(self.Xv - a[1]))

        self.idx_scan[Axis.Y.value] = y_index
        self.idx_scan[Axis.X.value] = x_index

        self.queried_area = a
        self.queried_plane = queried_plane.XY
    else:
        self.queried_area = None
        self.queried_plane = None

def queryYZ_callback(self, app_data):
    # print("queryYZ_callback")
    a = dpg.get_plot_query_area(app_data)
    if np.any(a):
        # Find the closest index in Zv for a[3]
        z_index = np.argmin(np.abs(self.Zv - a[3]))
        # Find the closest index in Yv for a[1]
        y_index = np.argmin(np.abs(self.Yv - a[1]))

        self.idx_scan[Axis.Z.value] = z_index
        self.idx_scan[Axis.Y.value] = y_index

        self.queried_area = a
        self.queried_plane = queried_plane.YZ
    else:
        self.queried_area = None
        self.queried_plane = None

def queryXZ_callback(self, app_data):
        # print("queryXZ_callback")
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # Find the closest index in Zv for a[3]
            z_index = np.argmin(np.abs(self.Zv - a[3]))
            # Find the closest index in Xv for a[1]
            x_index = np.argmin(np.abs(self.Xv - a[1]))

            self.idx_scan[Axis.Z.value] = z_index
            self.idx_scan[Axis.X.value] = x_index

            self.queried_area = a
            self.queried_plane = queried_plane.XZ
        else:
            self.queried_area = None
            self.queried_plane = None

def Calc_estimatedScanTime(self):
    N = np.ones(len(self.L_scan))
    for i in range(len(self.L_scan)):
        if self.b_Scan[i] == True:
            if self.dL_scan[i] > 0:
                N[i] = self.L_scan[i] / self.dL_scan[i]
    self.estimatedScanTime = round(np.prod(N) * (self.singleStepTime_scan + self.total_integration_time / 1e3) / 60,
                                   1)*2

def time_in_multiples_cycle_time(self, val, cycleTime: int = 4, min: int = 16, max: int = 50000000):
    val = (val // cycleTime) * cycleTime
    if val < min:
        val = min
    if val > max:
        val = max
    return int(val)

def UpdateCounterIntegrationTime(sender, app_data=None, user_data=5):
    sender.total_integration_time = user_data
    time.sleep(0.001)
    dpg.set_value(item="inDbl_total_integration_time", value=sender.total_integration_time)
    print("Set total_integration_time to: " + str(sender.total_integration_time) + "msec")

def toggle_sum_counters(self):
    self.sum_counters_flag = not self.sum_counters_flag
    print(f"Set counter sum flag to {self.sum_counters_flag}")

def UpdateWaitTime(sender, app_data, user_data):
    sender.Twait = user_data
    time.sleep(0.001)
    dpg.set_value(item="inDbl_wait_time", value=sender.Twait)
    print("Set Twait to: " + str(sender.Twait) + "usec")

def UpdateEdgeTime(sender, app_data, user_data):
    sender.Tedge = int(user_data)
    time.sleep(0.001)
    dpg.set_value(item="inInt_edge_time", value=sender.Tedge)
    print("Set Tedge to: " + str(sender.Tedge) + "nsec")

def UpdateTcounter(sender, app_data, user_data):
    sender.Tcounter = sender.time_in_multiples_cycle_time(int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Tcounter", value=sender.Tcounter)
    print("Set Tcounter to: " + str(sender.Tcounter) + "nsec")

def UpdateTpump(sender, app_data, user_data):
    sender.Tpump = sender.time_in_multiples_cycle_time(int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Tpump", value=sender.Tpump)
    print("Set Tpump to: " + str(sender.Tpump) + "nsec")

def UpdateTcounterPulsed(sender, app_data, user_data):
    sender.TcounterPulsed = sender.time_in_multiples_cycle_time(int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_TcounterPulsed", value=sender.TcounterPulsed)
    print("Set TcounterPulsed to: " + str(sender.TcounterPulsed) + "nsec")

def UpdateNumOfPoint(sender, app_data, user_data):
    sender.NumOfPoints = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="slideNumPts", value=sender.NumOfPoints)
    print("Set NumOfPoints to: " + str(sender.NumOfPoints))

def Update_mwResonanceFreq(sender, app_data, user_data):
    sender.mw_freq_resonance = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwResonanceFreq", value=sender.mw_freq_resonance)
    print("Set mw_freq_resonance to: " + str(sender.mw_freq_resonance))

def Update_mwP_amp(sender, app_data, user_data):
    sender.mw_P_amp = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwP_amp", value=sender.mw_P_amp)
    print("Set mw_Pamp to: " + str(sender.mw_P_amp))

def Update_mwP_amp2(sender, app_data, user_data):
    sender.mw_P_amp2 = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwP_amp2", value=sender.mw_P_amp2)
    print("Set mw_Pamp to: " + str(sender.mw_P_amp2))

def Update_off_time(sender, app_data, user_data):
    sender.off_time = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_f1", value=sender.off_time)
    print("Set off_time to: " + str(sender.off_time))

def Update_T_bin(sender, app_data, user_data):
    sender.T_bin = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_f1", value=sender.T_bin)
    print("Set T_bin to: " + str(sender.T_bin))

def Update_AWG_interval(sender, app_data, user_data):
    sender.AWG_interval = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_f1", value=sender.AWG_interval)
    print("Set AWG_interval to: " + str(sender.AWG_interval))

def Update_AWG_f_1(sender, app_data, user_data):
    sender.AWG_f_1 = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_f1", value=sender.AWG_f_1)
    print("Set AWG_f_1 to: " + str(sender.AWG_f_1))

def Update_AWG_f_2(sender, app_data, user_data):
    sender.AWG_f_2 = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_f2", value=sender.AWG_f_2)
    print("Set AWG_f_2 to: " + str(sender.AWG_f_2))

def Update_mwP_amp3(sender, app_data, user_data):
    sender.mw_P_amp3 = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwP_amp3", value=sender.mw_P_amp3)
    print("Set mw_Pamp3 to: " + str(sender.mw_P_amp3))

def Update_mw_2ndfreq_resonance(sender, app_data, user_data):
    sender.mw_2ndfreq_resonance = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mw_2ndfreq_resonance", value=sender.mw_2ndfreq_resonance)
    print("Set mw_2ndfreq_resonance to: " + str(sender.mw_2ndfreq_resonance))

def Update_mwFreq(sender, app_data, user_data):
    sender.mw_freq = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwFreq", value=sender.mw_freq)
    print("Set mw_freq to: " + str(sender.mw_freq))

def Update_df(sender, app_data, user_data):
    sender.mw_df = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mw_df", value=sender.mw_df)
    print("Set MW df to: " + str(sender.mw_df))

def UpdateScanRange(sender, app_data, user_data):
    sender.mw_freq_scan_range = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mwScanRange", value=sender.mw_freq_scan_range)
    print("Set freq_scan_range to: " + str(sender.mw_freq_scan_range))

def UpdateMWpwr(sender, app_data, user_data):
    sender.mw_Pwr = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_mw_pwr", value=sender.mw_Pwr)
    print("Set mwPwr to: " + str(sender.mw_Pwr))

def UpdateN_nuc_pump(sender, app_data, user_data):
    sender.n_nuc_pump = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_N_nuc_pump", value=sender.n_nuc_pump)
    print("Set n_nuc_pump to: " + str(sender.n_nuc_pump))

def UpdateN_p_amp(sender, app_data, user_data):
    sender.N_p_amp = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_N_p_amp", value=sender.N_p_amp)
    print("Set N_p_amp to: " + str(sender.N_p_amp))

def UpdateN_CPMG(sender, app_data, user_data):
    sender.n_CPMG = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_N_CPMG", value=sender.n_CPMG)
    print("Set n_CPMG to: " + str(sender.n_CPMG))

def UpdateNavg(sender, app_data, user_data):
    sender.n_avg = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_n_avg", value=sender.n_avg)
    print("Set n_avg to: " + str(sender.n_avg))

def UpdateCorrelationWidth(sender, app_data=None, user_data=None):
    sender.correlation_width = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_G2_correlation_width", value=sender.correlation_width)
    print("Set correlation_width to: " + str(sender.correlation_width))

def UpdateN_measure(sender, app_data, user_data):
    sender.n_measure = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_n_measure", value=sender.n_measure)
    print("Set n_measur to: " + str(sender.n_measure))

def UpdateMW_dif(sender, app_data, user_data):
    sender.MW_dif = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_MW_dif", value=sender.MW_dif)
    print("Set MW_dif to: " + str(sender.MW_dif))

def UpdatedN(sender, app_data, user_data):
    sender.dN = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="indN", value=sender.dN)
    print("Set dN to: " + str(sender.dN))

def Update_back_freq(sender, app_data, user_data):
    sender.back_freq = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="in_back_freq", value=sender.back_freq)
    print("Set back_freq to: " + str(sender.back_freq))

def Update_gate_number(sender, app_data, user_data):
    sender.gate_number = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="ind_gate_number", value=sender.gate_number)
    print("Set gate_number to: " + str(sender.gate_number))

def UpdateN_tracking_search(sender, app_data=None, user_data=None):
    sender.N_tracking_search = int(user_data)
    time.sleep(0.001)
    item_tag = "inInt_N_tracking_search"
    if dpg.does_item_exist(item_tag):
        dpg.set_value(item=item_tag, value=sender.N_tracking_search)
    else:
        print(f"[Warning] '{item_tag}' does not exist — possibly because an experiment is active.")
    print("Set N_tracking_search to:", sender.N_tracking_search)

def UpdateN_survey_g2_counts(sender, app_data, user_data):
    sender.survey_g2_counts = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_survey_g2_counts", value=sender.survey_g2_counts)
    print("Set survey_g2_counts to: " + str(sender.survey_g2_counts))

def UpdateN_survey_g2_threshold(sender, app_data, user_data):
        sender.survey_g2_threshold = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_survey_g2_threshold", value=sender.survey_g2_threshold)
        print("Set survey_g2_threshold to: " + str(sender.survey_g2_threshold))

def UpdateN_survey_g2_timeout(sender, app_data, user_data):
        sender.survey_g2_timeout = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_survey_g2_timeout", value=sender.survey_g2_timeout)
        print("Set survey_g2_timeout to: " + str(sender.survey_g2_timeout))

def toggle_stop_survey(sender, app_data, user_data):
        sender.stop_survey = (bool(user_data))
        time.sleep(0.001)
        dpg.set_value(item="chkbox_stop_survey", value=sender.stop_survey)
        print("Set stop_survey to: " + str(sender.stop_survey))

def UpdateT_rf_pulse_time(sender, app_data, user_data):
    sender.rf_pulse_time = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_rf_pulse_time", value=sender.rf_pulse_time)
    print("Set rf_pulse_time to: " + str(sender.rf_pulse_time))

def UpdateT_mw(sender, app_data, user_data):
    sender.t_mw = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_t_mw", value=sender.t_mw)
    print("Set t_mw to: " + str(sender.t_mw))

def UpdateT_mw2(sender, app_data, user_data):
    sender.t_mw2 = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_t_mw2", value=sender.t_mw2)
    print("Set t_mw2 to: " + str(sender.t_mw2))

def UpdateT_mw3(sender, app_data, user_data):
    sender.t_mw3 = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_t_mw3", value=sender.t_mw3)
    print("Set t_mw3 to: " + str(sender.t_mw3))

def Update_rf_pulse_time(sender, app_data, user_data):
    sender.rf_pulse_time = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_rf_pulse_time", value=sender.rf_pulse_time)
    print("Set rf_pulse_time to: " + str(sender.rf_pulse_time))

def Update_tGetTrackingSignalEveryTime(sender, app_data, user_data):
    sender.tGetTrackingSignalEveryTime = (user_data)
    time.sleep(0.001)
    dpg.set_value(item="inDbl_tGetTrackingSignalEveryTime", value=sender.tGetTrackingSignalEveryTime)
    print("Set tGetTrackingSignalEveryTime to: " + str(sender.tGetTrackingSignalEveryTime))

def Update_tTrackingSignaIntegrationTime(sender, app_data, user_data):
    sender.tTrackingSignaIntegrationTime = (user_data)
    time.sleep(0.001)
    dpg.set_value(item="inDbl_tTrackingSignaIntegrationTime", value=sender.tTrackingSignaIntegrationTime)
    print("Set tTrackingSignaIntegrationTime to: " + str(sender.tTrackingSignaIntegrationTime))

def Update_TrackingThreshold(sender, app_data, user_data):
    sender.TrackingThreshold = (user_data)
    time.sleep(0.001)
    dpg.set_value(item="inDbl_TrackingThreshold", value=sender.TrackingThreshold)
    print("Set TrackingThreshold to: " + str(sender.TrackingThreshold))

def UpdateScanTstart(sender, app_data, user_data):
    sender.scan_t_start = (int(user_data))
    sender.scan_t_start = sender.scan_t_start if sender.scan_t_start >= 20 else 20
    sender.scan_t_start = int(sender.scan_t_start / 4) * 4
    time.sleep(0.001)
    dpg.set_value(item="inInt_scan_t_start", value=sender.scan_t_start)
    print("Set scan_t_start to: " + str(sender.scan_t_start))

def on_off_slider_callback(self, sender, app_data):
    # app_data is the new slider value (0 or 1)
    if app_data == 1:
        self.is_green = True
        dpg.configure_item(sender, format="GREEN")
        dpg.bind_item_theme(sender, "OnTheme_OPX")
        print("Laser is Green!")
    else:
        self.is_green = False
        dpg.configure_item(sender, format="RED")
        dpg.bind_item_theme(sender, "OffTheme_OPX")
        print("Laser is Red!")

def UpdateTsettle(sender, app_data, user_data):
    sender.Tsettle = sender.time_in_multiples_cycle_time(int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_Tsettle", value=sender.Tsettle)
    print("Set measure_time to: " + str(sender.Tsettle))

def UpdateScanT_dt(sender, app_data, user_data):
    sender.scan_t_dt = (int(user_data))
    sender.scan_t_dt = int(sender.scan_t_dt if sender.scan_t_dt >= 4 else 4)
    time.sleep(0.001)
    dpg.set_value(item="inInt_scan_t_dt", value=sender.scan_t_dt)
    print("Set scan_t_dt to: " + str(sender.scan_t_dt))

def UpdateScanTend(sender, app_data, user_data):
    sender.scan_t_end = (int(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inInt_scan_t_end", value=sender.scan_t_end)
    print("Set scan_t_end to: " + str(sender.scan_t_end))

def Update_rf_resonance_Freq(sender, app_data, user_data):
    sender.rf_resonance_freq = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_rf_resonance_freq", value=sender.rf_resonance_freq)
    print("Set rf_resonance_freq to: " + str(sender.rf_resonance_freq))

def Update_rf_Freq(sender, app_data, user_data):
    sender.rf_freq = (float(user_data))
    time.sleep(0.001)
    dpg.set_value(item="inDbl_rf_freq", value=sender.rf_freq)
    print("Set rf_freq to: " + str(sender.rf_freq))

def Update_rf_ScanRange(sender, app_data, user_data):
    sender.rf_freq_scan_range_gui = (float(user_data))
    sender.rf_freq_scan_range = sender.rf_freq_scan_range_gui / 1e3
    time.sleep(0.001)
    dpg.set_value(item="inDbl_rf_ScanRange", value=sender.rf_freq_scan_range_gui)
    print("Set rf_freq_scan_range_gui to: " + str(sender.rf_freq_scan_range_gui))

def Update_rf_df(sender, app_data, user_data):
    sender.rf_df_gui = (float(user_data))
    sender.rf_df = sender.rf_df_gui / 1e3  # to [MHz]
    time.sleep(0.001)
    dpg.set_value(item="inDbl_rf_df", value=sender.rf_df_gui)
    print("Set rf_df to: " + str(sender.rf_df_gui))

def Update_rf_pwr(sender, app_data, user_data):
    sender.rf_Pwr = (float(user_data))
    sender.rf_proportional_pwr = sender.rf_Pwr / sender.OPX_rf_amp
    time.sleep(0.001)
    dpg.set_value(item="inDbl_rf_pwr", value=sender.rf_Pwr)
    print("Set rf_Pwr to: " + str(sender.rf_Pwr))

def Update_Intensity_Tracking_state(sender, app_data, user_data):
    sender.bEnableSignalIntensityCorrection = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_intensity_correction", value=sender.bEnableSignalIntensityCorrection)
    print("Set chkbox_intensity_correction to: " + str(sender.bEnableSignalIntensityCorrection))

def Update_QUA_Shuffle_state(sender, app_data, user_data):
    sender.bEnableShuffle = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_QUA_shuffle", value=sender.bEnableShuffle)
    print("Set bEnableShuffle to: " + str(sender.bEnableShuffle))

def Update_QUA_Simulate_state(sender, add_data, user_data):
    sender.bEnableSimulate = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_QUA_simulate", value=sender.bEnableSimulate)
    print("Set bEnableSimulate to: " + str(sender.bEnableSimulate))

def hide_legend(self):
    """Toggle the visibility of all legend series items."""
    items = (
        "series_counts_ref",
        "series_counts_ref2",
        "series_counts_ref3",
        "series_res_calcualted",
    )

    for item in items:
        # `is_item_shown` → True if the item is currently visible
        # (use `is_item_visible` if you’re on an older DearPyGui build)
        if dpg.is_item_shown(item):
            dpg.hide_item(item)
        else:
            dpg.show_item(item)

    # Hide legend
    if dpg.does_item_exist("graph_legend"):
        dpg.hide_item("graph_legend")

# GUI controls
def GetWindowSize(self):
    # Move to Common
    monitor = glfw.get_primary_monitor()  # Get the primary monitor
    mode = glfw.get_video_mode(monitor)  # Get the physical size of the monitor
    width, height = mode.size
    self.viewport_width = dpg.get_viewport_client_width()
    self.viewport_height = dpg.get_viewport_client_height()
    self.window_scale_factor = width / 3840

def set_all_themes(self):
        if dpg.does_item_exist("OnTheme_OPX"):
            dpg.delete_item("OnTheme_OPX")  # Remove old theme first!
        if dpg.does_item_exist("OffTheme_OPX"):
            dpg.delete_item("OffTheme_OPX")  # Remove old theme first!

        with dpg.theme(tag="OnTheme_OPX"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 200, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (0, 180, 0))  # handle when pressed
                # Optionally color the track:
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 70, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (60, 80, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 90, 70))

        # OFF Theme: keep the slider handle red in all states.
        with dpg.theme(tag="OffTheme_OPX"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (200, 0, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (180, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (70, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (80, 60, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (90, 70, 70))

# Display
def Plot_Scan(self, Nx=250, Ny=250, array_2d=None, startLoc=None, endLoc=None, switchAxes=False, current_z=None):
        """
        Plots a 2D scan using the provided array. If a division by zero occurs,
        the array will be set to zeros.
        """
        if dpg.does_item_exist("plot_draw_layer"):
            dpg.delete_item("plot_draw_layer", children_only=True)

        if array_2d is None:
            array_2d = np.zeros((Nx, Ny))  # Default to zeros if array is not provided

        if startLoc is None:
            startLoc = [0, 0]

        if endLoc is None:
            endLoc = [Nx, Ny]

        start_Plot_time = time.time()
        plot_size = [int(self.viewport_width * 0.2), int(self.viewport_height * 0.4)] #1-7-2025

        try:
            # Attempt to normalize the array
            max_value = array_2d.max()
            if max_value == 0:
                raise ZeroDivisionError("Maximum value of the array is zero, cannot normalize.")

            # Normalize and multiply by 255
            result_array = (array_2d * 255) / max_value
        except ZeroDivisionError:
            # print("Division by zero encountered. Setting entire array to zero.")
            result_array = np.zeros_like(array_2d)  # Set entire array to zeros
        except Exception as e:
            print(f"An unexpected error occurred during array normalization: {e}")
            result_array = np.zeros_like(array_2d)  # Fallback to zeros in case of any other error

        result_array_ = []
        for i in range(array_2d.shape[0]):
            for j in range(array_2d.shape[1]):
                if switchAxes:  # switchAxes = workaround. need to be fixed
                    try:
                        res = self.intensity_to_rgb_heatmap(result_array.astype(np.uint8)[i][j] / 255)
                        result_array_.append(res[0] / 255)
                        result_array_.append(res[1] / 255)
                        result_array_.append(res[2] / 255)
                        result_array_.append(res[3] / 255)
                    except Exception as e:
                        print(f"Error in intensity to RGB heatmap conversion: {e}")
                        result_array_.extend([0, 0, 0, 0])  # Append zeros if an error occurs
                else:
                    try:
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(255 / 255)
                    except Exception as e:
                        print(f"Error while appending normalized values: {e}")
                        result_array_.extend([0, 0, 0, 1])  # Append zeros if an error occurs

        # Plot XY graph (image)
        try:
            dpg.delete_item("scan_group")
            dpg.delete_item("texture_reg")
            dpg.delete_item("texture_tag")
        except Exception as e:
            print(f"Error deleting items: {e}")

        time.sleep(0)
        dpg.add_texture_registry(show=False, tag="texture_reg")

        try:
            if switchAxes:
                dpg.add_dynamic_texture(width=array_2d.shape[1], height=array_2d.shape[0], default_value=result_array_,
                                        tag="texture_tag",
                                        parent="texture_reg")
            else:
                dpg.add_dynamic_texture(width=array_2d.shape[0], height=array_2d.shape[1], default_value=result_array_,
                                        tag="texture_tag",
                                        parent="texture_reg")
        except Exception as e:
            print(f"Error adding dynamic texture: {e}")

        try:
            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1],
                         equal_aspects=True, crosshairs=True,query=True, callback=self.queryXY_callback)
            z_label = f"x axis [um]{f' @ Z={current_z:.1f} µm' if current_z is not None else ''}"
            dpg.add_plot_axis(dpg.mvXAxis, label=z_label, parent="plotImaga",tag="plotImaga_X")

            dpg.add_plot_axis(dpg.mvYAxis, label="y axis [um]", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series(f"texture_tag", bounds_min=[startLoc[0], startLoc[1]], bounds_max=[endLoc[0], endLoc[1]], label="Scan data", parent="plotImaga_Y")
            # Add a draw layer for text annotations (e.g., pulse energy)

            dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(array_2d), max_scale=np.max(array_2d), colormap=dpg.mvPlotColormap_Jet)

            # ✅ Apply persistent graph size override if exists
            if hasattr(self, "graph_size_override") and self.graph_size_override:
                w, h = self.graph_size_override
                dpg.set_item_width("plotImaga", w)
                dpg.set_item_height("plotImaga", h)
                print(f"Graph resized to override: {w}×{h}")

        except Exception as e:
            print(f"Error during plotting: {e}")
        end_Plot_time = time.time()
        print(f"time to plot scan: {end_Plot_time - start_Plot_time}")
        try:
            dpg.set_value("texture_tag", result_array_)
        except Exception as e:
            print(f"Error setting texture tag value: {e}")

def UpdateGuiDuringScan(self, Array2D, use_fast_rgb: bool = False):
        # If self.limit is true, cap the values in Array2D at dz (nm) value
        if self.limit:
            limit = dpg.get_value("inInt_limit")
            Array2D = np.where(Array2D > limit, limit, Array2D)

        val = Array2D.reshape(-1)
        idx = np.where(val != 0)[0]
        if len(idx) == 0:
            minI = 0
        else:
            minI = val[idx].min()

        result_array_ = self.fast_rgb_convert(np.flipud(Array2D.T))

        dpg.set_value("texture_tag", result_array_)
        dpg.delete_item("colormapXY")
        # --- new: add label above colorbar ---
        if dpg.does_item_exist("colormapXY_label"):
            dpg.delete_item("colormapXY_label")
        dpg.add_text("kCnts/s", parent="scan_group", tag="colormapXY_label")
        dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=minI,
                               max_scale=Array2D.max(),
                               colormap=dpg.mvPlotColormap_Jet)

def UpdateGuiDuringScan_____(self, Array2D: np.ndarray):  # $$$
        # todo: remove loops keep only when an imgae is needed
        start_updatePlot_time = time.time()
        result_array_ = []

        Array2D = Array2D * 255 / Array2D.max()  # BBB
        Array2D = np.fliplr(Array2D)

        for i in range(Array2D.shape[0]):  # Y
            for j in range(Array2D.shape[1]):  # X
                res = self.intensity_to_rgb_heatmap(Array2D.astype(np.uint8)[j, i] / 255)
                result_array_.append(res[0] / 255)  # shai 30-7-24
                result_array_.append(res[1] / 255)
                result_array_.append(res[2] / 255)
                result_array_.append(res[3] / 255)

        # dpg.set_value("textureXY_tag", result_array_) # 444
        dpg.set_value("texture_tag", result_array_)  # 444

def Update_scan(sender, app_data, user_data):
        sender.bScanChkbox = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_scan", value=sender.bScanChkbox)
        print("Set bScan to: " + str(sender.bScanChkbox))
        sender.load_scan_parameters()
        sender.GUI_ScanControls()

#new

def Z_correction(self, _refp: list, _point: list):
    # Define the points (self.positioner.LoggedPoints equivalent)
    P = np.array(self.positioner.LoggedPoints)
    refP = np.array(_refp)
    point = np.array(_point)

    # Vector U and normalization
    U = P[1, :] - P[0, :]
    u = U / np.linalg.norm(U)

    # Vector V and normalization
    V = P[2, :] - P[0, :]
    v = V / np.linalg.norm(V)

    # Cross product to find the normal vector N
    N = np.cross(u, v)

    # Calculate D
    D = -np.dot(refP, N)

    # Calculate the new points Pnew
    # Pnew = -(point[:, :2] @ N[:2] + D) / N[2]
    Znew = -(point[:2] @ N[:2] + D) / N[2]

    # print(Znew)

    return Znew

def set_hwp_angle(self, new_hwp_angle: float):
    """
    Move the half-wave plate (HWP) to exactly new_hwp_angle degrees.
    Blocks until the motion is within 0.01°.
    """
    try:
        print(f"!!!!! set HWP to {new_hwp_angle:.2f} deg !!!!!")
        # Kick off the motion
        self.kdc_101.MoveABSOLUTE(new_hwp_angle)
        time.sleep(0.2)

        # Poll until within 0.01°
        current_hwp = self.kdc_101.get_current_position()
        while abs(current_hwp - new_hwp_angle) > 0.01:
            time.sleep(0.2)
            current_hwp = self.kdc_101.get_current_position()

        return current_hwp
    except Exception as e:
        print(f"Error in set_hwp_angle: {e}")

def btnUpdateImages(self):
    self.Plot_Loaded_Scan(use_fast_rgb=True)

def Plot_data(self, data, bLoad=False):
    np_array = np.array(data) #numpy array of the csv data
    self.scan_Out=np_array # new
    # Nx = int(np_array[1,10])
    # Ny = int(np_array[1,11])
    # Nz = int(np_array[1,12])
    allPoints = np_array[0:, 3] #Intensity
    self.Xv = np_array[0:, 4].astype(float) / 1e6 # x data of the Smaract values from the csv
    self.Yv = np_array[0:, 5].astype(float) / 1e6 # y data of the Smaract values from the csv
    self.Zv = np_array[0:, 6].astype(float) / 1e6 # z data of the Smaract values from the csv

    allPoints = allPoints.astype(float)  # intensities
    Nx = int(round((self.Xv[-1] - self.Xv[0]) / (self.Xv[1] - self.Xv[0])) + 1) #Total range divided by step size
    if self.Yv[Nx] - self.Yv[0] == 0:
        if bLoad:
            dpg.set_value("Scan_Message", "Stopped in the middle of a frame")
            Nx, allPoints = self.attempt_to_display_unfinished_frame(allPoints=allPoints)
        else:
            return 0  # Running mode

    Ny = int(round((self.Yv[-1] - self.Yv[0]) / (self.Yv[Nx] - self.Yv[0])) + 1)  # 777
    if Nx * Ny < len(self.Zv) and self.Zv[Ny * Nx] - self.Zv[0] > 0:  # Z[Ny*Nx]-Z[0] > 0:
        Nz = int(round((self.Zv[-1] - self.Zv[0]) / (self.Zv[Ny * Nx] - self.Zv[0])) + 1)
        res = np.reshape(allPoints, (Nz, Ny, Nx))
        dpg.set_value("Scan_Message", f"Number of Z slices is {Nz}")
    else:
        Nz = 1
        res = np.reshape(allPoints[0:Nx * Ny], (Nz, Ny, Nx))
        dpg.set_value("Scan_Message", f"Number of Z slices is {Nz}")

    self.scan_data = res

    self.Xv = self.Xv[0:Nx]
    self.Yv = self.Yv[0:Nx * Ny:Nx]
    self.Zv = self.Zv[0:-1:Nx * Ny]
    # xy
    self.startLoc = [np_array[1, x] for x in [4,5,6]]
    self.endLoc = [np_array[-1, x] for x in [4,5,6]]

    if bLoad:
        self.Plot_Loaded_Scan(use_fast_rgb=True)  ### HERE
        print("Done.")
    else:
        self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=np.flipud(res[0, :, :]), startLoc=self.startLoc, endLoc=self.endLoc,
                       switchAxes=bLoad)

def attempt_to_display_unfinished_frame(self, allPoints):
    # Check and remove incomplete repetition if needed
    self.Xv, self.Yv, self.Zv, allPoints, Nx = self.check_last_period(self.Xv, self.Yv, self.Zv, allPoints)
    return Nx, allPoints

def check_last_period(self, x, y, z, allPoints):
    X_length = len(x)
    tolerance = 1e-10  # Set tolerance for floating point comparisons

    # Find the difference between the last two elements
    last_diff = x[-1] - x[-2]

    # Find the maximum value and its last occurrence using NumPy
    max_x = np.max(x)
    LastIdx = X_length - np.argmax(x[::-1] == max_x)  # Index of the last occurrence of max_x

    # Remove the incomplete section at the end based on LastIdx
    x_fixed = x[:LastIdx]
    y_fixed = y[:LastIdx]
    z_fixed = z[:LastIdx]
    allPoints_fixed = allPoints[:LastIdx]

    # Calculate the pattern length
    if len(x_fixed) > 1:
        pattern_length = int(np.ceil((x_fixed[-1] - x_fixed[0]) / last_diff) + 1)  # Round up
    else:
        pattern_length = 0  # Handle edge case where pattern cannot be calculated

    print(f'Pattern length: {pattern_length}')
    print(f'LastIdx: {LastIdx}')

    return x_fixed, y_fixed, z_fixed, allPoints_fixed, pattern_length

def create_scan_file_name(self, local=False):
    """
        Create a file name for saving a scan, adjusting the folder path based on survey mode.

        If 'local' is True, the scan data will be saved to a local temporary folder.
        Otherwise, if self.survey is True, the scan will be saved into:
            Q:/QT-Quantum_Optic_Lab/expData/survey{system_type}/scan
        If self.survey is False, the scan will be saved into:
            Q:/QT-Quantum_Optic_Lab/expData/scan/{system_type}

        The file name includes a timestamp, experiment name, and experiment notes.

        :param local: Boolean flag indicating whether to use a local folder.
        :return: The full file path for the scan file.
        """
    # file name
    timeStamp = self.getCurrentTimeStamp()  # get current time stamp
    if local:
        folder_path = "C:/temp/TempScanData/"
    else:
        # Determine folder path based on survey mode
        if hasattr(self, "survey") and self.survey:
            folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/survey{self.HW.config.system_type}/scan'
        else:
            folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/scan/{self.HW.config.system_type}'

    if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
        try:
            os.makedirs(folder_path)
        except FileNotFoundError as ex:
            print(f"An error occurd when trying to create {folder_path}")
            print("Saving to local folder instead.")
            return self.create_scan_file_name(local=True)
    fileName = os.path.join(folder_path, f"{timeStamp}_{self.exp.name}_{self.expNotes}")
    self.timeStamp = timeStamp
    self.last_loaded_file=fileName
    return fileName

def move_single_step(self, ch, step):
    self.positioner.MoveRelative(ch, step)
    res = self.readInpos(ch)
    self.positioner.GetPosition()
    self.absPosunits = self.positioner.AxesPosUnits[ch]
    self.absPos = self.positioner.AxesPositions[ch]
    print(f"ch{ch}: in position = {res}, position = {self.absPos} [{self.absPosunits}]")

def readInpos(self, ch):
    res = self.positioner.ReadIsInPosition(ch)
    while not (res):
        res = self.positioner.ReadIsInPosition(ch)
    return res

def check_srs_stability(self):
    if self.bEnableSignalIntensityCorrection:
        while not self.HW.SRS_PID_list[0].is_stable:
            if self.stopScan:
                return False
            print("Waiting for SRS to stabilize")
            time.sleep(1)

def change_AWG_freq(self, channel):
    # Get the current time
    if not self.simulation:
        current_time = time.time()

        # Initialize last_change_time if it doesn't exist yet.
        if not hasattr(self, 'last_change_time'):
            self.last_change_time = current_time

        # Check if enough time has passed since the last change.
        if current_time - self.last_change_time >= self.AWG_interval:
            # Toggle the frequency based on the current value.
            if self.current_awg_freq == self.AWG_f_1:
                self.awg.set_frequency(self.AWG_f_2, channel)
            elif self.current_awg_freq == self.AWG_f_2:
                self.awg.set_frequency(self.AWG_f_1, channel)

            # Update the current frequency by reading it back.
            self.current_awg_freq = self.awg.get_frequency()

            # Update the last change time.
            self.last_change_time = current_time
    else:
        current_time = time.time()
        if not hasattr(self, 'last_change_time'):
            self.last_change_time = current_time
        if current_time - self.last_change_time >= 0.00001:
            self.current_awg_freq = 5
            if self.current_awg_freq == 5:
                self.current_awg_freq = 7
            elif self.current_awg_freq == 7:
                self.current_awg_freq = 5
            self.awg_freq_list.append(self.current_awg_freq)
        #self.job.push_to_input_stream('awg_freq', self.current_awg_freq)
        print("Passed change_AWG_freq successfully")

def format_time(self, seconds):
    """
    Convert time from seconds to human-readable format.
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    time_str = ""
    if days > 0:
        time_str += f"{int(days)} days, "
    if hours > 0:
        time_str += f"{int(hours)} hours, "
    if minutes > 0:
        time_str += f"{int(minutes)} minutes, "
    if seconds > 0 or time_str == "":
        time_str += f"{int(seconds)} seconds"

    return time_str

def getCurrentTimeStamp(self):
    now = datetime.now()
    return str(now.year) + "_" + str(now.month) + "_" + str(now.day) + "_" + str(now.hour) + "_" + str(
        now.minute) + "_" + str(now.second)

def convert_to_correct_type(self, attribute, value, idx='none'):
    # Get the type of the attribute
    attribute_type = type(getattr(self, attribute))

    if not (idx == 'none'):
        attribute_type = type(getattr(self, attribute)[idx])

    # Convert value to the appropriate type
    if attribute_type is int:
        return int(value)
    elif attribute_type is float:
        return float(value)
    elif attribute_type is bool:
        return value.lower() == 'true'
    else:
        return value

def fast_rgb_convert(self, Array2D):
    # Mask for non-zero values
    mask_non_zero = Array2D > 0

    # Initialize normalized array
    normalized_array = np.zeros_like(Array2D, dtype=float)

    # Prevent division by zero
    if np.any(mask_non_zero):
        max_val = Array2D[mask_non_zero].max()
        if max_val > 0:
            normalized_array[mask_non_zero] = Array2D[mask_non_zero] / max_val

    # Generate the RGB heatmap, ignoring zeros
    result_array_ = intensity_to_rgb_heatmap_normalized(normalized_array)

    # Add the alpha channel: 1 for non-zero values, 0 for zero values
    alpha_channel = mask_non_zero.astype(float)

    return np.dstack((result_array_, alpha_channel))

def extract_vectors(self, current_positions_array: List[Union[float, Tuple[float, ...]]]) -> None:
    """
    Extract X, Y, Z vectors from an array of N-dimensional tuples (up to 3 dimensions)
    or floats (treated as X coordinates with Y and Z set to 0).

    :param current_positions_array: A list containing floats or tuples,
                                    each containing up to 3 coordinates (x, y, z).
    """
    # Initialize empty lists
    self.X_vec, self.Y_vec, self.Z_vec = [], [], []

    for pos in current_positions_array:
        if isinstance(pos, float):  # If pos is a float, treat it as an X coordinate
            self.X_vec.append(pos)
            self.Y_vec.append(0.0)  # Append 0 for missing Y
            self.Z_vec.append(0.0)  # Append 0 for missing Z
        elif isinstance(pos, tuple):  # If pos is a tuple, process it as coordinates
            if len(pos) > 0:  # X coordinate exists
                self.X_vec.append(pos[0])
            else:
                self.X_vec.append(0.0)
            if len(pos) > 1:  # Y coordinate exists
                self.Y_vec.append(pos[1])
            else:
                self.Y_vec.append(0.0)
            if len(pos) > 2:  # Z coordinate exists
                self.Z_vec.append(pos[2])
            else:
                self.Z_vec.append(0.0)
        else:
            raise TypeError(f"Invalid type in current_positions_array: {type(pos)}")

    # Convert empty lists to None if a dimension is missing (optional)
    self.X_vec = self.X_vec if self.X_vec else 0
    self.Y_vec = self.Y_vec if self.Y_vec else 0
    self.Z_vec = self.Z_vec if self.Z_vec else 0

def calculate_g2(self, correlated_histogram: Union[List[float], np.ndarray]) -> float:
    # Ensure that correlated_histogram has at least 40 elements
    if len(correlated_histogram) < 40:
        print("correlated_histogram should have at least 40 elements.")
        return 1

    # Compute the average of the first 10 points
    avg_first_10 = np.mean(correlated_histogram[:10])

    # Compute the center index (center of the array)
    center_index = len(correlated_histogram) // 2

    # Compute the indices for the 10 points around the center (+-5 from the center)
    start_idx = max(center_index - 5, 0)
    end_idx = min(center_index + 5 + 1, len(correlated_histogram))

    # Use the minimum of the 10 center values
    min_center_10 = np.min(correlated_histogram[start_idx:end_idx])

    # Return the ratio: min(center 10) / avg(first 10)
    return np.min([min_center_10 / (avg_first_10 + np.finfo(float).eps), 1])

def delayed_actions(self):
    # ✅ Setup dummy zero scan data (5×5×5)
    self.scan_data = np.zeros((5, 5, 5), dtype=float)
    self.idx_scan = [2, 2, 2]  # Middle slice for each axis
    self.Xv = np.linspace(0, 1, 5)
    self.Yv = np.linspace(0, 1, 5)
    self.Zv = np.linspace(0, 1, 5)
    self.startLoc = [0, 0, 0]
    self.endLoc = [1, 1, 1]

    # Call plot function
    load_window_positions()
    self.Plot_Loaded_Scan()
    load_window_positions()
    self.hide_legend()

def get_device_position(self, device):
    device.GetPosition()
    position = [0] * 3
    for channel in range(3):
        position[channel] = int(device.AxesPositions[channel] / device.StepsIn1mm * 1e3 * 1e6)  # [pm]
    return position

def intensity_to_rgb_heatmap(self, intensity):
    # Define a colormap (you can choose any colormap from Matplotlib)
    # cmap = plt.get_cmap('hot')
    cmap = plt.get_cmap('jet')

    # Normalize the intensity to the range [0, 1] (if necessary)
    intensity = max(0, min(0.99999999, intensity))

    # Map the intensity value to a color in the colormap
    rgba_color = cmap(intensity)

    # Convert RGBA tuple to RGB tuple (discard alpha channel)
    rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))

    return rgb_color

def FastScan_updateGraph(self):
        # Update the graph label with the current experiment name, iteration, and last Y value
        dpg.set_item_label("graphXY", f"{self.exp.name}, iteration = {self.iteration}, lastVal = {round(self.Y_vec[-1], 0)}")

        # Set the values for the X and Y data series
        dpg.set_value("series_counts", [self.X_vec, self.Y_vec])

        # Set the reference counts series to be empty
        dpg.set_value("series_counts_ref", [[], []])

        # Update the axis labels
        dpg.set_item_label("y_axis", "Intensity [kCounts/sec]")
        dpg.set_item_label("x_axis", "Position [pm]")

        # Fit the axis data to the new data range
        dpg.fit_axis_data('x_axis')
        dpg.fit_axis_data('y_axis')

        # Bind themes to the data series for visual distinction
        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")