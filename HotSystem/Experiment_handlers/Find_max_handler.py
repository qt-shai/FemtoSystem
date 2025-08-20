import time
import numpy as np

def FindMaxSignal(self):
    self.track_numberOfPoints = self.N_tracking_search  # number of point to scan for each axis
    self.trackStep = 30000  # [pm], step size
    initialShift = int(self.trackStep * self.track_numberOfPoints / 2)
    # self.numberOfRefPoints = 1000

    self.track_X = []
    self.coordinate = []

    for ch in range(3):
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ch{ch} !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self.track_X = []
        self.coordinate = []

        if (ch == 2):
            self.trackStep = 50000  # [pm]
            initialShift = int(self.trackStep * self.track_numberOfPoints / 2)

        # goto start location
        self.positioner.MoveRelative(ch, -1 * initialShift)
        time.sleep(0.01)
        while not (self.positioner.ReadIsInPosition(ch)):
            time.sleep(0.01)
        # print(f"is in position = {self.positioner.ReadIsInPosition(ch)}")
        self.positioner.GetPosition()
        self.absPosunits = self.positioner.AxesPosUnits[ch]
        self.absPos = self.positioner.AxesPositions[ch]

        for i in range(self.track_numberOfPoints):
            # grab/fetch new data from stream
            time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.001)  # [sec]
            self.GlobalFetchData()
            # while (last_iteration == self.iteration):  # wait for new data
            time.sleep(0.01)  # according to OS priorities
            self.GlobalFetchData()
            self.lock.acquire()
            current_signal = self.counter_Signal[0]
            self.lock.release()

            # Log data
            self.coordinate.append(i * self.trackStep + self.absPos)  # Log axis position
            self.track_X.append(current_signal)  # Loa signal to array

            # move to next location (relative move)
            self.positioner.MoveRelative(ch, self.trackStep)
            res = self.positioner.ReadIsInPosition(ch)
            while not (res):
                res = self.positioner.ReadIsInPosition(ch)  # print(f"i = {i}, ch = {ch}, is in position = {res}")

        print(f"ch={ch}:")
        coords_str = ", ".join(f"{c * 1e-6: .2f}" for c in self.coordinate)
        print(f"{coords_str}")
        intensity_vals = ", ".join(f"{v: .0f}" for v in self.track_X)
        print(f"{intensity_vals}")

        # find max signal
        maxPos = self.coordinate[self.track_X.index(max(self.track_X))]
        print(f"maxPos={maxPos * 1e-6:.1f}")

        # move to max signal position
        self.positioner.MoveABSOLUTE(ch, maxPos)
        time.sleep(0.01)

        print("Is it good?")

    # update new ref signal
    self.refSignal = max(self.track_X)
    print(f"new ref Signal = {self.refSignal}")

    # # get new val for comparison
    # time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.001 + 0.1)  # [sec]
    # self.GlobalFetchData()
    # print(f"self.tracking_ref = {self.tracking_ref}")

    # shift back tp experiment sequence
    self.qm.set_io1_value(0)
    time.sleep(0.1)

def FindFocus(self):
    """Scan channel2 (Z) to find the position of maximum signal and move there."""
    # number of points to scan on each side
    self.track_numberOfPoints = self.N_tracking_search * 5
    # fixed step size for Z in pm
    self.trackStep = 50000
    # start offset so scan is centered
    initialShift = int(self.trackStep * self.track_numberOfPoints / 2)

    # prepare storage
    ch = 2
    self.track_X = []
    self.coordinate = []

    # 1) move to start of scan range
    print(f"--- FindFocus: scanning channel {ch} ---")
    self.positioner.MoveRelative(ch, -initialShift)
    time.sleep(0.01)
    while not self.positioner.ReadIsInPosition(ch):
        time.sleep(0.01)

    # record absolute start position
    self.positioner.GetPosition()
    self.absPos = self.positioner.AxesPositions[ch]

    # 2) perform the scan
    for i in range(self.track_numberOfPoints):
        # wait for signal integration
        time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.001)
        # fetch twice to ensure new data
        self.GlobalFetchData()
        time.sleep(0.01)
        self.GlobalFetchData()

        # grab current signal
        with self.lock:
            current_signal = self.counter_Signal[0]

        # log position and signal
        pos = self.absPos + i * self.trackStep
        self.coordinate.append(pos)
        self.track_X.append(current_signal)

        # step to next
        self.positioner.MoveRelative(ch, self.trackStep)
        while not self.positioner.ReadIsInPosition(ch):
            time.sleep(0.005)

    # 3) report raw arrays
    coords_um = ", ".join(f"{c * 1e-6:.2f}" for c in self.coordinate)
    sig_vals = ", ".join(f"{v:.0f}" for v in self.track_X)
    print(f"Positions (µm): {coords_um}")
    print(f"Signals      : {sig_vals}")

    # 4) find max and go there
    idx_max = int(np.argmax(self.track_X))
    maxPos = self.coordinate[idx_max]
    print(f"Max signal at {maxPos * 1e-6:.2f}µm -> moving there")
    self.positioner.MoveABSOLUTE(ch, maxPos)
    time.sleep(0.01)

    # 5) update reference signal
    self.refSignal = self.track_X[idx_max]
    print(f"New reference signal = {self.refSignal:.2f}")

    # 6) return QM I/O to idle
    self.qm.set_io1_value(0)
    time.sleep(0.1)

def Find_max_signal_by_keysight_offset(self):
    """
    Sweep the Keysight AWG DC‐offset around its current value
    and find the offset that produces the maximum measured signal.
    """
    # 1) Determine channel
    ch = self.awg.channel

    # 2) Build sweep parameters
    self.track_numberOfPoints = self.N_tracking_search
    num_points = self.track_numberOfPoints  # e.g. 21
    step_size = 0.1  # volts per step (tweak as needed)
    center_off = self.awg.get_current_voltage(ch)
    half_span = step_size * (num_points // 2)
    offsets = [center_off - half_span + i * step_size
               for i in range(num_points)]

    # 3) Sweep and record
    signals = []
    for off in offsets:
        # set offset and wait for AWG + measurement to settle
        self.awg.set_offset(off, channel=ch)
        time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.01)

        # fetch your signal (using your existing fetch routine)
        self.GlobalFetchData()
        time.sleep(0.01)
        self.GlobalFetchData()
        current_signal = self.counter_Signal[0]

        signals.append(current_signal)
        print(f"Offset {off:.3f}V → Signal {current_signal:.0f}")

    # 4) Find the best offset
    best_idx = signals.index(max(signals))
    best_off = offsets[best_idx]
    best_sig = signals[best_idx]
    print(f"Max signal {best_sig:.0f} at offset {best_off:.3f} V")

    # 5) Move AWG back to best offset
    self.awg.set_offset(best_off, channel=ch)
    time.sleep(0.01)

    # 6) Update your reference value if you use one
    self.refSignal = best_sig
    print(f"Reference signal updated to {self.refSignal:.0f}")

def FindMaxSignal_atto_positioner_and_scanner(self):
    """
    Find the peak intensity by optimizing offset voltages:
    - X and Y axes are controlled by the atto_scanner.
    - Z axis is controlled by the atto_positioner.
    """
    print('Start looking for peak intensity using atto_positioner_and_scanner')

    # Move and read functions for mixed axes control
    def move_axes(channel: int, position: float):
        """
        Set offset voltage for the corresponding axis.
        """
        if channel in [0, 1]:  # X and Y axes: atto_scanner
            self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
        # elif channel == 2:  # Z axis: atto_positioner
        #     self.HW.atto_positioner.set_control_fix_output_voltage(self.HW.atto_positioner.channels[channel],
        #                                                            int(position))

    def get_positions():
        """
        Get current positions for all three axes.
        """
        x = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[0])  # X axis
        y = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[1])  # Y axis
        # z = self.HW.atto_positioner.get_control_fix_output_voltage(2)  # Z axis
        # return x, y, z
        return x, y

    # Example scan radii for each axis
    # tracking_scan_radius = [2.5, 2.5, 10000]
    tracking_scan_radius = [5, 5]

    initial_guess = get_positions()
    bounds = self.calculate_tracking_bounds(initial_guess, tracking_scan_radius)

    # Call the generalized find_max_signal function
    x_opt, y_opt, z_opt, intensity = find_max_signal(
        move_abs_fn=move_axes,
        read_in_pos_fn=lambda ch: (time.sleep(30e-3), True)[1],  # Ensure move has settled
        get_positions_fn=get_positions,
        fetch_data_fn=self.GlobalFetchData,  # Function to fetch new data
        get_signal_fn=lambda: self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref,
        # Signal to maximize
        bounds=bounds,
        method=OptimizerMethod.SEQUENTIAL,
        initial_guess=initial_guess,
        max_iter=30,
        use_coarse_scan=True
    )

    # Reset the output state or finalize settings
    self.qm.set_io1_value(0)

    if z_opt:
        print(
            f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV, z={z_opt:.2f} mV with intensity={intensity:.4f}")
    else:
        print(f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV with intensity={intensity:.4f}")

def FindMaxSignal_atto_positioner(self):
    print('Start looking for peak intensity using atto_positioner')
    initial_position = [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in
                        self.HW.atto_positioner.channels]

    bounds = ((self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
              (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
              (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max))

    # Now we call our generalized FindMaxSignal function with these parameters

    x_opt, y_opt, z_opt, intensity = find_max_signal(
        move_abs_fn=self.HW.atto_positioner.set_control_fix_output_voltage,
        read_in_pos_fn=lambda ch: (time.sleep(30e-3), True)[1],
        get_positions_fn=lambda: [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in
                                  self.HW.atto_positioner.channels],
        fetch_data_fn=self.GlobalFetchData,
        get_signal_fn=lambda: self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref,
        bounds=bounds,
        method=OptimizerMethod.SEQUENTIAL,
        initial_guess=initial_position,
        max_iter=30,
        use_coarse_scan=True
    )

    time.sleep(0.1)
    self.GlobalFetchData()

    self.refSignal = self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref
    print(f"new ref Signal = {self.refSignal}")

    self.qm.set_io1_value(0)
    time.sleep(0.1)

    print(
        f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV, z={z_opt:.2f} mV with intensity={intensity:.4f}")

def MoveToPeakIntensity(self):
    print('Start looking for peak intensity')
    if self.bEnableSignalIntensityCorrection or self.survey:
        # print(f"self.HW.atto_scanner is {self.HW.atto_scanner}")
        # print(f"self.HW.atto_positioner is {self.HW.atto_positioner}")
        if self.HW.atto_scanner or self.HW.atto_positioner:
            print("Working in Atto system")
            self.MAxSignalTh = threading.Thread(target=self.tracking_function)
        else:
            self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
        self.MAxSignalTh.start()

def SearchPeakIntensity(self):
    if self.bEnableSignalIntensityCorrection:
        if (self.refSignal == 0) and (not (self.MAxSignalTh.is_alive())):
            self.refSignal = self.tracking_ref  # round(sum(self.Y_Last_ref) / len(self.Y_Last_ref))
        elif (self.refSignal * self.TrackingThreshold > self.tracking_ref) and (not (self.MAxSignalTh.is_alive())):
            self.qm.set_io1_value(1)  # shift to reference only
            if self.system_name == SystemType.ATTO.value:
                self.MAxSignalTh = threading.Thread(target=self.tracking_function)
            else:
                self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
            self.MAxSignalTh.start()
        elif (not (self.MAxSignalTh.is_alive())):
            self.refSignal = self.refSignal if self.refSignal > self.tracking_ref else self.tracking_ref

def calculate_tracking_bounds(self, initial_guess, scan_radius):
    # Check if initial_guess is XY (2 elements) or XYZ (3 elements)
    if len(initial_guess) == 2:
        # For XY case, z_guess and scan_radius for z are not used
        x_guess, y_guess = initial_guess
        z_guess = 0  # Default to 0 for z in XY mode
        scan_radius.append(0)  # Append 0 to the scan_radius for z-axis (not used)
    elif len(initial_guess) == 3:
        # For XYZ case, all values are used
        x_guess, y_guess, z_guess = initial_guess
    else:
        raise ValueError("initial_guess must have either 2 (XY) or 3 (XYZ) elements.")

    # Clip around each axis with respective scan radii
    x_bounds = (
        np.clip(x_guess - scan_radius[0], self.HW.atto_scanner.offset_voltage_min,
                self.HW.atto_scanner.offset_voltage_max),
        np.clip(x_guess + scan_radius[0], self.HW.atto_scanner.offset_voltage_min,
                self.HW.atto_scanner.offset_voltage_max),
    )
    y_bounds = (
        np.clip(y_guess - scan_radius[1], self.HW.atto_scanner.offset_voltage_min,
                self.HW.atto_scanner.offset_voltage_max),
        np.clip(y_guess + scan_radius[1], self.HW.atto_scanner.offset_voltage_min,
                self.HW.atto_scanner.offset_voltage_max),
    )
    # Only include z_bounds if it's an XYZ case
    if len(initial_guess) == 3:
        z_bounds = (
            np.clip(z_guess - scan_radius[2], self.HW.atto_positioner.fix_output_voltage_min,
                    self.HW.atto_positioner.fix_output_voltage_max),
            np.clip(z_guess + scan_radius[2], self.HW.atto_positioner.fix_output_voltage_min,
                    self.HW.atto_positioner.fix_output_voltage_max),
        )
        bounds = (x_bounds, y_bounds, z_bounds)
    else:
        bounds = (x_bounds, y_bounds)

    print(f"Bounds are: {bounds}")
    return bounds

def fetch_peak_intensity(self, integration_time):
    self.qm.set_io2_value(self.ScanTrigger)  # should trigger measurement by QUA io
    time.sleep(integration_time * 1e-3 + 1e-3)  # wait for measurement do occur

    if self.counts_handle.is_processing():
        # print('Waiting for QUA counts')
        self.counts_handle.wait_for_values(1)
        time.sleep(0.1)
        counts = self.counts_handle.fetch_all()
        # print(f"counts.size =  {counts.size}")

        self.qmm.clear_all_job_results()
        return counts

