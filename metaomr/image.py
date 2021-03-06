from PIL import Image
import tempfile
import os
import shutil
import sys
from StringIO import StringIO
import subprocess
import numpy as np
from . import settings
try:
  from .pdfimage import pdf_to_images
except ImportError:
  sys.stderr.write("PDF import disabled; please install pylibtiff\n")
  pdf_to_images = None

def image_array(data):
  if type(data) is str:
    im = Image.open(StringIO(data))
  else:
    im = data
  im = im.convert('1')
  MAXSIZE = settings.IMAGE_MAX_SIZE
  if im.size[0] > MAXSIZE and im.size[0] > im.size[1]:
    im = im.resize((MAXSIZE, im.size[1]*MAXSIZE/im.size[0]))
  elif im.size[1] > MAXSIZE:
    im = im.resize((im.size[0]*MAXSIZE/im.size[1], MAXSIZE))
  im = im.convert('L')
  bytestring = im.tostring()
  pixels = np.fromstring(bytestring, dtype=np.uint8)
  pixels = pixels.reshape((im.size[1], im.size[0]))
  # Heuristic to detect whether image needs inverting
  if (pixels != 0).sum() > im.size[0] * im.size[1] / 2:
    # Swap pixels so colored pixels are 1
    np.logical_not(pixels, output=pixels)
  else:
    pixels[pixels != 0] = 1
  return pixels

# Open image or multi-page PDF, return list of data (or PIL Images)
def read_pages(path):
  if isinstance(path, basestring):
    path = open(path, 'rb')
  images = []
  path.seek(0)
  if path.read(4) == '%PDF':
    if pdf_to_images is None:
      images = fallback_pdf_to_images(path)
    else:
      images = pdf_to_images(path)
      if not len(images):
        images = fallback_pdf_to_images(path)
  else:
    path.seek(0)
    images = [path.read()]
  return images

def fallback_pdf_to_images(pdf):
  "Convert pdf using pdfimages subprocess"
  import glob
  import os
  import shutil
  import subprocess
  import tempfile
  tmpdir = tempfile.mkdtemp()
  try:
    subprocess.check_output(['pdfimages', pdf.name,
                             os.path.join(tmpdir, 'img')])
    images = sorted(glob.glob(os.path.join(tmpdir, 'img-*.pbm')))
    return [open(path).read() for path in images]
  finally:
    shutil.rmtree(tmpdir)
