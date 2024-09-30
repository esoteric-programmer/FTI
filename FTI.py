from abc import ABC, abstractmethod
from enum import IntEnum

# not implemented yet: Terminal, Ton, Unterprogramm
# not implemented: Meldung, Display, Ende (Ende: implizit!)
# not tested yet: Variable, Position, Vergleich, ... mit einer anderen Eingabe als einer Konstanten

class Richtung(IntEnum):
    LINKS = 1
    RECHTS = 2
    AUS = 3

class inputvalue(ABC):
  @abstractmethod
  def __init__(self):
    pass
  @property
  def type(self):
    return self._type
  @property
  def value(self):
    return self._value

class constant(inputvalue):
  def __init__(self, value):
    self._type = 1
    self._value = value

class variable(inputvalue):
  def __init__(self, variable):
    if variable < 1 or variable > 99:
      raise RuntimeException("invalid variable VAR"+str(variable))
    self._type = 2
    self._value = variable

class terminal(inputvalue):
  def __init__(self, eingang: str):
    self._type = 3
    if eingang == 'EA':
      self._value = 1
    elif eingang == 'EB':
      self._value = 2
    elif eingang == 'EC':
      self._value = 3
    elif eingang == 'ED':
      self.value = 4
    else:
      raise RuntimeException("invalid terminal input "+eingang)

class analog(inputvalue):
  def __init__(self, eingang: str):
    self._type = 4
    if eingang == 'EX':
      self._value = 5
    elif eingang == 'EY':
      self.value = 6
    else:
      raise RuntimeException("invalid analog input "+eingang)

def split_num(num: int, steps: int):
  return str(num//steps)+"."+str(num%steps)

class Baustein(ABC):
    def __init__(self):
        self._successor = []
        self._id = 0 ## not set
        #print("init id")
    def set_id(self, id):
      #print("set id")
      self._id = id
    @property
    @abstractmethod
    def incoming_trans(self):
        pass
    @property
    def outgoing_trans(self):
        return len(self._successor)
    @property
    @abstractmethod
    def num_M2(self): # only additional messages needed
        pass
    @property
    @abstractmethod
    def num_PT(self):
        pass
    @property
    @abstractmethod
    def num_PL(self):
        pass
    @property
    @abstractmethod
    def num_DL(self):
        pass
    def _set_successor(self, succ: 'Baustein', slot):
        if slot < 0 or slot >= self.outgoing_trans:
            raise RuntimeError("Ungültiger Nachfolger-Slot")
        if not succ.incoming_trans:
          raise RuntimeError("Baustein ohne eingehende Verbindung kann nicht als Nachfolger definiert werden")
        self._successor[slot] = succ
    def successor(self, succ: 'Baustein'):
      if self.outgoing_trans != 1:
        raise RuntimeError("Es existiert kein eindeutiger Nachfolger bei diesem Bausteintyp")
      self._set_successor(succ,0)
    def on_true(self, succ: 'Baustein'):
      if self.outgoing_trans != 2:
        raise RuntimeError("Dieser Bausteintyp implementiert keine bedingte Verzweigung")
      self._set_successor(succ,0)
    def on_false(self, succ: 'Baustein'):
      if self.outgoing_trans != 2:
        raise RuntimeError("Dieser Bausteintyp implementiert keine bedingte Verzweigung")
      self._set_successor(succ,1)
    def get_successor(self, slot):
      if slot < 0 or slot >= self.outgoing_trans:
        return None
      return self._successor[slot]
    @abstractmethod
    def get_q_code(self, offset_M1, offset_M2, offset_PT, offset_PL, offset_DL):
        pass
    def _get_successor_id(self, slot):
      succ = self.get_successor(slot)
      if succ is None:
        return 0
      if succ._id <= 0:
        raise RuntimeError("Cannot generate q code without knowing my successor's ID")
      return succ._id
    def _abs_code(self,slot: int, condition: str):
      return ":1\n:"+str(self._id)+"\n:1\n:"+str(self._get_successor_id(slot))+"\n:"+condition+"\n"



class Start(Baustein):
    def __init__(self):
        Baustein.__init__(self)
        self._successor = [None]
    @property
    def incoming_trans(self):
        return False
    @property
    def num_M2(self): # only additional messages needed
        return 2
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&Inif\n:M"+split_num(offset_M2,8)+"\n:M"+split_num(offset_M2+1,8)+"\n:M"+split_num(offset_M1,8)+"\n:A11.0\n:A13.0\n:A1.0\n:M1.0\n:DW1\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2+1,8))
        return [baustein_code, abs_code]




class Motor(Baustein):
    def __init__(self, motor: int, direction: Richtung):
        Baustein.__init__(self)
        if motor <= 0 or motor > 8:
          raise RuntimeError("Ungültige Motornummer: "+str(motor))
        self._successor = [None]
        self._motor = motor
        self._direction = int(direction)
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 0
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&SMOT\n:"+str(self._direction)+"\n:M"+split_num(offset_M1,8)+"\n:A"+str(self._motor)+".1\n:A"+str(self._motor)+".0\n"
        abs_code = self._abs_code(0,"M0.0")
        return [baustein_code, abs_code]


class Lampe(Motor):
    def __init__(self, lampe: int, on: bool):
      if lampe <= 0 or lampe > 8:
        raise RuntimeError("Ungültige Lampennummer: "+str(lampe))
      Motor.__init__(self,lampe,Richtung.RECHTS if on else Richtung.AUS)


class Eingang(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._successor = [None, None]
        self._eingang = eingang
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 1
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&Not\n:E"+str(self._eingang)+".0\n:M"+split_num(offset_M2,8)+"\n"
        abs_code = self._abs_code(0,"E"+str(self._eingang)+".0")
        abs_code = abs_code + self._abs_code(1,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]


class Flanke(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._successor = [None]
        self._eingang = eingang
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 2
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&FD10\n:E"+str(self._eingang)+".0\n:M"+split_num(offset_M2,8)+"\n:M"+split_num(offset_M2+1,8)+"\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]




class Variable(Baustein):
    def __init__(self, var: int, value: inputvalue):
        Baustein.__init__(self)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Variable: "+str(eingang))
        if value is None:
          raise RuntimeError("Ungültiges Ziel: is None")
        if value.type <= 0 or value.type > 4:
          raise RuntimeError("Ungültiger zugewiesener Wert. Must be Constant, Variable, Terminal Input, or Analog Input")
        self._successor = [None]
        self._target = value
        self._countervar = var
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 2
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&SVAR\n:"+str(self._target.type)+"\n:"+str(self._target.value)+"\n:DW107\n:M"+split_num(offset_M1,8)+"\n:DW"+str(self._countervar)+"\n:DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n:M"+split_num(offset_M2,8)+"\n:M"+split_num(offset_M2+1,8)+"\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]




class IncVariable(Baustein):
    def __init__(self, var: int):
        Baustein.__init__(self)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Variable: "+str(eingang))
        self._successor = [None]
        self._countervar = var
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 0
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&IVAR\n:2\n:M"+split_num(offset_M1,8)+"\n:DW"+str(self._countervar)+"\n"
        abs_code = self._abs_code(0,"M0.0")
        return [baustein_code, abs_code]


class DecVariable(Baustein):
    def __init__(self, var: int):
        Baustein.__init__(self)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Variable: "+str(eingang))
        self._successor = [None]
        self._countervar = var
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 0
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&IVAR\n:1\n:M"+split_num(offset_M1,8)+"\n:DW"+str(self._countervar)+"\n"
        abs_code = self._abs_code(0,"M0.0")
        return [baustein_code, abs_code]



class Vergleich(Baustein):
    def __init__(self, var: int, target: inputvalue, operator: str):
        Baustein.__init__(self)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Zählervariable: "+str(eingang))
        if target is None:
          raise RuntimeError("Ungültiges Ziel: is None")
        if target.type <= 0 or target.type > 3:
          raise RuntimeError("Ungültiges Ziel. Must be Constant, Variable, or Terminal Input")
        if operator == '=':
          self._operator = 1
        elif operator == '>':
          self._operator = 2
        elif operator == '<':
          self._operator = 3
        else:
          raise RuntimeError("Ungültiger Vergleichsoperator. Must be '=', '>', or '<', but was "+str(operator))
        self._successor = [None, None]
        self._target = target
        self._countervar = var
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 3
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&CMW\n:"+str(10*self._target.type+self._operator)+"\n:"+str(self._target.value)+"\n:DW107\n:DW"+str(self._countervar)+"\n:DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n:M"+split_num(offset_M2+1,8)+"\n::M"+split_num(offset_M2,8)+"\n:M"+split_num(offset_M2+2,8)+"\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2+1,8))
        abs_code = abs_code + self._abs_code(1,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]






class Position(Baustein):
    def __init__(self, eingang: int, target: inputvalue, countervar: int, decrement: bool):
        Baustein.__init__(self)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        if countervar <= 0 or countervar > 99:
          raise RuntimeError("Ungültige Zählervariable: "+str(eingang))
        if target is None:
          raise RuntimeError("Ungültiges Ziel: is None")
        if target.type <= 0 or target.type > 3:
          raise RuntimeError("Ungültiges Ziel. Must be Constant, Variable, or Terminal Input")
        self._successor = [None]
        self._eingang = eingang
        self._target = target
        self._countervar = countervar
        self._decrement = decrement
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 2
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&VRZF\n:"+str(self._target.type+(10 if self._decrement else 0))+"\n:"+str(self._target.value)+"\n:E"+str(self._eingang)+".0\n:M"+split_num(offset_M2,8)+"\n:DW"+str(self._countervar)+"\n:DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n:M"+split_num(offset_M2+1,8)+"\n:M"+split_num(offset_M1,8)+"\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]



class Reset(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self)
        self._successor = []
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._eingang = eingang
    @property
    def incoming_trans(self):
        return False
    @property
    def num_M2(self): # only additional messages needed
        return 0
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&ABB\n:E"+str(self._eingang)+".0\n:A13.0\n"
        abs_code = ""
        return [baustein_code, abs_code]



class NotAus(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self)
        self._successor = []
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._eingang = eingang
    @property
    def incoming_trans(self):
        return False
    @property
    def num_M2(self): # only additional messages needed
        return 0
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 0
    @property
    def num_DL(self):
        return 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&ABB\n:E"+str(self._eingang)+".0\n:A12.0\n"
        abs_code = ""
        return [baustein_code, abs_code]



class Warte(Baustein):
    def __init__(self, wait: int):
        Baustein.__init__(self)
        self._waittime = wait
        self._successor = [None]
    @property
    def incoming_trans(self):
        return True
    @property
    def num_M2(self): # only additional messages needed
        return 1
    @property
    def num_PT(self):
        return 0
    @property
    def num_PL(self):
        return 1
    @property
    def num_DL(self):
        return 2
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = "&EVF\n:PL"+str(offset_PL)+"\n:M"+split_num(offset_M1,8)+"\n:M"+split_num(offset_M2,8)+"\n:DL"+str(offset_DL)+"\n:DL"+str(offset_DL+1)+"\n#PL"+str(offset_PL)+"="+str(self._waittime)+"\n"
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]



class Program:
  def __init__(self):
    self._bausteine = []
  def add_baustein(self, baustein: Baustein):
    if baustein.incoming_trans:
      start = Start()
      start.successor(baustein)
      baustein = start
    self._bausteine.append(baustein)
  
  @staticmethod
  def _fill_successor_list(baustein: Baustein, liste):
    if baustein is None:
      return
    if baustein in liste:
      return
    liste.append(baustein)
    for i in range(0,baustein.outgoing_trans):
      Program._fill_successor_list(baustein.get_successor(i),liste)
  
  def _get_full_baustein_list(self):
    result = []
    

  def build_q_file(self):
    ## berechne benötigte Initialwerte
    offset_M1 = 8
    offset_M2 = 8
    offset_PT = 1
    offset_PL = 1
    offset_DL = 1
    ablauf_size = 0
    bausteinliste = []
    for baustein in self._bausteine:
      Program._fill_successor_list(baustein, bausteinliste)

    #print(bausteinliste)
    i = 1
    for baustein in bausteinliste:
      baustein.set_id(i)
      offset_M1 = offset_M1 + baustein.num_M2
      ablauf_size = ablauf_size + baustein.outgoing_trans
      i = i + (1 if baustein.outgoing_trans > 0 else 0) ## alles ohne ausgehende transitionen belegt keinen Platz in der Ablaufsteuerung
    q_header = "; Generated by Matthias Lutter's  Python Project\n"
    q_oben = "&BEG\n:10\n:15\n" # T_ms:10, Li_Nr:15
    q_unten = "&ABS\n:"+str(ablauf_size)+"\n:"+str(len(bausteinliste))+"\n:M"+split_num(offset_M1,8)+"\n:DW121\n:DW"+str(121+ablauf_size)+"\n:DW"+str(121+ablauf_size+1)+"\n:DW"+str(121+2*ablauf_size+1)+"\n:M0.0\n"
    q_footer = "&END\n:15" # Li_Nr:15
    
    for baustein in bausteinliste:
      q = baustein.get_q_code(offset_M1,offset_M2,offset_PT,offset_PL,offset_DL)
      q_oben = q_oben + q[0]
      q_unten = q_unten + q[1]
      offset_M1 = offset_M1 + (1 if baustein.outgoing_trans > 0 else 0) ## alles ohne ausgehende transitionen belegt keinen Platz in der Ablaufsteuerung
      offset_M2 = offset_M2 + baustein.num_M2
      offset_PT = offset_PT + baustein.num_PT
      offset_PL = offset_PL + baustein.num_PL
      offset_DL = offset_DL + baustein.num_DL
    return q_header + q_oben + q_unten + q_footer
