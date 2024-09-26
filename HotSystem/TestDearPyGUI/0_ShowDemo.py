import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

dpg.create_context()
dpg.configure_app(manual_callback_management=True)
dpg.create_viewport(title='Custom Title', width=600, height=600)

demo.show_demo()

dpg.setup_dearpygui()
dpg.show_viewport()
# dpg.start_dearpygui()
while dpg.is_dearpygui_running():
    jobs = dpg.get_callback_queue() # retrieves and clears queue
    dpg.run_callbacks(jobs)
    dpg.render_dearpygui_frame()
dpg.destroy_context()