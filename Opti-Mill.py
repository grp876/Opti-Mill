#!/usr/bin/env python3
"""
Opti-Mill - G-Code Creator for CNC Milling Operations
Version: 5.0 (Optimized)
License: GNU GPL 3.0

A comprehensive GUI application for generating G-code for various milling operations
including pockets, holes, frames, and specialized machining patterns.
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from fractions import Fraction
from pathlib import Path
from tkinter import PhotoImage
from typing import Dict, List, Optional, Union, Any
import logging

# Configure logging for debugging and error tracking
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from pygdk import Mill, Machine
except ImportError as e:
    logger.error(f"Failed to import pygdk: {e}")
    raise ImportError("pygdk module is required. Please ensure it's installed.") from e


class ToolCalculator:
    """
    Handles speed and feed calculations for various tools and materials.
    
    Provides RPM calculations based on Surface Feet per Minute (SFM) values
    and tool diameters, with interpolation for non-standard sizes.
    """
    
    def __init__(self, data: Dict[str, Any]) -> None:
        """
        Initialize calculator with tool data.
        
        Args:
            data: Dictionary containing material and tool specifications
        """
        self.data = data
        self.sfm = 0
        self.rpm = 0
        logger.info("ToolCalculator initialized")

    def interpolate_rpm(self, diameters: List[float], rpms: List[int], 
                       input_dia: float) -> Optional[float]:
        """
        Interpolate RPM for tool diameters not in the lookup table.
        
        Uses linear interpolation between the two closest diameter values
        to estimate appropriate RPM for the given diameter.
        
        Args:
            diameters: Sorted list of available tool diameters
            rpms: Corresponding RPM values for each diameter
            input_dia: Target diameter for interpolation
            
        Returns:
            Interpolated RPM value or None if out of range
        """
        for i in range(len(diameters) - 1):
            d1, d2 = diameters[i], diameters[i + 1]
            if d1 <= input_dia <= d2:
                r1, r2 = rpms[i], rpms[i + 1]
                # Linear interpolation formula
                interpolated_rpm = r1 + (r2 - r1) * ((input_dia - d1) / (d2 - d1))
                logger.debug(f"Interpolated RPM: {interpolated_rpm} for diameter: {input_dia}")
                return interpolated_rpm
        return None

    def calculate(self, material: str, tool: str, diameter: float) -> tuple[float, int]:
        """
        Calculate SFM and RPM for given material, tool, and diameter.
        
        Args:
            material: Material type (e.g., 'Aluminum', 'Steel')
            tool: Tool type (e.g., 'End Mill', 'Drill')
            diameter: Tool diameter in inches
            
        Returns:
            Tuple of (SFM, RPM) values
            
        Raises:
            ValueError: If diameter is out of interpolation range
            KeyError: If material or tool not found in data
        """
        try:
            tool_data = self.data[material][tool]
            self.sfm = tool_data["sfm"]
            rpm_dict = tool_data["rpm"]
            
            # Sort diameters for interpolation
            diameters = sorted([float(k) for k in rpm_dict.keys()])
            rpms = [rpm_dict[str(d)] for d in diameters]

            # Check for exact match first
            if str(diameter) in rpm_dict:
                self.rpm = rpm_dict[str(diameter)]
                logger.info(f"Exact RPM match found: {self.rpm}")
            else:
                # Use interpolation for non-standard diameters
                self.rpm = self.interpolate_rpm(diameters, rpms, diameter)
                if self.rpm is None:
                    error_msg = (
                        "Diameter out of range for interpolation. "
                        "Add values to tool_data.json or use Manual Mode."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

            return self.sfm, int(self.rpm)
            
        except KeyError as e:
            logger.error(f"Material/Tool not found: {e}")
            raise KeyError(f"Material '{material}' or tool '{tool}' not found in data") from e


class ToolManager:
    """
    Manages tool inventory and diameter conversions.
    
    Handles tool descriptions, diameter lookups, and fraction-to-decimal
    conversions for tool specifications.
    """
    
    def __init__(self, tools_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Initialize tool manager with inventory data.
        
        Args:
            tools_data: Dictionary containing tool inventory information
        """
        self.tools_data = tools_data
        self.diameter_map: Dict[str, float] = {}
        logger.info("ToolManager initialized")

    def get_descriptions(self, tool: str) -> List[str]:
        """
        Get available descriptions for a specific tool type.
        
        Args:
            tool: Tool type identifier
            
        Returns:
            List of tool descriptions
        """
        descriptions = []
        for item in self.tools_data.get(tool, []):
            if isinstance(item, dict) and "description" in item:
                descriptions.append(item["description"])
        logger.debug(f"Found {len(descriptions)} descriptions for tool: {tool}")
        return descriptions

    def get_diameter(self, tool: str, description: str) -> List[str]:
        """
        Get diameter as fraction string for given tool and description.
        
        Args:
            tool: Tool type identifier
            description: Specific tool description
            
        Returns:
            List containing fraction representation of diameter
        """
        for item in self.tools_data.get(tool, []):
            if (isinstance(item, dict) and 
                item.get("description") == description and 
                "diameter" in item):
                
                diameter = item["diameter"]
                # Convert to fraction for display, store decimal for calculations
                fraction_str = str(Fraction(diameter).limit_denominator())
                self.diameter_map[fraction_str] = diameter
                logger.debug(f"Mapped fraction {fraction_str} to diameter {diameter}")
                return [fraction_str]
        return []

    def get_numeric_diameter(self, fraction: str) -> Optional[float]:
        """
        Convert fraction string back to numeric diameter.
        
        Args:
            fraction: Fraction string representation
            
        Returns:
            Numeric diameter value or None if not found
        """
        return self.diameter_map.get(fraction, None)


class MotionTab(ttk.Frame):
    """
    Individual tab for each motion type (pocket, drill, etc.).
    
    Creates UI elements for motion parameters and handles G-code generation
    for the specific motion type.
    """
    
    def __init__(self, parent: ttk.Notebook, image: PhotoImage, 
                 method_name: str, motion_data: Dict[str, Any], 
                 app: 'MillApp') -> None:
        """
        Initialize motion tab with UI elements.
        
        Args:
            parent: Parent notebook widget
            image: Image to display for this motion type
            method_name: Name of the method in Mill class
            motion_data: Parameter definitions for this motion
            app: Reference to main application
        """
        super().__init__(parent)
        self.app = app
        self.method_name = method_name
        self.image = image
        self.entry: Dict[str, Union[tk.Entry, tk.BooleanVar]] = {}

        self._setup_ui(motion_data)
        logger.debug(f"MotionTab created for method: {method_name}")

    def _setup_ui(self, motion_data: Dict[str, Any]) -> None:
        """Create UI elements for motion parameters."""
        self.columnconfigure(0, weight=1)

        # Display motion type image
        tk.Label(self, image=self.image).grid(
            row=0, column=0, rowspan=len(motion_data) + 1, padx=5, pady=5
        )

        # Create input fields for each parameter
        for i, (name, default_value) in enumerate(motion_data.items()):
            if isinstance(default_value, bool):
                # Boolean parameters get checkboxes
                var = tk.BooleanVar(value=default_value)
                chk = tk.Checkbutton(self, text=name, variable=var)
                chk.grid(row=i, column=3, sticky=tk.NSEW)
                self.entry[name] = var
            else:
                # Numeric parameters get entry fields
                tk.Label(self, text=name).grid(row=i, column=2)
                ent = tk.Entry(self, justify="center")
                # Set default value if provided
                if default_value is not None:
                    ent.insert(0, str(default_value))
                ent.grid(row=i, column=3, sticky=tk.NSEW)
                self.entry[name] = ent

        # Generate G-code button
        tk.Button(
            self, text="Generate G-Code", 
            command=self.generate_gcode
        ).grid(row=10, padx=10, column=0, columnspan=5, sticky="ew")

    def generate_gcode(self) -> None:
        """
        Generate G-code for this motion type.
        
        Collects parameter values, creates Mill object, and generates
        appropriate G-code based on current settings.
        """
        try:
            # Always calculate speeds (even if using manual mode)
            self.app.calculate_speeds()

            # Create Mill object with machine configuration
            mill = Mill('sherline.json')
            mill.material = self.app.material_var.get()
            mill.tool = self.app.description_var.get()

            # Apply speed/feed settings based on mode
            self._apply_speed_settings(mill)

            # Collect and process motion parameters
            args = self._collect_motion_args()

            # Execute the motion method
            motion_func = getattr(mill, self.method_name, None)
            if not callable(motion_func):
                raise AttributeError(
                    f"Method '{self.method_name}' not found in Mill class"
                )

            motion_func(*args)
            
            # Generate and display G-code
            gcode = Machine.print_gcode(mill)
            self.app.output_box.insert(tk.END, gcode)
            logger.info(f"G-code generated for motion: {self.method_name}")
            
        except Exception as e:
            error_msg = f"Error generating G-code: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("G-Code Generation Error", error_msg)

    def _apply_speed_settings(self, mill: Mill) -> None:
        """Apply speed and feed settings based on current mode."""
        if self.app.mode_var.get() == "Manual":
            try:
                # Use manually entered values
                manual_sfm = float(self.app.sfm_entry.get())
                manual_rpm = float(self.app.rpm_entry.get())
                mill.feed = manual_sfm
                mill.rpm = manual_rpm
                logger.info(f"Using manual speeds: SFM={manual_sfm}, RPM={manual_rpm}")
            except ValueError:
                raise ValueError("Please enter valid numbers for SFM and RPM.")
        else:
            # Use calculated values
            mill.feed = self.app.calculator.sfm
            mill.rpm = self.app.calculator.rpm
            logger.info(f"Using calculated speeds: SFM={mill.feed}, RPM={mill.rpm}")

    def _collect_motion_args(self) -> List[Union[int, float, bool, str]]:
        """Collect and convert motion parameters to appropriate types."""
        args = []
        for entry_widget in self.entry.values():
            if isinstance(entry_widget, tk.BooleanVar):
                args.append(entry_widget.get())
            else:
                value = entry_widget.get()
                # Convert to appropriate numeric type if possible
                try:
                    float_val = float(value)
                    int_val = int(float_val)
                    args.append(int_val if float_val == int_val else float_val)
                except ValueError:
                    args.append(value)  # Keep as string if not numeric
        return args


class MillApp:
    """
    Main application class for Opti-Mill G-code generator.
    
    Manages the GUI, tool calculations, and G-code generation workflow.
    """
    
    def __init__(self, root: tk.Tk) -> None:
        """
        Initialize the main application.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Opti-Mill - G-Code Creator")
        self.root.columnconfigure(0, weight=1)

        # Initialize file paths
        self.base_dir = Path(__file__).parent
        self.gui_dir = self.base_dir / "GUI"

        # Load configuration data
        self._load_data_files()
        
        # Initialize managers and calculators
        self.calculator = ToolCalculator(self.tool_data)
        self.tool_manager = ToolManager(self.tools_inventory)

        # Initialize UI variables
        self._init_variables()
        
        # Motion method mapping for cleaner labels
        self.motion_method_map = {
            "boltCircle": {"method": "bolt_circle", "label": "  Bolt Circle  "},
            "frame": {"method": "frame", "label": "  Frame  "},
            "helix": {"method": "helix", "label": "  Helix  "},
            "millDrill": {"method": "mill_drill", "label": "  Mill Drill  "},
            "pocketCircle": {"method": "pocket_circle", "label": "  Pocket Circle  "},
            "circularPocket": {"method": "circular_pocket", "label": "  Circular Pocket  "},
            "legacyPocket": {"method": "legacy_pocket", "label": "  Rect Pocket or Face Mill  "}
        }

        # Build the user interface
        self.build_ui()
        logger.info("MillApp initialized successfully")

    def _load_data_files(self) -> None:
        """Load all required JSON data files."""
        try:
            # GUI form data
            with open(self.base_dir / "GUI/tkinterformdata.json") as f:
                self.tkinter_dict = json.load(f)

            # Tool specifications and speeds/feeds
            with open(self.base_dir / "tables/tool_data.json") as f:
                self.tool_data = json.load(f)

            # Tool inventory
            with open(self.base_dir / "tables/tool_inventory.json") as f:
                self.tools_inventory = json.load(f)

            # Tap drill chart
            with open(self.base_dir / "tables/tap_drill_chart.json") as f:
                self.tap_drill_data = json.load(f)
                
            logger.info("All data files loaded successfully")
            
        except FileNotFoundError as e:
            error_msg = f"Required data file not found: {e}"
            logger.error(error_msg)
            messagebox.showerror("Missing Data File", error_msg)
            raise
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in data file: {e}"
            logger.error(error_msg)
            messagebox.showerror("Invalid Data File", error_msg)
            raise

    def _init_variables(self) -> None:
        """Initialize tkinter variables for UI elements."""
        self.material_var = tk.StringVar()
        self.tool_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.diameter_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="Calculate")

    def build_ui(self) -> None:
        """Build the complete user interface."""
        # Configure main grid
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=1)

        # Create main UI sections
        self._create_setup_frame()
        self._create_speeds_feeds_frame()
        self._create_tap_drill_frame()
        self._create_motion_frame()
        self._create_output_frame()

    def _create_setup_frame(self) -> None:
        """Create the tool setup configuration frame."""
        setup_frame = ttk.LabelFrame(self.root, text="Tool Setup")
        setup_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)

        # Material selection
        ttk.Label(setup_frame, text="Material:").grid(row=0, column=0, sticky="e")
        material_menu = ttk.Combobox(
            setup_frame, textvariable=self.material_var,
            values=list(self.calculator.data.keys()), state="readonly"
        )
        material_menu.grid(row=0, column=1, padx=5, pady=2)

        # Tool type selection
        ttk.Label(setup_frame, text="Tool Type:").grid(row=1, column=0, sticky="e")
        tool_menu = ttk.Combobox(
            setup_frame, textvariable=self.tool_var,
            values=list(self.tool_manager.tools_data.keys()), state="readonly"
        )
        tool_menu.grid(row=1, column=1, padx=5, pady=2)
        tool_menu.bind("<<ComboboxSelected>>", self.update_descriptions)

        # Tool description
        ttk.Label(setup_frame, text="Description:").grid(row=2, column=0, sticky="e")
        self.description_combo = ttk.Combobox(
            setup_frame, textvariable=self.description_var, state="readonly"
        )
        self.description_combo.grid(row=2, column=1, padx=5, pady=2)
        self.description_combo.bind("<<ComboboxSelected>>", self.update_diameters)

        # Tool diameter
        ttk.Label(setup_frame, text="Tool Diameter:").grid(row=3, column=0, sticky="e")
        self.diameter_combo = ttk.Combobox(
            setup_frame, textvariable=self.diameter_var, state="readonly"
        )
        self.diameter_combo.grid(row=3, column=1, padx=5, pady=2)

        # Safe Z height (future implementation)
        ttk.Label(setup_frame, text="Safe Z: 10").grid(row=4, column=0, sticky="e")
        self.safe_z_var = ttk.Entry(setup_frame, state="disabled")
        self.safe_z_var.grid(row=4, column=1, padx=5, pady=2)

    def _create_speeds_feeds_frame(self) -> None:
        """Create the speeds and feeds configuration frame."""
        feeds_frame = ttk.LabelFrame(self.root, text="Speeds and Feeds", padding=10)
        feeds_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=5)

        # Mode selection (Calculate vs Manual)
        ttk.Label(feeds_frame, text="Mode:").grid(row=0, column=0, sticky="e")
        mode_combo = ttk.Combobox(
            feeds_frame, textvariable=self.mode_var,
            values=["Calculate", "Manual"], state="readonly"
        )
        mode_combo.grid(row=0, column=1, padx=5, pady=2)
        mode_combo.bind("<<ComboboxSelected>>", self.toggle_manual_inputs)

        # SFM entry
        ttk.Label(feeds_frame, text="SFM:").grid(row=1, column=0, sticky="e")
        self.sfm_entry = ttk.Entry(feeds_frame, state="disabled")
        self.sfm_entry.grid(row=1, column=1, padx=5, pady=2)

        # RPM entry
        ttk.Label(feeds_frame, text="RPM:").grid(row=2, column=0, sticky="e")
        self.rpm_entry = ttk.Entry(feeds_frame, state="disabled")
        self.rpm_entry.grid(row=2, column=1, padx=5, pady=2)

    def _create_tap_drill_frame(self) -> None:
        """Create the tap drill lookup frame."""
        tap_frame = ttk.LabelFrame(self.root, text="Tap Drill Lookup", padding=5)
        tap_frame.grid(row=0, column=2, sticky="nsew", padx=10, pady=5)

        # Screw size selection
        ttk.Label(tap_frame, text="Screw Size:").grid(row=0, column=0, sticky="e")
        self.screw_size_combo = ttk.Combobox(tap_frame, state="readonly")
        self.screw_size_combo.grid(row=0, column=1, padx=5, pady=2)
        self.screw_size_combo.bind("<<ComboboxSelected>>", self.update_thread_pitch)
        self.screw_size_combo['values'] = list(self.tap_drill_data.keys())

        # Thread pitch
        ttk.Label(tap_frame, text="Thread Pitch (TPI):").grid(row=1, column=0, sticky="e")
        self.thread_pitch_combo = ttk.Combobox(tap_frame, state="readonly")
        self.thread_pitch_combo.grid(row=1, column=1, padx=5, pady=2)
        self.thread_pitch_combo.bind("<<ComboboxSelected>>", self.update_thread_options)

        # Thread type
        ttk.Label(tap_frame, text="Thread % Type:").grid(row=2, column=0, sticky="e")
        self.thread_type_combo = ttk.Combobox(
            tap_frame,
            values=[
                "75% Thread for Aluminum, Brass, & Plastics",
                "50% Thread for Steel, Stainless, & Iron"
            ],
            state="readonly"
        )
        self.thread_type_combo.grid(row=2, column=1, padx=5, pady=2)
        self.thread_type_combo.bind("<<ComboboxSelected>>", self.update_drill_results)

        # Tap drill size
        ttk.Label(tap_frame, text="Tap Drill:").grid(row=3, column=0, sticky="e")
        self.tap_drill_combo = ttk.Combobox(tap_frame, state="readonly")
        self.tap_drill_combo.grid(row=3, column=1, padx=5, pady=2)

        # Clearance drill size
        ttk.Label(tap_frame, text="Clearance Drill:").grid(row=4, column=0, sticky="e")
        self.clearance_drill_combo = ttk.Combobox(tap_frame, state="readonly")
        self.clearance_drill_combo.grid(row=4, column=1, padx=5, pady=2)

    def _create_motion_frame(self) -> None:
        """Create the motion operations frame with tabs."""
        motion_frame = ttk.LabelFrame(self.root, text="Motion Operations", padding=10)
        motion_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10)
        
        self.notebook = ttk.Notebook(motion_frame)
        self.notebook.pack(expand=True, fill="both")
        
        self.load_motion_tabs()

    def _create_output_frame(self) -> None:
        """Create the G-code output and control frame."""
        output_frame = ttk.LabelFrame(self.root, text="G-Code Output", padding=10)
        output_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)
        
        # Configure grid weights for proper resizing
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(0, weight=1)

        # G-code output text area
        self.output_box = ScrolledText(
            output_frame, wrap=tk.WORD, height=8, width=80
        )
        self.output_box.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Control buttons
        button_frame = ttk.Frame(output_frame)
        button_frame.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        buttons = [
            ("Copy to Clipboard", self.to_clipboard),
            ("Save Program", self.save_program),
            ("Clear Output", self.clear_program),
            ("Exit", self.exit_application)
        ]

        for i, (text, command) in enumerate(buttons):
            tk.Button(button_frame, text=text, command=command).grid(
                row=i, column=0, sticky="ew", pady=2
            )

    # Event Handlers and Updates
    def toggle_manual_inputs(self, event=None) -> None:
        """Enable/disable manual SFM and RPM inputs based on mode."""
        mode = self.mode_var.get()
        if mode == "Manual":
            self.sfm_entry.config(state="normal")
            self.rpm_entry.config(state="normal")
            logger.info("Switched to manual speed input mode")
        else:
            self.sfm_entry.delete(0, tk.END)
            self.rpm_entry.delete(0, tk.END)
            self.sfm_entry.config(state="disabled")
            self.rpm_entry.config(state="disabled")
            logger.info("Switched to calculated speed mode")

    def update_descriptions(self, event=None) -> None:
        """Update tool descriptions when tool type changes."""
        tool = self.tool_var.get()
        descriptions = self.tool_manager.get_descriptions(tool)
        self.description_combo['values'] = descriptions
        
        if descriptions:
            self.description_var.set(descriptions[0])
            self.update_diameters()
        logger.debug(f"Updated descriptions for tool: {tool}")

    def update_diameters(self, event=None) -> None:
        """Update available diameters when tool description changes."""
        tool = self.tool_var.get()
        desc = self.description_var.get()
        diameters = self.tool_manager.get_diameter(tool, desc)
        self.diameter_combo['values'] = diameters
        
        if diameters:
            self.diameter_var.set(diameters[0])
        logger.debug(f"Updated diameters for tool: {tool}, description: {desc}")

    # Tap Drill Event Handlers
    def update_thread_pitch(self, event=None) -> None:
        """Update thread pitch options when screw size changes."""
        screw = self.screw_size_combo.get()
        if screw in self.tap_drill_data:
            tpi = self.tap_drill_data[screw]["tpi"]
            self.thread_pitch_combo['values'] = [tpi]
            self.thread_pitch_combo.set(str(tpi))
            self.thread_type_combo.set("")  # Reset downstream selections

    def update_thread_options(self, event=None) -> None:
        """Reset thread options when pitch changes."""
        self.thread_type_combo.set("")
        self.tap_drill_combo.set("")
        self.clearance_drill_combo.set("")

    def update_drill_results(self, event=None) -> None:
        """Update drill size recommendations based on thread type."""
        screw = self.screw_size_combo.get()
        thread_type = self.thread_type_combo.get()
        
        if screw not in self.tap_drill_data:
            return

        entry = self.tap_drill_data[screw]
        
        # Set tap drill size based on thread percentage
        if "75%" in thread_type:
            tap_info = entry['thread_75']
            self.tap_drill_combo.set(f"{tap_info['drill']} ({tap_info['dec_eq']})")
        elif "50%" in thread_type:
            tap_info = entry['thread_50']
            self.tap_drill_combo.set(f"{tap_info['drill']} ({tap_info['dec_eq']})")

        # Set clearance drill (using close fit)
        clearance_info = entry['clearance']['close_fit']
        self.clearance_drill_combo.set(
            f"{clearance_info['drill']} ({clearance_info['dec_eq']})"
        )

    def calculate_speeds(self) -> None:
        """Calculate speeds and feeds for current tool setup."""
        material = self.material_var.get()
        tool = self.tool_var.get()
        diameter_str = self.diameter_var.get()
        
        if not all([material, tool, diameter_str]):
            raise ValueError("Please select material, tool type, and diameter")
        
        diameter = self.tool_manager.get_numeric_diameter(diameter_str)
        if diameter is None:
            raise ValueError("Invalid diameter selection")
        
        self.calculator.calculate(material, tool, diameter)

    def load_motion_tabs(self) -> None:
        """Load motion operation tabs with images and parameters."""
        images = {}
        
        # Load images for each motion type
        for key in self.tkinter_dict:
            try:
                img_path = self.gui_dir / f"{key}.png"
                images[key] = PhotoImage(file=img_path)
            except Exception as e:
                logger.warning(f"Image for '{key}' not found: {e}")
                images[key] = PhotoImage()  # Blank fallback image

        # Create tabs for each motion type
        for motion_key, params in self.tkinter_dict.items():
            motion_info = self.motion_method_map.get(
                motion_key, {"method": motion_key, "label": motion_key}
            )
            method_name = motion_info["method"]
            label = motion_info["label"]
            
            tab = MotionTab(
                self.notebook, images[motion_key], method_name, params, self
            )
            self.notebook.add(tab, text=label)

    # Output Control Methods
    def to_clipboard(self) -> None:
        """Copy G-code output to system clipboard."""
        try:
            text = self.output_box.get('1.0', tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            logger.info("G-code copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            messagebox.showerror("Clipboard Error", f"Failed to copy to clipboard: {e}")

    def clear_program(self) -> None:
        """Clear the G-code output area."""
        self.output_box.delete('1.0', tk.END)
        logger.info("G-code output cleared")

    def save_program(self) -> None:
        """Save G-code output to file."""
        text = self.output_box.get('1.0', tk.END).strip()
        
        if not text:
            messagebox.showwarning("No Content", "No G-code to save.")
            return
            
        # Open file dialog for saving
        file_path = filedialog.asksaveasfilename(
            defaultextension=".nc",
            filetypes=[
                ("G-code files", "*.nc"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ],
            title="Save G-code Program"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("Success", f"G-code saved successfully to:\n{file_path}")
                logger.info(f"G-code saved to: {file_path}")
            except Exception as e:
                error_msg = f"Could not save file: {e}"
                logger.error(error_msg)
                messagebox.showerror("Save Error", error_msg)

    def exit_application(self) -> None:
        """Exit the application with confirmation."""
        if messagebox.askokcancel("Exit", "Are you sure you want to exit Opti-Mill?"):
            logger.info("Application exiting")
            self.root.quit()


def main() -> None:
    """Main entry point for the application."""
    try:
        # Create and configure root window
        root = tk.Tk()
        root.resizable(False, False)  # Fixed window size for consistent layout
        
        # Initialize application
        app = MillApp(root)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        messagebox.showerror("Startup Error", f"Failed to start Opti-Mill: {e}")
        raise


if __name__ == "__main__":
    main()