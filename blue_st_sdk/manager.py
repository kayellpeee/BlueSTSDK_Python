################################################################################
# COPYRIGHT(c) 2018 STMicroelectronics                                         #
#                                                                              #
# Redistribution and use in source and binary forms, with or without           #
# modification, are permitted provided that the following conditions are met:  #
#   1. Redistributions of source code must retain the above copyright notice,  #
#      this list of conditions and the following disclaimer.                   #
#   2. Redistributions in binary form must reproduce the above copyright       #
#      notice, this list of conditions and the following disclaimer in the #
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


"""manager

The manager module is responsible for managing the discovery process of
Bluetooth Low Energy (BLE) devices/nodes and allocating the needed resources.
"""


# IMPORT

from abc import ABCMeta
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
import threading
import logging
from bluepy.btle import Scanner
from bluepy.btle import DefaultDelegate
from bluepy.btle import BTLEException

from blue_st_sdk.node import Node
from blue_st_sdk.utils.ble_node_definitions import FeatureCharacteristic
from blue_st_sdk.utils.blue_st_exceptions import InvalidFeatureBitMaskException
from blue_st_sdk.utils.blue_st_exceptions import InvalidBLEAdvertisingDataException
from blue_st_sdk.python_utils import lock
from blue_st_sdk.python_utils import lock_for_object


# CLASSES

class _ScannerDelegate(DefaultDelegate):
    """Delegate class to scan Bluetooth Low Energy devices."""

    SCANNING_TIME_DEFAULT_s = 10
    """Default Bluetooth scanning timeout in seconds."""

    _SCANNING_TIME_PROCESS_s = 1
    """Default Bluetooth scanning timeout in seconds for a single call to
    bluepy's process() method."""

    def __init__(self, show_warnings=False):
        """Constructor.

        Args:
            show_warnings (bool, optional): If True shows warnings, if any, when
                discovering devices not respecting the BlueSTSDK's advertising
                data format, nothing otherwise.
        """
        DefaultDelegate.__init__(self)
        self._show_warnings = show_warnings

    def handleDiscovery(self, scan_entry, is_new_device, is_new_data):
        """Discovery handling callback.

        Called when an advertising data is received from a BLE device while a
        Scanner object is active.

        Args:
            scan_entry (ScanEntry): BLE device. It contains device information
                and advertising data. Refer to
                `ScanEntry <https://ianharvey.github.io/bluepy-doc/scanentry.html>`_
                for more information.
            is_new_device (bool): True if the device (as identified by its MAC
                address) has not been seen before by the scanner, False
                otherwise.
            is_new_data (bool): True if new or updated advertising data is
                available.
        """
        # Getting a Manager's instance.
        manager = Manager.instance()

        # Getting device's address.
        device_address = scan_entry.addr

        try:
            # If the node has already been added, skip adding it again, rather
            # update it.
            nodes = manager.get_nodes()[:]
            for node in nodes:
                if node.get_tag() == device_address:
                    node.is_alive(scan_entry.rssi)
                    node.update_advertising_data(scan_entry.getScanData())
                    return

            # Creating new node.
            node = Node(scan_entry)
            manager.add_node(node)
        except (BTLEException, InvalidBLEAdvertisingDataException) as e:
            if self._show_warnings:
                logging.warning(e)


class _StoppableScanner(threading.Thread):
    """Scanner class which can be started and stopped asynchronously.

    Non-thread-safe.

    It is implemented as a thread which checks regularly for the stop
    condition within the :meth:`run()` method; it can be stopped by calling the
    :meth:`stop()` method.
    """

    def __init__(self, show_warnings=False, timeout_s=0, *args, **kwargs):
        """Constructor.

        Args:
            show_warnings (bool, optional): If True shows warnings, if any, when
                discovering devices not respecting the BlueSTSDK's advertising
                data format, nothing otherwise.
            timeout_s (int, optional): Time in seconds to wait before stopping
                the discovery process.
        """
        super(_StoppableScanner, self).__init__(*args, **kwargs)
        self._stop_called = threading.Event()
        self._process_done = threading.Event()
        self._scanner = Scanner().withDelegate(_ScannerDelegate(show_warnings))
        self._timeout_s = timeout_s

    def run(self):
        """Run the thread."""
        #print('run()')
        self._stop_called.clear()
        self._process_done.clear()
        self._scanner.clear()
        try:
            self._exc = None
            self._scanner.start(passive=False)
            elapsed_time_s = 0
            while True:
                #print('.')
                self._scanner.process(_ScannerDelegate._SCANNING_TIME_PROCESS_s)
                elapsed_time_s += _ScannerDelegate._SCANNING_TIME_PROCESS_s
                if self._stop_called.isSet():
                    self._process_done.set()
                    break
                if elapsed_time_s >= self._timeout_s:
                    self._process_done.set()
                    self.stop()
                    break
        except BTLEException as e:
            # Save details of the exception raised but don't re-raise, just
            # complete the function.
            import sys
            self._exc = sys.exc_info()

    def stop(self):
        """Stop the thread."""
        #print('stop()')
        self._stop_called.set()
        while not (self._process_done.isSet() or self._exc):
            pass
        try:
            self._exc = None
            self._scanner.stop()
        except BTLEException as e:
            # Save details of the exception raised but don't re-raise, just
            # complete the function.
            import sys
            self._exc = sys.exc_info()

    def join(self):
        """Join the thread.
        
        Raises:
            'BTLEException' is raised if this method is not run as root.
        """
        super(_StoppableScanner, self).join()
        if self._exc:
            msg = '\nBluetooth scanning requires root privilege, ' \
                  'so please run the script with \"sudo\".'
            raise BTLEException(0, msg)


class Manager(object):
    """Singleton class to manage the discovery of Bluetooth Low Energy (BLE)
    devices.

    Before starting the scanning process, it is possible to define a new Device
    Id and to register/add new features to already defined devices.

    It notifies a new discovered node through the
    :class:`blue_st_sdk.manager.ManagerListener` class.
    Each callback is performed asynchronously by a thread running in background.
    """

    _INSTANCE = None
    """Instance object."""

    _NUMBER_OF_THREADS = 5
    """Number of threads to be used to notify the listeners."""

    _features_decoder_dic = {}
    """Features decoder dictionary.
    Dictionary that maps device identifiers to dictionaries that map
    feature-masks to feature-classes.
    """

    def __init__(self):
        """Constructor."""
        # Raise an exception if an object has already been instantiated.
        if self._INSTANCE is not None:
            raise Exception('An instance of \'Manager\' class already exists.')

        # BLE scanner.
        self._scanner = None

        # Scanning status.
        self._is_scanning = False

        # List of discovered nodes.
        self._discovered_nodes = []

        # Pool of thread used to notify the listeners.
        self._thread_pool = ThreadPoolExecutor(Manager._NUMBER_OF_THREADS)

        # _StoppableScanner object.
        self._scanner_thread = None

        # List of listeners to the manager changes.
        # It is a thread safe list, so a listener can subscribe itself through a
        # callback.
        self._listeners = []

    @classmethod
    def instance(self):
        """Getting an instance of the class.

        Returns:
            :class:`blue_st_sdk.manager.Manager`: An instance of the class.
        """
        if self._INSTANCE is None:
            self._INSTANCE = Manager()
        return self._INSTANCE

    def discover(self, show_warnings=False, timeout_s=0):
        """Perform the discovery process.

        The discovery process will last *timeout_s* seconds if provided, a
        default timeout otherwise.

        Synchronous method.

        Args:
            show_warnings (bool, optional): If True shows warnings, if any, when
                discovering devices not respecting the BlueSTSDK's advertising
                data format, nothing otherwise.
            timeout_s (int, optional): Time in seconds to wait before stopping
                the discovery process.

        Returns:
            bool: True if the discovery has finished, False if a discovery is
            already running.

        Raises:
            'BTLEException' is raised if this method is not run as root.
        """
        try:
            if self.is_discovering():
                return False
            if timeout_s == 0:
                timeout_s = _ScannerDelegate.SCANNING_TIME_DEFAULT_s
            self._notify_discovery_change(True)
            self._scanner = Scanner().withDelegate(_ScannerDelegate(show_warnings))
            self._scanner.scan(timeout_s)
            self._notify_discovery_change(False)
            return True
        except BTLEException as e:
            msg = '\nBluetooth scanning requires root privilege, ' \
                  'so please run the script with \"sudo\".'
            raise BTLEException(e.code, msg)

    def start_discovery(self, show_warnings=False, timeout_s=0):
        """Start the discovery process.

        The discovery process will last *timeout_s* seconds if provided, a
        default timeout otherwise.

        Asynchronous method, to be followed by a call to
        :meth:`stop_discovery()`'

        Args:
            show_warnings (bool, optional): If True shows warnings, if any, when
                discovering devices not respecting the BlueSTSDK's advertising
                data format, nothing otherwise.
            timeout_s (int, optional): Time in seconds to wait before stopping
                the discovery process.

        Returns:
            bool: True if the discovery has started, False if a discovery is
            already running.

        Raises:
            'BTLEException' is raised if this method is not run as root.
        """
        try:
            #print('start_discovery()')
            if self.is_discovering():
                return False
            if timeout_s == 0:
                timeout_s = _ScannerDelegate.SCANNING_TIME_DEFAULT_s
            self._notify_discovery_change(True)
            self._scanner_thread = _StoppableScanner(show_warnings, timeout_s)
            self._scanner_thread.start()
            return True
        except BTLEException as e:
            raise e

    def stop_discovery(self):
        """Stop a discovery process.

        Asynchronous method, to be preceeded by a call to
        :meth:`start_discovery()`.

        Returns:
            bool: True if the discovery has been stopped, False if there are no
            running discovery processes.

        Raises:
            'BTLEException' is raised if this method is not run as root.
        """
        try:
            #print('stop_discovery()')
            if self.is_discovering():
                self._scanner_thread.stop()
                self._scanner_thread.join()
                self._notify_discovery_change(False)
                return True
            return False
        except BTLEException as e:
            raise e

    def is_discovering(self):
        """Check the discovery process.

        Returns:
            bool: True if the manager is looking for new nodes, False otherwise.
        """
        return self._is_scanning

    def reset_discovery(self):
        """Reset the discovery process.

        Stop the discovery process and remove all the already discovered nodes.
        Node already bounded with the device will be kept in the list.

        Raises:
            'BTLEException' is raised if this method is not run as root.
        """
        try:
            if self.is_discovering():
                self.stop_discovery()
            self.remove_nodes()
        except BTLEException as e:
            raise e

    def _notify_discovery_change(self, status):
        """Notify :class:`blue_st_sdk.manager.ManagerListener` objects that the
        discovery process has changed status.

        Args:
            status (bool): If True the discovery starts, if False the discovery
                stops.
        """
        self._is_scanning = status
        for listener in self._listeners:
            # Calling user-defined callback.
            self._thread_pool.submit(listener.on_discovery_change(self, status))

    def _notify_new_node_discovered(self, node):
        """Notify :class:`blue_st_sdk.manager.ManagerListener` objects that a
        new node has been discovered.

        Args:
            node (:class:`blue_st_sdk.node.Node`): Node discovered.
        """
        for listener in self._listeners:
            # Calling user-defined callback.
            self._thread_pool.submit(listener.on_node_discovered(self, node))

    def add_node(self, new_node):
        """Insert a node to the Manager, and notify the listeners about it.

        Args:
            new_node (:class:`blue_st_sdk.node.Node`): Node to add.

        Returns:
            bool: True if the node is added, False if a node with the same tag
            is already present.
        """
        with lock_for_object(self._discovered_nodes):
            new_tag = new_node.get_tag()
            for node in self._discovered_nodes:
                if new_tag == node.get_tag():
                    return False
            self._discovered_nodes.append(new_node)
        self._notify_new_node_discovered(new_node)
        return True

    def get_nodes(self):
        """Get the list of the discovered nodes.

        Returns:
            list of :class:`blue_st_sdk.node.Node`: The list of all discovered
            nodes until the time of invocation.
        """
        with lock_for_object(self._discovered_nodes):
            return self._discovered_nodes

    def get_node_with_tag(self, tag):
        """Get the node with the given tag.

        Args:
            tag (str): Unique string identifier that identifies a node.

        Returns:
            :class:`blue_st_sdk.node.Node`: The node with the given tag, None
            if not found.
        """
        with lock_for_object(self._discovered_nodes):
            for node in self._discovered_nodes:
                if node.get_tag() == tag:
                    return node
        return None

    def get_node_with_name(self, name):
        """Get the node with the given name.

        Note:
            As the name is not unique, it will return the fist node matching.
            The match is case sensitive.

        Args:
            name (str): Name of the device.

        Returns:
            :class:`blue_st_sdk.node.Node`: The node with the given name, None
            if not found.
        """
        with lock_for_object(self._discovered_nodes):
            for node in self._discovered_nodes:
                if node.get_name() == name:
                    return node
        return None

    def remove_nodes(self):
        """Remove all nodes not bounded with the device."""
        with lock_for_object(self._discovered_nodes):
            for node in self._discovered_nodes:
                if not node.is_connected():
                    self._discovered_nodes.remove(node)

    @classmethod
    def add_features_to_node(self, device_id, mask_to_features_dic):
        """Add features to a node.

        Register a new device identifier with the corresponding mask-to-features
        dictionary summarizing its available features, or add available features
        to an already registered device, before performing the discovery
        process.

        Otherwise, it is possible to register the feature after discovering a
        node and before connecting to it (see
        :meth:`blue_st_sdk.node.Node.add_external_features()`).

        Args:
            device_id (int): Device identifier.
            mask_to_features_dic (dict): Mask-to-features dictionary to be added
                to the features decoder dictionary referenced by the device
                identifier. The feature masks of the dictionary must have only
                one bit set to "1".

        Raises:
            :exc:`blue_st_sdk.utils.blue_st_exceptions.InvalidFeatureBitMaskException`
                is raised when a feature is in a non-power-of-two position.
        """

        # Example:
        # # Adding a 'MyFeature' feature to a Nucleo device and mapping it to a
        # # custom '0x10000000-0001-11e1-ac36-0002a5d5c51b' characteristic.
        # mask_to_features_dic = {}
        # mask_to_features_dic[0x10000000] = MyFeature.MyFeature
        # try:
        #     Manager.add_features_to_node(0x80, mask_to_features_dic)
        # except InvalidFeatureBitMaskException as e:
        #     print(e)

        # Synchronous discovery of Bluetooth devices.
        manager.discover(False, SCANNING_TIME_s)

        if device_id in self._features_decoder_dic:
            decoder = self._features_decoder_dic.get(device_id)
        else:
            decoder = {}
            self._features_decoder_dic[device_id] = decoder

        decoder_to_check = mask_to_features_dic.copy()

        mask = 1
        for i in range(0, 32):
            feature_class = decoder_to_check.get(mask)
            if feature_class is not None:
                decoder[mask] = feature_class
                decoder_to_check.pop(mask)
            mask = mask << 1

        if bool(decoder_to_check):
            raise InvalidFeatureBitMaskException('Not all keys of the '
                'mask-to-features dictionary have a single bit set to "1".')

    @classmethod
    def get_node_features(self, device_id):
        """Get a copy of the features map available for the given device
        identifier.

        Args:
            device_id (int): Device identifier.
        
        Returns:
            dict: A copy of the features map available for the given device
            identifier if found, None otherwise.
        """
        if device_id in self._features_decoder_dic:
            return self._features_decoder_dic[device_id].copy()
        return FeatureCharacteristic.DEFAULT_MASK_TO_FEATURE_DIC.copy()

    def add_listener(self, listener):
        """Add a listener.
        
        Args:
            listener (:class:`blue_st_sdk.manager.ManagerListener`): Listener to
                be added.
        """
        if listener is not None:
            with lock(self):
                if not listener in self._listeners:
                    self._listeners.append(listener)

    def remove_listener(self, listener):
        """Remove a listener.
        
        Args:
            listener (:class:`blue_st_sdk.manager.ManagerListener`): Listener to
                be removed.
        """
        if listener is not None:
            with lock(self):
                if listener in self._listeners:
                    self._listeners.remove(listener)


# INTERFACES

class ManagerListener(object):
    """Interface used by the :class:`blue_st_sdk.manager.Manager` class to
    notify that a new Node has been discovered or that the scanning has
    started/stopped.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_discovery_change(self, manager, enabled):
        """This method is called whenever a discovery process starts or stops.

        Args:
            manager (:class:`blue_st_sdk.manager.Manager`): Manager instance
                that starts/stops the process.
            enabled (bool): True if a new discovery starts, False otherwise.

        Raises:
            'NotImplementedError' is raised if the method is not implemented.
        """
        raise NotImplementedError('You must define \"on_discovery_change()\" '
            'to use the \"ManagerListener\" class.')

    @abstractmethod
    def on_node_discovered(self, manager, node):
        """This method is called whenever a new node is discovered.

        Args:
            manager (:class:`blue_st_sdk.manager.Manager`): Manager instance
                that discovers the node.
            node (:class:`blue_st_sdk.node.Node`): New node discovered.


        Raises:
            'NotImplementedError' is raised if the method is not implemented.
        """
        raise NotImplementedError('You must define \"on_node_discovered()\" '
            'to use the \"ManagerListener\" class.')
