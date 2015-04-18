#set WorldBank API static parameters
start_url = "http://api.worldbank.org/"
end_url = "?per_page=30000&format=json"

#set url catalogs
countries = "countries/"
topics = "topics/"
indicators = "indicators/"

#set user.db
userdb = [["GRC", "ALB", "ITA", "TUR", "CYP"],
          ["SP.DYN.LE00.IN", "MYS.MEA.YSCH.25UP.MF", "SE.SCH.LIFE", "NY.GNP.PCAP.PP.CD", "UNDP.HDI.XD"]]

print "just called glob.py"
print start_url + countries + "GRC" + "/" + indicators + "AG.LND.FRST.K2" + "/" + end_url