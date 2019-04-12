"""

ui/TUI: Text User Interface
===========================

The curses library is one of those things I always wanted to use, but never got 
around to it.
That ends here, as this script will try to take curses and abstract it into a 
nice framework I can re-use without needing to pull out a manual for curses to 
figure out exactly what everything does (which is what I will be doing during 
the duration of writing this script).

I would like to note here that while I usually avoid using `import <module>` in 
favor of `from <module> import <component>`, I am making an exception here for 
curses due to how excessive and overkill that would be.

"""

import curses
from time import sleep

class TUI:
    def __init__(self):
        # self.screen = None
        self.windows = dict()
        self.running = True

        # This removes the need for `initialize` and `cleanup`
        curses.wrapper(self.run)

    # Puts terminal into correct modes and state
    def initialize(self):
        self.screen = curses.initscr()
        # So that input will be read and not just echo'd onto the screen
        curses.noecho()
        # Will read keys as they are typed without needing Enter pressed
        curses.cbreak()
        # Converts special keys into curses variables
        self.screen.keypad(True)
        self.running = True

    # Returns terminal back to how it was beforehand
    def cleanup(self):
        self.running = False
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()

    # Stop loop running in `run`
    def stop(self):
        self.running = False

    # Easily check if getch matches a letter or curses.KEY_* variable
    def is_key(self, getch, test):
        if type(test) is str:
            return getch == ord(test)
        return getch == test

    # Curses uses the format: height, width, y, x or y, x
    def create_window(start_x, start_y, width=None, height=None):
        window = dict()


    # Curses logic run inside wrapper to initialize/cleanup automatically
    def run(self, screen):
        
        win = dict()
        win["width"] = 80
        win["height"] = 24
        win["start_x"] = 10
        win["start_y"] = 10
        win["window"] = screen.subwin(win["height"], win["width"], 
            win["start_y"], win["start_x"])
        window = win["window"]

    # # Curses logic run inside wrapper to initialize/cleanup automatically
    # def run(self, screen):
    #     # Make getch non-blocking and clear the screen
    #     screen.nodelay(True)
    #     screen.clear()
        
    #     width = 4
    #     count = 0
    #     direction = 1

    #     while self.running:
    #         # Get user input
    #         char = screen.getch()
            
    #         # Flush the user input and clear the screen
    #         curses.flushinp()
    #         screen.clear()

    #         if self.is_key(char, "q"):
    #             screen.addstr("Closing...")
    #             self.stop()
    #             break
    #         elif self.is_key(char, curses.KEY_UP):
    #             width = width + 1
            
    #         screen.addstr("#" * count)
    #         count = count + direction
    #         if count == width:
    #             direction = -1
    #         elif count == 0:
    #             direction = 1
    #         sleep(0.1)