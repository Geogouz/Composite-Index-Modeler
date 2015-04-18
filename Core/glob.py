# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'
print "adding", __name__

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

# set checkpoint
checkpoint = 100

# print start_url + countries + "GRC" + "/" + indicators + "AG.LND.FRST.K2" + "/" + end_url