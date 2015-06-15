# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'

import kivy
kivy.require('1.9.0')

import threading
import time
from datetime import datetime
import urllib2
import json

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
from kivy.properties import BooleanProperty, StringProperty, DictProperty, ObjectProperty, ListProperty
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread

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
            # Compare my_indicators to sorted_indicators so we know if we must re-download model data.
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

    # Function that will run everytime mouse is moved.
    def on_mouse_pos(self, *args):
        for button in self.topics_dic.keys():
            if button.collide_point(*self.topics_slider.to_local(*args[1])):
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
                not (self.selected_indices["feat_index"].text in self.selected_indices["my_indicators"]):
            # Add Index to my_indicators.
            self.selected_indices["my_indicators"][self.selected_indices["feat_index"].text] = \
                self.selected_indices["feat_index"].code

            # Set proper btn backgrounds based on my_indicators.
            self.btn_index_background()

            # Create my_index_box to hold my_index components.
            my_index_box = Factory.MyIndexBox()

            # Create btn_rmv_anchor to hold btn_rmv.
            btn_rmv_anchor = AnchorLayout(size_hint_y=None, height=25, anchor_x="right", padding=[0, 0, 10, 0])

            # Create a removing index btn.
            btn_rmv = Factory.BtnRmv(index=self.selected_indices["feat_index"].text, on_release=self.rmv_my_indicators)

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
                            occurrences.append(index.partition(index[located:located+len(keyword)])[0])
                            occurrences.append("[color=ff0078][b]")
                            occurrences.append(index.partition(index[located:located+len(keyword)])[1])
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
                            note=topic_note)

                        # Bind on_release action.
                        new_button_object.bind(on_release=self.add_topic)

                        # Build each separate dictionary with topic's indices.
                        indices_dic = {}
                        for index in range(1, int(self.coredb_py[2][topic_numbers][0]["indicators_num"])+1):
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
                    topic=args[0].text)

                # Bind each index button with the on_index_selection function.
                btn.bind(on_release=self.on_index_selection)

                # Place the button in the stacklayout.
                self.indices_slider_stack.add_widget(btn)

                # Add the button's ID and object button itself in the global "shown_ind_btns" dictionary.
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

    all_indicators_data = DictProperty({})
    country_list = ListProperty()

    def __init__(self, **kwargs):
        # make sure we aren't overriding any important functionality
        super(IndexCreation, self).__init__(**kwargs)

        self.data_view_now = []
        self.data_queue = None
        self.must_draw_data = True

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    @staticmethod
    def threadonator(*arg):
        threading.Thread(target=arg[0], args=(arg,)).start()

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

    @mainthread
    def model_toolbox_activator(self, state):
        if state:
            self.model_toolbox.opacity = 1
        else:
            self.model_toolbox.opacity = 0

    def toolbox_switcher(self, button):
        self.toolbox_screenmanager.current = button.goto
        self.btn_view_indicators.disabled = False
        self.btn_series_selection.disabled = False
        self.btn_index_algebra.disabled = False
        button.disabled = True

    def dl_manager(self):

        # If I have no indicator in my list do nothing but alert.
        if not self.ic_index_selection.selected_indices["my_indicators"]:
            self.btn_get_indicators.state = "normal"
            self.popuper('"My Indicators" list should not be empty.\nGo to Indicator Selection.')

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
            self.threadonator(self.get_indicators)

    @mainthread
    def spawn_indicator_widget(self, *args):
        print args[0]

        # Creation and placement of each widget part.
        rvw_widget_main_layout = Factory.RvwWidgetMainLayout()
        rvw_widget_head_layout = BoxLayout(orientation="horizontal", size_hint=(None, None), size=(262, 70))
        rvw_widget_scroll = Factory.RvwWidgetScroll()
        rvw_widget_title = Factory.RvwWidgetTitle(text=str(args[0][6]))
        rvw_widget_short_id = Factory.RvwWidgetShortID(text=str(args[0][5]))
        rvw_widget_foot_layout = Factory.RvwWidgetFootLayout()
        rvw_widget_calc1 = Factory.RvwWidgetCalc(width=60)
        rvw_widget_calc1_data = Factory.RvwWidgetCalcData(size=(60, 31), text=str(args[0][0]), color=(0.9, 0.1, 0.1, 1))
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
        rvw_widget_calc3_data = Factory.RvwWidgetCalcData(size=(110, 31), text=args[0][1], color=(0, 0, 0, 1))
        rvw_widget_calc3_desc = Factory.RvwWidgetCalcDesc(size=(110, 32), text="Diachronic\nUnweighted Mean")

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

    def get_indicators(self, *arg):
        # Shortcut for "my_indicators".
        mi = dict(self.ic_index_selection.selected_indices["my_indicators"])

        # Reset indicator data from current database.
        self.all_indicators_data = {}

        # CleanUP country list.
        self.country_list = []

        # Reset connection list.
        connections = []

        # Sort keys for the ID sequence.
        self.sorted_indicators = mi.keys()
        self.sorted_indicators.sort()

        # Number of my indicators.
        items = len(self.sorted_indicators)

        # Prepare dictionary to link model's ID's to WorldBank's ID's.
        id_conn = {}

        # Characters to use for ID creation
        abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        # This var will show ID creation sequence.
        items_created = 0

        # Create short ID's, store that link to a dict and prepare each generic structure. (UPTO 26)
        for i in abc:

            short_id = "I"+i

            # Update ID link dictionary.
            id_conn[self.sorted_indicators[items_created]] = short_id

            # Prepare the basic structure for each indicator.
            self.all_indicators_data[short_id] = {}

            items_created += 1
            if items_created == items:
                break

        # Prepare new ID creation sequence.
        items_created = 0

        # Continue creating short ID's, store that link to a dict and prepare each generic structure. (UPTO 676)
        if items-26 > 0:
            for i in abc:
                for j in abc:

                    short_id = "I"+i+j

                    # Update ID link dictionary.
                    id_conn[self.sorted_indicators[items_created+26]] = short_id

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

            for key in self.all_indicators_data:
                self.all_indicators_data[key][country] = {}

        # Sort country list.
        self.country_list.sort()

        try:
            for indicator in self.sorted_indicators:

                short_id = id_conn[indicator]
                indicator_address = start_url + countries + indicators + mi[indicator] + "/" + end_url

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
                    self.all_indicators_data["LastFirst_"+short_id] = [min(year_list), max(year_list)]

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

                print sum(country_averages)/len(country_averages), mean

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
                print "def get_indicators(self, *arg):", type(e), e.__doc__, e.message

        self.btn_get_indicators.disabled = False
        self.btn_get_indicators.state = "normal"

    def init_data_viewer(self):
        if self.must_draw_data:

            sh_id = "IA"

            self.all_indicators_data = {'IA': {'Canada': {2010: '1.21703340993795', 2005: '1.25057348784206'}, 'Sao Tome and Principe': {}, 'Turkmenistan': {}, 'Lao PDR': {}, 'Arab World': {}, 'Latin America & Caribbean (all income levels)': {}, 'Cambodia': {}, 'Ethiopia': {2001: '0.323472328412633', 2002: '0.327078102286243', 2003: '0.38282658904673', 2004: '0.38282658904673', 2005: '0.444095344551524', 2006: '0.400700483808732', 2007: '0.394517665624361', 2008: '0.51315676939305', 2009: '0.475183264277229', 2010: '0.440188652279548', 2011: '0.510046800997674'}, 'Aruba': {}, 'Swaziland': {}, 'South Asia': {}, 'Argentina': {2002: '1.05353119415741'}, 'Bolivia': {}, 'Bahamas, The': {}, 'Burkina Faso': {}, 'OECD members': {}, 'Bahrain': {}, 'Saudi Arabia': {}, 'Rwanda': {}, 'Sub-Saharan Africa (IFC classification)': {}, 'Togo': {}, 'Thailand': {}, 'Japan': {2001: '35.468391404131', 2002: '35.3348729792148', 2003: '35.0506756756757', 2004: '35.9991514637251', 2005: '36.2745098039216', 2006: '36.0522372083066', 2007: '35.8924731182796', 2008: '35.0907519446845', 2009: '35.170318941202', 2010: '35.3799259743087', 2011: '34.5099758824819', 2012: '34.7109254781271'}, 'Channel Islands': {2001: '9.33333333333333', 2002: '14.8648648648649', 2003: '12.1621621621622', 2004: '6.66666666666667', 2005: '3.94736842105263', 2008: '0.740740740740741', 2009: '3.29545454545455', 2010: '3.51648351648352', 2011: '4.27083333333333', 2012: '3.15789473684211'}, 'American Samoa': {}, 'Northern Mariana Islands': {}, 'Slovenia': {2001: '0.588235294117647', 2002: '0.594059405940594', 2003: '0.588235294117647', 2004: '0.609756097560976', 2005: '0.392927308447937', 2006: '0.610997963340122', 2007: '0.803212851405622', 2008: '0.813008130081301', 2009: '0.854700854700855', 2010: '0.827643285743844', 2011: '0.872410032715376', 2012: '0.416927246195539'}, 'Guatemala': {}, 'Bosnia and Herzegovina': {}, 'Kuwait': {}, 'Russian Federation': {2001: '2.06906728272949', 2002: '2.05214838611407', 2003: '2.09962224369674', 2004: '2.09741642744699', 2005: '2.07436943620178', 2006: '2.05719111969112', 2007: '2.01937223560426', 2008: '1.97082053328631'}, 'Jordan': {2001: '7.14285714285714', 2002: '7.31707317073171', 2003: '7.06467661691542', 2004: '7.32883317261331', 2005: '7.89733464955577', 2006: '8.25147347740668', 2007: '7.47430706944877', 2008: '9.54241645244216', 2009: '9.24878048780488', 2010: '9.61787887857927', 2011: '9.60502692998205', 2012: '9.18161757651348'}, 'St. Lucia': {}, 'Congo, Rep.': {}, 'North Africa': {}, 'Dominica': {}, 'Liberia': {}, 'Maldives': {}, 'East Asia & Pacific (all income levels)': {}, 'Southern Cone': {}, 'Lithuania': {}, 'Tanzania': {}, 'Vietnam': {}, 'Cabo Verde': {2004: '4.7027027027027'}, 'Greenland': {}, 'Gabon': {}, 'Monaco': {}, 'New Zealand': {2002: '3.17381601785272'}, 'European Union': {}, 'Jamaica': {}, 'Albania': {2008: '9.99153259949196', 2009: '16.8151169566303', 2010: '17.0232248397569', 2012: '17.0398734704071', 2007: '17.426273458445'}, 'Samoa': {}, 'Slovak Republic': {2001: '4.92239467849224', 2002: '3.35270451497541', 2003: '4.20393559928444', 2004: '2.17166494312306', 2005: '1.33951571354972', 2006: '1.28932439401753', 2007: '1.29533678756477', 2008: '1.34228187919463', 2009: '1.03626943005181', 2010: '0.76104283437034', 2011: '0.715137067938021', 2012: '1.28670748158141'}, 'United Arab Emirates': {2010: '19.1291215706016'}, 'Guam': {}, 'Uruguay': {2006: '1.15824823521349', 2007: '1.07881536452965', 2008: '1.21786197564276', 2009: '1.18355339672984', 2010: '1.23938170171285', 2011: '1.3910140492419', 2012: '1.3107018808572'}, 'India': {2001: '32.2073057893366', 2002: '31.6168343173903', 2003: '29.8770444071011', 2004: '31.6293042652555', 2005: '32.9181910173581', 2006: '33.5667016719175', 2007: '34.3371784384755', 2008: '34.6595588398958', 2009: '35.1161071998133', 2010: '35.1893368343171'}, 'Azerbaijan': {2001: '29.9856709372893', 2002: '29.9900946279163', 2003: '29.9289109493964', 2004: '30.0321773328566', 2005: '30.0508552935737', 2006: '30.0357443229605', 2007: '30.0557132345212', 2008: '30.0523472155065', 2009: '29.5251508208438', 2010: '29.4767978518083', 2011: '29.4545683309917', 2012: '29.5262462512845'}, 'Lesotho': {2012: '0.0481337242375181'}, 'Kenya': {2001: '0.0447110548083014', 2002: '0.0261018718770975', 2003: '0.111632060727841', 2004: '0.0407528156490812', 2005: '0.0407377231316199', 2006: '0.0462038885192578', 2007: '0.0354243542435424', 2008: '0.0334558823529412', 2009: '0.0367941712204007'}, 'Latin America and the Caribbean (IFC classification)': {}, 'Upper middle income': {}, 'Tajikistan': {2008: '15.0370213666173', 2009: '14.7789473684211', 2006: '14.9440337909187', 2007: '15.0348910974836'}, 'Pacific island small states': {}, 'Turkey': {2002: '12.658996019031', 2003: '12.8309221533314', 2004: '12.6546954622664', 2005: '12.6507047036848', 2006: '12.87876916998', 2007: '13.2008606505506', 2008: '13.3300955983845', 2009: '13.4023797897767', 2010: '13.3676817389521', 2011: '13.6350563442884', 2012: '13.5782539641211'}, 'Afghanistan': {2001: '5.6684237014277', 2002: '4.62214923317352', 2003: '7.25929833816935', 2004: '5.50236079238216', 2005: '5.84014771828014', 2006: '6.08546557636508', 2007: '5.94038512265893', 2008: '5.77947771036666', 2009: '4.84304932735426', 2010: '5.00131891321551', 2011: '5.39171722500659', 2012: '5.46557636507518'}, 'Venezuela, RB': {}, 'Bangladesh': {2004: '51.346133218921', 2005: '51.1223284287402', 2006: '52.6185344827586'}, 'Mauritania': {}, 'Solomon Islands': {}, 'Hong Kong SAR, China': {}, 'San Marino': {}, 'Mongolia': {}, 'France': {2005: '5.66835871404399', 2007: '5.06152695628527'}, 'Syrian Arab Republic': {2003: '9.85303699413596', 2004: '10.3487953973391', 2005: '10.3124096037026', 2006: '10.1030482092671', 2007: '10.0453335252213', 2008: '9.75679953950209', 2009: '8.90135174000575', 2010: '9.64193270060397', 2011: '10.0908828620889', 2012: '10.2578837727175'}, 'Bermuda': {}, 'Namibia': {}, 'Somalia': {}, 'Peru': {}, 'Vanuatu': {}, 'Nigeria': {}, 'South Asia (IFC classification)': {}, 'Norway': {2010: '4.27435387673956', 2004: '4.23076923076923', 2005: '4.15057915057915', 2006: '5.41062801932367'}, "Cote d'Ivoire": {}, 'Europe & Central Asia (developing only)': {}, 'Benin': {}, 'Other small states': {}, 'Cuba': {}, 'Cameroon': {}, 'Montenegro': {}, 'Low & middle income': {}, 'Middle East (developing only)': {}, 'China': {2003: '9.08879911918271', 2006: '10.2904632770692'}, 'Sub-Saharan Africa (developing only)': {}, 'Armenia': {2008: '8.91422292424971', 2006: '8.76224094739239', 2007: '8.82470460642731'}, 'Small states': {}, 'Timor-Leste': {}, 'Dominican Republic': {2001: '8.90218687872764', 2002: '7.92127236580517', 2003: '7.67328739359546', 2004: '9.04134576408593'}, 'Sub-Saharan Africa excluding South Africa': {}, 'Low income': {}, 'Ukraine': {2006: '5.27322933824242', 2007: '5.26825958416129', 2008: '5.2697859149472', 2009: '5.26213780405078', 2010: '5.26086219012771', 2011: '5.25665560427315', 2012: '5.24493304598397'}, 'Ghana': {2010: '0.189873417721519', 2005: '0.0728476821192053', 2006: '0.117647058823529', 2007: '0.0714285714285714'}, 'Tonga': {}, 'Finland': {2001: '2.88028802880288', 2002: '2.86225402504472', 2003: '2.84951024042743', 2004: '2.84065690190857', 2005: '2.81442392260334', 2010: '0.558707987778263'}, 'Latin America & Caribbean (developing only)': {}, 'High income': {}, 'Libya': {}, 'Korea, Rep.': {2002: '54.872329338197', 2003: '53.4174553101998', 2004: '52.879027997887', 2005: '52.0999468367889', 2006: '51.3993541442411', 2007: '51.6304347826087'}, 'Cayman Islands': {}, 'Central African Republic': {}, 'Europe & Central Asia (all income levels)': {}, 'Mauritius': {2002: '21', 2003: '22.2222222222222', 2004: '21.4285714285714', 2005: '21.875', 2006: '22.3404255319149', 2007: '22.8260869565217', 2008: '23.0769230769231', 2009: '23.0769230769231', 2010: '21.978021978022', 2011: '22.4719101123595', 2012: '21.8390804597701'}, 'Liechtenstein': {}, 'Belarus': {2001: '1.25985977212971', 2002: '1.27423822714681', 2003: '1.26864010683285', 2004: '1.27274757173161', 2005: '1.27388535031847', 2006: '1.23911587407904', 2007: '1.24495289367429', 2008: '0.594370303913872', 2009: '0.526492662708637', 2010: '0.337154416722859', 2011: '0.338028169014085', 2012: '0.34106412005457'}, 'Mali': {}, 'Micronesia, Fed. Sts.': {}, 'Korea, Dem. Rep.': {}, 'Sub-Saharan Africa excluding South Africa and Nigeria': {}, 'Bulgaria': {2010: '1.78147268408551', 2003: '1.48328952309425', 2005: '1.02564102564103', 2007: '1.42689601250977'}, 'North America': {}, 'Romania': {2001: '2.2097580754156', 2002: '3.29329194223242', 2003: '3.84459459459459', 2004: '2.31422505307856', 2005: '0.324400564174894', 2006: '0.687370895362918', 2007: '2.34996331621423', 2008: '1.8849933988558', 2009: '2.17311504294839', 2010: '0.58844306301215', 2011: '0.739522242883708', 2012: '1.20803903007355'}, 'Angola': {}, 'Central Europe and the Baltics': {}, 'Egypt, Arab Rep.': {}, 'Trinidad and Tobago': {2004: '12.7272727272727'}, 'St. Vincent and the Grenadines': {}, 'Cyprus': {2001: '25', 2002: '25', 2003: '22.9299363057325', 2004: '21.7948717948718', 2005: '20.9580838323353', 2006: '21.0191082802548', 2007: '20.2445652173913', 2008: '21.1072664359862', 2009: '22.4137931034483', 2010: '21.9298245614035'}, 'Caribbean small states': {}, 'Brunei Darussalam': {2002: '0.909090909090909', 2003: '0.909090909090909', 2004: '0.909090909090909', 2005: '0.909090909090909', 2006: '0', 2007: '0.87719298245614'}, 'Qatar': {}, 'Middle income': {}, 'Austria': {2003: '1.00710900473934', 2005: '1.22586576769844', 2007: '1.35802469135802'}, 'High income: OECD': {}, 'Mozambique': {}, 'Uganda': {}, 'Kyrgyz Republic': {2001: '9.53043801039347', 2002: '9.53043801039347', 2003: '9.47416974169742', 2004: '9.49860724233983', 2005: '9.31596091205212', 2006: '9.30845859231579', 2007: '9.31342393229312', 2008: '9.30531732418525', 2009: '9.39504393772428', 2010: '9.40453641666431', 2011: '9.42263279445728', 2012: '9.43982325115897'}, 'Hungary': {2003: '2.54049445865303', 2004: '2.0450204638472', 2005: '1.28091420774348', 2006: '1.34136684455156', 2007: '2.08179783020493', 2008: '1.38238341968912', 2009: '1.84610063980633', 2010: '0.840351862249673', 2011: '1.78377365561177', 2012: '2.23304608467591'}, 'Niger': {2009: '0.236261477319446', 2010: '0.196907404869581', 2011: '0.218240372755927'}, 'United States': {}, 'Brazil': {2007: '1.64304770224169'}, 'World': {}, 'Middle East & North Africa (all income levels)': {}, 'Guinea': {}, 'Panama': {}, 'Costa Rica': {2005: '1.44289693593315', 2006: '1.51246537396122', 2007: '1.55555555555556', 2008: '1.51111111111111', 2009: '1.47567567567568', 2010: '1.49468085106383'}, 'Luxembourg': {}, 'Andorra': {}, 'Chad': {}, 'Euro area': {}, 'Ireland': {}, 'Pakistan': {2001: '65.6111929307806', 2002: '65.969930326366', 2003: '66.9482188762394', 2004: '69.4043655197928', 2005: '70.140428677014', 2006: '70.0989373396849', 2007: '71.0565476190476', 2008: '72.8207080319756', 2009: '73.502653525398', 2010: '75.9848484848485', 2011: '70.1694915254237'}, 'Palau': {}, 'Faeroe Islands': {}, 'Lower middle income': {}, 'Ecuador': {2002: '8.58477970627503', 2003: '9.26896551724138', 2004: '9.52570745316859', 2005: '10.0266666666667', 2006: '10.2229983879635', 2007: '10.7528332433891', 2008: '10.1813297515111', 2009: '12.6353790613718', 2012: '12.6283818886624'}, 'Czech Republic': {2003: '0.395877254626376', 2005: '0.39906103286385', 2007: '0.470698987997176', 2008: '0.235626767200754', 2009: '0.259495163953763', 2010: '0.448748228625413'}, 'Australia': {2001: '0.549923195084485', 2002: '0.569351230425056', 2003: '0.541069397042093', 2004: '0.545772647747154', 2005: '0.540268539298078', 2006: '0.585388285336552', 2007: '0.451993070849855', 2008: '0.443578535687583', 2009: '0.430531820482166', 2010: '0.461889708465051', 2011: '0.479163117084228', 2012: '0.528023991673942'}, 'Algeria': {2003: '1.80926534304623', 2004: '1.92733017377567', 2005: '2.00189269855136', 2006: '2.0276341031058', 2007: '2.19383302627751', 2008: '2.06976687888838'}, 'East Asia and the Pacific (IFC classification)': {}, 'El Salvador': {2003: '1.83752417794971', 2004: '1.75155279503106', 2005: '1.92332268370607', 2006: '2.20488466757123', 2007: '2.14095744680851', 2012: '1.25717932354818'}, 'Tuvalu': {}, 'St. Kitts and Nevis': {2005: '0.8', 2006: '7.98403193612774', 2007: '7.85854616895874', 2008: '7.84313725490196', 2009: '7.27272727272727', 2010: '10.5263157894737', 2011: '13.3333333333333', 2012: '13.3333333333333'}, 'Marshall Islands': {}, 'Chile': {2007: '5.63485002541942'}, 'Puerto Rico': {2002: '7.65765765765766', 2003: '7.90697674418605', 2012: '10.6707317073171', 2007: '8.57142857142857'}, 'Belgium': {2003: '0.136298421807747', 2005: '0.245487364620939', 2007: '0.416058394160584'}, 'Europe and Central Asia (IFC classification)': {}, 'Haiti': {2009: '5.39989868231338'}, 'Belize': {}, 'Fragile and conflict affected situations': {}, 'Sierra Leone': {}, 'Georgia': {2008: '4.00269488368406', 2006: '3.94337316140226', 2007: '4.15578247447162'}, 'East Asia & Pacific (developing only)': {}, 'Denmark': {2001: '7.62331838565022', 2002: '7.65478424015009', 2003: '7.67494356659142', 2004: '7.70975056689342', 2005: '9.67861100849649', 2006: '9.66789667896679', 2007: '9.5381149079985', 2008: '9.52023988005997', 2009: '9.64312832194381', 2010: '12.1477532368621'}, 'Philippines': {2006: '8.39130434782609', 2007: '8.32618025751073', 2008: '9.22881355932203', 2009: '9.51464435146444', 2010: '9.18333333333333', 2011: '9.38842975206612'}, 'Moldova': {2001: '11.0673493501378', 2002: '9.00552486187845', 2003: '9.02294303797468', 2004: '9.04440919904837', 2005: '9.12765106042417', 2006: '9.1864679822795', 2007: '9.05432595573441', 2008: '9.18984280532043', 2009: '9.22330097087379', 2010: '9.24949290060852'}, 'Macedonia, FYR': {2007: '7.39776951672862'}, 'Morocco': {2004: '4.29746013781166', 2005: '4.3049118009937', 2006: '3.87998397114807', 2007: '4.08611481975968', 2008: '4.39278209532704', 2009: '4.5679374454214', 2010: '4.54810709510042', 2011: '4.6057308379673'}, 'Croatia': {2003: '0.752508361204013', 2004: '1.02040816326531', 2005: '1.32122213047069', 2006: '0.32520325203252', 2007: '0.382695507487521', 2009: '0.384733764235149', 2010: '1.08711950817214'}, 'French Polynesia': {}, 'Guinea-Bissau': {}, 'Kiribati': {}, 'Switzerland': {2010: '2.37610764686577'}, 'Grenada': {2008: '2'}, 'Middle East and North Africa (IFC classification)': {}, 'Yemen, Rep.': {2002: '2.88298951640176', 2003: '1.9961693977442', 2004: '2.86539032983826', 2005: '3.04808060196404', 2006: '3.2674482583485'}, 'Isle of Man': {}, 'Portugal': {2010: '12.6733750339951', 2005: '11.8817063595917', 2007: '11.5310873733224'}, 'Estonia': {}, 'Kosovo': {}, 'Sweden': {2010: '2.04213938411669'}, 'Mexico': {2003: '1.9444976076555', 2004: '1.99903938520653', 2005: '5.2048309178744', 2006: '5.26829268292683', 2007: '5.18748595930886', 2008: '5.45470447610348', 2009: '5.47100638899964', 2010: '5.74275116039696', 2011: '6.27047670744237', 2012: '5.36151070708964'}, 'Africa': {}, 'South Africa': {2010: '1.58735073433033', 2011: '1.66123643306286'}, 'Uzbekistan': {}, 'Tunisia': {2001: '3.64248868301927', 2002: '3.67714841749462', 2003: '3.556827473426', 2004: '3.62156663275687', 2005: '3.62377850162866', 2006: '3.8037935957577', 2007: '3.88577256501785', 2008: '4.00769152919745', 2009: '4.12708141791807', 2010: '3.89519824666268', 2011: '3.76290706910246'}, 'Djibouti': {}, 'West Bank and Gaza': {2001: '4.41734417344173', 2002: '4.37837837837838', 2003: '4.19618528610354', 2004: '4.30517711171662', 2005: '4.23309510720176', 2006: '4.61280402571988', 2007: '5.00707213578501', 2008: '4.85436893203883'}, 'Antigua and Barbuda': {}, 'Spain': {2001: '12.6253387533875', 2002: '12.8488391855604', 2003: '12.2697492539361', 2004: '11.7436620687283', 2005: '11.7096420244137', 2006: '11.6031174640897', 2007: '11.8483073846593', 2008: '11.9387392509417', 2009: '11.4658562745799', 2010: '12.0021782537666'}, 'Colombia': {}, 'Burundi': {}, 'Least developed countries: UN classification': {}, 'Fiji': {}, 'Barbados': {}, 'Seychelles': {}, 'Madagascar': {2001: '2.17907597385109', 2002: '2.17907597385109', 2003: '2.17907597385109', 2004: '2.17907597385109', 2005: '2.17641161078913', 2006: '2.17641161078913', 2007: '2.17641161078913', 2008: '2.16571359046113', 2009: '2.15001811813021'}, 'Italy': {2010: '16.8891557516687', 2003: '18.3336687462266', 2005: '17.7320846905537', 2007: '18.8250247140234'}, 'Curacao': {}, 'Bhutan': {2003: '7.07635009310987', 2004: '6.50684931506849', 2005: '6.40809443507589', 2006: '6.58578856152513', 2007: '6.74955595026643'}, 'Sudan': {2002: '1.03458156755697', 2003: '1.13431948264328', 2004: '1.2334847617419', 2005: '1.18991273480254', 2006: '1.07311121401219', 2007: '0.857153314057754', 2008: '1.15071178802909', 2009: '1.04790089368983', 2011: '1.36365142051624'}, 'Latin America and the Caribbean': {}, 'Nepal': {2001: '27.4114057732927', 2002: '27.4242779995304', 2003: '27.4242779995304', 2004: '27.4242779995304', 2005: '27.4242779995304', 2006: '27.4242779995304', 2007: '27.4242779995304', 2008: '27.4242779995304'}, 'Singapore': {}, 'Malta': {2003: '20.1923076923077', 2005: '25.8064516129032', 2007: '30.1075268817204', 2008: '30.1075268817204', 2009: '30.1075268817204', 2010: '33.9805825242718', 2011: '33.9805825242718', 2012: '33.9805825242718'}, 'Netherlands': {2007: '10.5516088591726'}, 'Macao SAR, China': {}, 'Andean Region': {}, 'Middle East & North Africa (developing only)': {}, 'Turks and Caicos Islands': {}, 'St. Martin (French part)': {}, 'Iran, Islamic Rep.': {2001: '12.5675696849098', 2002: '12.7381175441884', 2003: '12.9106045281257', 2004: '13.0819092516205', 2005: '17.9987823056413', 2006: '18.2124049151551', 2007: '18.4219832338319', 2008: '19.020996397068'}, 'Israel': {2009: '28.3773440489858', 2010: '31.7742558948589', 2001: '31.5508021390374', 2002: '30.9058614564831', 2007: '30.0135109052307'}, 'Indonesia': {2002: '16.5290842772125', 2003: '11.7495850706392', 2004: '14.8669010547464', 2005: '16.0134833285952'}, 'Malaysia': {}, 'Iceland': {}, 'Zambia': {}, 'Sub-Saharan Africa (all income levels)': {}, 'Senegal': {2002: '0.636363636363636', 2003: '0.621976503109883', 2004: '0.686734577085956', 2005: '0.759120779515069', 2006: '0.729335494327391'}, 'Papua New Guinea': {}, 'Malawi': {2008: '0.53953488372093', 2005: '0.580270793036751', 2006: '0.530805687203791', 2007: '0.743718592964824'}, 'Suriname': {}, 'Zimbabwe': {}, 'Germany': {2009: '2.20893047494966'}, 'Oman': {2009: '4.17136414881623'}, 'Kazakhstan': {}, 'Poland': {2005: '0.446372438073683', 2007: '0.445076342956049'}, 'Sint Maarten (Dutch part)': {}, 'Eritrea': {}, 'Virgin Islands (U.S.)': {}, 'Iraq': {}, 'New Caledonia': {}, 'Paraguay': {}, 'Not classified': {}, 'Latvia': {2010: '0.0664819944598338', 2007: '0.0337139749864057'}, 'South Sudan': {}, 'Guyana': {}, 'Honduras': {}, 'Myanmar': {2003: '22.8373702422145', 2004: '23.1997834325934', 2005: '23.404066412146', 2006: '24.8081400362163', 2007: '24.7580106809079'}, 'Equatorial Guinea': {}, 'Central America': {}, 'Nicaragua': {}, 'Congo, Dem. Rep.': {}, 'Serbia': {2006: '0.513225424397947', 2007: '0.514545814367702', 2008: '0.514240506329114', 2009: '0.613254203758655', 2010: '0.495049504950495', 2011: '0.671803991306066', 2012: '1.04888185236493'}, 'Botswana': {2003: '0.000542719801519615', 2004: '0.00116162007279486', 2005: '0.00773948880676431', 2006: '0.00116265550517382', 2007: '0.000814458578963698', 2008: '0.00579575750550597', 2009: '0.00254649278493711', 2010: '0.00290011987162136', 2012: '0.00424923706879901'}, 'United Kingdom': {}, 'Gambia, The': {}, 'High income: nonOECD': {}, 'Greece': {2003: '28.6238291740355', 2005: '33.4928229665072', 2006: '17.7224371373308', 2007: '27.3739204606035', 2008: '17.2679879938268', 2009: '16.9040882037272'}, 'Sri Lanka': {}, 'Lebanon': {2003: '18.9792663476874', 2004: '19.7399342002193', 2005: '20.0612557427259', 2006: '20.9131075110457', 2007: '20.2333481022006'}, 'Comoros': {}, 'Heavily indebted poor countries (HIPC)': {}}, 'LastFirst_IA': [2001, 2012]}
            self.country_list = ['Afghanistan', 'Africa', 'Albania', 'Algeria', 'American Samoa', 'Andean Region', 'Andorra', 'Angola', 'Antigua and Barbuda', 'Arab World', 'Argentina', 'Armenia', 'Aruba', 'Australia', 'Austria', 'Azerbaijan', 'Bahamas, The', 'Bahrain', 'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bermuda', 'Bhutan', 'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei Darussalam', 'Bulgaria', 'Burkina Faso', 'Burundi', 'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada', 'Caribbean small states', 'Cayman Islands', 'Central African Republic', 'Central America', 'Central Europe and the Baltics', 'Chad', 'Channel Islands', 'Chile', 'China', 'Colombia', 'Comoros', 'Congo, Dem. Rep.', 'Congo, Rep.', 'Costa Rica', "Cote d'Ivoire", 'Croatia', 'Cuba', 'Curacao', 'Cyprus', 'Czech Republic', 'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic', 'East Asia & Pacific (all income levels)', 'East Asia & Pacific (developing only)', 'East Asia and the Pacific (IFC classification)', 'Ecuador', 'Egypt, Arab Rep.', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia', 'Ethiopia', 'Euro area', 'Europe & Central Asia (all income levels)', 'Europe & Central Asia (developing only)', 'Europe and Central Asia (IFC classification)', 'European Union', 'Faeroe Islands', 'Fiji', 'Finland', 'Fragile and conflict affected situations', 'France', 'French Polynesia', 'Gabon', 'Gambia, The', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Greenland', 'Grenada', 'Guam', 'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti', 'Heavily indebted poor countries (HIPC)', 'High income', 'High income: OECD', 'High income: nonOECD', 'Honduras', 'Hong Kong SAR, China', 'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran, Islamic Rep.', 'Iraq', 'Ireland', 'Isle of Man', 'Israel', 'Italy', 'Jamaica', 'Japan', 'Jordan', 'Kazakhstan', 'Kenya', 'Kiribati', 'Korea, Dem. Rep.', 'Korea, Rep.', 'Kosovo', 'Kuwait', 'Kyrgyz Republic', 'Lao PDR', 'Latin America & Caribbean (all income levels)', 'Latin America & Caribbean (developing only)', 'Latin America and the Caribbean', 'Latin America and the Caribbean (IFC classification)', 'Latvia', 'Least developed countries: UN classification', 'Lebanon', 'Lesotho', 'Liberia', 'Libya', 'Liechtenstein', 'Lithuania', 'Low & middle income', 'Low income', 'Lower middle income', 'Luxembourg', 'Macao SAR, China', 'Macedonia, FYR', 'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania', 'Mauritius', 'Mexico', 'Micronesia, Fed. Sts.', 'Middle East & North Africa (all income levels)', 'Middle East & North Africa (developing only)', 'Middle East (developing only)', 'Middle East and North Africa (IFC classification)', 'Middle income', 'Moldova', 'Monaco', 'Mongolia', 'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 'Nepal', 'Netherlands', 'New Caledonia', 'New Zealand', 'Nicaragua', 'Niger', 'Nigeria', 'North Africa', 'North America', 'Northern Mariana Islands', 'Norway', 'Not classified', 'OECD members', 'Oman', 'Other small states', 'Pacific island small states', 'Pakistan', 'Palau', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal', 'Puerto Rico', 'Qatar', 'Romania', 'Russian Federation', 'Rwanda', 'Samoa', 'San Marino', 'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore', 'Sint Maarten (Dutch part)', 'Slovak Republic', 'Slovenia', 'Small states', 'Solomon Islands', 'Somalia', 'South Africa', 'South Asia', 'South Asia (IFC classification)', 'South Sudan', 'Southern Cone', 'Spain', 'Sri Lanka', 'St. Kitts and Nevis', 'St. Lucia', 'St. Martin (French part)', 'St. Vincent and the Grenadines', 'Sub-Saharan Africa (IFC classification)', 'Sub-Saharan Africa (all income levels)', 'Sub-Saharan Africa (developing only)', 'Sub-Saharan Africa excluding South Africa', 'Sub-Saharan Africa excluding South Africa and Nigeria', 'Sudan', 'Suriname', 'Swaziland', 'Sweden', 'Switzerland', 'Syrian Arab Republic', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo', 'Tonga', 'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Turks and Caicos Islands', 'Tuvalu', 'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States', 'Upper middle income', 'Uruguay', 'Uzbekistan', 'Vanuatu', 'Venezuela, RB', 'Vietnam', 'Virgin Islands (U.S.)', 'West Bank and Gaza', 'World', 'Yemen, Rep.', 'Zambia', 'Zimbabwe']

            # Set year range.
            rng = range(int(self.all_indicators_data["LastFirst_"+sh_id][0]),
                        int(self.all_indicators_data["LastFirst_"+sh_id][1]+1))

            for region in self.country_list:
                self.data_view_now.append([region])
                for year in rng:
                    if year in self.all_indicators_data[sh_id][region]:
                        self.data_view_now[-1].append(self.all_indicators_data[sh_id][region][year])
                    else:
                        self.data_view_now[-1].append("")

            self.data_table.cols = len(rng)+1

            self.data_queue = list(self.data_view_now)

            # Schedule table building.
            Clock.schedule_interval(self.build_data_table, 0)

    def build_data_table(self, dt):
        if self.data_queue:
            self.data_table_slider.do_scroll = (False, False)
            # Set chunks number for each schedule.
            chunks = 25
            queue = self.data_queue[:chunks]
            self.data_queue = self.data_queue[chunks:]

            for country_row in queue:
                for i, date_col in enumerate(country_row, start=1):
                    if date_col == country_row[0]:
                        self.data_table.add_widget(Factory.DataViewTitle(text=str(date_col)))

                    else:
                        try:
                            # Format numbers to be more friendly.
                            tup = str("%.5G" % float(date_col)).partition('E')
                            val = (('[size=12]E'.join((tup[0], tup[-1]))+"[/size]")
                                   .replace("[size=12]E[/size]", ""))\
                                .replace(".", ",")

                        except ValueError:
                            val = date_col

                        finally:
                            if i % 2:
                                self.data_table.add_widget(Factory.DataViewEven(text=str(val)))
                            else:
                                self.data_table.add_widget(Factory.DataViewOdd(text=str(val)))

        else:
            self.data_table_slider.do_scroll = (True, True)
            self.must_draw_data = False
            Clock.unschedule(self.build_data_table)
            print "never called again"


class MapDesigner(Screen):

    pass


class CIMMenu(BoxLayout):

    pass


class MainWindow(BoxLayout):

    # Prepare kivy properties that show if a process or a popup are currently running. Set to False on app's init.
    processing = BooleanProperty(False)
    popup_active = BooleanProperty(False)

    # This method can generate new threads, so that main thread (GUI) won't get frozen.
    @staticmethod
    def threadonator(*arg):
        threading.Thread(target=arg[0], args=(arg,)).start()

    @mainthread
    def popuper(self, message):
        Popup(title='Warning:', content=Label(
            text=message,
            font_size=15,
            halign="center",
            italic=True
        ), size_hint=(None, None), size=(350, 180)).open()

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
                print "def core_build(self, *arg):", type(e), e.__doc__, e.message

        self.processing = False

    # This method checks for last core's index database update.
    def check(self, *arg):
        # For as long as the popup window is shown.
        while self.popup_active and (not CIMgui.app_closed):

            # If there is any process running, wait until finish.
            while self.processing:
                self.coredb_state.text = "Updating indicator database!\nDuration depends on your Internet speed.."
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
                print "def check(self, *arg):", type(e), e.__doc__, e.message

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
