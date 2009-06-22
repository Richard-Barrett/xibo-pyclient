#!/usr/bin/python
# -*- coding: utf-8 -*-

from libavg import avg, anim
from SOAPpy import WSDL
from xml.dom import minidom
import time, Queue, ConfigParser, gettext
import os
import re
import time
import sys
from threading import Thread, Semaphore

version = "1.1.0"
schemaVersion = 2

#### Abstract Classes
class XiboLog:
    "Abstract Class - Interface for Loggers"
    level=0
    def __init__(self,level): abstract
    def log(self,level,category,message): abstract
    def stat(self,type, message, layoutID, scheduleID, mediaID): abstract

class XiboScheduler(Thread):
    "Abstract Class - Interface for Schedulers"
    def run(self): abstract
    def nextLayout(self): abstract
    def hasNext(self): abstract
#### Finish Abstract Classes

#### Log Classes
class XiboLogFile(XiboLog):
    "Xibo Logger - to file"
    def __init__(self,level):
        pass
        
    def log(self,level, category, message):
        pass
    
    def stat(self,type, message, layoutID, scheduleID, mediaID):
        pass

class XiboLogScreen(XiboLog):
    "Xibo Logger - to screen"
    def __init__(self,level):
        # Make sure level is sane
        if level == "" or int(level) < 0:
            level=0
        self.level = int(level)
        
        self.log(2,"info",_("XiboLogScreen logger started at level ") + str(level))
    
    def log(self, severity, category, message):
        if self.level >= severity:
            print "LOG: " + str(severity) + " " + category + " " + message
    
    def stat(self, type, message, layoutID, scheduleID, mediaID=""):
        print "STAT: " + type + " " + message + " " + str(layoutID) + " " + str(scheduleID) + " " + str(mediaID)

class XiboLogXmds(XiboLog):
    def log(self,level, category, message):
        pass
    
    def stat(self,type, message, layoutID, scheduleID, mediaID):
        pass
#### Finish Log Classes

#### Download Manager        
class XiboDownloadManager(Thread):
    def __init__(self,xmds):
        log.log(3,"info",_("New XiboDownloadManager instance created."))
        Thread.__init__(self)
    
    def run(self):
        log.log(2,"info",_("New XiboDownloadManager instance started."))

class XiboDownloadThread(Thread):
    def __init__(self):
        Thread.__init__(self)
#### Finish Download Manager
        
#### Webservice
class Xmds:
    def __init__(self):
        pass
#### Finish Webservice

#### Layout/Region Management
class XiboLayoutManager(Thread):
    def __init__(self,parent,player,layout,zindex=0,opacity=1.0,hold=False):
        log.log(3,"info",_("New XiboLayoutManager instance created."))
        self.p = player
        self.l = layout
	self.zindex = zindex
        self.parent = parent
	self.opacity = opacity
	self.regions = []
	self.layoutNodeName = None
	self.layoutNodeNameExt = "-" + str(self.p.nextUniqueId())
	self.layoutExpired = False
	self.isPlaying = False
	self.hold = hold
        Thread.__init__(self)
    
    def run(self):
	self.isPlaying = True
        log.log(2,"info",_("XiboLayoutManager instance running."))
	
	# Add a DIV to contain the whole layout (for transitioning whole layouts in to one another)
	# TODO: Take account of the zindex parameter for transitions. Should this layout sit on top or underneath?
	# Ensure that the layoutNodeName is unique on the player (incase we have to transition to ourself)
	self.layoutNodeName = 'L' + str(self.l.layoutID) + self.layoutNodeNameExt

	# Create the XML that will render the layoutNode.
	tmpXML = '<div id="' + self.layoutNodeName + '" width="' + str(self.l.sWidth) + '" height="' + str(self.l.sHeight) + '" x="' + str(self.l.offsetX) + '" y="' + str(self.l.offsetY) + '" opacity="' + str(self.opacity) + '" />'
	self.p.enqueue('add',(tmpXML,'screen'))

	# TODO: Fix background colour
	# Add a ColorNode and maybe ImageNode to the layout div to draw the background

	# This code will work with libavg > 0.8.x
	# tmpXML = '<colornode fillcolor="' + self.l.backgroundColour + '" id="bgColor' + self.layoutNodeNameExt + '" />'
	# self.p.enqueue('add',(tmpXML,self.layoutNodeName))

	if self.l.backgroundImage != None:
		tmpXML = '<image href="' + config.get('Main','libraryDir') + os.sep + str(self.l.backgroundImage) + '" width="' + str(self.l.sWidth) + '" height="' + str(self.l.sHeight) + '" id="bg' + self.layoutNodeNameExt + '" />'
		self.p.enqueue('add',(tmpXML,self.layoutNodeName))

	# Break layout in to regions
	# Spawn a region manager for each region and then start them all running
	# Log each region in an array for checking later.
	for cn in self.l.children():
		if cn.nodeType == cn.ELEMENT_NODE and cn.localName == "region":
			log.log(1,"info","Encountered region")
			# Create a new Region Manager Thread and kick it running.
			# Pass in cn since it contains the XML for the whole region
		        tmpRegion = XiboRegionManager(self, self.p, self.layoutNodeName, self.layoutNodeNameExt, cn)
		        log.log(2,"info",_("XiboLayoutManager: run() -> Starting new XiboRegionManager."))
			# TODO: Instead of starting here, we need to sort the regions array by zindex attribute
			# then start in ascending order to ensure rendering happens in layers correctly.
		        tmpRegion.start()
			# Store a reference to the region so we can talk to it later
			self.regions.append(tmpRegion)
			
    
    def regionElapsed(self):
	log.log(2,"info",_("Region elapsed. Checking if layout has elapsed"))

	allExpired = True
	for i in self.regions:
		if i.regionExpired == False:
			log.log(3,"info",_("Region " + i.regionNodeName + " has not expired. Waiting"))
			allExpired = False

	if allExpired:
		log.log(2,"info",_("All regions have expired. Marking layout as expired"))
		self.layoutExpired = True

		# TODO: Check that there is something else to show before killing
		#       the layout off completely.


		# Enqueue region exit transitions by calling the dispose method on each regionManager
		for i in self.regions:
			i.dispose()

		return True
	else:
		return False

    def regionDisposed(self):
	log.log(2,"info",_("Region disposed. Checking if all regions have disposed"))

	allExpired = True
	for i in self.regions:
		if i.disposed == False:
			log.log(3,"info",_("Region " + i.regionNodeName + " has not disposed. Waiting"))
			allExpired = False

	if allExpired == True:
		log.log(2,"info",_("All regions have disposed. Marking layout as disposed"))
		self.layoutDisposed = True

		if self.hold:
		    log.log(2,"info",_("Holding the splash screen until we're told otherwise"))
		else:
		    log.log(2,"info",_("LayoutManager->parent->nextLayout()"))
		    self.parent.nextLayout()
	
    def dispose(self):
	# Enqueue region exit transitions by calling the dispose method on each regionManager
	for i in self.regions:
		i.dispose()

	# TODO: Remove this? The exiting layout should be left for a transition object to transition with.
	#       Leaving in place for testing though.
        # self.p.enqueue("reset","")

class XiboRegionManager(Thread):
    def __init__(self,parent,player,layoutNodeName,layoutNodeNameExt,cn):
        log.log(3,"info",_("New XiboRegionManager instance created."))
        Thread.__init__(self)
	# Semaphore used to block this thread's execution once it has passed control off to the Media thread.
	# Lock is released by a callback from the libavg player (which returns control to this thread such that the
	# player thread never blocks.
	self.lock = Semaphore()
	self.tLock = Semaphore()

	# Variables
	self.p = player
	self.parent = parent
	self.regionNode = cn
	self.layoutNodeName = layoutNodeName
	self.layoutNodeNameExt = layoutNodeNameExt
	self.regionExpired = False
	self.regionNodeNameExt = "-" + str(self.p.nextUniqueId())
	self.regionNodeName = None
	self.width = None
	self.height = None
	self.top = None
	self.left = None
	self.zindex = None
	self.disposed = False
	self.oneItemOnly = False
	self.previousMedia = None
	self.currentMedia = None

	# Calculate the region ID name
	try:
		self.regionNodeName = "R" + str(self.regionNode.attributes['id'].value) + self.regionNodeNameExt
	except KeyError:
		log.log(1,"error",_("Region XLF is invalid. Missing required id attribute"))
		self.regionExpired = True
		self.parent.regionElapsed()
		return


	# Calculate the region width
	try:
		self.width = int(self.regionNode.attributes['width'].value) * parent.l.scaleFactor
	except KeyError:
		log.log(1,"error",_("Region XLF is invalid. Missing required width attribute"))
		self.regionExpired = True
		self.parent.regionElapsed()
		return

	# Calculate the region height
	try:
		self.height =  int(self.regionNode.attributes['height'].value) * parent.l.scaleFactor
	except KeyError:
		log.log(1,"error",_("Region XLF is invalid. Missing required height attribute"))
		self.regionExpired = True
		self.parent.regionElapsed()
		return

	# Calculate the region top
	try:
		self.top = int(self.regionNode.attributes['top'].value) * parent.l.scaleFactor
	except KeyError:
		log.log(1,"error",_("Region XLF is invalid. Missing required top attribute"))
		self.regionExpired = True
		self.parent.regionElapsed()
		return

	# Calculate the region left
	try:
		self.left = int(self.regionNode.attributes['left'].value) * parent.l.scaleFactor
	except KeyError:
		log.log(1,"error",_("Region XLF is invalid. Missing required left attribute"))
		self.regionExpired = True
		self.parent.regionElapsed()
		return

	# Get region zindex
	try:
		self.zindex = int(self.regionNode.attributes['zindex'].value)
	except KeyError:
		self.zindex = 1

    def run(self):
	self.lock.acquire()
	self.tLock.acquire()
        log.log(3,"info",_("New XiboRegionManager instance running for region:") + self.regionNodeName)
	# Create a div for the region and add it
	tmpXML = '<div id="' + self.regionNodeName + '" width="' + str(self.width) + '" height="' + str(self.height) + '" x="' + str(self.left) + '" y="' + str(self.top) + '" opacity="1.0" />'
	self.p.enqueue('add',(tmpXML,self.layoutNodeName))

	#  * Iterate through the media items
	#  -> For each media, display on screen and set a timer to cause the next item to be shown
	#  -> attempt to acquire self.lock - which will block this thread. We will be woken by the callback
	#     to next() by the libavg player.
	#  * When all items complete, mark region complete by setting regionExpired = True and calling parent.regionElapsed()
	mediaCount = 0

	while self.disposed == False and self.oneItemOnly == False:
		for cn in self.regionNode.childNodes:
			if cn.nodeType == cn.ELEMENT_NODE and cn.localName == "media":
				log.log(3,"info","Encountered media")
				mediaCount = mediaCount + 1
				if self.disposed == False:
					type = str(cn.attributes['type'].value)
					type = type[0:1].upper() + type[1:]
					log.log(4,"info","Media is of type: " + type)
					try:
						import plugins.media
						__import__("plugins.media." + type + "Media",None,None,[''])
						self.currentMedia = eval("plugins.media." + type + "Media." + type + "Media")(log,self,self.p,cn)

						# Transition between media here...
						import plugins.transitions
						try:
							tmp1 = str(self.previousMedia.options['transOut'])
							tmp1 = tmp1[0:1].upper() + tmp1[1:]
						except:
							tmp1 = ""
						
						try:
							tmp2 = str(self.currentMedia.options['transIn'])
							tmp2 = tmp2[0:1].upper() + tmp2[1:]
						except:
							tmp2 = ""

						trans = (tmp1,tmp2)
						
						log.log(3,"info",_("Beginning transitions: " + str(trans)))
						# The two transitions match. Let one plugin handle both.
						if (trans[0] == trans[1]) and trans[0] != "":
							self.currentMedia.start()
							try:
								__import__("plugins.transitions." + trans[0] + "Transition",None,None,[''])
								tmpTransition = eval("plugins.transitions." + trans[0] + "Transition." + trans[0] + "Transition")(log,self.p,self.previousMedia,self.currentMedia,self.tNext)
								tmpTransition.start()
							except ImportError:
								__import__("plugins.transitions.DefaultTransition",None,None,[''])
								tmpTransition = plugins.transitions.DefaultTransition.DefaultTransition(log,self.p,self.previousMedia,self.currentMedia,self.tNext)
								tmpTransition.start()
							self.tLock.acquire()
						else:							
					
						# The two transitions don't match.
						# Create two transition plugins and run them sequentially.
							if (trans[0] != ""):
								try:
									__import__("plugins.transitions." + trans[0] + "Transition",None,None,[''])
									tmpTransition = eval("plugins.transitions." + trans[0] + "Transition." + trans[0] + "Transition")(log,self.p,self.previousMedia,None,self.tNext)
									tmpTransition.start()
								except ImportError:
									__import__("plugins.transitions.DefaultTransition",None,None,[''])
									tmpTransition = plugins.transitions.DefaultTransition.DefaultTransition(log,self.p,self.previousMedia,None,self.tNext)
									tmpTransition.start()
								self.tLock.acquire()

							if (trans[1] != ""):
								self.currentMedia.start()
								try:
									__import__("plugins.transitions." + trans[1] + "Transition",None,None,[''])
									tmpTransition = eval("plugins.transitions." + trans[1] + "Transition." + trans[1] + "Transition")(log,self.p,None,self.currentMedia,self.tNext)
									tmpTransition.start()
								except ImportError:
									__import__("plugins.transitions.DefaultTransition",None,None,[''])
									tmpTransition = plugins.transitions.DefaultTransition.DefaultTransition(log,self.p,None,self.currentMedia,self.tNext)
									tmpTransition.start()
								self.tLock.acquire()
							else:
								self.currentMedia.start()
						# Cleanup
						try:						
							self.p.enqueue('del',self.previousMedia.mediaNodeName)								
						except AttributeError:
							pass

						# Wait for the new media to finish
						self.lock.acquire()
						self.previousMedia = self.currentMedia
						self.currentMedia = None
					except ImportError as detail:
						log.log(0,"error","Missing media plugin for media type " + type + ": " + str(detail))
						# TODO: Do something with this layout? Blacklist?
						self.lock.release()				
	
		self.regionExpired = True
		if self.parent.regionElapsed():
			# If regionElapsed returns True, then the layout is on its way out so stop looping
			# Acheived by pretending to be a single item region
			self.oneItemOnly = True

		# If there's only one item, render it and leave it alone!
		if mediaCount == 1:
			self.oneItemOnly = True
		        log.log(3,"info",_("Region has only one media: ") + self.regionNodeName)
	# End while loop

    def next(self):
	# Release the lock semaphore so that the run() method of the thread can continue.
	# Called by a callback from libavg
        # log.log(3,"info",_("XiboRegionManager") + " " + self.regionNodeName + ": " + _("Next Media Item"))

	# Do nothing if the layout has already been removed from the screen
	if self.disposed == True:
		return

	self.lock.release()

    def tNext(self):
	if self.disposed == True:
		return

	self.tLock.release()

    def dispose(self):
	log.log(5,"info",self.regionNodeName + " is disposing.")
	rOptions = {}
	oNode = None

	# TODO: Perform any region exit transitions
	for cn in self.regionNode.childNodes:
		if cn.nodeType == cn.ELEMENT_NODE and cn.localName == "options":
			oNode = cn

	try:	
		for cn in oNode.childNodes:
			if cn.localName != None:
				rOptions[str(cn.localName)] = cn.childNodes[0].nodeValue
				log.log(5,"info","Region Options: " + str(cn.localName) + " -> " + str(cn.childNodes[0].nodeValue))
	except AttributeError:
		rOptions["transOut"] = ""

	# TODO: Make the transition objects and pass in options
	#       Once animation complete, they should call back to self.disposeTransitionComplete()
	transOut = str(rOptions["transOut"])
	if (transOut != ""):
		import plugins.transitions
		transOut = transOut[0:1].upper() + transOut[1:]
		log.log(5,"info",self.regionNodeName + " starting exit transition")
		try:
			__import__("plugins.transitions." + transOut + "Transition",None,None,[''])
			tmpTransition = eval("plugins.transitions." + transOut + "Transition." + transOut + "Transition")(log,self.p,self.previousMedia,None,self.disposeTransitionComplete,rOptions,None)
			tmpTransition.start()
			log.log(5,"info",self.regionNodeName + " control passed to Transition object.")
		except ImportError as detail:
			log.log(3,"error",self.regionNodeName + ": Unable to import requested Transition plugin. " + str(detail))
			self.disposeTransitionComplete()
	else:
		self.disposeTransitionComplete()

    def disposeTransitionComplete(self):
	# Notify the LayoutManager when these are complete.
	log.log(5,"info",self.regionNodeName + " is disposed.")
	self.disposed = True
	self.parent.regionDisposed()
	
#### Finish Layout/Region Managment

#### Scheduler Classes
class XiboLayout:
    def __init__(self,layoutID):
        self.layoutID = layoutID
	self.builtWithNoXLF = False
	self.schedule = ""
	self.layoutNode = None
	self.iter = None

	self.playerWidth = int(config.get('Main','width'))
	self.playerHeight = int(config.get('Main','height'))
	
	# Attributes
	self.width = None
	self.height = None
	self.sWidth = None
	self.sHeight = None
	self.offsetX = 0
	self.offsetY = 0
	self.scaleFactor = 1
	self.backgroundImage = None
	self.backgroundColour = None

	# Checks
	# TODO: Check these are appropriate defaults.
	self.schemaCheck = True
	self.mediaCheck = True
	self.scheduleCheck = True

	# Read XLF from file (if it exists)
	# Set builtWithNoXLF = True if it doesn't
	try:
		log.log(3,"info",_("Loading layout ID") + " " + self.layoutID + " " + _("from file") + " " + config.get('Main','libraryDir') + os.sep + self.layoutID + '.xlf')
		self.doc = minidom.parse(config.get('Main','libraryDir') + os.sep + self.layoutID + '.xlf')

		# Find the layout node and store it
		for e in self.doc.childNodes:
			if e.nodeType == e.ELEMENT_NODE and e.localName == "layout":
				self.layoutNode = e

		# Check the layout's schemaVersion matches the version this client understands
		try:
			xlfSchemaVersion = int(self.layoutNode.attributes['schemaVersion'].value)
		except KeyError:
			log.log(1,"error",_("Layout has no schemaVersion attribute and cannot be shown by this client"))
			self.schemaCheck = False
			return			

		if xlfSchemaVersion != schemaVersion:
			# Layout has incorrect schemaVersion.
			# Set the flag so the scheduler doesn't present this to the display
			log.log(1,"error",_("Layout has incorrect schemaVersion attribute and cannot be shown by this client.") + " " + str(xlfSchemaVersion) + " != " + str(schemaVersion))
			self.schemaCheck = False
			return
		else:
			self.schemaCheck = True

		# Setup variables from the layout node
		try:
			self.width = int(self.layoutNode.attributes['width'].value)
			self.height = int(self.layoutNode.attributes['height'].value)
			self.backgroundColour = str(self.layoutNode.attributes['bgcolor'].value)[1:]
		except KeyError:
			# Layout invalid as a required key was not present
			log.log(1,"error",_("Layout XLF is invalid. Missing required attributes"))

		try:
			self.backgroundImage = self.layoutNode.attributes['background'].value
		except KeyError:
			# Optional attributes, so pass on error.
			pass

		# Work out layout scaling and offset and set appropriate variables
		self.scaleFactor = min((self.playerWidth / float(self.width)),(self.playerHeight / float(self.height)))
		self.sWidth = int(self.width * self.scaleFactor)
		self.sHeight = int(self.height * self.scaleFactor)
		self.offsetX = abs(self.playerWidth - self.sWidth) / 2
		self.offsetY = abs(self.playerHeight - self.sHeight) / 2

		log.log(5,"debug",_("Screen Dimensions:") + " " + str(self.playerWidth) + "x" + str(self.playerHeight))
		log.log(5,"debug",_("Layout Dimensions:") + " " + str(self.width) + "x" + str(self.height))
		log.log(5,"debug",_("Scaled Dimensions:") + " " + str(self.sWidth) + "x" + str(self.sHeight))
		log.log(5,"debug",_("Offset Dimensions:") + " " + str(self.offsetX) + "x" + str(self.offsetY))
		log.log(5,"debug",_("Scale Ratio:") + " " + str(self.scaleFactor))

		# Present the children of the layout node for further parsing
		self.iter = self.layoutNode.childNodes

	except IOError:
		# File doesn't exist. Keep the layout object for the
		# schedule information it may contain later.
		log.log(3,"info",_("File does not exist. Marking layout built without XLF file"))
		self.builtWithNoXLF = True
	
    def canRun(self):
		return self.schemaCheck and self.mediaCheck and self.scheduleCheck

    def resetSchedule(self):
	pass

    def addSchedule(self,fromDt,toDt):
	pass

    def children(self):
	return self.iter
        
class DummyScheduler(XiboScheduler):
    "Dummy scheduler - returns a list of layouts in rotation forever"
    layoutList = ['1', '2', '3']
    layoutIndex = 0
    
    def __init__(self,xmds):
        Thread.__init__(self)
    
    def run(self):
        pass
    
    def nextLayout(self):
        "Return the next valid layout"
        
        layout = XiboLayout(self.layoutList[self.layoutIndex])
        self.layoutIndex = self.layoutIndex + 1

        if self.layoutIndex == len(self.layoutList):
            self.layoutIndex = 0
        
	if layout.canRun() == False:
	        log.log(3,"info",_("DummyScheduler: nextLayout() -> ") + str(layout.layoutID) + _(" is not ready to run."))
		return self.nextLayout()
	else:
	        log.log(3,"info",_("DummyScheduler: nextLayout() -> ") + str(layout.layoutID))
	        return layout
    
    def hasNext(self):
        "Return true if there are more layouts, otherwise false"
        log.log(3,"info",_("DummyScheduler: hasNext() -> true"))
        return True
#### Finish Scheduler Classes

class XMDS:
    def __init__(self):
	self.hasInitialised = False

	# Setup a Proxy for XMDS
	self.xmdsUrl = None
	try:
	    self.xmdsUrl = config.get('Main','xmdsUrl')
	    if self.xmdsUrl[-1] != "/":
		self.xmdsUrl = self.xmdsUrl + "/"
	    self.xmdsUrl = self.xmdsUrl + "xmds.php"
	except ConfigParser.NoOptionError:
	    log.log(0,"error",_("No XMDS URL specified in your configuration"))
	    log.log(0,"error",_("Please check your xmdsUrl configuration option"))
	    exit(1)

	self.wsdlFile = self.xmdsUrl + '?wsdl'

    def check(self):
	if self.hasInitialised:
	    return True
	else:
	    self.server = None
	    tries = 0
	    while self.server == None and tries < 3:
		tries = tries + 1
		log.log(2,"info",_("Connecting to XMDS at ") + self.xmdsUrl + " " + _("Attempt") + " " + str(tries))
	        try:
		    self.server = WSDL.Proxy(self.wsdlFile)
		    self.hasInitialised = True
	        except xml.parsers.expat.ExpatError:
		    log.log(0,"error",_("Could not connect to XMDS."))
	    # End While
	    if self.server == None:
		return False
	
	return True

class XiboDisplayManager:
    def __init__(self):
        pass
    
    def run(self):
        log.log(2,"info",_("New DisplayManager started"))

        # Create a XiboPlayer and start it running.
        self.Player = XiboPlayer()
	self.Player.start()

	# TODO: Display the splash screen
	self.currentLM = XiboLayoutManager(self, self.Player, XiboLayout('0'), 0, 1.0, True)
        self.currentLM.start()
		
	self.xmds = XMDS()
        
        # Load a DownloadManager and start it running in its own thread
        try:
            downloaderName = config.get('Main','downloader')
            self.downloader = eval(downloaderName)(self.xmds)
            self.downloader.start()
            log.log(2,"info",_("Loaded Download Manager ") + downloaderName)
        except ConfigParser.NoOptionError:
            log.log(0,"error",_("No DownloadManager specified in your configuration."))
            log.log(0,"error",_("Please check your Download Manager configuration."))
            exit(1)
        except:
            log.log(0,"error",downloaderName + _(" does not implement the methods required to be a Xibo DownloadManager or does not exist."))
            log.log(0,"error",_("Please check your Download Manager configuration."))
            exit(1)
        # End of DownloadManager init
        
        # Load a scheduler and start it running in its own thread
        try:
            schedulerName = config.get('Main','scheduler')
            self.scheduler = eval(schedulerName)(self.xmds)
            self.scheduler.start()
            log.log(2,"info",_("Loaded Scheduler ") + schedulerName)
        except ConfigParser.NoOptionError:
            log.log(0,"error",_("No Scheduler specified in your configuration"))
            log.log(0,"error",_("Please check your scheduler configuration."))
            exit(1)
        except:
            log.log(0,"error",schedulerName + _(" does not implement the methods required to be a Xibo Scheduler or does not exist."))
            log.log(0,"error",_("Please check your scheduler configuration."))
            exit(1)
        # End of scheduler init

	# TODO: Attempt to register with the webservice. Code should block here if
	# we're configured not to play cached content on startup.
	# TODO: Figure out what exceptions are raised here and handle them.
	if self.xmds.check():
		regReturn = self.xmds.server.RegisterDisplay("test","alex","New Client","1")
		log.log(0,"info",regReturn)
#	while regReturn != "The display is licensed and ready to start.":


	# TODO: Artificial pause while we talk to the webservice
	# Remove Me!
	time.sleep(5)
        
        # Done with the splash screen. Let it advance...
	self.currentLM.hold=False
	self.currentLM.regionDisposed()
            
    def nextLayout(self):
	# TODO: Whole function is wrong. This is where layout transitions should be supported.
	# Needs careful consideration.

        # Deal with any existing LayoutManagers that might still be running
	try:        
		if self.currentLM.isRunning == True:
        	    self.currentLM.dispose()
	except:
		pass
	self.Player.enqueue("reset","")        

        # New LayoutManager
        self.currentLM = XiboLayoutManager(self, self.Player, self.scheduler.nextLayout())
        log.log(2,"info",_("XiboLayoutManager: nextLayout() -> Starting new XiboLayoutManager with layout ") + str(self.currentLM.l.layoutID))
        self.currentLM.start()

class XiboPlayer(Thread):
	"Class to handle libavg interactions"
	def __init__(self):
		Thread.__init__(self)
		self.q = Queue.Queue(0)
		self.uniqueId = 0

	def getDimensions(self):
		return (self.player.width, self.player.height)

	def getElementByID(self,id):
		return self.player.getElementByID(id)

	def nextUniqueId(self):
		# This is just to ensure there are never two identically named nodes on the
		# player at once.
		# When we hit 100 times, reset to 0 as those nodes should be long gone.
		if self.uniqueId > 100:
			self.uniqueId = 0

		self.uniqueId += 1
		return self.uniqueId

	def run(self):
		log.log(1,"info",_("New XiboPlayer running"))
		self.player = avg.Player()
		if config.get('Main','fullscreen') == "true":
			self.player.setResolution(True,int(config.get('Main','width')),int(config.get('Main','height')),int(config.get('Main','bpp')))
		else:
			self.player.setResolution(False,int(config.get('Main','width')),int(config.get('Main','height')),int(config.get('Main','bpp')))
		#self.player.loadPlugin("ColorNode")
		self.player.showCursor(0)
		self.player.loadString('<avg id="main" width="' + config.get('Main','width') + '" height="' + config.get('Main','height') + '"><div id="screen"></div></avg>')
		self.player.setOnFrameHandler(self.frameHandle)
		self.player.play()

	def enqueue(self,command,data):
		log.log(3,"info","Enqueue: " + str(command) + " " + str(data))
		self.q.put((command,data))
		log.log(3,"info",_("Queue length is now") + " " + str(self.q.qsize()))

	def frameHandle(self):
		"Called on each new libavg frame. Takes queued commands and executes them"
		try:
			result = self.q.get(False)
			cmd = result[0]
			data = result[1]
			if cmd == "add":
				newNode = self.player.createNode(data[0])
				parentNode = self.player.getElementByID(data[1])
				parentNode.appendChild(newNode)
				log.log(5,"debug","Added new node to " + str(data[1]))
			elif cmd == "del":
				currentNode = self.player.getElementByID(data)
				parentNode = currentNode.getParent()
				parentNode.removeChild(currentNode)
				log.log(5,"debug","Removed node " + str(data))
			elif cmd == "reset":
				parentNode = self.player.getElementByID("screen")
				numChildren = parentNode.getNumChildren()
				log.log(5,"debug","Reset. Node has " + str(numChildren) + " nodes")
				for i in range(0,numChildren):
					try:
						node = parentNode.getChild(i)
						parentNode.removeChild(node)
						log.log(5,"debug","Removed child node at position " + str(i))
					except:
						pass
			elif cmd == "anim":
				currentNode = self.player.getElementByID(data[1])
				if data[0] == "fadeIn":
					animation = anim.fadeIn(currentNode,data[2])
				if data[0] == "fadeOut":
					animation = anim.fadeOut(currentNode,data[2])
				if data[0] == "linear":
					animation = anim.LinearAnim(currentNode,data[3],data[2],data[4],data[5],False,data[6])
			elif cmd == "play":
				currentNode = self.player.getElementByID(data)
				currentNode.play()
			elif cmd == "pause":
				currentNode = self.player.getElementByID(data)
				currentNode.pause()
			elif cmd == "stop":
				currentNode = self.player.getElementByID(data)
				currentNode.stop()
			elif cmd == "resize":
				currentNode = self.player.getElementByID(data[0])
				dimension = currentNode.getMediaSize()
				# log.log(1,'info',"Media dimensions: " + str(dimension))
				scaleFactor = min((float(data[1]) / dimension[0]),(float(data[2]) / dimension[1]))
				# log.log(1,'info',"Scale Factor: " + str(scaleFactor))
				currentNode.width = dimension[0] * scaleFactor
				currentNode.height = dimension[1] * scaleFactor
			elif cmd == "timer":
				self.player.setTimeout(data[0],data[1])
			elif cmd == "eofCallback":
				currentNode = self.player.getElementByID(data[0])
				currentNode.setEOFCallback(data[1])
			elif cmd == "setOpacity":
				currentNode = self.player.getElementByID(data[0])
				currentNode.opacity = data[1]
			self.q.task_done()
			# Call ourselves again to action any remaining queued items
			# This does not make an infinite loop since when all queued items are processed
			# A Queue.Empty exception is thrown and this whole block is skipped.
			self.frameHandle()
		except Queue.Empty:
			pass
		except RuntimeError as detail:
			log.log(1,"error",_("A runtime error occured: ") + detail)
		except:
			log.log(1,"error",_("An unspecified error occured: ") + str(sys.exc_info()[0]))

class XiboClient:
    "Main Xibo DisplayClient Class. May (in time!) host many DisplayManager classes"

    def __init__(self):
        pass
        
    def play(self):
        global version
        print _("Xibo Client v") + version

	global schemaVersion
        
        print _("Reading default configuration")
        global config
        config = ConfigParser.ConfigParser()
        config.readfp(open('defaults.cfg'))
        
        print _("Reading user configuration")
        config.read(['site.cfg', os.path.expanduser('~/.xibo')])
        
        logLevel = config.get('Logging','logLevel');
        print _("Log Level is: ") + logLevel;
        print _("Logging will be handled by: ") + config.get('Logging','logWriter')
        print _("Switching to new logger")
        
        global log
        logWriter = config.get('Logging','logWriter')
        log = eval(logWriter)(logLevel)
        try:

            log.log(2,"info",_("Switched to new logger"))
        except:
            print logWriter + _(" does not implement the methods required to be a Xibo logWriter or does not exist.")
            print _("Please check your logWriter configuration.")
            exit(1)
        
        self.dm = XiboDisplayManager()
        
        self.dm.run()

# Main - create a XiboClient and run
gettext.install("messages", "locale")

xc = XiboClient()
xc.play()
