# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'
print "adding", __name__

import os
import platform
import threading
import time
from datetime import datetime
import urllib
import json

from kivy.config import Config

# Reads the app's config. If not, defaults are loaded.
Config.read('cimgui.ini')

from kivy.core.window import Window
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.factory import Factory
from kivy.properties import BooleanProperty

# Set WorldBank API static parameters.
start_url = "http://api.worldbank.org/"
end_url = "?per_page=30000&format=json"

# Set url catalogs.
countries = "countries/"
topics = "topics/"
indicators = "indicators/"

# Prepare the file to store core's index database.
coredb_py = None

# Set userdb
userdb = [["GRC", "ALB", "ITA", "TUR", "CYP"],
          ["SP.DYN.LE00.IN", "MYS.MEA.YSCH.25UP.MF", "SE.SCH.LIFE", "NY.GNP.PCAP.PP.CD", "UNDP.HDI.XD"]]

# print start_url + countries + "GRC" + "/" + indicators + "AG.LND.FRST.K2" + "/" + end_url


class MainWindow(BoxLayout):

    # Prepare kivy properties that show if a process or a popup are currently running. Set to False on app's init.
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    def threadonator(self, *arg):
        threading.Thread(target=arg[0], args=(arg,)).start()
        return 1

    # This method addresses our window's state changes, to their specific handling actions.
    def windows_state(self, state):
        if state == "minimize":
            Window.minimize()
        elif state == "toggle_fullscreen":
            Window.toggle_fullscreen()
        elif state == "close":
            App.get_running_app().stop_warning()
        else:
            print "Unknown Windows State"
        return 1


    def config_state(self, state):
        config = App.get_running_app().read_config()
        config.set('graphics', 'fullscreen', 1)
        config.write()

    def config_state_delete(self, state):
        config = App.get_running_app().read_config()
        config.set('graphics', 'fullscreen', 0)
        config.write()

    def update_progress(self, *arg):
        anim_bar = Factory.AnimWidget()
        self.core_build_progress_bar.add_widget(anim_bar)
        anim = Animation(opacity=0.3, width=300, duration=0.6)
        anim += Animation(opacity=1, width=100, duration=0.6)
        anim.repeat = True
        anim.start(anim_bar)
        while self.processing:
            pass
        self.core_build_progress_bar.remove_widget(anim_bar)
        return 1

    # This method builds core's index database with indicators and countries.
    def core_build(self, *arg):

        # A process just started running (in a new thread).
        self.processing = True
        self.threadonator(self.update_progress)

        # Try, in case there is a problem with the online updating process.
        try:
            time.sleep(4)
            """
            # set target web links
            c_link = start_url + countries + end_url
            t_link = start_url + topics + end_url
            i_link = start_url + indicators + end_url

            # save sources into json files
            urllib.urlretrieve(c_link, "./DB/Countries.json")
            urllib.urlretrieve(t_link, "./DB/Topics.json")
            urllib.urlretrieve(i_link, "./DB/Indicators.json")

            # open json files
            file_countries = open("./DB/Countries.json", "r")
            file_topics = open("./DB/Topics.json", "r")
            file_indicators = open("./DB/indicators.json", "r")

            # convert json files into temp python structures
            countries_py = json.load(file_countries)
            topics_py = json.load(file_topics)
            indicators_py = json.load(file_indicators)

            # close json files
            file_countries.close()
            file_topics.close()
            file_indicators.close()

            # zip python structures into a single DB list
            countries_zip = [[]]
            topics_zip = [[]]
            free_indicators_zip = [[]]
            coredb = [None, None, None, None]

            for country in range(countries_py[0]["total"]):
                countries_zip.append([
                    (countries_py[1][country]["id"]),
                    (countries_py[1][country]["name"]),
                    (countries_py[1][country]["region"]["id"]),
                    (countries_py[1][country]["region"]["value"]),
                    (countries_py[1][country]["longitude"]),
                    (countries_py[1][country]["latitude"])])

            for topic in range(topics_py[0]["total"]):
                topics_zip.append([
                    {"name": (topics_py[1][topic]["value"])}])

            for indicator in range(indicators_py[0]["total"]):
                try:
                    topics_zip[int(indicators_py[1][indicator]["topics"][0]["id"])].append([
                        (indicators_py[1][indicator]["id"]),
                        (indicators_py[1][indicator]["name"]),
                        (indicators_py[1][indicator]["sourceNote"])])
                except:
                    free_indicators_zip.append([
                        (indicators_py[1][indicator]["id"]),
                        (indicators_py[1][indicator]["name"]),
                        (indicators_py[1][indicator]["sourceNote"])])

            for topic in range(len(topics_zip)-1):
                topics_zip[topic+1][0]["indicators_num"] = len(topics_zip[topic+1])-1

            # coredb update
            coredb[0] = {"table_date": str(datetime.today())}
            countries_zip[0] = {"countries_num": countries_py[0]["total"]}
            topics_zip[0] = {"topics_num": topics_py[0]["total"]}
            free_indicators_zip[0] = {"free_indicators_num": (len(free_indicators_zip)-1)}

            coredb[1] = countries_zip
            coredb[2] = topics_zip
            coredb[3] = free_indicators_zip

            # store the new coredb file
            file_coredb = open("./DB/core.db", "w")
            json.dump(coredb, file_coredb)
            file_coredb.close()

            # flush temp  python structures
            countries_py = None
            topics_py = None
            indicators_py = None
            countries_zip = None
            topics_zip = None
            free_indicators_zip = None
            coredb = None

            # delete temp downloaded json files
            os.remove("./DB/Countries.json")
            os.remove("./DB/Indicators.json")
            os.remove("./DB/Topics.json")
            """
        except:
            print "Could not update Coredb. Please try again."
        self.processing = False
        return 1

    # This method checks for last core's index database update.
    def check(self, *arg):
        global coredb_py

        while self.popup_active:
            # If there is any process running, wait until finish.
            while self.processing:
                time.sleep(1)

            # Try to open the json DB file.
            try:
                stored_coredb = open("./DB/core.db", "r")

                # Convert json file into temp python structure.
                coredb_py = json.load(stored_coredb)

                # Close json file.
                stored_coredb.close()

                self.coredb_state.text = ("Latest DB Update:\n" + coredb_py[0]['table_date'])
            except:
                self.coredb_state.text = "No valid Indices Database found!\nPlease update it."

            time.sleep(5)
        return 1


class CIMgui(App):

    def build_config(self, cim_config):
        cim_config.setdefaults('System Info',
                               {'usr_os': platform.system(),
                                'arch': platform.machine(), 'py': platform.python_version()})

        cim_config.setdefaults('graphics',
                               {'fullscreen': 0,
                                'height': 768,
                                'width': 1280,
                                'position': 'custom',
                                'top': 100, 'left': 100})

#    def build_settings(self, settings):
#        settings.add_json_panel("CIM Settings", self.config, data="""
#        [{"type": "options",
#        "title": "System Info",
#        "section": "System Info",
#        "key": "usr_os",
#        "options": ["1", "2"]}]""")

    def read_config(self):
        return self.config

    def stop_warning(self, *args, **kwargs):
        print "Are you sure?.."
        Window.close()

    def just_clicked_here(self, *args):
        print "just clicked here", args
        #print self.position

    def moving_cursor(self, *args):
        print "moving", args

    def mouse_position(self, *args):
        self.position = args[1]
        #print self.position
        #print self.collide_point(*args[1])
        """
        if self.hovered == inside:
            return
        self.hovered = inside
        """

    # This function prepares the window.
    def build(self):
        self.use_kivy_settings = False
        Window.borderless = True
        Window.bind(on_request_close=self.stop_warning)
        Window.bind(mouse_pos=self.mouse_position)
        Window.bind(on_touch_down=self.just_clicked_here)
        Window.bind(on_touch_move=self.moving_cursor)
        return MainWindow()

# Must be called from main.
if __name__ == "__main__":
    CIMgui().run()