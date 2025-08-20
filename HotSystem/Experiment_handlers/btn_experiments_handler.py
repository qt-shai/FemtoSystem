import time
import dearpygui.dearpygui as dpg
import glfw
import numpy as np

def Update_close_all_qm(sender, app_data, user_data):
    sender.chkbox_close_all_qm = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_close_all_qm", value=sender.chkbox_close_all_qm)
    print("Set chkbox_close_all_qm to: " + str(sender.chkbox_close_all_qm))

def Update_benchmark_switch_flag(sender, app_data, user_data):
    sender.benchmark_switch_flag = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_no_gate_benchmark", value=sender.benchmark_switch_flag)
    print("Set chkbox_no_gate_benchmark to: " + str(sender.benchmark_switch_flag))

def Update_benchmark_one_gate_only(sender, app_data, user_data):
    sender.benchmark_one_gate_only = user_data
    time.sleep(0.001)
    dpg.set_value(item="chkbox_single_gate_benchmark", value=sender.benchmark_one_gate_only)
    print("Set chkbox_single_gate_benchmark to: " + str(sender.benchmark_one_gate_only))

def Common_updateGraph(self, _xLabel="?? [??],", _yLabel="I [kCounts/sec]"):
    try:
        # todo: use this function as general update graph for all experiments
        self.lock.acquire()
        dpg.set_item_label("graphXY",
                           f"{self.exp.name}, iteration = {self.iteration}, tracking_ref = {self.tracking_ref: .1f}, ref Threshold = {self.refSignal: .1f},shuffle = {self.bEnableShuffle}, Tracking = {self.bEnableSignalIntensityCorrection}")
        dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
        if any(self.Y_vec_ref):
            dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
        if self.exp == Experiment.Nuclear_Fast_Rot:
            dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
        if self.exp == Experiment.RandomBenchmark:
            dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            dpg.set_value("series_counts_ref3", [self.X_vec, self.Y_vec_ref3])
            dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_vec_squared])  # MIC: works!
        if self.exp == Experiment.NUCLEAR_MR:
            dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            dpg.set_value("series_counts_ref3", [self.X_vec, self.Y_vec2])
            # dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_vec_squared]) # MIC: works!
        if self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
            dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_resCalculated])
        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            # dpg.set_value("Statistical counts", [self.X_vec, self.Y_vec_2])
            pass
        dpg.set_item_label("y_axis", _yLabel)
        dpg.set_item_label("x_axis", _xLabel)
        dpg.fit_axis_data('x_axis')
        dpg.fit_axis_data('y_axis')
        self.lock.release()  # self.lock.acquire()


    except Exception as e:
        print(f"{e}")
        self.btnStop()

def generate_x_y_vectors_for_average(self):
    if len(self.scan_frequencies_aggregated) == 0:
        print("One or more input arrays are empty")
        return

    # Use bins from X_vec and ensure they are sorted and unique
    bins = np.array(self.X_vec)
    # bins = np.unique(np.sort(bins))  # Ensure bins are monotonically increasing

    counts_aggregated = np.array(self.scan_counts_aggregated)
    freqs_aggregated = np.array(self.scan_frequencies_aggregated)

    if bins.size == 0 or counts_aggregated.size == 0 or freqs_aggregated.size == 0:
        print("One or more input arrays are empty")
        return

    # Flatten and concatenate the arrays
    flat_freqs = np.concatenate(freqs_aggregated) / 1e6
    flat_counts = np.concatenate(counts_aggregated)

    # Initialize Y_vec_ref with NaNs, keeping the same shape as X_vec
    self.Y_vec_ref = np.full(len(bins), np.nan)

    # Align Y_vec_ref with X_vec bins
    for i in range(len(bins)):
        mask = (flat_freqs >= bins[i]) & (flat_freqs < (bins[i + 1] if i + 1 < len(bins) else float('inf')))
        if np.any(mask):  # Ensure there's data in this bin
            self.Y_vec_ref[i] = np.mean(flat_counts[mask])  # Store mean count for this bin

    # Normalizing mean values
    try:
        min_ref = min(self.Y_vec_ref)
        max_ref = max(self.Y_vec_ref)
        max_y = max(self.Y_vec)

        if max_ref == min_ref:
            print("All elements in Y_vec_ref are the same. Normalization cannot be performed.")
            return

        # Normalize Y_vec_ref to the range [0, max(Y_vec)]
        self.Y_vec_ref = [
            (value - min_ref) / (max_ref - min_ref) * max_y for value in self.Y_vec_ref
        ]
        # print("Y_vec_ref normalized successfully.")
    except Exception as e:
        print(f"An error occurred in generate_x_y_vectors_for_average: {e}")

def ensure_list(self, x):
    """Return x if it is a list, otherwise wrap x in a list."""
    return x if isinstance(x, list) else [x]

def FetchData(self):
    self.pgm_end = False
    self.refSignal = 0
    if self.bEnableSignalIntensityCorrection:  # prepare search maxI thread
        self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
        # Do all the checks here. This includes motor positioning, laser stability and interforometer checks
        # Later those are to be made into buttons

    # verify job has started
    if not self.simulation:
        while not self.job._is_job_running:
            time.sleep(0.1)
        time.sleep(0.1)

    # fetch right parameters
    if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
        self.results = fetching_tool(self.job, data_list=["counts", "counts_ref"], mode="live")
    elif self.exp == Experiment.AWG_FP_SCAN:
        self.results = fetching_tool(self.job, data_list=["counts"], mode="live")
    elif self.exp == Experiment.G2:
        self.results = fetching_tool(self.job, data_list=["g2", "total_counts", "iteration"], mode="live")
    elif self.exp == Experiment.RandomBenchmark:
        # If nothing else get added you can put it in with counter
        self.results = fetching_tool(self.job,
                                     data_list=["counts", "counts_ref", "counts_ref2", "iteration", "tracking_ref",
                                                "number_order", "counts_square", "counts_ref3"], mode="live")
    elif self.exp == Experiment.NUCLEAR_MR:
        self.results = fetching_tool(self.job,
                                     data_list=["counts", "counts2", "counts_ref", "counts_ref2", "iteration",
                                                "tracking_ref"], mode="live")
    elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
        self.results = fetching_tool(self.job,
                                     data_list=["counts", "counts_ref", "counts_ref2", "resCalculated", "iteration",
                                                "tracking_ref"], mode="live")
    elif self.exp == Experiment.Nuclear_Fast_Rot:
        self.results = fetching_tool(self.job,
                                     data_list=["counts", "counts_ref", "counts_ref2", "iteration", "tracking_ref"],
                                     mode="live")
    elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        # if not self.simulation:
        self.results = fetching_tool(self.job, data_list=["iteration_list", "times", "counts", "statistics_counts",
                                                          "pulse_type"], mode="live")
        # if self.simulation:
        #     self.job = JobTesting_OPX.MockJob()
        # else:
        #     counts = create_counts_vector(vector_size=96)
        #     self.results = fetching_tool(job = JobTesting_OPX.MockJob(counts), data_list=["counts"], mode="live")
    else:
        self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "iteration", "tracking_ref"],
                                     mode="live")

    self.reset_data_val()

    dpg.bind_item_theme("series_counts", "LineYellowTheme")
    dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
    dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
    dpg.bind_item_theme("series_counts_ref3", "LineBlueTheme")
    dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

    self.lastTime = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6
    while self.results.is_processing():
        self.GlobalFetchData()

        dpg.set_item_label("series_counts", "counts")
        dpg.set_item_label("series_counts_ref", "counts_ref")

        if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
            try:
                dpg.set_item_label("graphXY", f"{self.exp.name},  lastVal = {round(self.Y_vec[-1], 2)}")
                dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
                dpg.set_value("series_counts_ref2", [[], []])
                dpg.set_value("series_res_calcualted", [[], []])
                dpg.set_item_label("series_counts", "det_1")
                dpg.set_item_label("series_counts_ref", "det_2")
                dpg.set_item_label("y_axis", "I [kCounts/sec]")
                dpg.set_item_label("x_axis", "time [sec]" if self.exp == Experiment.COUNTER else "Frequency [GHz]")
                dpg.fit_axis_data('x_axis')
                dpg.fit_axis_data('y_axis')

                dpg.bind_item_theme("series_counts", "LineYellowTheme")
                dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
                dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

            except:
                print('Failed updaitng graph')
            # self.Counter_updateGraph()

        if self.exp == Experiment.AWG_FP_SCAN:
            try:
                dpg.set_item_label("graphXY", f"{self.exp.name},  lastVal = {round(self.Y_vec[-1], 2)}")
                dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                dpg.set_item_label("y_axis", "I [kCounts/sec]")
                dpg.set_item_label("x_axis", "Frequency [GHz]")
                dpg.fit_axis_data('x_axis')
                dpg.fit_axis_data('y_axis')

                dpg.bind_item_theme("series_counts", "LineYellowTheme")
            except:
                print('Failed updating graph in experiment AWG_FP_SCAN')

        if self.exp == Experiment.ODMR_CW:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [GHz]")
        if self.exp == Experiment.RABI:  # time
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [nsec]")
        if self.exp == Experiment.ODMR_Bfield:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [GHz]")
        if self.exp == Experiment.PULSED_ODMR:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [GHz]")
        if self.exp == Experiment.NUCLEAR_RABI:  # time
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [nsec]")
        if self.exp == Experiment.NUCLEAR_MR:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [MHz]")
        if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [GHz]")
        if self.exp == Experiment.Nuclear_spin_lifetimeS0:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Nuclear_spin_lifetimeS1:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Nuclear_Ramsay:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Hahn:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Electron_lifetime:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Electron_Coherence:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [msec]")
        if self.exp == Experiment.Nuclear_Fast_Rot:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="amp [v]")
        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="index")
        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="index")
        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            # No MOCU since Shai said it is not yet tested
            self.SearchPeakIntensity()
            self.check_srs_stability()
            # self.change_AWG_freq(channel = 1)
            self.Common_updateGraph(_xLabel="times", _yLabel="counts")
        if self.exp == Experiment.G2:
            dpg.set_item_label("graphXY",
                               f"{self.exp.name}, Iteration = {self.iteration}, Total Counts = {round(self.g2_totalCounts, 0)}, g2 = {self.calculate_g2(self.Y_vec):.3f}")
            dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
            dpg.set_value("series_counts_ref", [[], []])
            dpg.set_value("series_counts_ref2", [[], []])
            dpg.set_value("series_res_calcualted", [[], []])
            dpg.set_item_label("series_counts", "G2 val")
            dpg.set_item_label("series_counts_ref", "_")
            dpg.set_item_label("series_counts_ref2", "_")
            dpg.set_item_label("series_res_calcualted", "_")
            dpg.set_item_label("y_axis", "events")
            dpg.set_item_label("x_axis", "dt [nsec]")
            dpg.fit_axis_data('x_axis')
            dpg.fit_axis_data('y_axis')

            dpg.bind_item_theme("series_counts", "LineYellowTheme")
            dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
            dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
            dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")
        if self.exp == Experiment.testCrap:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="time [nsec]")
        if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="freq [GHz]")
        if self.exp == Experiment.RandomBenchmark:
            self.SearchPeakIntensity()
            self.Common_updateGraph(_xLabel="Number of gates")

        if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
            wavelengths = self.HW.wavemeter.measured_wavelength[-30:]
            if len(wavelengths) == 30 and any(
                    sum(wavelengths[i] < wavelengths[i - 1] for i in range(j, j + 5)) == 5 and
                    sum(wavelengths[i] > wavelengths[i - 1] for i in range(j + 5, j + 10)) == 5
                    for j in range(21)):
                self.qm.set_io2_value(True)
                print("Green repump pulse")

        self.current_time = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6
        if not (self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]) and (
                self.current_time - self.lastTime) > self.tGetTrackingSignalEveryTime:
            folder = "d:/temp/"
            if not os.path.exists(folder):
                folder = "c:/temp/"
                if not os.path.exists(folder):
                    folder = None
            self.btnSave(folder=folder)
            self.lastTime = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6  # if self.exp == Experiment.RandomBenchmark:

        if self.StopFetch:
            # self.btnSave(folder= "Q:/QT-Quantum_Optic_Lab/expData/G2/")
            pass

    if not (self.StopFetch):
        self.pgm_end = True
        self.btnStop()

def GlobalFetchData(self):
    self.lock.acquire()

    data = [self.ensure_list(x) for x in self.results.fetch_all()]

    if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
        self.counter_Signal, self.ref_signal = self.results.fetch_all()
    elif self.exp == Experiment.AWG_FP_SCAN:
        self.counter_signal = self.results.fetch_all()
    elif self.exp == Experiment.G2:
        self.g2Vec, self.g2_totalCounts, self.iteration = self.results.fetch_all()
    elif self.exp == Experiment.RandomBenchmark:
        self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal, self.number_order, self.signal_squared, self.ref_signal3 = self.results.fetch_all()  # grab/fetch new data from stream
    elif self.exp == Experiment.NUCLEAR_MR:
        self.signal, self.signal2, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
    elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
        self.signal, self.ref_signal, self.ref_signal2, self.resCalculated, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
    elif self.exp == Experiment.Nuclear_Fast_Rot:
        self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
    elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        self.iteration_list, self.times_of_signal, self.signal, self.statistics_signal, self.type_of_pulse = self.results.fetch_all()
    else:
        self.signal, self.ref_signal, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream

    if self.exp == Experiment.COUNTER:
        if len(self.X_vec) > self.NumOfPoints:
            self.Y_vec = self.Y_vec[-self.NumOfPoints:]  # get last NumOfPoint elements from end
            self.Y_vec_ref = self.Y_vec_ref[-self.NumOfPoints:]  # get last NumOfPoint elements from end
            self.X_vec = self.X_vec[-self.NumOfPoints:]

        self.Y_vec.append(
            self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
        self.Y_vec_ref.append(
            self.ref_signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
        self.X_vec.append(self.counter_Signal[1] / self.u.s)  # Convert timestamps to seconds

    if self.exp == Experiment.AWG_FP_SCAN:
        new_data = list(np.array(self.counter_signal[0]) / self.total_integration_time)
        if not self.Y_vec == new_data:
            self.X_vec = list(np.linspace(0, 10, 200)) + list(np.linspace(10, 20, 200))
            self.Y_vec_aggregated.extend(new_data)
            self.Y_vec = new_data

    if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
        if len(self.X_vec) > self.NumOfPoints:
            data_to_save = {"Frequency[GHz]": self.X_vec, "Intensity[KCounts/sec]": self.Y_vec,
                            "Resonant Laser Power Reading [V]": self.Y_vec_ref}
            self.save_to_cvs(file_name=self.csv_file, data=data_to_save, to_append=True)
            print(f"Saved data to {self.csv_file}.")
            self.Y_vec = []  # get last NumOfPoint elements from end
            self.Y_vec_ref = []  # get last NumOfPoint elements from end
            self.X_vec = []

        self.Y_vec.append(
            self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
        if self.HW.arduino:
            with self.HW.arduino.lock:
                self.Y_vec_ref.append(self.HW.arduino.last_measured_value)  # counts/second
        with self.HW.wavemeter.lock:
            y1 = self.HW.wavemeter.measured_wavelength[-2]
            y2 = self.HW.wavemeter.measured_wavelength[-1]
            dx1 = self.HW.wavemeter.measurement_times[-1] - self.HW.wavemeter.measurement_times[
                -2]  # time interval for frequency measurements
            dx2 = time.time() - self.HW.wavemeter.measurement_times[-1]
            # TODO: Fix wrong values at frequency turning points
        self.X_vec.append(y2 + (y2 - y1) * dx2 / dx1)  # Linear extrapolation from last point.

    if self.exp == Experiment.ODMR_CW:  # freq
        self.X_vec = self.f_vec / self.u.MHz / 1e3 + self.mw_freq  # [GHz]
        self.Y_vec = self.signal / 1000 / (self.Tcounter * 1e-9)
        self.Y_vec_ref = self.ref_signal / 1000 / (self.Tcounter * 1e-9)
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.RABI:  # time
        self.X_vec = self.t_vec  # [nsec]]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.ODMR_Bfield:  # freq
        self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.PULSED_ODMR:  # freq
        self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.NUCLEAR_RABI:  # time
        self.X_vec = self.t_vec  # [nsec]]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.NUCLEAR_MR:  # freq
        self.X_vec = self.f_vec / float(1e6)  # [MHz]
        self.X_vec = self.X_vec.tolist()
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec = self.Y_vec.tolist()
        self.Y_vec2 = self.signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec2 = self.Y_vec2.tolist()
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.Y_vec_ref.tolist()
        self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref2 = self.Y_vec_ref2.tolist()
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
        self.X_vec = self.scan_param_vec / float(1e9) + self.mw_freq  # [GHz]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Nuclear_spin_lifetimeS0:  # time
        self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Nuclear_spin_lifetimeS1:  # time
        self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Nuclear_Ramsay or self.exp == Experiment.Electron_Coherence:  # time
        self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Hahn:  # time
        self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Electron_lifetime:  # time
        self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.Nuclear_Fast_Rot:  # time
        self.X_vec = [e for e in self.rf_Pwr_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:  # todo: convert graph to bars instead of line
        self.X_vec = self.idx_vec_ini  # index
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_resCalculated = self.resCalculated / 1e6
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:  # todo: convert graph to bars instead of line
        self.X_vec = self.idx_vec_ini  # index
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_resCalculated = self.resCalculated / 1e6
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.G2:
        self.X_vec = self.GenVector(-self.correlation_width + 1, self.correlation_width, True)
        self.Y_vec = self.g2Vec  # *self.iteration

    if self.exp == Experiment.RandomBenchmark:
        # Add Y^2 and first measure order and reverse
        self.X_vec = [e for e in self.t_vec]  # [msec]
        self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec = self.Y_vec.tolist()
        self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = self.Y_vec_ref.tolist()
        self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref2 = self.Y_vec_ref2.tolist()
        self.benchmark_number_order = self.number_order
        self.benchmark_number_order = self.benchmark_number_order.tolist()
        # self.benchmark_reverse_number_order = self.reverse_number_order
        # self.benchmark_reverse_number_order = self.benchmark_reverse_number_order.tolist()
        self.Y_vec_squared = self.signal_squared / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_squared = self.Y_vec_squared.tolist()
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        self.Y_vec_ref3 = self.ref_signal3 / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref3 = self.Y_vec_ref3.tolist()

    if self.exp == Experiment.testCrap:  # freq or time oe something else
        ## todo add switch per test for correct normalization
        # if self.test_type == Experiment.test_electron_spinMeasure:
        #     self.X_vec = self.scan_param_vec * 4
        #     if self.iteration == 0:
        #         self.Y_vec = np.array(self.signal)/np.array(self.scan_param_vec)/1e-9/1e3
        #         self.Y_vec_ref = ((self.iteration)*self.Y_vec_ref + np.array(self.ref_signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
        #     elif self.iteration > 0:
        #         self.Y_vec = ((self.iteration)*self.Y_vec + np.array(self.signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
        #         self.Y_vec_ref = ((self.iteration)*self.Y_vec_ref + np.array(self.ref_signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
        #     self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        # else:
        self.X_vec = self.scan_param_vec * 4  # [nsec]/ float(1e9) + self.mw_freq  # [GHz]
        self.Y_vec = np.array(self.signal) / np.array(
            self.scan_param_vec) / 1e-9 / 1e3  # [kcounts] # / (self.TcounterPulsed * 1e-9) / 1e3
        self.Y_vec_ref = np.array(self.ref_signal) / np.array(self.scan_param_vec) / 1e-9 / 1e3  #
        self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        print(4)
        offset = 0
        all_times = []
        counts_vector = np.ones(np.size(self.signal))
        self.awg_freq_list = self.repeat_elements(self.awg_freq_list, self.n_avg)
        self.counts_in_bin1 = []
        self.counts_in_bin2 = []
        self.counts_in_bin3 = []
        for i in range(np.size(self.type_of_pulse)):
            if self.type_of_pulse is not None:
                if self.type_of_pulse[i] == 4:
                    self.list_of_pulse_type.append("xPulse_Pi")
                elif self.type_of_pulse[i] == 3:
                    self.list_of_pulse_type.append("yPulse_Pi")
                elif self.type_of_pulse[i] == 2:
                    self.list_of_pulse_type.append("xPulse_Pi_Half")
                elif self.type_of_pulse[i] == 1:
                    self.list_of_pulse_type.append("yPulse_Pi_Half")
            else:
                self.list_of_pulse_type.append("Simulation")
        for counts in self.signal:
            if counts > 0:
                relevant_times = self.times_of_signal[offset: offset + counts]
                self.times_by_measurement.append(relevant_times)
                offset += counts
            else:
                self.times_by_measurement.append([])

        for time_tag in self.times_by_measurement:
            # Timing is according to the blinking in the measure command
            # The timing needs to be parametrized somehow
            time_tag = np.array(time_tag)
            bin1_count = np.sum((time_tag >= self.bin_times[0][0]) & (time_tag < self.bin_times[0][1]))
            bin2_count = np.sum((time_tag >= self.bin_times[1][0]) & (time_tag < self.bin_times[1][1]))
            bin3_count = np.sum((time_tag >= self.bin_times[2][0]) & (time_tag < self.bin_times[2][1]))

            self.counts_in_bin1.append(bin1_count)
            self.counts_in_bin2.append(bin2_count)
            self.counts_in_bin3.append(bin3_count)

            all_times.extend(time_tag)

        time_counter = Counter(all_times)
        # sorted_times = sorted(time_counter.keys())
        # sorted_counts = [time_counter[t] for t in sorted_times]
        times = np.arange(0, self.bin_times[2][1], 1)
        counts = np.zeros(len(times), dtype=int)
        for i, t in enumerate(times):
            if t in time_counter:
                counts[i] = time_counter[t]
        # self.exact_counts_all_times = dict(time_counter) #Times: counts
        self.X_vec = times.tolist()
        self.Y_vec = counts.tolist()
        self.Y_vec_2 = self.statistics_signal
    self.lock.release()

def btnStartG2(self):
    self.exp = Experiment.G2
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartEilons(self):
    self.exp = Experiment.testCrap
    self.test_type = Experiment.test_electron_spinPump  # add comobox
    self.test_type = Experiment.test_electron_spinMeasure  # add comobox
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    if self.test_type == Experiment.test_electron_spinPump:
        # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
        # self.mwModule.Set_freq(self.mw_freq)
        # self.mwModule.Set_power(self.mw_Pwr)
        # self.mwModule.Set_IQ_mode_ON()
        # self.mwModule.Set_PulseModulation_ON()
        # if not self.bEnableSimulate:
        #     self.mwModule.Turn_RF_ON()
        pass
    if self.test_type == Experiment.test_electron_spinMeasure:
        pass

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def StartFetch(self, _target):
    self.to_xml()  # write class parameters to XML
    self.timeStamp = self.getCurrentTimeStamp()

    self.StopFetch = False
    self.fetchTh = threading.Thread(target=_target)
    self.fetchTh.start()

def repeat_elements(self, lst, k):
    return [item for item in lst for _ in range(k)]

def btnStartCounterLive(self, b_startFetch=True):
    try:
        if self.counter_is_live:
            print('Counter is already live')
            return
        self.exp = Experiment.COUNTER
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                         num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[
                                                                                                0] != 0 else 1)
        if b_startFetch and not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)
        self.counter_is_live = True
    except Exception as e:
        print(f"Failed to start counter live: {e}")

def wait_for_job(self):
    try:
        while not self.job:
            time.sleep(1)
        if hasattr(self.job, "wait_for_execution"):
            self.job.wait_for_execution()
        time.sleep(1)
    except Exception as e:
        print(f'Error while waiting for job: {e}')

def btnStartODMR_CW(self):
    self.exp = Experiment.ODMR_CW
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()

    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartRABI(self):
    self.exp = Experiment.RABI
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)
    if not self.bEnableSimulate and not self.mwModule.simulation:
        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        # self.mwModule.Set_IQ_mode_OFF()
        self.mwModule.Set_PulseModulation_ON()
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartODMR_Bfield(self):
    self.exp = Experiment.ODMR_Bfield

    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearFastRot(self):
    self.exp = Experiment.Nuclear_Fast_Rot
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz] # todo: remove in all other experiment and also fix QUA
    self.mw_freq = self.mw_freq_resonance
    # self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartPulsedODMR(self):
    self.exp = Experiment.PULSED_ODMR
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearRABI(self):
    self.exp = Experiment.NUCLEAR_RABI
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)
    self.mwModule.Set_freq(self.mw_freq_resonance)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartRandomBenchmark(self):
    self.exp = Experiment.RandomBenchmark
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)
    print("reached button callback")
    if self.mwModule is not None:
        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)
        # self.FetchData()

def btnStartPopulateGateTomography(self):
    self.exp = Experiment.POPULATION_GATE_TOMOGRAPHY
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartStateTomography(self):
    self.exp = Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartTimeBinEntanglement(self):
    self.exp = Experiment.TIME_BIN_ENTANGLEMENT
    if self.simulation:
        self.qmm = QuantumMachinesManager(host=self.HW.config.opx_ip, cluster_name=self.HW.config.opx_cluster,
                                          timeout=60)  # in seconds
        time.sleep(1)
        self.close_qm_jobs()
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
    # self.mwModule.Set_freq(self.mw_freq)
    # self.mwModule.Set_power(self.mw_Pwr)
    # self.mwModule.Set_IQ_mode_ON()
    # self.mwModule.Set_PulseModulation_ON()
    # if not self.bEnableSimulate:
    #     self.mwModule.Turn_RF_ON()
    # calculates the count based on division due to timing limitaiton of the counter
    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)
        print("Fetching Data")

def btnStartNuclearPolESR(self):
    self.exp = Experiment.NUCLEAR_POL_ESR
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearMR(self):
    self.exp = Experiment.NUCLEAR_MR
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mwModule.Set_freq(self.mw_freq_resonance)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearSpinLifetimeS0(self):
    self.exp = Experiment.Nuclear_spin_lifetimeS0
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearSpinLifetimeS1(self):
    self.exp = Experiment.Nuclear_spin_lifetimeS1
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartNuclearRamsay(self):
    self.exp = Experiment.Nuclear_Ramsay
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
    if self.mwModule is not None:
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartElectron_Coherence(self):
    self.exp = Experiment.Electron_Coherence
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    # self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
    self.mwModule.Set_freq(self.mw_freq_resonance)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartHahn(self):
    self.exp = Experiment.Hahn
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
    self.mwModule.Set_freq(self.mw_freq)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def btnStartElectronLifetime(self):
    self.exp = Experiment.Electron_lifetime
    self.GUI_ParametersControl(isStart=self.bEnableSimulate)

    self.mwModule.Set_freq(self.mw_freq_resonance)
    self.mwModule.Set_power(self.mw_Pwr)
    self.mwModule.Set_IQ_mode_ON()
    self.mwModule.Set_PulseModulation_ON()
    if not self.bEnableSimulate:
        self.mwModule.Turn_RF_ON()

    self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

    if not self.bEnableSimulate:
        self.StartFetch(_target=self.FetchData)

def StopJob(self, job, qm):
    job.halt()
    report = job.execution_report()
    print(report)
    qm.close()
    newQM = self.qmm.list_open_qms()
    print(f"after close: {newQM}")
    return report

def stop_benchmark(self):
    self.stopScan = True
    self.StopFetch = True

    self.btnSave()

def btnStop(self):  # Stop Exp
        try:
            if self.survey_thread is not None and self.survey_thread.is_alive() and self.stop_survey:
                # Signal the survey thread to stop gracefully, e.g., by setting a stop flag
                self.survey_stop_flag = True
                self.survey_thread.join()
            # todo: creat methode that handle OPX close job and instances
            self.stopScan = True
            self.StopFetch = True
            if not self.exp == Experiment.SCAN:
                if hasattr(self, 'MAxSignalTh') and self.bEnableSignalIntensityCorrection:
                    if self.MAxSignalTh.is_alive():
                        self.MAxSignalTh.join()
            else:
                dpg.set_item_label("btnOPX_StartScan", "Start Scan")
                dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")

            self.GUI_ParametersControl(True)

            if not self.simulation and self.job:
                self.StopJob(self.job, self.qm)

            if not self.exp == Experiment.SCAN:
                if hasattr(self, 'fetchTh'):
                    while self.fetchTh.is_alive():
                        # if not(self.pgm_end):
                        time.sleep(0.1)
            else:
                dpg.enable_item("btnOPX_StartScan")

            self.Shoot_Femto_Pulses = False

            if self.exp == Experiment.COUNTER or self.exp == Experiment.SCAN or self.exp == Experiment.G2:
                self.counter_is_live = False
            else:
                if hasattr(self.mwModule, 'RFstate'):
                    self.mwModule.Get_RF_state()
                    if self.mwModule.RFstate:
                        self.mwModule.Turn_RF_OFF()

            if self.exp not in [Experiment.COUNTER, Experiment.SCAN, Experiment.PLE,
                                Experiment.EXTERNAL_FREQUENCY_SCAN]:
                self.btnSave()
            if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
                data_to_save = {"Frequency[GHz]": self.X_vec, "Intensity[KCounts/sec]": self.Y_vec,
                                "Resonant Laser Power Reading [V]": self.Y_vec_ref}
                self.save_to_cvs(file_name=self.csv_file, data=data_to_save, to_append=True)
                print(f"Saved data to {self.csv_file}.")
                print('Scan finished. Copying files.')
                folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + '/'
                destination_csv = os.path.join(folder_path, os.path.basename(self.csv_file))
                print(f"Copying file {self.csv_file} to {destination_csv}.")
                shutil.copy(self.csv_file, destination_csv)


        except Exception as e:
            print(f"An error occurred in btnStop: {e}")