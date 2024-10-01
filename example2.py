#!/usr/bin/python3
import FTI
from FTI_com import compile_and_send_program

prog = FTI.Program()

start = FTI.Start() #optional, siehe unten
eingang = FTI.Eingang(19)
wait = FTI.Warte(500)
lampe = FTI.Lampe(2, True)
wait2 = FTI.Warte(500)
lampe2 = FTI.Lampe(2, False)
terminal = FTI.Terminal()
ende = FTI.Ende() #äquivalent zu "ende=None" und daher optional

start.successor(eingang) #optional, siehe unten
eingang.on_true(wait)
eingang.on_false(ende) #optional, da Default immer None ist
wait.successor(lampe)
lampe.successor(wait2)
wait2.successor(lampe2)
lampe2.successor(wait)

prog.add_baustein(start) # wird hier ein Baustein mit eingehender Transition, z.B. "eingang", anstelle von "start" angegeben, wird implizit ein Start-Baustein eingefügt
prog.add_baustein(terminal)

terminal.e19 = True
compile_and_send_program(prog, '/dev/ttyUSB0') # Windows: anstelle von '/dev/ttyUSB0' bitten den Port 'COM1', 'COM2' oder 'COM3', ... angeben
