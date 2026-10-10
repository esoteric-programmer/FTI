# fischertechnik LLWin 2.1 — MDL File Format Specification

**Version:** 1.5  
**Date:** 2026-10-10  
**Based on:** Reverse engineering of LLWIN.EXE embedded 32-bit code  
**Extensions:** `.MDL` (models), `.MDN` (default/template models)  

## Overview

MDL files store fischertechnik LLWin 2.1 programs as serialized in-memory object
graphs. The format is a raw binary dump of linked C structs, with self-pointer
serialization for reconnecting references on load.

All multi-byte values are little-endian. Pointers stored in the file are stale
runtime addresses from the saving session; they serve only as identity tokens for
the pointer-fixup pass after loading.

## File Structure (Top Level)

```
┌───────────────────────────────────────────────────┐
│ Section 1: Program Sections                       │
│   (linked list, loop until next_ptr == 0)         │
│   Each program contains:                          │
│     • Program Header                              │
│     • Blocks (0xEC or 0x70 type)                  │
│       └── Elements (within 0xEC blocks)            │
├───────────────────────────────────────────────────┤
│ Section 2: Connection Data Sections               │
│   (one per 0xEC block, in order)                  │
│   Each section: entries terminated by 0x0000       │
└───────────────────────────────────────────────────┘
```

The file always contains at least one non-$Main program section followed by
one or more $Main (BAUSTEIN) program sections.

---

## Section 1: Program Sections

Programs are stored as a linked list. Each program begins with a header;
the `next_ptr` field chains them. The list terminates when `next_ptr == 0`.

### 1.1 Program Header

#### Base header (0x18 bytes, all programs):

| Offset | Size | Type   | Field           | Description                          |
|--------|------|--------|-----------------|--------------------------------------|
| 0x00   | 4    | uint32 | next_ptr        | Stale pointer; 0 = last program      |
| 0x04   | 12   | char[] | name            | Null/space-padded ASCII name         |
| 0x10   | 2    | uint16 | flags           | Bit flags (see below)                |
| 0x12   | 2    | uint16 | flags2          | Additional flags                     |
| 0x14   | 4    | uint32 | block_list_ptr  | Stale pointer to first block; 0=none |

**Flags (offset 0x10):**
- **Bit 0:** `is_main` — If set, this is a $Main/BAUSTEIN program section with
  0x70-byte block type definitions. If clear, this is a user program with 0xEC
  blocks.
- **Bit 2:** `use_extended_format` — Controls block size: when set, blocks are
  0xEC bytes and elements are 0x44 bytes. When clear, blocks are 0xD8 bytes and
  elements are read as 0x3C bytes (allocated in 0x44). In practice, all observed
  files use the 0xEC/0x44 format.

#### $Main extra header (0x1C bytes, only when flags bit 0 is set):

Immediately follows the base header (total = 0x34 bytes).

| Offset | Size | Type   | Field         | Description                        |
|--------|------|--------|---------------|------------------------------------|
| 0x18   | 4    | uint32 | struct_6      | Stale pointer                      |
| 0x1C   | 4    | uint32 | struct_7      | Stale pointer                      |
| 0x20   | 4    | uint32 | struct_8      | Stale data pointer                 |
| 0x24   | 4    | uint32 | var_data_size | Size of variable data following    |
| 0x28   | 4    | uint32 | struct_10     | Stale pointer                      |
| 0x2C   | 4    | uint32 | struct_11     | Size value                         |
| 0x30   | 4    | uint32 | struct_12     | Value                              |

If `var_data_size > 0`, immediately followed by `var_data_size` bytes of
variable data (global variable initial values for this program).

### 1.2 Program Types

Programs appear in a specific order:

1. **First program:** A non-$Main program (the user's main flowchart). Name is
   typically the filename (e.g., `SCHWENK.MDL`). Contains 0xEC blocks.
2. **Additional non-$Main programs:** Subprograms, if any. Same format.
3. **$Main programs (BAUSTEIN sections):** Block type catalog definitions. The
   first contains the block types used in this file; additional BAUSTEIN sections
   may follow with empty block lists.

**Important:** The non-$Main (0xEC) and $Main (0x70) sections can appear in any
interleaved order. While most files place all non-$Main programs first, some
files (e.g., `GELD.MDL`) have non-$Main sections appearing *after* the first
$Main section. A parser must handle both orderings — populate `block70_map` as
0x70 entries are encountered and resolve element types after all sections are
read.

### 1.3 Block Types

#### 0xEC Block (User Program Block)

Used in non-$Main programs. Represents a named subprogram/page in the flowchart.

| Offset | Size | Type   | Field          | Description                         |
|--------|------|--------|----------------|-------------------------------------|
| 0x00   | 4    | uint32 | next_ptr       | Stale pointer; 0 = last block       |
| 0x04   | 16   | char[] | name           | Block name (null/space-padded)      |
| 0x14   | 4    | -      | (padding)      |                                     |
| 0x18   | 2    | uint16 | num_outputs    | Number of output connectors         |
| 0x1A   | 2    | uint16 | num_inputs     | Number of input connectors          |
| 0x1C   | 4    | uint32 | elem_list_ptr  | Stale pointer to first element      |
| 0x20   | 4    | uint32 | self_ptr       | Self-pointer (used for fixup)       |
| 0x24   | 4    | uint32 | field_24       | Flags/display                       |
| 0x28   | 4    | uint32 | field_28       | Grid/display settings               |
| 0x2C   | 4    | uint32 | field_2C       | Display dimensions (packed)         |
| 0x30   | 4    | uint32 | output_tbl_ptr | Stale pointer to output table       |
| 0x34   | 4    | uint32 | input_tbl_ptr  | Stale pointer to input table        |
| 0x38   | 4    | uint32 | field_38       | Display properties                  |
| 0x3C   | 2    | uint16 | field_3C       |                                     |
| 0x3E   | 2    | uint16 | field_3E       |                                     |
| 0x40   | 172  | -      | display_data   | Visual properties, colors, layout   |

The region from ~0x78 to 0xEB typically contains display properties for the
block's visual appearance (colors, grid lines, etc.). Bytes 0xF8 appear as
uninitialized padding in many files.

**Following the 0xEC block header:**

1. **Output table** (if `output_tbl_ptr != 0` and `num_outputs > 0`):
   `num_outputs × 6` bytes. Each 6-byte entry describes an output connector.

2. **Input table** (if `input_tbl_ptr != 0` and `num_inputs > 0`):
   `num_inputs × 6` bytes. Each 6-byte entry describes an input connector.

3. **Elements** (if `elem_list_ptr != 0`):
   Linked list of elements (see §1.4). Loop until `next_ptr == 0`.

#### 0x70 Block (Block Type Definition)

Used in $Main/BAUSTEIN programs. Defines a block type available in the palette.

| Offset | Size | Type   | Field    | Description                            |
|--------|------|--------|----------|----------------------------------------|
| 0x00   | 4    | uint32 | next_ptr | Stale pointer; 0 = last block          |
| 0x04   | 16   | char[] | name     | Block type name (e.g., `MOTOR`)        |
| 0x14   | 4    | uint32 | field_14 | Type-specific properties               |
| 0x18   | 4    | uint32 | io_spec  | Packed I/O specification               |
| 0x1C–0x68 | varies | - | fields   | Type properties, display info, pointers |
| 0x6C   | 4    | uint32 | self_ptr | Self-pointer (used for fixup)          |

Standard block type names (sorted, as they appear in the BAUSTEIN catalog):

| Index | Name          | Description (German)      |
|-------|---------------|---------------------------|
| 0     | BEEP          | Beep/sound                |
| 1     | DECVARIABLE   | Decrement variable        |
| 2     | DISPLAY       | Display output            |
| 3     | EINGANG       | Input (sensor)            |
| 4     | ENDE          | End                       |
| 5     | FLANKE        | Edge detection            |
| 6     | INCVARIABLE   | Increment variable        |
| 7     | LAMPE         | Lamp output               |
| 8     | MELDUNG       | Message                   |
| 9     | MOTOR         | Motor output              |
| 10    | NOTAUS        | Emergency stop            |
| 11    | POSITION      | Position counter          |
| 12    | RESET         | Reset                     |
| 13    | START         | Start                     |
| 14    | TERMINAL      | Terminal I/O              |
| 15    | VARIABLE      | Variable operation        |
| 16    | VERGLEICH     | Comparison                |
| 17    | WARTE         | Wait/delay                |

### 1.4 Element (Flowchart Node)

Elements represent individual nodes in the flowchart (operations, conditions,
connectors, etc.). Each is a 0x44-byte struct followed by variable-length data.

#### Element Header (0x44 bytes):

| Offset | Size | Type   | Field         | Description                         |
|--------|------|--------|---------------|-------------------------------------|
| 0x00   | 4    | uint32 | next_ptr      | Stale pointer; 0 = last element     |
| 0x04   | 2    | uint16 | class_id      | Class/vtable discriminator (e.g. 0x2185) |
| 0x06   | 2    | uint16 | x_position    | Canvas X coordinate                 |
| 0x08   | 2    | uint16 | y_position    | Canvas Y coordinate                 |
| 0x0A   | 2    | uint16 | num_out_pins  | Number of output pins               |
| 0x0C   | 2    | uint16 | num_in_conns  | Number of input connections         |
| 0x0E   | 2    | uint16 | num_data      | Number of 8-byte data entries       |
| 0x10   | 2    | uint16 | type_size     | Type table size value (type identifier) |
| 0x12   | 2    | uint16 | field_12      | Usually 1; purpose unclear          |
| 0x14   | 4    | uint32 | out_pins_ptr  | Stale pointer to output pin array   |
| 0x18   | 4    | uint32 | in_conns_ptr  | Stale pointer to input conn array   |
| 0x1C   | 4    | uint32 | data_ptr      | Stale pointer to data array         |
| 0x20   | 4    | uint32 | block_type_ptr| Stale pointer to 0x70 block type def (its self_ptr) |
| 0x24   | 4    | uint32 | field_24      | Flags (bit 1 controls extra data)   |
| 0x28   | 2    | uint16 | conn_type_id  | Connection data type ID (unique non-zero per block) |
| 0x2A   | 2    | uint16 | field_2A      | Upper half of original field_28     |
| 0x2C   | 4    | uint32 | self_ptr      | Self-pointer (serialization ID)     |
| 0x30   | 4    | uint32 | field_30      | Display: size/dimension (100=default)|
| 0x34   | 4    | uint32 | field_34      | Display properties                  |
| 0x38   | 4    | uint32 | field_38      | Display properties                  |
| 0x3C   | 4    | uint32 | field_3C      | Display properties                  |
| 0x40   | 4    | uint32 | field_40      | Display properties                  |

**Type identification:** Elements are identified by two independent mechanisms:

1. **block_type_ptr (offset 0x20):** Stale pointer to the 0x70 block type
   definition that defines this element's type. Its value must equal the
   `self_ptr` of the corresponding BlockType entry in the BAUSTEIN catalog.
   This is the **primary** type identification — a direct object reference.

2. **type_size (offset 0x10):** A u16 value that matches the "size" column
   in the type table near EOF. This provides a second way to identify the
   element's type. Note: size values are NOT globally unique (e.g., MOTOR
   and LAMPE may both have size=62 in some files), so disambiguation may be
   needed for generation.

**x_position / y_position (offsets 0x06, 0x08):** Canvas coordinates where
the element is displayed. The LLWin grid snaps to 5-pixel increments, so
positions are typically multiples of 5. Elements with type_size=0 (sentinel
elements at the end of element lists) have x=0, y=0.

**class_id (offset 0x04):** Class/vtable discriminator word. Common values
include 0x2185 for standard visible elements and 0x0D42 for sentinel/invisible
elements.

**conn_type_id (offset 0x28):** The identifier written to connection data
sections (§2) for this element. Must be **unique and non-zero** within each
0xEC block. The reader (FUN_0003a28c) searches the element list for the
element whose conn_type_id matches the `type_id` read from the connection
data section. A value of 0 would collide with the section terminator.
Sequential assignment (1, 2, 3, ...) per block is recommended.

**self_ptr serialization:** Before writing, the software stores the element's
own runtime address in `self_ptr`. On load, this value is used to resolve
cross-references: other structs that held a pointer to this element stored
the same address, which the fixup pass replaces with the new runtime address.

#### Following the element header (serialization order):

The sub-structures are serialized in this exact order. Getting the order
wrong causes misalignment — the connection chain length varies per element,
so swapping it with fixed-size sections shifts all subsequent offsets.

1. **Output Pins** (if `out_pins_ptr != 0` and `num_out_pins > 0`):
   `num_out_pins × 0x14` bytes.

   Each output pin (0x14 bytes):

   | Offset | Size | Type   | Field     | Description                       |
   |--------|------|--------|-----------|-----------------------------------|
   | 0x00   | 4    | uint32 | field_00  | Stale pointer / properties        |
   | 0x04   | 4    | uint32 | field_04  | Properties / coordinates          |
   | 0x08   | 4    | uint32 | field_08  | Properties                        |
   | 0x0C   | 4    | uint32 | conn_head | Head of connection record list    |
   | 0x10   | 4    | uint32 | field_10  | Properties                        |

   Note: save the `conn_head` values but do NOT walk the connection chains
   yet — they come AFTER input connections and element data (see step 4).

2. **Input Connections** (if `in_conns_ptr != 0` and `num_in_conns > 0`):
   `num_in_conns × 6` bytes.

   Each input connection (6 bytes):

   | Offset | Size | Type   | Field  | Description                        |
   |--------|------|--------|--------|------------------------------------|
   | 0x00   | 2    | uint16 | ref_0  | Connection reference / index       |
   | 0x02   | 2    | uint16 | ref_2  | Connection reference / index       |
   | 0x04   | 2    | uint16 | ref_4  | Connection reference / index       |

3. **Element Data** (if `data_ptr != 0` and `num_data > 0`):
   `num_data × 8` bytes. Each entry is 8 bytes of type-specific parameter data.
   
   The format depends on the element's class and type — see §1.5 for details.

4. **Connection Records** (for each output pin with `conn_head != 0`):
   
   **IMPORTANT:** Connection records are serialized AFTER the input connections
   and element data, not immediately after the output pins. The serialization
   order is: pins → input conns → data → connection chains.
   
   For each pin whose `conn_head != 0`, walk the connection chain:
   
   Each connection record is 8 bytes:

   | Offset | Size | Type   | Field    | Description                      |
   |--------|------|--------|----------|----------------------------------|
   | 0x00   | 4    | uint32 | next_ptr | Next connection record; 0 = end  |
   | 0x04   | 4    | uint32 | target   | Stale pointer to target element  |

   The list is null-terminated: when `next_ptr == 0`, this is the last record.

### 1.5 Element Data Array Content

The element data array (`num_data × 8` bytes at `data_ptr`) has different
content layouts depending on the element's class_id. Text is Latin-1 encoded;
`0x0D` bytes represent line breaks.

#### Standard Bausteine (class_id 0x2185)

For normal flowchart nodes (MOTOR, EINGANG, WARTE, etc.), the data array
entries contain display properties (coordinates, colors, sizes). Parameter
values are stored in the connection data section's sub_data (see Appendix C),
**except** for MELDUNG and DISPLAY which store their text content here.

**MELDUNG** (class_id 0x2185, type MELDUNG): The user's message text is
stored in the element data array starting at byte 0, null-terminated,
Latin-1 encoded. Example: `"Geldausgabe\x00..."`.

**DISPLAY** (class_id 0x2185, type DISPLAY): Same layout as MELDUNG — the
display text starts at byte 0 of the data array.

#### Subprogram Entry Nodes (class_id low byte = 0x2D)

Class IDs: 0x202D, 0x212D (and potentially other high-byte variants).
These represent the entry point(s) of a subprogram — where control flow
enters from the caller.

Properties: `num_out_pins ≥ 1`, `num_in_conns = 0`, `type_size ≤ 1`.

Data array content: The entry label is stored at byte 0, null-terminated,
Latin-1. Typical values: `"I1"`, `"INP1"`, `"I2"`, etc.

#### Subprogram Exit Nodes (class_id low byte = 0x2C)

Class IDs: 0x202C, 0x212C (and potentially other high-byte variants).
These represent the exit point(s) — where control flow returns to the caller.

Properties: `num_out_pins = 0`, `num_in_conns ≥ 1`, `type_size = 0`.

Data array content: The exit label at byte 0, null-terminated, Latin-1.
Typical values: `"O1"`, `"OUTP1"`, `"O2"`, etc.

#### Text Annotations (class_id 0x2042, 0x2142)

Free-floating text labels on the canvas. No pins or connections
(`num_out_pins = 0`, `num_in_conns = 0`), `type_size = 0`.

Data array content (`num_data > 1` required for text):
- Bytes 0–7 (first 8-byte entry): Header containing font info and a stale
  pointer (display properties).
- Bytes 8+ (remaining entries): The annotation text, null-terminated, Latin-1.
  `0x0D` bytes represent line breaks (rendered as `\n`).

#### Sentinel Elements (class_id 0x0D42)

End-of-list markers. `type_size = 0`, `x = 0`, `y = 0`. Data entries may
be present but carry no meaningful content.

---

## Section 2: Connection Data Sections

After all program sections, the file contains connection data sections — one
per 0xEC block, in the same order as the blocks appeared in Section 1.

These sections contain computed/cached data about element interconnections that
supplements the structural data in the elements themselves.

### 2.1 Connection Data Section Format

Each section is a sequence of entries, one per element in the block's element
list (in linked-list order), terminated by a 0x0000 sentinel.

#### Entry format:

| Offset | Size | Type   | Field           | Description                       |
|--------|------|--------|-----------------|-----------------------------------|
| 0x00   | 2    | uint16 | type_id         | Connection type ID (= elem.field_28 & 0xFFFF); 0 = section end |

If `type_id != 0`, followed by:

| Offset | Size | Type   | Field           | Description                       |
|--------|------|--------|-----------------|-----------------------------------|
| 0x02   | 4    | uint32 | out_data_size   | Output data size in bytes         |
| 0x06   | N    | bytes  | out_data        | Output connection data (if > 0)   |
| 0x06+N | 4    | uint32 | in_data_size    | Input data size in bytes          |
| ...    | M    | bytes  | in_data         | Input connection data (if > 0)    |
| ...    | 4    | uint32 | extra_data_size | Extra data size (0 if bit 1 of elem.field_24 is set) |
| ...    | K    | bytes  | extra_data      | Extra element data (if > 0)       |
| ...    | 4    | int32  | sub_indicator   | Sub-block indicator (see below)   |

**out_data_size / in_data_size:** Computed by counting active output/input
entries and multiplying by 8. These store the connection routing data that
the runtime uses for signal propagation.

**extra_data_size:** Only present (non-zero) when bit 1 of the element's
`field_24` is clear. Contains element-specific parameter data.

**sub_indicator:**
- `0`: No sub-block data
- `> 0`: Followed by `sub_indicator` bytes of sub-block data (a flat array
  of 8-byte entries, count = `sub_indicator / 8`)
- `-1` (0xFFFFFFFF): Recursive — followed by a complete connection data
  section (same format, with its own entries and 0x0000 terminator). This
  occurs when the element represents a subprogram call, and the sub-section
  contains the connection data for that subprogram's elements.

#### Section terminator:

After the last entry, a 2-byte `0x0000` value terminates the section.

---

## Pointer Fixup (Deserialization)

After loading all sections, the software performs a pointer fixup pass
(FUN_00031af0). This resolves the stale pointer values stored in the file:

1. Each struct's `self_ptr` was set to its own runtime address before saving.
2. Other structs that reference it stored that same address value.
3. On load, the fixup pass scans all loaded structs:
   - For each stale pointer value, find the struct whose `self_ptr` matches.
   - Replace the stale value with the struct's new runtime address.

This means that for **file generation**, the pointer values need only be
internally consistent: `self_ptr` values must be unique, and any field that
references another struct must contain that struct's `self_ptr` value.

### Recommended approach for generating MDL files:

1. Assign each struct a unique synthetic `self_ptr` (e.g., sequential:
   0x10000, 0x10001, ...).
2. Set `next_ptr` fields to the next struct's `self_ptr`, or 0 for the last.
3. Set `elem_list_ptr`, `block_list_ptr`, etc. to the target struct's
   `self_ptr`.
4. Set `output_tbl_ptr`, `input_tbl_ptr`, `out_pins_ptr`, etc. to any
   non-zero value when the corresponding data is present (the actual address
   is irrelevant as long as the non-zero check passes correctly).

---

## Complete File Layout Example

For a simple single-subprogram MDL file with one $Main and one UP1 block:

```
Offset 0x0000: Program Header (non-$Main, name="EXAMPLE.MDL")
  0x0018: 0xEC Block "$Main"
          Output/Input tables (if any)
          Elements (linked list of 0x44-byte structs + variable data)
  0x????: 0xEC Block "UP1"
          Output/Input tables
          Elements

Program Header ($Main, name="BAUSTEIN")
  0x????: Extra header (0x1C bytes) + variable data
  0x????: 0x70 Block type definitions (e.g., MOTOR, WARTE, EINGANG...)

Program Header ($Main, second BAUSTEIN)  [optional, may have empty block list]
  ...

Program Header ($Main, third BAUSTEIN)   [optional]
  ...

Last program header (next_ptr = 0)

Connection Data Section for "$Main" block
  Entry 0: type_id, out_data, in_data, extra_data, sub_indicator
  Entry 1: ...
  0x0000 terminator

Connection Data Section for "UP1" block
  Entry 0: ...
  0x0000 terminator
```

---

## Validation Rules

For an MDL file to be accepted by LLWin 2.1:

1. Program headers must form a proper linked list (terminated by `next_ptr == 0`).
2. At least one non-$Main program must precede the $Main programs.
3. Block linked lists must be properly terminated.
4. Element struct sizes must be exactly 0x44 bytes.
5. Output pins must be exactly 0x14 bytes each.
6. Input connections must be exactly 6 bytes each.
7. Element data entries must be exactly 8 bytes each.
8. Connection records must be 8 bytes each, null-terminated lists.
9. Connection data sections must match 1:1 with 0xEC blocks, in order.
10. Each connection data section must have exactly as many entries as elements
    in the corresponding block.
11. Connection data sections must be terminated by 0x0000.
12. All data must be consumed — no trailing bytes.
13. Each element's `field_28 & 0xFFFF` (conn_type_id) must be unique and non-zero
    within its containing 0xEC block — 0 collides with the section terminator.
14. Connection data `type_id` values must match the element's `conn_type_id`
    (offset 0x28), NOT the element's `y_position` (offset 0x08).
15. Element `block_type_ptr` (offset 0x20) must reference the `self_ptr` of the
    matching 0x70 block type definition in the BAUSTEIN catalog.

---

## Key Functions (LLWIN.EXE 32-bit code at base 0x8800)

| Function     | Purpose                                    |
|--------------|--------------------------------------------|
| FUN_00039400 | Load orchestrator (dispatches load)        |
| FUN_000397ac | Program header reader                      |
| FUN_00039b10 | 0xEC block reader                          |
| FUN_00039ebc | 0x70 block reader                          |
| FUN_0003a024 | Element reader                             |
| FUN_0003a28c | Connection data section reader             |
| FUN_0003b5f8 | Top-level save function                    |
| FUN_0003b7d4 | Program writer                             |
| FUN_0003b8d0 | 0xEC block writer                          |
| FUN_0003ba10 | 0x70 block writer                          |
| FUN_0003ba4c | Element writer                             |
| FUN_0003bbe4 | Connection data section writer             |
| FUN_00031af0 | Pointer fixup (deserialization)            |
| FUN_0003d39c | read(handle, size, buffer) wrapper         |
| FUN_0003d3e4 | alloc+read(handle, size, &ptr) wrapper     |
| FUN_0003d478 | write(handle, size, buffer) wrapper        |
| FUN_00040dd0 | malloc wrapper                             |
| FUN_0006ac50 | Bit-test: ((*p & (1<<(b&0x1f))) != 0)     |

---

## Appendix A: Type Identification

Elements are identified by their `block_type_ptr` (offset 0x20) and `type_size`
(offset 0x10). **The field at offset 0x08 is the y_position, NOT a type ID.**

### Via block_type_ptr (primary):
The element's `block_type_ptr` matches the `self_ptr` of one of the 0x70
BlockType entries in the BAUSTEIN catalog. This directly identifies the type.

### Via type_size (secondary):
The `type_size` field (u16 at offset 0x10) matches the "size" column in the
type table embedded near EOF. Standard type sizes:

| type_size | Block Type    | params | conns |
|-----------|---------------|--------|-------|
| 53        | START         | 0      | 1     |
| 43        | ENDE          | 0      | 0     |
| 58        | EINGANG       | 3      | 2     |
| 62        | MOTOR/LAMPE/BEEP | varies | varies |
| 76        | VERGLEICH     | 4      | 2     |
| 82        | WARTE         | 1      | 1     |
| 69        | VARIABLE      | 3      | 1     |
| 50        | MELDUNG       | 3      | 1     |
| 68        | DISPLAY       | 3      | 1     |
| 287       | TERMINAL      | 0      | 0     |
| 84        | POSITION      | 6      | 1     |
| 48        | DECVARIABLE   | 2      | 1     |
| 60        | FLANKE        | 2      | 1     |
| 57        | INCVARIABLE   | 2      | 1     |
| 17        | NOTAUS        | 2      | 0     |
| 16        | RESET         | 2      | 0     |

**Note:** type_size values are NOT globally unique — MOTOR, LAMPE, and BEEP
may share size=62. Disambiguation requires checking the block_type_ptr or
the element's parameter data in the connection data section.

### Sentinel elements:
Elements with type_size=0, x=0, y=0, no pins/connections, and class_id=0x0D42
are sentinel/terminator elements at the end of element lists. They carry data
entries but are not visible on the canvas.

## Appendix B: Block I/O Table Entry Format

Each output table entry (6 bytes):

| Offset | Size | Type   | Description              |
|--------|------|--------|--------------------------|
| 0x00   | 2    | uint16 | Output index/identifier  |
| 0x02   | 2    | uint16 | Properties               |
| 0x04   | 2    | uint16 | Properties               |

Each input table entry (6 bytes):

| Offset | Size | Type   | Description              |
|--------|------|--------|--------------------------|
| 0x00   | 2    | uint16 | Input index/identifier   |
| 0x02   | 2    | uint16 | Properties               |
| 0x04   | 2    | uint16 | Properties               |

## Appendix C: Connection Data sub_data — Property Array

When `sub_indicator > 0`, the `sub_data` blob is `type_size * 8` bytes — a raw
dump of the element's runtime property array. Each entry is 8 bytes, accessed by
computed index. (Confirmed from LLWIN.EXE disassembly at 0x3BE1C: the writer
reads `[element+0x10]` (type_size), shifts left by 3, and writes that many
bytes from `[data_struct+0x18]`.)

The property array layout is type-specific. The early entries (indices 0–35)
hold cached/input values that may be zero in some files. The tail entries
(near the end of the array) are the **authoritative** parameter locations,
consistently populated across all tested files.

### MOTOR / LAMPE (type_size=62, sub_data=496 bytes):

| Entry | Byte offset | Type   | Field        | Notes                              |
|-------|-------------|--------|--------------|-------------------------------------|
| 0     | 0x004       | char   | number       | Motor/lamp number as ASCII '1'–'8'  |
| 53    | 0x1AC       | u32    | dir_code     | 1=LINKS, 2=RECHTS, 3=AUS (at +4)   |
| 55    | 0x1B8       | char[] | direction    | **Authoritative.** "RECHTS"/"LINKS"/"AUS"/"EIN" |
| 56    | 0x1C4       | char   | number_copy  | Motor number ASCII (at +4)          |
| 58    | 0x1D0       | u32+ch | num_int+asc  | Motor number as int (at +0) and ASCII (at +4) |
| 60    | 0x1E0       | char[] | dir_copy     | Direction string (copy of entry 55) |
| 61    | 0x1EC       | u32    | constant     | Always 9 (at +4)                    |

Entry 2 (0x010) sometimes contains the direction string but is NOT reliable —
it is empty in PROFI files like GELD.MDL. Always read from entry 55.

Direction disambiguates type: "RECHTS"/"LINKS" → MOTOR, "EIN" → LAMPE.

### WARTE (type_size=82, sub_data=656 bytes):

| Entry | Byte offset | Type   | Field        | Notes                              |
|-------|-------------|--------|--------------|-------------------------------------|
| 0–1   | 0x004       | double | wait_seconds | IEEE 754 LE, spans entry boundary   |
| 16    | 0x080       | char[] | display_str  | Time as text, e.g. "1.0   "         |
| 18    | 0x094       | u32    | constant     | 0x3E7 (999) at +4                   |

### EINGANG (type_size=58, sub_data=464 bytes):

| Entry | Byte offset | Type   | Field      | Notes                               |
|-------|-------------|--------|------------|--------------------------------------|
| 0     | 0x004       | char[] | eingang_id | "E  X" where X is digit             |
| 40    | 0x140       | char[] | name       | Eingang name, e.g. "E  1", "E  17"  |
| 41    | 0x14C       | u32    | ein_num    | Eingang number as integer (at +4)    |
| 52    | 0x1A0       | char[] | name_copy  | **Authoritative** Eingang name       |
| 53    | 0x1AC       | u32    | right_on   | **Authoritative.** '0' or '1' as ASCII (at +4) |
| 55    | 0x1B8       | u32+ch | const+ro   | 9 (at +0), rightOn ASCII (at +4)     |

Entry 2 (0x010) sometimes contains rightOn but may be empty in complex files.

### FLANKE sub_data:

Same structure as EINGANG for the eingang_id at entry 0 (byte 4).
The FLANKE type_size varies; the eingang name at entry 0 byte 4 is reliable.

### VARIABLE / VERGLEICH / INCVARIABLE / DECVARIABLE sub_data:

| Entry | Byte offset | Type   | Field  | Notes                                |
|-------|-------------|--------|--------|---------------------------------------|
| 0     | 0x004       | char[] | params | Parameter string, up to 16 chars      |

### NOTAUS / RESET sub_data:

| Entry | Byte offset | Type   | Field  | Notes                                |
|-------|-------------|--------|--------|---------------------------------------|
| 0     | 0x004       | char[] | params | Parameter string, up to 4 chars       |

## Appendix D: Known Constant Values

- The first 0xEC block in a non-$Main program is always named `$Main` (the
  block that contains the main flowchart of that program).
- The second 0xEC block is typically named `UP1` (subprogram 1).
- $Main program sections are named `BAUSTEIN` (German for "building block").
- The `$Main` block in simple files typically has 0 outputs and 0 inputs.
- Subprogram blocks (UP1, etc.) typically have 1 output and 1 input.

## Appendix E: Element Class IDs

The `class_id` field at element offset +0x04 discriminates element types:

| Class ID   | Type                | Description                              |
|------------|---------------------|------------------------------------------|
| 0x2185     | Normal Baustein     | Standard flowchart node (MOTOR, etc.)    |
| 0x2100     | Subprogram call     | btp → target subprogram's self_ptr       |
| 0x2700     | Graphic reference   | btp → graphic block's self_ptr           |
| 0x2742     | Graphic container   | Inside a graphic block (bitmap element)  |
| 0x0D42     | Sentinel/terminator | Marks end of an element list             |
| 0x2042     | Text annotation     | Free-text label on the canvas            |
| 0x2142     | Text annotation     | Variant (possibly different styling)     |
| 0x202D     | Subprogram entry    | Entry node; label in da_data byte 0      |
| 0x212D     | Subprogram entry    | Entry node variant                       |
| 0x202C     | Subprogram exit     | Exit node; label in da_data byte 0       |
| 0x212C     | Subprogram exit     | Exit node variant                        |

**Class ID pattern:** Entry nodes share low byte `0x2D`; exit nodes share low
byte `0x2C`. The high byte varies (0x20, 0x21, possibly others). Match on
`(class_id & 0xFF)` for reliable detection, combined with pin counts
(`nop ≥ 1, nic = 0` for entry; `nop = 0, nic ≥ 1` for exit).

## Appendix F: Graphic / Bitmap Encoding

Graphic subprograms reference external BMP files. The graphic block's 0xEC header
contains a filename at offset +0x88 (within the `display_data` region). The BMP
data is NOT embedded in the MDL file.

Example from GELD.MDL: the graphic subprogram references `GELDW.BMP`, found at
`PROFI/BITMAP/GELDW.BMP` (350x206 pixels, 4-bit Windows 3.x format).

Graphic elements (class_id 0x2700) in the main program reference the graphic
block via their `btp` field (pointing to the graphic block's self_ptr).
