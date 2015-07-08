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
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.animation import Animation
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

    # Link to CIMScreenManager
    is_manager = ObjectProperty()

    # Link to IndexCreation
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

    # Link to IndexSelection
    ic_index_selection = ObjectProperty()

    # List to show which indicator review is currently loaded.
    sorted_indicators = ListProperty()

    dropdown_id = ObjectProperty()
    dropdown_i = ObjectProperty()
    dropdown_r = ObjectProperty()
    dropdown_y = ObjectProperty()

    all_indicators_data = DictProperty({})
    country_list = ListProperty()
    country_dict = DictProperty({})
    inv_country_dict = DictProperty({})
    drawing_data = BooleanProperty(False)
    loading_percentage = NumericProperty(0)
    formula_items = DictProperty({"last_item": None, "p_group": []})

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexCreation, self).__init__(**kwargs)

        self.id_conn = {}
        self.year_row = []
        self.data_view_now = []
        self.data_queue = None
        self.acceding_order_buttons = []
        self.descending_order_buttons = []
        self.must_draw_data = True
        self.loaded_regions = {}
        self.loaded_years = []
        self.iry_iteration = {"i": [], "r": [], "y": []}

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
            for button in self.acceding_order_buttons:
                if button.collide_point(*button.to_widget(*args[1])):
                    button.background_normal = './Sources/acceding_down.png'
                else:
                    button.background_normal = './Sources/acceding_normal.png'

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

        # CleanUP country list and dict.
        self.country_list = []
        self.country_dict = {}

        # Reset connection list.
        connections = []

        # Sort keys for the ID sequence.
        self.sorted_indicators = mi.keys()
        self.sorted_indicators.sort()

        # Number of my indicators.
        items = len(self.sorted_indicators)

        # Prepare dictionary to link model's ID's to Indicator names.
        self.id_conn = {}

        # Characters to use for ID creation
        abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        # This var will show ID creation sequence.
        items_created = 0

        # Create short ID's, store link to a dict and prepare each structure. (UPTO 26)
        for i in abc:

            short_id = "I"+i

            # Update ID link dictionary.
            self.id_conn[self.sorted_indicators[items_created]] = short_id

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

        # Prepare Country List and place it inside all_indicators_data.
        for i in range(1, self.ic_index_selection.coredb_py[1][0]["countries_num"]+1):
            country = self.ic_index_selection.coredb_py[1][i][1]
            self.country_list.append(country)
            self.country_dict[country] = [self.ic_index_selection.coredb_py[1][i][0],
                                          self.ic_index_selection.coredb_py[1][i][2]]
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

            tempdb = open("./DB/temp.db", "w")
            json.dump(self.all_indicators_data, tempdb)
            tempdb.close()

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
                column = self.acceding_order_buttons.index(args[0]) + 1

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
                self.acceding_order_buttons = []
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
                        head_box = Factory.HeadBox(orientation="horizontal",
                                                   size_hint=(None, None),
                                                   size=(100, 20))
                        left_title = Factory.YearHeader(text=str(header))
                        right_box = BoxLayout(orientation="vertical",
                                              spacing=4,
                                              size_hint=(None, None),
                                              size=(30, 20))
                        acceding_btn = Factory.OrderBtn(
                            background_normal='./Sources/acceding_normal.png',
                            background_down='./Sources/acceding_down.png',
                            on_release=self.sort_data_manager)
                        descending_btn = Factory.OrderBtn(
                            background_normal='./Sources/descending_normal.png',
                            background_down='./Sources/descending_down.png',
                            on_release=self.sort_data_manager)

                        # Place buttons in a list. Will use that for hover checks.
                        self.acceding_order_buttons.append(acceding_btn)
                        self.descending_order_buttons.append(descending_btn)

                        right_box.add_widget(acceding_btn)
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

        min_y, max_y = 1950, 2015
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
        regions = sorted([i.text for j in self.loaded_regions.values() for i in j if i.state == "down"])
        years = sorted([i.text for i in self.loaded_years if i.state == "down"])

        # Set the default values.
        regions.insert(0, "Region")
        years.insert(0, "Year")

        self.iry_iteration["i"] = indicator
        self.iry_iteration["r"] = regions
        self.iry_iteration["y"] = years

        self.iry_iteration = {'i': ['IA', 'IB', 'IC', 'ID'], 'y': ['Year', '1950', '1951', '1952', '1953', '1954', '1955', '1956', '1957', '1958', '1959', '1960', '1961', '1962', '1963', '1964', '1965', '1966', '1967', '1968', '1969', '1970', '1971', '1972', '1973', '1974', '1975', '1976', '1977', '1978', '1979', '1980', '1981', '1982', '1983', '1984', '1985', '1986', '1987', '1988', '1989', '1990', '1991', '1992', '1993', '1994', '1995', '1996', '1997', '1998', '1999', '2000', '2001', '2002', '2003', '2004', '2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014'], 'r': ['Region', 'ABW', 'AFG', 'AFR', 'AGO', 'ALB', 'AND', 'ANR', 'ARB', 'ARE', 'ARG', 'ARM', 'ASM', 'ATG', 'AUS', 'AUT', 'AZE', 'BDI', 'BEL', 'BEN', 'BFA', 'BGD', 'BGR', 'BHR', 'BHS', 'BIH', 'BLR', 'BLZ', 'BMU', 'BOL', 'BRA', 'BRB', 'BRN', 'BTN', 'BWA', 'CAA', 'CAF', 'CAN', 'CEA', 'CEB', 'CEU', 'CHE', 'CHI', 'CHL', 'CHN', 'CIV', 'CLA', 'CME', 'CMR', 'COD', 'COG', 'COL', 'COM', 'CPV', 'CRI', 'CSA', 'CSS', 'CUB', 'CUW', 'CYM', 'CYP', 'CZE', 'DEU', 'DJI', 'DMA', 'DNK', 'DOM', 'DZA', 'EAP', 'EAS', 'ECA', 'ECS', 'ECU', 'EGY', 'EMU', 'ERI', 'ESP', 'EST', 'ETH', 'EUU', 'FCS', 'FIN', 'FJI', 'FRA', 'FRO', 'FSM', 'GAB', 'GBR', 'GEO', 'GHA', 'GIN', 'GMB', 'GNB', 'GNQ', 'GRC', 'GRD', 'GRL', 'GTM', 'GUM', 'GUY', 'HIC', 'HKG', 'HND', 'HPC', 'HRV', 'HTI', 'HUN', 'IDN', 'IMN', 'IND', 'INX', 'IRL', 'IRN', 'IRQ', 'ISL', 'ISR', 'ITA', 'JAM', 'JOR', 'JPN', 'KAZ', 'KEN', 'KGZ', 'KHM', 'KIR', 'KNA', 'KOR', 'KSV', 'KWT', 'LAC', 'LAO', 'LBN', 'LBR', 'LBY', 'LCA', 'LCN', 'LCR', 'LDC', 'LIC', 'LIE', 'LKA', 'LMC', 'LMY', 'LSO', 'LTU', 'LUX', 'LVA', 'MAC', 'MAF', 'MAR', 'MCA', 'MCO', 'MDA', 'MDE', 'MDG', 'MDV', 'MEA', 'MEX', 'MHL', 'MIC', 'MKD', 'MLI', 'MLT', 'MMR', 'MNA', 'MNE', 'MNG', 'MNP', 'MOZ', 'MRT', 'MUS', 'MWI', 'MYS', 'NAC', 'NAF', 'NAM', 'NCL', 'NER', 'NGA', 'NIC', 'NLD', 'NOC', 'NOR', 'NPL', 'NZL', 'OEC', 'OED', 'OMN', 'OSS', 'PAK', 'PAN', 'PER', 'PHL', 'PLW', 'PNG', 'POL', 'PRI', 'PRK', 'PRT', 'PRY', 'PSE', 'PSS', 'PYF', 'QAT', 'ROU', 'RUS', 'RWA', 'SAS', 'SAU', 'SCE', 'SDN', 'SEN', 'SGP', 'SLB', 'SLE', 'SLV', 'SMR', 'SOM', 'SRB', 'SSA', 'SSD', 'SSF', 'SST', 'STP', 'SUR', 'SVK', 'SVN', 'SWE', 'SWZ', 'SXM', 'SXZ', 'SYC', 'SYR', 'TCA', 'TCD', 'TGO', 'THA', 'TJK', 'TKM', 'TLS', 'TON', 'TTO', 'TUN', 'TUR', 'TUV', 'TZA', 'UGA', 'UKR', 'UMC', 'URY', 'USA', 'UZB', 'VCT', 'VEN', 'VIR', 'VNM', 'VUT', 'WLD', 'WSM', 'XZN', 'YEM', 'ZAF', 'ZMB', 'ZWE']} # todo

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

    def exec_formula(self, *args):

        self.country_dict = {'Canada': ['CAN', 'NAC'], 'Sao Tome and Principe': ['STP', 'SSF'], 'Turkmenistan': ['TKM', 'ECS'], 'Lao PDR': ['LAO', 'EAS'], 'Arab World': ['ARB', 'NA'], 'Latin America & Caribbean (all income levels)': ['LCN', 'NA'], 'Cambodia': ['KHM', 'EAS'], 'Ethiopia': ['ETH', 'SSF'], 'Aruba': ['ABW', 'LCN'], 'Swaziland': ['SWZ', 'SSF'], 'South Asia': ['SAS', 'NA'], 'Argentina': ['ARG', 'LCN'], 'Bolivia': ['BOL', 'LCN'], 'Bahamas, The': ['BHS', 'LCN'], 'Burkina Faso': ['BFA', 'SSF'], 'OECD members': ['OED', 'NA'], 'Bahrain': ['BHR', 'MEA'], 'Saudi Arabia': ['SAU', 'MEA'], 'Rwanda': ['RWA', 'SSF'], 'Sub-Saharan Africa (IFC classification)': ['CAA', 'NA'], 'Togo': ['TGO', 'SSF'], 'Thailand': ['THA', 'EAS'], 'Japan': ['JPN', 'EAS'], 'Channel Islands': ['CHI', 'ECS'], 'American Samoa': ['ASM', 'EAS'], 'Northern Mariana Islands': ['MNP', 'EAS'], 'Slovenia': ['SVN', 'ECS'], 'Guatemala': ['GTM', 'LCN'], 'Bosnia and Herzegovina': ['BIH', 'ECS'], 'Kuwait': ['KWT', 'MEA'], 'Russian Federation': ['RUS', 'ECS'], 'Jordan': ['JOR', 'MEA'], 'St. Lucia': ['LCA', 'LCN'], 'Congo, Rep.': ['COG', 'SSF'], 'North Africa': ['NAF', 'NA'], 'Dominica': ['DMA', 'LCN'], 'Liberia': ['LBR', 'SSF'], 'Maldives': ['MDV', 'SAS'], 'East Asia & Pacific (all income levels)': ['EAS', 'NA'], 'Southern Cone': ['SCE', 'NA'], 'Lithuania': ['LTU', 'ECS'], 'Tanzania': ['TZA', 'SSF'], 'Vietnam': ['VNM', 'EAS'], 'Cabo Verde': ['CPV', 'SSF'], 'Greenland': ['GRL', 'ECS'], 'Gabon': ['GAB', 'SSF'], 'Monaco': ['MCO', 'ECS'], 'New Zealand': ['NZL', 'EAS'], 'European Union': ['EUU', 'NA'], 'Jamaica': ['JAM', 'LCN'], 'Albania': ['ALB', 'ECS'], 'Samoa': ['WSM', 'EAS'], 'Slovak Republic': ['SVK', 'ECS'], 'United Arab Emirates': ['ARE', 'MEA'], 'Guam': ['GUM', 'EAS'], 'Uruguay': ['URY', 'LCN'], 'India': ['IND', 'SAS'], 'Azerbaijan': ['AZE', 'ECS'], 'Lesotho': ['LSO', 'SSF'], 'Kenya': ['KEN', 'SSF'], 'Latin America and the Caribbean (IFC classification)': ['CLA', 'NA'], 'Upper middle income': ['UMC', 'NA'], 'Tajikistan': ['TJK', 'ECS'], 'Pacific island small states': ['PSS', 'NA'], 'Turkey': ['TUR', 'ECS'], 'Afghanistan': ['AFG', 'SAS'], 'Venezuela, RB': ['VEN', 'LCN'], 'Bangladesh': ['BGD', 'SAS'], 'Mauritania': ['MRT', 'SSF'], 'Solomon Islands': ['SLB', 'EAS'], 'Hong Kong SAR, China': ['HKG', 'EAS'], 'San Marino': ['SMR', 'ECS'], 'Mongolia': ['MNG', 'EAS'], 'France': ['FRA', 'ECS'], 'Syrian Arab Republic': ['SYR', 'MEA'], 'Bermuda': ['BMU', 'NAC'], 'Namibia': ['NAM', 'SSF'], 'Somalia': ['SOM', 'SSF'], 'Peru': ['PER', 'LCN'], 'Vanuatu': ['VUT', 'EAS'], 'Nigeria': ['NGA', 'SSF'], 'South Asia (IFC classification)': ['CSA', 'NA'], 'Norway': ['NOR', 'ECS'], "Cote d'Ivoire": ['CIV', 'SSF'], 'Europe & Central Asia (developing only)': ['ECA', 'NA'], 'Benin': ['BEN', 'SSF'], 'Other small states': ['OSS', 'NA'], 'Cuba': ['CUB', 'LCN'], 'Cameroon': ['CMR', 'SSF'], 'Montenegro': ['MNE', 'ECS'], 'Low & middle income': ['LMY', 'NA'], 'Middle East (developing only)': ['MDE', 'NA'], 'China': ['CHN', 'EAS'], 'Sub-Saharan Africa (developing only)': ['SSA', 'NA'], 'Armenia': ['ARM', 'ECS'], 'Small states': ['SST', 'NA'], 'Timor-Leste': ['TLS', 'EAS'], 'Dominican Republic': ['DOM', 'LCN'], 'Sub-Saharan Africa excluding South Africa': ['SXZ', 'NA'], 'Low income': ['LIC', 'NA'], 'Ukraine': ['UKR', 'ECS'], 'Ghana': ['GHA', 'SSF'], 'Tonga': ['TON', 'EAS'], 'Finland': ['FIN', 'ECS'], 'Latin America & Caribbean (developing only)': ['LAC', 'NA'], 'High income': ['HIC', 'NA'], 'Libya': ['LBY', 'MEA'], 'Korea, Rep.': ['KOR', 'EAS'], 'Cayman Islands': ['CYM', 'LCN'], 'Central African Republic': ['CAF', 'SSF'], 'Europe & Central Asia (all income levels)': ['ECS', 'NA'], 'Mauritius': ['MUS', 'SSF'], 'Liechtenstein': ['LIE', 'ECS'], 'Belarus': ['BLR', 'ECS'], 'Mali': ['MLI', 'SSF'], 'Micronesia, Fed. Sts.': ['FSM', 'EAS'], 'Korea, Dem. Rep.': ['PRK', 'EAS'], 'Sub-Saharan Africa excluding South Africa and Nigeria': ['XZN', 'NA'], 'Bulgaria': ['BGR', 'ECS'], 'North America': ['NAC', 'NA'], 'Romania': ['ROU', 'ECS'], 'Angola': ['AGO', 'SSF'], 'Central Europe and the Baltics': ['CEB', 'NA'], 'Egypt, Arab Rep.': ['EGY', 'MEA'], 'Trinidad and Tobago': ['TTO', 'LCN'], 'St. Vincent and the Grenadines': ['VCT', 'LCN'], 'Cyprus': ['CYP', 'ECS'], 'Caribbean small states': ['CSS', 'NA'], 'Brunei Darussalam': ['BRN', 'EAS'], 'Qatar': ['QAT', 'MEA'], 'Middle income': ['MIC', 'NA'], 'Austria': ['AUT', 'ECS'], 'High income: OECD': ['OEC', 'NA'], 'Mozambique': ['MOZ', 'SSF'], 'Uganda': ['UGA', 'SSF'], 'Kyrgyz Republic': ['KGZ', 'ECS'], 'Hungary': ['HUN', 'ECS'], 'Niger': ['NER', 'SSF'], 'United States': ['USA', 'NAC'], 'Brazil': ['BRA', 'LCN'], 'World': ['WLD', 'NA'], 'Middle East & North Africa (all income levels)': ['MEA', 'NA'], 'Guinea': ['GIN', 'SSF'], 'Panama': ['PAN', 'LCN'], 'Costa Rica': ['CRI', 'LCN'], 'Luxembourg': ['LUX', 'ECS'], 'Andorra': ['AND', 'ECS'], 'Chad': ['TCD', 'SSF'], 'Euro area': ['EMU', 'NA'], 'Ireland': ['IRL', 'ECS'], 'Pakistan': ['PAK', 'SAS'], 'Palau': ['PLW', 'EAS'], 'Faeroe Islands': ['FRO', 'ECS'], 'Lower middle income': ['LMC', 'NA'], 'Ecuador': ['ECU', 'LCN'], 'Czech Republic': ['CZE', 'ECS'], 'Australia': ['AUS', 'EAS'], 'Algeria': ['DZA', 'MEA'], 'East Asia and the Pacific (IFC classification)': ['CEA', 'NA'], 'El Salvador': ['SLV', 'LCN'], 'Tuvalu': ['TUV', 'EAS'], 'St. Kitts and Nevis': ['KNA', 'LCN'], 'Marshall Islands': ['MHL', 'EAS'], 'Chile': ['CHL', 'LCN'], 'Puerto Rico': ['PRI', 'LCN'], 'Belgium': ['BEL', 'ECS'], 'Europe and Central Asia (IFC classification)': ['CEU', 'NA'], 'Haiti': ['HTI', 'LCN'], 'Belize': ['BLZ', 'LCN'], 'Fragile and conflict affected situations': ['FCS', 'NA'], 'Sierra Leone': ['SLE', 'SSF'], 'Georgia': ['GEO', 'ECS'], 'East Asia & Pacific (developing only)': ['EAP', 'NA'], 'Denmark': ['DNK', 'ECS'], 'Philippines': ['PHL', 'EAS'], 'Moldova': ['MDA', 'ECS'], 'Macedonia, FYR': ['MKD', 'ECS'], 'Morocco': ['MAR', 'MEA'], 'Croatia': ['HRV', 'ECS'], 'French Polynesia': ['PYF', 'EAS'], 'Guinea-Bissau': ['GNB', 'SSF'], 'Kiribati': ['KIR', 'EAS'], 'Switzerland': ['CHE', 'ECS'], 'Grenada': ['GRD', 'LCN'], 'Middle East and North Africa (IFC classification)': ['CME', 'NA'], 'Yemen, Rep.': ['YEM', 'MEA'], 'Isle of Man': ['IMN', 'ECS'], 'Portugal': ['PRT', 'ECS'], 'Estonia': ['EST', 'ECS'], 'Kosovo': ['KSV', 'ECS'], 'Sweden': ['SWE', 'ECS'], 'Mexico': ['MEX', 'LCN'], 'Africa': ['AFR', 'NA'], 'South Africa': ['ZAF', 'SSF'], 'Uzbekistan': ['UZB', 'ECS'], 'Tunisia': ['TUN', 'MEA'], 'Djibouti': ['DJI', 'MEA'], 'West Bank and Gaza': ['PSE', 'MEA'], 'Antigua and Barbuda': ['ATG', 'LCN'], 'Spain': ['ESP', 'ECS'], 'Colombia': ['COL', 'LCN'], 'Burundi': ['BDI', 'SSF'], 'Least developed countries: UN classification': ['LDC', 'NA'], 'Fiji': ['FJI', 'EAS'], 'Barbados': ['BRB', 'LCN'], 'Seychelles': ['SYC', 'SSF'], 'Madagascar': ['MDG', 'SSF'], 'Italy': ['ITA', 'ECS'], 'Curacao': ['CUW', 'LCN'], 'Bhutan': ['BTN', 'SAS'], 'Sudan': ['SDN', 'SSF'], 'Latin America and the Caribbean': ['LCR', 'NA'], 'Nepal': ['NPL', 'SAS'], 'Singapore': ['SGP', 'EAS'], 'Malta': ['MLT', 'MEA'], 'Netherlands': ['NLD', 'ECS'], 'Macao SAR, China': ['MAC', 'EAS'], 'Andean Region': ['ANR', 'NA'], 'Middle East & North Africa (developing only)': ['MNA', 'NA'], 'Turks and Caicos Islands': ['TCA', 'LCN'], 'St. Martin (French part)': ['MAF', 'LCN'], 'Iran, Islamic Rep.': ['IRN', 'MEA'], 'Israel': ['ISR', 'MEA'], 'Indonesia': ['IDN', 'EAS'], 'Malaysia': ['MYS', 'EAS'], 'Iceland': ['ISL', 'ECS'], 'Zambia': ['ZMB', 'SSF'], 'Sub-Saharan Africa (all income levels)': ['SSF', 'NA'], 'Senegal': ['SEN', 'SSF'], 'Papua New Guinea': ['PNG', 'EAS'], 'Malawi': ['MWI', 'SSF'], 'Suriname': ['SUR', 'LCN'], 'Zimbabwe': ['ZWE', 'SSF'], 'Germany': ['DEU', 'ECS'], 'Oman': ['OMN', 'MEA'], 'Kazakhstan': ['KAZ', 'ECS'], 'Poland': ['POL', 'ECS'], 'Sint Maarten (Dutch part)': ['SXM', 'LCN'], 'Eritrea': ['ERI', 'SSF'], 'Virgin Islands (U.S.)': ['VIR', 'LCN'], 'Iraq': ['IRQ', 'MEA'], 'New Caledonia': ['NCL', 'EAS'], 'Paraguay': ['PRY', 'LCN'], 'Not classified': ['INX', 'NA'], 'Latvia': ['LVA', 'ECS'], 'South Sudan': ['SSD', 'SSF'], 'Guyana': ['GUY', 'LCN'], 'Honduras': ['HND', 'LCN'], 'Myanmar': ['MMR', 'EAS'], 'Equatorial Guinea': ['GNQ', 'SSF'], 'Central America': ['MCA', 'NA'], 'Nicaragua': ['NIC', 'LCN'], 'Congo, Dem. Rep.': ['COD', 'SSF'], 'Serbia': ['SRB', 'ECS'], 'Botswana': ['BWA', 'SSF'], 'United Kingdom': ['GBR', 'ECS'], 'Gambia, The': ['GMB', 'SSF'], 'High income: nonOECD': ['NOC', 'NA'], 'Greece': ['GRC', 'ECS'], 'Sri Lanka': ['LKA', 'SAS'], 'Lebanon': ['LBN', 'MEA'], 'Comoros': ['COM', 'SSF'], 'Heavily indebted poor countries (HIPC)': ['HPC', 'NA']} # todo
        self.inv_country_dict = {v[0]: k for k, v in self.country_dict.items()}

        self.all_indicators_data = {"IA": {"Canada": {"1961": "9984670", "1962": "9984670", "1963": "9984670", "1964": "9984670", "1965": "9984670", "1966": "9984670", "1967": "9984670", "1968": "9984670", "1969": "9984670", "1970": "9984670", "1971": "9984670", "1972": "9984670", "1973": "9984670", "1974": "9984670", "1975": "9984670", "1976": "9984670", "1977": "9984670", "1978": "9984670", "1979": "9984670", "1980": "9984670", "1981": "9984670", "1982": "9984670", "1983": "9984670", "1984": "9984670", "1985": "9984670", "1986": "9984670", "1987": "9984670", "1988": "9984670", "1989": "9984670", "1990": "9984670", "1991": "9984670", "1992": "9984670", "1993": "9984670", "1994": "9984670", "1995": "9984670", "1996": "9984670", "1997": "9984670", "1998": "9984670", "1999": "9984670", "2000": "9984670", "2001": "9984670", "2002": "9984670", "2003": "9984670", "2004": "9984670", "2005": "9984670", "2006": "9984670", "2007": "9984670", "2008": "9984670", "2009": "9984670", "2010": "9984670", "2011": "9984670", "2012": "9984670", "2013": "9984670", "2014": "9984670"}, "Sao Tome and Principe": {"1961": "960", "1962": "960", "1963": "960", "1964": "960", "1965": "960", "1966": "960", "1967": "960", "1968": "960", "1969": "960", "1970": "960", "1971": "960", "1972": "960", "1973": "960", "1974": "960", "1975": "960", "1976": "960", "1977": "960", "1978": "960", "1979": "960", "1980": "960", "1981": "960", "1982": "960", "1983": "960", "1984": "960", "1985": "960", "1986": "960", "1987": "960", "1988": "960", "1989": "960", "1990": "960", "1991": "960", "1992": "960", "1993": "960", "1994": "960", "1995": "960", "1996": "960", "1997": "960", "1998": "960", "1999": "960", "2000": "960", "2001": "960", "2002": "960", "2003": "960", "2004": "960", "2005": "960", "2006": "960", "2007": "960", "2008": "960", "2009": "960", "2010": "960", "2011": "960", "2012": "960", "2013": "960", "2014": "960"}, "Turkmenistan": {"1961": "488100", "1962": "488100", "1963": "488100", "1964": "488100", "1965": "488100", "1966": "488100", "1967": "488100", "1968": "488100", "1969": "488100", "1970": "488100", "1971": "488100", "1972": "488100", "1973": "488100", "1974": "488100", "1975": "488100", "1976": "488100", "1977": "488100", "1978": "488100", "1979": "488100", "1980": "488100", "1981": "488100", "1982": "488100", "1983": "488100", "1984": "488100", "1985": "488100", "1986": "488100", "1987": "488100", "1988": "488100", "1989": "488100", "1990": "488100", "1991": "488100", "1992": "488100", "1993": "488100", "1994": "488100", "1995": "488100", "1996": "488100", "1997": "488100", "1998": "488100", "1999": "488100", "2000": "488100", "2001": "488100", "2002": "488100", "2003": "488100", "2004": "488100", "2005": "488100", "2006": "488100", "2007": "488100", "2008": "488100", "2009": "488100", "2010": "488100", "2011": "488100", "2012": "488100", "2013": "488100", "2014": "488100"}, "Lao PDR": {"1961": "236800", "1962": "236800", "1963": "236800", "1964": "236800", "1965": "236800", "1966": "236800", "1967": "236800", "1968": "236800", "1969": "236800", "1970": "236800", "1971": "236800", "1972": "236800", "1973": "236800", "1974": "236800", "1975": "236800", "1976": "236800", "1977": "236800", "1978": "236800", "1979": "236800", "1980": "236800", "1981": "236800", "1982": "236800", "1983": "236800", "1984": "236800", "1985": "236800", "1986": "236800", "1987": "236800", "1988": "236800", "1989": "236800", "1990": "236800", "1991": "236800", "1992": "236800", "1993": "236800", "1994": "236800", "1995": "236800", "1996": "236800", "1997": "236800", "1998": "236800", "1999": "236800", "2000": "236800", "2001": "236800", "2002": "236800", "2003": "236800", "2004": "236800", "2005": "236800", "2006": "236800", "2007": "236800", "2008": "236800", "2009": "236800", "2010": "236800", "2011": "236800", "2012": "236800", "2013": "236800", "2014": "236800"}, "Arab World": {"1961": "13781751", "1962": "13781751", "1963": "13781751", "1964": "13781751", "1965": "13781751", "1966": "13781751", "1967": "13781751", "1968": "13781751", "1969": "13781751", "1970": "13781751", "1971": "13781751", "1972": "13781751", "1973": "13781751", "1974": "13781751", "1975": "13781751", "1976": "13781751", "1977": "13781751", "1978": "13781751", "1979": "13781751", "1980": "13781751", "1981": "13781751", "1982": "13781751", "1983": "13781751", "1984": "13781751", "1985": "13781751", "1986": "13781751", "1987": "13781751", "1988": "13781751", "1989": "13781751", "1990": "13781751", "1991": "13781751", "1992": "13781771", "1993": "13781771", "1994": "13781771", "1995": "13781771", "1996": "13781771", "1997": "13781771", "1998": "13781771", "1999": "13781771", "2000": "13781771", "2001": "13781771", "2002": "13781771", "2003": "13781781", "2004": "13781791", "2005": "13781801", "2006": "13781801", "2007": "13781811", "2008": "13781821", "2009": "13779281", "2010": "13779281", "2011": "13152828.5", "2012": "13152828.5", "2013": "13152828.5", "2014": "13152828.5"}, "Latin America & Caribbean (all income levels)": {"1961": "20452622.4", "1962": "20452622.4", "1963": "20452622.4", "1964": "20452622.4", "1965": "20452622.4", "1966": "20452622.4", "1967": "20452622.4", "1968": "20452622.4", "1969": "20452622.4", "1970": "20452622.4", "1971": "20452622.4", "1972": "20452622.4", "1973": "20452622.4", "1974": "20452622.4", "1975": "20452622.4", "1976": "20452622.4", "1977": "20452622.4", "1978": "20452622.4", "1979": "20452622.4", "1980": "20452532.4", "1981": "20452532.4", "1982": "20452532.4", "1983": "20452532.4", "1984": "20452532.4", "1985": "20452532.4", "1986": "20452532.4", "1987": "20452532.4", "1988": "20452532.4", "1989": "20452532.4", "1990": "20452532.4", "1991": "20452532.4", "1992": "20452532.4", "1993": "20452532.4", "1994": "20452532.4", "1995": "20452532.4", "1996": "20452532.4", "1997": "20452532.4", "1998": "20425342.4", "1999": "20425342.4", "2000": "20425342.4", "2001": "20425342.4", "2002": "20425342.4", "2003": "20425342.4", "2004": "20425342.4", "2005": "20425342.4", "2006": "20425342.4", "2007": "20425342.4", "2008": "20425342.4", "2009": "20425342.4", "2010": "20425334.4", "2011": "20425334.4", "2012": "20425332.4", "2013": "20425332.4", "2014": "20425332.4"}, "Cambodia": {"1961": "181040", "1962": "181040", "1963": "181040", "1964": "181040", "1965": "181040", "1966": "181040", "1967": "181040", "1968": "181040", "1969": "181040", "1970": "181040", "1971": "181040", "1972": "181040", "1973": "181040", "1974": "181040", "1975": "181040", "1976": "181040", "1977": "181040", "1978": "181040", "1979": "181040", "1980": "181040", "1981": "181040", "1982": "181040", "1983": "181040", "1984": "181040", "1985": "181040", "1986": "181040", "1987": "181040", "1988": "181040", "1989": "181040", "1990": "181040", "1991": "181040", "1992": "181040", "1993": "181040", "1994": "181040", "1995": "181040", "1996": "181040", "1997": "181040", "1998": "181040", "1999": "181040", "2000": "181040", "2001": "181040", "2002": "181040", "2003": "181040", "2004": "181040", "2005": "181040", "2006": "181040", "2007": "181040", "2008": "181040", "2009": "181040", "2010": "181040", "2011": "181040", "2012": "181040", "2013": "181040", "2014": "181040"}, "Ethiopia": {"1961": "1221900", "1962": "1221900", "1963": "1221900", "1964": "1221900", "1965": "1221900", "1966": "1221900", "1967": "1221900", "1968": "1221900", "1969": "1221900", "1970": "1221900", "1971": "1221900", "1972": "1221900", "1973": "1221900", "1974": "1221900", "1975": "1221900", "1976": "1221900", "1977": "1221900", "1978": "1221900", "1979": "1221900", "1980": "1221900", "1981": "1221900", "1982": "1221900", "1983": "1221900", "1984": "1221900", "1985": "1221900", "1986": "1221900", "1987": "1221900", "1988": "1221900", "1989": "1221900", "1990": "1221900", "1991": "1221900", "1992": "1221900", "1993": "1104300", "1994": "1104300", "1995": "1104300", "1996": "1104300", "1997": "1104300", "1998": "1104300", "1999": "1104300", "2000": "1104300", "2001": "1104300", "2002": "1104300", "2003": "1104300", "2004": "1104300", "2005": "1104300", "2006": "1104300", "2007": "1104300", "2008": "1104300", "2009": "1104300", "2010": "1104300", "2011": "1104300", "2012": "1104300", "2013": "1104300", "2014": "1104300"}, "Aruba": {"1961": "180", "1962": "180", "1963": "180", "1964": "180", "1965": "180", "1966": "180", "1967": "180", "1968": "180", "1969": "180", "1970": "180", "1971": "180", "1972": "180", "1973": "180", "1974": "180", "1975": "180", "1976": "180", "1977": "180", "1978": "180", "1979": "180", "1980": "180", "1981": "180", "1982": "180", "1983": "180", "1984": "180", "1985": "180", "1986": "180", "1987": "180", "1988": "180", "1989": "180", "1990": "180", "1991": "180", "1992": "180", "1993": "180", "1994": "180", "1995": "180", "1996": "180", "1997": "180", "1998": "180", "1999": "180", "2000": "180", "2001": "180", "2002": "180", "2003": "180", "2004": "180", "2005": "180", "2006": "180", "2007": "180", "2008": "180", "2009": "180", "2010": "180", "2011": "180", "2012": "180", "2013": "180", "2014": "180"}, "Swaziland": {"1961": "17360", "1962": "17360", "1963": "17360", "1964": "17360", "1965": "17360", "1966": "17360", "1967": "17360", "1968": "17360", "1969": "17360", "1970": "17360", "1971": "17360", "1972": "17360", "1973": "17360", "1974": "17360", "1975": "17360", "1976": "17360", "1977": "17360", "1978": "17360", "1979": "17360", "1980": "17360", "1981": "17360", "1982": "17360", "1983": "17360", "1984": "17360", "1985": "17360", "1986": "17360", "1987": "17360", "1988": "17360", "1989": "17360", "1990": "17360", "1991": "17360", "1992": "17360", "1993": "17360", "1994": "17360", "1995": "17360", "1996": "17360", "1997": "17360", "1998": "17360", "1999": "17360", "2000": "17360", "2001": "17360", "2002": "17360", "2003": "17360", "2004": "17360", "2005": "17360", "2006": "17360", "2007": "17360", "2008": "17360", "2009": "17360", "2010": "17360", "2011": "17360", "2012": "17360", "2013": "17360", "2014": "17360"}, "South Asia": {"1961": "5144770", "1962": "5144770", "1963": "5144770", "1964": "5144770", "1965": "5144770", "1966": "5144770", "1967": "5144770", "1968": "5144770", "1969": "5144770", "1970": "5144770", "1971": "5144770", "1972": "5144770", "1973": "5144770", "1974": "5144770", "1975": "5144770", "1976": "5144770", "1977": "5144770", "1978": "5144770", "1979": "5144770", "1980": "5144770", "1981": "5144770", "1982": "5144770", "1983": "5144770", "1984": "5144770", "1985": "5144770", "1986": "5144770", "1987": "5144770", "1988": "5144770", "1989": "5144770", "1990": "5144770", "1991": "5144770", "1992": "5144770", "1993": "5144770", "1994": "5137847", "1995": "5137847", "1996": "5137847", "1997": "5137847", "1998": "5137847", "1999": "5137847", "2000": "5137847", "2001": "5137847", "2002": "5137847", "2003": "5137847", "2004": "5136164", "2005": "5136164", "2006": "5136164", "2007": "5136164", "2008": "5136164", "2009": "5136164", "2010": "5136164", "2011": "5136164", "2012": "5136164", "2013": "5136164", "2014": "5136164"}, "Argentina": {"1961": "2780400", "1962": "2780400", "1963": "2780400", "1964": "2780400", "1965": "2780400", "1966": "2780400", "1967": "2780400", "1968": "2780400", "1969": "2780400", "1970": "2780400", "1971": "2780400", "1972": "2780400", "1973": "2780400", "1974": "2780400", "1975": "2780400", "1976": "2780400", "1977": "2780400", "1978": "2780400", "1979": "2780400", "1980": "2780400", "1981": "2780400", "1982": "2780400", "1983": "2780400", "1984": "2780400", "1985": "2780400", "1986": "2780400", "1987": "2780400", "1988": "2780400", "1989": "2780400", "1990": "2780400", "1991": "2780400", "1992": "2780400", "1993": "2780400", "1994": "2780400", "1995": "2780400", "1996": "2780400", "1997": "2780400", "1998": "2780400", "1999": "2780400", "2000": "2780400", "2001": "2780400", "2002": "2780400", "2003": "2780400", "2004": "2780400", "2005": "2780400", "2006": "2780400", "2007": "2780400", "2008": "2780400", "2009": "2780400", "2010": "2780400", "2011": "2780400", "2012": "2780400", "2013": "2780400", "2014": "2780400"}, "Bolivia": {"1961": "1098580", "1962": "1098580", "1963": "1098580", "1964": "1098580", "1965": "1098580", "1966": "1098580", "1967": "1098580", "1968": "1098580", "1969": "1098580", "1970": "1098580", "1971": "1098580", "1972": "1098580", "1973": "1098580", "1974": "1098580", "1975": "1098580", "1976": "1098580", "1977": "1098580", "1978": "1098580", "1979": "1098580", "1980": "1098580", "1981": "1098580", "1982": "1098580", "1983": "1098580", "1984": "1098580", "1985": "1098580", "1986": "1098580", "1987": "1098580", "1988": "1098580", "1989": "1098580", "1990": "1098580", "1991": "1098580", "1992": "1098580", "1993": "1098580", "1994": "1098580", "1995": "1098580", "1996": "1098580", "1997": "1098580", "1998": "1098580", "1999": "1098580", "2000": "1098580", "2001": "1098580", "2002": "1098580", "2003": "1098580", "2004": "1098580", "2005": "1098580", "2006": "1098580", "2007": "1098580", "2008": "1098580", "2009": "1098580", "2010": "1098580", "2011": "1098580", "2012": "1098580", "2013": "1098580", "2014": "1098580"}, "Bahamas, The": {"1961": "13880", "1962": "13880", "1963": "13880", "1964": "13880", "1965": "13880", "1966": "13880", "1967": "13880", "1968": "13880", "1969": "13880", "1970": "13880", "1971": "13880", "1972": "13880", "1973": "13880", "1974": "13880", "1975": "13880", "1976": "13880", "1977": "13880", "1978": "13880", "1979": "13880", "1980": "13880", "1981": "13880", "1982": "13880", "1983": "13880", "1984": "13880", "1985": "13880", "1986": "13880", "1987": "13880", "1988": "13880", "1989": "13880", "1990": "13880", "1991": "13880", "1992": "13880", "1993": "13880", "1994": "13880", "1995": "13880", "1996": "13880", "1997": "13880", "1998": "13880", "1999": "13880", "2000": "13880", "2001": "13880", "2002": "13880", "2003": "13880", "2004": "13880", "2005": "13880", "2006": "13880", "2007": "13880", "2008": "13880", "2009": "13880", "2010": "13880", "2011": "13880", "2012": "13880", "2013": "13880", "2014": "13880"}, "Burkina Faso": {"1961": "274220", "1962": "274220", "1963": "274220", "1964": "274220", "1965": "274220", "1966": "274220", "1967": "274220", "1968": "274220", "1969": "274220", "1970": "274220", "1971": "274220", "1972": "274220", "1973": "274220", "1974": "274220", "1975": "274220", "1976": "274220", "1977": "274220", "1978": "274220", "1979": "274220", "1980": "274220", "1981": "274220", "1982": "274220", "1983": "274220", "1984": "274220", "1985": "274220", "1986": "274220", "1987": "274220", "1988": "274220", "1989": "274220", "1990": "274220", "1991": "274220", "1992": "274220", "1993": "274220", "1994": "274220", "1995": "274220", "1996": "274220", "1997": "274220", "1998": "274220", "1999": "274220", "2000": "274220", "2001": "274220", "2002": "274220", "2003": "274220", "2004": "274220", "2005": "274220", "2006": "274220", "2007": "274220", "2008": "274220", "2009": "274220", "2010": "274220", "2011": "274220", "2012": "274220", "2013": "274220", "2014": "274220"}, "OECD members": {"1961": "35962735", "1962": "35962735", "1963": "35962735", "1964": "35962735", "1965": "35962735", "1966": "35962735", "1967": "35962735", "1968": "35962735", "1969": "35962735", "1970": "35962735", "1971": "35962735", "1972": "35962735", "1973": "35962735", "1974": "35962735", "1975": "35962735", "1976": "35962735", "1977": "35962735", "1978": "35962735", "1979": "35962735", "1980": "35962735", "1981": "35962735", "1982": "35962735", "1983": "35962735", "1984": "35962735", "1985": "35962735", "1986": "35962735", "1987": "35962735", "1988": "35962735", "1989": "35962735", "1990": "35962735", "1991": "35962735", "1992": "35962735", "1993": "35962755", "1994": "35962765", "1995": "35962785", "1996": "35962795", "1997": "35962795", "1998": "35962795", "1999": "35962795", "2000": "35997865", "2001": "35998245", "2002": "35998615", "2003": "35998685", "2004": "35998725", "2005": "35998775", "2006": "35999105", "2007": "35999135", "2008": "36198751", "2009": "36198972", "2010": "36199339", "2011": "36199316", "2012": "36196595", "2013": "36196595", "2014": "36196595"}, "Bahrain": {"1961": "690", "1962": "690", "1963": "690", "1964": "690", "1965": "690", "1966": "690", "1967": "690", "1968": "690", "1969": "690", "1970": "690", "1971": "690", "1972": "690", "1973": "690", "1974": "690", "1975": "690", "1976": "690", "1977": "690", "1978": "690", "1979": "690", "1980": "690", "1981": "690", "1982": "690", "1983": "690", "1984": "690", "1985": "690", "1986": "690", "1987": "690", "1988": "690", "1989": "690", "1990": "690", "1991": "690", "1992": "710", "1993": "710", "1994": "710", "1995": "710", "1996": "710", "1997": "710", "1998": "710", "1999": "710", "2000": "710", "2001": "710", "2002": "710", "2003": "720", "2004": "730", "2005": "740", "2006": "740", "2007": "750", "2008": "760", "2009": "760", "2010": "760", "2011": "760", "2012": "760", "2013": "760", "2014": "760"}, "Saudi Arabia": {"1961": "2149690", "1962": "2149690", "1963": "2149690", "1964": "2149690", "1965": "2149690", "1966": "2149690", "1967": "2149690", "1968": "2149690", "1969": "2149690", "1970": "2149690", "1971": "2149690", "1972": "2149690", "1973": "2149690", "1974": "2149690", "1975": "2149690", "1976": "2149690", "1977": "2149690", "1978": "2149690", "1979": "2149690", "1980": "2149690", "1981": "2149690", "1982": "2149690", "1983": "2149690", "1984": "2149690", "1985": "2149690", "1986": "2149690", "1987": "2149690", "1988": "2149690", "1989": "2149690", "1990": "2149690", "1991": "2149690", "1992": "2149690", "1993": "2149690", "1994": "2149690", "1995": "2149690", "1996": "2149690", "1997": "2149690", "1998": "2149690", "1999": "2149690", "2000": "2149690", "2001": "2149690", "2002": "2149690", "2003": "2149690", "2004": "2149690", "2005": "2149690", "2006": "2149690", "2007": "2149690", "2008": "2149690", "2009": "2149690", "2010": "2149690", "2011": "2149690", "2012": "2149690", "2013": "2149690", "2014": "2149690"}, "Rwanda": {"1961": "26340", "1962": "26340", "1963": "26340", "1964": "26340", "1965": "26340", "1966": "26340", "1967": "26340", "1968": "26340", "1969": "26340", "1970": "26340", "1971": "26340", "1972": "26340", "1973": "26340", "1974": "26340", "1975": "26340", "1976": "26340", "1977": "26340", "1978": "26340", "1979": "26340", "1980": "26340", "1981": "26340", "1982": "26340", "1983": "26340", "1984": "26340", "1985": "26340", "1986": "26340", "1987": "26340", "1988": "26340", "1989": "26340", "1990": "26340", "1991": "26340", "1992": "26340", "1993": "26340", "1994": "26340", "1995": "26340", "1996": "26340", "1997": "26340", "1998": "26340", "1999": "26340", "2000": "26340", "2001": "26340", "2002": "26340", "2003": "26340", "2004": "26340", "2005": "26340", "2006": "26340", "2007": "26340", "2008": "26340", "2009": "26340", "2010": "26340", "2011": "26340", "2012": "26340", "2013": "26340", "2014": "26340"}, "Sub-Saharan Africa (IFC classification)": {}, "Togo": {"1961": "56790", "1962": "56790", "1963": "56790", "1964": "56790", "1965": "56790", "1966": "56790", "1967": "56790", "1968": "56790", "1969": "56790", "1970": "56790", "1971": "56790", "1972": "56790", "1973": "56790", "1974": "56790", "1975": "56790", "1976": "56790", "1977": "56790", "1978": "56790", "1979": "56790", "1980": "56790", "1981": "56790", "1982": "56790", "1983": "56790", "1984": "56790", "1985": "56790", "1986": "56790", "1987": "56790", "1988": "56790", "1989": "56790", "1990": "56790", "1991": "56790", "1992": "56790", "1993": "56790", "1994": "56790", "1995": "56790", "1996": "56790", "1997": "56790", "1998": "56790", "1999": "56790", "2000": "56790", "2001": "56790", "2002": "56790", "2003": "56790", "2004": "56790", "2005": "56790", "2006": "56790", "2007": "56790", "2008": "56790", "2009": "56790", "2010": "56790", "2011": "56790", "2012": "56790", "2013": "56790", "2014": "56790"}, "Thailand": {"1961": "513120", "1962": "513120", "1963": "513120", "1964": "513120", "1965": "513120", "1966": "513120", "1967": "513120", "1968": "513120", "1969": "513120", "1970": "513120", "1971": "513120", "1972": "513120", "1973": "513120", "1974": "513120", "1975": "513120", "1976": "513120", "1977": "513120", "1978": "513120", "1979": "513120", "1980": "513120", "1981": "513120", "1982": "513120", "1983": "513120", "1984": "513120", "1985": "513120", "1986": "513120", "1987": "513120", "1988": "513120", "1989": "513120", "1990": "513120", "1991": "513120", "1992": "513120", "1993": "513120", "1994": "513120", "1995": "513120", "1996": "513120", "1997": "513120", "1998": "513120", "1999": "513120", "2000": "513120", "2001": "513120", "2002": "513120", "2003": "513120", "2004": "513120", "2005": "513120", "2006": "513120", "2007": "513120", "2008": "513120", "2009": "513120", "2010": "513120", "2011": "513120", "2012": "513120", "2013": "513120", "2014": "513120"}, "Japan": {"1961": "377800", "1962": "377800", "1963": "377800", "1964": "377800", "1965": "377800", "1966": "377800", "1967": "377800", "1968": "377800", "1969": "377800", "1970": "377800", "1971": "377800", "1972": "377800", "1973": "377800", "1974": "377800", "1975": "377800", "1976": "377800", "1977": "377800", "1978": "377800", "1979": "377800", "1980": "377800", "1981": "377800", "1982": "377800", "1983": "377800", "1984": "377800", "1985": "377800", "1986": "377800", "1987": "377800", "1988": "377800", "1989": "377800", "1990": "377800", "1991": "377800", "1992": "377800", "1993": "377800", "1994": "377800", "1995": "377800", "1996": "377800", "1997": "377800", "1998": "377800", "1999": "377800", "2000": "377800", "2001": "377880", "2002": "377890", "2003": "377900", "2004": "377910", "2005": "377910", "2006": "377920", "2007": "377930", "2008": "377940", "2009": "377947", "2010": "377950", "2011": "377955", "2012": "377960", "2013": "377960", "2014": "377960"}, "Channel Islands": {"1961": "194", "1962": "194", "1963": "194", "1964": "194", "1965": "194", "1966": "194", "1967": "194", "1968": "194", "1969": "194", "1970": "194", "1971": "194", "1972": "194", "1973": "194", "1974": "194", "1975": "194", "1976": "194", "1977": "194", "1978": "194", "1979": "194", "1980": "194", "1981": "194", "1982": "194", "1983": "194", "1984": "194", "1985": "194", "1986": "194", "1987": "194", "1988": "194", "1989": "194", "1990": "194", "1991": "194", "1992": "194", "1993": "194", "1994": "194", "1995": "194", "1996": "194", "1997": "194", "1998": "194", "1999": "194", "2000": "194", "2001": "194", "2002": "194", "2003": "194", "2004": "194", "2005": "194", "2006": "194", "2007": "194", "2008": "194", "2009": "194", "2010": "190", "2011": "190", "2012": "190", "2013": "190", "2014": "190"}, "American Samoa": {"1961": "200", "1962": "200", "1963": "200", "1964": "200", "1965": "200", "1966": "200", "1967": "200", "1968": "200", "1969": "200", "1970": "200", "1971": "200", "1972": "200", "1973": "200", "1974": "200", "1975": "200", "1976": "200", "1977": "200", "1978": "200", "1979": "200", "1980": "200", "1981": "200", "1982": "200", "1983": "200", "1984": "200", "1985": "200", "1986": "200", "1987": "200", "1988": "200", "1989": "200", "1990": "200", "1991": "200", "1992": "200", "1993": "200", "1994": "200", "1995": "200", "1996": "200", "1997": "200", "1998": "200", "1999": "200", "2000": "200", "2001": "200", "2002": "200", "2003": "200", "2004": "200", "2005": "200", "2006": "200", "2007": "200", "2008": "200", "2009": "200", "2010": "200", "2011": "200", "2012": "200", "2013": "200", "2014": "200"}, "Northern Mariana Islands": {"1991": "460", "1992": "460", "1993": "460", "1994": "460", "1995": "460", "1996": "460", "1997": "460", "1998": "460", "1999": "460", "2000": "460", "2001": "460", "2002": "460", "2003": "460", "2004": "460", "2005": "460", "2006": "460", "2007": "460", "2008": "460", "2009": "460", "2010": "460", "2011": "460", "2012": "460", "2013": "460", "2014": "460"}, "Slovenia": {"1961": "20270", "1962": "20270", "1963": "20270", "1964": "20270", "1965": "20270", "1966": "20270", "1967": "20270", "1968": "20270", "1969": "20270", "1970": "20270", "1971": "20270", "1972": "20270", "1973": "20270", "1974": "20270", "1975": "20270", "1976": "20270", "1977": "20270", "1978": "20270", "1979": "20270", "1980": "20270", "1981": "20270", "1982": "20270", "1983": "20270", "1984": "20270", "1985": "20270", "1986": "20270", "1987": "20270", "1988": "20270", "1989": "20270", "1990": "20270", "1991": "20270", "1992": "20270", "1993": "20270", "1994": "20270", "1995": "20270", "1996": "20270", "1997": "20270", "1998": "20270", "1999": "20270", "2000": "20270", "2001": "20270", "2002": "20270", "2003": "20270", "2004": "20270", "2005": "20270", "2006": "20270", "2007": "20270", "2008": "20270", "2009": "20270", "2010": "20270", "2011": "20270", "2012": "20270", "2013": "20270", "2014": "20270"}, "Guatemala": {"1961": "108890", "1962": "108890", "1963": "108890", "1964": "108890", "1965": "108890", "1966": "108890", "1967": "108890", "1968": "108890", "1969": "108890", "1970": "108890", "1971": "108890", "1972": "108890", "1973": "108890", "1974": "108890", "1975": "108890", "1976": "108890", "1977": "108890", "1978": "108890", "1979": "108890", "1980": "108890", "1981": "108890", "1982": "108890", "1983": "108890", "1984": "108890", "1985": "108890", "1986": "108890", "1987": "108890", "1988": "108890", "1989": "108890", "1990": "108890", "1991": "108890", "1992": "108890", "1993": "108890", "1994": "108890", "1995": "108890", "1996": "108890", "1997": "108890", "1998": "108890", "1999": "108890", "2000": "108890", "2001": "108890", "2002": "108890", "2003": "108890", "2004": "108890", "2005": "108890", "2006": "108890", "2007": "108890", "2008": "108890", "2009": "108890", "2010": "108890", "2011": "108890", "2012": "108890", "2013": "108890", "2014": "108890"}, "Bosnia and Herzegovina": {"1961": "51210", "1962": "51210", "1963": "51210", "1964": "51210", "1965": "51210", "1966": "51210", "1967": "51210", "1968": "51210", "1969": "51210", "1970": "51210", "1971": "51210", "1972": "51210", "1973": "51210", "1974": "51210", "1975": "51210", "1976": "51210", "1977": "51210", "1978": "51210", "1979": "51210", "1980": "51210", "1981": "51210", "1982": "51210", "1983": "51210", "1984": "51210", "1985": "51210", "1986": "51210", "1987": "51210", "1988": "51210", "1989": "51210", "1990": "51210", "1991": "51210", "1992": "51210", "1993": "51210", "1994": "51210", "1995": "51210", "1996": "51210", "1997": "51210", "1998": "51210", "1999": "51210", "2000": "51210", "2001": "51210", "2002": "51210", "2003": "51210", "2004": "51210", "2005": "51210", "2006": "51210", "2007": "51210", "2008": "51210", "2009": "51210", "2010": "51210", "2011": "51210", "2012": "51210", "2013": "51210", "2014": "51210"}, "Kuwait": {"1961": "17820", "1962": "17820", "1963": "17820", "1964": "17820", "1965": "17820", "1966": "17820", "1967": "17820", "1968": "17820", "1969": "17820", "1970": "17820", "1971": "17820", "1972": "17820", "1973": "17820", "1974": "17820", "1975": "17820", "1976": "17820", "1977": "17820", "1978": "17820", "1979": "17820", "1980": "17820", "1981": "17820", "1982": "17820", "1983": "17820", "1984": "17820", "1985": "17820", "1986": "17820", "1987": "17820", "1988": "17820", "1989": "17820", "1990": "17820", "1991": "17820", "1992": "17820", "1993": "17820", "1994": "17820", "1995": "17820", "1996": "17820", "1997": "17820", "1998": "17820", "1999": "17820", "2000": "17820", "2001": "17820", "2002": "17820", "2003": "17820", "2004": "17820", "2005": "17820", "2006": "17820", "2007": "17820", "2008": "17820", "2009": "17820", "2010": "17820", "2011": "17820", "2012": "17820", "2013": "17820", "2014": "17820"}, "Russian Federation": {"1961": "17098240", "1962": "17098240", "1963": "17098240", "1964": "17098240", "1965": "17098240", "1966": "17098240", "1967": "17098240", "1968": "17098240", "1969": "17098240", "1970": "17098240", "1971": "17098240", "1972": "17098240", "1973": "17098240", "1974": "17098240", "1975": "17098240", "1976": "17098240", "1977": "17098240", "1978": "17098240", "1979": "17098240", "1980": "17098240", "1981": "17098240", "1982": "17098240", "1983": "17098240", "1984": "17098240", "1985": "17098240", "1986": "17098240", "1987": "17098240", "1988": "17098240", "1989": "17098240", "1990": "17098240", "1991": "17098240", "1992": "17098240", "1993": "17098240", "1994": "17098240", "1995": "17098240", "1996": "17098240", "1997": "17098240", "1998": "17098240", "1999": "17098240", "2000": "17098240", "2001": "17098240", "2002": "17098240", "2003": "17098240", "2004": "17098240", "2005": "17098240", "2006": "17098240", "2007": "17098240", "2008": "17098240", "2009": "17098240", "2010": "17098240", "2011": "17098240", "2012": "17098240", "2013": "17098240", "2014": "17098240"}, "Jordan": {"1961": "88780", "1962": "88780", "1963": "88780", "1964": "88780", "1965": "88780", "1966": "88780", "1967": "88780", "1968": "88780", "1969": "88780", "1970": "88780", "1971": "88780", "1972": "88780", "1973": "88780", "1974": "88780", "1975": "88780", "1976": "88780", "1977": "88780", "1978": "88780", "1979": "88780", "1980": "88780", "1981": "88780", "1982": "88780", "1983": "88780", "1984": "88780", "1985": "88780", "1986": "88780", "1987": "88780", "1988": "88780", "1989": "88780", "1990": "88780", "1991": "88780", "1992": "88780", "1993": "88780", "1994": "88780", "1995": "88780", "1996": "88780", "1997": "88780", "1998": "88780", "1999": "88780", "2000": "88780", "2001": "88780", "2002": "88780", "2003": "88780", "2004": "88780", "2005": "88780", "2006": "88780", "2007": "88780", "2008": "88780", "2009": "89320", "2010": "89320", "2011": "89320", "2012": "89320", "2013": "89320", "2014": "89320"}, "St. Lucia": {"1961": "620", "1962": "620", "1963": "620", "1964": "620", "1965": "620", "1966": "620", "1967": "620", "1968": "620", "1969": "620", "1970": "620", "1971": "620", "1972": "620", "1973": "620", "1974": "620", "1975": "620", "1976": "620", "1977": "620", "1978": "620", "1979": "620", "1980": "620", "1981": "620", "1982": "620", "1983": "620", "1984": "620", "1985": "620", "1986": "620", "1987": "620", "1988": "620", "1989": "620", "1990": "620", "1991": "620", "1992": "620", "1993": "620", "1994": "620", "1995": "620", "1996": "620", "1997": "620", "1998": "620", "1999": "620", "2000": "620", "2001": "620", "2002": "620", "2003": "620", "2004": "620", "2005": "620", "2006": "620", "2007": "620", "2008": "620", "2009": "620", "2010": "620", "2011": "620", "2012": "620", "2013": "620", "2014": "620"}, "Congo, Rep.": {"1961": "342000", "1962": "342000", "1963": "342000", "1964": "342000", "1965": "342000", "1966": "342000", "1967": "342000", "1968": "342000", "1969": "342000", "1970": "342000", "1971": "342000", "1972": "342000", "1973": "342000", "1974": "342000", "1975": "342000", "1976": "342000", "1977": "342000", "1978": "342000", "1979": "342000", "1980": "342000", "1981": "342000", "1982": "342000", "1983": "342000", "1984": "342000", "1985": "342000", "1986": "342000", "1987": "342000", "1988": "342000", "1989": "342000", "1990": "342000", "1991": "342000", "1992": "342000", "1993": "342000", "1994": "342000", "1995": "342000", "1996": "342000", "1997": "342000", "1998": "342000", "1999": "342000", "2000": "342000", "2001": "342000", "2002": "342000", "2003": "342000", "2004": "342000", "2005": "342000", "2006": "342000", "2007": "342000", "2008": "342000", "2009": "342000", "2010": "342000", "2011": "342000", "2012": "342000", "2013": "342000", "2014": "342000"}, "North Africa": {}, "Dominica": {"1961": "750", "1962": "750", "1963": "750", "1964": "750", "1965": "750", "1966": "750", "1967": "750", "1968": "750", "1969": "750", "1970": "750", "1971": "750", "1972": "750", "1973": "750", "1974": "750", "1975": "750", "1976": "750", "1977": "750", "1978": "750", "1979": "750", "1980": "750", "1981": "750", "1982": "750", "1983": "750", "1984": "750", "1985": "750", "1986": "750", "1987": "750", "1988": "750", "1989": "750", "1990": "750", "1991": "750", "1992": "750", "1993": "750", "1994": "750", "1995": "750", "1996": "750", "1997": "750", "1998": "750", "1999": "750", "2000": "750", "2001": "750", "2002": "750", "2003": "750", "2004": "750", "2005": "750", "2006": "750", "2007": "750", "2008": "750", "2009": "750", "2010": "750", "2011": "750", "2012": "750", "2013": "750", "2014": "750"}, "Liberia": {"1961": "111370", "1962": "111370", "1963": "111370", "1964": "111370", "1965": "111370", "1966": "111370", "1967": "111370", "1968": "111370", "1969": "111370", "1970": "111370", "1971": "111370", "1972": "111370", "1973": "111370", "1974": "111370", "1975": "111370", "1976": "111370", "1977": "111370", "1978": "111370", "1979": "111370", "1980": "111370", "1981": "111370", "1982": "111370", "1983": "111370", "1984": "111370", "1985": "111370", "1986": "111370", "1987": "111370", "1988": "111370", "1989": "111370", "1990": "111370", "1991": "111370", "1992": "111370", "1993": "111370", "1994": "111370", "1995": "111370", "1996": "111370", "1997": "111370", "1998": "111370", "1999": "111370", "2000": "111370", "2001": "111370", "2002": "111370", "2003": "111370", "2004": "111370", "2005": "111370", "2006": "111370", "2007": "111370", "2008": "111370", "2009": "111370", "2010": "111370", "2011": "111370", "2012": "111370", "2013": "111370", "2014": "111370"}, "Maldives": {"1961": "300", "1962": "300", "1963": "300", "1964": "300", "1965": "300", "1966": "300", "1967": "300", "1968": "300", "1969": "300", "1970": "300", "1971": "300", "1972": "300", "1973": "300", "1974": "300", "1975": "300", "1976": "300", "1977": "300", "1978": "300", "1979": "300", "1980": "300", "1981": "300", "1982": "300", "1983": "300", "1984": "300", "1985": "300", "1986": "300", "1987": "300", "1988": "300", "1989": "300", "1990": "300", "1991": "300", "1992": "300", "1993": "300", "1994": "300", "1995": "300", "1996": "300", "1997": "300", "1998": "300", "1999": "300", "2000": "300", "2001": "300", "2002": "300", "2003": "300", "2004": "300", "2005": "300", "2006": "300", "2007": "300", "2008": "300", "2009": "300", "2010": "300", "2011": "300", "2012": "300", "2013": "300", "2014": "300"}, "East Asia & Pacific (all income levels)": {"1961": "24822890", "1962": "24822890", "1963": "24822890", "1964": "24822890", "1965": "24822890", "1966": "24822890", "1967": "24822890", "1968": "24822890", "1969": "24822890", "1970": "24822890", "1971": "24822890", "1972": "24822890", "1973": "24822890", "1974": "24822890", "1975": "24822890", "1976": "24822890", "1977": "24820770", "1978": "24820770", "1979": "24822810", "1980": "24822890", "1981": "24822890", "1982": "24822890", "1983": "24822890", "1984": "24822890", "1985": "24822890", "1986": "24822890", "1987": "24821550", "1988": "24821560", "1989": "24821560", "1990": "24822230", "1991": "24824060", "1992": "24824090", "1993": "24824110", "1994": "24824110", "1995": "24824110", "1996": "24824110", "1997": "24824110", "1998": "24824110", "1999": "24824110", "2000": "24822240", "2001": "24822610.2", "2002": "24822725.2", "2003": "24822766.7", "2004": "24822803.5", "2005": "24824730.8", "2006": "24824776", "2007": "24824827", "2008": "24824791", "2009": "24824868.5", "2010": "24824909.7", "2011": "24824910.9", "2012": "24825037.9", "2013": "24825037.9", "2014": "24825037.9"}, "Southern Cone": {}, "Lithuania": {"1961": "65300", "1962": "65300", "1963": "65300", "1964": "65300", "1965": "65300", "1966": "65300", "1967": "65300", "1968": "65300", "1969": "65300", "1970": "65300", "1971": "65300", "1972": "65300", "1973": "65300", "1974": "65300", "1975": "65300", "1976": "65300", "1977": "65300", "1978": "65300", "1979": "65300", "1980": "65300", "1981": "65300", "1982": "65300", "1983": "65300", "1984": "65300", "1985": "65300", "1986": "65300", "1987": "65300", "1988": "65300", "1989": "65300", "1990": "65300", "1991": "65300", "1992": "65300", "1993": "65300", "1994": "65300", "1995": "65300", "1996": "65300", "1997": "65300", "1998": "65300", "1999": "65300", "2000": "65300", "2001": "65300", "2002": "65300", "2003": "65300", "2004": "65300", "2005": "65300", "2006": "65300", "2007": "65300", "2008": "65300", "2009": "65300", "2010": "65300", "2011": "65300", "2012": "65300", "2013": "65300", "2014": "65300"}, "Tanzania": {"1961": "947300", "1962": "947300", "1963": "947300", "1964": "947300", "1965": "947300", "1966": "947300", "1967": "947300", "1968": "947300", "1969": "947300", "1970": "947300", "1971": "947300", "1972": "947300", "1973": "947300", "1974": "947300", "1975": "947300", "1976": "947300", "1977": "947300", "1978": "947300", "1979": "947300", "1980": "947300", "1981": "947300", "1982": "947300", "1983": "947300", "1984": "947300", "1985": "947300", "1986": "947300", "1987": "947300", "1988": "947300", "1989": "947300", "1990": "947300", "1991": "947300", "1992": "947300", "1993": "947300", "1994": "947300", "1995": "947300", "1996": "947300", "1997": "947300", "1998": "947300", "1999": "947300", "2000": "947300", "2001": "947300", "2002": "947300", "2003": "947300", "2004": "947300", "2005": "947300", "2006": "947300", "2007": "947300", "2008": "947300", "2009": "947300", "2010": "947300", "2011": "947300", "2012": "947300", "2013": "947300", "2014": "947300"}, "Vietnam": {"1961": "331690", "1962": "331690", "1963": "331690", "1964": "331690", "1965": "331690", "1966": "331690", "1967": "331690", "1968": "331690", "1969": "331690", "1970": "331690", "1971": "331690", "1972": "331690", "1973": "331690", "1974": "331690", "1975": "331690", "1976": "331690", "1977": "329570", "1978": "329570", "1979": "331610", "1980": "331690", "1981": "331690", "1982": "331690", "1983": "331690", "1984": "331690", "1985": "331690", "1986": "331690", "1987": "330350", "1988": "330360", "1989": "330360", "1990": "331030", "1991": "331060", "1992": "331090", "1993": "331110", "1994": "331110", "1995": "331110", "1996": "331110", "1997": "331110", "1998": "331110", "1999": "331110", "2000": "329240", "2001": "329250", "2002": "329300", "2003": "329310", "2004": "329314", "2005": "331212", "2006": "331212", "2007": "331212", "2008": "331051", "2009": "331051", "2010": "330957", "2011": "330951", "2012": "330951", "2013": "330951", "2014": "330951"}, "Cabo Verde": {"1961": "4030", "1962": "4030", "1963": "4030", "1964": "4030", "1965": "4030", "1966": "4030", "1967": "4030", "1968": "4030", "1969": "4030", "1970": "4030", "1971": "4030", "1972": "4030", "1973": "4030", "1974": "4030", "1975": "4030", "1976": "4030", "1977": "4030", "1978": "4030", "1979": "4030", "1980": "4030", "1981": "4030", "1982": "4030", "1983": "4030", "1984": "4030", "1985": "4030", "1986": "4030", "1987": "4030", "1988": "4030", "1989": "4030", "1990": "4030", "1991": "4030", "1992": "4030", "1993": "4030", "1994": "4030", "1995": "4030", "1996": "4030", "1997": "4030", "1998": "4030", "1999": "4030", "2000": "4030", "2001": "4030", "2002": "4030", "2003": "4030", "2004": "4030", "2005": "4030", "2006": "4030", "2007": "4030", "2008": "4030", "2009": "4030", "2010": "4030", "2011": "4030", "2012": "4030", "2013": "4030", "2014": "4030"}, "Greenland": {"1961": "341700", "1962": "341700", "1963": "341700", "1964": "341700", "1965": "341700", "1966": "341700", "1967": "341700", "1968": "341700", "1969": "341700", "1970": "341700", "1971": "341700", "1972": "341700", "1973": "341700", "1974": "341700", "1975": "341700", "1976": "341700", "1977": "341700", "1978": "341700", "1979": "341700", "1980": "341700", "1981": "341700", "1982": "341700", "1983": "341700", "1984": "341700", "1985": "341700", "1986": "341700", "1987": "341700", "1988": "341700", "1989": "341700", "1990": "341700", "1991": "341700", "1992": "341700", "1993": "341700", "1994": "341700", "1995": "341700", "1996": "341700", "1997": "410450", "1998": "410450", "1999": "410450", "2000": "410450", "2001": "410450", "2002": "410450", "2003": "410450", "2004": "410450", "2005": "410450", "2006": "410450", "2007": "410450", "2008": "410450", "2009": "410450", "2010": "410450", "2011": "410450", "2012": "410450", "2013": "410450", "2014": "410450"}, "Gabon": {"1961": "267670", "1962": "267670", "1963": "267670", "1964": "267670", "1965": "267670", "1966": "267670", "1967": "267670", "1968": "267670", "1969": "267670", "1970": "267670", "1971": "267670", "1972": "267670", "1973": "267670", "1974": "267670", "1975": "267670", "1976": "267670", "1977": "267670", "1978": "267670", "1979": "267670", "1980": "267670", "1981": "267670", "1982": "267670", "1983": "267670", "1984": "267670", "1985": "267670", "1986": "267670", "1987": "267670", "1988": "267670", "1989": "267670", "1990": "267670", "1991": "267670", "1992": "267670", "1993": "267670", "1994": "267670", "1995": "267670", "1996": "267670", "1997": "267670", "1998": "267670", "1999": "267670", "2000": "267670", "2001": "267670", "2002": "267670", "2003": "267670", "2004": "267670", "2005": "267670", "2006": "267670", "2007": "267670", "2008": "267670", "2009": "267670", "2010": "267670", "2011": "267670", "2012": "267670", "2013": "267670", "2014": "267670"}, "Monaco": {"1961": "2", "1962": "2", "1963": "2", "1964": "2", "1965": "2", "1966": "2", "1967": "2", "1968": "2", "1969": "2", "1970": "2", "1971": "2", "1972": "2", "1973": "2", "1974": "2", "1975": "2", "1976": "2", "1977": "2", "1978": "2", "1979": "2", "1980": "2", "1981": "2", "1982": "2", "1983": "2", "1984": "2", "1985": "2", "1986": "2", "1987": "2", "1988": "2", "1989": "2", "1990": "2", "1991": "2", "1992": "2", "1993": "2", "1994": "2", "1995": "2", "1996": "2", "1997": "2", "1998": "2", "1999": "2", "2000": "2", "2001": "2", "2002": "2", "2003": "2", "2004": "2", "2005": "2", "2006": "2", "2007": "2", "2008": "2", "2009": "2", "2010": "2", "2011": "2", "2012": "2", "2013": "2", "2014": "2"}, "New Zealand": {"1961": "267710", "1962": "267710", "1963": "267710", "1964": "267710", "1965": "267710", "1966": "267710", "1967": "267710", "1968": "267710", "1969": "267710", "1970": "267710", "1971": "267710", "1972": "267710", "1973": "267710", "1974": "267710", "1975": "267710", "1976": "267710", "1977": "267710", "1978": "267710", "1979": "267710", "1980": "267710", "1981": "267710", "1982": "267710", "1983": "267710", "1984": "267710", "1985": "267710", "1986": "267710", "1987": "267710", "1988": "267710", "1989": "267710", "1990": "267710", "1991": "267710", "1992": "267710", "1993": "267710", "1994": "267710", "1995": "267710", "1996": "267710", "1997": "267710", "1998": "267710", "1999": "267710", "2000": "267710", "2001": "267710", "2002": "267710", "2003": "267710", "2004": "267710", "2005": "267710", "2006": "267710", "2007": "267710", "2008": "267710", "2009": "267710", "2010": "267710", "2011": "267710", "2012": "267710", "2013": "267710", "2014": "267710"}, "European Union": {"1961": "4352765", "1962": "4352765", "1963": "4352765", "1964": "4352765", "1965": "4352765", "1966": "4352765", "1967": "4352765", "1968": "4352765", "1969": "4352765", "1970": "4352765", "1971": "4352765", "1972": "4352765", "1973": "4352765", "1974": "4352765", "1975": "4352765", "1976": "4352765", "1977": "4352765", "1978": "4352765", "1979": "4352765", "1980": "4352765", "1981": "4352765", "1982": "4352765", "1983": "4352765", "1984": "4352765", "1985": "4352765", "1986": "4352765", "1987": "4352765", "1988": "4352765", "1989": "4352765", "1990": "4352765", "1991": "4352765", "1992": "4352765", "1993": "4352785", "1994": "4352795", "1995": "4352815", "1996": "4352895", "1997": "4352895", "1998": "4352825", "1999": "4352825", "2000": "4384955", "2001": "4384975", "2002": "4385285", "2003": "4385335", "2004": "4385405", "2005": "4385425", "2006": "4385715", "2007": "4385695", "2008": "4385711", "2009": "4385856", "2010": "4386040", "2011": "4385982", "2012": "4383136", "2013": "4383136", "2014": "4383136"}, "Jamaica": {"1961": "10990", "1962": "10990", "1963": "10990", "1964": "10990", "1965": "10990", "1966": "10990", "1967": "10990", "1968": "10990", "1969": "10990", "1970": "10990", "1971": "10990", "1972": "10990", "1973": "10990", "1974": "10990", "1975": "10990", "1976": "10990", "1977": "10990", "1978": "10990", "1979": "10990", "1980": "10990", "1981": "10990", "1982": "10990", "1983": "10990", "1984": "10990", "1985": "10990", "1986": "10990", "1987": "10990", "1988": "10990", "1989": "10990", "1990": "10990", "1991": "10990", "1992": "10990", "1993": "10990", "1994": "10990", "1995": "10990", "1996": "10990", "1997": "10990", "1998": "10990", "1999": "10990", "2000": "10990", "2001": "10990", "2002": "10990", "2003": "10990", "2004": "10990", "2005": "10990", "2006": "10990", "2007": "10990", "2008": "10990", "2009": "10990", "2010": "10990", "2011": "10990", "2012": "10990", "2013": "10990", "2014": "10990"}, "Albania": {"1961": "28750", "1962": "28750", "1963": "28750", "1964": "28750", "1965": "28750", "1966": "28750", "1967": "28750", "1968": "28750", "1969": "28750", "1970": "28750", "1971": "28750", "1972": "28750", "1973": "28750", "1974": "28750", "1975": "28750", "1976": "28750", "1977": "28750", "1978": "28750", "1979": "28750", "1980": "28750", "1981": "28750", "1982": "28750", "1983": "28750", "1984": "28750", "1985": "28750", "1986": "28750", "1987": "28750", "1988": "28750", "1989": "28750", "1990": "28750", "1991": "28750", "1992": "28750", "1993": "28750", "1994": "28750", "1995": "28750", "1996": "28750", "1997": "28750", "1998": "28750", "1999": "28750", "2000": "28750", "2001": "28750", "2002": "28750", "2003": "28750", "2004": "28750", "2005": "28750", "2006": "28750", "2007": "28750", "2008": "28750", "2009": "28750", "2010": "28750", "2011": "28750", "2012": "28750", "2013": "28750", "2014": "28750"}, "Samoa": {"1961": "2840", "1962": "2840", "1963": "2840", "1964": "2840", "1965": "2840", "1966": "2840", "1967": "2840", "1968": "2840", "1969": "2840", "1970": "2840", "1971": "2840", "1972": "2840", "1973": "2840", "1974": "2840", "1975": "2840", "1976": "2840", "1977": "2840", "1978": "2840", "1979": "2840", "1980": "2840", "1981": "2840", "1982": "2840", "1983": "2840", "1984": "2840", "1985": "2840", "1986": "2840", "1987": "2840", "1988": "2840", "1989": "2840", "1990": "2840", "1991": "2840", "1992": "2840", "1993": "2840", "1994": "2840", "1995": "2840", "1996": "2840", "1997": "2840", "1998": "2840", "1999": "2840", "2000": "2840", "2001": "2840", "2002": "2840", "2003": "2840", "2004": "2840", "2005": "2840", "2006": "2840", "2007": "2840", "2008": "2840", "2009": "2840", "2010": "2840", "2011": "2840", "2012": "2840", "2013": "2840", "2014": "2840"}, "Slovak Republic": {"1961": "49030", "1962": "49030", "1963": "49030", "1964": "49030", "1965": "49030", "1966": "49030", "1967": "49030", "1968": "49030", "1969": "49030", "1970": "49030", "1971": "49030", "1972": "49030", "1973": "49030", "1974": "49030", "1975": "49030", "1976": "49030", "1977": "49030", "1978": "49030", "1979": "49030", "1980": "49030", "1981": "49030", "1982": "49030", "1983": "49030", "1984": "49030", "1985": "49030", "1986": "49030", "1987": "49030", "1988": "49030", "1989": "49030", "1990": "49030", "1991": "49030", "1992": "49030", "1993": "49030", "1994": "49030", "1995": "49030", "1996": "49030", "1997": "49030", "1998": "49030", "1999": "49030", "2000": "49030", "2001": "49030", "2002": "49030", "2003": "49030", "2004": "49030", "2005": "49030", "2006": "49030", "2007": "49030", "2008": "49035", "2009": "49040", "2010": "49037", "2011": "49036", "2012": "49036", "2013": "49036", "2014": "49036"}, "United Arab Emirates": {"1961": "83600", "1962": "83600", "1963": "83600", "1964": "83600", "1965": "83600", "1966": "83600", "1967": "83600", "1968": "83600", "1969": "83600", "1970": "83600", "1971": "83600", "1972": "83600", "1973": "83600", "1974": "83600", "1975": "83600", "1976": "83600", "1977": "83600", "1978": "83600", "1979": "83600", "1980": "83600", "1981": "83600", "1982": "83600", "1983": "83600", "1984": "83600", "1985": "83600", "1986": "83600", "1987": "83600", "1988": "83600", "1989": "83600", "1990": "83600", "1991": "83600", "1992": "83600", "1993": "83600", "1994": "83600", "1995": "83600", "1996": "83600", "1997": "83600", "1998": "83600", "1999": "83600", "2000": "83600", "2001": "83600", "2002": "83600", "2003": "83600", "2004": "83600", "2005": "83600", "2006": "83600", "2007": "83600", "2008": "83600", "2009": "83600", "2010": "83600", "2011": "83600", "2012": "83600", "2013": "83600", "2014": "83600"}, "Guam": {"1961": "540", "1962": "540", "1963": "540", "1964": "540", "1965": "540", "1966": "540", "1967": "540", "1968": "540", "1969": "540", "1970": "540", "1971": "540", "1972": "540", "1973": "540", "1974": "540", "1975": "540", "1976": "540", "1977": "540", "1978": "540", "1979": "540", "1980": "540", "1981": "540", "1982": "540", "1983": "540", "1984": "540", "1985": "540", "1986": "540", "1987": "540", "1988": "540", "1989": "540", "1990": "540", "1991": "540", "1992": "540", "1993": "540", "1994": "540", "1995": "540", "1996": "540", "1997": "540", "1998": "540", "1999": "540", "2000": "540", "2001": "540", "2002": "540", "2003": "540", "2004": "540", "2005": "540", "2006": "540", "2007": "540", "2008": "540", "2009": "540", "2010": "540", "2011": "540", "2012": "540", "2013": "540", "2014": "540"}, "Uruguay": {"1961": "176220", "1962": "176220", "1963": "176220", "1964": "176220", "1965": "176220", "1966": "176220", "1967": "176220", "1968": "176220", "1969": "176220", "1970": "176220", "1971": "176220", "1972": "176220", "1973": "176220", "1974": "176220", "1975": "176220", "1976": "176220", "1977": "176220", "1978": "176220", "1979": "176220", "1980": "176220", "1981": "176220", "1982": "176220", "1983": "176220", "1984": "176220", "1985": "176220", "1986": "176220", "1987": "176220", "1988": "176220", "1989": "176220", "1990": "176220", "1991": "176220", "1992": "176220", "1993": "176220", "1994": "176220", "1995": "176220", "1996": "176220", "1997": "176220", "1998": "176220", "1999": "176220", "2000": "176220", "2001": "176220", "2002": "176220", "2003": "176220", "2004": "176220", "2005": "176220", "2006": "176220", "2007": "176220", "2008": "176220", "2009": "176220", "2010": "176220", "2011": "176220", "2012": "176220", "2013": "176220", "2014": "176220"}, "India": {"1961": "3287260", "1962": "3287260", "1963": "3287260", "1964": "3287260", "1965": "3287260", "1966": "3287260", "1967": "3287260", "1968": "3287260", "1969": "3287260", "1970": "3287260", "1971": "3287260", "1972": "3287260", "1973": "3287260", "1974": "3287260", "1975": "3287260", "1976": "3287260", "1977": "3287260", "1978": "3287260", "1979": "3287260", "1980": "3287260", "1981": "3287260", "1982": "3287260", "1983": "3287260", "1984": "3287260", "1985": "3287260", "1986": "3287260", "1987": "3287260", "1988": "3287260", "1989": "3287260", "1990": "3287260", "1991": "3287260", "1992": "3287260", "1993": "3287260", "1994": "3287260", "1995": "3287260", "1996": "3287260", "1997": "3287260", "1998": "3287260", "1999": "3287260", "2000": "3287260", "2001": "3287260", "2002": "3287260", "2003": "3287260", "2004": "3287260", "2005": "3287260", "2006": "3287260", "2007": "3287260", "2008": "3287260", "2009": "3287260", "2010": "3287260", "2011": "3287260", "2012": "3287260", "2013": "3287260", "2014": "3287260"}, "Azerbaijan": {"1961": "86600", "1962": "86600", "1963": "86600", "1964": "86600", "1965": "86600", "1966": "86600", "1967": "86600", "1968": "86600", "1969": "86600", "1970": "86600", "1971": "86600", "1972": "86600", "1973": "86600", "1974": "86600", "1975": "86600", "1976": "86600", "1977": "86600", "1978": "86600", "1979": "86600", "1980": "86600", "1981": "86600", "1982": "86600", "1983": "86600", "1984": "86600", "1985": "86600", "1986": "86600", "1987": "86600", "1988": "86600", "1989": "86600", "1990": "86600", "1991": "86600", "1992": "86600", "1993": "86600", "1994": "86600", "1995": "86600", "1996": "86600", "1997": "86600", "1998": "86600", "1999": "86600", "2000": "86600", "2001": "86600", "2002": "86600", "2003": "86600", "2004": "86600", "2005": "86600", "2006": "86600", "2007": "86600", "2008": "86600", "2009": "86600", "2010": "86600", "2011": "86600", "2012": "86600", "2013": "86600", "2014": "86600"}, "Lesotho": {"1961": "30360", "1962": "30360", "1963": "30360", "1964": "30360", "1965": "30360", "1966": "30360", "1967": "30360", "1968": "30360", "1969": "30360", "1970": "30360", "1971": "30360", "1972": "30360", "1973": "30360", "1974": "30360", "1975": "30360", "1976": "30360", "1977": "30360", "1978": "30360", "1979": "30360", "1980": "30360", "1981": "30360", "1982": "30360", "1983": "30360", "1984": "30360", "1985": "30360", "1986": "30360", "1987": "30360", "1988": "30360", "1989": "30360", "1990": "30360", "1991": "30360", "1992": "30360", "1993": "30360", "1994": "30360", "1995": "30360", "1996": "30360", "1997": "30360", "1998": "30360", "1999": "30360", "2000": "30360", "2001": "30360", "2002": "30360", "2003": "30360", "2004": "30360", "2005": "30360", "2006": "30360", "2007": "30360", "2008": "30360", "2009": "30360", "2010": "30360", "2011": "30360", "2012": "30360", "2013": "30360", "2014": "30360"}, "Kenya": {"1961": "580370", "1962": "580370", "1963": "580370", "1964": "580370", "1965": "580370", "1966": "580370", "1967": "580370", "1968": "580370", "1969": "580370", "1970": "580370", "1971": "580370", "1972": "580370", "1973": "580370", "1974": "580370", "1975": "580370", "1976": "580370", "1977": "580370", "1978": "580370", "1979": "580370", "1980": "580370", "1981": "580370", "1982": "580370", "1983": "580370", "1984": "580370", "1985": "580370", "1986": "580370", "1987": "580370", "1988": "580370", "1989": "580370", "1990": "580370", "1991": "580370", "1992": "580370", "1993": "580370", "1994": "580370", "1995": "580370", "1996": "580370", "1997": "580370", "1998": "580370", "1999": "580370", "2000": "580370", "2001": "580370", "2002": "580370", "2003": "580370", "2004": "580370", "2005": "580370", "2006": "580370", "2007": "580370", "2008": "580370", "2009": "580370", "2010": "580370", "2011": "580370", "2012": "580370", "2013": "580370", "2014": "580370"}, "Latin America and the Caribbean (IFC classification)": {}, "Upper middle income": {"1961": "41650020", "1962": "41650020", "1963": "41650020", "1964": "41650020", "1965": "41650020", "1966": "41650020", "1967": "41650020", "1968": "41650020", "1969": "41650020", "1970": "41650020", "1971": "41650020", "1972": "41650020", "1973": "41650020", "1974": "41650020", "1975": "41650020", "1976": "41650020", "1977": "41650020", "1978": "41650020", "1979": "41650020", "1980": "41650020", "1981": "41650020", "1982": "41650020", "1983": "41650020", "1984": "41650020", "1985": "41650020", "1986": "41650020", "1987": "41650020", "1988": "41650020", "1989": "41650020", "1990": "41650020", "1991": "41650660", "1992": "41650660", "1993": "41650660", "1994": "41650660", "1995": "41650650", "1996": "41650640", "1997": "41650640", "1998": "41623450", "1999": "41623450", "2000": "41623440", "2001": "41623434.2", "2002": "41623433.2", "2003": "41623432.7", "2004": "41623442.5", "2005": "41623441.8", "2006": "41623441.4", "2007": "41623440.8", "2008": "41623440.8", "2009": "41620901", "2010": "41620893", "2011": "41620893", "2012": "41620891", "2013": "41620891", "2014": "41620891"}, "Tajikistan": {"1961": "142550", "1962": "142550", "1963": "142550", "1964": "142550", "1965": "142550", "1966": "142550", "1967": "142550", "1968": "142550", "1969": "142550", "1970": "142550", "1971": "142550", "1972": "142550", "1973": "142550", "1974": "142550", "1975": "142550", "1976": "142550", "1977": "142550", "1978": "142550", "1979": "142550", "1980": "142550", "1981": "142550", "1982": "142550", "1983": "142550", "1984": "142550", "1985": "142550", "1986": "142550", "1987": "142550", "1988": "142550", "1989": "142550", "1990": "142550", "1991": "142550", "1992": "142550", "1993": "142550", "1994": "142550", "1995": "142550", "1996": "142550", "1997": "142550", "1998": "142550", "1999": "142550", "2000": "142550", "2001": "142550", "2002": "142550", "2003": "142550", "2004": "142550", "2005": "142550", "2006": "142550", "2007": "142550", "2008": "142550", "2009": "142550", "2010": "142550", "2011": "142550", "2012": "142550", "2013": "142550", "2014": "142550"}, "Pacific island small states": {"1961": "63790", "1962": "63790", "1963": "63790", "1964": "63790", "1965": "63790", "1966": "63790", "1967": "63790", "1968": "63790", "1969": "63790", "1970": "63790", "1971": "63790", "1972": "63790", "1973": "63790", "1974": "63790", "1975": "63790", "1976": "63790", "1977": "63790", "1978": "63790", "1979": "63790", "1980": "63790", "1981": "63790", "1982": "63790", "1983": "63790", "1984": "63790", "1985": "63790", "1986": "63790", "1987": "63790", "1988": "63790", "1989": "63790", "1990": "63790", "1991": "65130", "1992": "65130", "1993": "65130", "1994": "65130", "1995": "65130", "1996": "65130", "1997": "65130", "1998": "65130", "1999": "65130", "2000": "65130", "2001": "65130", "2002": "65130", "2003": "65130", "2004": "65130", "2005": "65130", "2006": "65130", "2007": "65130", "2008": "65130", "2009": "65130", "2010": "65130", "2011": "65130", "2012": "65130", "2013": "65130", "2014": "65130"}, "Turkey": {"1961": "783560", "1962": "783560", "1963": "783560", "1964": "783560", "1965": "783560", "1966": "783560", "1967": "783560", "1968": "783560", "1969": "783560", "1970": "783560", "1971": "783560", "1972": "783560", "1973": "783560", "1974": "783560", "1975": "783560", "1976": "783560", "1977": "783560", "1978": "783560", "1979": "783560", "1980": "783560", "1981": "783560", "1982": "783560", "1983": "783560", "1984": "783560", "1985": "783560", "1986": "783560", "1987": "783560", "1988": "783560", "1989": "783560", "1990": "783560", "1991": "783560", "1992": "783560", "1993": "783560", "1994": "783560", "1995": "783560", "1996": "783560", "1997": "783560", "1998": "783560", "1999": "783560", "2000": "783560", "2001": "783560", "2002": "783560", "2003": "783560", "2004": "783560", "2005": "783560", "2006": "783560", "2007": "783560", "2008": "783560", "2009": "783560", "2010": "783560", "2011": "783560", "2012": "783560", "2013": "783560", "2014": "783560"}, "Afghanistan": {"1961": "652860", "1962": "652860", "1963": "652860", "1964": "652860", "1965": "652860", "1966": "652860", "1967": "652860", "1968": "652860", "1969": "652860", "1970": "652860", "1971": "652860", "1972": "652860", "1973": "652860", "1974": "652860", "1975": "652860", "1976": "652860", "1977": "652860", "1978": "652860", "1979": "652860", "1980": "652860", "1981": "652860", "1982": "652860", "1983": "652860", "1984": "652860", "1985": "652860", "1986": "652860", "1987": "652860", "1988": "652860", "1989": "652860", "1990": "652860", "1991": "652860", "1992": "652860", "1993": "652860", "1994": "652860", "1995": "652860", "1996": "652860", "1997": "652860", "1998": "652860", "1999": "652860", "2000": "652860", "2001": "652860", "2002": "652860", "2003": "652860", "2004": "652860", "2005": "652860", "2006": "652860", "2007": "652860", "2008": "652860", "2009": "652860", "2010": "652860", "2011": "652860", "2012": "652860", "2013": "652860", "2014": "652860"}, "Venezuela, RB": {"1961": "912050", "1962": "912050", "1963": "912050", "1964": "912050", "1965": "912050", "1966": "912050", "1967": "912050", "1968": "912050", "1969": "912050", "1970": "912050", "1971": "912050", "1972": "912050", "1973": "912050", "1974": "912050", "1975": "912050", "1976": "912050", "1977": "912050", "1978": "912050", "1979": "912050", "1980": "912050", "1981": "912050", "1982": "912050", "1983": "912050", "1984": "912050", "1985": "912050", "1986": "912050", "1987": "912050", "1988": "912050", "1989": "912050", "1990": "912050", "1991": "912050", "1992": "912050", "1993": "912050", "1994": "912050", "1995": "912050", "1996": "912050", "1997": "912050", "1998": "912050", "1999": "912050", "2000": "912050", "2001": "912050", "2002": "912050", "2003": "912050", "2004": "912050", "2005": "912050", "2006": "912050", "2007": "912050", "2008": "912050", "2009": "912050", "2010": "912050", "2011": "912050", "2012": "912050", "2013": "912050", "2014": "912050"}, "Bangladesh": {"1961": "148460", "1962": "148460", "1963": "148460", "1964": "148460", "1965": "148460", "1966": "148460", "1967": "148460", "1968": "148460", "1969": "148460", "1970": "148460", "1971": "148460", "1972": "148460", "1973": "148460", "1974": "148460", "1975": "148460", "1976": "148460", "1977": "148460", "1978": "148460", "1979": "148460", "1980": "148460", "1981": "148460", "1982": "148460", "1983": "148460", "1984": "148460", "1985": "148460", "1986": "148460", "1987": "148460", "1988": "148460", "1989": "148460", "1990": "148460", "1991": "148460", "1992": "148460", "1993": "148460", "1994": "148460", "1995": "148460", "1996": "148460", "1997": "148460", "1998": "148460", "1999": "148460", "2000": "148460", "2001": "148460", "2002": "148460", "2003": "148460", "2004": "148460", "2005": "148460", "2006": "148460", "2007": "148460", "2008": "148460", "2009": "148460", "2010": "148460", "2011": "148460", "2012": "148460", "2013": "148460", "2014": "148460"}, "Mauritania": {"1961": "1030700", "1962": "1030700", "1963": "1030700", "1964": "1030700", "1965": "1030700", "1966": "1030700", "1967": "1030700", "1968": "1030700", "1969": "1030700", "1970": "1030700", "1971": "1030700", "1972": "1030700", "1973": "1030700", "1974": "1030700", "1975": "1030700", "1976": "1030700", "1977": "1030700", "1978": "1030700", "1979": "1030700", "1980": "1030700", "1981": "1030700", "1982": "1030700", "1983": "1030700", "1984": "1030700", "1985": "1030700", "1986": "1030700", "1987": "1030700", "1988": "1030700", "1989": "1030700", "1990": "1030700", "1991": "1030700", "1992": "1030700", "1993": "1030700", "1994": "1030700", "1995": "1030700", "1996": "1030700", "1997": "1030700", "1998": "1030700", "1999": "1030700", "2000": "1030700", "2001": "1030700", "2002": "1030700", "2003": "1030700", "2004": "1030700", "2005": "1030700", "2006": "1030700", "2007": "1030700", "2008": "1030700", "2009": "1030700", "2010": "1030700", "2011": "1030700", "2012": "1030700", "2013": "1030700", "2014": "1030700"}, "Solomon Islands": {"1961": "28900", "1962": "28900", "1963": "28900", "1964": "28900", "1965": "28900", "1966": "28900", "1967": "28900", "1968": "28900", "1969": "28900", "1970": "28900", "1971": "28900", "1972": "28900", "1973": "28900", "1974": "28900", "1975": "28900", "1976": "28900", "1977": "28900", "1978": "28900", "1979": "28900", "1980": "28900", "1981": "28900", "1982": "28900", "1983": "28900", "1984": "28900", "1985": "28900", "1986": "28900", "1987": "28900", "1988": "28900", "1989": "28900", "1990": "28900", "1991": "28900", "1992": "28900", "1993": "28900", "1994": "28900", "1995": "28900", "1996": "28900", "1997": "28900", "1998": "28900", "1999": "28900", "2000": "28900", "2001": "28900", "2002": "28900", "2003": "28900", "2004": "28900", "2005": "28900", "2006": "28900", "2007": "28900", "2008": "28900", "2009": "28900", "2010": "28900", "2011": "28900", "2012": "28900", "2013": "28900", "2014": "28900"}, "Hong Kong SAR, China": {"1961": "1070", "1962": "1070", "1963": "1070", "1964": "1070", "1965": "1070", "1966": "1070", "1967": "1070", "1968": "1070", "1969": "1070", "1970": "1070", "1971": "1070", "1972": "1070", "1973": "1070", "1974": "1070", "1975": "1070", "1976": "1070", "1977": "1070", "1978": "1070", "1979": "1070", "1980": "1070", "1981": "1070", "1982": "1070", "1983": "1070", "1984": "1070", "1985": "1070", "1986": "1070", "1987": "1070", "1988": "1070", "1989": "1070", "1990": "1070", "1991": "1070", "1992": "1070", "1993": "1070", "1994": "1070", "1995": "1080", "1996": "1090", "1997": "1090", "1998": "1090", "1999": "1090", "2000": "1100", "2001": "1100", "2002": "1100", "2003": "1100", "2004": "1100", "2005": "1100", "2006": "1100", "2007": "1100", "2008": "1100", "2009": "1100", "2010": "1100", "2011": "1100", "2012": "1100", "2013": "1100", "2014": "1100"}, "San Marino": {"1961": "60", "1962": "60", "1963": "60", "1964": "60", "1965": "60", "1966": "60", "1967": "60", "1968": "60", "1969": "60", "1970": "60", "1971": "60", "1972": "60", "1973": "60", "1974": "60", "1975": "60", "1976": "60", "1977": "60", "1978": "60", "1979": "60", "1980": "60", "1981": "60", "1982": "60", "1983": "60", "1984": "60", "1985": "60", "1986": "60", "1987": "60", "1988": "60", "1989": "60", "1990": "60", "1991": "60", "1992": "60", "1993": "60", "1994": "60", "1995": "60", "1996": "60", "1997": "60", "1998": "60", "1999": "60", "2000": "60", "2001": "60", "2002": "60", "2003": "60", "2004": "60", "2005": "60", "2006": "60", "2007": "60", "2008": "60", "2009": "60", "2010": "60", "2011": "60", "2012": "60", "2013": "60", "2014": "60"}, "Mongolia": {"1961": "1564120", "1962": "1564120", "1963": "1564120", "1964": "1564120", "1965": "1564120", "1966": "1564120", "1967": "1564120", "1968": "1564120", "1969": "1564120", "1970": "1564120", "1971": "1564120", "1972": "1564120", "1973": "1564120", "1974": "1564120", "1975": "1564120", "1976": "1564120", "1977": "1564120", "1978": "1564120", "1979": "1564120", "1980": "1564120", "1981": "1564120", "1982": "1564120", "1983": "1564120", "1984": "1564120", "1985": "1564120", "1986": "1564120", "1987": "1564120", "1988": "1564120", "1989": "1564120", "1990": "1564120", "1991": "1564120", "1992": "1564120", "1993": "1564120", "1994": "1564120", "1995": "1564120", "1996": "1564120", "1997": "1564120", "1998": "1564120", "1999": "1564120", "2000": "1564120", "2001": "1564120", "2002": "1564120", "2003": "1564120", "2004": "1564120", "2005": "1564120", "2006": "1564120", "2007": "1564120", "2008": "1564120", "2009": "1564120", "2010": "1564120", "2011": "1564120", "2012": "1564120", "2013": "1564120", "2014": "1564120"}, "France": {"1961": "549086", "1962": "549086", "1963": "549086", "1964": "549086", "1965": "549086", "1966": "549086", "1967": "549086", "1968": "549086", "1969": "549086", "1970": "549086", "1971": "549086", "1972": "549086", "1973": "549086", "1974": "549086", "1975": "549086", "1976": "549086", "1977": "549086", "1978": "549086", "1979": "549086", "1980": "549086", "1981": "549086", "1982": "549086", "1983": "549086", "1984": "549086", "1985": "549086", "1986": "549086", "1987": "549086", "1988": "549086", "1989": "549086", "1990": "549086", "1991": "549086", "1992": "549086", "1993": "549086", "1994": "549086", "1995": "549086", "1996": "549086", "1997": "549086", "1998": "549086", "1999": "549086", "2000": "549086", "2001": "549086", "2002": "549086", "2003": "549086", "2004": "549086", "2005": "549086", "2006": "549086", "2007": "549086", "2008": "549087", "2009": "549087", "2010": "549087", "2011": "549087", "2012": "549091", "2013": "549091", "2014": "549091"}, "Syrian Arab Republic": {"1961": "185180", "1962": "185180", "1963": "185180", "1964": "185180", "1965": "185180", "1966": "185180", "1967": "185180", "1968": "185180", "1969": "185180", "1970": "185180", "1971": "185180", "1972": "185180", "1973": "185180", "1974": "185180", "1975": "185180", "1976": "185180", "1977": "185180", "1978": "185180", "1979": "185180", "1980": "185180", "1981": "185180", "1982": "185180", "1983": "185180", "1984": "185180", "1985": "185180", "1986": "185180", "1987": "185180", "1988": "185180", "1989": "185180", "1990": "185180", "1991": "185180", "1992": "185180", "1993": "185180", "1994": "185180", "1995": "185180", "1996": "185180", "1997": "185180", "1998": "185180", "1999": "185180", "2000": "185180", "2001": "185180", "2002": "185180", "2003": "185180", "2004": "185180", "2005": "185180", "2006": "185180", "2007": "185180", "2008": "185180", "2009": "185180", "2010": "185180", "2011": "185180", "2012": "185180", "2013": "185180", "2014": "185180"}, "Bermuda": {"1961": "50", "1962": "50", "1963": "50", "1964": "50", "1965": "50", "1966": "50", "1967": "50", "1968": "50", "1969": "50", "1970": "50", "1971": "50", "1972": "50", "1973": "50", "1974": "50", "1975": "50", "1976": "50", "1977": "50", "1978": "50", "1979": "50", "1980": "50", "1981": "50", "1982": "50", "1983": "50", "1984": "50", "1985": "50", "1986": "50", "1987": "50", "1988": "50", "1989": "50", "1990": "50", "1991": "50", "1992": "50", "1993": "50", "1994": "50", "1995": "50", "1996": "50", "1997": "50", "1998": "50", "1999": "50", "2000": "50", "2001": "50", "2002": "50", "2003": "50", "2004": "50", "2005": "50", "2006": "50", "2007": "50", "2008": "50", "2009": "50", "2010": "50", "2011": "50", "2012": "50", "2013": "50", "2014": "50"}, "Namibia": {"1961": "824290", "1962": "824290", "1963": "824290", "1964": "824290", "1965": "824290", "1966": "824290", "1967": "824290", "1968": "824290", "1969": "824290", "1970": "824290", "1971": "824290", "1972": "824290", "1973": "824290", "1974": "824290", "1975": "824290", "1976": "824290", "1977": "824290", "1978": "824290", "1979": "824290", "1980": "824290", "1981": "824290", "1982": "824290", "1983": "824290", "1984": "824290", "1985": "824290", "1986": "824290", "1987": "824290", "1988": "824290", "1989": "824290", "1990": "824290", "1991": "824290", "1992": "824290", "1993": "824290", "1994": "824290", "1995": "824290", "1996": "824290", "1997": "824290", "1998": "824290", "1999": "824290", "2000": "824290", "2001": "824290", "2002": "824290", "2003": "824290", "2004": "824290", "2005": "824290", "2006": "824290", "2007": "824290", "2008": "824290", "2009": "824290", "2010": "824290", "2011": "824290", "2012": "824290", "2013": "824290", "2014": "824290"}, "Somalia": {"1961": "637660", "1962": "637660", "1963": "637660", "1964": "637660", "1965": "637660", "1966": "637660", "1967": "637660", "1968": "637660", "1969": "637660", "1970": "637660", "1971": "637660", "1972": "637660", "1973": "637660", "1974": "637660", "1975": "637660", "1976": "637660", "1977": "637660", "1978": "637660", "1979": "637660", "1980": "637660", "1981": "637660", "1982": "637660", "1983": "637660", "1984": "637660", "1985": "637660", "1986": "637660", "1987": "637660", "1988": "637660", "1989": "637660", "1990": "637660", "1991": "637660", "1992": "637660", "1993": "637660", "1994": "637660", "1995": "637660", "1996": "637660", "1997": "637660", "1998": "637660", "1999": "637660", "2000": "637660", "2001": "637660", "2002": "637660", "2003": "637660", "2004": "637660", "2005": "637660", "2006": "637660", "2007": "637660", "2008": "637660", "2009": "637660", "2010": "637660", "2011": "637660", "2012": "637660", "2013": "637660", "2014": "637660"}, "Peru": {"1961": "1285220", "1962": "1285220", "1963": "1285220", "1964": "1285220", "1965": "1285220", "1966": "1285220", "1967": "1285220", "1968": "1285220", "1969": "1285220", "1970": "1285220", "1971": "1285220", "1972": "1285220", "1973": "1285220", "1974": "1285220", "1975": "1285220", "1976": "1285220", "1977": "1285220", "1978": "1285220", "1979": "1285220", "1980": "1285220", "1981": "1285220", "1982": "1285220", "1983": "1285220", "1984": "1285220", "1985": "1285220", "1986": "1285220", "1987": "1285220", "1988": "1285220", "1989": "1285220", "1990": "1285220", "1991": "1285220", "1992": "1285220", "1993": "1285220", "1994": "1285220", "1995": "1285220", "1996": "1285220", "1997": "1285220", "1998": "1285220", "1999": "1285220", "2000": "1285220", "2001": "1285220", "2002": "1285220", "2003": "1285220", "2004": "1285220", "2005": "1285220", "2006": "1285220", "2007": "1285220", "2008": "1285220", "2009": "1285220", "2010": "1285220", "2011": "1285220", "2012": "1285220", "2013": "1285220", "2014": "1285220"}, "Vanuatu": {"1961": "12190", "1962": "12190", "1963": "12190", "1964": "12190", "1965": "12190", "1966": "12190", "1967": "12190", "1968": "12190", "1969": "12190", "1970": "12190", "1971": "12190", "1972": "12190", "1973": "12190", "1974": "12190", "1975": "12190", "1976": "12190", "1977": "12190", "1978": "12190", "1979": "12190", "1980": "12190", "1981": "12190", "1982": "12190", "1983": "12190", "1984": "12190", "1985": "12190", "1986": "12190", "1987": "12190", "1988": "12190", "1989": "12190", "1990": "12190", "1991": "12190", "1992": "12190", "1993": "12190", "1994": "12190", "1995": "12190", "1996": "12190", "1997": "12190", "1998": "12190", "1999": "12190", "2000": "12190", "2001": "12190", "2002": "12190", "2003": "12190", "2004": "12190", "2005": "12190", "2006": "12190", "2007": "12190", "2008": "12190", "2009": "12190", "2010": "12190", "2011": "12190", "2012": "12190", "2013": "12190", "2014": "12190"}, "Nigeria": {"1961": "923770", "1962": "923770", "1963": "923770", "1964": "923770", "1965": "923770", "1966": "923770", "1967": "923770", "1968": "923770", "1969": "923770", "1970": "923770", "1971": "923770", "1972": "923770", "1973": "923770", "1974": "923770", "1975": "923770", "1976": "923770", "1977": "923770", "1978": "923770", "1979": "923770", "1980": "923770", "1981": "923770", "1982": "923770", "1983": "923770", "1984": "923770", "1985": "923770", "1986": "923770", "1987": "923770", "1988": "923770", "1989": "923770", "1990": "923770", "1991": "923770", "1992": "923770", "1993": "923770", "1994": "923770", "1995": "923770", "1996": "923770", "1997": "923770", "1998": "923770", "1999": "923770", "2000": "923770", "2001": "923770", "2002": "923770", "2003": "923770", "2004": "923770", "2005": "923770", "2006": "923770", "2007": "923770", "2008": "923770", "2009": "923770", "2010": "923770", "2011": "923770", "2012": "923770", "2013": "923770", "2014": "923770"}, "South Asia (IFC classification)": {}, "Norway": {"1961": "385178", "1962": "385178", "1963": "385178", "1964": "385178", "1965": "385178", "1966": "385178", "1967": "385178", "1968": "385178", "1969": "385178", "1970": "385178", "1971": "385178", "1972": "385178", "1973": "385178", "1974": "385178", "1975": "385178", "1976": "385178", "1977": "385178", "1978": "385178", "1979": "385178", "1980": "385178", "1981": "385178", "1982": "385178", "1983": "385178", "1984": "385178", "1985": "385178", "1986": "385178", "1987": "385178", "1988": "385178", "1989": "385178", "1990": "385178", "1991": "385178", "1992": "385178", "1993": "385178", "1994": "385178", "1995": "385178", "1996": "385178", "1997": "385178", "1998": "385178", "1999": "385178", "2000": "385178", "2001": "385178", "2002": "385178", "2003": "385178", "2004": "385178", "2005": "385178", "2006": "385178", "2007": "385178", "2008": "385178", "2009": "385178", "2010": "385178", "2011": "385178", "2012": "385178", "2013": "385178", "2014": "385178"}, "Cote d'Ivoire": {"1961": "322460", "1962": "322460", "1963": "322460", "1964": "322460", "1965": "322460", "1966": "322460", "1967": "322460", "1968": "322460", "1969": "322460", "1970": "322460", "1971": "322460", "1972": "322460", "1973": "322460", "1974": "322460", "1975": "322460", "1976": "322460", "1977": "322460", "1978": "322460", "1979": "322460", "1980": "322460", "1981": "322460", "1982": "322460", "1983": "322460", "1984": "322460", "1985": "322460", "1986": "322460", "1987": "322460", "1988": "322460", "1989": "322460", "1990": "322460", "1991": "322460", "1992": "322460", "1993": "322460", "1994": "322460", "1995": "322460", "1996": "322460", "1997": "322460", "1998": "322460", "1999": "322460", "2000": "322460", "2001": "322460", "2002": "322460", "2003": "322460", "2004": "322460", "2005": "322460", "2006": "322460", "2007": "322460", "2008": "322460", "2009": "322460", "2010": "322460", "2011": "322460", "2012": "322460", "2013": "322460", "2014": "322460"}, "Europe & Central Asia (developing only)": {"1961": "6385527", "1962": "6385527", "1963": "6385527", "1964": "6385527", "1965": "6385527", "1966": "6385527", "1967": "6385527", "1968": "6385527", "1969": "6385527", "1970": "6385527", "1971": "6385527", "1972": "6385527", "1973": "6385527", "1974": "6385527", "1975": "6385527", "1976": "6385527", "1977": "6385527", "1978": "6385527", "1979": "6385527", "1980": "6385527", "1981": "6385527", "1982": "6385527", "1983": "6385527", "1984": "6385527", "1985": "6385527", "1986": "6385527", "1987": "6385527", "1988": "6385527", "1989": "6385527", "1990": "6385527", "1991": "6385527", "1992": "6385527", "1993": "6385597", "1994": "6385597", "1995": "6385607", "1996": "6385607", "1997": "6385597", "1998": "6385597", "1999": "6385597", "2000": "6385597", "2001": "6385597", "2002": "6385597", "2003": "6385597", "2004": "6385617", "2005": "6385617", "2006": "6385617", "2007": "6385617", "2008": "6385617", "2009": "6385616", "2010": "6385616", "2011": "6385616", "2012": "6385616", "2013": "6385616", "2014": "6385616"}, "Benin": {"1961": "114760", "1962": "114760", "1963": "114760", "1964": "114760", "1965": "114760", "1966": "114760", "1967": "114760", "1968": "114760", "1969": "114760", "1970": "114760", "1971": "114760", "1972": "114760", "1973": "114760", "1974": "114760", "1975": "114760", "1976": "114760", "1977": "114760", "1978": "114760", "1979": "114760", "1980": "114760", "1981": "114760", "1982": "114760", "1983": "114760", "1984": "114760", "1985": "114760", "1986": "114760", "1987": "114760", "1988": "114760", "1989": "114760", "1990": "114760", "1991": "114760", "1992": "114760", "1993": "114760", "1994": "114760", "1995": "114760", "1996": "114760", "1997": "114760", "1998": "114760", "1999": "114760", "2000": "114760", "2001": "114760", "2002": "114760", "2003": "114760", "2004": "114760", "2005": "114760", "2006": "114760", "2007": "114760", "2008": "114760", "2009": "114760", "2010": "114760", "2011": "114760", "2012": "114760", "2013": "114760", "2014": "114760"}, "Other small states": {"1961": "1905421", "1962": "1905421", "1963": "1905421", "1964": "1905421", "1965": "1905421", "1966": "1905421", "1967": "1905421", "1968": "1905421", "1969": "1905421", "1970": "1905421", "1971": "1905421", "1972": "1905421", "1973": "1905421", "1974": "1905421", "1975": "1905421", "1976": "1905421", "1977": "1905421", "1978": "1905421", "1979": "1905421", "1980": "1905421", "1981": "1905421", "1982": "1905421", "1983": "1905421", "1984": "1905421", "1985": "1905421", "1986": "1905421", "1987": "1905421", "1988": "1905421", "1989": "1905421", "1990": "1905421", "1991": "1905421", "1992": "1905421", "1993": "1905421", "1994": "1898498", "1995": "1898498", "1996": "1898498", "1997": "1898498", "1998": "1898498", "1999": "1898498", "2000": "1898498", "2001": "1898498", "2002": "1898498", "2003": "1898498", "2004": "1896815", "2005": "1896815", "2006": "1896815", "2007": "1896815", "2008": "1896815", "2009": "1896815", "2010": "1896815", "2011": "1896815", "2012": "1896815", "2013": "1896815", "2014": "1896815"}, "Cuba": {"1961": "109890", "1962": "109890", "1963": "109890", "1964": "109890", "1965": "109890", "1966": "109890", "1967": "109890", "1968": "109890", "1969": "109890", "1970": "109890", "1971": "109890", "1972": "109890", "1973": "109890", "1974": "109890", "1975": "109890", "1976": "109890", "1977": "109890", "1978": "109890", "1979": "109890", "1980": "109890", "1981": "109890", "1982": "109890", "1983": "109890", "1984": "109890", "1985": "109890", "1986": "109890", "1987": "109890", "1988": "109890", "1989": "109890", "1990": "109890", "1991": "109890", "1992": "109890", "1993": "109890", "1994": "109890", "1995": "109890", "1996": "109890", "1997": "109890", "1998": "109890", "1999": "109890", "2000": "109890", "2001": "109890", "2002": "109890", "2003": "109890", "2004": "109890", "2005": "109890", "2006": "109890", "2007": "109890", "2008": "109890", "2009": "109890", "2010": "109880", "2011": "109880", "2012": "109880", "2013": "109880", "2014": "109880"}, "Cameroon": {"1961": "475440", "1962": "475440", "1963": "475440", "1964": "475440", "1965": "475440", "1966": "475440", "1967": "475440", "1968": "475440", "1969": "475440", "1970": "475440", "1971": "475440", "1972": "475440", "1973": "475440", "1974": "475440", "1975": "475440", "1976": "475440", "1977": "475440", "1978": "475440", "1979": "475440", "1980": "475440", "1981": "475440", "1982": "475440", "1983": "475440", "1984": "475440", "1985": "475440", "1986": "475440", "1987": "475440", "1988": "475440", "1989": "475440", "1990": "475440", "1991": "475440", "1992": "475440", "1993": "475440", "1994": "475440", "1995": "475440", "1996": "475440", "1997": "475440", "1998": "475440", "1999": "475440", "2000": "475440", "2001": "475440", "2002": "475440", "2003": "475440", "2004": "475440", "2005": "475440", "2006": "475440", "2007": "475440", "2008": "475440", "2009": "475440", "2010": "475440", "2011": "475440", "2012": "475440", "2013": "475440", "2014": "475440"}, "Montenegro": {"1961": "13810", "1962": "13810", "1963": "13810", "1964": "13810", "1965": "13810", "1966": "13810", "1967": "13810", "1968": "13810", "1969": "13810", "1970": "13810", "1971": "13810", "1972": "13810", "1973": "13810", "1974": "13810", "1975": "13810", "1976": "13810", "1977": "13810", "1978": "13810", "1979": "13810", "1980": "13810", "1981": "13810", "1982": "13810", "1983": "13810", "1984": "13810", "1985": "13810", "1986": "13810", "1987": "13810", "1988": "13810", "1989": "13810", "1990": "13810", "1991": "13810", "1992": "13810", "1993": "13810", "1994": "13810", "1995": "13810", "1996": "13810", "1997": "13810", "1998": "13810", "1999": "13810", "2000": "13810", "2001": "13810", "2002": "13810", "2003": "13810", "2004": "13810", "2005": "13810", "2006": "13810", "2007": "13810", "2008": "13810", "2009": "13810", "2010": "13810", "2011": "13810", "2012": "13810", "2013": "13810", "2014": "13810"}, "Low & middle income": {"1961": "76737118", "1962": "76737118", "1963": "76737118", "1964": "76737118", "1965": "76737118", "1966": "76737118", "1967": "76737118", "1968": "76737118", "1969": "76737118", "1970": "76737118", "1971": "76737118", "1972": "76737118", "1973": "76737118", "1974": "76737118", "1975": "76737118", "1976": "76737118", "1977": "76734998", "1978": "76734998", "1979": "76737038", "1980": "76737118", "1981": "76737118", "1982": "76737118", "1983": "76737118", "1984": "76737118", "1985": "76737118", "1986": "76737118", "1987": "76735778", "1988": "76735788", "1989": "76735788", "1990": "76736458", "1991": "76737828", "1992": "76737858", "1993": "76620348", "1994": "76613425", "1995": "76613425", "1996": "76613415", "1997": "76613405", "1998": "76586215", "1999": "76586215", "2000": "76584335", "2001": "76584339.2", "2002": "76584388.2", "2003": "76584397.7", "2004": "76582738.5", "2005": "76584635.8", "2006": "76584635.4", "2007": "76584634.8", "2008": "76584473.8", "2009": "76581933", "2010": "76581831", "2011": "76599957.5", "2012": "76599955.5", "2013": "76599955.5", "2014": "76599955.5"}, "Middle East (developing only)": {}, "China": {"1961": "9562950", "1962": "9562950", "1963": "9562950", "1964": "9562950", "1965": "9562950", "1966": "9562950", "1967": "9562950", "1968": "9562950", "1969": "9562950", "1970": "9562950", "1971": "9562950", "1972": "9562950", "1973": "9562950", "1974": "9562950", "1975": "9562950", "1976": "9562950", "1977": "9562950", "1978": "9562950", "1979": "9562950", "1980": "9562950", "1981": "9562950", "1982": "9562950", "1983": "9562950", "1984": "9562950", "1985": "9562950", "1986": "9562950", "1987": "9562950", "1988": "9562950", "1989": "9562950", "1990": "9562950", "1991": "9562950", "1992": "9562950", "1993": "9562950", "1994": "9562950", "1995": "9562940", "1996": "9562930", "1997": "9562930", "1998": "9562930", "1999": "9562930", "2000": "9562920", "2001": "9562914.2", "2002": "9562913.2", "2003": "9562912.7", "2004": "9562912.5", "2005": "9562911.8", "2006": "9562911.4", "2007": "9562910.8", "2008": "9562910.8", "2009": "9562911", "2010": "9562911", "2011": "9562911", "2012": "9562911", "2013": "9562911", "2014": "9562911"}, "Sub-Saharan Africa (developing only)": {"1961": "24362101", "1962": "24362101", "1963": "24362101", "1964": "24362101", "1965": "24362101", "1966": "24362101", "1967": "24362101", "1968": "24362101", "1969": "24362101", "1970": "24362101", "1971": "24362101", "1972": "24362101", "1973": "24362101", "1974": "24362101", "1975": "24362101", "1976": "24362101", "1977": "24362101", "1978": "24362101", "1979": "24362101", "1980": "24362101", "1981": "24362101", "1982": "24362101", "1983": "24362101", "1984": "24362101", "1985": "24362101", "1986": "24362101", "1987": "24362101", "1988": "24362101", "1989": "24362101", "1990": "24362101", "1991": "24362101", "1992": "24362101", "1993": "24244501", "1994": "24244501", "1995": "24244501", "1996": "24244501", "1997": "24244501", "1998": "24244501", "1999": "24244501", "2000": "24244501", "2001": "24244501", "2002": "24244501", "2003": "24244501", "2004": "24244501", "2005": "24244501", "2006": "24244501", "2007": "24244501", "2008": "24244501", "2009": "24244501", "2010": "24244501", "2011": "24262633.5", "2012": "24262633.5", "2013": "24262633.5", "2014": "24262633.5"}, "Armenia": {"1961": "29740", "1962": "29740", "1963": "29740", "1964": "29740", "1965": "29740", "1966": "29740", "1967": "29740", "1968": "29740", "1969": "29740", "1970": "29740", "1971": "29740", "1972": "29740", "1973": "29740", "1974": "29740", "1975": "29740", "1976": "29740", "1977": "29740", "1978": "29740", "1979": "29740", "1980": "29740", "1981": "29740", "1982": "29740", "1983": "29740", "1984": "29740", "1985": "29740", "1986": "29740", "1987": "29740", "1988": "29740", "1989": "29740", "1990": "29740", "1991": "29740", "1992": "29740", "1993": "29740", "1994": "29740", "1995": "29740", "1996": "29740", "1997": "29740", "1998": "29740", "1999": "29740", "2000": "29740", "2001": "29740", "2002": "29740", "2003": "29740", "2004": "29740", "2005": "29740", "2006": "29740", "2007": "29740", "2008": "29740", "2009": "29740", "2010": "29740", "2011": "29740", "2012": "29740", "2013": "29740", "2014": "29740"}, "Small states": {"1961": "2404291", "1962": "2404291", "1963": "2404291", "1964": "2404291", "1965": "2404291", "1966": "2404291", "1967": "2404291", "1968": "2404291", "1969": "2404291", "1970": "2404291", "1971": "2404291", "1972": "2404291", "1973": "2404291", "1974": "2404291", "1975": "2404291", "1976": "2404291", "1977": "2404291", "1978": "2404291", "1979": "2404291", "1980": "2404201", "1981": "2404201", "1982": "2404201", "1983": "2404201", "1984": "2404201", "1985": "2404201", "1986": "2404201", "1987": "2404201", "1988": "2404201", "1989": "2404201", "1990": "2404201", "1991": "2405541", "1992": "2405541", "1993": "2405541", "1994": "2398618", "1995": "2398618", "1996": "2398618", "1997": "2398618", "1998": "2398618", "1999": "2398618", "2000": "2398618", "2001": "2398618", "2002": "2398618", "2003": "2398618", "2004": "2396935", "2005": "2396935", "2006": "2396935", "2007": "2396935", "2008": "2396935", "2009": "2396935", "2010": "2396935", "2011": "2396935", "2012": "2396935", "2013": "2396935", "2014": "2396935"}, "Timor-Leste": {"1961": "14870", "1962": "14870", "1963": "14870", "1964": "14870", "1965": "14870", "1966": "14870", "1967": "14870", "1968": "14870", "1969": "14870", "1970": "14870", "1971": "14870", "1972": "14870", "1973": "14870", "1974": "14870", "1975": "14870", "1976": "14870", "1977": "14870", "1978": "14870", "1979": "14870", "1980": "14870", "1981": "14870", "1982": "14870", "1983": "14870", "1984": "14870", "1985": "14870", "1986": "14870", "1987": "14870", "1988": "14870", "1989": "14870", "1990": "14870", "1991": "14870", "1992": "14870", "1993": "14870", "1994": "14870", "1995": "14870", "1996": "14870", "1997": "14870", "1998": "14870", "1999": "14870", "2000": "14870", "2001": "14870", "2002": "14870", "2003": "14870", "2004": "14870", "2005": "14870", "2006": "14870", "2007": "14870", "2008": "14870", "2009": "14870", "2010": "14870", "2011": "14870", "2012": "14870", "2013": "14870", "2014": "14870"}, "Dominican Republic": {"1961": "48670", "1962": "48670", "1963": "48670", "1964": "48670", "1965": "48670", "1966": "48670", "1967": "48670", "1968": "48670", "1969": "48670", "1970": "48670", "1971": "48670", "1972": "48670", "1973": "48670", "1974": "48670", "1975": "48670", "1976": "48670", "1977": "48670", "1978": "48670", "1979": "48670", "1980": "48670", "1981": "48670", "1982": "48670", "1983": "48670", "1984": "48670", "1985": "48670", "1986": "48670", "1987": "48670", "1988": "48670", "1989": "48670", "1990": "48670", "1991": "48670", "1992": "48670", "1993": "48670", "1994": "48670", "1995": "48670", "1996": "48670", "1997": "48670", "1998": "48670", "1999": "48670", "2000": "48670", "2001": "48670", "2002": "48670", "2003": "48670", "2004": "48670", "2005": "48670", "2006": "48670", "2007": "48670", "2008": "48670", "2009": "48670", "2010": "48670", "2011": "48670", "2012": "48670", "2013": "48670", "2014": "48670"}, "Sub-Saharan Africa excluding South Africa": {}, "Low income": {"1961": "13928831", "1962": "13928831", "1963": "13928831", "1964": "13928831", "1965": "13928831", "1966": "13928831", "1967": "13928831", "1968": "13928831", "1969": "13928831", "1970": "13928831", "1971": "13928831", "1972": "13928831", "1973": "13928831", "1974": "13928831", "1975": "13928831", "1976": "13928831", "1977": "13928831", "1978": "13928831", "1979": "13928831", "1980": "13928831", "1981": "13928831", "1982": "13928831", "1983": "13928831", "1984": "13928831", "1985": "13928831", "1986": "13928831", "1987": "13928831", "1988": "13928831", "1989": "13928831", "1990": "13928831", "1991": "13928831", "1992": "13928831", "1993": "13811231", "1994": "13811231", "1995": "13811231", "1996": "13811231", "1997": "13811231", "1998": "13811231", "1999": "13811231", "2000": "13811231", "2001": "13811231", "2002": "13811231", "2003": "13811231", "2004": "13811231", "2005": "13811231", "2006": "13811231", "2007": "13811231", "2008": "13811231", "2009": "13811231", "2010": "13811231", "2011": "14455816", "2012": "14455816", "2013": "14455816", "2014": "14455816"}, "Ukraine": {"1961": "603560", "1962": "603560", "1963": "603560", "1964": "603560", "1965": "603560", "1966": "603560", "1967": "603560", "1968": "603560", "1969": "603560", "1970": "603560", "1971": "603560", "1972": "603560", "1973": "603560", "1974": "603560", "1975": "603560", "1976": "603560", "1977": "603560", "1978": "603560", "1979": "603560", "1980": "603560", "1981": "603560", "1982": "603560", "1983": "603560", "1984": "603560", "1985": "603560", "1986": "603560", "1987": "603560", "1988": "603560", "1989": "603560", "1990": "603560", "1991": "603560", "1992": "603560", "1993": "603550", "1994": "603550", "1995": "603550", "1996": "603550", "1997": "603550", "1998": "603550", "1999": "603550", "2000": "603550", "2001": "603550", "2002": "603550", "2003": "603550", "2004": "603550", "2005": "603550", "2006": "603550", "2007": "603550", "2008": "603550", "2009": "603550", "2010": "603550", "2011": "603550", "2012": "603550", "2013": "603550", "2014": "603550"}, "Ghana": {"1961": "238540", "1962": "238540", "1963": "238540", "1964": "238540", "1965": "238540", "1966": "238540", "1967": "238540", "1968": "238540", "1969": "238540", "1970": "238540", "1971": "238540", "1972": "238540", "1973": "238540", "1974": "238540", "1975": "238540", "1976": "238540", "1977": "238540", "1978": "238540", "1979": "238540", "1980": "238540", "1981": "238540", "1982": "238540", "1983": "238540", "1984": "238540", "1985": "238540", "1986": "238540", "1987": "238540", "1988": "238540", "1989": "238540", "1990": "238540", "1991": "238540", "1992": "238540", "1993": "238540", "1994": "238540", "1995": "238540", "1996": "238540", "1997": "238540", "1998": "238540", "1999": "238540", "2000": "238540", "2001": "238540", "2002": "238540", "2003": "238540", "2004": "238540", "2005": "238540", "2006": "238540", "2007": "238540", "2008": "238540", "2009": "238540", "2010": "238540", "2011": "238540", "2012": "238540", "2013": "238540", "2014": "238540"}, "Tonga": {"1961": "750", "1962": "750", "1963": "750", "1964": "750", "1965": "750", "1966": "750", "1967": "750", "1968": "750", "1969": "750", "1970": "750", "1971": "750", "1972": "750", "1973": "750", "1974": "750", "1975": "750", "1976": "750", "1977": "750", "1978": "750", "1979": "750", "1980": "750", "1981": "750", "1982": "750", "1983": "750", "1984": "750", "1985": "750", "1986": "750", "1987": "750", "1988": "750", "1989": "750", "1990": "750", "1991": "750", "1992": "750", "1993": "750", "1994": "750", "1995": "750", "1996": "750", "1997": "750", "1998": "750", "1999": "750", "2000": "750", "2001": "750", "2002": "750", "2003": "750", "2004": "750", "2005": "750", "2006": "750", "2007": "750", "2008": "750", "2009": "750", "2010": "750", "2011": "750", "2012": "750", "2013": "750", "2014": "750"}, "Finland": {"1961": "338150", "1962": "338150", "1963": "338150", "1964": "338150", "1965": "338150", "1966": "338150", "1967": "338150", "1968": "338150", "1969": "338150", "1970": "338150", "1971": "338150", "1972": "338150", "1973": "338150", "1974": "338150", "1975": "338150", "1976": "338150", "1977": "338150", "1978": "338150", "1979": "338150", "1980": "338150", "1981": "338150", "1982": "338150", "1983": "338150", "1984": "338150", "1985": "338150", "1986": "338150", "1987": "338150", "1988": "338150", "1989": "338150", "1990": "338150", "1991": "338150", "1992": "338150", "1993": "338150", "1994": "338150", "1995": "338150", "1996": "338150", "1997": "338150", "1998": "338150", "1999": "338150", "2000": "338150", "2001": "338150", "2002": "338150", "2003": "338150", "2004": "338150", "2005": "338150", "2006": "338440", "2007": "338420", "2008": "338420", "2009": "338420", "2010": "338420", "2011": "338420", "2012": "338420", "2013": "338420", "2014": "338420"}, "Latin America & Caribbean (developing only)": {"1961": "15796480", "1962": "15796480", "1963": "15796480", "1964": "15796480", "1965": "15796480", "1966": "15796480", "1967": "15796480", "1968": "15796480", "1969": "15796480", "1970": "15796480", "1971": "15796480", "1972": "15796480", "1973": "15796480", "1974": "15796480", "1975": "15796480", "1976": "15796480", "1977": "15796480", "1978": "15796480", "1979": "15796480", "1980": "15796480", "1981": "15796480", "1982": "15796480", "1983": "15796480", "1984": "15796480", "1985": "15796480", "1986": "15796480", "1987": "15796480", "1988": "15796480", "1989": "15796480", "1990": "15796480", "1991": "15796480", "1992": "15796480", "1993": "15796480", "1994": "15796480", "1995": "15796480", "1996": "15796480", "1997": "15796480", "1998": "15769290", "1999": "15769290", "2000": "15769290", "2001": "15769290", "2002": "15769290", "2003": "15769290", "2004": "15769290", "2005": "15769290", "2006": "15769290", "2007": "15769290", "2008": "15769290", "2009": "15769290", "2010": "15769282", "2011": "15769282", "2012": "15769280", "2013": "15769280", "2014": "15769280"}, "High income": {"1961": "57421692.4", "1962": "57421692.4", "1963": "57421692.4", "1964": "57421692.4", "1965": "57421692.4", "1966": "57421692.4", "1967": "57421692.4", "1968": "57421692.4", "1969": "57421692.4", "1970": "57421692.4", "1971": "57421692.4", "1972": "57421692.4", "1973": "57421692.4", "1974": "57421692.4", "1975": "57421692.4", "1976": "57421692.4", "1977": "57421692.4", "1978": "57421692.4", "1979": "57421692.4", "1980": "57421602.4", "1981": "57421602.4", "1982": "57421602.4", "1983": "57421602.4", "1984": "57421602.4", "1985": "57421602.4", "1986": "57421602.4", "1987": "57421602.4", "1988": "57421602.4", "1989": "57421602.4", "1990": "57421602.4", "1991": "57422062.4", "1992": "57422082.4", "1993": "57422102.4", "1994": "57422112.4", "1995": "57422142.4", "1996": "57422232.4", "1997": "57490982.4", "1998": "57490912.4", "1999": "57490912.4", "2000": "57525992.4", "2001": "57526378.4", "2002": "57526754.4", "2003": "57526846.4", "2004": "57526949.4", "2005": "57527009.4", "2006": "57527345", "2007": "57527386.6", "2008": "57727017.6", "2009": "57727239.9", "2010": "57727555.1", "2011": "57727504.3", "2012": "57724785.3", "2013": "57724785.3", "2014": "57724785.3"}, "Libya": {"1961": "1759540", "1962": "1759540", "1963": "1759540", "1964": "1759540", "1965": "1759540", "1966": "1759540", "1967": "1759540", "1968": "1759540", "1969": "1759540", "1970": "1759540", "1971": "1759540", "1972": "1759540", "1973": "1759540", "1974": "1759540", "1975": "1759540", "1976": "1759540", "1977": "1759540", "1978": "1759540", "1979": "1759540", "1980": "1759540", "1981": "1759540", "1982": "1759540", "1983": "1759540", "1984": "1759540", "1985": "1759540", "1986": "1759540", "1987": "1759540", "1988": "1759540", "1989": "1759540", "1990": "1759540", "1991": "1759540", "1992": "1759540", "1993": "1759540", "1994": "1759540", "1995": "1759540", "1996": "1759540", "1997": "1759540", "1998": "1759540", "1999": "1759540", "2000": "1759540", "2001": "1759540", "2002": "1759540", "2003": "1759540", "2004": "1759540", "2005": "1759540", "2006": "1759540", "2007": "1759540", "2008": "1759540", "2009": "1759540", "2010": "1759540", "2011": "1759540", "2012": "1759540", "2013": "1759540", "2014": "1759540"}, "Korea, Rep.": {"1961": "99260", "1962": "99260", "1963": "99260", "1964": "99260", "1965": "99260", "1966": "99260", "1967": "99260", "1968": "99260", "1969": "99260", "1970": "99260", "1971": "99260", "1972": "99260", "1973": "99260", "1974": "99260", "1975": "99260", "1976": "99260", "1977": "99260", "1978": "99260", "1979": "99260", "1980": "99260", "1981": "99260", "1982": "99260", "1983": "99260", "1984": "99260", "1985": "99260", "1986": "99260", "1987": "99260", "1988": "99260", "1989": "99260", "1990": "99260", "1991": "99260", "1992": "99260", "1993": "99260", "1994": "99260", "1995": "99260", "1996": "99260", "1997": "99260", "1998": "99260", "1999": "99260", "2000": "99260", "2001": "99540", "2002": "99590", "2003": "99600", "2004": "99620", "2005": "99650", "2006": "99680", "2007": "99720", "2008": "99830", "2009": "99900", "2010": "100030", "2011": "100030", "2012": "100150", "2013": "100150", "2014": "100150"}, "Cayman Islands": {"1961": "264", "1962": "264", "1963": "264", "1964": "264", "1965": "264", "1966": "264", "1967": "264", "1968": "264", "1969": "264", "1970": "264", "1971": "264", "1972": "264", "1973": "264", "1974": "264", "1975": "264", "1976": "264", "1977": "264", "1978": "264", "1979": "264", "1980": "264", "1981": "264", "1982": "264", "1983": "264", "1984": "264", "1985": "264", "1986": "264", "1987": "264", "1988": "264", "1989": "264", "1990": "264", "1991": "264", "1992": "264", "1993": "264", "1994": "264", "1995": "264", "1996": "264", "1997": "264", "1998": "264", "1999": "264", "2000": "264", "2001": "264", "2002": "264", "2003": "264", "2004": "264", "2005": "264", "2006": "264", "2007": "264", "2008": "264", "2009": "264", "2010": "264", "2011": "264", "2012": "264", "2013": "264", "2014": "264"}, "Central African Republic": {"1961": "622980", "1962": "622980", "1963": "622980", "1964": "622980", "1965": "622980", "1966": "622980", "1967": "622980", "1968": "622980", "1969": "622980", "1970": "622980", "1971": "622980", "1972": "622980", "1973": "622980", "1974": "622980", "1975": "622980", "1976": "622980", "1977": "622980", "1978": "622980", "1979": "622980", "1980": "622980", "1981": "622980", "1982": "622980", "1983": "622980", "1984": "622980", "1985": "622980", "1986": "622980", "1987": "622980", "1988": "622980", "1989": "622980", "1990": "622980", "1991": "622980", "1992": "622980", "1993": "622980", "1994": "622980", "1995": "622980", "1996": "622980", "1997": "622980", "1998": "622980", "1999": "622980", "2000": "622980", "2001": "622980", "2002": "622980", "2003": "622980", "2004": "622980", "2005": "622980", "2006": "622980", "2007": "622980", "2008": "622980", "2009": "622980", "2010": "622980", "2011": "622980", "2012": "622980", "2013": "622980", "2014": "622980"}, "Europe & Central Asia (all income levels)": {"1961": "28360847", "1962": "28360847", "1963": "28360847", "1964": "28360847", "1965": "28360847", "1966": "28360847", "1967": "28360847", "1968": "28360847", "1969": "28360847", "1970": "28360847", "1971": "28360847", "1972": "28360847", "1973": "28360847", "1974": "28360847", "1975": "28360847", "1976": "28360847", "1977": "28360847", "1978": "28360847", "1979": "28360847", "1980": "28360847", "1981": "28360847", "1982": "28360847", "1983": "28360847", "1984": "28360847", "1985": "28360847", "1986": "28360847", "1987": "28360847", "1988": "28360847", "1989": "28360847", "1990": "28360847", "1991": "28360847", "1992": "28360847", "1993": "28360937", "1994": "28360947", "1995": "28360977", "1996": "28361057", "1997": "28429797", "1998": "28429727", "1999": "28429727", "2000": "28461857", "2001": "28461877", "2002": "28462187", "2003": "28462237", "2004": "28462317", "2005": "28462337", "2006": "28462627", "2007": "28462607", "2008": "28462623", "2009": "28462767", "2010": "28462947", "2011": "28462889", "2012": "28460043", "2013": "28460043", "2014": "28460043"}, "Mauritius": {"1961": "2040", "1962": "2040", "1963": "2040", "1964": "2040", "1965": "2040", "1966": "2040", "1967": "2040", "1968": "2040", "1969": "2040", "1970": "2040", "1971": "2040", "1972": "2040", "1973": "2040", "1974": "2040", "1975": "2040", "1976": "2040", "1977": "2040", "1978": "2040", "1979": "2040", "1980": "2040", "1981": "2040", "1982": "2040", "1983": "2040", "1984": "2040", "1985": "2040", "1986": "2040", "1987": "2040", "1988": "2040", "1989": "2040", "1990": "2040", "1991": "2040", "1992": "2040", "1993": "2040", "1994": "2040", "1995": "2040", "1996": "2040", "1997": "2040", "1998": "2040", "1999": "2040", "2000": "2040", "2001": "2040", "2002": "2040", "2003": "2040", "2004": "2040", "2005": "2040", "2006": "2040", "2007": "2040", "2008": "2040", "2009": "2040", "2010": "2040", "2011": "2040", "2012": "2040", "2013": "2040", "2014": "2040"}, "Liechtenstein": {"1961": "160", "1962": "160", "1963": "160", "1964": "160", "1965": "160", "1966": "160", "1967": "160", "1968": "160", "1969": "160", "1970": "160", "1971": "160", "1972": "160", "1973": "160", "1974": "160", "1975": "160", "1976": "160", "1977": "160", "1978": "160", "1979": "160", "1980": "160", "1981": "160", "1982": "160", "1983": "160", "1984": "160", "1985": "160", "1986": "160", "1987": "160", "1988": "160", "1989": "160", "1990": "160", "1991": "160", "1992": "160", "1993": "160", "1994": "160", "1995": "160", "1996": "160", "1997": "160", "1998": "160", "1999": "160", "2000": "160", "2001": "160", "2002": "160", "2003": "160", "2004": "160", "2005": "160", "2006": "160", "2007": "160", "2008": "160", "2009": "160", "2010": "160", "2011": "160", "2012": "160", "2013": "160", "2014": "160"}, "Belarus": {"1961": "207600", "1962": "207600", "1963": "207600", "1964": "207600", "1965": "207600", "1966": "207600", "1967": "207600", "1968": "207600", "1969": "207600", "1970": "207600", "1971": "207600", "1972": "207600", "1973": "207600", "1974": "207600", "1975": "207600", "1976": "207600", "1977": "207600", "1978": "207600", "1979": "207600", "1980": "207600", "1981": "207600", "1982": "207600", "1983": "207600", "1984": "207600", "1985": "207600", "1986": "207600", "1987": "207600", "1988": "207600", "1989": "207600", "1990": "207600", "1991": "207600", "1992": "207600", "1993": "207600", "1994": "207600", "1995": "207600", "1996": "207600", "1997": "207600", "1998": "207600", "1999": "207600", "2000": "207600", "2001": "207600", "2002": "207600", "2003": "207600", "2004": "207600", "2005": "207600", "2006": "207600", "2007": "207600", "2008": "207600", "2009": "207600", "2010": "207600", "2011": "207600", "2012": "207600", "2013": "207600", "2014": "207600"}, "Mali": {"1961": "1240190", "1962": "1240190", "1963": "1240190", "1964": "1240190", "1965": "1240190", "1966": "1240190", "1967": "1240190", "1968": "1240190", "1969": "1240190", "1970": "1240190", "1971": "1240190", "1972": "1240190", "1973": "1240190", "1974": "1240190", "1975": "1240190", "1976": "1240190", "1977": "1240190", "1978": "1240190", "1979": "1240190", "1980": "1240190", "1981": "1240190", "1982": "1240190", "1983": "1240190", "1984": "1240190", "1985": "1240190", "1986": "1240190", "1987": "1240190", "1988": "1240190", "1989": "1240190", "1990": "1240190", "1991": "1240190", "1992": "1240190", "1993": "1240190", "1994": "1240190", "1995": "1240190", "1996": "1240190", "1997": "1240190", "1998": "1240190", "1999": "1240190", "2000": "1240190", "2001": "1240190", "2002": "1240190", "2003": "1240190", "2004": "1240190", "2005": "1240190", "2006": "1240190", "2007": "1240190", "2008": "1240190", "2009": "1240190", "2010": "1240190", "2011": "1240190", "2012": "1240190", "2013": "1240190", "2014": "1240190"}, "Micronesia, Fed. Sts.": {"1991": "700", "1992": "700", "1993": "700", "1994": "700", "1995": "700", "1996": "700", "1997": "700", "1998": "700", "1999": "700", "2000": "700", "2001": "700", "2002": "700", "2003": "700", "2004": "700", "2005": "700", "2006": "700", "2007": "700", "2008": "700", "2009": "700", "2010": "700", "2011": "700", "2012": "700", "2013": "700", "2014": "700"}, "Korea, Dem. Rep.": {"1961": "120540", "1962": "120540", "1963": "120540", "1964": "120540", "1965": "120540", "1966": "120540", "1967": "120540", "1968": "120540", "1969": "120540", "1970": "120540", "1971": "120540", "1972": "120540", "1973": "120540", "1974": "120540", "1975": "120540", "1976": "120540", "1977": "120540", "1978": "120540", "1979": "120540", "1980": "120540", "1981": "120540", "1982": "120540", "1983": "120540", "1984": "120540", "1985": "120540", "1986": "120540", "1987": "120540", "1988": "120540", "1989": "120540", "1990": "120540", "1991": "120540", "1992": "120540", "1993": "120540", "1994": "120540", "1995": "120540", "1996": "120540", "1997": "120540", "1998": "120540", "1999": "120540", "2000": "120540", "2001": "120540", "2002": "120540", "2003": "120540", "2004": "120540", "2005": "120540", "2006": "120540", "2007": "120540", "2008": "120540", "2009": "120540", "2010": "120540", "2011": "120540", "2012": "120540", "2013": "120540", "2014": "120540"}, "Sub-Saharan Africa excluding South Africa and Nigeria": {}, "Bulgaria": {"1961": "110990", "1962": "110990", "1963": "110990", "1964": "110990", "1965": "110990", "1966": "110990", "1967": "110990", "1968": "110990", "1969": "110990", "1970": "110990", "1971": "110990", "1972": "110990", "1973": "110990", "1974": "110990", "1975": "110990", "1976": "110990", "1977": "110990", "1978": "110990", "1979": "110990", "1980": "110990", "1981": "110990", "1982": "110990", "1983": "110990", "1984": "110990", "1985": "110990", "1986": "110990", "1987": "110990", "1988": "110990", "1989": "110990", "1990": "110990", "1991": "110990", "1992": "110990", "1993": "110990", "1994": "110990", "1995": "110990", "1996": "110990", "1997": "110990", "1998": "110990", "1999": "110990", "2000": "110990", "2001": "110990", "2002": "110990", "2003": "110990", "2004": "111000", "2005": "111000", "2006": "111000", "2007": "111000", "2008": "111000", "2009": "111000", "2010": "111000", "2011": "111000", "2012": "111000", "2013": "111000", "2014": "111000"}, "North America": {"1961": "19613810", "1962": "19613810", "1963": "19613810", "1964": "19613810", "1965": "19613810", "1966": "19613810", "1967": "19613810", "1968": "19613810", "1969": "19613810", "1970": "19613810", "1971": "19613810", "1972": "19613810", "1973": "19613810", "1974": "19613810", "1975": "19613810", "1976": "19613810", "1977": "19613810", "1978": "19613810", "1979": "19613810", "1980": "19613810", "1981": "19613810", "1982": "19613810", "1983": "19613810", "1984": "19613810", "1985": "19613810", "1986": "19613810", "1987": "19613810", "1988": "19613810", "1989": "19613810", "1990": "19613810", "1991": "19613810", "1992": "19613810", "1993": "19613810", "1994": "19613810", "1995": "19613810", "1996": "19613810", "1997": "19613810", "1998": "19613810", "1999": "19613810", "2000": "19616750", "2001": "19616750", "2002": "19616750", "2003": "19616750", "2004": "19616750", "2005": "19616750", "2006": "19616750", "2007": "19616750", "2008": "19816230", "2009": "19816230", "2010": "19816230", "2011": "19816230", "2012": "19816230", "2013": "19816230", "2014": "19816230"}, "Romania": {"1961": "238390", "1962": "238390", "1963": "238390", "1964": "238390", "1965": "238390", "1966": "238390", "1967": "238390", "1968": "238390", "1969": "238390", "1970": "238390", "1971": "238390", "1972": "238390", "1973": "238390", "1974": "238390", "1975": "238390", "1976": "238390", "1977": "238390", "1978": "238390", "1979": "238390", "1980": "238390", "1981": "238390", "1982": "238390", "1983": "238390", "1984": "238390", "1985": "238390", "1986": "238390", "1987": "238390", "1988": "238390", "1989": "238390", "1990": "238390", "1991": "238390", "1992": "238390", "1993": "238390", "1994": "238390", "1995": "238390", "1996": "238390", "1997": "238390", "1998": "238390", "1999": "238390", "2000": "238390", "2001": "238390", "2002": "238390", "2003": "238390", "2004": "238390", "2005": "238390", "2006": "238390", "2007": "238390", "2008": "238390", "2009": "238390", "2010": "238390", "2011": "238390", "2012": "238390", "2013": "238390", "2014": "238390"}, "Angola": {"1961": "1246700", "1962": "1246700", "1963": "1246700", "1964": "1246700", "1965": "1246700", "1966": "1246700", "1967": "1246700", "1968": "1246700", "1969": "1246700", "1970": "1246700", "1971": "1246700", "1972": "1246700", "1973": "1246700", "1974": "1246700", "1975": "1246700", "1976": "1246700", "1977": "1246700", "1978": "1246700", "1979": "1246700", "1980": "1246700", "1981": "1246700", "1982": "1246700", "1983": "1246700", "1984": "1246700", "1985": "1246700", "1986": "1246700", "1987": "1246700", "1988": "1246700", "1989": "1246700", "1990": "1246700", "1991": "1246700", "1992": "1246700", "1993": "1246700", "1994": "1246700", "1995": "1246700", "1996": "1246700", "1997": "1246700", "1998": "1246700", "1999": "1246700", "2000": "1246700", "2001": "1246700", "2002": "1246700", "2003": "1246700", "2004": "1246700", "2005": "1246700", "2006": "1246700", "2007": "1246700", "2008": "1246700", "2009": "1246700", "2010": "1246700", "2011": "1246700", "2012": "1246700", "2013": "1246700", "2014": "1246700"}, "Central Europe and the Baltics": {"1961": "1134899", "1962": "1134899", "1963": "1134899", "1964": "1134899", "1965": "1134899", "1966": "1134899", "1967": "1134899", "1968": "1134899", "1969": "1134899", "1970": "1134899", "1971": "1134899", "1972": "1134899", "1973": "1134899", "1974": "1134899", "1975": "1134899", "1976": "1134899", "1977": "1134899", "1978": "1134899", "1979": "1134899", "1980": "1134899", "1981": "1134899", "1982": "1134899", "1983": "1134899", "1984": "1134899", "1985": "1134899", "1986": "1134899", "1987": "1134899", "1988": "1134899", "1989": "1134899", "1990": "1134899", "1991": "1134899", "1992": "1134899", "1993": "1134899", "1994": "1134899", "1995": "1134899", "1996": "1134969", "1997": "1134969", "1998": "1134899", "1999": "1134899", "2000": "1134899", "2001": "1134899", "2002": "1134899", "2003": "1134899", "2004": "1134959", "2005": "1134959", "2006": "1134949", "2007": "1134949", "2008": "1134954", "2009": "1134960", "2010": "1134907", "2011": "1134876", "2012": "1134876", "2013": "1134876", "2014": "1134876"}, "Egypt, Arab Rep.": {"1961": "1001450", "1962": "1001450", "1963": "1001450", "1964": "1001450", "1965": "1001450", "1966": "1001450", "1967": "1001450", "1968": "1001450", "1969": "1001450", "1970": "1001450", "1971": "1001450", "1972": "1001450", "1973": "1001450", "1974": "1001450", "1975": "1001450", "1976": "1001450", "1977": "1001450", "1978": "1001450", "1979": "1001450", "1980": "1001450", "1981": "1001450", "1982": "1001450", "1983": "1001450", "1984": "1001450", "1985": "1001450", "1986": "1001450", "1987": "1001450", "1988": "1001450", "1989": "1001450", "1990": "1001450", "1991": "1001450", "1992": "1001450", "1993": "1001450", "1994": "1001450", "1995": "1001450", "1996": "1001450", "1997": "1001450", "1998": "1001450", "1999": "1001450", "2000": "1001450", "2001": "1001450", "2002": "1001450", "2003": "1001450", "2004": "1001450", "2005": "1001450", "2006": "1001450", "2007": "1001450", "2008": "1001450", "2009": "1001450", "2010": "1001450", "2011": "1001450", "2012": "1001450", "2013": "1001450", "2014": "1001450"}, "Trinidad and Tobago": {"1961": "5130", "1962": "5130", "1963": "5130", "1964": "5130", "1965": "5130", "1966": "5130", "1967": "5130", "1968": "5130", "1969": "5130", "1970": "5130", "1971": "5130", "1972": "5130", "1973": "5130", "1974": "5130", "1975": "5130", "1976": "5130", "1977": "5130", "1978": "5130", "1979": "5130", "1980": "5130", "1981": "5130", "1982": "5130", "1983": "5130", "1984": "5130", "1985": "5130", "1986": "5130", "1987": "5130", "1988": "5130", "1989": "5130", "1990": "5130", "1991": "5130", "1992": "5130", "1993": "5130", "1994": "5130", "1995": "5130", "1996": "5130", "1997": "5130", "1998": "5130", "1999": "5130", "2000": "5130", "2001": "5130", "2002": "5130", "2003": "5130", "2004": "5130", "2005": "5130", "2006": "5130", "2007": "5130", "2008": "5130", "2009": "5130", "2010": "5130", "2011": "5130", "2012": "5130", "2013": "5130", "2014": "5130"}, "St. Vincent and the Grenadines": {"1961": "390", "1962": "390", "1963": "390", "1964": "390", "1965": "390", "1966": "390", "1967": "390", "1968": "390", "1969": "390", "1970": "390", "1971": "390", "1972": "390", "1973": "390", "1974": "390", "1975": "390", "1976": "390", "1977": "390", "1978": "390", "1979": "390", "1980": "390", "1981": "390", "1982": "390", "1983": "390", "1984": "390", "1985": "390", "1986": "390", "1987": "390", "1988": "390", "1989": "390", "1990": "390", "1991": "390", "1992": "390", "1993": "390", "1994": "390", "1995": "390", "1996": "390", "1997": "390", "1998": "390", "1999": "390", "2000": "390", "2001": "390", "2002": "390", "2003": "390", "2004": "390", "2005": "390", "2006": "390", "2007": "390", "2008": "390", "2009": "390", "2010": "390", "2011": "390", "2012": "390", "2013": "390", "2014": "390"}, "Cyprus": {"1961": "9250", "1962": "9250", "1963": "9250", "1964": "9250", "1965": "9250", "1966": "9250", "1967": "9250", "1968": "9250", "1969": "9250", "1970": "9250", "1971": "9250", "1972": "9250", "1973": "9250", "1974": "9250", "1975": "9250", "1976": "9250", "1977": "9250", "1978": "9250", "1979": "9250", "1980": "9250", "1981": "9250", "1982": "9250", "1983": "9250", "1984": "9250", "1985": "9250", "1986": "9250", "1987": "9250", "1988": "9250", "1989": "9250", "1990": "9250", "1991": "9250", "1992": "9250", "1993": "9250", "1994": "9250", "1995": "9250", "1996": "9250", "1997": "9250", "1998": "9250", "1999": "9250", "2000": "9250", "2001": "9250", "2002": "9250", "2003": "9250", "2004": "9250", "2005": "9250", "2006": "9250", "2007": "9250", "2008": "9250", "2009": "9250", "2010": "9250", "2011": "9250", "2012": "9250", "2013": "9250", "2014": "9250"}, "Caribbean small states": {"1961": "435080", "1962": "435080", "1963": "435080", "1964": "435080", "1965": "435080", "1966": "435080", "1967": "435080", "1968": "435080", "1969": "435080", "1970": "435080", "1971": "435080", "1972": "435080", "1973": "435080", "1974": "435080", "1975": "435080", "1976": "435080", "1977": "435080", "1978": "435080", "1979": "435080", "1980": "434990", "1981": "434990", "1982": "434990", "1983": "434990", "1984": "434990", "1985": "434990", "1986": "434990", "1987": "434990", "1988": "434990", "1989": "434990", "1990": "434990", "1991": "434990", "1992": "434990", "1993": "434990", "1994": "434990", "1995": "434990", "1996": "434990", "1997": "434990", "1998": "434990", "1999": "434990", "2000": "434990", "2001": "434990", "2002": "434990", "2003": "434990", "2004": "434990", "2005": "434990", "2006": "434990", "2007": "434990", "2008": "434990", "2009": "434990", "2010": "434990", "2011": "434990", "2012": "434990", "2013": "434990", "2014": "434990"}, "Brunei Darussalam": {"1961": "5770", "1962": "5770", "1963": "5770", "1964": "5770", "1965": "5770", "1966": "5770", "1967": "5770", "1968": "5770", "1969": "5770", "1970": "5770", "1971": "5770", "1972": "5770", "1973": "5770", "1974": "5770", "1975": "5770", "1976": "5770", "1977": "5770", "1978": "5770", "1979": "5770", "1980": "5770", "1981": "5770", "1982": "5770", "1983": "5770", "1984": "5770", "1985": "5770", "1986": "5770", "1987": "5770", "1988": "5770", "1989": "5770", "1990": "5770", "1991": "5770", "1992": "5770", "1993": "5770", "1994": "5770", "1995": "5770", "1996": "5770", "1997": "5770", "1998": "5770", "1999": "5770", "2000": "5770", "2001": "5770", "2002": "5770", "2003": "5770", "2004": "5770", "2005": "5770", "2006": "5770", "2007": "5770", "2008": "5770", "2009": "5770", "2010": "5770", "2011": "5770", "2012": "5770", "2013": "5770", "2014": "5770"}, "Qatar": {"1961": "11610", "1962": "11610", "1963": "11610", "1964": "11610", "1965": "11610", "1966": "11610", "1967": "11610", "1968": "11610", "1969": "11610", "1970": "11610", "1971": "11610", "1972": "11610", "1973": "11610", "1974": "11610", "1975": "11610", "1976": "11610", "1977": "11610", "1978": "11610", "1979": "11610", "1980": "11610", "1981": "11610", "1982": "11610", "1983": "11610", "1984": "11610", "1985": "11610", "1986": "11610", "1987": "11610", "1988": "11610", "1989": "11610", "1990": "11610", "1991": "11610", "1992": "11610", "1993": "11610", "1994": "11610", "1995": "11610", "1996": "11610", "1997": "11610", "1998": "11610", "1999": "11610", "2000": "11610", "2001": "11610", "2002": "11610", "2003": "11610", "2004": "11610", "2005": "11610", "2006": "11610", "2007": "11610", "2008": "11610", "2009": "11610", "2010": "11610", "2011": "11610", "2012": "11610", "2013": "11610", "2014": "11610"}, "Middle income": {"1961": "62808287", "1962": "62808287", "1963": "62808287", "1964": "62808287", "1965": "62808287", "1966": "62808287", "1967": "62808287", "1968": "62808287", "1969": "62808287", "1970": "62808287", "1971": "62808287", "1972": "62808287", "1973": "62808287", "1974": "62808287", "1975": "62808287", "1976": "62808287", "1977": "62806167", "1978": "62806167", "1979": "62808207", "1980": "62808287", "1981": "62808287", "1982": "62808287", "1983": "62808287", "1984": "62808287", "1985": "62808287", "1986": "62808287", "1987": "62806947", "1988": "62806957", "1989": "62806957", "1990": "62807627", "1991": "62808997", "1992": "62809027", "1993": "62809117", "1994": "62802194", "1995": "62802194", "1996": "62802184", "1997": "62802174", "1998": "62774984", "1999": "62774984", "2000": "62773104", "2001": "62773108.2", "2002": "62773157.2", "2003": "62773166.7", "2004": "62771507.5", "2005": "62773404.8", "2006": "62773404.4", "2007": "62773403.8", "2008": "62773242.8", "2009": "62770702", "2010": "62770600", "2011": "62144141.5", "2012": "62144139.5", "2013": "62144139.5", "2014": "62144139.5"}, "Austria": {"1961": "83870", "1962": "83870", "1963": "83870", "1964": "83870", "1965": "83870", "1966": "83870", "1967": "83870", "1968": "83870", "1969": "83870", "1970": "83870", "1971": "83870", "1972": "83870", "1973": "83870", "1974": "83870", "1975": "83870", "1976": "83870", "1977": "83870", "1978": "83870", "1979": "83870", "1980": "83870", "1981": "83870", "1982": "83870", "1983": "83870", "1984": "83870", "1985": "83870", "1986": "83870", "1987": "83870", "1988": "83870", "1989": "83870", "1990": "83870", "1991": "83870", "1992": "83870", "1993": "83870", "1994": "83870", "1995": "83870", "1996": "83870", "1997": "83870", "1998": "83870", "1999": "83870", "2000": "83870", "2001": "83870", "2002": "83870", "2003": "83870", "2004": "83870", "2005": "83870", "2006": "83870", "2007": "83870", "2008": "83870", "2009": "83879", "2010": "83879", "2011": "83879", "2012": "83879", "2013": "83879", "2014": "83879"}, "High income: OECD": {"1961": "33214795", "1962": "33214795", "1963": "33214795", "1964": "33214795", "1965": "33214795", "1966": "33214795", "1967": "33214795", "1968": "33214795", "1969": "33214795", "1970": "33214795", "1971": "33214795", "1972": "33214795", "1973": "33214795", "1974": "33214795", "1975": "33214795", "1976": "33214795", "1977": "33214795", "1978": "33214795", "1979": "33214795", "1980": "33214795", "1981": "33214795", "1982": "33214795", "1983": "33214795", "1984": "33214795", "1985": "33214795", "1986": "33214795", "1987": "33214795", "1988": "33214795", "1989": "33214795", "1990": "33214795", "1991": "33214795", "1992": "33214795", "1993": "33214815", "1994": "33214825", "1995": "33214845", "1996": "33214855", "1997": "33214855", "1998": "33214855", "1999": "33214855", "2000": "33249925", "2001": "33250305", "2002": "33250675", "2003": "33250745", "2004": "33250785", "2005": "33250835", "2006": "33251165", "2007": "33251195", "2008": "33450811", "2009": "33451032", "2010": "33451399", "2011": "33451376", "2012": "33448655", "2013": "33448655", "2014": "33448655"}, "Mozambique": {"1961": "799380", "1962": "799380", "1963": "799380", "1964": "799380", "1965": "799380", "1966": "799380", "1967": "799380", "1968": "799380", "1969": "799380", "1970": "799380", "1971": "799380", "1972": "799380", "1973": "799380", "1974": "799380", "1975": "799380", "1976": "799380", "1977": "799380", "1978": "799380", "1979": "799380", "1980": "799380", "1981": "799380", "1982": "799380", "1983": "799380", "1984": "799380", "1985": "799380", "1986": "799380", "1987": "799380", "1988": "799380", "1989": "799380", "1990": "799380", "1991": "799380", "1992": "799380", "1993": "799380", "1994": "799380", "1995": "799380", "1996": "799380", "1997": "799380", "1998": "799380", "1999": "799380", "2000": "799380", "2001": "799380", "2002": "799380", "2003": "799380", "2004": "799380", "2005": "799380", "2006": "799380", "2007": "799380", "2008": "799380", "2009": "799380", "2010": "799380", "2011": "799380", "2012": "799380", "2013": "799380", "2014": "799380"}, "Uganda": {"1961": "241550", "1962": "241550", "1963": "241550", "1964": "241550", "1965": "241550", "1966": "241550", "1967": "241550", "1968": "241550", "1969": "241550", "1970": "241550", "1971": "241550", "1972": "241550", "1973": "241550", "1974": "241550", "1975": "241550", "1976": "241550", "1977": "241550", "1978": "241550", "1979": "241550", "1980": "241550", "1981": "241550", "1982": "241550", "1983": "241550", "1984": "241550", "1985": "241550", "1986": "241550", "1987": "241550", "1988": "241550", "1989": "241550", "1990": "241550", "1991": "241550", "1992": "241550", "1993": "241550", "1994": "241550", "1995": "241550", "1996": "241550", "1997": "241550", "1998": "241550", "1999": "241550", "2000": "241550", "2001": "241550", "2002": "241550", "2003": "241550", "2004": "241550", "2005": "241550", "2006": "241550", "2007": "241550", "2008": "241550", "2009": "241550", "2010": "241550", "2011": "241550", "2012": "241550", "2013": "241550", "2014": "241550"}, "Kyrgyz Republic": {"1961": "199950", "1962": "199950", "1963": "199950", "1964": "199950", "1965": "199950", "1966": "199950", "1967": "199950", "1968": "199950", "1969": "199950", "1970": "199950", "1971": "199950", "1972": "199950", "1973": "199950", "1974": "199950", "1975": "199950", "1976": "199950", "1977": "199950", "1978": "199950", "1979": "199950", "1980": "199950", "1981": "199950", "1982": "199950", "1983": "199950", "1984": "199950", "1985": "199950", "1986": "199950", "1987": "199950", "1988": "199950", "1989": "199950", "1990": "199950", "1991": "199950", "1992": "199950", "1993": "199950", "1994": "199950", "1995": "199950", "1996": "199950", "1997": "199950", "1998": "199950", "1999": "199950", "2000": "199950", "2001": "199950", "2002": "199950", "2003": "199950", "2004": "199950", "2005": "199950", "2006": "199950", "2007": "199950", "2008": "199950", "2009": "199949", "2010": "199949", "2011": "199949", "2012": "199949", "2013": "199949", "2014": "199949"}, "Hungary": {"1961": "93030", "1962": "93030", "1963": "93030", "1964": "93030", "1965": "93030", "1966": "93030", "1967": "93030", "1968": "93030", "1969": "93030", "1970": "93030", "1971": "93030", "1972": "93030", "1973": "93030", "1974": "93030", "1975": "93030", "1976": "93030", "1977": "93030", "1978": "93030", "1979": "93030", "1980": "93030", "1981": "93030", "1982": "93030", "1983": "93030", "1984": "93030", "1985": "93030", "1986": "93030", "1987": "93030", "1988": "93030", "1989": "93030", "1990": "93030", "1991": "93030", "1992": "93030", "1993": "93030", "1994": "93030", "1995": "93030", "1996": "93030", "1997": "93030", "1998": "93030", "1999": "93030", "2000": "93030", "2001": "93030", "2002": "93030", "2003": "93030", "2004": "93030", "2005": "93030", "2006": "93030", "2007": "93030", "2008": "93030", "2009": "93030", "2010": "93030", "2011": "93030", "2012": "93030", "2013": "93030", "2014": "93030"}, "Niger": {"1961": "1267000", "1962": "1267000", "1963": "1267000", "1964": "1267000", "1965": "1267000", "1966": "1267000", "1967": "1267000", "1968": "1267000", "1969": "1267000", "1970": "1267000", "1971": "1267000", "1972": "1267000", "1973": "1267000", "1974": "1267000", "1975": "1267000", "1976": "1267000", "1977": "1267000", "1978": "1267000", "1979": "1267000", "1980": "1267000", "1981": "1267000", "1982": "1267000", "1983": "1267000", "1984": "1267000", "1985": "1267000", "1986": "1267000", "1987": "1267000", "1988": "1267000", "1989": "1267000", "1990": "1267000", "1991": "1267000", "1992": "1267000", "1993": "1267000", "1994": "1267000", "1995": "1267000", "1996": "1267000", "1997": "1267000", "1998": "1267000", "1999": "1267000", "2000": "1267000", "2001": "1267000", "2002": "1267000", "2003": "1267000", "2004": "1267000", "2005": "1267000", "2006": "1267000", "2007": "1267000", "2008": "1267000", "2009": "1267000", "2010": "1267000", "2011": "1267000", "2012": "1267000", "2013": "1267000", "2014": "1267000"}, "United States": {"1961": "9629090", "1962": "9629090", "1963": "9629090", "1964": "9629090", "1965": "9629090", "1966": "9629090", "1967": "9629090", "1968": "9629090", "1969": "9629090", "1970": "9629090", "1971": "9629090", "1972": "9629090", "1973": "9629090", "1974": "9629090", "1975": "9629090", "1976": "9629090", "1977": "9629090", "1978": "9629090", "1979": "9629090", "1980": "9629090", "1981": "9629090", "1982": "9629090", "1983": "9629090", "1984": "9629090", "1985": "9629090", "1986": "9629090", "1987": "9629090", "1988": "9629090", "1989": "9629090", "1990": "9629090", "1991": "9629090", "1992": "9629090", "1993": "9629090", "1994": "9629090", "1995": "9629090", "1996": "9629090", "1997": "9629090", "1998": "9629090", "1999": "9629090", "2000": "9632030", "2001": "9632030", "2002": "9632030", "2003": "9632030", "2004": "9632030", "2005": "9632030", "2006": "9632030", "2007": "9632030", "2008": "9831510", "2009": "9831510", "2010": "9831510", "2011": "9831510", "2012": "9831510", "2013": "9831510", "2014": "9831510"}, "Brazil": {"1961": "8515770", "1962": "8515770", "1963": "8515770", "1964": "8515770", "1965": "8515770", "1966": "8515770", "1967": "8515770", "1968": "8515770", "1969": "8515770", "1970": "8515770", "1971": "8515770", "1972": "8515770", "1973": "8515770", "1974": "8515770", "1975": "8515770", "1976": "8515770", "1977": "8515770", "1978": "8515770", "1979": "8515770", "1980": "8515770", "1981": "8515770", "1982": "8515770", "1983": "8515770", "1984": "8515770", "1985": "8515770", "1986": "8515770", "1987": "8515770", "1988": "8515770", "1989": "8515770", "1990": "8515770", "1991": "8515770", "1992": "8515770", "1993": "8515770", "1994": "8515770", "1995": "8515770", "1996": "8515770", "1997": "8515770", "1998": "8515770", "1999": "8515770", "2000": "8515770", "2001": "8515770", "2002": "8515770", "2003": "8515770", "2004": "8515770", "2005": "8515770", "2006": "8515770", "2007": "8515770", "2008": "8515770", "2009": "8515770", "2010": "8515770", "2011": "8515770", "2012": "8515770", "2013": "8515770", "2014": "8515770"}, "World": {"1961": "134158810.4", "1962": "134158810.4", "1963": "134158810.4", "1964": "134158810.4", "1965": "134158810.4", "1966": "134158810.4", "1967": "134158810.4", "1968": "134158810.4", "1969": "134158810.4", "1970": "134158810.4", "1971": "134158810.4", "1972": "134158810.4", "1973": "134158810.4", "1974": "134158810.4", "1975": "134158810.4", "1976": "134158810.4", "1977": "134156690.4", "1978": "134156690.4", "1979": "134158730.4", "1980": "134158720.4", "1981": "134158720.4", "1982": "134158720.4", "1983": "134158720.4", "1984": "134158720.4", "1985": "134158720.4", "1986": "134158720.4", "1987": "134157380.4", "1988": "134157390.4", "1989": "134157390.4", "1990": "134158060.4", "1991": "134159890.4", "1992": "134159940.4", "1993": "134042450.4", "1994": "134035537.4", "1995": "134035567.4", "1996": "134035647.4", "1997": "134104387.4", "1998": "134077127.4", "1999": "134077127.4", "2000": "134110327.4", "2001": "134110717.6", "2002": "134111142.6", "2003": "134111244.1", "2004": "134109687.9", "2005": "134111645.2", "2006": "134111980.4", "2007": "134112021.4", "2008": "134311491.4", "2009": "134309172.9", "2010": "134309386.1", "2011": "134327461.8", "2012": "134324740.8", "2013": "134324740.8", "2014": "134324740.8"}, "Middle East & North Africa (all income levels)": {"1961": "11373260", "1962": "11373260", "1963": "11373260", "1964": "11373260", "1965": "11373260", "1966": "11373260", "1967": "11373260", "1968": "11373260", "1969": "11373260", "1970": "11373260", "1971": "11373260", "1972": "11373260", "1973": "11373260", "1974": "11373260", "1975": "11373260", "1976": "11373260", "1977": "11373260", "1978": "11373260", "1979": "11373260", "1980": "11373260", "1981": "11373260", "1982": "11373260", "1983": "11373260", "1984": "11373260", "1985": "11373260", "1986": "11373260", "1987": "11373260", "1988": "11373260", "1989": "11373260", "1990": "11373260", "1991": "11373260", "1992": "11373280", "1993": "11373280", "1994": "11373280", "1995": "11373280", "1996": "11373280", "1997": "11373280", "1998": "11373280", "1999": "11373280", "2000": "11373280", "2001": "11373280", "2002": "11373280", "2003": "11373290", "2004": "11373300", "2005": "11373310", "2006": "11373310", "2007": "11373320", "2008": "11373330", "2009": "11370790", "2010": "11370790", "2011": "11370790", "2012": "11370790", "2013": "11370790", "2014": "11370790"}, "Guinea": {"1961": "245860", "1962": "245860", "1963": "245860", "1964": "245860", "1965": "245860", "1966": "245860", "1967": "245860", "1968": "245860", "1969": "245860", "1970": "245860", "1971": "245860", "1972": "245860", "1973": "245860", "1974": "245860", "1975": "245860", "1976": "245860", "1977": "245860", "1978": "245860", "1979": "245860", "1980": "245860", "1981": "245860", "1982": "245860", "1983": "245860", "1984": "245860", "1985": "245860", "1986": "245860", "1987": "245860", "1988": "245860", "1989": "245860", "1990": "245860", "1991": "245860", "1992": "245860", "1993": "245860", "1994": "245860", "1995": "245860", "1996": "245860", "1997": "245860", "1998": "245860", "1999": "245860", "2000": "245860", "2001": "245860", "2002": "245860", "2003": "245860", "2004": "245860", "2005": "245860", "2006": "245860", "2007": "245860", "2008": "245860", "2009": "245860", "2010": "245860", "2011": "245860", "2012": "245860", "2013": "245860", "2014": "245860"}, "Panama": {"1961": "75420", "1962": "75420", "1963": "75420", "1964": "75420", "1965": "75420", "1966": "75420", "1967": "75420", "1968": "75420", "1969": "75420", "1970": "75420", "1971": "75420", "1972": "75420", "1973": "75420", "1974": "75420", "1975": "75420", "1976": "75420", "1977": "75420", "1978": "75420", "1979": "75420", "1980": "75420", "1981": "75420", "1982": "75420", "1983": "75420", "1984": "75420", "1985": "75420", "1986": "75420", "1987": "75420", "1988": "75420", "1989": "75420", "1990": "75420", "1991": "75420", "1992": "75420", "1993": "75420", "1994": "75420", "1995": "75420", "1996": "75420", "1997": "75420", "1998": "75420", "1999": "75420", "2000": "75420", "2001": "75420", "2002": "75420", "2003": "75420", "2004": "75420", "2005": "75420", "2006": "75420", "2007": "75420", "2008": "75420", "2009": "75420", "2010": "75420", "2011": "75420", "2012": "75420", "2013": "75420", "2014": "75420"}, "Costa Rica": {"1961": "51100", "1962": "51100", "1963": "51100", "1964": "51100", "1965": "51100", "1966": "51100", "1967": "51100", "1968": "51100", "1969": "51100", "1970": "51100", "1971": "51100", "1972": "51100", "1973": "51100", "1974": "51100", "1975": "51100", "1976": "51100", "1977": "51100", "1978": "51100", "1979": "51100", "1980": "51100", "1981": "51100", "1982": "51100", "1983": "51100", "1984": "51100", "1985": "51100", "1986": "51100", "1987": "51100", "1988": "51100", "1989": "51100", "1990": "51100", "1991": "51100", "1992": "51100", "1993": "51100", "1994": "51100", "1995": "51100", "1996": "51100", "1997": "51100", "1998": "51100", "1999": "51100", "2000": "51100", "2001": "51100", "2002": "51100", "2003": "51100", "2004": "51100", "2005": "51100", "2006": "51100", "2007": "51100", "2008": "51100", "2009": "51100", "2010": "51100", "2011": "51100", "2012": "51100", "2013": "51100", "2014": "51100"}, "Luxembourg": {"2000": "2590", "2001": "2590", "2002": "2590", "2003": "2590", "2004": "2590", "2005": "2590", "2006": "2590", "2007": "2590", "2008": "2590", "2009": "2590", "2010": "2590", "2011": "2590", "2012": "2590", "2013": "2590", "2014": "2590"}, "Andorra": {"1961": "470", "1962": "470", "1963": "470", "1964": "470", "1965": "470", "1966": "470", "1967": "470", "1968": "470", "1969": "470", "1970": "470", "1971": "470", "1972": "470", "1973": "470", "1974": "470", "1975": "470", "1976": "470", "1977": "470", "1978": "470", "1979": "470", "1980": "470", "1981": "470", "1982": "470", "1983": "470", "1984": "470", "1985": "470", "1986": "470", "1987": "470", "1988": "470", "1989": "470", "1990": "470", "1991": "470", "1992": "470", "1993": "470", "1994": "470", "1995": "470", "1996": "470", "1997": "470", "1998": "470", "1999": "470", "2000": "470", "2001": "470", "2002": "470", "2003": "470", "2004": "470", "2005": "470", "2006": "470", "2007": "470", "2008": "470", "2009": "470", "2010": "470", "2011": "470", "2012": "470", "2013": "470", "2014": "470"}, "Chad": {"1961": "1284000", "1962": "1284000", "1963": "1284000", "1964": "1284000", "1965": "1284000", "1966": "1284000", "1967": "1284000", "1968": "1284000", "1969": "1284000", "1970": "1284000", "1971": "1284000", "1972": "1284000", "1973": "1284000", "1974": "1284000", "1975": "1284000", "1976": "1284000", "1977": "1284000", "1978": "1284000", "1979": "1284000", "1980": "1284000", "1981": "1284000", "1982": "1284000", "1983": "1284000", "1984": "1284000", "1985": "1284000", "1986": "1284000", "1987": "1284000", "1988": "1284000", "1989": "1284000", "1990": "1284000", "1991": "1284000", "1992": "1284000", "1993": "1284000", "1994": "1284000", "1995": "1284000", "1996": "1284000", "1997": "1284000", "1998": "1284000", "1999": "1284000", "2000": "1284000", "2001": "1284000", "2002": "1284000", "2003": "1284000", "2004": "1284000", "2005": "1284000", "2006": "1284000", "2007": "1284000", "2008": "1284000", "2009": "1284000", "2010": "1284000", "2011": "1284000", "2012": "1284000", "2013": "1284000", "2014": "1284000"}, "Euro area": {"1961": "2725255", "1962": "2725255", "1963": "2725255", "1964": "2725255", "1965": "2725255", "1966": "2725255", "1967": "2725255", "1968": "2725255", "1969": "2725255", "1970": "2725255", "1971": "2725255", "1972": "2725255", "1973": "2725255", "1974": "2725255", "1975": "2725255", "1976": "2725255", "1977": "2725255", "1978": "2725255", "1979": "2725255", "1980": "2725255", "1981": "2725255", "1982": "2725255", "1983": "2725255", "1984": "2725255", "1985": "2725255", "1986": "2725255", "1987": "2725255", "1988": "2725255", "1989": "2725255", "1990": "2725255", "1991": "2725255", "1992": "2725255", "1993": "2725275", "1994": "2725285", "1995": "2725305", "1996": "2725315", "1997": "2725315", "1998": "2725315", "1999": "2725315", "2000": "2757445", "2001": "2757465", "2002": "2757775", "2003": "2757825", "2004": "2757835", "2005": "2757855", "2006": "2758155", "2007": "2758135", "2008": "2758151", "2009": "2758296", "2010": "2758480", "2011": "2758422", "2012": "2758456", "2013": "2758456", "2014": "2758456"}, "Ireland": {"1961": "70280", "1962": "70280", "1963": "70280", "1964": "70280", "1965": "70280", "1966": "70280", "1967": "70280", "1968": "70280", "1969": "70280", "1970": "70280", "1971": "70280", "1972": "70280", "1973": "70280", "1974": "70280", "1975": "70280", "1976": "70280", "1977": "70280", "1978": "70280", "1979": "70280", "1980": "70280", "1981": "70280", "1982": "70280", "1983": "70280", "1984": "70280", "1985": "70280", "1986": "70280", "1987": "70280", "1988": "70280", "1989": "70280", "1990": "70280", "1991": "70280", "1992": "70280", "1993": "70280", "1994": "70280", "1995": "70280", "1996": "70280", "1997": "70280", "1998": "70280", "1999": "70280", "2000": "70280", "2001": "70280", "2002": "70280", "2003": "70280", "2004": "70280", "2005": "70280", "2006": "70280", "2007": "70280", "2008": "70280", "2009": "70280", "2010": "70280", "2011": "70280", "2012": "70280", "2013": "70280", "2014": "70280"}, "Pakistan": {"1961": "796100", "1962": "796100", "1963": "796100", "1964": "796100", "1965": "796100", "1966": "796100", "1967": "796100", "1968": "796100", "1969": "796100", "1970": "796100", "1971": "796100", "1972": "796100", "1973": "796100", "1974": "796100", "1975": "796100", "1976": "796100", "1977": "796100", "1978": "796100", "1979": "796100", "1980": "796100", "1981": "796100", "1982": "796100", "1983": "796100", "1984": "796100", "1985": "796100", "1986": "796100", "1987": "796100", "1988": "796100", "1989": "796100", "1990": "796100", "1991": "796100", "1992": "796100", "1993": "796100", "1994": "796100", "1995": "796100", "1996": "796100", "1997": "796100", "1998": "796100", "1999": "796100", "2000": "796100", "2001": "796100", "2002": "796100", "2003": "796100", "2004": "796100", "2005": "796100", "2006": "796100", "2007": "796100", "2008": "796100", "2009": "796100", "2010": "796100", "2011": "796100", "2012": "796100", "2013": "796100", "2014": "796100"}, "Palau": {"1991": "460", "1992": "460", "1993": "460", "1994": "460", "1995": "460", "1996": "460", "1997": "460", "1998": "460", "1999": "460", "2000": "460", "2001": "460", "2002": "460", "2003": "460", "2004": "460", "2005": "460", "2006": "460", "2007": "460", "2008": "460", "2009": "460", "2010": "460", "2011": "460", "2012": "460", "2013": "460", "2014": "460"}, "Faeroe Islands": {"1961": "1396", "1962": "1396", "1963": "1396", "1964": "1396", "1965": "1396", "1966": "1396", "1967": "1396", "1968": "1396", "1969": "1396", "1970": "1396", "1971": "1396", "1972": "1396", "1973": "1396", "1974": "1396", "1975": "1396", "1976": "1396", "1977": "1396", "1978": "1396", "1979": "1396", "1980": "1396", "1981": "1396", "1982": "1396", "1983": "1396", "1984": "1396", "1985": "1396", "1986": "1396", "1987": "1396", "1988": "1396", "1989": "1396", "1990": "1396", "1991": "1396", "1992": "1396", "1993": "1396", "1994": "1396", "1995": "1396", "1996": "1396", "1997": "1396", "1998": "1396", "1999": "1396", "2000": "1396", "2001": "1396", "2002": "1396", "2003": "1396", "2004": "1396", "2005": "1396", "2006": "1396", "2007": "1396", "2008": "1396", "2009": "1396", "2010": "1396", "2011": "1396", "2012": "1396", "2013": "1396", "2014": "1396"}, "Lower middle income": {"1961": "21158267", "1962": "21158267", "1963": "21158267", "1964": "21158267", "1965": "21158267", "1966": "21158267", "1967": "21158267", "1968": "21158267", "1969": "21158267", "1970": "21158267", "1971": "21158267", "1972": "21158267", "1973": "21158267", "1974": "21158267", "1975": "21158267", "1976": "21158267", "1977": "21156147", "1978": "21156147", "1979": "21158187", "1980": "21158267", "1981": "21158267", "1982": "21158267", "1983": "21158267", "1984": "21158267", "1985": "21158267", "1986": "21158267", "1987": "21156927", "1988": "21156937", "1989": "21156937", "1990": "21157607", "1991": "21158337", "1992": "21158367", "1993": "21158457", "1994": "21151534", "1995": "21151544", "1996": "21151544", "1997": "21151534", "1998": "21151534", "1999": "21151534", "2000": "21149664", "2001": "21149674", "2002": "21149724", "2003": "21149734", "2004": "21148065", "2005": "21149963", "2006": "21149963", "2007": "21149963", "2008": "21149802", "2009": "21149801", "2010": "21149707", "2011": "20523248.5", "2012": "20523248.5", "2013": "20523248.5", "2014": "20523248.5"}, "Ecuador": {"1961": "283560", "1962": "283560", "1963": "283560", "1964": "283560", "1965": "283560", "1966": "283560", "1967": "283560", "1968": "283560", "1969": "283560", "1970": "283560", "1971": "283560", "1972": "283560", "1973": "283560", "1974": "283560", "1975": "283560", "1976": "283560", "1977": "283560", "1978": "283560", "1979": "283560", "1980": "283560", "1981": "283560", "1982": "283560", "1983": "283560", "1984": "283560", "1985": "283560", "1986": "283560", "1987": "283560", "1988": "283560", "1989": "283560", "1990": "283560", "1991": "283560", "1992": "283560", "1993": "283560", "1994": "283560", "1995": "283560", "1996": "283560", "1997": "283560", "1998": "256370", "1999": "256370", "2000": "256370", "2001": "256370", "2002": "256370", "2003": "256370", "2004": "256370", "2005": "256370", "2006": "256370", "2007": "256370", "2008": "256370", "2009": "256370", "2010": "256370", "2011": "256370", "2012": "256370", "2013": "256370", "2014": "256370"}, "Czech Republic": {"1961": "78870", "1962": "78870", "1963": "78870", "1964": "78870", "1965": "78870", "1966": "78870", "1967": "78870", "1968": "78870", "1969": "78870", "1970": "78870", "1971": "78870", "1972": "78870", "1973": "78870", "1974": "78870", "1975": "78870", "1976": "78870", "1977": "78870", "1978": "78870", "1979": "78870", "1980": "78870", "1981": "78870", "1982": "78870", "1983": "78870", "1984": "78870", "1985": "78870", "1986": "78870", "1987": "78870", "1988": "78870", "1989": "78870", "1990": "78870", "1991": "78870", "1992": "78870", "1993": "78870", "1994": "78870", "1995": "78870", "1996": "78870", "1997": "78870", "1998": "78870", "1999": "78870", "2000": "78870", "2001": "78870", "2002": "78870", "2003": "78870", "2004": "78870", "2005": "78870", "2006": "78870", "2007": "78870", "2008": "78870", "2009": "78870", "2010": "78870", "2011": "78870", "2012": "78870", "2013": "78870", "2014": "78870"}, "Australia": {"1961": "7741220", "1962": "7741220", "1963": "7741220", "1964": "7741220", "1965": "7741220", "1966": "7741220", "1967": "7741220", "1968": "7741220", "1969": "7741220", "1970": "7741220", "1971": "7741220", "1972": "7741220", "1973": "7741220", "1974": "7741220", "1975": "7741220", "1976": "7741220", "1977": "7741220", "1978": "7741220", "1979": "7741220", "1980": "7741220", "1981": "7741220", "1982": "7741220", "1983": "7741220", "1984": "7741220", "1985": "7741220", "1986": "7741220", "1987": "7741220", "1988": "7741220", "1989": "7741220", "1990": "7741220", "1991": "7741220", "1992": "7741220", "1993": "7741220", "1994": "7741220", "1995": "7741220", "1996": "7741220", "1997": "7741220", "1998": "7741220", "1999": "7741220", "2000": "7741220", "2001": "7741220", "2002": "7741220", "2003": "7741220", "2004": "7741220", "2005": "7741220", "2006": "7741220", "2007": "7741220", "2008": "7741220", "2009": "7741220", "2010": "7741220", "2011": "7741220", "2012": "7741220", "2013": "7741220", "2014": "7741220"}, "Algeria": {"1961": "2381740", "1962": "2381740", "1963": "2381740", "1964": "2381740", "1965": "2381740", "1966": "2381740", "1967": "2381740", "1968": "2381740", "1969": "2381740", "1970": "2381740", "1971": "2381740", "1972": "2381740", "1973": "2381740", "1974": "2381740", "1975": "2381740", "1976": "2381740", "1977": "2381740", "1978": "2381740", "1979": "2381740", "1980": "2381740", "1981": "2381740", "1982": "2381740", "1983": "2381740", "1984": "2381740", "1985": "2381740", "1986": "2381740", "1987": "2381740", "1988": "2381740", "1989": "2381740", "1990": "2381740", "1991": "2381740", "1992": "2381740", "1993": "2381740", "1994": "2381740", "1995": "2381740", "1996": "2381740", "1997": "2381740", "1998": "2381740", "1999": "2381740", "2000": "2381740", "2001": "2381740", "2002": "2381740", "2003": "2381740", "2004": "2381740", "2005": "2381740", "2006": "2381740", "2007": "2381740", "2008": "2381740", "2009": "2381740", "2010": "2381740", "2011": "2381740", "2012": "2381740", "2013": "2381740", "2014": "2381740"}, "East Asia and the Pacific (IFC classification)": {}, "El Salvador": {"1961": "21040", "1962": "21040", "1963": "21040", "1964": "21040", "1965": "21040", "1966": "21040", "1967": "21040", "1968": "21040", "1969": "21040", "1970": "21040", "1971": "21040", "1972": "21040", "1973": "21040", "1974": "21040", "1975": "21040", "1976": "21040", "1977": "21040", "1978": "21040", "1979": "21040", "1980": "21040", "1981": "21040", "1982": "21040", "1983": "21040", "1984": "21040", "1985": "21040", "1986": "21040", "1987": "21040", "1988": "21040", "1989": "21040", "1990": "21040", "1991": "21040", "1992": "21040", "1993": "21040", "1994": "21040", "1995": "21040", "1996": "21040", "1997": "21040", "1998": "21040", "1999": "21040", "2000": "21040", "2001": "21040", "2002": "21040", "2003": "21040", "2004": "21040", "2005": "21040", "2006": "21040", "2007": "21040", "2008": "21040", "2009": "21040", "2010": "21040", "2011": "21040", "2012": "21040", "2013": "21040", "2014": "21040"}, "Tuvalu": {"1961": "30", "1962": "30", "1963": "30", "1964": "30", "1965": "30", "1966": "30", "1967": "30", "1968": "30", "1969": "30", "1970": "30", "1971": "30", "1972": "30", "1973": "30", "1974": "30", "1975": "30", "1976": "30", "1977": "30", "1978": "30", "1979": "30", "1980": "30", "1981": "30", "1982": "30", "1983": "30", "1984": "30", "1985": "30", "1986": "30", "1987": "30", "1988": "30", "1989": "30", "1990": "30", "1991": "30", "1992": "30", "1993": "30", "1994": "30", "1995": "30", "1996": "30", "1997": "30", "1998": "30", "1999": "30", "2000": "30", "2001": "30", "2002": "30", "2003": "30", "2004": "30", "2005": "30", "2006": "30", "2007": "30", "2008": "30", "2009": "30", "2010": "30", "2011": "30", "2012": "30", "2013": "30", "2014": "30"}, "St. Kitts and Nevis": {"1961": "350", "1962": "350", "1963": "350", "1964": "350", "1965": "350", "1966": "350", "1967": "350", "1968": "350", "1969": "350", "1970": "350", "1971": "350", "1972": "350", "1973": "350", "1974": "350", "1975": "350", "1976": "350", "1977": "350", "1978": "350", "1979": "350", "1980": "260", "1981": "260", "1982": "260", "1983": "260", "1984": "260", "1985": "260", "1986": "260", "1987": "260", "1988": "260", "1989": "260", "1990": "260", "1991": "260", "1992": "260", "1993": "260", "1994": "260", "1995": "260", "1996": "260", "1997": "260", "1998": "260", "1999": "260", "2000": "260", "2001": "260", "2002": "260", "2003": "260", "2004": "260", "2005": "260", "2006": "260", "2007": "260", "2008": "260", "2009": "260", "2010": "260", "2011": "260", "2012": "260", "2013": "260", "2014": "260"}, "Marshall Islands": {"1991": "180", "1992": "180", "1993": "180", "1994": "180", "1995": "180", "1996": "180", "1997": "180", "1998": "180", "1999": "180", "2000": "180", "2001": "180", "2002": "180", "2003": "180", "2004": "180", "2005": "180", "2006": "180", "2007": "180", "2008": "180", "2009": "180", "2010": "180", "2011": "180", "2012": "180", "2013": "180", "2014": "180"}, "Chile": {"1961": "756096", "1962": "756096", "1963": "756096", "1964": "756096", "1965": "756096", "1966": "756096", "1967": "756096", "1968": "756096", "1969": "756096", "1970": "756096", "1971": "756096", "1972": "756096", "1973": "756096", "1974": "756096", "1975": "756096", "1976": "756096", "1977": "756096", "1978": "756096", "1979": "756096", "1980": "756096", "1981": "756096", "1982": "756096", "1983": "756096", "1984": "756096", "1985": "756096", "1986": "756096", "1987": "756096", "1988": "756096", "1989": "756096", "1990": "756096", "1991": "756096", "1992": "756096", "1993": "756096", "1994": "756096", "1995": "756096", "1996": "756096", "1997": "756096", "1998": "756096", "1999": "756096", "2000": "756096", "2001": "756096", "2002": "756096", "2003": "756096", "2004": "756096", "2005": "756096", "2006": "756096", "2007": "756096", "2008": "756096", "2009": "756096", "2010": "756096", "2011": "756096", "2012": "756096", "2013": "756096", "2014": "756096"}, "Puerto Rico": {"1961": "8870", "1962": "8870", "1963": "8870", "1964": "8870", "1965": "8870", "1966": "8870", "1967": "8870", "1968": "8870", "1969": "8870", "1970": "8870", "1971": "8870", "1972": "8870", "1973": "8870", "1974": "8870", "1975": "8870", "1976": "8870", "1977": "8870", "1978": "8870", "1979": "8870", "1980": "8870", "1981": "8870", "1982": "8870", "1983": "8870", "1984": "8870", "1985": "8870", "1986": "8870", "1987": "8870", "1988": "8870", "1989": "8870", "1990": "8870", "1991": "8870", "1992": "8870", "1993": "8870", "1994": "8870", "1995": "8870", "1996": "8870", "1997": "8870", "1998": "8870", "1999": "8870", "2000": "8870", "2001": "8870", "2002": "8870", "2003": "8870", "2004": "8870", "2005": "8870", "2006": "8870", "2007": "8870", "2008": "8870", "2009": "8870", "2010": "8870", "2011": "8870", "2012": "8870", "2013": "8870", "2014": "8870"}, "Belgium": {"2000": "30530", "2001": "30530", "2002": "30530", "2003": "30530", "2004": "30530", "2005": "30530", "2006": "30530", "2007": "30530", "2008": "30530", "2009": "30530", "2010": "30530", "2011": "30530", "2012": "30530", "2013": "30530", "2014": "30530"}, "Europe and Central Asia (IFC classification)": {}, "Haiti": {"1961": "27750", "1962": "27750", "1963": "27750", "1964": "27750", "1965": "27750", "1966": "27750", "1967": "27750", "1968": "27750", "1969": "27750", "1970": "27750", "1971": "27750", "1972": "27750", "1973": "27750", "1974": "27750", "1975": "27750", "1976": "27750", "1977": "27750", "1978": "27750", "1979": "27750", "1980": "27750", "1981": "27750", "1982": "27750", "1983": "27750", "1984": "27750", "1985": "27750", "1986": "27750", "1987": "27750", "1988": "27750", "1989": "27750", "1990": "27750", "1991": "27750", "1992": "27750", "1993": "27750", "1994": "27750", "1995": "27750", "1996": "27750", "1997": "27750", "1998": "27750", "1999": "27750", "2000": "27750", "2001": "27750", "2002": "27750", "2003": "27750", "2004": "27750", "2005": "27750", "2006": "27750", "2007": "27750", "2008": "27750", "2009": "27750", "2010": "27750", "2011": "27750", "2012": "27750", "2013": "27750", "2014": "27750"}, "Belize": {"1961": "22970", "1962": "22970", "1963": "22970", "1964": "22970", "1965": "22970", "1966": "22970", "1967": "22970", "1968": "22970", "1969": "22970", "1970": "22970", "1971": "22970", "1972": "22970", "1973": "22970", "1974": "22970", "1975": "22970", "1976": "22970", "1977": "22970", "1978": "22970", "1979": "22970", "1980": "22970", "1981": "22970", "1982": "22970", "1983": "22970", "1984": "22970", "1985": "22970", "1986": "22970", "1987": "22970", "1988": "22970", "1989": "22970", "1990": "22970", "1991": "22970", "1992": "22970", "1993": "22970", "1994": "22970", "1995": "22970", "1996": "22970", "1997": "22970", "1998": "22970", "1999": "22970", "2000": "22970", "2001": "22970", "2002": "22970", "2003": "22970", "2004": "22970", "2005": "22970", "2006": "22970", "2007": "22970", "2008": "22970", "2009": "22970", "2010": "22970", "2011": "22970", "2012": "22970", "2013": "22970", "2014": "22970"}, "Fragile and conflict affected situations": {"1961": "14762328", "1962": "14762328", "1963": "14762328", "1964": "14762328", "1965": "14762328", "1966": "14762328", "1967": "14762328", "1968": "14762328", "1969": "14762328", "1970": "14762328", "1971": "14762328", "1972": "14762328", "1973": "14762328", "1974": "14762328", "1975": "14762328", "1976": "14762328", "1977": "14762328", "1978": "14762328", "1979": "14762328", "1980": "14762328", "1981": "14762328", "1982": "14762328", "1983": "14762328", "1984": "14762328", "1985": "14762328", "1986": "14762328", "1987": "14762328", "1988": "14762328", "1989": "14762328", "1990": "14762328", "1991": "14763208", "1992": "14763208", "1993": "14763208", "1994": "14763208", "1995": "14763208", "1996": "14763208", "1997": "14763208", "1998": "14763208", "1999": "14763208", "2000": "14763208", "2001": "14763208", "2002": "14763208", "2003": "14763208", "2004": "14763208", "2005": "14763208", "2006": "14763208", "2007": "14763208", "2008": "14763208", "2009": "14760128", "2010": "14760128", "2011": "14778260.5", "2012": "14778260.5", "2013": "14778260.5", "2014": "14778260.5"}, "Sierra Leone": {"1961": "72300", "1962": "72300", "1963": "72300", "1964": "72300", "1965": "72300", "1966": "72300", "1967": "72300", "1968": "72300", "1969": "72300", "1970": "72300", "1971": "72300", "1972": "72300", "1973": "72300", "1974": "72300", "1975": "72300", "1976": "72300", "1977": "72300", "1978": "72300", "1979": "72300", "1980": "72300", "1981": "72300", "1982": "72300", "1983": "72300", "1984": "72300", "1985": "72300", "1986": "72300", "1987": "72300", "1988": "72300", "1989": "72300", "1990": "72300", "1991": "72300", "1992": "72300", "1993": "72300", "1994": "72300", "1995": "72300", "1996": "72300", "1997": "72300", "1998": "72300", "1999": "72300", "2000": "72300", "2001": "72300", "2002": "72300", "2003": "72300", "2004": "72300", "2005": "72300", "2006": "72300", "2007": "72300", "2008": "72300", "2009": "72300", "2010": "72300", "2011": "72300", "2012": "72300", "2013": "72300", "2014": "72300"}, "Georgia": {"1961": "69700", "1962": "69700", "1963": "69700", "1964": "69700", "1965": "69700", "1966": "69700", "1967": "69700", "1968": "69700", "1969": "69700", "1970": "69700", "1971": "69700", "1972": "69700", "1973": "69700", "1974": "69700", "1975": "69700", "1976": "69700", "1977": "69700", "1978": "69700", "1979": "69700", "1980": "69700", "1981": "69700", "1982": "69700", "1983": "69700", "1984": "69700", "1985": "69700", "1986": "69700", "1987": "69700", "1988": "69700", "1989": "69700", "1990": "69700", "1991": "69700", "1992": "69700", "1993": "69700", "1994": "69700", "1995": "69700", "1996": "69700", "1997": "69700", "1998": "69700", "1999": "69700", "2000": "69700", "2001": "69700", "2002": "69700", "2003": "69700", "2004": "69700", "2005": "69700", "2006": "69700", "2007": "69700", "2008": "69700", "2009": "69700", "2010": "69700", "2011": "69700", "2012": "69700", "2013": "69700", "2014": "69700"}, "East Asia & Pacific (developing only)": {"1961": "16270280", "1962": "16270280", "1963": "16270280", "1964": "16270280", "1965": "16270280", "1966": "16270280", "1967": "16270280", "1968": "16270280", "1969": "16270280", "1970": "16270280", "1971": "16270280", "1972": "16270280", "1973": "16270280", "1974": "16270280", "1975": "16270280", "1976": "16270280", "1977": "16268160", "1978": "16268160", "1979": "16270200", "1980": "16270280", "1981": "16270280", "1982": "16270280", "1983": "16270280", "1984": "16270280", "1985": "16270280", "1986": "16270280", "1987": "16268940", "1988": "16268950", "1989": "16268950", "1990": "16269620", "1991": "16270990", "1992": "16271020", "1993": "16271040", "1994": "16271040", "1995": "16271030", "1996": "16271020", "1997": "16271020", "1998": "16271020", "1999": "16271020", "2000": "16269140", "2001": "16269144.2", "2002": "16269193.2", "2003": "16269202.7", "2004": "16269206.5", "2005": "16271103.8", "2006": "16271103.4", "2007": "16271102.8", "2008": "16270941.8", "2009": "16270942", "2010": "16270848", "2011": "16270842", "2012": "16270842", "2013": "16270842", "2014": "16270842"}, "Denmark": {"1961": "43090", "1962": "43090", "1963": "43090", "1964": "43090", "1965": "43090", "1966": "43090", "1967": "43090", "1968": "43090", "1969": "43090", "1970": "43090", "1971": "43090", "1972": "43090", "1973": "43090", "1974": "43090", "1975": "43090", "1976": "43090", "1977": "43090", "1978": "43090", "1979": "43090", "1980": "43090", "1981": "43090", "1982": "43090", "1983": "43090", "1984": "43090", "1985": "43090", "1986": "43090", "1987": "43090", "1988": "43090", "1989": "43090", "1990": "43090", "1991": "43090", "1992": "43090", "1993": "43090", "1994": "43090", "1995": "43090", "1996": "43090", "1997": "43090", "1998": "43090", "1999": "43090", "2000": "43090", "2001": "43090", "2002": "43090", "2003": "43090", "2004": "43090", "2005": "43090", "2006": "43090", "2007": "43090", "2008": "43090", "2009": "43090", "2010": "43090", "2011": "43090", "2012": "43090", "2013": "43090", "2014": "43090"}, "Philippines": {"1961": "300000", "1962": "300000", "1963": "300000", "1964": "300000", "1965": "300000", "1966": "300000", "1967": "300000", "1968": "300000", "1969": "300000", "1970": "300000", "1971": "300000", "1972": "300000", "1973": "300000", "1974": "300000", "1975": "300000", "1976": "300000", "1977": "300000", "1978": "300000", "1979": "300000", "1980": "300000", "1981": "300000", "1982": "300000", "1983": "300000", "1984": "300000", "1985": "300000", "1986": "300000", "1987": "300000", "1988": "300000", "1989": "300000", "1990": "300000", "1991": "300000", "1992": "300000", "1993": "300000", "1994": "300000", "1995": "300000", "1996": "300000", "1997": "300000", "1998": "300000", "1999": "300000", "2000": "300000", "2001": "300000", "2002": "300000", "2003": "300000", "2004": "300000", "2005": "300000", "2006": "300000", "2007": "300000", "2008": "300000", "2009": "300000", "2010": "300000", "2011": "300000", "2012": "300000", "2013": "300000", "2014": "300000"}, "Moldova": {"1961": "33760", "1962": "33760", "1963": "33760", "1964": "33760", "1965": "33760", "1966": "33760", "1967": "33760", "1968": "33760", "1969": "33760", "1970": "33760", "1971": "33760", "1972": "33760", "1973": "33760", "1974": "33760", "1975": "33760", "1976": "33760", "1977": "33760", "1978": "33760", "1979": "33760", "1980": "33760", "1981": "33760", "1982": "33760", "1983": "33760", "1984": "33760", "1985": "33760", "1986": "33760", "1987": "33760", "1988": "33760", "1989": "33760", "1990": "33760", "1991": "33760", "1992": "33760", "1993": "33840", "1994": "33840", "1995": "33850", "1996": "33850", "1997": "33840", "1998": "33840", "1999": "33840", "2000": "33840", "2001": "33840", "2002": "33840", "2003": "33840", "2004": "33850", "2005": "33850", "2006": "33850", "2007": "33850", "2008": "33850", "2009": "33850", "2010": "33850", "2011": "33850", "2012": "33850", "2013": "33850", "2014": "33850"}, "Macedonia, FYR": {"1961": "25710", "1962": "25710", "1963": "25710", "1964": "25710", "1965": "25710", "1966": "25710", "1967": "25710", "1968": "25710", "1969": "25710", "1970": "25710", "1971": "25710", "1972": "25710", "1973": "25710", "1974": "25710", "1975": "25710", "1976": "25710", "1977": "25710", "1978": "25710", "1979": "25710", "1980": "25710", "1981": "25710", "1982": "25710", "1983": "25710", "1984": "25710", "1985": "25710", "1986": "25710", "1987": "25710", "1988": "25710", "1989": "25710", "1990": "25710", "1991": "25710", "1992": "25710", "1993": "25710", "1994": "25710", "1995": "25710", "1996": "25710", "1997": "25710", "1998": "25710", "1999": "25710", "2000": "25710", "2001": "25710", "2002": "25710", "2003": "25710", "2004": "25710", "2005": "25710", "2006": "25710", "2007": "25710", "2008": "25710", "2009": "25710", "2010": "25710", "2011": "25710", "2012": "25710", "2013": "25710", "2014": "25710"}, "Morocco": {"1961": "446550", "1962": "446550", "1963": "446550", "1964": "446550", "1965": "446550", "1966": "446550", "1967": "446550", "1968": "446550", "1969": "446550", "1970": "446550", "1971": "446550", "1972": "446550", "1973": "446550", "1974": "446550", "1975": "446550", "1976": "446550", "1977": "446550", "1978": "446550", "1979": "446550", "1980": "446550", "1981": "446550", "1982": "446550", "1983": "446550", "1984": "446550", "1985": "446550", "1986": "446550", "1987": "446550", "1988": "446550", "1989": "446550", "1990": "446550", "1991": "446550", "1992": "446550", "1993": "446550", "1994": "446550", "1995": "446550", "1996": "446550", "1997": "446550", "1998": "446550", "1999": "446550", "2000": "446550", "2001": "446550", "2002": "446550", "2003": "446550", "2004": "446550", "2005": "446550", "2006": "446550", "2007": "446550", "2008": "446550", "2009": "446550", "2010": "446550", "2011": "446550", "2012": "446550", "2013": "446550", "2014": "446550"}, "Croatia": {"1961": "56540", "1962": "56540", "1963": "56540", "1964": "56540", "1965": "56540", "1966": "56540", "1967": "56540", "1968": "56540", "1969": "56540", "1970": "56540", "1971": "56540", "1972": "56540", "1973": "56540", "1974": "56540", "1975": "56540", "1976": "56540", "1977": "56540", "1978": "56540", "1979": "56540", "1980": "56540", "1981": "56540", "1982": "56540", "1983": "56540", "1984": "56540", "1985": "56540", "1986": "56540", "1987": "56540", "1988": "56540", "1989": "56540", "1990": "56540", "1991": "56540", "1992": "56540", "1993": "56540", "1994": "56540", "1995": "56540", "1996": "56610", "1997": "56610", "1998": "56540", "1999": "56540", "2000": "56540", "2001": "56540", "2002": "56540", "2003": "56540", "2004": "56590", "2005": "56590", "2006": "56590", "2007": "56590", "2008": "56590", "2009": "56590", "2010": "56590", "2011": "56590", "2012": "56590", "2013": "56590", "2014": "56590"}, "French Polynesia": {"1961": "4000", "1962": "4000", "1963": "4000", "1964": "4000", "1965": "4000", "1966": "4000", "1967": "4000", "1968": "4000", "1969": "4000", "1970": "4000", "1971": "4000", "1972": "4000", "1973": "4000", "1974": "4000", "1975": "4000", "1976": "4000", "1977": "4000", "1978": "4000", "1979": "4000", "1980": "4000", "1981": "4000", "1982": "4000", "1983": "4000", "1984": "4000", "1985": "4000", "1986": "4000", "1987": "4000", "1988": "4000", "1989": "4000", "1990": "4000", "1991": "4000", "1992": "4000", "1993": "4000", "1994": "4000", "1995": "4000", "1996": "4000", "1997": "4000", "1998": "4000", "1999": "4000", "2000": "4000", "2001": "4000", "2002": "4000", "2003": "4000", "2004": "4000", "2005": "4000", "2006": "4000", "2007": "4000", "2008": "4000", "2009": "4000", "2010": "4000", "2011": "4000", "2012": "4000", "2013": "4000", "2014": "4000"}, "Guinea-Bissau": {"1961": "36130", "1962": "36130", "1963": "36130", "1964": "36130", "1965": "36130", "1966": "36130", "1967": "36130", "1968": "36130", "1969": "36130", "1970": "36130", "1971": "36130", "1972": "36130", "1973": "36130", "1974": "36130", "1975": "36130", "1976": "36130", "1977": "36130", "1978": "36130", "1979": "36130", "1980": "36130", "1981": "36130", "1982": "36130", "1983": "36130", "1984": "36130", "1985": "36130", "1986": "36130", "1987": "36130", "1988": "36130", "1989": "36130", "1990": "36130", "1991": "36130", "1992": "36130", "1993": "36130", "1994": "36130", "1995": "36130", "1996": "36130", "1997": "36130", "1998": "36130", "1999": "36130", "2000": "36130", "2001": "36130", "2002": "36130", "2003": "36130", "2004": "36130", "2005": "36130", "2006": "36130", "2007": "36130", "2008": "36130", "2009": "36130", "2010": "36130", "2011": "36130", "2012": "36130", "2013": "36130", "2014": "36130"}, "Kiribati": {"1961": "810", "1962": "810", "1963": "810", "1964": "810", "1965": "810", "1966": "810", "1967": "810", "1968": "810", "1969": "810", "1970": "810", "1971": "810", "1972": "810", "1973": "810", "1974": "810", "1975": "810", "1976": "810", "1977": "810", "1978": "810", "1979": "810", "1980": "810", "1981": "810", "1982": "810", "1983": "810", "1984": "810", "1985": "810", "1986": "810", "1987": "810", "1988": "810", "1989": "810", "1990": "810", "1991": "810", "1992": "810", "1993": "810", "1994": "810", "1995": "810", "1996": "810", "1997": "810", "1998": "810", "1999": "810", "2000": "810", "2001": "810", "2002": "810", "2003": "810", "2004": "810", "2005": "810", "2006": "810", "2007": "810", "2008": "810", "2009": "810", "2010": "810", "2011": "810", "2012": "810", "2013": "810", "2014": "810"}, "Switzerland": {"1961": "41285", "1962": "41285", "1963": "41285", "1964": "41285", "1965": "41285", "1966": "41285", "1967": "41285", "1968": "41285", "1969": "41285", "1970": "41285", "1971": "41285", "1972": "41285", "1973": "41285", "1974": "41285", "1975": "41285", "1976": "41285", "1977": "41285", "1978": "41285", "1979": "41285", "1980": "41285", "1981": "41285", "1982": "41285", "1983": "41285", "1984": "41285", "1985": "41285", "1986": "41285", "1987": "41285", "1988": "41285", "1989": "41285", "1990": "41285", "1991": "41285", "1992": "41285", "1993": "41285", "1994": "41285", "1995": "41285", "1996": "41285", "1997": "41285", "1998": "41285", "1999": "41285", "2000": "41285", "2001": "41285", "2002": "41285", "2003": "41285", "2004": "41285", "2005": "41285", "2006": "41285", "2007": "41285", "2008": "41285", "2009": "41285", "2010": "41285", "2011": "41285", "2012": "41285", "2013": "41285", "2014": "41285"}, "Grenada": {"1961": "340", "1962": "340", "1963": "340", "1964": "340", "1965": "340", "1966": "340", "1967": "340", "1968": "340", "1969": "340", "1970": "340", "1971": "340", "1972": "340", "1973": "340", "1974": "340", "1975": "340", "1976": "340", "1977": "340", "1978": "340", "1979": "340", "1980": "340", "1981": "340", "1982": "340", "1983": "340", "1984": "340", "1985": "340", "1986": "340", "1987": "340", "1988": "340", "1989": "340", "1990": "340", "1991": "340", "1992": "340", "1993": "340", "1994": "340", "1995": "340", "1996": "340", "1997": "340", "1998": "340", "1999": "340", "2000": "340", "2001": "340", "2002": "340", "2003": "340", "2004": "340", "2005": "340", "2006": "340", "2007": "340", "2008": "340", "2009": "340", "2010": "340", "2011": "340", "2012": "340", "2013": "340", "2014": "340"}, "Middle East and North Africa (IFC classification)": {}, "Yemen, Rep.": {"1961": "527970", "1962": "527970", "1963": "527970", "1964": "527970", "1965": "527970", "1966": "527970", "1967": "527970", "1968": "527970", "1969": "527970", "1970": "527970", "1971": "527970", "1972": "527970", "1973": "527970", "1974": "527970", "1975": "527970", "1976": "527970", "1977": "527970", "1978": "527970", "1979": "527970", "1980": "527970", "1981": "527970", "1982": "527970", "1983": "527970", "1984": "527970", "1985": "527970", "1986": "527970", "1987": "527970", "1988": "527970", "1989": "527970", "1990": "527970", "1991": "527970", "1992": "527970", "1993": "527970", "1994": "527970", "1995": "527970", "1996": "527970", "1997": "527970", "1998": "527970", "1999": "527970", "2000": "527970", "2001": "527970", "2002": "527970", "2003": "527970", "2004": "527970", "2005": "527970", "2006": "527970", "2007": "527970", "2008": "527970", "2009": "527970", "2010": "527970", "2011": "527970", "2012": "527970", "2013": "527970", "2014": "527970"}, "Isle of Man": {"1961": "570", "1962": "570", "1963": "570", "1964": "570", "1965": "570", "1966": "570", "1967": "570", "1968": "570", "1969": "570", "1970": "570", "1971": "570", "1972": "570", "1973": "570", "1974": "570", "1975": "570", "1976": "570", "1977": "570", "1978": "570", "1979": "570", "1980": "570", "1981": "570", "1982": "570", "1983": "570", "1984": "570", "1985": "570", "1986": "570", "1987": "570", "1988": "570", "1989": "570", "1990": "570", "1991": "570", "1992": "570", "1993": "570", "1994": "570", "1995": "570", "1996": "570", "1997": "570", "1998": "570", "1999": "570", "2000": "570", "2001": "570", "2002": "570", "2003": "570", "2004": "570", "2005": "570", "2006": "570", "2007": "570", "2008": "570", "2009": "570", "2010": "570", "2011": "570", "2012": "570", "2013": "570", "2014": "570"}, "Portugal": {"1961": "92120", "1962": "92120", "1963": "92120", "1964": "92120", "1965": "92120", "1966": "92120", "1967": "92120", "1968": "92120", "1969": "92120", "1970": "92120", "1971": "92120", "1972": "92120", "1973": "92120", "1974": "92120", "1975": "92120", "1976": "92120", "1977": "92120", "1978": "92120", "1979": "92120", "1980": "92120", "1981": "92120", "1982": "92120", "1983": "92120", "1984": "92120", "1985": "92120", "1986": "92120", "1987": "92120", "1988": "92120", "1989": "92120", "1990": "92120", "1991": "92120", "1992": "92120", "1993": "92120", "1994": "92120", "1995": "92120", "1996": "92120", "1997": "92120", "1998": "92120", "1999": "92120", "2000": "92120", "2001": "92120", "2002": "92120", "2003": "92120", "2004": "92120", "2005": "92090", "2006": "92090", "2007": "92090", "2008": "92090", "2009": "92210", "2010": "92210", "2011": "92210", "2012": "92210", "2013": "92210", "2014": "92210"}, "Estonia": {"1961": "45230", "1962": "45230", "1963": "45230", "1964": "45230", "1965": "45230", "1966": "45230", "1967": "45230", "1968": "45230", "1969": "45230", "1970": "45230", "1971": "45230", "1972": "45230", "1973": "45230", "1974": "45230", "1975": "45230", "1976": "45230", "1977": "45230", "1978": "45230", "1979": "45230", "1980": "45230", "1981": "45230", "1982": "45230", "1983": "45230", "1984": "45230", "1985": "45230", "1986": "45230", "1987": "45230", "1988": "45230", "1989": "45230", "1990": "45230", "1991": "45230", "1992": "45230", "1993": "45230", "1994": "45230", "1995": "45230", "1996": "45230", "1997": "45230", "1998": "45230", "1999": "45230", "2000": "45230", "2001": "45230", "2002": "45230", "2003": "45230", "2004": "45230", "2005": "45230", "2006": "45230", "2007": "45230", "2008": "45230", "2009": "45230", "2010": "45230", "2011": "45230", "2012": "45230", "2013": "45230", "2014": "45230"}, "Kosovo": {"1961": "10887", "1962": "10887", "1963": "10887", "1964": "10887", "1965": "10887", "1966": "10887", "1967": "10887", "1968": "10887", "1969": "10887", "1970": "10887", "1971": "10887", "1972": "10887", "1973": "10887", "1974": "10887", "1975": "10887", "1976": "10887", "1977": "10887", "1978": "10887", "1979": "10887", "1980": "10887", "1981": "10887", "1982": "10887", "1983": "10887", "1984": "10887", "1985": "10887", "1986": "10887", "1987": "10887", "1988": "10887", "1989": "10887", "1990": "10887", "1991": "10887", "1992": "10887", "1993": "10887", "1994": "10887", "1995": "10887", "1996": "10887", "1997": "10887", "1998": "10887", "1999": "10887", "2000": "10887", "2001": "10887", "2002": "10887", "2003": "10887", "2004": "10887", "2005": "10887", "2006": "10887", "2007": "10887", "2008": "10887", "2009": "10887", "2010": "10887", "2011": "10887", "2012": "10887", "2013": "10887", "2014": "10887"}, "Sweden": {"1961": "450300", "1962": "450300", "1963": "450300", "1964": "450300", "1965": "450300", "1966": "450300", "1967": "450300", "1968": "450300", "1969": "450300", "1970": "450300", "1971": "450300", "1972": "450300", "1973": "450300", "1974": "450300", "1975": "450300", "1976": "450300", "1977": "450300", "1978": "450300", "1979": "450300", "1980": "450300", "1981": "450300", "1982": "450300", "1983": "450300", "1984": "450300", "1985": "450300", "1986": "450300", "1987": "450300", "1988": "450300", "1989": "450300", "1990": "450300", "1991": "450300", "1992": "450300", "1993": "450300", "1994": "450300", "1995": "450300", "1996": "450300", "1997": "450300", "1998": "450300", "1999": "450300", "2000": "450300", "2001": "450300", "2002": "450300", "2003": "450300", "2004": "450300", "2005": "450300", "2006": "450300", "2007": "450300", "2008": "450300", "2009": "450300", "2010": "450300", "2011": "450300", "2012": "447420", "2013": "447420", "2014": "447420"}, "Mexico": {"1961": "1964380", "1962": "1964380", "1963": "1964380", "1964": "1964380", "1965": "1964380", "1966": "1964380", "1967": "1964380", "1968": "1964380", "1969": "1964380", "1970": "1964380", "1971": "1964380", "1972": "1964380", "1973": "1964380", "1974": "1964380", "1975": "1964380", "1976": "1964380", "1977": "1964380", "1978": "1964380", "1979": "1964380", "1980": "1964380", "1981": "1964380", "1982": "1964380", "1983": "1964380", "1984": "1964380", "1985": "1964380", "1986": "1964380", "1987": "1964380", "1988": "1964380", "1989": "1964380", "1990": "1964380", "1991": "1964380", "1992": "1964380", "1993": "1964380", "1994": "1964380", "1995": "1964380", "1996": "1964380", "1997": "1964380", "1998": "1964380", "1999": "1964380", "2000": "1964380", "2001": "1964380", "2002": "1964380", "2003": "1964380", "2004": "1964380", "2005": "1964380", "2006": "1964380", "2007": "1964380", "2008": "1964380", "2009": "1964380", "2010": "1964380", "2011": "1964380", "2012": "1964380", "2013": "1964380", "2014": "1964380"}, "Africa": {}, "South Africa": {"1961": "1219090", "1962": "1219090", "1963": "1219090", "1964": "1219090", "1965": "1219090", "1966": "1219090", "1967": "1219090", "1968": "1219090", "1969": "1219090", "1970": "1219090", "1971": "1219090", "1972": "1219090", "1973": "1219090", "1974": "1219090", "1975": "1219090", "1976": "1219090", "1977": "1219090", "1978": "1219090", "1979": "1219090", "1980": "1219090", "1981": "1219090", "1982": "1219090", "1983": "1219090", "1984": "1219090", "1985": "1219090", "1986": "1219090", "1987": "1219090", "1988": "1219090", "1989": "1219090", "1990": "1219090", "1991": "1219090", "1992": "1219090", "1993": "1219090", "1994": "1219090", "1995": "1219090", "1996": "1219090", "1997": "1219090", "1998": "1219090", "1999": "1219090", "2000": "1219090", "2001": "1219090", "2002": "1219090", "2003": "1219090", "2004": "1219090", "2005": "1219090", "2006": "1219090", "2007": "1219090", "2008": "1219090", "2009": "1219090", "2010": "1219090", "2011": "1219090", "2012": "1219090", "2013": "1219090", "2014": "1219090"}, "Uzbekistan": {"1961": "447400", "1962": "447400", "1963": "447400", "1964": "447400", "1965": "447400", "1966": "447400", "1967": "447400", "1968": "447400", "1969": "447400", "1970": "447400", "1971": "447400", "1972": "447400", "1973": "447400", "1974": "447400", "1975": "447400", "1976": "447400", "1977": "447400", "1978": "447400", "1979": "447400", "1980": "447400", "1981": "447400", "1982": "447400", "1983": "447400", "1984": "447400", "1985": "447400", "1986": "447400", "1987": "447400", "1988": "447400", "1989": "447400", "1990": "447400", "1991": "447400", "1992": "447400", "1993": "447400", "1994": "447400", "1995": "447400", "1996": "447400", "1997": "447400", "1998": "447400", "1999": "447400", "2000": "447400", "2001": "447400", "2002": "447400", "2003": "447400", "2004": "447400", "2005": "447400", "2006": "447400", "2007": "447400", "2008": "447400", "2009": "447400", "2010": "447400", "2011": "447400", "2012": "447400", "2013": "447400", "2014": "447400"}, "Tunisia": {"1961": "163610", "1962": "163610", "1963": "163610", "1964": "163610", "1965": "163610", "1966": "163610", "1967": "163610", "1968": "163610", "1969": "163610", "1970": "163610", "1971": "163610", "1972": "163610", "1973": "163610", "1974": "163610", "1975": "163610", "1976": "163610", "1977": "163610", "1978": "163610", "1979": "163610", "1980": "163610", "1981": "163610", "1982": "163610", "1983": "163610", "1984": "163610", "1985": "163610", "1986": "163610", "1987": "163610", "1988": "163610", "1989": "163610", "1990": "163610", "1991": "163610", "1992": "163610", "1993": "163610", "1994": "163610", "1995": "163610", "1996": "163610", "1997": "163610", "1998": "163610", "1999": "163610", "2000": "163610", "2001": "163610", "2002": "163610", "2003": "163610", "2004": "163610", "2005": "163610", "2006": "163610", "2007": "163610", "2008": "163610", "2009": "163610", "2010": "163610", "2011": "163610", "2012": "163610", "2013": "163610", "2014": "163610"}, "Djibouti": {"1961": "23200", "1962": "23200", "1963": "23200", "1964": "23200", "1965": "23200", "1966": "23200", "1967": "23200", "1968": "23200", "1969": "23200", "1970": "23200", "1971": "23200", "1972": "23200", "1973": "23200", "1974": "23200", "1975": "23200", "1976": "23200", "1977": "23200", "1978": "23200", "1979": "23200", "1980": "23200", "1981": "23200", "1982": "23200", "1983": "23200", "1984": "23200", "1985": "23200", "1986": "23200", "1987": "23200", "1988": "23200", "1989": "23200", "1990": "23200", "1991": "23200", "1992": "23200", "1993": "23200", "1994": "23200", "1995": "23200", "1996": "23200", "1997": "23200", "1998": "23200", "1999": "23200", "2000": "23200", "2001": "23200", "2002": "23200", "2003": "23200", "2004": "23200", "2005": "23200", "2006": "23200", "2007": "23200", "2008": "23200", "2009": "23200", "2010": "23200", "2011": "23200", "2012": "23200", "2013": "23200", "2014": "23200"}, "West Bank and Gaza": {"1961": "6020", "1962": "6020", "1963": "6020", "1964": "6020", "1965": "6020", "1966": "6020", "1967": "6020", "1968": "6020", "1969": "6020", "1970": "6020", "1971": "6020", "1972": "6020", "1973": "6020", "1974": "6020", "1975": "6020", "1976": "6020", "1977": "6020", "1978": "6020", "1979": "6020", "1980": "6020", "1981": "6020", "1982": "6020", "1983": "6020", "1984": "6020", "1985": "6020", "1986": "6020", "1987": "6020", "1988": "6020", "1989": "6020", "1990": "6020", "1991": "6020", "1992": "6020", "1993": "6020", "1994": "6020", "1995": "6020", "1996": "6020", "1997": "6020", "1998": "6020", "1999": "6020", "2000": "6020", "2001": "6020", "2002": "6020", "2003": "6020", "2004": "6020", "2005": "6020", "2006": "6020", "2007": "6020", "2008": "6020", "2009": "6020", "2010": "6020", "2011": "6020", "2012": "6020", "2013": "6020", "2014": "6020"}, "Antigua and Barbuda": {"1961": "440", "1962": "440", "1963": "440", "1964": "440", "1965": "440", "1966": "440", "1967": "440", "1968": "440", "1969": "440", "1970": "440", "1971": "440", "1972": "440", "1973": "440", "1974": "440", "1975": "440", "1976": "440", "1977": "440", "1978": "440", "1979": "440", "1980": "440", "1981": "440", "1982": "440", "1983": "440", "1984": "440", "1985": "440", "1986": "440", "1987": "440", "1988": "440", "1989": "440", "1990": "440", "1991": "440", "1992": "440", "1993": "440", "1994": "440", "1995": "440", "1996": "440", "1997": "440", "1998": "440", "1999": "440", "2000": "440", "2001": "440", "2002": "440", "2003": "440", "2004": "440", "2005": "440", "2006": "440", "2007": "440", "2008": "440", "2009": "440", "2010": "440", "2011": "440", "2012": "440", "2013": "440", "2014": "440"}, "Spain": {"1961": "505990", "1962": "505990", "1963": "505990", "1964": "505990", "1965": "505990", "1966": "505990", "1967": "505990", "1968": "505990", "1969": "505990", "1970": "505990", "1971": "505990", "1972": "505990", "1973": "505990", "1974": "505990", "1975": "505990", "1976": "505990", "1977": "505990", "1978": "505990", "1979": "505990", "1980": "505990", "1981": "505990", "1982": "505990", "1983": "505990", "1984": "505990", "1985": "505990", "1986": "505990", "1987": "505990", "1988": "505990", "1989": "505990", "1990": "505990", "1991": "505990", "1992": "505990", "1993": "505990", "1994": "505990", "1995": "505990", "1996": "505990", "1997": "505990", "1998": "505990", "1999": "505990", "2000": "505000", "2001": "505020", "2002": "505320", "2003": "505370", "2004": "505370", "2005": "505370", "2006": "505370", "2007": "505370", "2008": "505370", "2009": "505370", "2010": "505600", "2011": "505600", "2012": "505600", "2013": "505600", "2014": "505600"}, "Colombia": {"1961": "1141750", "1962": "1141750", "1963": "1141750", "1964": "1141750", "1965": "1141750", "1966": "1141750", "1967": "1141750", "1968": "1141750", "1969": "1141750", "1970": "1141750", "1971": "1141750", "1972": "1141750", "1973": "1141750", "1974": "1141750", "1975": "1141750", "1976": "1141750", "1977": "1141750", "1978": "1141750", "1979": "1141750", "1980": "1141750", "1981": "1141750", "1982": "1141750", "1983": "1141750", "1984": "1141750", "1985": "1141750", "1986": "1141750", "1987": "1141750", "1988": "1141750", "1989": "1141750", "1990": "1141750", "1991": "1141750", "1992": "1141750", "1993": "1141750", "1994": "1141750", "1995": "1141750", "1996": "1141750", "1997": "1141750", "1998": "1141750", "1999": "1141750", "2000": "1141750", "2001": "1141750", "2002": "1141750", "2003": "1141750", "2004": "1141750", "2005": "1141750", "2006": "1141750", "2007": "1141750", "2008": "1141750", "2009": "1141750", "2010": "1141750", "2011": "1141750", "2012": "1141748", "2013": "1141748", "2014": "1141748"}, "Burundi": {"1961": "27830", "1962": "27830", "1963": "27830", "1964": "27830", "1965": "27830", "1966": "27830", "1967": "27830", "1968": "27830", "1969": "27830", "1970": "27830", "1971": "27830", "1972": "27830", "1973": "27830", "1974": "27830", "1975": "27830", "1976": "27830", "1977": "27830", "1978": "27830", "1979": "27830", "1980": "27830", "1981": "27830", "1982": "27830", "1983": "27830", "1984": "27830", "1985": "27830", "1986": "27830", "1987": "27830", "1988": "27830", "1989": "27830", "1990": "27830", "1991": "27830", "1992": "27830", "1993": "27830", "1994": "27830", "1995": "27830", "1996": "27830", "1997": "27830", "1998": "27830", "1999": "27830", "2000": "27830", "2001": "27830", "2002": "27830", "2003": "27830", "2004": "27830", "2005": "27830", "2006": "27830", "2007": "27830", "2008": "27830", "2009": "27830", "2010": "27830", "2011": "27830", "2012": "27830", "2013": "27830", "2014": "27830"}, "Least developed countries: UN classification": {"1961": "20926251", "1962": "20926251", "1963": "20926251", "1964": "20926251", "1965": "20926251", "1966": "20926251", "1967": "20926251", "1968": "20926251", "1969": "20926251", "1970": "20926251", "1971": "20926251", "1972": "20926251", "1973": "20926251", "1974": "20926251", "1975": "20926251", "1976": "20926251", "1977": "20926251", "1978": "20926251", "1979": "20926251", "1980": "20926251", "1981": "20926251", "1982": "20926251", "1983": "20926251", "1984": "20926251", "1985": "20926251", "1986": "20926251", "1987": "20926251", "1988": "20926251", "1989": "20926251", "1990": "20926251", "1991": "20926251", "1992": "20926251", "1993": "20808651", "1994": "20801728", "1995": "20801728", "1996": "20801728", "1997": "20801728", "1998": "20801728", "1999": "20801728", "2000": "20801728", "2001": "20801728", "2002": "20801728", "2003": "20801728", "2004": "20800045", "2005": "20800045", "2006": "20800045", "2007": "20800045", "2008": "20800045", "2009": "20800045", "2010": "20800045", "2011": "20818177.5", "2012": "20818177.5", "2013": "20818177.5", "2014": "20818177.5"}, "Fiji": {"1961": "18270", "1962": "18270", "1963": "18270", "1964": "18270", "1965": "18270", "1966": "18270", "1967": "18270", "1968": "18270", "1969": "18270", "1970": "18270", "1971": "18270", "1972": "18270", "1973": "18270", "1974": "18270", "1975": "18270", "1976": "18270", "1977": "18270", "1978": "18270", "1979": "18270", "1980": "18270", "1981": "18270", "1982": "18270", "1983": "18270", "1984": "18270", "1985": "18270", "1986": "18270", "1987": "18270", "1988": "18270", "1989": "18270", "1990": "18270", "1991": "18270", "1992": "18270", "1993": "18270", "1994": "18270", "1995": "18270", "1996": "18270", "1997": "18270", "1998": "18270", "1999": "18270", "2000": "18270", "2001": "18270", "2002": "18270", "2003": "18270", "2004": "18270", "2005": "18270", "2006": "18270", "2007": "18270", "2008": "18270", "2009": "18270", "2010": "18270", "2011": "18270", "2012": "18270", "2013": "18270", "2014": "18270"}, "Barbados": {"1961": "430", "1962": "430", "1963": "430", "1964": "430", "1965": "430", "1966": "430", "1967": "430", "1968": "430", "1969": "430", "1970": "430", "1971": "430", "1972": "430", "1973": "430", "1974": "430", "1975": "430", "1976": "430", "1977": "430", "1978": "430", "1979": "430", "1980": "430", "1981": "430", "1982": "430", "1983": "430", "1984": "430", "1985": "430", "1986": "430", "1987": "430", "1988": "430", "1989": "430", "1990": "430", "1991": "430", "1992": "430", "1993": "430", "1994": "430", "1995": "430", "1996": "430", "1997": "430", "1998": "430", "1999": "430", "2000": "430", "2001": "430", "2002": "430", "2003": "430", "2004": "430", "2005": "430", "2006": "430", "2007": "430", "2008": "430", "2009": "430", "2010": "430", "2011": "430", "2012": "430", "2013": "430", "2014": "430"}, "Seychelles": {"1961": "460", "1962": "460", "1963": "460", "1964": "460", "1965": "460", "1966": "460", "1967": "460", "1968": "460", "1969": "460", "1970": "460", "1971": "460", "1972": "460", "1973": "460", "1974": "460", "1975": "460", "1976": "460", "1977": "460", "1978": "460", "1979": "460", "1980": "460", "1981": "460", "1982": "460", "1983": "460", "1984": "460", "1985": "460", "1986": "460", "1987": "460", "1988": "460", "1989": "460", "1990": "460", "1991": "460", "1992": "460", "1993": "460", "1994": "460", "1995": "460", "1996": "460", "1997": "460", "1998": "460", "1999": "460", "2000": "460", "2001": "460", "2002": "460", "2003": "460", "2004": "460", "2005": "460", "2006": "460", "2007": "460", "2008": "460", "2009": "460", "2010": "460", "2011": "460", "2012": "460", "2013": "460", "2014": "460"}, "Madagascar": {"1961": "587040", "1962": "587040", "1963": "587040", "1964": "587040", "1965": "587040", "1966": "587040", "1967": "587040", "1968": "587040", "1969": "587040", "1970": "587040", "1971": "587040", "1972": "587040", "1973": "587040", "1974": "587040", "1975": "587040", "1976": "587040", "1977": "587040", "1978": "587040", "1979": "587040", "1980": "587040", "1981": "587040", "1982": "587040", "1983": "587040", "1984": "587040", "1985": "587040", "1986": "587040", "1987": "587040", "1988": "587040", "1989": "587040", "1990": "587040", "1991": "587040", "1992": "587040", "1993": "587040", "1994": "587040", "1995": "587040", "1996": "587040", "1997": "587040", "1998": "587040", "1999": "587040", "2000": "587040", "2001": "587040", "2002": "587040", "2003": "587040", "2004": "587040", "2005": "587040", "2006": "587040", "2007": "587040", "2008": "587040", "2009": "587040", "2010": "587040", "2011": "587295", "2012": "587295", "2013": "587295", "2014": "587295"}, "Italy": {"1961": "301340", "1962": "301340", "1963": "301340", "1964": "301340", "1965": "301340", "1966": "301340", "1967": "301340", "1968": "301340", "1969": "301340", "1970": "301340", "1971": "301340", "1972": "301340", "1973": "301340", "1974": "301340", "1975": "301340", "1976": "301340", "1977": "301340", "1978": "301340", "1979": "301340", "1980": "301340", "1981": "301340", "1982": "301340", "1983": "301340", "1984": "301340", "1985": "301340", "1986": "301340", "1987": "301340", "1988": "301340", "1989": "301340", "1990": "301340", "1991": "301340", "1992": "301340", "1993": "301340", "1994": "301340", "1995": "301340", "1996": "301340", "1997": "301340", "1998": "301340", "1999": "301340", "2000": "301340", "2001": "301340", "2002": "301340", "2003": "301340", "2004": "301340", "2005": "301340", "2006": "301340", "2007": "301340", "2008": "301340", "2009": "301340", "2010": "301340", "2011": "301340", "2012": "301340", "2013": "301340", "2014": "301340"}, "Curacao": {"1961": "444", "1962": "444", "1963": "444", "1964": "444", "1965": "444", "1966": "444", "1967": "444", "1968": "444", "1969": "444", "1970": "444", "1971": "444", "1972": "444", "1973": "444", "1974": "444", "1975": "444", "1976": "444", "1977": "444", "1978": "444", "1979": "444", "1980": "444", "1981": "444", "1982": "444", "1983": "444", "1984": "444", "1985": "444", "1986": "444", "1987": "444", "1988": "444", "1989": "444", "1990": "444", "1991": "444", "1992": "444", "1993": "444", "1994": "444", "1995": "444", "1996": "444", "1997": "444", "1998": "444", "1999": "444", "2000": "444", "2001": "444", "2002": "444", "2003": "444", "2004": "444", "2005": "444", "2006": "444", "2007": "444", "2008": "444", "2009": "444", "2010": "444", "2011": "444", "2012": "444", "2013": "444", "2014": "444"}, "Bhutan": {"1961": "47000", "1962": "47000", "1963": "47000", "1964": "47000", "1965": "47000", "1966": "47000", "1967": "47000", "1968": "47000", "1969": "47000", "1970": "47000", "1971": "47000", "1972": "47000", "1973": "47000", "1974": "47000", "1975": "47000", "1976": "47000", "1977": "47000", "1978": "47000", "1979": "47000", "1980": "47000", "1981": "47000", "1982": "47000", "1983": "47000", "1984": "47000", "1985": "47000", "1986": "47000", "1987": "47000", "1988": "47000", "1989": "47000", "1990": "47000", "1991": "47000", "1992": "47000", "1993": "47000", "1994": "40077", "1995": "40077", "1996": "40077", "1997": "40077", "1998": "40077", "1999": "40077", "2000": "40077", "2001": "40077", "2002": "40077", "2003": "40077", "2004": "38394", "2005": "38394", "2006": "38394", "2007": "38394", "2008": "38394", "2009": "38394", "2010": "38394", "2011": "38394", "2012": "38394", "2013": "38394", "2014": "38394"}, "Sudan": {"1961": "2505810", "1962": "2505810", "1963": "2505810", "1964": "2505810", "1965": "2505810", "1966": "2505810", "1967": "2505810", "1968": "2505810", "1969": "2505810", "1970": "2505810", "1971": "2505810", "1972": "2505810", "1973": "2505810", "1974": "2505810", "1975": "2505810", "1976": "2505810", "1977": "2505810", "1978": "2505810", "1979": "2505810", "1980": "2505810", "1981": "2505810", "1982": "2505810", "1983": "2505810", "1984": "2505810", "1985": "2505810", "1986": "2505810", "1987": "2505810", "1988": "2505810", "1989": "2505810", "1990": "2505810", "1991": "2505810", "1992": "2505810", "1993": "2505810", "1994": "2505810", "1995": "2505810", "1996": "2505810", "1997": "2505810", "1998": "2505810", "1999": "2505810", "2000": "2505810", "2001": "2505810", "2002": "2505810", "2003": "2505810", "2004": "2505810", "2005": "2505810", "2006": "2505810", "2007": "2505810", "2008": "2505810", "2009": "2505810", "2010": "2505810", "2011": "1879357.5", "2012": "1879357.5", "2013": "1879357.5", "2014": "1879357.5"}, "Latin America and the Caribbean": {}, "Nepal": {"1961": "147180", "1962": "147180", "1963": "147180", "1964": "147180", "1965": "147180", "1966": "147180", "1967": "147180", "1968": "147180", "1969": "147180", "1970": "147180", "1971": "147180", "1972": "147180", "1973": "147180", "1974": "147180", "1975": "147180", "1976": "147180", "1977": "147180", "1978": "147180", "1979": "147180", "1980": "147180", "1981": "147180", "1982": "147180", "1983": "147180", "1984": "147180", "1985": "147180", "1986": "147180", "1987": "147180", "1988": "147180", "1989": "147180", "1990": "147180", "1991": "147180", "1992": "147180", "1993": "147180", "1994": "147180", "1995": "147180", "1996": "147180", "1997": "147180", "1998": "147180", "1999": "147180", "2000": "147180", "2001": "147180", "2002": "147180", "2003": "147180", "2004": "147180", "2005": "147180", "2006": "147180", "2007": "147180", "2008": "147180", "2009": "147180", "2010": "147180", "2011": "147180", "2012": "147180", "2013": "147180", "2014": "147180"}, "Singapore": {"1961": "680", "1962": "680", "1963": "680", "1964": "680", "1965": "680", "1966": "680", "1967": "680", "1968": "680", "1969": "680", "1970": "680", "1971": "680", "1972": "680", "1973": "680", "1974": "680", "1975": "680", "1976": "680", "1977": "680", "1978": "680", "1979": "680", "1980": "680", "1981": "680", "1982": "680", "1983": "680", "1984": "680", "1985": "680", "1986": "680", "1987": "680", "1988": "680", "1989": "680", "1990": "680", "1991": "680", "1992": "680", "1993": "680", "1994": "680", "1995": "680", "1996": "680", "1997": "680", "1998": "680", "1999": "680", "2000": "680", "2001": "680", "2002": "685", "2003": "697", "2004": "699", "2005": "699", "2006": "704", "2007": "705", "2008": "710", "2009": "710", "2010": "712", "2011": "714", "2012": "716", "2013": "716", "2014": "716"}, "Malta": {"1961": "320", "1962": "320", "1963": "320", "1964": "320", "1965": "320", "1966": "320", "1967": "320", "1968": "320", "1969": "320", "1970": "320", "1971": "320", "1972": "320", "1973": "320", "1974": "320", "1975": "320", "1976": "320", "1977": "320", "1978": "320", "1979": "320", "1980": "320", "1981": "320", "1982": "320", "1983": "320", "1984": "320", "1985": "320", "1986": "320", "1987": "320", "1988": "320", "1989": "320", "1990": "320", "1991": "320", "1992": "320", "1993": "320", "1994": "320", "1995": "320", "1996": "320", "1997": "320", "1998": "320", "1999": "320", "2000": "320", "2001": "320", "2002": "320", "2003": "320", "2004": "320", "2005": "320", "2006": "320", "2007": "320", "2008": "320", "2009": "320", "2010": "320", "2011": "320", "2012": "320", "2013": "320", "2014": "320"}, "Netherlands": {"1961": "41530", "1962": "41530", "1963": "41530", "1964": "41530", "1965": "41530", "1966": "41530", "1967": "41530", "1968": "41530", "1969": "41530", "1970": "41530", "1971": "41530", "1972": "41530", "1973": "41530", "1974": "41530", "1975": "41530", "1976": "41530", "1977": "41530", "1978": "41530", "1979": "41530", "1980": "41530", "1981": "41530", "1982": "41530", "1983": "41530", "1984": "41530", "1985": "41530", "1986": "41530", "1987": "41530", "1988": "41530", "1989": "41530", "1990": "41530", "1991": "41530", "1992": "41530", "1993": "41530", "1994": "41530", "1995": "41530", "1996": "41530", "1997": "41530", "1998": "41530", "1999": "41530", "2000": "41530", "2001": "41530", "2002": "41530", "2003": "41530", "2004": "41530", "2005": "41540", "2006": "41540", "2007": "41540", "2008": "41540", "2009": "41540", "2010": "41540", "2011": "41500", "2012": "41500", "2013": "41500", "2014": "41500"}, "Macao SAR, China": {"1961": "20", "1962": "20", "1963": "20", "1964": "20", "1965": "20", "1966": "20", "1967": "20", "1968": "20", "1969": "20", "1970": "20", "1971": "20", "1972": "20", "1973": "20", "1974": "20", "1975": "20", "1976": "20", "1977": "20", "1978": "20", "1979": "20", "1980": "20", "1981": "20", "1982": "20", "1983": "20", "1984": "20", "1985": "20", "1986": "20", "1987": "20", "1988": "20", "1989": "20", "1990": "20", "1991": "20", "1992": "20", "1993": "20", "1994": "20", "1995": "20", "1996": "20", "1997": "20", "1998": "20", "1999": "20", "2000": "20", "2001": "26", "2002": "27", "2003": "27", "2004": "28", "2005": "28", "2006": "28.6", "2007": "29.2", "2008": "29.2", "2009": "29.5", "2010": "29.7", "2011": "29.9", "2012": "29.9", "2013": "29.9", "2014": "29.9"}, "Andean Region": {}, "Middle East & North Africa (developing only)": {"1961": "8777960", "1962": "8777960", "1963": "8777960", "1964": "8777960", "1965": "8777960", "1966": "8777960", "1967": "8777960", "1968": "8777960", "1969": "8777960", "1970": "8777960", "1971": "8777960", "1972": "8777960", "1973": "8777960", "1974": "8777960", "1975": "8777960", "1976": "8777960", "1977": "8777960", "1978": "8777960", "1979": "8777960", "1980": "8777960", "1981": "8777960", "1982": "8777960", "1983": "8777960", "1984": "8777960", "1985": "8777960", "1986": "8777960", "1987": "8777960", "1988": "8777960", "1989": "8777960", "1990": "8777960", "1991": "8777960", "1992": "8777960", "1993": "8777960", "1994": "8777960", "1995": "8777960", "1996": "8777960", "1997": "8777960", "1998": "8777960", "1999": "8777960", "2000": "8777960", "2001": "8777960", "2002": "8777960", "2003": "8777960", "2004": "8777960", "2005": "8777960", "2006": "8777960", "2007": "8777960", "2008": "8777960", "2009": "8775420", "2010": "8775420", "2011": "8775420", "2012": "8775420", "2013": "8775420", "2014": "8775420"}, "Turks and Caicos Islands": {"1961": "950", "1962": "950", "1963": "950", "1964": "950", "1965": "950", "1966": "950", "1967": "950", "1968": "950", "1969": "950", "1970": "950", "1971": "950", "1972": "950", "1973": "950", "1974": "950", "1975": "950", "1976": "950", "1977": "950", "1978": "950", "1979": "950", "1980": "950", "1981": "950", "1982": "950", "1983": "950", "1984": "950", "1985": "950", "1986": "950", "1987": "950", "1988": "950", "1989": "950", "1990": "950", "1991": "950", "1992": "950", "1993": "950", "1994": "950", "1995": "950", "1996": "950", "1997": "950", "1998": "950", "1999": "950", "2000": "950", "2001": "950", "2002": "950", "2003": "950", "2004": "950", "2005": "950", "2006": "950", "2007": "950", "2008": "950", "2009": "950", "2010": "950", "2011": "950", "2012": "950", "2013": "950", "2014": "950"}, "St. Martin (French part)": {"1961": "54.4", "1962": "54.4", "1963": "54.4", "1964": "54.4", "1965": "54.4", "1966": "54.4", "1967": "54.4", "1968": "54.4", "1969": "54.4", "1970": "54.4", "1971": "54.4", "1972": "54.4", "1973": "54.4", "1974": "54.4", "1975": "54.4", "1976": "54.4", "1977": "54.4", "1978": "54.4", "1979": "54.4", "1980": "54.4", "1981": "54.4", "1982": "54.4", "1983": "54.4", "1984": "54.4", "1985": "54.4", "1986": "54.4", "1987": "54.4", "1988": "54.4", "1989": "54.4", "1990": "54.4", "1991": "54.4", "1992": "54.4", "1993": "54.4", "1994": "54.4", "1995": "54.4", "1996": "54.4", "1997": "54.4", "1998": "54.4", "1999": "54.4", "2000": "54.4", "2001": "54.4", "2002": "54.4", "2003": "54.4", "2004": "54.4", "2005": "54.4", "2006": "54.4", "2007": "54.4", "2008": "54.4", "2009": "54.4", "2010": "54.4", "2011": "54.4", "2012": "54.4", "2013": "54.4", "2014": "54.4"}, "Iran, Islamic Rep.": {"1961": "1745150", "1962": "1745150", "1963": "1745150", "1964": "1745150", "1965": "1745150", "1966": "1745150", "1967": "1745150", "1968": "1745150", "1969": "1745150", "1970": "1745150", "1971": "1745150", "1972": "1745150", "1973": "1745150", "1974": "1745150", "1975": "1745150", "1976": "1745150", "1977": "1745150", "1978": "1745150", "1979": "1745150", "1980": "1745150", "1981": "1745150", "1982": "1745150", "1983": "1745150", "1984": "1745150", "1985": "1745150", "1986": "1745150", "1987": "1745150", "1988": "1745150", "1989": "1745150", "1990": "1745150", "1991": "1745150", "1992": "1745150", "1993": "1745150", "1994": "1745150", "1995": "1745150", "1996": "1745150", "1997": "1745150", "1998": "1745150", "1999": "1745150", "2000": "1745150", "2001": "1745150", "2002": "1745150", "2003": "1745150", "2004": "1745150", "2005": "1745150", "2006": "1745150", "2007": "1745150", "2008": "1745150", "2009": "1745150", "2010": "1745150", "2011": "1745150", "2012": "1745150", "2013": "1745150", "2014": "1745150"}, "Israel": {"1961": "22070", "1962": "22070", "1963": "22070", "1964": "22070", "1965": "22070", "1966": "22070", "1967": "22070", "1968": "22070", "1969": "22070", "1970": "22070", "1971": "22070", "1972": "22070", "1973": "22070", "1974": "22070", "1975": "22070", "1976": "22070", "1977": "22070", "1978": "22070", "1979": "22070", "1980": "22070", "1981": "22070", "1982": "22070", "1983": "22070", "1984": "22070", "1985": "22070", "1986": "22070", "1987": "22070", "1988": "22070", "1989": "22070", "1990": "22070", "1991": "22070", "1992": "22070", "1993": "22070", "1994": "22070", "1995": "22070", "1996": "22070", "1997": "22070", "1998": "22070", "1999": "22070", "2000": "22070", "2001": "22070", "2002": "22070", "2003": "22070", "2004": "22070", "2005": "22070", "2006": "22070", "2007": "22070", "2008": "22070", "2009": "22070", "2010": "22070", "2011": "22070", "2012": "22070", "2013": "22070", "2014": "22070"}, "Indonesia": {"1961": "1910930", "1962": "1910930", "1963": "1910930", "1964": "1910930", "1965": "1910930", "1966": "1910930", "1967": "1910930", "1968": "1910930", "1969": "1910930", "1970": "1910930", "1971": "1910930", "1972": "1910930", "1973": "1910930", "1974": "1910930", "1975": "1910930", "1976": "1910930", "1977": "1910930", "1978": "1910930", "1979": "1910930", "1980": "1910930", "1981": "1910930", "1982": "1910930", "1983": "1910930", "1984": "1910930", "1985": "1910930", "1986": "1910930", "1987": "1910930", "1988": "1910930", "1989": "1910930", "1990": "1910930", "1991": "1910930", "1992": "1910930", "1993": "1910930", "1994": "1910930", "1995": "1910930", "1996": "1910930", "1997": "1910930", "1998": "1910930", "1999": "1910930", "2000": "1910930", "2001": "1910930", "2002": "1910930", "2003": "1910930", "2004": "1910930", "2005": "1910930", "2006": "1910930", "2007": "1910930", "2008": "1910930", "2009": "1910930", "2010": "1910930", "2011": "1910930", "2012": "1910930", "2013": "1910930", "2014": "1910930"}, "Malaysia": {"1961": "330800", "1962": "330800", "1963": "330800", "1964": "330800", "1965": "330800", "1966": "330800", "1967": "330800", "1968": "330800", "1969": "330800", "1970": "330800", "1971": "330800", "1972": "330800", "1973": "330800", "1974": "330800", "1975": "330800", "1976": "330800", "1977": "330800", "1978": "330800", "1979": "330800", "1980": "330800", "1981": "330800", "1982": "330800", "1983": "330800", "1984": "330800", "1985": "330800", "1986": "330800", "1987": "330800", "1988": "330800", "1989": "330800", "1990": "330800", "1991": "330800", "1992": "330800", "1993": "330800", "1994": "330800", "1995": "330800", "1996": "330800", "1997": "330800", "1998": "330800", "1999": "330800", "2000": "330800", "2001": "330800", "2002": "330800", "2003": "330800", "2004": "330800", "2005": "330800", "2006": "330800", "2007": "330800", "2008": "330800", "2009": "330800", "2010": "330800", "2011": "330800", "2012": "330800", "2013": "330800", "2014": "330800"}, "Iceland": {"1961": "103000", "1962": "103000", "1963": "103000", "1964": "103000", "1965": "103000", "1966": "103000", "1967": "103000", "1968": "103000", "1969": "103000", "1970": "103000", "1971": "103000", "1972": "103000", "1973": "103000", "1974": "103000", "1975": "103000", "1976": "103000", "1977": "103000", "1978": "103000", "1979": "103000", "1980": "103000", "1981": "103000", "1982": "103000", "1983": "103000", "1984": "103000", "1985": "103000", "1986": "103000", "1987": "103000", "1988": "103000", "1989": "103000", "1990": "103000", "1991": "103000", "1992": "103000", "1993": "103000", "1994": "103000", "1995": "103000", "1996": "103000", "1997": "103000", "1998": "103000", "1999": "103000", "2000": "103000", "2001": "103000", "2002": "103000", "2003": "103000", "2004": "103000", "2005": "103000", "2006": "103000", "2007": "103000", "2008": "103000", "2009": "103000", "2010": "103000", "2011": "103000", "2012": "103000", "2013": "103000", "2014": "103000"}, "Zambia": {"1961": "752610", "1962": "752610", "1963": "752610", "1964": "752610", "1965": "752610", "1966": "752610", "1967": "752610", "1968": "752610", "1969": "752610", "1970": "752610", "1971": "752610", "1972": "752610", "1973": "752610", "1974": "752610", "1975": "752610", "1976": "752610", "1977": "752610", "1978": "752610", "1979": "752610", "1980": "752610", "1981": "752610", "1982": "752610", "1983": "752610", "1984": "752610", "1985": "752610", "1986": "752610", "1987": "752610", "1988": "752610", "1989": "752610", "1990": "752610", "1991": "752610", "1992": "752610", "1993": "752610", "1994": "752610", "1995": "752610", "1996": "752610", "1997": "752610", "1998": "752610", "1999": "752610", "2000": "752610", "2001": "752610", "2002": "752610", "2003": "752610", "2004": "752610", "2005": "752610", "2006": "752610", "2007": "752610", "2008": "752610", "2009": "752610", "2010": "752610", "2011": "752610", "2012": "752610", "2013": "752610", "2014": "752610"}, "Sub-Saharan Africa (all income levels)": {"1961": "24390611", "1962": "24390611", "1963": "24390611", "1964": "24390611", "1965": "24390611", "1966": "24390611", "1967": "24390611", "1968": "24390611", "1969": "24390611", "1970": "24390611", "1971": "24390611", "1972": "24390611", "1973": "24390611", "1974": "24390611", "1975": "24390611", "1976": "24390611", "1977": "24390611", "1978": "24390611", "1979": "24390611", "1980": "24390611", "1981": "24390611", "1982": "24390611", "1983": "24390611", "1984": "24390611", "1985": "24390611", "1986": "24390611", "1987": "24390611", "1988": "24390611", "1989": "24390611", "1990": "24390611", "1991": "24390611", "1992": "24390611", "1993": "24273011", "1994": "24273011", "1995": "24273011", "1996": "24273011", "1997": "24273011", "1998": "24273011", "1999": "24273011", "2000": "24273011", "2001": "24273011", "2002": "24273011", "2003": "24273011", "2004": "24273011", "2005": "24273011", "2006": "24273011", "2007": "24273011", "2008": "24273011", "2009": "24273011", "2010": "24273011", "2011": "24291143.5", "2012": "24291143.5", "2013": "24291143.5", "2014": "24291143.5"}, "Senegal": {"1961": "196710", "1962": "196710", "1963": "196710", "1964": "196710", "1965": "196710", "1966": "196710", "1967": "196710", "1968": "196710", "1969": "196710", "1970": "196710", "1971": "196710", "1972": "196710", "1973": "196710", "1974": "196710", "1975": "196710", "1976": "196710", "1977": "196710", "1978": "196710", "1979": "196710", "1980": "196710", "1981": "196710", "1982": "196710", "1983": "196710", "1984": "196710", "1985": "196710", "1986": "196710", "1987": "196710", "1988": "196710", "1989": "196710", "1990": "196710", "1991": "196710", "1992": "196710", "1993": "196710", "1994": "196710", "1995": "196710", "1996": "196710", "1997": "196710", "1998": "196710", "1999": "196710", "2000": "196710", "2001": "196710", "2002": "196710", "2003": "196710", "2004": "196710", "2005": "196710", "2006": "196710", "2007": "196710", "2008": "196710", "2009": "196710", "2010": "196710", "2011": "196710", "2012": "196710", "2013": "196710", "2014": "196710"}, "Papua New Guinea": {"1961": "462840", "1962": "462840", "1963": "462840", "1964": "462840", "1965": "462840", "1966": "462840", "1967": "462840", "1968": "462840", "1969": "462840", "1970": "462840", "1971": "462840", "1972": "462840", "1973": "462840", "1974": "462840", "1975": "462840", "1976": "462840", "1977": "462840", "1978": "462840", "1979": "462840", "1980": "462840", "1981": "462840", "1982": "462840", "1983": "462840", "1984": "462840", "1985": "462840", "1986": "462840", "1987": "462840", "1988": "462840", "1989": "462840", "1990": "462840", "1991": "462840", "1992": "462840", "1993": "462840", "1994": "462840", "1995": "462840", "1996": "462840", "1997": "462840", "1998": "462840", "1999": "462840", "2000": "462840", "2001": "462840", "2002": "462840", "2003": "462840", "2004": "462840", "2005": "462840", "2006": "462840", "2007": "462840", "2008": "462840", "2009": "462840", "2010": "462840", "2011": "462840", "2012": "462840", "2013": "462840", "2014": "462840"}, "Malawi": {"1961": "118480", "1962": "118480", "1963": "118480", "1964": "118480", "1965": "118480", "1966": "118480", "1967": "118480", "1968": "118480", "1969": "118480", "1970": "118480", "1971": "118480", "1972": "118480", "1973": "118480", "1974": "118480", "1975": "118480", "1976": "118480", "1977": "118480", "1978": "118480", "1979": "118480", "1980": "118480", "1981": "118480", "1982": "118480", "1983": "118480", "1984": "118480", "1985": "118480", "1986": "118480", "1987": "118480", "1988": "118480", "1989": "118480", "1990": "118480", "1991": "118480", "1992": "118480", "1993": "118480", "1994": "118480", "1995": "118480", "1996": "118480", "1997": "118480", "1998": "118480", "1999": "118480", "2000": "118480", "2001": "118480", "2002": "118480", "2003": "118480", "2004": "118480", "2005": "118480", "2006": "118480", "2007": "118480", "2008": "118480", "2009": "118480", "2010": "118480", "2011": "118480", "2012": "118480", "2013": "118480", "2014": "118480"}, "Suriname": {"1961": "163820", "1962": "163820", "1963": "163820", "1964": "163820", "1965": "163820", "1966": "163820", "1967": "163820", "1968": "163820", "1969": "163820", "1970": "163820", "1971": "163820", "1972": "163820", "1973": "163820", "1974": "163820", "1975": "163820", "1976": "163820", "1977": "163820", "1978": "163820", "1979": "163820", "1980": "163820", "1981": "163820", "1982": "163820", "1983": "163820", "1984": "163820", "1985": "163820", "1986": "163820", "1987": "163820", "1988": "163820", "1989": "163820", "1990": "163820", "1991": "163820", "1992": "163820", "1993": "163820", "1994": "163820", "1995": "163820", "1996": "163820", "1997": "163820", "1998": "163820", "1999": "163820", "2000": "163820", "2001": "163820", "2002": "163820", "2003": "163820", "2004": "163820", "2005": "163820", "2006": "163820", "2007": "163820", "2008": "163820", "2009": "163820", "2010": "163820", "2011": "163820", "2012": "163820", "2013": "163820", "2014": "163820"}, "Zimbabwe": {"1961": "390760", "1962": "390760", "1963": "390760", "1964": "390760", "1965": "390760", "1966": "390760", "1967": "390760", "1968": "390760", "1969": "390760", "1970": "390760", "1971": "390760", "1972": "390760", "1973": "390760", "1974": "390760", "1975": "390760", "1976": "390760", "1977": "390760", "1978": "390760", "1979": "390760", "1980": "390760", "1981": "390760", "1982": "390760", "1983": "390760", "1984": "390760", "1985": "390760", "1986": "390760", "1987": "390760", "1988": "390760", "1989": "390760", "1990": "390760", "1991": "390760", "1992": "390760", "1993": "390760", "1994": "390760", "1995": "390760", "1996": "390760", "1997": "390760", "1998": "390760", "1999": "390760", "2000": "390760", "2001": "390760", "2002": "390760", "2003": "390760", "2004": "390760", "2005": "390760", "2006": "390760", "2007": "390760", "2008": "390760", "2009": "390760", "2010": "390760", "2011": "390760", "2012": "390760", "2013": "390760", "2014": "390760"}, "Germany": {"1961": "356970", "1962": "356970", "1963": "356970", "1964": "356970", "1965": "356970", "1966": "356970", "1967": "356970", "1968": "356970", "1969": "356970", "1970": "356970", "1971": "356970", "1972": "356970", "1973": "356970", "1974": "356970", "1975": "356970", "1976": "356970", "1977": "356970", "1978": "356970", "1979": "356970", "1980": "356970", "1981": "356970", "1982": "356970", "1983": "356970", "1984": "356970", "1985": "356970", "1986": "356970", "1987": "356970", "1988": "356970", "1989": "356970", "1990": "356970", "1991": "356970", "1992": "356970", "1993": "356990", "1994": "357000", "1995": "357020", "1996": "357030", "1997": "357030", "1998": "357030", "1999": "357030", "2000": "357030", "2001": "357030", "2002": "357040", "2003": "357040", "2004": "357050", "2005": "357090", "2006": "357100", "2007": "357100", "2008": "357110", "2009": "357120", "2010": "357127", "2011": "357140", "2012": "357170", "2013": "357170", "2014": "357170"}, "Oman": {"1961": "309500", "1962": "309500", "1963": "309500", "1964": "309500", "1965": "309500", "1966": "309500", "1967": "309500", "1968": "309500", "1969": "309500", "1970": "309500", "1971": "309500", "1972": "309500", "1973": "309500", "1974": "309500", "1975": "309500", "1976": "309500", "1977": "309500", "1978": "309500", "1979": "309500", "1980": "309500", "1981": "309500", "1982": "309500", "1983": "309500", "1984": "309500", "1985": "309500", "1986": "309500", "1987": "309500", "1988": "309500", "1989": "309500", "1990": "309500", "1991": "309500", "1992": "309500", "1993": "309500", "1994": "309500", "1995": "309500", "1996": "309500", "1997": "309500", "1998": "309500", "1999": "309500", "2000": "309500", "2001": "309500", "2002": "309500", "2003": "309500", "2004": "309500", "2005": "309500", "2006": "309500", "2007": "309500", "2008": "309500", "2009": "309500", "2010": "309500", "2011": "309500", "2012": "309500", "2013": "309500", "2014": "309500"}, "Kazakhstan": {"1961": "2724900", "1962": "2724900", "1963": "2724900", "1964": "2724900", "1965": "2724900", "1966": "2724900", "1967": "2724900", "1968": "2724900", "1969": "2724900", "1970": "2724900", "1971": "2724900", "1972": "2724900", "1973": "2724900", "1974": "2724900", "1975": "2724900", "1976": "2724900", "1977": "2724900", "1978": "2724900", "1979": "2724900", "1980": "2724900", "1981": "2724900", "1982": "2724900", "1983": "2724900", "1984": "2724900", "1985": "2724900", "1986": "2724900", "1987": "2724900", "1988": "2724900", "1989": "2724900", "1990": "2724900", "1991": "2724900", "1992": "2724900", "1993": "2724900", "1994": "2724900", "1995": "2724900", "1996": "2724900", "1997": "2724900", "1998": "2724900", "1999": "2724900", "2000": "2724900", "2001": "2724900", "2002": "2724900", "2003": "2724900", "2004": "2724900", "2005": "2724900", "2006": "2724900", "2007": "2724900", "2008": "2724900", "2009": "2724900", "2010": "2724900", "2011": "2724900", "2012": "2724900", "2013": "2724900", "2014": "2724900"}, "Poland": {"1961": "312690", "1962": "312690", "1963": "312690", "1964": "312690", "1965": "312690", "1966": "312690", "1967": "312690", "1968": "312690", "1969": "312690", "1970": "312690", "1971": "312690", "1972": "312690", "1973": "312690", "1974": "312690", "1975": "312690", "1976": "312690", "1977": "312690", "1978": "312690", "1979": "312690", "1980": "312690", "1981": "312690", "1982": "312690", "1983": "312690", "1984": "312690", "1985": "312690", "1986": "312690", "1987": "312690", "1988": "312690", "1989": "312690", "1990": "312690", "1991": "312690", "1992": "312690", "1993": "312690", "1994": "312690", "1995": "312690", "1996": "312690", "1997": "312690", "1998": "312690", "1999": "312690", "2000": "312690", "2001": "312690", "2002": "312690", "2003": "312690", "2004": "312690", "2005": "312690", "2006": "312680", "2007": "312680", "2008": "312680", "2009": "312680", "2010": "312680", "2011": "312680", "2012": "312680", "2013": "312680", "2014": "312680"}, "Sint Maarten (Dutch part)": {"1961": "34", "1962": "34", "1963": "34", "1964": "34", "1965": "34", "1966": "34", "1967": "34", "1968": "34", "1969": "34", "1970": "34", "1971": "34", "1972": "34", "1973": "34", "1974": "34", "1975": "34", "1976": "34", "1977": "34", "1978": "34", "1979": "34", "1980": "34", "1981": "34", "1982": "34", "1983": "34", "1984": "34", "1985": "34", "1986": "34", "1987": "34", "1988": "34", "1989": "34", "1990": "34", "1991": "34", "1992": "34", "1993": "34", "1994": "34", "1995": "34", "1996": "34", "1997": "34", "1998": "34", "1999": "34", "2000": "34", "2001": "34", "2002": "34", "2003": "34", "2004": "34", "2005": "34", "2006": "34", "2007": "34", "2008": "34", "2009": "34", "2010": "34", "2011": "34", "2012": "34", "2013": "34", "2014": "34"}, "Eritrea": {"1961": "117600", "1962": "117600", "1963": "117600", "1964": "117600", "1965": "117600", "1966": "117600", "1967": "117600", "1968": "117600", "1969": "117600", "1970": "117600", "1971": "117600", "1972": "117600", "1973": "117600", "1974": "117600", "1975": "117600", "1976": "117600", "1977": "117600", "1978": "117600", "1979": "117600", "1980": "117600", "1981": "117600", "1982": "117600", "1983": "117600", "1984": "117600", "1985": "117600", "1986": "117600", "1987": "117600", "1988": "117600", "1989": "117600", "1990": "117600", "1991": "117600", "1992": "117600", "1993": "117600", "1994": "117600", "1995": "117600", "1996": "117600", "1997": "117600", "1998": "117600", "1999": "117600", "2000": "117600", "2001": "117600", "2002": "117600", "2003": "117600", "2004": "117600", "2005": "117600", "2006": "117600", "2007": "117600", "2008": "117600", "2009": "117600", "2010": "117600", "2011": "117600", "2012": "117600", "2013": "117600", "2014": "117600"}, "Virgin Islands (U.S.)": {"1961": "350", "1962": "350", "1963": "350", "1964": "350", "1965": "350", "1966": "350", "1967": "350", "1968": "350", "1969": "350", "1970": "350", "1971": "350", "1972": "350", "1973": "350", "1974": "350", "1975": "350", "1976": "350", "1977": "350", "1978": "350", "1979": "350", "1980": "350", "1981": "350", "1982": "350", "1983": "350", "1984": "350", "1985": "350", "1986": "350", "1987": "350", "1988": "350", "1989": "350", "1990": "350", "1991": "350", "1992": "350", "1993": "350", "1994": "350", "1995": "350", "1996": "350", "1997": "350", "1998": "350", "1999": "350", "2000": "350", "2001": "350", "2002": "350", "2003": "350", "2004": "350", "2005": "350", "2006": "350", "2007": "350", "2008": "350", "2009": "350", "2010": "350", "2011": "350", "2012": "350", "2013": "350", "2014": "350"}, "Iraq": {"1961": "438320", "1962": "438320", "1963": "438320", "1964": "438320", "1965": "438320", "1966": "438320", "1967": "438320", "1968": "438320", "1969": "438320", "1970": "438320", "1971": "438320", "1972": "438320", "1973": "438320", "1974": "438320", "1975": "438320", "1976": "438320", "1977": "438320", "1978": "438320", "1979": "438320", "1980": "438320", "1981": "438320", "1982": "438320", "1983": "438320", "1984": "438320", "1985": "438320", "1986": "438320", "1987": "438320", "1988": "438320", "1989": "438320", "1990": "438320", "1991": "438320", "1992": "438320", "1993": "438320", "1994": "438320", "1995": "438320", "1996": "438320", "1997": "438320", "1998": "438320", "1999": "438320", "2000": "438320", "2001": "438320", "2002": "438320", "2003": "438320", "2004": "438320", "2005": "438320", "2006": "438320", "2007": "438320", "2008": "438320", "2009": "435240", "2010": "435240", "2011": "435240", "2012": "435240", "2013": "435240", "2014": "435240"}, "New Caledonia": {"1961": "18580", "1962": "18580", "1963": "18580", "1964": "18580", "1965": "18580", "1966": "18580", "1967": "18580", "1968": "18580", "1969": "18580", "1970": "18580", "1971": "18580", "1972": "18580", "1973": "18580", "1974": "18580", "1975": "18580", "1976": "18580", "1977": "18580", "1978": "18580", "1979": "18580", "1980": "18580", "1981": "18580", "1982": "18580", "1983": "18580", "1984": "18580", "1985": "18580", "1986": "18580", "1987": "18580", "1988": "18580", "1989": "18580", "1990": "18580", "1991": "18580", "1992": "18580", "1993": "18580", "1994": "18580", "1995": "18580", "1996": "18580", "1997": "18580", "1998": "18580", "1999": "18580", "2000": "18580", "2001": "18580", "2002": "18580", "2003": "18580", "2004": "18580", "2005": "18580", "2006": "18580", "2007": "18580", "2008": "18580", "2009": "18580", "2010": "18580", "2011": "18580", "2012": "18580", "2013": "18580", "2014": "18580"}, "Paraguay": {"1961": "406750", "1962": "406750", "1963": "406750", "1964": "406750", "1965": "406750", "1966": "406750", "1967": "406750", "1968": "406750", "1969": "406750", "1970": "406750", "1971": "406750", "1972": "406750", "1973": "406750", "1974": "406750", "1975": "406750", "1976": "406750", "1977": "406750", "1978": "406750", "1979": "406750", "1980": "406750", "1981": "406750", "1982": "406750", "1983": "406750", "1984": "406750", "1985": "406750", "1986": "406750", "1987": "406750", "1988": "406750", "1989": "406750", "1990": "406750", "1991": "406750", "1992": "406750", "1993": "406750", "1994": "406750", "1995": "406750", "1996": "406750", "1997": "406750", "1998": "406750", "1999": "406750", "2000": "406750", "2001": "406750", "2002": "406750", "2003": "406750", "2004": "406750", "2005": "406750", "2006": "406750", "2007": "406750", "2008": "406750", "2009": "406750", "2010": "406752", "2011": "406752", "2012": "406752", "2013": "406752", "2014": "406752"}, "Not classified": {}, "Latvia": {"1961": "64559", "1962": "64559", "1963": "64559", "1964": "64559", "1965": "64559", "1966": "64559", "1967": "64559", "1968": "64559", "1969": "64559", "1970": "64559", "1971": "64559", "1972": "64559", "1973": "64559", "1974": "64559", "1975": "64559", "1976": "64559", "1977": "64559", "1978": "64559", "1979": "64559", "1980": "64559", "1981": "64559", "1982": "64559", "1983": "64559", "1984": "64559", "1985": "64559", "1986": "64559", "1987": "64559", "1988": "64559", "1989": "64559", "1990": "64559", "1991": "64559", "1992": "64559", "1993": "64559", "1994": "64559", "1995": "64559", "1996": "64559", "1997": "64559", "1998": "64559", "1999": "64559", "2000": "64559", "2001": "64559", "2002": "64559", "2003": "64559", "2004": "64559", "2005": "64559", "2006": "64559", "2007": "64559", "2008": "64559", "2009": "64560", "2010": "64510", "2011": "64480", "2012": "64480", "2013": "64480", "2014": "64480"}, "South Sudan": {"2011": "644330", "2012": "644330", "2013": "644330", "2014": "644330"}, "Guyana": {"1961": "214970", "1962": "214970", "1963": "214970", "1964": "214970", "1965": "214970", "1966": "214970", "1967": "214970", "1968": "214970", "1969": "214970", "1970": "214970", "1971": "214970", "1972": "214970", "1973": "214970", "1974": "214970", "1975": "214970", "1976": "214970", "1977": "214970", "1978": "214970", "1979": "214970", "1980": "214970", "1981": "214970", "1982": "214970", "1983": "214970", "1984": "214970", "1985": "214970", "1986": "214970", "1987": "214970", "1988": "214970", "1989": "214970", "1990": "214970", "1991": "214970", "1992": "214970", "1993": "214970", "1994": "214970", "1995": "214970", "1996": "214970", "1997": "214970", "1998": "214970", "1999": "214970", "2000": "214970", "2001": "214970", "2002": "214970", "2003": "214970", "2004": "214970", "2005": "214970", "2006": "214970", "2007": "214970", "2008": "214970", "2009": "214970", "2010": "214970", "2011": "214970", "2012": "214970", "2013": "214970", "2014": "214970"}, "Honduras": {"1961": "112490", "1962": "112490", "1963": "112490", "1964": "112490", "1965": "112490", "1966": "112490", "1967": "112490", "1968": "112490", "1969": "112490", "1970": "112490", "1971": "112490", "1972": "112490", "1973": "112490", "1974": "112490", "1975": "112490", "1976": "112490", "1977": "112490", "1978": "112490", "1979": "112490", "1980": "112490", "1981": "112490", "1982": "112490", "1983": "112490", "1984": "112490", "1985": "112490", "1986": "112490", "1987": "112490", "1988": "112490", "1989": "112490", "1990": "112490", "1991": "112490", "1992": "112490", "1993": "112490", "1994": "112490", "1995": "112490", "1996": "112490", "1997": "112490", "1998": "112490", "1999": "112490", "2000": "112490", "2001": "112490", "2002": "112490", "2003": "112490", "2004": "112490", "2005": "112490", "2006": "112490", "2007": "112490", "2008": "112490", "2009": "112490", "2010": "112490", "2011": "112490", "2012": "112490", "2013": "112490", "2014": "112490"}, "Myanmar": {"1961": "676590", "1962": "676590", "1963": "676590", "1964": "676590", "1965": "676590", "1966": "676590", "1967": "676590", "1968": "676590", "1969": "676590", "1970": "676590", "1971": "676590", "1972": "676590", "1973": "676590", "1974": "676590", "1975": "676590", "1976": "676590", "1977": "676590", "1978": "676590", "1979": "676590", "1980": "676590", "1981": "676590", "1982": "676590", "1983": "676590", "1984": "676590", "1985": "676590", "1986": "676590", "1987": "676590", "1988": "676590", "1989": "676590", "1990": "676590", "1991": "676590", "1992": "676590", "1993": "676590", "1994": "676590", "1995": "676590", "1996": "676590", "1997": "676590", "1998": "676590", "1999": "676590", "2000": "676590", "2001": "676590", "2002": "676590", "2003": "676590", "2004": "676590", "2005": "676590", "2006": "676590", "2007": "676590", "2008": "676590", "2009": "676590", "2010": "676590", "2011": "676590", "2012": "676590", "2013": "676590", "2014": "676590"}, "Equatorial Guinea": {"1961": "28050", "1962": "28050", "1963": "28050", "1964": "28050", "1965": "28050", "1966": "28050", "1967": "28050", "1968": "28050", "1969": "28050", "1970": "28050", "1971": "28050", "1972": "28050", "1973": "28050", "1974": "28050", "1975": "28050", "1976": "28050", "1977": "28050", "1978": "28050", "1979": "28050", "1980": "28050", "1981": "28050", "1982": "28050", "1983": "28050", "1984": "28050", "1985": "28050", "1986": "28050", "1987": "28050", "1988": "28050", "1989": "28050", "1990": "28050", "1991": "28050", "1992": "28050", "1993": "28050", "1994": "28050", "1995": "28050", "1996": "28050", "1997": "28050", "1998": "28050", "1999": "28050", "2000": "28050", "2001": "28050", "2002": "28050", "2003": "28050", "2004": "28050", "2005": "28050", "2006": "28050", "2007": "28050", "2008": "28050", "2009": "28050", "2010": "28050", "2011": "28050", "2012": "28050", "2013": "28050", "2014": "28050"}, "Central America": {}, "Nicaragua": {"1961": "130370", "1962": "130370", "1963": "130370", "1964": "130370", "1965": "130370", "1966": "130370", "1967": "130370", "1968": "130370", "1969": "130370", "1970": "130370", "1971": "130370", "1972": "130370", "1973": "130370", "1974": "130370", "1975": "130370", "1976": "130370", "1977": "130370", "1978": "130370", "1979": "130370", "1980": "130370", "1981": "130370", "1982": "130370", "1983": "130370", "1984": "130370", "1985": "130370", "1986": "130370", "1987": "130370", "1988": "130370", "1989": "130370", "1990": "130370", "1991": "130370", "1992": "130370", "1993": "130370", "1994": "130370", "1995": "130370", "1996": "130370", "1997": "130370", "1998": "130370", "1999": "130370", "2000": "130370", "2001": "130370", "2002": "130370", "2003": "130370", "2004": "130370", "2005": "130370", "2006": "130370", "2007": "130370", "2008": "130370", "2009": "130370", "2010": "130370", "2011": "130370", "2012": "130370", "2013": "130370", "2014": "130370"}, "Congo, Dem. Rep.": {"1961": "2344860", "1962": "2344860", "1963": "2344860", "1964": "2344860", "1965": "2344860", "1966": "2344860", "1967": "2344860", "1968": "2344860", "1969": "2344860", "1970": "2344860", "1971": "2344860", "1972": "2344860", "1973": "2344860", "1974": "2344860", "1975": "2344860", "1976": "2344860", "1977": "2344860", "1978": "2344860", "1979": "2344860", "1980": "2344860", "1981": "2344860", "1982": "2344860", "1983": "2344860", "1984": "2344860", "1985": "2344860", "1986": "2344860", "1987": "2344860", "1988": "2344860", "1989": "2344860", "1990": "2344860", "1991": "2344860", "1992": "2344860", "1993": "2344860", "1994": "2344860", "1995": "2344860", "1996": "2344860", "1997": "2344860", "1998": "2344860", "1999": "2344860", "2000": "2344860", "2001": "2344860", "2002": "2344860", "2003": "2344860", "2004": "2344860", "2005": "2344860", "2006": "2344860", "2007": "2344860", "2008": "2344860", "2009": "2344860", "2010": "2344860", "2011": "2344860", "2012": "2344860", "2013": "2344860", "2014": "2344860"}, "Serbia": {"1961": "88360", "1962": "88360", "1963": "88360", "1964": "88360", "1965": "88360", "1966": "88360", "1967": "88360", "1968": "88360", "1969": "88360", "1970": "88360", "1971": "88360", "1972": "88360", "1973": "88360", "1974": "88360", "1975": "88360", "1976": "88360", "1977": "88360", "1978": "88360", "1979": "88360", "1980": "88360", "1981": "88360", "1982": "88360", "1983": "88360", "1984": "88360", "1985": "88360", "1986": "88360", "1987": "88360", "1988": "88360", "1989": "88360", "1990": "88360", "1991": "88360", "1992": "88360", "1993": "88360", "1994": "88360", "1995": "88360", "1996": "88360", "1997": "88360", "1998": "88360", "1999": "88360", "2000": "88360", "2001": "88360", "2002": "88360", "2003": "88360", "2004": "88360", "2005": "88360", "2006": "88360", "2007": "88360", "2008": "88360", "2009": "88360", "2010": "88360", "2011": "88360", "2012": "88360", "2013": "88360", "2014": "88360"}, "Botswana": {"1961": "581730", "1962": "581730", "1963": "581730", "1964": "581730", "1965": "581730", "1966": "581730", "1967": "581730", "1968": "581730", "1969": "581730", "1970": "581730", "1971": "581730", "1972": "581730", "1973": "581730", "1974": "581730", "1975": "581730", "1976": "581730", "1977": "581730", "1978": "581730", "1979": "581730", "1980": "581730", "1981": "581730", "1982": "581730", "1983": "581730", "1984": "581730", "1985": "581730", "1986": "581730", "1987": "581730", "1988": "581730", "1989": "581730", "1990": "581730", "1991": "581730", "1992": "581730", "1993": "581730", "1994": "581730", "1995": "581730", "1996": "581730", "1997": "581730", "1998": "581730", "1999": "581730", "2000": "581730", "2001": "581730", "2002": "581730", "2003": "581730", "2004": "581730", "2005": "581730", "2006": "581730", "2007": "581730", "2008": "581730", "2009": "581730", "2010": "581730", "2011": "581730", "2012": "581730", "2013": "581730", "2014": "581730"}, "United Kingdom": {"1961": "243610", "1962": "243610", "1963": "243610", "1964": "243610", "1965": "243610", "1966": "243610", "1967": "243610", "1968": "243610", "1969": "243610", "1970": "243610", "1971": "243610", "1972": "243610", "1973": "243610", "1974": "243610", "1975": "243610", "1976": "243610", "1977": "243610", "1978": "243610", "1979": "243610", "1980": "243610", "1981": "243610", "1982": "243610", "1983": "243610", "1984": "243610", "1985": "243610", "1986": "243610", "1987": "243610", "1988": "243610", "1989": "243610", "1990": "243610", "1991": "243610", "1992": "243610", "1993": "243610", "1994": "243610", "1995": "243610", "1996": "243610", "1997": "243610", "1998": "243610", "1999": "243610", "2000": "243610", "2001": "243610", "2002": "243610", "2003": "243610", "2004": "243610", "2005": "243610", "2006": "243610", "2007": "243610", "2008": "243610", "2009": "243610", "2010": "243610", "2011": "243610", "2012": "243610", "2013": "243610", "2014": "243610"}, "Gambia, The": {"1961": "11300", "1962": "11300", "1963": "11300", "1964": "11300", "1965": "11300", "1966": "11300", "1967": "11300", "1968": "11300", "1969": "11300", "1970": "11300", "1971": "11300", "1972": "11300", "1973": "11300", "1974": "11300", "1975": "11300", "1976": "11300", "1977": "11300", "1978": "11300", "1979": "11300", "1980": "11300", "1981": "11300", "1982": "11300", "1983": "11300", "1984": "11300", "1985": "11300", "1986": "11300", "1987": "11300", "1988": "11300", "1989": "11300", "1990": "11300", "1991": "11300", "1992": "11300", "1993": "11300", "1994": "11300", "1995": "11300", "1996": "11300", "1997": "11300", "1998": "11300", "1999": "11300", "2000": "11300", "2001": "11300", "2002": "11300", "2003": "11300", "2004": "11300", "2005": "11300", "2006": "11300", "2007": "11300", "2008": "11300", "2009": "11300", "2010": "11300", "2011": "11300", "2012": "11300", "2013": "11300", "2014": "11300"}, "High income: nonOECD": {"1961": "24206897.4", "1962": "24206897.4", "1963": "24206897.4", "1964": "24206897.4", "1965": "24206897.4", "1966": "24206897.4", "1967": "24206897.4", "1968": "24206897.4", "1969": "24206897.4", "1970": "24206897.4", "1971": "24206897.4", "1972": "24206897.4", "1973": "24206897.4", "1974": "24206897.4", "1975": "24206897.4", "1976": "24206897.4", "1977": "24206897.4", "1978": "24206897.4", "1979": "24206897.4", "1980": "24206807.4", "1981": "24206807.4", "1982": "24206807.4", "1983": "24206807.4", "1984": "24206807.4", "1985": "24206807.4", "1986": "24206807.4", "1987": "24206807.4", "1988": "24206807.4", "1989": "24206807.4", "1990": "24206807.4", "1991": "24207267.4", "1992": "24207287.4", "1993": "24207287.4", "1994": "24207287.4", "1995": "24207297.4", "1996": "24207377.4", "1997": "24276127.4", "1998": "24276057.4", "1999": "24276057.4", "2000": "24276067.4", "2001": "24276073.4", "2002": "24276079.4", "2003": "24276101.4", "2004": "24276164.4", "2005": "24276174.4", "2006": "24276180", "2007": "24276191.6", "2008": "24276206.6", "2009": "24276207.9", "2010": "24276156.1", "2011": "24276128.3", "2012": "24276130.3", "2013": "24276130.3", "2014": "24276130.3"}, "Greece": {"1961": "131960", "1962": "131960", "1963": "131960", "1964": "131960", "1965": "131960", "1966": "131960", "1967": "131960", "1968": "131960", "1969": "131960", "1970": "131960", "1971": "131960", "1972": "131960", "1973": "131960", "1974": "131960", "1975": "131960", "1976": "131960", "1977": "131960", "1978": "131960", "1979": "131960", "1980": "131960", "1981": "131960", "1982": "131960", "1983": "131960", "1984": "131960", "1985": "131960", "1986": "131960", "1987": "131960", "1988": "131960", "1989": "131960", "1990": "131960", "1991": "131960", "1992": "131960", "1993": "131960", "1994": "131960", "1995": "131960", "1996": "131960", "1997": "131960", "1998": "131960", "1999": "131960", "2000": "131960", "2001": "131960", "2002": "131960", "2003": "131960", "2004": "131960", "2005": "131960", "2006": "131960", "2007": "131960", "2008": "131960", "2009": "131960", "2010": "131960", "2011": "131960", "2012": "131960", "2013": "131960", "2014": "131960"}, "Sri Lanka": {"1961": "65610", "1962": "65610", "1963": "65610", "1964": "65610", "1965": "65610", "1966": "65610", "1967": "65610", "1968": "65610", "1969": "65610", "1970": "65610", "1971": "65610", "1972": "65610", "1973": "65610", "1974": "65610", "1975": "65610", "1976": "65610", "1977": "65610", "1978": "65610", "1979": "65610", "1980": "65610", "1981": "65610", "1982": "65610", "1983": "65610", "1984": "65610", "1985": "65610", "1986": "65610", "1987": "65610", "1988": "65610", "1989": "65610", "1990": "65610", "1991": "65610", "1992": "65610", "1993": "65610", "1994": "65610", "1995": "65610", "1996": "65610", "1997": "65610", "1998": "65610", "1999": "65610", "2000": "65610", "2001": "65610", "2002": "65610", "2003": "65610", "2004": "65610", "2005": "65610", "2006": "65610", "2007": "65610", "2008": "65610", "2009": "65610", "2010": "65610", "2011": "65610", "2012": "65610", "2013": "65610", "2014": "65610"}, "Lebanon": {"1961": "10450", "1962": "10450", "1963": "10450", "1964": "10450", "1965": "10450", "1966": "10450", "1967": "10450", "1968": "10450", "1969": "10450", "1970": "10450", "1971": "10450", "1972": "10450", "1973": "10450", "1974": "10450", "1975": "10450", "1976": "10450", "1977": "10450", "1978": "10450", "1979": "10450", "1980": "10450", "1981": "10450", "1982": "10450", "1983": "10450", "1984": "10450", "1985": "10450", "1986": "10450", "1987": "10450", "1988": "10450", "1989": "10450", "1990": "10450", "1991": "10450", "1992": "10450", "1993": "10450", "1994": "10450", "1995": "10450", "1996": "10450", "1997": "10450", "1998": "10450", "1999": "10450", "2000": "10450", "2001": "10450", "2002": "10450", "2003": "10450", "2004": "10450", "2005": "10450", "2006": "10450", "2007": "10450", "2008": "10450", "2009": "10450", "2010": "10450", "2011": "10450", "2012": "10450", "2013": "10450", "2014": "10450"}, "Comoros": {"1961": "1861", "1962": "1861", "1963": "1861", "1964": "1861", "1965": "1861", "1966": "1861", "1967": "1861", "1968": "1861", "1969": "1861", "1970": "1861", "1971": "1861", "1972": "1861", "1973": "1861", "1974": "1861", "1975": "1861", "1976": "1861", "1977": "1861", "1978": "1861", "1979": "1861", "1980": "1861", "1981": "1861", "1982": "1861", "1983": "1861", "1984": "1861", "1985": "1861", "1986": "1861", "1987": "1861", "1988": "1861", "1989": "1861", "1990": "1861", "1991": "1861", "1992": "1861", "1993": "1861", "1994": "1861", "1995": "1861", "1996": "1861", "1997": "1861", "1998": "1861", "1999": "1861", "2000": "1861", "2001": "1861", "2002": "1861", "2003": "1861", "2004": "1861", "2005": "1861", "2006": "1861", "2007": "1861", "2008": "1861", "2009": "1861", "2010": "1861", "2011": "1861", "2012": "1861", "2013": "1861", "2014": "1861"}, "Heavily indebted poor countries (HIPC)": {"1961": "20510951", "1962": "20510951", "1963": "20510951", "1964": "20510951", "1965": "20510951", "1966": "20510951", "1967": "20510951", "1968": "20510951", "1969": "20510951", "1970": "20510951", "1971": "20510951", "1972": "20510951", "1973": "20510951", "1974": "20510951", "1975": "20510951", "1976": "20510951", "1977": "20510951", "1978": "20510951", "1979": "20510951", "1980": "20510951", "1981": "20510951", "1982": "20510951", "1983": "20510951", "1984": "20510951", "1985": "20510951", "1986": "20510951", "1987": "20510951", "1988": "20510951", "1989": "20510951", "1990": "20510951", "1991": "20510951", "1992": "20510951", "1993": "20393351", "1994": "20393351", "1995": "20393351", "1996": "20393351", "1997": "20393351", "1998": "20393351", "1999": "20393351", "2000": "20393351", "2001": "20393351", "2002": "20393351", "2003": "20393351", "2004": "20393351", "2005": "20393351", "2006": "20393351", "2007": "20393351", "2008": "20393351", "2009": "20393351", "2010": "20393351", "2011": "19767153.5", "2012": "19767153.5", "2013": "19767153.5", "2014": "19767153.5"}}, "LastFirst_IA": [1961, 2014]}
        test = "['[color=000000][b]IA[/b][/color][sub][color=ff0080][Region][/color][color=0d88d2][Year][/color][/sub]', '/', '(', '[color=000000][b]IB[/b][/color][sub][color=ff0080][b][ARE][/b][/color][color=0d88d2][Year][/color][/sub]', '-', '[color=000000][b]IC[/b][/color][sub][color=ff0080][b][ARE][/b][/color][color=0d88d2][b][1962][/b][/color][/sub]', ')', '*', '[color=f44336][i][font=timesi]fabs[/font][/i][/color]', '(', '[color=000000][b]ID[/b][/color][sub][color=ff0080][b][ARB][/b][/color][color=0d88d2][b][1963][/b][/color][/sub]', '*', '-', '1', ')']"

        # Set replacement dictionaries.
        rep1 = {"[color=000000][b]": "self.indicator_var_eval('",
                "[/b][/color][sub][color=ff0080][": "','",
                "][/color][color=0d88d2][": "','",
                "][/color][/sub]": "')"}
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

                formula.append(iv)

        #formula = "['self.indicator_var_eval('IA','Region','Year')', '/', 'self.indicator_var_eval('IB','ABW','Year')', '*', 'self.indicator_var_eval('IC','ABW','1950')', '-', 'self.indicator_var_eval('ID','Region','1950')', '+', 'math.fabs', '(', '-', '10', ')']"

        formula = ["self.indicator_var_eval('IA','Region','Year')", '/', "self.indicator_var_eval('IA','LCN','1961')"]
        string_formula = "".join(formula)

        for Region in self.iry_iteration["r"][1:]:
            region_formula = string_formula.replace('Region', Region)
            for Year in self.iry_iteration["y"][1:]:
                year_formula = region_formula.replace('Year', Year)
                try:
                    print Region, Year, eval(year_formula)
                except Exception as e:
                    print e, type(e)
                    print Region, Year
                    print formula, year_formula
                    for item in formula:
                        try:
                            print eval(item)
                        except:
                            print item

    # Evaluate Indicator value function.
    def indicator_var_eval(self, ind, reg, year):
        # Get region based on ID.
        reg = self.inv_country_dict[reg]

        try:
            # If there is any data, return it.
            return float(self.all_indicators_data[ind][reg][year])

        except KeyError:
            # If no Data, return notice for logging.
            return "NoData: ["+str(ind)+", "+str(reg)+", "+str(year)+"]"

        # Something really unexpected just happened.
        except Exception as e:
            print "def indicator_var_eval(self, ind, reg, year):", type(e), e.__doc__, e.message

class MapDesigner(Screen):

    pass


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
        # TODO Must tell the user to save his preferred indices because they will be lost
        CIMgui.app_closed = True

    # This function returns the window.
    def build(self):
        self.use_kivy_settings = False
        return MainWindow()

# Must be called from main.
if __name__ == "__main__":
    CIMgui().run()
