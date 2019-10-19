#!/usr/bin/env python3

from alignment.modules.trackReader import trackReader
from alignment.sensors import icp

from tqdm import tqdm
from collections import defaultdict  # to concatenate dictionaries
from pathlib import Path
import json

import numpy as np
import pyMille
import re
import sys

"""
Author: R. Klasen, roklasen@uni-mainz.de or r.klasen@gsi.de

TODO: Implement corridor alignment

steps:
- read tracks and reco files
- extract tracks and corresponding reco hits
- separate by x and y
- give to millepede
- obtain alignment parameters from millepede
- convert to alignment matrices

"""

class alignerModules:
    def __init__(self):

        self.reader = trackReader()
        print(f'reading detector parameters...')
        self.reader.readDetectorParameters()
        print(f'reading processed tracks file...')
        #self.reader.readTracksFromJson(Path('input/modulesAlTest/tracks_processed-singlePlane.json'))
        self.reader.readTracksFromJson(Path('input/modulesAlTest/tracks_processed-modules-1.0.json'))
        # self.reader.readTracksFromJson(Path('input/modulesAlTest/tracks_processed-aligned.json'))

    def dynamicCut(self, cloud1, cloud2, cutPercent=2):

        assert cloud1.shape == cloud2.shape

        if cutPercent == 0:
            return cloud1, cloud2

        # calculate center of mass of differences
        dRaw = cloud2 - cloud1
        com = np.average(dRaw, axis=0)

        # shift newhit2 by com of differences
        newhit2 = cloud2 - com

        # calculate new distance for cut
        dRaw = newhit2 - cloud1
        newDist = np.power(dRaw[:, 0], 2) + np.power(dRaw[:, 1], 2)

        # sort by distance and cut some percent from start and end (discard outliers)
        cut = int(len(cloud1) * cutPercent/100.0)
        
        # sort by new distance
        cloud1 = cloud1[newDist.argsort()]
        cloud2 = cloud2[newDist.argsort()]
        
        # cut off largest distances, NOT lowest
        cloud1 = cloud1[:-cut]
        cloud2 = cloud2[:-cut]

        return cloud1, cloud2

    def alignMillepede(self):

        # TODO: sort better by sector!
        sector = 0

        milleOut = f'output/millepede/moduleAlignment-sector{sector}.bin'

        MyMille = pyMille.Mille(milleOut, True, True)
        
        sigmaScale = 1e1
        gotems = 0
        endCalls = 0

        labels = np.array([1,2,3,4,5,6,7,8,9,10,11,12])
        # labels = np.array([1,2,3])

        outFile = ""

        print(f'Running pyMille...')
        for params in self.reader.generatorMilleParameters():
            if params[4] == sector:
                # TODO: slice here, use only second plane
                # paramsN = params[0][3:6]
                # if np.linalg.norm(np.array(paramsN)) == 0:
                #     continue

                # TODO: this order of parameters does't match the interface!!!
                MyMille.write(params[1], params[0], labels, params[2], params[3]*sigmaScale)
                # print(f'params: {paramsN}')
                # print(f'residual: {params[2]}, sigma: {params[3]*sigmaScale} (factor {params[2]/(params[3]*sigmaScale)})')
                # labels += 3
                gotems += 1

                outFile += f'{params[1]}, {params[0]}, {labels}, {params[2]}, {params[3]*sigmaScale}\n'

            if (gotems % 200) == 0:
                    endCalls += 1
                    MyMille.end()


                # if gotems == 1e4:
                #     break
        
        MyMille.end()

        print(f'Mille binary data ({gotems} records) written to {milleOut}!')
        print(f'endCalls: {endCalls}')
        # now, pede must be called
    
        # with open('writtenData.txt', 'w') as f:
            # f.write(outFile)

    def alignICP(self):
        print(f'Oh Hai!')

        # open detector geometry
        with open('input/detectorMatricesIdeal.json') as f:
            detectorComponents = json.load(f)

        modules = []

        # get only module paths
        for path in detectorComponents:
            regex = r"^/cave_(\d+)/lmd_root_(\d+)/half_(\d+)/plane_(\d+)/module_(\d+)$"
            p = re.compile(regex)
            m = p.match(path)

            if m:
                # print(m.group(0))
                modules.append(m.group(0))
        
        results = {}
        # jesus what are you doing here
        for mod in tqdm(modules):
            tempMat = self.justFuckingRefactorMe(mod)

            # homogenize
            resultMat = np.identity(4)
            resultMat[:2, :2] = tempMat[:2, :2]
            resultMat[:2, 3] = tempMat[:2, 2]

            results[mod] =  np.ndarray.tolist(resultMat.flatten())

        # print(results)

        # with open('alMat-modules-1.0.json', 'w') as f:
        #     json.dump(results, f, indent=2)


    def justFuckingRefactorMe(self, module):
        arrayOne = []
        arrayTwo = []

        gotems = 0

        for line in self.reader.generateICPParameters(module):
            # if True:
            arrayOne.append(np.ndarray.tolist(line[0]))
            arrayTwo.append(np.ndarray.tolist(line[1]))

            gotems += 1

            if gotems == 2000:
                break

        arrayOne = np.array(arrayOne)
        arrayTwo = np.array(arrayTwo)

        # nElem = len(arrayOne)/3

        # arrayOne = arrayOne.reshape((int(nElem), 3))
        # arrayTwo = arrayTwo.reshape((int(nElem), 3))

        if True:
            arrayOne, arrayTwo = self.dynamicCut(arrayOne, arrayTwo, 90)

        if False:

            # print(f'Average Distances for {module}:')
            dVec = arrayOne-arrayTwo
            # print(f'{np.average(dVec, axis=0)*1e4}')

            #! begin hist

            print(dVec.shape)

            import matplotlib
            import matplotlib.pyplot as plt
            from matplotlib.colors import LogNorm
            matplotlib.use('QT4Agg')

            # plot difference hit array
            fig = plt.figure(figsize=(16/2.54, 16/2.54))
            
            histB = fig.add_subplot()
            histB.hist2d(dVec[:, 0]*1e4, dVec[:, 1]*1e4, bins=150, norm=LogNorm(), label='Count (log)')
            histB.set_title(f'2D Distance\n{module}')
            histB.yaxis.tick_right()
            histB.yaxis.set_ticks_position('both')
            histB.set_xlabel('dx [µm]')
            histB.set_ylabel('dy [µm]')
            histB.tick_params(direction='out')
            histB.yaxis.set_label_position("right")

            fig.show()
            input()

            #! end hist

        # use 2D values
        arrayOne = arrayOne[..., :2]
        arrayTwo = arrayTwo[..., :2]

        # print(f'both arrays:\n{arrayOne}\n{arrayTwo}')

        T, _, _ = icp.best_fit_transform(arrayOne, arrayTwo)

        # print(f'T is:\n{T*1e4}')

        return T

        # print(f'Result transformation:\n{T}')