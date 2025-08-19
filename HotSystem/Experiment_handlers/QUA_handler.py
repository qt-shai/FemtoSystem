import numpy as np
from matplotlib import pyplot as plt
from qm.jobs.base_job import QmBaseJob
from qm.qua._expressions import QuaVariable, QuaVariableType
#from qm_saas import QmSaas, QoPVersion
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig, QuantumMachine, QmJob, QmPendingJob
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, assign, \
    elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger, counting, Math, Cast, case_, \
    switch_, strict_timing_, declare_input_stream
from gevent.libev.corecext import callback
from matplotlib import pyplot as plt
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from qualang_tools.results import fetching_tool
from qualang_tools.results import progress_counter, fetching_tool
from functools import partial
from qualang_tools.units import unit
from Common import Experiment
from typing import Union, Optional, Callable, List, Tuple, Any
import SystemConfig as configs

def reset_data_val(self):
    self.X_vec = []
    self.X_vec_ref = []
    self.Y_vec = []
    self.Y_vec2 = []
    self.Y_vec_ref = []
    self.Y_vec_ref2 = []
    self.Y_vec_ref3 = []
    self.Y_resCalculated = []
    self.Y_vec_squared = []
    self.benchmark_number_order = []
    self.benchmark_reverse_number_order = []
    self.benchmark_number_order_first_iteration = []
    self.benchmark_number_order_first_iteration = []
    self.tracking_ref = 0
    self.refSignal = 0
    self.iteration = 0
    self.counter = -10

def initQUA_gen(self, n_count=1, num_measurement_per_array=1):
    self.reset_data_val()
    self.to_xml()
    if self.exp == Experiment.COUNTER:
        self.counter_QUA_PGM(n_count=int(n_count))
    if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
        self.counter_QUA_PGM(n_count=int(n_count))
    if self.exp == Experiment.ODMR_CW:
        self.ODMR_CW_QUA_PGM()
    if self.exp == Experiment.RABI:
        self.RABI_QUA_PGM()
    if self.exp == Experiment.PULSED_ODMR:
        self.PulsedODMR_QUA_PGM()
    if self.exp == Experiment.NUCLEAR_RABI:
        self.NuclearRABI_QUA_PGM()
    if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
        self.Entanglement_gate_tomography_QUA_PGM(execute_qua=True)
    if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
        self.Population_gate_tomography_QUA_PGM(execute_qua=True)
    if self.exp == Experiment.NUCLEAR_POL_ESR:
        self.Nuclear_Pol_ESR_QUA_PGM(execute_qua=True)
    if self.exp == Experiment.NUCLEAR_MR:
        self.NuclearMR_QUA_PGM()
    if self.exp == Experiment.Nuclear_spin_lifetimeS0:
        self.Nuclear_spin_lifetimeS0_QUA_PGM()
    if self.exp == Experiment.Nuclear_spin_lifetimeS1:
        self.Nuclear_spin_lifetimeS1_QUA_PGM()
    if self.exp == Experiment.Nuclear_Ramsay:
        self.Nuclear_Ramsay_QUA_PGM()
    if self.exp == Experiment.Hahn:
        self.Hahn_QUA_PGM()
    if self.exp == Experiment.Electron_lifetime:
        self.Electron_lifetime_QUA_PGM()
    if self.exp == Experiment.Electron_Coherence:
        self.Electron_Coherence_QUA_PGM()
    if self.exp == Experiment.SCAN:  # ~ 35 msec per measurement for on average for larage scans
        self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count),
                                      num_measurement_per_array=int(num_measurement_per_array),
                                      triggerThreshold=self.ScanTrigger)
    if self.exp == Experiment.ODMR_Bfield:
        self.ODMR_Bfield_QUA_PGM()
    if self.exp == Experiment.Nuclear_Fast_Rot:
        self.NuclearFastRotation_QUA_PGM()
    if self.exp == Experiment.G2:
        self.g2_raw_QUA()
    if self.exp == Experiment.testCrap:
        self.Test_Crap_QUA_PGM()
    if self.exp == Experiment.RandomBenchmark:
        self.Random_Benchmark_QUA_PGM()
    if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        self.time_bin_entanglement_QUA_PGM(execute_qua=True)
    if self.exp == Experiment.PLE:
        self.bEnableShuffle = False
        # self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count), num_measurement_per_array=int(num_measurement_per_array), triggerThreshold=self.ScanTrigger)
        self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count),
                                      num_measurement_per_array=int(num_measurement_per_array),
                                      triggerThreshold=self.ScanTrigger,
                                      play_element=configs.QUAConfigBase.Elements.RESONANT_LASER.value)
        # self.MeasureByTrigger_Track_QUA_PGM(num_bins_per_measurement=int(n_count), num_measurement_per_array=int(num_measurement_per_array),triggerThreshold=self.ScanTrigger)
        self.bEnableShuffle = False
        self.MeasurePLE_QUA_PGM(trigger_threshold=self.ScanTrigger)
    if self.exp == Experiment.AWG_FP_SCAN:
        self.Y_vec_aggregated = []
        self.awg_sync_counter_QUA_PGM()

def QUA_execute(self, closeQM=False, quaPGM=None, QuaCFG=None):
    if QuaCFG == None:
        QuaCFG = self.quaCFG

    if self.bEnableSimulate:
        sourceFile = open('debug.py', 'w')
        print(generate_qua_script(self.quaPGM, QuaCFG), file=sourceFile)
        sourceFile.close()
        simulation_config = SimulationConfig(duration=48000)  # clock cycles
        job_sim = self.qmm.simulate(QuaCFG, self.quaPGM, simulation_config)
        # Simulate blocks python until the simulation is done
        waveform_report = job_sim.get_simulated_waveform_report()
        waveform_report.create_plot(plot=True, save_path="./")
        job_sim.get_simulated_samples().con1.plot()
        if self.connect_to_QM_OPX:
            # self.instance.close()
            pass
        if self.exp == Experiment.RandomBenchmark:
            waveform_report = job_sim.get_simulated_waveform_report()
            waveform_report.create_plot(plot=True, save_path="./")
        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            # waveform_report = job_sim.get_simulated_waveform_report()
            # waveform_report.create_plot(plot=True, save_path="./")
            pass
        plt.show()

        return None, None
    else:
        if closeQM or self.chkbox_close_all_qm:
            self.chkbox_close_all_qm = False
            self.qmm.close_all_quantum_machines()

        if quaPGM is None:
            quaPGM = self.quaPGM

        list_before = self.qmm.list_open_qms()
        print(f"before open new job: {list_before}")

        qm = self.qmm.open_qm(config=QuaCFG, close_other_machines=closeQM)
        qm_id = qm.id
        job = qm.execute(quaPGM)
        job_id = job.id

        list_after = self.qmm.list_open_qms()
        print(f"after open new job: {list_after}")

        self.my_qua_jobs = []  # todo: optional so have more then one program open from same QMachine
        self.my_qua_jobs.append({"qm_id": qm_id, "job_id": job_id})
        # Save the jobs to a text file
        with open('qua_jobs.txt', 'w') as f:
            for _job in self.my_qua_jobs:
                f.write(f"{_job['qm_id']},{_job['job_id']}\n")

        if self.connect_to_QM_OPX:
            # self.instance.close()
            pass

        return qm, job

def verify_insideQUA_FreqValues(self, freq, min=0, max=400):  # [MHz]
    if freq < min * self.u.MHz or freq > max * self.u.MHz:
        raise Exception(
            f'freq {freq} is out of range [{min},{max}]. verify base freq is up to 400 MHz relative to resonance')

def GenVector(self, min, max, delta, asInt=False, N="none"):
    if N == "none":
        N = int((max - min) / delta + 1)
    vec1 = np.linspace(min, max, N, endpoint=True)
    if asInt:
        vec1 = vec1.astype(int)
    # vec2 = np.arange(min, max + delta/10, delta)
    return vec1

def get_detector_input_type(self, detector_name: str) -> str:
    """
       Determines the input channel type (analog or digital) of a detector based on its configuration file.

       :param detector_name: The name of the detector (e.g., "Detector_OPD").
       :param config: The configuration dictionary containing all element configurations.
       :return: "analog" if the detector uses an analog channel, "digital" if it uses a digital channel,
                or "unknown" if the type cannot be determined.
       """
    try:
        # Check if the detector uses a digital channel
        if "digitalOutputs" in detector_name:
            return "digital"
        else:
            return "analog"
    except Exception as e:
        print(f"An error has occurred in finding detector input type: {e}")

def get_time_tagging_func(self, detector_name):
    """
       Return the appropriate time-tagging function (digital or analog)
       but do not call it yet.
       """
    input_type = self.get_detector_input_type(detector_name)
    dispatch_map = {
        "digital": time_tagging.digital,
        "analog": time_tagging.analog,
    }
    if input_type not in dispatch_map:
        raise ValueError(f"Unknown detector input type: {input_type}")

    return dispatch_map[input_type]

def QUA_shuffle(self, array, array_len):
    temp = declare(int)
    j = declare(int)
    i = declare(int)
    with for_(i, 0, i < array_len, i + 1):
        assign(j, Random().rand_int(array_len - i))
        assign(temp, array[j])
        assign(array[j], array[array_len - 1 - i])
        assign(array[array_len - 1 - i], temp)

def MW_and_reverse(self, p_mw, t_mw):
    play("xPulse" * amp(p_mw), "MW", duration=t_mw)
    play("-xPulse" * amp(p_mw), "MW", duration=t_mw)

def MW_and_reverse_general(self, p_mw, t_mw, first_pulse: str = "xPulse", second_pulse: str = "-xPulse"):
    # Todo  add option for pulses with duration not divided by 4
    play(first_pulse * amp(p_mw), "MW", duration=t_mw)  # pi pulse
    play(second_pulse * amp(p_mw), "MW", duration=t_mw)  # pi pulse

def QUA_Pump(self, t_pump, t_mw, t_rf, f_mw, f_rf, p_mw, p_rf, t_wait):
    align()

    # set frequencies to resonance
    update_frequency("MW", f_mw)
    update_frequency("RF", f_rf)

    # print(t_wait)
    # play MW
    # play("xPulse"* amp(p_mw), "MW", duration=t_mw // 4)
    self.MW_and_reverse(p_mw, (t_mw / 2) // 4)
    # play RF (@resonance freq & pulsed time)
    align("MW", "RF")
    play("const" * amp(p_rf), "RF", duration=(t_rf >> 2))
    # turn on laser to polarize
    align("RF", "Laser")
    play("Turn_ON", "Laser", duration=t_pump // 4)
    align()
    if t_wait > 16:
        wait(t_wait // 4)

def QUA_PGM(self):  # , exp_params, QUA_exp_sequence):
    if self.exp == Experiment.G2:
        self.g2_raw_QUA()
    else:
        with program() as self.quaPGM:
            self.n = declare(int)  # iteration variable
            self.n_st = declare_stream()  # stream iteration number
            self.n_st_2 = declare_stream()
            self.times = declare(int, size=100)
            self.times_ref = declare(int, size=100)

            self.f = declare(
                int)  # frequency variable which we change during scan - here f is according to calibration function
            self.t = declare(int)  # [cycles] time variable which we change during scan
            self.p = declare(fixed)  # [unit less] proportional amp factor which we change during scan

            self.m = declare(int)  # number of pumping iterations
            self.n_m = declare(int)  # Number of iteration inside a loop
            self.i_idx = declare(int)  # iteration variable
            self.j_idx = declare(int)  # iteration variable
            self.k_idx = declare(int)  # iteration variable

            self.site_state = declare(int)  # site preperation state
            self.m_state = declare(int)  # measure state

            self.simulation_random_integer = declare(int, size=100)
            # assign(self.simulation_random_integer, self.random_int)

            self.counts_tmp = declare(int)  # temporary variable for number of counts
            self.counts_tmp2 = declare(int)  # temporary variable for number of counts
            self.counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
            self.counts_ref2_tmp = declare(int)  # 2nd temporary variable for number of counts reference
            self.total_counts = declare(int, value=0)

            self.runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            self.track_idx = declare(int, value=0)  # iteration variable
            self.tracking_signal_tmp = declare(int)  # tracking temporary variable
            self.tracking_signal = declare(int, value=0)  # tracking variable
            self.tracking_signal_st = declare_stream()  # tracking stream variable
            self.sequenceState = declare(int, value=0)  # IO1 variable

            self.counts = declare(int, size=self.vectorLength)  # experiment signal (vector)
            self.counts_ref = declare(int, size=self.vectorLength)  # reference signal (vector)
            self.counts_ref2 = declare(int, size=self.vectorLength)  # reference signal (vector)
            self.resCalculated = declare(int, size=self.vectorLength)  # normalized values vector

            # Shuffle parameters
            # self.val_vec_qua = declare(fixed, value=self.p_vec_ini)    # volts QUA vector
            # self.f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            self.val_vec_qua = declare(int, value=np.array([int(i) for i in self.scan_param_vec]))  # volts QUA vector
            self.idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
            self.idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            self.counts_st = declare_stream()  # experiment signal
            self.counts2_st = declare_stream()  # 2nd experiment signal
            self.counts_ref_st = declare_stream()  # reference signal
            self.counts_ref2_st = declare_stream()  # reference signal
            self.resCalculated_st = declare_stream()  # reference signal
            self.total_counts_st = declare_stream()

            # if self.benchmark_switch_flag and self.exp == Experiment.RandomBenchmark:
            #     self.QUA_Pump(t_pump=self.tLaser, t_mw=self.tMW / 2, t_rf=self.tRF,
            #               f_mw=self.mw_freq * self.u.MHz,
            #               f_rf=self.rf_resonance_freq * self.u.MHz,
            #               p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=self.t_wait_benchmark)
            with for_(self.n, 0, self.n < self.n_avg, self.n + 1):  # AVG loop
                # reset vectors
                with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
                    assign(self.counts_ref2[self.idx], 0)  # shuffle - assign new val from randon index
                    assign(self.counts_ref[self.idx], 0)  # shuffle - assign new val from randon index
                    assign(self.counts[self.idx], 0)  # shuffle - assign new val from randon index
                    assign(self.resCalculated[self.idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(self.idx_vec_qua,
                                     self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(self.idx, 0, self.idx < self.array_length, self.idx + 1):  # loop over scan vector
                    assign(self.sequenceState, IO1)
                    with if_(self.sequenceState == 0):
                        self.execute_QUA()

                    with else_():
                        assign(self.tracking_signal, 0)
                        with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, self.time_tagging_fn(self.times_ref,
                                                                                              self.time_in_multiples_cycle_time(
                                                                                                  self.Tcounter),
                                                                                              self.tracking_signal_tmp))
                            assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(self.runTracking):
                    assign(self.track_idx, self.track_idx + 1)  # step up tracking counter
                    with if_(self.track_idx > self.trackingNumRepeatition - 1):
                        assign(self.tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, self.time_tagging_fn(self.times_ref,
                                                                                              self.time_in_multiples_cycle_time(
                                                                                                  self.Tcounter),
                                                                                              self.tracking_signal_tmp))
                            assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                        assign(self.track_idx, 0)

                # stream
                with if_(self.sequenceState == 0):
                    if self.exp == Experiment.RandomBenchmark:
                        save(self.total_counts, self.counts_st)  # MIC: I think this is an error
                        save(self.counts[self.idx], self.counts_st)  # MIC: I think this is correct
                        save(self.counts_ref[self.idx], self.counts_ref_st)
                        save(self.counts_ref2[self.idx], self.counts_ref2_st)
                        save(self.resCalculated[self.idx], self.resCalculated_st)
                    elif self.exp == Experiment.NUCLEAR_MR:
                        with for_(self.idx, 0, self.idx < self.vectorLength,
                                  self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                            save(self.counts[self.idx], self.counts_st)
                            save(self.counts2[self.idx], self.counts2_st)
                            save(self.counts_ref[self.idx], self.counts_ref_st)
                            save(self.counts_ref2[self.idx], self.counts_ref2_st)
                    else:
                        with for_(self.idx, 0, self.idx < self.vectorLength,
                                  self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                            save(self.counts[self.idx], self.counts_st)
                            save(self.counts_ref[self.idx], self.counts_ref_st)
                            save(self.counts_ref2[self.idx], self.counts_ref2_st)
                            save(self.resCalculated[self.idx], self.resCalculated_st)

                save(self.n, self.n_st)  # save number of iteration inside for_loop
                save(self.tracking_signal, self.tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                if self.exp == Experiment.RandomBenchmark:
                    # self.counts_st.save_all("counts")
                    # self.n_st.save_all("iteration")
                    self.counts_st.save_all("counts")
                    self.n_st.save_all("iteration")
                else:
                    self.counts_st.buffer(self.vectorLength).average().save("counts")
                    self.counts_ref_st.buffer(self.vectorLength).average().save("counts_ref")
                    self.counts_ref2_st.buffer(self.vectorLength).average().save("counts_ref2")
                    self.resCalculated_st.buffer(self.vectorLength).average().save("resCalculated")
                    self.n_st.save("iteration")
                    self.tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def QUA_PGM_No_Tracking(self):
    with program() as self.quaPGM:
        self.simulation_flag = declare(bool)
        assign(self.simulation_flag, self.simulation)

        self.n = declare(int)  # iteration variable
        self.n_st = declare_stream()  # stream iteration number
        self.times = declare(int, size=100)
        self.times2 = declare(int, size=100)
        self.times_ref = declare(int, size=100)

        self.r = declare(fixed)
        self.ln_to_int = declare(fixed)
        self.assign_input = declare(fixed, size=10)

        self.f = declare(
            int)  # frequency variable which we change during scan - here f is according to calibration function
        self.t = declare(int)  # [cycles] time variable which we change during scan
        self.p = declare(fixed)  # [unit less] proportional amp factor which we change during scan

        self.m = declare(int)  # number of pumping iterations
        self.i_idx = declare(int)  # iteration variable
        self.j_idx = declare(int)  # iteration variable
        self.k_idx = declare(int)  # iteration variable
        self.offset = declare(int)  # variables used for iteration assignment
        self.pulse_type = declare(int)
        self.bool_condition = declare(bool)
        self.n_pause_qua = declare(int)

        self.site_state = declare(int)  # site preperation state
        self.m_state = declare(int)  # measure state

        self.counts_tmp = declare(int)  # temporary variable for number of counts
        self.counts_tmp2 = declare(int)  # temporary variable for number of counts
        self.counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
        self.counts_ref2_tmp = declare(int)  # 2nd temporary variable for number of counts reference

        self.runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        self.track_idx = declare(int, value=0)  # iteration variable
        self.tracking_signal_tmp = declare(int)  # tracking temporary variable
        self.tracking_signal = declare(int, value=0)  # tracking variable
        self.tracking_signal_st = declare_stream()  # tracking stream variable
        self.sequenceState = declare(int, value=0)  # IO1 variable

        self.counts = declare(int, size=self.vectorLength)  # experiment signal (vector)
        self.counts2 = declare(int, size=self.vectorLength)  # experiment signal (vector)
        self.resCalculated = declare(int, size=self.vectorLength)  # normalized values vector

        # Shuffle parameters
        # self.val_vec_qua = declare(fixed, value=self.p_vec_ini)    # volts QUA vector
        # self.f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        self.val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # volts QUA vector
        self.idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
        self.idx = declare(int)  # index variable to sweep over all indexes

        self.mod4 = declare(int)
        self.stat_pulse_type_qua = declare(fixed)
        self.tMWPiStat = declare(int)
        self.awg_freq_qua = declare(int)

        # Variables for output simulation
        self.time_of_distributed_simulation_value = declare(fixed)
        self.exp_a_simulated = declare(fixed)
        self.exp_b_simulated = declare(fixed)
        assign(self.exp_a_simulated, self.lower_simulation_bound)
        assign(self.exp_b_simulated, self.higher_simulation_bound)

        # Input stream
        # awg_freq_qua = declare_input_stream(fixed, name = 'awg_freq')

        # stream parameters
        self.counts_st = declare_stream()  # experiment signal
        self.times_st = declare_stream()  # times during experiment signal
        self.pulse_type_st = declare_stream()
        self.counts_st2 = declare_stream()  # experiment signal for the second detector
        self.counts_ref_st = declare_stream()  # reference signal
        self.counts_ref2_st = declare_stream()  # reference signal
        self.resCalculated_st = declare_stream()  # reference signal
        self.awg_st = declare_stream()

        # with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
        #     assign(self.counts_ref[self.idx], 0)
        self.n_avg = 30
        self.n_pause = 8
        assign(self.n_pause_qua, self.n_pause)
        assign(self.bool_condition, False)
        with for_(self.n, 0, self.n < self.n_avg, self.n + 1):  # AVG loop
            assign(self.mod4, ((self.n + 1) & 3))
            # reset vectors
            with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
                assign(self.counts[self.idx], 0)  # shuffle - assign new val from randon index
                assign(self.counts2[self.idx], 0)  # shuffle - assign new val from randon index
                assign(self.times[self.idx], 0)  # shuffle - assign new val from randon index

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(self.idx_vec_qua,
                                 self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(self.idx, 0, self.idx < self.array_length, self.idx + 1):  # loop over scan vector
                assign(self.sequenceState, IO1)
                with if_(self.sequenceState == 0):
                    update_frequency("MW", self.f)
                    # assign(self.awg_freq_qua, self.current_awg_freq)
                    # # pi pulse type for statistics measurement (X ot Y)
                    # with if_(self.mod4 == 0):
                    #     # Group of 4
                    #     assign(self.pulse_type, 4)
                    # with if_(self.mod4 == 3):
                    #     # Group of 3
                    #     assign(self.pulse_type, 3)
                    # with if_(self.mod4 == 2):
                    #     # Group of 2
                    #     assign(self.pulse_type, 2)
                    # with if_(self.mod4 == 1):
                    #     # Group of 1
                    #     assign(self.pulse_type, 1)
                    with if_((self.n - (self.n // self.n_pause_qua) * self.n_pause_qua) == 0):
                        pause()
                        self.execute_QUA()
                    with else_():
                        self.execute_QUA()

                with else_():
                    assign(self.tracking_signal, 0)
                    with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None, time_tagging.analog(self.times_ref,
                                                                                         self.time_in_multiples_cycle_time(
                                                                                             self.Tcounter),
                                                                                         self.tracking_signal_tmp))
                        assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(self.runTracking):
                assign(self.track_idx, self.track_idx + 1)  # step up tracking counter
                with if_(self.track_idx > self.trackingNumRepeatition - 1):
                    assign(self.tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                        play("Turn_ON", "Laser",
                             duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None, time_tagging.analog(self.times_ref,
                                                                                         self.time_in_multiples_cycle_time(
                                                                                             self.Tcounter),
                                                                                         self.tracking_signal_tmp))
                        assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                    assign(self.track_idx, 0)

            # stream
            with if_(self.sequenceState == 0):
                with for_(self.idx, 0, self.idx < self.vectorLength,
                          self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(self.counts[self.idx], self.counts_st)
                    save(self.counts2[self.idx], self.counts_st2)
                with for_(self.idx, 0, self.idx < self.counts[0], self.idx + 1):
                    save(self.times[self.idx], self.times_st)
            save(self.n, self.n_st)  # save number of iteration inside for_loop
            save(self.tracking_signal, self.tracking_signal_st)  # save number of iteration inside for_loop
            save(self.pulse_type, self.pulse_type_st)
            # save(self.awg_freq_qua,self.awg_st)

        with stream_processing():
            # It makes sense to use save instead of save_all since stream_processing work parallel to sequence
            self.n_st.save_all("iteration_list")
            self.times_st.save_all("times")
            self.counts_st.save_all("counts")
            self.counts_st2.save_all("statistics_counts")
            self.pulse_type_st.save_all("pulse_type")
            # self.awg_st.save_all("awg_freq")
            # self.times_st.histogram([[i, i + 1] for i in range(0, self.tMeasure)]).save("times_hist")
    if not self.simulation:
        self.qm, self.job = self.QUA_execute()
    elif self.simulation and self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        self.qm, self.job = self.QUA_execute()
    # self.change_AWG_freq(channel=1)
    # self.job.resume()

def execute_QUA(self):
    if self.exp == Experiment.NUCLEAR_POL_ESR:
        self.Nuclear_Pol_ESR_QUA_PGM(Generate_QUA_sequance=True)
    if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
        self.Population_gate_tomography_QUA_PGM(Generate_QUA_sequance=True)
    if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
        self.Entanglement_gate_tomography_QUA_PGM(Generate_QUA_sequance=True)
    if self.exp == Experiment.testCrap:
        self.Test_Crap_QUA_PGM(Generate_QUA_sequance=True)
    # if self.exp == Experiment.RandomBenchmark:
    #     self.Random_Benchmark_QUA_PGM(Generate_QUA_sequance = True)

def QUA_measure_with_sum_counters(self, detector1: str, detector2: Optional[str], time_vector: QuaVariableType,
                                  measure_time: int, counts: QuaVariableType, total_counts: QuaVariableType,
                                  counts2: Optional[QuaVariableType] = None, measure_waveform: str = "min_readout",
                                  sum_counters: bool = False):
    """
       Perform a QUA measurement and optionally sum counters, using either digital or analog tagging.

       :param detector1: The primary detector name.
       :param detector2: The secondary detector name for summed measurements.
       :param time_vector: The QUA time vector.
       :param measure_time: Duration of the measurement.
       :param counts: The counter variable for the primary detector.
       :param total_counts: The variable holding the accumulated count.
       :param counts2: The counter variable for the secondary detector (if any).
       :param measure_waveform: The measurement waveform identifier.
       :param measure_type: The type of measurement (digital or analog).
       :param sum_counters: Whether to perform and sum a secondary counter measurement.
       :return: The updated total_counts variable.
       """

    # Measure with the primary detector
    measure(measure_waveform, detector1, None, self.time_tagging_fn(time_vector, measure_time, counts))

    # Measure with the secondary detector and add counts if requested
    if sum_counters:
        measure(measure_waveform, detector2, None, self.time_tagging_fn(time_vector, measure_time, counts2))
        assign(total_counts, total_counts + counts2)

    assign(total_counts, total_counts + counts)
    return total_counts


def tile_to_length(self, array, final_length):
    """
       Return a 1D array of exactly 'final_length' by repeating 'array'
       as many times as needed (and possibly truncating the last repetition).
       """
    if final_length <= 0:
        # Return empty array if final_length is not positive
        return np.array([], dtype=array.dtype)

    array_len = len(array)
    # Number of complete repeats
    num_full_repeats = final_length // array_len
    # Remaining elements needed for the partial repeat
    remainder = final_length % array_len

    # Repeat fully num_full_repeats times, then take the first 'remainder' elements
    repeated = np.concatenate([
        np.tile(array, num_full_repeats),
        array[:remainder]
    ])

    return repeated

# def play_random_qua_gate(self, N_vec, t_RF, amp_RF):
#     with switch_(N_vec[self.n_m]):
#         with case_(0):
#             #Identity
#             pass
#         with case_(1):
#             #X gate
#             play("const" * amp(amp_RF), "RF", duration=(t_RF))
#             assign(self.total_rf_wait, self.total_rf_wait + t_RF)
#         with case_(2):
#             #Y gate
#             frame_rotation_2pi(0.25, "RF")
#             play("const" * amp(amp_RF), "RF", duration=(2*t_RF))
#             frame_rotation_2pi(1 - 0.25, "RF")
#             assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
#
# def play_random_reverse_qua_gate(self, N_vec_reversed, t_RF, amp_RF):
#     with switch_(N_vec_reversed[self.n_m]):
#         with case_(0):
#             #Identity
#             pass
#         with case_(1):
#             #X gate
#             play("const" * amp(amp_RF), "RF", duration=(t_RF))
#             assign(self.total_rf_wait, self.total_rf_wait + t_RF)
#         with case_(2):
#             #Y gate
#             frame_rotation_2pi(1 - 0.25, "RF")
#             play("const" * amp(amp_RF), "RF", duration=(2*t_RF))
#             frame_rotation_2pi(0.25, "RF")
#             assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
def play_random_qua_gate(self, N_vec, t_RF, amp_RF):
    # Both amp_RF and t_RF are python variables
    with switch_(N_vec[self.n_m]):
        with case_(0):
            # Identity
            pass
        with case_(1):
            # X +pi/2 gate
            # X(pi/2)
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(2):
            # Y +pi/2 gate
            # Z(-pi/2)X(pi/2)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(3):
            # Z +pi/2 gate
            # Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
        with case_(4):
            # X -pi/2 gate
            # X(-pi/2)
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(5):
            # Y -pi/2 gate
            # Z(-pi/2)X(-pi/2)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(6):
            # Z -pi/2 gate
            # Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
        with case_(7):
            # X +pi gate
            # X(pi)
            play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(8):
            # Y +pi gate
            # Z(-pi/2)X(pi)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(9):
            # Z pi gate
            # Z(pi)
            frame_rotation_2pi(0.5, "RF")
        with case_(10):
            # 0X+Y+Z pi gate
            # Z(pi)X(pi/2)
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(11):
            # +X0Y+Z pi gate
            # Z(pi/2)X(pi/2)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(12):
            # +X+Y0Z pi gate
            # Z(pi/4)X(pi)Z(-pi/4)
            frame_rotation_2pi(1 - 0.125, "RF")
            play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(0.125, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(13):
            # 0X+Y-Z pi gate
            # X(pi/2)Z(-pi)
            frame_rotation_2pi(1 - 0.5, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(14):
            # -X0Y+Z pi gate
            # Z(3pi/2)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.75, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(15):
            # +X-Y0Z pi gate
            # Z(-pi/4)X(pi)Z(pi/4)
            frame_rotation_2pi(0.125, "RF")
            play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(1 - 0.125, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(16):
            # +X+Y+Z +pi*2/3 gate
            # Z(pi/2)X(pi/2)Z(0)
            # frame_rotation_2pi(0.125, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(17):
            # +X+Y+Z -pi*2/3 gate
            # Z(0)X(-pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(18):
            # -X+Y+Z +pi*2/3 gate
            # Z(pi)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(19):
            # -X+Y+Z -pi*2/3 gate
            # Z(pi/2)X(-pi/2)Z(-pi)
            frame_rotation_2pi(1 - 0.5, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(20):
            # +X-Y+Z +pi*2/3 gate
            # Z(0)X(pi/2)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(21):
            # +X-Y+Z -pi*2/3 gate
            # Z(-pi/2)X(-pi/2)Z(0)
            # frame_rotation_2pi(0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(22):
            # +X+Y-Z +pi*2/3 gate
            # Z(0)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(23):
            # +X+Y-Z -pi*2/3 gate
            # Z(pi/2)X(-pi/2)Z(0)
            # frame_rotation_2pi(1-0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)

def play_random_reverse_qua_gate(self, N_vec, t_RF, amp_RF):
    # Both amp_RF and t_RF are python variables
    with switch_(N_vec[self.n_m]):
        with case_(0):
            # Identity
            pass
        with case_(1):
            # X pi/2 gate
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(2):
            # Y pi/2 gate
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(3):
            # Z pi/2 gate
            frame_rotation_2pi(1 - 0.25, "RF")
        with case_(4):
            # X -pi/2 gate
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(5):
            # Y -pi/2 gate
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(6):
            # Z -pi/2 gate
            frame_rotation_2pi(0.25, "RF")
        with case_(7):
            # X +pi gate
            play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(8):
            # Y +pi gate
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(9):
            # Z pi gate
            frame_rotation_2pi(1 - 0.5, "RF")
        with case_(10):
            # 0X+Y+Z pi gate
            frame_rotation_2pi(1 - 0.5, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(11):
            # +X0Y+Z pi gate
            # Z(pi/2)X(pi/2)Z(pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(12):
            # +X+Y0Z pi gate
            # Z(pi/4)X(pi)Z(-pi/4)
            frame_rotation_2pi(0.125, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(1 - 0.125, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(13):
            # 0X+Y-Z pi gate
            # X(pi/2)Z(-pi)
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(14):
            # -X0Y+Z pi gate
            # Z(3pi/2)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.75, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(15):
            # +X-Y0Z pi gate
            # Z(-pi/4)X(pi)Z(pi/4)
            frame_rotation_2pi(0.125, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
            frame_rotation_2pi(1 - 0.125, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
        with case_(17):  # 16 & 17 are the inverse of each other
            # +X+Y+Z +pi*2/3 gate
            # Z(pi/2)X(pi/2)Z(0)
            # frame_rotation_2pi(0.125, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(16):
            # +X+Y+Z -pi*2/3 gate
            # Z(0)X(-pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(19):  # 18 & 19 are the inverse of each other
            # -X+Y+Z +pi*2/3 gate
            # Z(pi)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(18):
            # -X+Y+Z -pi*2/3 gate
            # Z(pi/2)X(-pi/2)Z(-pi)
            frame_rotation_2pi(1 - 0.5, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(21):  # 20 & 21 are the inverse of each other
            # +X-Y+Z +pi*2/3 gate
            # Z(0)X(pi/2)Z(pi/2)
            frame_rotation_2pi(0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(20):
            # +X-Y+Z -pi*2/3 gate
            # Z(-pi/2)X(-pi/2)Z(0)
            # frame_rotation_2pi(0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(1 - 0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(23):  # 22 & 23 are the inverse of each other
            # +X+Y-Z +pi*2/3 gate
            # Z(0)X(pi/2)Z(-pi/2)
            frame_rotation_2pi(1 - 0.25, "RF")
            play("const" * amp(amp_RF), "RF", duration=(t_RF))
            # frame_rotation_2pi(0.5, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)
        with case_(22):
            # +X+Y-Z -pi*2/3 gate
            # Z(pi/2)X(-pi/2)Z(0)
            # frame_rotation_2pi(1-0.25, "RF")
            play("const" * amp(-amp_RF), "RF", duration=(t_RF))
            frame_rotation_2pi(0.25, "RF")
            assign(self.total_rf_wait, self.total_rf_wait + t_RF)


def play_random_qua_two_qubit_gate(self, N_vec, t_MW1, amp_MW1, t_MW2, amp_MW2, t_MW3, amp_MW3, f_mw1, f_mw2, back_freq,
                                   keep_phase=False):
    with switch_(N_vec[self.n_m]):
        with case_(0):
            # C_{n}NOT_{e}
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(1):
            # IC_{n}NOT_{e}
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(2):
            # C_{n}H_{y_e}
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(3):
            # IC_{n}H_{y_e}
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(4):
            # C_{n}H_{x_e}
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(5):
            # IC_{n}H_{x_e}
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(6):
            # Add to reference
            # HCH_{n}H_{y_e}
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(7):
            # HCH_{n}IH_{y_e}
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(8):
            # HCH_{n}H_{x_e}
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(9):
            # HCH_{n}IH_{x_e}
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)


def play_random_reverse_qua_two_qubit_gate(self, N_vec, t_MW1, amp_MW1, t_MW2, amp_MW2, t_MW3, amp_MW3, f_mw1, f_mw2,
                                           back_freq, keep_phase=False):
    with switch_(N_vec[self.n_m]):
        with case_(0):
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(1):
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(2):
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(3):
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(4):
            update_frequency("MW", f_mw1, keep_phase=keep_phase)
            play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(5):
            update_frequency("MW", f_mw2, keep_phase=keep_phase)
            play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(6):
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(7):
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(8):
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)
        with case_(9):
            update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase=keep_phase)
            play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
            assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
            update_frequency("MW", back_freq, keep_phase=keep_phase)

def benchmark_play_list_of_gates(self, N_vec, N_vec_reversed, n, idx):
    assign(self.total_rf_wait, 4)
    with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
        # Gates
        self.play_random_qua_gate(N_vec=N_vec, t_RF=self.tRF, amp_RF=self.rf_proportional_pwr)
    with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
        # Inverse Gates
        self.play_random_reverse_qua_gate(N_vec=N_vec_reversed, t_RF=self.tRF, amp_RF=-self.rf_proportional_pwr)

def benchmark_play_list_of_two_qubit_gates(self, N_vec, N_vec_reversed, n, idx, keep_phase):
    assign(self.total_mw_wait, 4)
    with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
        self.play_random_qua_two_qubit_gate(N_vec=N_vec, t_MW1=(self.t_mw / 1), amp_MW1=self.mw_P_amp,
                                            t_MW2=(self.t_mw2 / 1), amp_MW2=self.mw_P_amp2, t_MW3=(self.t_mw3 / 1),
                                            amp_MW3=self.mw_P_amp3, f_mw1=self.fMW_res, f_mw2=self.fMW_2nd_res,
                                            back_freq=self.fMW_back_freq, keep_phase=keep_phase)
    with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
        self.play_random_reverse_qua_two_qubit_gate(N_vec=N_vec_reversed, t_MW1=(self.t_mw / 1), amp_MW1=self.mw_P_amp,
                                                    t_MW2=(self.t_mw2 / 1), amp_MW2=self.mw_P_amp2,
                                                    t_MW3=(self.t_mw3 / 1), amp_MW3=self.mw_P_amp3, f_mw1=self.fMW_res,
                                                    f_mw2=self.fMW_2nd_res, back_freq=self.fMW_back_freq,
                                                    keep_phase=keep_phase)

def create_random_qua_vector(self, jdx, vec_size, max_rand, n):
    random_qua = Random()
    random_qua.set_seed(n)
    with for_(jdx, 0, jdx < vec_size, jdx + 1):
        assign(self.idx_vec_ini_shaffle_qua[jdx], random_qua.rand_int(max_rand))
        save(self.idx_vec_ini_shaffle_qua[jdx], self.number_order_st)

def create_non_random_qua_vector(self, jdx, vec_size, max_rand, n):
    assign(self.one_gate_only_values_qua, self.gate_number)
    with for_(jdx, 0, jdx < vec_size, jdx + 1):
        assign(self.idx_vec_ini_shaffle_qua[jdx], self.one_gate_only_values_qua)
        save(self.idx_vec_ini_shaffle_qua[jdx], self.number_order_st)

def generate_random_qua_integer_benchmark(self, rand_val, number_of_gates):
    """Generates a random integer from 0 to 23 in QUA"""
    assign(rand_val, Random().rand_int(number_of_gates))

def reverse_qua_vector(self, idx, jdx):
    with for_(jdx, 0, jdx < idx, jdx + 1):
        with if_(jdx == 0):
            assign(self.idx_vec_ini_shaffle_qua_reversed[jdx], self.idx_vec_ini_shaffle_qua[idx - 1])
        with else_():
            assign(self.temp_idx, idx - jdx - 1)
            assign(self.idx_vec_ini_shaffle_qua_reversed[jdx], self.idx_vec_ini_shaffle_qua[self.temp_idx])

def benchmark_state_preparation(self, m, Npump, tPump, t_wait, final_state_qua, t_rf_extra=0, keep_phase=False):
    # pumping
    # The values are written in python and processed to QUA in QUA_PUMP function
    # self.fMW_res is defined in random_benchmark
    align()
    with for_(m, 0, m < Npump, m + 1):
        play("Turn_ON", "Laser", duration=tPump // 4)

    with switch_(final_state_qua):
        with case_(0):
            """qubit = |0e>|0n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=(self.rf_pulse_time + t_rf_extra),  # 2
                          f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|0n>
            pass
        with case_(1):
            """qubit = |1e>|0n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=(self.rf_pulse_time + t_rf_extra),  # 2
                          f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|0n>
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)  # MIC: @Daniel!! add self.keep_phase
        with case_(2):
            """qubit = |0e>|1n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=(self.rf_pulse_time + t_rf_extra),  # 2
                          f_mw=self.fMW_2nd_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|1n>
            pass
        with case_(3):
            """qubit = |1e>|1n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=(self.rf_pulse_time + t_rf_extra),  # 2
                          f_mw=self.fMW_2nd_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|1n>
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)  # MIC: @Daniel!! add self.keep_phase
        with case_(4):
            """qubit = |0e>|0n>-i|1e>|1n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
                          f_mw=self.fMW_2nd_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|1n>
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
            align("MW", "RF")
            play("const" * amp(self.rf_proportional_pwr), "RF", duration=((self.rf_pulse_time + t_rf_extra) >> 1) >> 2)
            wait(t_wait)
            # qubit = |1e>|-in>
            align("RF", "MW")
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |0e>|0n>-i|1e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
        with case_(5):
            """qubit = |0e>|0n>+i|1e>|1n> 2nd way"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
                          f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|0n>
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
            align("MW", "RF")
            play("const" * amp(self.rf_proportional_pwr), "RF", duration=((self.rf_pulse_time + t_rf_extra) >> 1) >> 2)
            wait(t_wait)
            # qubit = |1e>|in>
            align("RF", "MW")
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)
            # update_frequency("MW", self.fMW_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |0e>|0n>+i|1e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
        with case_(6):
            """qubit = |1e>|0n><1e|<0n|+|0e>|1n><0e|<1n|"""
            # self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
            #              f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
            #              p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>(|0n><0n|+|1n><1n|)
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n><1e|<0n|+|0e>|1n><0e|<1n|
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)  # MIC: @Daniel!! add self.keep_phase
        with case_(7):
            """qubit = |0e>(|0n><0n|+|1n>|<1n|)"""
            # self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
            #              f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
            #              p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>(|0n><0n|+|1n><1n|)
        with case_(8):
            """qubit = |1e>(|0n><0n|+|1n>|<1n|)"""
            # self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
            #              f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
            #              p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>(|0n><0n|+|1n><1n|)
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_2nd_res)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n><1e|<0n|+|0e>|1n><0e|<1n|
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>(|0n><0n|+|1n>|<1n|)
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
        with case_(9):
            """qubit = |1e>(|0n><0n|+|1n>|<1n|) - same as 8, but changing fMW order"""
            # self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
            #              f_mw=self.fMW_res, f_rf=self.rf_resonance_freq * self.u.MHz,
            #              p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>(|0n><0n|+|1n><1n|)
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n><1e|<0n|+|0e>|1n><0e|<1n|
            update_frequency("MW", self.fMW_2nd_res, keep_phase=keep_phase)  # @Daniel!! add self.keep_phase
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>(|0n><0n|+|1n>|<1n|)
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
        with case_(10):
            """qubit = |1e>|0n>-i|0e>|1n>"""
            self.QUA_Pump(t_pump=tPump, t_mw=self.t_mw, t_rf=self.rf_pulse_time + t_rf_extra,  # 2
                          f_mw=self.fMW_2nd_res, f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=t_wait)
            align()
            # qubit = |0e>|1n>
            # set MW frequency to second resonance frequency
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
            align("MW", "RF")
            play("const" * amp(self.rf_proportional_pwr), "RF", duration=((self.rf_pulse_time + t_rf_extra) >> 1) >> 2)
            wait(t_wait)
            # qubit = |1e>|-in>
            align("RF", "MW")
            update_frequency("MW", self.fMW_res, keep_phase=keep_phase)
            # play MW
            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
            # qubit = |1e>|0n>-i|0e>|1n>
            update_frequency("MW", self.fMW_back_freq, keep_phase=keep_phase)
    align()

def benchmark_state_readout(self, current_counts_, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure):
    """Make sure to have align with laser before"""
    align()
    play("Turn_ON", "Laser", duration=tLaser // 4)
    """measure signal"""
    # align("MW", "Detector_OPD") ## MIC: @daniel - why align with MW? I think we should align laser and OPD before turning on laser
    measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
    assign(current_counts_[idx_vec_qua[idx]], current_counts_[idx_vec_qua[idx]] + counts_tmp)

def Random_Benchmark_QUA_PGM(self):
    # sequence parameters
    is_new_benchmark_code = True
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    self.tMW = self.t_mw
    self.fMW_res = (self.mw_freq_resonance - self.mw_freq_resonance) * self.u.GHz
    self.verify_insideQUA_FreqValues(self.fMW_res)
    fMW_res1 = self.fMW_res
    self.fMW_1st_res = self.fMW_res
    self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq_resonance) * self.u.GHz
    self.fMW_back_freq = (self.back_freq - self.mw_freq_resonance) * self.u.GHz
    self.verify_insideQUA_FreqValues(self.fMW_2nd_res)
    fMW_res2 = self.fMW_2nd_res

    if self.benchmark_switch_flag:
        number_of_gates = 10
    else:
        number_of_gates = 24

    self.tRF = self.rf_pulse_time // 4  # why is it divided by 4? in """def NuclearRABI_QUA_PGM""" it is without the 4
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = 0  # in [cycles]
    tScan_max = self.n_measure  # in [cycles]
    t_wait = self.time_in_multiples_cycle_time(self.Twait * 1000) // 4
    self.tWait = t_wait
    # self.dN = 10  # in [cycles]
    self.t_vec = [i * 1 for i in range(tScan_min, tScan_max, self.dN)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + self.dN, self.dN)  # in [cycles]

    # length and idx vector
    array_length = self.n_measure
    # array_length = len(self.f_vec)                      # frquencies vector size
    gate_vector = np.arange(0, number_of_gates)
    idx_vec_ini = np.arange(0, array_length + 1, 1)  # indexes vector
    idx_vec_ini_shaffle = self.tile_to_length(gate_vector, array_length)
    # idx_vec_ini_shaffle = np.ones(self.n_measure)

    # tracking signal
    # tSequencePeriod = ((tMW + self.tRF + tPump) * Npump + 2 * tMW + self.tRF + tScan_max / 2 + tLaser) * array_length * 2
    tSequencePeriod = (2 * self.tRF * np.sum(self.t_vec) + np.size(self.t_vec) * (
                (tPump + self.tRF * 2 + self.t_mw) + self.t_mw2 + self.t_mw2 + tLaser)) * 3
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        final_state_qua = declare(int)
        assign(final_state_qua, 1)
        times_ref = declare(int, size=100)
        self.reverse_rf_amp = declare(int)
        self.temp_idx = declare(int)
        self.one_gate_only_values_qua = declare(int)

        self.tRF_qua = declare(int)
        self.t_RF_extra_qua = declare(int)
        self.t_mw_qua = declare(int)
        assign(self.t_mw_qua, (self.t_mw / 2) // 4)
        self.t_mw_qua2 = declare(int)
        assign(self.t_mw_qua2, (self.t_mw2 / 2) // 4)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan
        self.total_rf_wait = declare(int)
        self.total_mw_wait = declare(int)

        n = declare(int)  # iteration variable
        self.n_m = declare(int)
        m = declare(int)  # number of pumping iterations
        self.m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number
        self.Npump = self.n_nuc_pump

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_tmp_squared = declare(int)
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
        counts_loop_size = array_length // self.dN

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)
        counts_ref2 = declare(int, size=array_length)
        counts_ref3 = declare(int, size=array_length)
        counts_square = declare(int, size=array_length)
        idx_counts_qua = declare(int)

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        self.idx_vec_ini_shaffle_qua = declare(int, value=idx_vec_ini_shaffle)
        self.idx_vec_ini_shaffle_qua_reversed = declare(int, value=idx_vec_ini_shaffle)
        # self.idx_vec_ini_shaffle_qua = declare(int, value=self.n_measure)
        # self.idx_vec_ini_shaffle_qua_reversed = declare(int, value=self.n_measure)
        idx = declare(int)  # index variable to sweep over all indexes
        jdx = declare(int)
        self.wait_ref = declare(int)

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal
        counts_ref_st2 = declare_stream()  # reference signal
        counts_ref_st3 = declare_stream()  # reference signal
        self.number_order_st = declare_stream()
        self.reverse_number_order_st = declare_stream()
        self.counts_square_st = declare_stream()

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        """Starting the (Nearly Infinite) Measurement Loop"""

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + self.dN):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index
                assign(counts_ref2[idx], 0)
                assign(counts_square[idx], 0)
                assign(counts_ref3[idx], 0)

            """Create qua vector containing gates order of playing of size vec_size.
               Depending on the condition(checkbox) It is either: 
               1. randomly filled with numbers till max_rand
               2. Filled with the same number (chosen in the config) till vec_size"""
            if self.benchmark_one_gate_only:
                self.create_non_random_qua_vector(jdx=jdx, vec_size=array_length, max_rand=number_of_gates, n=n)
            else:
                self.create_random_qua_vector(jdx=jdx, vec_size=array_length, max_rand=number_of_gates, n=n)

            # sequence
            with for_(idx, 0, idx < array_length, idx + self.dN):
                assign(sequenceState, IO1)
                assign(self.tRF_qua, (self.tRF))
                if self.benchmark_switch_flag:
                    assign(self.t_RF_extra_qua, 0)
                else:
                    assign(self.t_RF_extra_qua, 0)
                    pass
                    # assign(self.t_RF_extra_qua, (idx-array_length/2)*self.scan_t_dt)
                """Creates a vector of reversed gates for each iteration of idx"""
                self.reverse_qua_vector(idx=idx, jdx=jdx)
                assign(self.total_rf_wait, 4)
                assign(self.total_mw_wait, 4)
                with if_(sequenceState == 0):
                    """ Experiment start """

                    if is_new_benchmark_code:
                        """signal 1 - gates + measure as is (|00><00|+|01><01|)"""
                        """signal 1 state preparation part"""
                        assign(final_state_qua, 10)
                        self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                                                         final_state_qua=final_state_qua, t_rf_extra=0,
                                                         keep_phase=False)
                        self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                    self.idx_vec_ini_shaffle_qua_reversed, n, idx,
                                                                    keep_phase=False)
                        # play Laser
                        self.benchmark_state_readout(counts, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure)
                        # assign(counts_tmp_squared, counts_tmp * counts_tmp)
                        # assign(counts_square[idx_vec_qua[idx]], counts_square[idx_vec_qua[idx]] + counts_tmp_squared)
                        align()

                        """reference 1 - (signal 2) - gates + measure |00><00| + |1(-i)><1(-i)|"""
                        assign(final_state_qua, 10)
                        self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                                                         final_state_qua=final_state_qua, t_rf_extra=0,
                                                         keep_phase=False)
                        # wait(idx * (self.t_mw//4) + 4)
                        self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                    self.idx_vec_ini_shaffle_qua_reversed, n, idx,
                                                                    keep_phase=False)
                        if False:
                            update_frequency("MW", self.fMW_res, keep_phase=False)
                            # play MW
                            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
                            # qubit = |1e>|0n><1e|<0n|+|0e>|1n><0e|<1n|
                            update_frequency("MW", self.fMW_2nd_res,
                                             keep_phase=False)  # @Daniel!! add self.keep_phase
                            # play MW
                            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua)
                            # qubit = |1e>(|0n><0n|+|1n>|<1n|)
                            update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                        else:
                            update_frequency("MW", self.fMW_res, keep_phase=False)
                            # play MW
                            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse",
                                                        second_pulse="xPulse")
                            update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                            align()
                            # frame_rotation_2pi(0.25, "RF")
                            play("const" * amp(-self.rf_proportional_pwr), "RF",
                                 duration=((self.rf_pulse_time + 0) >> 1) >> 2)
                            wait(t_wait)
                            align()
                            update_frequency("MW", self.fMW_res, keep_phase=False)
                            # play MW
                            self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse",
                                                        second_pulse="xPulse")
                            update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                        # play Laser
                        self.benchmark_state_readout(counts_ref, counts_tmp, tLaser, idx_vec_qua, idx, times,
                                                     tMeasure)
                        align()

                        """reference 4 (y^2)  - gates + measure |00><00| + |11><11|"""
                        assign(final_state_qua, 10)
                        self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                                                         final_state_qua=final_state_qua, t_rf_extra=0,
                                                         keep_phase=False)
                        self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                    self.idx_vec_ini_shaffle_qua_reversed, n,
                                                                    idx,
                                                                    keep_phase=False)
                        update_frequency("MW", self.fMW_res, keep_phase=False)
                        # play MW
                        self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua,
                                                    first_pulse="-xPulse", second_pulse="xPulse")
                        update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                        align()
                        play("const" * amp(-self.rf_proportional_pwr), "RF",
                             duration=((self.rf_pulse_time + 0) >> 1) >> 2)
                        wait(t_wait)
                        align()
                        # wait(4)
                        # play Laser
                        self.benchmark_state_readout(counts_square, counts_tmp, tLaser, idx_vec_qua, idx, times,
                                                     tMeasure)
                        align()

                        """reference 2 - waiting without gates + measure |00><00| + |01><01|"""
                        assign(final_state_qua, 10)
                        self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                                                         final_state_qua=final_state_qua, t_rf_extra=0,
                                                         keep_phase=False)
                        # self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                        #                                 final_state_qua=final_state_qua, t_rf_extra = self.t_RF_extra_qua, keep_phase = False)
                        wait(self.total_mw_wait)
                        # play Laser
                        self.benchmark_state_readout(counts_ref2, counts_tmp, tLaser, idx_vec_qua, idx, times,
                                                     tMeasure)
                        align()

                        """reference 3 - waiting without gates + measure |00><00| + |1(-i)><1(-i)|"""
                        assign(final_state_qua, 10)
                        self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait,
                                                         final_state_qua=final_state_qua, t_rf_extra=0,
                                                         keep_phase=False)
                        wait(self.total_mw_wait)
                        # wait(idx * (self.t_mw // 4) + 4)
                        update_frequency("MW", self.fMW_res, keep_phase=False)
                        # play MW
                        self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse",
                                                    second_pulse="xPulse")
                        update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                        align()
                        # frame_rotation_2pi(0.25, "RF")
                        play("const" * amp(-self.rf_proportional_pwr), "RF",
                             duration=((self.rf_pulse_time + 0) >> 1) >> 2)
                        wait(t_wait)
                        align()
                        update_frequency("MW", self.fMW_res, keep_phase=False)
                        # play MW
                        self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse",
                                                    second_pulse="xPulse")
                        update_frequency("MW", self.fMW_back_freq, keep_phase=False)
                        # play Laser
                        self.benchmark_state_readout(counts_ref3, counts_tmp, tLaser, idx_vec_qua, idx, times,
                                                     tMeasure)
                        align()

                    else:
                        """old benchmark code"""
                        """signal 1 state preparation part"""
                        # MIC: @Daniel add set(self.keep_phase,False)
                        # self.benchmark_state_preparation(m = m, Npump = Npump, tPump = tPump, t_wait = t_wait, final_state_qua = final_state_qua)
                        # """qubit = |0n>|1e>"""
                        self.QUA_prepare_state(4)
                        """qubit = |+n>|1e>"""

                        """signal 1 - manipulation part"""
                        align("MW", "RF")
                        if self.benchmark_switch_flag:  # 2 qubit
                            play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |+n>|1e>
                            align("RF", "MW")
                            wait(t_wait)
                            self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                        self.idx_vec_ini_shaffle_qua_reversed, n, idx,
                                                                        keep_phase=False)
                            align("MW", "RF")
                            # qubit = |+n>|1e>
                            play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |0n>|1e>
                        else:  # 1 qubit
                            self.benchmark_play_list_of_gates(self.idx_vec_ini_shaffle_qua,
                                                              self.idx_vec_ini_shaffle_qua_reversed, n, idx)
                            # qubit = |0n>|1e>

                        """signal 1 measurement part"""
                        wait(t_wait)
                        align("RF", "MW")
                        ##update_frequency("MW", self.fMW_res, keep_phase=False)  # @Daniel!! add self.keep_phase
                        ##self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse", second_pulse="xPulse")
                        # update_frequency("MW", self.fMW_2nd_res, keep_phase = False)  # @Daniel!! add self.keep_phase
                        # self.MW_and_reverse_general(p_mw = self.mw_P_amp,t_mw = self.t_mw_qua, first_pulse = "-xPulse", second_pulse = "xPulse")
                        update_frequency("MW", self.fMW_back_freq, keep_phase=False)  # @Daniel!! add self.keep_phase
                        # qubit = |0n>|0e>

                        # play Laser
                        align("MW", "Laser")
                        self.QUA_measure(m_state=2, idx=idx, tLaser=tLaser, tMeasure=tMeasure, t_rf=self.tRF,
                                         t_mw=self.t_mw, t_mw2=self.t_mw2, p_rf=self.rf_proportional_pwr)
                        self.benchmark_state_readout(counts, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure)
                        assign(counts_tmp_squared,
                               counts_tmp * counts_tmp)  # MIC: @Daniel - does count_tmp updated outside of readout by readout?
                        assign(counts_square[idx_vec_qua[idx]], counts_square[idx_vec_qua[idx]] + counts_tmp_squared)
                        align()

                        """reference 1 - (signal 2) - same as signal 1 but self.keep_phase = True"""
                        # MIC: @Daniel add set(self.keep_phase,True)
                        # self.benchmark_state_preparation(m = m, Npump = Npump, tPump = tPump, t_wait = t_wait, final_state_qua = final_state_qua, keep_phase = False)
                        # """qubit = |0n>|1e>"""
                        self.QUA_prepare_state(4)
                        """qubit = |+n>|1e>"""

                        """signal 2 - manipulation part"""
                        align("MW", "RF")
                        if self.benchmark_switch_flag:  # 2 qubit
                            # play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            """qubit = |+n>|1e>"""
                            align("RF", "MW")
                            wait(t_wait)
                            with if_((idx == 0)):  # no gates
                                wait(duration=4)
                            with else_():
                                # making ref1 to end at the excited state
                                self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                            self.idx_vec_ini_shaffle_qua_reversed, n,
                                                                            idx, keep_phase=False)
                            align("MW", "RF")
                            # play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            """qubit = |0n>|1e>"""
                        else:  # 1 qubit
                            with if_((idx == 0)):  # no gates
                                pass
                            with else_():  # idx gates
                                wait(self.total_rf_wait)

                        """measurement signal 2 (reference 1)"""
                        wait(t_wait)
                        align("RF", "MW")
                        ##update_frequency("MW", self.fMW_res, keep_phase=True)  # @Daniel!! add self.keep_phase
                        ##self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse", second_pulse="xPulse")
                        # update_frequency("MW", self.fMW_2nd_res, keep_phase=True)  # @Daniel!! add self.keep_phase
                        # self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse", second_pulse="xPulse")
                        update_frequency("MW", self.fMW_back_freq, keep_phase=False)  # @Daniel!! add self.keep_phase
                        # qubit = |0n>|0e>

                        # play Laser
                        align("MW", "Laser")
                        self.QUA_measure(m_state=16, idx=idx, tLaser=tLaser, tMeasure=tMeasure, t_rf=self.tRF,
                                         t_mw=self.t_mw, t_mw2=self.t_mw2, p_rf=self.rf_proportional_pwr)
                        self.benchmark_state_readout(counts_ref, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure)
                        align()

                        """reference 2 - waiting without gates - and measuring as |0n>|0e>"""
                        # self.benchmark_state_preparation(m = m, Npump = Npump, tPump = tPump, t_wait = t_wait, final_state_qua = final_state_qua)
                        # """qubit = |0n>|1e>"""
                        self.QUA_prepare_state(4)
                        """qubit = |+n>|1e>"""

                        """reference 2 - manipulation part"""
                        align("MW", "RF")
                        if self.benchmark_switch_flag:  # 2 qubit
                            # play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |+n>|1e>
                            wait(t_wait)
                            with if_((idx == 0)):
                                wait(duration=4)
                                # qubit = |0n>|1e>
                            with else_():  # idx gates
                                wait(self.total_mw_wait)
                            align("MW", "RF")
                            # qubit = |+n>|1e>
                            # play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |0n>|1e>
                        else:  # 1 qubit
                            play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |+n>|1e>
                            with if_((idx == 0)):
                                pass
                            with else_():  # idx gates
                                wait(self.total_rf_wait)
                            play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |0n>|1e>

                        """measurment reference 2"""
                        wait(t_wait)
                        align("RF", "MW")
                        ##update_frequency("MW", self.fMW_res)  # @Daniel!! add self.keep_phase
                        ##self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse", second_pulse="xPulse")
                        # update_frequency("MW", self.fMW_2nd_res)  # @Daniel!! add self.keep_phase
                        # self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="-xPulse", second_pulse="xPulse")
                        update_frequency("MW", self.fMW_back_freq)  # @Daniel!! add self.keep_phase
                        # qubit = |0n>|0e>

                        # play Laser
                        align("MW", "Laser")
                        self.QUA_measure(m_state=17, idx=idx, tLaser=tLaser, tMeasure=tMeasure, t_rf=self.tRF,
                                         t_mw=self.t_mw, t_mw2=self.t_mw2, p_rf=self.rf_proportional_pwr)
                        self.benchmark_state_readout(counts_ref2, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure)
                        align()

                        """reference 3 - waiting without gates - and measuring as |0n>|1e>"""
                        # self.benchmark_state_preparation(m=m, Npump=Npump, tPump=tPump, t_wait=t_wait, final_state_qua = final_state_qua)
                        # """qubit = |0n>|1e>"""
                        self.QUA_prepare_state(4)
                        """qubit = |+n>|1e>"""

                        """reference 3 - manipulation part"""
                        align("MW", "RF")
                        if self.benchmark_switch_flag:  # 2 qubit
                            # play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |+n>|1e>
                            wait(t_wait)
                            with if_((idx == 0)):
                                wait(duration=4)
                                # qubit = |0n>|1e>
                            with else_():  # idx gates
                                wait(self.total_mw_wait)
                            align("MW", "RF")
                            # qubit = |+n>|1e>
                            # play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |0n>|1e>
                        else:  # 1 qubit
                            play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |+n>|1e>
                            with if_((idx == 0)):
                                pass
                            with else_():  # idx gates
                                wait(self.total_rf_wait)
                            play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            # qubit = |0n>|1e>

                        """measurement reference 3"""
                        wait(t_wait)
                        align("RF", "MW")
                        # self.MW_and_reverse_general(p_mw=self.mw_P_amp, t_mw=self.t_mw_qua, first_pulse="xPulse", second_pulse="-xPulse")
                        # play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # # qubit = is still |0n>|1e> and not like ref2 |0n>|0e>

                        # play Laser
                        align("MW", "Laser")
                        self.QUA_measure(m_state=18, idx=idx, tLaser=tLaser, tMeasure=tMeasure, t_rf=self.tRF,
                                         t_mw=self.t_mw, t_mw2=self.t_mw2, p_rf=self.rf_proportional_pwr)
                        self.benchmark_state_readout(counts_ref3, counts_tmp, tLaser, idx_vec_qua, idx, times, tMeasure)
                        align()

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

                with if_(idx == array_length - 1):
                    with for_(jdx, 0, jdx < idx, jdx + self.dN):
                        save(self.idx_vec_ini_shaffle_qua_reversed[jdx], self.reverse_number_order_st)

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + self.dN):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)
                    save(counts_ref2[idx], counts_ref_st2)
                    save(counts_square[idx], self.counts_square_st)
                    save(counts_ref3[idx], counts_ref_st3)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            counts_ref_st2.buffer(len(self.t_vec)).average().save("counts_ref2")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")
            self.number_order_st.buffer(len(self.t_vec)).average().save("number_order")
            # self.reverse_number_order_st.buffer(len(self.t_vec)).average().save("reverse_number_order")
            self.counts_square_st.buffer(len(self.t_vec)).average().save("counts_square")
            counts_ref_st3.buffer(len(self.t_vec)).average().save("counts_ref3")

    self.qm, self.job = self.QUA_execute()

def single_shot_play_list_of_gates(self):
    align("MW", "RF")
    play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF // 4)
    frame_rotation_2pi(0.5, "RF")
    play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF // 4)
    frame_rotation_2pi(0.5, "RF")
    align("RF", "Laser")

def single_shot_measure_nuclear_spin(self, t_wait):
    # Change N_pump to a new N parameter that is resposible for this
    if t_wait > 16:
        wait(t_wait)
    with for_(self.n_m, 0, self.n_m < self.n_measure, self.n_m + 1):
        self.MW_and_reverse(p_mw=self.mw_P_amp, t_mw=(self.t_mw / 2) // 4)
        align("MW", "Laser")
        align("MW", "Detector_OPD")
        play("Turn_ON", "Laser", duration=self.tLaser // 4)
        measure("readout", "Detector_OPD", None, time_tagging.digital(self.times, self.tMeasure, self.counts_tmp))
        assign(self.total_counts, self.total_counts + self.counts_tmp)

def Single_shot_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False, execute_qua=False):
    if generate_params:
        # sequence parameters
        self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime) // 4
        # self.tPump = self.time_in_multiples_cycle_time(self.Tpump) //4
        self.tLaser = self.time_in_multiples_cycle_time(self.Tpump)
        self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) // 4
        # self.tMeasure = 50
        self.fMW_2 = self.time_in_multiples_cycle_time(self.mw_freq_2)
        self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
        self.tMW2 = self.time_in_multiples_cycle_time(self.t_mw2) // 4
        self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        self.rf_pulse_time = 1000
        self.tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
        self.Npump = self.n_nuc_pump
        self.t_wait_benchmark = self.time_in_multiples_cycle_time(self.Twait * 1000) // 4
        self.mw_dif_freq_2 = self.MW_dif  # [MHz] to [GHz]

        # frequency scan vector
        # self.scan_param_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
        #                                      delta=self.mw_df * self.u.MHz, asInt=False)
        self.scan_param_vec = [1]

        # length and idx vector
        self.vectorLength = len(self.scan_param_vec)  # size of arrays
        self.array_length = len(self.scan_param_vec)  # frquencies vector size
        self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector

        # Simulation
        self.random_int = [random.randint(0, 100) for _ in range(100)]

        # tracking signal
        self.tSequencePeriod = ((self.tMW + self.tLaser) * (
                self.Npump + 2) + self.tRF * self.Npump) * self.array_length
        self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
        self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
            self.Tcounter)
        self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (
            self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

    if Generate_QUA_sequance:
        if not self.benchmark_switch_flag:
            play("Turn_ON", "Laser", duration=self.tLaser // 4)
            # qubit = |Mn>|0e>

            # Pumping: MW + RF + Laser (In that order)
            self.QUA_Pump(t_pump=self.tLaser, t_mw=self.tMW / 2, t_rf=self.tRF, f_mw=self.mw_freq * self.u.MHz,
                          f_rf=self.rf_resonance_freq * self.u.MHz,
                          p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=self.t_wait_benchmark)
            # First set of pi/2 half pulses with frequency f_2
            update_frequency("MW", self.mw_freq * self.u.MHz)
            self.MW_and_reverse(p_mw=self.mw_P_amp, t_mw=(self.t_mw / 2) // 4)
            # Second set of pi/2 half pulses with frequency f_1
            update_frequency("MW", (self.mw_freq + self.mw_dif_freq_2) * self.u.MHz)
            self.MW_and_reverse(p_mw=self.mw_P_amp, t_mw=(self.t_mw / 2) // 4)
            # Implementing all the gates
            self.single_shot_play_list_of_gates()
            play("Turn_ON", "Laser", duration=self.tLaser // 4)
            align("Laser", "MW")
            # Add wait time
            self.single_shot_measure_nuclear_spin(t_wait=self.t_wait_benchmark)
            align()
        else:
            assign(self.total_counts, 0)
            update_frequency("MW", (self.mw_freq + self.mw_dif_freq_2) * self.u.MHz)
            self.single_shot_measure_nuclear_spin(t_wait=self.t_wait_benchmark)
            align()

    if execute_qua:
        self.Single_shot_QUA_PGM(generate_params=True)
        self.QUA_PGM()

def Test_Crap_QUA_PGM(self):
    if self.test_type == Experiment.test_electron_spinPump:
        # wait time
        self.t_wait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        # scan variable
        min_scan_val = self.time_in_multiples_cycle_time(self.scan_t_start) // 4
        max_scan_val = self.time_in_multiples_cycle_time(self.scan_t_end) // 4
        self.scan_param_vec = self.GenVector(min=min_scan_val, max=max_scan_val, delta=self.scan_t_dt // 4,
                                             asInt=True)  # laser time [nsec]
        self.t_measure = self.time_in_multiples_cycle_time(self.TcounterPulsed)  # till solving the measure error

        # length and idx vector
        self.vectorLength = len(self.scan_param_vec)  # size of arrays
        self.array_length = len(self.scan_param_vec)  # frquencies vector size
        self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector
        self.cycle_tot_time = (self.t_wait + max_scan_val * 2 + min_scan_val * 2) * self.array_length

    if self.test_type == Experiment.test_electron_spinMeasure:
        # wait time
        self.t_wait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        # scan variable
        min_scan_val = self.time_in_multiples_cycle_time(self.scan_t_start) // 4
        max_scan_val = self.time_in_multiples_cycle_time(self.scan_t_end) // 4
        self.scan_param_vec = self.GenVector(min=min_scan_val, max=max_scan_val, delta=self.scan_t_dt // 4,
                                             asInt=True)  # laser time [nsec]
        self.t_measure = self.time_in_multiples_cycle_time(self.TcounterPulsed)  # till solving the measure error
        self.tLaser = self.time_in_multiples_cycle_time(self.Tpump)
        self.tMW = self.t_mw

        self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_1st_res)
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

        # length and idx vector
        self.vectorLength = len(self.scan_param_vec)  # size of arrays
        self.array_length = len(self.scan_param_vec)  # frquencies vector size
        self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector
        self.cycle_tot_time = (self.t_wait + max_scan_val * 2 + min_scan_val * 2) * self.array_length

    # tracking signal
    tSequencePeriod = self.cycle_tot_time
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        n = declare(int)  # iteration variable

        # QUA program parameters
        times = declare(int, size=20)
        times_ref = declare(int, size=20)

        with for_(n, 0, n < 20, n + 1):
            assign(times[n], 0)
            assign(times_ref[n], 0)

        tRead = declare(float)

        f = declare(int)  # frequency variable which we change during scan
        self.scan_param = declare(int)
        self.idx_timestamp = declare(int)
        self.measure_param = declare(int)
        self.wait_param = declare(int)

        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=self.array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=self.array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.scan_param_vec]))
        idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes
        idx1 = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        time_st = declare_stream()
        time_ref_st = declare_stream()
        # counts_st = declare_stream()  # experiment signal
        # counts_ref_st = declare_stream()  # reference signal

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < self.array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle and not (self.test_type == Experiment.test_electron_spinMeasure)):
                self.QUA_shuffle(idx_vec_qua, self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < self.array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    if self.test_type == Experiment.test_electron_spinPump:
                        assign(self.scan_param,
                               val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        play("Turn_ON", "Laser", duration=self.scan_param)
                        assign(self.wait_param, self.scan_param - self.t_measure // 4)
                        wait(self.wait_param, "Detector_OPD")
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times, self.t_measure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_tmp)
                        wait(self.t_wait // 4)

                    if self.test_type == Experiment.test_electron_spinMeasure:
                        assign(idx, self.array_length)  # only one cycle

                        # assign(self.scan_param, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        # tRead = self.scan_param

                        wait(self.MeasProcessTime // 4)

                        update_frequency("MW", self.fMW_1st_res)
                        play("Turn_ON", "Laser", duration=self.tLaser // 4)
                        # wait(self.tMW // 4)
                        # play MW (pi pulse)
                        align("Laser", "MW")
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMW // 4)

                        # Measure
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=self.tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times, self.tLaser, counts_tmp))
                        align()

                        wait(self.MeasProcessTime // 4)

                        # assign(self.idx_timestamp,0)
                        # with for_(idx1, 1, idx1 < self.array_length + 1, idx1 + 1):
                        #     #with if_(~(idx1==0)):
                        #     #    assign(counts[idx1], counts[idx1] + counts[idx1-1])
                        #     with while_((times[self.idx_timestamp]<val_vec_qua[idx1]*4)&(times[self.idx_timestamp]>=val_vec_qua[idx1-1]*4)&(self.idx_timestamp<counts_tmp)):
                        #         assign(counts[idx1-1], counts[idx1-1] + 1)
                        #         assign(self.idx_timestamp, self.idx_timestamp+1)

                        # Take reference (without pi pulse)
                        wait(self.tMW // 4)
                        play("Turn_ON", "Laser", duration=self.tLaser // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.tLaser, counts_ref_tmp))
                        align()

                        wait(self.MeasProcessTime // 4)

                        # assign(self.idx_timestamp,0)
                        # with for_(idx1, 1, idx1 < self.array_length + 1, idx1 + 1):
                        #     #with if_(~(idx1==0)):
                        #     #    assign(counts_ref[idx1], counts_ref[idx1] + counts_ref[idx1-1])
                        #     with while_((times_ref[self.idx_timestamp]<val_vec_qua[idx1]*4)&(times_ref[self.idx_timestamp]>=val_vec_qua[idx1-1]*4)&(self.idx_timestamp<counts_ref_tmp)):
                        #         assign(counts_ref[idx1-1], counts_ref[idx1-1] + 1)
                        #         assign(self.idx_timestamp, self.idx_timestamp+1)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx1, 0, idx1 < self.array_length,
                          idx1 + 1):  # in shuffle all elements need to be saved later to send to the stream
                    # save(counts[idx1], counts_st)
                    # save(counts_ref[idx1], counts_ref_st)
                    save(times[idx1], time_st)
                    save(times_ref[idx1], time_ref_st)
            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(self.array_length).average().save("counts")
            # counts_ref_st.buffer(self.array_length).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")
            time_st.histogram([[i, i + (self.scan_t_dt - 1)] for i in
                               range(self.scan_t_start, self.scan_t_end, self.scan_t_dt)]).save("counts")
            time_ref_st.histogram([[i, i + (self.scan_t_dt - 1)] for i in
                                   range(self.scan_t_start, self.scan_t_end, self.scan_t_dt)]).save("counts_ref")

    self.qm, self.job = self.QUA_execute()

def Nuclear_Pol_ESR_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False,
                            execute_qua=False):  # NUCLEAR_POL_ESR
    self.Entanglement_gate_tomography_QUA_PGM(Generate_QUA_sequance=True)
    if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
        # for i in range(self.n_of_awg_changes):
        #     self.change_AWG_freq(channel = 1)
        #     if self.simulation:
        #         self.awg_freq_list.append(self.current_awg_freq)
        #     else:
        #         self.awg_freq_list.append(self.awg.get_frequency())
        self.time_bin_entanglement_QUA_PGM(Generate_QUA_sequance=True)

def Nuclear_Pol_ESR_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False,
                            execute_qua=False):  # NUCLEAR_POL_ESR
    if generate_params:
        # sequence parameters
        self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
        self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
        self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        self.tMW = self.t_mw
        self.tMW2 = self.t_mw2
        self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        # fMW_res = 0 if fMW_res < 0 else fMW_res
        # self.fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
        self.fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_res)
        self.tRF = self.rf_pulse_time
        self.Npump = self.n_nuc_pump

        # frequency scan vector
        self.scan_param_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                                             delta=self.mw_df * self.u.MHz, asInt=False)

        # length and idx vector
        self.vectorLength = len(self.scan_param_vec)  # size of arrays
        self.array_length = len(self.scan_param_vec)  # frquencies vector size
        self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector

        # tracking signal
        self.tSequencePeriod = ((self.tMW + self.tLaser) * (
                    self.Npump + 2) + self.tRF * self.Npump + 2 * self.tWait) * self.array_length
        self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
        self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
            self.Tcounter)
        self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (
            self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1
    if Generate_QUA_sequance:
        assign(self.f, self.val_vec_qua[self.idx_vec_qua[self.idx]])  # shuffle - assign new val from randon index

        # signal
        # polarize (@fMW_res @ fRF_res)
        # play("Turn_ON", "Laser", duration=(self.tLaser) // 4)

        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        align()

        # CNOT
        # update_frequency("MW", self.fMW_2nd_res)
        # play MW
        ##play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
        #
        # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        #
        ## align("MW","RF")
        # RF pi/2 Y pulse
        # frame_rotation_2pi(0.25,"RF")
        ## play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF/2) // 4)
        # frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
        #
        ## align("RF","MW")

        # CNOT
        ## update_frequency("MW", self.fMW_res)
        # play MW
        # play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)

        ## play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        ## play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)

        # update MW frequency
        update_frequency("MW", self.f)
        # play MW
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=self.tMW2 // 4)
        # play("xPulse"*amp(self.mw_P_amp2), "MW", duration=(self.tMW2/2) // 4)
        # play("-xPulse"*amp(self.mw_P_amp2), "MW", duration=(self.tMW2/2) // 4)
        # play Laser
        align()
        # align("MW", "Laser")
        play("Turn_ON", "Laser", duration=(self.tLaser) // 4)
        # play Laser
        # align("MW", "Detector_OPD")
        # measure signal
        measure("readout", "Detector_OPD", None, self.time_tagging_fn(self.times, self.tMeasure, self.counts_tmp))
        assign(self.counts[self.idx_vec_qua[self.idx]], self.counts[self.idx_vec_qua[self.idx]] + self.counts_tmp)
        align()

        # reference
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        align()
        wait((self.tMW2 + self.tMW) // 4)  # don't Play MW
        # Play laser
        play("Turn_ON", "Laser", duration=(self.tLaser) // 4)
        # Measure ref
        measure("readout", "Detector_OPD", None,
                self.time_tagging_fn(self.times_ref, self.tMeasure, self.counts_ref_tmp))
        assign(self.counts_ref[self.idx_vec_qua[self.idx]],
               self.counts_ref[self.idx_vec_qua[self.idx]] + self.counts_ref_tmp)
    if execute_qua:
        self.Nuclear_Pol_ESR_QUA_PGM(generate_params=True)
        self.QUA_PGM()

def QUA_prepare_state(self, site_state):
    # ************ shift to gen parameters ************
    # self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
    # self.verify_insideQUA_FreqValues(self.fMW_1st_res)
    # self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
    # self.verify_insideQUA_FreqValues(self.fMW_2nd_res)
    # ************ shift to gen parameters ************

    self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)

    # duration of preps 0 to 3 (incl. reset) is  tLaser+tWait+Npump*(tWait+tPump+tRF+tMW)+tMW
    # duration of prep 4 (incl. reset) is  tLaser+tWait+Npump*(tWait+tPump+tRF+tMW)+tMW+tRF/2

    # reset
    align()
    play("Turn_ON", "Laser", self.tLaser // 4)
    align()
    if self.exp != Experiment.RandomBenchmark:
        wait(int(self.tWait) // 4)
    else:  # doing RandomBenchmark
        t_wait = self.time_in_multiples_cycle_time(self.Twait * 1000) // 4
        # wait(t_wait)

    with if_(site_state == 0):  # |00>
        # pump
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_1st_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        align()
        wait(int(self.tMW) // 4)

    with if_(site_state == 1):  # |01>
        # pump
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_2nd_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        align()
        wait(int(self.tMW) // 4)

    with if_(site_state == 2):  # |10>
        # pump
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_1st_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        align()
        # play MW
        # update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)
        update_frequency("MW", self.fMW_2nd_res)
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)

    with if_(site_state == 3):  # |11> if pumping and 50% |11> and 50% |00> if not
        # pump
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_2nd_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        # play MW
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
        update_frequency("MW", self.fMW_1st_res)
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)

    with if_(site_state == 4):  # |00>+|11>
        # pump
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_1st_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr,
                          t_wait=self.tWait)
        # Todo Check "f_mw = self.fMW_2nd_res"
        align()
        # play MW
        update_frequency("MW", self.fMW_2nd_res)
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        align("MW", "RF")
        # RF Y pulse
        frame_rotation_2pi(0.25, "RF")
        play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        wait(self.tWait // 4)
        # --> |1+> Todo - check

        align("RF", "MW")
        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)

    with if_(site_state == 5):  # |00>+|11> through echo-protected CeNOTn
        # pump to |0>|0>
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_1st_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp,
                          p_rf=self.rf_proportional_pwr, t_wait=self.tWait)
        align()
        # MW pi/2 pulse
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(self.t_mw2 / 2) // 4)

        # RF pi/2 X pulse
        align("MW", "RF")
        play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // 4)

        # MW pi pulse
        align("RF", "MW")
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        # wait for the pi time iof the RF
        wait(self.tRF // 4)

        # MW pi pulse
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        # RF pi/2 X pulse
        align("MW", "RF")
        play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // 4)

    with if_(site_state == 6):  # |10>+|11>
        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
            self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_1st_res,
                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp,
                          p_rf=self.rf_proportional_pwr, t_wait=self.tWait)
        align()
        # play MW
        # update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)
        update_frequency("MW", self.fMW_2nd_res)
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / 2) // 4)
        # play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # |10>

        align("MW", "RF")
        # RF Y pulse pi/2
        frame_rotation_2pi(0.25, "RF")
        play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        wait(self.tWait // 4)
        align("RF", "MW")
        # |10>+|11>

        # play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # play("yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)

def QUA_measure(self, m_state, idx, tLaser, tMeasure, t_rf, t_mw, t_mw2, p_rf):
    """A lot of updates from MIC branch. Cheeck cases with Eilon"""
    align()
    # durations of all measurements should be t_rf+2*t_mw+t_wait
    """populations"""
    with if_(m_state == 1):
        """|00><00| + |01><01|"""
        # pass
        wait(int(t_rf + 2 * t_mw + self.tWait) // 4)

    with if_(m_state == 2):
        """|00><00| + |11><11|"""
        wait((t_rf + t_mw + self.tWait) // 4)
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)

    with if_(m_state == 3):
        """|00><00| + |10><10|"""
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=t_rf // 4)
        align("RF", "MW")
        wait(self.tWait // 4)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)

    """e-coherences"""
    with if_(m_state == 4):
        # update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        # wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        wait(int((t_rf + t_mw - t_mw2 + self.tWait) // 4))
    with if_(m_state == 5):
        # update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        wait(int((t_rf + 2 * t_mw - t_mw2 + self.tWait) // 4))
        # wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
        # update_frequency("MW", self.fMW_1st_res)
        # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 6):
        # update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
        # play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        # wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        wait(int((t_rf + t_mw - t_mw2 + self.tWait) // 4))
    with if_(m_state == 7):
        # update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
        # play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        # wait(int((t_rf+t_mw-t_mw2/2) // 4))
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        wait(int((t_rf + 2 * t_mw - t_mw2) // 4))
        # update_frequency("MW", self.fMW_1st_res)
        # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

    """n-coherences"""
    with if_(m_state == 8):
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        wait(int((t_rf / 2 + t_mw + self.tWait) // 4))
        align("RF", "MW")
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 9):
        frame_rotation_2pi(0.25, "RF")  # RF Y pulse
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        align("RF", "MW")
        wait(int((t_rf / 2 + t_mw + self.tWait) // 4))
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 10):
        # update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=t_mw2 // 4)
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        align("RF", "MW")
        wait(int((t_rf / 2 - t_mw + self.tWait) // 4))
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 11):
        # update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        # play("xPulse"* amp(self.mw_P_amp2), "MW", duration=t_mw2 // 4)
        update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res) / 2)
        play("yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp2), "MW", duration=(t_mw2 / 2) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        frame_rotation_2pi(0.25, "RF")  # RF Y pulse
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        align("RF", "MW")
        wait(int((t_rf / 2 - t_mw + self.tWait) // 4))
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

    """entanglement coherences"""
    with if_(m_state == 12):
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        wait(int((t_rf / 2 + self.tWait) // 4))
        align("RF", "MW")
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 13):
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        frame_rotation_2pi(0.25, "RF")  # RF Y pulse
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        align("RF", "MW")
        wait(int((t_rf / 2 + self.tWait) // 4))
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 14):
        update_frequency("MW", self.fMW_2nd_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        align("RF", "MW")
        wait(int((t_rf / 2 + self.tWait) // 4))
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    with if_(m_state == 15):
        update_frequency("MW", self.fMW_2nd_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        align("MW", "RF")
        frame_rotation_2pi(0.25, "RF")  # RF Y pulse
        play("const" * amp(p_rf), "RF", duration=(t_rf / 2) // 4)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        align("RF", "MW")
        wait(int((t_rf / 2 + self.tWait) // 4))
        update_frequency("MW", self.fMW_1st_res)
        play("yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(t_mw / 2) // 4)
        # update_frequency("MW", self.fMW_2nd_res)
        # play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

    # # e-n-coherences
    # with if_(m_state==12):
    #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
    #     play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
    #     align("MW","RF")
    #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
    #     align("RF","MW")
    #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
    #     update_frequency("MW", self.fMW_1st_res)
    #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     #update_frequency("MW", self.fMW_2nd_res)
    #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    # with if_(m_state==13):
    #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
    #     play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
    #     align("MW","RF")
    #     frame_rotation_2pi(0.25,"RF") # RF Y pulse
    #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
    #     frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
    #     align("RF","MW")
    #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
    #     update_frequency("MW", self.fMW_1st_res)
    #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     #update_frequency("MW", self.fMW_2nd_res)
    #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    # with if_(m_state==14):
    #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
    #     play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
    #     align("MW","RF")
    #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
    #     align("RF","MW")
    #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
    #     update_frequency("MW", self.fMW_1st_res)
    #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     #update_frequency("MW", self.fMW_2nd_res)
    #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
    # with if_(m_state==15):
    #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
    #     play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
    #     align("MW","RF")
    #     frame_rotation_2pi(0.25,"RF") # RF Y pulse
    #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
    #     frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
    #     align("RF","MW")
    #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
    #     update_frequency("MW", self.fMW_1st_res)
    #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
    #     #update_frequency("MW", self.fMW_2nd_res)
    #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

    with if_(m_state == 16):
        """|01><01| + |10><10|"""
        if self.exp != Experiment.RandomBenchmark:
            wait((t_rf + t_mw + self.tWait) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 2
        else:
            duration_divsor = 2
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / duration_divsor) // 4, "-yPulse", "yPulse")
        # play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        # play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        """|01><01| + |10><10| --> |01><01| + |00><00|"""
        ##update_frequency("MW", self.fMW_2nd_res)
        ##play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)

    with if_(m_state == 17):
        """|00> + |11>"""
        if self.exp != Experiment.RandomBenchmark:
            wait((t_rf + t_mw + self.tWait) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 2
        else:
            duration_divsor = 2
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / duration_divsor) // 4, "yPulse", "-yPulse")
        # play("yPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        # play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        # --> |10>

        ##update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        ##play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        align("MW", "RF")
        # RF Y pulse
        frame_rotation_2pi(0.25, "RF")
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 1
        else:
            duration_divsor = 4
        play("const" * amp(-self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // duration_divsor)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        wait(self.tWait // 4)
        # --> |1+> Todo - check

        align("RF", "MW")
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 2
        else:
            duration_divsor = 2
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / duration_divsor) // 4, "-yPulse", "yPulse")
        # play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # play("yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # --> |00>+|11> Todo - check

    with if_(m_state == 18):
        """|00> - |11>"""
        if self.exp != Experiment.RandomBenchmark:
            wait((t_rf + t_mw + self.tWait) // 4)
        update_frequency("MW", self.fMW_2nd_res)
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 2
        else:
            duration_divsor = 2
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / duration_divsor) // 4, "yPulse", "-yPulse")
        # play("yPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        # play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
        # --> |10>

        ##update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        ##play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        align("MW", "RF")
        # RF Y pulse
        frame_rotation_2pi(0.25, "RF")
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 1
        else:
            duration_divsor = 4
        play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF / 2) // duration_divsor)
        frame_rotation_2pi(-0.25, "RF")  # reset phase back to zero
        wait(self.tWait // 4)
        # --> |1+> Todo - check

        align("RF", "MW")
        if self.exp == Experiment.RandomBenchmark:
            duration_divsor = 2
        else:
            duration_divsor = 2
        self.MW_and_reverse_general(self.mw_P_amp, (self.tMW / duration_divsor) // 4, "-yPulse", "yPulse")
        # play("-yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # play("yPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
        # --> |00>+|11> Todo - check

    if self.exp != Experiment.RandomBenchmark:
        align()
        # Play laser
        play("Turn_ON", "Laser", duration=tLaser // 4)
        # Measure ref
        measure("readout", "Detector_OPD", None, self.time_tagging_fn(self.times_ref, tMeasure, self.counts_tmp))
        assign(self.counts[idx], self.counts[idx] + self.counts_tmp)

def QUA_ref0(self, idx, tPump, tLaser, tMeasure, tWait1, tWait2):
    # pump
    align()
    wait(int(tWait1 // 4))
    play("Turn_ON", "Laser", duration=tPump // 4)
    align()
    wait(int(tWait2 // 4))
    # measure
    align()
    play("Turn_ON", "Laser", duration=tLaser // 4)
    measure("readout", "Detector_OPD", None, self.time_tagging_fn(self.times_ref, tMeasure, self.counts_ref_tmp))
    assign(self.counts_ref[idx], self.counts_ref[idx] + self.counts_ref_tmp)

def QUA_ref1(self, idx, tPump, tLaser, tMeasure, tWait1, tWait2, t_mw, f_mw1, f_mw2, p_mw):
    # pump
    align()
    wait(int(tWait1 // 4))
    play("Turn_ON", "Laser", duration=tPump // 4)
    align()
    wait(int(tWait2 // 4))
    # play MW
    align()
    update_frequency("MW", f_mw1)
    ##play("xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw) // 4)
    play("xPulse" * amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw / 2) // 4)
    play("-xPulse" * amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw / 2) // 4)
    update_frequency("MW", f_mw2)
    play("xPulse" * amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw / 2) // 4)
    play("-xPulse" * amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw / 2) // 4)
    align()
    # measure
    play("Turn_ON", "Laser", duration=tLaser // 4)
    measure("readout", "Detector_OPD", None, self.time_tagging_fn(self.times_ref, tMeasure, self.counts_ref2_tmp))
    assign(self.counts_ref2[idx], self.counts_ref2[idx] + self.counts_ref2_tmp)

def Entanglement_gate_tomography_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False, execute_qua=False):
    if generate_params:
        # todo update parameters if needed for this sequence
        # dummy vectors to be aligned with QUA_PGM convention
        self.array_length = 1
        self.idx_vec_ini = np.arange(0, self.array_length, 1)
        self.scan_param_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                                             delta=self.mw_df * self.u.MHz, asInt=False)

        # sequence parameters
        self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)  # [nsec]
        self.tPump = self.time_in_multiples_cycle_time(self.Tpump)  # [nsec]
        self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)  # [nsec]
        self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)  # [nsec]
        self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        self.Npump = self.n_nuc_pump

        # MW parameters
        self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
        self.tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
        self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_1st_res)
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

        # RF parameters
        self.tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
        self.f_rf = self.rf_resonance_freq

        # length and idx vector
        self.first_state = 3  # serial number of first initial state
        self.last_state = 3  # serial number of last initial state
        self.number_of_states = 1  # number of initial states
        self.number_of_measurement = 3  # number of measurements
        self.measurements = [1, 2, 3]  # ,4,5,6,7,8,9,10,11,12,13,14,15]
        self.vectorLength = self.number_of_states * self.number_of_measurement  # total number of measurements
        self.idx_vec_ini = np.arange(0, self.vectorLength, 1)  # for visualization purpose

        # tracking signal
        self.tSequencePeriod = (self.tMW + self.tRF) * self.array_length
        self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
        self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
            self.Tcounter)
        self.trackingNumRepeatition = 1000  # self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

        self.bEnableShuffle = False

    if Generate_QUA_sequance:
        self.measurements_qua = declare(int, value=self.measurements)
        with for_(self.site_state, self.first_state, self.site_state < self.last_state + 1,
                  self.site_state + 1):  # site state loop
            with for_(self.j_idx, 0, self.j_idx < self.number_of_measurement, self.j_idx + 1):  # measure loop
                assign(self.i_idx, self.site_state * (self.number_of_states - 1) + self.j_idx)
                # prepare state
                self.QUA_prepare_state(site_state=self.site_state)

                # duration of CNOT or NOOP is tMW.
                # C-NOT
                align()
                # update_frequency("MW", self.fMW_1st_res)
                # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                # update_frequency("MW", self.fMW_2nd_res)
                # play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
                # wait(self.tMW//4)
                # measure
                self.QUA_measure(m_state=self.measurements_qua[self.j_idx], idx=self.i_idx, tLaser=self.tLaser,
                                 tMeasure=self.tMeasure, t_rf=self.tRF, t_mw=self.tMW, t_mw2=self.tMW2,
                                 p_rf=self.rf_proportional_pwr)
                # reference
                # total duration of reference for prep 4 is tLaser+tWait +Npump*(tWait+tPump+tRF+tMW)+tMW+tRF/2 +tMW +tRF+2tMW +tLaser
                self.QUA_ref0(idx=self.i_idx, tPump=self.tPump, tLaser=self.tLaser, tMeasure=self.tMeasure,
                              tWait1=self.tWait + self.tRF + self.tMW,
                              tWait2=self.tWait + 4 * self.tMW + 3 / 2 * self.tRF)
                self.QUA_ref1(idx=self.i_idx,
                              tPump=self.tPump, tLaser=self.tLaser, tMeasure=self.tMeasure,
                              tWait1=self.tWait + self.tRF + self.tMW,
                              tWait2=self.tWait + 4 * self.tMW + 3 / 2 * self.tRF - self.t_mw2,
                              t_mw=self.time_in_multiples_cycle_time(self.t_mw), f_mw1=self.fMW_1st_res,
                              f_mw2=self.fMW_2nd_res, p_mw=self.mw_P_amp)

        with for_(self.i_idx, 0, self.i_idx < self.vectorLength, self.i_idx + 1):
            assign(self.resCalculated[self.i_idx],
                   (self.counts[self.i_idx] - self.counts_ref2[self.i_idx]) * 1000000 / (
                               self.counts_ref2[self.i_idx] - self.counts_ref[self.i_idx]))

    if execute_qua:
        self.Entanglement_gate_tomography_QUA_PGM(generate_params=True)
        self.QUA_PGM()

def repeated_time_bin_qua_sequence_start(self):
    time_tagger = self.get_time_tagging_func("Detector_OPD")
    # In the first part of the experiment we want information on the timing of the photon arrivals.
    # Only one photon can be recorded at the detector at a time
    align("Laser", "Blinding")
    play("Turn_ON", "Laser", duration=self.tLaser)
    play("Turn_ON", "Blinding", duration=self.tBlinding_pump)
    play(f"opr_{int(self.off_time + 1)}", "Blinding")  # Calibrated for 1ns Laser trigger time
    play(f"opr_left_{int(self.tblidning_2_to_3_first_waveform_length)}", "Blinding")
    align("Laser", "MW")
    play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
    align("MW", "Resonant_Laser")
    play("Turn_ON", "Resonant_Laser", duration=self.tRed)
    # Records #self.times at points where self.counts_tmp is recorded
    # self.times is NOT a vector of length self.tMeasure
    # self.counts_tmp stores the total number of photon arrivals as an integer
    align("Laser", "Detector_OPD")
    measure("readout", "Detector_OPD", None,
            time_tagger(self.times, int(self.MeasProcessTime), self.counts_tmp))
    assign(self.counts[self.idx], self.counts[self.idx] + self.counts_tmp)
    align("Blinding", "MW")
    play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMW)
    play("Turn_ON", "Blinding", duration=self.tBlinding)
    play(f"opr_{int(self.off_time + 1)}", "Blinding")
    align("MW", "Resonant_Laser")
    play("Turn_ON", "Resonant_Laser", duration=self.tRed)
    play(f"opr_left_{int(self.tblidning_2_to_3_first_waveform_length)}", "Blinding")
    # The pulse below is to enforce total length of 16 ns, can be changes to any length above self.tblidning_2_to_3_first_waveform_length
    play(f"opr_{int(self.tblidning_2_to_3_second_waveform_length)}", "Blinding")
    # Insert an if condition here in the future
    # In the second half of the experiment we want the number of counts and not their timing
    align("Blinding", "MW")  # Check the timing correctly
    wait(self.T_bin_qua)  # +1 to give the pulses some space

def repeated_time_bin_qua_sequence_end(self):
    time_tagger = self.get_time_tagging_func("Detector_OPD")
    # align("MW", self.laser_type_stat)
    # play("Turn_ON", self.laser_type_stat, duration=self.tStatistics)
    # align("MW", "Detector2_OPD")
    # measure("min_readout", "Detector2_OPD", None,
    #         time_tagger(self.times2, int(self.tStatistics), self.counts_tmp2))
    # assign(self.counts2[self.idx], self.counts2[self.idx] + self.counts_tmp2)

def time_bin_entanglement_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False, execute_qua=False):
    if generate_params:
        # dummy vectors to be aligned with QUA_PGM convention
        self.array_length = 1  # time vector size
        self.idx_vec_ini = np.arange(0, self.array_length, 1)  # Index array for QUA_PGM
        self.f_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                                    delta=self.mw_df * self.u.MHz,
                                    asInt=False)  # Don't need it, but QUA_PGM requires it

        # Updated experiment parameters
        self.collection_time = 25  # time of light collection in a single bin in ns
        self.red_laser_wait = 3  # time to wait after shooting a red laser pulse in ns
        self.Tpump = 5000  # [nsec]
        self.t_mw = 32  # [nsec]
        self.t_blinding_pump = 5000  # First blinding, to cover the detector before the first measure
        self.tblinding_2_to_3 = 16  # [nsec]
        # self.bin_times = [[20, 48], [84, 112], [128, 156]] # Does not change as of 12.02.2025
        self.tblidning_2_to_3_first_waveform_length = self.tblinding_2_to_3 - (
                    self.T_bin - self.tblinding_2_to_3) - 1  # To understand, check how waveforms are defined in the config
        self.tblidning_2_to_3_second_waveform_length = self.tblinding_2_to_3 - self.tblidning_2_to_3_first_waveform_length

        # sequence parameters.
        self.tLaser = self.time_in_multiples_cycle_time(self.Tpump) // 4
        self.tWaitTimeGateSuppression = self.time_in_multiples_cycle_time(
            self.TwaitTimeBin) // 4  # This returns 16ns
        self.tWaitDectorMeasure = self.time_in_multiples_cycle_time(self.TwaitTimeBinMeasure) // 4
        self.tWaitfroblinding = self.time_in_multiples_cycle_time(self.TwaitForBlinding) // 4

        # New red laser parameters:
        self.tRed = self.time_in_multiples_cycle_time(self.TRed) // 4
        self.tCollectionWait = self.time_in_multiples_cycle_time(1)
        self.tStatistics = self.time_in_multiples_cycle_time(self.TRedStatistics) // 4  # change to resonant measure

        # MW parameters
        self.tMW = self.time_in_multiples_cycle_time(self.t_mw) // 4
        self.tMWPiHalf = self.time_in_multiples_cycle_time(self.t_mw / 2) // 4
        # self.tMWPiStat = self.tMW
        # Change to time between blidning and MW
        self.time_to_next_MW = self.time_in_multiples_cycle_time(self.T_bin) // 4
        self.T_bin_qua = self.time_in_multiples_cycle_time(self.T_bin) // 4

        self.tBlinding_pump = self.tLaser + self.tMWPiHalf  # +1 to prevent recording laser light
        self.tBlinding = self.tMW  # Second blinding, between the first and second measurement bin
        self.tBlinding_2_to_3 = self.time_in_multiples_cycle_time(
            self.tblinding_2_to_3) // 4  # Third blinding, between 2 and 3 measure, fixed to 16ns for now
        self.wait_before_stat = self.time_in_multiples_cycle_time(2 * self.T_bin) // 4

        # length and idx vector
        # Move to qua units below
        self.MeasProcessTime = self.tMWPiHalf + (self.off_time + 1) + self.T_bin + self.tMW + (
                    self.off_time + 1) + 2 * self.T_bin + self.tblinding_2_to_3 + 1  # time required of measure, 4 is red laser trigger+2ns wait
        # self.tMeasure = self.time_in_multiples_cycle_time(
        #     self.MeasProcessTime) // 4  # Measurement time of the detector
        self.vectorLength = 1  # Length of the counts vector
        self.idx_vec = np.arange(0, self.vectorLength, 1)  # indexes vector for fetch and plot
        self.all_times_vec = np.arange(0, self.MeasProcessTime, 1)
        self.number_of_statistical_measurements = 1000
        self.statistics_pulse_type = "xPulse"

        # tracking signal
        self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
        self.Npump = self.n_nuc_pump
        self.tSequencePeriod = ((self.tMW + self.tLaser) * (
                self.Npump + 2) * self.Npump) * self.array_length
        self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
        self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
            self.Tcounter)
        self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (
            self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

        # Defining the type of laser to use in the second half of the experiment
        if self.is_green:
            self.laser_type_stat = "Laser"
        else:
            self.laser_type_stat = "Resonant_Laser"

        start_bin_1 = self.t_mw // 2 + 1 + self.off_time  # +1 [ns] is red laser trigger time
        start_bin_2 = start_bin_1 + self.T_bin + self.t_mw + 1 + self.off_time
        start_bin_3 = start_bin_2 + self.T_bin + self.tblinding_2_to_3
        self.bin_times = [[start_bin_1, start_bin_1 + self.T_bin], [start_bin_2, start_bin_2 + self.T_bin],
                          [start_bin_3, start_bin_3 + self.T_bin]]

        # Variables for simulation
        a = 20
        b = 48
        self.tau = 1.2
        self.lower_simulation_bound = np.exp(-a / self.tau)
        self.higher_simulation_bound = np.exp(-b / self.tau)

    if Generate_QUA_sequance:
        with if_(self.simulation_flag):
            # rand = Random()
            # assign(self.r,rand.rand_fixed())
            # assign(self.times[self.n_avg], -self.tau * Math.ln(self.exp_a_simulated - self.r * (self.exp_a_simulated - self.exp_b_simulated)))
            assign(self.counts[self.idx], 4)
            with for_(self.j_idx, 0, self.j_idx < self.counts[self.idx], self.j_idx + 1):
                assign(self.times[self.j_idx], self.j_idx * 10)
            #     #assign(self.times[self.j_idx], Cast.to_int(-1.2 * Math.ln(1.0 - self.r)))
            #     #assign(self.assign_input[self.j_idx], -1.2 * Math.ln(1.0 - self.r)) #Despite declared as a fixed array, takes int
            assign(self.counts2[self.idx], 15)
        with else_():
            with switch_(self.mod4, unsafe=True):
                with case_(0):
                    self.repeated_time_bin_qua_sequence_start()
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
                    self.repeated_time_bin_qua_sequence_end()
                    assign(self.pulse_type, 4)

                with case_(3):
                    self.repeated_time_bin_qua_sequence_start()
                    play("yPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
                    self.repeated_time_bin_qua_sequence_end()
                    assign(self.pulse_type, 3)

                with case_(2):
                    self.repeated_time_bin_qua_sequence_start()
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMW)
                    self.repeated_time_bin_qua_sequence_end()
                    assign(self.pulse_type, 2)

                with case_(1):
                    self.repeated_time_bin_qua_sequence_start()
                    play("yPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf, condition=self.bool_condition)
                    self.repeated_time_bin_qua_sequence_end()
                    assign(self.pulse_type, 1)

        ## The code below simulates 20 pulses with increasing pulse length by 1ns.
        # with for_(self.k_idx, 0, self.k_idx < 20+5, self.k_idx + 1):
        #     with if_(self.k_idx < 16):
        #         with switch_(self.k_idx, unsafe=True):
        #             for jdx in range(16):
        #                 with case_(jdx):
        #                     play(f"opr_{jdx}", "Blinding")
        #     with else_():
        #         with switch_(self.k_idx, unsafe=True):
        #             for jdx in range(4):
        #                 with case_(jdx + 16):
        #                     play(f"opr2_{jdx}", "Blinding")
        #                     play('Turn_ON', 'Blinding', duration=4)#Required for pulses longer than 16ns

        ##Below is testing of playing of a single command
        # play(f"opr2_{3}", "Blinding") # Length is n-1, where opr2_n
        # play('Turn_ON', 'Blinding', duration=4)
        #     wait(25, 'Blinding')

    if execute_qua:
        self.time_bin_entanglement_QUA_PGM(generate_params=True)
        # counts = create_counts_vector(vector_size=96)
        self.QUA_PGM_No_Tracking()

def Population_gate_tomography_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False, execute_qua=False):
    if generate_params:
        # dummy vectors to be aligned with QUA_PGM convention
        self.array_length = 1
        self.idx_vec_ini = np.arange(0, self.array_length, 1)
        self.scan_param_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                                             delta=self.mw_df * self.u.MHz, asInt=False)

        # sequence parameters
        self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)  # [nsec]
        self.tPump = self.time_in_multiples_cycle_time(self.Tpump)  # [nsec]
        self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)  # [nsec]
        self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)  # [nsec]
        self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
        self.Npump = self.n_nuc_pump

        # MW parameters
        self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
        self.tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
        self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_1st_res)
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

        # RF parameters
        self.tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
        self.f_rf = self.rf_resonance_freq

        # length and idx vector
        self.number_of_states = 4  # number of initial states |00>, |01>, |10>, |11>
        self.number_of_measurement = 3  # number of intensities measurements
        self.vectorLength = self.number_of_states * self.number_of_measurement  # total number of measurements
        self.idx_vec_ini = np.arange(0, self.vectorLength, 1)  # for visualization purpose

        # tracking signal
        self.tSequencePeriod = (self.tMW + self.tRF) * self.array_length
        self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
        self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
            self.Tcounter)
        self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (
            self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

        self.bEnableShuffle = False

    if Generate_QUA_sequance:
        with for_(self.site_state, 0, self.site_state < self.number_of_states, self.site_state + 1):  # site state loop
            with for_(self.j_idx, 0, self.j_idx < self.number_of_measurement, self.j_idx + 1):  # measure loop
                assign(self.i_idx, self.site_state * (self.number_of_states - 1) + self.j_idx)
                # prepare state
                self.QUA_prepare_state(site_state=self.site_state)
                # C-NOT
                update_frequency("MW", self.fMW_1st_res)
                play("xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
                play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(self.tMW / 2) // 4)
                # wait(self.tMW//4)
                # measure
                self.QUA_measure(m_state=self.j_idx + 1, idx=self.i_idx, tLaser=self.tLaser, tMeasure=self.tMeasure,
                                 t_rf=self.tRF, t_mw=self.tMW, t_mw2=self.tMW2, p_rf=self.rf_proportional_pwr)
                # reference
                self.QUA_ref0(idx=self.i_idx, tPump=self.tPump, tLaser=self.tLaser, tMeasure=self.tMeasure,
                              tWait1=self.tWait + self.tRF + self.tMW,
                              tWait2=self.tWait + 4 * self.tMW + 3 / 2 * self.tRF)
                self.QUA_ref1(idx=self.i_idx,
                              tPump=self.tPump, tLaser=self.tLaser, tMeasure=self.tMeasure,
                              tWait1=self.tWait + self.tRF + self.tMW,
                              tWait2=self.tWait + 4 * self.tMW + 3 / 2 * self.tRF - self.t_mw2,
                              t_mw=self.time_in_multiples_cycle_time(self.t_mw2), f_mw1=self.fMW_1st_res,
                              f_mw2=self.fMW_2nd_res, p_mw=self.mw_P_amp)

        with for_(self.i_idx, 0, self.i_idx < self.vectorLength, self.i_idx + 1):
            assign(self.resCalculated[self.i_idx],
                   (self.counts[self.i_idx] - self.counts_ref2[self.i_idx]) * 1000000 / (
                               self.counts_ref2[self.i_idx] - self.counts_ref[self.i_idx]))

    if execute_qua:
        self.Population_gate_tomography_QUA_PGM(generate_params=True)
        self.QUA_PGM()

def MZI_g2(self, g2, times_1, counts_1, times_2, counts_2, correlation_width):
    """
       Calculate the second order correlation of click times between two counting channels

       :param g2: (QUA array of type int) - g2 measurement from the previous iteration.
       The size must be greater than correlation width.
       :param times_1: (QUA array of type int) - Click times in nanoseconds from channel 1
       :param counts_1: (QUA int) - Number of total clicks at channel 1
       :param times_2: (QUA array of type int) - Click times in nanoseconds from channel 2
       :param counts_2: (QUA int) - Number of total clicks at channel 2
       :param correlation_width: (int) - Relevant correlation window to analyze data
       :return: (QUA array of type int) - Updated g2
       """
    j = declare(int)
    k = declare(int)
    diff = declare(int)
    diff_ind = declare(int)
    lower_index_tracker = declare(int)
    # set the lower index tracker for each dataset
    assign(lower_index_tracker, 0)
    with for_(k, 0, k < counts_1, k + 1):
        with for_(j, lower_index_tracker, j < counts_2, j + 1):
            assign(diff, times_2[j] - times_1[k])
            # if correlation is outside the relevant window move to the next photon
            with if_(diff > correlation_width):
                assign(j, counts_2 + 1)
            with elif_((diff <= correlation_width) & (diff >= -correlation_width)):
                assign(diff_ind, diff + correlation_width)
                assign(g2[diff_ind], g2[diff_ind] + 1)
            # Track and evolve the lower bound forward every time a photon falls behind the lower bound
            with elif_(diff < -correlation_width):
                assign(lower_index_tracker, lower_index_tracker + 1)
    return g2

def g2_raw_QUA(self):
    # Scan Parameters
    n_avg = self.n_avg
    # res = self.GetItemsVal(["inInt_G2_correlation_width"])
    correlation_width = self.correlation_width * self.u.ns
    self.correlation_width = int(correlation_width)
    expected_counts = 1000
    N = 1000  # every N cycles it tries to update the stream

    with program() as self.quaPGM:
        counts_1 = declare(int)  # variable for the number of counts on SPCM1
        counts_2 = declare(int)  # variable for the number of counts on SPCM2
        times_1 = declare(int, size=expected_counts)  # array of count clicks on SPCM1
        times_2 = declare(int, size=expected_counts)  # array of count clicks on SPCM2

        # g2 = declare(int,value=self.GenVector(min=0,max=0,delta=0,N=int(2*correlation_width),asInt=True))  # array for g2 to be saved
        g2 = declare(int, size=int(2 * correlation_width))  # array for g2 to be saved
        total_counts = declare(int)

        # Streamables
        g2_st = declare_stream()  # g2 stream
        total_counts_st = declare_stream()  # total counts stream
        n_st = declare_stream()  # iteration stream

        # Variables for computation
        p = declare(int)  # Some index to run over
        n = declare(int)  # n: repeat index
        # with infinite_loop_():
        # play("Turn_ON", "Laser")
        idxN = declare(int, value=0)  # every N steps it will try to update the stream
        iteration_number = declare(int, value=0)  # every N steps it will try to update the stream

        with infinite_loop_():
            assign(idxN, idxN + 1)
            assign(iteration_number, iteration_number + 1)

            play("Turn_ON", "Laser")
            measure("readout", "Detector_OPD", None, self.time_tagging_fn(times_1, self.Tcounter, counts_1))
            measure("readout", "Detector2_OPD", None, self.time_tagging_fn(times_2, self.Tcounter, counts_2))

            with if_((counts_1 > 0) & (counts_2 > 0)):
                g2 = self.MZI_g2(g2, times_1, counts_1, times_2, counts_2, correlation_width)

            assign(total_counts, counts_1 + counts_2 + total_counts)

            with if_(idxN > N - 1):
                assign(idxN, 0)
                with for_(p, 0, p < g2.length(), p + 1):
                    save(g2[p], g2_st)
                    # assign(g2[p], 0)

                save(iteration_number, n_st)
                save(total_counts, total_counts_st)

        save(iteration_number, n_st)
        save(total_counts, total_counts_st)

        with stream_processing():
            # g2_st.buffer(correlation_width*2).save("g2")
            g2_st.buffer(correlation_width * 2).average().save("g2")
            total_counts_st.save("total_counts")
            n_st.save("iteration")

    self.qm, self.job = self.QUA_execute()

def ODMR_Bfield_QUA_PGM(self):  # CW_ODMR

    # specific per experiment
    # get experiment values from GUI
    items_val = self.GetItemsVal(
        items_tag=["inInt_process_time", "inInt_TcounterPulsed", "inInt_Tsettle", "inInt_t_mw", "inInt_edge_time"])

    # Experiment time period parameters
    tLaser = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"] +
                                               items_val["inInt_Tsettle"] +
                                               items_val[
                                                   "inInt_process_time"])  # self.TcounterPulsed+self.Tsettle+tMeasueProcess)
    tMW = self.time_in_multiples_cycle_time(items_val["inInt_t_mw"])  # self.t_mw)
    tMeasure = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"])  # self.TcounterPulsed)
    tSettle = self.time_in_multiples_cycle_time(items_val["inInt_Tsettle"])  # self.Tsettle)
    tEdge = self.time_in_multiples_cycle_time(items_val["inInt_edge_time"])  # self.Tedge)
    tBfield = self.time_in_multiples_cycle_time(tMW + 2 * tEdge)

    # Scan over MW frequency - gen its vector
    vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                         delta=self.mw_df * self.u.MHz)
    array_length = len(vec)
    self.f_vec = vec

    # length and idx vector
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = (tBfield + tLaser) * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to zero - DC pulse
        update_frequency("RF", 0 * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set new MW frequency
                    assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                    update_frequency("MW", f)  # update frequency

                    # Signal
                    wait(tEdge // 4, "MW")
                    play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                    # wait(300//4,"RF")
                    play("const" * amp(p), "RF", duration=tBfield // 4)

                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference sequence
                    # don't play MW
                    wait(tEdge // 4, "MW")
                    play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                    # play("const" * amp(p), "RF",duration=tBfield // 4)

                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    align()

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def NuclearFastRotation_QUA_PGM(self):
    # time
    tMeasueProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tMW = self.time_in_multiples_cycle_time(self.t_mw)
    tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tEdge = self.time_in_multiples_cycle_time(self.Tedge)
    tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)
    tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
    tBfield = self.time_in_multiples_cycle_time(tMW2 + 2 * tEdge)
    Npump = self.n_nuc_pump

    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res  # here should be zero
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # amp scan vector
    # set RF frequency:
    pRF = self.rf_Pwr / self.OPX_rf_amp  # p should be between 0 to 1
    pRF = pRF if 0 < pRF < 1 else 0
    if pRF == 0:
        print(f"error RF freq is out of limit {pRF}")
    dp_N = float(self.N_p_amp)
    p_vec_ini = np.arange(0, 0.4, 1 / dp_N, dtype=float)  # proportion vect
    self.rf_Pwr_vec = p_vec_ini * self.OPX_rf_amp  # in [V], used to plot the graph

    # MW frequency scan vector
    # fitCoff - see Eilon's Onenote
    # f2_GHz*1e9 + (b*V/(V + c))*1e9
    b = 0.0344
    c = 0.124
    self.f_vec = ((fMW_res1 + fMW_res2) / 2 + (
            self.rf_Pwr_vec * b / (self.rf_Pwr_vec + c)) * 1e9)  # [Hz], frequencies vector
    self.f_vec = self.f_vec.astype(int)

    # length and idx vector
    array_length = len(p_vec_ini)  # amps vector size
    # array_length = len(self.t_vec)                      # time vector size
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + tBfield + tWait + tMW + tLaser) * 3 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan - here f is according to calibration function
        t = declare(int)  # [cycles] time variable which we change during scan
        p = declare(fixed)  # [unit less] proportional amp factor which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
        counts_ref2_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)
        counts_ref2 = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        # f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))
        f_vec_qua = declare(int, value=self.f_vec)  # frequencies QUA vector
        val_vec_qua = declare(fixed, value=p_vec_ini)  # volts QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal
        counts_ref2_st = declare_stream()  # reference signal

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref2[idx], 0)  # shuffle - assign new val from randon index
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set new RF proportional amplitude
                    assign(p, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index

                    assign(f, f_vec_qua[idx_vec_qua[idx]])

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                        play("const" * amp(pRF), "RF", duration=tRF // 4)
                        # turn on laser to polarize
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    wait(tEdge // 4, "MW")
                    update_frequency("MW", f)
                    play("cw" * amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                    # wait(20//4,"RF") # manual calibration
                    update_frequency("RF", 0 * self.u.MHz)  # set RF frequency to resonance
                    play("const" * amp(p), "RF", duration=tBfield // 4)

                    align()
                    wait(tWait // 4)
                    update_frequency("MW", fMW_res1)
                    play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference sequence
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                        play("const" * amp(pRF), "RF", duration=tRF // 4)
                        # turn on laser to polarize
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    wait((tEdge + tMW2 + tWait) // 4, "MW")
                    # update_frequency("MW", fMW_res2)
                    # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                    # wait(300//4,"RF") # manual calibration
                    # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                    # play("const" * amp(p), "RF",duration=tBfield // 4)

                    # align()
                    # wait(tWait)
                    update_frequency("MW", fMW_res1)
                    play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    align()

                    # reference sequence
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                        play("const" * amp(pRF), "RF", duration=tRF // 4)
                        # turn on laser to polarize
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    wait((tEdge + tMW2 + tWait) // 4, "MW")
                    # update_frequency("MW", fMW_res2)
                    # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                    # wait(300//4,"RF") # manual calibration
                    # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                    # play("const" * amp(p), "RF",duration=tBfield // 4)

                    # align()
                    # wait(tWait//4)
                    update_frequency("MW", fMW_res2)
                    play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref2_tmp))
                    assign(counts_ref2[idx_vec_qua[idx]], counts_ref2[idx_vec_qua[idx]] + counts_ref2_tmp)

                    align()

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)
                    save(counts_ref2[idx], counts_ref2_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_ref2_st.buffer(len(self.f_vec)).average().save("counts_ref2")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Electron_lifetime_QUA_PGM(self):  # T1
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + tScan_max / 2 + tMW + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index
                    # signal
                    wait(t)
                    # play Laser
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # measure signal
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()
                    # play MW
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    wait(t)
                    align()
                    # play Laser
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # Measure ref
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Nuclear_spin_lifetimeS0_QUA_PGM(self):
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + tScan_max / 2 + tMW + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to polarize
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play Laser
                    play("Turn_ON", "Laser", duration=(tSettle) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res1)
                    # play MW
                    align("Laser", "MW")
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # measure signal
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to polarize
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play Laser
                    play("Turn_ON", "Laser", duration=(tSettle) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    align("Laser", "MW")
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # Measure ref
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Nuclear_spin_lifetimeS1_QUA_PGM(self):
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + tScan_max / 2 + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()

                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    play("cw", "MW", duration=tMW // 4)

                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play Laser
                    play("Turn_ON", "Laser", duration=(tSettle) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res1)
                    # play MW
                    align("Laser", "MW")
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # measure signal
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    play("cw", "MW", duration=tMW // 4)

                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play Laser
                    play("Turn_ON", "Laser", duration=(tSettle) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    align("Laser", "MW")
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # Measure ref
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Nuclear_Ramsay_QUA_PGM(self):
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tWait = self.time_in_multiples_cycle_time(self.Twait)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + tRF + tScan_max / 2 + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes
        jdx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    play("Turn_ON", "Laser", duration=tPump // 4)
                    align("Laser", "MW")
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                        wait(tWait // 4)
                    align()

                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # CnNOTe
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)

                    # play RF pi/2
                    align("MW", "RF")
                    play("const" * amp(p), "RF", duration=(tRF / 2) // 4)

                    # flip electron spin down by MW pulses on both resonances
                    # align("RF", "MW")
                    # play("-xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)
                    # play("xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)
                    # update_frequency("MW", fMW_res1)
                    # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)

                    # play laser during the wait time
                    align("RF", "Laser")
                    # align("MW", "Laser")
                    # play("Turn_ON", "Laser", duration=(t-(tMW*4)//4))
                    play("Turn_ON", "Laser", duration=t - (tMW * 2) // 4)
                    # with for_(jdx,0,jdx<(t-(tMW*2)//4),jdx+tSettle//4):
                    #    play("Turn_ON", "Laser", duration=tPump//4)
                    #    wait(tSettle//4-tPump//4)

                    # Twait, note: t is already in cycles!
                    # wait(t)
                    # flip electron spin back up
                    align("Laser", "MW")
                    update_frequency("MW", fMW_res1)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    update_frequency("MW", fMW_res2)
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)

                    # play RF pi/2
                    align("MW", "RF")
                    # align("Laser","RF")
                    play("const" * amp(-p), "RF", duration=(tRF / 2) // 4)
                    # play Laser
                    # align("RF", "Laser")
                    # play("Turn_ON", "Laser", duration=tSettle // 4)

                    align("RF", "MW")
                    wait(tWait // 4)

                    # CnNOTe
                    update_frequency("MW", fMW_res2)
                    play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)

                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # measure signal
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    # polarize (@fMW_res @ fRF_res)
                    play("Turn_ON", "Laser", duration=tPump // 4)
                    align("Laser", "MW")
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                        wait(tWait // 4)
                    align()

                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # CnNOTe
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)

                    # Nucl. pi/2
                    align("MW", "RF")
                    play("const" * amp(p), "RF", duration=(tRF / 2) // 4)

                    # flip electron spin down
                    # align("RF", "MW")
                    # play("-xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)
                    # play("xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)
                    # update_frequency("MW", fMW_res1)
                    # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)

                    # do not play laser
                    # wait(t - (tMW*4)//4)
                    wait(t)
                    # wait(tWait //4)
                    # play Laser
                    # play("Turn_ON", "Laser", duration=tSettle // 4)

                    # flip electron spin back up
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                    # update_frequency("MW", fMW_res2)
                    # play("xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse"*amp(self.mw_P_amp2), "MW", duration=(tMW/2) // 4)

                    # align("MW","RF")
                    # play RF pi/2
                    play("const" * amp(-p), "RF", duration=(tRF / 2) // 4)
                    # play Laser
                    # align("RF", "Laser")
                    # play("Turn_ON", "Laser", duration=tSettle // 4)

                    align("RF", "MW")
                    wait(tWait // 4)

                    # CnNOTe
                    update_frequency("MW", fMW_res2)
                    play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(tMW / 2) // 4)

                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # Measure ref
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Electron_Coherence_QUA_PGM(self):  # Also CPMG when N>0
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.time_in_multiples_cycle_time(self.t_mw)
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Ncpmg = self.n_CPMG

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector (Twait)
    tStart = self.time_in_multiples_cycle_time(self.scan_t_start)  # [nsec]
    if Ncpmg > 0:
        if ((tStart / (2 * Ncpmg) - tMW / 2) <= 20):  # [nsec]
            tStart = (40 + tMW) * Ncpmg
    tScan_min = tStart // 4 if tStart // 4 > 0 else 1  # in [cycles]
    self.scan_t_start = tScan_min * 4

    tEnd = self.time_in_multiples_cycle_time(self.scan_t_end)
    tScan_max = tEnd // 4 if tEnd // 4 > 0 else 1  # in [cycles]
    if tScan_max < tScan_min + self.scan_t_dt // 4:
        tScan_max = tScan_min + self.scan_t_dt // 4

    self.scan_t_end = tScan_max * 4

    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = (tMW + tScan_max / 2 + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        tWait = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        # update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        # p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index

                    assign(tWait, val_vec_qua[idx_vec_qua[idx]])

                    with if_(Ncpmg > 0):
                        assign(t, tWait / (2 * Ncpmg) - (tMW / 2) // 4)

                        # signal
                    update_frequency("MW", 0)  # const I&Q
                    # play MW (I=1,Q=0) @ Pi/2
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)  # xPulse I = 0.5V, Q = zero
                    # wait t unit
                    with if_(Ncpmg == 0):
                        wait(tWait)

                    # "CPMG section" I=0, Q=1 @ Pi
                    with for_(m, 0, m < Ncpmg, m + 1):
                        wait(t)
                        # play MW
                        update_frequency("MW", 0)
                        play("yPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # yPulse I = zero, Q = 0.5V
                        # wait t unit
                        wait(t)
                    # align()

                    # play MW (I=1,Q=0) @ Pi/2
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)

                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser) // 4)
                    # measure signal
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    # wait Tmw + Twait
                    with if_(Ncpmg == 0):
                        wait(tWait + tMW // 4)
                    with if_(Ncpmg > 0):
                        wait(Ncpmg * (2 * t + tMW // 4) + tMW // 4)

                    # play laser
                    play("Turn_ON", "Laser", duration=(tLaser) // 4)
                    # Measure ref
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def Hahn_QUA_PGM(self):
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_res)
    fMW_res1 = fMW_res
    fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
    self.verify_insideQUA_FreqValues(fMW_2nd_res)
    fMW_res2 = fMW_2nd_res

    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # time scan vector
    tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

    # length and idx vector
    array_length = len(self.t_vec)
    # array_length = len(self.f_vec)                      # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + 2 * tRF + tScan_max + tLaser) * array_length * 2
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan
        t = declare(int)  # [cycles] time variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # # Shuffle parameters - freq
        # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
        # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
        # idx = declare(int)                                                          # index variable to sweep over all indexes

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    play("cw", "MW", duration=tMW // 4)
                    # play RF pi/2
                    align("MW", "RF")
                    play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play RF pi
                    play("const" * amp(p), "RF", duration=tRF // 4)
                    # Twait, note: t is already in cycles!
                    wait(t)
                    # play RF pi/2
                    play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    align("RF", "MW")
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # measure signal
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF (@resonance freq & pulsed time)
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # turn on laser to pump
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tPump // 4)
                    align()
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    play("cw", "MW", duration=tMW // 4)
                    # do not play RF
                    wait(2 * t + (2 * tRF) // 4)
                    # set MW frequency to resonance
                    update_frequency("MW", fMW_res2)
                    # play MW
                    play("cw", "MW", duration=tMW // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # Measure ref
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            # counts_st.buffer(len(self.f_vec)).average().save("counts")
            # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def NuclearSpinPolarization_pulsedODMR_QUA_PGM(self):  # NUCLEAR_POL_ESR
    # sequence parameters
    tMeasureProcess = self.MeasProcessTime
    tPump = self.time_in_multiples_cycle_time(self.Tpump)
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    tMW2 = self.t_mw2
    fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    fMW_res = 0 if fMW_res < 0 else fMW_res
    fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
    tRF = self.rf_pulse_time
    Npump = self.n_nuc_pump

    # frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # length and idx vector
    array_length = len(self.f_vec)  # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = ((tMW + tLaser) * (Npump + 2) + tRF * Npump) * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan

        n = declare(int)  # iteration variable
        m = declare(int)  # number of pumping iterations
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index

                    # signal
                    # polarize (@fMW_res @ fRF_res)
                    with for_(m, 0, m < Npump, m + 1):
                        # # set MW frequency to resonance
                        # update_frequency("MW", fMW_res)
                        # # play MW
                        # play("cw", "MW", duration=tMW // 4)
                        # # play RF (@resonance freq & pulsed time)
                        # align("MW", "RF")
                        # play("const" * amp(p), "RF", duration=tRF // 4)
                        # # turn on laser to polarize
                        # align("RF", "Laser")
                        # play("Turn_ON", "Laser", duration=tPump // 4)

                        self.QUA_Pump(t_pump=tPump, t_mw=tMW, t_rf=tRF, f_mw=fMW_res,
                                      f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=p,
                                      t_wait=self.tWait)
                    align()

                    # update MW frequency
                    update_frequency("MW", f)
                    # play MW
                    play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)
                    # play Laser
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # play Laser
                    align("MW", "Detector_OPD")
                    # measure signal
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    wait(tMW2 // 4)  # don't Play MW
                    # Play laser
                    play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                    # Measure ref
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def NuclearMR_QUA_PGM(self):  # v
    # time
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    tRF = self.rf_pulse_time
    pMW = self.mw_P_amp
    tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]

    # RF frequency scan vector
    f_min = (self.rf_freq + 0) * self.u.MHz  # [MHz],start of freq sweep
    f_max = (self.rf_freq + self.rf_freq_scan_range) * self.u.MHz  # [MHz], end of freq sweep
    df = self.rf_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # length and idx vector
    array_length = len(self.f_vec)  # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = (tMW * 2 + tRF + tLaser) * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        self.fMW_res = (self.mw_freq_resonance - self.mw_freq_resonance) * self.u.GHz  # Hz
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq_resonance) * self.u.GHz  # Hz

        f = declare(int)
        p = declare(fixed)  # fixed is similar to float 4bit.28bit

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)
        counts2 = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref2 = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal
        counts2_st = declare_stream()  # experiment signal
        counts_ref2_st = declare_stream()  # reference signal

        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index
                assign(counts_ref2[idx], 0)  # shuffle - assign new val from randon index
                assign(counts2[idx], 0)  # shuffle - assign new val from randon index

            # shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set RF freq
                    assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                    update_frequency("RF", f)

                    """reference 1"""
                    # play MW for time Tmw
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    update_frequency("MW", self.fMW_res)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # Don't play RF after MW just wait
                    wait(tRF // 4)
                    wait(tWait)
                    # play MW
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    align()

                    """Signal 1"""
                    # play MW for time Tmw
                    update_frequency("MW", self.fMW_res)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)

                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play RF after MW
                    align("MW", "RF")
                    play("const" * amp(p), "RF",
                         duration=tRF // 4)  # t already devide by four when creating the time vector
                    wait(tWait)
                    # play MW after RF
                    align("RF", "MW")
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    """reference 2"""
                    # play MW for time Tmw
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    update_frequency("MW", self.fMW_2nd_res)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # Don't play RF after MW just wait
                    wait(tRF // 4)
                    wait(tWait)
                    # play MW
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref2[idx_vec_qua[idx]], counts_ref2[idx_vec_qua[idx]] + counts_ref_tmp)
                    align()

                    """Signal 2"""
                    # play MW for time Tmw
                    update_frequency("MW", self.fMW_2nd_res)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)

                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play RF after MW
                    align("MW", "RF")
                    play("const" * amp(p), "RF",
                         duration=tRF // 4)  # t already devide by four when creating the time vector
                    wait(tWait)
                    # play MW after RF
                    align("RF", "MW")
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts2[idx_vec_qua[idx]], counts2[idx_vec_qua[idx]] + counts_tmp)
                    align()

                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length, idx + 1):
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)
                    save(counts2[idx], counts2_st)
                    save(counts_ref2[idx], counts_ref2_st)
            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            counts2_st.buffer(len(self.f_vec)).average().save("counts2")
            counts_ref2_st.buffer(len(self.f_vec)).average().save("counts_ref2")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def NuclearRABI_QUA_PGM(self):  # v

    self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
    self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
    self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    self.tMW = self.t_mw
    self.tMW2 = self.t_mw2
    self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
    # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    # fMW_res = 0 if fMW_res < 0 else fMW_res
    # self.fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
    # self.fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
    # self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
    self.fMW_res = (self.mw_freq_resonance - self.mw_freq_resonance) * self.u.GHz  # Hz
    self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq_resonance) * self.u.GHz  # Hz
    self.verify_insideQUA_FreqValues(self.fMW_res)
    self.tRF = self.rf_pulse_time
    self.Npump = self.n_nuc_pump
    # Pump parameters
    # tPump = self.time_in_multiples_cycle_time(self.Tpump)
    # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
    # fMW_res = 0 if fMW_res < 0 else fMW_res
    # fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
    # tRF = self.rf_pulse_time
    # Npump = self.n_nuc_pump

    # time
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW = self.t_mw
    # tRF = self.rf_pulse_time
    # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz

    # time scan vector
    tRabi_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tRabi_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tRabi_min, tRabi_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt / 10, dt)  # in [cycles]

    # indexes vector
    array_length = len(self.t_vec)
    idx_vec_ini = np.arange(0, array_length, 1)

    # tracking signal
    tSequencePeriod = (tMW * 2 + tRabi_max + tLaser + self.Twait * 1000) * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        t = declare(int)  # time variable which we change during scan
        p = declare(fixed)  # fixed is similar to float 4bit.28bit

        self.t_mw_qua = declare(int)
        assign(self.t_mw_qua, (self.t_mw / 2) // 4)

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number
        self.m = declare(int)  # number of pumping iterations
        self.t_wait = declare(int)  # [cycles] time variable which we change during scan
        self.Npump = self.n_nuc_pump
        assign(self.t_wait, self.Twait * 1000 // 4)

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        # Set RF frequency to resonance
        update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # updates RF frerquency
        p = self.rf_proportional_pwr  # p should be between 0 to 1

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)
                assign(counts[idx], 0)

            # Shuffle
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set new random Trf
                    assign(t, val_vec_qua[idx_vec_qua[idx]])

                    # polarize (@fMW_res @ fRF_res)
                    with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                        self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_res,
                                      f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp,
                                      p_rf=self.rf_proportional_pwr, t_wait=self.tWait)
                        # self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=0)#self.tWait)
                    align()

                    # Signal
                    # play MW for time Tmw
                    # update_frequency("MW", self.fMW_res)
                    # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)

                    update_frequency("MW", 0)
                    update_frequency("MW", self.fMW_2nd_res)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)

                    # play RF after MW
                    align("MW", "RF")
                    play("const" * amp(p), "RF",
                         duration=t)  # t already devide by four when creating the time vector
                    # play MW after RF
                    align("RF", "MW")
                    # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    # update_frequency("MW", self.fMW_2nd_res)
                    wait(self.t_wait)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    align()
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    align()

                    # reference
                    with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                        self.QUA_Pump(t_pump=self.tPump, t_mw=self.tMW, t_rf=self.tRF, f_mw=self.fMW_res,
                                      f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp,
                                      p_rf=self.rf_proportional_pwr, t_wait=self.tWait)
                        # self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=0)#self.tWait)
                    align()

                    # play MW for time Tmw
                    # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    # update_frequency("MW", self.fMW_2nd_res)
                    update_frequency("MW", 0)
                    update_frequency("MW", self.fMW_2nd_res)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # Don't play RF after MW just wait
                    wait(t)  # t already devide by four
                    wait(self.t_wait)
                    # play MW
                    # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                    # update_frequency("MW", self.fMW_2nd_res)
                    play("-xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    play("xPulse" * amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)
                    # play laser after MW
                    align("MW", "Laser")
                    align()
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    measure("readout", "Detector_OPD", None,
                            self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    align()
                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length, idx + 1):
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)
            save(tracking_signal, tracking_signal_st)

        with stream_processing():
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def PulsedODMR_QUA_PGM(self):
    # time
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
    tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)

    # MW frequency scan vector
    f_min = 0 * self.u.MHz  # start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
    df = self.mw_df * self.u.MHz  # freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

    # length and idx vector
    array_length = len(self.f_vec)  # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = (tMW2 + tLaser) * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_tmp2 = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # assign new frequency val from randon index
                    assign(f, val_vec_qua[idx_vec_qua[idx]])
                    update_frequency("MW", f)

                    # play MW for time Tmw
                    play("xPulse" * amp(self.mw_P_amp2), "MW",
                         duration=tMW2 // 4)  # tMW2 defines the Rabi time and length of pi pulse
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    if self.sum_counters_flag:
                        align("MW", "Detector2_OPD")
                    # measure("readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    # assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       sum_counters=self.sum_counters_flag)

                    align()

                    # don't play MW for time t
                    wait(tMW2 // 4)
                    # play laser after MW
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    # measure("readout", "Detector_OPD", None,
                    #         self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    # assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times_ref,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts_ref[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       sum_counters=self.sum_counters_flag)
                    # align()
                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # add one by one elements from counts (which is a vector) into counts_st
                    save(counts[idx], counts_st)  # here counts_st = counts[t]
                    save(counts_ref[idx], counts_ref_st)  # here counts_st = counts[t]

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def RABI_QUA_PGM(self):  # v
    # time
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
    tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)

    # MW parameters
    self.fMW_1st_res = 0  # (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
    self.verify_insideQUA_FreqValues(self.fMW_1st_res)
    self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq_resonance) * self.u.GHz  # Hz
    self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

    # time scan vector
    tRabi_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
    tRabi_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
    dt = self.scan_t_dt // 4  # in [cycles]
    self.t_vec = [i * 4 for i in range(tRabi_min, tRabi_max + 1, dt)]  # in [nsec], used to plot the graph
    self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt / 10, dt)  # in [cycles]

    # indexes vector
    array_length = len(self.t_vec)
    idx_vec_ini = np.arange(0, array_length, 1)

    # tracking signal
    tSequencePeriod = (tRabi_max + tLaser) * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        t = declare(int)  # time variable which we change during scan

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_tmp2 = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters - time
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes
        t_pad = declare(int)

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal
        # CheckIndexes_st = declare_stream()                      # stream iteration number - due to qua bug/issue

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)
                assign(counts[idx], 0)

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):  # range over Tmw
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set new random TmW
                    assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                    assign(t_pad, int(self.t_vec_ini[-1]) - t + 5)

                    wait(t_pad)  # pad zeros to make the total time between perp and meas constant
                    # play MW for time t
                    # update_frequency("MW", 0)
                    update_frequency("MW", self.fMW_1st_res)
                    if self.benchmark_switch_flag:
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=t / 2)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=t / 2)
                    else:
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=t)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                    # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                    # update_frequency("MW", self.fMW_2nd_res)
                    # ## play("xPulse"*amp(self.mw_P_amp), "MW", duration=t)
                    # play("xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                    # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    if self.sum_counters_flag:
                        align("Detector2_OPD", "Detector_OPD")
                    # measure("min_readout_pulse", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    # assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)

                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       measure_waveform="min_readout_pulse",
                                                       sum_counters=self.sum_counters_flag)

                    align()
                    # don't play MW for the maximal mw pulsae duration
                    wait(int(self.t_vec_ini[-1]) + 5)
                    # play laser after MW
                    align("MW", "Laser")
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    # play measure after MW
                    align("MW", "Detector_OPD")
                    if self.sum_counters_flag:
                        align("MW", "Detector2_OPD")
                    wait(12, "Detector_OPD")
                    if self.sum_counters_flag:
                        wait(12, "Detector_OPD")
                    # measure("min_readout_pulse", "Detector_OPD", None, self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    # assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times_ref,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts_ref[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       measure_waveform="min_readout_pulse",
                                                       sum_counters=self.sum_counters_flag)
                    align()
                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.t_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def ODMR_CW_QUA_PGM(self):  # CW_ODMR
    # time
    tMeasueProcess = self.MeasProcessTime
    tLaser = self.time_in_multiples_cycle_time(self.Tcounter + self.Tsettle + tMeasueProcess)
    tMW = tLaser
    tMeasure = self.time_in_multiples_cycle_time(self.Tcounter)
    tSettle = self.time_in_multiples_cycle_time(self.Tsettle)

    # MW frequency scan vector
    f_min = 0 * self.u.MHz  # [Hz], start of freq sweep
    f_max = self.mw_freq_scan_range * self.u.MHz  # [Hz] end of freq sweep
    df = self.mw_df * self.u.MHz  # [Hz], freq step
    self.f_vec = np.arange(f_min, f_max + df / 10, df)  # [Hz], frequencies vector

    # length and idx vector
    array_length = len(self.f_vec)  # frquencies vector size
    idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

    # tracking signal
    tSequencePeriod = tLaser * 2 * array_length
    tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
    tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
    tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // tMeasure
    trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
        tSequencePeriod) > 1 else 1

    with program() as self.quaPGM:
        # QUA program parameters
        times = declare(int, size=100)
        times_ref = declare(int, size=100)

        f = declare(int)  # frequency variable which we change during scan

        n = declare(int)  # iteration variable
        n_st = declare_stream()  # stream iteration number

        counts_tmp = declare(int)  # temporary variable for number of counts
        counts_tmp2 = declare(int)  # temporary variable for number of counts
        counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

        runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
        track_idx = declare(int, value=0)  # iteration variable
        tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
        tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
        tracking_signal_st = declare_stream()
        sequenceState = declare(int, value=0)

        counts = declare(int, size=array_length)  # experiment signal (vector)
        counts_ref = declare(int, size=array_length)  # reference signal (vector)

        # Shuffle parameters
        val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
        idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
        idx = declare(int)  # index variable to sweep over all indexes

        # stream parameters
        counts_st = declare_stream()  # experiment signal
        counts_ref_st = declare_stream()  # reference signal

        with for_(n, 0, n < self.n_avg, n + 1):
            # reset
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                assign(counts[idx], 0)  # shuffle - assign new val from randon index

            # shuffle index
            with if_(self.bEnableShuffle):
                self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

            # sequence
            with for_(idx, 0, idx < array_length, idx + 1):
                assign(sequenceState, IO1)
                with if_(sequenceState == 0):
                    # set new MW frequency
                    assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                    update_frequency("MW", f)  # update frequency

                    # Signal
                    play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    wait(tSettle // 4, "Detector_OPD")
                    # measure("min_readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure, counts_tmp))
                    # assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       sum_counters=self.sum_counters_flag)
                    align()

                    # reference sequence
                    # don't play MW
                    play("Turn_ON", "Laser", duration=tLaser // 4)
                    wait(tSettle // 4, "Detector_OPD")
                    # measure("min_readout", "Detector_OPD", None, self.time_tagging_fn(times_ref, tMeasure, counts_ref_tmp))
                    # assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    self.QUA_measure_with_sum_counters("Detector_OPD",
                                                       "Detector2_OPD",
                                                       times_ref,
                                                       tMeasure,
                                                       counts_tmp,
                                                       counts_ref[idx_vec_qua[idx]],
                                                       counts_tmp2,
                                                       sum_counters=self.sum_counters_flag)
                    align()
                with else_():
                    assign(tracking_signal, 0)
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, tMeasure, tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    align()

            # tracking signal
            with if_(runTracking):
                assign(track_idx, track_idx + 1)  # step up tracking counter
                with if_(track_idx > trackingNumRepeatition - 1):
                    assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                    # reference sequence
                    with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                        play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                        measure("min_readout", "Detector_OPD", None,
                                self.time_tagging_fn(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                     tracking_signal_tmp))
                        assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                    assign(track_idx, 0)

            # stream
            with if_(sequenceState == 0):
                with for_(idx, 0, idx < array_length,
                          idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                    save(counts[idx], counts_st)
                    save(counts_ref[idx], counts_ref_st)

            save(n, n_st)  # save number of iteration inside for_loop
            save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

        with stream_processing():
            counts_st.buffer(len(self.f_vec)).average().save("counts")
            counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
            n_st.save("iteration")
            tracking_signal_st.save("tracking_ref")

    self.qm, self.job = self.QUA_execute()

def TrackingCounterSignal_QUA_PGM(self):  # obsolete. keep in order to learn on how to swithc between two PGM
    # integration time for single loop
    tTrackingSignaIntegrationTime_nsec = self.tTrackingSignaIntegrationTime * 1e6
    tMeasure = self.time_in_multiples_cycle_time(
        50000 if tTrackingSignaIntegrationTime_nsec > 50000 else tTrackingSignaIntegrationTime_nsec)  # 50000 [nsec]
    # number of repeatitions
    n_count = tTrackingSignaIntegrationTime_nsec // tMeasure if tTrackingSignaIntegrationTime_nsec // tMeasure > 1 else 1
    # total integration time
    self.tTrackingSignaIntegrationTime = n_count * tMeasure / 1e6  # [msec]

    with program() as self.quaTrackingPGM:
        times = declare(int, size=100)
        n = declare(int)
        counts_tracking = declare(int)
        total_counts_tracking = declare(int, value=0)
        counts_tracking_st = declare_stream()  # stream for counts

        pause()
        with infinite_loop_():
            assign(total_counts_tracking, 0)
            with for_(n, 0, n < n_count, n + 1):  # number of averages / total integation time
                play("Turn_ON", "Laser", duration=tMeasure // 4)
                measure("min_readout", "Detector_OPD", None, self.time_tagging_fn(times, tMeasure), counts_tracking)
                assign(total_counts_tracking, total_counts_tracking + counts_tracking)

            save(total_counts_tracking, counts_tracking_st)

        with stream_processing():
            counts_tracking_st.save("counts_tracking")

    self.qmTracking, self.job_Tracking = self.QUA_execute(closeQM=False, quaPGM=self.quaTrackingPGM)

def counter_QUA_PGM(self, n_count=1):
    if self.is_green:
        self.laser_type = "Laser"
    else:
        self.laser_type = "Resonant_Laser"

    with program() as self.quaPGM:
        # self.MeasProcessTime = 510 # [nsec] - delay due to OPX measure process time
        # self.Tcounter -= self.MeasProcessTime
        self.times = declare(int, size=1000)
        self.times_ref = declare(int, size=1000)
        self.counts = declare(int)  # apd1
        self.counts_ref = declare(int)  # apd2
        self.total_counts = declare(int, value=0)  # apd1
        self.total_counts2 = declare(int, value=0)  # apd1
        self.n = declare(int)  #
        self.counts_st = declare_stream()
        self.counts_ref_st = declare_stream()  # stream for counts
        self.n_st = declare_stream()  # stream for number of iterations
        pump_pulse = declare(bool, value=False)
        scan_freq_experiment = self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN

        with infinite_loop_():
            if scan_freq_experiment:
                assign(pump_pulse, IO2)
                with if_(pump_pulse):
                    play("Turn_ON", "Laser", duration=int(self.Tpump * self.u.ns // 4))  #
                    wait(250)
                    align()
                    assign(IO2, False)
            with for_(self.n, 0, self.n < n_count, self.n + 1):  # number of averages / total integation time
                if scan_freq_experiment:
                    play("Turn_ON", "Resonant_Laser", duration=int(self.Tcounter * self.u.ns // 4))  #
                else:
                    play("Turn_ON", self.laser_type, duration=int(self.Tcounter * self.u.ns // 4))  #
                measure("min_readout", "Detector_OPD", None,
                        self.time_tagging_fn(self.times, int(self.Tcounter * self.u.ns), self.counts))
                # measure("min_readout", "Detector2_OPD", None, self.time_tagging_fn(self.times_ref, int(self.Tcounter * self.u.ns), self.counts_ref))
                measure("min_readout", "Detector2_OPD", None,
                        self.time_tagging_fn(self.times_ref, int(self.Tcounter * self.u.ns), self.counts_ref))

                assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language  # align()
                if self.sum_counters_flag:
                    assign(self.total_counts, self.total_counts + self.counts_ref)
                else:
                    assign(self.total_counts2, self.total_counts2 + self.counts_ref)
            save(self.total_counts, self.counts_st)
            save(self.total_counts2, self.counts_ref_st)  # only to keep on convention
            assign(self.total_counts, 0)
            assign(self.total_counts2, 0)
            # save(self.n, self.n_st)  # save number of iteration inside for_loop

        with stream_processing():
            self.counts_st.with_timestamps().save("counts")
            self.counts_ref_st.with_timestamps().save("counts_ref")
            # self.counts_st.with_timestamps().save("counts_reg")
            # self.n_st.save("iteration")

    self.qm, self.job = self.QUA_execute()

def awg_sync_counter_QUA_PGM(self, n_count=1):
    if self.is_green:
        self.laser_type = "Laser"
    else:
        self.laser_type = "Resonant_Laser"

    with program() as self.quaPGM:
        # self.MeasProcessTime = 510 # [nsec] - delay due to OPX measure process time
        # self.Tcounter -= self.MeasProcessTime
        self.times = declare(int, size=1000)
        self.times_ref = declare(int, size=1000)
        self.counts = declare(int)  # apd1
        self.counts_ref = declare(int)  # apd2
        self.total_counts = declare(int, value=0)  # apd1
        self.total_counts2 = declare(int, value=0)  # apd1
        self.n = declare(int)  #
        self.counts_st = declare_stream()
        self.counts_ref_st = declare_stream()  # stream for counts
        self.n_st = declare_stream()  # stream for number of iterations

        with infinite_loop_():
            play("Turn_ON", configs.QUAConfigBase.Elements.AWG_TRigger.value, duration=int(1000 * self.u.ns // 4))  #
            wait(1000 // 4)
            align()
            with for_(self.n, 0, self.n < self.total_integration_time * self.u.ms,
                      self.n + self.Tcounter):  # number of averages / total integation time
                play("Turn_ON", self.laser_type, duration=int(self.Tcounter * self.u.ns // 4))  #
                measure("min_readout", "Detector_OPD", None,
                        self.time_tagging_fn(self.times, int(self.Tcounter * self.u.ns), self.counts))

                if self.sum_counters_flag:
                    measure("min_readout", "Detector2_OPD", None,
                            self.time_tagging_fn(self.times, int(self.Tcounter * self.u.ns), self.counts_ref))
                    assign(self.total_counts,
                           self.total_counts + self.counts_ref)  # assign is equal in qua language  # align()
                assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language  # align()
            save(self.total_counts, self.counts_st)
            assign(self.total_counts, 0)

        with stream_processing():
            # TODO: Change buffer size to not be hardcoded
            # self.counts_st.buffer(400).average().save("counts")
            self.counts_st.buffer(400).save("counts")

    self.qm, self.job = self.QUA_execute()

def MeasureByTrigger_QUA_PGM(self, num_bins_per_measurement: int = 1, num_measurement_per_array: int = 1,
                             triggerThreshold: int = 1, play_element=configs.QUAConfigBase.Elements.LASER.value):
    # MeasureByTrigger_QUA_PGM function measures counts.
    # It will run a single measurement every trigger.
    # each measurement will be append to buffer.
    delay = 25000  # 2usec
    pulsesTriggerDelay = 50000 // 4  # 50 [usec]
    laser_on_duration = int((self.Tcounter + 2 * delay) * self.u.ns // 4)
    single_integration_time = int(self.Tcounter * self.u.ns)
    # smaract_ttl_duration = int(self.smaract_ttl_duration * self.u.ms // 4)

    ini_vec = [0 for i in range(num_measurement_per_array)]

    with program() as self.quaPGM:
        times = declare(int, size=1000)  # maximum number of counts allowed per measurements
        times2 = declare(int, size=1000)  # maximum number of counts allowed per measurements
        counts = declare(int, value=0)  # apd1
        counts2 = declare(int, value=0)  # apd1
        total_counts = declare(int, value=ini_vec)  # apd1
        n = declare(int)  #
        i = declare(int, value=0)  #
        meas_idx = declare(int, value=0)
        counts_st = declare_stream()
        meas_idx_st = declare_stream()

        # pulsesTriggerDelay = 5000000 // 4
        sequenceState = declare(int, value=0)
        triggerTh = declare(int, value=triggerThreshold)
        assign(IO2, 0)

        with infinite_loop_():
            # wait_for_SW_trigger("Laser")
            assign(sequenceState, IO2)
            # wait(pulsesTriggerDelay)

            with if_(sequenceState == self.ScanTrigger):
                with for_(n, 0, n < num_bins_per_measurement, n + 1):
                    play("Turn_ON", "Laser", duration=laser_on_duration)
                    wait(delay // 4, "Detector_OPD")
                    wait(delay // 4, "Detector2_OPD")
                    # todo: change to general measure function
                    measure("min_readout", "Detector_OPD", None,
                            self.time_tagging_fn(times, single_integration_time, counts))

                    # with if_(self.sum_counters_flag == True):
                    if self.sum_counters_flag:
                        measure("min_readout", "Detector2_OPD", None,
                                self.time_tagging_fn(times2, single_integration_time, counts2))
                        assign(total_counts[i], total_counts[i] + counts2)

                    assign(total_counts[i], total_counts[i] + counts)

                # wait(pulsesTriggerDelay)
                assign(meas_idx, meas_idx + 1)
                assign(i, i + 1)

                with if_(i == num_measurement_per_array):
                    save(meas_idx, meas_idx_st)

                    with for_(i, 0, i < num_measurement_per_array, i + 1):
                        save(total_counts[i], counts_st)
                        assign(total_counts[i], 0)
                    assign(i, 0)

                assign(IO2, self.ScanTrigger - 1)

        with stream_processing():
            meas_idx_st.save("meas_idx_scanLine")
            counts_st.buffer(num_measurement_per_array).save("counts_scanLine")

    self.qm, self.job = self.QUA_execute()

def MeasurePLE_QUA_PGM(self, trigger_threshold: int = 1):
    # MeasureByTrigger_QUA_PGM function measures counts.
    # It will run a single measurement every trigger.
    # each measurement will be append to buffer.
    laser_on_duration = int(self.total_integration_time * self.u.ms // 4)
    single_integration_time = int(self.Tcounter * self.u.ns)
    init_pulse_time = self.Tpump * self.u.ns // 4
    tracking_pulse_time = int(5 * self.u.ms // 4)
    tracking_measure_time = int(self.Tcounter * self.u.ns)
    num_tracking_signal_loops = int((5 * self.u.ms / int(self.Tcounter * self.u.ns)))
    t_wait_after_init = int(500 * self.u.ns // 4)
    n_count = int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns)

    with program() as self.quaPGM:
        times = declare(int, size=1000)  # maximum number of counts allowed per measurements
        counts = declare(int)  # apd1
        total_counts = declare(int, value=0)  # apd1
        n = declare(int)  #
        meas_idx = declare(int, value=0)
        counts_st = declare_stream()
        counts_ref_st = declare_stream()
        meas_idx_st = declare_stream()

        sequence_state = declare(int, value=0)
        should_we_track = declare(int, value=0)
        trigger_threshold = declare(int, value=trigger_threshold)
        assign(IO2, 0)
        assign(IO1, 0)

        with infinite_loop_():
            # wait_for_trigger("Laser")
            assign(sequence_state, IO2)
            with if_((sequence_state + 1 > trigger_threshold) & (sequence_state - 1 < trigger_threshold)):
                assign(IO2, 0)
                assign(sequence_state, 0)
                assign(total_counts, 0)
                align()
                # Tracking pulse
                play("Turn_ON", configs.QUAConfigBase.Elements.LASER.value, duration=tracking_pulse_time)
                with for_(n, 0, n < num_tracking_signal_loops, n + 1):
                    measure("min_readout", "Detector_OPD", None,
                            self.time_tagging_fn(times, tracking_measure_time, counts))
                    assign(total_counts, total_counts + counts)
                save(total_counts, counts_ref_st)
                align()

                assign(total_counts, 0)
                # assign(should_we_track, IO1)
                with if_(should_we_track == 0):
                    with for_(n, 0, n < self.n_avg, n + 1):
                        wait(500 // 4)
                        wait(t_wait_after_init - 28 // 4)
                        play("Turn_ON", configs.QUAConfigBase.Elements.LASER.value, duration=init_pulse_time)
                        wait(t_wait_after_init - 28 // 4)
                        align()
                        # we have 28ns delay between measure command and actual measure start due to tof delay
                        with for_(n, 0, n < n_count, n + 1):
                            play("Turn_ON", configs.QUAConfigBase.Elements.RESONANT_LASER.value,
                                 duration=single_integration_time // 4)
                            measure("readout", "Detector_OPD", None,
                                    self.time_tagging_fn(times, single_integration_time, counts))
                            assign(total_counts, total_counts + counts)
                    save(total_counts, counts_st)
                    assign(meas_idx, meas_idx + 1)
                    save(meas_idx, meas_idx_st)

        with stream_processing():
            meas_idx_st.save("meas_idx_scanLine")
            counts_st.save("counts_scanLine")
            counts_ref_st.save("counts_Ref")  # fix
    self.qm, self.job = self.QUA_execute()
