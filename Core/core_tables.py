import urllib
import json
from datetime import datetime
import glob


def build():
    #build core table with indicators and countries

    #save sources into json files
    #urllib.urlretrieve(glob.start_url+glob.countries+glob.end_url, "./DB/Countries.json")
    #urllib.urlretrieve(glob.start_url+glob.topics+glob.end_url, "./DB/Topics.json")
    #urllib.urlretrieve(glob.start_url+glob.indicators+glob.end_url, "./DB/Indicators.json")

    #open json files
    file_countries = open("./DB/Countries.json", "r")
    file_topics = open("./DB/Topics.json", "r")
    file_indicators = open("./DB/indicators.json", "r")
    file_config = open("./DB/config.ini", "w")

    #convert json files into temp python structures
    countries_py = json.load(file_countries)
    topics_py = json.load(file_topics)
    indicators_py = json.load(file_indicators)

    #close json files
    file_countries.close()
    file_topics.close()
    file_indicators.close()
    file_config.close()

    #zip python structures into lists
    #get countries names
    countries_zip = []
    topics_zip = []
    indicators_zip = []
    cfg = [None, None, None]

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
            (topics_py[1][topic]["id"]),
            (topics_py[1][topic]["value"])])

    for indicator in range(indicators_py[0]["total"]):
        indicators_zip.append([
            (indicators_py[1][0]["id"])
            (indicators_py[1][0]["name"])
            (indicators_py[1][0]["sourceNote"])
            (indicators_py[1][0]["topics"][0]["id"])
        ])

    #cfg update
    cfg[0] = {"table_date": str(datetime.today()), "countries_num": countries_py[0]["total"], "topics_num": topics_py[0]["total"]}
    cfg[1] = countries_zip
    cfg[2] = topics_zip

    #store the new cfg file
    file_config = open("./DB/config.ini", "w")
    json.dump(cfg, file_config)
    file_config.close()

    #flush temp  python structures
    countries_py = None
    topics_py = None
    indicators_py = None

    countries_zip = None
    topics_zip = None
    indicators_zip = None

    cfg = None

#def check():
    #check for last core_table update