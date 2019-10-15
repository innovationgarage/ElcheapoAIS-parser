import dbus
import dbus.service
import dbus.mainloop.glib
import gi.repository.GLib
import gi.repository.GObject
import sys
import os
import threading
import ais.stream
import ais.compatibility.gpsd
import queue
import time
import json
import serial
import serial.serialutil
import termios

def timeout(to):
    def wrapper(fn):
        gi.repository.GLib.timeout_add(to, fn)
    return wrapper

def get(bus, bus_name, obj_path, interface_name, parameter_name, default=None):
    try:
        return bus.get_object(bus_name, obj_path).Get(interface_name, parameter_name)
    except:
        return default
    
class StatusObject(dbus.service.Object):
    def __init__(self, manager, object_path='/no/innovationgarage/elcheapoais/nmea'):
        dbus.service.Object.__init__(self, manager.bus, object_path)
        self.manager = manager

    @dbus.service.signal('no.innovationgarage.elcheapoais')
    def NMEA(self, message):
        pass

class Reader(object):
    def __init__(self, **kws):
        self.kws = kws
        self.f = None
        self.open()
        
    def open(self):
        self.close()
        if "filename" in self.kws:
            self.f = open(self.kws["filename"])
        elif "port" in self.kws:
            self.f = serial.Serial(**self.kws)
        else:
            raise Exception("You must specify either filename or port")
        self.stream = iter(ais.stream.decode(self.f, keep_nmea=True))

    def close(self):
        if self.f:
            self.f.close()
        self.f = None

    def next(self):
        while True:
            try:
                return next(self.stream)
            except:
                if "filename" in self.kws:
                    raise StopIteration
                time.sleep(0.1)
                self.open()
        
class ReaderThread(threading.Thread):
    def __init__(self, manager):
        self.manager = manager
        self.is_quitting = False
        self.stream = None
        self.station_id = None
        threading.Thread.__init__(self)

    def quit(self):
        self.is_quitting = True

    def open(self, **kws):
        print("Opening %s" % (kws,))
        stream = self.stream
        self.stream = Reader(**kws)
        if stream: stream.close()

    def run(self):
        while not self.is_quitting:
            if not self.stream:
                time.sleep(0.5)
                continue
            try:
                msg = self.stream.next()
            except StopIteration:
                time.sleep(0.5)
                continue
            msg = ais.compatibility.gpsd.mangle(msg)
            if "AIVDO" in msg["nmea"]:
                msg["own_ship"] = True
                if not self.station_id:
                    try:
                        self.manager.dbus_thread.bus.get_object(
                            'no.innovationgarage.elcheapoais.config', '/no/innovationgarage/elcheapoais/receiver'
                        ).Set("no.innovationgarage.elcheapoais.receiver", "station_id", msg["mmsi"])
                        self.station_id = msg["mmsi"]
                    except Exception as e:
                        print(e)
            print(msg)
            self.manager.dbus_thread.status.NMEA(json.dumps(msg))
        print("Shutting down ReaderThread...")

class DBusThread(threading.Thread):
    def __init__(self, manager):
        self.manager = manager
        gi.repository.GObject.threads_init()
        dbus.mainloop.glib.threads_init()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self.bus = getattr(dbus, os.environ.get("ELCHEAPOAIS_DBUS", "SystemBus"))()
        self.bus_name = dbus.service.BusName('no.innovationgarage.elcheapoais.parser', self.bus)
        self.status = StatusObject(self)
        self.is_quitting = False
        self.bus.add_signal_receiver(self.PropertiesChanged,
                                     dbus_interface = "org.freedesktop.DBus.Properties",
                                     signal_name = "PropertiesChanged",
                                     message_keyword='dbus_message')
        device = get(self.bus,
                     'no.innovationgarage.elcheapoais.config', '/no/innovationgarage/elcheapoais/install',
                     "no.innovationgarage.elcheapoais.receiver", "device", None)
        if device is not None:
            self.manager.reader_thread.open(**device)

        gi.repository.GLib.timeout_add(100, self.check_exit)
        threading.Thread.__init__(self)

    def quit(self):
        self.is_quitting = True

    def PropertiesChanged(self, interface_name, properties_modified, properties_deleted, dbus_message):
        if interface_name == "no.innovationgarage.elcheapoais.receiver":
            for key, value in properties_modified.items():
                if key == "device":
                    print("Setting %s=%s" % (key, value))
                    self.manager.reader_thread.open(**value)
        
    def check_exit(self):
        if self.is_quitting:
            self.loop.quit()
        return True

    def run(self):
        self.loop = gi.repository.GLib.MainLoop()
        self.loop.run()
        print("Shutting down DBusThread...")
    
class Manager(object):
    def __init__(self):
        self.reader_thread = ReaderThread(self)
        self.reader_thread.start()
        self.dbus_thread = DBusThread(self)
        self.dbus_thread.start()

        
        #print("Shutting down...")
        #self.reader_thread.quit()
        #self.dbus_thread.quit()
        #sys.exit(0)

def main():
    Manager()
