"""
This module contains the App class which is used to create the user interface for the application
"""

__author__ = "Mahmoud Mohamed Ahmed"

# Import Modules

import os
import time
from datetime import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import control as ctl
import matplotlib.pyplot as plt
import sympy as sym


# Let's Build Our App

class App:
    """
    This class creates the user interface and provides methods to interact with the elements of the user interface.
    """
    def __init__(self):
        """
        Class constructor; it builds the user interface by invoking various private member methods.
        """

        #CREATE THE MAIN WINDOW FOR THE APPLICATION
        self.root=tk.Tk()
        self.root.title('Bode Plot')
        self.root.configure()

        #CREATE THE WORKSPACE SEGMENT
        self.__createWorkspaceSegment()


    def launch(self):
        """
        This function will launch the user interface when invoked. Internally this function invokes the mainloop()
        function on the application main window object

        PARAMETERS
        ----------
        NONE

        RETURNS
        -------
        NOTHING
        """
        self.root.mainloop()

    def __createWorkspaceSegment(self):
        """
        This private method creates the Workspace Segment in the application.

        PARAMETERS
        ----------
        NONE

        RETURNS
        -------
        NOTHING
        """
        self.workspace_segment = tk.LabelFrame(self.root, text="Choose Your Model")
        self.workspace_segment.pack(expand=1, fill=tk.X, padx=5)

#----------------------------------------------------------------------------------------------------------------------------        