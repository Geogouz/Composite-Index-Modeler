import kivy
kivy.require('1.9.0')

# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'
print "adding", __name__

import os
import threading
import time
from datetime import datetime
import urllib
import json

from kivy.config import Config
Config.set("kivy", "exit_on_escape", False)
Config.set("graphics", "height", 768)
Config.set("graphics", "width", 1300)

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.factory import Factory
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import BooleanProperty, ObjectProperty, DictProperty

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


class Home(Screen):
    pass


class IndexSelection(Screen):

    topics_dic = {}
    topics_box = ObjectProperty()

    def __init__(self, **kwargs):
        # Preparing the IndexSelection.topics_dic on loading
        try:
            is_stored_coredb = open("./DB/core.db", "r")
            is_coredb_py = json.load(is_stored_coredb)
            is_stored_coredb.close()

            IndexSelection.topics_dic = is_coredb_py
            print IndexSelection.topics_dic

        except Exception as e:
            print e.__doc__
            print e.message
            print "No index DB available found. Must update indices."

        Window.bind(mouse_pos=self.on_mouse_hover)
        super(IndexSelection, self).__init__(**kwargs)

    def build_topics_box(self, **kwargs):
        if False:
            self.topics_but_2 = Button(text='Hello world 1')
            self.topics_box.add_widget(self.topics_but_2)
        else:
            print "Please update your Indices"

    def on_mouse_hover(self, *args):
        if self.topics_but_1.collide_point(*args[1]):
            self.topics_but_1.background_normal = './Sources/button_hovered.png'
        else:
            self.topics_but_1.background_normal = './Sources/button_normal.png'


class MapDesigner(Screen):
    pass


class CIMScreenManager(ScreenManager):
    pass


class CIMMenu(BoxLayout):
    pass


class MainWindow(BoxLayout):

    # Prepare kivy properties that show if a process or a popup are currently running. Set to False on app's init.
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    def threadonator(self, *arg):
        threading.Thread(target=arg[0], args=(arg,)).start()
        return 1

    def update_progress(self, *arg):
        anim_bar = Factory.AnimWidget()
        # Some time to render
        time.sleep(1)
        self.core_build_progress_bar.add_widget(anim_bar)
        anim = Animation(opacity=0.3, width=300, duration=0.6)
        anim += Animation(opacity=1, width=100, duration=0.6)
        anim.repeat = True
        anim.start(anim_bar)
        while self.processing:
            pass
        self.core_build_progress_bar.remove_widget(anim_bar)
        return 1

    # This method checks if there is any core DB available and calls index selection screen
    def build_topics_dic(self):
        # If there is no index DB available, then popup the update notice
        if IndexSelection.topics_dic == {}:
            print "pure new"
        # If there is a DB continue to index selection screen
        else:
            print "continue"

    # This method builds core's index database with indicators and countries.
    def core_build(self, *arg):

        # A process just started running (in a new thread).
        self.processing = True
        self.threadonator(self.update_progress)

        # Try, in case there is a problem with the online updating process.
        try:
            time.sleep(5)
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

            # delete temp downloaded json files
            os.remove("./DB/Countries.json")
            os.remove("./DB/Indicators.json")
            os.remove("./DB/Topics.json")
            """
        except Exception as e:
            print e.__doc__
            print e.message
            print "Could not update Coredb. Please try again."
        self.processing = False
        return 1

    # This method checks for last core's index database update.
    def check(self, *arg):
        global coredb_py

        # For as long as the popup window is shown.
        while self.popup_active and (not CIMgui.app_closed):

            # If there is any process running, wait until finish.
            while self.processing:
                self.coredb_state.text = ("Updating Indices!\nDuration depends on your Internet speed..")
                time.sleep(1)

            # Try to open the json DB file.
            try:
                stored_coredb = open("./DB/core.db", "r")
                coredb_py = json.load(stored_coredb)
                stored_coredb.close()

                self.coredb_state.text = ("Latest DB Update:\n" + coredb_py[0]['table_date'])

            except Exception as e:
                print e.__doc__
                print e.message
                self.coredb_state.text = "No valid Indices Database found!\nPlease update it."
            time.sleep(2)
        return 1


class CIMgui(App):

    # app_closed will get triggered when App stops.
    app_closed = False

    def on_stop(self):
        CIMgui.app_closed = True
        return 1

    # This function prepares the window.
    def build(self):
        self.use_kivy_settings = False
        return MainWindow()

# Must be called from main.
if __name__ == "__main__":
    CIMgui().run()