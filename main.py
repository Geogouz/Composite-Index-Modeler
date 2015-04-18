# -*- coding: utf-8 -*-
__author__ = 'Dimitris Xenakis'

from Core import core_tables

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout


class MainWindow(BoxLayout):
    pass


class CIMgui(App):
    def build(self):
        return MainWindow()

#must be called from main
if __name__ == "__main__":
    CIMgui().run()

#core_tables.core_build()