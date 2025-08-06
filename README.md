Opti-Mill is a G-Code creator for creating simple shapes without requiring or learning a complicated CAM or 3D package. Testing is on a Sherline CNC Mill using a GRBL friendly - FluidNC motion controller, CNCjs and a Raspberry Pi 5.  Basically this is an attempt to fill the void between writing your own G-Code and going full blown CAD/CAM software package.  Enjoy and keep on building!

<img width="902" height="837" alt="image" src="https://github.com/user-attachments/assets/5fe4d6f2-1827-440b-9a97-03d9876b1300" />

 ##### Disclaimer: ##### 

Use this software at your own risk. Check the gcode thoroughly before running it on your machine. Everything you do with this software is your choice and responsibility. I hope it is useful, but I cannot be held responsible for injury or damage, even if it's due to errors in the software. CNC machines are dangerous. Be smart about it. As we all know, 0.001 is way different than 0.1. Coding in python or straight G-Code always can have clerical errors that cost money, lead to injury, death or just being surprised. Check and understand your G-Code before utilizing any G-Code generator - even expensive ones.

 ##### About the Testing System #####

The original Sherline manual mill was converted to a CNC-ready mill using OEM parts then the hunt for non-OEM stepper motors, a motion controller board, 24VDC power supply and the Raspberry Pi with software began.  A much longer task then anticipated.  Luckily, I currently do not have the need for something as complex as LinxCNC or similiar CAM packages so this Python GUI was created.

The motion controller is an extremely flexible motion controller from FluidNC (http://wiki.fluidnc.com/en/hardware/existing_hardware). I also utilize CNCjs (https://cnc.js.org/) which is free. Both this program, CNCjs and FluidNC run on a Raspberry Pi5 with no problems (as of 07/31/2025). CNCjs installation instructions can be found on the cncjs website or you can utilized (https://github.com/cncjs/cncjs-pi-raspbian) to create an SD card ready to go with Raspbian and CNCjs.

 ##### Opti-Mill - Currently only Metric: ##### 

Opti-Mill is a GUI to generate G-Code for bolt circles, rectangular pockets, frames, circular pockets, helix and more. No need to hunt for a free CAM package or slow yourself down with learning one that came with your 3D package (unless your doing complex contours). Please note this was build on the shoulder of awesomeness. The pygdk code that runs in the background does most of the math. This GUI helps me utilize the pygdk package without writing scripts. It has required some adjustments to the original pygdk code so the G-Code could be utilized with the FluidNC controller and CNCjs.

 ##### Tooling and Feeds & Speeds JSON: ##### 

Speeds and feeds are based on the tool_data.json file. Original values were based on Sherline.com manual for there CNC ready mills (I haven't tested these yet but I'm assuming Sherline knows their machines - which are GREAT). Diameters that fall outside of the tool_data speed and rpm interpolation curves will throw an error. You will need to expand this table based on your testing. I attempted to expand to the common 3/8' but this was only utilizing an online software tool. Actual testing will occur in the future when I have a good source of materials.

tap_drill_chart.json can be expanded to include various threads you would like to utilize. - I've misplaced my card stock tap-chart cheat sheet one to many times. So ultimately I would like this json document to contain any thread types that the Sherline CNC mill can handle.

tool_inventory.json is a list of all your tools.


 ##### The GUI: ##### 

The information below is a portion of the original pygdk readme file. The sections I've left are to show how you can expand on this GUI program and also the explaination of each of the motions.

Again, this would have taken a lot longer without people that believe in the GNU V3 and the Python G-code Development Kit - pygdk (https://github.com/cilynx/pygdk) modified by (https://github.com/grp876) 07/2025 under GNU V3.

 ##### Length of App: ##### 

You can change the height of the Output text box to fit your screen height and also show more G-Code once created. "self.output_box = ScrolledText(output_frame, wrap=tk.WORD, height=8)". You could change it to: self.output_box = ScrolledText(output_frame, wrap=tk.WORD, height=50) for example.

<img width="1015" height="526" alt="image" src="https://github.com/user-attachments/assets/daffef2b-790b-4fcc-a2fc-f9edabfaa47a" />



 ##### Featured Motions: ##### 


 ##### Bolt Circle: ##### 

machine.bolt_circle(c_x, c_y, n, r, depth)

  c_x is the x coordinate of the center of the bolt circle

  c_y is the y coordinate of the center of the bolt circle

  n is the number of bolt holes to put around the perimeter

  r is the radius of the bolt circle

  depth is how deep to drill each hole

 <img width="902" height="835" alt="image" src="https://github.com/user-attachments/assets/b5e526a5-8a24-46dd-a840-b532828c3c0e" />



 ##### Circular Pocket: ##### 

machine.circular_pocket(c_x, c_y, diameter, depth, step=None, finish=0.1, retract=True)

  c_x is the x coordinate of the center of the pocket

  c_y is the y coordinate of the center of the pocket

  diameter is the diameter of the pocket

  depth is how deep to make the pocket

  step is how much material to take off with each pass, but will be automatically calculated if not provided

  finish is how much material to leave for the finishing pass

  retract is whether or not to retract the cutter to a safe position outside of the pocket after completing the operation

  <img width="907" height="847" alt="image" src="https://github.com/user-attachments/assets/24082e9e-3d5b-44da-aa76-967f0b89908b" />



 ##### Frame: ##### 

  machine.frame(c_x, c_y, x, y, z_top=0, z_bottom=0, z_step=None, inside=False, r=None, r_steps=10)

  Like helix, but rectangular.

  c_x is the x coordinate of the center of the frame

  c_y is the y coordinate of the center of the frame

  x is the x-dimension of the frame

  y is the y-dimension of the frame

  z_top is the top of the frame -- usually 0

  z_bottom is the bottom depth of the frame -- usually something negative

  z_step is how far down z to move with each pass

  inside is whether the cutter is inside or outside the requested dimensions

  r is the corner radius

  <img width="902" height="846" alt="image" src="https://github.com/user-attachments/assets/a9ba42e2-b88f-4828-8d21-2c70e6fac2c2" />



 ##### Helix: ##### 

  machine.helix(c_x, c_y, diameter, depth, z_step=0.1, outside=False, retract=True):

  Follows a circular path in [x,y] while steadily spiraling down in z.

  c_x is the x coordinate of the center of the helix

  c_y is the y coordinate of the center of the helix

  diameter is the diameter of the helix

  depth is how deep to cut in total

  z_step is how far to move down for each rotation of the helix

  If outside is False (the default), the cutter will run inside the requested diameter. If outside is True, the cutter will run outside the requested diameter.

  retract is whether or not to retract the cutter to a safe position outside of the helix after performing the operation. If you're moving somewhere else, you probably want it to be True, but if you're going to    slot off sideways from within the helix, you might want it   to be False.

  <img width="903" height="845" alt="image" src="https://github.com/user-attachments/assets/3dc827c3-ce48-46e9-aa35-4e80046c04ac" />



 ##### Mill Drill: ##### 

  machine.mill_drill(c_x, c_y, diameter, depth, z_step=0.1, retract=True)

  Uses a helix under the hood to drill a hole that is up to 2x the diameter of the endmill being used.

  c_x is the x coordinate of the center of the hole

  c_y is the y coordinate of the center of the hole

  diameter is the diameter of the hole

  depth is how deep to drill

  z_step is how far to move down for each rotation of the helix

  retract is whether or not to retract the cutter to a safe position outside of the hole after performing the operation. Generally, you probably want to do this so it defaults to True, but it's useful to set to    False when mill-drilling to start a pocket.

  <img width="898" height="845" alt="image" src="https://github.com/user-attachments/assets/906e19cc-a7a9-4e92-b58d-b2dfabd3437b" />



 ##### Pocket Circle: ##### 

  machine.pocket_circle(c_x, c_y, n, r, depth, diameter)

  Like a Bolt Circle, but all the holes are Circular Pockets

  c_x is the x coordinate of the center of the pocket circle

  c_y is the y coordinate of the center of the pocket circle

  n is the number of pocket holes to put around the perimeter

  r is the radius of the pocket circle

  depth is how deep to mill each pocket

  diameter is the diameter of each pocket

  <img width="901" height="847" alt="image" src="https://github.com/user-attachments/assets/26f1b9ce-3e4e-40e6-b148-5de8e56d6a68" />



 ##### Rectangular Pocket: ##### 

  machine.rectangular_pocket(c_x, c_y, x, y, z_top=0, z_bottom=0, z_step=None undercut=False, retract=True):

  c_x is the x coordinate of the center of the pocket

  c_y is the y coordinate of the center of the pocket

  x is the x-dimension of the pocket

  y is the y-dimension of the pocket

  z_top is the top of the pocket -- usually 0

  z_bottom is the bottom depth of the pocket -- usually something negative

  z_step is how far down z to move with each pass when initially spiraling in

  undercut is whether or not to put "mouse ears" in the corners to provide clearance for sharp corners to mate into the pocket

  <img width="898" height="841" alt="image" src="https://github.com/user-attachments/assets/815b7d70-07ec-4935-85b1-af315eb13386" />



