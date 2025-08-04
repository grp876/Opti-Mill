import json
import math
from pathlib import Path

from .machine import Machine
from .tool import Tool

RED    = '\033[31m'
ORANGE = '\033[91m'
YELLOW = '\033[93m'
GREEN  = '\033[92m'
CYAN   = '\033[36m'
ENDC   = '\033[0m'

################################################################################
# Initializer -- Load details from JSON
################################################################################

class Mill(Machine):
    def __init__(self, json_file):
        super().__init__(json_file)
        self.queue(comment='Loading Mill parameters from JSON', style='mill')

        with open(f"machines/{json_file}") as f:
            config = json.load(f)

        if 'Tool Table' not in config:
            raise KeyError(f"{RED}Your machine configuration must reference a tool table file{ENDC}")

        # Load the new-style tool_inventory.json and flatten it
        tool_table_path = Path("tables") / config['Tool Table']
        with open(tool_table_path, 'r') as tt:
            nested_tool_data = json.load(tt)

        # Flatten the tool table to match the old layout
        self._tool_table = {}
        counter = 0
        for tool_type, tools in nested_tool_data.items():
            for tool in tools:
                tool["type"] = tool_type  # preserve type in each tool entry
                self._tool_table[str(counter)] = tool
                counter += 1

        self.max_rpm = config['Max Spindle RPM']
        self.safe_z = 10 #TODO: This should be in a Workpiece class

################################################################################
# Constant Surface Speed
################################################################################

    @property
    def css(self):
        return self._css

    @css.setter
    def css(self, value):
        #self.queue(comment=f"Desired Constant Surface Speed (CSS): {value:.4f} m/s | {value*196.85:.4f} ft/min{ENDC}", style='mill')
        #self.queue(comment=f"Calculating RPM from CSS and tool diameter.", style='mill')
        rpm = value * 60000 / math.pi / self.tool.diameter
        if rpm > self.max_rpm:
            css = self.max_rpm * math.pi * self.tool.diameter / 60000
            self.queue(comment=f"{self.name} cannot do {rpm:.4f} rpm.  Maxing out at {self.max_rpm} rpm | {css:.4f} m/s | {css*196.85:.4f} ft/min", style='warning')
            rpm = self.max_rpm;
        self.queue(comment=f"Setting RPM: {rpm:.4f} | {rpm/60:.4f} Hz on the VFD", style='mill')
        self._rpm = rpm

    surface_speed = css

################################################################################
# Spindle Speed (S)
################################################################################

    @property
    def rpm(self):
        return self._rpm

    @rpm.setter
    def rpm(self, value):
        if value > self.max_rpm:
            raise ValueError(f"Machine.rpm ({value}) must be lower than Machine.max_rpm ({self.max_rpm})")
        self._rpm = value
        self.queue(code='G97', comment='Constant Spindle Speed')
        self.queue(code=f"S{value}", comment=f"Set Spindle RPM: {value:.4f}")
        if self.tool.diameter is not None:
            css = self.rpm * math.pi * self.tool.diameter / 60000
            if round(self._css, 4) != round(css, 4):
                self._css = css
                self.queue(comment=f"Calculated Tool Constant Surface Speed (CSS): {self.css:.4f} m/s | {self.css*196.85:.4f} ft/min", style='mill')
        else:
            self.queue(comment='Cannot calculate CSS from RPM because tool diameter is undefined', style='warning')

################################################################################
# Feeds and Speeds
################################################################################

    def update_fas(self):
        if self.material and self.tool:
            fas_file = 'tables/feeds-and-speeds.json'
            with open(fas_file, 'r') as fas:
                self._fas = json.load(fas)
            sfm = self._fas['SFM']
            chipload = self._fas['Chipload']
            cutter = self.tool.material
            if self.material in sfm[cutter] and self.material in chipload:
                self.queue(comment=f"Workpiece is {self.material}", style='machine')

                if self.tool.rpm:
                    rpm = (self.tool.rpm[self.material][0]+self.tool.rpm[self.material][1])/2
                    self.queue(comment=f"Using tool manufacturer recommended spindle RPM: {rpm:.4f} rpm", style='machine')
                    self.rpm = rpm
                else:
                    self.css = (sfm[cutter][self.material][0]+sfm[cutter][self.material][1])/2/196.85

                if self.tool.ipm:
                    ipm = (self.tool.ipm[self.material][0]+self.tool.ipm[self.material][1])/2
                    self.queue(comment=f"Using tool manufacturer recommended feed: {ipm:.4f} in/min", style='machine')
                    self.feed = ipm*25.4
                else:
                    self.queue(comment=f"No manufacturer-recommended IPM Feed.  Calculating.", style='machine')
                    cl_range = chipload[self.material].get(f"{self.tool.diameter/25.4:.3f}", None)
                    if cl_range:
                        cl_mean = (cl_range[0]+cl_range[1])/2
                        self.feed = self.rpm * self.tool.flutes * cl_mean * 25.4
                    else:
                        self.queue(comment=f"Tool not available in chipload table.  You're on your own for feeds and speeds.", style='warning')

################################################################################
# Linear Interpolated Cuts (G1)
################################################################################

    cut = Machine.linear_interpolation
    icut = Machine.i_linear_interpolation
