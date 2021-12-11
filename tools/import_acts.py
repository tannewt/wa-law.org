import PyPDF2
import math

from PyPDF2.pdf import ContentStream
from PyPDF2.generic import TextStringObject, NumberObject

o = open("/home/tannewt/Downloads/1879pam1.pdf", "rb")

reader = PyPDF2.PdfFileReader(o)

print(reader.numPages)

page = reader.getPage(225)

def key(entry):
    position = entry[0]
    return (1000 - position[0], position[1])

def x_only(entry):
    return entry[0][1]

def extract_text(page):
    content = page["/Contents"].getObject()
    print(type(content))
    if not isinstance(content, ContentStream):
        content = ContentStream(content, page.pdf)
    # Note: we check all strings are TextStringObjects.  ByteStringObjects
    # are strings where the byte->string encoding was unknown, so adding
    # them to the text here would be gibberish.
    #print(content.operations)
    text_pieces = []
    for operands, operator in content.operations:
        if operator == b"Tj":
            _text = operands[0]
            if isinstance(_text, TextStringObject):
                text_pieces.append((current_position, _text))
        # elif operator == b"T*":
        #     text += "\n"
        # elif operator == b"'":
        #     text += "\n"
        #     _text = operands[0]
        #     if isinstance(_text, TextStringObject):
        #         text += operands[0]
        # elif operator == b'"':
        #     _text = operands[2]
        #     if isinstance(_text, TextStringObject):
        #         text += "\n"
        #         text += _text
        elif operator == b"TJ":
            print(operands)
            all_text = []
            for o in operands[0]:
                print(o)
                if isinstance(o, TextStringObject):
                    all_text.append(o)
                # elif isinstance(o, NumberObject):
                #     print("old", current_position)
                #     current_position = (current_position[0], current_position[1] - int(o) / 100)
                #     print("new", current_position)
            text_pieces.append((current_position, "".join(all_text)))
        elif operator == b"Tm":
            print(operator, operands)
            current_position = tuple(map(float, reversed(operands[-2:])))
        elif operator == b"Td":
            print(operator, operands)
            print("old", current_position)
            current_position = (current_position[0] + float(operands[1]), current_position[1] + float(operands[0]))
            print("new", current_position)
        # b"Tr" sets the text to invisible
        else:
            print(operator, operands)
    text_pieces = sorted(text_pieces, key=key)
    last_position = None
    all_lines = []
    current_line = []
    # Do a first pass to split lines
    for entry in text_pieces:
        position, text = entry
        diff = 0
        if last_position is not None:
            diff = last_position[0] - position[0]
        if diff > 6:
            all_lines.append(current_line)
            current_line = []
        current_line.append(entry)
        last_position = position
    all_lines.append(current_line)
    all_joined = []
    # Do a second pass to re-sort the line entries and then join
    for line in all_lines:
        sorted_line = sorted(line, key=x_only)
        last_x = None
        last_length = 1
        for position, text in sorted_line:
            x = position[1]
            diff = 0
            if last_x:
                diff = x - last_x

            print(x, diff / last_length, "'" + text + "'")
            last_x = x
            last_length = len(text)
        print()
        all_joined.append("".join([x[1] for x in sorted_line]))
        
    return "\n".join(all_joined)

t = extract_text(page)
print(t)

o.close()
