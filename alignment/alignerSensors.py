#!/usr/bin/env python3

from alignment.sensors.alignmentMatrixCombiner import alignmentMatrixCombiner
from alignment.sensors.matrixComparator import overlapComparator
from alignment.sensors.hitPairSorter import hitPairSorter
from alignment.sensors.sensorMatrixFinder import sensorMatrixFinder

from detail.LMDRunConfig import LMDRunConfig

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import collections
import concurrent
import json
import numpy as np

"""
Author: R. Klasen, roklasen@uni-mainz.de or r.klasen@gsi.de

This aligner needs a LMDRunConfig object. It will then:

- read Lumi_Pairs_*.root files
- sort to numpy files
- read all numpy files
- find overlap matrices
- compute misalignment matrices from overlap matrices
- save them as deviation matrices to json

Info: all positional vectors are row-major! This aligner also need info about the geometry
to transform sensor-local matrices to PANDA global:

- detectorOverlapsIdeal.json | containing all design matrices of the Luminosity detector 

TODO: save overlap matrices to json file!
TODO: save log, how many pairs were available for each overlap?
"""


class alignerSensors:

    def __init__(self):
        self.idealOverlapsPath = Path('input') / Path('detectorOverlapsIdeal.json')
        self.idealDetectorMatrixPath = Path('input') / Path('detectorMatricesIdeal.json')
        self.availableOverlapIDs = self.getOverlapsFromJSON()
        self.overlapMatrices = {}     
        self.alignmentMatrices = {}                                                      # dictionary overlapID: matrix
        self.lock = Lock()

    @classmethod
    def fromRunConfig(cls, runConfig):
        temp = cls()
        temp.config = runConfig
        return temp

    def loadExternalMatrices(self, fileName):
        with open(fileName) as f:
            self.externalMatrices = json.load(f)

    # this retrieves overlapIDs from the json file
    def getOverlapsFromJSON(self):
        overlapIDs = []
        with open(self.idealOverlapsPath) as overlapsFile:
            idealOverlaps = json.load(overlapsFile)

        for overlapID in idealOverlaps:
            overlapIDs.append(overlapID)

        return overlapIDs

    def sortPairs(self):
        pairSourcePath = Path(self.config.pathTrksQA())
        numpyPairPath = pairSourcePath / Path('npPairs')

        sorter = hitPairSorter(pairSourcePath, numpyPairPath)
        sorter.availableOverlapIDs = self.availableOverlapIDs

        sorter.sortAll()

    def findSingleMatrix(self, overlapID, numpyPath, idealOverlapsPath):

        matrixFinder = sensorMatrixFinder(overlapID)

        with open(idealOverlapsPath, 'r') as f:
            idealOverlapInfos = json.load(f)

        with open(self.idealDetectorMatrixPath) as idealMatricesFile:
            idealDetectorMatrices = json.load(idealMatricesFile)

        matrixFinder.idealOverlapInfos = idealOverlapInfos
        matrixFinder.idealDetectorMatrices = idealDetectorMatrices
        matrixFinder.readNumpyFiles(numpyPath)

        matrixFinder.findMatrix()

        matrix = matrixFinder.getOverlapMatrix()

        # python dictionaries might be thread safe, but just in case
        with self.lock:
            self.overlapMatrices[overlapID] = matrix

    def findMatrices(self):
        # setup paths
        numpyPath = self.config.pathTrksQA() / Path('npPairs')

        if self.config.useDebug:
            print(f'Finding matrices single-threaded!')
            for overlapID in self.availableOverlapIDs:
                self.findSingleMatrix(overlapID, numpyPath, self.idealOverlapsPath)

        else:
            # TODO: automatically set to something reasonable
            maxThreads = 16
            print('Waiting for all Sensor Aligners...')

            with concurrent.futures.ThreadPoolExecutor(max_workers=maxThreads) as executor:
                for overlapID in self.availableOverlapIDs:
                    executor.submit(self.findSingleMatrix, overlapID, numpyPath, self.idealOverlapsPath)

            # wait for all threads, this might not even be needed
            executor.shutdown(wait=True)

    def combineAlignmentMatrices(self):

        if self.externalMatrices == None:
            print('Error! Please set externally measured matrices!')

        # these are important! the combiner MUST only get the overlap matrices
        sortedMatrices = collections.defaultdict(dict)
        sortedOverlaps = collections.defaultdict(dict)

        with open(self.idealOverlapsPath) as overlapsFile:
            idealOverlaps = json.load(overlapsFile)

        # sort overlap matrices by module they are on
        for overlapID in self.availableOverlapIDs:
            modulePath = idealOverlaps[overlapID]['pathModule']
            sortedMatrices[modulePath].update({overlapID: self.overlapMatrices[overlapID]})

        print(f'found {len(sortedMatrices)}, modules, should be 40.')

        # sort overlapInfos to dict by module path
        for modulePath in sortedMatrices:
            for overlapID in idealOverlaps:
                if idealOverlaps[overlapID]['pathModule'] == modulePath:
                    sortedOverlaps[modulePath].update({overlapID: idealOverlaps[overlapID]})

        with open(self.idealDetectorMatrixPath) as idealMatricesFile:
            idealMatrices = json.load(idealMatricesFile)

        for modulePath in sortedMatrices:
            combiner = alignmentMatrixCombiner(modulePath)

            combiner.setIdealDetectorMatrices(idealMatrices)
            combiner.setOverlapMatrices(sortedMatrices[modulePath])
            combiner.setExternallyMeasuredMatrices(self.externalMatrices)

            combiner.combineMatrices()

            resultMatrices = combiner.getAlignmentMatrices()
            self.alignmentMatrices.update(resultMatrices)

        print(f'combined for all sensors on all modules. length: {len(self.alignmentMatrices)}')

    def saveOverlapMatrices(self, outputFile):
        # first, flatten all alignment matrices before saving them to json
        saveOverlapMatrices = {}

        for overlapID in self.overlapMatrices:
            saveOverlapMatrices[overlapID] = np.ndarray.tolist(self.overlapMatrices[overlapID].flatten())

        if Path(outputFile).exists():
            print(f'WARNING. Replacing file: {outputFile}!\n')
            Path(outputFile).unlink()

        if not Path(outputFile).parent.exists():
            Path(outputFile).parent.mkdir()

        with open(outputFile, 'w') as outfile:
            print(f'\nSaving alignment matrix to file: {outputFile}\n\n')
            json.dump(saveOverlapMatrices, outfile, indent=2)
        
    def saveAlignmentMatrices(self, outputFile):
        
        # first, flatten all alignment matrices before saving them to json
        for path in self.alignmentMatrices:
            self.alignmentMatrices[path] = np.ndarray.tolist(self.alignmentMatrices[path].flatten())

        if Path(outputFile).exists():
            print(f'WARNING. Replacing file: {outputFile}!\n')
            Path(outputFile).unlink()

        if not Path(outputFile).parent.exists():
            Path(outputFile).parent.mkdir()

        with open(outputFile, 'w') as outfile:
            print(f'\nSaving alignment matrix to file: {outputFile}\n\n')
            json.dump(self.alignmentMatrices, outfile, indent=2)
        
if __name__ == "__main__":
    print(f'Error! Can not be run individually!')
