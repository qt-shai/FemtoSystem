"""
A Rabi experiment sweeping the duration of the MW pulse.
"""
import numpy as np
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
from qm import SimulationConfig
import matplotlib.pyplot as plt
from configuration import *

###################
# The QUA program #
###################

t_min = 100 // 4  # in clock cycles units (must be >= 4)
t_max = 1000 // 4  # in clock cycles units
dt = 100 // 4  # in clock cycles units
t_vec = np.arange(t_min, t_max + 0.1, dt)  # +0.1 to include t_max in array
array_length = len(t_vec)
n_avg = 1e6
idx = np.arange(0, array_length, 1)

# array_len = most by constant since it is python variable
def QUA_shuffle(array, array_len): # python
    # qua
    # f = declare(fixed) # example for float 4bit.28bit
    temp = declare(int)
    j = declare(int)
    i = declare(int)
    with for_(i, 0, i < array_len, i+1):
        assign(j, Random().rand_int(array_len-i)) # between 0 to array_len - i
        # swap last with random location
        assign(temp, array[j])
        assign(array[j], array[array_len - 1 - i])
        assign(array[array_len - 1 - i], temp)


with program() as time_rabi:
    counts = declare(int, size=array_length)
    counts_tmp = declare(int)  # variable for number of counts
    counts_st = declare_stream()  # stream for counts
    times = declare(int, size=100)
    t_vec_qua = declare(int, value=np.array([int(i) for i in t_vec]))
    idx_qua = declare(int, value=idx)
    t = declare(int)  # variable to sweep over in time
    n = declare(int)  # variable to for_loop
    index = declare(int)
    tau = declare(int)
    n_st = declare_stream()  # stream to save iterations

    play("laser_ON", "AOM")
    wait(100, "AOM")
    with for_(n, 0, n < n_avg, n + 1):
        QUA_shuffle(idx_qua, array_length) # idx_qua is after shuffle
        with for_(t, 0, t < array_length, t + 1):

            assign(tau, t_vec_qua[idx_qua[t]])

            play("pi", "NV", duration=tau)  # pulse of varied lengths
            align()
            play("laser_ON", "AOM")  # 3 microseconds
            measure("readout", "SPCM", None, time_tagging.analog(times, meas_len, counts_tmp))  # 500 ns
            assign(counts[idx_qua[t]], counts_tmp) # here counts[idx_qua[t]] = counts_temp
            # measure("readout", "SPCM", None, time_tagging.analog(times2, meas_len, counts2))  # 500 ns
            wait(100)
        with for_(t, 0, t < array_length, t + 1): # add one by one elements from counts (which is a vector) into counts_st
            save(counts[t], counts_st) # here counts_st = counts[t]


        save(n, n_st)  # save number of iteration inside for_loop

    with stream_processing():
        counts_st.buffer(len(t_vec)).average().save("counts")
        n_st.save("iteration")

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(opx_ip, opx_port)  # remove octave flag if not using it
# qmm = QuantumMachinesManager(opx_ip, cluster_name=cluster_name)  # remove octave flag if not using it

simulate = False
if simulate:
    simulation_config = SimulationConfig(duration=28000)
    job = qmm.simulate(config, time_rabi, simulation_config)
    res = job.get_simulated_samples()
    job.get_simulated_samples().con1.plot()
    plt.show()
else:
    qm = qmm.open_qm(config)
    # execute QUA program
    job = qm.execute(time_rabi)
    # Get results from QUA program
    results = fetching_tool(job, data_list=["counts", "iteration"], mode="live")
    # Live plotting
    fig = plt.figure()
    interrupt_on_close(fig, job)  # Interrupts the job when closing the figure

    while results.is_processing():
        # Fetch results
        counts, iteration = results.fetch_all()
        # Progress bar
        progress_counter(iteration, n_avg, start_time=results.get_start_time())
        # Plot data
        plt.cla()
        plt.plot(4 * t_vec, counts / 1000 / (meas_len / u.s))
        plt.xlabel("Tau [ns]")
        plt.ylabel("Intensity [kcps]")
        plt.title("Time Rabi")
        plt.pause(0.1)
