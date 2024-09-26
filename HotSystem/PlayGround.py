import math
import time
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from qm import SimulationConfig, LoopbackInterface
from qm.qua import *
from qm import QuantumMachinesManager
from configuration import *

freq = 3.03*u.MHz

with program() as hello_QUA:
    play("const", "RF",duration=1000//4) # 50 ns delay
    wait(250, "RF") # maybe in cycles
    update_frequency("RF",freq)
    with infinite_loop_():
        play("const","RF", duration=10000//4)
        wait(2000//4,"RF")
        align()

qmm = QuantumMachinesManager(opx_ip, opx_port)

qm = qmm.open_qm(config)
job = qm.execute(hello_QUA) # compile and run
job.halt()
qm.close()
