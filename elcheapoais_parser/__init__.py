import dbus
import dbus.service
import dbus.mainloop.glib
import gi.repository.GLib
import sys
import threading
import ais.stream
import ais.compatibility.gpsd
import queue
import time
import json

def timeout(to):
    def wrapper(fn):
        gi.repository.GLib.timeout_add(to, fn)
    return wrapper
           
class StatusObject(dbus.service.Object):
    def __init__(self, manager, object_path='/no/innovationgarage/elcheapoais/nmea'):
        dbus.service.Object.__init__(self, manager.bus, object_path)
        self.manager = manager
        self.nmea_queue = queue.Queue()
        self.station_id = None
        gi.repository.GLib.timeout_add(100, self.send_nmea)

    def send_nmea(self):
        while not self.nmea_queue.empty():
            msg = self.nmea_queue.get(False)
            if "AIVDO" in msg["nmea"]:
                msg["own_ship"] = True
                if not self.station_id:
                    try:
                        self.manager.bus.get_object(
                            'no.innovationgarage.elcheapoais.config', '/no/innovationgarage/elcheapoais/receiver'
                        ).Set("no.innovationgarage.elcheapoais.receiver", "station_id", msg["mmsi"])
                        self.station_id = msg["mmsi"]
                    except Exception as e:
                        print(e)
            self.NMEA(json.dumps(msg))
        return True
        
    @dbus.service.signal('no.innovationgarage.elcheapoais')
    def NMEA(self, message):
        pass

class DBusThread(threading.Thread):
    def __init__(self, bus_name):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self.bus = getattr(dbus, bus_name)()
        self.bus_name = dbus.service.BusName('no.innovationgarage.elcheapoais.parser', self.bus)
        self.status = StatusObject(self)
        self.quit = False
        gi.repository.GLib.timeout_add(100, self.check_exit)
        threading.Thread.__init__(self)

    def check_exit(self):
        if self.quit:
            self.loop.quit()
        return True

    def run(self):
        self.loop = gi.repository.GLib.MainLoop()
        self.loop.run()
        print("END")
    
class Manager(object):
    def __init__(self, filename, bus_name="SessionBus"):
        dbus_thread = DBusThread(bus_name)
        dbus_thread.start()
        
        with open(filename) as f:
            for msg in ais.stream.decode(f, keep_nmea=True):
                json = ais.compatibility.gpsd.mangle(msg)
                dbus_thread.status.nmea_queue.put(json)

        print("Waiting for queue to empty...")
        while not dbus_thread.status.nmea_queue.empty():
            time.sleep(1)

        print("Shutting down...")
        dbus_thread.quit = True
        sys.exit(0)

def main():
    Manager(*sys.argv[1:])
