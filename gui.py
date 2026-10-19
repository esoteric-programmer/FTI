import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from abc import ABC, abstractmethod
from enum import Enum
import struct
import traceback

# Define the global enum
class Mode(Enum):
  NONE=0
  INSERT=1
  REMOVE=2
  LINK=3


class SubProgram:
    def __init__(self, name, num_inputs=0, num_outputs=0):
        self.name = name
        self.num_inputs = num_inputs
        self.num_outputs = num_outputs
        self.bausteine = []
        self.connections = []
        self.drawn_path_segments = []
        self.path_anchor_stubs = []
        self.connection_lines = []
        self.text_annotations = []


## TODO
## forbid duplicate connections
## make Bausteine editable, moveable and removeable
## make connection moveable and deleteable
## passive mode
##
## --- Future work for LLWin 2.1 MDL compatibility ---
## missing Baustein classes:
##   Display  — sets DW109/DW110 (terminal display), implemented as &SVAR
##   Meldung  — shows a text string, uses &T2D command
##   Terminal — hardware terminal I/O block
## text comments: LLWin lets users place free-text annotations on the
##   canvas (e.g. "Sortierband", "40 Schritte"). Stored in MDL as their
##   own records with position and string content, no connections.
## save/open project in LLWin 2.1 MDL format (see reverse_mdl_format.txt)



CROSSING_PENALTY  = 500   # extra cost per existing connection a new segment would cross
STUB_PENALTY      = 10000 # extra cost per anchor stub crossed (virtually blocked)
PATH_CLEARANCE    = 4     # minimum pixel distance from other path segments (parallel)
PROXIMITY_PENALTY = 200   # extra cost per parallel segment that's too close

programs = []
current_program = None
drawn_path_segments = []  # aliased to current_program.drawn_path_segments by switch_program
path_anchor_stubs   = []  # aliased to current_program.path_anchor_stubs by switch_program


def _hv_segment_blocked(x1, y1, x2, y2, margin=3):
  """Return True if the horizontal or vertical segment passes through any Baustein BB.
  Segments that only touch a BB boundary (strict inequality) are allowed."""
  global bausteine
  for b in bausteine:
    bb = b.getBoundingBox()
    bx1, by1, bx2, by2 = bb[0]-margin, bb[1]-margin, bb[2]+margin, bb[3]+margin
    if x1 == x2:   # vertical segment at x=x1
      sy1, sy2 = min(y1, y2), max(y1, y2)
      if bx1 < x1 < bx2 and sy1 < by2 and sy2 > by1:
        return True
    else:           # horizontal segment at y=y1
      sx1, sx2 = min(x1, x2), max(x1, x2)
      if by1 < y1 < by2 and sx1 < bx2 and sx2 > bx1:
        return True
  return False


def _count_hv_crossings(x1, y1, x2, y2, segments):
  """Count how many segments in the list the new H/V segment crosses."""
  count = 0
  for seg in segments:
    sx1, sy1 = seg[0][0], seg[0][1]
    sx2, sy2 = seg[1][0], seg[1][1]
    if x1 == x2:   # new segment is vertical at x=x1
      if sy1 == sy2:   # existing segment is horizontal at y=sy1
        ny1, ny2 = min(y1, y2), max(y1, y2)
        ex1, ex2 = min(sx1, sx2), max(sx1, sx2)
        if ex1 < x1 < ex2 and ny1 < sy1 < ny2:
          count += 1
    else:           # new segment is horizontal at y=y1
      if sx1 == sx2:   # existing segment is vertical at x=sx1
        ey1, ey2 = min(sy1, sy2), max(sy1, sy2)
        nx1, nx2 = min(x1, x2), max(x1, x2)
        if nx1 < sx1 < nx2 and ey1 < y1 < ey2:
          count += 1
  return count


def _crossing_cost(x1, y1, x2, y2):
  """Return extra cost for crossing drawn connections or anchor stubs."""
  global drawn_path_segments, path_anchor_stubs
  cost  = _count_hv_crossings(x1, y1, x2, y2, drawn_path_segments) * CROSSING_PENALTY
  cost += _count_hv_crossings(x1, y1, x2, y2, path_anchor_stubs)   * STUB_PENALTY
  return cost


def _proximity_cost(x1, y1, x2, y2):
  """Return penalty for running within PATH_CLEARANCE pixels of an existing segment
  in the parallel direction (avoids paths hugging each other)."""
  global drawn_path_segments
  cost = 0
  for seg in drawn_path_segments:
    sx1, sy1 = seg[0][0], seg[0][1]
    sx2, sy2 = seg[1][0], seg[1][1]
    if x1 == x2 and sx1 == sx2:          # both vertical
      gap = abs(x1 - sx1)
      if 0 < gap < PATH_CLEARANCE:
        ey1, ey2 = min(sy1, sy2), max(sy1, sy2)
        ny1, ny2 = min(y1,  y2),  max(y1,  y2)
        if ny1 < ey2 and ny2 > ey1:      # y ranges overlap
          cost += PROXIMITY_PENALTY
    elif x1 != x2 and sx1 != sx2:        # both horizontal (sy1==sy2, y1==y2)
      gap = abs(y1 - sy1)
      if 0 < gap < PATH_CLEARANCE:
        ex1, ex2 = min(sx1, sx2), max(sx1, sx2)
        nx1, nx2 = min(x1,  x2),  max(x1,  x2)
        if nx1 < ex2 and nx2 > ex1:      # x ranges overlap
          cost += PROXIMITY_PENALTY
  return cost


def simple_route(start, target):
  """Simple geometric routing matching LLWin 2.1 behavior.

  Tries 0-bend (straight), 1-bend (L-shape), 2-bend (Z-shape),
  then falls back to a direct diagonal line."""
  global bausteine

  sx, sy = int(start[0]), int(start[1])
  tx, ty = int(target[0]), int(target[1])

  if sx == tx and sy == ty:
    return [[sx, sy]]

  MARGIN = 3
  GRID = 50

  def seg_cost(x1, y1, x2, y2):
    return _crossing_cost(x1, y1, x2, y2) + _proximity_cost(x1, y1, x2, y2)

  def seg_ok(x1, y1, x2, y2):
    return not _hv_segment_blocked(x1, y1, x2, y2, MARGIN)

  # 0-bend: straight H or V line
  if (sx == tx or sy == ty) and seg_ok(sx, sy, tx, ty):
    return [[sx, sy], [tx, ty]]

  # 1-bend: L-shape (two options)
  l_options = []
  # Option A: vertical then horizontal
  if seg_ok(sx, sy, sx, ty) and seg_ok(sx, ty, tx, ty):
    cost = seg_cost(sx, sy, sx, ty) + seg_cost(sx, ty, tx, ty)
    l_options.append((cost, [[sx, sy], [sx, ty], [tx, ty]]))
  # Option B: horizontal then vertical
  if seg_ok(sx, sy, tx, sy) and seg_ok(tx, sy, tx, ty):
    cost = seg_cost(sx, sy, tx, sy) + seg_cost(tx, sy, tx, ty)
    l_options.append((cost, [[sx, sy], [tx, sy], [tx, ty]]))

  if l_options:
    l_options.sort(key=lambda x: x[0])
    if l_options[0][0] == 0:
      return l_options[0][1]

  # 2-bend: Z-shape — collect candidate midpoints
  mid_candidates_y = set()
  mid_candidates_x = set()
  mid_y = (sy + ty) // 2
  mid_x = (sx + tx) // 2
  mid_candidates_y.add(mid_y)
  mid_candidates_x.add(mid_x)
  mid_candidates_y.add(round(mid_y / GRID) * GRID)
  mid_candidates_x.add(round(mid_x / GRID) * GRID)
  for g_val in range(0, 1500, GRID):
    if min(sy, ty) - GRID <= g_val <= max(sy, ty) + GRID:
      mid_candidates_y.add(g_val)
    if min(sx, tx) - GRID <= g_val <= max(sx, tx) + GRID:
      mid_candidates_x.add(g_val)
  for b in bausteine:
    bb = b.getBoundingBox()
    mid_candidates_y.add(bb[1] - MARGIN - 1)
    mid_candidates_y.add(bb[3] + MARGIN + 1)
    mid_candidates_x.add(bb[0] - MARGIN - 1)
    mid_candidates_x.add(bb[2] + MARGIN + 1)

  z_best = None
  z_best_cost = float('inf')

  # Z type 1: V-H-V (vertical, horizontal, vertical)
  for my in mid_candidates_y:
    if seg_ok(sx, sy, sx, my) and seg_ok(sx, my, tx, my) and seg_ok(tx, my, tx, ty):
      cost = seg_cost(sx, sy, sx, my) + seg_cost(sx, my, tx, my) + seg_cost(tx, my, tx, ty)
      if cost < z_best_cost:
        z_best_cost = cost
        z_best = [[sx, sy], [sx, my], [tx, my], [tx, ty]]

  # Z type 2: H-V-H (horizontal, vertical, horizontal)
  for mx in mid_candidates_x:
    if seg_ok(sx, sy, mx, sy) and seg_ok(mx, sy, mx, ty) and seg_ok(mx, ty, tx, ty):
      cost = seg_cost(sx, sy, mx, sy) + seg_cost(mx, sy, mx, ty) + seg_cost(mx, ty, tx, ty)
      if cost < z_best_cost:
        z_best_cost = cost
        z_best = [[sx, sy], [mx, sy], [mx, ty], [tx, ty]]

  if z_best:
    return z_best

  # Prefer L-shape with crossings over diagonal
  if l_options:
    return l_options[0][1]

  # Diagonal fallback
  return [[sx, sy], [tx, ty]]


def simplifyPath(path):
  """Merge consecutive collinear segments (same orientation H or V)."""
  if path is None or len(path) == 0:
    return []
  if len(path) == 1:
    return [[path[0], path[0]]]
  segments = []
  seg_start = path[0]
  for i in range(1, len(path) - 1):
    prev_vertical = (path[i][0] == path[i-1][0])
    next_vertical = (path[i][0] == path[i+1][0])
    if prev_vertical != next_vertical:   # orientation change → corner
      segments.append([seg_start, path[i]])
      seg_start = path[i]
  segments.append([seg_start, path[-1]])
  return segments


def drawPath(path):
  global innercanvas, drawn_path_segments, path_anchor_stubs, current_program
  pathes = simplifyPath(path)
  arrow = 'last'
  for seg in reversed(pathes):
    lid = innercanvas.create_line(seg[0][0], seg[0][1], seg[1][0], seg[1][1],
                                  fill='green', width=3, arrow=arrow)
    current_program.connection_lines.append(lid)
    arrow = 'none'
  drawn_path_segments.extend(pathes)
  # Seal the gap between each connection point and its Baustein's BB with a virtual
  # stub.  The stub runs from the anchor point back toward the Baustein (opposite to
  # the first outgoing segment, and continuing beyond the target anchor in the same
  # inbound direction), long enough to cover the visual stub + expansion margin gap.
  STUB_LEN = 5   # covers the ~4 px visual stub plus the 1 px expanded-BB gap
  if pathes:
    src     = pathes[0][0]
    src_dir = [pathes[0][1][0] - src[0], pathes[0][1][1] - src[1]]
    if src_dir[0] == 0:   # first segment vertical
      dy = 1 if src_dir[1] > 0 else -1
      path_anchor_stubs.append([[src[0], src[1] - dy * STUB_LEN], [src[0], src[1]]])
    else:                 # first segment horizontal
      dx = 1 if src_dir[0] > 0 else -1
      path_anchor_stubs.append([[src[0] - dx * STUB_LEN, src[1]], [src[0], src[1]]])

    tgt      = pathes[-1][1]
    tgt_dir  = [tgt[0] - pathes[-1][0][0], tgt[1] - pathes[-1][0][1]]
    if tgt_dir[0] == 0:  # last segment vertical
      dy = 1 if tgt_dir[1] > 0 else -1
      path_anchor_stubs.append([[tgt[0], tgt[1]], [tgt[0], tgt[1] + dy * STUB_LEN]])
    else:                # last segment horizontal
      dx = 1 if tgt_dir[0] > 0 else -1
      path_anchor_stubs.append([[tgt[0], tgt[1]], [tgt[0] + dx * STUB_LEN, tgt[1]]])



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

    @abstractmethod
    def getConnections(self):
        # each entry: x,y,outgoing?
        return []

    def getPosition(self):
        return [self.x,self.y]

    @abstractmethod
    def getBoundingBox(self):
        pass

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

    def toString(self):
        return self.__class__.__name__+" at ("+str(self.x)+";"+str(self.y)+")"

    @abstractmethod
    def objects(self):
        pass

    def to_fti(self):
        raise NotImplementedError(f"{self.__class__.__name__}.to_fti() not implemented")

    def get_fti_slot(self, conn_idx):
        return 0


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
    def getConnections(self):
        return [[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-10,self.x+70,self.y+15]
    def to_fti(self):
        import FTI
        return FTI.Start()


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
    def getConnections(self):
        return [[0,-19,False]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+10]
    def to_fti(self):
        return None  # Ende = None in FTI

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
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def to_fti(self):
        import FTI
        return FTI.Ton()


class IncDecBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.var = 0
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white', outline='black'), -70, -10, 70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -50, -8, 30, 8],
          [self.canvas.create_text(0, 0, text="VAR ??", font=("Helvetica", 12), fill='blue'), -10, 2],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.var <= 0 or self.var > 99:
         try:
          self.var = int(tk.simpledialog.askstring("Variable", "Nummer der Variablen [1-99]"))
         except:
          pass
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[4]['element'], text="VAR "+str(self.var))


class IncBaustein(IncDecBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="INC", font=("Helvetica", 12), fill='black'), 50, 2])
        return objs
    def to_fti(self):
        import FTI
        return FTI.IncVariable(self.var)


class DecBaustein(IncDecBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="DEC", font=("Helvetica", 12), fill='black'), 50, 2])
        return objs
    def to_fti(self):
        import FTI
        return FTI.DecVariable(self.var)


class EingangBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.eingang = 0
        self.rightOn = -1
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
    def getConnections(self):
        return [[0,-39,False],[0,39,True],[79,0,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-35,self.x+75,self.y+35]
    def onUserCreated(self):
        while self.eingang <= 0 or self.eingang >= 27:
         try:
          self.eingang = int(tk.simpledialog.askstring("Eingang", "Nummer der Eingangs [1-26]"))
         except:
          pass
        while self.rightOn < 0 or self.rightOn > 1:
         try:
          self.rightOn = int(tk.simpledialog.askstring("Verzweigung", "Verzweigung rechts bei [0/1]"))
         except:
          pass
        self.canvas.itemconfigure(self.elements[4]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[7]['element'], text="E "+str(self.eingang))
        if self.rightOn == 1:
          self.canvas.itemconfigure(self.elements[5]['element'], text="1")
          self.canvas.itemconfigure(self.elements[6]['element'], text="0")
    def to_fti(self):
        import FTI
        return FTI.Eingang(self.eingang)
    def get_fti_slot(self, conn_idx):
        # conn[1]=bottom, conn[2]=right
        # rightOn==0: bottom=True(slot 0), right=False(slot 1)
        # rightOn==1: bottom=False(slot 1), right=True(slot 0)
        if conn_idx == 1:  # bottom
            return 0 if self.rightOn == 0 else 1
        elif conn_idx == 2:  # right
            return 1 if self.rightOn == 0 else 0
        return 0


class FlankeBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.eingang = 0
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), 20, -8, 56, 8],
          [self.canvas.create_text(0, 0, text="Flanke", font=("Helvetica", 12), fill='black'), -10, 2],
          [self.canvas.create_text(0, 0, text="E ?", font=("Helvetica", 12), fill='black'), 38, 2],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -55, -5, -45, -5],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -45, -5, -45, 5],
          [self.canvas.create_line(0,0,0,0, fill='black', width=1), -45, 5, -35, 5],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.eingang <= 0 or self.eingang >= 27:
         try:
          self.eingang = int(tk.simpledialog.askstring("Eingang", "Nummer der Eingangs [1-26]"))
         except:
          pass
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], text="E "+str(self.eingang))
    def to_fti(self):
        import FTI
        return FTI.Flanke(self.eingang)


class PositionBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.eingang = 0
        self.countervar = 0
        self.target_value = None
        self.decrement = False
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 25, 0, 35],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -25, 0, -35],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -50, -25, 70, -25, 50, 25, -70, 25],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white', outline='black'), -48, -23, -20, -8],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -10, -23, 45, -9],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -10, -7, 45, 7],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -10, 9, 45, 23],
          [self.canvas.create_text(0, 0, text="ZV", font=("Helvetica", 11), fill='black'), -25, 2],
          [self.canvas.create_text(0, 0, text="HW", font=("Helvetica", 11), fill='black'), -25, 18],
          [self.canvas.create_text(0, 0, text="INC", font=("Helvetica", 11), fill='black'), -33, -14],
          [self.canvas.create_text(0, 0, text="E ?", font=("Helvetica", 11), fill='black'), 17, -14],
          [self.canvas.create_text(0, 0, text="VAR ?", font=("Helvetica", 11), fill='black'), 17, 2],
          [self.canvas.create_text(0, 0, text="0", font=("Helvetica", 11), fill='black'), 17, 18],
          ]
      return objs
    def getConnections(self):
        return [[0,-34,False],[0,34,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-30,self.x+70,self.y+30]
    def onUserCreated(self):
        mode_str = ''
        while mode_str not in ['inc', 'dec']:
            r = tk.simpledialog.askstring("Position", "Modus [inc/dec]")
            if r:
                mode_str = r.lower()
        self.decrement = (mode_str == 'dec')

        while self.eingang <= 0 or self.eingang > 26:
            try:
                self.eingang = int(tk.simpledialog.askstring("Position", "Eingangsnummer [1-26]"))
            except:
                pass

        while self.countervar <= 0 or self.countervar > 99:
            try:
                self.countervar = int(tk.simpledialog.askstring("Position", "Zählervariable [1-99]"))
            except:
                pass

        while self.target_value is None:
            try:
                self.target_value = int(tk.simpledialog.askstring("Position", "Zielwert (Konstante)"))
            except:
                pass

        self.canvas.itemconfigure(self.elements[9]['element'], text='DEC' if self.decrement else 'INC')
        self.canvas.itemconfigure(self.elements[4]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[6]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[10]['element'], text=f"E {self.eingang}")
        self.canvas.itemconfigure(self.elements[11]['element'], text=f"VAR {self.countervar}")
        self.canvas.itemconfigure(self.elements[12]['element'], text=str(self.target_value))
    def to_fti(self):
        import FTI
        return FTI.Position(self.eingang, FTI.constant(self.target_value), self.countervar, self.decrement)


class VariableBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.var = 0
        self.value_type = None   # 'konstante' | 'variable' | 'terminal' | 'analog'
        self.value = None        # int for konstante/variable, str for terminal/analog
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white', outline='black'), -70, -10, 70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -40, -8, 60, 8],
          [self.canvas.create_text(0, 0, text="VAR ? = ?????", font=("Helvetica", 8), fill='black'), 10, 2],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.var <= 0 or self.var > 99:
            try:
                self.var = int(tk.simpledialog.askstring("Variable", "Variablennummer [1-99]"))
            except:
                pass
        while self.value_type not in ('konstante', 'variable', 'terminal', 'analog'):
            r = tk.simpledialog.askstring(
                "Variable",
                "Zuzuweisender Wert:\n  1 = Konstante\n  2 = Variable (VAR1..VAR99)\n  3 = Terminal-Eingang (EA/EB/EC/ED)\n  4 = Analog-Eingang (EX/EY)")
            if r:
                r = r.strip()
                if r == '1' or r.lower() == 'konstante':
                    self.value_type = 'konstante'
                elif r == '2' or r.lower() == 'variable':
                    self.value_type = 'variable'
                elif r == '3' or r.lower().startswith('terminal'):
                    self.value_type = 'terminal'
                elif r == '4' or r.lower().startswith('analog'):
                    self.value_type = 'analog'
        if self.value_type == 'konstante':
            while self.value is None:
                try:
                    self.value = int(tk.simpledialog.askstring("Variable", "Konstanter Wert"))
                except:
                    pass
            display_val = str(self.value)
        elif self.value_type == 'variable':
            while not (isinstance(self.value, int) and 1 <= self.value <= 99):
                try:
                    self.value = int(tk.simpledialog.askstring("Variable", "Quell-Variablennummer [1-99]"))
                except:
                    pass
            display_val = f"VAR{self.value}"
        elif self.value_type == 'terminal':
            while self.value not in ('EA', 'EB', 'EC', 'ED'):
                r = tk.simpledialog.askstring("Variable", "Terminal-Eingang [EA / EB / EC / ED]")
                if r:
                    self.value = r.upper().strip()
            display_val = self.value
        else:  # analog
            while self.value not in ('EX', 'EY'):
                r = tk.simpledialog.askstring("Variable", "Analog-Eingang [EX / EY]")
                if r:
                    self.value = r.upper().strip()
            display_val = self.value
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[4]['element'], text=f"VAR {self.var} = {display_val}")
    def to_fti(self):
        import FTI
        if self.value_type == 'konstante':
            src = FTI.constant(self.value)
        elif self.value_type == 'variable':
            src = FTI.variable(self.value)
        elif self.value_type == 'terminal':
            src = FTI.terminal(self.value)
        else:  # analog
            src = FTI.analog(self.value)
        return FTI.Variable(self.var, src)


class VergleichBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.var = 0
        self.operator = '='
        self.compare_type = None   # 'konstante' | 'variable' | 'terminal'
        self.compare_value = None  # int for konstante/variable, str ('EA'..'ED') for terminal
        self.rightJ = True         # True: J (condition met) goes right, N goes bottom
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
    def getConnections(self):
        return [[0,-39,False],[0,39,True],[79,0,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-35,self.x+75,self.y+35]
    def onUserCreated(self):
        while self.var <= 0 or self.var > 99:
            try:
                self.var = int(tk.simpledialog.askstring("Vergleich", "Variablennummer [1-99]"))
            except:
                pass
        while self.operator not in ['=', '>', '<', '>=', '<=']:
            r = tk.simpledialog.askstring("Vergleich", "Vergleichsoperator [= / > / < / >= / <=]")
            if r:
                self.operator = r.strip()
        while self.compare_type not in ('konstante', 'variable', 'terminal'):
            r = tk.simpledialog.askstring(
                "Vergleich",
                "Vergleichstyp:\n  1 = Konstante\n  2 = Variable (VAR1..VAR99)\n  3 = Terminal-Eingang (EA/EB/EC/ED)")
            if r:
                r = r.strip()
                if r == '1' or r.lower() == 'konstante':
                    self.compare_type = 'konstante'
                elif r == '2' or r.lower() == 'variable':
                    self.compare_type = 'variable'
                elif r == '3' or r.lower().startswith('terminal'):
                    self.compare_type = 'terminal'
        if self.compare_type == 'konstante':
            while self.compare_value is None:
                try:
                    self.compare_value = int(tk.simpledialog.askstring("Vergleich", "Konstanter Vergleichswert"))
                except:
                    pass
            display_val = str(self.compare_value)
        elif self.compare_type == 'variable':
            while not (isinstance(self.compare_value, int) and 1 <= self.compare_value <= 99):
                try:
                    self.compare_value = int(tk.simpledialog.askstring("Vergleich", "Vergleichs-Variablennummer [1-99]"))
                except:
                    pass
            display_val = f"VAR{self.compare_value}"
        else:  # terminal
            while self.compare_value not in ('EA', 'EB', 'EC', 'ED'):
                r = tk.simpledialog.askstring("Vergleich", "Terminal-Eingang [EA / EB / EC / ED]")
                if r:
                    self.compare_value = r.upper().strip()
            display_val = self.compare_value
        r = ''
        while r not in ('J', 'N'):
            val = tk.simpledialog.askstring("Vergleich", "Verzweigung rechts bei [J/N]")
            if val:
                r = val.upper().strip()
        self.rightJ = (r == 'J')
        self.canvas.itemconfigure(self.elements[4]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], text='J' if self.rightJ else 'N')
        self.canvas.itemconfigure(self.elements[6]['element'], text='N' if self.rightJ else 'J')
        self.canvas.itemconfigure(self.elements[7]['element'],
                                  text=f"V{self.var} {self.operator} {display_val}")
    def to_fti(self):
        import FTI
        if self.compare_type == 'konstante':
            target = FTI.constant(self.compare_value)
        elif self.compare_type == 'variable':
            target = FTI.variable(self.compare_value)
        else:  # terminal
            target = FTI.terminal(self.compare_value)
        # >= and <= are implemented as their complements (< and >) with J/N swapped
        fti_op = {'=': '=', '>': '>', '<': '<', '>=': '<', '<=': '>'}[self.operator]
        return FTI.Vergleich(self.var, target, fti_op)
    def get_fti_slot(self, conn_idx):
        # rightJ=True:  right=J(slot 0/on_true),  bottom=N(slot 1/on_false)
        # rightJ=False: right=N(slot 1/on_false), bottom=J(slot 0/on_true)
        # >= / <= use complement operator, so true/false are swapped at FTI level
        flip = self.operator in ('>=', '<=')
        if conn_idx == 1:   # bottom
            slot = 1 if self.rightJ else 0
        elif conn_idx == 2:  # right
            slot = 0 if self.rightJ else 1
        else:
            return 0
        return (1 - slot) if flip else slot


class MotorBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.motor_num = 0
        self.motor_dir = 'aus'
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
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.motor_num <= 0 or self.motor_num > 8:
            try:
                self.motor_num = int(tk.simpledialog.askstring("Motor", "Motornummer [1-8]"))
            except:
                pass
        dir_str = ''
        while dir_str not in ['links', 'rechts', 'aus']:
            r = tk.simpledialog.askstring("Motor", "Richtung [links/rechts/aus]")
            if r:
                dir_str = r.lower()
        self.motor_dir = dir_str
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], text=f"M{self.motor_num} {dir_str.upper()}")
    def to_fti(self):
        import FTI
        dir_map = {'links': FTI.Richtung.LINKS, 'rechts': FTI.Richtung.RECHTS, 'aus': FTI.Richtung.AUS}
        return FTI.Motor(self.motor_num, dir_map[self.motor_dir])


class LampeBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.lamp_num = 0
        self.lamp_on = False
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), -15, -8, 55, 8],
          [self.canvas.create_text(0, 0, text="Lampe", font=("Helvetica", 11), fill='black'), -40, 2],
          [self.canvas.create_text(0, 0, text="? AUS", font=("Helvetica", 10), fill='black'), 20, 2],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.lamp_num <= 0 or self.lamp_num > 8:
            try:
                self.lamp_num = int(tk.simpledialog.askstring("Lampe", "Lampennummer [1-8]"))
            except:
                pass
        on_str = ''
        while on_str not in ['ein', 'aus']:
            r = tk.simpledialog.askstring("Lampe", "Schalten [ein/aus]")
            if r:
                on_str = r.lower()
        self.lamp_on = (on_str == 'ein')
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], text=f"L{self.lamp_num} {'EIN' if self.lamp_on else 'AUS'}")
    def to_fti(self):
        import FTI
        return FTI.Lampe(self.lamp_num, self.lamp_on)


class WarteBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.wait_ms = 0
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
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]
    def onUserCreated(self):
        while self.wait_ms <= 0:
            try:
                val = tk.simpledialog.askstring("Warte", "Wartezeit in Millisekunden")
                if val:
                    self.wait_ms = int(val)
            except:
                pass
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[5]['element'], text=f"{self.wait_ms/1000:.1f}s")
    def to_fti(self):
        import FTI
        return FTI.Warte(self.wait_ms)


class NotausResetBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.eingang = 0
    def objects(self):
      objs = [
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='white'), -60, -10, 60, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), -70, -10, -50, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='grey'), 50, -10, 70, 10],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='pink', outline='black'), 10, -8, 50, 7],
          [self.canvas.create_text(0, 0, text="E ?", font=("Helvetica", 11), fill='black'), 30, 2],
          ]
      return objs
    def getBoundingBox(self):
        return [self.x-70,self.y-10,self.x+70,self.y+10]
    def onUserCreated(self):
        while self.eingang <= 0 or self.eingang > 26:
            try:
                self.eingang = int(tk.simpledialog.askstring("Eingang", "Eingangsnummer [1-26]"))
            except:
                pass
        self.canvas.itemconfigure(self.elements[3]['element'], fill='white')
        self.canvas.itemconfigure(self.elements[4]['element'], text=f"E {self.eingang}")


class NotausBaustein(NotausResetBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="NOTAUS", font=("Helvetica", 10), fill='red'), -20, 2])
        return objs
    def to_fti(self):
        import FTI
        return FTI.NotAus(self.eingang)


class ResetBaustein(NotausResetBaustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
    def objects(self):
        objs = super().objects()
        objs.append([self.canvas.create_text(0, 0, text="RESET", font=("Helvetica", 10), fill='blue'), -20, 2])
        return objs
    def to_fti(self):
        import FTI
        return FTI.Reset(self.eingang)


class MeldungBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.text = ''
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_text(0, 0, text="", font=("Helvetica", 8), fill='black'), 0, 2],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]


class DisplayBaustein(Baustein):
    def __init__(self, canvas, x=None, y=None):
        super().__init__(canvas, x, y)
        self.text = ''
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill='white', outline='black'), -60, -10, 70, -10, 60, 10, -70, 10],
          [self.canvas.create_text(0, 0, text="", font=("Helvetica", 8), fill='black'), 0, 2],
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False],[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+15]


class SubProgramEingang(Baustein):
    def __init__(self, canvas, index=1, x=None, y=None, label=None):
        self.index = index
        self.label = label or f"I{index}"
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, 10, 0, 20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='#e0ffe0'), -60, -10, 60, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='#90cc90'), -70, -10, -50, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='#90cc90'), 50, -10, 70, 10],
          [self.canvas.create_text(0, 0, text=self.label, font=("Helvetica", 12), fill='darkgreen'), 0, 2]
          ]
      return objs
    def getConnections(self):
        return [[0,19,True]]
    def getBoundingBox(self):
        return [self.x-70,self.y-10,self.x+70,self.y+15]


class SubProgramAusgang(Baustein):
    def __init__(self, canvas, index=1, x=None, y=None, label=None):
        self.index = index
        self.label = label or f"O{index}"
        super().__init__(canvas, x, y)
    def objects(self):
      objs = [
          [self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -10, 0, -20],
          [self.canvas.create_rectangle(0, 0, 0, 0, fill='#ffe0e0'), -60, -10, 60, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='#cc9090'), -70, -10, -50, 10],
          [self.canvas.create_oval(0, 0, 0, 0, fill='#cc9090'), 50, -10, 70, 10],
          [self.canvas.create_text(0, 0, text=self.label, font=("Helvetica", 12), fill='darkred'), 0, 2]
          ]
      return objs
    def getConnections(self):
        return [[0,-19,False]]
    def getBoundingBox(self):
        return [self.x-70,self.y-15,self.x+70,self.y+10]


class BausteinBaustein(Baustein):
    def __init__(self, canvas, subprogram=None, x=None, y=None):
        self.subprogram = subprogram
        super().__init__(canvas, x, y)
    def _io_counts(self):
        if self.subprogram:
            return self.subprogram.num_inputs, self.subprogram.num_outputs
        return 1, 1
    def _half_height(self):
        ni, no = self._io_counts()
        return max(10, 10 + max(ni - 1, no - 1) * 15)
    def objects(self):
        ni, no = self._io_counts()
        hh = self._half_height()
        name = self.subprogram.name if self.subprogram else "UP?"
        objs = []
        objs.append([self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, -hh, 0, -(hh+10)])
        for i in range(1, ni):
            y = -hh + 10 + (i-1) * 30
            objs.append([self.canvas.create_line(0,0,0,0, fill='green', width=3), -70, y, -80, y])
        objs.append([self.canvas.create_line(0,0,0,0, fill='green', width=3), 0, hh, 0, hh+10])
        for i in range(1, no):
            y = -hh + 10 + (i-1) * 30
            objs.append([self.canvas.create_line(0,0,0,0, fill='green', width=3), 70, y, 80, y])
        objs.append([self.canvas.create_polygon(0,0,0,0,0,0,0,0, fill='#ffffcc', outline='black'),
                     -60, -hh, 70, -hh, 60, hh, -70, hh])
        objs.append([self.canvas.create_text(0,0, text=name, font=("Helvetica", 12), fill='black'), 0, 2])
        return objs
    def getConnections(self):
        ni, no = self._io_counts()
        hh = self._half_height()
        conns = []
        conns.append([0, -(hh+9), False])
        for i in range(1, ni):
            conns.append([-79, -hh + 10 + (i-1) * 30, False])
        conns.append([0, hh+9, True])
        for i in range(1, no):
            conns.append([79, -hh + 10 + (i-1) * 30, True])
        return conns
    def getBoundingBox(self):
        ni, no = self._io_counts()
        hh = self._half_height()
        left = -75 if ni > 1 else -70
        right = 75 if no > 1 else 70
        return [self.x+left, self.y-(hh+5), self.x+right, self.y+(hh+5)]
    def toString(self):
        name = self.subprogram.name if self.subprogram else "?"
        return f"Unterprogramm {name} at ({self.x};{self.y})"


class SubProgramSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent, sub_programs):
        self.sub_programs = sub_programs
        super().__init__(parent, "Unterprogramm")
    def body(self, master):
        tk.Label(master, text="Unterprogramm wählen oder neu erstellen:").pack(pady=(5,2))
        self.listbox = tk.Listbox(master, selectmode=tk.SINGLE,
                                  height=min(10, len(self.sub_programs) + 2), width=35)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.listbox.insert(tk.END, "Neu erstellen...")
        for prog in self.sub_programs:
            self.listbox.insert(tk.END, f"{prog.name}  ({prog.num_inputs} Ein / {prog.num_outputs} Aus)")
        self.listbox.selection_set(0)
        return self.listbox
    def apply(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            self.result = 'new'
        else:
            self.result = self.sub_programs[idx - 1]


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
            elif self.selected_item == "Position":
              PositionBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Variable":
              VariableBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Vergleich":
              VergleichBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Motor":
              MotorBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Lampe":
              LampeBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Warte":
              WarteBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Notaus":
              NotausBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Reset":
              ResetBaustein(self.canvas, 100, 50)
            elif self.selected_item == "Unterprogramm":
              BausteinBaustein(self.canvas, None, 100, 50)
            else:
              self.canvas.create_text(100, 50, text=self.selected_item, font=("Arial", 14))

    def apply(self):
        # When OK is pressed, return the selected item
        self.result = self.selected_item


mode = Mode.NONE
bs = None
fixed = True
bausteine = []
connections = []  # each entry: [from_baustein, from_conn_idx, to_baustein, to_conn_idx]
drawFrom = None

def function_rightclick(event):
    global bs, fixed, innercanvas, drawFrom, mode
    #print("rightclick, mode="+str(mode)+", event="+str(event))
    if mode == Mode.INSERT and bs is not None:
      #print("cancel insert")
      bs.delete()
      bs = None
      fixed = True
      mode = Mode.NONE
      innercanvas.configure(cursor="arrow")
    elif event is not None and (mode == Mode.LINK or mode == Mode.NONE):
      #print("make connection?")
      for b in bausteine:
        if b is None:
          continue
        pos = b.getPosition()
        conn = b.getConnections()
        n = 0
        for c in conn:
          if c is None:
            continue
          x=pos[0]+c[0]
          y=pos[1]+c[1]
          if abs(x-event.x)<=5 and abs(y-event.y)<=5:
            #print("check drawFrom and mode...")
            if drawFrom is None and c[2] and mode == Mode.NONE:
              #print("start conn")
              innercanvas.configure(cursor="dotbox")
              drawFrom = [b,n,x,y]
              mode = Mode.LINK
            elif drawFrom is not None and not c[2] and mode == Mode.LINK:
              print("searching path from "+drawFrom[0].toString()+", item no "+str(drawFrom[1])+" @("+str(drawFrom[2])+","+str(drawFrom[3])+") to "+b.toString()+", item no "+str(n)+" @("+str(x)+","+str(y)+")")
              innercanvas.configure(cursor="arrow")
              try:
                path = simple_route(drawFrom[2:4], [x,y])
                print("path: "+str(path))
                drawPath(path)
                connections.append([drawFrom[0], drawFrom[1], b, n])
              except Exception as e:
                print(f"Exception: {type(e).__name__}")
                print(f"Details: {e}")
                print("Call Stack:")
                traceback.print_exc()
              drawFrom = None
              mode = Mode.NONE
          n = n+1
    elif event is None:
      innercanvas.configure(cursor="arrow")
      drawFrom = None

def redraw_grid():
  for x in range(0, canvas_width, 50):
    innercanvas.create_line(x, 0, x, canvas_height, dash=(4, 2), fill="gray")
  for y in range(0, canvas_height, 50):
    innercanvas.create_line(0, y, canvas_width, y, dash=(4, 2), fill="gray")

def newProject():
  global programs
  if not messagebox.askyesno("Neu", "Neues Projekt erstellen? Nicht gespeicherte Änderungen gehen verloren."):
    return
  function_rightclick(None)
  for prog in programs:
    for b in prog.bausteine:
      if b is not None:
        b.delete()
  innercanvas.delete("all")
  redraw_grid()
  programs.clear()
  main_prog = SubProgram("$Main")
  programs.append(main_prog)
  switch_program(main_prog)


def _parse_mdl(filepath):
  """Parse an LLWin 2.1 MDL file and return a list of block dicts.

  Uses struct-based parsing of the MDL binary format:
  - Program headers (0x18 bytes, linked list)
  - 0xEC blocks with element linked lists (0x44 bytes each)
  - 0x70 block type definitions (BAUSTEIN catalog)
  - Connection data sections (parameters in sub_data)

  Element type is identified via block_type_ptr (offset 0x20) → Block70 self_ptr.
  Position is at offset 0x06 (x) and 0x08 (y) in the element struct.
  """
  with open(filepath, 'rb') as f:
    data = f.read()

  def _u16(o): return struct.unpack_from('<H', data, o)[0]
  def _u32(o): return struct.unpack_from('<I', data, o)[0]
  def _i32(o): return struct.unpack_from('<i', data, o)[0]
  def _str(o, n):
    end = data.find(b'\x00', o, o + n)
    if end < 0: end = o + n
    return data[o:end].rstrip(b' ').decode('ascii', errors='replace')

  block70_map = {}   # self_ptr → type name
  ec_self_map = {}   # 0xEC block self_ptr → block_name (for subprogram call resolution)
  ec_blocks = []     # list of (block_name, [elem_dicts])
  pos = 0

  # Pass 1: walk program headers, parse blocks and elements
  while pos + 0x18 <= len(data):
    next_ptr = _u32(pos)
    flags = _u16(pos + 16)
    blp = _u32(pos + 20)
    is_main = (flags & 1) != 0
    pos += 0x18

    if is_main:
      var_sz = _u32(pos + 12)
      pos += 0x1C
      if var_sz > 0:
        pos += var_sz
      if blp != 0:
        while pos + 0x70 <= len(data):
          bname = _str(pos + 4, 16)
          sp = _u32(pos + 0x6C)
          block70_map[sp] = bname
          np = _u32(pos)
          pos += 0x70
          if np == 0:
            break
    else:
      while pos + 0xEC <= len(data):
        blk_name = _str(pos + 4, 16)
        nout = _u16(pos + 0x18)
        ninp = _u16(pos + 0x1A)
        ep = _u32(pos + 0x1C)
        ec_sp = _u32(pos + 0x20)
        otp = _u32(pos + 0x30)
        inp = _u32(pos + 0x34)
        np = _u32(pos)
        if ec_sp != 0:
          ec_self_map[ec_sp] = blk_name
        pos += 0xEC

        if otp != 0 and nout > 0:
          pos += nout * 6
        if inp != 0 and ninp > 0:
          pos += ninp * 6

        elems = []
        if ep != 0:
          while pos + 0x44 <= len(data):
            enp = _u32(pos)
            class_id = _u16(pos + 0x04)
            x = _u16(pos + 0x06)
            y = _u16(pos + 0x08)
            nop = _u16(pos + 0x0A)
            nic = _u16(pos + 0x0C)
            nda = _u16(pos + 0x0E)
            ts = _u16(pos + 0x10)
            opp = _u32(pos + 0x14)
            icp = _u32(pos + 0x18)
            dap = _u32(pos + 0x1C)
            btp = _u32(pos + 0x20)
            self_ptr = _u32(pos + 0x2C)
            pos += 0x44

            pin_targets = []
            conn_pins = []
            if opp != 0 and nop > 0:
              for pi in range(nop):
                pin_targets.append(_u32(pos + pi * 0x14))
                conn_pins.append(_u32(pos + pi * 0x14 + 0x0C))
              pos += nop * 0x14
            if icp != 0 and nic > 0:
              pos += nic * 6
            da_data = b''
            if dap != 0 and nda > 0:
              da_data = data[pos:pos + nda * 8]
              pos += nda * 8
            pin_waypoints = []
            for cp in conn_pins:
              wps = []
              if cp != 0:
                while pos + 8 <= len(data):
                  cn = _u32(pos)
                  wp_x = _u16(pos + 4)
                  wp_y = _u16(pos + 6)
                  wps.append((wp_x, wp_y))
                  pos += 8
                  if cn == 0:
                    break
              pin_waypoints.append(wps)

            elems.append({'type': '', 'x': x, 'y': y, 'type_size': ts,
                          'nop': nop, 'nic': nic, 'nda': nda,
                          'btp': btp, 'self_ptr': self_ptr,
                          'pin_targets': pin_targets, 'class_id': class_id,
                          'da_data': da_data, 'pin_waypoints': pin_waypoints})
            if enp == 0:
              break

        ec_blocks.append((blk_name, elems))
        if np == 0:
          break

    if next_ptr == 0:
      break

  # Resolve element types now that block70_map is populated
  for blk_name, elems in ec_blocks:
    for e in elems:
      e['type'] = block70_map.get(e['btp'], '')

  # Pass 2: parse connection data sections (one per 0xEC block)
  # Extract parameters from sub_data for each element
  for blk_name, elems in ec_blocks:
    entry_idx = 0
    while pos + 2 <= len(data):
      tid = _u16(pos)
      pos += 2
      if tid == 0:
        break

      blobs = []
      for _ in range(3):
        sz = _i32(pos)
        pos += 4
        if sz > 0:
          blobs.append(data[pos:pos + sz])
          pos += sz
        else:
          blobs.append(b'')

      sub_ind = _i32(pos)
      pos += 4
      sub_data = b''
      if sub_ind == -1:
        def _skip_recursive():
          nonlocal pos
          while pos + 2 <= len(data):
            t = _u16(pos)
            pos += 2
            if t == 0:
              break
            for _ in range(3):
              s = _i32(pos)
              pos += 4
              if s > 0:
                pos += s
            si = _i32(pos)
            pos += 4
            if si == -1:
              _skip_recursive()
            elif si > 0:
              pos += si
        _skip_recursive()
      elif sub_ind > 0:
        sub_data = data[pos:pos + sub_ind]
        pos += sub_ind

      if entry_idx < len(elems):
        elems[entry_idx]['sub_data'] = sub_data
        elems[entry_idx]['blobs'] = blobs
      entry_idx += 1

  # Pass 3: build result list with parameters extracted from sub_data
  blocks = []
  entry_count = {}
  exit_count = {}
  for blk_name, elems in ec_blocks:
    for e in elems:
      tname = e['type']
      cid = e.get('class_id', 0)

      # Subprogram call (cls=0x2100) or graphic subprogram ref (cls=0x2700 with nop>0)
      if e['type_size'] == 0 and cid in (0x2100, 0x2700) and len(e.get('pin_targets', [])) > 0:
        target_name = ec_self_map.get(e['btp'], '')
        blk = {'type': 'BAUSTEIN', 'x': e['x'], 'y': e['y'], 'params': '',
               'block_name': blk_name, 'self_ptr': e.get('self_ptr', 0),
               'pin_targets': e.get('pin_targets', []),
               'pin_waypoints': e.get('pin_waypoints', []),
               'subprogram_name': target_name}
        blocks.append(blk)
        continue

      # Subprogram entry node (cls low byte 0x2D): nop>=1, nic=0
      if (cid & 0xFF) == 0x2D and e.get('nop', 0) > 0:
        idx = entry_count.get(blk_name, 0) + 1
        entry_count[blk_name] = idx
        da = e.get('da_data', b'')
        label = da.split(b'\x00')[0].decode('latin-1', errors='replace') if da else ''
        blk = {'type': 'SUBPROGRAM_EINGANG', 'x': e['x'], 'y': e['y'], 'params': '',
               'block_name': blk_name, 'self_ptr': e.get('self_ptr', 0),
               'pin_targets': e.get('pin_targets', []),
               'pin_waypoints': e.get('pin_waypoints', []),
               'entry_index': idx, 'entry_label': label}
        blocks.append(blk)
        continue

      # Subprogram exit node (cls low byte 0x2C): nop=0, nic>=1
      if (cid & 0xFF) == 0x2C and e.get('nic', 0) > 0:
        idx = exit_count.get(blk_name, 0) + 1
        exit_count[blk_name] = idx
        da = e.get('da_data', b'')
        label = da.split(b'\x00')[0].decode('latin-1', errors='replace') if da else ''
        blk = {'type': 'SUBPROGRAM_AUSGANG', 'x': e['x'], 'y': e['y'], 'params': '',
               'block_name': blk_name, 'self_ptr': e.get('self_ptr', 0),
               'pin_targets': e.get('pin_targets', []),
               'pin_waypoints': e.get('pin_waypoints', []),
               'exit_index': idx, 'exit_label': label}
        blocks.append(blk)
        continue

      # Text annotations (cls 0x2042/0x2142): free-floating text on canvas
      if cid in (0x2042, 0x2142) and e.get('nda', 0) > 1:
        da = e.get('da_data', b'')
        txt = da[8:].split(b'\x00')[0].decode('latin-1', errors='replace').replace('\r', '\n') if len(da) > 8 else ''
        if txt.strip():
          blk = {'type': 'TEXT_ANNOTATION', 'x': e['x'], 'y': e['y'], 'params': txt.strip(),
                 'block_name': blk_name, 'self_ptr': e.get('self_ptr', 0),
                 'pin_targets': []}
          blocks.append(blk)
        continue

      if not tname or e['type_size'] == 0:
        continue

      sub = e.get('sub_data', b'')
      da = e.get('da_data', b'')
      blk = {'type': tname, 'x': e['x'], 'y': e['y'], 'params': '',
             'block_name': blk_name, 'self_ptr': e.get('self_ptr', 0),
             'pin_targets': e.get('pin_targets', []),
             'pin_waypoints': e.get('pin_waypoints', [])}

      if tname == 'MOTOR' or tname == 'LAMPE':
        if len(sub) > 4:
          num_byte = sub[4]
          if 0x31 <= num_byte <= 0x38:
            blk['num'] = num_byte - 0x30
        if len(sub) >= 448:
          dir_bytes = sub[440:448].split(b'\x00')[0]
          blk['direction'] = dir_bytes.decode('ascii', errors='replace').strip()
          d = blk.get('direction', '')
          if d in ('RECHTS', 'LINKS'):
            blk['type'] = 'MOTOR'
          elif d == 'EIN':
            blk['type'] = 'LAMPE'
          tname = blk['type']

      elif tname == 'WARTE':
        if len(sub) >= 12:
          blk['wait_seconds'] = struct.unpack_from('<d', sub, 4)[0]

      elif tname == 'EINGANG':
        if len(sub) >= 424:
          eid = sub[416:424].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          for ch in eid:
            if ch.isdigit():
              blk['eingang_num'] = int(ch)
              break
        elif len(sub) > 8:
          eid = sub[4:8].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          for ch in eid:
            if ch.isdigit():
              blk['eingang_num'] = int(ch)
              break
        if len(sub) >= 432:
          ron_byte = sub[428]
          if ron_byte in (0x30, 0x31):
            blk['right_on'] = ron_byte - 0x30

      elif tname == 'FLANKE':
        if len(sub) > 8:
          eid = sub[4:8].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          for ch in eid:
            if ch.isdigit():
              blk['eingang_num'] = int(ch)
              break

      elif tname == 'VARIABLE':
        if len(sub) > 8:
          ps = sub[4:20].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          blk['params'] = ps

      elif tname == 'VERGLEICH':
        if len(sub) > 8:
          ps = sub[4:20].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          blk['params'] = ps

      elif tname in ('INCVARIABLE', 'DECVARIABLE'):
        if len(sub) > 8:
          ps = sub[4:20].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          blk['params'] = ps

      elif tname in ('NOTAUS', 'RESET'):
        if len(sub) > 8:
          eid = sub[4:8].split(b'\x00')[0].decode('ascii', errors='replace').strip()
          blk['params'] = eid

      elif tname == 'MELDUNG':
        if da:
          blk['meldung_text'] = da.split(b'\x00')[0].decode('latin-1', errors='replace')

      elif tname == 'DISPLAY':
        if da:
          blk['display_text'] = da.split(b'\x00')[0].decode('latin-1', errors='replace')

      blocks.append(blk)

  return blocks


def _parse_motor_params(param_str):
  """Parse Motor param string like 'M1 RECHTS' or 'RECHTS' → (motor_num, direction)."""
  parts = param_str.upper().split()
  motor_num = 1
  direction = 'aus'
  for p in parts:
    if p.startswith('M') and len(p) >= 2 and p[1:].isdigit():
      motor_num = int(p[1:])
    elif p in ('LINKS', 'RECHTS', 'AUS', 'EIN'):
      direction = p.lower()
  return motor_num, direction


def _parse_lampe_params(param_str):
  """Parse Lampe param string → (lamp_num, on)."""
  parts = param_str.upper().split()
  lamp_num = 1
  on = False
  for p in parts:
    if p.startswith('L') and len(p) >= 2 and p[1:].isdigit():
      lamp_num = int(p[1:])
    elif p == 'EIN':
      on = True
    elif p == 'AUS':
      on = False
  return lamp_num, on


def _parse_eingang_num(param_str):
  """Parse 'E  1' or 'E 12' → integer."""
  for part in param_str.split():
    if part.isdigit():
      return int(part)
  return 1


def _parse_variable_params(param_str):
  """Parse 'VAR  1 = 0' or 'VAR 1=EX' → (var_num, value_type, value)."""
  var_num = 1
  value_type = 'konstante'
  value = 0
  parts = param_str.replace('=', ' = ').split()
  for i, p in enumerate(parts):
    if p.upper().startswith('VAR') and i + 1 < len(parts) and parts[i + 1].isdigit():
      var_num = int(parts[i + 1])
    elif p == '=' and i + 1 < len(parts):
      rhs = parts[i + 1].strip()
      if rhs.upper().startswith('VAR') and rhs[3:].isdigit():
        value_type = 'variable'
        value = int(rhs[3:])
      elif rhs.upper() in ('EA', 'EB', 'EC', 'ED'):
        value_type = 'terminal'
        value = rhs.upper()
      elif rhs.upper() in ('EX', 'EY'):
        value_type = 'analog'
        value = rhs.upper()
      else:
        try:
          value = int(rhs)
        except ValueError:
          pass
  return var_num, value_type, value


def _parse_warte_params(param_str):
  """Parse warte time string → milliseconds."""
  try:
    val = float(param_str.replace(',', '.').strip())
    return int(val * 1000)
  except ValueError:
    return 1000


def _create_baustein(blk):
  """Create a GUI Baustein from a parsed block dict. Returns the Baustein or None."""
  btype = blk['type']
  bx, by = blk['x'], blk['y']
  params = blk['params']
  bs = None

  if btype == 'START':
    bs = StartBaustein(innercanvas, bx, by)

  elif btype == 'ENDE':
    bs = EndeBaustein(innercanvas, bx, by)

  elif btype == 'MOTOR':
    bs = MotorBaustein(innercanvas, bx, by)
    motor_num = blk.get('num', 1)
    direction = blk.get('direction', 'AUS').lower()
    bs.motor_num = motor_num
    bs.motor_dir = direction
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[5]['element'],
                              text=f"M{motor_num} {direction.upper()}")

  elif btype == 'LAMPE':
    bs = LampeBaustein(innercanvas, bx, by)
    lamp_num = blk.get('num', 1)
    direction = blk.get('direction', 'AUS')
    on = direction.upper() == 'EIN'
    bs.lamp_num = lamp_num
    bs.lamp_on = on
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[5]['element'],
                              text=f"L{lamp_num} {'EIN' if on else 'AUS'}")

  elif btype == 'EINGANG':
    bs = EingangBaustein(innercanvas, bx, by)
    bs.eingang = blk.get('eingang_num', _parse_eingang_num(params))
    bs.rightOn = blk.get('right_on', 0)
    innercanvas.itemconfigure(bs.elements[4]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[7]['element'], text=f"E {bs.eingang}")

  elif btype == 'FLANKE':
    bs = FlankeBaustein(innercanvas, bx, by)
    bs.eingang = blk.get('eingang_num', _parse_eingang_num(params))
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[5]['element'], text=f"E {bs.eingang}")

  elif btype == 'VARIABLE':
    bs = VariableBaustein(innercanvas, bx, by)
    var_num, value_type, value = _parse_variable_params(params)
    bs.var = var_num
    bs.value_type = value_type
    bs.value = value
    if value_type == 'konstante':
      display_val = str(value)
    elif value_type == 'variable':
      display_val = f"VAR{value}"
    elif value_type in ('terminal', 'analog'):
      display_val = str(value)
    else:
      display_val = '?'
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[4]['element'],
                              text=f"VAR {var_num} = {display_val}")

  elif btype == 'VERGLEICH':
    bs = VergleichBaustein(innercanvas, bx, by)
    bs.var = 1
    bs.operator = '='
    bs.compare_type = 'konstante'
    bs.compare_value = 0
    _parse_vergleich_from_params(bs, params)
    innercanvas.itemconfigure(bs.elements[4]['element'], fill='white')
    if bs.compare_type == 'konstante':
      dv = str(bs.compare_value)
    elif bs.compare_type == 'variable':
      dv = f"VAR{bs.compare_value}"
    else:
      dv = str(bs.compare_value)
    innercanvas.itemconfigure(bs.elements[7]['element'],
                              text=f"V{bs.var} {bs.operator} {dv}")

  elif btype == 'INCVARIABLE':
    bs = IncBaustein(innercanvas, bx, by)
    bs.var = _parse_eingang_num(params)
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[4]['element'], text=f"VAR {bs.var}")

  elif btype == 'DECVARIABLE':
    bs = DecBaustein(innercanvas, bx, by)
    bs.var = _parse_eingang_num(params)
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[4]['element'], text=f"VAR {bs.var}")

  elif btype == 'WARTE':
    bs = WarteBaustein(innercanvas, bx, by)
    if 'wait_seconds' in blk:
      bs.wait_ms = int(blk['wait_seconds'] * 1000)
    else:
      bs.wait_ms = _parse_warte_params(params)
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    secs = bs.wait_ms / 1000
    if secs == int(secs):
      time_str = f"{int(secs)}s"
    else:
      time_str = f"{secs}s"
    innercanvas.itemconfigure(bs.elements[5]['element'], text=time_str)

  elif btype == 'POSITION':
    bs = PositionBaustein(innercanvas, bx, by)
    bs.countervar = _parse_eingang_num(params)
    bs.eingang = 1
    bs.target_value = 0
    bs.decrement = False
    innercanvas.itemconfigure(bs.elements[4]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[5]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[6]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[11]['element'],
                              text=f"VAR {bs.countervar}")

  elif btype == 'BEEP':
    bs = BeepBaustein(innercanvas, bx, by)

  elif btype == 'NOTAUS':
    bs = NotausBaustein(innercanvas, bx, by)
    bs.eingang = _parse_eingang_num(params)
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[4]['element'], text=f"E {bs.eingang}")

  elif btype == 'RESET':
    bs = ResetBaustein(innercanvas, bx, by)
    bs.eingang = _parse_eingang_num(params)
    innercanvas.itemconfigure(bs.elements[3]['element'], fill='white')
    innercanvas.itemconfigure(bs.elements[4]['element'], text=f"E {bs.eingang}")

  elif btype == 'MELDUNG':
    bs = MeldungBaustein(innercanvas, bx, by)
    txt = blk.get('meldung_text', '') or params
    bs.text = txt
    innercanvas.itemconfigure(bs.elements[2]['element'], fill='#e0e0ff')
    innercanvas.itemconfigure(bs.elements[3]['element'], text=txt if txt else 'Meldung')

  elif btype == 'DISPLAY':
    bs = DisplayBaustein(innercanvas, bx, by)
    txt = blk.get('display_text', '') or params
    bs.text = txt
    innercanvas.itemconfigure(bs.elements[2]['element'], fill='#ffe0e0')
    innercanvas.itemconfigure(bs.elements[3]['element'], text=txt if txt else 'Display')

  elif btype == 'BAUSTEIN':
    sub_name = blk.get('subprogram_name', '')
    sub_prog = None
    for p in programs:
      if p.name == sub_name:
        sub_prog = p
        break
    if sub_prog is None and sub_name:
      sub_prog = SubProgram(sub_name)
    bs = BausteinBaustein(innercanvas, sub_prog, bx, by)

  elif btype == 'SUBPROGRAM_EINGANG':
    idx = blk.get('entry_index', 1)
    label = blk.get('entry_label', '') or None
    bs = SubProgramEingang(innercanvas, idx, bx, by, label=label)

  elif btype == 'SUBPROGRAM_AUSGANG':
    idx = blk.get('exit_index', 1)
    label = blk.get('exit_label', '') or None
    bs = SubProgramAusgang(innercanvas, idx, bx, by, label=label)

  return bs


def openProject():
  global programs
  filepath = filedialog.askopenfilename(
      title="MDL-Datei öffnen",
      filetypes=[("LLWin MDL", "*.mdl *.MDL"), ("Alle Dateien", "*.*")])
  if not filepath:
    return

  try:
    blocks = _parse_mdl(filepath)
  except Exception as e:
    messagebox.showerror("Fehler", f"MDL-Datei konnte nicht gelesen werden:\n{e}")
    traceback.print_exc()
    return

  # Clear current project
  function_rightclick(None)
  for prog in programs:
    for b in prog.bausteine:
      if b is not None:
        b.delete()
  innercanvas.delete("all")
  programs.clear()

  # Blocks extend up to ~80px left / ~40px above their (x,y) position.
  # Tk Canvas clips at (0,0), so shift all positions to keep every bounding
  # box visible. The waypoint coordinate transform uses block positions, so
  # it inherits the shift automatically.
  global canvas_width, canvas_height
  BB_LEFT = 80
  BB_TOP = 40
  min_x = min((blk['x'] for blk in blocks), default=BB_LEFT) - BB_LEFT
  min_y = min((blk['y'] for blk in blocks), default=BB_TOP) - BB_TOP
  pad_x = max(0, -min_x)
  pad_y = max(0, -min_y)
  if pad_x or pad_y:
    for blk in blocks:
      blk['x'] += pad_x
      blk['y'] += pad_y
  max_x = 1000
  max_y = 750
  for blk in blocks:
    max_x = max(max_x, blk['x'] + 200)
    max_y = max(max_y, blk['y'] + 200)
  canvas_width = max_x
  canvas_height = max_y
  innercanvas.configure(width=canvas_width, height=canvas_height)
  redraw_grid()

  # Group blocks by subprogram (block_name)
  from collections import OrderedDict
  prog_blocks = OrderedDict()
  for blk in blocks:
    pname = blk.get('block_name', '$Main')
    if pname not in prog_blocks:
      prog_blocks[pname] = []
    prog_blocks[pname].append(blk)

  if not prog_blocks:
    prog_blocks['$Main'] = []

  # Create all SubProgram objects first so BAUSTEIN blocks can find targets
  prog_objs = {}
  for prog_name, blks in prog_blocks.items():
    ni = sum(1 for b in blks if b['type'] == 'SUBPROGRAM_EINGANG')
    no = sum(1 for b in blks if b['type'] == 'SUBPROGRAM_AUSGANG')
    prog = SubProgram(prog_name, ni, no)
    programs.append(prog)
    prog_objs[prog_name] = prog

  skipped = []
  created = 0
  conn_count = 0

  for prog_name, prog_blks in prog_blocks.items():
    switch_program(prog_objs[prog_name])

    for blk in prog_blks:
      if blk['type'] == 'TERMINAL':
        skipped.append(blk['type'])
        continue

      if blk['type'] == 'TEXT_ANNOTATION':
        txt = blk.get('params', '')
        tid = innercanvas.create_text(blk['x'], blk['y'], text=txt,
                                      font=("Helvetica", 10), fill='#444444',
                                      anchor='nw')
        prog_objs[prog_name].text_annotations.append(tid)
        created += 1
        continue

      bs = _create_baustein(blk)
      if bs is None:
        skipped.append(blk['type'])
        continue

      bausteine.append(bs)
      blk['_baustein'] = bs
      created += 1

    # Wire connections within this subprogram
    sp_to_blk = {}
    for blk in prog_blks:
      sp = blk.get('self_ptr', 0)
      if sp != 0:
        sp_to_blk[sp] = blk

    for blk in prog_blks:
      from_bs = blk.get('_baustein')
      if from_bs is None:
        continue
      from_conns = from_bs.getConnections()
      out_indices = [i for i, c in enumerate(from_conns) if c[2]]
      for pin_idx, target_ptr in enumerate(blk.get('pin_targets', [])):
        if target_ptr == 0 or pin_idx >= len(out_indices):
          continue
        target_blk = sp_to_blk.get(target_ptr)
        if target_blk is None:
          continue
        to_bs = target_blk.get('_baustein')
        if to_bs is None:
          continue
        from_conn_idx = out_indices[pin_idx]
        to_conns = to_bs.getConnections()
        in_indices = [i for i, c in enumerate(to_conns) if not c[2]]
        if not in_indices:
          continue
        to_conn_idx = in_indices[0]
        from_pos = from_bs.getPosition()
        to_pos = to_bs.getPosition()
        fc = from_conns[from_conn_idx]
        tc = to_conns[to_conn_idx]
        start = [from_pos[0] + fc[0], from_pos[1] + fc[1]]
        end = [to_pos[0] + tc[0], to_pos[1] + tc[1]]
        try:
          wps = blk.get('pin_waypoints', [])
          wp_chain = wps[pin_idx] if pin_idx < len(wps) else []
          if len(wp_chain) >= 2:
            llwin_src = wp_chain[-1]
            dx = start[0] - llwin_src[0]
            dy = start[1] - llwin_src[1]
            path = [start]
            for wi in range(len(wp_chain) - 2, 0, -1):
              wx, wy = wp_chain[wi]
              path.append([wx + dx, wy + dy])
            path.append(end)
          else:
            path = simple_route(start, end)
          drawPath(path)
          connections.append([from_bs, from_conn_idx, to_bs, to_conn_idx])
          conn_count += 1
        except Exception:
          pass

  for blk in blocks:
    blk.pop('_baustein', None)

  # Switch to $Main (or first program)
  main = next((p for p in programs if p.name == '$Main'), programs[0])
  switch_program(main)

  import os
  fname = os.path.basename(filepath)
  prog_names = [p.name for p in programs]
  msg = f"{fname}: {created} Bausteine, {conn_count} Verbindungen geladen."
  if len(programs) > 1:
    msg += f"\nUnterprogramme: {', '.join(prog_names)}"
  if skipped:
    from collections import Counter
    skip_counts = Counter(skipped)
    skip_str = ', '.join(f"{n}x {t}" for t, n in skip_counts.items())
    msg += f"\nÜbersprungen: {skip_str}"
  messagebox.showinfo("MDL geladen", msg)


def _parse_vergleich_from_params(bs, params):
  """Parse Vergleich param string and set fields on bs."""
  for op in ['>=', '<=', '>', '<', '=']:
    if op in params:
      parts = params.split(op, 1)
      lhs = parts[0].strip()
      rhs = parts[1].strip() if len(parts) > 1 else '0'
      # LHS: "VAR  1" or "V1"
      for p in lhs.replace('VAR', '').replace('V', '').split():
        if p.isdigit():
          bs.var = int(p)
          break
      bs.operator = op
      # RHS
      rhs = rhs.strip()
      if rhs.upper().startswith('VAR') and rhs[3:].strip().isdigit():
        bs.compare_type = 'variable'
        bs.compare_value = int(rhs[3:].strip())
      elif rhs.upper() in ('EA', 'EB', 'EC', 'ED'):
        bs.compare_type = 'terminal'
        bs.compare_value = rhs.upper()
      else:
        try:
          bs.compare_value = int(rhs)
        except ValueError:
          pass
      return


def insertBaustein():
  global bs, fixed, innercanvas, root, mode

  ## cancel current insertion (if any)
  function_rightclick(None)

  items = ["Beep", "Decrement Variable", "Display", "Eingang", "Ende", "Flanke", "Increment Variable", "Lampe", "Meldung", "Motor", "Notaus", "Position", "Reset", "Start", "Terminal", "Unterprogramm", "Variable", "Vergleich", "Warte"]
  dialog = ItemSelectionDialog(root, "Baustein auswählen", items)

  bs = None
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
  elif dialog.result == "Position":
    bs = PositionBaustein(innercanvas)
  elif dialog.result == "Variable":
    bs = VariableBaustein(innercanvas)
  elif dialog.result == "Vergleich":
    bs = VergleichBaustein(innercanvas)
  elif dialog.result == "Motor":
    bs = MotorBaustein(innercanvas)
  elif dialog.result == "Lampe":
    bs = LampeBaustein(innercanvas)
  elif dialog.result == "Warte":
    bs = WarteBaustein(innercanvas)
  elif dialog.result == "Notaus":
    bs = NotausBaustein(innercanvas)
  elif dialog.result == "Reset":
    bs = ResetBaustein(innercanvas)
  elif dialog.result == "Unterprogramm":
    sub_progs = [p for p in programs if p.name != "$Main" and p is not current_program]
    if not sub_progs:
      messagebox.showinfo("Unterprogramm",
                          "Keine Unterprogramme vorhanden.\n"
                          "Erstellen Sie zuerst eines über\nBearbeiten > Unterprogramm...")
    else:
      name = simpledialog.askstring("Unterprogramm einfügen",
                                    f"Welches Unterprogramm?\n({', '.join(p.name for p in sub_progs)})")
      if name:
        prog = next((p for p in sub_progs if p.name == name.strip()), None)
        if prog:
          bs = BausteinBaustein(innercanvas, prog)
        else:
          messagebox.showerror("Fehler", f"Unterprogramm '{name.strip()}' nicht gefunden.")
  elif dialog.result:
    print("ERROR: not implemented yet")
  else:
    print("No item selected.")

  if bs is not None:
    fixed = False
    mode = Mode.INSERT

def removeBaustein():
  ## cancel current insertion (if any)
  global mode
  function_rightclick(None)
  mode = Mode.REMOVE
  innercanvas.configure(cursor="arrow")
  pass

def callback_motion(event):
    global bs, fixed, drawFrom
    if not fixed and bs:
      x, y = event.x, event.y
      bs.position(x,y)

def callback(event):
    global bs, fixed, mode
    fixed = True
    if bs is not None:
      bs.onUserCreated()
      bausteine.append(bs)
      bs = None
      mode = Mode.NONE


def _inline_subprograms(main_prog):
  """Build a flat FTI graph from the main program, inlining all BausteinBaustein calls."""
  import FTI as fti_module

  fti_map = {}      # gui block id → FTI object (main program blocks only)
  all_fti = []      # all FTI objects for root detection

  # bb_inp:  (BausteinBaustein id, inp_index 1-based) → FTI object that INP connects TO
  # bb_outp: (BausteinBaustein id, outp_index 1-based) → (FTI object, slot) before OUTP
  bb_inp = {}
  bb_outp = {}

  for b in main_prog.bausteine:
    if b is None or isinstance(b, EndeBaustein):
      continue
    if isinstance(b, BausteinBaustein):
      sp = b.subprogram
      if sp is None:
        continue
      sp_fti = {}
      for sb in sp.bausteine:
        if isinstance(sb, (SubProgramEingang, SubProgramAusgang, EndeBaustein)):
          continue
        fti_obj = sb.to_fti()
        if fti_obj is not None:
          sp_fti[id(sb)] = fti_obj
          all_fti.append(fti_obj)
      for conn in sp.connections:
        sf, si, st, sti = conn
        if isinstance(sf, SubProgramEingang):
          if not isinstance(st, (SubProgramAusgang, EndeBaustein)):
            t = sp_fti.get(id(st))
            if t:
              bb_inp[(id(b), sf.index)] = t
          continue
        if isinstance(st, SubProgramAusgang):
          s = sp_fti.get(id(sf))
          if s:
            bb_outp[(id(b), st.index)] = (s, sf.get_fti_slot(si))
          continue
        fti_from = sp_fti.get(id(sf))
        if fti_from is None:
          continue
        if isinstance(st, EndeBaustein):
          fti_from.set_successor(None, sf.get_fti_slot(si))
        else:
          fti_to = sp_fti.get(id(st))
          if fti_to:
            fti_from.set_successor(fti_to, sf.get_fti_slot(si))
      continue
    fti_obj = b.to_fti()
    if fti_obj is not None:
      fti_map[id(b)] = fti_obj
      all_fti.append(fti_obj)

  def _resolve_target(to_b, to_idx):
    if isinstance(to_b, EndeBaustein):
      return None, True
    if isinstance(to_b, BausteinBaustein):
      bb_conns = to_b.getConnections()
      in_indices = [i for i, c in enumerate(bb_conns) if not c[2]]
      try:
        order = in_indices.index(to_idx)
      except ValueError:
        return None, False
      t = bb_inp.get((id(to_b), order + 1))
      return t, t is not None
    t = fti_map.get(id(to_b))
    return t, t is not None

  for conn in main_prog.connections:
    from_b, from_idx, to_b, to_idx = conn

    if isinstance(from_b, BausteinBaustein):
      bb_conns = from_b.getConnections()
      out_indices = [i for i, c in enumerate(bb_conns) if c[2]]
      try:
        order = out_indices.index(from_idx)
      except ValueError:
        continue
      info = bb_outp.get((id(from_b), order + 1))
      if info is None:
        continue
      fti_source, slot = info
      fti_target, ok = _resolve_target(to_b, to_idx)
      if ok:
        fti_source.set_successor(fti_target, slot)
      continue

    fti_from = fti_map.get(id(from_b))
    if fti_from is None:
      continue
    fti_target, ok = _resolve_target(to_b, to_idx)
    if ok:
      fti_from.set_successor(fti_target, from_b.get_fti_slot(from_idx))

  has_incoming = set()
  for conn in main_prog.connections:
    has_incoming.add(id(conn[2]))

  prog = fti_module.Program()
  for b in main_prog.bausteine:
    if b is None or isinstance(b, (EndeBaustein, BausteinBaustein)):
      continue
    if id(b) not in has_incoming:
      fti_obj = fti_map.get(id(b))
      if fti_obj is not None:
        prog.add_baustein(fti_obj)
  return prog

def runAktivModus():
  port = tk.simpledialog.askstring("Aktiv-Modus", "Serieller Port:", initialvalue="/dev/ttyUSB0")
  if not port:
    return
  try:
    from FTI_com import compile_and_send_program
    prog = _inline_subprograms(programs[0])
    compile_and_send_program(prog, port)
    messagebox.showinfo("Aktiv-Modus", "Programm erfolgreich übertragen!")
  except Exception as e:
    messagebox.showerror("Fehler beim Kompilieren", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


def switch_program(prog):
    global current_program, bausteine, connections, drawn_path_segments, path_anchor_stubs
    function_rightclick(None)
    if current_program is not None:
        for b in current_program.bausteine:
            for e in b.elements:
                innercanvas.itemconfigure(e['element'], state='hidden')
        for lid in current_program.connection_lines:
            innercanvas.itemconfigure(lid, state='hidden')
        for tid in current_program.text_annotations:
            innercanvas.itemconfigure(tid, state='hidden')
    current_program = prog
    bausteine = prog.bausteine
    connections = prog.connections
    drawn_path_segments = prog.drawn_path_segments
    path_anchor_stubs = prog.path_anchor_stubs
    for b in prog.bausteine:
        for e in b.elements:
            innercanvas.itemconfigure(e['element'], state='normal')
    for lid in prog.connection_lines:
        innercanvas.itemconfigure(lid, state='normal')
    for tid in prog.text_annotations:
        innercanvas.itemconfigure(tid, state='normal')
    root.title(f"LLWin Nachbau — {prog.name}")
    update_window_menu()

def update_window_menu():
    last = wndwmenu.index(tk.END)
    if last is not None and last >= 7:
        wndwmenu.delete(7, tk.END)
    wndwmenu.add_separator()
    for i, prog in enumerate(programs):
        wndwmenu.add_command(label=f"{i+1}: {prog.name}",
                             command=lambda p=prog: switch_program(p))

def createSubProgram():
    sub_progs = [p for p in programs if p.name != "$Main"]
    dialog = SubProgramSelectionDialog(root, sub_progs)
    if dialog.result is None:
        return
    if isinstance(dialog.result, SubProgram):
        switch_program(dialog.result)
        return
    name = simpledialog.askstring("Neues Unterprogramm", "Name (z.B. UP1):")
    if not name:
        return
    name = name.strip()
    if name.startswith("$"):
        messagebox.showerror("Fehler", "Name darf nicht mit '$' beginnen.")
        return
    for prog in programs:
        if prog.name == name:
            messagebox.showerror("Fehler", f"Unterprogramm '{name}' existiert bereits.")
            return
    num_inputs = simpledialog.askinteger("Neues Unterprogramm", "Anzahl Eingangspfade:",
                                         initialvalue=1, minvalue=1, maxvalue=8)
    if num_inputs is None:
        return
    num_outputs = simpledialog.askinteger("Neues Unterprogramm", "Anzahl Ausgangspfade:",
                                          initialvalue=1, minvalue=1, maxvalue=8)
    if num_outputs is None:
        return
    prog = SubProgram(name, num_inputs, num_outputs)
    programs.append(prog)
    switch_program(prog)
    spacing = 150
    start_x = max(200, (canvas_width - (max(num_inputs, num_outputs) - 1) * spacing) // 2)
    for i in range(num_inputs):
        inp = SubProgramEingang(innercanvas, i + 1, start_x + i * spacing, 50)
        bausteine.append(inp)
    for i in range(num_outputs):
        outp = SubProgramAusgang(innercanvas, i + 1, start_x + i * spacing, 650)
        bausteine.append(outp)

def deleteSubProgram():
    sub_names = [p.name for p in programs if p.name != "$Main"]
    if not sub_names:
        messagebox.showinfo("Löschen", "Keine Unterprogramme vorhanden.")
        return
    name = simpledialog.askstring("Unterprogramm löschen",
                                  f"Name des zu löschenden Unterprogramms\n({', '.join(sub_names)}):")
    if not name:
        return
    name = name.strip()
    prog = None
    for p in programs:
        if p.name == name:
            prog = p
            break
    if prog is None or prog.name == "$Main":
        messagebox.showerror("Fehler", f"Unterprogramm '{name}' nicht gefunden.")
        return
    if not messagebox.askyesno("Löschen", f"Unterprogramm '{name}' wirklich löschen?"):
        return
    if current_program is prog:
        switch_program(programs[0])
    for b in prog.bausteine:
        if b is not None:
            b.delete()
    for lid in prog.connection_lines:
        innercanvas.delete(lid)
    programs.remove(prog)
    update_window_menu()


root = tk.Tk()
root.title("LLWin Nachbau")
root.geometry("800x600+"+str(int((root.winfo_screenwidth()-800)/2))+"+"+str(int((root.winfo_screenheight()-600)/2)))
menu = tk.Menu(root)
root.config(menu=menu)
filemenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Datei", menu=filemenu)
filemenu.add_command(label="Neu...", command=newProject)
filemenu.add_command(label="Öffnen...", command=openProject)
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
editmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Bearbeiten", menu=editmenu)
editmenu.add_command(label="Hauptprogramm", command=lambda: switch_program(programs[0]))
editmenu.add_command(label="Unterprogramm...", command=createSubProgram)
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
subprogmenu.add_command(label="Löschen...", command=deleteSubProgram)
subprogmenu.add_command(label="Attribute...")
runmenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Run", menu=runmenu)
runmenu.add_command(label="Init")
runmenu.add_command(label="Start")
runmenu.add_command(label="Stop")
runmenu.add_separator()
runmenu.add_command(label="Aktiv-Modus", command=runAktivModus)
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

# Place the canvas and scrollbars
canvas.grid(row=0, column=0, sticky="nsew")
scrollbar_y.grid(row=0, column=1, sticky="ns")
scrollbar_x.grid(row=1, column=0, sticky="ew")

# Configure the grid to make the canvas expandable
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

# Create a frame inside the canvas
frame = tk.Frame(canvas)

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


canvas_width, canvas_height = 1000, 750  # Size larger than the window
innercanvas = tk.Canvas(frame, bg="white", width=canvas_width, height=canvas_height)
innercanvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

redraw_grid()

main_prog = SubProgram("$Main")
programs.append(main_prog)
switch_program(main_prog)

innercanvas.bind("<Motion>", callback_motion)
innercanvas.bind("<Button-1>", callback)
innercanvas.bind("<Button-3>", function_rightclick)

# Run the application
root.mainloop()

print("the following Bausteine have been created:")
for prog in programs:
  print(f"  [{prog.name}]")
  for b in prog.bausteine:
    if b is not None:
      print(f"    {b.toString()}")

exit(0)
