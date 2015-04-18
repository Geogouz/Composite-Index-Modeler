# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'
print "adding", __name__

import urllib
import json
from datetime import datetime
import os
from threading import Thread
from glob import *


def update_progressbar():
    global checkpoint, t1

    try:
        print checkpoint, ":", str(datetime.today() - t1)
        checkpoint += 1
        t1 = datetime.today()
    except:
        print "no checkpoint to be grow"
        pass


# build coredb with indicators and countries
def core_build():
    global checkpoint, t1

    # init progressbar
    t1 = datetime.today()
    checkpoint = 0

    # set target web links
    c_link = start_url + countries + end_url
    t_link = start_url + topics + end_url
    i_link = start_url + indicators + end_url
    update_progressbar()

    print urllib.urlopen(c_link).info()['Content-Length']
    update_progressbar()
    print urllib.urlopen(t_link).info()['Content-Length']
    update_progressbar()
    print urllib.urlopen(i_link).info()['Content-Length']
    update_progressbar()

    # save sources into json files
    urllib.urlretrieve(c_link, "./DB/Countries.json")
    update_progressbar()
    urllib.urlretrieve(t_link, "./DB/Topics.json")
    update_progressbar()
    urllib.urlretrieve(i_link, "./DB/Indicators.json")
    update_progressbar()

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
    update_progressbar()

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
    update_progressbar()


# check for last coredb update
def check():
    global coredb_py
    # try to open the json DB file
    try:
        stored_coredb = open("./DB/core.db", "r")

        # convert json file into temp python structure
        coredb_py = json.load(stored_coredb)

        # close json file
        stored_coredb.close()
        return "Latest DB Update:\n" + coredb_py[0]['table_date']
    except:
        return "No valid Indices Database found!\nPlease update it."


# build valuesdb with indicators and countries
def values_build():
    print "thread started"
    return "test function"


# multithread function generator
def threadonator(target_function):
    try:
        if target_function == "values_build":
            t = Thread(target=values_build).start()
            return (t.start())
        elif target_function == "check":
            t = Thread(target=values_build)
            t.start()
    except:
        print "no such function"
