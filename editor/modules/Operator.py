#!/usr/bin/python
# -*- coding: utf8 -*-
# WordForge Translation Editor
# Copyright 2006 WordForge Foundation
#
# Version 0.1 (31 August 2006)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Developed by:
#       Hok Kakada (hokkakada@khmeros.info)
#       Keo Sophon (keosophon@khmeros.info)
#       San Titvirak (titvirak@khmeros.info)
#       Seth Chanratha (sethchanratha@khmeros.info)
#     
from PyQt4 import QtCore, QtGui
from translate.storage import factory
from translate.storage import po
from translate.storage import poheader
from translate.storage import xliff
import modules.World as World
from modules.Status import Status

class Operator(QtCore.QObject):
    """
    Operates on the internal datastructure.
    The class loads and saves files and navigates in the data.
    Provides means for searching and filtering.
    
    @signal currentStatus(string): emitted with the new status message
    @signal newUnits(store.units): emitted with the new units
    @signal currentUnit(unit): emitted with the current unit
    @signal updateUnit(): emitted when the views should update the unit´s data
    @signal toggleFirstLastUnit(atFirst, atLast): emitted to allow dis/enable of actions
    @signal filterChanged(filter, lenFilter): emitted when the filter was changed
    @signal savedAlready(False): emitted when a file was saved
    """
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.store = None
        self._modified = False
        self.currentUnitIndex = 0
        
    def getUnits(self, fileName):
        """reading a file into the internal datastructure.
        @param fileName: the file to open"""
        self.fileName = fileName
        self.store = factory.getobject(fileName)
        self._modified = False

        # filter flags
        self.filter = World.filterAll
        
        # get status for units
        self.status = Status(self.store.units)
        self.emitStatus()

        self.filteredList = []
        start = 0
        if (self.store.units[0].isheader()):
            start = 1
        self.currentUnitIndex = start
        i = start
        j = 0
        for unit in self.store.units[start:]:
            unit.x_editor_index = i
            unit.x_editor_filterIndex = j
            self.filteredList.append(unit)
            i += 1
            j += 1
        self.emit(QtCore.SIGNAL("newUnits"), self.store.units[start:])
        self.emitFiltered(self.filter)

    def emitStatus(self):
        self.emit(QtCore.SIGNAL("currentStatus"), self.status.statusString())        
    
    def emitUnit(self, unit):
        if hasattr(unit, "x_editor_index"):
            self.currentUnitIndex = unit.x_editor_index
            self.searchPointer = self.currentUnitIndex
            self.emit(QtCore.SIGNAL("currentUnit"), unit)
    
    def filterFuzzy(self, checked):
        """add/remove fuzzy to filter, and send filter signal.
        @param checked: True or False when Fuzzy checkbox is checked or unchecked.
        """
        filter = self.filter
        if (checked):
            filter |= World.fuzzy
        else:
            filter &= ~World.fuzzy
        self.emitFiltered(filter)
    
    def filterTranslated(self, checked):
        """add/remove translated to filter, and send filter signal.
        @param checked: True or False when Translated checkbox is checked or unchecked."""
        filter = self.filter
        if (checked):
            filter |= World.translated
        else:
            filter &= ~World.translated
        self.emitFiltered(filter)
        
    def filterUntranslated(self, checked):
        """add/remove untranslated to filter, and send filter signal.
        @param checked: True or False when Untranslated checkbox is checked or unchecked.
        """
        filter = self.filter
        if (checked):
            filter |= World.untranslated
        else:
            filter &= ~World.untranslated
        self.emitFiltered(filter)

    def emitFiltered(self, filter):
        """send filtered list signal according to filter."""
        self.emitUpdateUnit()
        if (filter != self.filter):
            # build a new filteredList when only filter has changed.
            self.filter = filter
            self.filteredList = []
            start = 0
            if (self.store.units[0].isheader()):
                start = 1
            i = 0
            for unit in self.store.units[start:]:
                # add unit to filteredList if it is in the filter
                if (self.filter & unit.x_editor_state):
                    unit.x_editor_filterIndex = i
                    self.filteredList.append(unit)
                    i += 1
                else:
                    unit.x_editor_filterIndex = None
        self.emit(QtCore.SIGNAL("filterChanged"), filter, len(self.filteredList))
        unit = self.store.units[self.currentUnitIndex]
        if (len(self.filteredList) > 0):
            self.emitUnit(unit)
        
    def filterUnit(self, unit):
        if (not self.filter & unit.x_editor_state):
            self.filteredList.remove(unit.x_editor_index)
    
    def emitUpdateUnit(self):
        """emit "updateUnit" signal."""
        if (not self.store):
            return
        self.emit(QtCore.SIGNAL("updateUnit"))

    def headerData(self):
        """@return Header comment and Header dictonary"""
        if (not isinstance(self.store, poheader.poheader)):
            return (None, None)

        header = self.store.header() 
        if header:
            headerDic = self.store.parseheader()
            return (header.getnotes("translator"), headerDic)
        else:
            return ("", {})

    def makeNewHeader(self, headerDic):
          """receive headerDic as dictionary, and return header as string"""
          #TODO: move to world
          self.store.x_generator = World.settingOrg + ' ' + World.settingApp + ' ' + World.settingVer
          if isinstance(self.store, poheader.poheader):
              self.store.updateheader(add=True, **headerDic)
              return self.store.makeheaderdict(**headerDic)
          else: return {}
          
    def updateNewHeader(self, othercomments, headerDic):
        """will update header"""
        #TODO: need to make it work with xliff file
        if (not isinstance(self.store, poheader.poheader)):
            return {}
        
        header = self.store.header()
        if (header):
            header.removenotes()
            header.target = ""
            header.addnote(str(othercomments))
            self.store.updateheader(add=True, **headerDic)
            
    def saveStoreToFile(self, fileName):
        """
        save the temporary store into a file.
        @param fileName: String type
        """
        self.emitUpdateUnit()
        if (World.settings.value("headerAuto", QtCore.QVariant(True)).toBool()):
            self.emit(QtCore.SIGNAL("headerAuto"))
        self.store.savefile(fileName)
        self._modified = False
        self.emit(QtCore.SIGNAL("savedAlready"), False) 

    def modified(self):
        """
        @return bool: True or False if current unit is modified or not modified.
        """
        self.emitUpdateUnit()
        return self._modified
    
    def setComment(self, comment):
        """set the comment to the current unit.
        @param comment: QString type
        """
        unit = self.store.units[self.currentUnitIndex]
        unit.removenotes()
        unit.addnote(unicode(comment))
        self._modified = True
    
    def setTarget(self, target):
        """set the target which is QString type to the current unit.
        @param target: QString type"""
        unit = self.store.units[self.currentUnitIndex]
        translatedState = unit.istranslated()
        # update target for current unit
        unit.target = unicode(target)
        if (unit.target):
            self.status.markTranslated(unit, True)
        else:
            self.status.markTranslated(unit, False)
        self._modified = True
        self.emitStatus()

    def setUnitFromIndex(self, index):
        """build a unit from index and call emitUnit.
        @param index: index inside the store.units."""
        if (index < len(self.store.units)):
            self.emitUpdateUnit()
            unit = self.store.units[index]
            self.emitUnit(unit)
        
    def setUnitFromPosition(self, position):
        if (position < len(self.filteredList)):
            self.emitUpdateUnit()
            unit = self.filteredList[position]
            self.emitUnit(unit)
        
    def toggleFuzzy(self):
        """toggle fuzzy state for current unit."""
        self.emitUpdateUnit()
        unit = self.store.units[self.currentUnitIndex]
        if (unit.x_editor_state & World.fuzzy):
            self.status.markFuzzy(unit, False)
        elif (unit.x_editor_state & World.translated):
            self.status.markFuzzy(unit, True)
        else:
            return
        self._modified = True
        self.emitUnit(unit)
        self.emitStatus()
    
    def initSearch(self, searchString, searchableText, matchCase):
        """initilize the needed variables for searching.
        @param searchString: string to search for.
        @param searchableText: text fields to search through.
        @param matchCase: bool indicates case sensitive condition."""
        self.currentTextField = 0
        self.foundPosition = -1
        self.searchString = str(searchString)
        self.searchableText = searchableText
        self.matchCase = matchCase
        if (not matchCase):
            self.searchString = self.searchString.lower()

    def searchNext(self):
        """search forward through the text fields."""
        while (self.searchPointer < len(self.filteredList)):
            unitString = self._getUnitString()
            self.foundPosition = unitString.find(self.searchString, self.foundPosition + 1)
            # found in current textField
            if (self.foundPosition >= 0):
                self._searchFound()
                return True
                #break
            else:
                # next textField
                if (self.currentTextField < len(self.searchableText) - 1):
                    self.currentTextField += 1
                    continue
                # next unit
                else:
                    self.currentTextField = 0
                    self.searchPointer += 1
        else:
            # exhausted
            self._searchNotFound()
            self.emit(QtCore.SIGNAL("generalInfo"), "Search has reached end of document")
            self.searchPointer = len(self.filteredList) - 1

    def searchPrevious(self):
        """search backward through the text fields."""
        while (self.searchPointer >= 0):
            unitString = self._getUnitString()
            self.foundPosition = unitString.rfind(self.searchString, 0, self.foundPosition)
            # found in current textField
            if (self.foundPosition >= 0):
                self._searchFound()
                break
            else:
                # previous textField
                if (self.currentTextField > 0):
                    self.currentTextField -= 1
                    unitString = self._getUnitString()
                    self.foundPosition = len(unitString)
                    continue
                # previous unit
                else:
                    self.currentTextField = len(self.searchableText) - 1
                    self.searchPointer -= 1
                unitString = self._getUnitString()
                self.foundPosition = len(unitString)
        else:
            # exhausted
            self._searchNotFound()
            self.emit(QtCore.SIGNAL("generalInfo"), "Search has reached start of document")
    
    def replace(self, replacedText):
        """replace the found text in the text fields.
        @param replacedText: text to replace."""
        self.foundPosition = -1
        if self.searchNext():
            textField = self.searchableText[self.currentTextField]
            self.emit(QtCore.SIGNAL("replaceText"), \
                textField, \
                self.foundPosition, \
                len(unicode(self.searchString)), \
                replacedText)

    def replaceAll(self, replacedText):
        """replace the found text in the text fields through out the units.
        @param replacedText: text to replace."""
        self.searchPointer = 0
        self.foundPosition = -1
        for i in self.filteredList:
            if self.searchNext():
                textField = self.searchableText[self.currentTextField]
                self.emit(QtCore.SIGNAL("replaceText"), \
                    textField, \
                    self.foundPosition, \
                    len(unicode(self.searchString)), \
                    replacedText)
        
    def _getUnitString(self):
        """@return: the string of current text field."""
        textField = self.searchableText[self.currentTextField]
        if (textField == World.source):
            unitString = self.filteredList[self.searchPointer].source
        elif (textField == World.target):
            unitString = self.filteredList[self.searchPointer].target
        elif (textField == World.comment):
            unitString = self.filteredList[self.searchPointer].getnotes()
        else:
            unitString = ""
        if (not self.matchCase):
            unitString = unitString.lower()
        return unitString

    def _searchFound(self):
        """emit searchResult signal with text field, position, and length."""
        self.setUnitFromPosition(self.searchPointer)
        textField = self.searchableText[self.currentTextField]
        self.emit(QtCore.SIGNAL("searchResult"), textField, self.foundPosition, len(unicode(self.searchString)))
        self.emit(QtCore.SIGNAL("generalInfo"), "")

    def _searchNotFound(self):
        """emit searchResult signal with text field, position, and length."""
        textField = self.searchableText[self.currentTextField]
        self.emit(QtCore.SIGNAL("searchResult"), textField, None, None)
