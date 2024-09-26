import smaract.ctl as ctl

from HW_wrapper.SmarAct.smaract_movement import Movement
from HW_wrapper.SmarAct.smaract_stream_manager import StreamManager
from HW_wrapper.Wrapper_Smaract import smaractMCS2
import numpy as np

controller = smaractMCS2()
dev_list = ctl.FindDevices()
controller.Connect(dev_list.splitlines()[0])

stream_manager = StreamManager(controller.dHandle)
movement = Movement(controller.dHandle, stream_manager.stream_handle)

movement.set_properties(0)
movement.set_properties(1)
movement.set_properties(2)
movement.configure_stream()
#

motion_buffer = 1e6 # 1 micron
controller.GetPosition()
start_positions = controller.AxesPositions
target_position = start_positions[0] + 1e9 + motion_buffer

ctl.SetProperty_i32(controller.dHandle, 0, ctl.Property.CH_POS_COMP_DIRECTION, ctl.TriggerCondition.EITHER)
ctl.SetProperty_i64(controller.dHandle, 0, ctl.Property.CH_POS_COMP_START_THRESHOLD, 0)
ctl.SetProperty_i64(controller.dHandle, 0, ctl.Property.CH_POS_COMP_LIMIT_MIN, int(1e9))  # pm
ctl.SetProperty_i64(controller.dHandle, 0, ctl.Property.CH_POS_COMP_LIMIT_MAX, int(2e9))  # pm
ctl.SetProperty_i64(controller.dHandle, 0, ctl.Property.CH_POS_COMP_INCREMENT, int(1e6))  # pm
ctl.SetProperty_i32(controller.dHandle, 0, ctl.Property.CH_OUTPUT_TRIG_PULSE_WIDTH, 1000)  # ns
ctl.SetProperty_i64()

controller.MoveABSOLUTE(0, target_position)
points = [(x, x*2) for x in np.linspace(0, 100000, 10)]
stream_manager.start_stream_2d(points, ctl.StreamTriggerMode.DIRECT)

# controller.Disconnect()

end_positions = controller.GetPosition()

