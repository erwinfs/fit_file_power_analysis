# fit_file_power_analysis
Python program that analyses fit files to calculate power and hr stats.

This program allows the user to select a subfolder from where it is run
and processes all .fit files that subfolder.
The subfolder can have an optional race distance in km. This shold be added
following an underscore and should be the first underscore in the folder name,
e.g. yyyy-mm-dd_distance. 
Fit files should be of the format ww-name-yyyy-mm-dd.fit
where ww is the weight in kg (could be www :-) and name is the name of rider
Output is to a .csv file and to stdout.

The prerequisites for this are:
import csv
import os
import glob
import fitparse
import pytz
import pandas as pd
import numpy as np
from datetime import datetime
from tkinter import *

All pretty standard Python except for fitparse which is available here: https://github.com/dtcooper/python-fitparse
