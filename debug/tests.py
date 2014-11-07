import json

#open json files for read
file_countries = open("Countries.json")
file_topics = open("Topics.json")
file_indicators = open("indicators.json")
#file_config = open("config.ini")

#convert json files into temp python structures
countries_py = json.load(file_countries)
topics_py = json.load(file_topics)
indicators_py = json.load(file_indicators)
#config_py = json.load(file_config)

#close json files
file_countries.close()
file_topics.close()
file_indicators.close()
#file_config.close()

