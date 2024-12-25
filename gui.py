import tkinter as tk
from tkinter import simpledialog
from abc import ABC, abstractmethod

# https://realpython.com/python-gui-tkinter/
# https://tkinterpython.top/drawing/
# https://chatgpt.com/share/67640442-7e84-8004-a4e5-9526cc30ab9e
# https://www.python-kurs.eu/tkinter_menus.php
# https://inf-schule.de/software/gui/entwicklung_tkinter/fensterdialoge/messagebox
# https://www.geeksforgeeks.org/changing-the-mouse-cursor-tkinter/
# https://www.tutorialspoint.com/python/tk_scrollbar.htm
# https://stackoverflow.com/questions/10057672/correct-way-to-implement-a-custom-popup-tkinter-dialog-box , https://stackoverflow.com/questions/16803686/how-to-create-a-modal-dialog-in-tkinter



class Baustein:
    def __init__(self, canvas, x=None, y=None):
        self.x = 0
        self.y = 0
        self.canvas = canvas
        self.elements = []
        for obj in self.objects():
          e = {}
          e['element'] = obj[0]
          e['x1'] = obj[1]
          e['y1'] = obj[2]
          if len(obj)>=5:
            e['x2'] = obj[3]
            e['y2'] = obj[4]
            if len(obj) >= 9:
              e['x3'] = obj[5]
              e['y3'] = obj[6]
              e['x4'] = obj[7]
              e['y4'] = obj[8]
          self.elements.append(e)
        if x is None or y is None:
          self.position(canvas.winfo_pointerx()-canvas.winfo_rootx(), canvas.winfo_pointery()-canvas.winfo_rooty())
        else:
          self.position(x,y)

    def position(self,x,y):
        # Update the position of the graphic based on the mouse cursor
        self.x = x
        self.y = y
        for e in self.elements:
          # Move the graphic (ellipse, circle, and text) to the new position
          if 'x2' in e and 'y2' in e:
            if 'x3' in e and 'y3' in e and 'x4' in e and 'y4' in e:
              self.canvas.coords(e['element'], x+e['x1'], y+e['y1'], x+e['x2'], y+e['y2'], x+e['x3'], y+e['y3'], x+e['x4'], y+e['y4'])
            else:
              self.canvas.coords(e['element'], x+e['x1'], y+e['y1'], x+e['x2'], y+e['y2'])
          else:
            self.canvas.coords(e['element'], x+e['x1'], y+e['y1'])

    def onUserCreated(self):
        pass

    def delete(self):
        for e in self.elements:
          self.canvas.delete(e['element'])
        self.elements = []

    def print(self):
        print(self.__class__.__name__+" at ("+str(self.x)+";"+str(self.y)+")")

    @abstractmethod
    def objects(self):
        pass


class StartBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white'), -60, -10, 60, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), -70, -10, -50, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), 50, -10, 70, 10],
          [self.canvas.create_text(0, 0, text="START", font=("Helvetica", 12), fill='blue'), 0, 2]
          ]
      return objs


class EndeBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white'), -60, -10, 60, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), -70, -10, -50, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), 50, -10, 70, 10],
          [self.canvas.create_text(0, 0, text="ENDE", font=("Helvetica", 12), fill='blue'), 0, 2]
          ]
      return objs

class BeepBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_text(0, 0, text="BEEP", font=("Helvetica", 12), fill='blue'), 0, 2]
          ]
      return objs


class IncDecBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white', outline='black'), -70, -10, 70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -50, -8, 30, 8],
          [self.canvas.create_text(0, 0, text="VAR ??", font=("Helvetica", 12), fill='blue'), -10, 2],
          ]
      return objs
    
    # TODO: ask which variable should be incremented or decremented
    def onUserCreated(self):
        pass


class IncBaustein(IncDecBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="INC", font=("Helvetica", 12), fill='black'), 50, 2])
        return objs


class DecBaustein(IncDecBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="DEC", font=("Helvetica", 12), fill='black'), 50, 2])
        return objs


class EingangBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 30, 0, 40],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -30, 0, -40],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 70, 0, 80, 0],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), 0, -30, 70, 0, 0, 30, -70, 0],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -30, -8, 30, 8],
          [self.canvas.create_text(0, 0, text="0", font=("Helvetica", 12), fill='black'), 50, 2],
          [self.canvas.create_text(0, 0, text="1", font=("Helvetica", 12), fill='black'), 0, 22],
          [self.canvas.create_text(0, 0, text="E ?", font=("Helvetica", 12), fill='black'), 0, 2],
          ]
      return objs
    
    # TODO: ask which entry should be read // ask in which case we should go to the right?
    def onUserCreated(self):
        pass


class FlankeBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), 20, -8, 50, 8],
          [self.canvas.create_text(0, 0, text="Flanke", font=("Helvetica", 12), fill='black'), -10, 2],
          [self.canvas.create_text(0, 0, text="E ?", font=("Helvetica", 12), fill='black'), 35, 2],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -55, -5, -45, -5],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -45, -5, -45, 5],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -45, 5, -35, 5],
          ]
      return objs
    # TODO: ask which entry should be read
    def onUserCreated(self):
        pass


class VariableBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white', outline='black'), -70, -10, 70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -40, -8, 60, 8],
          [self.canvas.create_text(0, 0, text="VAR ? = ?????", font=("Helvetica", 8), fill='black'), 10, 2],
          ]
      return objs

    # TODO: ask which variable the value should be assigned to and which value should be assigned
    def onUserCreated(self):
        pass


class VergleichBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 30, 0, 40],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -30, 0, -40],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 70, 0, 80, 0],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), 0, -30, 70, 0, 0, 30, -70, 0],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -40, -8, 40, 8],
          [self.canvas.create_text(0, 0, text="J", font=("Helvetica", 12), fill='black'), 50, 2],
          [self.canvas.create_text(0, 0, text="N", font=("Helvetica", 12), fill='black'), 0, 22],
          [self.canvas.create_text(0, 0, text="VAR ? = ?????", font=("Helvetica", 8), fill='black'), 0, 2],
          ]
      return objs
    
    # TODO: ask which variable should be read, which operator should be used, to which value it should be compared and in which case we should go to the right?
    def onUserCreated(self):
        pass


class MotorBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -15, -8, 55, 8],
          [self.canvas.create_text(0, 0, text="Motor", font=("Helvetica", 12), fill='black'), -40, 2],
          [self.canvas.create_text(0, 0, text="? AUS", font=("Helvetica", 10), fill='black'), 20, 2],
          ]
      return objs
    # TODO: ask which motor should be controlled and in which direction (Off, left, Right)
    def onUserCreated(self):
        pass


class WarteBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -15, -8, 55, 8],
          [self.canvas.create_text(0, 0, text="Warte", font=("Helvetica", 12), fill='black'), -40, 2],
          [self.canvas.create_text(0, 0, text="0.0", font=("Helvetica", 10), fill='black'), 20, 2],
          ]
      return objs
    # TODO: ask how long time should be waited
    def onUserCreated(self):
        pass


class ItemSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent, title, items):
        self.items = items
        self.selected_item = None
        super().__init__(parent, title)

    def body(self, master):
        # Canvas for item preview
        self.canvas = tk.Canvas(master, width=200, height=100, bg="white")
        self.canvas.pack(pady=10)

        # Scrollable listbox
        self.listbox_frame = tk.Frame(master)
        self.listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(self.listbox_frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(self.listbox_frame, selectmode=tk.SINGLE, yscrollcommand=self.scrollbar.set, height=10)
        
        self.scrollbar.config(command=self.listbox.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate listbox with items
        for item in self.items:
            self.listbox.insert(tk.END, item)

        # Bind selection event
        self.listbox.bind("<<ListboxSelect>>", self.on_item_select)

        return self.listbox  # Focus initial widget

    def on_item_select(self, event):
        # Get the selected item
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            self.selected_item = self.items[index]

            # Update the preview in the canvas
            self.canvas.delete("all")
            if self.selected_item == "Start":
              StartBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Beep":
              BeepBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Increment Variable":
              IncBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Decrement Variable":
              DecBaustein(self.canvas, 100, 50),
            elif self.selected_item == "Eingang":
              EingangBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Ende":
              EndeBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Flanke":
              FlankeBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Variable":
              VariableBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Vergleich":
              VergleichBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Motor":
              MotorBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Warte":
              WarteBaustein(self.canvas, 100, 50)
            else:
              self.canvas.create_text(100, 50, text=self.selected_item, font=("Arial", 14))

    def apply(self):
        # When OK is pressed, return the selected item
        self.result = self.selected_item



bs = None
fixed = True
bausteine = []

def function_rightclick(event):
    global bs, fixed
    if bs is not None:
      bs.delete()
      bs = None
    fixed = True


def insertBaustein():
  ## TODO: baustein-type-selection
  global bs, fixed, innercanvas, root
  
  ## cancel current insertion (if any)
  function_rightclick(None)
  
  items = ["Beep", "Decrement Variable", "Display", "Eingang", "Ende", "Flanke", "Increment Variable", "Lampe", "Meldung", "Motor", "Notaus", "Position", "Reset", "Start", "Terminal", "Variable", "Vergleich", "Warte"]
  dialog = ItemSelectionDialog(root, "Baustein auswählen", items)

  if dialog.result == "Start":
    bs = StartBaustein(innercanvas)
  elif dialog.result == "Beep":
    bs = BeepBaustein(innercanvas)
  elif dialog.result == "Increment Variable":
    bs = IncBaustein(innercanvas)
  elif dialog.result == "Decrement Variable":
    bs = DecBaustein(innercanvas)
  elif dialog.result == "Eingang":
    bs = EingangBaustein(innercanvas)
  elif dialog.result == "Ende":
    bs = EndeBaustein(innercanvas)
  elif dialog.result == "Flanke":
    bs = FlankeBaustein(innercanvas)
  elif dialog.result == "Variable":
    bs = VariableBaustein(innercanvas)
  elif dialog.result == "Vergleich":
    bs = VergleichBaustein(innercanvas)
  elif dialog.result == "Motor":
    bs = MotorBaustein(innercanvas)
  elif dialog.result == "Warte":
    bs = WarteBaustein(innercanvas)
  elif dialog.result:
    print("ERROR: not implemented yet")
  else:
    print("No item selected.")

  if bs is not None:
    fixed = False
  

def update_graphic(event):
    global bs, fixed
    if not fixed and bs:
      x, y = event.x, event.y
      bs.position(x,y)
    #global innercanvas
    #print(str(innercanvas.winfo_pointerx()))

def callback(event):
    global bs, fixed
    fixed = True
    if bs is not None:
      bs.onUserCreated()
      bausteine.append(bs)
      bs = None




root = tk.Tk()
root.title("LLWin Nachbau")
root.geometry("800x600+"+str(int((root.winfo_screenwidth()-800)/2))+"+"+str(int((root.winfo_screenheight()-600)/2)))
menu = tk.Menu(root)
root.config(menu=menu)
filemenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Datei", menu=filemenu)
filemenu.add_command(label="Neu...")
filemenu.add_command(label="Öffnen...")
filemenu.add_command(label="Speichern")
filemenu.add_command(label="Speichern unter...")
filemenu.add_command(label="Schließen")
filemenu.add_separator()
filemenu.add_command(label="Level")
filemenu.add_separator()
filemenu.add_command(label="Seite drucken")
filemenu.add_command(label="Projekt drucken")
filemenu.add_separator()
filemenu.add_command(label="Beenden", command=root.quit)
# HISTORY:
#filemenu.add_separator()
#filemenu.add_command(label="1 /home/matthias/file1.mdl")
#filemenu.add_command(label="2 /home/matthias/test3.mdl")
editmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Bearbeiten", menu=editmenu)
editmenu.add_command(label="Hauptprogramm")
editmenu.add_command(label="Unterprogramm...")
editmenu.add_separator()
editmenu.add_command(label="Rückgängig")
editmenu.add_separator()
editmenu.add_command(label="Baustein einfügen...", command=insertBaustein)
editmenu.add_command(label="Baustein löschen")
editmenu.add_command(label="Baustein ersetzen")
subprogmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Unterprogramm", menu=subprogmenu)
subprogmenu.add_command(label="Kopieren...")
subprogmenu.add_command(label="Aussehen...")
subprogmenu.add_command(label="Löschen...")
subprogmenu.add_command(label="Attribute...")
runmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Run", menu=runmenu)
runmenu.add_command(label="Init")
runmenu.add_command(label="Start")
runmenu.add_command(label="Stop")
runmenu.add_separator()
runmenu.add_command(label="Aktiv-Modus")
prefmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Optionen", menu=prefmenu)
prefmenu.add_command(label="Arbeitsblatt...")
prefmenu.add_command(label="Zoom...")
prefmenu.add_separator()
prefmenu.add_command(label="Anschlüsse")
prefmenu.add_command(label="Statuszeile")
prefmenu.add_command(label="Cursorumschaltung")
prefmenu.add_command(label="Autorouting...")
prefmenu.add_separator()
prefmenu.add_command(label="Interfacediagnose...")
prefmenu.add_command(label="Interfaceeinstellung...")
wndwmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Fenster", menu=wndwmenu)
wndwmenu.add_command(label="Überlappend")
wndwmenu.add_command(label="Nebeneinander")
wndwmenu.add_command(label="Symbole anordnen")
wndwmenu.add_command(label="Schließen")
wndwmenu.add_command(label="Alle schließen")
wndwmenu.add_separator()
wndwmenu.add_command(label="1: $Main")
#wndwmenu.add_command(label="2: ...")
wndwmenu.add_command(label="Kopieren zur Ablagemappe")
helpmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Fenster", menu=helpmenu)
helpmenu.add_command(label="Index")
helpmenu.add_command(label="Tastatur")
helpmenu.add_command(label="Befehle")
helpmenu.add_command(label="Hilfe verwenden")
helpmenu.add_separator()
helpmenu.add_command(label="Info über...")


canvas = tk.Canvas(root)
scrollbar_y = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollbar_x = tk.Scrollbar(root, orient="horizontal", command=canvas.xview)
#canvas.grid_propagate(False)

# Place the canvas and scrollbars
canvas.grid(row=0, column=0, sticky="nsew")
scrollbar_y.grid(row=0, column=1, sticky="ns")
scrollbar_x.grid(row=1, column=0, sticky="ew")

# Configure the grid to make the canvas expandable
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

# Create a frame inside the canvas
frame = tk.Frame(canvas)  # Frame larger than the window
#frame.grid_propagate(False)  # Prevent resizing based on content

# Add the frame to the canvas
frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

# Configure canvas scrolling
canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

# Update the canvas scroll region when the frame's size changes
def update_scrollbars(event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))

    # Get the dimensions of the content and the canvas
    content_width, content_height = canvas.bbox("all")[2:4]
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()

    # Show or hide the vertical scrollbar
    if content_height > canvas_height:
        scrollbar_y.grid()
    else:
        scrollbar_y.grid_remove()

    # Show or hide the horizontal scrollbar
    if content_width > canvas_width:
        scrollbar_x.grid()
    else:
        scrollbar_x.grid_remove()

frame.bind("<Configure>", update_scrollbars)
canvas.bind("<Configure>", update_scrollbars)

# Add some content to the frame (for demonstration)
#for i in range(20):
#    tk.Label(frame, text=f"Item {i+1}").grid(row=i, column=0, padx=10, pady=5)


canvas_width, canvas_height = 1000, 750  # Size larger than the window
innercanvas = tk.Canvas(frame, bg="white", width=canvas_width, height=canvas_height)
innercanvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
#innercanvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

for x in range(0, canvas_width, 50):  # Vertical dashed lines every 50 pixels
        innercanvas.create_line(x, 0, x, canvas_height, dash=(4, 2), fill="gray")

for y in range(0, canvas_height, 50):  # Horizontal dashed lines every 50 pixels
        innercanvas.create_line(0, y, canvas_width, y, dash=(4, 2), fill="gray")




innercanvas.bind("<Motion>", update_graphic)
innercanvas.bind("<Button-1>", callback)
innercanvas.bind("<Button-3>", function_rightclick)

# Run the application
root.mainloop()

print("the following Bausteine have been created:")
for b in bausteine:
  if b is not None:
    b.print()

exit(0)






############ old code
frame_a = tk.Frame()

greeting = tk.Label(text="Hello, Tkinter")
greeting.pack()

label = tk.Label(
    text="Hello, Tkinter",
    foreground="white",  # Set the text color to white
    background="black",  # Set the background color to black
    width=50,
    height=10
)
label.pack()
button = tk.Button(
    text="Click me!",
    width=25,
    height=5,
    bg="blue",
    fg="yellow",
)
button.pack()
button.bind("<Button-1>", handle_click)
entry = tk.Entry(fg="yellow", bg="blue", width=50)
entry.pack()

frame_a = tk.Frame()
frame_b = tk.Frame()

label_a = tk.Label(master=frame_a, text="I'm in Frame A")
label_a.pack()

label_b = tk.Label(master=frame_b, text="I'm in Frame B")
label_b.pack()

frame_a.pack()
frame_b.pack()

window.mainloop()
#window.destroy()
