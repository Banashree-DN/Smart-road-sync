import random
import math
import time
import threading
import pygame
import sys
import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

# Read CSV and skip the header row if necessary
try:
    df = pd.read_csv("data_new.csv", skiprows=1, names=["right", "down", "left", "up", "total_passed", "avg_wt_time"])

    # Convert columns to numeric and handle non-numeric values
    df['right'] = pd.to_numeric(df['right'], errors='coerce')
    df['down'] = pd.to_numeric(df['down'], errors='coerce')
    df['left'] = pd.to_numeric(df['left'], errors='coerce')
    df['up'] = pd.to_numeric(df['up'], errors='coerce')

    # Prepare data for Linear Regression (using simplified time index for training)
    x = np.array(np.arange(0, len(df))).reshape(-1, 1)
    
    # Train models
    right_model = LinearRegression().fit(x, np.array(df['right']).reshape(-1, 1))
    down_model = LinearRegression().fit(x, np.array(df['down']).reshape(-1, 1))
    left_model = LinearRegression().fit(x, np.array(df['left']).reshape(-1, 1))
    up_model = LinearRegression().fit(x, np.array(df['up']).reshape(-1, 1))

except FileNotFoundError:
    print("Warning: data_new.csv not found. ML prediction for proportional timing is disabled.")
    # Initialize models to None if file is missing
    right_model = down_model = left_model = up_model = None
except Exception as e:
    print(f"Error loading or training ML models: {e}. ML prediction is disabled.")
    right_model = down_model = left_model = up_model = None

# New global flags for emergency mode
isEmergency = False
emergencyDirection = None
emergencyTransitionYellow = False # <--- NEW FLAG FOR YELLOW TRANSITION

vehicles = {
    'right': {0: [], 1: [], 2: [], 'crossed': 0},
    'down': {0: [], 1: [], 2: [], 'crossed': 0},
    'left': {0: [], 1: [], 2: [], 'crossed': 0},
    'up': {0: [], 1: [], 2: [], 'crossed': 0}
}

#to store count of total vehicles after each time unit
totalVehicles=0
totalVehiclesLane1=0
totalVehiclesLane2=0
totalVehiclesLane3=0
totalVehiclesLane4=0
totalWaitingTime=0
oneTimeUnit=60 # The maximum green time unit for proportional logic

# Default values of signal times
defaultRed = 150
defaultYellow = 5
defaultGreen = 10
defaultMinimum = 10
defaultMaximum = 60

signals = []
noOfSignals = 4
simTime = 36000       # change this to change time of simulation
timeElapsed = 0

currentGreen = 0   # Indicates which signal is green
nextGreen = (currentGreen + 1) % noOfSignals
currentYellow = 0   # Indicates whether yellow signal is on or off 

# Average times for vehicles to pass the intersection
carTime = 2
bikeTime = 1
rickshawTime = 2.25 
busTime = 2.5
truckTime = 2.5

# Count of cars at a traffic signal
noOfCars = 0
noOfBikes = 0
noOfBuses =0
noOfTrucks = 0
noOfRickshaws = 0
noOfLanes = 2

# Red signal time at which cars will be detected at a signal
detectionTime = 5

# Added 'emergency' vehicle speed (faster)
speeds = {'car':2.25, 'bus':1.8, 'truck':1.8, 'rickshaw':2, 'bike':2.5, 'emergency':3.0}  

# Coordinates of start
x = {'right':[0,0,0], 'down':[755,727,697], 'left':[1400,1400,1400], 'up':[602,627,657]}    
y = {'right':[348,370,398], 'down':[0,0,0], 'left':[498,466,436], 'up':[800,800,800]}

vehicles = {'right': {0:[], 1:[], 2:[], 'crossed':0}, 'down': {0:[], 1:[], 2:[], 'crossed':0}, 'left': {0:[], 1:[], 2:[], 'crossed':0}, 'up': {0:[], 1:[], 2:[], 'crossed':0}}
# Added 'emergency' as a vehicle type (type 5)
vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'rickshaw', 4:'bike', 5:'emergency'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# Coordinates of signal image, timer, and vehicle count
signalCoods = [(530,230),(810,230),(810,570),(530,570)]
signalTimerCoods = [(530,210),(810,210),(810,550),(530,550)]
vehicleCountCoods = [(480,210),(880,210),(880,550),(480,550)]
vehicleCountTexts = ["0", "0", "0", "0"]

#Carbon Emission Data
carbonEmissionCoods=[10,75] 
totalCarbonEmission=0
# Added carbon value for 'emergency' vehicle (higher value)
carbonValue={"car":0.8,"bus":1.2,"truck":1.3,"rickshaw":0.9,"bike":0.3,"emergency":1.5} #Carbon emission of vehicles per second in micro-grams

# Coordinates of stop lines
stopLines = {'right': 590, 'down': 330, 'left': 800, 'up': 535}
defaultStop = {'right': 580, 'down': 320, 'left': 810, 'up': 545}
stops = {'right': [580,580,580], 'down': [320,320,320], 'left': [810,810,810], 'up': [545,545,545]}

mid = {'right': {'x':705, 'y':445}, 'down': {'x':695, 'y':450}, 'left': {'x':695, 'y':425}, 'up': {'x':695, 'y':400}}
rotationAngle = 3

# Gap between vehicles
gap = 15    # stopping gap
gap2 = 15   # moving gap


pygame.init()
simulation = pygame.sprite.Group()


def activateEmergencySignal(direction_index):
    """Overrides the traffic signal system to prioritize the emergency vehicle."""
    global currentGreen, currentYellow, isEmergency, emergencyDirection, emergencyTransitionYellow
    
    # Do nothing if emergency mode is already active or in transition
    if isEmergency or emergencyTransitionYellow:
        return

    # Check if the emergency direction is ALREADY the current green signal
    if currentGreen == direction_index:
        # Emergency direction is already green, just extend the green time and stop other lanes
        isEmergency = True
        emergencyDirection = directionNumbers[direction_index]
        currentYellow = 0 # Ensure yellow is off
        for i in range(noOfSignals):
            if i == direction_index:
                signals[i].green = defaultMaximum * 4  
                signals[i].red = 0
                signals[i].yellow = 0
            else:
                signals[i].red = defaultMaximum * 4 
                signals[i].yellow = 0
                signals[i].green = 0
        print(f"!!! Emergency detected in {emergencyDirection}, extending green time. !!!")
        return

    # Standard transition: Stop current green traffic with a yellow light.
    print(f"!!! Emergency detected in {directionNumbers[direction_index]} !!! Starting Emergency Yellow Transition from {directionNumbers[currentGreen]}.")
    
    emergencyDirection = directionNumbers[direction_index] # Set direction for the *next* state
    emergencyTransitionYellow = True # Activate the special yellow state
    
    # Force the current green signal to yellow immediately
    signals[currentGreen].green = 0 # Ends the green, repeat() handles the yellow phase
    
def checkForEmergency():
    """Checks for an approaching emergency vehicle and activates/deactivates emergency mode."""
    global isEmergency, emergencyDirection, currentGreen, nextGreen

    # If already in emergency mode, only check for clearance
    if isEmergency:
        # Check if ALL emergency vehicles in the emergencyDirection have crossed
        all_clear = True
        
        # Check for un-crossed emergency vehicles in the active emergency lane
        for lane in vehicles[emergencyDirection]:
            if lane == 'crossed': continue
            if any(v.is_emergency and v.crossed == 0 for v in vehicles[emergencyDirection][lane]):
                all_clear = False
                break

        if all_clear:
            # All emergency vehicles in the dedicated lane have cleared
            print(f"!!! Emergency vehicle cleared in {emergencyDirection} !!! Resuming normal operation.")
            isEmergency = False
            emergencyDirection = None
            # Force the current green signal timer (which was the emergency lane) to end immediately
            # This triggers the yellow light and returns control to the normal repeat() cycle.
            signals[currentGreen].green = 0
        return
        
    # If not in emergency mode, check for a new detection
    emergency_detected_direction_index = None
    
    # Check for a new un-crossed emergency vehicle
    for i in range(noOfSignals):
        direction = directionNumbers[i]
        for lane in vehicles[direction]:
            if lane == 'crossed': continue
            # Check if an emergency vehicle is waiting to cross (crossed==0)
            if any(v.is_emergency and v.crossed == 0 for v in vehicles[direction][lane]):
                emergency_detected_direction_index = i
                break
        if emergency_detected_direction_index is not None: 
            break

    if emergency_detected_direction_index is not None and not isEmergency and not emergencyTransitionYellow:
        # Emergency detected, activate override
        direction_index = emergency_detected_direction_index
        activateEmergencySignal(direction_index)


class TrafficSignal:
    def __init__(self, red, yellow, green, minimum, maximum):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.minimum = minimum
        self.maximum = maximum
        self.signalText = "30"
        self.totalGreenTime = 0
        
class Vehicle(pygame.sprite.Sprite):
    global totalCarbonEmission
    global totalWaitingTime
    def __init__(self, lane, vehicleClass, direction_number, direction, will_turn, is_emergency=False):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        
        self.is_emergency = is_emergency
        
        # Use 'emergency' speed and class if emergency flag is set
        if self.is_emergency:
             self.speed = speeds['emergency'] 
             self.vehicleClass = 'emergency'
        else:
             self.speed = speeds.get(vehicleClass, speeds['car'])
             self.vehicleClass = vehicleClass
             
        # --- FIX FOR AttributeError: 'Vehicle' object has no attribute 'currentImage' ---
        # 1. Load images first to ensure attributes exist before they are used later in __init__
        image_class = self.vehicleClass
        path = "images/" + direction + "/" + image_class + ".png"
        if self.is_emergency and not os.path.exists(path):
            # Fallback to car image for emergency if specific image not found
            path = "images/" + direction + "/" + 'car' + ".png" 

        try:
            self.originalImage = pygame.image.load(path)
            self.currentImage = pygame.image.load(path)
        except pygame.error as e:
            # Handle case where the image file might be missing entirely
            print(f"Error loading image at {path}: {e}. Vehicle creation aborted.")
            return # Abort initialization if image fails to load
        # ---------------------------------------------------------------------------------

        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        self.willTurn = will_turn
        self.turned = 0
        self.rotateAngle = 0
        self.waitingTime=0
        
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1
        
        self.isOn=1 #by default the engine would be on , which we would be toggling it on random basis on traffic signal

    
        if(direction=='right'):
            if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):    # if more than 1 vehicle in the lane of vehicle before it has crossed stop line
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].currentImage.get_rect().width - gap         # setting stop coordinate as: stop coordinate of next vehicle - width of next vehicle - gap
            else:
                self.stop = defaultStop[direction]
            # Set new starting and stopping coordinate
            temp = self.currentImage.get_rect().width + gap    
            x[direction][lane] -= temp
            stops[direction][lane] -= temp
        elif(direction=='left'):
            if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].currentImage.get_rect().width + gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().width + gap
            x[direction][lane] += temp
            stops[direction][lane] += temp
        elif(direction=='down'):
            if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].currentImage.get_rect().height - gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] -= temp
            stops[direction][lane] -= temp
        elif(direction=='up'):
            if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].currentImage.get_rect().height + gap
            else:
                self.stop = defaultStop[direction]
            temp = self.currentImage.get_rect().height + gap
            y[direction][lane] += temp
            stops[direction][lane] += temp
        simulation.add(self)


    def render(self, screen):
        screen.blit(self.currentImage, (self.x, self.y))

    def move(self):
        global totalCarbonEmission
        global totalWaitingTime
        global isEmergency
        global emergencyDirection
        
        carb_value = carbonValue.get(self.vehicleClass, carbonValue['car'])
        
        # --- EMERGENCY ROUTING OVERRIDE ---
        # If an emergency is active AND this is NOT the emergency lane, 
        # the vehicle stops, UNLESS it has already crossed the stop line (self.crossed == 1).
        # This allows committed vehicles to clear the intersection.
        if isEmergency and self.direction != emergencyDirection and self.crossed == 0:
            self.waitingTime += 1
            totalWaitingTime += 1
            # Engine idling/off logic when stopped
            if self.isOn == 1:
                self.isOn = random.randint(0, 1)
                totalCarbonEmission += (carb_value * self.isOn)
            return # Vehicle is stopped by emergency override
        
        # --- NORMAL MOVEMENT LOGIC (Rest of the original function) ---

        if(self.direction=='right'):
            if(self.crossed==0 and self.x+self.currentImage.get_rect().width>stopLines[self.direction]):   # if the image has crossed stop line now
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
            if(self.willTurn==1):
                if(self.crossed==0 or self.x+self.currentImage.get_rect().width<mid[self.direction]['x']):
                    if((self.x+self.currentImage.get_rect().width<=self.stop or (currentGreen==0 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - gap2) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                        self.x += self.speed
                        totalCarbonEmission+=carb_value
                    else:
                        if not self.is_emergency and self.isOn==1:
                            self.isOn=random.randint(0,1)
                            totalCarbonEmission+=(carb_value*self.isOn) 
                        self.waitingTime+=1
                        totalWaitingTime+=1
                else:   
                    if(self.turned==0):
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x += 2
                        self.y += 1.8
                        totalCarbonEmission+=carb_value
                        if(self.rotateAngle==90):
                            self.turned = 1
                    else:
                        if(self.index==0 or self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - gap2) or self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - gap2)):
                            self.y += self.speed
                            totalCarbonEmission+=carb_value
            else: 
                if((self.x+self.currentImage.get_rect().width<=self.stop or self.crossed == 1 or (currentGreen==0 and currentYellow==0)) and (self.index==0 or self.x+self.currentImage.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - gap2) or (vehicles[self.direction][self.lane][self.index-1].turned==1))):                
                # (if the image has not reached its stop coordinate or has crossed stop line or has green signal) and (it is either the first vehicle in that lane or it is has enough gap to the next vehicle in that lane)
                    self.x += self.speed  # move the vehicle
                    totalCarbonEmission+=carb_value
                    
                else:
                    self.waitingTime+=1
                    totalWaitingTime+=1
                    #here the vehicle has stopped 
                    #if engine is ON then on random basis we'll turn it on or off
                    if not self.is_emergency and self.isOn==1:
                        self.isOn=random.randint(0,1)
                        totalCarbonEmission+=(carb_value*self.isOn) #if isOn is 0 then no carb emission , else carbon emission


        elif(self.direction=='down'):
            if(self.crossed==0 and self.y+self.currentImage.get_rect().height>stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
            if(self.willTurn==1):
                if(self.crossed==0 or self.y+self.currentImage.get_rect().height<mid[self.direction]['y']):
                    if((self.y+self.currentImage.get_rect().height<=self.stop or (currentGreen==1 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - gap2) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                        self.y += self.speed
                        totalCarbonEmission+=carb_value
                    else:
                        if not self.is_emergency and self.isOn==1:
                            self.isOn=random.randint(0,1)
                            totalCarbonEmission+=(carb_value*self.isOn)
                        self.waitingTime+=1
                        totalWaitingTime+=1
                else:   
                    if(self.turned==0):
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x -= 2.5
                        self.y += 2
                        totalCarbonEmission+=carb_value
                        if(self.rotateAngle==90):
                            self.turned = 1
                    else:
                        if(self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or self.y<(vehicles[self.direction][self.lane][self.index-1].y - gap2)):
                            self.x -= self.speed
                            totalCarbonEmission+=carb_value
            else: 
                if((self.y+self.currentImage.get_rect().height<=self.stop or self.crossed == 1 or (currentGreen==1 and currentYellow==0)) and (self.index==0 or self.y+self.currentImage.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - gap2) or (vehicles[self.direction][self.lane][self.index-1].turned==1))):                
                    self.y += self.speed
                    totalCarbonEmission+=carb_value
                else:
                    self.waitingTime+=1
                    totalWaitingTime+=1
                    #here the vehicle has stopped 
                    #if engine is ON then on random basis we'll turn it on or off
                    if not self.is_emergency and self.isOn==1:
                        self.isOn=random.randint(0,1)
                        totalCarbonEmission+=(carb_value*self.isOn) #if isOn is 0 then no carb emission , else carbon emission
            
        elif(self.direction=='left'):
            if(self.crossed==0 and self.x<stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                totalCarbonEmission+=carb_value
            if(self.willTurn==1):
                if(self.crossed==0 or self.x>mid[self.direction]['x']):
                    if((self.x>=self.stop or (currentGreen==2 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                        self.x -= self.speed
                        totalCarbonEmission+=carb_value
                    else:
                        if not self.is_emergency and self.isOn==1:
                            self.isOn=random.randint(0,1)
                            totalCarbonEmission+=(carb_value*self.isOn)
                        self.waitingTime+=1
                        totalWaitingTime+=1
                else: 
                    if(self.turned==0):
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x -= 1.8
                        self.y -= 2.5
                        totalCarbonEmission+=carb_value
                        if(self.rotateAngle==90):
                            self.turned = 1
                    else:
                        if(self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height +  gap2) or self.x>(vehicles[self.direction][self.lane][self.index-1].x + gap2)):
                            self.y -= self.speed
                            totalCarbonEmission+=carb_value
            else: 
                if((self.x>=self.stop or self.crossed == 1 or (currentGreen==2 and currentYellow==0)) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width + gap2) or (vehicles[self.direction][self.lane][self.index-1].turned==1))):                
                # (if the image has not reached its stop coordinate or has crossed stop line or has green signal) and (it is either the first vehicle in that lane or it is has enough gap to the next vehicle in that lane)
                    self.x -= self.speed  # move the vehicle    
                    totalCarbonEmission+=carb_value
                else:
                    self.waitingTime+=1
                    totalWaitingTime+=1
                    #here the vehicle has stopped 
                    #if engine is ON then on random basis we'll turn it on or off
                    if not self.is_emergency and self.isOn==1:
                        self.isOn=random.randint(0,1)
                        totalCarbonEmission+=(carb_value*self.isOn) #if isOn is 0 then no carb emission , else carbon emission
        elif(self.direction=='up'):
            if(self.crossed==0 and self.y<stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                totalCarbonEmission+=carb_value
            if(self.willTurn==1):
                if(self.crossed==0 or self.y>mid[self.direction]['y']):
                    if((self.y>=self.stop or (currentGreen==3 and currentYellow==0) or self.crossed == 1) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height +  gap2) or vehicles[self.direction][self.lane][self.index-1].turned==1)):
                        self.y -= self.speed
                        totalCarbonEmission+=carb_value
                    else:
                        if not self.is_emergency and self.isOn==1:
                            self.isOn=random.randint(0,1)
                            totalCarbonEmission+=(carb_value*self.isOn)
                        self.waitingTime+=1
                        totalWaitingTime+=1
                else:   
                    if(self.turned==0):
                        self.rotateAngle += rotationAngle
                        self.currentImage = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x += 1
                        self.y -= 1
                        totalCarbonEmission+=carb_value
                        if(self.rotateAngle==90):
                            self.turned = 1
                    else:
                        if(self.index==0 or self.x<(vehicles[self.direction][self.lane][self.index-1].x - vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().width - gap2) or self.y>(vehicles[self.direction][self.lane][self.index-1].y + gap2)):
                            self.x += self.speed
                            totalCarbonEmission+=carb_value
            else: 
                if((self.y>=self.stop or self.crossed == 1 or (currentGreen==3 and currentYellow==0)) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].currentImage.get_rect().height + gap2) or (vehicles[self.direction][self.lane][self.index-1].turned==1))):                
                    self.y -= self.speed
                    totalCarbonEmission+=carb_value
                else:
                    self.waitingTime+=1
                    totalWaitingTime+=1
                    #here the vehicle has stopped 
                    #if engine is ON then on random basis we'll turn it on or off
                    if not self.is_emergency and self.isOn==1:
                        self.isOn=random.randint(0,1)
                        totalCarbonEmission+=(carb_value*self.isOn) #if isOn is 0 then no carb emission , else carbon emission

# Initialization of signals with default values
def initialize():
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts1)
    ts2 = TrafficSignal(ts1.red+ts1.yellow+ts1.green, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts2)
    ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts3)
    ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen, defaultMinimum, defaultMaximum)
    signals.append(ts4)
    repeat()

# Set time according to formula
def setTime():
    global totalCarbonEmission,totalWaitingTime , vehicles
    global noOfCars, noOfBikes, noOfBuses, noOfTrucks, noOfRickshaws, noOfLanes
    global carTime, busTime, truckTime, rickshawTime, bikeTime
    global totalVehicles,totalVehiclesLane1,totalVehiclesLane2,totalVehiclesLane3,totalVehiclesLane4,oneTimeUnit
    global isEmergency # Add global for isEmergency
    global right_model, down_model, left_model, up_model

    if isEmergency or emergencyTransitionYellow: # Skip proportional time setting during emergency
        return

    noOfCars, noOfBikes, noOfBuses, noOfTrucks, noOfRickshaws = 0,0,0,0,0
    
    # 1. Count vehicles for the NEXT green signal (which is currentGreen + 1)
    next_direction = directionNumbers[nextGreen]
    for j in range(len(vehicles[next_direction][0])):
        vehicle = vehicles[next_direction][0][j]
        if(vehicle.crossed==0):
            # Exclude 'emergency' from proportional calculation
            if vehicle.vehicleClass != 'emergency':
                noOfBikes += 1
    for i in range(1,3):
        for j in range(len(vehicles[next_direction][i])):
            vehicle = vehicles[next_direction][i][j]
            if(vehicle.crossed==0):
                vclass = vehicle.vehicleClass
                # Exclude 'emergency' from proportional calculation
                if vclass == 'car':
                    noOfCars += 1
                elif vclass == 'bus':
                    noOfBuses += 1
                elif vclass == 'truck':
                    noOfTrucks += 1
                elif vclass == 'rickshaw':
                    noOfRickshaws += 1

    currentLaneCount = noOfCars + noOfBuses + noOfTrucks + noOfRickshaws + noOfBikes
    
    # 2. Get Predicted Green Time based on ML/Proportional Logic
    predicted_flow = 0
    greenTime = defaultMinimum

    if timeElapsed > 0 and right_model and down_model and left_model and up_model:
        # ML prediction attempt (using the timeElapsed as the index for flow prediction)
        t = np.array([[timeElapsed]])
        if next_direction == "right":
            predicted_flow = right_model.predict(t)[0][0]
        elif next_direction == "down":
            predicted_flow = down_model.predict(t)[0][0]
        elif next_direction == "left":
            predicted_flow = left_model.predict(t)[0][0]
        elif next_direction == "up":
            predicted_flow = up_model.predict(t)[0][0]
        
        # Simple proportional timing based on current flow 
        total_flow = totalVehiclesLane1 + totalVehiclesLane2 + totalVehiclesLane3 + totalVehiclesLane4
        if total_flow != 0:
            # Use current vehicle count for the target lane for simple proportional logic
            greenTime = int((currentLaneCount / total_flow) * oneTimeUnit)
            
    else:
        # Fallback to Simple Proportional Timing (as in simulation_proportional.py)
        total_flow = totalVehiclesLane1 + totalVehiclesLane2 + totalVehiclesLane3 + totalVehiclesLane4
        if total_flow != 0:
            greenTime = int((currentLaneCount / total_flow) * oneTimeUnit)
            
    
    # Ensure green time is within limits
    greenTime = max(defaultMinimum, min(defaultMaximum, greenTime))
    
    # 3. Data Logging and Waiting Time Calculation (Original logic preserved)
    
    # After each unit of time We will reach to right lane , so storing data at that point only
    if(directionNumbers[(currentGreen+1)%noOfSignals]=="right"):
        # Calculate total vehicle count across all lanes for logging purposes
        total_count_log = totalVehiclesLane1+totalVehiclesLane2+totalVehiclesLane3+totalVehiclesLane4
        if(total_count_log==0):#as it would return infinity
            avg_waiting=0
        else:
            avg_waiting=math.ceil(totalWaitingTime/total_count_log)
            
        print(f"Debug : Total waiting Time : {totalWaitingTime} Total Vehicles : {total_count_log} Avg : {avg_waiting}")

        # Log data for the previous cycle
        file=open('data_new.csv','a') #This is the file in which I will be storing all details
        file.write(str(totalVehiclesLane1)+','+str(totalVehiclesLane2)+','+str(totalVehiclesLane3)+','+str(totalVehiclesLane4)+','+str(total_count_log)+','+str(avg_waiting)+'\n')
        file.close()

    # Waiting time only counts for vehicles NOT in the next green lane
    directions=["right","down","left","up"]
    for dir in directions:
        if dir==next_direction:
            continue
        else:
            for i in range(0,3):
                for vehicle in vehicles[dir][i]:
                    if vehicle.crossed == 0 and not vehicle.is_emergency: # Don't count waiting time for emergency if it's currently stopped by a normal light
                        vehicle.waitingTime+=1
                        totalWaitingTime+=1
                
    # Update total vehicle counters (current flow)
    totalVehiclesLaneCount = noOfCars+noOfRickshaws+noOfBuses+noOfTrucks+noOfBikes
    
    #storing count of vehicles from each lane
    if(next_direction=="right"):
        totalVehiclesLane1+=totalVehiclesLaneCount
    elif(next_direction=="down"):
        totalVehiclesLane2+=totalVehiclesLaneCount
    elif(next_direction=="left"):
        totalVehiclesLane3+=totalVehiclesLaneCount
    elif(next_direction=="up"):
        totalVehiclesLane4+=totalVehiclesLaneCount
    
    # 4. Apply calculated green time
    signals[nextGreen].green = greenTime
    print(f'Setting Green Time for {next_direction}: {greenTime} seconds')

   
def repeat():
    global currentGreen, currentYellow, nextGreen, isEmergency, emergencyTransitionYellow
    
    while(signals[currentGreen].green>0):   # while the timer of current green signal is not zero
        
        checkForEmergency() # Check for emergency on every iteration
        
        printStatus()
        updateValues()
        
        # Only set time for next signal if not in emergency mode AND not in emergency transition
        if(signals[(currentGreen+1)%(noOfSignals)].red==detectionTime and not isEmergency and not emergencyTransitionYellow):    
            thread = threading.Thread(name="detection",target=setTime, args=())
            thread.daemon = True
            thread.start()
        
        time.sleep(1)
        
    # --- TRANSITION TO YELLOW ---
    # This block handles the standard or emergency-induced yellow transition
    currentYellow = 1   # set yellow signal on
    vehicleCountTexts[currentGreen] = "0"
    
    # reset stop coordinates of lanes and vehicles 
    for i in range(0,3):
        stops[directionNumbers[currentGreen]][i] = defaultStop[directionNumbers[currentGreen]]
        for vehicle in vehicles[directionNumbers[currentGreen]][i]:
            # Added a check here to ensure the vehicle object is fully initialized (in case of failed image load)
            if hasattr(vehicle, 'currentImage'):
                vehicle.stop = defaultStop[directionNumbers[currentGreen]]
            
    # --- YELLOW PHASE LOOP ---
    while(signals[currentGreen].yellow>0):  # while the timer of current yellow signal is not zero
        
        checkForEmergency() # Keep checking for emergency during yellow
        
        # If emergency transition is active and the yellow time is about to expire, force it
        if emergencyTransitionYellow and signals[currentGreen].yellow <= 1:
            signals[currentGreen].yellow = 0 # Force end of yellow
            break 
        
        # If emergency is detected and current green finished its yellow, or yellow naturally ends
        if isEmergency:
            signals[currentGreen].yellow = 0 # This condition is now mainly for emergency clearance
            break 
            
        printStatus()
        updateValues()
        time.sleep(1)
        
    currentYellow = 0   # set yellow signal off
    
    # --- TRANSITION TO NEXT SIGNAL (Normal or Emergency) ---
    
    if emergencyTransitionYellow:
        # Emergency transition is complete, apply the emergency signal state
        isEmergency = True
        emergencyTransitionYellow = False # Turn off the special flag

        # Get the index of the detected emergency direction
        # Note: directionNumbers is a dict {0:'right', 1:'down', ...}
        direction_index = -1
        for key, value in directionNumbers.items():
            if value == emergencyDirection:
                direction_index = key
                break
        
        # Apply the long red/green state now
        for i in range(noOfSignals):
            if i == direction_index:
                # Set the emergency lane to a very long green time
                signals[i].green = defaultMaximum * 4  
                signals[i].red = 0
                signals[i].yellow = 0
                currentGreen = i # Explicitly set currentGreen to the emergency lane
            else:
                # Set all other lanes to long red time
                signals[i].red = defaultMaximum * 4 
                signals[i].yellow = 0
                signals[i].green = 0
        
        nextGreen = (currentGreen + 1) % noOfSignals # Update nextGreen based on the new currentGreen
        
    elif not isEmergency: # Only reset to default and transition normally if not in emergency mode
        # Reset all signal times of current signal to default times
        signals[currentGreen].green = defaultGreen
        signals[currentGreen].yellow = defaultYellow
        signals[currentGreen].red = defaultRed
       
        # Normal cycle transition
        currentGreen = nextGreen # set next signal as green signal
        nextGreen = (currentGreen+1)%noOfSignals    # set next green signal
        signals[nextGreen].red = signals[currentGreen].yellow+signals[currentGreen].green    # set the red time of next to next signal as (yellow time + green time) of next signal

    # Repeat loop starts over with the new currentGreen state (either emergency or normal)
    repeat()     

# Print the signal timers on cmd
def printStatus():                                                                                           
    # Added emergency status print
    global isEmergency, emergencyDirection, emergencyTransitionYellow
    if isEmergency:
        status_label = f"EMERGENCY: {emergencyDirection}"
    elif emergencyTransitionYellow:
        status_label = f"EMERGENCY TRANSITION: STOPPING {directionNumbers[currentGreen]}"
    else:
        status_label = "NORMAL CYCLE"

    print(f"--- {status_label} ---")
    
    for i in range(0, noOfSignals):
        if(i==currentGreen):
            if(currentYellow==0):
                print(" GREEN TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
            else:
                print("YELLOW TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
        else:
            print("   RED TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
    print()

# Update values of the signal timers after every second
def updateValues():
    for i in range(0, noOfSignals):
        if(i==currentGreen):
            if(currentYellow==0):
                signals[i].green-=1
                signals[i].totalGreenTime+=1
            else:
                signals[i].yellow-=1
        else:
            signals[i].red-=1

# Generating vehicles in the simulation
def generateVehicles():
    # Define the probability for a vehicle to be an emergency vehicle (e.g., 5%)
    emergency_probability = 0.05 
    EMERGENCY_VEHICLE_INDEX = 5 

    while True:
        # Determine if the next vehicle is an emergency vehicle
        is_emergency = random.random() < emergency_probability
        
        if is_emergency:
            vehicle_type_index = EMERGENCY_VEHICLE_INDEX
            # Emergency vehicles occupy regular lanes (1 or 2, excluding the bike lane 0)
            lane_number = random.randint(1, 2)
            will_turn = 0 
        else:
            vehicle_type_index = random.randint(0, 4)
            if vehicle_type_index == 4: # Bike
                lane_number = 0
            else: # Car, bus, truck, rickshaw
                lane_number = random.randint(1, 2)
            
            will_turn = 0
            if lane_number == 2:
                temp = random.randint(0, 4)
                if temp <= 2:
                    will_turn = 1
                elif temp > 2:
                    will_turn = 0
        
        temp = random.randint(0, 999)
        direction_number = 0
        # Reduced probability for 'up' and 'left' to create more distinct flow (traffic density)
        a = [400, 800, 900, 1000]
        if temp < a[0]:
            direction_number = 0 # right
        elif temp < a[1]:
            direction_number = 1 # down
        elif temp < a[2]:
            direction_number = 2 # left
        elif temp < a[3]:
            direction_number = 3 # up

        # Create the vehicle
        vehicle_type = vehicleTypes[vehicle_type_index]
        Vehicle(lane_number, vehicle_type, direction_number, directionNumbers[direction_number], will_turn, is_emergency=is_emergency)
        
        # Log to the console if an emergency vehicle is created
        if is_emergency:
            print(f"Emergency vehicle created in direction: {directionNumbers[direction_number]}, lane: {lane_number}")

        # Wait before generating the next vehicle
        time.sleep(0.75)


def simulationTime():
    global timeElapsed, simTime
    while(True):
        timeElapsed += 1
        time.sleep(1)
        if(timeElapsed==simTime):
            totalVehicles = 0
            print('Lane-wise Vehicle Counts')
            for i in range(noOfSignals):
                print('Lane',i+1,':',vehicles[directionNumbers[i]]['crossed'])
                totalVehicles += vehicles[directionNumbers[i]]['crossed']
            print('Total vehicles passed: ',totalVehicles)
            print('Total time passed: ',timeElapsed)
            print('No. of vehicles passed per unit time: ',(float(totalVehicles)/float(timeElapsed)))
            os._exit(1)
    

class Main:
    global totalCarbonEmission
    thread4 = threading.Thread(name="simulationTime",target=simulationTime, args=()) 
    thread4.daemon = True
    thread4.start()

    thread2 = threading.Thread(name="initialization",target=initialize, args=())    # initialization
    thread2.daemon = True
    thread2.start()

    # Colours 
    black = (0, 0, 0)
    white = (255, 255, 255)

    # Screensize 
    screenWidth = 1400
    screenHeight = 800
    screenSize = (screenWidth, screenHeight)

    # Setting background image i.e. image of intersection
    background = pygame.image.load('images/mod_int.png')

    screen = pygame.display.set_mode(screenSize)
    pygame.display.set_caption("SIMULATION")

    # Loading signal images and font
    redSignal = pygame.image.load('images/signals/red.png')
    yellowSignal = pygame.image.load('images/signals/yellow.png')
    greenSignal = pygame.image.load('images/signals/green.png')
    font = pygame.font.Font(None, 30)

    thread3 = threading.Thread(name="generateVehicles",target=generateVehicles, args=())    # Generating vehicles
    thread3.daemon = True
    thread3.start()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        screen.blit(background,(0,0))   # display background in simulation
        for i in range(0,noOfSignals):  # display signal and set timer according to current status: green, yello, or red
            if(i==currentGreen):
                if(currentYellow==1):
                    if(signals[i].yellow==0):
                        signals[i].signalText = "STOP"
                    else:
                        signals[i].signalText = signals[i].yellow
                    screen.blit(yellowSignal, signalCoods[i])
                else:
                    if(signals[i].green==0):
                        signals[i].signalText = "SLOW"
                    else:
                        signals[i].signalText = signals[i].green
                    screen.blit(greenSignal, signalCoods[i])
            else:
                if signals[i].red <= 10 and not isEmergency and not emergencyTransitionYellow: 
                    if signals[i].red == 0:
                        signals[i].signalText = "GO"
                    else:
                        signals[i].signalText = signals[i].red
                else:
                    signals[i].signalText = "---"
                    # Display EMERGENCY if the signal is forced to a long red by the override
                    if isEmergency and i != currentGreen and signals[i].red > defaultMaximum:
                         signals[i].signalText = "EMERG"
                    elif emergencyTransitionYellow and i != currentGreen:
                         signals[i].signalText = "WAIT"
                         
                screen.blit(redSignal, signalCoods[i])
        signalTexts = ["","","",""]

        # display signal timer and vehicle count
        for i in range(0,noOfSignals):  
            signalTexts[i] = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(signalTexts[i],signalTimerCoods[i]) 
            displayText = vehicles[directionNumbers[i]]['crossed']
            vehicleCountTexts[i] = font.render(str(displayText), True, black, white)
            screen.blit(vehicleCountTexts[i],vehicleCountCoods[i])

        timeElapsedText = font.render(("Time Elapsed: "+str(timeElapsed)), True, black, white)
        screen.blit(timeElapsedText,(1100,50))
        
        # Display Emergency Status
        if isEmergency:
            emergency_text = font.render(f"EMERGENCY ACTIVE: {emergencyDirection.upper()} LANE", True, (255, 0, 0), white)
            screen.blit(emergency_text, (550, 10))
        elif emergencyTransitionYellow:
            emergency_text = font.render(f"EMERGENCY TRANSITION: STOPPING TRAFFIC", True, (255, 165, 0), white)
            screen.blit(emergency_text, (520, 10))
        else:
            normal_text = font.render("NORMAL OPERATION", True, (0, 150, 0), white)
            screen.blit(normal_text, (580, 10))
            
        # Carbon Emission Display 
        if totalCarbonEmission<1000:
            carbonText=font.render(("Carbon Emission : "+str(round(totalCarbonEmission,2))+"  µg"), True, black, white)
        elif totalCarbonEmission>=1000 and totalCarbonEmission<1000000:
            carbonText=font.render(("Carbon Emission : "+str(round(totalCarbonEmission/1000,2))+"  mg"), True, black, white)
        elif totalCarbonEmission>=1000000 and totalCarbonEmission<1000000000:
            carbonText=font.render(("Carbon Emission : "+str(round(totalCarbonEmission/1000000,2))+"  g"), True, black, white)
        else:
            carbonText=font.render(("Carbon Emission : "+str(round(totalCarbonEmission/1000000000,2))+"  Kg"), True, black, white)
        screen.blit(carbonText,(10,75))


        # display the vehicles
        for vehicle in simulation:  
            screen.blit(vehicle.currentImage, [vehicle.x, vehicle.y])
            vehicle.move()
        pygame.display.update()


Main()