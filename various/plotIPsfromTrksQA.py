#!/usr/bin/env python3

from collections import defaultdict  # to concatenate dictionaries

import numpy as np
import uproot
import sys

"""
reads TrksQA.root files (supports wildcards like Lumi_TrksQA_*.root through uproot!) and returns the most probable IP position

uses 98% cut by default
set module=i to filter by module i, same for half
"""


def getIPfromTrksQA(filename, cut=5.0, sensor=-1, module=-1, plane=-1, half=-1):

    # uproot.iterate will produce a dict with JaggedArrays, so we can create an empty dict and append each iteration
    resultDict = defaultdict(list)

    try:
        # open the root trees in a TChain-like manner
        print('reading files...')
        for array in uproot.iterate(filename, 'pndsim', [b'LMDTrackQ.fTrkRecStatus', b'LMDTrackQ.fHalf', b'LMDTrackQ.fModule', b'LMDTrackQ.fXrec', b'LMDTrackQ.fYrec', b'LMDTrackQ.fZrec']):
            clean = cleanArray(array)

            for key in clean:
                resultDict[key] = np.append(resultDict[key], clean[key], axis=0)

    except Exception as e:
        print('error occured:')
        print(e)
        sys.exit(0)

    # return extractIP(extractIP, -1, -1)

    # great, at this point I now have a dictionary with the keys mod, x, y, z and numpy arrays for the values. perfect!
    if cut > 0.01:
        resultDict = percentileCut(resultDict, cut)

    ip = extractIP(resultDict, module, half)

    return ip


def extractIP(cleanArray, module, half):

    thalf = cleanArray['half']
    tmod = cleanArray['mod']
    recX = cleanArray['x']
    recY = cleanArray['y']
    recZ = cleanArray['z']

    # apply a mask to remove outliers
    recMask = (np.abs(recX) < 5000) & (np.abs(recY) < 5000)

    if module > 0:
        recMask = recMask & (module == tmod)
    if half > 0:
        recMask = recMask & (half == thalf)

    # this is the position of the interaction point!
    ip = [np.average(recX[recMask]), np.average(recY[recMask]), np.average(recZ[recMask]), 1.0]
    
    print(f'average IP: {ip}')

    # return ip

    result = np.zeros((len(recX), 3))
    result[:, 0] = recX[recMask]
    result[:, 1] = recY[recMask]
    result[:, 2] = recZ[recMask]

    return result
    # return ip


def percentileCut(arrayDict, cut):

    # first, remove outliers that are just too large, use a mask
    outMaskLimit = 5000
    outMask = (np.abs(arrayDict['x']) < outMaskLimit) & (np.abs(arrayDict['y']) < outMaskLimit) & (np.abs(arrayDict['z']) < outMaskLimit)

    # cut outliers, this creates a copy (performance?)
    for key in arrayDict:
        arrayDict[key] = arrayDict[key][outMask]

    # create new temp array to perform all calculations on - numpy style
    tempArray = np.array((arrayDict['x'], arrayDict['y'], arrayDict['z'], arrayDict['mod'], arrayDict['half'])).T

    # calculate cut length, we're cutting 2%
    cut = int(len(tempArray) * (cut / 100))

    # calculate approximate c.o.m. and shift
    # don't use average, some values are far too large, median is a better estimation
    comMed = np.median(tempArray, axis=0)
    tempArray -= comMed

    # sort by distance and cut largest
    distSq = np.power(tempArray[:, 0], 2) + np.power(tempArray[:, 1], 2) + np.power(tempArray[:, 2], 2)
    tempArray = tempArray[distSq.argsort()]
    tempArray = tempArray[:-cut]

    # shift back
    tempArray += comMed

    # re-save to array for return
    arrayDict['x'] = tempArray[:, 0]
    arrayDict['y'] = tempArray[:, 1]
    arrayDict['z'] = tempArray[:, 2]
    arrayDict['mod'] = tempArray[:, 3]
    arrayDict['half'] = tempArray[:, 4]

    return arrayDict


def cleanArray(arrayDict):

    # okay, so arrays is a multi dimensional array, or jagged array. some lines don't have any values,
    # while some lines have multiple entries. a single line is an event, which is why the array is exactly
    # 100k lines long. a line can have none, one or multiple entries, so first we need to filter out empty events:

    # use just the recStatus for indexes, this tells us how many recs there are per event
    recStatusJagged = arrayDict[b'LMDTrackQ.fTrkRecStatus']
    nonZeroEvents = (recStatusJagged.counts > 0)

    # flatten all arrays for ease of access and apply a mask.
    # this is numpy notation to select some entries according to a criterion and works very fast:
    half = arrayDict[b'LMDTrackQ.fHalf'][nonZeroEvents].flatten()
    module = arrayDict[b'LMDTrackQ.fModule'][nonZeroEvents].flatten()
    recX = arrayDict[b'LMDTrackQ.fXrec'][nonZeroEvents].flatten()
    recY = arrayDict[b'LMDTrackQ.fYrec'][nonZeroEvents].flatten()
    recZ = arrayDict[b'LMDTrackQ.fZrec'][nonZeroEvents].flatten()

    # return a dict
    return {'half': half, 'mod': module, 'x': recX, 'y': recY, 'z': recZ}


if __name__ == "__main__":
    filePath = 'Lumi_TrksQA_100000.root'

    resultDict = getIPfromTrksQA(filePath, 5.0)
    print(resultDict)

    #! begin hist

    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    
    # plot difference hit array
    fig = plt.figure(figsize=(17/2.54, 9/2.54))
    # fig.suptitle('reconstructed target position')
    axis = fig.add_subplot(1,2,1)
    axis.hist2d(resultDict[:, 0]*1e1, resultDict[:, 1]*1e1, bins=50, norm=LogNorm(), label='Count (log)')#, range=((-300,300), (-300,300)))
    axis.set_title(f'x-y position')
    axis.yaxis.tick_left()
    # axis.yaxis.set_ticks_position('both')
    axis.set_xlabel('px [mm]')
    axis.set_ylabel('py [mm]')
    axis.tick_params(direction='out')
    axis.yaxis.set_label_position("left")

    axis2 = fig.add_subplot(1,2,2)
    axis2.hist(resultDict[:, 2]*1e1, bins=50, log=True)#, range=((-300,300), (-300,300)))
    axis2.set_title(f'z position')
    # axis2.yaxis.set_yscale('log')
    axis2.yaxis.tick_right()
    # axis2.yaxis.set_ticks_position('both')
    axis2.set_xlabel('dz [mm]')
    axis2.set_ylabel('count [log]')
    axis2.tick_params(direction='out')
    axis2.yaxis.set_label_position("right")

    # fig.show()
    fig.tight_layout()
    fig.savefig(f'IP-distribution-cut.png')
    plt.close(fig)
    #! end hist