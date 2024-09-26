from ECM import *
from Common import *
# examples:
# text = (1.0, 0.5, 0.0, 1.0)  # Example original text color
# factor = (0.5, 0.5, 0.5, 1.0)  # Example factor for modification


def PushStyleColor(factor, text, but, hov, act):
    i = 0
    modified_text = [text[i] * factor[i] for i in range(4)]
    modified_but = [but[i] * factor[i] for i in range(4)]
    modified_hov = [hov[i] * factor[i] for i in range(4)]
    modified_act = [act[i] * factor[i] for i in range(4)]
    imgui.push_style_color(imgui.COLOR_TEXT, modified_text[0], modified_text[1], modified_text[2], modified_text[3])
    i = i + 1
    imgui.push_style_color(imgui.COLOR_BUTTON, modified_but[0], modified_but[1], modified_but[2], modified_but[3])
    i = i + 1
    imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, modified_hov[0], modified_hov[1], modified_hov[2], modified_hov[3])
    i = i + 1
    imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, modified_act[0], modified_act[1], modified_act[2], modified_act[3])
    i = i + 1
    return i
def DisableGUI(name, message):
    imgui.open_popup(name)

    # Begin the modal popup with the specified name
    if imgui.begin_popup_modal(name, None, imgui.WINDOW_ALWAYS_AUTO_RESIZE):
        # Display the message text
        imgui.text(message)
        # Add a separator
        imgui.separator()
def HelpMarker(desc):
    # Display the disabled text "(?)"
    imgui.text_disabled("(?)")

    # Check if the item is hovered
    if imgui.is_item_hovered():
        # Begin the tooltip
        imgui.begin_tooltip()
        
        # Set text wrapping position
        imgui.push_text_wrap_pos(imgui.get_font_size() * 35.0)
        
        # Display the description text
        imgui.text_unformatted(desc)
        
        # Reset text wrapping position
        imgui.pop_text_wrap_pos()
        
        # End the tooltip
        imgui.end_tooltip()
def HelpHovered(desc):
    if imgui.is_item_hovered():
        imgui.begin_tooltip()
        imgui.push_text_wrap_pos(imgui.get_font_size() * 35.0)
        imgui.text_unformatted(desc)
        imgui.pop_text_wrap_pos()
        imgui.end_tooltip()

def inputInt(val = 0, label = "", unitsLabel = "", guiString = "none", r = 1, g = 1, b = 1 , a = 1, itemWidth = 150, above_zero = False, step = 1, step_fast = 100, enterKey = True):
        changed, val = inputFloat(val, label, unitsLabel, guiString, r, g, b, a, itemWidth, above_zero, '%.0f', step, step_fast, enterKey)
        return changed, int(val)
        guiID = Common_Counter_Singletone()
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(label, r, g, b, a)
        imgui.pop_id()
        
        imgui.same_line()

        imgui.push_item_width(itemWidth)
        imgui.push_style_color(imgui.COLOR_TEXT, r,g,b,a)
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))

        if enterKey:
            flagIdx = imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
        else:
            flagIdx = 0

        changed, val = imgui.input_int("", val, step, step_fast, flagIdx)
        imgui.pop_id()
        imgui.pop_style_color(1)
        imgui.pop_item_width()

        imgui.same_line()

        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(unitsLabel, r, g, b, a)
        imgui.pop_id()



        if above_zero and val<=0:
            val = 1

        return changed, val
def inputFloat(val = 0, label = "", unitsLabel = "", guiString = "none", r = 1, g = 1, b = 1 , a = 1, itemWidth = 150, isAlwaysPositive = False, str_format = '%.4f', step = 0.0, step_fast = 0.0, enterKey = True):
        guiID = Common_Counter_Singletone()
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(label, r, g, b, a)
        imgui.pop_id()
        
        imgui.same_line()

        imgui.push_item_width(itemWidth)
        imgui.push_style_color(imgui.COLOR_TEXT, r,g,b,a)
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))

        if enterKey:
            flagIdx = imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
        else:
            flagIdx = 0

        changed, val = imgui.input_float("", val, step, step_fast, str_format,flagIdx)
        
        imgui.pop_id()
        imgui.pop_style_color(1)
        imgui.pop_item_width()

        imgui.same_line()

        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(unitsLabel, r, g, b, a)
        imgui.pop_id()

        if isAlwaysPositive and val<=0:
            val = 0

        return changed, val
def inputDouble(val = 0, label = "", unitsLabel = "", guiString = "none", r = 1, g = 1, b = 1 , a = 1, itemWidth = 150, isAlwaysPositive = False, str_format = '%.4f', step = 0.0, step_fast = 0.0, enterKey = True):
        guiID = Common_Counter_Singletone()
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(label, r, g, b, a)
        imgui.pop_id()
        
        imgui.same_line()

        imgui.push_item_width(itemWidth)
        imgui.push_style_color(imgui.COLOR_TEXT, r,g,b,a)
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))

        if enterKey:
            flagIdx = imgui.INPUT_TEXT_ENTER_RETURNS_TRUE
        else:
            flagIdx = 0

        changed, val = imgui.input_double("", val, step, step_fast, str_format,flagIdx)
        
        imgui.pop_id()
        imgui.pop_style_color(1)
        imgui.pop_item_width()

        imgui.same_line()

        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(unitsLabel, r, g, b, a)
        imgui.pop_id()

        if isAlwaysPositive and val<=0:
            val = 0

        return changed, val
def checkbox(val = 0, label = "", guiString = "none", r = 1, g = 1, b = 1 , a = 1):
    guiID = Common_Counter_Singletone()

    guiID.Step_up()
    imgui.push_id(guiString + str(guiID.counter))
    imgui.text_colored(label, r, g, b, a)
    imgui.pop_id()

    imgui.same_line()
    
    guiID.Step_up()
    imgui.push_id(guiString + str(guiID.counter))
    clicked,state = imgui.checkbox("",val)
    if (clicked):
        val = not(val)
    imgui.pop_id()

    return clicked, state, val
    # return val