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
