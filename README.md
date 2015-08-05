CIM
=======================
<img align="right" height="218" src="http://gouz.webfactional.com/Gouz_Sources/CIM_GIT_LOGO.png"/>
Composite Index Modeler (CIM) provides a basic set of tools for the creation and visualization of an Index. You can calculate and view an already formed Index by combining available Indicators, or even create your own Model based on your custom mathematical formula.

At the moment App is using [WorldBank's World Development Indicators (WDI)](http://data.worldbank.org/data-catalog/world-development-indicators) database; however, additional databases could be included in the future too.
</br></br>
___
<a href="http://kivy.org/" target="_blank"><img align="left" width="64" src="http://kivy.org/logos/kivy-logo-black-64.png"/></a>
&nbsp;&nbsp;&nbsp;&nbsp;CIM has been developed using an Open source Python library - [kivy](http://kivy.org/) and can run
</br>&nbsp;&nbsp;&nbsp;&nbsp;on almost all operating systems (Linux, Windows, OS X, Android and iOS..).
</br>&nbsp;&nbsp;&nbsp;&nbsp;Running it from source code, requires Python 2.7 and kivy 1.9.

If you are on Windows and would like to avoid "playing"  with source code,
</br>you could just use this self-extracting portable version: [Download Ver. 1.0.1](http://gouz.webfactional.com/Gouz_Sources/CIM_Portable.exe)
___

</br>
Check CIM's quick preview here: [Youtube Link](http://youtu.be/DOX4SlNqN8Y)
</br>Or you could also follow guide below:

Menu:
=======================
*(Right Sidebar)*

**[Icons]** - CIM consists of 3 main components (Indicator Selection, Index Creation and Thematic Mapper).
                    You can navigate among them using each corresponding Icon.

**[Update DB]** - Download latest Indicator dictionary from WorldBank.
                             Updating can only be done right after Application is started and before Indicator Selection has been loaded.

**[?]** - Return back here.


Indicator Selection:
=====================================================
*(Choosing your Indicators)*

**[Topics List]** - Select a parent topic to view all its child Indicators.

**[Indicator List]** - Scroll and select an Indicator to read its description in the Indicator Panel at the bottom.

**[Open]** - Increase panel's height for a better description view and less scrolling.

**[ADD IND.]** - Add currently selected Indicator to "My Indicators" list.

**[My Indicators]** - All Indicators in that list will later (at Index Creation) become available both as data and as variables.

**[Search]** - Search for a specific keyword within Indicator's title.

<img width="730" src="http://gouz.webfactional.com/Gouz_Sources/Indicator_Selection.png"/>
.

Index Creation:
==============================================
*(Constructing your Index)*

**[Get Indicator Data]** - Download Indicator values for all available years and regions (and for each Indicator in "My Indicators" list).
                                             This procedure also generates a quick statistic preview and an ID pointing back to the Indicator.
                                             When everything is completed 3 new sections will become accessible (View Indicator Data, Series Selection and Index Algebra).

**[View Indicator Data]** - Build a sortable Region/Year Table containing all Data Values from the selected Indicator.
                                               Loading time depends on the number of available Regions*Years and also your CPU Clock Rate.
                                               (Future updates may offer better loading/response times and an anchored Region Bar, equivalent to current Year Bar.)

**[ID]** - Select one Indicator to build its Data Table.

**[Year Arrows]** - Sort entire table based on targeted year's values and sorting direction.

**[Series Selection]** - Choose those Regions and Years (at least 1 Region and 1 Year) for which later calculations (at Index Algebra) will be made.
                                       You can select/deselect them all at once. Unselected Years can be either blank or grey.
                                       Black suggests that at least one Indicator (among "My Indicators") contains data for that year
                                       Grey means that no Indicator contains data for that year.

<img width="730" src="http://gouz.webfactional.com/Gouz_Sources/Index_Creation.png"/>

**[Index Algebra]** - This section consists of 2 main modules. The Formula Screen and the Index Calculator.

**[Formula Screen]** - Like a regular calculator screen, this module will print all statements coming from Index Calculator below.
                                      User can interact with this screen (left click) placing the cursor above or next to an item.
                                      CIM provides also a live parenthesis checking system to notify whether any still remain open.

**[Index Calculator]**- This module is the formula builder. User has 3 tools at his disposal (Function Tools, Indicator Variable and Calculator Panel).
                        As soon as we execute the formula for the first time, a new component (Thematic Mapper) will become accessible in main Menu.

*A simple example:*
        We want to calculate our Custom Index (CI) for all selected Regions and Years (in Series Selection).
        Let's say that this **CI** is **Life Expectancy Index (LEI)**. Our formula should then be: (**IA[Region][Year]**-20)/(85-20)

*Most simplistic example:*
        To export indicator itself into a csv, we could just use that: **IA[Region][Year]**

<img width="730" src="http://gouz.webfactional.com/Gouz_Sources/Index_Creation_B.png"/>
.

Thematic Mapper:
=============================================
*(Visualizing Results)*

**[Year List]** - First thing you should do to view results, is to select a year.
                          This will load all calculated data of that year into a sortable Data Table (inside the right slider which initiates closed).

**[Slider]** - Besides Data Table, slider contains Legend module too.

**[Data Table]** - When creating a new thematic map, only current values of this table are going to be used.

**[Legend]** - This works not only as a Thematic Mapper but as a Legend too.
                       Pick 2 range colors, choose the number of equal Intervals, press Apply and that's it.
                       CIM will automatically generate both the Legend and the Thematic Map, based on your choices.
                       (Future updates may introduce more division methods and better drawing times.)

**[Borders, Labels]** - Turn On/Off those features.

**[Export Map]** - Press PNG to export map as a Raster file, or SVG to export map as a vector one.

<img width="730" src="http://gouz.webfactional.com/Gouz_Sources/Thematic_Mapper_A.png"/>
.

Support
=======

If you need any assistance, you can contact Dev at:

D. Xenakis | Email : gouzounakis@hotmail.com
