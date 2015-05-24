# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'

import kivy
kivy.require('1.9.0')

import os
import threading
import time
from datetime import datetime
import urllib
import json

from kivy.config import Config
Config.set("kivy", "exit_on_escape", False)
Config.set("graphics", "height", 660)
Config.set("graphics", "width", 1340)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.animation import Animation
from kivy.factory import Factory
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import BooleanProperty, StringProperty, DictProperty, ListProperty
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button

# Set WorldBank API static parameters.
start_url = "http://api.worldbank.org/"
end_url = "?per_page=30000&format=json"

# Set url catalogs. # TODO which of those needed?
countries = "countries/"
topics = "topics/"
indicators = "indicators/"

# Set url for World Development Indicators (WDI)
wdi_url = "http://api.worldbank.org/source/2/indicators/?per_page=30000&format=json"

# Prepare the file to store core's index database.
coredb_py = None

# Set userdb
userdb = [["GRC", "ALB", "ITA", "TUR", "CYP"],
          ["SP.DYN.LE00.IN", "MYS.MEA.YSCH.25UP.MF", "SE.SCH.LIFE", "NY.GNP.PCAP.PP.CD", "UNDP.HDI.XD"]]

# print start_url + countries + "GRC" + "/" + indicators + "AG.LND.FRST.K2" + "/" + end_url


class TopicToggleButton(ToggleButton):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(TopicToggleButton, self).__init__(**kwargs)

    note = StringProperty("")


class IndexToggleButton(ToggleButton):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexToggleButton, self).__init__(**kwargs)

    code = StringProperty("")
    note = StringProperty("")
    topic = StringProperty("")


class Btn_Rmv(Button):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(Btn_Rmv, self).__init__(**kwargs)

    index = StringProperty("")


class IndexStackLayout(StackLayout):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexStackLayout, self).__init__(**kwargs)

    def do_layout(self, *largs):
        super(IndexStackLayout, self).do_layout()

        # Try to fix each Index button.
        try:
            # Calculate how many cols are inside the slider.
            col = int((self.width-8)//380)

            for button in range(1, len(IndexSelection.shown_ind_btns)+1, col):
                # Prepare the list to store each button height per line.
                height_list = []

                # Locate the highest texture_size per line.
                for step in range(col):
                    height_list.append(IndexSelection.shown_ind_btns[button+step].texture_size[1])
                    # If current is last button, break.
                    if button+step == len(IndexSelection.shown_ind_btns):
                        break

                # Renew the height of each button per line, to the highest one.
                for step in range(col):
                    IndexSelection.shown_ind_btns[button+step].height = max(height_list)+20
                    # If current is last button, break.
                    if button+step == len(IndexSelection.shown_ind_btns):
                        break
        except:
            pass


class IndexSelection(Screen):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexSelection, self).__init__(**kwargs)

    # TODO must set to True after update
    must_build_topics = True

    # Use this dictionary as a Class variable (usable from other Classes too).
    shown_ind_btns = {}
    selected_indices = DictProperty({"feat_index": None, "my_indices": {}})

    # Recursively convert Unicode objects to strings objects.
    def string_it(self, obj):
        if isinstance(obj, dict):
            return {self.string_it(key): self.string_it(value) for key, value in obj.iteritems()}
        elif isinstance(obj, list):
            return [self.string_it(element) for element in obj]
        elif isinstance(obj, unicode):
            return obj.encode('utf-8')
        else:
            return obj

    # Function that will run everytime mouse is moved.
    def on_mouse_hover(self, *args):
        for button in self.topics_dic.keys():
            if button.collide_point(
                    self.topics_slider.to_local(args[1][0], args[1][1])[0],
                    self.topics_slider.to_local(args[1][0], args[1][1])[1]):
                button.background_normal = './Sources/button_hovered.png'
            else:
                button.background_normal = './Sources/button_normal.png'

        # Check if mouse is over add_index_icon.
        if self.add_index_icon.collide_point(args[1][0], args[1][1]):
            self.add_index_label.color = (0.34, 0.65, 0.90, 1)
        else:
            self.add_index_label.color = (1, 1, 1, 1)

        # Check if mouse is over toggle_index_desc_icon.
        if self.toggle_index_desc_icon.collide_point(args[1][0], args[1][1]):
            self.toggle_index_desc_label.color = (0.34, 0.65, 0.90, 1)
        else:
            self.toggle_index_desc_label.color = (1, 1, 1, 1)

        # Check if mouse is over search_bar.
        if self.search_bar.collide_point(
                self.my_indices_screen.to_local(args[1][0], args[1][1])[0],
                self.my_indices_screen.to_local(args[1][0], args[1][1])[1]) and \
                        self.my_indices_search_sm.current == "my_indices":
            print "search_bar"

        # Check if mouse is over my_indices_bar.
        if self.my_indices_bar.collide_point(
                self.search_screen.to_local(args[1][0], args[1][1])[0],
                self.search_screen.to_local(args[1][0], args[1][1])[1]) and \
                        self.my_indices_search_sm.current == "search_index":
            print "my_indices_bar"

    # Function that clears the slider's stacklayout.
    def clear_indices_stack(self):
        # Clear all widgets from stack layout.
        self.indices_slider_stack.clear_widgets()

        # Clear minimum_height of layout (needed cause of kivy version bug).
        self.indices_slider_stack.minimum_height = 0

        # Reset slider position back to top.
        self.indices_slider.scroll_y = 1

        # Clear the "feat_index".
        self.selected_indices["feat_index"] = None

    # This function is called when an Index is selected.
    def on_index_selection(self, *args):
        # If current index selection is the feat_index.
        if args[0] == self.selected_indices["feat_index"]:
            # It means the same button has been toggled and should clear the "feat_index".
            self.selected_indices["feat_index"] = None
        else:
            try:
                self.selected_indices["feat_index"].state = "normal"
            except:
                pass
            self.selected_indices["feat_index"] = args[0]
        # Reset slider position back to top.
        self.index_desc_slider.scroll_y = 1

    # This function is called when an Index is added to my_indices.
    def on_my_indices(self):
        # If user has selected an Index..
        if not self.selected_indices["feat_index"] is None and \
                not (self.selected_indices["feat_index"].text in self.selected_indices["my_indices"]):
            # Add Index to my_indices.
            self.selected_indices["my_indices"][self.selected_indices["feat_index"].text] = \
                self.selected_indices["feat_index"].code

            # Set proper btn backgrounds based on my_indices.
            self.btn_index_background()

            # Create my_index_box to hold my_index components.
            my_index_box = Factory.MyIndexBox()

            # Create btn_rmv_anchor to hold btn_rmv.
            btn_rmv_anchor = AnchorLayout(size_hint_y=None, height=25, anchor_x= "right", padding=[0, 0, 10, 0])

            # Create a removing index btn and add it to it's parent float.
            btn_rmv = Factory.Btn_Rmv(index=self.selected_indices["feat_index"].text, on_release=self.rmv_my_indices)

            # Add btn_rmv in btn_rmv_anchor.
            btn_rmv_anchor.add_widget(btn_rmv)

            # Create my_index Label.
            my_index = Factory.MyIndex(text=self.selected_indices["feat_index"].text)

            # Create my_topic Label.
            my_topic = Factory.MyTopic(text=self.selected_indices["feat_index"].topic)

            # Add all components in my_index_box.
            my_index_box.add_widget(btn_rmv_anchor)
            my_index_box.add_widget(Factory.ShadeLine())
            my_index_box.add_widget(my_index)
            my_index_box.add_widget(my_topic)

            # Bind children heights to parent box.
            my_index.bind(height=self.fix_my_index_h)
            my_topic.bind(height=self.fix_my_index_h)

            # Add my_index_box in my_indices_container.
            self.my_indices_container.add_widget(my_index_box)

            # Switch to my_indices.
            self.my_indices_search_sm.current = "my_indices"

    def rmv_my_indices(self, *args):
        # Remove index from the dict with my indices.
        self.selected_indices["my_indices"].pop(args[0].index, None)

        # Remove that specific my_index_box.
        self.my_indices_container.remove_widget(args[0].parent.parent)

        # Set proper btn backgrounds based on my_indices.
        self.btn_index_background()

    def fix_my_index_h(self, *args):

        # Init box height is the sum of the Top and Bottom box paddings
        args[0].parent.height = args[0].parent.padding[3]

        # For each child in box add it's height to the box.
        for child in args[0].parent.children:
            args[0].parent.height += child.height

    # This function sets proper background_normal of index buttons.
    def btn_index_background(self):
        for btn in IndexSelection.shown_ind_btns.values():
            # For each index button, search if it is in my_indices.
            if btn.text in self.selected_indices["my_indices"].keys():
                btn.background_normal = './Sources/grey_btn_down.png'
                btn.bold = True
            else:
                btn.background_normal = './Sources/wht_btn_normal.png'
                btn.bold = False

    # This method checks if there is any core DB available.
    # If there is, it creates the topics dictionary (topics - button objects).
    def build_indices(self):
        # TODO must first unbind other window and other kind of binds from other screens
        # TODO do same oon other screens Classes

        # If topics dictionary shouldn't be loaded, do nothing.
        if not self.must_build_topics:
            pass

        else:
            self.topics_dic = {}

            # Checks if there is a coreDB available.
            try:
                set_stored_coredb = open("./DB/core.db", "r")
                set_coredb_py = self.string_it(json.load(set_stored_coredb))
                set_stored_coredb.close()

                # There is no topic at the beginning.
                topics_count = 0

                # For each topic in core DB..
                for topic_numbers in range(1, (set_coredb_py[2][0]['topics_num'])+1):

                    # Except topics without Topic note.
                    if set_coredb_py[2][topic_numbers][0]['note'] != "":

                        # Count topics.
                        topics_count += 1

                        # Grab the topic Info.
                        topic_note = str(set_coredb_py[2][topic_numbers][0]["note"])
                        topic_name = str(set_coredb_py[2][topic_numbers][0]["name"])

                        # Create a new topic button object.
                        new_button_object = TopicToggleButton(
                            text=topic_name,
                            note=topic_note)

                        # Bind on_release action.
                        new_button_object.bind(on_release=self.add_topic)

                        # Build each separate dictionary with topic's indices.
                        indices_dic = {}
                        for index in range(1, set_coredb_py[2][topic_numbers][0]["indicators_num"]+1):
                            indices_dic[set_coredb_py[2][topic_numbers][index][1]] = \
                                [set_coredb_py[2][topic_numbers][index][0],
                                 set_coredb_py[2][topic_numbers][index][2]]

                        # Store the keys and values from the DB to the cache dictionary.
                        self.topics_dic[new_button_object] = indices_dic

                        # Place the button inside the slider.
                        self.topics_slider_box.add_widget(new_button_object)

                # Every time mouse moves on Index Selection screen, on_mouse_hover method will be called.
                Window.bind(mouse_pos=self.on_mouse_hover)

                # Set the height of the Topics menu based on heights and box padding.
                self.topics_slider_box.height = (topics_count * 48) + topics_count + 1

                # Topics dictionary should not be loaded again.
                self.must_build_topics = False

            # If there is no core DB available it prompts for indices update.
            except Exception as e:
                self.topics_dic = {}
                print e.__doc__, "That which means no index DB has been found. Must update indices first."  # TODO UPDATE MESSAGE

    def add_topic(self, *args):
        # If topic button is pressed, create index buttons.
        if args[0].state == "down":

            self.clear_indices_stack()
            # Switch topic buttons states.
            for button in self.topics_dic.keys():
                if button.state == "down" and (button != args[0]):
                    button.state = "normal"

            # Create and add the topic title.
            topic = Factory.TopicTitle(text=args[0].text)
            self.indices_slider_stack.add_widget(topic)

            # Create and add the topic note.
            topic_description = Factory.TopicDescription(text=args[0].note)
            self.indices_slider_stack.add_widget(topic_description)

            # Prepare var for each index button ID
            index_btn_id = 0

            # Prepare an empty dictionary to hold each index button object and it's ID.
            IndexSelection.shown_ind_btns = {}

            # Create and add the topic index buttons.
            for index in sorted(self.topics_dic[args[0]].keys()):
                index_btn_id += 1
                btn = IndexToggleButton(
                    code=self.topics_dic[args[0]][index][0],
                    text=index,
                    note=self.topics_dic[args[0]][index][1],
                    topic=args[0].text)

                # Bind each index button with the on_index_selection function.
                btn.bind(on_release=self.on_index_selection)

                # Place the button in the stacklayout.
                self.indices_slider_stack.add_widget(btn)

                # Add the button's ID and object button itself in the global "shown_ind_btns" dictionary.
                IndexSelection.shown_ind_btns[index_btn_id] = btn

            # Set proper btn backgrounds based on my_indices.
            self.btn_index_background()

        # Button is not pressed, which means it self toggled.
        else:
            self.clear_indices_stack()


class Home(Screen):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(Home, self).__init__(**kwargs)


class MapDesigner(Screen):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(MapDesigner, self).__init__(**kwargs)


class CIMScreenManager(ScreenManager):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(CIMScreenManager, self).__init__(**kwargs)


class CIMMenu(BoxLayout):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(CIMMenu, self).__init__(**kwargs)


class MainWindow(BoxLayout):

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(MainWindow, self).__init__(**kwargs)

    # Prepare kivy properties that show if a process or a popup are currently running. Set to False on app's init.
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    def threadonator(self, *arg):
        threading.Thread(target=arg[0], args=(arg,)).start()

    # Loading bar
    def update_progress(self, *arg):
        anim_bar = Factory.AnimWidget()
        # Some time to render.
        time.sleep(1)
        self.core_build_progress_bar.add_widget(anim_bar)
        anim = Animation(opacity=0.3, width=300, duration=0.6)
        anim += Animation(opacity=1, width=100, duration=0.6)
        anim.repeat = True
        anim.start(anim_bar)
        while self.processing:
            pass
        self.core_build_progress_bar.remove_widget(anim_bar)

    # This method builds core's index database with indicators and countries.
    def core_build(self, *arg):
        # TODO Must tell the user to save his preferred indices because they will be lost
        # A process just started running (in a new thread).
        self.processing = True
        self.threadonator(self.update_progress)

        # Try, in case there is a problem with the online updating process.
        try:
            # Set target web links.
            c_link = start_url + countries + end_url
            t_link = start_url + topics + end_url

            # Save sources into json files.
            urllib.urlretrieve(c_link, "./DB/Countries.json")
            urllib.urlretrieve(t_link, "./DB/Topics.json")
            urllib.urlretrieve(wdi_url, "./DB/WDI.json")

            # Open json files.
            file_countries = open("./DB/Countries.json", "r")
            file_topics = open("./DB/Topics.json", "r")
            file_wdi = open("./DB/WDI.json", "r")

            # Convert json files into temp python structures.
            countries_py = json.load(file_countries)
            topics_py = json.load(file_topics)
            wdi_py = json.load(file_wdi)

            # Close json files.
            file_countries.close()
            file_topics.close()
            file_wdi.close()

            # Zip python structures into a single DB list.
            countries_zip = [[]]
            topics_zip = [[]]

            coredb = [None, None, None]

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
                    {"name": (topics_py[1][topic]["value"]),
                     "note": (topics_py[1][topic]["sourceNote"])}])

            # Add one last "Various" topic for all indicators without one.
            topics_zip.append([{"name": "Various", "note": "Various"}])

            # Append all indicators to their parent topic/topics.
            for indicator in range(wdi_py[0]["total"]):

                # Check if an indicator has no parents.
                if len(wdi_py[1][indicator]["topics"]) == 0:

                    # We will append it to "Various" topics (last item in the list).
                    topics_zip[-1].append([
                        (wdi_py[1][indicator]["id"]),
                        (wdi_py[1][indicator]["name"]),
                        (wdi_py[1][indicator]["sourceNote"])])

                used_topics = []

                # If an indicator has multiple parents, we want to append it to all of them.
                # Max parent_topic from a single indicator is 5 (with id's: 3,20,7,19,7)
                for parent_topic in range(len(wdi_py[1][indicator]["topics"])):
                    # Check if indicator has been added to same parent topic again before.
                    if int(wdi_py[1][indicator]["topics"][parent_topic]["id"]) not in used_topics:
                        used_topics.append(int(wdi_py[1][indicator]["topics"][parent_topic]["id"]))
                        topics_zip[int(wdi_py[1][indicator]["topics"][parent_topic]["id"])].append([
                            (wdi_py[1][indicator]["id"]),
                            (wdi_py[1][indicator]["name"]),
                            (wdi_py[1][indicator]["sourceNote"])])

            for topic in range(len(topics_zip)-1):
                topics_zip[topic+1][0]["indicators_num"] = len(topics_zip[topic+1])-1

            # Core DB update.
            coredb[0] = {"table_date": str(datetime.today())}
            countries_zip[0] = {"countries_num": countries_py[0]["total"]}
            # Use -1 to exclude first empty [] from the list
            topics_zip[0] = {"topics_num": len(topics_zip)-1}

            coredb[1] = countries_zip
            coredb[2] = topics_zip

            # Store the new coredb file.
            file_coredb = open("./DB/core.db", "w")
            json.dump(coredb, file_coredb)
            file_coredb.close()

            # Delete temp downloaded json files.
            os.remove("./DB/Countries.json")
            os.remove("./DB/Topics.json")
            os.remove("./DB/WDI.json")

        except Exception as e:
            print e.__doc__, e.message, "Could not update Coredb. Please try again."
        self.processing = False

    # This method checks for last core's index database update.
    def check(self, *arg):
        global coredb_py

        # For as long as the popup window is shown.
        while self.popup_active and (not CIMgui.app_closed):

            # If there is any process running, wait until finish.
            while self.processing:
                self.coredb_state.text = "Updating Indices!\nDuration depends on your Internet speed.."
                time.sleep(1)

            # Try to open the json DB file.
            try:
                stored_coredb = open("./DB/core.db", "r")
                coredb_py = json.load(stored_coredb)
                stored_coredb.close()

                self.coredb_state.text = ("Latest DB Update:\n" + coredb_py[0]['table_date'])

            except Exception as e:
                print e.__doc__, e.message
                self.coredb_state.text = "No valid Indices Database found!\nPlease update it."
            time.sleep(2)


class CIMgui(App):

    # app_closed will get triggered when App stops.
    app_closed = False

    def on_stop(self):
        CIMgui.app_closed = True

    # This function returns the window.
    def build(self):
        self.use_kivy_settings = False
        return MainWindow()

# Must be called from main.
if __name__ == "__main__":
    CIMgui().run()