import serial
import threading
import sys
from FTI_compile_q import compile_q_file
from FTI import Program


def send(data, ser2):
    data = bytes([data])
    ser2.write(data)

def read(num, ser2):
    for i in range(num):
      result = ser2.read(1)
      sys.stdout.flush()
      if num == 1:
        return result

def init(ser2):
  send(0xe0, ser2)
  result = read(1, ser2)
  if result[0] != 0xe0:
    return # error!!

def reset(ser2): # motors off
  send(0xc2,ser2)
  send(0x00,ser2)
  send(0x00,ser2)

def read_data_end(odd, ser2):
    send(0x10, ser2)
    if odd:
      send(0x31, ser2)
    else:
      send(0x30, ser2)
    result = read(1, ser2)
    if result[0] != 0x04:
      return # error!

def read_data_chunk(odd, ser2):
    more = False
    # request data
    send(0x10, ser2)
    if odd:
      send(0x31, ser2)
    else:
      send(0x30, ser2)
    
    result = read(1, ser2)
    if result[0] != 0x10:
      return b'' # error // some other command...
    result = read(1, ser2)
    if result[0] != 0x02:
      return b'' # error // some other command...
    data = b''
    checksum = 0xffff
    while True:
      result = read(1, ser2)
      checksum -= result[0]
      if result[0] == 0x10:
        result = read(1, ser2)
        checksum -= result[0]
        if result[0] != 0x10:
          # do action
          if result[0] != 0x03 and result[0] != 0x17:
            return data # error // some other command...
          if result[0] == 0x17:
            more = True
          # read checksum
          result = read(1, ser2)
          res = result[0] + 256*(read(1, ser2)[0])
          if res != checksum:
            print('checksum error: recv:'+str(res)+' vs comp:'+str(checksum))
          if more:
            return data + read_data_chunk(not odd, ser2)
          read_data_end(not odd, ser2)
          return data
      data = data + result[0].to_bytes(1, byteorder='big')

def read_data(ser2):
    result = read(1, ser2) # read 0x05, i.e. client wanna send data
    if result[0] != 0x05:
        return b'' # error: client doesn't want to send data
    return read_data_chunk(False, ser2)

def send_data(data, ser2):
    send(0x05, ser2) # i wanna send data
    read(2, ser2) # read 0x10 0x30: you can start send
    send(0x10, ser2)
    send(0x02, ser2)

    sent = 0
    checksum = 0xffff
    for byte in data:
      if sent > 115:
        send(0x10, ser2)
        checksum -= 0x10
        send(0x17, ser2)
        checksum -= 0x17
        send(checksum & 0xFF, ser2)
        send((checksum & 0xFF00) // 256, ser2)
        checksum = 0xffff
        sent = 0
        read(2, ser2) # read 0x10 0x31
        send(0x10, ser2)
        send(0x02, ser2)
      if byte == 0x10:
        send(0x10, ser2)
        sent += 1
        checksum -= 0x10
      send(byte, ser2)
      sent += 1
      checksum -= byte
    send(0x10, ser2)
    checksum -= 0x10
    send(0x03, ser2)
    checksum -= 0x03
    send(checksum & 0xFF, ser2)
    send((checksum & 0xFF00) // 256, ser2)
    read(2, ser2) # read 0x10 0x31
    send(0x04, ser2)


def print_version(ser2):
  send_data(b'\x00', ser2) ## read version
  data = read_data(ser2)
  if data[0] == 0x05:
    print('Got Some Additional Unknown Information: '+str(data[1]))

def get_ROM(ser2):
  send_data(b'\x02', ser2) ## read ROM
  data = read_data(ser2)
  return data


def send_PROG(prog, ser2):
  send_data(b'\x01\x06\x00', ser2) ## send program...
  for chunk in prog:
      send_data(b'\x05' + chunk, ser2) ## send program parts, each starting with \x05 instruction
  send_data(b'\x03', ser2) ## \x03: end of chunks

def compile_and_send_program(prog: Program, port: str):
  # configure the serial connections (the parameters differs on the device you are connecting to)
  ser2 = serial.Serial(
    port=port,
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
  )

  if ser2.is_open == False:
    ser2.open()

  print('Initializing Interface Connection...')
  # init active mode
  init(ser2)

  print('Turning All Ports Off...')
  # set outputs to zero  
  reset(ser2)

  print('Receiving ATT File...')
  rom = get_ROM(ser2)
  print_version(ser2)

  #print('Generating Code...')
  #with open('TMP.ATT', 'wb') as f:
  #    f.write(rom)

  prog = compile_q_file(prog.build_q_file(), rom) #'TMP.ATT')

  print('Sending the Program...')
  send_PROG(prog, ser2)

  ser2.close()
  print('Done.')
  print('The Intelligent Interface will Execute the Program in about 2-3 Seconds.')



# command list: [2byte code, \x00-terminated string (command name)]*
# &\x02ABS\x00;IAPR8\x00=\x9dJPZ\x00Y\x97NOP\x00\x00\x11BEG\x00\x00\x12END\x00Y\xc6Init\x00Y\xcdVRZF\x00?\xf0SMOT\x00B\x92SVAR\x00CoIVAR\x00F\x0fCMW\x00F\x87EVF\x00J\xf0T2D\x00M\xd2Inif\x00M\xdbNot\x00N\xdeFD10\x00O\x1bABB\x00O\x97ADDW\x00O\xd3SUBW\x00P\x1aDIVW\x00PbMULW\x00Q\x02SCHW\x00QPAND\x00Q\xbeOR\x00S\x10CMPW\x00TbFD01\x00UvFFR\x00U\xf2FFS\x00VCBGW\x00V\x94AWW\x00W\xfdABW\x00X*AWB\x00X\xe3TON\x00
