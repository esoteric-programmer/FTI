import struct
import re
import io

def read_commands(file, datawidth):
        dictionary = {}
        while True:
            # Lese den Bezeichner (null-terminiert)
            identifier = bytearray()
            while True:
                char = file.read(1)
                if len(char) == 0:
                  raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen des Bezeichners")
                if char == b'\0':
                    break
                identifier.append(ord(char))
            
            if len(identifier) == 0:
                # Wenn kein Bezeichner gefunden wurde, sind wir sehr wahrscheinlich am Ende des Arrays
                break
            
            # Konvertiere den Bezeichner von Bytes zu einem String
            identifier = identifier.decode('ascii')

            # Lese die 2-Byte ID (big endian) // datawidth bytes!!
            id_bytes = file.read(datawidth)
            if len(id_bytes) != datawidth:
                raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen der ID")

            # Konvertiere die 2-Byte ID zu einem Integer (big endian)
            if datawidth == 2:
              identifier_id = struct.unpack('>H', id_bytes)[0]
            else:
              identifier_id = struct.unpack('>I', id_bytes)[0]

            # Füge den Bezeichner und die ID zum Dictionary hinzu
            dictionary[identifier] = identifier_id
        if len(file.read(3)) != 3: ## read NULL entry -- is always 4 bytes long, while 1 byte has already been read ;; TODO: test if everything of the 3 bytes is really ZERO -- if not: either raise exception or continue reading the array...
            raise ValueError("Fehler: Unerwartetes Ende der Datei am Ende des Arrays")
        return dictionary


def read_symbols(file, datawidth):
        dictionary = {}
        ## also uses datawidth from above
        while True:
            # Lese den Bezeichner (null-terminiert)
            identifier = bytearray()
            while True:
                char = file.read(1)
                if len(char) == 0:
                  raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen des Bezeichners")
                if char == b'\0':
                    break
                identifier.append(ord(char))
            
            if len(identifier) == 0:
                # Wenn kein Bezeichner gefunden wurde, sind wir am Ende des Arrays
                break
            
            # Konvertiere den Bezeichner von Bytes zu einem String
            identifier = identifier.decode('ascii')

            # Lese die Daten: 2*offset (2 or 4 bytes each, depending on datawidth), size (4bytes), 2x schrittweite (jeweils 2 bytes); (big endian)
            id_bytes = file.read(2*datawidth + 8)
            if len(id_bytes) != 2*datawidth + 8:
                raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen der ID")

            # Konvertiere die 2-Byte ID zu einem Integer (big endian)
            if datawidth == 2:
              data = struct.unpack('>HHIHH', id_bytes)
            else:
              data = struct.unpack('>IIIHH', id_bytes)
            
            if data[0] != data[1]:
              ## data[0]: offset zum lesen; data[1]: offset zum schreiben
              print('Warning: different offsets for reading and writing of symbol '+str(identifier))
              #raise ValueError("Fehler: Unbekanntes Dateiformat (zwei Offsets unterscheiden sich)")
            # data[2]: verfügbare speichergröße
            # data[3]: schrittweite des größeren werts
            # data[4]: schrittweite des kleineren werts, bzw. 0, falls es keinen kleineren wert gibt

            # Füge den Bezeichner und die ID zum Dictionary hinzu
            dictionary[identifier] = data
        if len(file.read(7)) != 7: ## read NULL entry TODO: test if everything of the 3 bytes is really ZERO -- if not: either raise exception or continue reading the array...
            print('error: Unerwartetes Ende der Datei am Ende des Arrays') ## however, since its the end of the file, we try to proceed
        return dictionary


def read_fileinfo(file):
  filename = bytearray()
  reached_end = False
  for i in range(0,12):
    char = file.read(1)
    if len(char) == 0:
      raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen des Dateiheaders")
    if char == b'\0':
      reached_end = True
    if not reached_end:
      filename.append(char[0])
  processor = bytearray()
  reached_end = False
  for i in range(0,11):
    char = file.read(1)
    if len(char) == 0:
      raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen des Dateiheaders")
    if char == b'\0':
      reached_end = True
    if not reached_end:
      processor.append(char[0])
  return filename.decode('iso-8859-15'), processor.decode('iso-8859-15')

def read_offsets(file):
  data = file.read(32)
  if len(data) != 32:
    raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen der Speicheroffsets")
  return struct.unpack('>HHHHHHHHHHHHHHHH', data)




def compile_q_file(q_file, att_file):
    commands = {}
    symbols = {}
    offsets = {}
    datawidth = 2
    with io.BytesIO(att_file) as file:
      info = read_fileinfo(file)
      print('ATT-File:  '+info[0])
      print('Processor: '+info[1])
      offsets = read_offsets(file)
      if offsets[0] != 5: ## TODO: what is this value for?
        print('error: unexpected value at start of offsets') ## LLWin2.1 seems to fail if we change this value, so we throw an exception here
      if offsets[7] < 1:
        print('error: unexpected section size') ## if this is smaller than 1, we cannot add the entry point. LLWin2.1 fails in this case as well
      ##offsets[4] ## TODO: what is this value for?
      #offsets[15] ## TODO: what is this value for?
      #print(offsets)
      datawidth = file.read(1) ## width of datawords...
      if len(datawidth) != 1:
        raise ValueError("Fehler: Unerwartetes Ende der Datei beim Lesen der Bezeichnerliste")
      datawidth = datawidth[0]
      if datawidth == 2:
        print('interface is 16bit')
      elif datawidth == 4:
        print('interface is 32bit')
      else:
        raise ValueError('error: interface reported unknown width of datawords - should be 2 or 4 bytes, but is '+str(datawidth)+' bytes')
      
      commands = read_commands(file, datawidth)
      #print(commands)
      symbols = read_symbols(file, datawidth)
      #print(symbols)
    if datawidth != 2:
      raise ValueError('interface reported 32 bit architecture, but only 16bit code generation is suported yet')
    result = None
    constants = []
    final_result = []
    #with open(q_file, 'r', encoding='iso-8859-15') as file:
    if True:
        result = bytearray()
        offset = offsets[2] ## from ATT file
        fix_offset_at = -1
        result.extend(struct.pack('>HH',offset,0)) ## 2 bytes chunk offset, 2 bytes padding
        for line in q_file.splitlines():
        #for line in file:
            # Entferne alles nach einem Kommentarzeichen ';' oder '#'
            line = line.split(';')[0].strip()
            
            if '&' in line:
              code = 0
              line = line.split('&',1)[1].strip()
              cmd = line
              if ':' in cmd:
                cmd = cmd.split(':')[0].strip()
              try:
                code = commands[cmd]
              except Exception as e:
                print('Command: '+str(cmd))
                print(str(e))
              if fix_offset_at > 0:
                fix_offset_to_value = struct.pack('>H',offset+len(result)-4) ## substract header info
                result[fix_offset_at] = fix_offset_to_value[0]
                result[fix_offset_at+1] = fix_offset_to_value[1]
              result.extend(struct.pack('>HH',code,offset)) ## default JUMP-offset: entry-point;; fix previous one in order to point to next instruction!
              fix_offset_at = len(result)-2
            if ':' in line:
              ## -> match AA0[.0]
              # Extrahiere den Teil nach dem '&' oder ':'
              match = re.search(r'([A-Za-z]+)([0-9]+)(\.[0-9]+)?', line.split(':', 1)[1].strip())
              if match:
                symb = match.groups()
                try:
                  symbol = symbols[symb[0]]
                  result.extend(struct.pack('>H',symbol[0] + symbol[3]*int(symb[1])+(symbol[4]*int(symb[2][1:]) if symb[2] is not None else 0)))
                except Exception as e:
                  print('Symbol: '+str(symb))
                  print(str(e))
              else:
                try:
                  result.extend(struct.pack('>H',int(line.split(':', 1)[1].strip())))
                except Exception as e:
                  print(str(e))
            if '#' in line:
              match = re.search(r'([A-Za-z]+)*([0-9]+)(\.[0-9]+)?[ \t]*=[ \t](-?[0-9]*\.?[0-9]+)', line.split('#', 1)[1].strip())
              if match:
                equ = match.groups()
                try:
                  symbol = symbols[equ[0]]
                  data = bytearray()
                  data.extend(struct.pack('>HH',symbol[1] + symbol[3]*int(equ[1])+(symbol[4]*int(equ[2][1:]) if equ[2] is not None else 0),0))
                  number = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                  #print('symbollen: '+str(symbol[3]))
                  if '.' in equ[3]:
                    if float(equ[3]) == 1.0:
                      number = b'\xff\x00\x00\x00\x00\x00\x00\x00'
                    elif float(equ[3]) != 0.0:
                      print('line: '+line)
                      print('error: floating point numbers no supported -- set to 0.000000') ## should not occur
                    if symbol[3] != 8:
                      print('error: data length in att file..?')
                      number = b'\x00'*symbol[3]
                  else:
                    if symbol[3] == 4:
                      number = struct.pack('>i',int(equ[3]))
                    elif symbol[3] == 2:
                      ## handle overflow
                      tmp = int(equ[3])
                      if tmp > 0x7fff and tmp <= 0xffff:
                        tmp = tmp - 0x10000
                      number = struct.pack('>h',tmp)
                    else:
                      print('line: '+line)
                      print('error: data length in att file..?')
                      number = b'\x00'*symbol[3]
                  data.extend(number)
                  constants.append(data)
                except Exception as e:
                  print('Equation: '+str(equ))
                  print(str(e))
              else:
                match = re.search(r'([A-Za-z]+)*([0-9]+)(\.[0-9]+)?[ \t]*=[ \t]*"([^"]*)"', line.split('#', 1)[1].strip())
                if match:
                  equ = match.groups()
                  try:
                    symbol = symbols[equ[0]]
                    data = bytearray()
                    data.extend(struct.pack('>HH',symbol[1] + symbol[3]*int(equ[1])+(symbol[4]*int(equ[2][1:]) if equ[2] is not None else 0),0))
                    data.extend(equ[3].encode('iso-8859-15'))
                    data.append(0)
                    if len(data)%2 != 0:
                      data.append(0)
                    constants.append(data)
                  except Exception as e:
                    print('Equation: '+str(equ))
                    print(str(e))
                else:
                  #print('line: '+line)
                  #print('warning: constant definition without assignment is being ignored')
                  pass
    ## pading
    while len(result) % 4 != 0:
      result.append(0x00) ## appending 0x00 seems to work, although the LLWin2.1 seems to append other values. but I don't know how they are computed. maybe simply some uninitialized memory?
    ## split into 900 bytes data blocks
    while len(result) > 904:
      final_result.append(result[0:904])
      offset += 900
      remaining = result[904:]
      result = bytearray()
      result.extend(struct.pack('>HH',offset,0))  ## 2 bytes chunk offset, 2 bytes padding
      result = result + remaining
    final_result.append(result)
    unknown_data = bytearray()
    unknown_data.extend(struct.pack('>HH',offsets[6],0))
    for i in range(0,offsets[7]+1): ### 00-0f: word in FTI.ATT after 0x65fc-offset defines number of chunks
      data = struct.pack('>IH',0x00000000,0xffff) ## unused data?? -- what does it do? entry points of additional threads??
      if i == 1:
        data = struct.pack('>IH',0x0000000a,offsets[2]) ## why 0x0a?? ## TODO: does this code the startoffset??
      unknown_data.extend(data)
    final_result.append(unknown_data)
    final_result = final_result + constants
    
    ## HINT: program_info is not written to MVL file
    program_info = bytearray() ## filename and some unknown additional infos - we simply set the filename to 'TEST'
    program_info.extend(struct.pack('>HH4s8sIIHB',offsets[14],0,b'ICON',b'TEST    ',
    	0x00000000, ## unbekannter wert; einfach auf 0 setzen scheint nicht zu schaden
    	0x00000000, ## unbekannter wert; ggf. eine checksum von diesem chunk?? --- einfach auf 0 setzen scheint nicht zu schaden
    	0x0000, ## scheint fast immer null zu sein; einfach auf null setzen scheint nicht zu schaden
    	0x00    ## scheint sowieso immer 0 zu sein
    	))
    final_result.append(program_info)
    
    return final_result


## if we want to write an MVL file, we can ignore the last chunk (program info), which is not part of the MVL file
## if we read an MVL file, we must create the program info by ourselfes



## observed differences only in program_info (last CHUNK) and in padding of main program (last 2 bytes of the last result-CHUNK)

