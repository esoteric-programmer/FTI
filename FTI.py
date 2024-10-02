from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Callable, List

# TODO: Unterprogramm
# not implemented: Meldung
# not tested yet: Variable, Position, Vergleich, ... mit einer anderen Eingabe als einer Konstanten

def Ende() -> 'Baustein': # Ende-Baustein wird durch None-Referenz abgebildet
  return None

class Richtung(IntEnum):
    LINKS = 1
    RECHTS = 2
    AUS = 3

class inputvalue(ABC):
  @abstractmethod
  def __init__(self):
    pass
  @property
  def type(self) -> int:
    return self._type
  @property
  def value(self) -> int:
    return self._value

class constant(inputvalue):
  def __init__(self, value: int):
    self._type = 1
    self._value = value

class variable(inputvalue):
  def __init__(self, variable: int):
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

def split_num(num: int, steps: int) -> str:
  return str(num//steps)+"."+str(num%steps)

class Baustein(ABC):
    def __init__(self, incoming: int, outgoing: int, M2: int, PT: int, PL: int, DL: int):
        self._successor = [None]*outgoing
        if incoming != 0 and incoming != 1:
          raise RuntimeException("unsupported number of incoming connections")
        self._incoming = (True if incoming>0 else False)
        self._M2 = M2
        self._PT = PT
        self._PL = PL
        self._DL = DL
        self._id = 0
    def set_id(self, id: int) -> None:
      self._id = id
    @property
    def incoming_trans(self) -> bool:
        return self._incoming
    @property
    def outgoing_trans(self) -> int:
        return len(self._successor)
    @property
    def num_M2(self) -> int: # only additional messages needed
        return self._M2
    @property
    def num_PT(self) -> int:
        return self._PT
    @property
    def num_PL(self) -> int:
        return self._PL
    @property
    def num_DL(self) -> int:
        return self._DL
    def _set_successor(self, succ: 'Baustein', slot: int) -> None:
        if slot < 0 or slot >= self.outgoing_trans:
            raise RuntimeError("Ungültiger Nachfolger-Slot")
        if succ is None:
          self._successor[slot] = succ
          return
        if not succ.incoming_trans:
          raise RuntimeError("Baustein ohne eingehende Verbindung kann nicht als Nachfolger definiert werden")
        self._successor[slot] = succ
    def successor(self, succ: 'Baustein') -> None:
      if self.outgoing_trans != 1:
        raise RuntimeError("Es existiert kein eindeutiger Nachfolger bei diesem Bausteintyp")
      self._set_successor(succ,0)
    def on_true(self, succ: 'Baustein') -> None:
      if self.outgoing_trans != 2:
        raise RuntimeError("Dieser Bausteintyp implementiert keine bedingte Verzweigung")
      self._set_successor(succ,0)
    def on_false(self, succ: 'Baustein') -> None:
      if self.outgoing_trans != 2:
        raise RuntimeError("Dieser Bausteintyp implementiert keine bedingte Verzweigung")
      self._set_successor(succ,1)
    def get_successor(self, slot: int) -> 'Baustein':
      if slot < 0 or slot >= self.outgoing_trans:
        return None
      return self._successor[slot]
    @abstractmethod
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        pass
    def _get_successor_id(self, slot: int) -> 'Baustein':
      succ = self.get_successor(slot)
      if succ is None:
        return 0
      if succ._id <= 0:
        raise RuntimeError("Cannot generate q code without knowing my successor's ID")
      return succ._id
    def _abs_code(self,slot: int, condition: str) -> str:
      return ":1\n:"+str(self._id)+"\n:1\n:"+str(self._get_successor_id(slot))+"\n:"+condition+"\n"



class Start(Baustein):
    def __init__(self):
        Baustein.__init__(self,0,1,2,0,0,0)
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&Inif\n" # Baustein
            ":M"+split_num(offset_M2,8)+"\n" # P0
            ":M"+split_num(offset_M2+1,8)+"\n" # P1: Baustein-Ausführung abgeschlossen (&ABS Wartebedingung)
            ":M"+split_num(offset_M1,8)+"\n" # SM: Starte Baustein-Ausführung (&ABS Array-Index)
            ":A11.0\n" # reset (TERMINAL-Baustein)
            ":A13.0\n" # reset (RESET-Baustein)
            ":A1.0\n"
            ":M1.0\n"
            ":DW1\n"
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2+1,8))
        return [baustein_code, abs_code]




class Motor(Baustein):
    def __init__(self, motor: int, direction: Richtung):
        Baustein.__init__(self,1,1,0,0,0,0)
        if motor <= 0 or motor > 8:
          raise RuntimeError("Ungültige Motornummer: "+str(motor))
        self._motor = motor
        self._direction = int(direction)
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&SMOT\n" # Baustein
            ":"+str(self._direction)+"\n" # Drehrichtung (1=LINKS, 2=RECHTS/LAMPE, 3=AUS)
            ":M"+split_num(offset_M1,8)+"\n" # P1: Starte Baustein-Ausführung (&ABS Array-Index)
            ":A"+str(self._motor)+".1\n" # SB2: Motorausgang 2
            ":A"+str(self._motor)+".0\n" # SB1: Motorausgang 1
            )
        abs_code = self._abs_code(0,"M0.0") # NO WAITING
        return [baustein_code, abs_code]


class Lampe(Motor):
    def __init__(self, lampe: int, on: bool):
      if lampe <= 0 or lampe > 8:
        raise RuntimeError("Ungültige Lampennummer: "+str(lampe))
      Motor.__init__(self,lampe,Richtung.RECHTS if on else Richtung.AUS)


class Eingang(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self,1,2,1,0,0,0)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._eingang = eingang
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&Not\n" # Baustein
            ":E"+str(self._eingang)+".0\n" # SB2: Eingang (ebenso &ABS Wartebedingung für True)
            ":M"+split_num(offset_M2,8)+"\n" # SB1: negierter Eingang -> &ABS Wartebedingung für False
            )
        abs_code = self._abs_code(0,"E"+str(self._eingang)+".0") # TRUE
        abs_code = abs_code + self._abs_code(1,"M"+split_num(offset_M2,8)) # FALSE
        return [baustein_code, abs_code]


class Flanke(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self,1,1,2,0,0,0)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._eingang = eingang
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&FD10\n" # Baustein
            ":E"+str(self._eingang)+".0\n" # EIMPULS: Eingang
            ":M"+split_num(offset_M2,8)+"\n" # QIMPULS: Baustein-Ausführung abgeschlossen (&ABS Wartebedingung)
            ":M"+split_num(offset_M2+1,8)+"\n" # MIMPULS: interner Zustand
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]



class Variable(Baustein):
    def __init__(self, var: int, value: inputvalue):
        Baustein.__init__(self,1,1,2,0,0,0)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Variable: "+str(eingang))
        if value is None:
          raise RuntimeError("Ungültiges Ziel: is None")
        if value.type <= 0 or value.type > 4:
          raise RuntimeError("Ungültiger zugewiesener Wert. Must be Constant, Variable, Terminal Input, or Analog Input")
        self._target = value
        self._countervar = var
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&SVAR\n" # Baustein
            ":"+str(self._target.type)+"\n" # Quelltyp: 1: constant, 2: variable, 3: terminal, 4: analog
            ":"+str(self._target.value)+"\n" # Quellwert: Wert der Konstanten oder Variablennummer oder Eingansnummer (EA=1, EB=, EC=3, ED=4, EX=5, EY=6)
            ":DW107\n" # TEMP-Variable (?)
            ":M"+split_num(offset_M1,8)+"\n" # P1: Starte Baustein-Ausführung (&ABS Array-Index)
            ":DW"+str(self._countervar)+"\n" # Var1: Zielvariable
            ":DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n" # Var2: Quellvariable oder DW0, falls eine Konstantenzuweisung erfolgt
            ":M"+split_num(offset_M2,8)+"\n" # Trans: Baustein-Ausführung abgeschlossen (&ABS Wartebedingung)
            ":M"+split_num(offset_M2+1,8)+"\n" # State: interner Zustand
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]


# Genau wie Variablenzusweisung, wobei die Zielvariable entweder 109 (DISPLAY 1) oder 110 (DISPLAY 2) ist
class Display(Variable):
    def __init__(self, display: int, value: inputvalue):
      if display != 1 and display != 2:
        raise RuntimeError("Ungültiges Display: "+str(display))
      Variable.__init__(self,1,value)
      self._countervar = 109+display


class IncVariable(Baustein):
    def __init__(self, var: int):
        Baustein.__init__(self,1,1,0,0,0,0)
        if var <= 0 or var > 99:
          raise RuntimeError("Ungültige Variable: "+str(eingang))
        self._countervar = var
        self._inc = 2
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&IVAR\n" # Baustein
            ":"+str(self._inc)+"\n" # 2: Increment, 1: Decrement
            ":M"+split_num(offset_M1,8)+"\n" # P1: Starte Baustein-Ausführung (&ABS Array-Index)
            ":DW"+str(self._countervar)+"\n" # Var: zu inkrementierende Variable
            )
        abs_code = self._abs_code(0,"M0.0") # NO WAITING
        return [baustein_code, abs_code]


# Wie Increment, aber setze Verhalten auf 1
class DecVariable(IncVariable):
    def __init__(self, var: int):
        IncVariable.__init__(self, var)
        self._inc = 1


class Vergleich(Baustein):
    def __init__(self, var: int, target: inputvalue, operator: str):
        Baustein.__init__(self,1,2,3,0,0,0)
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
        self._target = target
        self._countervar = var
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&CMW\n" # Baustein
            ":"+str(10*self._target.type+self._operator)+"\n" # 1: =, 2: >, 3: <; addiere Vergleichswert: 10: constant, 20: variable, 30: terminal
            ":"+str(self._target.value)+"\n" # Vergleichswert: Wert der Konstanten oder Variablennummer oder Eingansnummer (EA=1, EB=, EC=3, ED=4)
            ":DW107\n" # TEMP-Variable (?)
            ":DW"+str(self._countervar)+"\n" # W1: Variable
            ":DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n" # W2: Vergleichswert (oder DW0, falls konstante)
            ":M"+split_num(offset_M2+1,8)+"\n" # SB: &ABS Wartebedingung für True
            ":M"+split_num(offset_M2,8)+"\n" # SB1: &ABS Wartebedingung für False
            ":M"+split_num(offset_M2+2,8)+"\n" # State: interner Zustand
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2+1,8)) # TRUE
        abs_code = abs_code + self._abs_code(1,"M"+split_num(offset_M2,8)) # FALSE
        return [baustein_code, abs_code]



class Position(Baustein):
    def __init__(self, eingang: int, target: inputvalue, countervar: int, decrement: bool):
        Baustein.__init__(self,1,1,2,0,0,0)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        if countervar <= 0 or countervar > 99:
          raise RuntimeError("Ungültige Zählervariable: "+str(eingang))
        if target is None:
          raise RuntimeError("Ungültiges Ziel: is None")
        if target.type <= 0 or target.type > 3:
          raise RuntimeError("Ungültiges Ziel. Must be Constant, Variable, or Terminal Input")
        self._eingang = eingang
        self._target = target
        self._countervar = countervar
        self._decrement = decrement
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int) -> List[str]:
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&VRZF\n"
            ":"+str(self._target.type+(10 if self._decrement else 0))+"\n:"+str(self._target.value)+"\n"
            ":E"+str(self._eingang)+".0\n"
            ":M"+split_num(offset_M2,8)+"\n"
            ":DW"+str(self._countervar)+"\n"
            ":DW"+str(0 if self._target.type == 1 else self._target.value + (100 if self._target.type > 2 else 0))+"\n"
            ":M"+split_num(offset_M2+1,8)+"\n"
            ":M"+split_num(offset_M1,8)+"\n"
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]



class Reset(Baustein):
    def __init__(self, eingang: int):
        Baustein.__init__(self,0,0,0,0,0,0)
        if eingang <= 0 or eingang > 26:
          raise RuntimeError("Ungültige Eingangsnummer: "+str(eingang))
        self._eingang = eingang
        self._code = 13 # RESET
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&ABB\n"
            ":E"+str(self._eingang)+".0\n"
            ":A"+str(self._code)+".0\n"
            )
        abs_code = ""
        return [baustein_code, abs_code]


class NotAus(Reset):
    def __init__(self, eingang: int):
        Reset.__init__(self,eingang)
        self._code = 12 # NOTAUS


class Terminal(Baustein):
    def __init__(self):
        Baustein.__init__(self,0,0,0,0,0,0)
        self.e17 = False
        self.e18 = False
        self.e19 = False
        self.e20 = False
        self.e21 = False
        self.e22 = False
        self.e23 = False
        self.e24 = False
        self.e25 = False
        self.e26 = False
        self.ea = 0
        self.eb = 0
        self.ec = 0
        self.ed = 0
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "#DW101="+str(self.ea)+"\n"
            "#DW102="+str(self.eb)+"\n"
            "#DW103="+str(self.ec)+"\n"
            "#DW104="+str(self.ed)+"\n"
            "#E17="+("1.000000" if self.e17 else "0.000000")+"\n"
            "#E18="+("1.000000" if self.e18 else "0.000000")+"\n"
            "#E19="+("1.000000" if self.e19 else "0.000000")+"\n"
            "#E20="+("1.000000" if self.e20 else "0.000000")+"\n"
            "#E21="+("1.000000" if self.e21 else "0.000000")+"\n"
            "#E22="+("1.000000" if self.e22 else "0.000000")+"\n"
            "#E23="+("1.000000" if self.e23 else "0.000000")+"\n"
            "#E24="+("1.000000" if self.e24 else "0.000000")+"\n"
            "#E25="+("1.000000" if self.e25 else "0.000000")+"\n"
            "#E26="+("1.000000" if self.e26 else "0.000000")+"\n"
            "#A10=0.000000\n"
            "#A11=0.000000\n"
            )
        abs_code = ""
        return [baustein_code, abs_code]


class Warte(Baustein):
    def __init__(self, wait: int):
        Baustein.__init__(self,1,1,1,0,1,2)
        self._waittime = wait
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&EVF\n"
            ":PL"+str(offset_PL)+"\n"
            ":M"+split_num(offset_M1,8)+"\n"
            ":M"+split_num(offset_M2,8)+"\n"
            ":DL"+str(offset_DL)+"\n"
            ":DL"+str(offset_DL+1)+"\n"
            "#PL"+str(offset_PL)+"="+str(self._waittime)+"\n"
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]




class Ton(Baustein):
    def __init__(self):
        Baustein.__init__(self,1,1,1,0,1,2)
    def get_q_code(self, offset_M1: int, offset_M2: int, offset_PT: int, offset_PL: int, offset_DL: int):
        if self._id <= 0:
          raise RuntimeError("Cannot generate q code without knowing my own ID")
        baustein_code = (
            "&TON\n"
            ":7\n"
            ":5\n"
            ":PL"+str(offset_PL)+"\n"
            ":M"+split_num(offset_M1,8)+"\n"
            ":M"+split_num(offset_M2,8)+"\n"
            ":DL"+str(offset_DL)+"\n"
            ":DL"+str(offset_DL+1)+"\n"
            "#PL"+str(offset_PL)+"=50\n"
            )
        abs_code = self._abs_code(0,"M"+split_num(offset_M2,8))
        return [baustein_code, abs_code]




class Program:
  def __init__(self):
    self._bausteine = []
  def add_baustein(self, baustein: Baustein):
    if baustein is None:
      return
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
    print('Generating Q File...')
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

    i = 1
    for baustein in bausteinliste:
      baustein.set_id(i)
      offset_M1 = offset_M1 + baustein.num_M2
      ablauf_size = ablauf_size + baustein.outgoing_trans
      i = i + (1 if baustein.outgoing_trans > 0 else 0) ## alles ohne definierbare ausgehende transitionen belegt keinen Platz in der Ablaufsteuerung
    q_header = "; Generated by Matthias Lutter's  Python Project\n"
    q_oben = (
        "&BEG\n"
        ":10\n" # T_ms
        ":15\n" # Li_Nr
        )
    q_unten = (
        "#M"+split_num(offset_M1+i-1,8)+"\n" # Reserviere letzten M-Eintrag, um Überlaufen zur Compilezeit erkennen zu können
        "#DW"+str(121+3*ablauf_size)+"\n" # Reserviere letzten DW-Eintrag &Cms[ablauf_size-1], um Überlaufen zur Compilezeit erkennen zu können
        "&ABS\n" # Baustein (Ablaufsteuerung)
        ":"+str(ablauf_size)+"\n" # Größe des nachfolgenden Ablauf-Arrays
        ":"+str(i)+"\n" # Anzahl der Zustände (manche Zustände können mehrere Einträge im Ablauf-Array haben)
        ":M"+split_num(offset_M1,8)+"\n" # ST: Offset für ABS-Startnachrichten gegenüber ABS-Index (Zustandsnummer im ABS-Array)
        ":DW121\n" # TR
        ":DW"+str(121+ablauf_size)+"\n" # Err
        ":DW"+str(121+ablauf_size+1)+"\n" # Cps
        ":DW"+str(121+2*ablauf_size+1)+"\n" # Cms
        ":M0.0\n" # Rev: wird auf True gesetzt, um bei Bausteinen ohne Warte-Bedingung direkt fortzufahren
        )
    q_footer = (
        "&END\n"
        ":15\n" # Li_Nr
        )

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

