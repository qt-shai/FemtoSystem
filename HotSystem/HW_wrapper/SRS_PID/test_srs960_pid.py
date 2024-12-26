from HW_wrapper import SRSsim900, SRSsim960

mainframe_port = "COM6"
temp_mainframe = SRSsim900(mainframe_port)
temp_mainframe.connect()

pid = SRSsim960(temp_mainframe,3)

pid.get_proportional_gain()
pid.set_proportional_gain(0.1)
pid.set_integral_gain(0.01)
