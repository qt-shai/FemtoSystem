from ECM import *
from ImGuiwrappedMethods import *
from Common import *

# todo: add parser
# todo: add graph
# todo: add confilcts warnings
# todo: save AVG, var for each xRep measurements (each sequence)
# todo: repeat each xRep y times
# todo: scan each parameter seperatly NxM dimensions for all scans
# todo: add dependency option to be sync + offsets relative to specific element
# todo: list all propeties that need scan option for example: scan over element repetitions
# todo: inherit Pipulse from MW

class DepedencyRefernce(Enum):
    Start2Start = 0
    Start2End = 1
    End2Start = 2
    End2End = 3


class Element:
    # here golbal parameters for all instances of this class
    def __init__(self):
        self.text = "none"
        self.repetitions = 0 # nsec
        self.deltaBetweenRepetitions = 0 # nsec
        self.duration = 0 # nsec
        self.duration_range = []
        self.lag = 0 # nsec
        self.lag_range = []
        self.dependencyText ='none' # should be based on the element line later to parse in to the element name + line number
        self.dependencyLine = []
        self.dependencyCheckBox = []
        self.elementID = uuid.uuid4() # probably will be similar to line in the table
        self.isScanParamer = False # if true this parameter need to be scanned
        self.isDependecyParam = False
    def controls(self):
        pass 
    def common_controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name    
        
        clicked, state, self.isScanParamer = checkbox(self.isScanParamer, "scan?", guiString, 0, 1, 1, 1)
        
        if self.isScanParamer: # range GUI
            if len(self.duration_range)<1:
                for i in range(3):
                    self.duration_range.append(self.duration)
            
            changed, self.duration_range[0] = inputInt(self.duration_range[0], "duration (nsec) from", "", guiString, 1, 1, 1, 1, 110, True)
            imgui.same_line()
            changed, self.duration_range[1] = inputInt(self.duration_range[1], "to", "", guiString, 1, 1, 1, 1, 110, True)
            imgui.same_line()
            changed, self.duration_range[2] = inputInt(self.duration_range[2], "step", "", guiString, 1, 1, 1, 1, 110, True)
        else:
            imgui.same_line()
            changed, self.duration = inputInt(self.duration, "Duration", "nsec", guiString, 1, 1, 1, 1, 110, True)
        
        if self.isScanParamer: # range GUI
            if len(self.lag_range)<1:
                for i in range(3):
                    self.lag_range.append(self.lag)
            
            changed, self.lag_range[0] = inputInt(self.lag_range[0], "Lag (nsec) from", "", guiString, 1, 1, 1, 1, 110, True)
            imgui.same_line()
            changed, self.lag_range[1] = inputInt(self.lag_range[1], "to", "", guiString, 1, 1, 1, 1, 110, True)
            imgui.same_line()
            changed, self.lag_range[2] = inputInt(self.lag_range[2], "step", "", guiString, 1, 1, 1, 1, 110, True)
        else:
            imgui.same_line()
            changed, self.lag = inputInt(self.lag, "Lag", "nsec", guiString, 1, 1, 1, 1, 110, True)

        if not(self.isScanParamer):
            imgui.same_line()

        changed, self.repetitions = inputInt(self.repetitions, "Element Rep", "", guiString, 1, 1, 0, 1, 110, True)
        if self.repetitions>1:
            imgui.same_line()
            changed, self.deltaBetweenRepetitions = inputInt(self.deltaBetweenRepetitions, "delta", "nsec", guiString, 1, 1, 0, 1, 110, True)

class SetLaserPowerElement(Element):
    def __init__(self):
        super().__init__()
        self.power = 0.0 # mW
        self.text = "Set Laser Power"
        
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        changed, self.power = inputFloat(self.power, "Power", "mW", guiString, 0, 1, 0, 1, 150, True, '%.2f', 0.01, 1.0)
class LaserPulseElement(Element):
    def __init__(self):
        super().__init__()
        self.text = "Laser Pulse"
        self.isDependecyParam = True
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        
        imgui.same_line()
        self.common_controls()
class SetMicrowaveFreqWlement(Element):
    def __init__(self):
        super().__init__()
        self.text = "Set MW freq"
        self.frequency = float(2.87) # GHz
        
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        changed, self.frequency = inputFloat(self.frequency, "Freuency", "GHz", guiString, 0, 1, 0, 1, 150, True, '%.6f', 0.001, 0.1)
class MicrowavePulseElement(Element):
    def __init__(self):
        super().__init__()
        self.text = "MW pulse"
        self.isDependecyParam = True
        
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name

        self.common_controls()
class PiPulse(Element):
    def __init__(self):
        super().__init__()
        self.text = "PiPulse"
        self.isDependecyParam = True
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name

        self.common_controls()
class APD1(Element):
    def __init__(self):
        super().__init__()
        self.text = "APD1"
        self.isDependecyParam = True
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name

        self.common_controls()
class APD2(Element):
    def __init__(self):
        super().__init__()
        self.text = "APD2"
        self.isDependecyParam = True
    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name

        self.common_controls()

class ElementsList:
    def __init__(self):
        self.elements = [Element(), SetLaserPowerElement(), SetMicrowaveFreqWlement(), LaserPulseElement(), MicrowavePulseElement(), PiPulse(), APD1(), APD2()]
        self.items = []
        for e in self.elements:
            self.items.append(e.text)
class SingleSeqElement:
    def __init__(self):
        el = ElementsList()
        self.items = el.items
        self.elements = el.elements
        self.selected = 0
        self.element = Element()
        self.depedencyRefernce = DepedencyRefernce.End2Start

    def UpdateLine(self,line):
        self.line = line
        self.id = "e" + str(self.line)

    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name

        imgui.push_item_width(150)
        self.guiID.Step_up()
        imgui.push_id(guiString + str(self.guiID.counter))
        if imgui.begin_combo("", self.items[self.selected]):
            for i, item in enumerate(self.items):
                is_selected = (i == self.selected)
                if imgui.selectable(item, is_selected)[0]:
                    self.selected = i
                    imgui.set_item_default_focus()
                    self.element = self.elements[i]
                    break
                if is_selected:
                    imgui.set_item_default_focus()
            imgui.end_combo()
        imgui.pop_id()
        imgui.pop_item_width()

        imgui.same_line()
        self.element.controls()

class SeqModule:
    def __init__(self):
        self.text = "Block sequence"
        self.seqList = [SingleSeqElement()]
        self.idxToRemove = []
        self.repetition = 1
        self.isDependency = -1

    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        
        self.idxToRemove.clear()
        
        self.guiID.Step_up()
        imgui.push_id(guiString + str(self.guiID.counter))
        if (imgui.begin_table("Block Table "+str(self.guiID.counter), 1)):
            for i, row in enumerate(self.seqList):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                
                if len(self.seqList)>1:
                    self.guiID.Step_up()
                    imgui.push_id(guiString + str(self.guiID.counter))
                    if imgui.button("del element"):
                        self.idxToRemove.append(i)
                        imgui.pop_id()
                    else:
                        imgui.pop_id()
                    imgui.same_line()

                row.controls()

                if len(self.seqList)>1 and row.element.isDependecyParam:
                    imgui.same_line()
                    self.guiID.Step_up()
                    imgui.push_id(guiString + str(self.guiID.counter))
                    if(imgui.button("Set Dependencies")):
                        self.isDependency = i
                    imgui.pop_id()
                    imgui.same_line()
                
                if self.isDependency == i:
                    self.Dependency(row)
            imgui.end_table()
        imgui.pop_id()

        if len(self.seqList)>1:
            changed, self.repetition = inputInt(self.repetition, "Sequence rep", "", guiString, 1, 1, 0, 1, 150, True)
            
        self.RemoveIdx()
        # self.RemoveAllNone()
        self.VerifyLastElementNone()

    def Dependency(self, row):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        
        self.guiID.Step_up()
        imgui.push_id(guiString + str(self.guiID.counter))
        with imgui.begin("Dependencies of "+ row.element.text):
            self.guiID.Step_up()
            imgui.push_id(guiString + str(self.guiID.counter))
            with imgui.begin_child("region",0, 0, True,imgui.WINDOW_ALWAYS_AUTO_RESIZE):
                depList = []
                
                for i in range(self.isDependency):
                    depList.append(self.seqList[i])
                    if not(self.isDependency == len(self.seqList[self.isDependency].element.dependencyLine)):
                        self.seqList[self.isDependency].element.dependencyCheckBox.append(0)
                self.seqList[self.isDependency].element.dependencyCheckBox[-1]=1


                self.guiID.Step_up()
                imgui.push_id(guiString + str(self.guiID.counter))
                if (imgui.begin_table("Dependency Table "+str(self.guiID.counter), 1)):
                    for i, row in enumerate(depList):
                        imgui.table_next_row()
                        imgui.table_set_column_index(0)
                        
                        clicked, state, self.seqList[self.isDependency].element.dependencyCheckBox[i] = checkbox(self.seqList[self.isDependency].element.dependencyCheckBox[i],"",guiString)
                        imgui.same_line()
                        imgui.text(row.element.text)
                    imgui.end_table()
                imgui.pop_id()


                # review thw code again
                typeList = []
                typeList.append(DepedencyRefernce.End2Start)
                typeList.append(DepedencyRefernce.End2End)
                typeList.append(DepedencyRefernce.Start2Start)
                typeList.append(DepedencyRefernce.Start2End)

                imgui.push_item_width(150)
                self.guiID.Step_up()
                imgui.push_id(guiString + str(self.guiID.counter))
                if imgui.begin_combo("",self.seqList[self.isDependency].depedencyRefernce.name):
                    for i, item in enumerate(typeList):
                        is_selected = (item.name == self.seqList[self.isDependency].depedencyRefernce.name)
                        if imgui.selectable(item.name, is_selected)[0]:
                            # imgui.set_item_default_focus()
                            self.seqList[self.isDependency].depedencyRefernce = item
                            break
                        if is_selected:
                            imgui.set_item_default_focus()
                    imgui.end_combo()
                imgui.pop_id()
                imgui.pop_item_width()
                # review up to here
                
                self.guiID.Step_up()
                imgui.push_id(guiString + str(self.guiID.counter))
                if(imgui.button("close")):
                    self.isDependency = -1
                imgui.pop_id()
                
                imgui.end_child
            imgui.pop_id()
        imgui.pop_id()
    
    

    def RemoveIdx(self):
        self.idxToRemove.reverse()
        for idx in self.idxToRemove:
            self.seqList.pop(idx)
        self.idxToRemove.clear()
    def RemoveAllNone(self):
        # find all "none"
        for idx, row in enumerate(self.seqList):
            if row.element.text == "none":
                self.idxToRemove.append(idx)
        self.RemoveIdx()    
    def VerifyLastElementNone(self):
        # check if last element is none if not add new "none"
        if (len(self.seqList)<1 or (self.seqList[-1].selected !=0)):
            se = SingleSeqElement()
            se.UpdateLine(len(self.seqList))
            self.seqList.append(se)        

class Block:
    def __init__(self):
        self.text = "Block"
        self.blockList = [SeqModule()]
        self.idxToRemove = []

    def controls(self):
        self.guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name
        
        self.idxToRemove.clear()
        
        self.guiID.Step_up()
        imgui.push_id(guiString + str(self.guiID.counter))
        if(imgui.button("add Block")):
            self.AddModule()
        imgui.pop_id()
        
        self.guiID.Step_up()
        imgui.push_id(guiString + str(self.guiID.counter))
        if (imgui.begin_table("Repetition Table "+str(self.guiID.counter), 1)):
            for i, row in enumerate(self.blockList):
                imgui.table_next_row()
                imgui.table_set_column_index(0)

                if len(self.blockList)>1:
                    self.guiID.Step_up()
                    imgui.push_id(guiString + str(self.guiID.counter))
                    if imgui.button("Delete block"):
                        self.idxToRemove.append(i)
                        imgui.pop_id()
                    else:
                        imgui.pop_id()
                    
                    imgui.same_line()

                
                row.controls()
                imgui.separator()

            imgui.end_table()
        imgui.pop_id()

        # remove items
        for idx in self.idxToRemove:
            self.blockList.pop(idx)

    def AddModule(self):
        self.blockList.append(SeqModule())


class ExpSequenceGui:

    def __init__(self):
        self.mainElement = Block()

    def controls(self):
        imgui.begin("Experiment Sequencer") # open new window
        self.mainElement.controls()
        imgui.end()
        pass


