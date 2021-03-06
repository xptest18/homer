from Tkinter import *
from PIL import ImageTk
from PIL import Image
import numpy as np
import os
import subprocess
import sys
import tempfile
import glob
import shutil
import json

pdfpath = sys.argv[1]
jsonpath = sys.argv[2]
tmpdir = tempfile.mkdtemp()
subprocess.call(['/usr/bin/env', 'pdfimages', pdfpath, os.path.join(tmpdir,'p')])
images = glob.glob(os.path.join(tmpdir,'p-*.pbm'))
if not images:
    sys.exit(1)

def get_images():
    for img in images:
        yield Image.open(img)
    shutil.rmtree(tmpdir)

t=Tk()
W=900
H=1200
SH=800
f=Frame(t,width=W,height=SH)
f.grid(row=0,column=0)

pages = []
staves = None
gen = get_images()
cv = Canvas(f, width=W, height=SH, scrollregion=(0,0,W,H))

vbar = Scrollbar(f,orient=VERTICAL)
vbar.pack(side=RIGHT,fill=Y)
vbar.config(command=cv.yview)
cv.config(yscrollcommand=vbar.set)
cv.pack(side=LEFT,expand=True,fill=BOTH)
def next_image(x):
    global img, imgTk, scale, staves
    if staves is not None:
        pages.append(staves)
        staves = []
    try:
        img = gen.next()
    except StopIteration:
        json.dump(pages, open(jsonpath, 'wb'))
        sys.exit(0)
    imgsize = img.size
    scale = min(float(W)/imgsize[0], float(H)/imgsize[1])
    newsize = map(int, [imgsize[0]*scale, imgsize[1]*scale])
    imgTk = ImageTk.PhotoImage(img.convert('L').resize(newsize, Image.ANTIALIAS))
    cv.delete('all')
    cv.create_image(newsize[0]/2,newsize[1]/2,image=imgTk)
next_image(None)
staves = []
cur_staff = None
cur_lines = []
staffspace_line = None
staffspace = None
def get_staffspace(x,y):
    for (x0,y0),(x1,y1) in zip(cur_staff[:-1],cur_staff[1:]):
        if x0 <= x and x < x1:
            staff_y = y0 + (x - x0) * (y1 - y0) / (x1 - x0)
            return y - staff_y
    return 0
def click(e):
    global staves, cur_staff, cur_lines, staffspace_line
    img_point = [int(e.x / scale), int(e.y / scale)]
    if cur_staff is None:
        cur_staff = [img_point]
        cur_lines = []
    elif staffspace_line:
        staves.append(dict(center=cur_staff, staffspace=int(abs(staffspace))))
        cur_staff = None
        cur_lines = []
        staffspace_line = None
    else:
        x0 = int(cur_staff[-1][0] * scale)
        y0 = int(cur_staff[-1][1] * scale)
        cur_lines.append(cv.create_line(x0, y0, e.x, e.y, fill='red'))
        cur_staff.append(img_point)
def motion(e):
    global cur_staff, staffspace_line, staffspace
    x = e.x / scale
    y = e.y / scale
    if staffspace_line is not None:
        staffspace = get_staffspace(x, y)
        for (x0,y0), (x1,y1), spaceseg in \
                zip(cur_staff[:-1], cur_staff[1:], staffspace_line):
            cv.coords(spaceseg, x0*scale, (y0+staffspace)*scale,
                                x1*scale, (y1+staffspace)*scale)
def remove_line(e):
    global cur_staff, cur_lines, staffspace_line
    if cur_lines and not staffspace_line:
        cv.delete(cur_lines.pop())
        cur_staff.pop()
    elif cur_staff and not staffspace_line:
        cur_staff = None
        cur_lines = []
def key(e):
    if e.char == ' ':
        global staves, cur_staff, staffspace_line
        assert cur_staff
        if staffspace_line is None:
            staffspace_line = [cv.create_line(0,0,0,0,fill='blue')
                               for seg in cur_staff[:-1]]

t.bind('<Return>', next_image)
cv.bind('<Button-1>', click)
t.bind('<BackSpace>', remove_line)
t.bind('<Key>', key)
t.bind('<Motion>', motion)
t.focus()
t.mainloop()
