import urllib
import json
from datetime import datetime
import glob
import os

#build coredb with indicators and countries
def core_build():
    #save sources into json files
    urllib.urlretrieve(glob.start_url + glob.countries + glob.end_url, "./DB/Countries.json")
    urllib.urlretrieve(glob.start_url + glob.topics + glob.end_url, "./DB/Topics.json")
    urllib.urlretrieve(glob.start_url + glob.indicators + glob.end_url, "./DB/Indicators.json")

    #open json files
    file_countries = open("./DB/Countries.json", "r")
    file_topics = open("./DB/Topics.json", "r")
    file_indicators = open("./DB/indicators.json", "r")
    file_coredb = open("./DB/core.db", "w")

    #convert json files into temp python structures
    countries_py = json.load(file_countries)
    topics_py = json.load(file_topics)
    indicators_py = json.load(file_indicators)

    #close json files
    file_countries.close()
    file_topics.close()
    file_indicators.close()
    file_coredb.close()

    #zip python structures into a single DB list
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

    #coredb update
    coredb[0] = {"table_date": str(datetime.today())}
    countries_zip[0] = {"countries_num": countries_py[0]["total"]}
    topics_zip[0] = {"topics_num": topics_py[0]["total"]}
    free_indicators_zip[0] = {"free_indicators_num": (len(free_indicators_zip)-1)}

    coredb[1] = countries_zip
    coredb[2] = topics_zip
    coredb[3] = free_indicators_zip

    #store the new coredb file
    file_coredb = open("./DB/core.db", "w")
    json.dump(coredb, file_coredb)
    file_coredb.close()

    #flush temp  python structures
    countries_py = None
    topics_py = None
    indicators_py = None
    countries_zip = None
    topics_zip = None
    free_indicators_zip = None
    coredb = None

    #delete temp downloaded json files
    os.remove("./DB/Countries.json")
    os.remove("./DB/Indicators.json")
    os.remove("./DB/Topics.json")

#check for last coredb update
def check():
    pass

def values_build():
    pass