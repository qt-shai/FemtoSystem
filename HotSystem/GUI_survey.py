import os
import dearpygui.dearpygui as dpg


class SurveyApp:
    def __init__(self):
        # Attributes for image state and point selection.
        self.image_id = None  # Tag for the image widget
        self.texture_tag = "image_tex"  # Tag for the texture
        self.selection_mode = False
        self.selected_points = []  # List to store (x, y) tuples

        # Setup GUI handlers and build the interface.
        self.setup_handlers()
        self.build_gui()

    def setup_handlers(self):
        # Create an item handler registry for image click events.
        with dpg.item_handler_registry(tag="image_handler"):
            dpg.add_item_clicked_handler(callback=self.on_image_click)

    def build_gui(self):
        # Create a hidden file dialog for image loading.
        with dpg.file_dialog(directory_selector=False, show=False, callback=self.on_file_select, tag="file_dialog_id",
            modal=True, file_count=1, default_path="Q://QT-Quantum_Optic_Lab//Lab notebook//Test_data_for_survey",
            width=700, height=400):
            dpg.add_file_extension(".png")
            dpg.add_file_extension(".jpg")
            dpg.add_file_extension(".*")

        # Build the main Survey window.
        with dpg.window(label="Survey", width=800, height=600, tag="main_window"):
            with dpg.group(horizontal = True):
                dpg.add_button(label="Load Image", callback=lambda: dpg.show_item("file_dialog_id"))
                dpg.add_button(label="Select Points (Off)", tag="toggle_btn", callback=self.on_toggle_select)

            # Create a child window for displaying the image.
            with dpg.child_window(label="Image View", width=600, height=400, border=True, tag="image_window"):
                dpg.add_text("Load an image to display here...")

    def on_file_select(self, sender, app_data):
        """Called when an image file is selected from the file dialog."""
        file_path = app_data["file_path_name"]
        if not os.path.isfile(file_path):
            print("Invalid file selected.")
            return

        # Load the image data.
        width, height, channels, data = dpg.load_image(file_path)

        # Create/update the texture in the texture registry.
        if dpg.does_item_exist(self.texture_tag):
            dpg.delete_item(self.texture_tag)
        with dpg.texture_registry(show=False):
            dpg.add_static_texture(width, height, data, tag=self.texture_tag)

        # Remove any existing image widget before creating a new one.
        if self.image_id is not None and dpg.does_item_exist(self.image_id):
            dpg.delete_item(self.image_id)

        # Create the image widget inside the "image_window" child.
        self.image_id = dpg.add_image(self.texture_tag, parent="image_window", tag="image_widget", width=width,
                                      height=height)

        # If selection mode is active, bind the click handler to the new image.
        if self.selection_mode:
            dpg.bind_item_handler_registry(self.image_id, "image_handler")

    def on_toggle_select(self, sender, app_data):
        """Toggle the coordinate selection mode on/off."""
        self.selection_mode = not self.selection_mode

        if self.selection_mode:
            dpg.configure_item("toggle_btn", label="Select Points (On)")
            self.selected_points = []  # Clear previous selections
            if self.image_id is not None:
                dpg.bind_item_handler_registry(self.image_id, "image_handler")
        else:
            dpg.configure_item("toggle_btn", label="Select Points (Off)")
            if self.image_id is not None:
                # Unbind the click handler to stop recording points.
                dpg.bind_item_handler_registry(self.image_id, None)
            # For now, simply print the selected points.
            print("Recorded points:", self.selected_points)
            # Clear stored points.
            self.selected_points = []

    def on_image_click(self, sender, app_data, user_data):
        """Record the coordinates of a mouse click on the image."""
        if not self.selection_mode:
            return

        # Get the absolute mouse position.
        mouse_pos = dpg.get_mouse_pos(local=False)
        # Get the image widget's top-left position (screen coordinates).
        image_pos = dpg.get_item_rect_min("image_widget")
        # Get the current scroll offset of the image sub-window.
        scroll_x = dpg.get_x_scroll("image_window")
        scroll_y = dpg.get_y_scroll("image_window")

        # Calculate the click position relative to the image widget.
        rel_x = mouse_pos[0] - image_pos[0] + scroll_x
        rel_y = mouse_pos[1] - image_pos[1] + scroll_y

        self.selected_points.append((int(rel_x), int(rel_y)))
        print(f"Recorded point: ({int(rel_x)}, {int(rel_y)})")

    def run(self):
        """Run the Dear PyGui application."""
        dpg.create_viewport(title="Dear PyGui Survey Interface", width=820, height=620)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()


if __name__ == "__main__":
    dpg.create_context()
    app = SurveyApp()
    app.run()
