"""
A Rabi experiment sweeping the duration of the MW pulse.
"""
from qm import QuantumMachinesManager
from qm.qua import *
import matplotlib
matplotlib.use('TkAgg')
from qm import SimulationConfig
import matplotlib.pyplot as plt
from configuration import *

###################
# The QUA program #
###################

t_min = 16 // 4  # in clock cycles units (must be >= 4)
t_max = 1000 // 4  # in clock cycles units
dt = 4 // 4  # in clock cycles units
t_vec = np.arange(t_min, t_max + 0.1, dt)  # +0.1 to include t_max in array
n_avg = 1e6
# t_vec_rand  = [4, 12, 7, 8, 12]
with program() as time_rabi:
    counts = declare(int)  # variable for number of counts
    counts_st = declare_stream()  # stream for counts
    times = declare(int, size=100)
    counts_ref = declare(int)  # variable for number of counts
    counts_ref_st = declare_stream()  # stream for counts
    times_ref = declare(int, size=100)
    # t_vec = declare(int, value= t_vec_rand)
    t = declare(int)  # variable to sweep over in time
    n = declare(int)  # variable to for_loop
    n_st = declare_stream()  # stream to save iterations

    play("laser_ON", "AOM")
    wait(750, "AOM")
    with for_(n, 0, n < n_avg, n + 1):
        with for_(t, t_min, t <= t_max, t + dt):
            play("pi", "NV", duration=t)  # pulse of varied lengths
            wait(50, 'NV')
            align()
            play("laser_ON", "AOM")  # 3 microseconds
            wait(20, 'SPCM_OPD')
            measure("readout", "SPCM_OPD", None, time_tagging.digital(times, meas_len, counts))  # 500 ns
            wait(750)

            align()

            play("pi"*amp(0), "NV", duration=t)  # pulse of varied lengths
            wait(50, 'NV')
            align()
            play("laser_ON", "AOM")  # 3 microseconds
            wait(20, 'SPCM_OPD')
            measure("readout", "SPCM_OPD", None, time_tagging.digital(times_ref, meas_len, counts_ref))  # 500 ns

            save(counts, counts_st)  # save counts
            save(counts_ref, counts_ref_st)  # save counts
            wait(750)

        save(n, n_st)  # save number of iteration inside for_loop

    with stream_processing():
        (counts_st).buffer(len(t_vec)).average().save("counts")
        (counts_ref_st).buffer(len(t_vec)).average().save("counts_ref")
        n_st.save("iteration")

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(opx_ip, opx_port)  # remove octave flag if not using it

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=28000)
    job = qmm.simulate(config, time_rabi, simulation_config)
    job.get_simulated_samples().con1.plot()
else:
    qm = qmm.open_qm(config)
    # execute QUA program
    job = qm.execute(time_rabi)
    # Get results from QUA program
    results = fetching_tool(job, data_list=["counts", "counts_ref", "iteration"], mode="live")
    # Live plotting
    fig = plt.figure()
    interrupt_on_close(fig, job)  # Interrupts the job when closing the figure

    while results.is_processing():
        # Fetch results
        counts, counts_ref, iteration = results.fetch_all()
        # Progress bar
        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        # Plot data
        plt.cla()
        plt.plot(4 * t_vec, counts / 1000 / (meas_len / u.s))
        plt.plot(4 * t_vec, counts_ref / 1000 / (meas_len / u.s))
        plt.xlabel("Tau [ns]")
        plt.ylabel("Intensity [kcps]")
        plt.title("Time Rabi")
        plt.pause(0.1)

    plt.show()
