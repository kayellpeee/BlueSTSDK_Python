#!/usr/bin/env python

################################################################################
# COPYRIGHT(c) 2018 STMicroelectronics                                         #
#                                                                              #
# Redistribution and use in source and binary forms, with or without           #
# modification, are permitted provided that the following conditions are met:  #
#   1. Redistributions of source code must retain the above copyright notice,  #
#      this list of conditions and the following disclaimer.                   #
#   2. Redistributions in binary form must reproduce the above copyright       #
#      notice, this list of conditions and the following disclaimer in the     #
#      documentation and/or other materials provided with the distribution.    #
#   3. Neither the name of STMicroelectronics nor the names of its             #
#      contributors may be used to endorse or promote products derived from    #
#      this software without specific prior written permission.                #
#                                                                              #
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"  #
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE    #
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE   #
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE    #
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR          #
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF         #
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS     #
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN      #
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)      #
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE   #
# POSSIBILITY OF SUCH DAMAGE.                                                  #
################################################################################

################################################################################
# Author:  Davide Aliprandi, STMicroelectronics                                #
################################################################################


# DESCRIPTION
#
# This application example shows how to perform a Bluetooth Low Energy (BLE)
# scan, connect to a device, retrieve its exported features, and get push
# notifications from it.


# IMPORT

from __future__ import print_function
import sys
import os
import time
from time import gmtime, strftime
from abc import abstractmethod
from bluepy.btle import BTLEException

from blue_st_sdk.manager import Manager
from blue_st_sdk.manager import ManagerListener
from blue_st_sdk.node import NodeListener
from blue_st_sdk.feature import FeatureListener
from blue_st_sdk.features.feature_audio_adpcm import FeatureAudioADPCM
from blue_st_sdk.features.feature_audio_adpcm_sync import FeatureAudioADPCMSync


# PRECONDITIONS
#
# Please remember to add to the "PYTHONPATH" environment variable the location
# of the "BlueSTSDK_Python" SDK.
#
# On Linux:
#   export PYTHONPATH=/home/<user>/BlueSTSDK_Python


# CONSTANTS

# Presentation message.
INTRO = """##################
# BlueST Example #
##################"""

# Bluetooth Scanning time in seconds.
SCANNING_TIME_s = 5

# Number of notifications to get before disabling them.
NOTIFICATIONS = 10


# FUNCTIONS

#
# Printing intro.
#
def print_intro():
    print('\n' + INTRO + '\n')


# INTERFACES

#
# Implementation of the interface used by the Manager class to notify that a new
# node has been discovered or that the scanning starts/stops.
#
class MyManagerListener(ManagerListener):

    #
    # This method is called whenever a discovery process starts or stops.
    #
    # @param manager Manager instance that starts/stops the process.
    # @param enabled True if a new discovery starts, False otherwise.
    #
    def on_discovery_change(self, manager, enabled):
        print('Discovery %s.' % ('started' if enabled else 'stopped'))
        if not enabled:
            print()

    #
    # This method is called whenever a new node is discovered.
    #
    # @param manager Manager instance that discovers the node.
    # @param node    New node discovered.
    #
    def on_node_discovered(self, manager, node):
        print('New device discovered: %s.' % (node.get_name()))


#
# Implementation of the interface used by the Node class to notify that a node
# has updated its status.
#
class MyNodeListener(NodeListener):

    #
    # To be called whenever a node changes its status.
    #
    # @param node       Node that has changed its status.
    # @param new_status New node status.
    # @param old_status Old node status.
    #
    def on_status_change(self, node, new_status, old_status):
        print('Device %s from %s to %s.' %
            (node.get_name(), str(old_status), str(new_status)))


#
# Implementation of the interface used by the Feature class to notify that a
# feature has updated its data.
#
class MyFeatureListener(FeatureListener):
    def __init__(self, deviceName, logfile):
        self.name = deviceName
        self.f = open(logfile, 'w')
        self.f.write(("\n\n* * * * * * * * * STARTING RUN %s * * * *\n") % strftime('%a, %d %b %Y %H:%M:%S +0000', gmtime())) 
        print('created logfile (%s) for: %s' % (logfile, self.name))

    num = 0
    #
    # To be called whenever the feature updates its data.
    #
    # @param feature Feature that has updated.
    # @param sample  Data extracted from the feature.
    #
    def on_update(self, feature, sample):
        self.f.write(('%s: %s\n') % (self.name, feature))


# MAIN APPLICATION

#
# Main application.
#
def main(argv):

    # Printing intro.
    print_intro()

    try:
        # Creating Bluetooth Manager.
        manager = Manager.instance()
        manager_listener = MyManagerListener()
        manager.add_listener(manager_listener)

        while True:
            # Synchronous discovery of Bluetooth devices.
            print('Scanning Bluetooth devices...\n')
            manager.discover(False, SCANNING_TIME_s)

            # Getting discovered devices.
            discovered_devices = manager.get_nodes()

            # Listing discovered devices.
            if not discovered_devices:
                print('\nNo Bluetooth devices found.')
                sys.exit(0)
            print('\nAvailable Bluetooth devices:')
            i = 1
            for device in discovered_devices:
                print('%d) %s: [%s]' % (i, device.get_name(), device.get_tag()))
                i += 1

            # Selecting a device.
            while True:
                choice = int(input("\nSelect a device (\'0\' to quit): "))
                if choice >= 0 and choice <= len(discovered_devices):
                    break
            if choice == 0:
                # Exiting.
                manager.remove_listener(manager_listener)
                print('Exiting...\n')
                sys.exit(0)
            device = discovered_devices[choice - 1]
            device2 = discovered_devices[choice]
            device3 = discovered_devices[choice + 1]
            device4 = discovered_devices[choice + 2]
            device5 = discovered_devices[choice + 3]
            device6 = discovered_devices[choice + 4]
            
            # Connecting to the device.
            node_listener = MyNodeListener()
            node_listener2 = MyNodeListener()
            node_listener3 = MyNodeListener()
            node_listener4 = MyNodeListener()
            node_listener5 = MyNodeListener()
            node_listener6 = MyNodeListener()
            device.add_listener(node_listener)
            device2.add_listener(node_listener2)
            device3.add_listener(node_listener3)
            device4.add_listener(node_listener4)
            device5.add_listener(node_listener5)
            device6.add_listener(node_listener6)
            print('\nConnecting to %s...' % (device.get_name()))
            print('\nConnecting to %s...' % (device2.get_name()))
            print('\nConnecting to %s...' % (device3.get_name()))
            print('\nConnecting to %s...' % (device4.get_name()))
            print('\nConnecting to %s...' % (device5.get_name()))
            print('\nConnecting to %s...' % (device6.get_name()))
            device.connect()
            device2.connect()
            device3.connect()
            device4.connect()
            device5.connect()
            device6.connect()
            print('Connection done.')

            while True:
                # Getting features.
                print('\nFeatures:')
                i = 1
                features = device.get_features()
                features2 = device2.get_features()
                features3 = device3.get_features()
                features4 = device4.get_features()
                features5 = device5.get_features()
                features6 = device6.get_features()
                
                audioFeature = None
                audioSyncFeature = None
                
                for feature in features:
                    if not feature.get_name() == FeatureAudioADPCMSync.FEATURE_NAME:
                        if feature.get_name() == FeatureAudioADPCM.FEATURE_NAME:
                            audioFeature = feature
                            print('%d,%d) %s' % (i,i+1, "Audio & Sync"))
                        else:
                            print('%d) %s' % (i, feature.get_name()))
                        i+=1
                    else:
                        audioSyncFeature = feature
                # Selecting a feature.
                while True:
                    choice = int(input('\nSelect a feature (device1)'
                                       '(\'0\' to disconnect): '))
                    if choice >= 0 and choice <= len(features):
                        break
                if choice == 0:
                    # Disconnecting from the device.
                    print('\nDisconnecting from %s...' % (device.get_name()))
                    device.disconnect()
                    print('Disconnection done.')
                    device.remove_listener(node_listener)
                    # Going back to the list of devices.
                    break
                feature = features[choice - 1]
                feature2 = features2[choice - 1]
                feature3 = features3[choice - 1]
                feature4 = features4[choice - 1]
                feature5 = features5[choice - 1]
                feature6 = features6[choice - 1]
                
                # Enabling notifications.
                feature_listener = MyFeatureListener(device.get_tag(), 'log1.txt')
                feature.add_listener(feature_listener)
                device.enable_notifications(feature)

                feature_listener2 = MyFeatureListener(device2.get_tag(), 'log2.txt')
                feature2.add_listener(feature_listener2)
                device2.enable_notifications(feature2)

                feature_listener3 = MyFeatureListener(device3.get_tag(), 'log3.txt')
                feature3.add_listener(feature_listener3)
                device3.enable_notifications(feature3)

                
                feature_listener4 = MyFeatureListener(device4.get_tag(), 'log4.txt')
                feature4.add_listener(feature_listener4)
                device4.enable_notifications(feature4)

                feature_listener5 = MyFeatureListener(device5.get_tag(), 'log5.txt')
                feature5.add_listener(feature_listener5)
                device5.enable_notifications(feature5)

                feature_listener6 = MyFeatureListener(device6.get_tag(), 'log6.txt')
                feature6.add_listener(feature_listener6)
                device6.enable_notifications(feature6)

                if feature.get_name() == FeatureAudioADPCM.FEATURE_NAME:
                    audioSyncFeature_listener = MyFeatureListener()
                    audioSyncFeature.add_listener(audioSyncFeature_listener)
                    device.enable_notifications(audioSyncFeature)
                elif feature.get_name() == FeatureAudioADPCMSync.FEATURE_NAME:
                    audioFeature_listener = MyFeatureListener()
                    audioFeature.add_listener(audioFeature_listener)
                    device.enable_notifications(audioFeature)
                
                # Getting notifications.
                while True:
                    device.wait_for_notifications(0.05)
                    device2.wait_for_notifications(0.05)
                    device3.wait_for_notifications(0.05)
                    device4.wait_for_notifications(0.05)
                    device5.wait_for_notifications(0.05)
                    device6.wait_for_notifications(0.05)

    except BTLEException as e:
        print(e)
        # Exiting.
        print('Exiting...\n')
        sys.exit(0)
    except KeyboardInterrupt:
        try:
            # Exiting.
            print('\nExiting...\n')
            sys.exit(0)
        except SystemExit:
            os._exit(0)


if __name__ == "__main__":

    main(sys.argv[1:])
