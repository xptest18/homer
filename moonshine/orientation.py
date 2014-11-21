from .gpu import *
from . import bitimage, hough
import numpy as np
from reikna.core import Type
import reikna.fft

prg = build_program(['rotate', 'bitimage'])

def rotate(page, force_orientation=None):
    if force_orientation is not None:
        page.orientation = force_orientation
    else:
        orientation(page)
    new_img = rotate_kernel(page.img, page.orientation)
    page.img = new_img
    page.bitimg = new_img.get()
    page.byteimg = bitimage.as_hostimage(new_img)
    return page.orientation

def rotate_kernel(img, theta):
    new_img = thr.empty_like(img)
    new_img.fill(0)
    prg.rotate_image(img,
                     np.cos(theta).astype(np.float32),
                     np.sin(theta).astype(np.float32),
                     new_img,
                     global_size=(img.shape[1], img.shape[0]))
    return new_img

def patch_orientation_numpy(page, patch_size=256, step_size=None):
    if step_size is None:
        step_size = patch_size/2
    patch_x0 = np.arange(0, page.orig_size[1] - patch_size, step_size)
    patch_y0 = np.arange(0, page.orig_size[0] - patch_size, step_size)
    orientations = np.zeros((len(patch_y0), len(patch_x0)))
    mask = np.zeros_like(orientations, dtype=bool)

    # Windowed FFT
    # We can probably get away with a box filter.
    # The strongest response represents the staves, and should be slightly
    # rotated from vertical. There are also higher frequencies at multiples
    # of the actual staff size. We try to get the peak which is at a
    # frequency 3 times higher than the actual staff size, by zeroing out
    # all but a band around there.
    # For good measure, patch_size should be at least 10*staff_dist.
    # (it actually needs to be >> 6*staff_dist)
    for patch_y in xrange(orientations.shape[0]):
        for patch_x in xrange(orientations.shape[1]):
            patch = page.byteimg[patch_y*patch_size:(patch_y+1)*patch_size,
                                 patch_x*patch_size:(patch_x+1)*patch_size]
            patch_fft = np.abs(np.fft.fft2(patch))
            fft_top = patch_fft[:patch_size/2]
            fft_top[:int(page.staff_dist*2.5)] = 0
            fft_top[int(page.staff_dist*3.5):] = 0
            peak_y, peak_x = np.unravel_index(np.argmax(fft_top),
                                              fft_top.shape)
            if peak_x > patch_size/2:
                peak_x -= patch_size
            if peak_y:
                orientations[patch_y, patch_x] = np.arctan2(peak_x, peak_y)
            else:
                mask[patch_y, patch_x] = True
    return np.ma.masked_array(orientations, mask)

def patch_orientation(page, patch_size=256, step_size=None):
    if step_size is None:
        step_size = patch_size/4
    patch_x0 = np.arange(0, page.orig_size[1] - patch_size, step_size)
    patch_y0 = np.arange(0, page.orig_size[0] - patch_size, step_size)
    orientations = np.zeros((len(patch_y0), len(patch_x0)))
    score = np.zeros_like(orientations)
    mask = np.zeros_like(orientations, dtype=bool)

    patch = thr.empty_like(Type(np.complex64, (patch_size, patch_size)))
    our_fft = reikna.fft.FFT(patch).compile(thr)
    patch_fft = thr.empty_like(patch)
    for i, y0 in enumerate(patch_y0):
        for j, x0 in enumerate(patch_x0):
            prg.copy_bits_complex64(
                page.img,
                np.int32(x0),
                np.int32(y0),
                np.int32(page.img.shape[1]),
                patch, global_size=patch.shape[::-1])
            our_fft(patch_fft, patch)
            fft_top = np.abs(patch_fft[:patch_size/2].get())
            fft_top[:int(page.staff_dist*2.5)] = 0
            fft_top[int(page.staff_dist*3.5):] = 0
            peak_y, peak_x = np.unravel_index(np.argmax(fft_top),
                                              fft_top.shape)

            maxval = np.amax(fft_top)
            fft_top[max(0, peak_y-page.staff_thick*2)
                        : min(fft_top.shape[0], peak_y+page.staff_thick*2),
                    max(0, peak_x-page.staff_thick*2)
                        : min(fft_top.shape[1], peak_x+page.staff_thick*2)] = 0
            bgval = np.amax(fft_top)
            if bgval > 0:
                score[i, j] = maxval / bgval

            if peak_x > patch_size/2:
                peak_x -= patch_size
            if peak_y:
                orientations[i, j] = np.arctan2(peak_x, peak_y)
            else:
                mask[i, j] = True
    return np.ma.masked_array(np.dstack([orientations, score]),
                    np.repeat(mask[:,:,None], 2, axis=2))

def orientation(page):
    assert type(page.staff_dist) is not tuple, \
           "Multiple staff sizes not supported"
    patch_size = 1024
    while page.staff_dist * 10 > patch_size:
        patch_size *= 2
    assert patch_size <= 2048
    patches = patch_orientation(page, patch_size)
    orientations = patches[:,:,0]
    scores = patches[:,:,1]
    score_cutoff = min(1.5, np.ma.median(scores) * 2)
    page.orientation = float(np.ma.mean(orientations[scores >= score_cutoff]))
    if np.isnan(page.orientation):
        page.orientation = 0.0
    return page.orientation
