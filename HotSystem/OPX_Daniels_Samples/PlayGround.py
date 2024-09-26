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



with program() as hello_QUA1:
    times_ref = declare(int, size=100)
    counts_ref = declare(int)  # variable for number of counts

    with infinite_loop_():
        wait_for_trigger(element="which element waits for the trigger")
        align()
        measure("long_readout", "SPCM_OPD", None, time_tagging.digital(times_ref, long_meas_len, counts_ref))
        # play("const","SPCM_OPD", duration=10000//4)
        # wait(2000//4,"RF")
        pause()
        align()

with program() as hello_QUA:
    play("const", "RF",duration=1000//4) # 50 ns delay
    wait(250, "RF") # maybe in cycles
    update_frequency("RF",freq)
    with infinite_loop_():
        play("const"*amp(1),"RF", duration=10000//4)
        
        wait(2000//4,"RF")
        pause()
        align()

qmm = QuantumMachinesManager(opx_ip, opx_port)
qmm.close_all_quantum_machines()


qm = qmm.open_qm(config,close_other_machines=False)
qm1 = qmm.open_qm(config1,close_other_machines=False)

# program_id = qm.compile(hello_QUA)
# program_id1 = qm.compile(hello_QUA1)
# pending_job = qm.queue.add_compiled(program_id) # also execute the job
# pending_job = qm.queue.add_compiled(program_id1)
# job = pending_job.wait_for_execution()

job = qm.execute(hello_QUA)
# job1 = qm1.execute(hello_QUA1)
print(f"job is_paused =:{job.is_paused()}")
print(f"job _is_job_running =:{job._is_job_running()}")
job.resume()
time.sleep(10)
if job.is_paused():
    print(f"job is_paused =:{job.is_paused()}")
    print(f"job _is_job_running =:{job._is_job_running()}")
    job1 = qm1.execute(hello_QUA1) # compile and run
    print(f"job is_paused =:{job.is_paused()}")
    print(f"job _is_job_running =:{job._is_job_running()}")
    print(f"job1 is_paused =:{job1.is_paused()}")
    print(f"job1 _is_job_running =:{job1._is_job_running()}")

if job1.is_paused():
    job.resume()

job1.halt()
job.halt()
# job1.halt()

qm.close()
qm1.close()
