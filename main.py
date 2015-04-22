# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'
print "adding", __name__

import os
import threading
import time
from datetime import datetime
import urllib
import json

from kivy.core.window import Window
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty

# set WorldBank API static parameters
start_url = "http://api.worldbank.org/"
end_url = "?per_page=30000&format=json"

# set url catalogs
countries = "countries/"
topics = "topics/"
indicators = "indicators/"

# set_coredb
coredb_py = None

# set user.db
userdb = [["GRC", "ALB", "ITA", "TUR", "CYP"],
          ["SP.DYN.LE00.IN", "MYS.MEA.YSCH.25UP.MF", "SE.SCH.LIFE", "NY.GNP.PCAP.PP.CD", "UNDP.HDI.XD"]]

# print start_url + countries + "GRC" + "/" + indicators + "AG.LND.FRST.K2" + "/" + end_url


class MainWindow(BoxLayout):

    # set kivy properties. no process or popup is running on app init
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    def threadonator(self, *arg):
        threading.Thread(target=arg[0], args=(arg,)).start()
        return 1

    def update_progressbar(self, *arg):
        while self.processing:
            self.coredb_state.text = "A process is running..\nPlease wait."
            print "loading..."
            self.core_build_progress_bar.value = 50
            time.sleep(1)
        self.core_build_progress_bar.value = 100
        return 1

    # build coredb with indicators and countries
    def core_build(self, *arg):
        # init process
        self.processing = True
        self.threadonator(self.update_progressbar)
        time.sleep(10)

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

        self.processing = False
        return 1

    # check for last coredb update
    def check(self, *arg):
        global coredb_py
        while True:# na to kaluterepsw me loop
            # if there is any process running, wait until finish
            while self.processing:
                if not self.popup_active:
                    return
                else:
                    time.sleep(1)

            self.processing = True
            # try to open the json DB file
            try:
                stored_coredb = open("./DB/core.db", "r")

                # convert json file into temp python structure
                coredb_py = json.load(stored_coredb)

                # close json file
                stored_coredb.close()
                self.coredb_state.text = ("Latest DB Update:\n" + coredb_py[0]['table_date'])
            except:
                self.coredb_state.text = "No valid Indices Database found!\nPlease update it."

            self.processing = False

    # build valuesdb with indicators and countries
    def values_build(self):
        return "test function"


class CIMgui(App):

    def stop_warning(self, *args, **kwargs):
        print "Are you sure?.."
        return True

    def build(self):
        #Window.borderless = True # halted until bug fixed
        Window.bind(on_request_close=self.stop_warning)
        return MainWindow()

# must be called from main
if __name__ == "__main__":
    CIMgui().run()