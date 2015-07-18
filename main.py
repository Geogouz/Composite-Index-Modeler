# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'

import kivy
kivy.require('1.9.0')

import threading
import time
from datetime import datetime
import urllib2
import json
import operator
import gc
import os
from functools import partial
import math

from kivy.config import Config
Config.set("kivy", "exit_on_escape", False)
Config.set("graphics", "height", 660)
Config.set("graphics", "width", 1340)

from kivy.app import App
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.scatter import Scatter
from kivy.graphics.svg import Svg
from kivy.animation import Animation
from kivy.uix.stencilview import StencilView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import BooleanProperty, StringProperty, DictProperty, ObjectProperty,\
    ListProperty, NumericProperty
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread
from kivy.uix.dropdown import DropDown

# Set WorldBank API static parameters.
start_url = "http://api.worldbank.org/"
end_url = "?per_page=30000&format=json"

# Set url catalogs.
countries = "countries/"
topics = "topics/"
indicators = "indicators/"

# Set url for World Development Indicators (WDI)
wdi_url = "http://api.worldbank.org/source/2/indicators/?per_page=30000&format=json"


class TopicToggleButton(ToggleButton):

    note = StringProperty("")


class IndexToggleButton(ToggleButton):

    code = StringProperty("")
    note = StringProperty("")
    topic = StringProperty("")


class BtnRmv(Button):

    index = StringProperty("")


class SelectAll(Button):

    region = ObjectProperty()
    normal = StringProperty("")


class MyIndicesBar(BoxLayout):

    # Link to ScreenManager
    mib_my_indicators_search_sm = ObjectProperty()

    def on_touch_down(self, *args):
        super(MyIndicesBar, self).on_touch_down(*args)
        # Check if mouse is over my_indicators_bar.
        if self.collide_point(args[0].pos[0], args[0].pos[1]):

            # Switch Screens.
            self.mib_my_indicators_search_sm.current = "my_indicators"


class SearchBar(BoxLayout):

    # Link to ScreenManager
    sb_my_indicators_search_sm = ObjectProperty()

    def on_touch_down(self, *args):
        super(SearchBar, self).on_touch_down(*args)
        # Check if mouse is over search_bar.
        if self.collide_point(args[0].pos[0], args[0].pos[1]):

            # This touch should not be used to defocus.
            FocusBehavior.ignored_touch.append(args[0])

            # Switch Screens.
            self.sb_my_indicators_search_sm.current = "search_index"


class SearchArea(TextInput):

    pass


class IndexStackLayout(StackLayout):

    def do_layout(self, *largs):
        super(IndexStackLayout, self).do_layout()

        col = int((self.width-8)//380)
        # Try to fix each Index button.
        if col > 0:
            # Calculate how many cols are inside the slider.
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


class CIMScreenManager(ScreenManager):

    mouse_pos = ListProperty()

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(CIMScreenManager, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.setter('mouse_pos'))

    def on_mouse_pos(self, *args):
        self.current_screen.mouse_pos = self.mouse_pos


class MouseScreen(Screen):

    mouse_pos = ListProperty()


class Home(Screen):

    pass


class IndexSelection(MouseScreen):

    # Link to Update button from MainWindow.
    is_update_db = ObjectProperty()

    # Link to CIMScreenManager.
    is_manager = ObjectProperty()

    # Link to IndexCreation.
    is_index_creation = ObjectProperty()

    selected_indices = DictProperty({"feat_index": None, "my_indicators": {}})

    coredb_py = ObjectProperty()

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexSelection, self).__init__(**kwargs)

        self.must_build_topics = True
        self.shown_ind_btns = {}
        self.search_dic = None
        self.topics_dic = None

    # This function updates status Icon that belongs to IndexCreation Class.
    @mainthread
    def dl_status_icon_setter(self):
        # If there is no active Indicator data download..
        if not self.is_index_creation.btn_get_indicators.disabled:
            # Compare my_indicators to sorted_indicators so we know if we must re-download data.
            my_in = self.selected_indices["my_indicators"].keys()
            my_in.sort()

            # If lists are the same..
            if my_in == self.is_index_creation.sorted_indicators:
                self.is_index_creation.downloading_state_icon.source = './Sources/status_valid.png'
            else:
                self.is_index_creation.downloading_state_icon.source = './Sources/status_error.png'

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

    # Function that will run every time mouse is moved.
    def on_mouse_pos(self, *args):
        for button in self.topics_dic.keys():
            if button.collide_point(*button.to_widget(*args[1])):
                button.background_normal = './Sources/button_hovered.png'
            else:
                button.background_normal = './Sources/button_normal.png'

        # Check if mouse is over add_index_icon.
        if self.add_index_icon.collide_point(*args[1]):
            self.add_index_label.color = (0.34, 0.65, 0.90, 1)
        else:
            self.add_index_label.color = (1, 1, 1, 1)

        # Check if mouse is over toggle_index_desc_icon.
        if self.toggle_index_desc_icon.collide_point(*args[1]):
            self.toggle_index_desc_label.color = (0.34, 0.65, 0.90, 1)
        else:
            self.toggle_index_desc_label.color = (1, 1, 1, 1)

    # Function that clears the slider's stacklayout.
    def clear_indices_stack(self):
        # Clear all widgets from stack layout.
        self.indices_slider_stack.clear_widgets()

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
            if self.selected_indices["feat_index"] is not None:
                self.selected_indices["feat_index"].state = "normal"

            self.selected_indices["feat_index"] = args[0]

        # Reset slider position back to top.
        self.index_desc_slider.scroll_y = 1

    # This function is called when an Index is added to my_indicators.
    def on_my_indicators(self):
        # If user has selected an Index..
        if not self.selected_indices["feat_index"] is None and \
                not (self.selected_indices["feat_index"].text in self.selected_indices[
                    "my_indicators"]):
            # Add Index to my_indicators.
            self.selected_indices["my_indicators"][self.selected_indices["feat_index"].text] = \
                self.selected_indices["feat_index"].code

            # Set proper btn backgrounds based on my_indicators.
            self.btn_index_background()

            # Create my_index_box to hold my_index components.
            my_index_box = Factory.MyIndexBox()

            # Create btn_rmv_anchor to hold btn_rmv.
            btn_rmv_anchor = AnchorLayout(size_hint_y=None,
                                          height=25,
                                          anchor_x="right",
                                          padding=[0, 0, 10, 0])

            # Create a removing index btn.
            btn_rmv = Factory.BtnRmv(index=self.selected_indices["feat_index"].text,
                                     on_release=self.rmv_my_indicators)

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

            # Add my_index_box in my_indicators_container.
            self.my_indicators_container.add_widget(my_index_box)

            # Switch to my_indicators.
            self.my_indicators_search_sm.current = "my_indicators"

            # Remove previous text inputs.
            self.search_area.text = ""

            # Check if indicator data must be downloaded again.
            self.dl_status_icon_setter()

    def rmv_my_indicators(self, *args):
        # Remove index from the dict with my indices.
        self.selected_indices["my_indicators"].pop(args[0].index, None)

        # Remove that specific my_index_box.
        self.my_indicators_container.remove_widget(args[0].parent.parent)

        # Set proper btn backgrounds based on my_indicators.
        self.btn_index_background()

        # Check if indicator data must be downloaded again.
        self.dl_status_icon_setter()

    # Function that clears all search results.
    def clear_search_results(self, *args):
        # Clear all widgets from search_results_container.
        self.search_results_container.clear_widgets()

        # Reset slider position back to top.
        self.search_results_slider.scroll_y = 1

        # Clear search area too because user pressed the clear button.
        if len(args) == 1:
            # Remove previous text inputs.
            self.search_area.text = ""

    @staticmethod
    def fix_my_index_h(*args):
        # Init box height is the sum of the Top and Bottom box paddings
        args[0].parent.height = args[0].parent.padding[1] + args[0].parent.padding[3]

        # For each child in box add it's height to the box.
        for child in args[0].parent.children:
            args[0].parent.height += child.height

    # This function sets proper background_normal of index buttons.
    def btn_index_background(self):
        # For each index button..
        for btn in IndexSelection.shown_ind_btns.values():
            # search if it is in my_indicators.
            if btn.text in self.selected_indices["my_indicators"].keys():
                btn.background_normal = './Sources/grey_btn_down.png'
                btn.bold = True
            else:
                btn.background_normal = './Sources/wht_btn_normal.png'
                btn.bold = False

    def search_results(self, keyword):
        # Clears all search results.
        self.clear_search_results()

        # Create sr_toolbox to hold sr_title and clear_sr.
        sr_toolbox = BoxLayout(orientation="vertical", size_hint_y=None, height=55)

        # Create search Title Label.
        sr_title = Factory.SR_Title()

        # Create button to clear results.
        clear_sr = Factory.SR_Clear(on_press=self.clear_search_results)

        # Add search Title and clear button to sr_toolbox
        sr_toolbox.add_widget(clear_sr)
        sr_toolbox.add_widget(sr_title)

        # Add sr_toolbox to search_results_container.
        self.search_results_container.add_widget(sr_toolbox)

        for topic in self.search_dic:
            for index in self.search_dic[topic]:
                if keyword.lower() in index.lower():

                    # Create searched_index_box to hold searched_index components.
                    searched_index_box = Factory.SearchBox()

                    # List to store occurrences.
                    occurrences = []

                    located = None
                    # Convert each index into a marked index.
                    while located != -1:
                        located = index.lower().find(keyword.lower())
                        if located != -1:

                            occurrences.append(
                                index.partition(index[located:located+len(keyword)])[0])
                            occurrences.append("[color=ff0078][b]")
                            occurrences.append(
                                index.partition(index[located:located+len(keyword)])[1])
                            occurrences.append("[/b][/color]")

                            index = index.partition(index[located:located+len(keyword)])[2]
                        else:
                            occurrences.append(index)

                    marked_index = ''.join(occurrences)

                    # Create search result index Label.
                    my_index = Factory.SR_Index(text=marked_index)

                    # Create search result topic Label.
                    my_topic = Factory.SR_Topic(text=topic)

                    # Add all components in searched_index_box.
                    searched_index_box.add_widget(my_topic)
                    searched_index_box.add_widget(my_index)

                    # Bind children heights to parent box.
                    my_index.bind(height=self.fix_my_index_h)
                    my_topic.bind(height=self.fix_my_index_h)

                    # Add searched_index_box in search_results_container.
                    self.search_results_container.add_widget(searched_index_box)

        # Show number of search results.
        if len(self.search_results_container.children) > 1:
            sr_title.text = str(len(self.search_results_container.children)-1) + " matches found:"
            sr_title.color = (0.1, 1, 0.1, 1)
        else:
            sr_title.text = "No results"
            sr_title.color = (1, 0, 0, 1)

    # This method checks if there is any core DB available.
    # If there is, it creates the topics dictionary (topics - button objects).
    def build_indices(self):
        # If topics dictionary shouldn't be loaded, do nothing.
        if not self.must_build_topics:
            # Switch screen without updating indicator database.
            self.is_manager.current = 'IndexSelectionScreen'

        else:

            self.topics_dic = {}

            # Checks if there is a coreDB available.
            try:
                set_stored_coredb = open("./DB/core.db", "r")
                self.coredb_py = self.string_it(json.load(set_stored_coredb))
                set_stored_coredb.close()

                # There is no topic at the beginning.
                topics_count = 0

                # For each topic in core DB..
                for topic_numbers in range(1, int(self.coredb_py[2][0]['topics_num'])+1):

                    # Except topics without Topic note.
                    if self.coredb_py[2][topic_numbers][0]['note'] != "":

                        # Count topics.
                        topics_count += 1

                        # Grab the topic Info.
                        topic_note = str(self.coredb_py[2][topic_numbers][0]["note"])
                        topic_name = str(self.coredb_py[2][topic_numbers][0]["name"])

                        # Create a new topic button object.
                        new_button_object = TopicToggleButton(
                            text=topic_name,
                            note=topic_note,
                            on_release=self.add_topic)

                        # Build each separate dictionary with topic's indices.
                        indices_dic = {}
                        for index in range(
                                1, int(self.coredb_py[2][topic_numbers][0]["indicators_num"])+1):
                            indices_dic[self.coredb_py[2][topic_numbers][index][1]] = \
                                [self.coredb_py[2][topic_numbers][index][0],
                                 self.coredb_py[2][topic_numbers][index][2]]

                        # Store the keys and values from the DB to the cache dictionary.
                        self.topics_dic[new_button_object] = indices_dic

                        # Place the button inside the slider.
                        self.topics_slider_box.add_widget(new_button_object)

                # Set the height of the Topics menu based on heights and box padding.
                self.topics_slider_box.height = (topics_count * 48) + topics_count + 1

                # Topics dictionary should not be loaded again.
                self.must_build_topics = False

                # Database cannot be updated any more. To update user must restart.
                self.is_update_db.disabled = True

                # This will build the live Search dictionary.
                self.search_dic = {}
                for first_depth_key in self.topics_dic:
                    self.search_dic[first_depth_key.text] = []
                    for second_depth_key in self.topics_dic[first_depth_key]:
                        self.search_dic[first_depth_key.text].append(second_depth_key)

                # After cache data are ready, switch screen.
                self.is_manager.current = 'IndexSelectionScreen'

            # If there is no core DB available it prompts for indices update.
            except IOError:
                self.topics_dic = {}
                self.is_manager.current = 'Home'
                Popup(title='Warning:', content=Label(
                    text='No Indicator available.\nUpdate the database first.',
                    font_size=15,
                    halign="center",
                    italic=True
                ), size_hint=(None, None), size=(350, 180)).open()

            # Something really unexpected just happened.
            except Exception as e:
                print "def build_indices(self):", type(e), e.__doc__, e.message

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
                    topic=args[0].text,
                    on_release=self.on_index_selection)

                # Place the button in the stacklayout.
                self.indices_slider_stack.add_widget(btn)

                # Add the button's ID and object button itself in the global "shown_ind_btns" dict.
                IndexSelection.shown_ind_btns[index_btn_id] = btn

            # Set proper btn backgrounds based on my_indicators.
            self.btn_index_background()

        # Button is not pressed, which means it self toggled.
        else:
            self.clear_indices_stack()


class IndexCreation(MouseScreen):

    # Link to IndexSelection.
    ic_index_selection = ObjectProperty()

    # Link to Thematic Button from MainWindow.
    ic_thematic_btn = ObjectProperty()

    # Link to Thematic Map Designer.
    ic_th_designer = ObjectProperty()

    # List to show which indicator review is currently loaded.
    sorted_indicators = ListProperty()

    dropdown_id = ObjectProperty()
    dropdown_i = ObjectProperty()
    dropdown_r = ObjectProperty()
    dropdown_y = ObjectProperty()

    all_indicators_data = DictProperty({})
    country_list = ListProperty()
    country_dict = DictProperty({})
    rev_country_dict = DictProperty({})
    drawing_data = BooleanProperty(False)
    loading_percentage = NumericProperty(0)
    formula_items = DictProperty({"last_item": None, "p_group": []})

    cim = DictProperty({})

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexCreation, self).__init__(**kwargs)

        self.id_conn = {}
        self.rev_id_conn = {}
        self.year_row = []
        self.data_view_now = []
        self.data_queue = None
        self.ascending_order_buttons = []
        self.descending_order_buttons = []
        self.must_draw_data = True
        self.loaded_regions = {}
        self.loaded_years = []
        self.iry_iteration = {"i": [], "r": [], "y": []}

        # todo
        self.iry_iteration["y"] = ['Year', '1960', '1961', '1962', '1963', '1964', '1965', '1966', '1967', '1968', '1969', '1970', '1971', '1972', '1973', '1974', '1975', '1976', '1977', '1978', '1979', '1980', '1981', '1982', '1983', '1984', '1985', '1986', '1987', '1988', '1989', '1990', '1991', '1992', '1993', '1994', '1995', '1996', '1997', '1998', '1999', '2000', '2001', '2002', '2003', '2004', '2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014']
        self.cim = {'Canada': ['-', 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0, 9984670.0], 'Turkmenistan': ['-', 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0, 488100.0], 'Ethiopia': ['-', 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1221900.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0, 1104300.0], 'OECD members': ['-', 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962735.0, 35962755.0, 35962765.0, 35962785.0, 35962795.0, 35962795.0, 35962795.0, 35962795.0, 35997865.0, 35998245.0, 35998615.0, 35998685.0, 35998725.0, 35998775.0, 35999105.0, 35999135.0, 36198751.0, 36198972.0, 36199339.0, 36199316.0, 36196595.0, 36196595.0, 36196595.0], 'Swaziland': ['-', 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0, 17360.0], 'Cameroon': ['-', 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0, 475440.0], 'Burkina Faso': ['-', 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0, 274220.0], 'Channel Islands': ['-', 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 194.0, 190.0, 190.0, 190.0, 190.0, 190.0], 'Bosnia and Herzegovina': ['-', 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0, 51210.0], 'Russian Federation': ['-', 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0, 17098240.0], 'St. Lucia': ['-', 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0, 620.0], 'North Africa': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Dominica': ['-', 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0], 'Liberia': ['-', 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0, 111370.0], 'Maldives': ['-', 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0, 300.0], 'East Asia & Pacific (all income levels)': ['-', 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24820770.0, 24820770.0, 24822810.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24822890.0, 24821550.0, 24821560.0, 24821560.0, 24822230.0, 24824060.0, 24824090.0, 24824110.0, 24824110.0, 24824110.0, 24824110.0, 24824110.0, 24824110.0, 24824110.0, 24822240.0, 24822610.2, 24822725.2, 24822766.7, 24822803.5, 24824730.8, 24824776.0, 24824827.0, 24824791.0, 24824868.5, 24824909.7, 24824910.9, 24825037.9, 24825037.9, 24825037.9], 'Lithuania': ['-', 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0, 65300.0], 'Tanzania': ['-', 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0, 947300.0], 'Seychelles': ['-', 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0], 'Monaco': ['-', 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0], 'Madagascar': ['-', 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587040.0, 587295.0, 587295.0, 587295.0, 587295.0], 'Yemen, Rep.': ['-', 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0, 527970.0], 'Latin America and the Caribbean (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Upper middle income': ['-', 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650020.0, 41650660.0, 41650660.0, 41650660.0, 41650660.0, 41650650.0, 41650640.0, 41650640.0, 41623450.0, 41623450.0, 41623440.0, 41623434.2, 41623433.2, 41623432.7, 41623442.5, 41623441.8, 41623441.4, 41623440.8, 41623440.8, 41620901.0, 41620893.0, 41620893.0, 41620891.0, 41620891.0, 41620891.0], 'Tajikistan': ['-', 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0, 142550.0], 'Turkey': ['-', 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0, 783560.0], 'Afghanistan': ['-', 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0, 652860.0], 'Korea, Rep.': ['-', 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99260.0, 99540.0, 99590.0, 99600.0, 99620.0, 99650.0, 99680.0, 99720.0, 99830.0, 99900.0, 100030.0, 100030.0, 100150.0, 100150.0, 100150.0], 'France': ['-', 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549086.0, 549087.0, 549087.0, 549087.0, 549087.0, 549091.0, 549091.0, 549091.0], 'Vanuatu': ['-', 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0, 12190.0], 'South Asia (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Norway': ['-', 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0, 385178.0], 'Malawi': ['-', 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0, 118480.0], 'West Bank and Gaza': ['-', 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0, 6020.0], 'Montenegro': ['-', 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0, 13810.0], 'Middle East (developing only)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Taiwan, China': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Antigua and Barbuda': ['-', 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0, 440.0], 'Dominican Republic': ['-', 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0, 48670.0], 'Ghana': ['-', 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0, 238540.0], 'Indonesia': ['-', 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0, 1910930.0], 'Latin America & Caribbean (developing only)': ['-', 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15796480.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769290.0, 15769282.0, 15769282.0, 15769280.0, 15769280.0, 15769280.0], 'Libya': ['-', 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0, 1759540.0], 'Finland': ['-', 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338150.0, 338440.0, 338420.0, 338420.0, 338420.0, 338420.0, 338420.0, 338420.0, 338420.0, 338420.0], 'Central African Republic': ['-', 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0, 622980.0], 'Europe & Central Asia (all income levels)': ['-', 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360847.0, 28360937.0, 28360947.0, 28360977.0, 28361057.0, 28429797.0, 28429727.0, 28429727.0, 28461857.0, 28461877.0, 28462187.0, 28462237.0, 28462317.0, 28462337.0, 28462627.0, 28462607.0, 28462623.0, 28462767.0, 28462947.0, 28462889.0, 28460043.0, 28460043.0, 28460043.0], 'Liechtenstein': ['-', 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0, 160.0], 'Micronesia, Fed. Sts.': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0, 700.0], 'Korea, Dem. Rep.': ['-', 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0, 120540.0], 'North America': ['-', 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19613810.0, 19616750.0, 19616750.0, 19616750.0, 19616750.0, 19616750.0, 19616750.0, 19616750.0, 19616750.0, 19816230.0, 19816230.0, 19816230.0, 19816230.0, 19816230.0, 19816230.0, 19816230.0], 'Portugal': ['-', 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92120.0, 92090.0, 92090.0, 92090.0, 92090.0, 92210.0, 92210.0, 92210.0, 92210.0, 92210.0, 92210.0], 'St. Vincent and the Grenadines': ['-', 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0, 390.0], 'Fiji': ['-', 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0, 18270.0], 'Middle income': ['-', 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62806167.0, 62806167.0, 62808207.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62808287.0, 62806947.0, 62806957.0, 62806957.0, 62807627.0, 62808997.0, 62809027.0, 62809117.0, 62802194.0, 62802194.0, 62802184.0, 62802174.0, 62774984.0, 62774984.0, 62773104.0, 62773108.2, 62773157.2, 62773166.7, 62771507.5, 62773404.8, 62773404.4, 62773403.8, 62773242.8, 62770702.0, 62770600.0, 62144141.5, 62144139.5, 62144139.5, 62144139.5], 'Kyrgyz Republic': ['-', 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199950.0, 199949.0, 199949.0, 199949.0, 199949.0, 199949.0, 199949.0], 'United States': ['-', 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9629090.0, 9632030.0, 9632030.0, 9632030.0, 9632030.0, 9632030.0, 9632030.0, 9632030.0, 9632030.0, 9831510.0, 9831510.0, 9831510.0, 9831510.0, 9831510.0, 9831510.0, 9831510.0], 'Middle East & North Africa (all income levels)': ['-', 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373260.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373280.0, 11373290.0, 11373300.0, 11373310.0, 11373310.0, 11373320.0, 11373330.0, 11370790.0, 11370790.0, 11370790.0, 11370790.0, 11370790.0, 11370790.0], 'Kuwait': ['-', 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0, 17820.0], 'Panama': ['-', 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0, 75420.0], 'Costa Rica': ['-', 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0, 51100.0], 'Luxembourg': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0, 2590.0], 'Andorra': ['-', 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0, 470.0], 'Ireland': ['-', 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0, 70280.0], 'Italy': ['-', 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0, 301340.0], 'Nigeria': ['-', 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0, 923770.0], 'Ecuador': ['-', 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 283560.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0, 256370.0], 'Australia': ['-', 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0, 7741220.0], 'El Salvador': ['-', 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0, 21040.0], 'Tuvalu': ['-', 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0], 'Czech Republic': ['-', 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0, 78870.0], 'Thailand': ['-', 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0, 513120.0], 'Belize': ['-', 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0, 22970.0], 'Sierra Leone': ['-', 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0, 72300.0], 'Georgia': ['-', 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0, 69700.0], 'East Asia & Pacific (developing only)': ['-', 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16268160.0, 16268160.0, 16270200.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16270280.0, 16268940.0, 16268950.0, 16268950.0, 16269620.0, 16270990.0, 16271020.0, 16271040.0, 16271040.0, 16271030.0, 16271020.0, 16271020.0, 16271020.0, 16271020.0, 16269140.0, 16269144.2, 16269193.2, 16269202.7, 16269206.5, 16271103.8, 16271103.4, 16271102.8, 16270941.8, 16270942.0, 16270848.0, 16270842.0, 16270842.0, 16270842.0, 16270842.0], 'Denmark': ['-', 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0, 43090.0], 'Philippines': ['-', 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0, 300000.0], 'Moldova': ['-', 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33760.0, 33840.0, 33840.0, 33850.0, 33850.0, 33840.0, 33840.0, 33840.0, 33840.0, 33840.0, 33840.0, 33840.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0, 33850.0], 'Morocco': ['-', 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0, 446550.0], 'Chad': ['-', 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0, 1284000.0], 'Estonia': ['-', 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0, 45230.0], 'Kosovo': ['-', 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0, 10887.0], 'Lebanon': ['-', 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0, 10450.0], 'Uzbekistan': ['-', 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0, 447400.0], 'Colombia': ['-', 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141750.0, 1141748.0, 1141748.0, 1141748.0], 'Cyprus': ['-', 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0, 9250.0], 'Barbados': ['-', 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0, 430.0], 'Qatar': ['-', 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0, 11610.0], 'Palau': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0], 'Suriname': ['-', 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0, 163820.0], 'Sudan': ['-', 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 2505810.0, 1879357.5, 1879357.5, 1879357.5, 1879357.5], 'Latin America and the Caribbean': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Nepal': ['-', 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0, 147180.0], 'Netherlands': ['-', 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41530.0, 41540.0, 41540.0, 41540.0, 41540.0, 41540.0, 41540.0, 41500.0, 41500.0, 41500.0, 41500.0], 'Andean Region': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Middle East & North Africa (developing only)': ['-', 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8777960.0, 8775420.0, 8775420.0, 8775420.0, 8775420.0, 8775420.0, 8775420.0], 'Israel': ['-', 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0, 22070.0], 'Malaysia': ['-', 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0, 330800.0], 'Senegal': ['-', 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0, 196710.0], 'Papua New Guinea': ['-', 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0, 462840.0], 'Zimbabwe': ['-', 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0, 390760.0], 'Jordan': ['-', 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 88780.0, 89320.0, 89320.0, 89320.0, 89320.0, 89320.0, 89320.0], 'Mauritania': ['-', 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0, 1030700.0], 'Trinidad and Tobago': ['-', 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0, 5130.0], 'Not classified': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Latvia': ['-', 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64559.0, 64560.0, 64510.0, 64480.0, 64480.0, 64480.0, 64480.0], 'Hungary': ['-', 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0, 93030.0], 'Mexico': ['-', 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0, 1964380.0], 'Serbia': ['-', 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0, 88360.0], 'United Kingdom': ['-', 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0, 243610.0], 'High income: nonOECD': ['-', 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206897.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24206807.4, 24207267.4, 24207287.4, 24207287.4, 24207287.4, 24207297.4, 24207377.4, 24276127.4, 24276057.4, 24276057.4, 24276067.4, 24276073.4, 24276079.4, 24276101.4, 24276164.4, 24276174.4, 24276180.0, 24276191.6, 24276206.6, 24276207.9, 24276156.1, 24276128.3, 24276130.3, 24276130.3, 24276130.3], 'Greece': ['-', 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0, 131960.0], 'Paraguay': ['-', 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406750.0, 406752.0, 406752.0, 406752.0, 406752.0, 406752.0], 'Botswana': ['-', 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0, 581730.0], 'Heavily indebted poor countries (HIPC)': ['-', 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20510951.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 20393351.0, 19767153.5, 19767153.5, 19767153.5, 19767153.5], 'Sao Tome and Principe': ['-', 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0, 960.0], 'Lao PDR': ['-', 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0, 236800.0], 'Arab World': ['-', 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781751.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781771.0, 13781781.0, 13781791.0, 13781801.0, 13781801.0, 13781811.0, 13781821.0, 13779281.0, 13779281.0, 13152828.5, 13152828.5, 13152828.5, 13152828.5], 'Latin America & Caribbean (all income levels)': ['-', 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452622.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20452532.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425342.4, 20425334.4, 20425334.4, 20425332.4, 20425332.4, 20425332.4], 'Cambodia': ['-', 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0, 181040.0], 'Switzerland': ['-', 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0, 41285.0], 'Slovak Republic': ['-', 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49030.0, 49035.0, 49040.0, 49037.0, 49036.0, 49036.0, 49036.0, 49036.0], 'Aruba': ['-', 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0], 'South Asia': ['-', 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5144770.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5137847.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0, 5136164.0], 'Argentina': ['-', 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0, 2780400.0], 'Bolivia': ['-', 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0, 1098580.0], 'Bahamas, The': ['-', 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0, 13880.0], 'Bahrain': ['-', 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 690.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 710.0, 720.0, 730.0, 740.0, 740.0, 750.0, 760.0, 760.0, 760.0, 760.0, 760.0, 760.0, 760.0], 'Saudi Arabia': ['-', 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0, 2149690.0], 'Sub-Saharan Africa (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'American Samoa': ['-', 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 200.0], 'Slovenia': ['-', 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0, 20270.0], 'Guatemala': ['-', 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0, 108890.0], 'Guinea': ['-', 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0, 245860.0], 'World': ['-', 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134158810.4, 134156690.4, 134156690.4, 134158730.4, 134158720.4, 134158720.4, 134158720.4, 134158720.4, 134158720.4, 134158720.4, 134158720.4, 134157380.4, 134157390.4, 134157390.4, 134158060.4, 134159890.4, 134159940.4, 134042450.4, 134035537.4, 134035567.4, 134035647.4, 134104387.4, 134077127.4, 134077127.4, 134110327.4, 134110717.6, 134111142.6, 134111244.1, 134109687.9, 134111645.2, 134111980.4, 134112021.4, 134311491.4, 134309172.9, 134309386.1, 134327461.8, 134324740.8, 134324740.8, 134324740.8], 'Congo, Rep.': ['-', 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0, 342000.0], 'Spain': ['-', 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505990.0, 505000.0, 505020.0, 505320.0, 505370.0, 505370.0, 505370.0, 505370.0, 505370.0, 505370.0, 505370.0, 505600.0, 505600.0, 505600.0, 505600.0, 505600.0], 'Pakistan': ['-', 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0, 796100.0], 'Southern Cone': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Oman': ['-', 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0, 309500.0], 'Cabo Verde': ['-', 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0, 4030.0], 'Albania': ['-', 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0, 28750.0], 'Gabon': ['-', 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0, 267670.0], 'New Zealand': ['-', 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0, 267710.0], 'European Union': ['-', 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352765.0, 4352785.0, 4352795.0, 4352815.0, 4352895.0, 4352895.0, 4352825.0, 4352825.0, 4384955.0, 4384975.0, 4385285.0, 4385335.0, 4385405.0, 4385425.0, 4385715.0, 4385695.0, 4385711.0, 4385856.0, 4386040.0, 4385982.0, 4383136.0, 4383136.0, 4383136.0], 'Jamaica': ['-', 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0, 10990.0], 'Greenland': ['-', 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 341700.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0, 410450.0], 'Samoa': ['-', 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0, 2840.0], 'United Arab Emirates': ['-', 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0, 83600.0], 'Guam': ['-', 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0, 540.0], 'India': ['-', 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0, 3287260.0], 'Azerbaijan': ['-', 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0, 86600.0], 'Lesotho': ['-', 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0, 30360.0], 'Kenya': ['-', 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0, 580370.0], 'Pacific island small states': ['-', 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 63790.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0, 65130.0], 'Venezuela, RB': ['-', 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0, 912050.0], 'Northern Mariana Islands': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0, 460.0], 'Eritrea': ['-', 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0, 117600.0], 'Solomon Islands': ['-', 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0, 28900.0], 'San Marino': ['-', 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0], 'Mongolia': ['-', 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0, 1564120.0], 'Syrian Arab Republic': ['-', 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0, 185180.0], 'Rwanda': ['-', 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0, 26340.0], 'Somalia': ['-', 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0, 637660.0], 'Peru': ['-', 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0, 1285220.0], "Cote d'Ivoire": ['-', 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0, 322460.0], 'Europe & Central Asia (developing only)': ['-', 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385527.0, 6385597.0, 6385597.0, 6385607.0, 6385607.0, 6385597.0, 6385597.0, 6385597.0, 6385597.0, 6385597.0, 6385597.0, 6385597.0, 6385617.0, 6385617.0, 6385617.0, 6385617.0, 6385617.0, 6385616.0, 6385616.0, 6385616.0, 6385616.0, 6385616.0, 6385616.0], 'Benin': ['-', 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0, 114760.0], 'Other small states': ['-', 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1905421.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1898498.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0, 1896815.0], 'Cuba': ['-', 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109890.0, 109880.0, 109880.0, 109880.0, 109880.0, 109880.0], 'Low & middle income': ['-', 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76734998.0, 76734998.0, 76737038.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76737118.0, 76735778.0, 76735788.0, 76735788.0, 76736458.0, 76737828.0, 76737858.0, 76620348.0, 76613425.0, 76613425.0, 76613415.0, 76613405.0, 76586215.0, 76586215.0, 76584335.0, 76584339.2, 76584388.2, 76584397.7, 76582738.5, 76584635.8, 76584635.4, 76584634.8, 76584473.8, 76581933.0, 76581831.0, 76599957.5, 76599955.5, 76599955.5, 76599955.5], 'Togo': ['-', 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0, 56790.0], 'China': ['-', 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562950.0, 9562940.0, 9562930.0, 9562930.0, 9562930.0, 9562930.0, 9562920.0, 9562914.2, 9562913.2, 9562912.7, 9562912.5, 9562911.8, 9562911.4, 9562910.8, 9562910.8, 9562911.0, 9562911.0, 9562911.0, 9562911.0, 9562911.0, 9562911.0], 'Armenia': ['-', 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0, 29740.0], 'Germany': ['-', 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356970.0, 356990.0, 357000.0, 357020.0, 357030.0, 357030.0, 357030.0, 357030.0, 357030.0, 357030.0, 357040.0, 357040.0, 357050.0, 357090.0, 357100.0, 357100.0, 357110.0, 357120.0, 357127.0, 357140.0, 357170.0, 357170.0, 357170.0], 'Ukraine': ['-', 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603560.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0, 603550.0], 'Tonga': ['-', 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0, 750.0], 'Cayman Islands': ['-', 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0, 264.0], 'Mauritius': ['-', 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0, 2040.0], 'Sweden': ['-', 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 450300.0, 447420.0, 447420.0, 447420.0], 'Vietnam': ['-', 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 329570.0, 329570.0, 331610.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 331690.0, 330350.0, 330360.0, 330360.0, 331030.0, 331060.0, 331090.0, 331110.0, 331110.0, 331110.0, 331110.0, 331110.0, 331110.0, 331110.0, 329240.0, 329250.0, 329300.0, 329310.0, 329314.0, 331212.0, 331212.0, 331212.0, 331051.0, 331051.0, 330957.0, 330951.0, 330951.0, 330951.0, 330951.0], 'Mali': ['-', 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0, 1240190.0], 'Sub-Saharan Africa excluding South Africa and Nigeria': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Bulgaria': ['-', 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 110990.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0, 111000.0], 'Romania': ['-', 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0, 238390.0], 'Angola': ['-', 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0, 1246700.0], 'Central Europe and the Baltics': ['-', 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134969.0, 1134969.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134899.0, 1134959.0, 1134959.0, 1134949.0, 1134949.0, 1134954.0, 1134960.0, 1134907.0, 1134876.0, 1134876.0, 1134876.0, 1134876.0], 'Egypt, Arab Rep.': ['-', 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0, 1001450.0], 'South Africa': ['-', 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0, 1219090.0], 'Caribbean small states': ['-', 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 435080.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0, 434990.0], 'Brunei Darussalam': ['-', 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0, 5770.0], 'Austria': ['-', 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83870.0, 83879.0, 83879.0, 83879.0, 83879.0, 83879.0, 83879.0], 'High income: OECD': ['-', 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214795.0, 33214815.0, 33214825.0, 33214845.0, 33214855.0, 33214855.0, 33214855.0, 33214855.0, 33249925.0, 33250305.0, 33250675.0, 33250745.0, 33250785.0, 33250835.0, 33251165.0, 33251195.0, 33450811.0, 33451032.0, 33451399.0, 33451376.0, 33448655.0, 33448655.0, 33448655.0], 'Mozambique': ['-', 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0, 799380.0], 'Uganda': ['-', 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0, 241550.0], 'Japan': ['-', 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377800.0, 377880.0, 377890.0, 377900.0, 377910.0, 377910.0, 377920.0, 377930.0, 377940.0, 377947.0, 377950.0, 377955.0, 377960.0, 377960.0, 377960.0], 'Niger': ['-', 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0, 1267000.0], 'Brazil': ['-', 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0, 8515770.0], 'Virgin Islands (U.S.)': ['-', 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0], 'Euro area': ['-', 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725255.0, 2725275.0, 2725285.0, 2725305.0, 2725315.0, 2725315.0, 2725315.0, 2725315.0, 2757445.0, 2757465.0, 2757775.0, 2757825.0, 2757835.0, 2757855.0, 2758155.0, 2758135.0, 2758151.0, 2758296.0, 2758480.0, 2758422.0, 2758456.0, 2758456.0, 2758456.0], 'Faeroe Islands': ['-', 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0, 1396.0], 'Lower middle income': ['-', 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21156147.0, 21156147.0, 21158187.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21158267.0, 21156927.0, 21156937.0, 21156937.0, 21157607.0, 21158337.0, 21158367.0, 21158457.0, 21151534.0, 21151544.0, 21151544.0, 21151534.0, 21151534.0, 21151534.0, 21149664.0, 21149674.0, 21149724.0, 21149734.0, 21148065.0, 21149963.0, 21149963.0, 21149963.0, 21149802.0, 21149801.0, 21149707.0, 20523248.5, 20523248.5, 20523248.5, 20523248.5], 'Bangladesh': ['-', 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0, 148460.0], 'Belarus': ['-', 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0, 207600.0], 'Algeria': ['-', 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0, 2381740.0], 'East Asia and the Pacific (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'St. Kitts and Nevis': ['-', 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0, 260.0], 'Marshall Islands': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0, 180.0], 'Chile': ['-', 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0, 756096.0], 'Puerto Rico': ['-', 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0, 8870.0], 'Belgium': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0, 30530.0], 'Europe and Central Asia (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Haiti': ['-', 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0, 27750.0], 'Iraq': ['-', 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 438320.0, 435240.0, 435240.0, 435240.0, 435240.0, 435240.0, 435240.0], 'Fragile and conflict affected situations': ['-', 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14762328.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14763208.0, 14760128.0, 14760128.0, 14778260.5, 14778260.5, 14778260.5, 14778260.5], 'Namibia': ['-', 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0, 824290.0], 'French Polynesia': ['-', 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0, 4000.0], 'Guinea-Bissau': ['-', 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0, 36130.0], 'Kiribati': ['-', 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0, 810.0], 'Macedonia, FYR': ['-', 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0, 25710.0], 'Grenada': ['-', 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0, 340.0], 'Middle East and North Africa (IFC classification)': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Isle of Man': ['-', 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0, 570.0], 'Uruguay': ['-', 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0, 176220.0], 'Africa': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Equatorial Guinea': ['-', 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0, 28050.0], 'Hong Kong SAR, China': ['-', 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1070.0, 1080.0, 1090.0, 1090.0, 1090.0, 1090.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0, 1100.0], 'Central America': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Djibouti': ['-', 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0, 23200.0], 'Bermuda': ['-', 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], 'Timor-Leste': ['-', 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0, 14870.0], 'Low income': ['-', 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13928831.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 13811231.0, 14455816.0, 14455816.0, 14455816.0, 14455816.0], 'High income': ['-', 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421692.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57421602.4, 57422062.4, 57422082.4, 57422102.4, 57422112.4, 57422142.4, 57422232.4, 57490982.4, 57490912.4, 57490912.4, 57525992.4, 57526378.4, 57526754.4, 57526846.4, 57526949.4, 57527009.4, 57527345.0, 57527386.6, 57727017.6, 57727239.9, 57727555.1, 57727504.3, 57724785.3, 57724785.3, 57724785.3], 'Burundi': ['-', 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0, 27830.0], 'Least developed countries: UN classification': ['-', 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20926251.0, 20808651.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20801728.0, 20800045.0, 20800045.0, 20800045.0, 20800045.0, 20800045.0, 20800045.0, 20800045.0, 20818177.5, 20818177.5, 20818177.5, 20818177.5], 'Turks and Caicos Islands': ['-', 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0, 950.0], 'Congo, Dem. Rep.': ['-', 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0, 2344860.0], 'Curacao': ['-', 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0, 444.0], 'Bhutan': ['-', 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 47000.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 40077.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0, 38394.0], 'Sub-Saharan Africa (developing only)': ['-', 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24362101.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24244501.0, 24262633.5, 24262633.5, 24262633.5, 24262633.5], 'Malta': ['-', 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0, 320.0], 'Macao SAR, China': ['-', 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 26.0, 27.0, 27.0, 28.0, 28.0, 28.6, 29.2, 29.2, 29.5, 29.7, 29.9, 29.9, 29.9, 29.9], 'St. Martin (French part)': ['-', 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4, 54.4], 'Iran, Islamic Rep.': ['-', 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0, 1745150.0], 'Iceland': ['-', 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0, 103000.0], 'Zambia': ['-', 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0, 752610.0], 'Sub-Saharan Africa (all income levels)': ['-', 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24390611.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24273011.0, 24291143.5, 24291143.5, 24291143.5, 24291143.5], 'Sub-Saharan Africa excluding South Africa': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'], 'Kazakhstan': ['-', 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0, 2724900.0], 'Poland': ['-', 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312690.0, 312680.0, 312680.0, 312680.0, 312680.0, 312680.0, 312680.0, 312680.0, 312680.0, 312680.0], 'Small states': ['-', 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404291.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2404201.0, 2405541.0, 2405541.0, 2405541.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2398618.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0, 2396935.0], 'New Caledonia': ['-', 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0, 18580.0], 'South Sudan': ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', 644330.0, 644330.0, 644330.0, 644330.0], 'Guyana': ['-', 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0, 214970.0], 'Honduras': ['-', 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0, 112490.0], 'Myanmar': ['-', 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0, 676590.0], 'Tunisia': ['-', 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0, 163610.0], 'Nicaragua': ['-', 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0, 130370.0], 'Singapore': ['-', 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 680.0, 685.0, 697.0, 699.0, 699.0, 704.0, 705.0, 710.0, 710.0, 712.0, 714.0, 716.0, 716.0, 716.0], 'Gambia, The': ['-', 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0, 11300.0], 'Sint Maarten (Dutch part)': ['-', 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0, 34.0], 'Sri Lanka': ['-', 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0, 65610.0], 'Croatia': ['-', 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56610.0, 56610.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56540.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0, 56590.0], 'Comoros': ['-', 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0, 1861.0]}

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    @staticmethod
    def threadonator(*args):
        threading.Thread(target=args[0], args=(args,)).start()

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

    @mainthread
    def popuper(self, message, title):
        Popup(title=title, content=Label(
            text=message,
            text_size=(340, 180),
            valign="middle",
            font_size=15,
            halign="center",
            italic=True
        ), size_hint=(None, None), size=(400, 200)).open()

    # Function that will run every time mouse is moved.
    def on_mouse_pos(self, *args):
        if self.toolbox_screenmanager.current == "view_indicators_screen":
            for button in self.ascending_order_buttons:
                if button.collide_point(*button.to_widget(*args[1])):
                    button.background_normal = './Sources/ascending_down.png'
                else:
                    button.background_normal = './Sources/ascending_normal.png'

            for button in self.descending_order_buttons:
                if button.collide_point(*button.to_widget(*args[1])):
                    button.background_normal = './Sources/descending_down.png'
                else:
                    button.background_normal = './Sources/descending_normal.png'

        if self.toolbox_screenmanager.current == "series_selection_screen"\
                and self.country_selection_sm.current in self.loaded_regions:
            for button in self.loaded_regions[self.country_selection_sm.current]:
                if button.collide_point(*button.to_widget(*args[1])):
                    button.background_normal = button.background_down
                else:
                    button.background_normal = button.normal

            if len(self.loaded_years) > 1:
                for button in self.loaded_years[-2:]:
                    if button.collide_point(*button.to_widget(*args[1])):
                        button.background_normal = button.background_down
                    else:
                        button.background_normal = button.normal

        if self.toolbox_screenmanager.current == "index_algebra_screen":
            for button in self.calculator.children:
                if button.collide_point(*button.to_widget(*args[1])):
                    button.background_normal = button.background_down
                else:
                    button.background_normal = button.normal

            if self.ind_calc_btn.collide_point(*self.ind_calc_btn.to_widget(*args[1])):
                self.ind_calc_btn.background_normal = self.ind_calc_btn.background_down
            else:
                self.ind_calc_btn.background_normal = self.ind_calc_btn.normal

    @mainthread
    def model_toolbox_activator(self, state):
        if state:
            self.model_toolbox.opacity = 1
        else:
            self.model_toolbox.opacity = 0

    def toolbox_switcher(self, button):
        if not self.drawing_data:
            self.toolbox_screenmanager.current = button.goto
            self.btn_view_indicators.disabled = False
            self.btn_series_selection.disabled = False
            self.btn_index_algebra.disabled = False
            button.disabled = True

    def dl_manager(self):
        # If togglebutton was pressed and table is currently being loaded, do nothing..
        if not self.drawing_data:

            # If I have no indicator in my list do nothing but alert.
            if not self.ic_index_selection.selected_indices["my_indicators"]:
                self.btn_get_indicators.state = "normal"
                self.popuper(
                    '"My Indicators" list should not be empty.\nGo to Indicator Selection.',
                    'Warning:')

            else:
                # Clear model's indicator list.
                self.indicator_list.clear_widgets()

                # Clear current formula in case there is one.
                self.my_formula.clear_widgets()

                self.btn_view_indicators.disabled = False
                self.btn_series_selection.disabled = False
                self.btn_index_algebra.disabled = False

                self.toolbox_screenmanager.current = "intro"
                self.model_toolbox_activator(False)

                self.btn_get_indicators.disabled = True
                self.downloading_state_icon.source = './Sources/loader.gif'

                # Next time btn_view_indicators will be pressed, It will recreate data table.
                self.must_draw_data = True

                self.threadonator(self.get_indicators)

        # ..but re-toggle the button.
        else:
            self.btn_get_indicators.state = "normal"

    @mainthread
    def spawn_indicator_widget(self, *args):
        # Creation and placement of each widget part.
        rvw_widget_main_layout = Factory.RvwWidgetMainLayout()
        rvw_widget_head_layout = BoxLayout(orientation="horizontal",
                                           size_hint=(None, None),
                                           size=(262, 70))
        rvw_widget_scroll = Factory.RvwWidgetScroll()
        rvw_widget_title = Factory.RvwWidgetTitle(text=str(args[0][6]))
        rvw_widget_short_id = Factory.RvwWidgetShortID(text=str(args[0][5]))
        rvw_widget_foot_layout = Factory.RvwWidgetFootLayout()
        rvw_widget_calc1 = Factory.RvwWidgetCalc(width=60)
        rvw_widget_calc1_data = Factory.RvwWidgetCalcData(size=(60, 31),
                                                          text=str(args[0][0]),
                                                          color=(0.9, 0.1, 0.1, 1))
        rvw_widget_calc1_desc = Factory.RvwWidgetCalcDesc(size=(60, 32), text="Regions\nW/O Data")
        rvw_widget_calc2 = Factory.RvwWidgetCalc(width=90)
        rvw_widget_calc2_sum1 = BoxLayout(size_hint=(None, None), size=(90, 15), spacing=5)
        rvw_widget_calc2_sum1_desc = Factory.RvwWidgetCalc2Desc(text="60-80:")
        rvw_widget_calc2_sum1_data = Factory.RvwWidgetCalc2Data(text=str(args[0][2]))
        rvw_widget_calc2_sum2 = BoxLayout(size_hint=(None, None), size=(90, 15), spacing=5)
        rvw_widget_calc2_sum2_desc = Factory.RvwWidgetCalc2Desc(text="80-00:")
        rvw_widget_calc2_sum2_data = Factory.RvwWidgetCalc2Data(text=str(args[0][3]))
        rvw_widget_calc2_sum3 = BoxLayout(size_hint=(None, None), size=(90, 15), spacing=5)
        rvw_widget_calc2_sum3_desc = Factory.RvwWidgetCalc2Desc(text="00+:")
        rvw_widget_calc2_sum3_data = Factory.RvwWidgetCalc2Data(text=str(args[0][4]))
        rvw_widget_calc2_desc = Factory.RvwWidgetCalcDesc(size=(90, 18), text="Total Records")
        rvw_widget_calc3 = Factory.RvwWidgetCalc(width=110)
        rvw_widget_calc3_data = Factory.RvwWidgetCalcData(size=(110, 31),
                                                          text=args[0][1],
                                                          color=(0, 0, 0, 1))
        rvw_widget_calc3_desc = Factory.RvwWidgetCalcDesc(size=(110, 32),
                                                          text="Diachronic\nUnweighted Mean")

        rvw_widget_scroll.add_widget(rvw_widget_title)

        rvw_widget_head_layout.add_widget(rvw_widget_scroll)
        rvw_widget_head_layout.add_widget(rvw_widget_short_id)

        rvw_widget_calc1.add_widget(rvw_widget_calc1_data)
        rvw_widget_calc1.add_widget(rvw_widget_calc1_desc)

        rvw_widget_calc2_sum1.add_widget(rvw_widget_calc2_sum1_desc)
        rvw_widget_calc2_sum1.add_widget(rvw_widget_calc2_sum1_data)

        rvw_widget_calc2_sum2.add_widget(rvw_widget_calc2_sum2_desc)
        rvw_widget_calc2_sum2.add_widget(rvw_widget_calc2_sum2_data)

        rvw_widget_calc2_sum3.add_widget(rvw_widget_calc2_sum3_desc)
        rvw_widget_calc2_sum3.add_widget(rvw_widget_calc2_sum3_data)

        rvw_widget_calc2.add_widget(rvw_widget_calc2_sum1)
        rvw_widget_calc2.add_widget(rvw_widget_calc2_sum2)
        rvw_widget_calc2.add_widget(rvw_widget_calc2_sum3)
        rvw_widget_calc2.add_widget(rvw_widget_calc2_desc)

        rvw_widget_calc3.add_widget(rvw_widget_calc3_data)
        rvw_widget_calc3.add_widget(rvw_widget_calc3_desc)

        rvw_widget_foot_layout.add_widget(rvw_widget_calc1)
        rvw_widget_foot_layout.add_widget(rvw_widget_calc2)
        rvw_widget_foot_layout.add_widget(rvw_widget_calc3)

        rvw_widget_main_layout.add_widget(rvw_widget_head_layout)
        rvw_widget_main_layout.add_widget(rvw_widget_foot_layout)

        # Finally, add new widget inside model's indicator list.
        self.indicator_list.add_widget(rvw_widget_main_layout)

    def get_indicators(self, *args):
        # Shortcut for "my_indicators".
        mi = dict(self.ic_index_selection.selected_indices["my_indicators"])

        # Reset indicator data from current database.
        self.all_indicators_data = {}

        # CleanUP country list and dict's.
        self.country_list = []
        self.country_dict = {}
        self.rev_country_dict = {}

        # Reset connection list.
        connections = []

        # Sort keys for the ID sequence.
        self.sorted_indicators = mi.keys()
        self.sorted_indicators.sort()

        # Number of my indicators.
        items = len(self.sorted_indicators)

        # Prepare dictionaries to link model's ID's to Indicator names and vice versa.
        self.id_conn = {}
        self.rev_id_conn = {}

        # Characters to use for ID creation
        abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        # This var will show ID creation sequence.
        items_created = 0

        # Create short ID's, store link to a dict and prepare each structure. (UPTO 26)
        for i in abc:

            short_id = "I"+i

            # Update ID link's in dictionaries.
            self.id_conn[self.sorted_indicators[items_created]] = short_id
            self.rev_id_conn[short_id] = self.sorted_indicators[items_created]

            # Prepare the basic structure for each indicator.
            self.all_indicators_data[short_id] = {}

            items_created += 1
            if items_created == items:
                break

        # Prepare new ID creation sequence.
        items_created = 0

        # Continue creating short ID's, store link to a dict and prepare each structure. (UPTO 676)
        if items-26 > 0:
            for i in abc:
                for j in abc:

                    short_id = "I"+i+j

                    # Update ID link dictionary.
                    self.id_conn[self.sorted_indicators[items_created+26]] = short_id

                    # Prepare the basic structure for each indicator.
                    self.all_indicators_data[short_id] = {}

                    items_created += 1
                    if items_created == items-26:
                        break
                if items_created == items-26:
                    break

        # Prepare Country Dict's and List and place the list inside all_indicators_data.
        for i in range(1, self.ic_index_selection.coredb_py[1][0]["countries_num"]+1):
            country = self.ic_index_selection.coredb_py[1][i][1]
            self.country_list.append(country)

            # Prepare Country dict.
            self.country_dict[country] = [self.ic_index_selection.coredb_py[1][i][0],
                                          self.ic_index_selection.coredb_py[1][i][2]]

            # Prepare reversed Country dict.
            self.rev_country_dict[self.ic_index_selection.coredb_py[1][i][0]] = country

            for key in self.all_indicators_data:
                self.all_indicators_data[key][country] = {}

        # Sort country list.
        self.country_list.sort()

        try:
            for indicator in self.sorted_indicators:

                short_id = self.id_conn[indicator]
                indicator_address = start_url+countries+indicators+mi[indicator]+"/"+end_url

                # Define World Bank connection (JSON data).
                ind_data_connection = urllib2.urlopen(indicator_address, timeout=120)

                # Add current connection to the list with all connections.
                connections.append(ind_data_connection)

                # Convert JSON data into temp python structure.
                ind_data_py = self.string_it(json.load(ind_data_connection))

                # This list will store all years with data for each short_id (model indicator).
                year_list = []

                # For each record in the json file..
                for record in range(len(ind_data_py[1])):
                    country = ind_data_py[1][record]["country"]["value"]
                    year = int(ind_data_py[1][record]["date"])
                    value = ind_data_py[1][record]["value"]

                    if value:
                        self.all_indicators_data[short_id][country][year] = value
                        year_list.append(year)

                # If year list is not an empty list..
                if year_list:
                    self.all_indicators_data["LastFirst_"+short_id] = [min(year_list),
                                                                       max(year_list)]

                # Begin statistic calculations.
                # Track number of countries with no data available for any year.
                empty_countries = 0

                country_averages = []

                plus1960 = 0
                plus1980 = 0
                plus2000 = 0

                for country in self.all_indicators_data[short_id]:
                    sum_value = 0
                    available_years = 0
                    for year, value in self.all_indicators_data[short_id][country].iteritems():
                        if value:
                            sum_value += float(value)
                            available_years += 1
                            if year < 1980:
                                plus1960 += 1
                            elif year < 2000:
                                plus1980 += 1
                            else:
                                plus2000 += 1

                    if available_years == 0:
                        empty_countries += 1
                    else:
                        country_averages.append(sum_value/available_years)

                # Format numbers to be more friendly.
                tup = str("%.5G" % (sum(country_averages)/len(country_averages))).partition('E')
                mean = (('[size=12]E'.join((tup[0], tup[-1]))+"[/size]")
                        .replace("[size=12]E[/size]", ""))\
                    .replace(".", ",")

                ind_review = [empty_countries,
                              mean,
                              plus1960,
                              plus1980,
                              plus2000,
                              short_id,
                              indicator]

                self.spawn_indicator_widget(ind_review)

            self.model_toolbox_activator(True)

        except Exception as e:
            self.popuper("Could not prepare "+indicator+"\nPlease try again.\n\n"+e.message,
                         'Warning:')

            # Flush sorted_indicators to alert that download did not end with success.
            self.sorted_indicators = []

        finally:
            try:
                # Close created connections to WorldBank.
                for conn in connections:
                    conn.close()

            # Something really unexpected just happened.
            except Exception as e:
                print "def get_indicators(self, *args):", type(e), e.__doc__, e.message

        # On every data reload, we also recalculate available years in series_selection_screen.
        self.generate_year_buttons()

        self.btn_get_indicators.disabled = False
        self.btn_get_indicators.state = "normal"

    def init_data_viewer(self, sh_id="IA", *args):
        # If args have passed, we are calling this from ID List and we should draw data again.
        if args:
            self.must_draw_data = True

        if self.must_draw_data:

            self.drawing_data = True
            self.must_draw_data = False

            self.all_indicators_data["table_desc"] = sh_id

            # Set year range.
            rng = range(int(self.all_indicators_data["LastFirst_"+sh_id][0]),
                        int(self.all_indicators_data["LastFirst_"+sh_id][1]+1))

            # Create first row list (ID & Years).
            self.year_row = ["top_left_cell"]
            for year in rng:
                self.year_row.append(year)

            # Clear data_view_now in case we have already created that.
            self.data_view_now = []

            # Build self.data_view_now
            for region in self.country_list:
                self.data_view_now.append([region])
                for year in rng:
                    if year in self.all_indicators_data[sh_id][region]:
                        self.data_view_now[-1].append(
                            float(self.all_indicators_data[sh_id][region][year]))
                    else:
                        self.data_view_now[-1].append("")

            self.screen_load_toolbox.add_widget(Factory.TempDataTable(cols=len(rng)+1))

            self.data_queue = list(self.data_view_now)

            # Schedule table building.
            Clock.schedule_interval(self.build_data_table, 0)

    def sort_data_manager(self, *args):
        # If table is currently being loaded, do nothing.
        if not self.drawing_data:
            # Set drawing data state.
            self.drawing_data = True

            # Check if button is in the descending list.
            rev = args[0] in self.descending_order_buttons

            # Check index of the button to know which column will sort.
            if rev:
                column = self.descending_order_buttons.index(args[0]) + 1
            else:
                column = self.ascending_order_buttons.index(args[0]) + 1

            temp_sorted = []

            for row in sorted(self.data_view_now, key=operator.itemgetter(column), reverse=rev):
                temp_sorted.append(row)

            self.data_view_now = temp_sorted
            self.data_queue = list(self.data_view_now)

            # Schedule table building.
            Clock.schedule_interval(self.build_data_table, 0)

    def build_data_table(self, dt):
        # As long as there are data in the queue..
        if self.data_queue:
            self.loading_percentage = int(100 - (len(self.data_queue)/263.) * 100)

            first_build = self.data_queue == self.data_view_now

            # Set chunks number for each schedule.
            chunks = 30
            queue = self.data_queue[:chunks]
            self.data_queue = self.data_queue[chunks:]

            # Check if first line needs to be added.
            if first_build:
                # Clear button lists because they may already contain items.
                self.ascending_order_buttons = []
                self.descending_order_buttons = []

                # Clear previous headers that would exist, if we are currently sorting.
                self.data_table_top.clear_widgets()

                for header in self.year_row:
                    # Check if this is the 0.0 cell to build the dropdown.
                    if header == "top_left_cell":
                        self.dropdown_id = DropDown(auto_width=False, width=200)

                        for index in self.sorted_indicators:
                            btn = Button(text=self.id_conn[index],
                                         size_hint_y=None,
                                         height=50,
                                         background_normal='./Sources/option_id_normal.png',
                                         background_down='./Sources/option_id_normal.png',
                                         on_press=self.dropdown_id.dismiss)
                            btn.bind(on_release=partial(self.init_data_viewer, btn.text))
                            self.dropdown_id.add_widget(btn)

                        mainbutton = Button(text=self.all_indicators_data["table_desc"],
                                            size_hint=(None, None),
                                            size=(200, 20),
                                            background_normal='./Sources/selected_id_normal.png',
                                            background_down='./Sources/selected_id_down.png')

                        mainbutton.bind(on_release=self.dropdown_id.open)
                        mainbutton.bind(on_release=lambda x: setattr(
                            x, "background_normal", './Sources/selected_id_down.png'))

                        self.data_table_top.add_widget(mainbutton)

                    else:
                        head_box = Factory.HeadBox(size_hint=(None, None), size=(100, 20))
                        left_title = Factory.YearHeader(text=str(header))
                        right_box = BoxLayout(orientation="vertical",
                                              spacing=4,
                                              size_hint=(None, None),
                                              size=(30, 20))
                        ascending_btn = Factory.OrderBtn(
                            background_normal='./Sources/ascending_normal.png',
                            background_down='./Sources/ascending_down.png',
                            on_release=self.sort_data_manager)
                        descending_btn = Factory.OrderBtn(
                            background_normal='./Sources/descending_normal.png',
                            background_down='./Sources/descending_down.png',
                            on_release=self.sort_data_manager)

                        # Place buttons in a list. Will use that for hover checks.
                        self.ascending_order_buttons.append(ascending_btn)
                        self.descending_order_buttons.append(descending_btn)

                        right_box.add_widget(ascending_btn)
                        right_box.add_widget(descending_btn)

                        head_box.add_widget(left_title)
                        head_box.add_widget(right_box)

                        self.data_table_top.add_widget(head_box)

            for country_row in queue:
                for i, cell in enumerate(country_row, start=1):
                    # Identify Region names.
                    if cell == country_row[0]:
                        self.screen_load_toolbox.children[0].add_widget(
                            Factory.DataViewTitle(text=str(cell)))

                    else:
                        if isinstance(cell, float):
                            # Format numbers to be more friendly.
                            tup = str("%.5G" % cell).partition('E')
                            val = (('[size=12] E'.join((tup[0], tup[-1]))+"[/size]")
                                   .replace("[size=12] E[/size]", ""))\
                                .replace(".", ",")

                        else:
                            val = cell

                        # Use different color styles for Odd/Even columns.
                        if i % 2:
                            self.screen_load_toolbox.children[0].add_widget(
                                Factory.DataViewEven(text=str(val)))
                        else:
                            self.screen_load_toolbox.children[0].add_widget(
                                Factory.DataViewOdd(text=str(val)))

        else:
            # End table drawing reschedules.
            Clock.unschedule(self.build_data_table)

            # Take a screen shot to use that inside the slider.
            self.screen_load_toolbox.children[0].export_to_png("./DB/table.png")

            # Reload img table source.
            try:
                self.data_table_img._coreimage.remove_from_cache()

            except AttributeError:
                pass

            finally:
                new_img = self.data_table_img.source
                self.data_table_img.source = ''
                self.data_table_img.source = new_img

            try:
                os.remove("./DB/table.png")
            except OSError:
                pass

            # If we have already added a temp table data widget, remove the older one.
            if len(self.screen_load_toolbox.children) > 1:
                self.screen_load_toolbox.remove_widget(self.screen_load_toolbox.children[1])

            # Schedule last step of data table creation (widget removal).
            Clock.schedule_interval(self.wdg_removal, 0)

    def wdg_removal(self, *args):
        if self.screen_load_toolbox.children[0].children:
            for wdg in self.screen_load_toolbox.children[0].children[:1000]:
                self.screen_load_toolbox.children[0].remove_widget(wdg)
        else:
            # Schedule memory cleanup.
            gc.collect()

            # Table created and loaded.
            self.drawing_data = False

            # Reset bar for next time.
            self.loading_percentage = 0

            # End reschedules.
            Clock.unschedule(self.wdg_removal)

    def init_country_viewer(self, *args):
        # Check if current screen has already been added in loaded_regions dict.
        if args[0] in self.loaded_regions:
            pass

        else:
            # Add current screen in loaded_regions dict and prepare new list to hold buttons.
            self.loaded_regions[args[0]] = []

            # Create and place a widget module for each Country.
            country_stack = Factory.CountryStack()

            country_slider = Factory.CountryScroll()
            country_slider.add_widget(country_stack)

            self.country_selection_sm.get_screen(args[0]).add_widget(country_slider)

            for key, val in self.country_dict.iteritems():
                if args[0] == val[1]:
                    country_name = Factory.CountryName(text=key)
                    country_id = Factory.CountryCode(text=val[0])

                    mid_frame = Factory.CountryMidFrame()
                    mid_frame.add_widget(country_name)
                    mid_frame.add_widget(country_id)

                    country_frame = Factory.CountryFrame()
                    country_frame.add_widget(Factory.CountryBtnImage())
                    country_frame.add_widget(mid_frame)
                    btn = Factory.CountrySelectToggle(text=val[0])
                    country_frame.add_widget(btn)
                    country_stack.add_widget(country_frame)

                    # Add current button in region buttons list.
                    self.loaded_regions[args[0]].append(btn)

            country_multi_select_frame = BoxLayout(size_hint=(None, None), size=(200, 50))
            country_select_none = SelectAll(
                size_hint=(None, None),
                size=(50, 50),
                normal='./Sources/no_country_checked_normal.png',
                background_normal='./Sources/no_country_checked_normal.png',
                background_down='./Sources/no_country_checked_down.png',
                region=args[0],
                on_release=self.all_selection_countries)

            country_multi_select = Factory.CountryMultiSelect()

            country_select_all = SelectAll(
                size_hint=(None, None),
                size=(50, 50),
                normal='./Sources/all_country_checked_normal.png',
                background_normal='./Sources/all_country_checked_normal.png',
                background_down='./Sources/all_country_checked_down.png',
                region=args[0],
                on_release=self.all_selection_countries)

            country_multi_select_frame.add_widget(country_select_none)
            country_multi_select_frame.add_widget(country_multi_select)
            country_multi_select_frame.add_widget(country_select_all)

            country_stack.add_widget(country_multi_select_frame)

            # Add select all/none buttons in region buttons list.
            self.loaded_regions[args[0]].append(country_select_none)
            self.loaded_regions[args[0]].append(country_select_all)

    def all_selection_countries(self, *args):
        # Manage country button state.
        if args[0].normal == "./Sources/all_country_checked_normal.png":
            for button in self.loaded_regions[args[0].region][:-2]:
                button.state = "down"
        else:
            for button in self.loaded_regions[args[0].region][:-2]:
                button.state = "normal"

    @mainthread
    # This will run each time series_selection_screen initiates for first time after data reload.
    def generate_year_buttons(self):
        # Clear all previously created year_buttons.
        self.years_stack.clear_widgets()

        self.loaded_years = []

        min_y, max_y = 1960, 2015
        d = [item for k, v in self.all_indicators_data.items() if 'LastFirst_' in k for item in v]

        # Check if there is at least one year with data.
        if d:
            first_y, last_y = min(*d), max(*d)
        # If not, we will make first and last year be out of range, so that all years will be grey.
        else:
            first_y, last_y = max_y+1, min_y-1

        # Will iter each year in database. In future min_y, max_y could change so we use min max.
        for y in range(min(min_y, first_y), max(max_y, last_y)):

            if y in range(first_y, last_y + 1):
                year_btn = Factory.YearSelector(
                    text=str(y),
                    background_normal='./Sources/btn_years_normal.png')
            else:
                year_btn = Factory.YearSelector(
                    text=str(y),
                    background_normal='./Sources/btn_empty_years_normal.png')

            self.years_stack.add_widget(year_btn)

            # Also add current button in year buttons list.
            self.loaded_years.append(year_btn)

        # Create and Add mass selections button.
        year_multi_select_frame = BoxLayout(size_hint=(None, None), size=(75, 25))
        year_select_none = SelectAll(size_hint=(None, None),
                                     size=(25, 25),
                                     normal='./Sources/deselect_all_years_normal.png',
                                     background_normal='./Sources/deselect_all_years_normal.png',
                                     background_down='./Sources/deselect_all_years_down.png',
                                     on_release=self.all_selection_years)

        btn_label = Factory.AllYearsLabel()

        year_select_all = SelectAll(size_hint=(None, None),
                                    size=(25, 25),
                                    normal='./Sources/select_all_years_normal.png',
                                    background_normal='./Sources/select_all_years_normal.png',
                                    background_down='./Sources/select_all_years_down.png',
                                    on_release=self.all_selection_years)

        year_multi_select_frame.add_widget(year_select_none)
        year_multi_select_frame.add_widget(btn_label)
        year_multi_select_frame.add_widget(year_select_all)

        self.years_stack.add_widget(year_multi_select_frame)

        # Add select all/none buttons in year buttons list.
        self.loaded_years.append(year_select_none)
        self.loaded_years.append(year_select_all)

    def all_selection_years(self, *args):
        # Manage year button state.
        if args[0].normal == './Sources/select_all_years_normal.png':
            for button in self.loaded_years[:-2]:
                button.state = "down"
        else:
            for button in self.loaded_years[:-2]:
                button.state = "normal"

    # Check if we have selected at least one Year and one Region.
    def check_if_ry(self, *args):
        c = 0
        for keylist in self.loaded_regions.values():
            for item in keylist:
                if item.state == "down":
                    c = 1
                    break
            if c == 1:
                break

        for j in self.loaded_years:
            if j.state == "down":
                c += 1
                break

        if c == 2:
            return True
        else:
            return False

    # Prepare a combined and filtered dict, with user's region/year selection.
    def init_iry_iteration(self):

        indicator = [self.id_conn[i] for i in self.sorted_indicators]
        regions = sorted(
            [i.text for j in self.loaded_regions.values() for i in j if i.state == "down"])
        years = sorted([i.text for i in self.loaded_years if i.state == "down"])

        # Set the default values.
        regions.insert(0, "Region")
        years.insert(0, "Year")

        self.iry_iteration["i"] = indicator
        self.iry_iteration["r"] = regions
        self.iry_iteration["y"] = years

    def init_indicator_var_iry(self):
        # Create indicator ID drop list.
        self.dropdown_i = DropDown(auto_width=False, width=90)

        for i in self.iry_iteration["i"]:
            btn = Factory.IRY_OptionBtn(text=i, on_press=self.dropdown_i.dismiss)
            btn.bind(on_release=partial(self.update_iry_preview, "indicator", btn.text))
            btn.bind(on_release=lambda btn: self.dropdown_i.select(btn.text))
            self.dropdown_i.add_widget(btn)

        mainbutton_i = Factory.IRY_MainbuttonBtn(text="IA")

        mainbutton_i.bind(on_release=self.dropdown_i.open)
        mainbutton_i.bind(on_release=lambda x: setattr(
            x, "background_normal", './Sources/selected_iry_down.png'))

        self.iry_table.add_widget(mainbutton_i)
        self.dropdown_i.bind(on_select=lambda instance, x: setattr(mainbutton_i, 'text', x))
        self.dropdown_i.bind(on_dismiss=lambda instance: setattr(
            mainbutton_i, "background_normal", './Sources/selected_iry_normal.png'))

        # Create region drop list.
        self.dropdown_r = DropDown(auto_width=False, width=90)

        for r in self.iry_iteration["r"]:
            btn = Factory.IRY_OptionBtn(text=r, on_press=self.dropdown_r.dismiss)
            btn.bind(on_release=partial(self.update_iry_preview, "region", btn.text))
            btn.bind(on_release=lambda btn: self.dropdown_r.select(btn.text))
            self.dropdown_r.add_widget(btn)

        mainbutton_r = Factory.IRY_MainbuttonBtn(text="[color=ff0080][Region][/color]")

        mainbutton_r.bind(on_release=self.dropdown_r.open)
        mainbutton_r.bind(on_release=lambda x: setattr(
            x, "background_normal", './Sources/selected_iry_down.png'))

        self.iry_table.add_widget(mainbutton_r)
        self.dropdown_r.bind(on_select=lambda instance, x: setattr(
            mainbutton_r, 'text', "[color=ff0080]["+x+"][/color]"))
        self.dropdown_r.bind(on_dismiss=lambda instance: setattr(
            mainbutton_r, "background_normal", './Sources/selected_iry_normal.png'))

        # Create year drop list.
        self.dropdown_y = DropDown(auto_width=False, width=90)

        for y in self.iry_iteration["y"]:
            btn = Factory.IRY_OptionBtn(text=y, on_press=self.dropdown_y.dismiss)
            btn.bind(on_release=partial(self.update_iry_preview, "year", btn.text))
            btn.bind(on_release=lambda btn: self.dropdown_y.select(btn.text))
            self.dropdown_y.add_widget(btn)

        mainbutton_y = Factory.IRY_MainbuttonBtn(text="[color=0d88d2][Year][/color]")

        mainbutton_y.bind(on_release=self.dropdown_y.open)
        mainbutton_y.bind(on_release=lambda x: setattr(
            x, "background_normal", './Sources/selected_iry_down.png'))

        self.iry_table.add_widget(mainbutton_y)
        self.dropdown_y.bind(on_select=lambda instance, x: setattr(
            mainbutton_y, 'text', "[color=0d88d2]["+x+"][/color]"))
        self.dropdown_y.bind(on_dismiss=lambda instance: setattr(
            mainbutton_y, "background_normal", './Sources/selected_iry_normal.png'))

    def update_iry_preview(self, *args):
        if args[0] == "indicator":
            self.iry_preview.indicator = args[1]
        elif args[0] == "region":
            if args[1] != "Region":
                self.iry_preview.region = "[b]["+args[1]+"][/b]"
            else:
                self.iry_preview.region = "["+args[1]+"]"
        else:
            if args[1] != "Year":
                self.iry_preview.year = "[b]["+args[1]+"][/b]"
            else:
                self.iry_preview.year = "["+args[1]+"]"

    # Check if string is number.
    @staticmethod
    def is_number(s):
        try:
            if s[-1] in "0123456789.":
                return True
        except IndexError:
            return False

    # Every time an item is selected.
    def formula_selected_item(self, item):
        if self.formula_items["last_item"]:
            self.formula_items["last_item"].background_normal = './Sources/formula_item_normal.png'

        if item.text:
            item.background_normal = './Sources/formula_item_down.png'
        else:
            item.background_normal = './Sources/formula_empty_item_down.png'

        self.formula_items["last_item"] = item

        self.parenthesis_handler(item)

    # Calculator's button manager.
    def calc_btn_pressed(self, t):
        # Ref my_formula children list.
        fc = self.my_formula.children

        # Ref Last Item.
        li = self.formula_items["last_item"]

        # Ref Last Item index.
        ili = fc.index(li)

        # If a number was pressed.
        if t in "0123456789.":
            # And this number is not the first item of the formula.
            if len(fc)-1 != ili:
                # If current selection is a number.
                if self.is_number(li.text):
                    # If item above contains no "." or pressed button is not ".".
                    if not ("." in li.text) or ("." != t):
                        # Move "selection" of last_item right to the next item (an empty item).
                        self.formula_selected_item(fc[ili-1])
                        # Ref last item index again because we changed that above.
                        ili = fc.index(self.formula_items["last_item"])
                    # Item above contains "." and button pressed is "." too.
                    else:
                        # Do not add it.
                        return None

                # If previous item from current selection is a number.
                if self.is_number(fc[ili+1].text):
                    # If item above contains no "." or pressed button is not "." .
                    if not ("." in fc[ili+1].text) or ("." != t):
                        # Update previous number item.
                        fc[ili+1].text += t
                    # After we either updated previous item or decided not to, do nothing else.
                    return None

        # If this number is "." or "0".
        if t == "." or t == "0":
            # Change number into "0."
            t = "0."

        # If last item is a blank space.
        if li.text == "":
            # Place item 1 spot right.
            index = fc.index(li)
        else:
            # Place item 2 spots right.
            index = fc.index(li)-1

        # Check if this is an index variable and create the new calc item.
        if t[0:6] == "[color":
            new_calc_item = Factory.Calc_Formula_Item(text=t,
                                                      markup=True,
                                                      on_press=self.formula_selected_item)
        elif t[0:10] == "<function>":
            t = "[color=f44336][i][font=timesi]"+t[10:]+"[/font][/i][/color]"
            new_calc_item = Factory.Calc_Formula_Item(text=t,
                                                      markup=True,
                                                      on_press=self.formula_selected_item)
        else:
            new_calc_item = Factory.Calc_Formula_Item(text=t,
                                                      color=(0, 0, 0, 1),
                                                      bold=True,
                                                      on_press=self.formula_selected_item)

        # Insert formula item.
        self.my_formula.add_widget(new_calc_item, index)

        # Creation of new space item.
        self.formula_spacer(index)

        # Locate possible parentheses errors.
        self.validate_parentheses()

    # Creation of empty space.
    def formula_spacer(self, index):
        # Creation of new space item.
        new_space_item = Factory.Calc_Formula_Item(text="",
                                                   on_press=self.formula_selected_item)

        # Insert formula space.
        self.my_formula.add_widget(new_space_item, index)

        # Set this to be the active item.
        self.formula_selected_item(new_space_item)

    # Find parenthesis closure point.
    def parenthesis_handler(self, selection):
        # Change states of previously selected parentheses, back to normal.
        for p in self.formula_items["p_group"]:
            p.color = (0, 0, 0, 1)
        self.formula_items["p_group"] = []

        f = self.my_formula.children
        i = f.index(selection)

        if selection.text == "(" or selection.text == ")":
            # By default selected parenthesis is not a reversed one.
            reverse = False
            # Ref p_text to current parenthesis.
            p_text = selection.text

            # Ref rev_p_text to the reverse parenthesis.
            if p_text == "(":
                rev_p_text = ")"
            else:
                rev_p_text = "("
                # Selected parenthesis is a reversed one.
                reverse = True

            p, rev_p = 0, 0
            # Iter upwards or downwards depending the parenthesis direction.
            for item in f[i:] if reverse else f[i::-1]:
                if item.text == p_text:
                    p += 1
                elif item.text == rev_p_text:
                    rev_p += +1
                if p > 0 and p == rev_p:
                    self.formula_items["p_group"] = [selection, item]
                    for p in self.formula_items["p_group"]:
                        p.color = (0.96, 0.26, 0.21, 1)
                    break
        else:
            p, rev_p = 0, 0
            for item in f[i:]:
                if item.text == "(":
                    p += 1
                elif item.text == ")":
                    rev_p += 1
                if p > rev_p:
                    self.parenthesis_handler(item)
                    break

    def validate_parentheses(self):
        # Define parentheses only list.
        pl = []
        # Define valid parentheses list.
        vl = []

        for i in self.my_formula.children[::-1]:
            if i.text == "(" or i.text == ")":
                pl.append(i)

        for o in pl:
            p, rev_p = 0, 0
            if o.text == "(":
                for c in pl[pl.index(o):]:
                    if c.text == ")":
                        rev_p += +1
                    else:
                        p += +1
                    if p == rev_p:
                        vl.append(o)
                        vl.append(c)
                        break

        for par in pl:
            if par in vl:
                par.bold = True
                par.italic = False
                par.color = (0, 0, 0, 1)
            else:
                par.bold = False
                par.italic = True
                par.color = (0.5, 0.5, 0.5, 1)

    # Index Algebra calculations.
    def calc_backspace_pressed(self):
        # Ref my_formula children list.
        fc = self.my_formula.children

        # Ref Last Item.
        li = self.formula_items["last_item"]

        # Ref Last Item index.
        ili = fc.index(li)

        # If selected item is not the first item of the formula.
        if len(fc)-1 != ili:

            try:
                # Try to select the item 2 slots to the left.
                self.formula_selected_item(fc[ili+2])
            except IndexError:
                # Selected item is the 2nd in the list. Select first item.
                self.formula_selected_item(fc[ili+1])

            # Redefine ili because last_item was changed.
            ili = fc.index(self.formula_items["last_item"])

            self.my_formula.remove_widget(fc[ili-1])

            # If not first item in the formula.
            if fc.index(self.formula_items["last_item"]) != 0:
                self.my_formula.remove_widget(fc[ili-2])

            # Locate possible parentheses errors.
            self.validate_parentheses()

    def clear_formula(self):
        # Clear formula.
        self.my_formula.clear_widgets()

        # Creation of new space item.
        self.formula_spacer(0)

    def exec_formula(self):
        # Prepare composite index model dict.
        self.cim = {self.rev_country_dict[r]: [] for r in self.iry_iteration["r"][1:]}

        # Replacement set of dictionaries.
        rep1 = {"[color=000000][b]": "self.indicator_var_eval('",
                "[/b][/color][sub][color=ff0080][": "','",
                "][/color][color=0d88d2][": "',",
                "][/color][/sub]": ")"}
        rep2 = {"b][": "", "][/b": ""}
        rep3 = {"[color=f44336][i][font=timesi]": "math.", "[/font][/i][/color]": ""}

        formula = []

        for item in reversed(self.my_formula.children):
            if item.text != "":
                iv = item.text

                # Cleanup markup code Indicator Variables.
                if iv[:17] == "[color=000000][b]":
                    # LvL 1 replacement.
                    for key, var in rep1.iteritems():
                        iv = iv.replace(key, var)
                    # LvL 2 replacement.
                    for key, var in rep2.iteritems():
                        iv = iv.replace(key, var)

                # Cleanup markup code from function Names.
                elif iv[:17] == "[color=f44336][i]":
                    for key, var in rep3.iteritems():
                        iv = iv.replace(key, var)

                else:
                    # Try to convert all numbers to floats.
                    try:
                        iv = str(float(iv))

                    except ValueError:
                        pass

                    # Something really unexpected just happened.
                    except Exception as nfe:
                        print "def exec_formula(self):", type(nfe), nfe.__doc__, nfe.message

                formula.append(iv)

        # Join formula into a single string.
        string_formula = "".join(formula)

        # Store possible errors in this dictionary.
        e = {}

        try:
            # Start building the log file.
            with open("my_index.log", "w") as log_file:

                log_file.write("Indicators Variables\n===========================\n")
                for key, val in self.rev_id_conn.iteritems():
                    log_file.write(val+" = "+key)
                log_file.write("\n===========================\n\nComposite Index Formula"
                               "\n===========================\nCI('Region','Year'): [")
                log_file.write(string_formula.replace("self.indicator_var_eval", "IndValue") + "]")
                log_file.write("\n===========================\n\nFailed Calculations"
                               "\n===========================\n")

                for Region in self.iry_iteration["r"][1:]:
                    region_formula = string_formula.replace('Region', Region)
                    for Year in self.iry_iteration["y"][1:]:
                        year_formula = region_formula.replace('Year', Year)
                        try:
                            # If evaluation of year_formula results a float, add that in self.cim.
                            self.cim[self.rev_country_dict[Region]].append(
                                float(eval(year_formula)))

                        except Exception as fe:
                            # If no float was returned, add the formula and error message in log.
                            self.cim[self.rev_country_dict[Region]].append("-")
                            log_file.write("CI" +
                                           str((self.rev_country_dict[Region], Year)) + ": ")
                            for item in formula:
                                if "indicator_var_eval" in item:
                                    log_file.write(str(eval(item.replace(
                                        'Region', Region).replace(
                                        'Year', Year))))
                                else:
                                    log_file.write(item)
                            log_file.write("  <"+str(fe)+">\n")

                log_file.write("===========================")

        # Something really unexpected just happened.
        except Exception as l_er:
            e["my_index.log"] = l_er

        try:
            # Start building the calculation file.
            with open("my_index.csv", "w") as calc_file:
                for y in self.iry_iteration["y"][1:]:
                    calc_file.write(";"+y)
                for r in self.iry_iteration["r"][1:]:
                    calc_file.write("\n"+self.rev_country_dict[r])
                    for val in self.cim[self.rev_country_dict[r]]:
                        calc_file.write(";"+str(val).replace('.', ","))

        # Something really unexpected just happened.
        except Exception as c_er:
            e["my_index.csv"] = c_er

        # If error dict is not empty, a problem has occurred.
        if e != {}:
            self.popuper("Could not prepare files properly:\n" +
                         str([k + " >> " + v.__doc__ for k, v in e.iteritems()]) +
                         "\n\nMake sure file/s above are not already opened",
                         'Unexpected Error!')

        # If not, no errors found.
        else:
            self.popuper("Two files have been saved\nin App's root directory.\n\n"
                         "Check 'my_index.csv' for results and\n"
                         "'my_index.log' for calculation logs.",
                         "Calculations done!")

            # Prepare Thematic Screen.
            self.prepare_thematic()

    # Evaluate Indicator value function.
    def indicator_var_eval(self, ind, reg, year):
        try:
            # If there is any data, return it.
            return float(self.all_indicators_data[ind][self.rev_country_dict[reg]][year])

        except KeyError:
            # If no Data, return notice for logging.
            return "NoData["+str(ind)+", "+str(self.rev_country_dict[reg])+", "+str(year)+"]"

        # Something really unexpected just happened.
        except Exception as e:
            print "def indicator_var_eval(self, ind, reg, year):", type(e), e.__doc__, e.message

    # This function prepares the Thematic Designer Screen.
    def prepare_thematic(self):
        # Activate Thematic Button from MainWindow.
        self.ic_thematic_btn.disabled = False

        # Clear all previously created year_buttons and Data Tables.
        self.ic_th_designer.th_years_stack.clear_widgets()
        self.ic_th_designer.th_data_table_regions.clear_widgets()
        self.ic_th_designer.th_data_table_values.clear_widgets()

        for y in self.iry_iteration["y"][1:]:
            year_btn = Factory.TH_YearSelector(text=str(y), group='year')
            self.ic_th_designer.th_years_stack.add_widget(year_btn)
            year_btn.bind(on_release=self.ic_th_designer.th_data_table_init)


class ThematicValues(Label):

    calc_number = ObjectProperty()
    region = StringProperty("")


class SvgWidget(FloatLayout, StencilView):
    pass


class WorldMapSVG(Scatter):

    def __init__(self, **kwargs):
        super(WorldMapSVG, self).__init__(**kwargs)
        with self.canvas:
            world_map = Svg("./Sources/WorldMap.svg")


class MapDesigner(MouseScreen):

    # Link to IndexCreation.
    md_index_creation = ObjectProperty()

    @mainthread
    def popuper(self, message, title):
        Popup(title=title, content=Label(
            text=message,
            font_size=15,
            halign="center",
            italic=True
        ), size_hint=(None, None), size=(350, 180)).open()

    # "#FFFFFF" -> [255,255,255].
    @staticmethod
    def hex_to_rgb(hex_c):
        # Pass 16 to the integer function for change of base.
        return [int(hex_c[i:i+2], 16) for i in range(1,6,2)]

    # [255,255,255] -> "#FFFFFF".
    @staticmethod
    def rgb_to_hex(rgb_c):
        # Components need to be integers for hex to make sense.
        rgb_c = [int(x) for x in rgb_c]
        return "#"+"".join(["0{0:x}".format(v) if v < 16 else "{0:x}".format(v) for v in rgb_c])

    # Creates thematic legend based on given number of classes.
    def setup_linear_gradient(self, start_hex, finish_hex, n):
        # Starting and ending colors in RGB form
        s = self.hex_to_rgb(start_hex)
        f = self.hex_to_rgb(finish_hex)

        # Initialize a list of the output colors with the starting color.
        rgb_list = [s]

        # Calculate a color at each evenly spaced value of t from 1 to n.
        for t in range(1, n):
            # Interpolate RGB vector for color at the current value of t
            curr_vector = [int(s[j] + (float(t)/(n-1))*(f[j]-s[j])) for j in range(3)]

            # Add it to our list of output colors
            rgb_list.append(curr_vector)

        # Prepare a temp data_set {Region: Value}, to be used for the legend's creation.
        data_set = {p.region: p.calc_number for p in self.th_data_table_values.children
                    if p.calc_number != "-"}

        # Takes in the RGB sub-lists and returns dictionary of colors in RGB and hex form.
        color_dict = {"hex": [self.rgb_to_hex(rgb_c) for rgb_c in rgb_list],
                      "r": [rgb_c[0] for rgb_c in rgb_list],
                      "g": [rgb_c[1] for rgb_c in rgb_list],
                      "b": [rgb_c[2] for rgb_c in rgb_list]}

        # If there is at least 1 region with a value in data table, proceed with the calculations.
        if len(data_set) > 0:
            min_v = min(data_set.values())
            max_v = max(data_set.values())
            range_v = max_v - min_v
            interval_v = range_v/float(n)

            # If we have only one interval, use current min and max values.
            if n == 1:
                classification = [(min_v, max_v)]

            # If we have more than one intervals..
            else:
                # Set first tuple of the classification.
                classification = [(min_v, interval_v)]
                # Set the other ones (except the last one)
                for i in range(1, n-1):
                    classification.append((interval_v*i, interval_v*(i+1)))
                # Set the last one too.
                classification.append((interval_v*(n-1), max_v))

            # Create classified legend.
            self.build_legend(classification, color_dict['r'], color_dict['g'], color_dict['b'])

            # Reversing the list will help with color assignment.
            classification = list(reversed(classification))

            # Replace data value with the equivalent color.
            for k, v in data_set.iteritems():
                for g in range(len(classification)):
                    if classification[g][0] <= v <= classification[g][1]:
                        break
                data_set[k] = color_dict['hex'][g]

            # Prepare the SVG before loading it, according to calculated color classes.
            self.prepare_svg(data_set)

        # If data table has no values pop a notice.
        else:
            self.popuper("There should be at least one region\n"
                         "with a numeric value in the Data Table.",
                         "Warning!")

    # This function creates the legend with all color classes.
    def build_legend(self, classes, r, g, b):
        print classes

    # This function prepares the SVG thematic colors.
    def prepare_svg(self, d_set):
        print d_set

    def th_map(self):
        self.map_canvas.clear_widgets()
        svg = WorldMapSVG()
        self.map_canvas.add_widget(svg)
        svg.center_x = self.width/2
        svg.center_y = self.height/2

    # Prepare list that will be used to build the Data Table.
    def th_data_table_init(self, year_btn):
        # Ref the index of year button pressed.
        year_index = list(reversed(self.th_years_stack.children)).index(year_btn)

        data_set = sorted([(v[year_index], k) for k, v in self.md_index_creation.cim.iteritems()],
                          key=operator.itemgetter(1))

        # Build the data table using the generated data_set.
        self.build_th_data_table(data_set)

    # Prepare list that will be used to sort the Data Table.
    def sort_data(self, direction_btn):
        # Set reverse option based on button pressed.
        rev = False if direction_btn == "ascending" else True

        data_set = sorted([(i.calc_number, i.region) for i in self.th_data_table_values.children],
                          key=operator.itemgetter(0),
                          reverse=rev)

        # Build the data table using the generated data_set.
        self.build_th_data_table(data_set)

    # Build Data Table.
    def build_th_data_table(self, data_set):
        # Clear Data Tables.
        self.th_data_table_regions.clear_widgets()
        self.th_data_table_values.clear_widgets()

        # For each item in our data_set.
        for i in range(len(data_set)):
            # Ref float and region to handle str/float items.
            data_value = data_set[i][0]
            r = data_set[i][1]

            # Create the region label.
            region = Factory.TH_Regions(text=r)
            self.th_data_table_regions.add_widget(region)

            if isinstance(data_value, float):
                # Format numbers to be more friendly.
                tup = str("%.5G" % data_value).partition('E')
                val = (('[size=12] E'.join((tup[0], tup[-1]))+"[/size]")
                       .replace("[size=12] E[/size]", ""))\
                    .replace(".", ",")
            else:
                # Handle cases where item is not a number.
                val = data_value
                data_value = "-"

            year_value = Factory.ThematicValues(text=str(val), calc_number=data_value, region=r)
            self.th_data_table_values.add_widget(year_value)


class CIMMenu(BoxLayout):

    pass


class MainWindow(BoxLayout):

    # Prepare kivy properties that show if a process or a popup are currently running.
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    @staticmethod
    def threadonator(*args):
        threading.Thread(target=args[0], args=(args,)).start()

    @mainthread
    def popuper(self, message, title):
        Popup(title=title, content=Label(
            text=message,
            font_size=15,
            halign="center",
            italic=True
        ), size_hint=(None, None), size=(350, 180)).open()

    # Loading bar
    def update_progress(self, *args):
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
    def core_build(self, *args):
        # A process just started running (in a new thread).
        self.processing = True
        self.threadonator(self.update_progress)

        # Try, in case there is a problem with the online updating process.
        try:
            # Set target web links.
            c_link = start_url + countries + end_url
            t_link = start_url + topics + end_url

            # Define World Bank connections (JSON data).
            file_countries = urllib2.urlopen(c_link, timeout=60)
            file_topics = urllib2.urlopen(t_link, timeout=60)
            file_wdi = urllib2.urlopen(wdi_url, timeout=60)

            # Convert JSON data into temp python structures.
            countries_py = json.load(file_countries)
            topics_py = json.load(file_topics)
            wdi_py = json.load(file_wdi)

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
                        topics_zip[int(wdi_py[1][indicator]["topics"][parent_topic]["id"])].append(
                            [(wdi_py[1][indicator]["id"]),
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

        except Exception as e:
            self.popuper("Could not update Coredb.\nPlease try again.\n\n"+e.message, 'Warning:')

        # Close URL json files.
        finally:
            try:
                file_countries.close()
                file_topics.close()
                file_wdi.close()

            # If there is no connection, do nothing.
            except UnboundLocalError:
                pass

            # Something really unexpected just happened.
            except Exception as e:
                print "def core_build(self, *args):", type(e), e.__doc__, e.message

        self.processing = False

    # This method checks for last core's index database update.
    def check(self, *args):
        # For as long as the popup window is shown.
        while self.popup_active and (not CIMgui.app_closed):

            # If there is any process running, wait until finish.
            while self.processing:
                self.coredb_state.text =\
                    "Updating indicator database!\nDuration depends on your Internet speed.."
                time.sleep(1)

            # Try to open the json DB file.
            try:
                stored_coredb = open("./DB/core.db", "r")
                py_coredb = json.load(stored_coredb)
                stored_coredb.close()

                self.coredb_state.text = ("Latest DB Update:\n" + py_coredb[0]['table_date'])

            # No file found.
            except IOError:
                self.coredb_state.text = "No valid Database found!\nPlease update it."

            # Something really unexpected just happened.
            except Exception as e:
                print "def check(self, *args):", type(e), e.__doc__, e.message

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
