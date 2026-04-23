import tkinter as tk
from tkinter import simpledialog, messagebox
from abc import ABC, abstractmethod
from enum import Enum
import traceback

# Define the global enum
class Mode(Enum):
  NONE=0
  INSERT=1
  REMOVE=2
  LINK=3


## TODO
## save Baustein connections and canvas line objects in some datastructure so it can be considered when compiling the program...
## forbid duplicate connections
## speed up a* search, e.g. by searching on a graph instead of canvas pixels
## enhance bounding box // pixels occipied by Baustein
## handle impossible connections by disabling bounding box checks
## make Bausteine editable, moveable and removeable
## make connection moveable and deleteable
## subprograms
## implement missing Baustein classes: Display, Meldung, Terminal
## save project, open project (compatible to LLWin 2.1 file format??)
## passive mode



CROSSING_PENALTY  = 500   # extra cost per existing connection a new segment would cross
STUB_PENALTY      = 10000 # extra cost per anchor stub crossed (virtually blocked)
TURN_PENALTY      = 50    # extra cost for each direction change (prefer straight paths)
PATH_CLEARANCE    = 4     # minimum pixel distance from other path segments (parallel)
PROXIMITY_PENALTY = 200   # extra cost per parallel segment that's too close

drawn_path_segments = []  # all [p1, p2] segments of already-drawn connections
path_anchor_stubs   = []  # short virtual stubs sealing the gap between BB and anchor


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


def a_star(start, target):
  """A* on a Hanan grid for orthogonal routing.

  State: (node_id, direction) so that direction changes can be penalised.
  Direction encoding: 0=left 1=right 2=up 3=down  None=start (no penalty yet).
  The Manhattan-distance heuristic remains admissible because it never counts
  turn penalties, so it never over-estimates the true cost."""
  global bausteine, canvas_width, canvas_height

  start = (int(start[0]), int(start[1]))
  target = (int(target[0]), int(target[1]))

  if start == target:
    return [list(start)]

  MARGIN = 3
  MOVES  = [(-1, 0, 0), (1, 0, 1), (0, -1, 2), (0, 1, 3)]  # dix, diy, dir-id

  # Build Hanan grid: one x- and y-line through each significant coordinate
  xs = {start[0], target[0]}
  ys = {start[1], target[1]}
  for b in bausteine:
    bb = b.getBoundingBox()
    xs.add(bb[0] - MARGIN);  xs.add(bb[2] + MARGIN)
    ys.add(bb[1] - MARGIN);  ys.add(bb[3] + MARGIN)
  xs = sorted(x for x in xs if 0 <= x < canvas_width)
  ys = sorted(y for y in ys if 0 <= y < canvas_height)

  xi = {x: i for i, x in enumerate(xs)}
  yi = {y: i for i, y in enumerate(ys)}

  if start[0] not in xi or start[1] not in yi or target[0] not in xi or target[1] not in yi:
    return None

  cols = len(ys)
  rows = len(xs)
  def nid(ix, iy): return ix * cols + iy

  si = nid(xi[start[0]],  yi[start[1]])
  ti = nid(xi[target[0]], yi[target[1]])

  # g and prev are keyed by (node_id, direction); None direction = initial state
  g    = {}
  prev = {}
  start_state = (si, None)
  g[start_state] = 0.0
  open_set = [start_state]

  def h(node_id):
    ix, iy = divmod(node_id, cols)
    return abs(xs[ix] - target[0]) + abs(ys[iy] - target[1])

  while open_set:
    cs = min(open_set, key=lambda s: g[s] + h(s[0]))
    open_set.remove(cs)
    ci, cur_dir = cs

    if ci == ti:
      path = []
      state = cs
      while state is not None:
        node_id, _ = state
        ix, iy = divmod(node_id, cols)
        path.append([xs[ix], ys[iy]])
        state = prev.get(state)
      path.reverse()
      return path

    ix, iy = divmod(ci, cols)
    for dix, diy, new_dir in MOVES:
      nix, niy = ix + dix, iy + diy
      if nix < 0 or nix >= rows or niy < 0 or niy >= cols:
        continue
      x1, y1 = xs[ix],  ys[iy]
      x2, y2 = xs[nix], ys[niy]
      if _hv_segment_blocked(x1, y1, x2, y2, MARGIN):
        continue
      turn_cost = TURN_PENALTY if (cur_dir is not None and new_dir != cur_dir) else 0
      dist = abs(x2 - x1) + abs(y2 - y1)
      ng   = g[cs] + dist + turn_cost \
             + _crossing_cost(x1, y1, x2, y2) \
             + _proximity_cost(x1, y1, x2, y2)
      ni = nid(nix, niy)
      ns = (ni, new_dir)
      if g.get(ns, float('inf')) > ng:
        g[ns]    = ng
        prev[ns] = cs
        if ns not in open_set:
          open_set.append(ns)

  return None   # no path found


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
  global innercanvas, drawn_path_segments, path_anchor_stubs
  pathes = simplifyPath(path)
  arrow = 'last'
  for seg in reversed(pathes):
    innercanvas.create_line(seg[0][0], seg[0][1], seg[1][0], seg[1][1],
                            fill='green', width=3, arrow=arrow)
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
                path = a_star(drawFrom[2:4], [x,y])
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

def newProject():
  global bs, fixed, mode, drawFrom, bausteine, drawn_path_segments, path_anchor_stubs, connections
  if not messagebox.askyesno("Neu", "Neues Projekt erstellen? Nicht gespeicherte Änderungen gehen verloren."):
    return
  function_rightclick(None)
  for b in bausteine:
    if b is not None:
      b.delete()
  bausteine = []
  connections = []
  drawn_path_segments = []
  path_anchor_stubs = []
  innercanvas.delete("all")
  for x in range(0, canvas_width, 50):
    innercanvas.create_line(x, 0, x, canvas_height, dash=(4, 2), fill="gray")
  for y in range(0, canvas_height, 50):
    innercanvas.create_line(0, y, canvas_width, y, dash=(4, 2), fill="gray")

def insertBaustein():
  global bs, fixed, innercanvas, root, mode

  ## cancel current insertion (if any)
  function_rightclick(None)

  items = ["Beep", "Decrement Variable", "Display", "Eingang", "Ende", "Flanke", "Increment Variable", "Lampe", "Meldung", "Motor", "Notaus", "Position", "Reset", "Start", "Terminal", "Variable", "Vergleich", "Warte"]
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


def runAktivModus():
  global bausteine, connections
  port = tk.simpledialog.askstring("Aktiv-Modus", "Serieller Port:", initialvalue="/dev/ttyUSB0")
  if not port:
    return
  try:
    import FTI as fti_module
    from FTI_com import compile_and_send_program

    # Create FTI objects for all GUI Bausteine (except Ende which maps to None)
    fti_map = {}
    for b in bausteine:
      if b is None or isinstance(b, EndeBaustein):
        continue
      fti_obj = b.to_fti()
      if fti_obj is not None:
        fti_map[id(b)] = fti_obj

    # Link successors based on stored connections
    for conn in connections:
      from_b, from_conn_idx, to_b, to_conn_idx = conn
      fti_from = fti_map.get(id(from_b))
      if fti_from is None:
        continue
      if isinstance(to_b, EndeBaustein):
        fti_to = None
      else:
        fti_to = fti_map.get(id(to_b))
        if fti_to is None:
          continue
      slot = from_b.get_fti_slot(from_conn_idx)
      fti_from.set_successor(fti_to, slot)

    # Identify root Bausteine: those with no incoming connection in this graph
    has_incoming = set()
    for conn in connections:
      has_incoming.add(id(conn[2]))

    prog = fti_module.Program()
    for b in bausteine:
      if b is None or isinstance(b, EndeBaustein):
        continue
      if id(b) not in has_incoming:
        fti_obj = fti_map.get(id(b))
        if fti_obj is not None:
          prog.add_baustein(fti_obj)

    compile_and_send_program(prog, port)
    messagebox.showinfo("Aktiv-Modus", "Programm erfolgreich übertragen!")
  except Exception as e:
    messagebox.showerror("Fehler beim Kompilieren", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


root = tk.Tk()
root.title("LLWin Nachbau")
root.geometry("800x600+"+str(int((root.winfo_screenwidth()-800)/2))+"+"+str(int((root.winfo_screenheight()-600)/2)))
menu = tk.Menu(root)
root.config(menu=menu)
filemenu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="Datei", menu=filemenu)
filemenu.add_command(label="Neu...", command=newProject)
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
wndwmenu.add_command(label="1: $Main")
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

for x in range(0, canvas_width, 50):  # Vertical dashed lines every 50 pixels
        innercanvas.create_line(x, 0, x, canvas_height, dash=(4, 2), fill="gray")

for y in range(0, canvas_height, 50):  # Horizontal dashed lines every 50 pixels
        innercanvas.create_line(0, y, canvas_width, y, dash=(4, 2), fill="gray")




innercanvas.bind("<Motion>", callback_motion)
innercanvas.bind("<Button-1>", callback)
innercanvas.bind("<Button-3>", function_rightclick)

# Run the application
root.mainloop()

print("the following Bausteine have been created:")
for b in bausteine:
  if b is not None:
    print(b.toString())

exit(0)
