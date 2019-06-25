#!/bin/bash

align=""
misalign=""

matpath="/home/roklasen/PandaRoot/macro/detectors/lmd/geo/misMatrices/"
matid="misMat-identity-1.00.root"

box025=${matpath}"misMat-box-0.25.root"
box050=${matpath}"misMat-box-0.50.root"
box100=${matpath}"misMat-box-1.00.root"
box200=${matpath}"misMat-box-2.00.root"

combi050=${matpath}"misMat-combi-0.50.root"
combi100=${matpath}"misMat-combi-1.00.root"
combi200=${matpath}"misMat-combi-2.00.root"

run_sims() {
    ./doSimulationReconstruction.py 100000 500 1.5 dpm_elastic
    ./doSimulationReconstruction.py 100000 500 1.5 dpm_elastic --misalignment_matrices_path ${misalign}
    ./doSimulationReconstruction.py 100000 500 1.5 dpm_elastic --alignment_matrices_path ${align}
    ./doSimulationReconstruction.py 100000 500 1.5 dpm_elastic --misalignment_matrices_path ${misalign} --alignment_matrices_path ${align}
}

align=${box025}
misalign=${align}

run_sims