from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
from configuration import *
from qm import SimulationConfig
import matplotlib.pyplot as plt
import numpy as np


t_min = 4 // 4
t_max = 3000 // 4
dt = 40 // 4
t_vec = np.arange(t_min, t_max, dt)

wait_before_measure = 100 // 4
wait_after_measure = 800 // 4
repsN = 1
simulate = True
a_avg = 1e8

def xy8_1():
    wait(t, "NV")
    xy8_block()
    wait(t, "NV")

def xy8_2():
    wait(t, "NV")
    xy8_block()
    wait(two_t, "NV")
    xy8_block()
    wait(t, "NV")

def xy8_n(n):
    # Performs the full xy8_n sequence. First block is outside loop, to avoid delays caused from either the loop or from
    # two consecutive wait commands.
    # Assumes it starts frame at x, if not, need to reset_frame before

    wait(t, "NV")

    xy8_block()

    with for_(i, 0, i < n - 1, i + 1):
        wait(two_t, "NV")
        xy8_block()

    wait(t, "NV")


def xy8_block():
    # A single XY8 block, ends at x frame.\

    play("x180", "NV")  # 1 X
    wait(two_t, "NV")

    play("y180", "NV")  # 2 Y
    wait(two_t, "NV")

    play("x180", "NV")  # 3 X
    wait(two_t, "NV")

    play("y180", "NV")  # 4 Y
    wait(two_t, "NV")

    play("y180", "NV")  # 5 Y
    wait(two_t, "NV")

    play("x180", "NV")  # 6 X
    wait(two_t, "NV")

    play("y180", "NV")  # 7 Y
    wait(two_t, "NV")

    play("x180", "NV")  # 8 X



with program() as xy8:
    # Realtime FPGA variables
    a = declare(int)  # For averages
    i = declare(int)  # For XY8-N
    t = declare(int)  # For tau
    two_t = declare(int)  # For tau
    iterations = declare_stream() # iteration stream
    phi = declare(fixed, value=0)  # Random phase
    times = declare(int, size=100)  # Time-Tagging
    counts = declare(int)  # Counts
    counts_ref = declare(int)
    diff = declare(int)  # Diff in counts between counts & counts_ref
    counts_st = declare_stream()  # Streams for server processing
    counts_ref_st = declare_stream()
    diff_st = declare_stream()
    update_frequency("NV", -146e6)
    with for_(a, 0, a < a_avg, a + 1):
        play("laser_ON", "AOM")
        wait(250 // 4)
        with for_(t, t_min, t <= t_max, t + dt):  # Implicit Align
            # Play meas (pi/2 pulse at x)
            assign(two_t, 2*t)
            play("x90", "NV")
            if repsN == 1:
                xy8_1()
            elif repsN == 2:
                xy8_2()
            else:
                xy8_n(repsN)
            play("x90", "NV")
            wait(wait_before_measure, 'NV')
            align('NV', 'AOM', 'SPCM')
            play("laser_ON", "AOM")
            measure("readout", "SPCM", None, time_tagging.analog(times, meas_len, counts))
            # Time tagging done here, in real time
            wait(wait_after_measure, 'SPCM')

            
            align('NV', 'AOM', 'SPCM')
            # Plays ref (pi/2 pulse at -x)
            play("x90", "NV")
            if repsN == 1:
                xy8_1()
            elif repsN == 2:
                xy8_2()
            else:
                xy8_n(repsN)
            play("-x90", "NV")
            reset_frame("NV")  # Such that next tau would start in x.
            wait(wait_before_measure, 'NV')
            align('NV', 'AOM', 'SPCM')
            play('laser_ON', 'AOM')
            
            measure(
                "readout", "SPCM", None, time_tagging.analog(times, meas_len, counts_ref)
            )
            # Time tagging done here, in real time
            wait(wait_after_measure, 'SPCM')
            # save counts:
            assign(diff, counts - counts_ref)
            save(counts, counts_st)
            save(counts_ref, counts_ref_st)
            save(diff, diff_st)
        save(a, iterations)

    with stream_processing():
        counts_st.buffer(len(t_vec)).average().save("dd")
        counts_ref_st.buffer(len(t_vec)).average().save("ddref")
        diff_st.buffer(len(t_vec)).average().save("diff")
        iterations.save("iterations")


# qmm = QuantumMachinesManager(host=qop_ip, port=opx_port, octave=octave_config)
qmm = QuantumMachinesManager()
# qmm = QuantumMachinesManager(host=qop_ip, port=opx_port)

if simulate:
    job = qmm.simulate(config, xy8, SimulationConfig(20000))
    job.get_simulated_samples().con1.plot()

else:
    qm = qmm.open_qm(config)
    #job = qm.execute(xy8, duration_limit=0, time_limit=0)
    job = qm.execute(xy8)
    
    results = fetching_tool(job, data_list=["dd", "ddref", "diff", "iterations"], mode="live")
    # Live plotting
    fig = plt.figure()
    interrupt_on_close(fig, job)  # Interrupts the job when closing the figure

    while results.is_processing():
        # Fetch results
        counts1, counts2, diff, iteration = results.fetch_all()
        # Progress bar
        progress_counter(iteration, a_avg, start_time=results.get_start_time())
        # Plot data
        
        signal1 = counts1 / (meas_len / u.s)
        signal2 = counts2 / (meas_len / u.s)
        
        contrast = (signal1-signal2)/(signal1+signal2)

        
        plt.cla()
        plt.plot(4 * t_vec*2, signal1)
        plt.plot(4 * t_vec*2, signal2)
        plt.xlabel("Tau [ns]")
        plt.ylabel("Intensity [cps]")
        plt.legend(("counts 1", "counts 2"))
        plt.title("XY" + str(repsN*8))
        plt.pause(3)
        
        plt.cla()
        plt.plot(4 * t_vec*2, contrast)
        plt.xlabel("Tau [ns]")
        plt.ylabel("Intensity [cps]")
        plt.legend(("counts 1", "counts 2"))
        plt.title("XY" + str(repsN*8))
        plt.pause(3)
    
        np.save("XY" + str(repsN*8) + ".npy", [2*4 * t_vec, signal1, signal2, contrast])
        
    qm.close()
    
    
    
    
    
