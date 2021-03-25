# This program allows the user to select a subfolder from where it is run
# and processes all .fit files that subfolders.
# The subfolder can have an optional race distance in km. This shold be added
# following an underscore and should be the only underscore in the folder name
# .fit files should be of the format ww-name-yyyy-mm-dd.fit
# where ww is the weight in kg (could be www :-) and name is the name of rider
import csv
import os
import glob
import fitparse
import pytz
import pandas as pd
import numpy as np
from datetime import datetime
from tkinter import *

# Set timezone
UTC = pytz.UTC
CST = pytz.timezone('GB')

# Fields used from .fit file
allowed_fields = ['timestamp','distance', 'heart_rate', 'power',
                  'cadence', 'speed']
required_fields = ['timestamp', 'power']

# Iterate through messages and add them to data list
# This code is lifted from a fitparse example
def read_fit_file(fit_input, allowed_fields, required_fields):
    # Open file using firparse library and assign messages to variable
    fitfile = fitparse.FitFile(fit_input,
              data_processor=fitparse.StandardUnitsDataProcessor())
    messages = fitfile.messages
    # messages[10].fields

    data = []
    for m in messages:
        skip=False
        fields = m.fields

        # create an empty set to collect data in
        mdata = {}

        # check for important data types
        for field in fields:
            # Only read allowed fields
            if field.name in allowed_fields:
                # 'timestamp' gets special treatment by converting to
                # local time zone
                if field.name=='timestamp':
                    mdata[field.name] = UTC.localize(field.value).astimezone(CST)
                else:
                    # Zwift files have duplicate fields, one with value other
                    # with 'None'. This now only adds fields the either don't
                    # exist yet or with a value other than 'None'
                    if field.name not in mdata or field.value != None:
                        mdata[field.name] = field.value

        # Make sure all required fields have been read. If not, skip this item
        for rf in required_fields:
            if rf not in mdata:
                skip=True
        if not skip:
            # Append data to mdata if all required fields are present
            data.append(mdata)
    return data

# Read the each fit file in the folder 'event' and calculate stats
# Race_distance is used to calculate means ignoring cooldown
def process_fit_data(event, race_distance):
    fit_folder = '/' + event + '/'
    fit_inputs = glob.glob('.' + fit_folder + '*.fit')
    print(fit_inputs)


    # Set columns for result data frame so that the .csv sequence is guarenteed.
    # These need to be the same as those created in the loops below
    res_cols = ['Name', 'FileName', 'Weight', 'MeanPower(w)', 'MeanPower(w/kg)',
                '15sec(w)','15sec(w/kg)','15sec(bpm)',
                '30sec(w)', '30sec(w/kg)','30sec(bpm)',
                '1min(w)', '1min(w/kg)', '1min(bpm)',
                '5min(w)', '5min(w/kg)', '5min(bpm)',
                '20min(w)', '20min(w/kg)', '20min(bpm)',
                'FTP(w)', 'FTP(w/kg)', 'MaxHR',  'MeanHR', 'MeanCadence']
    res_df = pd.DataFrame(columns = res_cols)

    # Set intervals, in seconds, for which moving averagaes are calculated
    power_intervals = [15, 30, 60, 300, 1200]
    hr_intervals = [15, 30, 60, 300, 1200]


    # Loop through all the files in the fit folder
    for fit_input in fit_inputs:

        # Filename needs to start with weight in kg followed by '-'
        weight = float(os.path.basename(fit_input).split('-')[0])

        #  Read fit file using the function defined above
        data = read_fit_file(fit_input, allowed_fields, required_fields)

        # Convert list to a data frame
        df = pd.DataFrame(data)

        # Calculate moving average of power over 20 minute rolling window and
        # moving average to a new column in the data frame
        df.index = df.timestamp
        df = df.sort_index()


        # Print / save identifying info
        print('--- ', os.path.basename(fit_input), ' ---')
        print('Weight {0:0.1f} kg'.format(weight))
        res_dict = {'FileName': os.path.basename(fit_input), 'Weight': weight}

        # Create and populate df fields for moving average for each power interval
        # and calculate maxima
        power_max = [] # List to store max power for each time interval
        for i in power_intervals:
            field_name = 'power_ma' + str(i)
            interval = str(i) + 's'
            df[field_name] = df['power'].rolling(interval, min_periods = i).mean()
            power_max.append(df[field_name].max())

        # Create and populate df fields for moving average for each hr interval
        # and calculate maxima
        hr_max = [] # List to store max hr for each time interval
        for i in hr_intervals:
            field_name = 'hr_ma' + str(i)
            interval = str(i) + 's'
            df[field_name] = df['heart_rate'].rolling(interval, min_periods = i).mean()
            hr_max.append(df[field_name].max())

        # Prints power moving average max for each interval specified in the
        # list power_intervals[]
        print('Max Power over:')
        for i in range(len(power_intervals)):
            if power_intervals[i] < 60:
                print('{0:2d} sec: {1:0.0f} watt, {2:0.2f} w/kg'
                      .format(power_intervals[i], power_max[i], power_max[i]/weight))
                res_dict['{0:2d}sec(w)'.format(power_intervals[i])] = power_max[i]
                res_dict['{0:2d}sec(w/kg)'.format(power_intervals[i])] = power_max[i]/weight
            else:
                print('{0:2.0f} min: {1:0.0f} watt, {2:0.2f} w/kg'
                      .format(power_intervals[i]/60, power_max[i], power_max[i]/weight))
                res_dict['{0:.0f}min(w)'.format(power_intervals[i]/60)] = power_max[i]
                res_dict['{0:.0f}min(w/kg)'.format(power_intervals[i]/60)] = power_max[i]/weight
            if power_intervals[i] == 1200:
                print('FTP {0:0.0f}w, {1:0.2f}w/kg'.format(power_max[i] * 0.95, power_max[i]/weight * 0.95))
                res_dict['FTP(w)'] = power_max[i] * 0.95
                res_dict['FTP(w/kg)'] =  power_max[i]/weight * 0.95

        # Prints heart rate moving average max for each interval specified in the
        # list hr_intervals[]
        print('Max Heart Rate over:')
        for i in range(len(hr_intervals)):
            if hr_intervals[i] < 60:
                print('{0:2d} sec: {1:0.0f} bpm'
                      .format(hr_intervals[i], hr_max[i]))
                res_dict['{0:2d}sec(bpm)'.format(hr_intervals[i])] = hr_max[i]
            else:
                print('{0:2.0f} min: {1:0.0f} bpm'
                      .format(hr_intervals[i]/60, hr_max[i]))
                res_dict['{0:.0f}min(bpm)'.format(power_intervals[i]/60)] = power_max[i]

        # Print mean power and HR for a subset of the activity
        # Start at first distance > 0.01 (allow 10m movement) up to race_distance to cater for start delays
        dfr = df[(df.power != float('nan')) & (df.distance > 0.01) & (df.distance <= race_distance)]

        print('\nMean power: {0:0.0f}w, {1:0.2f}w/kg, Mean HR: {2:0.0f}, Max HR: {3:0.0f}, Mean cadence: {4:0.0f}'
              .format(dfr.power.mean(), dfr.power.mean()/weight, dfr.heart_rate.mean(), dfr.heart_rate.max(),
              dfr.cadence.mean()))
        print(' ')
        res_dict['MeanPower(w)'] = dfr.power.mean()
        res_dict['MeanPower(w/kg)'] = dfr.power.mean()/weight
        res_dict['MeanHR'] = dfr.heart_rate.mean()
        res_dict['MaxHR'] = dfr.heart_rate.max()
        res_dict['MeanCadence'] = dfr.cadence.mean()

        res_df = res_df.append(res_dict, ignore_index=True)

    # Strip name out from file name and add as a new column
    res_df['Name'] = res_df.FileName.str.split('-').str[1]
    # Write resulta data frame to CSV
    res_df.to_csv('Results-' + event + '.csv', float_format='%.2f', index=False)
    print('Done')


# UI that prompts user to select folder

# Function that is called when OK is pressed
# Call main function with folder name and the distance to be used
def ok():
    event = variable.get()
    # Extract distance form folder name and use large distance if none found
    if len(event.split('_')) > 1:
        race_distance = float(event.split('_')[1])
    else:
        race_distance = 1000
    print ('Folder: ', event)
    print ('Distance: ', race_distance)
    process_fit_data(event, race_distance)

# Quit function
def quit():
    global root
    root.destroy()

# Read subfolders to populate the drop down menu (exclude hidden ones)
subfolders = [f.path[2:] for f in os.scandir('.')
              if ((f.is_dir()) & (f.path[2] != '.' ))]

root = Tk()
root.title("Fit file processing utility")
# master.geometry('400x300')

# Add a grid
mainframe = Frame(root)
mainframe.grid(column=0,row=0, sticky=(N,W,E,S) )
mainframe.columnconfigure(0, weight = 1)
mainframe.rowconfigure(0, weight = 1)
mainframe.pack(pady = 100, padx = 100)

Label(mainframe, text="Choose an event").grid(row = 1, column = 1)

variable = StringVar(root)
variable.set(subfolders[0]) # default value

menu = OptionMenu(mainframe, variable, *subfolders)
menu.grid(row = 2, column =1)

button = Button(mainframe, text="OK", command=ok)
button.grid(row = 2, column = 2)

button = Button(mainframe, text="Quit", command=quit)
button.grid(row = 4, column = 1)

mainloop()
