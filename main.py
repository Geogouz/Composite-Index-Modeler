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

    all_indicators_data = DictProperty({})
    country_list = ListProperty()
    country_dict = DictProperty({})
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
    def popuper(self, message):
        Popup(title='Warning:', content=Label(
            text=message,
            font_size=15,
            halign="center",
            italic=True
        ), size_hint=(None, None), size=(350, 180)).open()

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
                    '"My Indicators" list should not be empty.\nGo to Indicator Selection.')

            else:
                # Clear model's indicator list.
                self.indicator_list.clear_widgets()

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
            self.popuper("Could not prepare Indicators.\nPlease try again.\n\n"+e.message)

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
                    # Check if this is the 0.0 cell.
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
                    btn = Factory.CountrySelectToggle()
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
    def calc_btn_pressed(self, calc_btn):
        self.input.text += calc_btn.text

        t = calc_btn.text

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

        # Creation of new calc item.
        new_calc_item = Factory.Calc_Formula_Item(text=t,
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
    def backward(self):
        if self.my_formula.children:
            self.my_formula.children.remove(self.my_formula.children[0])

    def clear_formula(self):
        # Clear formula.
        self.my_formula.clear_widgets()

        # Creation of new space item.
        self.formula_spacer(0)

    def exec_formula(self, formula):
        if not formula:
            return

        try:
            self.input.text = str(eval(formula))
        except Exception:
            self.input.text = 'error'


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
    def popuper(self, message):
        Popup(title='Warning:', content=Label(
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
            self.popuper("Could not update Coredb.\nPlease try again.\n\n"+e.message)

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
