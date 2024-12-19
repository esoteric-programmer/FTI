import tkinter as tk

# https://realpython.com/python-gui-tkinter/
# https://tkinterpython.top/drawing/
# https://chatgpt.com/share/67640442-7e84-8004-a4e5-9526cc30ab9e
# https://www.python-kurs.eu/tkinter_menus.php
# https://inf-schule.de/software/gui/entwicklung_tkinter/fensterdialoge/messagebox
# https://www.geeksforgeeks.org/changing-the-mouse-cursor-tkinter/
# https://www.tutorialspoint.com/python/tk_scrollbar.htm
# https://stackoverflow.com/questions/10057672/correct-way-to-implement-a-custom-popup-tkinter-dialog-box , https://stackoverflow.com/questions/16803686/how-to-create-a-modal-dialog-in-tkinter




class StartBaustein:
    def __init__(self, canvas):
        self.x = 0
        self.y = 0
        self.canvas = canvas
        # Dra line
        self.line = canvas.create_line(0,0,0,0, fill='green', width=3)
        # Draw an rectangle
        self.rect = canvas.create_rectangle(0, 0, 0, 0, fill='white')
        # Draw a circle
        self.circle = canvas.create_oval(0, 0, 0, 0, fill='grey')
        # Draw a circle
        self.circle2 = canvas.create_oval(0, 0, 0, 0, fill='grey')
        # Draw some text
        self.text = canvas.create_text(0, 0, text="START", font=("Helvetica", 12), fill='blue')
        # Call the method to draw the circle and rectangle
        self.position(canvas.winfo_pointerx()-canvas.winfo_rootx(), canvas.winfo_pointery()-canvas.winfo_rooty())

    def position(self,x,y):
        # Update the position of the graphic based on the mouse cursor
        self.x = x
        self.y = y

        # Move the graphic (ellipse, circle, and text) to the new position
        self.canvas.coords(self.circle, x-70, y-10, x-50, y+10)  # Circle coordinates
        self.canvas.coords(self.circle2, x+50, y-10, x+70, y+10)  # Circle coordinates
        self.canvas.coords(self.rect, x-60, y-10, x+60, y+10)  # Ellipse coordinates
        self.canvas.coords(self.text, x, y+2)  # Text position
        self.canvas.coords(self.line, x,y+10,x,y+20)

    def delete(self):
        self.canvas.delete(self.circle)
        self.canvas.delete(self.circle2)
        self.canvas.delete(self.rect)
        self.canvas.delete(self.text)
        self.canvas.delete(self.line)

    def print_pos(self):
        print("Baustein at ("+str(self.x)+";"+str(self.y)+")")



bs = None
fixed = True
bausteine = []

def insertBaustein():
  ## TODO: baustein-type-selection
  global bs, fixed, innercanvas
  if bs is None:
    bs = StartBaustein(innercanvas)
    fixed = False
  else:
    bs.position(innercanvas.winfo_pointerx()-innercanvas.winfo_rootx(), innercanvas.winfo_pointery()-innercanvas.winfo_rooty())

def update_graphic(event):
    global bs, fixed
    if not fixed and bs:
      x, y = event.x, event.y
      bs.position(x,y)
    #global innercanvas
    #print(str(innercanvas.winfo_pointerx()))

def callback(event):
    global bs, fixed
    if bs is not None:
      bausteine.append(bs)
    fixed = True
    bs = None

def function_rightclick(event):
    global bs, fixed
    if bs is not None:
      bs.delete()
      bs = None
    fixed = True


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
    b.print_pos()

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
