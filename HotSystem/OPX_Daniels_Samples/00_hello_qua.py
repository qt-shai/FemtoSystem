"""
hello_qua.py: template for basic qua program demonstration
"""
import math
import time
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from qm import SimulationConfig, LoopbackInterface
from qm.qua import *
from qm import QuantumMachinesManager
from configuration import *

#
###################
# The QUA program #
###################

with program() as hello_QUA:
    # with infinite_loop_():
    #     play('ON', 'MW_switch')

    play("laser_ON", "AOM") # 50 ns delay
    wait(250, "AOM") # maybe in cycles
    with infinite_loop_():
        #### here at the beginning of each loop there is align() for all elements in side the loop

        # i = declare(int)
        # # with for_(i, 0, i < 20,i+1 ):
        # play('laser_ON', 'AOM', duration= int(5e7 // 4))
        # wait(int(1e9//4),'AOM')
        # --- play('cw', 'NV', duration = int(50//4))
        # --- wait(250, 'NV')  # clock cycle
        # play('cw', 'NV')
        # --- wait(2500, 'NV')
        # align('NV', 'AOM')
        # play('laser_ON','AOM')


        play("pi", "NV", duration=100//4)  # pulse of varied lengths in cycles
        wait(410//4,'NV') # only NV element will wait, time in cycles
        #wait(200, 'NV')
        # ?align()
        play("laser_ON", "AOM")  # 5 microseconds
        #align()
        play("pi", "NV", duration=100//4)  # pulse of varied lengths in cycles
        wait(410//4,'NV')
        #align()
        # align("SPCM","AOM")
        # wait(10,"SPCM")
        # measure("readout", "SPCM", None, time_tagging.analog(times, meas_len, counts))  # 500 ns
        # --- measure("readout", "SPCM_OPD", None, time_tagging.digital(times, meas_len, counts))  # 500 ns
        # wait(500, "SPCM")
        # measure("readout", "SPCM", None, time_tagging.analog(times2, meas_len, counts2))  # 500 ns
        # --- save(counts, counts_st)  # save counts
        #wait(250)  # wait for all channels


#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(opx_ip, opx_port)

simulate = False

if simulate:
    simulation_config = SimulationConfig(
        duration=28000, simulation_interface=LoopbackInterface([("con1", 3, "con1", 1)])  # in clock cycle
    )
    job_sim = qmm.simulate(config, hello_QUA, simulation_config)
    # Simulate blocks python until the simulation is done
    job_sim.get_simulated_samples().con1.plot()
    plt.show()
else:
    qm = qmm.open_qm(config)
    job = qm.execute(hello_QUA) # compile and run
    # Execute does not block python! As this is an infinite loop, the job would run forever. In this case, we've put a 10
    # seconds sleep and then halted the job.
    # time.sleep(10)
    job.halt()
    qm.close()
