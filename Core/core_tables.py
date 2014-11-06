print "importing core_tables"

import urllib
import json
from datetime import datetime
import glob


def build():
    #build core table with indicators and countries

    #save sources into json files
    urllib.urlretrieve(glob.start_url+glob.countries+glob.end_url, "./DB/Countries.json")
    urllib.urlretrieve(glob.start_url+glob.topics+glob.end_url, "./DB/Topics.json")
    #urllib.urlretrieve(glob.start_url+glob.indicators+glob.end_url, "./DB/Indicators.json")

    #open json files
    loaded_countries = open("./DB/Countries.json", "r")
    loaded_topics = open("./DB/Topics.json", "r")
    loaded_indicators = open("./DB/indicators.json", "r")
    readfile = open("./DB/config.ini")

    #convert json files into python structures
    glob.countriesPY = json.load(open("./DB/Countries.json", "r"))
    glob.topicsPY = json.load(open("./DB/Topics.json", "r"))
    glob.indicatorsPY = json.load(open("./DB/indicators.json", "r"))
    glob.cfg_loaded = json.load(readfile)

    #close json files
    loaded_countries.close()
    loaded_topics.close()
    loaded_indicators.close()
    readfile.close()

    #cfg update - last core_table update datetime
    glob.cfg_loaded.update({"table_date": str(datetime.today())})

    #write cfg file
    writefile = open("./DB/config.ini", "w")
    json.dump(glob.cfg_loaded, writefile)
    #close cfg file
    writefile.close()

#def check():
    #check for last core_table update
