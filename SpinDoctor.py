# Automation Script to Control the Hydrogel Imaging Sample Prep System
# HLS 2025

#Imports 
import logging
from mpetk.mpeconfig import source_configuration #importing stuff to post messages to the log server
import pprint
import sys
import keyboard
from time import sleep
import subprocess #used to run the wash stepper motor via the tic command interface
import yaml #used to read in information about the tic motor control board and check status
from runze_control.multichannel_syringe_pump import SY01B #import the relevant type of syringe pump from the runze control library
from runze_control.runze_device import get_protocol, set_protocol #used to set the protocol of the syringe pump if not done already
from runze_control.protocol import Protocol

#Set up the source config and print a startup message
try:
    config = source_configuration('spindoctor')
    logging.info("Configuration Loaded. Spin Doctor is on call.", extra={"weblog":True})
except Exception as e:
    logging.info("Config Error: {}".format(e), extra={"weblog":True})
    exit()

#Setup COM ports
S_COM_PORT = config['S_COM_PORT']
#Stream selector ports 
CHAMBER = config['CHAMBER']
DRAIN = config['DRAIN']
AIR = config['AIR']
WASTE = config['WASTE']
FLUID_1 = config['FLUID_1']
FLUID_2 = config['FLUID_2']
#Number of washes per cycle
num_washes = config['num_washes']
#Wash Duration, Min
#wash_time = config['wash_time'] - user requested custom wash time entry for the 3 washes
#Stain Cycle Duration, Min
#stain_time = 90
#Wash Volume, mL
wash_vol = config['wash_vol']
num_fills = int((wash_vol)/4)

#Initial Startup Message to User
print("Starting SpinDoctor. Press CTRL+C to exit at any time")
wash_time = input ("Please enter the desired duration of all washes in minutes ")

try:
    #Connect to the syringe pump
    logging.info('Connecting to the Multichannel Syringe Pump...', extra ={'weblog':True})
    try:
        pump = SY01B(S_COM_PORT, baudrate=9600, position_count=6, syringe_volume_ul=5000)
        logging.info('Connection Successful!', extra ={'weblog':True})
        #report on the status of the pump once connected
        print(f"Address: {pump.get_address()}")
        print(f"Baud rate: {pump.get_rs232_baudrate()}")
        print(f"Firmware Version: {pump.get_firmware_version()}")
        #initialize the pump to start
        logging.info("Initializing Syringe...", extra={'weblog':True})
        pump.move_valve_to_position(WASTE)
        pump.reset_syringe_position()
        logging.info('Syringe Pump is Ready', extra ={'weblog':True})
    except Exception as e:
        logging.error("Could not connect to the Multichannel Syringe Pump: {}" .format(e), extra ={"weblog":True})
        exit()
    
    #Set up the subprocess to run ticcmd 
    def ticcmd(*args):
        return subprocess.check_output(['ticcmd'] + list(args))
    #connect to the tic board using subprocess and get information on it's status
    logging.info('Connecting to the Stepper Motor...', extra ={'weblog':True})
    try:
        status = yaml.safe_load(ticcmd('-s', '--full'))
        ticname = status['Name']
        serialnum = status ['Serial number']
        firmware = status['Firmware version']
        vin = status['VIN voltage']
        energize = status['Energized']
        logging.info('Connection Successful!', extra ={'weblog':True})
        print("Tic Board Name: {}".format(ticname))
        print("Serial Number: {}".format(serialnum))
        print("Firmware Version: {}".format(firmware))
        print("VIN Voltage: {}" .format(vin))
        print("Energized?: {}".format(energize))
        #Test the motor by energizing it and moving it forward and backward
        logging.info("Testing Motor...", extra ={'weblog':True})
        ticcmd('--energize')
        ticcmd('--exit-safe-start')                                                    
        ticcmd('--velocity', str(400000) )
        sleep(3)
        ticcmd('--halt-and-hold')
        ticcmd('--velocity', str(-400000))
        sleep(3)
        ticcmd('--halt-and-hold')
        ticcmd('--deenergize')
        logging.info("Motor is ready", extra ={'weblog':True})
    except Exception as e:
        logging.error("Could not connect to the Stepper Motor Controller - {}".format(e), extra ={"weblog":True})
        exit()
    
    #Purge the lines initially
    print("Purging fill line with air...")
    pump.move_valve_to_position(AIR)
    pump.withdraw(4800)
    pump.move_valve_to_position(CHAMBER)
    pump.reset_syringe_position()
    
    #Drain the chamber initially
    print ("Draining any residuals in the Chamber")
    for i in range(num_fills):
            pump.move_valve_to_position(DRAIN)
            pump.withdraw(4800)
            pump.move_valve_to_position(WASTE)
            pump.dispense(4800)

    #Give cycle info and prompt the user to begin the cycle
    input ("Place the samples in the wash tray and place the wash tray in the basket. Press ENTER to initiate WASH Cycle")
        
    # ~~~~~~~~~~ WASH CYCLE ~~~~~~~~~~
    for i in range(num_washes):
        #prime the syringe to draw water
        print ("Priming Wash Liquid")
        pump.move_valve_to_position(FLUID_1)
        pump.withdraw(2500)
        sleep(0.5)
        pump.dispense(2500)
        sleep(0.5)
        #Draw water and fill the tank
        ticcmd('--energize')
        ticcmd('--exit-safe-start')                                                    
        wash_vel = 300000  #speed at which the motor spins durng the wash process (microsteps per 1000s)
        ticcmd('--velocity', str(wash_vel) )
        print("Filliing the Chamber...")
        for j in range(num_fills):
            pump.withdraw(4000)
            pump.move_valve_to_position(CHAMBER)
            pump.dispense(4000)
            pump.move_valve_to_position(FLUID_1)
        #Purge the lines again with air to make sure all liquid is in the chamber 
        print ("Purging fill line to finish fill...")
        pump.move_valve_to_position(AIR)
        pump.withdraw(4500)
        pump.move_valve_to_position(CHAMBER)
        pump.reset_syringe_position()
        sleep(0.5)
        
        #Wash cycle
        logging.info("Starting Wash {}/{}, time = {} minute(s)" .format( i+1, num_washes, wash_time), extra={'weblog':True})
        #Run the wash for the alloted time and then stop the motor
        mins = int(wash_time)
        wash_seconds = mins * 60
        print ("wash duration: {} seconds" .format(wash_seconds))
        for k in range(wash_seconds):
            print("Washing |", end="\r", flush=True)
            sleep(0.167)
            print("Washing /",end="\r", flush=True)
            sleep(0.167)
            print("Washing \\",end="\r", flush=True)
            sleep(0.167)
            print("Washing |",end="\r", flush=True)
            sleep(0.167)
            print("Washing /",end="\r", flush=True)
            sleep(0.167)
            print("Washing \\",end="\r", flush=True)
            sleep(0.167)
        logging.info("Wash {}/{} Complete!" .format(i+1,num_washes), extra={'weblog':True})
        
        if i == (num_washes-1): 
            #Prompt the user to remove the wash tray 
            ticcmd('--velocity', str(0) )
            ticcmd('--deenergize')
            input ("Final Wash Complete. Remove sample tray and press ENTER to drain the chamber...")
    
        # ~~~~~~~~ DRAIN ~~~~~~~~
        logging.info("Draining the Chamber...",extra={'weblog':True})
        num_drains = int(num_fills + 3)
        sleep(1)
        for m in range(num_drains):
            pump.move_valve_to_position(DRAIN)
            pump.withdraw(4000)
            pump.move_valve_to_position(WASTE)
            pump.dispense(4000)
        logging.info("Drain Complete!",extra={'weblog':True})
        ticcmd('--velocity', str(0) )
        ticcmd('--deenergize')
    
    #end of script - print a message saying goodbye
    logging.info("Washes complete. Exiting program...", extra={'weblog':True})

except KeyboardInterrupt: 
    print("User Interrupt Recieved. Exiting...")
    ticcmd('--deenergize')





















