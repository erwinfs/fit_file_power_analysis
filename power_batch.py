# This program allows the user to select a subfolder from where it is run
# and processes all .fit files that subfolder.
# The subfolder can have an optional race distance in km. This shold be added
# following an underscore and should be the only underscore in the folder name
# .fit files should be of the format name_ww_ftp_yyyy-mm-dd.fit
# where name is the name of rider, ww is the weight in kg (could be www :-) and
#  ftp is the ridder's current ftp. This is not very robust, no checking done on
# file & folder name formats. Results with malformed names may be unpredictable.

import csv
import os
import glob
import fitparse
import pytz
import pandas as pd
import numpy as np
from datetime import datetime
from tkinter import *
import pprint as pp
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates

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

# Create and populate df fields for moving average for each power interval
# and calculate maxima
def power_interval_stats(df, weight, res_dict):
    # Must include 30 (for NP) and 1200 (for FTP)
    power_intervals = [15, 30, 60, 300, 1200]

    power_max = [] # List to store max power for each time interval
    for i in power_intervals:
        field_name = 'power_ma' + str(i)
        interval = str(i) + 's'
        df[field_name] = df['power'].rolling(interval, min_periods = i).mean()
        max_power = df[field_name].max()
        power_max.append(max_power)

        # Create Columns min and seconds and calculate FTP
        if i < 60:
            res_dict['{0:2d}sec(w)'.format(i)] = max_power
            res_dict['{0:2d}sec(w/kg)'.format(i)] = max_power / weight
        else:
            res_dict['{0:.0f}min(w)'.format(i/60)] = max_power
            res_dict['{0:.0f}min(w/kg)'.format(i/60)] = max_power/weight
        if i == 1200:
            res_dict['EventFTP(w)'] =  max_power * 0.95
            res_dict['EventFTP(w/kg)'] =  max_power / weight * 0.95

# Create and populate df fields for moving average for each hr interval
# and calculate maxima
def hr_interval_stats(df, res_dict):
    hr_intervals = [15, 30, 60, 300, 1200]

    hr_max = [] # List to store max hr for each time interval
    for i in hr_intervals:
        field_name = 'hr_ma' + str(i)
        interval = str(i) + 's'
        df[field_name] = df['heart_rate'].rolling(interval, min_periods = i).mean()
        max_hr = df[field_name].max()
        hr_max.append(max_hr)

        if i < 60:
            res_dict['{0:2d}sec(bpm)'.format(i)] = max_hr
        else:
            res_dict['{0:.0f}min(bpm)'.format(i/60)] = max_hr

# Plot the data and output to screen if only one rider, output to files
# if there are 1 or more riders
def plot_data(df, name, event, no_res):
    fig, ax = plt.subplots(2, 1, constrained_layout=True, figsize=(10, 6))

    ax[0].plot(df.timestamp, df.heart_rate, label = 'HR')
    ax[0].set_title('Heart Rate')

    ax[1].plot(df.timestamp, df.power, label = 'Power')
    ax[1].plot(df.timestamp, df.power_ma1200, label = '20 min moving average')
    ax[1].plot(df.timestamp, df.power_ma300, label = '5 min moving average')
    ax[1].plot(df.timestamp, df.power_ma60, label = '1 min moving average')
    ax[1].set_title('Power')

    locator = mdates.AutoDateLocator(minticks=20, maxticks=30)
    formatter = mdates.ConciseDateFormatter(locator)

    for a in ax:
        a.grid(True)
        a.xaxis.set_major_locator(locator)
        a.xaxis.set_major_formatter(formatter)
        a.set_xlabel('Time')
        a.legend(loc='best')
        for label in a.get_xticklabels():
            label.set_rotation(40)
            label.set_horizontalalignment('right')
    if no_res == 1:
        plt.show()
    plt.savefig('Plot-'+ event + '-' + name + '.png')
    plt.close()

# Read the each fit file in the folder 'event' and calculate stats
# Race_distance is used to calculate means ignoring cooldown
def process_fit_data(event, race_distance):
    fit_folder = '/' + event + '/'
    fit_inputs = glob.glob('.' + fit_folder + '*.fit')
    print(fit_inputs)

    # Set columns for result data frame so that the .csv sequence is guarenteed.
    # These need to be the same as those created below
    res_cols = ['Name', 'Weight', 'FTP', 'Distance(km)', 'Duration(min)',
                'MeanPower(w)', 'NormalisedPower(w)',
                'MeanPower(w/kg)', 'IntensityFactor', 'TrainingStressScore',
                'EventFTP(w)', 'EventFTP(w/kg)', 'MaxHR',  'MeanHR', 'MeanCadence',
                '15sec(w)','15sec(w/kg)','15sec(bpm)',
                '30sec(w)', '30sec(w/kg)','30sec(bpm)',
                '1min(w)', '1min(w/kg)', '1min(bpm)',
                '5min(w)', '5min(w/kg)', '5min(bpm)',
                '20min(w)', '20min(w/kg)', '20min(bpm)', 'FileName']
    res_df = pd.DataFrame(columns = res_cols)

    # Loop through all the files in the fit folder
    for fit_input in fit_inputs:

        # Filename needs to start with weight in kg followed by '-'
        name = os.path.basename(fit_input).split('_')[0]
        weight = float(os.path.basename(fit_input).split('_')[1])
        FTP = float(os.path.basename(fit_input).split('_')[2])

        res_df.FileName.str.split('-').str[1]

        #  Read fit file using the function defined above
        data = read_fit_file(fit_input, allowed_fields, required_fields)

        # Convert list to a data frame and sort on timestamp
        df = pd.DataFrame(data)
        df.index = df.timestamp
        df = df.sort_index()

        # Print / save identifying info
        print('--- ', os.path.basename(fit_input), ' ---')
        res_dict = {'FileName': os.path.basename(fit_input), 'Weight': weight, 'Name': name, 'FTP': FTP}

        # Calculate interval stats and append to results (res_dict)
        power_interval_stats(df, weight, res_dict)
        hr_interval_stats(df, res_dict)

        # Print mean power and HR for a subset of the activity
        # Start at first distance > 0.01 (allow 10m movement) up to race_distance to cater for start delays
        dfr = df[(df.power != float('nan')) & (df.distance > 0.01) & (df.distance <= race_distance)]

        res_dict['Distance(km)'] = race_distance
        res_dict['MeanPower(w)'] = dfr.power.mean()
        res_dict['MeanPower(w/kg)'] = dfr.power.mean()/weight
        res_dict['MeanHR'] = dfr.heart_rate.mean()
        res_dict['MaxHR'] = dfr.heart_rate.max()
        res_dict['MeanCadence'] = dfr.cadence.mean()

        # Creates subset that excludes rows with no 30s moving power average and create col with ^4
        dfrNP = dfr[(dfr.power_ma30 > 0)].copy()
        dfrNP['power_ma30_4'] = dfrNP['power_ma30']**4

        # Calculate Normalised Power (this requires 30s interval to have been calculated above)
        # Calculate NP, IF and TSS
        duration = pd.Timedelta(dfr.timestamp.max() - dfr.timestamp.min()).seconds
        res_dict['Duration(min)'] = duration / 60
        normalised_power = (dfrNP.power_ma30_4.mean())**0.25 # Nominal Power
        res_dict['NormalisedPower(w)'] = normalised_power

        # If FTP was specified calculate IF and TSS
        if FTP > 0:
            intensity_factor = normalised_power / FTP  # Intensity Factor
            res_dict['IntensityFactor'] = intensity_factor

            training_stress_score = (duration * normalised_power * intensity_factor) / (FTP * 36)
            res_dict['TrainingStressScore'] = training_stress_score

        # Pretty print results sictionary to stdout
        pp.pprint(res_dict)

        # Append results dictionary to dataframe
        res_df = res_df.append(res_dict, ignore_index=True)

        # Plot data
        plot_data(df, name, event, len(fit_inputs))

    # Write resulta data frame to CSV
    res_df.to_csv('Results-' + event + '.csv', float_format='%.2f', index=False)
    print('Done')


# UI that prompts user to select folder
# -------------------------------------

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

# Menu that shows a list of subfolders
menu = OptionMenu(mainframe, variable, *subfolders)
menu.grid(row = 2, column =1)

button = Button(mainframe, text="OK", command=ok)
button.grid(row = 2, column = 2)

button = Button(mainframe, text="Quit", command=quit)
button.grid(row = 4, column = 1)

mainloop()
