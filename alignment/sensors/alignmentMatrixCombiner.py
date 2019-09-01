#!/usr/bin/env python3

import json
import numpy as np
from numpy.linalg import inv

"""
Author: R. Klasen, roklasen@uni-mainz.de or r.klasen@gsi.de

Uses multiple overlap matrices and the ideal detector matrices to compute alignment matrices for each sensor.
Each combiner is responsible for a single module.

Steps:

WAIT UPDATE

Okay so now I can create the overlap matrices like they are in the geometry (with alignment) from the ideal matrices plus the misalignment for the overlap.
perfect, I only need to do the three steps I did to arrive here backwards! no base transforming etc, just do the three steps backwards.

END UPDATE

REMEMBER. The overlap matrices come from the Reco Points and are thusly already in PANDA global!

- gather perfect 0->x matrices
- substract (inverse multiply actually) perfect matrices to combined 0->x matrices
- remainder is misalignment AS GIVEN IN PANDA GLOBAL SYSTEM
- base transform each misalignment matrix to system of respective sensor
- save to dict, return to master
"""


class alignmentMatrixCombiner:

    def __init__(self, modulePath):
        self.modulePath = modulePath
        self.alignmentMatrices = {}
        self.overlapMatrices = None
        self.overlapInfos = None
        self.idealDetectorMatrices = None
        self.externalMatrices = None

    def setOverlapMatrices(self, matrices):
        self.overlapMatrices = matrices

    def setIdealDetectorMatrices(self, matrices):
        self.idealDetectorMatrices = matrices

    def setExternallyMeasuredMatrices(self, matrices):
        self.externalMatrices = matrices

    def setOverlapInfos(self, infos):
        # should only contain the overlap infos relevant to THIS combiner, not all the overlaps!
        self.overlapInfos = infos
        tempDict = {}
        # add small overlap to each overlap info, we'll need that info later
        for info in self.overlapInfos:

            # check if modulePath from constructor and overlapInfo match
            if self.modulePath != self.overlapInfos[info]['pathModule']:
                print(f"ERROR! Module path mis match: {self.modulePath} and {self.overlapInfos[info]['pathModule']}")

            smallOverlap = self.getSmallOverlap(info)
            self.overlapInfos[info]['smallOverlap'] = smallOverlap
            tempDict[smallOverlap] = self.overlapInfos[info]

        # and sort by new small overlap. that's okay, the real overlapID is still a field of the dict
        self.overlapInfos = tempDict

    def getDigit(self, number, n):
        return int(number) // 10**n % 10

    def getSmallOverlap(self, overlap):
        return str(self.getDigit(overlap, 0))

    def getAlignmentMatrices(self):
        return self.alignmentMatrices

    def getIdealMatrixP1ToP2(self, path1, path2):
        # matrix from pnd global to sen1
        m1 = np.array(self.idealDetectorMatrices[path1]).reshape(4, 4)
        # matrix from pnd global to sen2
        m2 = np.array(self.idealDetectorMatrices[path2]).reshape(4, 4)
        # matrix from sen1 to sen2
        return m2@inv(m1)

    def getMatrixP1ToP2fromMatrixDict(self, path1, path2, mat):
        # matrix from pnd global to sen1
        m1 = np.array(mat[path1]).reshape(4, 4)
        # matrix from pnd global to sen2
        m2 = np.array(mat[path2]).reshape(4, 4)
        # matrix from sen1 to sen2
        return m2@inv(m1)

    def getTotalOverlapMatrix(self, p1, p2):
        
        # prepare ideal matrix
        matPndTo1 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
        mat1to2ideal = self.getIdealMatrixP1ToP2(p1, p2)
        mat1to2idealIn1 = inv(matPndTo1) @ mat1to2ideal @ (matPndTo1)

        # prepare ICP matrix
        # TODO: change this to use the actual ICP matrix
        matICPmisalign1to2 = self.getOverlapMisalignLikeICP(p1, p2)
        matICP1to2In1 = inv(matPndTo1) @ matICPmisalign1to2 @ (matPndTo1)
        
        # make total matrix from ICP matrix and ideal matrix
        mat1to8TotalIn1 = matICP1to2In1 @ mat1to2idealIn1
        return mat1to8TotalIn1

    def combine1to2NEW(self):
        p1 = self.modulePath + '/sensor_1'
        p2 = self.modulePath + '/sensor_2'
        p8 = self.modulePath + '/sensor_8'

        mat1to8TotalIn1 = self.getTotalOverlapMatrix(p1, p8)
        mat2to8TotalIn2 = self.getTotalOverlapMatrix(p2, p8)

        # so, use the overlap matrices themselves to transform the matrices
        # I know this base transform is pointless, but for completeness sake leave it in!
        mat2to8TotalIn8 = mat2to8TotalIn2 @ mat2to8TotalIn2 @ inv(mat2to8TotalIn2)

        # I know the base transform looks inverted,
        # but that's because I need m8to1, and I only have m1to8. to that's fine.
        mat2to8TotalIn1 = inv(mat1to8TotalIn1) @ mat2to8TotalIn8 @ mat1to8TotalIn1

        # they are now both in the system of sensor 1
        mat1to2totalIn1 = inv(mat2to8TotalIn1) @ mat1to8TotalIn1
        return mat1to2totalIn1


    def combine1to2(self):
        p1 = self.modulePath + '/sensor_1'
        p2 = self.modulePath + '/sensor_2'
        p8 = self.modulePath + '/sensor_8'

        # I have thse matrices from the detector design
        mat1to8ideal = self.getIdealMatrixP1ToP2(p1, p8)
        mat2to8ideal = self.getIdealMatrixP1ToP2(p2, p8)

        matPndTo1 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
        matPndTo2 = np.array(self.idealDetectorMatrices[p2]).reshape(4, 4)

        #? get ICP matrices and transform them to their local sensor 1

        # this is the ICP-like matrix
        # TODO: change this to use the actual ICP matrix
        matICPmisalign1to8 = self.getOverlapMisalignLikeICP(p1, p8)
        matICPmisalign2to8 = self.getOverlapMisalignLikeICP(p2, p8)

        # this is the matrix the ICP finds in the frame of reference of MISALIGNED sensor 1/2
        mat1to8idealIn1 = inv(matPndTo1) @ mat1to8ideal @ (matPndTo1)
        mat2to8idealIn2 = inv(matPndTo2) @ mat2to8ideal @ (matPndTo2)

        #? make total overlap matrices

        # this is the trick! transform everything to sensor BEFORE you apply the ICP matrix to the ideal
        matICP1to8In1 = inv(matPndTo1) @ matICPmisalign1to8 @ (matPndTo1)
        # careful, this should be in sensor TWO, not one, because this is still local to 2!
        matICP2to8In2 = inv(matPndTo2) @ matICPmisalign2to8 @ (matPndTo2)

        # apply ICP matrix to ideal IN SENSOR 1/2!
        mat1to8TotalIn1 = matICP1to8In1 @ mat1to8idealIn1
        mat2to8TotalIn2 = matICP2to8In2 @ mat2to8idealIn2

        #? transform all total matrices to sensor 1

        # so, use the overlap matrices themselves to transform the matrices
        # I know this base transform is pointless, but for completeness sake leave it in!
        mat2to8TotalIn8 = mat2to8TotalIn2 @ mat2to8TotalIn2 @ inv(mat2to8TotalIn2)

        # I know the base transform looks inverted,
        # but that's because I need m8to1, and I only have m1to8. to that's fine.
        mat2to8TotalIn1 = inv(mat1to8TotalIn1) @ mat2to8TotalIn8 @ mat1to8TotalIn1

        #? finally, combine individual total matrices

        # they are now both in the system of sensor 1
        mat1to2totalIn1 = inv(mat2to8TotalIn1) @ mat1to8TotalIn1
        return mat1to2totalIn1

    def combineMatrices(self):
        # checks here
        if self.overlapMatrices is None or self.idealDetectorMatrices is None or self.overlapInfos is None:
            print(f'ERROR! Please set overlaps, overlap matrices and ideal detector matrices first!')
            return

        if self.externalMatrices is None:
            print(f'ERROR! Please set the externally measured matrices for sensor 0 and 1 for module {self.modulePath}!')
            return

        # these two matrices are measured externally, e.g. by microscope
        # for now, they are generated by a different function,
        # but the file description should not change anymore
        # m0t1 = self.getIdealMatrixP1ToP2(self.modulePath + '/sensor_0', self.modulePath + '/sensor_1')
        # m0mis = self.externalMatrices[self.modulePath]['mis0']
        # m1mis = self.externalMatrices[self.modulePath]['mis1']

        # ? create all intermediate matrices here
        m1t2icp = self.combine1to2NEW()
        # m1t3icp = m4 @ inv(m1)
        # m1t4icpa = m4 @ inv(m5) @ m6 @ inv(m2)
        # m1t4icpb = m4 @ inv(m1) @ m7 @ inv(m8)

        # m1t5icp = m0
        # m1t6icp = m4 @ inv(m1) @ m3
        # m1t7icp = m4 @ inv(m1) @ m7
        # m1t8icp = m4
        # m1t9icpa = m4 @ inv(m5) @ m6
        # m1t9icpb = m4 @ inv(m1) @ m7 @ inv(m8) @ m2

        # print(f'm0t1: {m0t1}')
        # print(f'm1t2: {m1t2icp}')
        # print(f'm1t3: {m1t3icp}')
        # print(f'm1t4a: {m1t4icpa}')
        # print(f'm1t4b: {m1t4icpb}')
        # print(f'm1t5: {m1t5icp}')
        # print(f'm1t6: {m1t6icp}')
        # print(f'm1t7: {m1t7icp}')
        # print(f'm1t8: {m1t8icp}')
        # print(f'm1t9a: {m1t9icpa}')
        # print(f'm1t9b: {m1t9icpb}')

        # TODO: delte these after everything else is completed. the combiner won't know the misalignment matrices at all!
        with open('input/misMatrices/misMat-sensors-1.00.json') as f:
            misalignMatrices = json.load(f)

        with open('input/detectorMatrices-sensors-1.00.json') as f:
            totalMatrices = json.load(f)

        if False:
            """
            # port this to the comparer! this is how you compare the overlap matrix to the simulation matrix
            ! DO NOT DELETE THIS BLOCK until you ported it to the comparer!
            """
            print('New test, ICP matrices should be in PND global now!')

            m0t5misIcp = self.overlapMatrices['0']

            matPndTo0 = np.array(self.idealDetectorMatrices[self.modulePath + '/sensor_0']).reshape(4, 4)
            matPndTo5 = np.array(self.idealDetectorMatrices[self.modulePath + '/sensor_5']).reshape(4, 4)

            matMisOn0 = np.array(misalignMatrices[self.modulePath + '/sensor_0']).reshape(4, 4)
            matMisOn5 = np.array(misalignMatrices[self.modulePath + '/sensor_5']).reshape(4, 4)

            matMisOn0InPnd = matPndTo0 @ matMisOn0 @ inv(matPndTo0)
            matMisOn5InPnd = matPndTo5 @ matMisOn5 @ inv(matPndTo5)

            matMis0to5 = matMisOn5InPnd @ inv(matMisOn0InPnd)

            #matMis0to5 = np.round(matMis0to5, 5)
            #m0t5misIcp = np.round(m0t5misIcp, 5)
            print(f'overlap matrix as seen by ICP vs from calculations:')
            self.dMat(m0t5misIcp, matMis0to5)

        if False:
            """
            This creates total overlap matrices from sensor A to B from the ICP matrix and the ideal matrix A to B!
            We can also compare the construced matrices with the actual matrices.
            ! DO NOT DELETE THIS BLOCK until you ported it to the comparer!
            """
            p1 = self.modulePath + '/sensor_0'
            p2 = self.modulePath + '/sensor_5'

            # I have thse matrices from the detector design
            mat0to5ideal = self.getIdealMatrixP1ToP2(p1, p2)
            matPndTo0 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
            matPndTo5 = np.array(self.idealDetectorMatrices[p2]).reshape(4, 4)

            # I don't have these!
            matMisOn0 = np.array(misalignMatrices[p1]).reshape(4, 4)
            matMisOn5 = np.array(misalignMatrices[p2]).reshape(4, 4)

            matMisOn0InPnd = matPndTo0 @ matMisOn0 @ inv(matPndTo0)
            matMisOn5InPnd = matPndTo5 @ matMisOn5 @ inv(matPndTo5)

            matPndTo0mis = matMisOn0InPnd @ matPndTo0
            matPndTo5mis = matMisOn5InPnd @ matPndTo5

            # this is the ICP-like matrix
            matICP0to5 = self.getOverlapMisalignLikeICP(p1, p2)

            # * but wait, we're in sensor local, transform everything here!
            mat0to5actually = self.getActualMatrixFromGeoManager(p1, p2)
            # this is mat0to5 as seen from the MISALIGNED sensor0! (which is what the ICP sees)
            # I don't know these, but this is just to see if I found the correct matrix.
            mat0to5actually = inv(matPndTo0mis) @ mat0to5actually @ (matPndTo0mis)

            # this is the matrix the ICP finds in the frame of reference of MISALIGNED sensor 0
            mat0to5idealIn0 = inv(matPndTo0) @ mat0to5ideal @ (matPndTo0)

            # this is the trick! transform everything to sensor BEFORE you apply the ICP matrix to the ideal
            matWanted = inv(matPndTo0) @ matICP0to5 @ (matPndTo0)

            # apply ICP matrix to ideal IN SENSOR 0!
            matWanted = matWanted @ mat0to5idealIn0
            print(f'my new difference')
            self.dMat(matWanted, mat0to5actually)

        # ? current work position

        if False:
            """
            Now, using the stuff I learned above, I can hopefully combine multiple matrices to get mat1to2
            """
            p1 = self.modulePath + '/sensor_1'
            p2 = self.modulePath + '/sensor_2'
            p8 = self.modulePath + '/sensor_8'

            # I have thse matrices from the detector design
            mat1to8ideal = self.getIdealMatrixP1ToP2(p1, p8)
            mat2to8ideal = self.getIdealMatrixP1ToP2(p2, p8)

            matPndTo1 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
            matPndTo2 = np.array(self.idealDetectorMatrices[p2]).reshape(4, 4)
            matPndTo8 = np.array(self.idealDetectorMatrices[p8]).reshape(4, 4)

            # I don't have these!
            matMisOn1 = np.array(misalignMatrices[p1]).reshape(4, 4)
            matMisOn2 = np.array(misalignMatrices[p2]).reshape(4, 4)
            matMisOn8 = np.array(misalignMatrices[p8]).reshape(4, 4)

            matMisOn1InPnd = matPndTo1 @ matMisOn1 @ inv(matPndTo1)
            matMisOn2InPnd = matPndTo2 @ matMisOn2 @ inv(matPndTo2)
            matMisOn8InPnd = matPndTo8 @ matMisOn8 @ inv(matPndTo8)

            matPndTo1mis = matMisOn1InPnd @ matPndTo1
            matPndTo2mis = matMisOn2InPnd @ matPndTo2
            matPndTo8mis = matMisOn8InPnd @ matPndTo8

            # this is the ICP-like matrix
            matICP1to8 = self.getOverlapMisalignLikeICP(p1, p8)
            matICP2to8 = self.getOverlapMisalignLikeICP(p2, p8)

            # * but wait, we're in sensor local, transform everything here!
            mat1to8actually = self.getActualMatrixFromGeoManager(p1, p8)
            mat2to8actually = self.getActualMatrixFromGeoManager(p2, p8)
            mat1to2actually = self.getActualMatrixFromGeoManager(p1, p2)

            # this is mat1to2 as seen from the MISALIGNED sensor1!
            # I don't know these, but this is just to see if I found the correct matrix.
            mat1To8actuallyIn1mis = inv(matPndTo1mis) @ mat1to8actually @ (matPndTo1mis)
            mat2To8actuallyIn2mis = inv(matPndTo2mis) @ mat2to8actually @ (matPndTo2mis)
            mat1to2actuallyIn1mis = inv(matPndTo1mis) @ mat1to2actually @ (matPndTo1mis)

            # these are the matrices m4 and m5 and their combination!
            # this is the matrix the ICP finds in the frame of reference of MISALIGNED sensor 0
            mat1to8idealIn1 = inv(matPndTo1) @ mat1to8ideal @ (matPndTo1)
            mat2to8idealIn2 = inv(matPndTo2) @ mat2to8ideal @ (matPndTo2)

            # this is the trick! transform everything to sensor BEFORE you apply the ICP matrix to the ideal
            matICP1to8In1 = inv(matPndTo1) @ matICP1to8 @ (matPndTo1)
            # careful, this should be in sensor TWO, not one, because this is still local to 2!
            matICP2to8In2 = inv(matPndTo2) @ matICP2to8 @ (matPndTo2)

            # apply ICP matrix to ideal IN SENSOR 1/2!
            mat1to8TotalIn1 = matICP1to8In1 @ mat1to8idealIn1
            mat2to8TotalIn2 = matICP2to8In2 @ mat2to8idealIn2

            print(f'compare actual and constructed for 1-8:')
            self.dMat(mat1To8actuallyIn1mis, mat1to8TotalIn1)
            print(f'compare actual and constructed for 2-8:')
            self.dMat(mat2To8actuallyIn2mis, mat2to8TotalIn2)

            # alright, if I want to multiply m4 and m5, they both have to live in the same
            # system of reference, otherwise I just get junk.

            # careful, I can't use m1to2Ideal, because there is misalignment on p2 and p8
            # that we don't know. therefore, this transformation matrix has no misalignment
            # and doesn't work.
            # there are matrices that do have misalignment and point from A to B,
            # they are our overlap matrices!

            # so, use the overlap matrices themselves to transform the matrices
            # I know this base transform is pointless, but for completeness sake leave it in!
            mat2to8TotalIn8 = mat2to8TotalIn2 @ mat2to8TotalIn2 @ inv(mat2to8TotalIn2)

            # this is the things that's been missing for so long! I know the base transform looks
            # inverted, but that's because I need m8to1, and I only have m1to8. to that's fine.
            mat2to8TotalIn1 = inv(mat1to8TotalIn1) @ mat2to8TotalIn8 @ mat1to8TotalIn1

            # they are now both in the system of sensor 1
            mat1to2totalIn1 = inv(mat2to8TotalIn1) @ mat1to8TotalIn1

            print('AND THE GREAT FINALE:')
            print(f'compare actual and constructed for 1-2:')
            self.dMat(mat1to2actuallyIn1mis, mat1to2totalIn1)

            """
            Oh my god yes, finally! This is it! This works! I can finally compute the combined matrices in a stringent way!
            """

        """
        now, the overlap misalignments are in PND global, as they should, but to apply them to an ideal overlap,
        they must be transformed into the system of the first sensor of the overlap
        """
        
        #! keep cheating, just for now:
        p1 = self.modulePath + '/sensor_1'
        p2 = self.modulePath + '/sensor_2'
        matPndTo1 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
        matMisOn1 = np.array(misalignMatrices[p1]).reshape(4, 4)
        matMisOn1InPnd = matPndTo1 @ matMisOn1 @ inv(matPndTo1)
        matPndTo1mis = matMisOn1InPnd @ matPndTo1
        mat1to2actually = self.getActualMatrixFromGeoManager(p1, p2)
        mat1to2actuallyIn1mis = inv(matPndTo1mis) @ mat1to2actually @ (matPndTo1mis)

        print(f'while you refine:')
        self.dMat(mat1to2actuallyIn1mis, m1t2icp)

    #! we don't have some of these matrices, this is cheating and should go in the comparer
    def getOverlapMisalignLikeICP(self, p1, p2):
        with open('input/misMatrices/misMat-sensors-1.00.json') as f:
            misalignMatrices = json.load(f)

        # TODO: include a filter for overlapping sensors!
        # this code works for any sensor pair (which is good),
        # which doesn't make sense because I want overlap matrices!

        matPndTo0 = np.array(self.idealDetectorMatrices[p1]).reshape(4, 4)
        matPndTo5 = np.array(self.idealDetectorMatrices[p2]).reshape(4, 4)

        # I don't have these!
        matMisOn0 = np.array(misalignMatrices[p1]).reshape(4, 4)
        matMisOn5 = np.array(misalignMatrices[p2]).reshape(4, 4)

        matMisOn0InPnd = matPndTo0 @ matMisOn0 @ inv(matPndTo0)
        matMisOn5InPnd = matPndTo5 @ matMisOn5 @ inv(matPndTo5)

        # this is the ICP like matrix
        mat0to5MisInPnd = matMisOn5InPnd @ inv(matMisOn0InPnd)
        return mat0to5MisInPnd

    #! we don't have some of these matrices, this is cheating and should go in the comparer
    def getActualMatrixFromGeoManager(self, p1, p2):
        with open('input/detectorMatrices-sensors-1.00.json') as f:
            totalMatrices = json.load(f)
        matP1toP2 = self.getMatrixP1ToP2fromMatrixDict(p1, p2, totalMatrices)
        return matP1toP2

    #! this doesn't belong here, move it to the comparer or delete it!
    def dMat(self, mat1, mat2):
        mat1 = np.round(mat1, 5)
        mat2 = np.round(mat2, 5)
        dmat = (mat1 - mat2)*1e4

        print('=== dmat ===')
        print(f'mat1:\n{mat1}')
        print(f'mat2:\n{mat2}')
        print(f'dmat *1e4:\n{dmat}')
        print('=== end ===')
