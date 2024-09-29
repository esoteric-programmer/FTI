import FTI
from FTI_com import compile_and_send_program

prog = FTI.Program()


eingang2 = FTI.Eingang(1)
eingang3 = FTI.Eingang(1)
eingang4 = FTI.Eingang(1)
inc6 = FTI.IncVariable(42)
inc7 = FTI.IncVariable(42)
lampe2 = FTI.Lampe(2,True)

eingang2.on_true(eingang3)
eingang2.on_false(eingang4)
eingang3.on_true(eingang3)
eingang4.on_false(eingang4)
eingang3.on_false(inc6)
inc6.successor(eingang4)
eingang4.on_true(inc7)
inc7.successor(eingang3)




start = FTI.Start()

vergleich = FTI.Vergleich(42,FTI.constant(9),'>')
vergleich.on_false(vergleich)

#position = FTI.Position(1,FTI.constant(10),42,False)
reset = FTI.Variable(42,FTI.constant(0))
inc1 = FTI.IncVariable(42)
inc2 = FTI.IncVariable(42)
inc3 = FTI.IncVariable(42)
inc4 = FTI.IncVariable(42)
inc5 = FTI.IncVariable(42)
dec1 = FTI.DecVariable(42)

eingang = FTI.Eingang(1)
#flanke = FTI.Flanke(1)
flanke2 = FTI.Flanke(1)
lampe = FTI.Lampe(2,True)
motor = FTI.Motor(3,FTI.Richtung.LINKS)
off2 = FTI.Lampe(2,False)
off3 = FTI.Lampe(3,False)
##warte = FTI.Warte(500) ### das ist noch aus irgendwelchen gründen buggy und funktioniert nicht...


start.successor(reset)
reset.successor(inc1)
inc1.successor(inc2)
inc2.successor(inc3)
inc3.successor(inc4)
inc4.successor(inc5)
inc5.successor(dec1)
dec1.successor(vergleich) #(flanke)

#flanke.successor(lampe)
vergleich.on_true(lampe)
lampe.successor(flanke2)
flanke2.successor(off2)
off2.successor(reset)

#start.successor(eingang)
#eingang.on_true(motor) ## wenn E1 gedrückt, drehe motor M3 nach links
#eingang.on_false(lampe) ## wenn E1 nicht gedrückt, schalte lampe M2 ein
#lampe.successor(off3)
#off3.successor(eingang)
#motor.successor(off2)
#off2.successor(eingang)
##warte.successor(eingang)


prog.add_baustein(start)
prog.add_baustein(FTI.NotAus(3))
prog.add_baustein(eingang2)
compile_and_send_program(prog, '/dev/ttyUSB2')
